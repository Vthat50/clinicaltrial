"""
Covariate Adjustment Methods
=============================

Methods for adjusting treatment effect estimates for baseline covariates.

Required by:
- FDA Guidance: "Adjusting for Covariates in Randomized Clinical Trials" (2021)
- ICH E9: Statistical Principles for Clinical Trials (Section 5.7)
- EMA: Guideline on adjustment for baseline covariates

Methods:
- ANCOVA (Analysis of Covariance)
- Stratified analysis
- Propensity score methods
- Inverse probability weighting (IPW)
- G-computation
- Targeted maximum likelihood estimation (TMLE)

Key concepts:
- Prognostic covariates
- Predictive covariates
- Stratification factors
- Variance reduction
- Precision gains
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CovariateType(Enum):
    """Types of covariates"""
    PROGNOSTIC = "Prognostic"          # Predicts outcome regardless of treatment
    PREDICTIVE = "Predictive"          # Modifies treatment effect
    STRATIFICATION = "Stratification"   # Used in randomization
    BASELINE = "Baseline"              # General baseline characteristic


class AdjustmentMethod(Enum):
    """Covariate adjustment methods"""
    ANCOVA = "ANCOVA"
    STRATIFIED_ANALYSIS = "Stratified Analysis"
    PROPENSITY_SCORE = "Propensity Score"
    IPW = "Inverse Probability Weighting"
    GCOMPUTATION = "G-Computation"
    TMLE = "Targeted Maximum Likelihood"


@dataclass
class Covariate:
    """
    Specification for a single covariate.

    Defines how a covariate is used in analysis.
    """
    name: str                          # Variable name
    label: str                         # Display label
    covariate_type: CovariateType

    # Variable properties
    continuous: bool = False
    categorical: bool = True
    categories: List[str] = field(default_factory=list)

    # Adjustment specification
    include_in_primary: bool = True
    include_in_sensitivity: bool = True

    # Justification
    prognostic_evidence: str = ""      # Why this is prognostic
    correlation_with_outcome: str = ""  # Expected correlation

    # Handling
    center_continuous: bool = True     # Center at mean
    reference_category: Optional[str] = None


@dataclass
class ANCOVASpec:
    """
    ANCOVA (Analysis of Covariance) specification.

    Adjusts for baseline covariates using linear/Cox/logistic regression.
    """
    # Covariates to adjust for
    covariates: List[Covariate] = field(default_factory=list)

    # Model specification
    include_treatment_by_covariate: bool = False  # Test interactions
    stratification_factors: List[str] = field(default_factory=list)

    # For continuous outcomes
    outcome_transformation: Optional[str] = None  # "log", "sqrt", None

    # For survival outcomes
    check_proportional_hazards: bool = True
    robust_variance: bool = True

    # Missing data
    exclude_missing: bool = True      # Or use imputation

    # Sensitivity analyses
    sensitivity_no_adjustment: bool = True
    sensitivity_different_covariates: List[List[str]] = field(default_factory=list)


@dataclass
class StratifiedAnalysisSpec:
    """
    Stratified analysis specification.

    Analyzes within strata, then combines.
    """
    stratification_factors: List[str]

    # Combination method
    combining_method: str = "Mantel-Haenszel"  # or "Inverse variance"

    # For survival
    stratified_log_rank: bool = True

    # For binary
    cmh_test: bool = True

    # Homogeneity testing
    test_homogeneity: bool = True
    homogeneity_threshold: float = 0.10


@dataclass
class PropensityScoreSpec:
    """
    Propensity score methods specification.

    Used primarily for observational studies, but can be applied
    to RCTs for covariate balance assessment.
    """
    # Variables for propensity model
    covariates: List[str]

    # PS method
    method: str = "matching"  # "matching", "weighting", "stratification"

    # Matching
    matching_ratio: int = 1           # 1:1, 1:n
    caliper: float = 0.2              # Caliper for matching (in SD units)
    replacement: bool = False

    # Weighting
    weight_type: str = "ATE"          # "ATE", "ATT", "ATO"

    # Assessment
    check_balance: bool = True
    balance_threshold: float = 0.10   # Standardized mean difference


@dataclass
class IPWSpec:
    """
    Inverse Probability Weighting specification.

    Adjusts for confounding by weighting subjects.
    """
    # Weight model
    treatment_model_vars: List[str]

    # Weight type
    weight_type: str = "ATE"          # "ATE", "ATT", "ATC"

    # Stabilization
    stabilize_weights: bool = True

    # Trimming
    trim_weights: bool = True
    trim_percentile: float = 0.99     # Trim at 99th percentile

    # Diagnostics
    check_positivity: bool = True
    plot_weights: bool = True


class CovariateAdjustmentService:
    """
    Service for covariate adjustment specifications.

    Implements FDA 2021 guidance on covariate adjustment.
    """

    def __init__(self):
        """Initialize covariate adjustment service"""
        pass

    def create_standard_ancova(
        self,
        endpoint_type: str,
        stratification_factors: List[str],
        prognostic_covariates: List[Covariate] = None
    ) -> ANCOVASpec:
        """
        Create standard ANCOVA specification per FDA guidance.

        Args:
            endpoint_type: "survival", "binary", "continuous"
            stratification_factors: Factors used in randomization
            prognostic_covariates: Additional prognostic factors

        Returns:
            ANCOVASpec
        """
        covariates = []

        # Always adjust for stratification factors
        for factor in stratification_factors:
            covariates.append(Covariate(
                name=factor,
                label=factor,
                covariate_type=CovariateType.STRATIFICATION,
                categorical=True,
                include_in_primary=True
            ))

        # Add prognostic covariates
        if prognostic_covariates:
            covariates.extend(prognostic_covariates)

        spec = ANCOVASpec(
            covariates=covariates,
            stratification_factors=stratification_factors,
            check_proportional_hazards=(endpoint_type == "survival"),
            sensitivity_no_adjustment=True
        )

        return spec

    def generate_ancova_methodology(
        self,
        spec: ANCOVASpec,
        endpoint_type: str
    ) -> str:
        """
        Generate ANCOVA methodology text for SAP.

        Args:
            spec: ANCOVA specification
            endpoint_type: Type of endpoint

        Returns:
            Formatted SAP text
        """
        text = """
