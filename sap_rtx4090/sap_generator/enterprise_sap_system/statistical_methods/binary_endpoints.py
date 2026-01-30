"""
Binary Endpoint Analysis Methods
=================================

Statistical methods for binary endpoints in oncology trials.

Common endpoints:
- Objective Response Rate (ORR): CR + PR
- Disease Control Rate (DCR): CR + PR + SD
- Complete Response (CR) Rate
- Clinical Benefit Rate (CBR)

Methods:
- Exact binomial tests (Clopper-Pearson)
- Cochran-Mantel-Haenszel tests (stratified)
- Risk difference with confidence intervals
- Odds ratio and relative risk
- Multiple comparison procedures for ORR

FDA Requirements:
- ORR must be confirmed per RECIST (4+ weeks apart)
- Independent review recommended for pivotal trials
- Multiple comparison adjustment for multi-arm trials
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


class BinaryEndpointType(Enum):
    """Types of binary endpoints"""
    ORR = "Objective Response Rate"
    DCR = "Disease Control Rate"
    CBR = "Clinical Benefit Rate"
    CR_RATE = "Complete Response Rate"
    CONVERSION_RATE = "Conversion Rate"  # e.g., resectability
    CUSTOM = "Custom Binary Endpoint"


class ConfidenceIntervalMethod(Enum):
    """Methods for CI calculation"""
    CLOPPER_PEARSON = "Clopper-Pearson (Exact)"
    WILSON = "Wilson Score"
    AGRESTI_COULL = "Agresti-Coull"
    JEFFREYS = "Jeffreys"
    WALD = "Wald (Normal Approximation)"


class ComparisonMethod(Enum):
    """Methods for comparing proportions"""
    CMH = "Cochran-Mantel-Haenszel"
    FISHER_EXACT = "Fisher's Exact Test"
    CHI_SQUARE = "Chi-Square Test"
    BARNARD = "Barnard's Exact Test"
    MIETTINEN_NURMINEN = "Miettinen-Nurminen"


@dataclass
class ResponseCriteria:
    """
    Definition of response for binary endpoint.

    Specifies which RECIST categories constitute a "response".
    """
    name: str                           # e.g., "ORR", "DCR"
    response_categories: List[str]      # e.g., ["CR", "PR"]
    requires_confirmation: bool = True
    confirmation_interval_days: int = 28

    # Special handling
    include_unconfirmed: bool = False   # For sensitivity analysis

    def is_responder(self, best_response: str, confirmed: bool = True) -> bool:
        """Determine if subject is a responder"""
        if best_response not in self.response_categories:
            return False

        if self.requires_confirmation and not confirmed:
            return False

        return True


@dataclass
class BinaryEndpointSpec:
    """
    Complete specification for binary endpoint analysis.

    Defines the endpoint, analysis method, and all parameters.
    """
    # Endpoint definition
    endpoint_name: str
    endpoint_type: BinaryEndpointType
    response_criteria: ResponseCriteria

    # Analysis population
    analysis_population: str = "ITT"    # or "Per-Protocol", "Evaluable"

    # Primary analysis method
    primary_method: ComparisonMethod = ComparisonMethod.CMH
    ci_method: ConfidenceIntervalMethod = ConfidenceIntervalMethod.CLOPPER_PEARSON
    confidence_level: float = 0.95

    # Stratification
    stratification_factors: List[str] = field(default_factory=list)

    # Hypothesis testing
    one_sided: bool = True
    alpha: float = 0.025
    null_hypothesis_rate: Optional[float] = None  # For single-arm

    # Sensitivity analyses
    sensitivity_populations: List[str] = field(default_factory=list)
    include_unconfirmed_responses: bool = True  # As sensitivity

    # Missing data
    exclude_missing_assessments: bool = True
    missing_counted_as: Optional[str] = None  # "non-responder", "responder", None


@dataclass
class ResponseData:
    """Data for response analysis"""
    # Counts by treatment
    treatment_n: int
    treatment_responders: int
    control_n: int
    control_responders: int

    # Stratification (optional)
    stratum: Optional[str] = None

    def treatment_rate(self) -> float:
        """Treatment response rate"""
        return self.treatment_responders / self.treatment_n if self.treatment_n > 0 else 0.0

    def control_rate(self) -> float:
        """Control response rate"""
        return self.control_responders / self.control_n if self.control_n > 0 else 0.0

    def risk_difference(self) -> float:
        """Risk difference (treatment - control)"""
        return self.treatment_rate() - self.control_rate()


@dataclass
class BinaryAnalysisResult:
    """Results from binary endpoint analysis"""
    # Point estimates
    treatment_rate: float
    treatment_ci_lower: float
    treatment_ci_upper: float

    control_rate: Optional[float] = None
    control_ci_lower: Optional[float] = None
    control_ci_upper: Optional[float] = None

    # Comparison
    risk_difference: Optional[float] = None
    rd_ci_lower: Optional[float] = None
    rd_ci_upper: Optional[float] = None

    odds_ratio: Optional[float] = None
    or_ci_lower: Optional[float] = None
    or_ci_upper: Optional[float] = None

    # Hypothesis test
    p_value: Optional[float] = None
    test_statistic: Optional[float] = None
    test_name: str = ""


class BinaryEndpointService:
    """
    Service for binary endpoint analysis specifications.

    Provides methods for ORR, DCR, and other binary endpoint analyses.
    """

    # Standard response criteria definitions
    STANDARD_CRITERIA = {
        "ORR": ResponseCriteria(
            name="Objective Response Rate",
            response_categories=["CR", "PR"],
            requires_confirmation=True,
            confirmation_interval_days=28
        ),
        "DCR": ResponseCriteria(
            name="Disease Control Rate",
            response_categories=["CR", "PR", "SD"],
            requires_confirmation=False  # SD doesn't require confirmation for DCR
        ),
        "CR_Rate": ResponseCriteria(
            name="Complete Response Rate",
            response_categories=["CR"],
            requires_confirmation=True,
            confirmation_interval_days=28
        ),
        "CBR": ResponseCriteria(
            name="Clinical Benefit Rate",
            response_categories=["CR", "PR", "SD≥24wks"],
            requires_confirmation=True,
            confirmation_interval_days=28
        ),
    }

    def __init__(self):
        """Initialize binary endpoint service"""
        pass

    def create_orr_spec(
        self,
        stratification_factors: List[str] = None,
        one_sided: bool = True,
        alpha: float = 0.025
    ) -> BinaryEndpointSpec:
        """
        Create standard ORR analysis specification.

        Args:
            stratification_factors: Stratification variables
            one_sided: One-sided test
            alpha: Significance level

        Returns:
            BinaryEndpointSpec for ORR
        """
        return BinaryEndpointSpec(
            endpoint_name="Objective Response Rate",
            endpoint_type=BinaryEndpointType.ORR,
            response_criteria=self.STANDARD_CRITERIA["ORR"],
            primary_method=ComparisonMethod.CMH,
            ci_method=ConfidenceIntervalMethod.CLOPPER_PEARSON,
            stratification_factors=stratification_factors or [],
            one_sided=one_sided,
            alpha=alpha,
            sensitivity_populations=["ITT", "Per-Protocol", "Evaluable for Response"],
            include_unconfirmed_responses=True
        )

    def create_dcr_spec(
        self,
        stratification_factors: List[str] = None
    ) -> BinaryEndpointSpec:
        """Create standard DCR analysis specification"""
        return BinaryEndpointSpec(
            endpoint_name="Disease Control Rate",
            endpoint_type=BinaryEndpointType.DCR,
            response_criteria=self.STANDARD_CRITERIA["DCR"],
            primary_method=ComparisonMethod.CMH,
            ci_method=ConfidenceIntervalMethod.CLOPPER_PEARSON,
            stratification_factors=stratification_factors or [],
            one_sided=True,
            alpha=0.025
        )

    def generate_orr_methodology(
        self,
        spec: BinaryEndpointSpec,
        single_arm: bool = False
    ) -> str:
        """
        Generate ORR analysis methodology for SAP.

        Args:
            spec: Binary endpoint specification
            single_arm: True for single-arm trial

        Returns:
            Formatted SAP text
        """
        text = f"""
