"""
Repeated Measures / Longitudinal Analysis Methods
==================================================

Methods for analyzing outcomes measured at multiple time points.

Required by:
- NRC Panel on Missing Data (2010)
- FDA Guidance on Missing Data (2019)
- ICH E9(R1): Estimands framework for longitudinal data

Methods:
- MMRM (Mixed Model for Repeated Measures)
- GEE (Generalized Estimating Equations)
- Linear mixed effects models
- Growth curve models
- Time series analysis

Common in:
- PRO/QoL endpoints measured over time
- Tumor burden trajectories
- Biomarker longitudinal profiles
- Safety lab values over time
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CovarianceStructure(Enum):
    """Covariance structures for repeated measures"""
    UNSTRUCTURED = "Unstructured (UN)"
    COMPOUND_SYMMETRY = "Compound Symmetry (CS)"
    AUTOREGRESSIVE = "AR(1)"
    TOEPLITZ = "Toeplitz"
    ANTE_DEPENDENCE = "Ante-dependence (ANTE)"
    SPATIAL_POWER = "Spatial Power (SP)"


class MissingDataMethod(Enum):
    """Missing data handling methods"""
    LIKELIHOOD = "Likelihood-based (MAR)"
    MI = "Multiple Imputation"
    GEE = "GEE with working correlation"
    LOCF = "Last Observation Carried Forward"
    BASELINE_OBSERVATION = "Baseline Observation Carried Forward"


class TimeEffect(Enum):
    """Modeling of time effects"""
    CATEGORICAL = "Categorical (visit as factor)"
    CONTINUOUS_LINEAR = "Continuous Linear"
    CONTINUOUS_QUADRATIC = "Continuous Quadratic"
    PIECEWISE_LINEAR = "Piecewise Linear"
    SPLINE = "Natural Cubic Spline"


@dataclass
class MMRMSpec:
    """
    Mixed Model for Repeated Measures (MMRM) specification.

    MMRM is the gold standard for longitudinal continuous outcomes
    with MAR missing data.
    """
    # Outcome
    outcome_variable: str              # e.g., "CHG" (change from baseline)
    baseline_variable: Optional[str] = "BASE"

    # Time
    time_variable: str = "AVISIT"      # Analysis visit
    time_points: List[str] = field(default_factory=list)  # e.g., ["Week 4", "Week 8", ...]
    time_effect: TimeEffect = TimeEffect.CATEGORICAL

    # Fixed effects
    treatment_variable: str = "TRT01P"
    treatment_by_time_interaction: bool = True
    baseline_adjustment: bool = True
    baseline_by_time_interaction: bool = False

    # Covariates
    covariates: List[str] = field(default_factory=list)
    stratification_factors: List[str] = field(default_factory=list)

    # Random effects
    random_intercept: bool = True
    random_slope: bool = False

    # Covariance structure
    covariance_structure: CovarianceStructure = CovarianceStructure.UNSTRUCTURED
    covariance_structure_alternatives: List[CovarianceStructure] = field(
        default_factory=lambda: [
            CovarianceStructure.UNSTRUCTURED,
            CovarianceStructure.AUTOREGRESSIVE,
            CovarianceStructure.TOEPLITZ
        ]
    )

    # Model selection
    use_aic_bic: bool = True           # Select covariance using AIC/BIC
    reml: bool = True                  # Use REML estimation

    # Inference
    degrees_of_freedom_method: str = "Kenward-Roger"  # or "Satterthwaite"
    alpha: float = 0.05

    # Primary time point
    primary_time_point: Optional[str] = None  # If one time point is primary

    # Missing data
    missing_data_assumption: str = "MAR"


@dataclass
class GEESpec:
    """
    Generalized Estimating Equations (GEE) specification.

    GEE for longitudinal data with focus on population-average effects.
    """
    # Outcome
    outcome_variable: str
    outcome_distribution: str = "normal"  # "normal", "binomial", "poisson"
    link_function: str = "identity"       # "identity", "log", "logit"

    # Time
    time_variable: str = "AVISIT"
    time_points: List[str] = field(default_factory=list)

    # Fixed effects
    treatment_variable: str = "TRT01P"
    treatment_by_time_interaction: bool = True
    baseline_adjustment: bool = True

    # Covariates
    covariates: List[str] = field(default_factory=list)

    # Working correlation structure
    working_correlation: str = "exchangeable"  # "independent", "exchangeable", "ar1", "unstructured"

    # Subject ID
    subject_id_variable: str = "USUBJID"

    # Variance estimation
    robust_variance: bool = True       # Sandwich/empirical variance estimator

    # Missing data
    # GEE assumes MCAR/MAR with complete case approach


@dataclass
class LongitudinalProfile:
    """
    Specification for visualizing longitudinal profiles.

    Spaghetti plots, mean profiles, etc.
    """
    outcome_variable: str
    time_variable: str

    # Plot types
    individual_profiles: bool = True   # Spaghetti plot
    mean_profiles: bool = True         # Mean ± SE by treatment
    median_profiles: bool = False      # Median with IQR

    # Stratification
    by_treatment: bool = True
    by_response: bool = False          # Separate by responders/non-responders

    # Time points
    time_points: List[str] = field(default_factory=list)


class RepeatedMeasuresService:
    """
    Service for repeated measures analysis specifications.

    Provides MMRM and GEE methodology for longitudinal data.
    """

    def __init__(self):
        """Initialize repeated measures service"""
        pass

    def create_standard_mmrm(
        self,
        outcome_variable: str,
        time_points: List[str],
        baseline_variable: str = "BASE",
        primary_time_point: str = None
    ) -> MMRMSpec:
        """
        Create standard MMRM specification.

        Args:
            outcome_variable: Outcome variable (usually change from baseline)
            time_points: List of analysis visits
            baseline_variable: Baseline value variable
            primary_time_point: Primary time point if applicable

        Returns:
            MMRMSpec with standard settings
        """
        return MMRMSpec(
            outcome_variable=outcome_variable,
            baseline_variable=baseline_variable,
            time_points=time_points,
            time_effect=TimeEffect.CATEGORICAL,
            treatment_by_time_interaction=True,
            baseline_adjustment=True,
            covariance_structure=CovarianceStructure.UNSTRUCTURED,
            degrees_of_freedom_method="Kenward-Roger",
            primary_time_point=primary_time_point or time_points[-1]
        )

    def generate_mmrm_methodology(self, spec: MMRMSpec) -> str:
        """
        Generate MMRM methodology text for SAP.

        Args:
            spec: MMRM specification

        Returns:
            Formatted SAP text
        """
        text = f"""
