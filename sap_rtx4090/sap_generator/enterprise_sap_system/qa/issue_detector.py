#!/usr/bin/env python3
"""
Issue Detector for SAP Quality Assurance
=========================================

Month 3-4 Implementation: Detect common SAP quality issues

Severity Levels:
- ERROR (Critical): Must be fixed before SAP is acceptable
- WARNING: Should be addressed, may cause regulatory issues
- SUGGESTION: Best practice recommendations

Target: Reach 85-90% quality (Level 2.5)
"""

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any


class IssueSeverity(Enum):
    """Issue severity levels"""
    ERROR = "error"           # Critical - must fix
    WARNING = "warning"       # Important - should fix
    SUGGESTION = "suggestion" # Best practice


@dataclass
class Issue:
    """Represents a detected issue in the SAP"""
    severity: IssueSeverity
    section: str
    rule_id: str
    message: str
    suggestion: str
    context: Optional[str] = None  # Relevant text from SAP

    def __str__(self) -> str:
        icons = {
            IssueSeverity.ERROR: "❌",
            IssueSeverity.WARNING: "⚠️",
            IssueSeverity.SUGGESTION: "💡"
        }
        return f"{icons[self.severity]} [{self.section}] {self.message}"


@dataclass
class DetectionResult:
    """Result of issue detection"""
    issues: List[Issue] = field(default_factory=list)
    score: float = 100.0  # Quality score (100 = perfect)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)

    @property
    def suggestion_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.SUGGESTION)

    def calculate_score(self) -> float:
        """Calculate quality score based on issues found"""
        # Deductions: Error=-10, Warning=-3, Suggestion=-1
        deductions = (
            self.error_count * 10 +
            self.warning_count * 3 +
            self.suggestion_count * 1
        )
        self.score = max(0, 100 - deductions)
        return self.score


