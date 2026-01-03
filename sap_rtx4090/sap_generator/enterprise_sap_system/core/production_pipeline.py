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

# =============================================================================
# CORE IMPORTS (no inference-based classifiers)
# =============================================================================

# Sectioned Extractor (NEW - per-section extraction with confidence)
try:
    from .sectioned_extractor import SectionedProtocolExtractor, create_sectioned_extractor
    SECTIONED_EXTRACTOR_AVAILABLE = True
except ImportError:
    SectionedProtocolExtractor = None
    create_sectioned_extractor = None
    SECTIONED_EXTRACTOR_AVAILABLE = False

# Legacy extractor (fallback)
try:
    from .claude_extractor import ClaudeProtocolExtractor, ExtractedProtocol
except ImportError:
    ClaudeProtocolExtractor = None
    ExtractedProtocol = None

# Knowledge Graph (CONTEXT only, not method selection)
try:
    from .knowledge_rule_engine import KnowledgeRuleEngine
except ImportError:
    KnowledgeRuleEngine = None

# RAG Sanitizer
try:
    from .rag_sanitizer import RAGSanitizer
except ImportError:
    RAGSanitizer = None

# Fact Verifier (SELF-RAG pattern)
try:
    from .fact_verifier import FactVerifier, VerificationResult
except ImportError:
    FactVerifier = None
    VerificationResult = None

# Vector Store
try:
    from ..rag.vector_store import create_vector_store
except ImportError:
    try:
        from enterprise_sap_system.rag.vector_store import create_vector_store
    except ImportError:
        create_vector_store = None

# LLM Client
try:
    from .tiered_llm import TieredLLMClient
except ImportError:
    TieredLLMClient = None

# Extraction Schema
try:
    from .extraction_schema import ExtractedProtocolFacts, from_claude_extraction