## Repeated Measures Analysis

### Analysis Method: Mixed Model for Repeated Measures (MMRM)

The longitudinal data will be analyzed using a Mixed Model for Repeated Measures (MMRM),
which is a likelihood-based approach that appropriately handles missing data under the
MAR (Missing At Random) assumption.

### Model Specification

**Outcome Variable:** {spec.outcome_variable}

The following MMRM will be fit:

**Fixed Effects:**
"""

        # List fixed effects
        fixed_effects = [f"- Treatment ({spec.treatment_variable})"]
        fixed_effects.append(f"- Time ({spec.time_variable})")

        if spec.treatment_by_time_interaction:
            fixed_effects.append(f"- Treatment-by-Time interaction")

        if spec.baseline_adjustment and spec.baseline_variable:
            fixed_effects.append(f"- Baseline value ({spec.baseline_variable})")

            if spec.baseline_by_time_interaction:
                fixed_effects.append(f"- Baseline-by-Time interaction")

        for cov in spec.covariates:
            fixed_effects.append(f"- {cov}")

        text += "\n".join(fixed_effects) + "\n"

        text += f"""
**Random Effects:**
"""

        if spec.random_intercept:
            text += "- Random intercept for each subject\n"
        if spec.random_slope:
            text += "- Random slope for time\n"

        text += f"""
**Covariance Structure:** {spec.covariance_structure.value}

The within-subject covariance structure will be modeled using an {spec.covariance_structure.value} structure.
"""

        if spec.covariance_structure == CovarianceStructure.UNSTRUCTURED:
            text += """
The unstructured covariance allows for:
- Different variances at each time point
- Different correlations between all pairs of time points
- Maximum flexibility but requires most parameters

This is the most general structure and is recommended when sample size permits.
"""

        elif spec.covariance_structure == CovarianceStructure.AUTOREGRESSIVE:
            text += """
The AR(1) structure assumes:
- Correlation decreases exponentially with time lag
- Corr(Yi,t, Yi,t+k) = ρ^k
- Appropriate when correlation depends primarily on time separation
"""

        text += """
**Covariance Structure Selection:**

"""

        if spec.use_aic_bic:
            text += f"""
Multiple covariance structures will be fit:
"""
            for cov_struct in spec.covariance_structure_alternatives:
                text += f"- {cov_struct.value}\n"

            text += f"""
The structure with the lowest Akaike Information Criterion (AIC) and/or Bayesian
Information Criterion (BIC) will be selected for the primary analysis.

**Selection Criteria:**
- AIC = -2 × log-likelihood + 2 × number of parameters
- BIC = -2 × log-likelihood + log(n) × number of parameters