class IssueDetector:
    """
    Detect common SAP quality issues

    Usage:
        detector = IssueDetector()
        result = detector.detect(protocol_facts, sap_sections)

        for issue in result.issues:
            print(issue)

        print(f"Quality Score: {result.score}%")
    """

    # TTE endpoint keywords
    TTE_KEYWORDS = ['survival', 'pfs', 'efs', 'dfs', 'rfs', 'ttp', 'dor',
                    'time to', 'duration of', 'progression-free', 'event-free']

    # Binary endpoint keywords
    BINARY_KEYWORDS = ['response', 'remission', 'responder', 'orr', 'cr', 'pr',
                       'acr20', 'acr50', 'pasi75', 'pasi90']

    # Continuous endpoint keywords
    CONTINUOUS_KEYWORDS = ['change from baseline', 'cfb', 'mean change',
                           'mmrm', 'ancova', 'mixed model']

    def __init__(self):
        self.rules = self._build_rules()

    def _build_rules(self) -> List[Dict]:
        """Build detection rules"""
        return [
            # === CRITICAL ERRORS ===
            {
                'id': 'TTE_NO_CENSORING',
                'severity': IssueSeverity.ERROR,
                'section': 'statistical_methods',
                'check': self._check_tte_censoring,
                'message': 'Time-to-event endpoint but no censoring rules specified',
                'suggestion': 'Add censoring rules for: alive at cutoff, lost to follow-up, subsequent therapy'
            },
            {
                'id': 'STRAT_DESIGN_NOT_ANALYSIS',
                'severity': IssueSeverity.ERROR,
                'section': 'statistical_methods',
                'check': self._check_stratification_consistency,
                'message': 'Stratification factors in design but not in analysis model',
                'suggestion': 'Include stratification factors as covariates in Cox/logistic model'
            },
            {
                'id': 'ENDPOINT_METHOD_MISMATCH',
                'severity': IssueSeverity.ERROR,
                'section': 'statistical_methods',
                'check': self._check_endpoint_method_match,
                'message': 'Primary endpoint type does not match analysis method',
                'suggestion': 'Use appropriate method: TTE→Cox/KM, Binary→Logistic, Continuous→MMRM/ANCOVA'
            },
            {
                'id': 'SAMPLE_SIZE_POWER_MISMATCH',
                'severity': IssueSeverity.ERROR,
                'section': 'sample_size',
                'check': self._check_sample_size_power,
                'message': 'Sample size does not match stated power calculation',
                'suggestion': 'Verify sample size formula and recalculate if needed'
            },

            # === WARNINGS ===
            {
                'id': 'IMMUNOTHERAPY_NO_IRECIST',
                'severity': IssueSeverity.WARNING,
                'section': 'endpoints',
                'check': self._check_immunotherapy_recist,
                'message': 'Immunotherapy trial without iRECIST/imRECIST mention',
                'suggestion': 'Consider using iRECIST criteria for tumor response assessment'
            },
            {
                'id': 'RESPONSE_NO_CONFIRMATION',
                'severity': IssueSeverity.WARNING,
                'section': 'endpoints',
                'check': self._check_response_confirmation,
                'message': 'Response endpoint without confirmation requirement',
                'suggestion': 'Specify confirmation timing (e.g., response confirmed ≥4 weeks later)'
            },
            {
                'id': 'CROSSOVER_NO_ANALYSIS',
                'severity': IssueSeverity.WARNING,
                'section': 'statistical_methods',
                'check': self._check_crossover_analysis,
                'message': 'Crossover design without crossover-adjusted analysis',
                'suggestion': 'Consider RPSFT or IPCW methods for crossover adjustment'
            },
            {
                'id': 'RARE_DISEASE_NO_SMALL_SAMPLE',
                'severity': IssueSeverity.WARNING,
                'section': 'statistical_methods',
                'check': self._check_rare_disease_methods,
                'message': 'Rare disease/small sample without appropriate methods',
                'suggestion': 'Consider exact methods, Bayesian approaches, or adaptive designs'
            },
            {
                'id': 'MULTIPLE_ENDPOINTS_NO_ADJUSTMENT',
                'severity': IssueSeverity.WARNING,
                'section': 'statistical_methods',
                'check': self._check_multiplicity_adjustment,
                'message': 'Multiple primary/key secondary endpoints without multiplicity adjustment',
                'suggestion': 'Specify alpha allocation strategy (Hochberg, Holm, hierarchical testing)'
            },

            # === INTERIM ANALYSIS CHECKS (NEW) ===
            {
                'id': 'INTERIM_NO_COUNT',
                'severity': IssueSeverity.ERROR,
                'section': 'interim_analysis',
                'check': self._check_interim_count,
                'message': 'Interim analysis mentioned but count not specified',
                'suggestion': 'Specify exact number of interim analyses (e.g., "3 IAs + 1 FA")'
            },
            {
                'id': 'INTERIM_NO_TIMING',
                'severity': IssueSeverity.ERROR,
                'section': 'interim_analysis',
                'check': self._check_interim_timing,
                'message': 'Interim analysis without timing/event counts specified',
                'suggestion': 'Specify timing for each IA (e.g., "IA1 at ~27 months, ~354 PFS events")'
            },
            {
                'id': 'INTERIM_NO_ALPHA_SPENDING',
                'severity': IssueSeverity.ERROR,
                'section': 'interim_analysis',
                'check': self._check_alpha_spending,
                'message': 'Interim analysis without alpha spending function specified',
                'suggestion': 'Specify alpha spending function (e.g., "Lan-DeMets O\'Brien-Fleming")'
            },
            {
                'id': 'INTERIM_NO_BOUNDARIES',
                'severity': IssueSeverity.WARNING,
                'section': 'interim_analysis',
                'check': self._check_efficacy_boundaries,
                'message': 'Interim analysis without efficacy boundaries specified',
                'suggestion': 'Include boundary table with Z-scores, p-values, and HR at boundary for each IA'
            },
            {
                'id': 'POWER_CALC_INCOMPLETE',
                'severity': IssueSeverity.WARNING,
                'section': 'sample_size',
                'check': self._check_power_calculation_detail,
                'message': 'Power calculation missing key assumptions',
                'suggestion': 'Include control median, assumed HR, power percentage for each endpoint'
            },
            {
                'id': 'CENSORING_RULES_MISSING',
                'severity': IssueSeverity.WARNING,
                'section': 'statistical_methods',
                'check': self._check_censoring_detail,
                'message': 'Time-to-event endpoint without detailed censoring rules',
                'suggestion': 'Include censoring rules table for PFS, OS, DOR with each scenario'
            },
            {
                'id': 'PRO_THRESHOLDS_MISSING',
                'severity': IssueSeverity.WARNING,
                'section': 'endpoints',
                'check': self._check_pro_thresholds,
                'message': 'PRO endpoints without analysis thresholds specified',
                'suggestion': 'Include PRO primary timepoint, completion threshold, MCID definition'
            },

            # === SUGGESTIONS ===
            {
                'id': 'NO_SENSITIVITY_MISSING_DATA',
                'severity': IssueSeverity.SUGGESTION,
                'section': 'missing_data',
                'check': self._check_sensitivity_analysis,
                'message': 'Consider sensitivity analysis for missing data assumptions',
                'suggestion': 'Add tipping point analysis or pattern mixture models per ICH E9(R1)'
            },
            {
                'id': 'FDA_GUIDANCE_AVAILABLE',
                'severity': IssueSeverity.SUGGESTION,
                'section': 'statistical_methods',
                'check': self._check_fda_guidance,
                'message': 'FDA guidance available for this indication',
                'suggestion': 'Review relevant FDA guidance document for endpoint/method recommendations'
            },
            {
                'id': 'SUBGROUP_NO_INTERACTION',
                'severity': IssueSeverity.SUGGESTION,
                'section': 'statistical_methods',
                'check': self._check_subgroup_interaction,
                'message': 'Subgroup analysis planned without interaction test',
                'suggestion': 'Include treatment×subgroup interaction test for pre-specified subgroups'
            },
        ]

    def detect(self, protocol_facts: Any, sap_sections: Dict[str, str]) -> DetectionResult:
        """
        Detect issues in generated SAP

        Args:
            protocol_facts: Extracted protocol facts (FullProtocolFacts)
            sap_sections: Dictionary of generated SAP sections

        Returns:
            DetectionResult with list of issues and quality score
        """
        result = DetectionResult()

        for rule in self.rules:
            try:
                issue = rule['check'](protocol_facts, sap_sections, rule)
                if issue:
                    result.issues.append(issue)
            except Exception as e:
                # Log but don't fail on individual rule errors
                print(f"[QA] Warning: Rule {rule['id']} failed: {e}")

        result.calculate_score()
        return result

    # === CRITICAL ERROR CHECKS ===

    def _check_tte_censoring(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: TTE endpoint must have censoring rules"""
        endpoint = getattr(facts, 'primary_endpoint', '') or ''
        endpoint_lower = endpoint.lower()

        # Is it a TTE endpoint?
        is_tte = any(kw in endpoint_lower for kw in self.TTE_KEYWORDS)
        if not is_tte:
            return None

        # Check for censoring rules
        methods = sections.get('7_statistical_methods', '') + sections.get('5_endpoints', '')
        has_censoring = 'censoring' in methods.lower() or 'censored' in methods.lower()

        if not has_censoring:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=rule['message'],
                suggestion=rule['suggestion'],
                context=f"Endpoint: {endpoint}"
            )
        return None

    def _check_stratification_consistency(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Stratification factors in design must appear in analysis"""
        strat_factors = getattr(facts, 'stratification_factors', []) or []
        if not strat_factors:
            return None

        methods = sections.get('7_statistical_methods', '').lower()
        design = sections.get('3_study_design', '').lower()

        # Check if stratification mentioned in design but not methods
        strat_in_design = 'stratif' in design
        strat_in_analysis = 'stratif' in methods or 'covariate' in methods

        if strat_in_design and not strat_in_analysis:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=f"{rule['message']}: {strat_factors}",
                suggestion=rule['suggestion'],
                context=f"Factors: {', '.join(strat_factors)}"
            )
        return None

    def _check_endpoint_method_match(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Endpoint type must match analysis method"""
        endpoint = getattr(facts, 'primary_endpoint', '') or ''
        endpoint_lower = endpoint.lower()
        methods = sections.get('7_statistical_methods', '').lower()

        # Determine endpoint type
        is_tte = any(kw in endpoint_lower for kw in self.TTE_KEYWORDS)
        is_binary = any(kw in endpoint_lower for kw in self.BINARY_KEYWORDS)
        is_continuous = any(kw in endpoint_lower for kw in self.CONTINUOUS_KEYWORDS)

        # Check appropriate method
        if is_tte:
            correct_method = any(m in methods for m in ['kaplan', 'cox', 'log-rank', 'survival'])
            if not correct_method:
                return Issue(
                    severity=rule['severity'],
                    section=rule['section'],
                    rule_id=rule['id'],
                    message=f"TTE endpoint ({endpoint}) but no survival analysis method",
                    suggestion="Use Kaplan-Meier, Cox proportional hazards, or log-rank test"
                )

        elif is_binary:
            correct_method = any(m in methods for m in ['logistic', 'chi-square', 'fisher', 'cmh', 'cochran'])
            if not correct_method:
                return Issue(
                    severity=rule['severity'],
                    section=rule['section'],
                    rule_id=rule['id'],
                    message=f"Binary endpoint ({endpoint}) but no appropriate method",
                    suggestion="Use logistic regression, CMH test, or Fisher's exact test"
                )

        elif is_continuous:
            correct_method = any(m in methods for m in ['mmrm', 'ancova', 'mixed model', 'anova', 't-test'])
            if not correct_method:
                return Issue(
                    severity=rule['severity'],
                    section=rule['section'],
                    rule_id=rule['id'],
                    message=f"Continuous endpoint ({endpoint}) but no appropriate method",
                    suggestion="Use MMRM, ANCOVA, or mixed model repeated measures"
                )

        return None

    def _check_sample_size_power(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Sample size should match power calculation"""
        # TODO: Implement detailed power verification
        # This requires parsing the sample size section and verifying calculations
        return None

    # === WARNING CHECKS ===

    def _check_immunotherapy_recist(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Immunotherapy trials should mention iRECIST"""
        # Check for immunotherapy indicators
        protocol_text = str(facts.__dict__).lower()
        drug_name = getattr(facts, 'drug_name', '') or ''

        is_immunotherapy = any(kw in protocol_text or kw in drug_name.lower()
                               for kw in ['immuno', 'checkpoint', 'pd-1', 'pd-l1', 'ctla-4',
                                          'pembrolizumab', 'nivolumab', 'atezolizumab', 'durvalumab',
                                          'ipilimumab', 'avelumab'])

        if not is_immunotherapy:
            return None

        endpoints = sections.get('5_endpoints', '').lower()
        has_irecist = any(term in endpoints for term in ['irecist', 'imrecist', 'immune-related'])

        if not has_irecist:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=rule['message'],
                suggestion=rule['suggestion'],
                context=f"Drug: {drug_name}"
            )
        return None

    def _check_response_confirmation(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Response endpoints should have confirmation requirement"""
        endpoint = getattr(facts, 'primary_endpoint', '') or ''
        endpoint_lower = endpoint.lower()

        is_response = any(kw in endpoint_lower for kw in ['response', 'orr', 'cr', 'pr'])
        if not is_response:
            return None

        endpoints = sections.get('5_endpoints', '').lower()
        has_confirmation = any(term in endpoints for term in ['confirm', 'consecutive', 'weeks apart', 'days apart'])

        if not has_confirmation:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=rule['message'],
                suggestion=rule['suggestion']
            )
        return None

    def _check_crossover_analysis(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Crossover designs need appropriate analysis"""
        design = sections.get('3_study_design', '').lower()
        methods = sections.get('7_statistical_methods', '').lower()

        has_crossover = 'crossover' in design or 'cross-over' in design
        if not has_crossover:
            return None

        has_adjustment = any(term in methods for term in ['rpsft', 'ipcw', 'rank-preserving',
                                                           'crossover adjust', 'treatment switch'])

        if not has_adjustment:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=rule['message'],
                suggestion=rule['suggestion']
            )
        return None

    def _check_rare_disease_methods(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Rare disease trials need small-sample appropriate methods"""
        total_n = getattr(facts, 'total_n', 0) or 0
        indication = getattr(facts, 'indication', '') or ''

        is_rare = 'rare' in indication.lower() or 'orphan' in indication.lower() or total_n < 50
        if not is_rare:
            return None

        methods = sections.get('7_statistical_methods', '').lower()
        has_appropriate = any(term in methods for term in ['exact', 'bayesian', 'adaptive',
                                                            'small sample', 'simon'])

        if not has_appropriate:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=f"{rule['message']} (N={total_n})",
                suggestion=rule['suggestion']
            )
        return None

    def _check_multiplicity_adjustment(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Multiple endpoints need alpha adjustment"""
        secondary = getattr(facts, 'secondary_endpoints', []) or []

        # If many secondary endpoints marked as key
        if len(secondary) < 2:
            return None

        methods = sections.get('7_statistical_methods', '').lower()
        has_adjustment = any(term in methods for term in ['hochberg', 'holm', 'bonferroni',
                                                           'hierarchical', 'gatekeeping',
                                                           'alpha allocation', 'multiplicity'])

        if not has_adjustment:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=f"{rule['message']} ({len(secondary)} endpoints)",
                suggestion=rule['suggestion']
            )
        return None

    # === SUGGESTION CHECKS ===

    def _check_sensitivity_analysis(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Recommend sensitivity analysis for missing data"""
        missing = sections.get('8_missing_data', '').lower()

        has_sensitivity = any(term in missing for term in ['tipping point', 'pattern mixture',
                                                            'sensitivity', 'delta adjustment'])

        if not has_sensitivity:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=rule['message'],
                suggestion=rule['suggestion']
            )
        return None

    def _check_fda_guidance(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Reference FDA guidance if available"""
        # TODO: Implement FDA guidance lookup by indication/endpoint
        return None

    def _check_subgroup_interaction(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Subgroup analysis should include interaction test"""
        methods = sections.get('7_statistical_methods', '').lower()

        has_subgroup = 'subgroup' in methods
        if not has_subgroup:
            return None

        has_interaction = 'interaction' in methods or 'heterogeneity' in methods

        if not has_interaction:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=rule['message'],
                suggestion=rule['suggestion']
            )
        return None

    # === NEW: Interim Analysis Checks ===

    def _check_interim_count(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Interim analysis should specify exact count"""
        # Check both possible section names
        interim = sections.get('7_interim_analysis', '') or sections.get('interim_analysis', '')
        methods = sections.get('7_statistical_methods', '')
        combined = (interim + methods).lower()

        # Check if interim analysis is mentioned
        has_interim = 'interim analysis' in combined or 'interim analyses' in combined
        if not has_interim:
            return None  # No interim analysis planned, so no issue

        # Check for count specification
        import re
        count_patterns = [
            r'\d+\s*(?:interim|ia)',
            r'(?:one|two|three|four|1|2|3|4)\s*interim',
            r'ia\s*[123]',
            r'first\s*interim.*second\s*interim',
        ]

        has_count = any(re.search(p, combined, re.IGNORECASE) for p in count_patterns)

        if not has_count:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=rule['message'],
                suggestion=rule['suggestion']
            )
        return None

    def _check_interim_timing(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Interim analysis should specify timing/events"""
        interim = sections.get('7_interim_analysis', '') or sections.get('interim_analysis', '')
        methods = sections.get('7_statistical_methods', '')
        combined = (interim + methods).lower()

        has_interim = 'interim analysis' in combined
        if not has_interim:
            return None

        # Check for timing specification
        import re
        timing_patterns = [
            r'\d+\s*(?:months?|events?)',
            r'~\d+',
            r'approximately\s*\d+',
            r'\d+%\s*(?:information|events)',
        ]

        has_timing = any(re.search(p, combined, re.IGNORECASE) for p in timing_patterns)

        if not has_timing:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=rule['message'],
                suggestion=rule['suggestion']
            )
        return None

    def _check_alpha_spending(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Interim analysis should specify alpha spending function"""
        interim = sections.get('7_interim_analysis', '') or sections.get('interim_analysis', '')
        methods = sections.get('7_statistical_methods', '')
        combined = (interim + methods).lower()

        has_interim = 'interim analysis' in combined
        if not has_interim:
            return None

        # Check for alpha spending function
        spending_keywords = [
            "o'brien-fleming", 'obrien-fleming', 'obf',
            'lan-demets', 'pocock', 'alpha spending',
            'spending function', 'hwang-shih-decani'
        ]

        has_spending = any(kw in combined for kw in spending_keywords)

        if not has_spending:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=rule['message'],
                suggestion=rule['suggestion']
            )
        return None

    def _check_efficacy_boundaries(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Interim analysis should include efficacy boundaries"""
        interim = sections.get('7_interim_analysis', '') or sections.get('interim_analysis', '')
        methods = sections.get('7_statistical_methods', '')
        combined = (interim + methods).lower()

        has_interim = 'interim analysis' in combined
        if not has_interim:
            return None

        # Check for boundary specifications
        import re
        boundary_patterns = [
            r'z\s*[=<>]\s*[\d.]+',
            r'p\s*[=<>]\s*0\.\d+',
            r'hr\s*[=<>≤≥]\s*[\d.]+',
            r'boundary',
            r'stopping\s+(?:rule|criteria)',
        ]

        has_boundary = any(re.search(p, combined, re.IGNORECASE) for p in boundary_patterns)

        if not has_boundary:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=rule['message'],
                suggestion=rule['suggestion']
            )
        return None

    def _check_power_calculation_detail(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: Power calculation should include key assumptions"""
        sample_size = sections.get('8_sample_size', '') or sections.get('sample_size', '')
        sample_size_lower = sample_size.lower()

        # Check for key power calculation components
        import re
        has_power = re.search(r'\d+%?\s*power', sample_size_lower) is not None
        has_hr = 'hazard ratio' in sample_size_lower or re.search(r'hr\s*[=:]\s*[\d.]+', sample_size_lower)
        has_median = 'median' in sample_size_lower
        has_events = 'events' in sample_size_lower

        # Need at least 3 of 4 components for a complete power calculation
        components = sum([has_power, bool(has_hr), has_median, has_events])

        if components < 3:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=rule['message'],
                suggestion=rule['suggestion'],
                context=f"Found {components}/4 components (power, HR, median, events)"
            )
        return None

    def _check_censoring_detail(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: TTE endpoints need detailed censoring rules"""
        endpoint = getattr(facts, 'primary_endpoint', '') or ''
        endpoint_lower = endpoint.lower()

        # Is it a TTE endpoint?
        is_tte = any(kw in endpoint_lower for kw in self.TTE_KEYWORDS)
        if not is_tte:
            return None

        methods = sections.get('7_statistical_methods', '')
        methods_lower = methods.lower()

        # Check for detailed censoring (not just mention of "censoring")
        detailed_censoring_patterns = [
            r'censor.*(?:date|time|event)',
            r'(?:death|progression|lost|withdraw).*censor',
            r'censoring\s+(?:rules?|table)',
            r'(?:new|subsequent)\s+(?:therapy|treatment).*censor',
        ]

        import re
        has_detailed = any(re.search(p, methods_lower, re.IGNORECASE) for p in detailed_censoring_patterns)

        if not has_detailed:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=rule['message'],
                suggestion=rule['suggestion'],
                context=f"Endpoint: {endpoint}"
            )
        return None

    def _check_pro_thresholds(self, facts: Any, sections: Dict[str, str], rule: Dict) -> Optional[Issue]:
        """Check: PRO endpoints should have analysis thresholds"""
        endpoints = sections.get('5_endpoints', '')
        methods = sections.get('7_statistical_methods', '')
        combined = (endpoints + methods).lower()

        # Check if PRO is mentioned
        pro_keywords = ['patient-reported', 'quality of life', 'qol', 'eortc', 'eq-5d', 'pro ']
        has_pro = any(kw in combined for kw in pro_keywords)

        if not has_pro:
            return None

        # Check for PRO thresholds
        threshold_patterns = [
            r'(?:mcid|minimal.*clinically.*important)',
            r'\d+\s*point',
            r'threshold',
            r'completion.*\d+%',
            r'compliance.*\d+%',
            r'week\s*\d+.*primary',
        ]

        import re
        has_threshold = any(re.search(p, combined, re.IGNORECASE) for p in threshold_patterns)

        if not has_threshold:
            return Issue(
                severity=rule['severity'],
                section=rule['section'],
                rule_id=rule['id'],
                message=rule['message'],
                suggestion=rule['suggestion']
            )
        return None

    def print_report(self, result: DetectionResult) -> None:
        """Print a formatted issue report"""
        print("\n" + "="*70)
        print("SAP QUALITY ASSURANCE REPORT")
        print("="*70)

        if not result.issues:
            print("\n✓ No issues detected!")
        else:
            # Group by severity
            errors = [i for i in result.issues if i.severity == IssueSeverity.ERROR]
            warnings = [i for i in result.issues if i.severity == IssueSeverity.WARNING]
            suggestions = [i for i in result.issues if i.severity == IssueSeverity.SUGGESTION]

            if errors:
                print(f"\n❌ CRITICAL ERRORS ({len(errors)}):")
                for issue in errors:
                    print(f"   {issue}")
                    print(f"      → {issue.suggestion}")

            if warnings:
                print(f"\n⚠️ WARNINGS ({len(warnings)}):")
                for issue in warnings:
                    print(f"   {issue}")
                    print(f"      → {issue.suggestion}")

            if suggestions:
                print(f"\n💡 SUGGESTIONS ({len(suggestions)}):")
                for issue in suggestions:
                    print(f"   {issue}")
                    print(f"      → {issue.suggestion}")

        print(f"\n{'='*70}")
        print(f"QUALITY SCORE: {result.score:.1f}%")
        print(f"  Errors: {result.error_count} | Warnings: {result.warning_count} | Suggestions: {result.suggestion_count}")
        print("="*70)


def create_issue_detector() -> IssueDetector:
    """Factory function to create IssueDetector"""
    return IssueDetector()


# === CLI ===
if __name__ == "__main__":
    import sys

    print("SAP Issue Detector - Month 3-4 Implementation")
    print("=" * 50)
    print("\nAvailable rules:")

    detector = IssueDetector()
    for rule in detector.rules:
        icon = {"error": "❌", "warning": "⚠️", "suggestion": "💡"}[rule['severity'].value]
        print(f"  {icon} {rule['id']}: {rule['message']}")

    print(f"\nTotal rules: {len(detector.rules)}")
    print("\nUsage:")
    print("  from enterprise_sap_system.qa import IssueDetector")
    print("  detector = IssueDetector()")
    print("  result = detector.detect(protocol_facts, sap_sections)")
    print("  detector.print_report(result)")
