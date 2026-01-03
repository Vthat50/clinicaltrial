#!/usr/bin/env python3
"""
Production SAP Pipeline - Separation of Concerns Architecture
==============================================================

Based on 2024-2025 RAG best practices:

1. EXTRACTION (Ground Truth) - Single source for all numerical values
2. KNOWLEDGE GRAPH (Method Selection) - Rules for statistical methods
3. RAG (Prose Style Only) - Sanitized examples with numbers stripped
4. CONSTRAINED GENERATION - Explicit source attribution in prompts
5. SELF-RAG VERIFICATION - Verify and correct if needed

References:
- SELF-RAG (ICLR 2024 Oral): Reflection tokens for factuality
- AI21 Labs: "Centralizing through single trusted data source"
- Graph RAG (2025): Knowledge graphs as factual constraints
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Import components
try:
    from .claude_extractor import ClaudeProtocolExtractor, ExtractedProtocol
except ImportError:
    ClaudeProtocolExtractor = None
    ExtractedProtocol = None

try:
    from .knowledge_rule_engine import KnowledgeRuleEngine
except ImportError:
    KnowledgeRuleEngine = None

try:
    from .rag_sanitizer import RAGSanitizer
except ImportError:
    RAGSanitizer = None

try:
    from .fact_verifier import FactVerifier, VerificationResult
except ImportError:
    FactVerifier = None
    VerificationResult = None

try:
    from ..rag.vector_store import create_vector_store
except ImportError:
    try:
        from enterprise_sap_system.rag.vector_store import create_vector_store
    except ImportError:
        create_vector_store = None

try:
    from .tiered_llm import TieredLLMClient
except ImportError:
    TieredLLMClient = None

try:
    from .drug_classifier import DrugClassifier, DrugClassification, create_drug_classifier
except ImportError:
    DrugClassifier = None
    DrugClassification = None
    create_drug_classifier = None

try:
    from .study_design_classifier import StudyDesignClassifier, StudyDesignResult, StudyDesignType, StatisticalApproach
except ImportError:
    StudyDesignClassifier = None
    StudyDesignResult = None
    StudyDesignType = None
    StatisticalApproach = None

# HYBRID CLASSIFIER: Uses RAG + LLM for more accurate classification
try:
    from .hybrid_design_classifier import (
        HybridDesignClassifier,
        HybridClassificationResult,
        StudyDesignType as HybridDesignType,
        StatisticalApproach as HybridApproach,
        create_hybrid_classifier
    )
except ImportError:
    HybridDesignClassifier = None
    HybridClassificationResult = None
    HybridDesignType = None
    HybridApproach = None
    create_hybrid_classifier = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MethodConstraints:
    """Method constraints from Knowledge Graph."""
    primary_test: str = ""
    primary_test_params: Dict[str, Any] = field(default_factory=dict)
    forbidden_primary: str = ""  # Method NOT to use as primary
    sensitivity_methods: List[str] = field(default_factory=list)
    interim_method: Optional[str] = ""
    alpha_spending: Optional[str] = ""
    nph_methods: List[str] = field(default_factory=list)
    conditions_detected: List[str] = field(default_factory=list)

    # Phase II / Single-arm / Pilot study fields
    descriptive_methods: List[str] = field(default_factory=list)
    binary_methods: List[str] = field(default_factory=list)
    sample_size_approach: str = ""  # "power" or "precision" or "exploratory"

    # Neoadjuvant-specific fields
    time_origin: str = ""  # "randomization" or "surgery"
    neoadjuvant_methods: List[str] = field(default_factory=list)
    pathologic_criteria: str = ""  # "Junker", "Miller-Payne", etc.


@dataclass
class GenerationResult:
    """Final SAP generation result."""
    success: bool
    sap_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)
    facts: Dict[str, Any] = field(default_factory=dict)
    constraints: Optional[MethodConstraints] = None
    verification: Optional[VerificationResult] = None
    drug_classification: Optional[Any] = None  # DrugClassification from ontology
    study_design: Optional[Any] = None  # StudyDesignResult from classifier
    regeneration_count: int = 0
    warnings: List[str] = field(default_factory=list)
    error: str = ""


# =============================================================================
# PRODUCTION PIPELINE
# =============================================================================

class ProductionSAPPipeline:
    """
    Production-grade SAP generation with explicit source priority.

    Architecture:
    1. EXTRACTION → Structured facts (GROUND TRUTH for all numbers)
    2. KNOWLEDGE GRAPH → Method constraints (what methods to use)
    3. RAG → Sanitized examples (prose style only, numbers stripped)
    4. GENERATION → Constrained prompts with explicit source attribution
    5. VERIFICATION → SELF-RAG pattern with correction loop
    """

    # SAP sections to generate
    SECTIONS = [
        ('introduction', 'Introduction'),
        ('objectives', 'Study Objectives and Endpoints'),
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
        """
        Initialize production pipeline.

        Args:
            max_regenerations: Max times to regenerate on verification failure
        """
        self.max_regenerations = max_regenerations

        # Initialize components
        print("[ProductionPipeline] Initializing components...")

        # 1. Extractor (Ground Truth)
        self.extractor = None
        if ClaudeProtocolExtractor:
            try:
                self.extractor = ClaudeProtocolExtractor()
                print("[ProductionPipeline] ✓ ClaudeProtocolExtractor initialized")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ Extractor failed: {e}")

        # 2. Knowledge Graph (Method Selection)
        self.knowledge_graph = None
        if KnowledgeRuleEngine:
            try:
                self.knowledge_graph = KnowledgeRuleEngine()
                print(f"[ProductionPipeline] ✓ KnowledgeRuleEngine loaded ({len(self.knowledge_graph.rules)} rules)")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ Knowledge graph failed: {e}")

        # 3. RAG (Prose Style)
        self.rag = None
        if create_vector_store:
            try:
                self.rag = create_vector_store()
                print("[ProductionPipeline] ✓ ChromaDB RAG connected")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ RAG failed: {e}")

        # 4. RAG Sanitizer
        self.sanitizer = None
        if RAGSanitizer:
            self.sanitizer = RAGSanitizer(aggressive=True)
            print("[ProductionPipeline] ✓ RAG Sanitizer initialized")

        # 5. Fact Verifier (SELF-RAG)
        self.verifier = None
        if FactVerifier:
            self.verifier = FactVerifier()
            print("[ProductionPipeline] ✓ Fact Verifier initialized")

        # 6. LLM Client
        self.llm = None
        if TieredLLMClient:
            try:
                self.llm = TieredLLMClient()
                print("[ProductionPipeline] ✓ LLM client initialized")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ LLM failed: {e}")

        # 7. Drug Classifier (Ontology Integration)
        self.drug_classifier = None
        if DrugClassifier:
            try:
                self.drug_classifier = create_drug_classifier(llm_client=self.llm)
                print("[ProductionPipeline] ✓ DrugClassifier initialized (NCI Thesaurus + LLM fallback)")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ Drug classifier failed: {e}")

        # 8. Study Design Classifier (Hybrid: RAG + LLM for accuracy)
        self.study_design_classifier = None
        self.hybrid_classifier = None

        # Try hybrid classifier first (more accurate)
        if HybridDesignClassifier and self.rag and self.llm:
            try:
                self.hybrid_classifier = create_hybrid_classifier(
                    rag_store=self.rag,
                    llm_client=self.llm
                )
                print("[ProductionPipeline] ✓ HybridDesignClassifier initialized (RAG + LLM)")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ Hybrid classifier failed: {e}")

        # Fall back to rule-based if hybrid unavailable
        if not self.hybrid_classifier and StudyDesignClassifier:
            try:
                self.study_design_classifier = StudyDesignClassifier()
                print("[ProductionPipeline] ✓ StudyDesignClassifier initialized (rule-based fallback)")
            except Exception as e:
                print(f"[ProductionPipeline] ✗ Study design classifier failed: {e}")

    def generate(self, protocol_text: str) -> GenerationResult:
        """
        Generate SAP using production pipeline.

        Steps:
        1. Extract structured facts (GROUND TRUTH)
        2. Get method constraints from knowledge graph
        3. Get sanitized RAG examples (numbers stripped)
        4. Generate with constrained prompts
        5. Verify and regenerate if needed (SELF-RAG)
        """
        try:
            # STEP 1: Extract facts (GROUND TRUTH)
            print("\n[Step 1] Extracting facts (GROUND TRUTH)...")
            facts = self._extract_facts(protocol_text)
            print(f"[Step 1] Extracted: {facts.get('nct_id')}, {facts.get('sample_size')} patients")

            # DEBUG: Log critical fields that often fail
            print(f"[Step 1] statistical_method: '{facts.get('statistical_method', 'NOT FOUND')}'")
            print(f"[Step 1] statistical_method_details: '{facts.get('statistical_method_details', 'NOT FOUND')}'")
            print(f"[Step 1] treatment_setting: '{facts.get('treatment_setting', 'NOT FOUND')}'")
            print(f"[Step 1] has_interim_analysis: {facts.get('has_interim_analysis', 'NOT FOUND')}")
            print(f"[Step 1] num_interim_analyses: {facts.get('num_interim_analyses', 'NOT FOUND')}")

            # STEP 1.5: Classify study design (Hybrid: RAG + LLM > Rule-based)
            study_design_result = None

            # Try HYBRID classifier first (more accurate - uses LLM reasoning)
            if self.hybrid_classifier:
                print("\n[Step 1.5] Classifying study design (HYBRID: RAG + LLM)...")
                study_design_result = self.hybrid_classifier.classify(protocol_text, facts)
                print(f"[Step 1.5] Design: {study_design_result.design_type.value}")
                print(f"[Step 1.5] Approach: {study_design_result.statistical_approach.value}")
                print(f"[Step 1.5] Confidence: {study_design_result.confidence:.1%}")
                print(f"[Step 1.5] Source: {study_design_result.classification_source}")
                if study_design_result.confidence_reasoning:
                    print(f"[Step 1.5] Reasoning: {study_design_result.confidence_reasoning[:100]}...")
                if study_design_result.requires_review:
                    print(f"[Step 1.5] ⚠ REQUIRES REVIEW: {study_design_result.review_reasons}")

            # Fall back to rule-based if hybrid unavailable
            elif self.study_design_classifier:
                print("\n[Step 1.5] Classifying study design (rule-based fallback)...")
                study_design_result = self.study_design_classifier.classify(protocol_text, facts)
                print(f"[Step 1.5] Design: {study_design_result.design_type.value}")
                print(f"[Step 1.5] Approach: {study_design_result.statistical_approach.value}")
                print(f"[Step 1.5] Confidence: {study_design_result.confidence:.1%} (rule-based)")
                if study_design_result.requires_review:
                    print(f"[Step 1.5] ⚠ REQUIRES REVIEW: {study_design_result.review_reasons}")

            # CRITICAL: Update facts with classifier results (works for both hybrid and rule-based)
            if study_design_result:
                facts['phase'] = study_design_result.phase
                facts['is_single_arm'] = not study_design_result.is_randomized
                facts['treatment_setting'] = study_design_result.treatment_setting
                facts['study_design_confidence'] = study_design_result.confidence
                facts['study_design_requires_review'] = study_design_result.requires_review

                # Handle different result types (hybrid vs rule-based)
                if hasattr(study_design_result, 'is_pilot'):
                    facts['is_pilot_study'] = study_design_result.is_pilot
                if hasattr(study_design_result, 'time_origin'):
                    facts['time_origin'] = study_design_result.time_origin
                if hasattr(study_design_result, 'has_interim_analysis'):
                    facts['has_interim_analysis'] = study_design_result.has_interim_analysis

                # Determine if hypothesis testing based on approach
                approach_value = study_design_result.statistical_approach.value
                facts['hypothesis_testing_planned'] = approach_value != 'descriptive_only'

                # Store classification source
                if hasattr(study_design_result, 'classification_source'):
                    facts['classification_source'] = study_design_result.classification_source
                else:
                    facts['classification_source'] = 'rule_based'

            # STEP 2: Get method constraints (with Drug Classification)
            print("\n[Step 2] Getting method constraints from Knowledge Graph...")
            conditions, drug_classification = self._detect_conditions(facts, protocol_text)
            constraints = self._get_constraints_from_design(facts, conditions, study_design_result)
            print(f"[Step 2] Primary test: {constraints.primary_test}")
            print(f"[Step 2] Conditions: {conditions}")
            if drug_classification:
                print(f"[Step 2] Drug: {drug_classification.drug_name} → {drug_classification.drug_class} ({drug_classification.source})")

            # STEP 3: Get sanitized RAG examples
            print("\n[Step 3] Getting sanitized RAG examples (numbers stripped)...")
            sanitized_examples = self._get_sanitized_examples(facts)
            print(f"[Step 3] Retrieved {sum(len(v) for v in sanitized_examples.values())} sanitized examples")

            # STEP 4: Generate sections
            print("\n[Step 4] Generating SAP sections with constrained prompts...")
            sections = self._generate_all_sections(facts, constraints, sanitized_examples)

            # Assemble full SAP
            sap_text = self._assemble_sap(sections, facts)

            # STEP 5: Verify and regenerate if needed (SELF-RAG)
            print("\n[Step 5] Verifying against extracted facts (SELF-RAG)...")
            verification, sap_text, regeneration_count = self._verify_and_correct(
                sap_text, facts, constraints
            )

            if verification and verification.passed:
                print(f"[Step 5] ✓ Verification PASSED (score: {verification.score:.2f})")
            else:
                print(f"[Step 5] ⚠ Verification completed with issues after {regeneration_count} regenerations")

            return GenerationResult(
                success=True,
                sap_text=sap_text,
                sections=sections,
                facts=facts,
                constraints=constraints,
                verification=verification,
                drug_classification=drug_classification,
                study_design=study_design_result,
                regeneration_count=regeneration_count
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return GenerationResult(
                success=False,
                error=str(e)
            )

    def _extract_facts(self, protocol_text: str) -> Dict[str, Any]:
        """
        Step 1: Extract structured facts using Claude LLM.
        These are the GROUND TRUTH - single source for all numerical values.
        """
        if self.extractor:
            try:
                extracted = self.extractor.extract(protocol_text)
                if extracted:
                    # Convert to dict
                    if hasattr(extracted, 'dict'):
                        facts = extracted.dict()
                    elif hasattr(extracted, '__dict__'):
                        facts = {k: v for k, v in extracted.__dict__.items() if not k.startswith('_')}
                    else:
                        facts = dict(extracted)

                    # CRITICAL: Preserve raw_text for fallback extraction
                    facts['raw_text'] = protocol_text.lower()

                    # Normalize field names for consistency
                    facts = self._normalize_facts(facts)

                    # Log what was extracted
                    print(f"[Extraction] Randomization ratio: {facts.get('randomization_ratio', 'NOT FOUND')}")

                    return facts
            except Exception as e:
                print(f"[Extraction] Error: {e}")

        # Fallback to basic extraction
        return self._basic_extraction(protocol_text)

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

        # CRITICAL: Extract randomization ratio if missing (fallback from raw_text)
        if not normalized.get('randomization_ratio') and normalized.get('raw_text'):
            raw_text = normalized['raw_text']
            ratio_patterns = [
                r'(\d+:\d+(?::\d+)?)\s*(?:randomization|allocation)',
                r'(?:randomiz|allocat)\w*\s*(?:in\s+a\s+)?(\d+:\d+(?::\d+)?)',
                r'\((\d+:\d+(?::\d+)?)\)\s*(?:ratio|randomization)?',
            ]
            for pattern in ratio_patterns:
                ratio_match = re.search(pattern, raw_text, re.IGNORECASE)
                if ratio_match:
                    normalized['randomization_ratio'] = ratio_match.group(1)
                    print(f"[Normalize] Extracted ratio from raw text: {normalized['randomization_ratio']}")
                    break

        return normalized

    def _basic_extraction(self, text: str) -> Dict[str, Any]:
        """Fallback basic extraction."""
        facts = {'raw_text': text.lower()}

        # NCT ID
        nct_match = re.search(r'NCT\d{8}', text, re.IGNORECASE)
        if nct_match:
            facts['nct_id'] = nct_match.group()

        # Sample size
        size_match = re.search(r'(\d+)\s*(?:patients|subjects|participants)', text, re.IGNORECASE)
        if size_match:
            facts['sample_size'] = int(size_match.group(1))

        # Events - distinguish between final and interim
        # Final events patterns (order matters - most specific first)
        final_patterns = [
            r'(?:final\s+analysis)[:\s]*(\d+)\s*(?:os\s+)?(?:deaths?|events?)',
            r'(?:final)[:\s]*(\d+)\s*(?:os\s+)?(?:deaths?|events?)',
            r'(\d+)\s*(?:os\s+)?(?:deaths?|events?)\s*(?:for\s+)?(?:final|at\s+final)',
            r'(?:total|planned)[:\s]*(\d+)\s*(?:os\s+)?(?:deaths?|events?)',
        ]
        for pattern in final_patterns:
            final_match = re.search(pattern, text, re.IGNORECASE)
            if final_match:
                facts['final_events'] = int(final_match.group(1))
                break

        # Interim events patterns
        interim_patterns = [
            r'(?:interim\s+analysis)[:\s]*(?:at\s+)?(\d+)\s*(?:deaths?|events?)',
            r'(?:interim)[:\s]*(?:at\s+)?(\d+)\s*(?:deaths?|events?)',
            r'(\d+)\s*(?:deaths?|events?)\s*(?:for\s+)?(?:interim)',
            r'(?:at\s+)?(\d+)\s*(?:deaths?|events?).*?(?:interim)',
        ]
        for pattern in interim_patterns:
            interim_match = re.search(pattern, text, re.IGNORECASE)
            if interim_match:
                candidate = int(interim_match.group(1))
                # Don't confuse with final events
                if candidate != facts.get('final_events'):
                    facts['interim_events'] = candidate
                    break

        # Fallback if no final events found but we have a number
        if not facts.get('final_events'):
            events_match = re.search(r'(\d+)\s*(?:deaths?|events?|os events?)', text, re.IGNORECASE)
            if events_match:
                facts['final_events'] = int(events_match.group(1))

        # CRITICAL: Randomization ratio extraction
        # Multiple patterns to catch different formats
        ratio_patterns = [
            # "2:1 randomization", "randomization 2:1"
            r'(\d+:\d+(?::\d+)?)\s*(?:randomization|allocation)',
            r'(?:randomiz|allocat)\w*\s*(?:in\s+a\s+)?(\d+:\d+(?::\d+)?)',
            # "randomized 2 to 1", "2 to 1 ratio"
            r'(\d+)\s*(?:to|:)\s*(\d+)(?:\s*(?:to|:)\s*(\d+))?\s*(?:ratio|randomization)',
            # "randomized to [drug] or [comparator] (2:1)"
            r'\((\d+:\d+(?::\d+)?)\)',
        ]
        for pattern in ratio_patterns:
            ratio_match = re.search(pattern, text, re.IGNORECASE)
            if ratio_match:
                groups = ratio_match.groups()
                # Handle "2 to 1" format
                if len(groups) >= 2 and groups[1] and groups[0].isdigit():
                    if len(groups) >= 3 and groups[2]:
                        facts['randomization_ratio'] = f"{groups[0]}:{groups[1]}:{groups[2]}"
                    else:
                        facts['randomization_ratio'] = f"{groups[0]}:{groups[1]}"
                else:
                    # Handle "2:1" format
                    facts['randomization_ratio'] = groups[0]
                break

        # Drug name
        drug_patterns = [
            r'(?:nivolumab|pembrolizumab|atezolizumab|durvalumab|avelumab)',
            r'(?:BMS-\d+|MK-\d+)',
        ]
        for pattern in drug_patterns:
            drug_match = re.search(pattern, text, re.IGNORECASE)
            if drug_match:
                facts['drug_name'] = drug_match.group()
                break

        # Stratification factors - more robust extraction
        strat_patterns = [
            # "stratified by X, Y, and Z"
            r'stratif\w*\s+(?:by|according to)[:\s]*([^.\n]+)',
            # "stratification factors: X, Y, Z"
            r'stratification factors?\s*[:\s]+([^.\n]+)',
            # Look for bullet list after "stratified"
            r'stratif\w*\s+(?:by|according to)[:\s]*\n((?:\s*[-•]\s*[^\n]+\n?)+)',
        ]

        for pattern in strat_patterns:
            strat_match = re.search(pattern, text, re.IGNORECASE)
            if strat_match:
                strat_text = strat_match.group(1)
                # Clean up and parse factors
                # Handle bullet points (only at start of line/item, not hyphens within words)
                if re.search(r'(?:^|\n)\s*[-•]\s*\w', strat_text):
                    factors = re.split(r'(?:^|\n)\s*[-•]\s*', strat_text)
                else:
                    # Split on comma and "and" but not hyphens
                    factors = re.split(r'\s*(?:,\s*(?:and\s+)?|(?:\s+and\s+))', strat_text.strip())
                # Clean up each factor
                clean_factors = []
                for f in factors:
                    f = f.strip()
                    if f and len(f) < 100:  # Sanity check on length
                        clean_factors.append(f)
                if clean_factors:
                    facts['stratification_factors'] = clean_factors
                    break

        # Subgroup analyses extraction
        subgroup_match = re.search(
            r'(?:subgroup|subgroups)\s+(?:analys|includ)[^:]*[:\s]*([^.]+(?:\.[^.]+)?)',
            text, re.IGNORECASE
        )
        if subgroup_match:
            sg_text = subgroup_match.group(1)
            # Parse common subgroup factors
            subgroups = re.split(r'\s*(?:,|;|\band\b)\s*', sg_text.strip())
            clean_subgroups = [s.strip() for s in subgroups if s.strip() and len(s.strip()) < 80]
            if clean_subgroups:
                facts['subgroup_analyses'] = clean_subgroups

        # Bridging/consistency study detection
        if any(term in text.lower() for term in ['bridging', 'consistency', 'regional', 'checkmate 057', 'checkmate 017']):
            facts['is_bridging_study'] = True
            facts['has_consistency_objective'] = True

            # Try to find reference studies
            ref_match = re.findall(r'(CheckMate\s*\d+|KEYNOTE[- ]\d+)', text, re.IGNORECASE)
            if ref_match:
                facts['consistency_reference_studies'] = list(set(ref_match))

        # Hierarchical testing detection
        if 'hierarchic' in text.lower() or 'gatekeep' in text.lower():
            facts['has_hierarchical_testing'] = True
            # Try to extract order
            order_match = re.search(
                r'(?:order|sequence|first|then)[:\s]*([^.]+)',
                text, re.IGNORECASE
            )
            if order_match:
                order_text = order_match.group(1)
                # Look for OS, ORR, PFS patterns
                endpoints = re.findall(r'\b(OS|PFS|ORR|DOR|TTF)\b', order_text, re.IGNORECASE)
                if endpoints:
                    facts['hierarchical_testing_order'] = [e.upper() for e in endpoints]

        # TTF/Regulatory interim detection
        if 'ttf' in text.lower() and 'china' in text.lower():
            facts['has_regulatory_interim'] = True
            facts['regulatory_interim_endpoint'] = 'TTF'
            facts['regulatory_interim_region'] = 'China'
            # Look for timing
            timing_match = re.search(r'(\d+)\s*(?:subjects?|patients?)', text, re.IGNORECASE)
            if timing_match:
                facts['regulatory_interim_timing'] = f"~{timing_match.group(1)} subjects"

        # =====================================================================
        # CRITICAL: STUDY TYPE DETECTION
        # This determines whether to apply comparative or descriptive statistics
        # =====================================================================
        text_lower = text.lower()

        # 1. Detect Phase (I, II, III, IV)
        phase_match = re.search(r'phase\s*([1-4]|i{1,3}v?|iv)', text, re.IGNORECASE)
        if phase_match:
            phase_raw = phase_match.group(1).lower()
            phase_map = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, '1': 1, '2': 2, '3': 3, '4': 4}
            facts['phase'] = phase_map.get(phase_raw, int(phase_raw) if phase_raw.isdigit() else 2)
        else:
            facts['phase'] = 3  # Default to Phase III

        # 2. Detect Single-Arm vs Comparative
        is_single_arm = (
            'single-arm' in text_lower or
            'single arm' in text_lower or
            'one-arm' in text_lower or
            facts.get('num_arms', 2) == 1 or
            (not any(term in text_lower for term in ['versus', ' vs ', 'compared to', 'comparator', 'control arm', 'placebo arm']))
        )
        facts['is_single_arm'] = is_single_arm

        # 3. Detect Pilot/Feasibility Study
        is_pilot = (
            'pilot' in text_lower or
            'feasibility' in text_lower or
            'exploratory' in text_lower or
            'proof-of-concept' in text_lower or
            'proof of concept' in text_lower or
            (facts.get('sample_size', 100) <= 50 and facts.get('phase', 3) <= 2)
        )
        facts['is_pilot_study'] = is_pilot

        # 4. Detect Neoadjuvant/Adjuvant Setting
        # PRIORITY: Use Claude-extracted treatment_setting if available
        # FALLBACK: Only use keyword detection if Claude didn't extract it
        claude_setting = facts.get('treatment_setting', '')
        if claude_setting and claude_setting not in ['', 'empty', 'unknown']:
            print(f"[BasicExtraction] Using Claude-extracted setting: {claude_setting}")
            # Claude already set it, determine time_origin
            if 'neoadjuvant' in claude_setting.lower() or 'adjuvant' in claude_setting.lower():
                facts['time_origin'] = 'surgery'
            else:
                facts['time_origin'] = 'randomization'
        else:
            # FALLBACK: Keyword detection - but be more careful
            # Only trigger neoadjuvant if it's in the title or primary objectives
            title = str(facts.get('protocol_title', '')).lower()
            is_neoadjuvant_study = 'neoadjuvant' in title or 'neo-adjuvant' in title
            is_adjuvant_study = 'adjuvant' in title and 'neoadjuvant' not in title

            if is_neoadjuvant_study:
                facts['treatment_setting'] = 'neoadjuvant'
                facts['time_origin'] = 'surgery'
            elif is_adjuvant_study:
                facts['treatment_setting'] = 'adjuvant'
                facts['time_origin'] = 'surgery'
            else:
                # Not found in title - flag for review but use safe default for time_origin
                facts['treatment_setting'] = '[TREATMENT SETTING NOT EXTRACTED - NEEDS REVIEW]'
                facts['time_origin'] = 'randomization'  # Safe default - most trials use this
                print(f"[BasicExtraction] ⚠ WARNING: treatment_setting NOT EXTRACTED - flagging for review")

        # 5. Detect No Hypothesis Testing (descriptive only)
        no_hypothesis_testing = (
            'no formal sample size' in text_lower or
            'no statistical test' in text_lower or
            'descriptive' in text_lower or
            'no hypothesis test' in text_lower or
            is_pilot or
            (is_single_arm and facts.get('phase', 3) <= 2)
        )
        facts['hypothesis_testing_planned'] = not no_hypothesis_testing

        # 6. Detect if Interim Analysis is Explicitly Mentioned
        facts['has_interim_analysis'] = bool(
            re.search(r'interim\s+analysis', text, re.IGNORECASE) and
            not re.search(r'no\s+interim', text, re.IGNORECASE)
        )

        # 7. Detect Pathologic Response Criteria (neoadjuvant specific)
        if 'junker' in text_lower:
            facts['pathologic_response_criteria'] = 'Junker criteria'
        elif 'miller-payne' in text_lower or 'miller payne' in text_lower:
            facts['pathologic_response_criteria'] = 'Miller-Payne'
        elif 'pcr' in text_lower or 'pathologic complete response' in text_lower:
            facts['pathologic_response_criteria'] = 'pCR'

        # 8. Detect Response Criteria (RECIST, etc.)
        if 'recist 1.1' in text_lower:
            facts['response_criteria'] = 'RECIST 1.1'
        elif 'recist' in text_lower:
            facts['response_criteria'] = 'RECIST'
        elif 'irecist' in text_lower:
            facts['response_criteria'] = 'iRECIST'

        # Log study type for debugging
        print(f"[StudyType] Phase: {facts.get('phase')}, Single-arm: {is_single_arm}, Pilot: {is_pilot}")
        print(f"[StudyType] Setting: {facts.get('treatment_setting')}, Hypothesis testing: {facts.get('hypothesis_testing_planned')}")

        return facts

    def _detect_conditions(self, facts: Dict[str, Any], protocol_text: str) -> Tuple[List[str], Optional[Any]]:
        """
        Step 2a: Detect conditions for method selection.

        Uses Drug Classifier with ontology integration for accurate classification.

        Returns:
            Tuple of (conditions list, drug_classification)
        """
        conditions = set()
        drug_classification = None

        # STEP 1: Classify drug using ontology (NCI Thesaurus → LLM fallback)
        drug_name = facts.get('drug_name', '')
        if drug_name and self.drug_classifier:
            drug_classification = self.drug_classifier.classify(drug_name)

            if drug_classification:
                # Get statistical implications from classification
                implications = self.drug_classifier.get_statistical_implications(drug_classification)
                conditions.update(implications.get('conditions_to_add', []))

                # Log classification source
                print(f"[Conditions] Drug '{drug_name}' classified as {drug_classification.drug_class}")
                print(f"[Conditions]   Source: {drug_classification.source}, Confidence: {drug_classification.confidence:.2f}")
                if drug_classification.expects_delayed_effect:
                    print(f"[Conditions]   → Expects delayed effect (use Fleming-Harrington)")

        # STEP 2: Use Knowledge Graph for additional conditions
        if self.knowledge_graph:
            facts_with_text = {**facts, 'raw_text': protocol_text.lower()}
            kg_conditions = self.knowledge_graph.detect_conditions(facts_with_text)
            conditions.update(kg_conditions)

        # STEP 3: Text-based fallback for conditions not detected by KG
        text_lower = protocol_text.lower()

        # Time-to-event endpoints
        if any(x in text_lower for x in ['survival', 'os', 'pfs', 'time to', 'time-to-event']):
            conditions.add('time_to_event')

        # Crossover/treatment switching
        if 'crossover' in text_lower or 'cross-over' in text_lower:
            conditions.add('crossover')
            conditions.add('treatment_switching')

        # Interim analysis
        if 'interim' in text_lower:
            conditions.add('interim_analysis')

        # Stratification
        if 'stratif' in text_lower:
            conditions.add('stratified')

        # Non-proportional hazards (from drug classification or text)
        if drug_classification and drug_classification.expects_non_proportional_hazards:
            conditions.add('non_proportional_hazards')

        return list(conditions), drug_classification

    def _get_constraints(self, facts: Dict[str, Any], conditions: List[str]) -> MethodConstraints:
        """
        Step 2b: Get method constraints based on study type.

        CRITICAL: Different study types require completely different statistical approaches:
        - Phase III comparative: Log-rank, Cox, Fleming-Harrington
        - Phase II single-arm: Descriptive statistics only (Kaplan-Meier, binomial CI)
        - Pilot/feasibility: No formal hypothesis testing
        """
        constraints = MethodConstraints(conditions_detected=conditions)

        # =====================================================================
        # CRITICAL: Check study type FIRST before applying any methods
        # =====================================================================
        is_single_arm = facts.get('is_single_arm', False)
        is_pilot = facts.get('is_pilot_study', False)
        phase = facts.get('phase', 3)
        hypothesis_testing = facts.get('hypothesis_testing_planned', True)
        has_interim = facts.get('has_interim_analysis', False)
        treatment_setting = facts.get('treatment_setting', 'metastatic')

        # =====================================================================
        # PHASE II SINGLE-ARM / PILOT STUDIES: Descriptive statistics only
        # =====================================================================
        if is_single_arm or is_pilot or (phase <= 2 and not hypothesis_testing):
            print(f"[Constraints] Applying DESCRIPTIVE approach (Phase {phase}, single-arm={is_single_arm}, pilot={is_pilot})")

            constraints.primary_test = "Descriptive statistics only (no comparative hypothesis testing)"
            constraints.forbidden_primary = "log-rank test, Cox regression, Fleming-Harrington (comparative methods inappropriate for single-arm study)"

            # Time-to-event: Kaplan-Meier descriptive only
            if 'time_to_event' in conditions:
                constraints.nph_methods = []  # No NPH methods for single-arm
                constraints.sensitivity_methods = []  # No sensitivity analyses for single-arm
                constraints.descriptive_methods = [
                    "Kaplan-Meier survival curves",
                    "Median survival with 95% CI",
                    "Survival rates at landmark timepoints (6, 12, 24 months)"
                ]

            # Binary endpoints: Binomial exact methods
            constraints.binary_methods = [
                "Response rate with exact binomial 95% CI (Clopper-Pearson or Wilson)",
                "Descriptive proportions"
            ]

            # Sample size: No formal power calculation
            if is_pilot:
                constraints.sample_size_approach = "No formal sample size estimation - exploratory/pilot study"
            else:
                constraints.sample_size_approach = "Sample size based on precision (confidence interval width) rather than power"

            # No interim analysis for single-arm unless explicitly stated
            if not has_interim:
                constraints.interim_method = None
                constraints.alpha_spending = None

            # Neoadjuvant-specific
            if treatment_setting == 'neoadjuvant':
                constraints.time_origin = "surgery (not enrollment)"
                constraints.neoadjuvant_methods = [
                    "Pathologic response grading per protocol-specified criteria",
                    "DFS/OS measured from date of surgery"
                ]
                if facts.get('pathologic_response_criteria'):
                    constraints.pathologic_criteria = facts['pathologic_response_criteria']

            return constraints

        # =====================================================================
        # PHASE III COMPARATIVE STUDIES: Full inferential statistics
        # =====================================================================
        print(f"[Constraints] Applying COMPARATIVE approach (Phase {phase})")

        if self.knowledge_graph:
            methods = self.knowledge_graph.get_primary_analysis_methods(facts)

            if methods:
                primary = methods.get('primary_test', {})
                if primary:
                    constraints.primary_test = primary.get('description', primary.get('method', ''))

                # NPH methods
                nph = methods.get('nph_methods', [])
                constraints.nph_methods = [m.get('method', m) if isinstance(m, dict) else m for m in nph]

                # Interim - only if explicitly in protocol
                if has_interim:
                    interim = methods.get('interim_analysis_method', {})
                    if interim:
                        constraints.interim_method = interim.get('method', '')
                        constraints.alpha_spending = "O'Brien-Fleming"

        # =================================================================
        # CRITICAL: Protocol-extracted methods OVERRIDE inference rules
        # =================================================================
        protocol_method = facts.get('statistical_method', '') or facts.get('statistical_method_details', '')

        if protocol_method:
            # USE WHAT THE PROTOCOL SAYS - don't infer!
            print(f"[Constraints] Using PROTOCOL-SPECIFIED method: {protocol_method}")
            constraints.primary_test = protocol_method
            constraints.forbidden_primary = ""
        else:
            # NO DEFAULT - flag for review
            print(f"[Constraints] ⚠ WARNING: statistical_method NOT EXTRACTED - flagging for review")
            constraints.primary_test = "[STATISTICAL METHOD NOT FOUND IN PROTOCOL - NEEDS REVIEW]"
            constraints.forbidden_primary = ""
            # Add to warnings
            if not hasattr(constraints, 'warnings'):
                constraints.warnings = []

        # Only add interim methods if protocol has interim analysis
        if has_interim and 'interim_analysis' in conditions and not constraints.interim_method:
            constraints.interim_method = "Lan-DeMets"
            constraints.alpha_spending = "O'Brien-Fleming"

        return constraints

    def _get_constraints_from_design(
        self,
        facts: Dict[str, Any],
        conditions: List[str],
        study_design_result: Optional[Any]
    ) -> MethodConstraints:
        """
        Get method constraints using the study design classification result.

        Supports both:
        - HybridClassificationResult (RAG + LLM based - more accurate)
        - StudyDesignResult (rule-based - fallback)

        Args:
            facts: Extracted protocol facts
            conditions: Detected conditions (immunotherapy, crossover, etc.)
            study_design_result: Result from either classifier

        Returns:
            MethodConstraints with appropriate methods for the study design
        """
        # If no classifier result, fall back to keyword-based approach
        if not study_design_result:
            return self._get_constraints(facts, conditions)

        constraints = MethodConstraints(conditions_detected=conditions)

        # Get statistical constraints from the classifier (both types have this method)
        stat_constraints = study_design_result.get_statistical_constraints()

        # Get approach value (works for both enum types)
        approach_value = study_design_result.statistical_approach.value

        # =====================================================================
        # DESCRIPTIVE STUDIES (Phase II single-arm, pilot, etc.)
        # =====================================================================
        if approach_value == 'descriptive_only':
            print(f"[Constraints] Using DESCRIPTIVE approach from classifier (confidence: {study_design_result.confidence:.1%})")

            constraints.primary_test = stat_constraints.get('primary_test', 'Descriptive statistics only')
            constraints.forbidden_primary = ', '.join(stat_constraints.get('forbidden', []))
            constraints.sample_size_approach = stat_constraints.get('sample_size_approach', '')

            # Time-to-event descriptive methods
            if 'time_to_event' in conditions:
                constraints.descriptive_methods = [
                    "Kaplan-Meier survival curves",
                    "Median survival with 95% CI",
                    "Survival rates at landmark timepoints (6, 12, 24 months)"
                ]

            # Binary endpoint methods
            constraints.binary_methods = [
                "Response rate with exact binomial 95% CI (Clopper-Pearson)",
                "Descriptive proportions"
            ]

            # Neoadjuvant-specific
            if study_design_result.treatment_setting == 'neoadjuvant':
                constraints.time_origin = "surgery (not enrollment)"
                constraints.neoadjuvant_methods = [
                    "Pathologic response grading per protocol-specified criteria",
                    "DFS/OS measured from date of surgery"
                ]
                if facts.get('pathologic_response_criteria'):
                    constraints.pathologic_criteria = facts['pathologic_response_criteria']

            # No interim for descriptive studies unless explicit
            if not study_design_result.has_interim_analysis:
                constraints.interim_method = None
                constraints.alpha_spending = None

            return constraints

        # =====================================================================
        # SIMON'S TWO-STAGE DESIGN
        # =====================================================================
        if approach_value == 'simon_two_stage':
            print(f"[Constraints] Using SIMON TWO-STAGE approach from classifier")

            constraints.primary_test = "Simon's two-stage design"
            constraints.forbidden_primary = "log-rank test, Cox regression (not appropriate for binary endpoint)"
            constraints.binary_methods = [
                "Stage 1 analysis with stopping rule",
                "Stage 2 final analysis",
                "Response rate with exact binomial 95% CI"
            ]
            constraints.sample_size_approach = "Simon's optimal or minimax design"
            constraints.interim_method = "Simon's two-stage stopping rule"

            return constraints

        # =====================================================================
        # COMPARATIVE STUDIES (Phase III RCT, Phase II RCT)
        # =====================================================================
        print(f"[Constraints] Using COMPARATIVE approach from classifier (confidence: {study_design_result.confidence:.1%})")

        # Use knowledge graph for comparative study methods
        if self.knowledge_graph:
            methods = self.knowledge_graph.get_primary_analysis_methods(facts)

            if methods:
                primary = methods.get('primary_test', {})
                if primary:
                    constraints.primary_test = primary.get('description', primary.get('method', ''))

                # NPH methods
                nph = methods.get('nph_methods', [])
                constraints.nph_methods = [m.get('method', m) if isinstance(m, dict) else m for m in nph]

                # Interim - only if explicitly in protocol
                if study_design_result.has_interim_analysis:
                    interim = methods.get('interim_analysis_method', {})
                    if interim:
                        constraints.interim_method = interim.get('method', '')
                        constraints.alpha_spending = "O'Brien-Fleming"

        # =================================================================
        # CRITICAL: Protocol-extracted methods OVERRIDE inference rules
        # =================================================================
        protocol_method = facts.get('statistical_method', '') or facts.get('statistical_method_details', '')

        if protocol_method:
            # USE WHAT THE PROTOCOL SAYS - don't infer!
            print(f"[Constraints] Using PROTOCOL-SPECIFIED method: {protocol_method}")
            constraints.primary_test = protocol_method
            constraints.forbidden_primary = ""
        else:
            # NO DEFAULT - flag for review
            print(f"[Constraints] ⚠ WARNING: statistical_method NOT EXTRACTED - flagging for review")
            constraints.primary_test = "[STATISTICAL METHOD NOT FOUND IN PROTOCOL - NEEDS REVIEW]"
            constraints.forbidden_primary = ""

        # Interim analysis for comparative studies
        if study_design_result.has_interim_analysis and 'interim_analysis' in conditions:
            if not constraints.interim_method:
                constraints.interim_method = "Lan-DeMets"
                constraints.alpha_spending = "O'Brien-Fleming"

        return constraints

    # Wrong indication patterns to filter out during retrieval
    WRONG_INDICATION_PATTERNS = {
        'NSCLC': [r'\bmRCC\b', r'\brenal cell\b', r'\bkidney cancer\b',
                  r'\bhepatocellular\b', r'\bHCC\b', r'\bmelanoma\b',
                  r'\burothelial\b', r'\bbladder\b', r'\bEGFR.mutant\b',
                  r'\bosimertinib\b', r'\bpemetrexed\b', r'\bplatinum\b'],
        'RCC': [r'\bNSCLC\b', r'\bnon.small cell lung\b', r'\blung cancer\b',
                r'\bhepatocellular\b', r'\bHCC\b', r'\bmelanoma\b'],
        'HCC': [r'\bNSCLC\b', r'\blung cancer\b', r'\bmRCC\b', r'\brenal\b',
                r'\bmelanoma\b', r'\burothelial\b'],
        'MELANOMA': [r'\bNSCLC\b', r'\blung\b', r'\bmRCC\b', r'\brenal\b',
                     r'\bhepatocellular\b', r'\bHCC\b'],
    }

    # Wrong drug patterns (monotherapy vs combination)
    WRONG_DRUG_PATTERNS = {
        'nivolumab_mono': [r'\bnivo.*ipi\b', r'\bipilimumab\b', r'\bcombination\b',
                           r'\bnivolumab\s*\+', r'\bwith\s+ipilimumab\b'],
        'nivolumab_combo': [r'\bmonotherapy\b', r'\bsingle.agent\b'],
    }

    def _get_sanitized_examples(self, facts: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Step 3: Get RAG examples with STRICT filtering and sanitization.

        CRITICAL: Filter by indication and drug to prevent cross-study contamination.
        RAG is for PROSE STYLE only, not for facts.
        """
        examples = {}

        if not self.rag:
            return examples

        # Build query from facts
        query_parts = []
        for key in ['primary_endpoint', 'indication', 'drug_name']:
            value = facts.get(key)
            if value and isinstance(value, str):
                query_parts.append(value)

        query = ' '.join(query_parts) if query_parts else 'oncology phase 3 survival'

        # CRITICAL: Build filters from extracted facts
        filters = self._build_rag_filters(facts)
        print(f"[RAG] Query: '{query[:50]}...' with filters: {filters}")

        # Detect if this is monotherapy or combination
        drug_name = str(facts.get('drug_name') or '').lower()
        is_monotherapy = 'mono' in drug_name or facts.get('num_arms', 0) == 2

        # Get current indication for post-filter
        indication = str(facts.get('indication') or '').upper()
        if not indication:
            # Try to infer from therapeutic area
            ta = str(facts.get('therapeutic_area') or '').upper()
            if 'LUNG' in ta:
                indication = 'NSCLC'
            elif 'RENAL' in ta or 'KIDNEY' in ta:
                indication = 'RCC'

        # Query and sanitize each section type
        section_types = ['methods', 'interim_analysis', 'sensitivity_analysis', 'sample_size']

        for section_type in section_types:
            try:
                # Query WITH filters
                results = self.rag.query(section_type, query, n_results=5, filters=filters)

                if results:
                    sanitized = []
                    for r in results:
                        if isinstance(r, dict):
                            content = r.get('content', str(r))
                        elif hasattr(r, 'content'):
                            content = r.content
                        else:
                            content = str(r)

                        # POST-FILTER: Skip chunks with wrong indication
                        if self._has_wrong_indication(content, indication):
                            print(f"[RAG] Filtered out chunk with wrong indication")
                            continue

                        # POST-FILTER: Skip chunks with wrong drug pattern
                        if self._has_wrong_drug_pattern(content, is_monotherapy):
                            print(f"[RAG] Filtered out chunk with wrong drug pattern")
                            continue

                        # SANITIZE: Strip all contaminating content
                        if self.sanitizer:
                            content = self.sanitizer.sanitize(content)

                        sanitized.append(content)

                        # Limit to 2 clean examples per section
                        if len(sanitized) >= 2:
                            break

                    examples[section_type] = sanitized
                    print(f"[RAG] {section_type}: {len(sanitized)} clean examples")

            except Exception as e:
                print(f"[RAG] Error querying {section_type}: {e}")

        return examples

    def _build_rag_filters(self, facts: Dict[str, Any]) -> Dict[str, Any]:
        """Build metadata filters for RAG query."""
        filters = {}

        # Filter by therapeutic area if available
        ta = facts.get('therapeutic_area')
        if ta:
            filters['therapeutic_area'] = ta

        # Filter by indication if available
        indication = facts.get('indication')
        if indication:
            filters['indication'] = indication

        # Filter by phase if available
        phase = facts.get('phase')
        if phase:
            filters['phase'] = phase

        return filters if filters else None

    def _has_wrong_indication(self, content: str, current_indication: str) -> bool:
        """Check if content mentions wrong indication."""
        if not current_indication:
            return False

        patterns = self.WRONG_INDICATION_PATTERNS.get(current_indication, [])
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def _has_wrong_drug_pattern(self, content: str, is_monotherapy: bool) -> bool:
        """Check if content has wrong drug pattern (mono vs combo)."""
        if is_monotherapy:
            patterns = self.WRONG_DRUG_PATTERNS.get('nivolumab_mono', [])
        else:
            patterns = self.WRONG_DRUG_PATTERNS.get('nivolumab_combo', [])

        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def _generate_all_sections(
        self,
        facts: Dict[str, Any],
        constraints: MethodConstraints,
        sanitized_examples: Dict[str, List[str]]
    ) -> Dict[str, str]:
        """Step 4: Generate all SAP sections with constrained prompts."""
        sections = {}

        for section_key, section_title in self.SECTIONS:
            # Get relevant examples
            examples = sanitized_examples.get(section_key, [])
            if not examples and section_key == 'statistical_methods':
                examples = sanitized_examples.get('methods', [])

            # Generate section
            section_text = self._generate_section(
                section_key, section_title, facts, constraints, examples
            )
            sections[section_key] = section_text

        return sections

    def _generate_section(
        self,
        section_key: str,
        section_title: str,
        facts: Dict[str, Any],
        constraints: MethodConstraints,
        examples: List[str]
    ) -> str:
        """Generate a single section with constrained prompt."""

        # Build the constrained prompt
        prompt = self._build_constrained_prompt(
            section_key, section_title, facts, constraints, examples
        )

        # Generate with LLM
        if self.llm:
            try:
                response = self.llm.chat(prompt, max_tokens=2000)
                if hasattr(response, 'success') and response.success and hasattr(response, 'content'):
                    return response.content
                elif isinstance(response, str) and response:
                    return response
            except Exception as e:
                print(f"[Generation] LLM error for {section_key}: {e}")

        # Fallback to template
        return self._generate_fallback(section_key, section_title, facts, constraints)

    def _build_constrained_prompt(
        self,
        section_key: str,
        section_title: str,
        facts: Dict[str, Any],
        constraints: MethodConstraints,
        examples: List[str]
    ) -> str:
        """
        Build prompt with explicit source attribution and priority.
        This is the key to preventing RAG contamination.
        """

        # Format numerical facts (GROUND TRUTH)
        facts_section = self._format_numerical_facts(facts, section_key)

        # Format method constraints
        constraints_section = self._format_constraints(constraints, section_key)

        # Format sanitized examples
        examples_section = "\n\n---\n\n".join(examples[:2]) if examples else "No examples available."

        return f"""You are an expert biostatistician writing a Statistical Analysis Plan section.

## CRITICAL INSTRUCTIONS:
1. Use ONLY the numerical values from "PROTOCOL FACTS" below - these are GROUND TRUTH
2. Use ONLY the methods from "METHOD CONSTRAINTS" below
3. Use the "EXAMPLE" for prose style ONLY - it has placeholders, not actual numbers
4. If a value is not in PROTOCOL FACTS, write "[To be specified]"
5. NEVER invent or assume numerical values

## PROTOCOL FACTS (Source: Protocol Extraction - USE THESE EXACTLY):
{facts_section}

## METHOD CONSTRAINTS (Source: Knowledge Graph - USE THESE METHODS):
{constraints_section}

## EXAMPLE PROSE STYLE (for structure only - numbers are placeholders):
{examples_section}

## SECTION TO WRITE: {section_title}

Write the {section_title} section now.
- Use EXACT numbers from PROTOCOL FACTS
- Use EXACT methods from METHOD CONSTRAINTS
- Match prose style of EXAMPLE but with YOUR numbers and methods
- Start with "## {section_title}" as header
"""

    def _format_numerical_facts(self, facts: Dict[str, Any], section_key: str) -> str:
        """Format numerical facts for the prompt."""
        lines = []

        # Always include these CRITICAL facts
        if facts.get('nct_id'):
            lines.append(f"- NCT ID: {facts['nct_id']}")
        if facts.get('sample_size'):
            lines.append(f"- Sample Size: {facts['sample_size']} patients")

        # =====================================================================
        # CRITICAL: Study Type Information (determines statistical approach)
        # =====================================================================
        phase = facts.get('phase', 3)
        is_single_arm = facts.get('is_single_arm', False)
        is_pilot = facts.get('is_pilot_study', False)
        treatment_setting = facts.get('treatment_setting', 'metastatic')

        lines.append(f"- Phase: {phase}")

        if is_single_arm:
            lines.append("- Design: SINGLE-ARM (no comparator group)")
            lines.append("- Statistical Approach: DESCRIPTIVE ONLY (no comparative hypothesis testing)")

        if is_pilot:
            lines.append("- Study Type: PILOT/FEASIBILITY/EXPLORATORY")
            lines.append("- Sample Size Justification: No formal power calculation (exploratory)")

        if treatment_setting == 'neoadjuvant':
            lines.append("- Setting: NEOADJUVANT")
            lines.append("- Time Origin: FROM SURGERY (not enrollment/randomization)")
            if facts.get('pathologic_response_criteria'):
                lines.append(f"- Pathologic Response Criteria: {facts['pathologic_response_criteria']}")

        if facts.get('response_criteria'):
            lines.append(f"- Response Criteria: {facts['response_criteria']}")

        # Hypothesis testing status
        if not facts.get('hypothesis_testing_planned', True):
            lines.append("- Hypothesis Testing: NO FORMAL TESTING (descriptive analysis only)")

        # =====================================================================
        # Randomization ratio (only for comparative studies)
        # =====================================================================
        if not is_single_arm:
            if facts.get('randomization_ratio'):
                ratio = facts['randomization_ratio']
                lines.append(f"- Randomization Ratio: {ratio}")
                # Also calculate per-arm N if ratio is clear
                if ':' in str(ratio):
                    parts = [int(p) for p in str(ratio).split(':')]
                    total_parts = sum(parts)
                    sample_size = facts.get('sample_size', 0)
                    if sample_size and total_parts > 0:
                        per_arm = [int(sample_size * p / total_parts) for p in parts]
                        lines.append(f"- Per-Arm N: {' : '.join(map(str, per_arm))}")
            else:
                # FALLBACK: Try to extract ratio from num_arms
                num_arms = facts.get('num_arms', 2)
                if num_arms == 2:
                    lines.append(f"- Randomization Ratio: [Check protocol - likely 1:1 or 2:1]")

        if facts.get('drug_name'):
            lines.append(f"- Study Drug: {facts['drug_name']}")
        if facts.get('comparator'):
            lines.append(f"- Comparator: {facts['comparator']}")

        # Stratification factors - filter out None values
        if facts.get('stratification_factors'):
            strat = facts['stratification_factors']
            if isinstance(strat, list):
                # Filter out None values and convert to strings
                strat_clean = [str(s) for s in strat if s is not None]
                if strat_clean:
                    lines.append(f"- Stratification Factors: {', '.join(strat_clean)}")
            else:
                lines.append(f"- Stratification Factors: {strat}")

        # Section-specific facts
        if section_key in ['statistical_methods', 'interim_analysis']:
            final_events = facts.get('final_events') or facts.get('final_analysis_events')
            interim_events = facts.get('interim_events') or facts.get('interim_analysis_events')

            if final_events:
                lines.append(f"- Events at Final Analysis: {final_events} deaths")
            if interim_events:
                # Handle list or single value
                if isinstance(interim_events, list):
                    interim_events = interim_events[0] if interim_events else None
                if interim_events:
                    lines.append(f"- Events at Interim Analysis: {interim_events} deaths")

                    # CRITICAL: Calculate information fraction automatically
                    if final_events and interim_events:
                        info_fraction = round(100 * int(interim_events) / int(final_events), 1)
                        lines.append(f"- Information Fraction: {info_fraction}% ({interim_events}/{final_events})")

            if facts.get('num_interim_analyses') or facts.get('num_interim'):
                num = facts.get('num_interim_analyses') or facts.get('num_interim')
                lines.append(f"- Number of Interim Analyses: {num}")
            if facts.get('alpha_at_interim') or facts.get('interim_alpha_spent'):
                alpha = facts.get('alpha_at_interim')
                if not alpha and facts.get('interim_alpha_spent'):
                    alpha = facts['interim_alpha_spent'][0] if isinstance(facts['interim_alpha_spent'], list) else facts['interim_alpha_spent']
                if alpha:
                    lines.append(f"- Alpha at Interim: {alpha}")
            if facts.get('alpha_at_final') or facts.get('alpha_level'):
                alpha = facts.get('alpha_at_final') or facts.get('alpha_level')
                lines.append(f"- Alpha at Final: {alpha}")
            if facts.get('error_spending_function'):
                lines.append(f"- Error Spending Function: {facts['error_spending_function']}")
            if facts.get('stopping_boundaries'):
                lines.append(f"- Stopping Boundaries: {facts['stopping_boundaries']}")

        if section_key == 'sample_size':
            if facts.get('power'):
                power = facts['power']
                if power < 1:
                    power = power * 100
                lines.append(f"- Statistical Power: {int(power)}%")
            if facts.get('expected_hazard_ratio') or facts.get('hazard_ratio'):
                hr = facts.get('expected_hazard_ratio') or facts.get('hazard_ratio')
                lines.append(f"- Expected Hazard Ratio: {hr}")

        if section_key == 'objectives':
            if facts.get('primary_endpoint'):
                lines.append(f"- Primary Endpoint: {facts['primary_endpoint']}")
            if facts.get('secondary_endpoints'):
                endpoints = facts['secondary_endpoints']
                if isinstance(endpoints, list):
                    endpoints = ', '.join(str(e) for e in endpoints[:5])
                lines.append(f"- Secondary Endpoints: {endpoints}")

            # CRITICAL: Consistency/bridging study objectives
            if facts.get('has_consistency_objective') or facts.get('is_bridging_study'):
                lines.append("- Study Type: BRIDGING STUDY (consistency with global studies required)")
                if facts.get('consistency_reference_studies'):
                    refs = facts['consistency_reference_studies']
                    if isinstance(refs, list):
                        refs = ', '.join(refs)
                    lines.append(f"- Reference Studies: {refs}")
                if facts.get('consistency_margin'):
                    lines.append(f"- Consistency Margin: {facts['consistency_margin']}")
                if facts.get('consistency_test_description'):
                    lines.append(f"- Consistency Test: {facts['consistency_test_description']}")

            # Hierarchical testing order
            if facts.get('hierarchical_testing_order'):
                order = facts['hierarchical_testing_order']
                if isinstance(order, list):
                    order = ' → '.join(order)
                lines.append(f"- Hierarchical Testing Order: {order}")
            elif facts.get('has_hierarchical_testing'):
                lines.append("- Hierarchical Testing: Yes (order to be specified)")

        # Multiplicity section
        if section_key == 'multiplicity':
            if facts.get('hierarchical_testing_order'):
                order = facts['hierarchical_testing_order']
                if isinstance(order, list):
                    order = ' → '.join(order)
                lines.append(f"- Testing Order: {order}")
            if facts.get('hierarchical_testing_description'):
                lines.append(f"- Procedure: {facts['hierarchical_testing_description']}")

            # Two-step testing for bridging studies
            if facts.get('is_bridging_study') or facts.get('has_consistency_objective'):
                lines.append("- TWO-STEP TESTING REQUIRED:")
                lines.append("  Step 1: Test consistency with global studies (HR upper bound < threshold)")
                lines.append("  Step 2: If Step 1 passes, test superiority")

        # Subgroup analyses
        if section_key == 'subgroup_analysis':
            if facts.get('subgroup_analyses'):
                subgroups = facts['subgroup_analyses']
                if isinstance(subgroups, list):
                    lines.append(f"- Pre-specified Subgroups ({len(subgroups)} total):")
                    for sg in subgroups:
                        lines.append(f"  • {sg}")
                else:
                    lines.append(f"- Subgroups: {subgroups}")

        # Regulatory interim (TTF for China)
        if section_key in ['interim_analysis', 'regulatory']:
            if facts.get('has_regulatory_interim'):
                lines.append("- REGULATORY INTERIM ANALYSIS:")
                if facts.get('regulatory_interim_endpoint'):
                    lines.append(f"  Endpoint: {facts['regulatory_interim_endpoint']}")
                if facts.get('regulatory_interim_region'):
                    lines.append(f"  Region: {facts['regulatory_interim_region']}")
                if facts.get('regulatory_interim_timing'):
                    lines.append(f"  Timing: {facts['regulatory_interim_timing']}")
                if facts.get('regulatory_interim_purpose'):
                    lines.append(f"  Purpose: {facts['regulatory_interim_purpose']}")

        return '\n'.join(lines) if lines else "No specific numerical facts for this section."

    def _format_constraints(self, constraints: MethodConstraints, section_key: str) -> str:
        """Format method constraints for the prompt."""
        lines = []

        # =====================================================================
        # Check if this is a descriptive-only study (Phase II single-arm/pilot)
        # =====================================================================
        primary_test_str = str(constraints.primary_test or '')
        is_descriptive = (
            constraints.descriptive_methods or
            "Descriptive" in primary_test_str or
            "descriptive" in primary_test_str.lower()
        )

        if section_key == 'statistical_methods':
            if constraints.primary_test:
                lines.append(f"- PRIMARY APPROACH: {constraints.primary_test}")
            if constraints.forbidden_primary:
                lines.append(f"- DO NOT USE: {constraints.forbidden_primary}")

            # Descriptive study methods
            if is_descriptive:
                if constraints.descriptive_methods:
                    lines.append("- TIME-TO-EVENT ANALYSIS:")
                    for m in constraints.descriptive_methods:
                        lines.append(f"  • {m}")
                if constraints.binary_methods:
                    lines.append("- BINARY ENDPOINT ANALYSIS:")
                    for m in constraints.binary_methods:
                        lines.append(f"  • {m}")
                # Neoadjuvant specific
                if constraints.time_origin:
                    lines.append(f"- TIME ORIGIN: {constraints.time_origin}")
                if constraints.neoadjuvant_methods:
                    lines.append("- NEOADJUVANT-SPECIFIC METHODS:")
                    for m in constraints.neoadjuvant_methods:
                        lines.append(f"  • {m}")
                if constraints.pathologic_criteria:
                    lines.append(f"- PATHOLOGIC RESPONSE: Use {constraints.pathologic_criteria}")
            else:
                # Comparative study methods
                if constraints.nph_methods:
                    lines.append(f"- NPH Methods: {', '.join(constraints.nph_methods)}")
                if constraints.sensitivity_methods:
                    lines.append(f"- Sensitivity Methods: {', '.join(constraints.sensitivity_methods)}")
                lines.append("- Include: estimands (ICH E9 R1), censoring rules, stratification factors")

        elif section_key == 'sample_size':
            if constraints.sample_size_approach:
                lines.append(f"- SAMPLE SIZE APPROACH: {constraints.sample_size_approach}")
                sample_size_str = str(constraints.sample_size_approach or '').lower()
                if "exploratory" in sample_size_str or "no formal" in sample_size_str:
                    lines.append("- DO NOT describe power calculations or formal sample size estimation")
                    lines.append("- Describe rationale as exploratory/feasibility based")

        elif section_key == 'interim_analysis':
            if constraints.interim_method:
                lines.append(f"- Interim Method: {constraints.interim_method}")
                if constraints.alpha_spending:
                    lines.append(f"- Alpha Spending: {constraints.alpha_spending}")
                lines.append("- Include: information fractions, stopping boundaries, alpha allocation")
            else:
                lines.append("- NO INTERIM ANALYSIS SPECIFIED IN PROTOCOL")
                lines.append("- DO NOT describe interim analysis unless explicitly in protocol")

        elif section_key == 'sensitivity_analysis':
            if is_descriptive:
                lines.append("- For single-arm studies, no formal sensitivity analyses are typically performed")
                lines.append("- May describe sensitivity to missing data assumptions if applicable")
            else:
                if constraints.sensitivity_methods:
                    lines.append(f"- Required Methods: {', '.join(constraints.sensitivity_methods)}")
                conditions = [str(c) for c in (constraints.conditions_detected or [])]
                if 'crossover' in conditions or 'treatment_switching' in conditions:
                    lines.append("- Treatment Switching: Include RPSFT and IPCW if crossover present")

        return '\n'.join(lines) if lines else "No specific method constraints for this section."

    def _generate_fallback(
        self,
        section_key: str,
        section_title: str,
        facts: Dict[str, Any],
        constraints: MethodConstraints
    ) -> str:
        """Generate section using templates (fallback when LLM unavailable)."""

        if section_key == 'statistical_methods':
            return self._fallback_statistical_methods(facts, constraints)
        elif section_key == 'interim_analysis':
            return self._fallback_interim_analysis(facts, constraints)
        else:
            return f"## {section_title}\n\n[Section to be completed based on protocol specifications.]"

    def _fallback_statistical_methods(self, facts: Dict[str, Any], constraints: MethodConstraints) -> str:
        """Template fallback for statistical methods - uses extracted facts."""
        primary_test = constraints.primary_test or "stratified log-rank test"
        endpoint = facts.get('primary_endpoint', 'the primary endpoint')
        final_events = facts.get('final_events') or facts.get('final_analysis_events') or '[N]'

        text = f"""## Statistical Methods

### Primary Analysis

The primary efficacy endpoint ({endpoint}) will be analyzed using the **{primary_test}**.

The analysis will be based on {final_events} death events.
"""
        if constraints.nph_methods:
            text += f"""
### Non-Proportional Hazards Methods

Given the expected delayed treatment effect, the following methods will be used:
"""
            for method in constraints.nph_methods:
                text += f"- {method}\n"

        return text

    def _fallback_interim_analysis(self, facts: Dict[str, Any], constraints: MethodConstraints) -> str:
        """Template fallback for interim analysis - uses extracted facts."""
        method = constraints.interim_method or "Lan-DeMets"
        spending = constraints.alpha_spending or "O'Brien-Fleming"
        num_interim = facts.get('num_interim_analyses') or facts.get('num_interim') or 1
        interim_events = facts.get('interim_events') or facts.get('interim_analysis_events') or '[N]'
        final_events = facts.get('final_events') or facts.get('final_analysis_events') or '[N]'
        alpha_interim = facts.get('alpha_at_interim') or '[α]'
        alpha_final = facts.get('alpha_at_final') or facts.get('alpha_level') or '[α]'

        return f"""## Interim Analysis

### Alpha Spending Approach

{num_interim} interim analysis will be conducted using the {method} alpha spending function with {spending} spending boundaries.

### Analysis Schedule

- Interim Analysis: At {interim_events} events
- Final Analysis: At {final_events} events

### Stopping Boundaries

- At interim: Reject H₀ if p < {alpha_interim}
- At final: Reject H₀ if p < {alpha_final}
"""

    def _verify_and_correct(
        self,
        sap_text: str,
        facts: Dict[str, Any],
        constraints: MethodConstraints
    ) -> Tuple[Optional[VerificationResult], str, int]:
        """
        Step 5: SELF-RAG verification and correction loop.

        Returns:
            Tuple of (verification_result, corrected_text, regeneration_count)
        """
        if not self.verifier:
            return None, sap_text, 0

        regeneration_count = 0
        current_text = sap_text

        for attempt in range(self.max_regenerations + 1):
            # Verify current text
            constraints_dict = {
                'primary_test': constraints.primary_test,
                'forbidden_primary': constraints.forbidden_primary,
            }
            verification = self.verifier.verify(current_text, facts, constraints_dict)

            if verification.passed:
                return verification, current_text, regeneration_count

            if attempt < self.max_regenerations:
                print(f"[Verification] Attempt {attempt + 1} failed, regenerating...")
                print(f"[Verification] Errors: {[e.context for e in verification.errors]}")

                # Generate correction prompt
                correction_prompt = self.verifier.generate_correction_prompt(current_text, facts)

                # Regenerate
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
        section_order = [
            'introduction', 'objectives', 'study_design', 'sample_size',
            'analysis_populations', 'statistical_methods', 'interim_analysis',
            'sensitivity_analysis', 'missing_data', 'multiplicity', 'safety'
        ]

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
    print("TESTING PRODUCTION SAP PIPELINE")
    print("=" * 60)

    test_protocol = """
    NCT02041533 - CheckMate 078
    Phase 3, Randomized Study of Nivolumab vs Docetaxel in NSCLC

    Primary Endpoint: Overall Survival (OS)
    Sample Size: 504 patients (2:1 randomization)

    Immunotherapy checkpoint inhibitor - delayed treatment effect expected.

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

    if result.verification:
        print(f"Verification passed: {result.verification.passed}")
        print(f"Score: {result.verification.score:.2f}")
        if result.verification.errors:
            print("Errors:")
            for e in result.verification.errors:
                print(f"  - {e.field}: {e.context}")

    print(f"\nSAP length: {len(result.sap_text)} chars")
    print("\nFirst 2000 chars:")
    print("-" * 60)
    print(result.sap_text[:2000])
