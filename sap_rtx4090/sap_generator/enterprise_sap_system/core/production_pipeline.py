#!/usr/bin/env python3
"""
Production SAP Pipeline - Clean Architecture
=============================================

ARCHITECTURE (sources and their roles):
| Source              | Role                                          |
|---------------------|-----------------------------------------------|
| Protocol Extraction | GROUND TRUTH for all values and methods       |
| Knowledge Graph     | CONTEXT ONLY (regulatory, scientific)         |
| RAG                 | PROSE STYLE ONLY (numbers stripped)           |

CRITICAL PRINCIPLES:
1. EXTRACTION → All methods come from protocol extraction (sectioned, with confidence)
2. KNOWLEDGE GRAPH → Provides regulatory context (ICH E9, FDA guidance)
                   → Never overrides protocol-specified methods
3. RAG → Sanitized examples for writing style only
4. MISSING DATA → Flag [NEEDS REVIEW], never infer
5. ESTIMANDS → Required per ICH E9 R1

REMOVED (2025-01 refactor):
- DrugClassifier: Inferred methods from drug class
- StudyDesignClassifier: Keyword-based inference
- HybridDesignClassifier: LLM+rules hybrid that still inferred
- All method-forcing rules

References:
- ICH E9 R1: Estimands framework
- Gamble et al. 2017: SAP checklist (55 items)
- SELF-RAG (ICLR 2024 Oral): Reflection tokens for factuality
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# =============================================================================
# CORE IMPORTS - NO FALLBACKS (fail fast if missing)
# =============================================================================

# Required components - will fail if not available
from .sectioned_extractor import SectionedProtocolExtractor, create_sectioned_extractor
from .two_pass_extractor import TwoPassExtractor, TwoPassExtractionResult
from .tiered_llm import TieredLLMClient
from .rag_sanitizer import RAGSanitizer
from .fact_verifier import FactVerifier, VerificationResult
from .extraction_schema import ExtractedProtocolFacts, from_claude_extraction
from .decision_engine import OncologyDecisionEngine
from .sap_validator import SAPValidator
from ..rag.vector_store import create_vector_store

# Optional: Knowledge graph (context only, not critical)
try:
    from .knowledge_rule_engine import KnowledgeRuleEngine
except ImportError:
    KnowledgeRuleEngine = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MethodConstraints:
    """Method constraints extracted from protocol (not inferred)."""
    primary_test: str = ""
    primary_test_params: Dict[str, Any] = field(default_factory=dict)
    sensitivity_methods: List[str] = field(default_factory=list)
    interim_method: Optional[str] = ""
    alpha_spending: Optional[str] = ""
    conditions_detected: List[str] = field(default_factory=list)

    # Descriptive study fields
    descriptive_methods: List[str] = field(default_factory=list)
    binary_methods: List[str] = field(default_factory=list)
    sample_size_approach: str = ""

    # Neoadjuvant fields
    time_origin: str = ""
    neoadjuvant_methods: List[str] = field(default_factory=list)
    pathologic_criteria: str = ""


@dataclass
class GenerationResult:
    """Final SAP generation result."""
    success: bool
    sap_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)
    facts: Dict[str, Any] = field(default_factory=dict)
    constraints: Optional[MethodConstraints] = None
    verification: Optional[VerificationResult] = None
    extraction_confidence: Dict[str, float] = field(default_factory=dict)
    needs_review: List[str] = field(default_factory=list)
    regeneration_count: int = 0
    warnings: List[str] = field(default_factory=list)
    error: str = ""


# =============================================================================
# PRODUCTION PIPELINE
# =============================================================================

class ProductionSAPPipeline:
    """
    Production-grade SAP generation with clean architecture.

    Architecture:
    1. SECTIONED EXTRACTION → Structured facts with confidence scores
    2. KNOWLEDGE GRAPH → Scientific context (not method selection)
    3. RAG → Sanitized examples (prose style only)
    4. GENERATION → Constrained prompts with source attribution
    5. VERIFICATION → SELF-RAG pattern with correction loop
    """

    # SAP sections to generate (per ICH E9 R1 + Gamble et al. 2017)
    # Tuple: (key, title, complexity) where complexity determines model choice
    # "complex" = Opus 4.5 (slow but accurate), "simple" = Haiku/GPT-4o-mini (fast)
    SECTIONS = [
        ('introduction', 'Introduction', 'simple'),
        ('objectives', 'Study Objectives and Endpoints', 'simple'),
        ('estimands', 'Estimands', 'complex'),  # ICH E9 R1 - needs accuracy
        ('study_design', 'Study Design', 'simple'),
        ('sample_size', 'Sample Size Determination', 'complex'),  # Math-heavy
        ('analysis_populations', 'Analysis Populations', 'simple'),
        ('statistical_methods', 'Statistical Methods', 'complex'),  # Critical section
        ('interim_analysis', 'Interim Analysis', 'complex'),  # Math-heavy
        ('sensitivity_analysis', 'Sensitivity Analyses', 'complex'),  # Technical
        ('missing_data', 'Missing Data Handling', 'simple'),
        ('multiplicity', 'Multiplicity Adjustment', 'complex'),  # Math-heavy
        ('safety', 'Safety Analyses', 'simple'),
    ]

    # Cache for extracted protocol facts (avoid re-parsing same PDF)
    _extraction_cache: Dict[str, Tuple[Dict, Dict]] = {}

    def __init__(self, max_regenerations: int = 2):
        """Initialize production pipeline - NO FALLBACKS."""
        self.max_regenerations = max_regenerations

        print("[ProductionPipeline] Initializing (no fallbacks)...")

        # 1. LLM Client (required)
        self.llm = TieredLLMClient()
        self.fast_llm = TieredLLMClient()  # Second client for fast sections
        print("[ProductionPipeline] ✓ LLM client (tiered: Claude → OpenAI → Groq)")

        # 2. Two-Pass Extractor (primary) + Sectioned Extractor (fallback)
        self.two_pass_extractor = TwoPassExtractor()
        print("[ProductionPipeline] ✓ TwoPassExtractor (primary)")
        self.sectioned_extractor = create_sectioned_extractor(llm_client=self.llm)
        print("[ProductionPipeline] ✓ SectionedProtocolExtractor (fallback)")

        # 3. Decision Engine (required - routes response criteria + methods)
        chromadb_path = str(Path(__file__).parent.parent.parent / "data" / "chroma_db")
        self.decision_engine = OncologyDecisionEngine(chromadb_path=chromadb_path)
        print("[ProductionPipeline] ✓ OncologyDecisionEngine")

        # 4. SAP Validator (required - pre/post validation)
        self.sap_validator = SAPValidator(strict_mode=True)
        print("[ProductionPipeline] ✓ SAPValidator (strict)")

        # 5. RAG (required - prose style examples)
        self.rag = create_vector_store()
        print("[ProductionPipeline] ✓ ChromaDB RAG")

        # 6. RAG Sanitizer (required)
        self.sanitizer = RAGSanitizer(aggressive=True)
        print("[ProductionPipeline] ✓ RAG Sanitizer")

        # 7. Fact Verifier (required - SELF-RAG pattern)
        self.verifier = FactVerifier()
        print("[ProductionPipeline] ✓ Fact Verifier")

        # 8. Knowledge Graph (optional - context only)
        self.knowledge_graph = None
        if KnowledgeRuleEngine:
            try:
                self.knowledge_graph = KnowledgeRuleEngine()
                print("[ProductionPipeline] ✓ KnowledgeRuleEngine (optional)")
            except Exception:
                pass  # Not critical

        print("[ProductionPipeline] Ready")

    def generate(self, protocol_text: str, pdf_path: str = None, parallel: bool = True, **kwargs) -> GenerationResult:
        """
        Generate SAP using clean production pipeline.

        Args:
            protocol_text: Full protocol text
            pdf_path: Path to PDF file for Vision-based section parsing
            parallel: Enable parallel processing for faster generation (default: True)
            **kwargs: Additional arguments (nct_id, etc.)

        Steps:
        1. Extract facts by section with confidence scores
        1.5 Pre-generation validation
        2-4. [PARALLEL] Scientific context + Constraints + RAG queries
        5. [PARALLEL] Generate 12 sections simultaneously
        6-7. Verify and validate
        """
        try:
            # =================================================================
            # STEP 1: TWO-PASS EXTRACTION (discovery then extraction)
            # =================================================================
            print("\n[Step 1] TWO-PASS EXTRACTION (discovery → extraction)...")
            facts, section_results = self._extract_facts_two_pass(protocol_text, pdf_path=pdf_path)

            # Log extraction quality (handle None confidences)
            confidences = [r.confidence for r in section_results.values() if r.confidence is not None]
            overall_confidence = sum(confidences) / len(confidences) if confidences else 0
            print(f"[Step 1] Overall extraction confidence: {overall_confidence:.0%}")

            # Log ALL extracted fields for diagnostics
            print("\n" + "="*60)
            print("[EXTRACTION DIAGNOSTICS] All extracted facts:")
            print("="*60)
            critical_fields = [
                'nct_id', 'sample_size', 'allocation_ratio', 'power', 'hazard_ratio', 'expected_hazard_ratio',
                'treatment_setting', 'disease_type', 'phase', 'drug_name', 'comparator',
                'primary_endpoint', 'secondary_endpoints', 'co_primary_endpoints',
                'statistical_method', 'test_sidedness',
                'stratification_factors', 'stratification_factor_levels',
                'has_interim_analysis', 'num_interim_analyses', 'interim_events', 'final_events',
                'alpha_spending_function', 'alpha_at_interim', 'alpha_at_final',
                'has_multiplicity', 'hypotheses_list', 'alpha_per_hypothesis', 'testing_sequence',
                'itt_definition', 'censoring_rules',
                'estimand_variable', 'intercurrent_events'
            ]
            for field in critical_fields:
                value = facts.get(field)
                status = "✓" if value and str(value) not in ['[NOT FOUND]', 'null', 'None', '[]', '{}'] else "✗"
                print(f"  {status} {field}: {value}")
            print("="*60 + "\n")

            # Collect fields needing review
            needs_review = []
            for section_name, result in section_results.items():
                if result.needs_review:
                    needs_review.extend(result.needs_review)
                    print(f"[Step 1] ⚠ {section_name} NEEDS REVIEW: {result.needs_review}")

            # =================================================================
            # STEP 1.5: PRE-GENERATION VALIDATION (catch errors early)
            # =================================================================
            if self.sap_validator:
                print("\n[Step 1.5] Running pre-generation validation...")
                pre_validation = self.sap_validator.validate_before_generation(facts)

                if not pre_validation['valid']:
                    print(f"[Step 1.5] ⚠ Pre-validation found {len(pre_validation['errors'])} errors:")
                    for error in pre_validation['errors']:
                        print(f"  - {error}")
                        needs_review.append(error)

                if pre_validation['warnings']:
                    print(f"[Step 1.5] Warnings: {len(pre_validation['warnings'])}")
                    for warning in pre_validation['warnings']:
                        print(f"  - {warning}")

                # Apply auto-fixes if available
                if pre_validation.get('auto_fixes'):
                    print(f"[Step 1.5] Applying {len(pre_validation['auto_fixes'])} auto-fixes...")
                    for fix in pre_validation['auto_fixes']:
                        field = fix.get('field')
                        new_value = fix.get('new_value')
                        if field and new_value is not None:
                            facts[field] = new_value
                            print(f"  - Fixed {field}: {new_value}")

            # =================================================================
            # STEPS 2-4: PARALLEL CONTEXT GATHERING
            # Scientific context, decision engine, and RAG can run simultaneously
            # =================================================================
            scientific_context = ""
            conditions = []
            sanitized_examples = {}
            constraints = None

            if parallel:
                print("\n[Steps 2-4] PARALLEL context gathering...")

                def get_scientific_context():
                    """Get scientific context from knowledge graph."""
                    ctx = ""
                    conds = []
                    if self.knowledge_graph:
                        conds = list(self.knowledge_graph.detect_conditions(facts))
                        ctx = self.knowledge_graph.get_context_for_generation(facts)
                    return ctx, conds

                def get_rag_examples():
                    """Get sanitized RAG examples."""
                    return self._get_sanitized_examples(facts, parallel=True)

                with ThreadPoolExecutor(max_workers=2) as executor:
                    # Submit parallel tasks
                    future_context = executor.submit(get_scientific_context)
                    future_rag = executor.submit(get_rag_examples)

                    # Collect results
                    scientific_context, conditions = future_context.result()
                    sanitized_examples = future_rag.result()

                print(f"[Step 2] Scientific context: {len(scientific_context)} chars, conditions: {conditions}")
                print(f"[Step 4] RAG examples: {sum(len(v) for v in sanitized_examples.values())} total")

                # Build constraints (quick, doesn't need parallelization)
                constraints = self._build_constraints_from_extraction(facts, conditions)
                print(f"[Step 3] Primary test: {constraints.primary_test}")

            else:
                # SEQUENTIAL fallback
                print("\n[Step 2] Getting scientific context...")
                if self.knowledge_graph:
                    conditions = list(self.knowledge_graph.detect_conditions(facts))
                    print(f"[Step 2] Conditions detected: {conditions}")
                    scientific_context = self.knowledge_graph.get_context_for_generation(facts)
                    print(f"[Step 2] Generated context ({len(scientific_context)} chars)")
                    method_ctx = self.knowledge_graph.get_method_context(facts)
                    for note in method_ctx.get('discrepancy_notes', []):
                        print(f"[Step 2] {note['severity'].upper()}: {note['observation'][:80]}...")

                print("\n[Step 3] Building method constraints from extraction...")
                constraints = self._build_constraints_from_extraction(facts, conditions)
                print(f"[Step 3] Primary test: {constraints.primary_test}")

                print("\n[Step 4] Getting sanitized RAG examples...")
                sanitized_examples = self._get_sanitized_examples(facts, parallel=False)
                print(f"[Step 4] Retrieved {sum(len(v) for v in sanitized_examples.values())} examples")

            # =================================================================
            # STEP 3.5: DECISION ENGINE DISABLED
            # No defaults - extraction failures should be explicit [NOT FOUND]
            # =================================================================
            print("\n[Step 3.5] Decision engine defaults DISABLED - using extraction only")

            # =================================================================
            # STEP 5: GENERATE SECTIONS (PARALLEL - biggest speedup!)
            # =================================================================
            print("\n[Step 5] Generating SAP sections...")
            sections = self._generate_all_sections(
                facts, constraints, sanitized_examples, scientific_context,
                parallel=parallel, max_workers=6  # 6 concurrent LLM calls
            )

            # Assemble full SAP
            sap_text = self._assemble_sap(sections, facts)

            # =================================================================
            # STEP 5.5: INTERNAL CONSISTENCY CHECK
            # Before outputting [NEEDS REVIEW], check if value exists elsewhere
            # =================================================================
            sap_text = self._ensure_internal_consistency(sap_text, facts)

            # =================================================================
            # STEP 5.6: DIRECT INJECTION OF FACTUAL FIELDS
            # NO LLM - programmatic replacement of known correct values
            # This catches cases where LLM generated wrong defaults
            # =================================================================
            print("\n[Step 5.6] Direct injection of factual fields...")
            sap_text = self._direct_inject_facts(sap_text, facts)

            # =================================================================
            # STEP 6: VERIFY (SELF-RAG pattern)
            # =================================================================
            print("\n[Step 6] Verifying against extracted facts...")
            verification, sap_text, regeneration_count = self._verify_and_correct(
                sap_text, facts, constraints
            )

            if verification and verification.passed:
                print(f"[Step 6] ✓ Verification PASSED (score: {verification.score:.2f})")
            else:
                print(f"[Step 6] ⚠ Verification completed with issues")

            # =================================================================
            # STEP 7: POST-GENERATION VALIDATION (catch output errors)
            # =================================================================
            warnings = []
            if self.sap_validator:
                print("\n[Step 7] Running post-generation validation...")
                post_validation = self.sap_validator.validate_after_generation(sap_text, facts)

                if not post_validation['valid']:
                    print(f"[Step 7] ⚠ Post-validation found {len(post_validation['errors'])} errors:")
                    for error in post_validation['errors']:
                        print(f"  - {error}")
                        needs_review.append(error)

                if post_validation.get('warnings'):
                    print(f"[Step 7] Warnings: {len(post_validation['warnings'])}")
                    for warning in post_validation['warnings']:
                        print(f"  - {warning}")
                        warnings.append(warning)

                # Report confidence
                if post_validation.get('overall_confidence'):
                    print(f"[Step 7] Overall confidence: {post_validation['overall_confidence']:.0%}")

                # Report sections needing human review
                if post_validation.get('human_review_sections'):
                    print(f"[Step 7] Sections needing human review:")
                    for section in post_validation['human_review_sections']:
                        print(f"  - {section}")
                        needs_review.append(f"Review section: {section}")

            return GenerationResult(
                success=True,
                sap_text=sap_text,
                sections=sections,
                facts=facts,
                constraints=constraints,
                verification=verification,
                extraction_confidence={
                    name: r.confidence for name, r in section_results.items()
                },
                needs_review=needs_review,
                regeneration_count=regeneration_count,
                warnings=warnings
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return GenerationResult(success=False, error=str(e))

    def _extract_facts_sectioned(
        self,
        protocol_text: str,
        pdf_path: str = None,
        use_cache: bool = True
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract facts using sectioned extraction with confidence scores.
        NO FALLBACKS - will raise if extraction fails.

        Args:
            use_cache: If True, cache extraction results by PDF path or text hash
        """
        # Generate cache key
        import hashlib
        if pdf_path:
            cache_key = pdf_path
        else:
            cache_key = hashlib.md5(protocol_text[:5000].encode()).hexdigest()

        # Check cache
        if use_cache and cache_key in self._extraction_cache:
            print(f"[Extraction] ✓ Using cached extraction (key: {cache_key[:20]}...)")
            return self._extraction_cache[cache_key]

        # Extract (slow operation)
        extracted_facts, section_results = self.sectioned_extractor.extract_all_sections(
            protocol_text,
            pdf_path=pdf_path
        )
        # Convert to flat dict for generation
        facts = extracted_facts.to_flat_dict() if hasattr(extracted_facts, 'to_flat_dict') else {}
        facts['raw_text'] = protocol_text.lower()

        # Cache result
        if use_cache:
            self._extraction_cache[cache_key] = (facts, section_results)
            print(f"[Extraction] Cached for future use (key: {cache_key[:20]}...)")

        return facts, section_results

    def _extract_facts_two_pass(
        self,
        protocol_text: str,
        pdf_path: str = None,
        use_cache: bool = True
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract facts using TWO-PASS extraction (discovery then extraction).

        This is the PRODUCTION extraction method that:
        1. Discovers ALL statistical elements in the protocol
        2. Extracts detailed information for each element

        Returns same format as _extract_facts_sectioned for compatibility.
        """
        import hashlib

        # Generate cache key
        if pdf_path:
            cache_key = f"twopass_{pdf_path}"
        else:
            cache_key = f"twopass_{hashlib.md5(protocol_text[:5000].encode()).hexdigest()}"

        # Check cache
        if use_cache and cache_key in self._extraction_cache:
            print(f"[TwoPass] ✓ Using cached extraction (key: {cache_key[:30]}...)")
            return self._extraction_cache[cache_key]

        # Run two-pass extraction
        protocol_id = Path(pdf_path).stem if pdf_path else "protocol"
        result = self.two_pass_extractor.extract(
            protocol_text,
            protocol_id=protocol_id,
            max_elements=50,
            priority_threshold=3,
            verbose=True
        )

        # Convert TwoPassExtractionResult to facts dict
        facts = self._convert_two_pass_to_facts(result)
        facts['raw_text'] = protocol_text.lower()

        # Create section_results compatible format
        # The pipeline expects section_results to have .confidence and .needs_review
        @dataclass
        class SectionResult:
            confidence: float
            needs_review: List[str]

        section_results = {}
        categories_seen = set()

        for name, elem in result.extracted_data.items():
            cat = elem.category
            if cat not in categories_seen:
                categories_seen.add(cat)
                # Create a section result for each category
                section_results[cat] = SectionResult(
                    confidence=elem.confidence,
                    needs_review=elem.notes if elem.confidence < 0.7 else []
                )

        # Add validation flags as needs_review items
        if result.validation_flags:
            section_results['_validation'] = SectionResult(
                confidence=0.5,
                needs_review=result.validation_flags
            )

        # Cache result
        if use_cache:
            self._extraction_cache[cache_key] = (facts, section_results)
            print(f"[TwoPass] Cached for future use (key: {cache_key[:30]}...)")

        return facts, section_results

    def _convert_two_pass_to_facts(self, result: TwoPassExtractionResult) -> Dict[str, Any]:
        """
        Convert TwoPassExtractionResult to flat facts dict for SAP generation.

        Maps two-pass extracted elements to the fields expected by generation prompts.
        """
        facts = {}

        # Track what we've extracted
        facts['_two_pass_discovery_count'] = len(result.discovered_elements)
        facts['_two_pass_extraction_count'] = len(result.extracted_data)
        facts['_two_pass_categories'] = result.metadata.get('categories_found', [])

        # Process each extracted element
        for element_name, elem in result.extracted_data.items():
            data = elem.extracted_data
            cat = elem.category

            # Study Design elements
            if cat == 'study_design':
                if 'design_type' in data or 'type' in data:
                    facts['design_type'] = data.get('design_type') or data.get('type')
                if 'blinding' in data or 'masking' in data:
                    facts['blinding_type'] = data.get('blinding') or data.get('masking')
                if 'phase' in data:
                    facts['phase'] = data.get('phase')
                if 'duration' in data:
                    facts['study_duration'] = data.get('duration')
                if 'treatment_arm' in data or 'treatment' in data or 'drug' in data:
                    facts['drug_name'] = data.get('treatment_arm') or data.get('treatment') or data.get('drug')
                if 'comparator' in data or 'control' in data:
                    facts['comparator'] = data.get('comparator') or data.get('control')
                if 'allocation_ratio' in data or 'randomization_ratio' in data:
                    facts['allocation_ratio'] = data.get('allocation_ratio') or data.get('randomization_ratio')
                # Disease/Indication fields often in study_design
                if 'disease' in data or 'indication' in data:
                    facts['disease_type'] = data.get('disease') or data.get('indication')
                    facts['indication'] = data.get('indication') or data.get('disease')
                if 'tumor_type' in data or 'cancer_type' in data:
                    facts['tumor_type'] = data.get('tumor_type') or data.get('cancer_type')
                if 'histology' in data:
                    facts['histology'] = data.get('histology')
                if 'stage' in data or 'disease_stage' in data:
                    facts['disease_stage'] = data.get('stage') or data.get('disease_stage')
                if 'biomarker' in data or 'biomarker_status' in data:
                    facts['biomarker_status'] = data.get('biomarker') or data.get('biomarker_status')
                if 'setting' in data or 'treatment_setting' in data:
                    facts['treatment_setting'] = data.get('setting') or data.get('treatment_setting')
                if 'nct_id' in data or 'nct' in data:
                    facts['nct_id'] = data.get('nct_id') or data.get('nct')
                if 'protocol_number' in data or 'protocol_id' in data:
                    facts['protocol_number'] = data.get('protocol_number') or data.get('protocol_id')
                # Also extract from element name if it contains useful info
                elem_lower = element_name.lower()
                if 'phase' in elem_lower and not facts.get('phase'):
                    # Try to extract phase from element name like "Phase 3 study"
                    import re
                    phase_match = re.search(r'phase\s*(\d+[ab]?)', elem_lower, re.IGNORECASE)
                    if phase_match:
                        facts['phase'] = f"Phase {phase_match.group(1)}"

            # Endpoints
            elif cat == 'endpoints':
                if 'primary' in element_name.lower() or data.get('type') == 'primary':
                    if 'definition' in data:
                        facts['primary_endpoint'] = data.get('definition')
                    elif 'endpoint' in data:
                        facts['primary_endpoint'] = data.get('endpoint')
                    if 'analysis_method' in data:
                        facts['statistical_method'] = data.get('analysis_method')
                    if 'estimand' in data:
                        facts['estimand_variable'] = data.get('estimand')
                elif 'secondary' in element_name.lower() or data.get('type') == 'secondary':
                    if 'secondary_endpoints' not in facts:
                        facts['secondary_endpoints'] = []
                    endpoint_def = data.get('definition') or data.get('endpoint') or element_name
                    facts['secondary_endpoints'].append(endpoint_def)

            # Populations
            elif cat == 'populations':
                pop_name = data.get('name', element_name)
                pop_def = data.get('definition', '')
                if 'itt' in pop_name.lower() or 'intent' in pop_name.lower():
                    facts['itt_definition'] = pop_def or pop_name
                elif 'fas' in pop_name.lower() or 'full analysis' in pop_name.lower():
                    facts['fas_definition'] = pop_def or pop_name
                    facts['primary_analysis_population'] = 'FAS'
                elif 'safety' in pop_name.lower():
                    facts['safety_population_definition'] = pop_def or pop_name
                elif 'per protocol' in pop_name.lower() or 'pp' in pop_name.lower():
                    facts['per_protocol_definition'] = pop_def or pop_name
                # Store n_expected if available
                if 'n_expected' in data:
                    facts['expected_n_' + pop_name.lower().replace(' ', '_')] = data['n_expected']

            # Sample Size
            elif cat == 'sample_size':
                # Multiple ways sample size might be stored
                if 'total' in data or 'total_n' in data or 'n' in data or 'sample_size' in data:
                    n = data.get('total') or data.get('total_n') or data.get('n') or data.get('sample_size')
                    # Ensure n is an integer - Claude must return numbers, not text
                    if isinstance(n, int):
                        facts['sample_size'] = n
                        facts['sample_size_total'] = n
                    elif isinstance(n, str) and n.isdigit():
                        facts['sample_size'] = int(n)
                        facts['sample_size_total'] = int(n)
                    # Skip non-numeric values - extraction prompt should enforce integers
                if 'per_arm' in data or 'n_per_arm' in data:
                    facts['sample_size_per_arm'] = data.get('per_arm') or data.get('n_per_arm')
                if 'power' in data or 'statistical_power' in data:
                    facts['power'] = data.get('power') or data.get('statistical_power')
                if 'alpha' in data or 'significance_level' in data or 'type_i_error' in data:
                    alpha = data.get('alpha') or data.get('significance_level') or data.get('type_i_error')
                    facts['alpha'] = alpha
                    facts['overall_alpha'] = alpha
                if 'assumptions' in data:
                    assumptions = data.get('assumptions', {})
                    if 'hazard_ratio' in assumptions or 'hr' in assumptions or 'expected_hr' in assumptions:
                        facts['expected_hazard_ratio'] = assumptions.get('hazard_ratio') or assumptions.get('hr') or assumptions.get('expected_hr')
                    if 'median_survival' in assumptions or 'median_os' in assumptions:
                        facts['median_survival'] = assumptions.get('median_survival') or assumptions.get('median_os')
                    if 'effect_size' in assumptions:
                        facts['effect_size'] = assumptions.get('effect_size')
                    if 'dropout' in assumptions or 'dropout_rate' in assumptions:
                        facts['dropout_rate'] = assumptions.get('dropout') or assumptions.get('dropout_rate')
                # Direct fields from data
                if 'hazard_ratio' in data or 'hr' in data or 'expected_hr' in data:
                    facts['expected_hazard_ratio'] = data.get('hazard_ratio') or data.get('hr') or data.get('expected_hr')
                if 'events' in data or 'required_events' in data:
                    facts['required_events'] = data.get('events') or data.get('required_events')

            # Hypotheses
            elif cat == 'hypotheses':
                if 'null' in data:
                    facts['null_hypothesis'] = data.get('null')
                if 'alternative' in data:
                    facts['alternative_hypothesis'] = data.get('alternative')
                if 'type' in data:
                    hyp_type = data.get('type', '').lower()
                    if 'superiority' in hyp_type:
                        facts['hypothesis_type'] = 'superiority'
                    elif 'non-inferiority' in hyp_type:
                        facts['hypothesis_type'] = 'non-inferiority'
                        if 'margin' in data:
                            facts['non_inferiority_margin'] = data.get('margin')
                if 'alpha_allocated' in data:
                    facts['alpha_per_hypothesis'] = data.get('alpha_allocated')

            # Statistical Methods
            elif cat == 'statistical_methods':
                if 'method' in data or 'test' in data:
                    facts['statistical_method'] = data.get('method') or data.get('test')
                if 'sidedness' in data:
                    facts['test_sidedness'] = data.get('sidedness')
                if 'stratification' in data:
                    facts['stratification_factors'] = data.get('stratification')

            # Interim Analysis
            elif cat == 'interim_analysis':
                facts['has_interim_analysis'] = True
                if 'num_analyses' in data or 'number' in data:
                    facts['num_interim_analyses'] = data.get('num_analyses') or data.get('number')
                if 'timing' in data or 'events' in data:
                    events = data.get('events') or data.get('timing')
                    if isinstance(events, list):
                        facts['interim_events'] = events
                    else:
                        facts['interim_events'] = [events]
                if 'spending_function' in data or 'alpha_spending' in data:
                    facts['alpha_spending_function'] = data.get('spending_function') or data.get('alpha_spending')
                if 'boundaries' in data:
                    facts['stopping_boundaries'] = data.get('boundaries')

            # Multiplicity
            elif cat == 'multiplicity':
                facts['has_multiplicity'] = True
                if 'method' in data:
                    facts['multiplicity_method'] = data.get('method')
                if 'testing_sequence' in data:
                    facts['testing_sequence'] = data.get('testing_sequence')
                if 'hypotheses' in data:
                    facts['hypotheses_list'] = data.get('hypotheses')

            # Missing Data
            elif cat == 'missing_data':
                if 'handling' in data or 'method' in data:
                    facts['missing_data_handling'] = data.get('handling') or data.get('method')
                if 'censoring_rules' in data:
                    facts['censoring_rules'] = data.get('censoring_rules')

            # Sensitivity Analyses
            elif cat == 'sensitivity_analyses':
                if 'sensitivity_analyses' not in facts:
                    facts['sensitivity_analyses'] = []
                sens_info = {
                    'name': data.get('name', element_name),
                    'method': data.get('method', ''),
                    'purpose': data.get('purpose', '')
                }
                facts['sensitivity_analyses'].append(sens_info)

            # Safety
            elif cat == 'safety':
                if 'ae_definitions' in data:
                    facts['ae_definitions'] = data.get('ae_definitions')
                if 'safety_endpoints' in data:
                    facts['safety_endpoints'] = data.get('safety_endpoints')

            # PRO
            elif cat == 'patient_reported_outcomes':
                if 'pro_instruments' not in facts:
                    facts['pro_instruments'] = []
                pro_info = {
                    'instrument': data.get('instrument', element_name),
                    'domains': data.get('domains', []),
                    'timing': data.get('timing', [])
                }
                facts['pro_instruments'].append(pro_info)

        # Set defaults for missing critical fields
        if not facts.get('has_interim_analysis'):
            facts['has_interim_analysis'] = False
        if not facts.get('has_multiplicity'):
            facts['has_multiplicity'] = False

        # Catch-all: capture any remaining data fields not explicitly mapped
        # This helps ensure we don't miss important extractions
        for element_name, elem in result.extracted_data.items():
            data = elem.extracted_data
            for key, value in data.items():
                # Skip if already mapped or if value is empty
                if key in facts or not value:
                    continue
                # Skip internal fields
                if key.startswith('_') or key in ('raw_response', 'source_text'):
                    continue
                # Map common variations to standard names
                key_lower = key.lower()
                if key_lower not in facts:
                    # Store with original key if not already present
                    facts[key_lower] = value

        return facts

    def _normalize_facts(self, facts: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize field names for consistency."""
        normalized = dict(facts)

        # =====================================================================
        # CRITICAL: Sample size field mapping
        # Extraction uses: sample_size_total, sample_size_per_arm
        # Generation uses: total_sample_size
        # =====================================================================
        if 'sample_size_total' in normalized and normalized['sample_size_total']:
            normalized['total_sample_size'] = normalized['sample_size_total']
            print(f"[Normalize] Mapped sample_size_total -> total_sample_size: {normalized['total_sample_size']}")

        # If only sample_size exists (per-arm), and we have allocation info, calculate total
        if 'total_sample_size' not in normalized or not normalized.get('total_sample_size'):
            sample_size = normalized.get('sample_size')
            sample_size_per_arm = normalized.get('sample_size_per_arm')

            if sample_size_per_arm and isinstance(sample_size_per_arm, list):
                # Use per-arm breakdown
                normalized['total_sample_size'] = sum(sample_size_per_arm)
                print(f"[Normalize] Calculated total_sample_size from per_arm: {normalized['total_sample_size']}")
            elif sample_size and normalized.get('num_arms', 0) > 1:
                # sample_size is per-arm, multiply by number of arms
                num_arms = normalized.get('num_arms', 2)
                normalized['total_sample_size'] = int(sample_size) * num_arms
                print(f"[Normalize] Calculated total_sample_size: {sample_size} x {num_arms} = {normalized['total_sample_size']}")

        # =====================================================================
        # CRITICAL: Sidedness normalization - NEVER default to one-sided
        # The extraction should determine sidedness, not defaults
        # =====================================================================
        # Collect all possible sidedness sources
        sidedness = None
        sidedness_sources = [
            normalized.get('test_sidedness'),
            normalized.get('alpha_sidedness'),
            normalized.get('sidedness'),
        ]
        # Also check nested alpha dict
        alpha_dict = normalized.get('alpha')
        if isinstance(alpha_dict, dict):
            sidedness_sources.append(alpha_dict.get('sidedness'))

        # Use first non-null sidedness found
        for src in sidedness_sources:
            if src and src not in ('', None, '[NOT FOUND]', '[NEEDS REVIEW]'):
                sidedness = src.lower().strip()
                break

        if sidedness:
            # Normalize and propagate to all sidedness fields
            normalized['test_sidedness'] = sidedness
            normalized['alpha_sidedness'] = sidedness
            print(f"[Normalize] Sidedness extracted: {sidedness}")
        else:
            # LEAVE AS NONE - do NOT default to one-sided
            # Generation templates should handle missing sidedness explicitly
            print(f"[Normalize] WARNING: No sidedness found in extraction - will need review")

        # =====================================================================
        # CRITICAL: Primary analysis population (FAS vs ITT)
        # =====================================================================
        primary_pop = normalized.get('primary_analysis_population', '')
        if not primary_pop or primary_pop in ('[NOT FOUND]', '[NEEDS REVIEW]'):
            # Check other sources
            if normalized.get('fas_definition'):
                normalized['primary_analysis_population'] = 'FAS'
                print(f"[Normalize] Primary population set to FAS (has FAS definition)")
            elif normalized.get('itt_definition'):
                normalized['primary_analysis_population'] = 'ITT'
                print(f"[Normalize] Primary population set to ITT (has ITT definition)")

        # Event counts
        if 'final_analysis_events' not in normalized and 'final_events' in normalized:
            normalized['final_analysis_events'] = normalized['final_events']
        if 'interim_analysis_events' not in normalized and 'interim_events' in normalized:
            normalized['interim_analysis_events'] = normalized['interim_events']

        # Alpha values
        if 'alpha_at_interim' not in normalized:
            if 'interim_alpha_spent' in normalized and normalized['interim_alpha_spent']:
                if isinstance(normalized['interim_alpha_spent'], list):
                    normalized['alpha_at_interim'] = normalized['interim_alpha_spent'][0] if normalized['interim_alpha_spent'] else None
                else:
                    normalized['alpha_at_interim'] = normalized['interim_alpha_spent']

        if 'alpha_at_final' not in normalized and 'alpha_level' in normalized:
            normalized['alpha_at_final'] = normalized.get('alpha_level')

        # Interim count
        if 'num_interim' not in normalized and 'num_interim_analyses' in normalized:
            normalized['num_interim'] = normalized['num_interim_analyses']

        # =====================================================================
        # CROSS-REFERENCE: Endpoint <-> Estimand
        # If primary_endpoint is missing but estimand has the info, use it
        # =====================================================================
        primary_ep = normalized.get('primary_endpoint', '')
        is_ep_missing = (
            not primary_ep or
            '[NOT' in str(primary_ep) or
            '[NEEDS REVIEW]' in str(primary_ep) or
            '[To be specified]' in str(primary_ep)
        )

        if is_ep_missing:
            # Try estimand sources
            estimand_var = normalized.get('estimand_variable') or normalized.get('primary_estimand_variable')
            if estimand_var and '[NOT' not in str(estimand_var):
                normalized['primary_endpoint'] = estimand_var
                print(f"[CrossRef] Primary endpoint populated from estimand: {estimand_var}")

            # Try primary_estimand object
            primary_estimand = normalized.get('primary_estimand')
            if isinstance(primary_estimand, dict) and primary_estimand.get('variable'):
                normalized['primary_endpoint'] = primary_estimand['variable']
                print(f"[CrossRef] Primary endpoint populated from primary_estimand: {primary_estimand['variable']}")

            # Try co-primary endpoints
            co_primary = normalized.get('co_primary_endpoints') or normalized.get('dual_primary_endpoints')
            if co_primary and isinstance(co_primary, list) and len(co_primary) > 0:
                # Join them for display
                ep_names = [ep.get('name', ep) if isinstance(ep, dict) else str(ep) for ep in co_primary]
                normalized['primary_endpoint'] = ' and '.join(ep_names)
                normalized['is_co_primary'] = True
                print(f"[CrossRef] Primary endpoint populated from co-primary: {normalized['primary_endpoint']}")

        # =====================================================================
        # CROSS-REFERENCE: Estimand <- Endpoint (reverse direction)
        # If estimand_variable is missing but endpoint has the info, use it
        # =====================================================================
        estimand_var = normalized.get('estimand_variable', '')
        is_estimand_missing = (
            not estimand_var or
            '[NOT' in str(estimand_var) or
            '[NEEDS REVIEW]' in str(estimand_var)
        )

        if is_estimand_missing and normalized.get('primary_endpoint'):
            ep = normalized['primary_endpoint']
            if '[NOT' not in str(ep) and '[NEEDS REVIEW]' not in str(ep):
                normalized['estimand_variable'] = ep
                print(f"[CrossRef] Estimand variable populated from endpoint: {ep}")

        return normalized

    def _build_constraints_from_extraction(
        self,
        facts: Dict[str, Any],
        conditions: List[str]
    ) -> MethodConstraints:
        """
        Build method constraints from EXTRACTED protocol data.

        CRITICAL: No inference from drug class or keywords.
        All methods come from protocol extraction.
        """
        constraints = MethodConstraints(conditions_detected=conditions)

        # =================================================================
        # PRIMARY TEST: Use extracted method, never infer
        # =================================================================
        protocol_method = (
            facts.get('statistical_method', '') or
            facts.get('statistical_method_details', '') or
            facts.get('primary_test', '')
        )

        if protocol_method and '[NEEDS REVIEW]' not in protocol_method and '[NOT' not in protocol_method:
            print(f"[Constraints] Using PROTOCOL-SPECIFIED method: {protocol_method}")
            constraints.primary_test = protocol_method
        else:
            print(f"[Constraints] ⚠ Statistical method NOT EXTRACTED - flagging for review")
            constraints.primary_test = "[STATISTICAL METHOD NOT FOUND IN PROTOCOL - NEEDS REVIEW]"

        # =================================================================
        # INTERIM ANALYSIS: Only if extracted from protocol
        # =================================================================
        if facts.get('has_interim_analysis'):
            protocol_interim = (
                facts.get('interim_analysis_method', '') or
                facts.get('alpha_spending_function', '') or
                facts.get('error_spending_function', '')
            )

            if protocol_interim:
                constraints.interim_method = protocol_interim
                constraints.alpha_spending = facts.get('alpha_spending_function', '')
            else:
                constraints.interim_method = "[INTERIM METHOD NOT EXTRACTED - NEEDS REVIEW]"
                constraints.alpha_spending = "[ALPHA SPENDING NOT EXTRACTED - NEEDS REVIEW]"

        # =================================================================
        # SENSITIVITY ANALYSES: From extraction only
        # =================================================================
        protocol_sensitivity = facts.get('sensitivity_methods', []) or facts.get('sensitivity_analyses', [])
        if protocol_sensitivity:
            if isinstance(protocol_sensitivity, list):
                constraints.sensitivity_methods = protocol_sensitivity
            else:
                constraints.sensitivity_methods = [protocol_sensitivity]

        # =================================================================
        # STUDY TYPE: From extraction, affects what methods are appropriate
        # =================================================================
        is_single_arm = facts.get('is_single_arm', False)
        is_pilot = facts.get('is_pilot_study', False)
        treatment_setting = facts.get('treatment_setting', '')

        if is_single_arm or is_pilot:
            constraints.descriptive_methods = [
                "Kaplan-Meier survival curves",
                "Median survival with 95% CI",
                "Survival rates at landmark timepoints"
            ]
            constraints.binary_methods = [
                "Response rate with exact binomial 95% CI (Clopper-Pearson)"
            ]
            if is_pilot:
                constraints.sample_size_approach = "No formal sample size - exploratory study"

        if 'neoadjuvant' in treatment_setting.lower():
            constraints.time_origin = "surgery (not enrollment)"
            constraints.neoadjuvant_methods = [
                "Pathologic response grading per protocol criteria",
                "DFS/OS measured from date of surgery"
            ]
            if facts.get('pathologic_response_criteria'):
                constraints.pathologic_criteria = facts['pathologic_response_criteria']

        return constraints

    # =========================================================================
    # RAG METHODS
    # =========================================================================

    WRONG_INDICATION_PATTERNS = {
        'NSCLC': [r'\bmRCC\b', r'\brenal cell\b', r'\bkidney cancer\b',
                  r'\bhepatocellular\b', r'\bHCC\b', r'\bmelanoma\b'],
        'RCC': [r'\bNSCLC\b', r'\bnon.small cell lung\b', r'\blung cancer\b'],
        'HCC': [r'\bNSCLC\b', r'\blung cancer\b', r'\bmRCC\b', r'\brenal\b'],
    }

    def _get_sanitized_examples(self, facts: Dict[str, Any], parallel: bool = True) -> Dict[str, List[str]]:
        """Get RAG examples with sanitization (prose style only)."""
        examples = {}

        if not self.rag:
            return examples

        # Build query
        query_parts = []
        for key in ['primary_endpoint', 'indication', 'drug_name']:
            value = facts.get(key)
            if value and isinstance(value, str):
                query_parts.append(value)

        query = ' '.join(query_parts) if query_parts else 'oncology phase 3 survival'

        # Get indication for filtering
        indication = str(facts.get('indication') or '').upper()

        # Query each section type
        section_types = ['methods', 'interim_analysis', 'sensitivity_analysis', 'sample_size']

        def query_one_section(section_type: str) -> Tuple[str, List[str]]:
            """Query one section type (thread-safe)."""
            try:
                results = self.rag.query(section_type, query, n_results=5)

                if results:
                    sanitized = []
                    for r in results:
                        # Handle RetrievalResult dataclass (has .content attribute)
                        # or dict (has 'content' key) or string
                        if hasattr(r, 'content'):
                            content = r.content
                        elif isinstance(r, dict):
                            content = r.get('content', str(r))
                        else:
                            content = str(r)

                        # Filter wrong indication
                        if self._has_wrong_indication(content, indication):
                            continue

                        # Sanitize
                        if self.sanitizer:
                            content = self.sanitizer.sanitize(content)

                        sanitized.append(content)
                        if len(sanitized) >= 2:
                            break

                    return section_type, sanitized
                return section_type, []
            except Exception as e:
                print(f"[RAG] Error querying {section_type}: {e}")
                return section_type, []

        if parallel:
            # PARALLEL RAG QUERIES - 4x faster
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(query_one_section, st) for st in section_types]
                for future in as_completed(futures):
                    section_type, results = future.result()
                    if results:
                        examples[section_type] = results
        else:
            # Sequential fallback
            for section_type in section_types:
                _, results = query_one_section(section_type)
                if results:
                    examples[section_type] = results

        return examples

    def _has_wrong_indication(self, content: str, current_indication: str) -> bool:
        """Check if content mentions wrong indication."""
        if not current_indication:
            return False

        patterns = self.WRONG_INDICATION_PATTERNS.get(current_indication, [])
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    # =========================================================================
    # GENERATION METHODS
    # =========================================================================

    def _generate_all_sections(
        self,
        facts: Dict[str, Any],
        constraints: MethodConstraints,
        sanitized_examples: Dict[str, List[str]],
        scientific_context: str = "",
        parallel: bool = True,
        max_workers: int = 12  # Increased from 6 to 12 for max speed
    ) -> Dict[str, str]:
        """
        Generate all SAP sections with tiered model selection.

        Args:
            parallel: If True, generate sections in parallel (faster)
            max_workers: Number of parallel threads (default 12 for max speed)

        Model Selection:
            - "complex" sections: OpenAI GPT-4o (accurate, affordable)
            - "simple" sections: GPT-4o-mini or Groq (fast)
        """
        sections = {}

        if parallel:
            # PARALLEL GENERATION with TIERED MODELS
            complex_count = sum(1 for _, _, c in self.SECTIONS if c == 'complex')
            simple_count = len(self.SECTIONS) - complex_count
            print(f"[Generation] Parallel mode: {complex_count} complex (Opus), {simple_count} simple (fast)")

            def generate_one(section_key: str, section_title: str, complexity: str) -> Tuple[str, str]:
                """Generate one section with appropriate model."""
                examples = sanitized_examples.get(section_key, [])
                if not examples and section_key == 'statistical_methods':
                    examples = sanitized_examples.get('methods', [])

                section_text = self._generate_section(
                    section_key, section_title, facts, constraints, examples, scientific_context,
                    use_fast_model=(complexity == 'simple')
                )
                return section_key, section_text

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all section generations with complexity info
                futures = {
                    executor.submit(generate_one, key, title, complexity): key
                    for key, title, complexity in self.SECTIONS
                }

                # Collect results as they complete
                for future in as_completed(futures):
                    section_key = futures[future]
                    try:
                        key, text = future.result()
                        sections[key] = text
                        print(f"[Generation] ✓ {key}")
                    except Exception as e:
                        print(f"[Generation] ✗ {section_key}: {e}")
                        sections[section_key] = f"## {section_key}\n\n[Generation failed: {e}]"
        else:
            # SEQUENTIAL GENERATION (fallback)
            for section_key, section_title, complexity in self.SECTIONS:
                examples = sanitized_examples.get(section_key, [])
                if not examples and section_key == 'statistical_methods':
                    examples = sanitized_examples.get('methods', [])

                section_text = self._generate_section(
                    section_key, section_title, facts, constraints, examples, scientific_context,
                    use_fast_model=(complexity == 'simple')
                )
                sections[section_key] = section_text

        return sections

    def _generate_section(
        self,
        section_key: str,
        section_title: str,
        facts: Dict[str, Any],
        constraints: MethodConstraints,
        examples: List[str],
        scientific_context: str = "",
        use_fast_model: bool = False
    ) -> str:
        """
        Generate a single section.

        Args:
            use_fast_model: If True, use GPT-4o-mini/Groq for speed (simple sections)
                           If False, use OpenAI GPT-4o for accuracy (complex sections)
        """
        prompt = self._build_prompt(
            section_key, section_title, facts, constraints, examples, scientific_context
        )

        if self.llm:
            try:
                # Select model tier based on complexity
                if use_fast_model:
                    # Use fast tier for simple sections
                    response = self.llm.chat(
                        prompt,
                        max_tokens=1500  # Smaller for simple sections
                    )
                else:
                    # Use default tier (Claude) for accurate extraction
                    response = self.llm.chat(
                        prompt,
                        max_tokens=2000
                    )

                if hasattr(response, 'success') and response.success and hasattr(response, 'content'):
                    return response.content
                elif isinstance(response, str) and response:
                    return response
            except Exception as e:
                print(f"[Generation] LLM error for {section_key}: {e}")

        return f"## {section_title}\n\n[Section to be completed based on protocol specifications.]"

    def _build_prompt(
        self,
        section_key: str,
        section_title: str,
        facts: Dict[str, Any],
        constraints: MethodConstraints,
        examples: List[str],
        scientific_context: str = ""
    ) -> str:
        """Build constrained generation prompt."""
        facts_section = self._format_facts(facts, section_key)
        constraints_section = self._format_constraints(constraints, section_key)
        examples_section = "\n\n---\n\n".join(examples[:2]) if examples else "No examples available."

        context_section = ""
        if scientific_context and section_key in ['statistical_methods', 'interim_analysis', 'sensitivity_analysis']:
            context_section = f"""
## SCIENTIFIC CONTEXT (Informational - DO NOT override protocol method):
{scientific_context}

IMPORTANT: Use context for rationale only. Protocol-specified method is source of truth.
"""

        return f"""You are an expert biostatistician writing a Statistical Analysis Plan section.

## CRITICAL INSTRUCTIONS:
1. Use ONLY values from "PROTOCOL FACTS" - these are GROUND TRUTH
2. Use ONLY methods from "METHOD CONSTRAINTS"
3. If a value shows "[NEEDS REVIEW]", keep that marker in your output
4. NEVER invent or assume numerical values
5. Use extracted values even if labels differ slightly (e.g., "Power" = "Statistical power", "Statistical Method" = "Primary analysis method")
6. ONLY write "[To be specified]" if information is truly ABSENT from PROTOCOL FACTS - not just labeled differently
7. When writing sample size/power sections, check ALL fields in PROTOCOL FACTS for relevant values before defaulting to placeholder

## PROTOCOL FACTS (Source: Protocol Extraction):
{facts_section}

## METHOD CONSTRAINTS (Source: Protocol):
{constraints_section}
{context_section}
## EXAMPLE PROSE STYLE (structure only - numbers are placeholders):
{examples_section}

## SECTION TO WRITE: {section_title}

Write the {section_title} section now. Start with "## {section_title}" as header.
"""

    def _format_facts(self, facts: Dict[str, Any], section_key: str) -> str:
        """
        Format ALL extracted facts for prompt.

        Uses all fields from to_flat_dict() in extraction_schema.py.
        Skips empty, None, or [NOT FOUND] values.
        """
        lines = []

        def is_valid(value) -> bool:
            """Check if value should be included."""
            if value is None:
                return False
            if isinstance(value, str):
                if not value.strip():
                    return False
                if '[NOT' in value or '[NEEDS' in value:
                    return False
            if isinstance(value, (list, dict)) and len(value) == 0:
                return False
            return True

        def format_value(value) -> str:
            """Format a value for display."""
            if isinstance(value, list):
                return ', '.join(str(v) for v in value)
            if isinstance(value, dict):
                return ', '.join(f"{k}: {v}" for k, v in value.items())
            return str(value)

        # =================================================================
        # CORE STUDY INFORMATION (always include)
        # =================================================================
        core_fields = [
            ('nct_id', 'NCT ID'),
            ('protocol_number', 'Protocol'),
            ('phase', 'Phase'),
            ('drug_name', 'Study Drug'),
            ('comparator', 'Comparator'),
            ('sample_size', 'Sample Size'),
            ('allocation_ratio', 'Randomization Ratio'),
            ('design_type', 'Design Type'),
            ('blinding_type', 'Blinding'),
        ]
        for key, label in core_fields:
            if is_valid(facts.get(key)):
                val = facts[key]
                if key == 'sample_size':
                    lines.append(f"- {label}: {val} patients")
                else:
                    lines.append(f"- {label}: {format_value(val)}")

        # =================================================================
        # DISEASE/INDICATION (critical for context)
        # =================================================================
        disease_fields = [
            ('disease_type', 'Disease'),
            ('tumor_type', 'Tumor Type'),
            ('histology', 'Histology'),
            ('disease_stage', 'Disease Stage'),
            ('biomarker_status', 'Biomarker Status'),
            ('treatment_setting', 'Treatment Setting'),
        ]
        for key, label in disease_fields:
            if is_valid(facts.get(key)):
                lines.append(f"- {label}: {format_value(facts[key])}")

        # =================================================================
        # STRATIFICATION
        # =================================================================
        if is_valid(facts.get('stratification_factors')):
            strat = facts['stratification_factors']
            lines.append(f"- Stratification Factors: {format_value(strat)}")
        if is_valid(facts.get('stratification_factor_levels')):
            levels = facts['stratification_factor_levels']
            if isinstance(levels, dict):
                for factor, levs in levels.items():
                    lines.append(f"  • {factor}: {format_value(levs)}")

        # =================================================================
        # ENDPOINTS
        # =================================================================
        endpoint_fields = [
            ('primary_endpoint', 'Primary Endpoint'),
            ('secondary_endpoints', 'Secondary Endpoints'),
            ('co_primary_endpoints', 'Co-Primary Endpoints'),
        ]
        for key, label in endpoint_fields:
            if is_valid(facts.get(key)):
                lines.append(f"- {label}: {format_value(facts[key])}")

        # =================================================================
        # STATISTICAL METHODS
        # =================================================================
        method_fields = [
            ('statistical_method', 'Statistical Method'),
            ('primary_test', 'Primary Test'),
            ('hazard_ratio_method', 'HR Method'),
            ('expected_hazard_ratio', 'Expected HR'),
            ('power', 'Power'),
            ('null_hypothesis', 'Null Hypothesis'),
            ('alternative_hypothesis', 'Alternative Hypothesis'),
            ('test_sidedness', 'Sidedness'),
        ]
        for key, label in method_fields:
            if is_valid(facts.get(key)):
                lines.append(f"- {label}: {format_value(facts[key])}")

        # =================================================================
        # INTERIM ANALYSIS
        # =================================================================
        interim_fields = [
            ('has_interim_analysis', 'Has Interim Analysis'),
            ('num_interim_analyses', 'Number of Interim Analyses'),
            ('interim_events', 'Events at Interim'),
            ('final_events', 'Events at Final'),
            ('information_fractions', 'Information Fractions'),
            ('alpha_spending_function', 'Alpha Spending Function'),
            ('overall_alpha', 'Overall Alpha'),
            ('alpha_at_interim', 'Alpha at Interim'),
            ('alpha_at_final', 'Alpha at Final'),
            ('stopping_boundaries', 'Stopping Boundaries'),
        ]
        for key, label in interim_fields:
            if is_valid(facts.get(key)):
                lines.append(f"- {label}: {format_value(facts[key])}")

        # =================================================================
        # MULTIPLICITY
        # =================================================================
        mult_fields = [
            ('multiplicity_method', 'Multiplicity Method'),
            ('adjustment_method', 'Adjustment Method'),
            ('testing_sequence', 'Testing Sequence'),
            ('alpha_per_hypothesis', 'Alpha per Hypothesis'),
            ('hypotheses_list', 'Hypotheses'),
        ]
        for key, label in mult_fields:
            if is_valid(facts.get(key)):
                lines.append(f"- {label}: {format_value(facts[key])}")

        # =================================================================
        # POPULATIONS
        # =================================================================
        pop_fields = [
            ('itt_definition', 'ITT Definition'),
            ('fas_definition', 'FAS Definition'),
            ('per_protocol_definition', 'Per-Protocol Definition'),
            ('safety_population_definition', 'Safety Population'),
        ]
        for key, label in pop_fields:
            if is_valid(facts.get(key)):
                lines.append(f"- {label}: {format_value(facts[key])}")

        # =================================================================
        # ESTIMAND (ICH E9 R1)
        # =================================================================
        estimand_fields = [
            ('estimand_population', 'Estimand Population'),
            ('estimand_variable', 'Estimand Variable'),
            ('intercurrent_events', 'Intercurrent Events'),
            ('primary_estimand', 'Primary Estimand'),
        ]
        for key, label in estimand_fields:
            if is_valid(facts.get(key)):
                lines.append(f"- {label}: {format_value(facts[key])}")

        # =================================================================
        # MISSING DATA & SENSITIVITY
        # =================================================================
        missing_fields = [
            ('censoring_rules', 'Censoring Rules'),
            ('treatment_discontinuation_strategy', 'Discontinuation Strategy'),
            ('subsequent_therapy_handling', 'Subsequent Therapy Handling'),
            ('tipping_point_analysis', 'Tipping Point Analysis'),
            ('sensitivity_analyses', 'Sensitivity Analyses'),
        ]
        for key, label in missing_fields:
            if is_valid(facts.get(key)):
                lines.append(f"- {label}: {format_value(facts[key])}")

        # =================================================================
        # CROSSOVER
        # =================================================================
        if is_valid(facts.get('has_crossover')) and facts.get('has_crossover'):
            lines.append(f"- Has Crossover: Yes")
            if is_valid(facts.get('crossover_adjustment_methods')):
                lines.append(f"- Crossover Methods: {format_value(facts['crossover_adjustment_methods'])}")

        return '\n'.join(lines) if lines else "No specific facts extracted for this section."

    def _format_constraints(self, constraints: MethodConstraints, section_key: str) -> str:
        """Format constraints for prompt."""
        lines = []

        if section_key == 'statistical_methods':
            if constraints.primary_test:
                lines.append(f"- PRIMARY TEST: {constraints.primary_test}")
            if constraints.descriptive_methods:
                lines.append("- DESCRIPTIVE METHODS:")
                for m in constraints.descriptive_methods:
                    lines.append(f"  • {m}")

        elif section_key == 'interim_analysis':
            if constraints.interim_method:
                lines.append(f"- Interim Method: {constraints.interim_method}")
            if constraints.alpha_spending:
                lines.append(f"- Alpha Spending: {constraints.alpha_spending}")

        elif section_key == 'sensitivity_analysis':
            if constraints.sensitivity_methods:
                lines.append(f"- Methods: {', '.join(constraints.sensitivity_methods)}")

        return '\n'.join(lines) if lines else "No specific constraints."

    # =========================================================================
    # VERIFICATION
    # =========================================================================

    def _verify_and_correct(
        self,
        sap_text: str,
        facts: Dict[str, Any],
        constraints: MethodConstraints
    ) -> Tuple[Optional[VerificationResult], str, int]:
        """SELF-RAG verification and correction loop."""
        if not self.verifier:
            return None, sap_text, 0

        regeneration_count = 0
        current_text = sap_text

        for attempt in range(self.max_regenerations + 1):
            constraints_dict = {'primary_test': constraints.primary_test}
            verification = self.verifier.verify(current_text, facts, constraints_dict)

            if verification.passed:
                return verification, current_text, regeneration_count

            if attempt < self.max_regenerations:
                print(f"[Verification] Attempt {attempt + 1} failed, regenerating...")

                correction_prompt = self.verifier.generate_correction_prompt(current_text, facts)

                if self.llm:
                    try:
                        response = self.llm.chat(correction_prompt, max_tokens=3000)
                        if hasattr(response, 'success') and response.success:
                            current_text = response.content
                        elif isinstance(response, str):
                            current_text = response
                        regeneration_count += 1
                    except Exception as e:
                        print(f"[Verification] Regeneration error: {e}")
                        break

        return verification, current_text, regeneration_count

    def _assemble_sap(self, sections: Dict[str, str], facts: Dict[str, Any]) -> str:
        """Assemble sections into full SAP document."""
        nct_id = facts.get('nct_id', 'NCT_UNKNOWN')
        drug = facts.get('drug_name', 'Study Drug')

        sap_text = f"""# STATISTICAL ANALYSIS PLAN

**Protocol:** {nct_id}
**Study Drug:** {drug}
**Version:** 1.0
**Date:** [DATE]

---

"""
        section_order = [s[0] for s in self.SECTIONS]

        for section_key in section_order:
            if section_key in sections:
                sap_text += sections[section_key] + "\n\n---\n\n"

        return sap_text

    def _ensure_internal_consistency(self, sap_text: str, facts: Dict[str, Any]) -> str:
        """
        Use LLM to replace [To be specified] placeholders with extracted facts.
        
        Why LLM instead of regex:
        1. Handles all text variations ("Power:", "Statistical power:", "**Power**:")
        2. Understands context (won't replace wrong placeholders)
        3. No regex errors from variable-length lookbehind
        4. Can handle new patterns without code changes
        """
        # Check if there are any placeholders to fix
        if '[To be specified]' not in sap_text and '[NEEDS REVIEW]' not in sap_text:
            return sap_text
        
        # Build facts summary for LLM - DYNAMICALLY extract ALL facts
        facts_for_replacement = []
        
        # Special formatters for specific field types
        def format_value(key, value):
            """Format value based on field type."""
            if value is None or value == '':
                return None
            if isinstance(value, str) and ('[NOT' in value or '[NEEDS' in value):
                return None
            
            # Power: convert 0.8 to 80%
            if key in ('power', 'statistical_power') and isinstance(value, (int, float)):
                if value <= 1:
                    return f"{float(value)*100:.0f}%"
                return f"{value}%"
            
            # Sample size: add "patients"
            if 'sample_size' in key and isinstance(value, (int, float)) and 'per_arm' not in key:
                return f"{int(value)} patients"
            
            # Lists: join with commas
            if isinstance(value, list):
                if not value:
                    return None
                return ', '.join(str(v) for v in value if v)
            
            # Dicts: format as key: value pairs
            if isinstance(value, dict):
                if not value:
                    return None
                return ', '.join(f"{k}: {v}" for k, v in value.items() if v)
            
            return str(value)
        
        # Convert key to human-readable label
        def key_to_label(key):
            """Convert snake_case key to Human Readable Label."""
            # Special cases
            label_map = {
                'nct_id': 'NCT ID',
                'itt_definition': 'ITT Definition',
                'fas_definition': 'FAS Definition',
                'hr': 'Hazard Ratio',
                'ci': 'Confidence Interval',
                'pk': 'Pharmacokinetic',
                'ae': 'Adverse Event',
                'sae': 'Serious Adverse Event',
                'dmc': 'Data Monitoring Committee',
                'os': 'Overall Survival',
                'pfs': 'Progression-Free Survival',
                'orr': 'Objective Response Rate',
                'dor': 'Duration of Response',
                'ttr': 'Time to Recurrence',
            }
            
            # Check if key matches a special case
            key_lower = key.lower()
            for abbrev, full in label_map.items():
                if key_lower == abbrev:
                    return full
            
            # Standard conversion: sample_size -> Sample Size
            words = key.replace('_', ' ').split()
            # Capitalize each word, handle acronyms
            result = []
            for word in words:
                if word.upper() in ['ID', 'NCT', 'ITT', 'FAS', 'HR', 'CI', 'PK', 'AE', 'SAE', 'OS', 'PFS', 'DMC']:
                    result.append(word.upper())
                else:
                    result.append(word.capitalize())
            return ' '.join(result)
        
        # Iterate through ALL facts dynamically

        for key, value in facts.items():
            formatted = format_value(key, value)
            if formatted:
                label = key_to_label(key)
                # Add common aliases for better matching
                aliases = {
                    'power': 'Statistical Power/Power',
                    'sample_size': 'Sample Size/Number of Patients/N',
                    'statistical_method': 'Statistical Method/Primary Analysis Method/Primary Test',
                    'blinding_type': 'Blinding/Blinding Type/Masking',
                    'primary_endpoint': 'Primary Endpoint/Primary Efficacy Endpoint',
                    'comparator': 'Comparator/Control/Control Arm',
                    'drug_name': 'Study Drug/Investigational Product/Treatment',
                    'stratification_factors': 'Stratification Factors/Stratification Variables',
                    'allocation_ratio': 'Randomization Ratio/Allocation Ratio',
                    'hazard_ratio': 'Hazard Ratio/HR/Expected HR/Targeted HR',
                    'alpha': 'Alpha/Significance Level/Type I Error',
                    'overall_alpha': 'Overall Alpha/Alpha Level/Significance Level',
                }
                if key in aliases:
                    label = aliases[key]
                facts_for_replacement.append(f"- {label}: {formatted}")
        if not facts_for_replacement:
            return sap_text  # No facts to replace with
        
        facts_str = "\n".join(facts_for_replacement)
        
        prompt = f"""You are a text editor. Your ONLY task is to replace placeholder markers in a document with actual values.

## EXTRACTED VALUES (use these to replace placeholders):
{facts_str}

## RULES:
1. Find ALL instances of "[To be specified]" or "[NEEDS REVIEW]" in the text
2. If there is a matching value in EXTRACTED VALUES, replace the placeholder with that value
3. Match by context - "**Power**: [To be specified]" should use the "Statistical Power/Power" value
4. Keep the surrounding formatting (**, :, etc.) - only replace the placeholder text itself
5. If no matching value exists, keep the placeholder unchanged
6. Do NOT change anything else in the document - no rewording, no restructuring
7. Return ONLY the corrected text, nothing else

## DOCUMENT TO FIX:
{sap_text}

## OUTPUT:
Return the document with placeholders replaced. No explanations, just the fixed document."""

        try:
            # Higher token limit for full SAP documents
            if self.fast_llm:
                response = self.fast_llm.chat(prompt, max_tokens=16000)
            elif self.llm:
                response = self.llm.chat(prompt, max_tokens=16000)
            else:
                return sap_text
            
            # Extract text from response
            if hasattr(response, 'content'):
                if isinstance(response.content, list):
                    result = ''.join(block.text for block in response.content if hasattr(block, 'text'))
                else:
                    result = response.content
            elif isinstance(response, str):
                result = response
            else:
                return sap_text
            
            # Validate result
            if result and len(result) > len(sap_text) * 0.3 and '##' in result:
                original_placeholders = sap_text.count('[To be specified]') + sap_text.count('[NEEDS REVIEW]')
                remaining_placeholders = result.count('[To be specified]') + result.count('[NEEDS REVIEW]')
                fixed_count = original_placeholders - remaining_placeholders
                
                if fixed_count > 0:
                    print(f"[PostProcess] Fixed {fixed_count} placeholders via LLM")
                
                return result
            else:
                print("[PostProcess] LLM response invalid, keeping original")
                return sap_text
                
        except Exception as e:
            print(f"[PostProcess] LLM error: {e}, keeping original")
            return sap_text

    def _direct_inject_facts(self, sap_text: str, facts: Dict[str, Any]) -> str:
        """
        DIRECT INJECTION: Programmatically replace factual values without LLM.

        This is the FINAL authority for factual fields. If extraction found a value,
        it gets injected here regardless of what LLM generated.

        NO LLM INVOLVED - pure regex/string replacement.
        """
        import re

        corrections_made = []
        result = sap_text

        # =====================================================================
        # 1. SAMPLE SIZE: Fix wrong sample size values
        # =====================================================================
        total_sample_size = facts.get('total_sample_size') or facts.get('sample_size_total')
        if total_sample_size and int(total_sample_size) > 0:
            # Pattern: "238 patients" when it should be "530 patients" (or similar)
            # Look for sample size mentions that are wrong
            sample_size_per_arm = facts.get('sample_size') or facts.get('sample_size_per_arm')
            if sample_size_per_arm and isinstance(sample_size_per_arm, (int, float)):
                per_arm = int(sample_size_per_arm)
                total = int(total_sample_size)

                # If text says per-arm number as total, fix it
                if per_arm != total:
                    # Replace "238 patients will be enrolled" with "530 patients will be enrolled"
                    pattern = rf'\b{per_arm}\s+(patients|subjects|participants)\s+(will be|are|to be)\s+(enrolled|randomized|recruited)'
                    replacement = rf'{total} \1 \2 \3'
                    new_result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
                    if new_result != result:
                        corrections_made.append(f"Sample size: {per_arm} -> {total}")
                        result = new_result

                    # Also fix "total sample size of 238"
                    pattern = rf'total\s+(?:sample\s+)?size\s+(?:of\s+)?{per_arm}'
                    replacement = f'total sample size of {total}'
                    new_result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
                    if new_result != result:
                        corrections_made.append(f"Total sample size: {per_arm} -> {total}")
                        result = new_result

        # =====================================================================
        # 2. SIDEDNESS: Fix one-sided when it should be two-sided (or vice versa)
        # =====================================================================
        extracted_sidedness = facts.get('test_sidedness') or facts.get('alpha_sidedness')
        if extracted_sidedness and extracted_sidedness.lower() in ('one-sided', 'two-sided'):
            correct_sidedness = extracted_sidedness.lower()
            wrong_sidedness = 'one-sided' if correct_sidedness == 'two-sided' else 'two-sided'

            # Count occurrences
            wrong_count = result.lower().count(wrong_sidedness)
            if wrong_count > 0:
                # Replace wrong sidedness with correct one
                # Be careful: only replace in statistical context, not in unrelated text
                stat_patterns = [
                    rf'({wrong_sidedness})\s*(significance|alpha|test|p-value|hypothesis)',
                    rf'(significance|alpha|test|p-value|hypothesis)\s*[^.]*({wrong_sidedness})',
                    rf'at\s+(?:a\s+)?({wrong_sidedness})',
                    rf'using\s+(?:a\s+)?({wrong_sidedness})',
                    rf'({wrong_sidedness})\s+α',
                    rf'α\s*=\s*\d+\.?\d*\s*\({wrong_sidedness}\)',
                ]

                for pattern in stat_patterns:
                    new_result = re.sub(pattern, lambda m: m.group(0).replace(wrong_sidedness, correct_sidedness),
                                       result, flags=re.IGNORECASE)
                    if new_result != result:
                        result = new_result

                # Simple global replacement as fallback if statistical context patterns don't catch all
                new_count = result.lower().count(wrong_sidedness)
                if new_count > 0:
                    result = re.sub(wrong_sidedness, correct_sidedness, result, flags=re.IGNORECASE)

                corrections_made.append(f"Sidedness: {wrong_sidedness} -> {correct_sidedness}")

        # =====================================================================
        # 3. POWER: Ensure power is correctly stated
        # =====================================================================
        power = facts.get('power') or facts.get('statistical_power')
        if power:
            # Normalize to percentage
            if isinstance(power, (int, float)):
                power_pct = power if power > 1 else power * 100
                power_str = f"{int(power_pct)}%"

                # Replace placeholder
                result = re.sub(
                    r'\*\*Power\*\*:\s*\[To be specified\]',
                    f'**Power**: {power_str}',
                    result
                )
                result = re.sub(
                    r'Power:\s*\[To be specified\]',
                    f'Power: {power_str}',
                    result
                )

        # =====================================================================
        # 4. ALPHA: Ensure alpha is correctly stated
        # =====================================================================
        alpha = facts.get('alpha') or facts.get('overall_alpha') or facts.get('alpha_level')
        if alpha:
            if isinstance(alpha, dict):
                alpha = alpha.get('primary_alpha', 0.05)
            if isinstance(alpha, (int, float)):
                alpha_str = f"{alpha}"

                # Replace placeholder
                result = re.sub(
                    r'\*\*Alpha\*\*:\s*\[To be specified\]',
                    f'**Alpha**: {alpha_str}',
                    result
                )
                result = re.sub(
                    r'Significance level:\s*\[To be specified\]',
                    f'Significance level: {alpha_str}',
                    result
                )

        # =====================================================================
        # 5. PRIMARY ANALYSIS POPULATION: FAS vs ITT
        # =====================================================================
        primary_pop = facts.get('primary_analysis_population')
        if primary_pop and primary_pop.upper() in ('FAS', 'ITT', 'MITT', 'PP'):
            correct_pop = primary_pop.upper()

            # If FAS is specified but text says ITT as primary, fix it
            if correct_pop == 'FAS':
                # Pattern: "ITT population will serve as the primary" or similar
                pattern = r'(ITT|Intent-to-Treat)\s+(population\s+)?(will\s+)?(serve\s+as\s+|is\s+)?the\s+primary'
                if re.search(pattern, result, flags=re.IGNORECASE):
                    result = re.sub(pattern, r'FAS (Full Analysis Set) \2\3\4the primary', result, flags=re.IGNORECASE)
                    corrections_made.append(f"Primary population: ITT -> FAS")

        # =====================================================================
        # 6. HAZARD RATIO: Ensure correct HR
        # =====================================================================
        hr = facts.get('hazard_ratio') or facts.get('expected_hr') or facts.get('hr')
        if hr and isinstance(hr, (int, float)):
            hr_str = f"{hr:.3f}" if hr < 1 else f"{hr:.2f}"

            result = re.sub(
                r'Hazard ratio:\s*\[To be specified\]',
                f'Hazard ratio: {hr_str}',
                result,
                flags=re.IGNORECASE
            )
            result = re.sub(
                r'HR\s*=\s*\[To be specified\]',
                f'HR = {hr_str}',
                result
            )

        # =====================================================================
        # 7. EVENTS: Fix event counts
        # =====================================================================
        final_events = facts.get('final_events') or facts.get('final_analysis_events')
        if final_events and isinstance(final_events, (int, float)):
            events_str = str(int(final_events))
            result = re.sub(
                r'(\d+)\s+events\s+for\s+final\s+analysis',
                f'{events_str} events for final analysis',
                result,
                flags=re.IGNORECASE
            )

        interim_events = facts.get('interim_events') or facts.get('interim_analysis_events')
        if interim_events:
            if isinstance(interim_events, list) and len(interim_events) > 0:
                events_str = str(int(interim_events[0]))
            elif isinstance(interim_events, (int, float)):
                events_str = str(int(interim_events))
            else:
                events_str = None

            if events_str:
                result = re.sub(
                    r'interim\s+analysis\s+(?:at\s+)?(\d+)\s+events',
                    f'interim analysis at {events_str} events',
                    result,
                    flags=re.IGNORECASE
                )

        # =====================================================================
        # LOG CORRECTIONS
        # =====================================================================
        if corrections_made:
            print(f"[DirectInject] Made {len(corrections_made)} corrections:")
            for c in corrections_made:
                print(f"  - {c}")
        else:
            print("[DirectInject] No corrections needed")

        return result
