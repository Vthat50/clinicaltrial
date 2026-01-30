#!/usr/bin/env python3
"""
Production-Grade Study Design Classifier
=========================================

Comprehensive study design classification that goes beyond keyword matching.

Features:
1. Multi-signal detection (keywords, structure, semantics)
2. Proper study design taxonomy (not just binary)
3. Confidence scores with human review flags
4. Protocol structure parsing
5. Evidence-based classification with reasoning

Study Design Taxonomy:
- PHASE3_RCT: Phase III randomized controlled trial (comparative, inferential)
- PHASE3_SINGLE_ARM: Rare, usually accelerated approval (descriptive + historical)
- PHASE2_RCT: Phase II randomized (signal-finding, limited inference)
- PHASE2_SINGLE_ARM: Phase II single-arm (descriptive, binomial CI)
- PHASE2_SIMON: Simon's two-stage design (specific stopping rules)
- PHASE1_DOSE_FINDING: Phase I dose escalation (3+3, CRM, etc.)
- PILOT_FEASIBILITY: Exploratory/feasibility (no hypothesis testing)
- BASKET_UMBRELLA: Master protocols (complex multiplicity)
- PLATFORM_ADAPTIVE: Adaptive platform trials
- NEOADJUVANT: Pre-surgical treatment (time from surgery)
- ADJUVANT: Post-surgical treatment (time from surgery)
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


class StudyDesignType(Enum):
    """Comprehensive study design taxonomy."""
    # Phase III
    PHASE3_RCT = "phase3_rct"
    PHASE3_SINGLE_ARM = "phase3_single_arm"  # Rare, accelerated approval

    # Phase II
    PHASE2_RCT = "phase2_rct"  # Randomized Phase II
    PHASE2_SINGLE_ARM = "phase2_single_arm"
    PHASE2_SIMON = "phase2_simon"  # Simon's two-stage
    PHASE2_RANDOMIZED_DISCONTINUATION = "phase2_rdd"

    # Phase I
    PHASE1_DOSE_FINDING = "phase1_dose"
    PHASE1_EXPANSION = "phase1_expansion"

    # Special designs
    PILOT_FEASIBILITY = "pilot"
    BASKET_TRIAL = "basket"
    UMBRELLA_TRIAL = "umbrella"
    PLATFORM_ADAPTIVE = "platform"

    # By setting
    NEOADJUVANT = "neoadjuvant"
    ADJUVANT = "adjuvant"

    # Fallback
    UNKNOWN = "unknown"


class StatisticalApproach(Enum):
    """Statistical approach based on study design."""
    INFERENTIAL_COMPARATIVE = "inferential_comparative"  # Log-rank, Cox, etc.
    INFERENTIAL_HISTORICAL = "inferential_historical"  # vs historical control
    DESCRIPTIVE_ONLY = "descriptive_only"  # KM curves, binomial CI
    BAYESIAN_ADAPTIVE = "bayesian_adaptive"  # Bayesian methods
    SIMON_TWO_STAGE = "simon_two_stage"  # Specific stopping rules
    DOSE_RESPONSE = "dose_response"  # 3+3, CRM, BOIN


@dataclass
class DetectionEvidence:
    """Evidence for classification decision."""
    signal_name: str
    signal_value: Any
    confidence: float  # 0-1
    source: str  # "keyword", "structure", "semantic", "extracted"


@dataclass
class StudyDesignResult:
    """Complete study design classification result."""
    # Primary classification
    design_type: StudyDesignType
    statistical_approach: StatisticalApproach
    confidence: float  # 0-1 overall confidence

    # Design characteristics
    phase: int  # 1, 2, 3, 4
    is_randomized: bool
    is_controlled: bool  # Has comparator arm
    is_blinded: bool
    num_arms: int

    # Setting
    treatment_setting: str  # "neoadjuvant", "adjuvant", "metastatic", "maintenance"
    time_origin: str  # "randomization", "surgery", "enrollment"

    # Special characteristics
    is_pilot: bool
    is_adaptive: bool
    has_interim_analysis: bool

    # Evidence trail
    evidence: List[DetectionEvidence] = field(default_factory=list)

    # Human review
    requires_review: bool = False
    review_reasons: List[str] = field(default_factory=list)

    # Constraints for SAP generation
    forbidden_methods: List[str] = field(default_factory=list)
    required_methods: List[str] = field(default_factory=list)

    def get_statistical_constraints(self) -> Dict[str, Any]:
        """Get SAP-relevant constraints based on classification."""
        if self.statistical_approach == StatisticalApproach.DESCRIPTIVE_ONLY:
            return {
                'primary_test': 'Descriptive statistics only',
                'forbidden': ['log-rank test', 'Cox regression', 'Fleming-Harrington',
                             'hazard ratio', 'RPSFT', 'IPCW'],
                'required': ['Kaplan-Meier curves', 'Median with 95% CI',
                            'Response rate with exact binomial CI'],
                'sample_size_approach': 'No formal power calculation',
                'interim_analysis': False
            }
        elif self.statistical_approach == StatisticalApproach.INFERENTIAL_COMPARATIVE:
            return {
                'primary_test': 'Comparative hypothesis testing',
                'forbidden': [],
                'required': ['Primary hypothesis test', 'Effect size with CI'],
                'sample_size_approach': 'Power-based calculation',
                'interim_analysis': self.has_interim_analysis
            }
        elif self.statistical_approach == StatisticalApproach.SIMON_TWO_STAGE:
            return {
                'primary_test': "Simon's two-stage design",
                'forbidden': ['log-rank test', 'Cox regression'],
                'required': ['Stage 1 stopping rule', 'Stage 2 analysis',
                            'Response rate with exact CI'],
                'sample_size_approach': "Simon's optimal/minimax",
                'interim_analysis': True  # Built into design
            }
        else:
            return {
                'primary_test': 'To be determined',
                'forbidden': [],
                'required': [],
                'sample_size_approach': 'Per protocol',
                'interim_analysis': self.has_interim_analysis
            }


class StudyDesignClassifier:
    """
    Production-grade study design classifier.

    Uses multiple signals:
    1. Keyword patterns (weighted)
    2. Protocol structure analysis
    3. Extracted facts validation
    4. Cross-signal consistency checks
    """

    # ==========================================================================
    # SIGNAL PATTERNS (weighted by reliability)
    # ==========================================================================

    # High confidence keywords (explicit statements)
    HIGH_CONFIDENCE_PATTERNS = {
        'single_arm': [
            (r'\bsingle[- ]?arm\b', 0.95),
            (r'\bone[- ]?arm\b', 0.90),
            (r'\bnon[- ]?randomized\b', 0.85),
            (r'\buncontrolled\b', 0.80),
            (r'\bopen[- ]?label[,\s]+single[- ]?arm\b', 0.95),
            (r'\ball patients (?:will )?receive\b', 0.70),
        ],
        'randomized': [
            (r'\brandomized\b', 0.90),
            (r'\brandomised\b', 0.90),
            (r'\brandom allocation\b', 0.95),
            (r'\b\d+:\d+(?::\d+)?\s*(?:randomization|allocation)\b', 0.95),
        ],
        'controlled': [
            (r'\bplacebo[- ]?controlled\b', 0.95),
            (r'\bactive[- ]?controlled\b', 0.90),
            (r'\bcomparator\s+arm\b', 0.90),
            (r'\bcontrol\s+arm\b', 0.85),
            (r'\bversus\b', 0.70),
            (r'\b(?:compared|comparison)\s+(?:to|with)\b', 0.75),
        ],
        'pilot': [
            (r'\bpilot\s+study\b', 0.95),
            (r'\bfeasibility\s+study\b', 0.95),
            (r'\bexploratory\s+study\b', 0.85),
            (r'\bproof[- ]?of[- ]?concept\b', 0.90),
            (r'\bno\s+formal\s+(?:sample\s+size|power)\b', 0.90),
        ],
        'neoadjuvant': [
            (r'\bneoadjuvant\b', 0.95),
            (r'\bneo[- ]?adjuvant\b', 0.95),
            (r'\bpre[- ]?surgical\b', 0.85),
            (r'\bpre[- ]?operative\b', 0.85),
            (r'\bbefore\s+surgery\b', 0.80),
        ],
        'adjuvant': [
            (r'\badjuvant\b', 0.85),  # Lower because "neoadjuvant" contains it
            (r'\bpost[- ]?surgical\b', 0.90),
            (r'\bpost[- ]?operative\b', 0.90),
            (r'\bafter\s+surgery\b', 0.85),
        ],
        'simon_two_stage': [
            (r'\bsimon(?:\'s)?\s+(?:two[- ]?stage|optimal|minimax)\b', 0.98),
            (r'\btwo[- ]?stage\s+design\b', 0.85),
            (r'\bstage\s+1.*?stage\s+2\b', 0.75),
        ],
        'adaptive': [
            (r'\badaptive\s+design\b', 0.95),
            (r'\bplatform\s+trial\b', 0.95),
            (r'\bmaster\s+protocol\b', 0.90),
            (r'\bbasket\s+trial\b', 0.95),
            (r'\bumbrella\s+trial\b', 0.95),
        ],
        'no_hypothesis_testing': [
            (r'\bno\s+(?:formal\s+)?statistical\s+test(?:s|ing)?\b', 0.95),
            (r'\bdescriptive\s+(?:statistics|analysis)\s+only\b', 0.95),
            (r'\bno\s+hypothesis\s+test(?:s|ing)?\b', 0.95),
            (r'\bno\s+formal\s+sample\s+size\b', 0.90),
        ],
    }

    # Phase detection patterns
    PHASE_PATTERNS = [
        (r'\bphase\s*(?:1|i)\b(?!\s*(?:2|ii|3|iii))', 1, 0.95),
        (r'\bphase\s*(?:1|i)\s*/\s*(?:2|ii)\b', 1, 0.90),  # Phase 1/2
        (r'\bphase\s*(?:2|ii)\b(?!\s*(?:3|iii))', 2, 0.95),
        (r'\bphase\s*(?:2|ii)\s*/\s*(?:3|iii)\b', 2, 0.90),  # Phase 2/3
        (r'\bphase\s*(?:3|iii)\b', 3, 0.95),
        (r'\bphase\s*(?:4|iv)\b', 4, 0.95),
        (r'\bpivotal\s+(?:study|trial)\b', 3, 0.80),  # Pivotal usually Phase 3
        (r'\bregistration\s+(?:study|trial)\b', 3, 0.80),
    ]

    # Structure patterns (look for sections/headers)
    STRUCTURE_PATTERNS = {
        'has_comparator_section': [
            r'(?:^|\n)\s*(?:\d+\.?\s*)?(?:comparator|control)\s*(?:arm|group|treatment)',
            r'(?:^|\n)\s*(?:\d+\.?\s*)?(?:arm\s*(?:2|b|ii)|treatment\s*(?:2|b|ii))',
        ],
        'has_randomization_section': [
            r'(?:^|\n)\s*(?:\d+\.?\s*)?randomization\s*(?:scheme|procedure|method)',
            r'(?:^|\n)\s*(?:\d+\.?\s*)?stratification\s*factors?',
        ],
        'has_sample_size_section': [
            r'(?:^|\n)\s*(?:\d+\.?\s*)?sample\s*size\s*(?:determination|calculation|justification)',
            r'(?:^|\n)\s*(?:\d+\.?\s*)?power\s*(?:analysis|calculation)',
        ],
        'has_interim_section': [
            r'(?:^|\n)\s*(?:\d+\.?\s*)?interim\s*analysis',
            r'(?:^|\n)\s*(?:\d+\.?\s*)?data\s*(?:safety\s*)?monitoring',
        ],
    }

    def __init__(self):
        """Initialize classifier."""
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self.compiled_high_conf = {}
        for category, patterns in self.HIGH_CONFIDENCE_PATTERNS.items():
            self.compiled_high_conf[category] = [
                (re.compile(p, re.IGNORECASE), conf)
                for p, conf in patterns
            ]

        self.compiled_phase = [
            (re.compile(p, re.IGNORECASE), phase, conf)
            for p, phase, conf in self.PHASE_PATTERNS
        ]

        self.compiled_structure = {}
        for category, patterns in self.STRUCTURE_PATTERNS.items():
            self.compiled_structure[category] = [
                re.compile(p, re.IGNORECASE | re.MULTILINE)
                for p in patterns
            ]

    def classify(
        self,
        protocol_text: str,
        extracted_facts: Optional[Dict[str, Any]] = None
    ) -> StudyDesignResult:
        """
        Classify study design using multiple signals.

        Args:
            protocol_text: Full protocol text
            extracted_facts: Optional pre-extracted facts dict

        Returns:
            StudyDesignResult with classification and confidence
        """
        evidence = []
        review_reasons = []

        # =======================================================================
        # SIGNAL 1: Keyword Pattern Matching
        # =======================================================================
        keyword_signals = self._detect_keywords(protocol_text, evidence)

        # =======================================================================
        # SIGNAL 2: Protocol Structure Analysis
        # =======================================================================
        structure_signals = self._detect_structure(protocol_text, evidence)

        # =======================================================================
        # SIGNAL 3: Extracted Facts Validation
        # =======================================================================
        if extracted_facts:
            facts_signals = self._validate_extracted_facts(extracted_facts, evidence)
        else:
            facts_signals = {}

        # =======================================================================
        # SIGNAL 4: Phase Detection
        # =======================================================================
        phase, phase_confidence = self._detect_phase(protocol_text, evidence)

        # =======================================================================
        # CROSS-SIGNAL CONSISTENCY & CLASSIFICATION
        # =======================================================================
        result = self._resolve_classification(
            keyword_signals, structure_signals, facts_signals,
            phase, phase_confidence, evidence, review_reasons
        )

        return result

    def _detect_keywords(
        self,
        text: str,
        evidence: List[DetectionEvidence]
    ) -> Dict[str, Tuple[bool, float]]:
        """Detect design signals from keywords."""
        signals = {}

        for category, patterns in self.compiled_high_conf.items():
            max_confidence = 0.0
            matched = False

            for pattern, base_conf in patterns:
                if pattern.search(text):
                    matched = True
                    max_confidence = max(max_confidence, base_conf)
                    evidence.append(DetectionEvidence(
                        signal_name=category,
                        signal_value=True,
                        confidence=base_conf,
                        source="keyword"
                    ))

            signals[category] = (matched, max_confidence)

        return signals

    def _detect_structure(
        self,
        text: str,
        evidence: List[DetectionEvidence]
    ) -> Dict[str, bool]:
        """Detect structural elements in protocol."""
        signals = {}

        for category, patterns in self.compiled_structure.items():
            found = any(p.search(text) for p in patterns)
            signals[category] = found

            if found:
                evidence.append(DetectionEvidence(
                    signal_name=category,
                    signal_value=True,
                    confidence=0.85,
                    source="structure"
                ))

        return signals

    def _validate_extracted_facts(
        self,
        facts: Dict[str, Any],
        evidence: List[DetectionEvidence]
    ) -> Dict[str, Any]:
        """Validate and use pre-extracted facts."""
        signals = {}

        # Number of arms
        num_arms = facts.get('num_arms', 0)
        if num_arms > 0:
            signals['num_arms'] = num_arms
            evidence.append(DetectionEvidence(
                signal_name='num_arms',
                signal_value=num_arms,
                confidence=0.90,
                source="extracted"
            ))

        # Randomization ratio
        ratio = facts.get('randomization_ratio', '')
        if ratio and ':' in str(ratio):
            signals['has_randomization'] = True
            evidence.append(DetectionEvidence(
                signal_name='randomization_ratio',
                signal_value=ratio,
                confidence=0.95,
                source="extracted"
            ))

        # Sample size
        n = facts.get('sample_size', 0)
        if n > 0:
            signals['sample_size'] = n
            evidence.append(DetectionEvidence(
                signal_name='sample_size',
                signal_value=n,
                confidence=0.90,
                source="extracted"
            ))

        # Comparator
        if facts.get('comparator'):
            signals['has_comparator'] = True
            evidence.append(DetectionEvidence(
                signal_name='comparator',
                signal_value=facts['comparator'],
                confidence=0.95,
                source="extracted"
            ))

        return signals

    def _detect_phase(
        self,
        text: str,
        evidence: List[DetectionEvidence]
    ) -> Tuple[int, float]:
        """Detect study phase."""
        best_phase = 3  # Default
        best_confidence = 0.5

        for pattern, phase, conf in self.compiled_phase:
            if pattern.search(text):
                if conf > best_confidence:
                    best_phase = phase
                    best_confidence = conf

        evidence.append(DetectionEvidence(
            signal_name='phase',
            signal_value=best_phase,
            confidence=best_confidence,
            source="keyword"
        ))

        return best_phase, best_confidence

    def _resolve_classification(
        self,
        keyword_signals: Dict[str, Tuple[bool, float]],
        structure_signals: Dict[str, bool],
        facts_signals: Dict[str, Any],
        phase: int,
        phase_confidence: float,
        evidence: List[DetectionEvidence],
        review_reasons: List[str]
    ) -> StudyDesignResult:
        """Resolve final classification from all signals."""

        # =======================================================================
        # STEP 1: Determine if randomized/controlled
        # =======================================================================
        is_single_arm, single_arm_conf = keyword_signals.get('single_arm', (False, 0))
        is_randomized, rand_conf = keyword_signals.get('randomized', (False, 0))
        is_controlled, ctrl_conf = keyword_signals.get('controlled', (False, 0))

        # Cross-validate with structure
        has_comparator_section = structure_signals.get('has_comparator_section', False)
        has_randomization_section = structure_signals.get('has_randomization_section', False)

        # Cross-validate with extracted facts
        has_randomization_ratio = facts_signals.get('has_randomization', False)
        has_comparator_fact = facts_signals.get('has_comparator', False)
        num_arms = facts_signals.get('num_arms', 0)
        sample_size = facts_signals.get('sample_size', 0)

        # Resolve conflicts
        if is_single_arm and is_randomized:
            # Conflict! Single-arm can't be randomized
            review_reasons.append("Conflicting signals: both single-arm and randomized detected")
            # Trust structural evidence more
            if has_comparator_section or has_randomization_section or num_arms > 1:
                is_single_arm = False
            else:
                is_randomized = False

        # Final determination
        if not is_single_arm and not is_randomized:
            # Neither explicitly detected - use structural signals
            if has_comparator_section or has_randomization_section or num_arms > 1 or has_comparator_fact:
                is_randomized = True
                is_controlled = True
            elif sample_size > 0 and sample_size <= 100 and phase <= 2:
                # Small sample + early phase + no comparator = likely single-arm
                is_single_arm = True

        # =======================================================================
        # STEP 2: Determine special design types
        # =======================================================================
        is_pilot, pilot_conf = keyword_signals.get('pilot', (False, 0))
        is_neoadjuvant, neoadj_conf = keyword_signals.get('neoadjuvant', (False, 0))
        is_adjuvant, adj_conf = keyword_signals.get('adjuvant', (False, 0))
        is_simon, simon_conf = keyword_signals.get('simon_two_stage', (False, 0))
        is_adaptive, adaptive_conf = keyword_signals.get('adaptive', (False, 0))
        no_hypothesis, no_hyp_conf = keyword_signals.get('no_hypothesis_testing', (False, 0))

        has_interim = structure_signals.get('has_interim_section', False)

        # Determine treatment setting
        if is_neoadjuvant:
            treatment_setting = "neoadjuvant"
            time_origin = "surgery"
        elif is_adjuvant and not is_neoadjuvant:  # Exclude neoadjuvant false positive
            treatment_setting = "adjuvant"
            time_origin = "surgery"
        else:
            treatment_setting = "metastatic"
            time_origin = "randomization" if is_randomized else "enrollment"

        # =======================================================================
        # STEP 3: Classify design type and statistical approach
        # =======================================================================

        # Simon's two-stage (high confidence pattern)
        if is_simon and simon_conf > 0.8:
            design_type = StudyDesignType.PHASE2_SIMON
            statistical_approach = StatisticalApproach.SIMON_TWO_STAGE

        # Adaptive/Platform trials
        elif is_adaptive:
            design_type = StudyDesignType.PLATFORM_ADAPTIVE
            statistical_approach = StatisticalApproach.BAYESIAN_ADAPTIVE

        # Pilot/Feasibility
        elif is_pilot or (no_hypothesis and no_hyp_conf > 0.8):
            design_type = StudyDesignType.PILOT_FEASIBILITY
            statistical_approach = StatisticalApproach.DESCRIPTIVE_ONLY

        # Phase I
        elif phase == 1:
            design_type = StudyDesignType.PHASE1_DOSE_FINDING
            statistical_approach = StatisticalApproach.DOSE_RESPONSE

        # Phase II single-arm
        elif phase == 2 and (is_single_arm or not is_randomized):
            design_type = StudyDesignType.PHASE2_SINGLE_ARM
            statistical_approach = StatisticalApproach.DESCRIPTIVE_ONLY

        # Phase II randomized
        elif phase == 2 and is_randomized:
            design_type = StudyDesignType.PHASE2_RCT
            statistical_approach = StatisticalApproach.INFERENTIAL_COMPARATIVE

        # Phase III randomized
        elif phase == 3 and is_randomized:
            design_type = StudyDesignType.PHASE3_RCT
            statistical_approach = StatisticalApproach.INFERENTIAL_COMPARATIVE

        # Phase III single-arm (rare)
        elif phase == 3 and is_single_arm:
            design_type = StudyDesignType.PHASE3_SINGLE_ARM
            statistical_approach = StatisticalApproach.INFERENTIAL_HISTORICAL
            review_reasons.append("Phase III single-arm is unusual - verify design")

        # Default
        else:
            design_type = StudyDesignType.UNKNOWN
            statistical_approach = StatisticalApproach.DESCRIPTIVE_ONLY
            review_reasons.append("Could not confidently classify study design")

        # =======================================================================
        # STEP 4: Calculate overall confidence
        # =======================================================================
        confidences = [
            phase_confidence,
            single_arm_conf if is_single_arm else rand_conf,
            pilot_conf if is_pilot else 0.8,
        ]
        overall_confidence = sum(confidences) / len(confidences)

        # Lower confidence if there are review reasons
        if review_reasons:
            overall_confidence *= 0.8

        # =======================================================================
        # STEP 5: Determine forbidden/required methods
        # =======================================================================
        forbidden_methods = []
        required_methods = []

        if statistical_approach == StatisticalApproach.DESCRIPTIVE_ONLY:
            forbidden_methods = [
                'log-rank test', 'Cox regression', 'hazard ratio',
                'Fleming-Harrington', 'RPSFT', 'IPCW',
                'stratified analysis', 'treatment effect estimation'
            ]
            required_methods = [
                'Kaplan-Meier survival curves',
                'Median survival with 95% CI',
                'Response rate with exact binomial CI',
                'Descriptive statistics'
            ]

        # =======================================================================
        # STEP 6: Build result
        # =======================================================================
        requires_review = overall_confidence < 0.7 or len(review_reasons) > 0

        return StudyDesignResult(
            design_type=design_type,
            statistical_approach=statistical_approach,
            confidence=overall_confidence,
            phase=phase,
            is_randomized=is_randomized,
            is_controlled=is_controlled or has_comparator_fact,
            is_blinded=False,  # Would need additional detection
            num_arms=num_arms if num_arms > 0 else (1 if is_single_arm else 2),
            treatment_setting=treatment_setting,
            time_origin=time_origin,
            is_pilot=is_pilot,
            is_adaptive=is_adaptive,
            has_interim_analysis=has_interim,
            evidence=evidence,
            requires_review=requires_review,
            review_reasons=review_reasons,
            forbidden_methods=forbidden_methods,
            required_methods=required_methods
        )


def test_classifier():
    """Test the classifier with various protocol types."""
    classifier = StudyDesignClassifier()

    # Test 1: Phase III RCT (CheckMate-like)
    phase3_rct = """
    This is a Phase III, randomized, open-label study comparing nivolumab
    versus docetaxel in patients with advanced NSCLC. Patients will be
    randomized in a 2:1 ratio. An interim analysis is planned.
    """

    # Test 2: Phase II single-arm (NEOMUN-like)
    phase2_single = """
    NEOMUN is a Phase II, single-arm, open-label study evaluating
    neoadjuvant pembrolizumab in patients with resectable NSCLC.
    This is an exploratory pilot study with N=30 patients.
    No formal sample size estimation was performed.
    No statistical tests will be performed due to small sample size.
    """

    # Test 3: Edge case - uncontrolled but not explicitly "single-arm"
    edge_case = """
    This is a Phase II study where all patients receive treatment.
    There is no comparator arm. The study will enroll 40 patients.
    Efficacy will be assessed descriptively.
    """

    test_cases = [
        ("Phase III RCT", phase3_rct),
        ("Phase II Single-Arm", phase2_single),
        ("Edge Case (uncontrolled)", edge_case),
    ]

    for name, text in test_cases:
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print('='*60)

        result = classifier.classify(text)

        print(f"Design Type: {result.design_type.value}")
        print(f"Statistical Approach: {result.statistical_approach.value}")
        print(f"Confidence: {result.confidence:.2%}")
        print(f"Phase: {result.phase}")
        print(f"Randomized: {result.is_randomized}")
        print(f"Setting: {result.treatment_setting}")
        print(f"Time Origin: {result.time_origin}")
        print(f"Requires Review: {result.requires_review}")
        if result.review_reasons:
            print(f"Review Reasons: {result.review_reasons}")
        print(f"Forbidden Methods: {result.forbidden_methods[:3]}...")
        print(f"Required Methods: {result.required_methods[:3]}...")


if __name__ == "__main__":
    test_classifier()