## Covariate Adjustment

### Rationale

Covariate adjustment will be used in the primary analysis to:
1. Account for stratification factors used in randomization
2. Improve precision of treatment effect estimates
3. Reduce residual variance

Per FDA Guidance (2021) on "Adjusting for Covariates in Randomized Clinical Trials,"
covariate adjustment is appropriate and recommended when:
- Covariates are pre-specified
- Covariates are measured at baseline (pre-randomization)
- Analysis method is appropriate for the endpoint type

"""

        if endpoint_type == "survival":
            text += """
### Analysis Method: Cox Proportional Hazards with Covariate Adjustment

The primary analysis will use a stratified Cox proportional hazards model:

**Model Specification:**
```
h(t | X, Z) = h₀(t) exp(β₁·Treatment + β₂·X₁ + β₃·X₂ + ...)
```

where:
- h(t | X, Z) = hazard function at time t
- h₀(t) = baseline hazard function
- Treatment = indicator for experimental treatment
- X₁, X₂, ... = baseline covariates
- β₁ = log hazard ratio for treatment effect (parameter of interest)

"""

        elif endpoint_type == "binary":
            text += """
### Analysis Method: Logistic Regression with Covariate Adjustment

The primary analysis will use logistic regression:

**Model Specification:**
```
logit(P(Y=1 | X, Z)) = β₀ + β₁·Treatment + β₂·X₁ + β₃·X₂ + ...
```

where:
- Y = binary outcome (1=response, 0=no response)
- Treatment = indicator for experimental treatment
- X₁, X₂, ... = baseline covariates
- β₁ = log odds ratio for treatment effect (parameter of interest)

The odds ratio exp(β₁) will be reported along with 95% confidence interval.

"""

        elif endpoint_type == "continuous":
            text += """
### Analysis Method: ANCOVA

The primary analysis will use Analysis of Covariance (ANCOVA):

**Model Specification:**
```
Y = β₀ + β₁·Treatment + β₂·X₁ + β₃·X₂ + ... + ε
```

where:
- Y = continuous outcome
- Treatment = indicator for experimental treatment
- X₁, X₂, ... = baseline covariates
- β₁ = treatment effect (difference in means) - parameter of interest
- ε = random error

"""

        # Add covariates table
        text += """
### Covariates Included in Analysis

The following baseline covariates will be included in the adjusted analysis:

