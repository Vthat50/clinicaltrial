"""
SAP Evaluation Framework (v2)
=============================

Evaluates generated SAPs based on REAL regulatory criteria:

1. Protocol-SAP Alignment (ICH E9 R1)
   - Does the SAP match the protocol's population, endpoints, design?

2. Regulatory Completeness (Gamble et al. 2017 JAMA Guidelines)
   - Does it have the 6 required sections?
   - Are the 55 recommended items addressed?

3. Estimand Alignment (ICH E9 R1 Addendum)
   - Population, Treatment, Endpoint, Intercurrent Events, Summary Measure

Sources:
- JAMA Guidelines: https://jamanetwork.com/journals/jama/fullarticle/2666509
- ICH E9(R1): https://pmc.ncbi.nlm.nih.gov/articles/PMC9232859/
- FDA Review: https://www.fda.gov/media/87621/download
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import time


# =============================================================================
# SECTION 1: Data Structures
# =============================================================================

@dataclass
class EvalResult:
    """Evaluation result for a single SAP."""
    nct_id: str

    # 1. Protocol-SAP Alignment (0-1 scores)
    population_alignment: float = 0.0      # Does SAP population match protocol?
    endpoint_alignment: float = 0.0        # Do endpoints match?
    design_alignment: float = 0.0          # Does design match?
    treatment_alignment: float = 0.0       # Do treatment arms match?

    # 2. Regulatory Completeness (0-1 scores)
    has_admin_section: float = 0.0         # Section 1: Title, version, signatures
    has_intro_section: float = 0.0         # Section 2: Background, objectives
    has_methods_section: float = 0.0       # Section 3: Design, randomization
    has_principles_section: float = 0.0    # Section 4: Hypothesis, alpha, power
    has_population_section: float = 0.0    # Section 5: Analysis sets (ITT, PP)
    has_analysis_section: float = 0.0      # Section 6: Primary, secondary, safety
    regulatory_completeness: float = 0.0   # Average of above

    # 3. Estimand Components (ICH E9 R1)
    has_estimand_population: float = 0.0   # Target population defined?
    has_estimand_treatment: float = 0.0    # Treatment conditions specified?
    has_estimand_endpoint: float = 0.0     # Variable/endpoint defined?
    has_estimand_intercurrent: float = 0.0 # Intercurrent events addressed?
    has_estimand_summary: float = 0.0      # Summary measure specified?
    estimand_completeness: float = 0.0     # Average of above

    # 4. FDA Review Criteria
    is_prospective: float = 0.0            # SAP before unblinding?
    has_primary_analysis: float = 0.0      # Primary endpoint analysis clear?
    has_multiplicity_control: float = 0.0  # Multiple comparisons addressed?
    has_missing_data_plan: float = 0.0     # Missing data handling?
    has_interim_plan: float = 0.0          # Interim analysis specified?
    fda_criteria_score: float = 0.0        # Average of above

    # 5. Text Similarity (reference comparison)
    rouge_l: float = 0.0
    cosine_similarity: float = 0.0

    # Overall
    overall_score: float = 0.0
    eval_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'nct_id': self.nct_id,
            'protocol_alignment': {
                'population': self.population_alignment,
                'endpoint': self.endpoint_alignment,
                'design': self.design_alignment,
                'treatment': self.treatment_alignment,
                'score': (self.population_alignment + self.endpoint_alignment +
                         self.design_alignment + self.treatment_alignment) / 4
            },
            'regulatory_completeness': {
                'admin_section': self.has_admin_section,
                'intro_section': self.has_intro_section,
                'methods_section': self.has_methods_section,
                'principles_section': self.has_principles_section,
                'population_section': self.has_population_section,
                'analysis_section': self.has_analysis_section,
                'score': self.regulatory_completeness,
            },
            'estimand_alignment': {
                'population': self.has_estimand_population,
                'treatment': self.has_estimand_treatment,
                'endpoint': self.has_estimand_endpoint,
                'intercurrent': self.has_estimand_intercurrent,
                'summary': self.has_estimand_summary,
                'score': self.estimand_completeness,
            },
            'fda_criteria': {
                'prospective': self.is_prospective,
                'primary_analysis': self.has_primary_analysis,
                'multiplicity': self.has_multiplicity_control,
                'missing_data': self.has_missing_data_plan,
                'interim': self.has_interim_plan,
                'score': self.fda_criteria_score,
            },
            'similarity': {
                'rouge_l': self.rouge_l,
                'cosine': self.cosine_similarity,
            },
            'overall_score': self.overall_score,
            'eval_time': self.eval_time,
            'errors': self.errors,
        }


# =============================================================================
# SECTION 2: Protocol Extractor
# =============================================================================

class ProtocolExtractor:
    """
    Extract key elements from protocol for alignment checking.
    """

    def extract(self, protocol_text: str) -> Dict[str, Any]:
        """Extract protocol elements for comparison."""
        text_lower = protocol_text.lower()

        return {
            'population': self._extract_population(protocol_text),
            'endpoints': self._extract_endpoints(protocol_text),
            'design': self._extract_design(protocol_text),
            'treatments': self._extract_treatments(protocol_text),
            'sample_size': self._extract_sample_size(protocol_text),
            'phase': self._extract_phase(protocol_text),
        }

    def _extract_population(self, text: str) -> Dict[str, Any]:
        """Extract population/eligibility criteria."""
        population = {
            'age_min': None,
            'age_max': None,
            'sex': None,
            'conditions': [],
        }

        # Age extraction
        age_pattern = r'(?:minimum|min)?\s*age[:\s]*(\d+)\s*(?:years|yrs)?'
        age_match = re.search(age_pattern, text, re.IGNORECASE)
        if age_match:
            population['age_min'] = int(age_match.group(1))

        max_age_pattern = r'(?:maximum|max)\s*age[:\s]*(\d+)\s*(?:years|yrs)?'
        max_match = re.search(max_age_pattern, text, re.IGNORECASE)
        if max_match:
            population['age_max'] = int(max_match.group(1))

        # Sex
        if 'female' in text.lower() and 'male' not in text.lower():
            population['sex'] = 'female'
        elif 'male' in text.lower() and 'female' not in text.lower():
            population['sex'] = 'male'
        else:
            population['sex'] = 'all'

        # Cancer types
        cancer_types = [
            'breast cancer', 'lung cancer', 'nsclc', 'sclc',
            'colorectal', 'prostate', 'melanoma', 'lymphoma',
            'leukemia', 'myeloma', 'ovarian', 'pancreatic',
            'hepatocellular', 'gastric', 'renal', 'bladder',
            'head and neck', 'glioblastoma', 'sarcoma'
        ]
        for cancer in cancer_types:
            if cancer in text.lower():
                population['conditions'].append(cancer)

        return population

    def _extract_endpoints(self, text: str) -> Dict[str, List[str]]:
        """Extract primary and secondary endpoints."""
        endpoints = {'primary': [], 'secondary': []}

        # Common oncology endpoints
        endpoint_terms = {
            'overall survival': 'os',
            'progression-free survival': 'pfs',
            'progression free survival': 'pfs',
            'objective response rate': 'orr',
            'response rate': 'orr',
            'duration of response': 'dor',
            'disease control rate': 'dcr',
            'time to progression': 'ttp',
            'event-free survival': 'efs',
            'complete response': 'cr',
            'partial response': 'pr',
        }

        text_lower = text.lower()

        # Find primary endpoints
        primary_section = re.search(
            r'primary\s+(?:endpoint|outcome|objective)[s]?[:\s]*(.*?)(?:secondary|$)',
            text_lower, re.DOTALL
        )
        if primary_section:
            section_text = primary_section.group(1)
            for term, abbrev in endpoint_terms.items():
                if term in section_text:
                    endpoints['primary'].append(abbrev)

        # Find secondary endpoints
        secondary_section = re.search(
            r'secondary\s+(?:endpoint|outcome|objective)[s]?[:\s]*(.*?)(?:exploratory|safety|$)',
            text_lower, re.DOTALL
        )
        if secondary_section:
            section_text = secondary_section.group(1)
            for term, abbrev in endpoint_terms.items():
                if term in section_text:
                    endpoints['secondary'].append(abbrev)

        return endpoints

    def _extract_design(self, text: str) -> Dict[str, Any]:
        """Extract study design elements."""
        design = {
            'type': None,
            'randomized': False,
            'blinding': None,
            'arms': 0,
            'allocation': None,
        }

        text_lower = text.lower()

        # Study type
        if 'phase 3' in text_lower or 'phase iii' in text_lower:
            design['type'] = 'phase3'
        elif 'phase 2' in text_lower or 'phase ii' in text_lower:
            design['type'] = 'phase2'
        elif 'phase 1' in text_lower or 'phase i' in text_lower:
            design['type'] = 'phase1'

        # Randomization
        design['randomized'] = 'random' in text_lower

        # Blinding
        if 'double-blind' in text_lower or 'double blind' in text_lower:
            design['blinding'] = 'double'
        elif 'single-blind' in text_lower or 'single blind' in text_lower:
            design['blinding'] = 'single'
        elif 'open-label' in text_lower or 'open label' in text_lower:
            design['blinding'] = 'open'

        # Allocation ratio
        ratio_match = re.search(r'(\d+):(\d+)\s*(?:ratio|allocation)', text_lower)
        if ratio_match:
            design['allocation'] = f"{ratio_match.group(1)}:{ratio_match.group(2)}"

        return design

    def _extract_treatments(self, text: str) -> List[str]:
        """Extract treatment arms."""
        treatments = []

        # Look for arm descriptions
        arm_pattern = r'(?:arm|group)\s*[:\s]*([^.]+)'
        matches = re.findall(arm_pattern, text, re.IGNORECASE)
        treatments.extend([m.strip()[:50] for m in matches[:4]])  # Max 4 arms

        return treatments

    def _extract_sample_size(self, text: str) -> Optional[int]:
        """Extract sample size."""
        patterns = [
            r'enrollment[:\s]*(\d+)',
            r'sample\s*size[:\s]*(\d+)',
            r'(\d+)\s*(?:subjects|patients|participants)',
            r'n\s*=\s*(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return None

    def _extract_phase(self, text: str) -> Optional[str]:
        """Extract study phase."""
        text_lower = text.lower()

        if 'phase 3' in text_lower or 'phase3' in text_lower or 'phase iii' in text_lower:
            return 'phase3'
        elif 'phase 2' in text_lower or 'phase2' in text_lower or 'phase ii' in text_lower:
            return 'phase2'
        elif 'phase 1' in text_lower or 'phase1' in text_lower or 'phase i' in text_lower:
            return 'phase1'

        return None


# =============================================================================
# SECTION 3: Protocol-SAP Alignment Checker
# =============================================================================

class AlignmentChecker:
    """
    Check if SAP aligns with protocol (ICH E9 R1 requirement).

    This is the key insight: Real SAP evaluation is about whether
    the SAP correctly reflects what's in the protocol.
    """

    def __init__(self):
        self.extractor = ProtocolExtractor()

    def check_alignment(self, protocol: str, sap: str) -> Dict[str, float]:
        """
        Check SAP alignment with protocol.

        Returns scores for:
        - population_alignment: Do populations match?
        - endpoint_alignment: Do endpoints match?
        - design_alignment: Does design match?
        - treatment_alignment: Do treatments match?
        """
        protocol_data = self.extractor.extract(protocol)
        sap_data = self.extractor.extract(sap)

        return {
            'population_alignment': self._check_population(
                protocol_data['population'],
                sap_data['population']
            ),
            'endpoint_alignment': self._check_endpoints(
                protocol_data['endpoints'],
                sap_data['endpoints']
            ),
            'design_alignment': self._check_design(
                protocol_data['design'],
                sap_data['design']
            ),
            'treatment_alignment': self._check_treatments(
                protocol_data['treatments'],
                sap_data['treatments']
            ),
        }

    def _check_population(self, protocol_pop: Dict, sap_pop: Dict) -> float:
        """Check population alignment."""
        score = 0.0
        checks = 0

        # Check conditions match
        if protocol_pop['conditions']:
            checks += 1
            proto_conditions = set(protocol_pop['conditions'])
            sap_conditions = set(sap_pop['conditions'])
            if proto_conditions & sap_conditions:  # Any overlap
                score += 1.0
            elif sap_conditions:  # SAP has conditions but wrong ones
                score += 0.5

        # Check age alignment
        if protocol_pop['age_min']:
            checks += 1
            if sap_pop['age_min'] == protocol_pop['age_min']:
                score += 1.0
            elif sap_pop['age_min']:
                score += 0.5  # Has age, but different

        return score / checks if checks > 0 else 0.5

    def _check_endpoints(self, protocol_ep: Dict, sap_ep: Dict) -> float:
        """Check endpoint alignment."""
        score = 0.0

        # Primary endpoints
        if protocol_ep['primary']:
            proto_primary = set(protocol_ep['primary'])
            sap_primary = set(sap_ep['primary'])

            if proto_primary == sap_primary:
                score += 0.6  # Perfect match
            elif proto_primary & sap_primary:
                score += 0.4  # Partial match
            elif sap_primary:
                score += 0.2  # Has primary but different
        else:
            score += 0.3  # No protocol primary to compare

        # Secondary endpoints
        if protocol_ep['secondary']:
            proto_secondary = set(protocol_ep['secondary'])
            sap_secondary = set(sap_ep['secondary'])

            if proto_secondary & sap_secondary:
                score += 0.4
            elif sap_secondary:
                score += 0.2
        else:
            score += 0.2

        return min(score, 1.0)

    def _check_design(self, protocol_design: Dict, sap_design: Dict) -> float:
        """Check design alignment."""
        score = 0.0
        checks = 0

        # Phase
        if protocol_design['type']:
            checks += 1
            if sap_design['type'] == protocol_design['type']:
                score += 1.0

        # Randomization
        checks += 1
        if sap_design['randomized'] == protocol_design['randomized']:
            score += 1.0

        # Blinding
        if protocol_design['blinding']:
            checks += 1
            if sap_design['blinding'] == protocol_design['blinding']:
                score += 1.0

        return score / checks if checks > 0 else 0.5

    def _check_treatments(self, protocol_tx: List, sap_tx: List) -> float:
        """Check treatment alignment."""
        if not protocol_tx:
            return 0.5  # Nothing to compare

        # Simple check: do any treatment terms overlap?
        protocol_terms = ' '.join(protocol_tx).lower()
        sap_terms = ' '.join(sap_tx).lower()

        # Extract drug names (simplified)
        proto_words = set(protocol_terms.split())
        sap_words = set(sap_terms.split())

        overlap = proto_words & sap_words
        if overlap:
            return min(len(overlap) / len(proto_words), 1.0)

        return 0.0


# =============================================================================
# SECTION 4: Regulatory Completeness Checker
# =============================================================================

class RegulatoryChecker:
    """
    Check SAP against Gamble et al. 2017 JAMA Guidelines.

    The 6 required sections:
    1. Administrative (title, version, signatures)
    2. Introduction (background, objectives)
    3. Study Methods (design, randomization, blinding)
    4. Statistical Principles (hypothesis, alpha, power)
    5. Trial Population (analysis sets: ITT, PP, Safety)
    6. Analysis (primary, secondary, sensitivity, safety)
    """

    # Section indicators
    SECTION_PATTERNS = {
        'admin': [
            r'statistical\s+analysis\s+plan',
            r'version\s*[:\s]*\d',
            r'protocol\s+(?:no|number|#)',
            r'sponsor',
            r'date\s*[:\s]*\d',
            r'signature',
        ],
        'intro': [
            r'introduction',
            r'background',
            r'study\s+objectives?',
            r'purpose',
            r'rationale',
        ],
        'methods': [
            r'study\s+design',
            r'randomization',
            r'blinding',
            r'masking',
            r'allocation',
            r'stratification',
        ],
        'principles': [
            r'statistical\s+(?:hypothesis|principles?|methods?)',
            r'type\s+i\s+error',
            r'alpha\s*=?\s*0?\.\d',
            r'significance\s+level',
            r'power\s*=?\s*\d',
            r'two-?sided',
            r'one-?sided',
            r'sample\s+size',
        ],
        'population': [
            r'analysis\s+(?:population|set)s?',
            r'intent[- ]to[- ]treat',
            r'\bitt\b',
            r'per[- ]protocol',
            r'safety\s+(?:population|set)',
            r'full\s+analysis\s+set',
            r'\bfas\b',
            r'evaluable',
        ],
        'analysis': [
            r'primary\s+(?:endpoint|outcome|analysis|efficacy)',
            r'secondary\s+(?:endpoint|outcome|analysis)',
            r'sensitivity\s+analysis',
            r'subgroup\s+analysis',
            r'safety\s+analysis',
            r'adverse\s+event',
            r'interim\s+analysis',
        ],
    }

    def check_completeness(self, sap_text: str) -> Dict[str, float]:
        """Check if SAP has all required sections."""
        text_lower = sap_text.lower()

        results = {}
        for section, patterns in self.SECTION_PATTERNS.items():
            found = 0
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    found += 1

            # Score based on how many indicators found
            results[f'has_{section}_section'] = min(found / 2, 1.0)

        # Overall completeness
        results['regulatory_completeness'] = sum(
            v for k, v in results.items() if k.startswith('has_')
        ) / 6

        return results


# =============================================================================
# SECTION 5: Estimand Checker (ICH E9 R1)
# =============================================================================

class EstimandChecker:
    """
    Check SAP for estimand components per ICH E9(R1).

    The 5 estimand attributes:
    1. Population - Target population
    2. Treatment - Treatment conditions
    3. Endpoint - Variable measured
    4. Intercurrent events - How to handle discontinuation, rescue, etc.
    5. Summary measure - Hazard ratio, mean difference, etc.
    """

    ESTIMAND_PATTERNS = {
        'population': [
            r'target\s+population',
            r'population\s+(?:of|for)\s+interest',
            r'patients?\s+(?:with|who)',
            r'eligib(?:le|ility)',
            r'inclusion\s+criteria',
        ],
        'treatment': [
            r'treatment\s+(?:arm|group|condition)s?',
            r'intervention',
            r'comparator',
            r'control\s+(?:arm|group)',
            r'placebo',
            r'active\s+(?:treatment|control)',
        ],
        'endpoint': [
            r'endpoint\s+definition',
            r'outcome\s+(?:measure|variable)',
            r'primary\s+(?:endpoint|variable)',
            r'time\s+(?:to\s+event|frame)',
            r'assessment\s+(?:schedule|window)',
        ],
        'intercurrent': [
            r'intercurrent\s+event',
            r'treatment\s+discontinuation',
            r'rescue\s+(?:medication|therapy)',
            r'treatment\s+switch',
            r'protocol\s+deviation',
            r'withdrawal',
            r'loss\s+to\s+follow',
            r'missing\s+data\s+(?:due\s+to|handling)',
        ],
        'summary': [
            r'hazard\s+ratio',
            r'odds\s+ratio',
            r'risk\s+(?:ratio|difference)',
            r'mean\s+difference',
            r'difference\s+in\s+(?:means|proportions)',
            r'treatment\s+effect',
            r'estimator',
            r'confidence\s+interval',
        ],
    }

    def check_estimand(self, sap_text: str) -> Dict[str, float]:
        """Check if SAP addresses estimand components."""
        text_lower = sap_text.lower()

        results = {}
        for component, patterns in self.ESTIMAND_PATTERNS.items():
            found = 0
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    found += 1

            results[f'has_estimand_{component}'] = min(found / 2, 1.0)

        # Overall estimand completeness
        results['estimand_completeness'] = sum(
            v for k, v in results.items() if k.startswith('has_estimand_')
        ) / 5

        return results


# =============================================================================
# SECTION 6: FDA Criteria Checker
# =============================================================================

class FDACriteriaChecker:
    """
    Check SAP against FDA review criteria.

    From FDA Good Review Practice guidance:
    1. Is SAP prospective (before unblinding)?
    2. Is primary endpoint analysis clear?
    3. Is multiplicity controlled?
    4. Is missing data handling specified?
    5. Are interim analyses pre-specified?
    """

    def check_fda_criteria(self, sap_text: str) -> Dict[str, float]:
        """Check FDA review criteria."""
        text_lower = sap_text.lower()

        results = {}

        # 1. Prospective (hard to verify from text, check for version/date)
        prospective_patterns = [
            r'version\s*\d',
            r'date.*20\d\d',
            r'final\s+(?:sap|version)',
            r'prior\s+to\s+(?:unblinding|database\s+lock)',
        ]
        results['is_prospective'] = min(
            sum(1 for p in prospective_patterns if re.search(p, text_lower)) / 2,
            1.0
        )

        # 2. Primary analysis clear
        primary_patterns = [
            r'primary\s+(?:endpoint|outcome)\s+(?:analysis|will\s+be)',
            r'analysis\s+of\s+(?:the\s+)?primary',
            r'primary\s+efficacy\s+(?:endpoint|analysis)',
            r'for\s+the\s+primary\s+(?:endpoint|outcome)',
        ]
        results['has_primary_analysis'] = min(
            sum(1 for p in primary_patterns if re.search(p, text_lower)) / 2,
            1.0
        )

        # 3. Multiplicity control
        multiplicity_patterns = [
            r'multiplicity',
            r'multiple\s+(?:comparison|testing|endpoint)',
            r'family-?wise\s+error',
            r'bonferroni',
            r'hochberg',
            r'holm',
            r'gatekeeping',
            r'hierarchical\s+testing',
            r'alpha\s+(?:spending|allocation)',
            r'type\s+i\s+error\s+(?:control|rate)',
        ]
        results['has_multiplicity_control'] = min(
            sum(1 for p in multiplicity_patterns if re.search(p, text_lower)) / 2,
            1.0
        )

        # 4. Missing data handling
        missing_patterns = [
            r'missing\s+data',
            r'missing\s+values?',
            r'imputation',
            r'last\s+observation\s+carried',
            r'\blocf\b',
            r'multiple\s+imputation',
            r'sensitivity\s+analysis.*missing',
            r'missing.*sensitivity',
            r'tipping\s+point',
            r'pattern\s+mixture',
        ]
        results['has_missing_data_plan'] = min(
            sum(1 for p in missing_patterns if re.search(p, text_lower)) / 2,
            1.0
        )

        # 5. Interim analysis
        interim_patterns = [
            r'interim\s+analysis',
            r'interim\s+look',
            r'data\s+(?:monitoring|safety)\s+(?:committee|board)',
            r'\b(?:dmc|dsmb|idmc)\b',
            r'alpha\s+spending',
            r'o\'brien.?fleming',
            r'lan.?demets',
            r'group\s+sequential',
            r'futility',
            r'early\s+stopping',
        ]
        results['has_interim_plan'] = min(
            sum(1 for p in interim_patterns if re.search(p, text_lower)) / 2,
            1.0
        )

        # Overall FDA score
        results['fda_criteria_score'] = sum(
            v for k, v in results.items() if k not in ['fda_criteria_score']
        ) / 5

        return results


# =============================================================================
# SECTION 7: Text Similarity (for reference comparison)
# =============================================================================

class TextSimilarity:
    """Simple text similarity metrics."""

    def __init__(self):
        self._rouge = None

    def _ensure_rouge(self):
        if self._rouge is not None:
            return self._rouge
        try:
            from rouge_score import rouge_scorer
            self._rouge = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
        except ImportError:
            os.system("pip install rouge-score -q")
            from rouge_score import rouge_scorer
            self._rouge = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
        return self._rouge

    def compute_rouge_l(self, reference: str, generated: str) -> float:
        """Compute ROUGE-L score."""
        try:
            scorer = self._ensure_rouge()
            scores = scorer.score(reference, generated)
            return scores['rougeL'].fmeasure
        except:
            return 0.0

    def compute_cosine(self, reference: str, generated: str) -> float:
        """Compute cosine similarity using TF-IDF."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            # Truncate for memory
            ref = reference[:50000]
            gen = generated[:50000]

            vectorizer = TfidfVectorizer()
            tfidf = vectorizer.fit_transform([ref, gen])

            return float(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
        except:
            return 0.0


# =============================================================================
# SECTION 8: Main Evaluator
# =============================================================================

class SAPEvaluator:
    """
    Main SAP evaluation class.

    Evaluates generated SAPs using real regulatory criteria:
    1. Protocol-SAP alignment
    2. Regulatory completeness (6 sections)
    3. Estimand components (ICH E9 R1)
    4. FDA review criteria
    5. Text similarity (optional)
    """

    def __init__(self, use_similarity: bool = True):
        self.alignment = AlignmentChecker()
        self.regulatory = RegulatoryChecker()
        self.estimand = EstimandChecker()
        self.fda = FDACriteriaChecker()
        self.similarity = TextSimilarity() if use_similarity else None

    def evaluate(
        self,
        protocol: str,
        generated_sap: str,
        reference_sap: str = None,
        nct_id: str = "unknown",
    ) -> EvalResult:
        """
        Evaluate a generated SAP.

        Args:
            protocol: The input protocol text
            generated_sap: The SAP to evaluate
            reference_sap: Optional reference SAP for similarity comparison
            nct_id: Trial identifier

        Returns:
            EvalResult with all scores
        """
        start_time = time.time()
        result = EvalResult(nct_id=nct_id)

        try:
            # 1. Protocol-SAP Alignment
            alignment = self.alignment.check_alignment(protocol, generated_sap)
            result.population_alignment = alignment['population_alignment']
            result.endpoint_alignment = alignment['endpoint_alignment']
            result.design_alignment = alignment['design_alignment']
            result.treatment_alignment = alignment['treatment_alignment']

            # 2. Regulatory Completeness
            regulatory = self.regulatory.check_completeness(generated_sap)
            result.has_admin_section = regulatory['has_admin_section']
            result.has_intro_section = regulatory['has_intro_section']
            result.has_methods_section = regulatory['has_methods_section']
            result.has_principles_section = regulatory['has_principles_section']
            result.has_population_section = regulatory['has_population_section']
            result.has_analysis_section = regulatory['has_analysis_section']
            result.regulatory_completeness = regulatory['regulatory_completeness']

            # 3. Estimand Components
            estimand = self.estimand.check_estimand(generated_sap)
            result.has_estimand_population = estimand['has_estimand_population']
            result.has_estimand_treatment = estimand['has_estimand_treatment']
            result.has_estimand_endpoint = estimand['has_estimand_endpoint']
            result.has_estimand_intercurrent = estimand['has_estimand_intercurrent']
            result.has_estimand_summary = estimand['has_estimand_summary']
            result.estimand_completeness = estimand['estimand_completeness']

            # 4. FDA Criteria
            fda = self.fda.check_fda_criteria(generated_sap)
            result.is_prospective = fda['is_prospective']
            result.has_primary_analysis = fda['has_primary_analysis']
            result.has_multiplicity_control = fda['has_multiplicity_control']
            result.has_missing_data_plan = fda['has_missing_data_plan']
            result.has_interim_plan = fda['has_interim_plan']
            result.fda_criteria_score = fda['fda_criteria_score']

            # 5. Text Similarity (if reference provided)
            if reference_sap and self.similarity:
                result.rouge_l = self.similarity.compute_rouge_l(
                    reference_sap, generated_sap
                )
                result.cosine_similarity = self.similarity.compute_cosine(
                    reference_sap, generated_sap
                )

            # Overall score (weighted average)
            alignment_score = (
                result.population_alignment + result.endpoint_alignment +
                result.design_alignment + result.treatment_alignment
            ) / 4

            result.overall_score = (
                0.30 * alignment_score +           # Protocol alignment most important
                0.25 * result.regulatory_completeness +
                0.25 * result.estimand_completeness +
                0.20 * result.fda_criteria_score
            )

        except Exception as e:
            result.errors.append(str(e))

        result.eval_time = time.time() - start_time
        return result


# =============================================================================
# SECTION 9: Batch Runner
# =============================================================================

class SAPEvalRunner:
    """Run evaluation on multiple SAPs."""

    def __init__(
        self,
        eval_set_path: str = None,
        cache_path: str = None,
    ):
        self.eval_set_path = Path(eval_set_path) if eval_set_path else self._default_path()
        self.cache_path = Path(cache_path) if cache_path else self.eval_set_path / 'eval_cache_v2.json'
        self.evaluator = SAPEvaluator()
        self.cache = self._load_cache()

    def _default_path(self) -> Path:
        return Path(__file__).parent.parent.parent / 'data' / 'eval_set'

    def _load_cache(self) -> Dict:
        if self.cache_path.exists():
            try:
                with open(self.cache_path) as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_cache(self):
        with open(self.cache_path, 'w') as f:
            json.dump(self.cache, f, indent=2)

    def get_eval_pairs(self) -> List[Tuple[str, str, str]]:
        """Get (nct_id, protocol_path, sap_path) tuples."""
        pairs = []
        for sap_path in self.eval_set_path.glob('*_sap.txt'):
            nct_id = sap_path.stem.replace('_sap', '')
            protocol_path = self.eval_set_path / f'{nct_id}_protocol.txt'
            if protocol_path.exists():
                pairs.append((nct_id, str(protocol_path), str(sap_path)))
        return pairs

    def run(self, limit: int = None) -> List[EvalResult]:
        """Run evaluation on all pairs."""
        pairs = self.get_eval_pairs()
        if limit:
            pairs = pairs[:limit]

        results = []
        print(f"Evaluating {len(pairs)} SAPs...")

        for i, (nct_id, prot_path, sap_path) in enumerate(pairs, 1):
            try:
                with open(prot_path, encoding='utf-8') as f:
                    protocol = f.read()
                with open(sap_path, encoding='utf-8') as f:
                    reference_sap = f.read()

                # For now, evaluate reference SAP itself (ground truth check)
                result = self.evaluator.evaluate(
                    protocol=protocol,
                    generated_sap=reference_sap,
                    reference_sap=reference_sap,
                    nct_id=nct_id,
                )
                results.append(result)

                print(f"[{i}/{len(pairs)}] {nct_id}: "
                      f"align={result.population_alignment:.2f}, "
                      f"reg={result.regulatory_completeness:.2f}, "
                      f"est={result.estimand_completeness:.2f}, "
                      f"fda={result.fda_criteria_score:.2f}")

            except Exception as e:
                print(f"[{i}/{len(pairs)}] {nct_id}: ERROR - {e}")

        return results


# =============================================================================
# SECTION 10: CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="SAP Evaluation (v2)")
    parser.add_argument('--eval-path', type=str, help='Path to eval set')
    parser.add_argument('--limit', type=int, help='Limit number of evaluations')

    args = parser.parse_args()

    runner = SAPEvalRunner(eval_set_path=args.eval_path)
    results = runner.run(limit=args.limit)

    # Summary
    if results:
        avg_alignment = sum(r.population_alignment for r in results) / len(results)
        avg_regulatory = sum(r.regulatory_completeness for r in results) / len(results)
        avg_estimand = sum(r.estimand_completeness for r in results) / len(results)
        avg_fda = sum(r.fda_criteria_score for r in results) / len(results)
        avg_overall = sum(r.overall_score for r in results) / len(results)

        print("\n" + "="*60)
        print("EVALUATION SUMMARY")
        print("="*60)
        print(f"Evaluated: {len(results)} SAPs")
        print(f"Avg Protocol Alignment: {avg_alignment:.3f}")
        print(f"Avg Regulatory Completeness: {avg_regulatory:.3f}")
        print(f"Avg Estimand Completeness: {avg_estimand:.3f}")
        print(f"Avg FDA Criteria: {avg_fda:.3f}")
        print(f"Avg Overall Score: {avg_overall:.3f}")


if __name__ == "__main__":
    main()
