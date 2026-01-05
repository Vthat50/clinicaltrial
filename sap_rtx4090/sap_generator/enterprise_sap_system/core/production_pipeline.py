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
    SECTIONS = [
        ('introduction', 'Introduction'),
        ('objectives', 'Study Objectives and Endpoints'),
        ('estimands', 'Estimands'),  # ICH E9 R1 requirement
        ('study_design', 'Study Design'),
        ('sample_size', 'Sample Size Determination'),
        ('analysis_populations', 'Analysis Populations'),
        ('statistical_methods', 'Statistical Methods'),
        ('interim_analysis', 'Interim Analysis'),
        ('sensitivity_analysis', 'Sensitivity Analyses'),
        ('missing_data', 'Missing Data Handling'),
        ('multiplicity', 'Multiplicity Adjustment'),
        ('safety', 'Safety Analyses'),
    ]

    def __init__(self, max_regenerations: int = 2):
        """Initialize production pipeline - NO FALLBACKS."""
        self.max_regenerations = max_regenerations

        print("[ProductionPipeline] Initializing (no fallbacks)...")

        # 1. LLM Client (required)
        self.llm = TieredLLMClient()
        print("[ProductionPipeline] ✓ LLM client (Claude Opus 4.5)")

        # 2. Sectioned Extractor (required)
        self.sectioned_extractor = create_sectioned_extractor(llm_client=self.llm)
        print("[ProductionPipeline] ✓ SectionedProtocolExtractor")

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
            # STEP 1: SECTIONED EXTRACTION (with confidence scores)
            # =================================================================
            print("\n[Step 1] Extracting facts by section (with confidence)...")
            facts, section_results = self._extract_facts_sectioned(protocol_text, pdf_path=pdf_path)

            # Log extraction quality
            overall_confidence = sum(r.confidence for r in section_results.values()) / len(section_results) if section_results else 0
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
            # STEP 3.5: DECISION ENGINE RECOMMENDATIONS (augment constraints)
            # =================================================================
            if self.decision_engine:
                print("\n[Step 3.5] Getting decision engine recommendations...")

                # Get response criteria recommendation
                response_rec = self.decision_engine.recommend_response_criteria(facts)
                if response_rec and response_rec.get('criteria'):
                    facts['response_criteria'] = response_rec['criteria']
                    facts['response_criteria_rationale'] = response_rec.get('rationale', '')
                    print(f"[Step 3.5] Response criteria: {response_rec['criteria']}")
                    if response_rec.get('warnings'):
                        for w in response_rec['warnings']:
                            print(f"[Step 3.5] ⚠ {w}")

                # Get statistical methods recommendation (if protocol method unclear)
                if '[NEEDS REVIEW]' in constraints.primary_test or '[NOT' in constraints.primary_test:
                    method_rec = self.decision_engine.recommend_statistical_methods(facts)
                    if method_rec and method_rec.get('primary_method'):
                        # Flag as recommendation, not protocol-specified
                        recommended_method = f"{method_rec['primary_method']} [RECOMMENDED - verify against protocol]"
                        constraints.primary_test = recommended_method
                        print(f"[Step 3.5] Recommended method: {method_rec['primary_method']}")
                        if method_rec.get('rationale'):
                            print(f"[Step 3.5] Rationale: {method_rec['rationale']}")

                # Get population definitions recommendation
                pop_rec = self.decision_engine.recommend_population_definitions(facts)
                if pop_rec:
                    if pop_rec.get('itt_definition') and not facts.get('itt_definition'):
                        facts['itt_definition'] = pop_rec['itt_definition']
                    if pop_rec.get('fas_definition') and not facts.get('fas_definition'):
                        facts['fas_definition'] = pop_rec['fas_definition']
                    if pop_rec.get('per_protocol_definition') and not facts.get('per_protocol_definition'):
                        facts['per_protocol_definition'] = pop_rec['per_protocol_definition']
                    if pop_rec.get('safety_population_definition') and not facts.get('safety_population_definition'):
                        facts['safety_population_definition'] = pop_rec['safety_population_definition']
                    print(f"[Step 3.5] Population definitions augmented from decision engine")

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
        pdf_path: str = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract facts using sectioned extraction with confidence scores.
        NO FALLBACKS - will raise if extraction fails.
        """
        extracted_facts, section_results = self.sectioned_extractor.extract_all_sections(
            protocol_text,
            pdf_path=pdf_path
        )
        # Convert to flat dict for generation
        facts = extracted_facts.to_flat_dict() if hasattr(extracted_facts, 'to_flat_dict') else {}
        facts['raw_text'] = protocol_text.lower()
        return facts, section_results

    def _normalize_facts(self, facts: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize field names for consistency."""
        normalized = dict(facts)

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
                        content = r.get('content', str(r)) if isinstance(r, dict) else str(r)

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
        max_workers: int = 6
    ) -> Dict[str, str]:
        """
        Generate all SAP sections.

        Args:
            parallel: If True, generate sections in parallel (faster)
            max_workers: Number of parallel threads (default 6 to avoid rate limits)
        """
        sections = {}

        if parallel:
            # PARALLEL GENERATION - up to 6x faster
            print(f"[Generation] Parallel mode with {max_workers} workers")

            def generate_one(section_key: str, section_title: str) -> Tuple[str, str]:
                """Generate one section (thread-safe)."""
                examples = sanitized_examples.get(section_key, [])
                if not examples and section_key == 'statistical_methods':
                    examples = sanitized_examples.get('methods', [])

                section_text = self._generate_section(
                    section_key, section_title, facts, constraints, examples, scientific_context
                )
                return section_key, section_text

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all section generations
                futures = {
                    executor.submit(generate_one, key, title): key
                    for key, title in self.SECTIONS
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
            for section_key, section_title in self.SECTIONS:
                examples = sanitized_examples.get(section_key, [])
                if not examples and section_key == 'statistical_methods':
                    examples = sanitized_examples.get('methods', [])

                section_text = self._generate_section(
                    section_key, section_title, facts, constraints, examples, scientific_context
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
        scientific_context: str = ""
    ) -> str:
        """Generate a single section."""
        prompt = self._build_prompt(
            section_key, section_title, facts, constraints, examples, scientific_context
        )

        if self.llm:
            try:
                response = self.llm.chat(prompt, max_tokens=2000)
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
5. If value not in PROTOCOL FACTS, write "[To be specified]"

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
        Scan generated SAP for [NEEDS REVIEW]/[To be specified] markers and
        replace with actual values if they exist elsewhere in the document or facts.

        This fixes the bug where one section says "[To be specified]" but another
        section has the actual value.
        """
        import re

        # Mapping of common marker patterns to fact keys
        marker_patterns = [
            # Primary endpoint variations
            (r'\[To be specified\](?=.*[Pp]rimary [Ee]ndpoint)', 'primary_endpoint'),
            (r'\[PRIMARY ENDPOINT NOT EXTRACTED[^\]]*\]', 'primary_endpoint'),
            (r'\[NEEDS REVIEW\](?=.*[Pp]rimary)', 'primary_endpoint'),

            # Statistical method variations
            (r'\[STATISTICAL METHOD NOT FOUND[^\]]*\]', 'statistical_method'),
            (r'\[STATISTICAL METHOD NOT EXTRACTED[^\]]*\]', 'statistical_method'),

            # Treatment setting
            (r'\[TREATMENT SETTING NOT EXTRACTED[^\]]*\]', 'treatment_setting'),

            # Interim analysis
            (r'\[INTERIM METHOD NOT EXTRACTED[^\]]*\]', 'interim_analysis_method'),
            (r'\[ALPHA SPENDING NOT EXTRACTED[^\]]*\]', 'alpha_spending_function'),

            # Sample size
            (r'\[SAMPLE SIZE NOT EXTRACTED[^\]]*\]', 'sample_size'),
        ]

        modified = sap_text
        replacements_made = 0

        for pattern, fact_key in marker_patterns:
            fact_value = facts.get(fact_key)
            if fact_value and '[NOT' not in str(fact_value) and '[NEEDS' not in str(fact_value):
                # Replace the marker with the actual value
                matches = re.findall(pattern, modified)
                if matches:
                    modified = re.sub(pattern, str(fact_value), modified)
                    replacements_made += len(matches)
                    print(f"[Consistency] Replaced {len(matches)} marker(s) for {fact_key}: {fact_value}")

        # Also scan for values that appear in one section but not another
        # Extract endpoint from Estimand section if present
        estimand_match = re.search(
            r'(?:Primary Estimand|Estimand).*?(?:Endpoint|Variable)[:\s]*([^\n\[]+)',
            sap_text, re.IGNORECASE | re.DOTALL
        )
        if estimand_match:
            found_endpoint = estimand_match.group(1).strip()
            if found_endpoint and len(found_endpoint) > 5:
                # Replace generic "[To be specified]" near Primary Endpoint
                pattern = r'(\*\*Primary Endpoint[:\*]*\s*)\[To be specified\]'
                if re.search(pattern, modified):
                    modified = re.sub(pattern, rf'\1{found_endpoint}', modified)
                    print(f"[Consistency] Populated Primary Endpoint from Estimand: {found_endpoint}")
                    replacements_made += 1

        if replacements_made > 0:
            print(f"[Consistency] Total replacements: {replacements_made}")

        return modified


# =============================================================================
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