except ImportError:
    ExtractedProtocolFacts = None
    from_claude_extraction = None


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
        """Initialize production pipeline with clean components."""
        self.max_regenerations = max_regenerations

        print("[ProductionPipeline] Initializing components...")

        # 1. LLM Client (needed for extractors)
        self.llm = None
        if TieredLLMClient:
            try:
                self.llm = TieredLLMClient()
                print("[ProductionPipeline] ✓ LLM client initialized (Claude Opus 4.5)")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ LLM failed: {e}")

        # 2. Sectioned Extractor (NEW - primary extraction method)
        self.sectioned_extractor = None
        if SECTIONED_EXTRACTOR_AVAILABLE and self.llm:
            try:
                self.sectioned_extractor = create_sectioned_extractor(llm_client=self.llm)
                print("[ProductionPipeline] ✓ SectionedProtocolExtractor initialized")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ Sectioned extractor failed: {e}")

        # 3. Legacy Extractor (fallback)
        self.legacy_extractor = None
        if ClaudeProtocolExtractor:
            try:
                self.legacy_extractor = ClaudeProtocolExtractor()
                print("[ProductionPipeline] ✓ Legacy ClaudeProtocolExtractor (fallback)")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ Legacy extractor failed: {e}")

        # 4. Knowledge Graph (CONTEXT only)
        self.knowledge_graph = None
        if KnowledgeRuleEngine:
            try:
                self.knowledge_graph = KnowledgeRuleEngine()
                print("[ProductionPipeline] ✓ KnowledgeRuleEngine (context only)")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ Knowledge graph failed: {e}")

        # 5. RAG (prose style)
        self.rag = None
        if create_vector_store:
            try:
                self.rag = create_vector_store()
                print("[ProductionPipeline] ✓ ChromaDB RAG connected")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ RAG failed: {e}")

        # 6. RAG Sanitizer
        self.sanitizer = None
        if RAGSanitizer:
            self.sanitizer = RAGSanitizer(aggressive=True)
            print("[ProductionPipeline] ✓ RAG Sanitizer initialized")

        # 7. Fact Verifier (SELF-RAG)
        self.verifier = None
        if FactVerifier:
            self.verifier = FactVerifier()
            print("[ProductionPipeline] ✓ Fact Verifier initialized")

        print("[ProductionPipeline] Initialization complete")

    def generate(self, protocol_text: str) -> GenerationResult:
        """
        Generate SAP using clean production pipeline.

        Steps:
        1. Extract facts by section with confidence scores
        2. Get scientific context from knowledge graph
        3. Get sanitized RAG examples
        4. Generate with constrained prompts
        5. Verify and regenerate if needed
        """
        try:
            # =================================================================
            # STEP 1: SECTIONED EXTRACTION (with confidence scores)
            # =================================================================
            print("\n[Step 1] Extracting facts by section (with confidence)...")
            facts, section_results = self._extract_facts_sectioned(protocol_text)

            # Log extraction quality
            overall_confidence = sum(r.confidence for r in section_results.values()) / len(section_results) if section_results else 0
            print(f"[Step 1] Overall extraction confidence: {overall_confidence:.0%}")

            # Log critical fields
            print(f"[Step 1] NCT ID: {facts.get('nct_id', 'NOT FOUND')}")
            print(f"[Step 1] Sample size: {facts.get('sample_size', 'NOT FOUND')}")
            print(f"[Step 1] Treatment setting: {facts.get('treatment_setting', 'NOT FOUND')}")
            print(f"[Step 1] Statistical method: {facts.get('statistical_method', 'NOT FOUND')}")
            print(f"[Step 1] Has interim: {facts.get('has_interim_analysis', 'NOT FOUND')}")

            # Collect fields needing review
            needs_review = []
            for section_name, result in section_results.items():
                if result.needs_review:
                    needs_review.extend(result.needs_review)
                    print(f"[Step 1] ⚠ {section_name} NEEDS REVIEW: {result.needs_review}")

            # =================================================================
            # STEP 2: SCIENTIFIC CONTEXT (from knowledge graph)
            # =================================================================
            print("\n[Step 2] Getting scientific context...")
            scientific_context = ""
            conditions = []

            if self.knowledge_graph:
                # Detect conditions for context
                conditions = list(self.knowledge_graph.detect_conditions(facts))
                print(f"[Step 2] Conditions detected: {conditions}")

                # Get context string (does NOT select methods)
                scientific_context = self.knowledge_graph.get_context_for_generation(facts)
                print(f"[Step 2] Generated context ({len(scientific_context)} chars)")

                # Log any discrepancy notes
                method_ctx = self.knowledge_graph.get_method_context(facts)
                for note in method_ctx.get('discrepancy_notes', []):
                    print(f"[Step 2] {note['severity'].upper()}: {note['observation'][:80]}...")

            # =================================================================
            # STEP 3: METHOD CONSTRAINTS (from extraction, not inference)
            # =================================================================
            print("\n[Step 3] Building method constraints from extraction...")
            constraints = self._build_constraints_from_extraction(facts, conditions)
            print(f"[Step 3] Primary test: {constraints.primary_test}")

            # =================================================================
            # STEP 4: SANITIZED RAG EXAMPLES
            # =================================================================
            print("\n[Step 4] Getting sanitized RAG examples...")
            sanitized_examples = self._get_sanitized_examples(facts)
            print(f"[Step 4] Retrieved {sum(len(v) for v in sanitized_examples.values())} examples")

            # =================================================================
            # STEP 5: GENERATE SECTIONS
            # =================================================================
            print("\n[Step 5] Generating SAP sections...")
            sections = self._generate_all_sections(
                facts, constraints, sanitized_examples, scientific_context
            )

            # Assemble full SAP
            sap_text = self._assemble_sap(sections, facts)

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
                regeneration_count=regeneration_count
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return GenerationResult(success=False, error=str(e))

    def _extract_facts_sectioned(
        self,
        protocol_text: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract facts using sectioned extraction with confidence scores.

        Returns:
            Tuple of (facts dict, section_results dict)
        """
        section_results = {}

        # Try sectioned extractor first
        if self.sectioned_extractor:
            try:
                extracted_facts, section_results = self.sectioned_extractor.extract_all_sections(
                    protocol_text
                )
                # Convert to flat dict for generation
                facts = extracted_facts.to_flat_dict() if hasattr(extracted_facts, 'to_flat_dict') else {}
                facts['raw_text'] = protocol_text.lower()
                return facts, section_results
            except Exception as e:
                print(f"[Extraction] Sectioned extraction failed: {e}, falling back to legacy")

        # Fallback to legacy extractor
        if self.legacy_extractor:
            try:
                extracted = self.legacy_extractor.extract(protocol_text)
                if extracted:
                    if hasattr(extracted, 'dict'):
                        facts = extracted.dict()
                    elif hasattr(extracted, '__dict__'):
                        facts = {k: v for k, v in extracted.__dict__.items() if not k.startswith('_')}
                    else:
                        facts = dict(extracted)

                    facts['raw_text'] = protocol_text.lower()
                    facts = self._normalize_facts(facts)

                    # Create dummy section results for legacy
                    section_results = {
                        'legacy': type('Result', (), {
                            'confidence': 0.7,
                            'needs_review': [],
                            'fields_found': list(facts.keys()),
                            'fields_not_found': []
                        })()
                    }
                    return facts, section_results
            except Exception as e:
                print(f"[Extraction] Legacy extraction failed: {e}")

        # Final fallback to basic extraction
        facts = self._basic_extraction(protocol_text)
        section_results = {
            'basic': type('Result', (), {
                'confidence': 0.3,
                'needs_review': ['all fields'],
                'fields_found': [],
                'fields_not_found': []
            })()
        }
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

    def _basic_extraction(self, text: str) -> Dict[str, Any]:
        """Fallback basic extraction using regex."""
        facts = {'raw_text': text.lower()}

        # NCT ID
        nct_match = re.search(r'NCT\d{8}', text, re.IGNORECASE)
        if nct_match:
            facts['nct_id'] = nct_match.group()

        # Sample size
        size_match = re.search(r'(\d+)\s*(?:patients|subjects|participants)', text, re.IGNORECASE)
        if size_match:
            facts['sample_size'] = int(size_match.group(1))

        # Events
        final_match = re.search(r'(?:final|total)[:\s]*(\d+)\s*(?:deaths?|events?)', text, re.IGNORECASE)
        if final_match:
            facts['final_events'] = int(final_match.group(1))

        interim_match = re.search(r'interim[:\s]*(?:at\s+)?(\d+)\s*(?:deaths?|events?)', text, re.IGNORECASE)
        if interim_match:
            facts['interim_events'] = int(interim_match.group(1))

        # Interim analysis
        facts['has_interim_analysis'] = bool(
            re.search(r'interim\s+analysis', text, re.IGNORECASE) and
            not re.search(r'no\s+interim', text, re.IGNORECASE)
        )

        # Treatment setting - flag for review, don't infer
        facts['treatment_setting'] = '[TREATMENT SETTING NOT EXTRACTED - NEEDS REVIEW]'

        # Statistical method - flag for review, don't infer
        facts['statistical_method'] = '[STATISTICAL METHOD NOT EXTRACTED - NEEDS REVIEW]'

        return facts

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

    def _get_sanitized_examples(self, facts: Dict[str, Any]) -> Dict[str, List[str]]:
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

        for section_type in section_types:
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

                    examples[section_type] = sanitized

            except Exception as e:
                print(f"[RAG] Error querying {section_type}: {e}")

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
        scientific_context: str = ""
    ) -> Dict[str, str]:
        """Generate all SAP sections."""
        sections = {}

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
        """Format facts for prompt."""
        lines = []

        # Always include core facts
        if facts.get('nct_id'):
            lines.append(f"- NCT ID: {facts['nct_id']}")
        if facts.get('sample_size'):
            lines.append(f"- Sample Size: {facts['sample_size']} patients")
        if facts.get('treatment_setting'):
            lines.append(f"- Treatment Setting: {facts['treatment_setting']}")
        if facts.get('disease_type'):
            lines.append(f"- Disease: {facts['disease_type']}")
        if facts.get('drug_name'):
            lines.append(f"- Study Drug: {facts['drug_name']}")
        if facts.get('comparator'):
            lines.append(f"- Comparator: {facts['comparator']}")

        # Section-specific facts
        if section_key in ['statistical_methods', 'interim_analysis']:
            if facts.get('statistical_method'):
                lines.append(f"- Statistical Method: {facts['statistical_method']}")
            if facts.get('final_events') or facts.get('final_analysis_events'):
                events = facts.get('final_events') or facts.get('final_analysis_events')
                lines.append(f"- Events at Final: {events}")
            if facts.get('interim_events'):
                lines.append(f"- Events at Interim: {facts['interim_events']}")
            if facts.get('alpha_at_interim'):
                lines.append(f"- Alpha at Interim: {facts['alpha_at_interim']}")
            if facts.get('alpha_at_final'):
                lines.append(f"- Alpha at Final: {facts['alpha_at_final']}")

        if section_key == 'sample_size':
            if facts.get('power'):
                lines.append(f"- Power: {facts['power']}")
            if facts.get('expected_hazard_ratio'):
                lines.append(f"- Expected HR: {facts['expected_hazard_ratio']}")

        if section_key == 'objectives':
            if facts.get('primary_endpoint'):
                lines.append(f"- Primary Endpoint: {facts['primary_endpoint']}")
            if facts.get('secondary_endpoints'):
                lines.append(f"- Secondary Endpoints: {facts['secondary_endpoints']}")

        if section_key == 'multiplicity':
            if facts.get('alpha_per_hypothesis'):
                lines.append(f"- Alpha per Hypothesis: {facts['alpha_per_hypothesis']}")
            if facts.get('testing_sequence'):
                lines.append(f"- Testing Sequence: {facts['testing_sequence']}")

        return '\n'.join(lines) if lines else "No specific facts for this section."

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