## {spec.endpoint_name} Analysis

### Endpoint Definition

**{spec.endpoint_name} ({spec.endpoint_type.name})** is defined as the proportion of subjects
who achieve a best overall response of {' or '.join(spec.response_criteria.response_categories)}
per RECIST 1.1.

**Response Criteria:**
"""

        for category in spec.response_criteria.response_categories:
            text += f"- {category}: "
            if category == "CR":
                text += "Complete disappearance of all target and non-target lesions\n"
            elif category == "PR":
                text += "≥30% decrease in sum of diameters of target lesions\n"
            elif category == "SD":
                text += "Neither PR nor PD criteria met\n"

        if spec.response_criteria.requires_confirmation:
            text += f"""
**Confirmation Requirement:**
Responses (CR/PR) must be confirmed by repeat assessment ≥{spec.response_criteria.confirmation_interval_days} days
after initial documentation. Only confirmed responses will be counted in the primary analysis.
"""

        text += f"""
### Analysis Population

The primary analysis will be conducted in the {spec.analysis_population} population, defined as
all randomized subjects.

### Statistical Method

"""

        if single_arm:
            text += self._generate_single_arm_method(spec)
        else:
            text += self._generate_two_arm_method(spec)

        text += self._generate_confidence_interval_section(spec)
        text += self._generate_hypothesis_test_section(spec, single_arm)
        text += self._generate_sensitivity_analyses_section(spec)

        return text.strip()

    def _generate_single_arm_method(self, spec: BinaryEndpointSpec) -> str:
        """Generate methodology for single-arm trial"""
        null_rate = spec.null_hypothesis_rate or 0.10

        text = f"""
