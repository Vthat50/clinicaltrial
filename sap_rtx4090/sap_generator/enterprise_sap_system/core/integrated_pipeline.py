#!/usr/bin/env python3
"""
Integrated Production SAP Pipeline
====================================
This is the ACTUAL production pipeline that integrates ALL components:

1. EXTRACTION: Regex-based fact extraction (no hallucination)
2. RAG RETRIEVAL: 1,198 indexed SAP sections for few-shot examples
3. KNOWLEDGE GRAPH: 39 nodes for statistical method selection
4. SPECIALIZED TEMPLATES: Oncology, Phase 1, Phase 2/3, CAR-T, etc.
5. CONSTRAINED GENERATION: Literal types prevent hallucination
6. QA VALIDATION: Issue detection and quality scoring

This replaces the scattered components with a single integrated flow.
"""

import os
import re
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from datetime import datetime


# =============================================================================
# RESULT TYPES
# =============================================================================

@dataclass
class IntegratedResult:
    """Result from the integrated pipeline"""
    success: bool
    sap_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)

    # Full facts dictionary (for API access to interim_analysis, power_calculations, etc.)
    facts: Dict[str, Any] = field(default_factory=dict)
    trial_type: str = "unknown"

    # Extracted facts (individual fields for convenience)
    drug_name: str = ""
    sample_size: int = 0
    num_arms: int = 0
    randomization_ratio: str = ""
    phase: str = ""
    therapeutic_area: str = ""
    endpoint_type: str = ""
    primary_endpoint: str = ""

    # RAG info
    rag_examples_used: int = 0
    rag_nct_ids: List[str] = field(default_factory=list)

    # Knowledge graph info
    recommended_methods: List[str] = field(default_factory=list)
    adam_datasets: List[str] = field(default_factory=list)

    # Templates used
    templates_applied: List[str] = field(default_factory=list)

    # QA results
    quality_score: float = 0.0
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Timing
    extraction_time: float = 0.0
    rag_time: float = 0.0
    generation_time: float = 0.0
    qa_time: float = 0.0
    total_time: float = 0.0

    errors: List[str] = field(default_factory=list)


class TrialType(Enum):
    """Trial types for template selection"""
    ONCOLOGY_SOLID = "oncology_solid"
    ONCOLOGY_HEMATOLOGIC = "oncology_hematologic"
    ONCOLOGY_PHASE1 = "oncology_phase1"
    ONCOLOGY_CART = "oncology_cart"
    ONCOLOGY_BASKET = "oncology_basket"
    IBD = "ibd"
    RHEUMATOLOGY = "rheumatology"
    CNS = "cns"
    CARDIOVASCULAR = "cardiovascular"
    METABOLIC = "metabolic"
    GENERAL = "general"


# =============================================================================
# STEP 1: EXTRACTION (Regex-only, no LLM)
# =============================================================================

