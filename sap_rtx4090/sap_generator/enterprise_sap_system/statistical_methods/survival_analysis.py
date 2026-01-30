"""
Advanced Survival Analysis Methods
===================================

Statistical methods for time-to-event endpoints in oncology trials.

Methods:
- Kaplan-Meier estimation
- Log-rank test
- Cox proportional hazards
- Weighted log-rank tests (Fleming-Harrington)
- Restricted mean survival time (RMST)
- Milestone analysis
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SurvivalEndpoint(Enum):
    """Time-to-event endpoint types"""
    OVERALL_SURVIVAL = "Overall Survival"
    PROGRESSION_FREE_SURVIVAL = "Progression-Free Survival"
    DISEASE_FREE_SURVIVAL = "Disease-Free Survival"
    EVENT_FREE_SURVIVAL = "Event-Free Survival"
    TIME_TO_PROGRESSION = "Time to Progression"
    DURATION_OF_RESPONSE = "Duration of Response"


class CensoringRule(Enum):
    """Censoring rules for time-to-event analysis"""
    LAST_ASSESSMENT = "Last tumor assessment"
    LAST_CONTACT = "Last known alive date"
    DATA_CUTOFF = "Data cutoff date"
    STUDY_DISCONTINUATION = "Study discontinuation"


@dataclass
class SurvivalAnalysisSpec:
    """
    Specification for survival analysis in SAP.

    Defines all parameters for time-to-event analysis.
    """
    endpoint_name: str
    endpoint_type: SurvivalEndpoint

    # Definition
    start_date_variable: str = "RANDDT"  # Randomization date
    event_date_variable: str = ""         # Event date variable
    censor_date_variable: str = ""        # Censoring date variable

    # Event definition
    event_indicator: str = "CNSR"         # 0=event, 1=censored
    event_description: str = ""

    # Censoring rules
    censoring_rules: List[str] = field(default_factory=list)

    # Primary analysis method
    primary_method: str = "Cox proportional hazards"

    # Hazard ratio estimation
    estimate_hazard_ratio: bool = True
    hr_confidence_level: float = 0.95

    # Stratification
    stratification_factors: List[str] = field(default_factory=list)

    # Additional analyses
    perform_log_rank: bool = True
    perform_milestone: bool = False
    milestone_times: List[int] = field(default_factory=list)  # e.g., [12, 24, 36] months
    perform_rmst: bool = False
    rmst_timepoint: Optional[int] = None

    # Proportional hazards assumption
    test_ph_assumption: bool = True
    ph_test_methods: List[str] = field(default_factory=lambda: ["Schoenfeld residuals", "Time-varying covariate"])

    # Subgroup analysis
    subgroup_variables: List[str] = field(default_factory=list)

    # Sensitivity analyses
    sensitivity_analyses: List[str] = field(default_factory=list)


@dataclass
class KaplanMeierSpec:
    """Kaplan-Meier analysis specification"""
    # Estimation
    confidence_level: float = 0.95
    confidence_method: str = "Greenwood"  # or "log-log"

    # Median survival
    estimate_median: bool = True
    median_confidence_method: str = "Brookmeyer-Crowley"

    # Survival rates
    estimate_rates_at: List[int] = field(default_factory=list)  # Time points for rates

    # Presentation
    plot_survival_curve: bool = True
    plot_confidence_bands: bool = True
    plot_risk_table: bool = True
    plot_censoring_marks: bool = True


@dataclass
class LogRankTestSpec:
    """Log-rank test specification"""
    # Test type
    test_type: str = "standard"  # "standard", "stratified", "weighted"

    # Stratification
    stratification_factors: List[str] = field(default_factory=list)

    # Weighted tests (Fleming-Harrington family)
    use_weighted_test: bool = False
    weight_function: str = ""  # e.g., "FH(0,1)" for early differences, "FH(1,0)" for late
    rho: float = 0.0           # Fleming-Harrington rho parameter
    gamma: float = 0.0         # Fleming-Harrington gamma parameter

    # Significance level
    alpha: float = 0.05
    one_sided: bool = False


@dataclass
class CoxModelSpec:
    """Cox proportional hazards model specification"""
    # Treatment effect
    treatment_variable: str = "TRT01P"
    reference_group: str = ""

    # Covariates
    covariates: List[str] = field(default_factory=list)
    stratification_factors: List[str] = field(default_factory=list)

    # Model building
    model_selection_method: str = "Forward"  # "Forward", "Backward", "Stepwise", "None"
    entry_criterion: float = 0.10
    stay_criterion: float = 0.05

    # Hazard ratio
    confidence_level: float = 0.95

    # Interactions
    test_interactions: List[str] = field(default_factory=list)  # e.g., ["TRT01P*AGEGR1"]

    # Diagnostics
    check_linearity: bool = True  # For continuous covariates
    check_proportionality: bool = True

    # Presentation
    forest_plot: bool = True


@dataclass
class RestrictedMeanSurvivalTimeSpec:
    """RMST analysis specification"""
    # Time restriction
    restriction_time: int = 24  # months

    # Estimation method
    method: str = "pseudo-values"  # or "direct"

    # Comparison
    compare_arms: bool = True
    difference_confidence_level: float = 0.95

    # Interpretation
    clinical_importance_threshold: Optional[float] = None  # months


class SurvivalAnalysisService:
    """
    Service for survival analysis specifications in SAP.

    Generates standardized methodology text for time-to-event analyses.
    """

    def __init__(self):
        """Initialize survival analysis service"""
        pass

    def generate_km_methodology(self, spec: KaplanMeierSpec) -> str:
        """
        Generate Kaplan-Meier methodology text.

        Args:
            spec: KM specification

        Returns:
            Formatted methodology text
        """
        text = """