**Single-Arm Design:**

The trial will test whether the {spec.endpoint_name} exceeds a historical control rate.

**Hypotheses:**
- H0: ORR ≤ {null_rate * 100:.0f}% (null hypothesis)
- HA: ORR > {null_rate * 100:.0f}% (alternative hypothesis)

**Test:** Exact binomial test against historical control rate of {null_rate * 100:.0f}%

**Decision Rule:**
Reject H0 if the lower bound of the {spec.confidence_level * 100:.0f}% confidence interval
for ORR exceeds {null_rate * 100:.0f}%.

"""
        return text

    def _generate_two_arm_method(self, spec: BinaryEndpointSpec) -> str:
        """Generate methodology for two-arm trial"""
        text = f"""
**Comparison Method:** {spec.primary_method.value}

"""

        if spec.primary_method == ComparisonMethod.CMH:
            if spec.stratification_factors:
                factors_str = ", ".join(spec.stratification_factors)
                text += f"""
The Cochran-Mantel-Haenszel (CMH) test will be used to compare {spec.endpoint_name} between
treatment groups, stratified by {factors_str}.

**Rationale:** The CMH test accounts for stratification factors used in randomization and
provides appropriate Type I error control.

**Test Statistic:** The CMH chi-square statistic with 1 degree of freedom
"""
            else:
                text += """
The Cochran-Mantel-Haenszel (CMH) test will be used to compare {spec.endpoint_name} between
treatment groups (unstratified, equivalent to Pearson chi-square test).
"""

        elif spec.primary_method == ComparisonMethod.FISHER_EXACT:
            text += """
Fisher's exact test will be used due to small sample size or low expected cell counts.