| Covariate | Type | Role | Justification |
|-----------|------|------|---------------|
"""

        for cov in spec.covariates:
            var_type = "Continuous" if cov.continuous else "Categorical"
            text += f"| {cov.label} | {var_type} | {cov.covariate_type.value} | {cov.prognostic_evidence or 'Randomization stratification factor'} |\n"

        text += """
**Selection Criteria:**
- All randomization stratification factors are included (per FDA guidance)
- Additional covariates were pre-specified based on clinical knowledge and Phase 2 data
- All covariates measured at baseline (before randomization)

"""

        # Stratification
        if spec.stratification_factors:
            text += f"""
### Stratification

The analysis will be stratified by: {', '.join(spec.stratification_factors)}.

"""
            if endpoint_type == "survival":
                text += """
**Implementation:** The Cox model will be stratified using the STRATA statement,
allowing separate baseline hazards for each stratum while assuming common treatment effect.

"""

        # Model assumptions
        text += self._generate_assumptions_section(spec, endpoint_type)

        # Sensitivity analyses
        text += self._generate_sensitivity_section(spec)

        # FDA compliance
        text += self._generate_fda_compliance_section()

        return text.strip()

    def _generate_assumptions_section(
        self,
        spec: ANCOVASpec,
        endpoint_type: str
    ) -> str:
        """Generate model assumptions section"""
        text = """
### Model Assumptions

"""

        if endpoint_type == "survival":
            text += """
**Proportional Hazards Assumption:**

The proportional hazards assumption will be assessed using:
1. Schoenfeld residuals test
2. Log-log survival plots by treatment group
3. Time-varying covariate test

If the proportional hazards assumption is violated:
- Consider stratified analysis
- Use time-varying coefficient models
- Report restricted mean survival time as alternative

"""

        elif endpoint_type == "continuous":
            text += """
**ANCOVA Assumptions:**

Standard linear model assumptions will be assessed:
1. Linearity: Residual plots
2. Homoscedasticity: Levene's test, residual plots
3. Normality: Q-Q plots, Shapiro-Wilk test
4. Independence: By design (randomization)

If assumptions are violated:
- Consider transformation (log, square root)
- Use robust standard errors
- Apply non-parametric alternative (rank-based ANCOVA)

"""

        text += """
**Missing Data:**

Missing covariate data will be handled as follows:
- Primary analysis: Complete case analysis (exclude subjects with missing covariates)
- Sensitivity analysis: Multiple imputation for missing covariates

The proportion of subjects with missing covariate data will be reported and
compared between treatment groups.

"""

        return text

    def _generate_sensitivity_section(self, spec: ANCOVASpec) -> str:
        """Generate sensitivity analyses section"""
        text = """
### Sensitivity Analyses

To assess robustness of covariate adjustment:

"""

        if spec.sensitivity_no_adjustment:
            text += """
#### 1. Unadjusted Analysis

The primary endpoint will also be analyzed without covariate adjustment to assess
the impact of adjustment on:
- Point estimate of treatment effect
- Standard error and confidence interval width
- Statistical significance

**Expected Impact:** Covariate adjustment typically:
- Does not substantially change point estimate (due to randomization)
- Reduces standard error (improved precision)
- May change significance if close to threshold

"""

        text += """
#### 2. Alternative Covariate Sets

Treatment effect will be estimated with different sets of covariates:
- Minimal adjustment: Stratification factors only
- Maximal adjustment: All pre-specified prognostic factors
- Compare stability of estimates across models

#### 3. Treatment-by-Covariate Interactions

Exploratory analysis will test for treatment-by-covariate interactions to assess
whether treatment effect varies by covariate levels (effect modification).

**Note:** These are exploratory; primary conclusions based on main effects model.

"""

        return text

    def _generate_fda_compliance_section(self) -> str:
        """Generate FDA compliance section"""
        return """
### Regulatory Compliance

This covariate adjustment approach complies with:

**FDA Guidance (2021): "Adjusting for Covariates in Randomized Clinical Trials for Drugs and Biological Products"**

Key recommendations followed:
1. ✓ All covariates pre-specified before database lock
2. ✓ All covariates measured at baseline (pre-randomization)
3. ✓ Stratification factors from randomization included
4. ✓ Analysis method appropriate for endpoint type
5. ✓ Adjustment method specified in SAP
6. ✓ Sensitivity analyses planned (adjusted vs unadjusted)
7. ✓ Treatment-by-covariate interactions explored

**ICH E9:** Statistical Principles for Clinical Trials (Section 5.7 - Adjustment for Covariates)