### Kaplan-Meier Analysis

The distribution of time-to-event will be estimated using the Kaplan-Meier (product-limit) method [Kaplan and Meier, 1958].

**Survival Function Estimation:**
- Survival curves will be plotted by treatment group
"""

        if spec.plot_confidence_bands:
            text += f"- {spec.confidence_level*100:.0f}% confidence intervals will be computed using the {spec.confidence_method} method\n"

        if spec.estimate_median:
            text += f"- Median survival time and {spec.confidence_level*100:.0f}% confidence interval will be estimated using the {spec.median_confidence_method} method\n"

        if spec.estimate_rates_at:
            times_str = ", ".join([str(t) for t in spec.estimate_rates_at])
            text += f"- Survival rates at {times_str} months will be estimated with {spec.confidence_level*100:.0f}% confidence intervals\n"

        text += """
**Censoring:**
- Censored observations will be indicated on survival plots
- Number at risk will be displayed at regular intervals
"""

        return text.strip()

    def generate_logrank_methodology(self, spec: LogRankTestSpec) -> str:
        """
        Generate log-rank test methodology.

        Args:
            spec: Log-rank specification

        Returns:
            Formatted methodology text
        """
        text = """
### Log-Rank Test

Treatment groups will be compared using"""

        if spec.test_type == "stratified":
            text += " a stratified log-rank test"
            if spec.stratification_factors:
                factors_str = ", ".join(spec.stratification_factors)
                text += f", stratified by {factors_str}"
        elif spec.use_weighted_test:
            text += f" a weighted log-rank test (Fleming-Harrington family with ρ={spec.rho}, γ={spec.gamma})"
        else:
            text += " the log-rank test"

        text += ".\n\n"

        if spec.one_sided:
            text += f"**Statistical Test:** One-sided test at α={spec.alpha} level\n"
        else:
            text += f"**Statistical Test:** Two-sided test at α={spec.alpha} level\n"

        text += """
**Null Hypothesis:** The survival distributions are the same in both treatment groups

**Alternative Hypothesis:** The survival distributions differ between treatment groups

**Test Statistic:** The log-rank statistic follows a chi-square distribution with 1 degree of freedom under the null hypothesis
"""

        if spec.use_weighted_test:
            text += f"""
**Weighted Test Rationale:**
The Fleming-Harrington weighted log-rank test with ρ={spec.rho} and γ={spec.gamma} is used to weight"""

            if spec.rho > 0 and spec.gamma == 0:
                text += " early differences in survival more heavily, appropriate when treatment effects are expected to be greatest early in follow-up.\n"
            elif spec.rho == 0 and spec.gamma > 0:
                text += " late differences in survival more heavily, appropriate for treatments with delayed effects.\n"
            else:
                text += " differences across the survival curve.\n"

        return text.strip()

    def generate_cox_methodology(self, spec: CoxModelSpec) -> str:
        """
        Generate Cox proportional hazards methodology.

        Args:
            spec: Cox model specification

        Returns:
            Formatted methodology text
        """
        text = """
### Cox Proportional Hazards Model

Treatment effect will be estimated using the Cox proportional hazards regression model [Cox, 1972].

**Model Specification:**
"""

        # Treatment variable
        text += f"- Treatment group ({spec.treatment_variable}) as the primary factor\n"

        # Covariates
        if spec.covariates:
            covariates_str = ", ".join(spec.covariates)
            text += f"- Covariates: {covariates_str}\n"

        # Stratification
        if spec.stratification_factors:
            factors_str = ", ".join(spec.stratification_factors)
            text += f"- Stratified by: {factors_str}\n"

        text += """
**Hazard Ratio:**
- The hazard ratio (HR) and """
        text += f"{spec.confidence_level*100:.0f}% confidence interval will be estimated\n"
        text += "- HR < 1 indicates reduced hazard (improved survival) in the experimental arm\n"

        if spec.check_proportionality:
            text += """