**Rationale:** Fisher's exact test provides exact p-values without requiring large-sample
assumptions, appropriate when cell counts are small (<5).
"""

        return text

    def _generate_confidence_interval_section(self, spec: BinaryEndpointSpec) -> str:
        """Generate CI methodology section"""
        text = f"""
### Confidence Intervals

**Method:** {spec.ci_method.value}

{spec.confidence_level * 100:.0f}% confidence intervals will be calculated for:
- {spec.endpoint_name} in each treatment group
- Risk difference (Experimental - Control)
- Odds ratio (Experimental vs Control)

"""

        if spec.ci_method == ConfidenceIntervalMethod.CLOPPER_PEARSON:
            text += """
**Clopper-Pearson (Exact) Method:**
The Clopper-Pearson method provides exact confidence intervals based on the binomial distribution.
This method is conservative (actual coverage ≥ nominal coverage) and is recommended by FDA for
response rates in oncology.

**Formula:** The confidence limits are the solutions to:
- Lower limit: P(X ≥ x | n, p_L) = α/2
- Upper limit: P(X ≤ x | n, p_U) = α/2

where X ~ Binomial(n, p), x = observed responders
"""

        elif spec.ci_method == ConfidenceIntervalMethod.WILSON:
            text += """
**Wilson Score Method:**
The Wilson score interval provides better coverage properties than the Wald interval,
especially for extreme proportions or small samples.

**Formula:**
(p̂ + z²/2n ± z√[p̂(1-p̂)/n + z²/4n²]) / (1 + z²/n)

where p̂ = sample proportion, z = normal quantile, n = sample size
"""

        return text

    def _generate_hypothesis_test_section(
        self,
        spec: BinaryEndpointSpec,
        single_arm: bool
    ) -> str:
        """Generate hypothesis testing section"""
        text = """
### Hypothesis Testing

"""

        if single_arm:
            text += f"""
**Null Hypothesis:** H0: ORR ≤ {spec.null_hypothesis_rate * 100:.0f}%
**Alternative Hypothesis:** HA: ORR > {spec.null_hypothesis_rate * 100:.0f}%
"""
        else:
            text += """
**Null Hypothesis:** H0: ORR_experimental = ORR_control
**Alternative Hypothesis:** HA: ORR_experimental > ORR_control
"""

        if spec.one_sided:
            text += f"\n**Significance Level:** One-sided α = {spec.alpha}\n"
        else:
            text += f"\n**Significance Level:** Two-sided α = {spec.alpha * 2}\n"

        text += """
**Decision Rule:**
Reject H0 if p-value < α, concluding that the experimental treatment has superior ORR.

**Interpretation:**
- p < 0.001: Very strong evidence of difference
- 0.001 ≤ p < 0.01: Strong evidence
- 0.01 ≤ p < 0.05: Moderate evidence
- p ≥ 0.05: Insufficient evidence
"""

        return text

    def _generate_sensitivity_analyses_section(self, spec: BinaryEndpointSpec) -> str:
        """Generate sensitivity analyses section"""
        text = """
### Sensitivity Analyses

To assess the robustness of the primary analysis, the following sensitivity analyses will be
performed:

"""

        if spec.include_unconfirmed_responses:
            text += f"""
#### 1. Including Unconfirmed Responses

{spec.endpoint_name} will be recalculated including subjects with unconfirmed responses
(responses documented at only one assessment). This analysis assesses whether the confirmation
requirement substantially impacts results.

"""

        if spec.sensitivity_populations:
            text += """
#### 2. Alternative Analysis Populations

"""
            for pop in spec.sensitivity_populations:
                text += f"- {pop} population\n"

        text += """
#### 3. Missing Data Assumptions

**Primary Analysis:** Subjects without adequate tumor assessments excluded from denominator

**Sensitivity:**
- Non-responder imputation: Subjects without assessments counted as non-responders
- Completer analysis: Only subjects with confirmed assessments

#### 4. Independent Review

For pivotal trials, an independent radiological review committee (IRC) will assess all
responses. Agreement between investigator and IRC assessments will be summarized.