**Interpretation:**
- Primary conclusion based on covariate-adjusted analysis
- Unadjusted analysis provided for comparison
- Similar results expected due to randomization; adjustment improves precision
- If results differ meaningfully, both will be reported with explanation

**Type I Error Control:**
Covariate adjustment does not inflate Type I error rate when:
- Covariates pre-specified
- Model selection not data-driven
- Primary analysis model fixed regardless of observed data
"""

    def generate_stratified_analysis_text(
        self,
        spec: StratifiedAnalysisSpec,
        endpoint_type: str
    ) -> str:
        """Generate stratified analysis methodology"""
        text = f"""
## Stratified Analysis

### Method

The primary analysis will be stratified by: {', '.join(spec.stratification_factors)}.

"""

        if endpoint_type == "survival":
            text += """
**Stratified Log-Rank Test:**

The stratified log-rank test will be used to compare survival distributions between
treatment groups while accounting for stratification factors.

**Formula:** The test statistic is:
```
χ² = [Σₛ (Oₑₛ - Eₑₛ)]² / Σₛ Vₛ
```

where:
- s = stratum index
- Oₑₛ = observed events in experimental arm in stratum s
- Eₑₛ = expected events under null hypothesis
- Vₛ = variance in stratum s

**Hazard Ratio:**
The stratified hazard ratio will be estimated using:
- Stratified Cox proportional hazards model
- Mantel-Haenszel estimator

"""

        elif endpoint_type == "binary":
            text += f"""
**Cochran-Mantel-Haenszel (CMH) Test:**

The CMH test will compare response rates between treatment groups, stratified by
{', '.join(spec.stratification_factors)}.

**Assumptions:**
- Common odds ratio across strata (no effect modification by strata)

**Homogeneity Test:**
Breslow-Day test will assess homogeneity of odds ratios across strata (p < {spec.homogeneity_threshold}).

If heterogeneity detected:
- Report stratum-specific estimates
- Consider interaction terms
- Use alternative combining method

"""

        return text

    def generate_sas_code(self, spec: ANCOVASpec, endpoint_type: str) -> str:
        """Generate SAS code for ANCOVA"""

        covariates_str = " ".join([cov.name for cov in spec.covariates])
        strata_str = " ".join(spec.stratification_factors) if spec.stratification_factors else ""

        if endpoint_type == "survival":
            return f"""
/* Cox Proportional Hazards with Covariate Adjustment */

proc phreg data=adtte;
    class TRT01P (ref='Control') {' '.join([f"{cov.name}" for cov in spec.covariates if cov.categorical])};
    model AVAL*CNSR(1) = TRT01P {covariates_str} / risklimits;
    {f"strata {strata_str};" if strata_str else ""}

    /* Hazard ratio for treatment */
    hazardratio TRT01P / diff=ref;

    /* Check proportional hazards */
    assess ph / resample;

    title "Cox Model with Covariate Adjustment";
run;

/* Unadjusted analysis for comparison */
proc phreg data=adtte;
    class TRT01P (ref='Control');
    model AVAL*CNSR(1) = TRT01P / risklimits;
    {f"strata {strata_str};" if strata_str else ""}
    hazardratio TRT01P / diff=ref;
    title "Unadjusted Cox Model";
run;
"""

        elif endpoint_type == "binary":
            return f"""
/* Logistic Regression with Covariate Adjustment */

proc logistic data=adrs;
    class TRT01P (ref='Control') {' '.join([f"{cov.name}" for cov in spec.covariates if cov.categorical])};
    model RESPONSE(event='1') = TRT01P {covariates_str} / clodds=wald;

    /* Odds ratio for treatment */
    oddsratio TRT01P / diff=ref;

    title "Logistic Regression with Covariate Adjustment";
run;

/* CMH test (unadjusted, stratified) */
proc freq data=adrs;
    tables {strata_str + ' *' if strata_str else ''} TRT01P * RESPONSE / cmh chisq;
    title "CMH Test (Stratified, Unadjusted for Covariates)";
run;
"""

        return ""


# Singleton instance
_covariate_service: Optional[CovariateAdjustmentService] = None


def get_covariate_adjustment_service() -> CovariateAdjustmentService:
    """
    Get covariate adjustment service instance.

    Returns:
        CovariateAdjustmentService instance
    """
    global _covariate_service

    if _covariate_service is None:
        _covariate_service = CovariateAdjustmentService()

    return _covariate_service