**Proportional Hazards Assumption:**
The proportional hazards assumption will be assessed using:
- Graphical assessment: Log-log survival plots
- Statistical test: Schoenfeld residuals test
- Time-varying covariate approach

If the proportional hazards assumption is violated, stratified analysis or time-varying coefficient models will be considered.
"""

        if spec.test_interactions:
            interactions_str = ", ".join(spec.test_interactions)
            text += f"""
**Interaction Testing:**
The following interaction terms will be tested: {interactions_str}

Interactions will be considered significant if p < 0.10.
"""

        if spec.forest_plot:
            text += """
**Forest Plot:**
A forest plot will be presented showing hazard ratios and confidence intervals for treatment effects overall and within subgroups.
"""

        return text.strip()

    def generate_rmst_methodology(self, spec: RestrictedMeanSurvivalTimeSpec) -> str:
        """
        Generate RMST methodology.

        Args:
            spec: RMST specification

        Returns:
            Formatted methodology text
        """
        text = f"""
### Restricted Mean Survival Time (RMST)

As a supplementary analysis, the restricted mean survival time up to {spec.restriction_time} months will be calculated.

**Definition:**
RMST is the area under the survival curve up to a specified time point (τ = {spec.restriction_time} months). It represents the average survival time for subjects followed up to τ months.

**Method:**
- RMST will be estimated using the {spec.method} method
- {spec.difference_confidence_level*100:.0f}% confidence intervals will be computed
"""

        if spec.compare_arms:
            text += f"""
**Treatment Comparison:**
- The difference in RMST between treatment arms will be estimated
- {spec.difference_confidence_level*100:.0f}% confidence interval for the difference will be provided
- A positive difference indicates longer average survival in the experimental arm
"""

        if spec.clinical_importance_threshold:
            text += f"""
**Clinical Interpretation:**
A difference of ≥{spec.clinical_importance_threshold} months in RMST is considered clinically meaningful.
"""

        text += """
**Rationale:**
RMST provides an alternative summary measure that does not require the proportional hazards assumption and is easily interpretable as average survival time.

**Reference:**
Royston P, Parmar MK. Restricted mean survival time: an alternative to the hazard ratio for the design and analysis of randomized trials with a time-to-event outcome. BMC Med Res Methodol. 2013;13:152.
"""

        return text.strip()

    def generate_complete_survival_section(
        self,
        endpoint_spec: SurvivalAnalysisSpec,
        km_spec: KaplanMeierSpec,
        logrank_spec: LogRankTestSpec,
        cox_spec: CoxModelSpec
    ) -> str:
        """
        Generate complete survival analysis section for SAP.

        Args:
            endpoint_spec: Overall endpoint specification
            km_spec: Kaplan-Meier specification
            logrank_spec: Log-rank test specification
            cox_spec: Cox model specification

        Returns:
            Complete formatted section
        """
        section = f"""
## {endpoint_spec.endpoint_name} Analysis

### Endpoint Definition

**{endpoint_spec.endpoint_name}** is defined as the time from {endpoint_spec.start_date_variable.lower().replace('dt', ' date')} to {endpoint_spec.event_description}.

**Event:**
{endpoint_spec.event_description}

**Censoring Rules:**
"""
        for rule in endpoint_spec.censoring_rules:
            section += f"- {rule}\n"

        section += "\n"

        # Add method sections
        section += self.generate_km_methodology(km_spec) + "\n\n"
        section += self.generate_logrank_methodology(logrank_spec) + "\n\n"
        section += self.generate_cox_methodology(cox_spec) + "\n\n"

        # Add milestone if specified
        if endpoint_spec.perform_milestone and endpoint_spec.milestone_times:
            section += self._generate_milestone_text(endpoint_spec.milestone_times) + "\n\n"

        # Add RMST if specified
        if endpoint_spec.perform_rmst and endpoint_spec.rmst_timepoint:
            rmst_spec = RestrictedMeanSurvivalTimeSpec(restriction_time=endpoint_spec.rmst_timepoint)
            section += self.generate_rmst_methodology(rmst_spec) + "\n\n"

        return section.strip()

    def _generate_milestone_text(self, milestone_times: List[int]) -> str:
        """Generate milestone analysis text"""
        times_str = ", ".join([f"{t}-month" for t in milestone_times])
        return f"""
### Milestone Analysis

Survival rates at {times_str} will be estimated from the Kaplan-Meier curves with 95% confidence intervals. The difference in survival rates between treatment arms will be tested using the Z-test.
"""


# Singleton instance
_survival_service: Optional[SurvivalAnalysisService] = None


def get_survival_analysis_service() -> SurvivalAnalysisService:
    """
    Get survival analysis service instance.

    Returns:
        SurvivalAnalysisService instance
    """
    global _survival_service

    if _survival_service is None:
        _survival_service = SurvivalAnalysisService()

    return _survival_service
