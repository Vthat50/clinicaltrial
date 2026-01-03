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
    interim_method: str = ""
    alpha_spending: str = ""
    nph_methods: List[str] = field(default_factory=list)
    conditions_detected: List[str] = field(default_factory=list)


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
            print(f"[Step 1] Extracted: {facts.get('nct_id')}, {facts.get('sample_size')} patients, {facts.get('final_events')} events")

            # STEP 2: Get method constraints (with Drug Classification)
            print("\n[Step 2] Getting method constraints from Knowledge Graph...")
            conditions, drug_classification = self._detect_conditions(facts, protocol_text)
            constraints = self._get_constraints(facts, conditions)
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
        """Step 2b: Get method constraints from knowledge graph."""
        constraints = MethodConstraints(conditions_detected=conditions)

        if self.knowledge_graph:
            methods = self.knowledge_graph.get_primary_analysis_methods(facts)

            if methods:
                primary = methods.get('primary_test', {})
                if primary:
                    constraints.primary_test = primary.get('description', primary.get('method', ''))

                # NPH methods
                nph = methods.get('nph_methods', [])
                constraints.nph_methods = [m.get('method', m) if isinstance(m, dict) else m for m in nph]

                # Interim
                interim = methods.get('interim_analysis_method', {})
                if interim:
                    constraints.interim_method = interim.get('method', '')
                    constraints.alpha_spending = "O'Brien-Fleming"

        # Apply immunotherapy-specific constraints
        if 'immunotherapy' in conditions and 'time_to_event' in conditions:
            constraints.primary_test = "Fleming-Harrington weighted log-rank test G(ρ=0, γ=1)"
            constraints.forbidden_primary = "stratified log-rank"
            constraints.nph_methods = ['Fleming-Harrington', 'RMST', 'landmark_analysis']
            constraints.sensitivity_methods = ['stratified log-rank (unweighted)']

        if 'interim_analysis' in conditions and not constraints.interim_method:
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
        drug_name = facts.get('drug_name', '').lower()
        is_monotherapy = 'mono' in drug_name or facts.get('num_arms', 0) == 2

        # Get current indication for post-filter
        indication = facts.get('indication', '').upper()
        if not indication:
            # Try to infer from therapeutic area
            ta = facts.get('therapeutic_area', '').upper()
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

        # CRITICAL: Randomization ratio - this was MISSING!
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

        # Stratification factors - also was missing
        if facts.get('stratification_factors'):
            strat = facts['stratification_factors']
            if isinstance(strat, list):
                lines.append(f"- Stratification Factors: {', '.join(strat)}")
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

        if section_key == 'statistical_methods':
            if constraints.primary_test:
                lines.append(f"- PRIMARY TEST: {constraints.primary_test}")
            if constraints.forbidden_primary:
                lines.append(f"- DO NOT use as primary: {constraints.forbidden_primary}")
            if constraints.nph_methods:
                lines.append(f"- NPH Methods: {', '.join(constraints.nph_methods)}")
            if constraints.sensitivity_methods:
                lines.append(f"- Sensitivity Methods: {', '.join(constraints.sensitivity_methods)}")
            lines.append("- Include: estimands (ICH E9 R1), censoring rules, stratification factors")

        elif section_key == 'interim_analysis':
            if constraints.interim_method:
                lines.append(f"- Interim Method: {constraints.interim_method}")
            if constraints.alpha_spending:
                lines.append(f"- Alpha Spending: {constraints.alpha_spending}")
            lines.append("- Include: information fractions, stopping boundaries, alpha allocation")

        elif section_key == 'sensitivity_analysis':
            if constraints.sensitivity_methods:
                lines.append(f"- Required Methods: {', '.join(constraints.sensitivity_methods)}")
            if 'crossover' in constraints.conditions_detected or 'treatment_switching' in constraints.conditions_detected:
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