Lower values indicate better fit penalized for complexity.
"""

        else:
            text += f"The {spec.covariance_structure.value} structure is pre-specified.\n"

        text += f"""
### Estimation Method

**REML (Restricted Maximum Likelihood):** {"Yes" if spec.reml else "No (Maximum Likelihood)"}

"""

        if spec.reml:
            text += """
REML provides unbiased estimates of variance components and is recommended for
models where fixed effects are of primary interest.
"""

        text += f"""
**Degrees of Freedom:** {spec.degrees_of_freedom_method} approximation

"""

        if spec.degrees_of_freedom_method == "Kenward-Roger":
            text += """
The Kenward-Roger method provides:
- Adjusted degrees of freedom accounting for variance component uncertainty
- More accurate inference in small samples
- Recommended for MMRM analysis
"""

        # Primary inference
        text += self._generate_inference_section(spec)

        # Missing data
        text += self._generate_missing_data_section()

        # Assumptions
        text += self._generate_assumptions_section()

        # Software
        text += self._generate_software_section()

        return text.strip()

    def _generate_inference_section(self, spec: MMRMSpec) -> str:
        """Generate inference section"""
        text = """
### Statistical Inference

"""

        if spec.primary_time_point:
            text += f"""
**Primary Comparison:**

The primary comparison is the treatment difference at **{spec.primary_time_point}**.

The null hypothesis H0: μ_exp({spec.primary_time_point}) = μ_ctrl({spec.primary_time_point})

will be tested using an F-test (or t-test) from the MMRM model.

**Test Statistic:** Difference in least squares means (LSM) at {spec.primary_time_point}

**Confidence Interval:** 95% CI for the treatment difference

**P-value:** Two-sided test at α = {spec.alpha}

"""

        if spec.treatment_by_time_interaction:
            text += """
**Treatment-by-Time Interaction:**

The treatment-by-time interaction term allows treatment effect to vary by time point.

- If interaction is significant: treatment effect differs across time
- Treatment effect estimated separately at each time point
- Time point-specific LSM differences reported with 95% CIs

"""

        text += """
**Least Squares Means (LSM):**

LSM will be estimated for each treatment group at each time point, representing
the expected outcome for a typical subject (averaged over covariate distribution).

**Contrasts:**
- Treatment difference (Experimental - Control) at each time point
- Time contrasts within each treatment group (change over time)

"""

        return text

    def _generate_missing_data_section(self) -> str:
        """Generate missing data handling section"""
        return """
### Missing Data Handling

**Assumption:** Missing At Random (MAR)

The MMRM uses likelihood-based estimation, which provides valid inference under MAR
without requiring imputation.

**MAR Assumption:**
The probability of missing data may depend on observed data (baseline values, previous
measurements) but not on unobserved data (current or future measurements).

**Validity:**
- All available data from each subject are used
- No need to impute missing values
- More efficient than complete case analysis
- Unbiased under MAR

**Subjects Included:**
- All subjects with baseline and at least one post-baseline assessment
- Subjects contribute to analysis at all time points where data are observed

**Sensitivity Analyses:**
To assess robustness to MAR assumption:
1. Pattern mixture models
2. Tipping point analysis
3. Multiple imputation under MNAR scenarios
4. Per-protocol analysis (completers only)

"""

    def _generate_assumptions_section(self) -> str:
        """Generate model assumptions section"""
        return """
### Model Assumptions

**MMRM Assumptions:**

1. **Multivariate Normality:** Residuals at each time point follow normal distribution
   - Assessment: Q-Q plots, histograms of residuals
   - Robustness: MMRM is fairly robust to moderate departures

2. **Correct Specification:** Mean structure and covariance structure are correctly specified
   - Assessment: Model fit statistics (AIC/BIC), residual plots
   - Action: Try alternative covariance structures if poor fit

3. **MAR:** Missing data mechanism is MAR (not MNAR)
   - Assessment: Compare baseline characteristics between completers and non-completers
   - Action: Sensitivity analyses under MNAR if dropout related to outcome

4. **No Measurement Error:** Outcomes measured without substantial error
   - Usually reasonable assumption for clinical assessments

**Diagnostics:**
- Residual plots by time point and treatment
- Influence diagnostics
- Covariance structure selection criteria
- Convergence checks

"""

    def _generate_software_section(self) -> str:
        """Generate software implementation section"""
        return """
### Software Implementation

**SAS:**
```sas
proc mixed data=analysis_data method=reml;
    class USUBJID TRT01P AVISIT STRATA1;
    model CHG = BASE BASE*AVISIT TRT01P AVISIT TRT01P*AVISIT STRATA1 / ddfm=kr solution;
    repeated AVISIT / subject=USUBJID type=un rcorr;
    lsmeans TRT01P*AVISIT / pdiff=all cl alpha=0.05 slice=AVISIT;
run;
```