**Primary Analysis:** Based on investigator assessment
**Sensitivity:** Based on IRC assessment

### Presentation

Results will be presented as:
- Response rates with exact 95% confidence intervals by treatment group
- Forest plot showing ORR and 95% CI for overall and subgroups
- Risk difference and odds ratio with confidence intervals
- Waterfall plot showing best percent change in tumor burden
- Spider plot showing tumor burden over time by subject
"""

        return text

    def generate_cmh_test_code(self, spec: BinaryEndpointSpec, language: str = "SAS") -> str:
        """
        Generate code for CMH test.

        Args:
            spec: Binary endpoint specification
            language: "SAS" or "R"

        Returns:
            Example code
        """
        if language == "SAS":
            strata = " ".join(spec.stratification_factors) if spec.stratification_factors else ""

            return f"""
/* Cochran-Mantel-Haenszel Test for {spec.endpoint_name} */

/* Create response flag */
data adrs_orr;
    set adrs;
    where PARAMCD = 'BOR' and ANL01FL = 'Y';

    /* Define responder */
    RESPONSE = 0;
    if AVALC in ('CR', 'PR') and AVAL = 1 then RESPONSE = 1;  /* Confirmed responses */
run;

/* CMH Test */
proc freq data=adrs_orr;
    tables {strata + ' *' if strata else ''} TRT01P * RESPONSE / cmh chisq nocol nopercent;
    exact fisher;
    title "{spec.endpoint_name} by Treatment Group";
run;

/* Exact Confidence Intervals */
proc freq data=adrs_orr;
    tables TRT01P * RESPONSE / binomial(level='1');
    exact binomial;
    by TRT01P;
run;

/* Stratified Risk Difference */
proc freq data=adrs_orr;
    tables {strata + ' *' if strata else ''} TRT01P * RESPONSE / riskdiff(cl=wald) cmh;
    title "Risk Difference in {spec.endpoint_name}";
run;
"""

        elif language == "R":
            return f"""
# Cochran-Mantel-Haenszel Test for {spec.endpoint_name}

library(epiR)
library(binom)

# Create response flag
adrs_orr <- adrs %>%
    filter(PARAMCD == 'BOR', ANL01FL == 'Y') %>%
    mutate(
        RESPONSE = if_else(AVALC %in% c('CR', 'PR') & AVAL == 1, 1, 0)
    )

# CMH Test (stratified)
strata <- list({", ".join([f"adrs_orr${f}" for f in spec.stratification_factors])})
cmh_result <- mantelhaen.test(
    adrs_orr$TRT01P,
    adrs_orr$RESPONSE,
    strata
)

print(cmh_result)

# Exact Confidence Intervals by Treatment
by_treatment <- adrs_orr %>%
    group_by(TRT01P) %>%
    summarise(
        n = n(),
        responders = sum(RESPONSE),
        rate = mean(RESPONSE)
    )

# Clopper-Pearson exact CI
for(trt in unique(by_treatment$TRT01P)) {{
    ci <- binom.confint(
        by_treatment$responders[by_treatment$TRT01P == trt],
        by_treatment$n[by_treatment$TRT01P == trt],
        method = "exact"
    )
    print(paste(trt, ":", ci$mean, "(", ci$lower, ",", ci$upper, ")"))
}}

# Risk Difference with CI
riskdiff_result <- epi.2by2(
    table(adrs_orr$TRT01P, adrs_orr$RESPONSE),
    method = "cohort.count"
)

print(riskdiff_result$res$RD.strata.wald)
"""

        return ""


# Singleton instance
_binary_service: Optional[BinaryEndpointService] = None


def get_binary_endpoint_service() -> BinaryEndpointService:
    """
    Get binary endpoint service instance.

    Returns:
        BinaryEndpointService instance
    """
    global _binary_service

    if _binary_service is None:
        _binary_service = BinaryEndpointService()

    return _binary_service