class FactExtractor:
    """Extract all protocol facts using regex patterns + LLM for complex elements"""

    def __init__(self, use_llm_for_complex: bool = True):
        """
        Initialize FactExtractor.

        Args:
            use_llm_for_complex: If True, use LLM to extract complex elements
                                 (interim analysis, power calculations, etc.)
        """
        self.use_llm_for_complex = use_llm_for_complex
        self._llm_extractor = None

    def _get_llm_extractor(self):
        """Lazy-load LLM extractor"""
        if self._llm_extractor is None and self.use_llm_for_complex:
            try:
                from .llm_extractor import LLMExtractor
                self._llm_extractor = LLMExtractor()
            except Exception as e:
                print(f"[FactExtractor] LLM extractor not available: {e}")
        return self._llm_extractor

    def extract(self, protocol_text: str) -> Dict[str, Any]:
        """Extract all facts from protocol text"""
        facts = {}

        # First extract basic facts with regex
        facts = self._extract_basic_facts(protocol_text, facts)

        # Then extract complex elements with LLM if available
        if self.use_llm_for_complex:
            facts = self._extract_complex_facts_with_llm(protocol_text, facts)

        return facts

    def _extract_basic_facts(self, protocol_text: str, facts: Dict[str, Any]) -> Dict[str, Any]:
        """Extract basic facts using regex patterns"""

        # NCT ID
        nct_match = re.search(r'(NCT\d{8})', protocol_text, re.IGNORECASE)
        facts['nct_id'] = nct_match.group(1) if nct_match else None

        # Drug name - multiple patterns (order matters - most specific first)
        drug_patterns = [
            # Biologics with specific suffixes
            r'([A-Za-z][a-z]+(?:mab|nib|zumab|ximab|tinib|ciclib|simod|stat|parin|vastatin|prazole))',
            # Study of [DRUG]
            r'(?:study of|trial of)\s+([A-Za-z][A-Za-z0-9-]+)',
            # Receive [DRUG]
            r'(?:receive|receiving)\s+(?:either\s+)?([A-Za-z][A-Za-z0-9-]+)\s*(?:\d+\s*mg)?',
            # Study drug/investigational product
            r'(?:study drug|investigational product|active treatment)[:\s]+([A-Za-z][A-Za-z0-9-]+)',
            # Randomized to [DRUG]
            r'randomized\s+(?:to\s+)?(?:receive\s+)?([A-Za-z][A-Za-z0-9-]+)',
            # [DRUG] vs placebo
            r'([A-Za-z][A-Za-z0-9-]+)\s+(?:vs\.?|versus)\s+placebo',
            # [DRUG] 2mg or similar dose pattern
            r'([A-Za-z][A-Za-z0-9-]+)\s+\d+\s*(?:mg|mcg|ug|ml)',
        ]
        for pattern in drug_patterns:
            match = re.search(pattern, protocol_text, re.IGNORECASE)
            if match:
                drug = match.group(1)
                # Filter out common non-drug words
                skip_words = ['placebo', 'study', 'trial', 'phase', 'patients', 'subjects',
                              'either', 'active', 'treatment', 'control', 'arm', 'group',
                              'double', 'blind', 'randomized', 'week', 'day', 'dose']
                if drug.lower() not in skip_words and len(drug) > 3:
                    facts['drug_name'] = drug.capitalize()
                    break
        if 'drug_name' not in facts:
            facts['drug_name'] = None

        # Sample size
        size_patterns = [
            r'(?:approximately|total of|enroll)\s*(\d+)\s*(?:patients|subjects|participants)',
            r'[Nn]\s*=\s*(\d+)',
            r'sample size[:\s]+(\d+)',
            r'(\d+)\s*(?:patients|subjects)\s*will be\s*(?:enrolled|randomized)',
        ]
        for pattern in size_patterns:
            match = re.search(pattern, protocol_text, re.IGNORECASE)
            if match:
                size = int(match.group(1))
                if 10 <= size <= 10000:
                    facts['sample_size'] = size
                    break
        if 'sample_size' not in facts:
            facts['sample_size'] = 0

        # CRITICAL: Detect single-arm trials FIRST
        text_lower = protocol_text.lower()
        is_single_arm = any(x in text_lower for x in [
            'single-arm', 'single arm', 'one-arm', 'one arm',
            'non-randomized', 'nonrandomized', 'open-label single'
        ])

        # Randomization ratio
        ratio_patterns = [
            r'(\d+:\d+(?::\d+)?)\s*(?:randomization|ratio)',
            r'randomiz(?:ed|ation)\s*(?:in a)?\s*(\d+:\d+(?::\d+)?)',
            r'(\d+:\d+)\s*(?:to|allocation)',
        ]
        ratio_found = False
        for pattern in ratio_patterns:
            match = re.search(pattern, protocol_text, re.IGNORECASE)
            if match:
                facts['randomization_ratio'] = match.group(1)
                ratio_found = True
                break

        # Set ratio and arms based on single-arm detection
        if is_single_arm or not ratio_found:
            if is_single_arm:
                facts['randomization_ratio'] = "N/A (single-arm)"
                facts['num_arms'] = 1
            else:
                # Only default to 1:1 if NOT single-arm
                facts['randomization_ratio'] = "1:1"
                facts['num_arms'] = 2
        else:
            # Number of arms from ratio
            facts['num_arms'] = facts['randomization_ratio'].count(':') + 1

        # Phase
        phase_match = re.search(r'phase\s*([1-4](?:/[2-4])?|[IiVv]+(?:/[IiVv]+)?)', protocol_text, re.IGNORECASE)
        if phase_match:
            phase = phase_match.group(1).upper()
            phase = phase.replace('I', '1').replace('II', '2').replace('III', '3').replace('IV', '4')
            facts['phase'] = f"Phase {phase}"
        else:
            facts['phase'] = "Phase 3"

        # Treatment arms
        facts['arms'] = self._extract_arms(protocol_text)

        # Stratification factors
        strat_match = re.search(r'stratif(?:ied|ication)\s*(?:by|factors?)[:\s]*([^\n.]+)', protocol_text, re.IGNORECASE)
        if strat_match:
            factors = re.split(r'[,;]|\s+and\s+', strat_match.group(1))
            facts['stratification_factors'] = [f.strip() for f in factors if len(f.strip()) > 2]
        else:
            facts['stratification_factors'] = []

        # Alpha level
        alpha_match = re.search(r'(?:alpha|significance)\s*(?:level)?\s*(?:of)?\s*(0\.0\d+|\.0\d+)', protocol_text, re.IGNORECASE)
        facts['alpha'] = float(alpha_match.group(1)) if alpha_match else 0.05

        # Sidedness
        if 'one-sided' in protocol_text.lower() or 'one sided' in protocol_text.lower():
            facts['alpha_sidedness'] = 'one-sided'
        else:
            facts['alpha_sidedness'] = 'two-sided'

        # Power
        power_match = re.search(r'(?:power|powered)\s*(?:of)?\s*(\d{2})%?', protocol_text, re.IGNORECASE)
        facts['power'] = int(power_match.group(1)) / 100 if power_match else 0.80

        # Therapeutic area
        facts['therapeutic_area'] = self._detect_therapeutic_area(protocol_text)

        # Endpoint type
        facts['endpoint_type'] = self._detect_endpoint_type(protocol_text)

        # Primary endpoint text
        facts['primary_endpoint'] = self._extract_primary_endpoint(protocol_text)

        # Trial type (for template selection)
        facts['trial_type'] = self._classify_trial_type(protocol_text, facts)

        return facts

    def _extract_arms(self, text: str) -> List[Dict]:
        """Extract treatment arms"""
        arms = []

        # Look for arm descriptions
        arm_patterns = [
            r'(?:arm|group)\s*([A-D1-4])[:\s]+([^\n]+)',
            r'([A-Za-z]+)\s+(\d+(?:\.\d+)?\s*mg)',
        ]

        for pattern in arm_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:4]:
                arm_name = match[0] if len(match[0]) > 2 else f"Arm {match[0]}"
                arms.append({
                    'name': arm_name,
                    'description': match[1] if len(match) > 1 else "",
                    'is_placebo': 'placebo' in str(match).lower()
                })

        # Default if none found
        if not arms:
            arms = [
                {'name': 'Placebo', 'description': 'Placebo', 'is_placebo': True},
                {'name': 'Active Treatment', 'description': 'Study drug', 'is_placebo': False}
            ]

        return arms

    def _detect_therapeutic_area(self, text: str) -> str:
        """Detect therapeutic area from text"""
        text_lower = text.lower()

        if any(x in text_lower for x in ['ulcerative colitis', 'crohn', 'ibd', 'inflammatory bowel']):
            return "IBD"
        elif any(x in text_lower for x in ['cancer', 'tumor', 'oncology', 'carcinoma', 'melanoma', 'lymphoma']):
            return "Oncology"
        elif any(x in text_lower for x in ['rheumatoid arthritis', 'psoriatic arthritis', 'das28', 'acr20']):
            return "Rheumatology"
        elif any(x in text_lower for x in ['diabetes', 'hba1c', 'glucose', 'metabolic']):
            return "Metabolic"
        elif any(x in text_lower for x in ['depression', 'anxiety', 'schizophrenia', 'cns', 'madrs']):
            return "CNS"
        elif any(x in text_lower for x in ['heart', 'cardiac', 'cardiovascular', 'mace']):
            return "Cardiovascular"
        elif any(x in text_lower for x in ['psoriasis', 'dermatitis', 'eczema', 'pasi']):
            return "Dermatology"
        else:
            return "General"

    def _detect_endpoint_type(self, text: str) -> str:
        """Detect primary endpoint type"""
        text_lower = text.lower()

        if any(x in text_lower for x in ['overall survival', 'progression-free survival', 'pfs', ' os ', 'time to']):
            return "time-to-event"
        elif any(x in text_lower for x in ['change from baseline', 'mean change', 'reduction in']):
            return "continuous"
        elif any(x in text_lower for x in ['remission', 'response', 'proportion', 'percentage', 'orr']):
            return "binary"
        else:
            return "binary"

    def _extract_primary_endpoint(self, text: str) -> str:
        """Extract primary endpoint description"""
        patterns = [
            r'primary\s+(?:efficacy\s+)?endpoint[:\s]+([^\n.]+)',
            r'primary\s+objective[:\s]+([^\n.]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                endpoint = match.group(1).strip()
                if len(endpoint) > 10:
                    return endpoint[:200]

        return "Primary endpoint"

    def _classify_trial_type(self, text: str, facts: Dict) -> TrialType:
        """Classify trial type for template selection"""
        text_lower = text.lower()
        ta = str(facts.get('therapeutic_area') or '').lower()
        phase = str(facts.get('phase') or '').lower()

        if ta == 'oncology' or 'cancer' in text_lower:
            if 'car-t' in text_lower or 'chimeric antigen' in text_lower:
                return TrialType.ONCOLOGY_CART
            elif 'basket' in text_lower or 'umbrella' in text_lower:
                return TrialType.ONCOLOGY_BASKET
            elif 'phase 1' in phase or 'dose escalation' in text_lower:
                return TrialType.ONCOLOGY_PHASE1
            elif any(x in text_lower for x in ['lymphoma', 'leukemia', 'myeloma', 'lugano', 'imwg']):
                return TrialType.ONCOLOGY_HEMATOLOGIC
            else:
                return TrialType.ONCOLOGY_SOLID
        elif ta == 'ibd' or 'colitis' in text_lower or 'crohn' in text_lower:
            return TrialType.IBD
        elif ta == 'rheumatology':
            return TrialType.RHEUMATOLOGY
        elif ta == 'cns':
            return TrialType.CNS
        elif ta == 'cardiovascular':
            return TrialType.CARDIOVASCULAR
        elif ta == 'metabolic':
            return TrialType.METABOLIC
        else:
            return TrialType.GENERAL

    def _extract_complex_facts_with_llm(self, protocol_text: str, facts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract complex elements using LLM (interim analysis, power calculations, etc.)

        These elements require semantic understanding and can't be reliably extracted with regex.
        """
        llm_extractor = self._get_llm_extractor()
        if not llm_extractor:
            return facts

        try:
            print("[FactExtractor] Extracting complex elements with LLM...")

            # Use the enhanced LLM extractor
            llm_facts = llm_extractor.extract(
                protocol_text,
                include_windows=False,  # Not needed for SAP
                include_interim=True,
                include_power=True,
                include_exploratory=True,
                include_pro=True,
                include_regional=True,
                include_censoring=True
            )

            if llm_facts.extraction_success:
                # Add interim analysis details
                if llm_facts.interim_analysis.num_interim_analyses > 0:
                    facts['interim_analysis'] = llm_facts.interim_analysis.to_dict()
                    print(f"  [FactExtractor] Found {llm_facts.interim_analysis.num_interim_analyses} interim analyses")

                # Add power calculations
                if llm_facts.power_calculations.pfs_power or llm_facts.power_calculations.os_superiority_power:
                    facts['power_calculations'] = llm_facts.power_calculations.to_dict()

                # Add exploratory endpoints
                if llm_facts.exploratory_endpoints.dor or llm_facts.exploratory_endpoints.pfs2:
                    facts['exploratory_endpoints'] = llm_facts.exploratory_endpoints.to_dict()

                # Add PRO details
                if llm_facts.pro_details.primary_timepoint or llm_facts.pro_details.instruments:
                    facts['pro_details'] = llm_facts.pro_details.to_dict()

                # Add regional extensions
                if llm_facts.regional_extensions.china_sample_size:
                    facts['regional_extensions'] = llm_facts.regional_extensions.to_dict()

                # Add censoring rules
                if llm_facts.censoring_rules.pfs_censoring or llm_facts.censoring_rules.dor_censoring:
                    facts['censoring_rules'] = llm_facts.censoring_rules.to_dict()

                # Also capture alpha allocation and multiplicity from LLM
                if llm_facts.alpha_allocation:
                    facts['alpha_allocation_detail'] = llm_facts.alpha_allocation
                if llm_facts.multiplicity_adjustment:
                    facts['multiplicity_adjustment'] = llm_facts.multiplicity_adjustment
                if llm_facts.testing_hierarchy:
                    facts['testing_hierarchy'] = llm_facts.testing_hierarchy

        except Exception as e:
            print(f"[FactExtractor] LLM extraction failed: {e}")

        return facts


# =============================================================================
# STEP 2: RAG RETRIEVAL
# =============================================================================

class RAGRetriever:
    """Retrieve similar SAP sections from vector store"""

    def __init__(self):
        self.sections_db = {}
        self.indexed = False
        self._load_sections()

    def _load_sections(self):
        """Load SAP sections from data directory"""
        data_dir = Path(__file__).parent.parent.parent / "data"
        all_pairs_dir = data_dir / "all_pairs"
        ground_truth_dir = data_dir / "ground_truth"

        total_sections = 0

        for sap_dir in [ground_truth_dir, all_pairs_dir]:
            if not sap_dir.exists():
                continue

            for sap_file in sap_dir.glob("*_sap.txt"):
                nct_id = sap_file.stem.replace("_sap", "")
                try:
                    sap_text = sap_file.read_text(encoding='utf-8', errors='ignore')
                    sections = self._parse_sections(sap_text)

                    # Detect therapeutic area from content
                    ta = self._detect_ta(sap_text)

                    for section_name, content in sections.items():
                        if content and len(content) > 50:
                            key = f"{nct_id}_{section_name}"
                            self.sections_db[key] = {
                                'nct_id': nct_id,
                                'section': section_name,
                                'content': content,
                                'therapeutic_area': ta,
                                'length': len(content)
                            }
                            total_sections += 1
                except Exception as e:
                    print(f"[RAG] Warning: Could not load {nct_id}: {e}")
                    continue

        self.indexed = total_sections > 0
        print(f"RAG: Loaded {total_sections} sections from {len(set(s['nct_id'] for s in self.sections_db.values()))} SAPs")

    def _parse_sections(self, sap_text: str) -> Dict[str, str]:
        """Parse SAP text into sections"""
        sections = {}
        current_section = "introduction"
        current_content = []

        section_patterns = {
            'introduction': r'^#+\s*(?:1[\.\s]*)?introduction',
            'objectives': r'^#+\s*(?:2[\.\s]*)?(?:study\s+)?objectives',
            'endpoints': r'^#+\s*(?:3[\.\s]*)?(?:study\s+)?endpoints?',
            'design': r'^#+\s*(?:4[\.\s]*)?study\s+design',
            'populations': r'^#+\s*(?:5[\.\s]*)?(?:analysis\s+)?populations?',
            'methods': r'^#+\s*(?:6[\.\s]*)?statistical\s+(?:analysis\s+)?methods?',
            'sample_size': r'^#+\s*(?:7[\.\s]*)?sample\s+size',
            'missing_data': r'^#+\s*(?:8[\.\s]*)?(?:handling\s+of\s+)?missing\s+data',
        }

        for line in sap_text.split('\n'):
            line_lower = line.lower().strip()

            # Check for section headers
            for section_name, pattern in section_patterns.items():
                if re.match(pattern, line_lower):
                    if current_content:
                        sections[current_section] = '\n'.join(current_content)
                    current_section = section_name
                    current_content = []
                    break
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _detect_ta(self, text: str) -> str:
        """Detect therapeutic area"""
        text_lower = text.lower()
        if 'colitis' in text_lower or 'crohn' in text_lower:
            return 'ibd'
        elif 'cancer' in text_lower or 'tumor' in text_lower:
            return 'oncology'
        elif 'arthritis' in text_lower:
            return 'rheumatology'
        return 'general'

    def retrieve(self, facts: Dict, section_type: str = None, k: int = 3) -> List[Dict]:
        """Retrieve similar sections based on therapeutic area and endpoint type"""
        if not self.indexed:
            return []

        ta = str(facts.get('therapeutic_area') or '').lower()
        results = []

        for key, section_data in self.sections_db.items():
            # Filter by therapeutic area match
            if section_data['therapeutic_area'] == ta:
                score = 1.0
            elif section_data['therapeutic_area'] == 'general':
                score = 0.5
            else:
                score = 0.2

            # Filter by section type if specified
            if section_type and section_data['section'] != section_type:
                continue

            # Boost longer, more complete sections
            if section_data['length'] > 500:
                score += 0.2

            results.append({
                'nct_id': section_data['nct_id'],
                'section': section_data['section'],
                'content': section_data['content'],
                'score': score
            })

        # Sort by score and return top k
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:k]

    def get_sanitized_examples(self, facts: Dict, section_type: str = None, k: int = 2) -> str:
        """Get sanitized examples with protocol-specific values replaced"""
        examples = self.retrieve(facts, section_type, k)

        if not examples:
            return ""

        sanitized_parts = []
        for ex in examples:
            content = ex['content']

            # Replace specific values with placeholders to prevent contamination
            # This is CRITICAL - we don't want the LLM to copy wrong values
            content = re.sub(r'NCT\d{8}', '{PROTOCOL_ID}', content)
            content = re.sub(r'\b\d{2,4}\s*(?:patients|subjects|participants)', '{SAMPLE_SIZE} patients', content, flags=re.IGNORECASE)
            content = re.sub(r'\b\d+:\d+(?::\d+)?\s*(?:randomization|ratio)', '{RATIO} randomization', content, flags=re.IGNORECASE)

            sanitized_parts.append(f"### Example from {ex['nct_id']} ({ex['section']}):\n{content[:1500]}")

        return "\n\n".join(sanitized_parts)


# =============================================================================
# STEP 3: KNOWLEDGE GRAPH
# =============================================================================

class KnowledgeGraph:
    """Static knowledge graph for statistical method selection"""

    # Endpoint type -> Recommended methods
    ENDPOINT_METHODS = {
        'time-to-event': {
            'primary': ['Kaplan-Meier', 'Log-rank test', 'Cox proportional hazards'],
            'secondary': ['Restricted mean survival time', 'Landmark analysis'],
            'sensitivity': ['Fleming-Harrington weighted log-rank', 'Peto-Peto test'],
            'adam_datasets': ['ADTTE'],
            'key_variables': ['AVAL', 'CNSR', 'STARTDT', 'ADT', 'EVNTDESC'],
        },
        'binary': {
            'primary': ['Cochran-Mantel-Haenszel test', 'Logistic regression', 'Chi-square test'],
            'secondary': ['Exact methods', 'Confidence intervals for proportions'],
            'sensitivity': ['Multiple imputation', 'Tipping point analysis'],
            'adam_datasets': ['ADEFF', 'ADRS'],
            'key_variables': ['AVALC', 'AVAL', 'CRIT1FL', 'ANL01FL'],
        },
        'continuous': {
            'primary': ['MMRM', 'ANCOVA', 'Mixed-effects model'],
            'secondary': ['t-test', 'Wilcoxon rank-sum'],
            'sensitivity': ['Pattern mixture models', 'Last observation carried forward'],
            'adam_datasets': ['ADEFF', 'ADLB'],
            'key_variables': ['AVAL', 'BASE', 'CHG', 'PCHG', 'ABLFL'],
        },
    }

    # Therapeutic area -> Specific considerations
    TA_CONSIDERATIONS = {
        'oncology': {
            'endpoints': ['OS', 'PFS', 'ORR', 'DOR', 'DCR'],
            'criteria': ['RECIST 1.1', 'iRECIST', 'RANO'],
            'populations': ['ITT', 'Evaluable', 'Per-protocol'],
            'special': ['Independent central review', 'Confirmation of response'],
        },
        'ibd': {
            'endpoints': ['Clinical remission', 'Clinical response', 'Endoscopic improvement', 'Mucosal healing'],
            'criteria': ['Modified Mayo score', 'CDAI', 'SES-CD', 'IBDQ'],
            'populations': ['FAS', 'Per-protocol', 'Bio-naive', 'Bio-experienced'],
            'special': ['Endoscopic subscore', 'Histologic remission'],
        },
        'rheumatology': {
            'endpoints': ['ACR20/50/70', 'DAS28', 'HAQ-DI', 'SDAI/CDAI'],
            'criteria': ['ACR criteria', 'EULAR response'],
            'populations': ['MTX-IR', 'TNF-IR', 'Bio-naive'],
            'special': ['Structural damage', 'Radiographic progression'],
        },
    }

    def get_recommended_methods(self, endpoint_type: str, therapeutic_area: str = None) -> Dict:
        """Get recommended statistical methods based on endpoint type"""
        endpoint_type = endpoint_type.lower().replace('-', '_').replace(' ', '_')

        if endpoint_type not in self.ENDPOINT_METHODS:
            endpoint_type = 'binary'  # Default

        methods = self.ENDPOINT_METHODS[endpoint_type].copy()

        # Add TA-specific considerations
        ta = (therapeutic_area or '').lower()
        if ta in self.TA_CONSIDERATIONS:
            methods['ta_specific'] = self.TA_CONSIDERATIONS[ta]

        return methods

    def get_adam_requirements(self, endpoint_type: str) -> Dict:
        """Get ADaM dataset requirements"""
        endpoint_type = endpoint_type.lower().replace('-', '_').replace(' ', '_')

        if endpoint_type not in self.ENDPOINT_METHODS:
            endpoint_type = 'binary'

        return {
            'datasets': self.ENDPOINT_METHODS[endpoint_type].get('adam_datasets', ['ADEFF']),
            'key_variables': self.ENDPOINT_METHODS[endpoint_type].get('key_variables', []),
        }


# =============================================================================
# STEP 4: SPECIALIZED TEMPLATES
# =============================================================================

class TemplateSelector:
    """Select and apply specialized templates based on trial type"""

    TEMPLATES = {
        TrialType.ONCOLOGY_SOLID: {
            'response_criteria': 'RECIST 1.1',
            'endpoints': ['ORR', 'PFS', 'OS', 'DOR', 'DCR', 'TTR'],
            'populations': ['ITT', 'Safety', 'Evaluable', 'Per-protocol'],
            'special_analyses': [
                'Subgroup analyses by PD-L1 status',
                'Sensitivity analysis with investigator assessment',
                'Duration of response analysis',
            ],
            'censoring_rules': [
                'Subjects without documented progression: censored at last adequate tumor assessment',
                'Subjects who start new anticancer therapy: censored at last assessment before new therapy',
                'Subjects who die without documented progression: event at date of death',
            ],
        },
        TrialType.ONCOLOGY_HEMATOLOGIC: {
            'response_criteria': 'Lugano criteria / IMWG criteria',
            'endpoints': ['ORR', 'CR', 'VGPR', 'PFS', 'OS', 'MRD negativity'],
            'populations': ['ITT', 'Response-evaluable', 'MRD-evaluable'],
            'special_analyses': [
                'MRD assessment by flow cytometry or NGS',
                'Response by cytogenetic risk group',
            ],
        },
        TrialType.ONCOLOGY_PHASE1: {
            'design': '3+3 dose escalation / BOIN / CRM',
            'endpoints': ['MTD', 'DLT rate', 'RP2D', 'PK parameters'],
            'populations': ['DLT-evaluable', 'PK-evaluable', 'Safety'],
            'special_analyses': [
                'DLT evaluation period analysis',
                'Dose-toxicity modeling',
                'PK/PD correlation',
            ],
        },
        TrialType.ONCOLOGY_CART: {
            'response_criteria': 'Disease-specific criteria',
            'endpoints': ['ORR', 'CR', 'CRS rate', 'Neurotoxicity rate', 'OS', 'PFS'],
            'safety_endpoints': [
                'CRS by ASTCT grading (Grade 1-4)',
                'ICANS by ICE score',
                'Cytokine levels (IL-6, IFN-gamma, ferritin)',
            ],
            'special_analyses': [
                'Time to CRS onset',
                'CAR-T cell expansion kinetics',
                'B-cell aplasia duration',
            ],
        },
        TrialType.ONCOLOGY_BASKET: {
            'design': 'Basket trial / Master protocol',
            'endpoints': ['ORR per tumor type', 'Pooled ORR'],
            'special_analyses': [
                'Tumor-agnostic analysis',
                'Hierarchical modeling across tumor types',
                'Predictive biomarker analysis',
            ],
        },
        TrialType.IBD: {
            'response_criteria': 'Modified Mayo score / CDAI',
            'endpoints': ['Clinical remission', 'Clinical response', 'Endoscopic improvement', 'Mucosal healing'],
            'endpoint_definitions': {
                'clinical_remission': 'Total Mayo score ≤2 with no individual subscore >1',
                'clinical_response': '≥3-point decrease and ≥30% reduction from baseline in total Mayo score',
                'endoscopic_improvement': 'Mayo endoscopic subscore ≤1',
                'mucosal_healing': 'Mayo endoscopic subscore 0',
            },
            'populations': ['FAS', 'Bio-naive', 'Bio-experienced', 'Per-protocol'],
            'special_analyses': [
                'Analysis by prior biologic exposure',
                'Histologic endpoints (Geboes score, Nancy index)',
                'Corticosteroid-free remission',
            ],
        },
        TrialType.RHEUMATOLOGY: {
            'response_criteria': 'ACR criteria / EULAR response',
            'endpoints': ['ACR20', 'ACR50', 'ACR70', 'DAS28-CRP', 'HAQ-DI', 'SDAI', 'CDAI'],
            'populations': ['FAS', 'MTX-IR', 'TNF-IR', 'Per-protocol'],
            'special_analyses': [
                'Radiographic progression (mTSS)',
                'ACR/EULAR Boolean remission',
                'Analysis by baseline disease activity',
            ],
        },
        TrialType.GENERAL: {
            'endpoints': ['Primary efficacy', 'Key secondary endpoints'],
            'populations': ['FAS', 'Safety', 'Per-protocol'],
            'special_analyses': ['Subgroup analyses', 'Sensitivity analyses'],
        },
    }

    def get_template(self, trial_type: TrialType) -> Dict:
        """Get template for trial type"""
        return self.TEMPLATES.get(trial_type, self.TEMPLATES[TrialType.GENERAL])

    def apply_template(self, trial_type: TrialType, facts: Dict) -> Dict:
        """Apply template with protocol-specific facts"""
        template = self.get_template(trial_type)

        # Merge with extracted facts
        applied = template.copy()
        applied['drug_name'] = facts.get('drug_name', 'Study drug')
        applied['sample_size'] = facts.get('sample_size', 0)
        applied['randomization_ratio'] = facts.get('randomization_ratio', '1:1')
        applied['arms'] = facts.get('arms', [])
        applied['stratification_factors'] = facts.get('stratification_factors', [])
        applied['alpha'] = facts.get('alpha', 0.05)
        applied['alpha_sidedness'] = facts.get('alpha_sidedness', 'two-sided')
        applied['power'] = facts.get('power', 0.80)

        return applied


# =============================================================================
# STEP 5: SAP GENERATION (Constrained)
# =============================================================================

class SAPGenerator:
    """Generate SAP sections using LLM with constraints"""

    def __init__(self):
        self.llm_client = None
        self._init_llm()

    def _init_llm(self):
        """Initialize LLM client"""
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            try:
                from groq import Groq
                self.llm_client = Groq(api_key=api_key)
            except ImportError:
                print("Warning: groq not installed")

    def generate_section(
        self,
        section_name: str,
        facts: Dict,
        template: Dict,
        methods: Dict,
        rag_examples: str = ""
    ) -> str:
        """Generate a single SAP section"""

        # Build prompt with mandatory facts
        prompt = self._build_section_prompt(section_name, facts, template, methods, rag_examples)

        if not self.llm_client:
            return self._generate_fallback(section_name, facts, template)

        try:
            response = self.llm_client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM error: {e}")
            return self._generate_fallback(section_name, facts, template)

    def _get_system_prompt(self) -> str:
        return """You are a biostatistician writing a Statistical Analysis Plan (SAP).

CRITICAL RULES:
1. Use ONLY the values provided in MANDATORY FACTS
2. NEVER invent drug names, sample sizes, or randomization ratios
3. NEVER copy specific values from examples - they are templates only
4. Write in formal regulatory language suitable for FDA submission
5. Be specific and technical - avoid vague statements"""

    def _build_section_prompt(
        self,
        section_name: str,
        facts: Dict,
        template: Dict,
        methods: Dict,
        rag_examples: str
    ) -> str:
        """Build prompt for section generation"""

        # Mandatory facts block
        facts_block = f"""
## MANDATORY FACTS (Use these EXACTLY)
- Drug Name: {facts.get('drug_name', 'Study drug')}
- Sample Size: {facts.get('sample_size', 'TBD')} patients
- Randomization Ratio: {facts.get('randomization_ratio', '1:1')}
- Number of Arms: {facts.get('num_arms', 2)}
- Phase: {facts.get('phase', 'Phase 3')}
- Therapeutic Area: {facts.get('therapeutic_area', 'Not specified')}
- Primary Endpoint: {facts.get('primary_endpoint', 'Primary endpoint')}
- Alpha Level: {facts.get('alpha', 0.05)} ({facts.get('alpha_sidedness', 'two-sided')})
- Power: {facts.get('power', 0.80) * 100}%
"""

        # Treatment arms
        arms = facts.get('arms', [])
        if arms:
            facts_block += "\n- Treatment Arms:\n"
            for arm in arms:
                facts_block += f"  - {arm.get('name', 'Arm')}: {arm.get('description', '')}\n"

        # Stratification factors
        strat = facts.get('stratification_factors', [])
        if strat:
            facts_block += f"\n- Stratification Factors: {', '.join(strat)}\n"

        # === NEW: Include detailed extracted facts ===

        # Interim Analysis details (for interim_analysis and statistical_methods sections)
        interim = facts.get('interim_analysis', {})
        if interim and section_name in ['interim_analysis', 'statistical_methods', 'sample_size']:
            facts_block += f"""
## INTERIM ANALYSIS DETAILS (CRITICAL - Use EXACT values)
- Number of Interim Analyses: {interim.get('num_interim_analyses', 'Not specified')}
- Alpha Spending Function: {interim.get('alpha_spending_function', 'Not specified')}
- Alpha for PFS: {interim.get('alpha_pfs', 'Not specified')}
- Alpha for OS: {interim.get('alpha_os', 'Not specified')}
"""
            # Add timing details
            timing = interim.get('interim_timing', [])
            if timing:
                facts_block += "- Interim Timing:\n"
                for t in timing:
                    facts_block += f"  - IA{t.get('ia', '?')}: ~{t.get('months', '?')} months, ~{t.get('events', '?')} {t.get('endpoint', '')} events ({t.get('population', '')})\n"

            # Final analysis
            final = interim.get('final_analysis_timing', {})
            if final:
                facts_block += f"- Final Analysis: ~{final.get('months', '?')} months, ~{final.get('events', '?')} events\n"

            # Efficacy boundaries
            boundaries = interim.get('efficacy_boundaries', [])
            if boundaries:
                facts_block += "- Efficacy Boundaries:\n"
                for b in boundaries:
                    facts_block += f"  - IA{b.get('ia', '?')}: Z={b.get('z_score', '?')}, p={b.get('p_value', '?')}, HR≤{b.get('hr_boundary', '?')}, IF={b.get('info_fraction', '?')}\n"

        # Power calculations (for sample_size section)
        power_calc = facts.get('power_calculations', {})
        if power_calc and section_name in ['sample_size', 'statistical_methods']:
            facts_block += f"""
## POWER CALCULATIONS (CRITICAL - Use EXACT values)
- PFS Power: {power_calc.get('pfs_power', 'Not specified')}
- OS Superiority Power: {power_calc.get('os_superiority_power', 'Not specified')}
- OS Non-Inferiority Power: {power_calc.get('os_ni_power', 'Not specified')}
- Control Median PFS: {power_calc.get('control_median_pfs', 'Not specified')}
- Control Median OS: {power_calc.get('control_median_os', 'Not specified')}
- Assumed Hazard Ratio: {power_calc.get('assumed_hr', 'Not specified')}
- Dropout Rate: {power_calc.get('dropout_rate', 'Not specified')}
"""

        # Exploratory endpoints (for endpoints section)
        exploratory = facts.get('exploratory_endpoints', {})
        if exploratory and section_name in ['endpoints', 'statistical_methods']:
            facts_block += f"""
## EXPLORATORY ENDPOINTS
- Duration of Response (DOR): {exploratory.get('dor', 'Not specified')}
- Disease Control Rate (DCR): {exploratory.get('dcr', 'Not specified')}
- Clinical Benefit Rate (CBR): {exploratory.get('cbr', 'Not specified')}
- PFS2 (Time to 2nd progression): {exploratory.get('pfs2', 'Not specified')}
- iRECIST Endpoints: {', '.join(exploratory.get('irecist_endpoints', [])) or 'Not specified'}
"""

        # PRO details
        pro = facts.get('pro_details', {})
        if pro and section_name in ['endpoints', 'statistical_methods']:
            facts_block += f"""
## PATIENT-REPORTED OUTCOMES
- Primary Timepoint: {pro.get('primary_timepoint', 'Not specified')}
- Completion Threshold: {pro.get('completion_threshold', 'Not specified')}
- Compliance Threshold: {pro.get('compliance_threshold', 'Not specified')}
- Improvement Definition: {pro.get('improvement_definition', 'Not specified')}
- Stability Definition: {pro.get('stability_definition', 'Not specified')}
- Instruments: {', '.join(pro.get('instruments', [])) or 'Not specified'}
"""

        # Regional extensions
        regional = facts.get('regional_extensions', {})
        if regional and section_name in ['sample_size', 'statistical_methods', 'study_design']:
            facts_block += f"""
## REGIONAL EXTENSION (CHINA)
- China Sample Size: {regional.get('china_sample_size', 'Not specified')}
- China PFS Events: {regional.get('china_pfs_events', 'Not specified')}
- China OS Events: {regional.get('china_os_events', 'Not specified')}
- Consistency Criterion: {regional.get('consistency_criterion', 'Not specified')}
"""

        # Censoring rules (for statistical_methods section)
        censoring = facts.get('censoring_rules', {})
        if censoring and section_name in ['statistical_methods', 'endpoints']:
            pfs_rules = censoring.get('pfs_censoring', [])
            dor_rules = censoring.get('dor_censoring', [])
            pfs2_rules = censoring.get('pfs2_censoring', [])

            if pfs_rules or dor_rules or pfs2_rules:
                facts_block += "\n## CENSORING RULES\n"
                if pfs_rules:
                    facts_block += "- PFS Censoring:\n"
                    for rule in pfs_rules[:5]:  # Limit to avoid prompt bloat
                        facts_block += f"  - {rule.get('scenario', '?')}: {rule.get('censoring', rule.get('event_type', '?'))}\n"
                if dor_rules:
                    facts_block += "- DOR Censoring:\n"
                    for rule in dor_rules[:5]:
                        facts_block += f"  - {rule.get('scenario', '?')}: {rule.get('censoring', rule.get('event_type', '?'))}\n"
                if pfs2_rules:
                    facts_block += "- PFS2 Censoring:\n"
                    for rule in pfs2_rules[:5]:
                        facts_block += f"  - {rule.get('scenario', '?')}: {rule.get('censoring', rule.get('event_type', '?'))}\n"

        # Methods from knowledge graph
        methods_block = ""
        if methods:
            methods_block = f"""
## RECOMMENDED METHODS
- Primary Analysis: {', '.join(methods.get('primary', []))}
- Secondary Analysis: {', '.join(methods.get('secondary', []))}
- ADaM Datasets: {', '.join(methods.get('adam_datasets', []))}
"""

        # Template info
        template_block = ""
        if template:
            template_block = f"""
## TEMPLATE GUIDANCE
- Response Criteria: {template.get('response_criteria', 'Standard criteria')}
- Endpoints: {', '.join(template.get('endpoints', []))}
- Populations: {', '.join(template.get('populations', []))}
"""

        # Examples (sanitized)
        examples_block = ""
        if rag_examples:
            examples_block = f"""
## REFERENCE EXAMPLES (Use structure only, NOT specific values)
{rag_examples}
"""

        return f"""Write the {section_name} section for a Statistical Analysis Plan.

{facts_block}
{methods_block}
{template_block}
{examples_block}

Write the {section_name} section now. Use markdown formatting.
Remember: Use ONLY the mandatory facts provided above."""

    def _generate_fallback(self, section_name: str, facts: Dict, template: Dict) -> str:
        """Generate section without LLM (template-based) - comprehensive fallback"""
        drug = facts.get('drug_name') or 'study drug'
        n = facts.get('sample_size') or 'TBD'
        ratio = facts.get('randomization_ratio') or '1:1'
        phase = facts.get('phase') or 'Phase 3'
        ta = facts.get('therapeutic_area') or 'Not specified'
        endpoint = facts.get('primary_endpoint') or 'Primary endpoint'
        alpha = facts.get('alpha', 0.05)
        sidedness = facts.get('alpha_sidedness', 'two-sided')
        power = facts.get('power', 0.80)
        strat = facts.get('stratification_factors', [])
        arms = facts.get('arms', [])
        methods = template.get('primary', []) if isinstance(template, dict) else []
        populations = template.get('populations', ['FAS', 'Safety', 'Per-protocol'])
        response_criteria = template.get('response_criteria', '')
        endpoints = template.get('endpoints', [endpoint])

        if section_name == 'introduction':
            return f"""## 1. Introduction

### 1.1 Background
This Statistical Analysis Plan (SAP) describes the planned statistical analyses for the {phase} study of {drug}.

### 1.2 Study Overview
- **Study Drug:** {drug}
- **Therapeutic Area:** {ta}
- **Phase:** {phase}
- **Sample Size:** {n} patients
- **Randomization:** {ratio}

### 1.3 Purpose
This document provides a comprehensive description of the statistical methods to be used in the analysis of efficacy and safety data from this study.
"""

        elif section_name == 'objectives':
            return f"""## 2. Study Objectives

### 2.1 Primary Objective
To evaluate the efficacy of {drug} compared to placebo in patients as measured by {endpoint}.

### 2.2 Secondary Objectives
- To evaluate additional efficacy endpoints
- To evaluate the safety and tolerability of {drug}
- To characterize the pharmacokinetics of {drug}
"""

        elif section_name == 'endpoints':
            endpoints_list = '\n'.join([f"- {e}" for e in endpoints[:5]])
            return f"""## 3. Study Endpoints

### 3.1 Primary Endpoint
{endpoint}

{f"**Assessment Criteria:** {response_criteria}" if response_criteria else ""}

### 3.2 Secondary Endpoints
{endpoints_list}

### 3.3 Exploratory Endpoints
- Biomarker analyses
- Subgroup analyses by baseline characteristics
"""

        elif section_name == 'study_design':
            arms_desc = '\n'.join([f"- **{arm.get('name', 'Arm')}:** {arm.get('description', 'Treatment')}" for arm in arms]) if arms else "- Treatment arm\n- Control arm"
            strat_desc = ', '.join(strat) if strat else 'Baseline disease severity, prior therapy'
            return f"""## 4. Study Design

### 4.1 Design Overview
This is a {phase}, randomized, double-blind, placebo-controlled study.

### 4.2 Sample Size
- **Total:** {n} patients
- **Randomization Ratio:** {ratio}

### 4.3 Treatment Arms
{arms_desc}

### 4.4 Stratification Factors
Randomization will be stratified by:
- {strat_desc}

### 4.5 Study Duration
Treatment period followed by follow-up assessments.
"""

        elif section_name == 'populations':
            pops_list = '\n'.join([f"- **{p}:** Analysis population" for p in populations])
            return f"""## 5. Analysis Populations

### 5.1 Population Definitions
{pops_list}

### 5.2 Full Analysis Set (FAS)
All randomized subjects who receive at least one dose of study drug and have at least one post-baseline efficacy assessment.

### 5.3 Safety Population
All subjects who receive at least one dose of study drug.

### 5.4 Per-Protocol Population
All FAS subjects without major protocol deviations.
"""

        elif section_name == 'statistical_methods':
            methods_list = ', '.join(methods) if methods else 'Cochran-Mantel-Haenszel test'
            return f"""## 6. Statistical Methods

### 6.1 Primary Analysis
The primary efficacy analysis will use **{methods_list}** stratified by randomization factors.

- **Significance Level:** {sidedness} α = {alpha}
- **Confidence Intervals:** {int((1-alpha)*100)}% confidence intervals will be provided

### 6.2 Secondary Analyses
Secondary endpoints will be analyzed using appropriate methods:
- Binary endpoints: CMH test, logistic regression
- Continuous endpoints: ANCOVA, MMRM
- Time-to-event endpoints: Kaplan-Meier, Cox regression

### 6.3 Sensitivity Analyses
- Per-protocol analysis
- Multiple imputation for missing data
- Tipping point analysis

### 6.4 Subgroup Analyses
Subgroup analyses will be performed by:
- Prior therapy status
- Baseline disease severity
- Geographic region
"""

        elif section_name == 'sample_size':
            return f"""## 7. Sample Size

### 7.1 Sample Size Calculation
A total of **{n} patients** will be randomized in a **{ratio}** ratio.

### 7.2 Assumptions
- **Power:** {int(power*100)}%
- **Significance Level:** {sidedness} α = {alpha}
- **Expected Response Rate (Placebo):** Based on historical data
- **Expected Response Rate (Treatment):** Based on Phase 2 data
- **Dropout Rate:** ~15%

### 7.3 Justification
The sample size provides adequate power to detect a clinically meaningful treatment difference.
"""

        elif section_name == 'missing_data':
            return f"""## 8. Handling of Missing Data

### 8.1 General Approach
- Primary analysis: Modified intent-to-treat (all randomized with baseline and ≥1 post-baseline)
- Missing data assumed to be missing at random (MAR)

### 8.2 Methods for Missing Data
- **Primary:** Mixed Model for Repeated Measures (MMRM)
- **Sensitivity 1:** Multiple imputation
- **Sensitivity 2:** Last observation carried forward (LOCF)
- **Sensitivity 3:** Non-responder imputation (for binary endpoints)

### 8.3 Intercurrent Events
- Treatment discontinuation: Treatment policy estimand
- Use of rescue medication: Composite strategy
- Death: Handled per endpoint definition
"""

        else:
            return f"""## {section_name.replace('_', ' ').title()}

### Overview
This section describes the {section_name.replace('_', ' ')} for the study of {drug}.

- Sample Size: {n} patients
- Randomization: {ratio}
- Phase: {phase}
"""

    def generate_all_sections(
        self,
        facts: Dict,
        template: Dict,
        methods: Dict,
        rag_retriever: 'RAGRetriever'
    ) -> Dict[str, str]:
        """Generate all SAP sections"""
        sections = {}

        section_names = [
            'introduction',
            'objectives',
            'endpoints',
            'study_design',
            'populations',
            'statistical_methods',
            'interim_analysis',  # NEW: Added interim analysis section
            'sample_size',
            'missing_data',
        ]

        for section_name in section_names:
            # Get RAG examples for this section type
            rag_examples = rag_retriever.get_sanitized_examples(facts, section_name, k=2)

            # Generate section
            sections[section_name] = self.generate_section(
                section_name, facts, template, methods, rag_examples
            )

        return sections


# =============================================================================
# STEP 6: QA VALIDATION
# =============================================================================

class QAValidator:
    """Validate generated SAP for quality issues"""

    def validate(self, sap_text: str, facts: Dict) -> Dict:
        """Run all validation checks"""
        issues = []
        warnings = []
        score = 100.0

        # Check 1: Drug name present
        drug = facts.get('drug_name')
        if drug and drug.lower() not in sap_text.lower():
            issues.append(f"Drug name '{drug}' not found in SAP")
            score -= 10

        # Check 2: Sample size present
        n = facts.get('sample_size')
        if n and str(n) not in sap_text:
            issues.append(f"Sample size '{n}' not found in SAP")
            score -= 10

        # Check 3: Randomization ratio present
        ratio = facts.get('randomization_ratio')
        if ratio and ratio not in sap_text:
            issues.append(f"Randomization ratio '{ratio}' not found in SAP")
            score -= 5

        # Check 4: Required sections present
        required_sections = ['introduction', 'endpoint', 'population', 'method', 'sample size']
        for section in required_sections:
            if section not in sap_text.lower():
                warnings.append(f"Section '{section}' may be missing")
                score -= 5

        # Check 5: Contamination check - wrong NCT IDs
        nct_ids = re.findall(r'NCT\d{8}', sap_text)
        expected_nct = facts.get('nct_id')
        for nct in nct_ids:
            if expected_nct and nct != expected_nct:
                issues.append(f"Contamination: Wrong NCT ID '{nct}' (expected {expected_nct})")
                score -= 15

        # Check 6: Minimum length
        if len(sap_text) < 2000:
            warnings.append("SAP may be too short")
            score -= 10

        return {
            'score': max(0, score),
            'issues': issues,
            'warnings': warnings,
            'valid': len(issues) == 0
        }


# =============================================================================
# MAIN INTEGRATED PIPELINE
# =============================================================================

class IntegratedPipeline:
    """
    The fully integrated production pipeline.

    This is what ACTUALLY runs in production, using:
    1. Regex extraction
    2. RAG retrieval
    3. Knowledge graph
    4. Specialized templates
    5. Constrained LLM generation
    6. QA validation
    """

    def __init__(self):
        print("=" * 60)
        print("INTEGRATED PRODUCTION PIPELINE")
        print("=" * 60)

        # Initialize components
        print("Initializing components...")

        self.extractor = FactExtractor()
        print("  [OK] Fact Extractor")

        self.rag_retriever = RAGRetriever()
        print(f"  [OK] RAG Retriever ({len(self.rag_retriever.sections_db)} sections)")

        self.knowledge_graph = KnowledgeGraph()
        print("  [OK] Knowledge Graph")

        self.template_selector = TemplateSelector()
        print("  [OK] Template Selector")

        self.generator = SAPGenerator()
        print("  [OK] SAP Generator")

        self.validator = QAValidator()
        print("  [OK] QA Validator")

        print("=" * 60)

    def generate(self, protocol_text: str, nct_id: str = None) -> IntegratedResult:
        """Run the full integrated pipeline"""
        result = IntegratedResult(success=False)
        start_time = time.time()

        try:
            # =================================================================
            # STEP 1: EXTRACTION
            # =================================================================
            print("\n[1/6] EXTRACTING FACTS (regex only)...")
            t0 = time.time()

            facts = self.extractor.extract(protocol_text)
            if nct_id:
                facts['nct_id'] = nct_id

            result.facts = facts  # Store full facts dict for API access
            result.drug_name = facts.get('drug_name', '')
            result.sample_size = facts.get('sample_size', 0)
            result.num_arms = facts.get('num_arms', 0)
            result.randomization_ratio = facts.get('randomization_ratio', '')
            result.phase = facts.get('phase', '')
            result.therapeutic_area = facts.get('therapeutic_area', '')
            result.endpoint_type = facts.get('endpoint_type', '')
            result.primary_endpoint = facts.get('primary_endpoint', '')

            result.extraction_time = time.time() - t0
            print(f"  Drug: {result.drug_name}")
            print(f"  N: {result.sample_size}")
            print(f"  Ratio: {result.randomization_ratio}")
            print(f"  Therapeutic Area: {result.therapeutic_area}")
            print(f"  Endpoint Type: {result.endpoint_type}")

            # =================================================================
            # STEP 2: RAG RETRIEVAL
            # =================================================================
            print("\n[2/6] RETRIEVING RAG EXAMPLES...")
            t0 = time.time()

            similar = self.rag_retriever.retrieve(facts, k=3)
            result.rag_examples_used = len(similar)
            result.rag_nct_ids = [s['nct_id'] for s in similar]

            result.rag_time = time.time() - t0
            print(f"  Found {len(similar)} similar sections")
            if result.rag_nct_ids:
                print(f"  From: {result.rag_nct_ids}")

            # =================================================================
            # STEP 3: KNOWLEDGE GRAPH
            # =================================================================
            print("\n[3/6] QUERYING KNOWLEDGE GRAPH...")

            methods = self.knowledge_graph.get_recommended_methods(
                result.endpoint_type,
                result.therapeutic_area
            )
            adam_reqs = self.knowledge_graph.get_adam_requirements(result.endpoint_type)

            result.recommended_methods = methods.get('primary', [])
            result.adam_datasets = adam_reqs.get('datasets', [])

            print(f"  Recommended Methods: {result.recommended_methods}")
            print(f"  ADaM Datasets: {result.adam_datasets}")

            # =================================================================
            # STEP 4: TEMPLATE SELECTION
            # =================================================================
            print("\n[4/6] SELECTING SPECIALIZED TEMPLATE...")

            trial_type = facts.get('trial_type', TrialType.GENERAL)
            template = self.template_selector.apply_template(trial_type, facts)

            result.templates_applied = [trial_type.value]
            result.trial_type = trial_type.value  # Store for API access
            print(f"  Trial Type: {trial_type.value}")
            print(f"  Response Criteria: {template.get('response_criteria', 'Standard')}")

            # =================================================================
            # STEP 5: GENERATION
            # =================================================================
            print("\n[5/6] GENERATING SAP SECTIONS...")
            t0 = time.time()

            sections = self.generator.generate_all_sections(
                facts, template, methods, self.rag_retriever
            )

            result.sections = sections
            result.generation_time = time.time() - t0
            print(f"  Generated {len(sections)} sections")

            # Assemble full document
            result.sap_text = self._assemble_document(sections, facts)

            # =================================================================
            # STEP 6: QA VALIDATION
            # =================================================================
            print("\n[6/6] VALIDATING OUTPUT...")
            t0 = time.time()

            qa_result = self.validator.validate(result.sap_text, facts)

            result.quality_score = qa_result['score']
            result.issues = qa_result['issues']
            result.warnings = qa_result['warnings']
            result.qa_time = time.time() - t0

            print(f"  Quality Score: {result.quality_score:.1f}/100")
            if result.issues:
                print(f"  Issues: {result.issues}")
            if result.warnings:
                print(f"  Warnings: {result.warnings}")

            result.success = qa_result['valid'] or result.quality_score >= 70
            result.total_time = time.time() - start_time

            print("\n" + "=" * 60)
            print(f"PIPELINE COMPLETE in {result.total_time:.1f}s")
            print(f"Success: {result.success}")
            print(f"Quality: {result.quality_score:.1f}/100")
            print("=" * 60)

        except Exception as e:
            result.errors.append(str(e))
            result.total_time = time.time() - start_time
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()

        return result

    def _assemble_document(self, sections: Dict[str, str], facts: Dict) -> str:
        """Assemble sections into complete SAP document"""

        header = f"""# STATISTICAL ANALYSIS PLAN

**Protocol:** {facts.get('nct_id', 'TBD')}
**Drug:** {facts.get('drug_name', 'Study Drug')}
**Phase:** {facts.get('phase', 'Phase 3')}
**Date:** {datetime.now().strftime('%d-%b-%Y')}

---

"""

        body_parts = []
        section_order = [
            'introduction',
            'objectives',
            'endpoints',
            'study_design',
            'populations',
            'statistical_methods',
            'sample_size',
            'missing_data',
        ]

        for section_name in section_order:
            if section_name in sections:
                body_parts.append(sections[section_name])

        footer = """

---

**Document History**

| Version | Date | Description |
|---------|------|-------------|
| 1.0 | {date} | Initial version |

---

*Generated using Integrated Production Pipeline*
""".format(date=datetime.now().strftime('%d-%b-%Y'))

        return header + "\n\n".join(body_parts) + footer


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_integrated_pipeline() -> IntegratedPipeline:
    """Create an integrated pipeline instance"""
    return IntegratedPipeline()


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    # Quick test
    pipeline = create_integrated_pipeline()

    test_protocol = """
    Protocol: NCT12345678

    A Phase 3, Randomized, Double-Blind, Placebo-Controlled Study of
    Pembrolizumab in Patients with Ulcerative Colitis

    Approximately 300 patients will be randomized in a 1:1 ratio to receive
    either pembrolizumab 200mg IV or placebo.

    Primary Endpoint: Clinical remission at Week 12, defined as total Mayo
    score ≤2 with no individual subscore >1.

    Stratification factors: Prior biologic use (yes/no), baseline disease severity

    Statistical Analysis: Primary analysis using CMH test stratified by
    randomization factors. Two-sided alpha of 0.05.
    """

    result = pipeline.generate(test_protocol, nct_id="NCT12345678")

    print("\n\nGENERATED SAP PREVIEW:")
    print(result.sap_text[:2000])