**R:**
```r
library(nlme)
library(emmeans)

# Fit MMRM
model <- lme(
    CHG ~ BASE + BASE:AVISIT + TRT01P * AVISIT + STRATA1,
    random = ~ 1 | USUBJID,
    correlation = corSymm(form = ~ as.numeric(AVISIT) | USUBJID),
    weights = varIdent(form = ~ 1 | AVISIT),
    data = analysis_data,
    method = "REML",
    na.action = na.omit
)

# Least squares means
lsm <- emmeans(model, ~ TRT01P | AVISIT)

# Contrasts
contrasts <- contrast(lsm, "trt.vs.ctrl", by = "AVISIT")
```

**Key Parameters:**
- `method=reml`: REML estimation
- `ddfm=kr`: Kenward-Roger degrees of freedom
- `type=un`: Unstructured covariance
- `lsmeans`: Least squares means and contrasts

"""

    def generate_gee_methodology(self, spec: GEESpec) -> str:
        """Generate GEE methodology text"""
        text = f"""
## GEE Analysis

### Method: Generalized Estimating Equations

GEE will be used to estimate population-average treatment effects over time,
accounting for within-subject correlation.

**Model:**
- Outcome distribution: {spec.outcome_distribution}
- Link function: {spec.link_function}
- Working correlation: {spec.working_correlation}

"""

        if spec.robust_variance:
            text += """
**Variance Estimation:**
Robust (sandwich/empirical) variance estimator will be used, which provides
consistent standard errors even if the working correlation structure is misspecified.
"""

        text += """
**Advantages of GEE:**
- Focus on population-average effects (marginal model)
- Robust to working correlation misspecification
- Handles various outcome distributions

**Limitations:**
- Assumes data are MCAR (missing completely at random)
- Less efficient than likelihood methods under MAR
- Interpretation: population-average, not subject-specific

**When to Use GEE:**
- When population-average effects are of interest
- For binary or count outcomes with repeated measures
- When missingness is believed to be MCAR

"""

        return text

    def generate_sas_code(self, spec: MMRMSpec) -> str:
        """Generate SAS code for MMRM"""
        baseline_term = f"{spec.baseline_variable} {spec.baseline_variable}*{spec.time_variable}" if spec.baseline_adjustment else ""
        interaction_term = f"{spec.treatment_variable}*{spec.time_variable}" if spec.treatment_by_time_interaction else ""
        covariates = " ".join(spec.covariates + spec.stratification_factors)

        return f"""
/* Mixed Model for Repeated Measures (MMRM) */

proc mixed data=adam_data method={'reml' if spec.reml else 'ml'};
    class USUBJID {spec.treatment_variable} {spec.time_variable} {' '.join(spec.stratification_factors)};

    model {spec.outcome_variable} = {baseline_term} {spec.treatment_variable} {spec.time_variable}
          {interaction_term} {covariates} / ddfm={'kr' if spec.degrees_of_freedom_method == 'Kenward-Roger' else 'sat'} solution;

    repeated {spec.time_variable} / subject=USUBJID type={spec.covariance_structure.value.split('(')[1].rstrip(')')} rcorr;

    /* Least squares means at each time point */
    lsmeans {spec.treatment_variable}*{spec.time_variable} / pdiff=all cl alpha={spec.alpha} slice={spec.time_variable};

    /* Store estimates */
    ods output LSMeans=lsmeans Diffs=diffs Tests3=tests;

    title "MMRM Analysis - {spec.outcome_variable}";
run;

/* Focus on primary time point */
%if "{spec.primary_time_point}" ne "" %then %do;
    proc mixed data=adam_data method={'reml' if spec.reml else 'ml'};
        where {spec.time_variable} = "{spec.primary_time_point}";
        class {spec.treatment_variable} {' '.join(spec.stratification_factors)};
        model {spec.outcome_variable} = {spec.baseline_variable} {spec.treatment_variable} {covariates};
        lsmeans {spec.treatment_variable} / pdiff=all cl;
        title "Analysis at Primary Time Point: {spec.primary_time_point}";
    run;
%end;
"""


# Singleton instance
_repeated_measures_service: Optional[RepeatedMeasuresService] = None


def get_repeated_measures_service() -> RepeatedMeasuresService:
    """
    Get repeated measures service instance.

    Returns:
        RepeatedMeasuresService instance
    """
    global _repeated_measures_service

    if _repeated_measures_service is None:
        _repeated_measures_service = RepeatedMeasuresService()

    return _repeated_measures_service