# FACTORY FUNCTION
# =============================================================================

def create_production_pipeline(max_regenerations: int = 2) -> ProductionSAPPipeline:
    """Factory function to create the production pipeline."""
    return ProductionSAPPipeline(max_regenerations=max_regenerations)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TESTING CLEAN PRODUCTION SAP PIPELINE")
    print("=" * 60)

    test_protocol = """
    NCT02041533 - CheckMate 078
    Phase 3, Randomized Study of Nivolumab vs Docetaxel in NSCLC

    Treatment Setting: Second-line (previously treated with platinum-based chemotherapy)
    Disease: Non-small cell lung cancer (NSCLC)

    Primary Endpoint: Overall Survival (OS)
    Sample Size: 504 patients (2:1 randomization)

    Statistical Method: Stratified log-rank test, stratified by ECOG PS and histology.

    INTERIM ANALYSIS:
    - One interim analysis at 291 events (76% information)
    - Final analysis at 382 events
    - Alpha at interim: 0.020
    - Alpha at final: 0.044
    - Lan-DeMets with O'Brien-Fleming spending function

    CROSSOVER: Patients on docetaxel may cross over to nivolumab upon progression.
    """

    pipeline = create_production_pipeline()
    result = pipeline.generate(test_protocol)

    print(f"\n{'=' * 60}")
    print("RESULT")
    print("=" * 60)
    print(f"Success: {result.success}")
    print(f"Regenerations: {result.regeneration_count}")
    print(f"Needs Review: {result.needs_review}")
    print(f"Extraction Confidence: {result.extraction_confidence}")

    if result.verification:
        print(f"Verification passed: {result.verification.passed}")
        print(f"Score: {result.verification.score:.2f}")

    print(f"\nSAP length: {len(result.sap_text)} chars")
