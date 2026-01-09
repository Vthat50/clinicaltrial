"""
Sample Size and Power Calculation Methods
==========================================

Methods for sample size determination and power analysis for clinical trials.

Required by:
- ICH E9: Statistical Principles for Clinical Trials (Section 3.5)
- FDA Guidance: Various endpoint-specific guidances

Methods:
- Time-to-event (survival) endpoints
- Binary endpoints (response rates)
- Continuous endpoints
- Non-inferiority designs
- Equivalence designs
- Group sequential designs

Key parameters:
- Type I error (alpha)
- Type II error (beta) / Power (1-beta)
- Effect size
- Dropout/loss to follow-up rates
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


class DesignType(Enum):
    """Clinical trial design types"""
    SUPERIORITY = "Superiority"
    NON_INFERIORITY = "Non-Inferiority"
    EQUIVALENCE = "Equivalence"
    FIXED_SAMPLE = "Fixed Sample"
    GROUP_SEQUENTIAL = "Group Sequential"
    ADAPTIVE = "Adaptive"


class EndpointClass(Enum):
    """Endpoint classification for sample size"""
    TIME_TO_EVENT = "Time-to-Event"
    BINARY = "Binary"
    CONTINUOUS = "Continuous"
    COUNT = "Count"
    ORDINAL = "Ordinal"


@dataclass
class PowerParameters:
    """Common power calculation parameters"""
    alpha: float = 0.025            # One-sided
    beta: float = 0.10              # Type II error (power = 1-beta = 90%)
    power: float = 0.90             # Derived from beta
    one_sided: bool = True

    def __post_init__(self):
        """Ensure power and beta are consistent"""
        if self.power != 1.0 - self.beta:
            self.power = 1.0 - self.beta


@dataclass
class SurvivalSampleSize:
    """
    Sample size calculation for time-to-event endpoints.

    Based on log-rank test or Cox proportional hazards model.
    """
    # Design parameters
    power_params: PowerParameters = field(default_factory=PowerParameters)

    # Effect size
    hazard_ratio: float = 0.70      # HR for experimental vs control

    # Control group parameters
    control_median_survival: float = 12.0  # months

    # Study design
    accrual_period: float = 24.0    # months
    follow_up_period: float = 12.0  # months after last patient enrolled
    accrual_pattern: str = "uniform"  # "uniform" or "exponential"

    # Dropout
    annual_dropout_rate: float = 0.05

    # Allocation
    allocation_ratio: float = 1.0   # Experimental:Control

    # Stratification
    num_strata: int = 1
    stratified: bool = False

    # Results (calculated)
    required_events: int = 0
    required_sample_size: int = 0
    probability_of_event: float = 0.0

    def calculate_events(self) -> int:
        """
        Calculate required number of events using Schoenfeld formula.

        Formula: d = (Z_α + Z_β)² × (r+1)² / [r × (log(HR))²]
        where r = allocation ratio

        Returns:
            Required number of events
        """
        # Z-scores
        z_alpha = self._inverse_normal(1 - self.power_params.alpha)
        z_beta = self._inverse_normal(self.power_params.power)

        r = self.allocation_ratio
        hr = self.hazard_ratio

        # Schoenfeld formula
        numerator = (z_alpha + z_beta) ** 2 * (r + 1) ** 2
        denominator = r * (math.log(hr)) ** 2

        events = numerator / denominator

        # Adjust for stratification (small inflation)
        if self.stratified:
            events *= 1.02

        self.required_events = math.ceil(events)
        return self.required_events

    def calculate_sample_size(self) -> int:
        """
        Calculate required sample size to achieve required events.

        Accounts for:
        - Accrual pattern
        - Follow-up time
        - Dropout rate
        - Event probability

        Returns:
            Required sample size
        """
        # First calculate required events
        if self.required_events == 0:
            self.calculate_events()

        # Calculate probability of event for each patient
        # This depends on survival distribution, accrual, and follow-up
        self.probability_of_event = self._calculate_event_probability()

        # Sample size = events / P(event)
        # Add inflation for dropout
        dropout_inflation = 1.0 / (1.0 - self._cumulative_dropout_rate())

        sample_size = self.required_events / self.probability_of_event * dropout_inflation

        # Adjust for allocation ratio
        total = sample_size * (1 + self.allocation_ratio)

        self.required_sample_size = math.ceil(total)
        return self.required_sample_size

    def _calculate_event_probability(self) -> float:
        """
        Calculate average probability of event per patient.

        Uses exponential survival model and uniform accrual.
        """
        # Control group hazard rate
        control_lambda = math.log(2) / self.control_median_survival

        # Experimental group hazard rate
        exp_lambda = control_lambda * self.hazard_ratio

        # Average hazard
        r = self.allocation_ratio
        avg_lambda = (control_lambda + r * exp_lambda) / (1 + r)

        # Average follow-up time per patient (with uniform accrual)
        avg_follow_up = self.follow_up_period + self.accrual_period / 2.0

        # Probability of event = 1 - S(t)
        prob_event = 1.0 - math.exp(-avg_lambda * avg_follow_up / 12.0)

        return prob_event

    def _cumulative_dropout_rate(self) -> float:
        """Calculate cumulative dropout probability"""
        study_duration = self.accrual_period + self.follow_up_period
        years = study_duration / 12.0

        # Assuming exponential dropout
        cum_dropout = 1.0 - math.exp(-self.annual_dropout_rate * years)
        return min(cum_dropout, 0.30)  # Cap at 30%

    @staticmethod
    def _inverse_normal(p: float) -> float:
        """Approximate inverse normal CDF"""
        if p <= 0.5:
            return -SurvivalSampleSize._inverse_normal(1 - p)

        # Simplified approximation
        t = math.sqrt(-2 * math.log(1 - p))
        z = t - (2.30753 + 0.27061 * t) / (1 + 0.99229 * t + 0.04481 * t ** 2)
        return z


@dataclass
class BinarySampleSize:
    """
    Sample size calculation for binary endpoints (e.g., ORR).

    Based on two-sample test of proportions.
    """
    # Design parameters
    power_params: PowerParameters = field(default_factory=PowerParameters)

    # Effect size
    control_rate: float = 0.10      # Control response rate
    experimental_rate: float = 0.25  # Experimental response rate

    # Design
    allocation_ratio: float = 1.0

    # Dropout
    dropout_rate: float = 0.10

    # Results
    required_sample_size: int = 0
    risk_difference: float = 0.0
    odds_ratio: float = 0.0

    def calculate_sample_size(self, method: str = "arcsin") -> int:
        """
        Calculate sample size for two proportions.

        Args:
            method: "arcsin", "normal", or "exact"

        Returns:
            Required sample size per group (control)
        """
        p1 = self.control_rate
        p2 = self.experimental_rate
        r = self.allocation_ratio

        self.risk_difference = p2 - p1
        self.odds_ratio = (p2 / (1 - p2)) / (p1 / (1 - p1)) if p1 < 1 else float('inf')

        if method == "arcsin":
            # Arcsin transformation (stabilizes variance)
            z_alpha = self._inverse_normal(1 - self.power_params.alpha)
            z_beta = self._inverse_normal(self.power_params.power)

            theta1 = math.asin(math.sqrt(p1))
            theta2 = math.asin(math.sqrt(p2))

            n_control = ((z_alpha + z_beta) ** 2 * (1 + r)) / (r * 4 * (theta2 - theta1) ** 2)

        elif method == "normal":
            # Normal approximation (Fleiss)
            z_alpha = self._inverse_normal(1 - self.power_params.alpha)
            z_beta = self._inverse_normal(self.power_params.power)

            p_avg = (p1 + r * p2) / (1 + r)

            numerator = (z_alpha * math.sqrt(p_avg * (1 - p_avg) * (1 + 1/r)) +
                        z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2) / r)) ** 2
            denominator = (p2 - p1) ** 2

            n_control = numerator / denominator

        else:
            # Simplified approximation
            z_alpha = self._inverse_normal(1 - self.power_params.alpha)
            z_beta = self._inverse_normal(self.power_params.power)

            n_control = ((z_alpha + z_beta) ** 2 *
                        (p1 * (1 - p1) + p2 * (1 - p2) / r)) / (p2 - p1) ** 2

        # Adjust for dropout
        n_control = n_control / (1 - self.dropout_rate)

        # Total sample size
        self.required_sample_size = math.ceil(n_control * (1 + r))

        return self.required_sample_size

    @staticmethod
    def _inverse_normal(p: float) -> float:
        """Approximate inverse normal CDF"""
        if p <= 0.5:
            return -BinarySampleSize._inverse_normal(1 - p)

        t = math.sqrt(-2 * math.log(1 - p))
        z = t - (2.30753 + 0.27061 * t) / (1 + 0.99229 * t + 0.04481 * t ** 2)
        return z


@dataclass
class ContinuousSampleSize:
    """
    Sample size for continuous endpoints.

    Based on two-sample t-test.
    """
    power_params: PowerParameters = field(default_factory=PowerParameters)

    # Effect size
    mean_difference: float = 10.0   # Expected difference in means
    common_sd: float = 25.0         # Common standard deviation
    standardized_effect: float = 0.0  # Cohen's d

    # Design
    allocation_ratio: float = 1.0
    dropout_rate: float = 0.10

    # Results
    required_sample_size: int = 0

    def __post_init__(self):
        """Calculate standardized effect size"""
        if self.standardized_effect == 0.0 and self.common_sd > 0:
            self.standardized_effect = self.mean_difference / self.common_sd

    def calculate_sample_size(self) -> int:
        """
        Calculate sample size for two-sample t-test.

        Returns:
            Total required sample size
        """
        r = self.allocation_ratio
        delta = self.standardized_effect

        z_alpha = self._inverse_normal(1 - self.power_params.alpha)
        z_beta = self._inverse_normal(self.power_params.power)

        # Sample size per group (control)
        n_control = ((z_alpha + z_beta) ** 2 * (1 + 1/r)) / (delta ** 2)

        # Adjust for dropout
        n_control = n_control / (1 - self.dropout_rate)

        # Total
        self.required_sample_size = math.ceil(n_control * (1 + r))

        return self.required_sample_size

    @staticmethod
    def _inverse_normal(p: float) -> float:
        """Approximate inverse normal CDF"""
        if p <= 0.5:
            return -ContinuousSampleSize._inverse_normal(1 - p)

        t = math.sqrt(-2 * math.log(1 - p))
        z = t - (2.30753 + 0.27061 * t) / (1 + 0.99229 * t + 0.04481 * t ** 2)
        return z


@dataclass
class NonInferioritySampleSize:
    """
    Sample size for non-inferiority trials.

    Tests H0: experimental is inferior by margin δ vs H1: experimental is non-inferior
    """
    power_params: PowerParameters = field(default_factory=PowerParameters)

    # Non-inferiority margin
    ni_margin: float = 0.10         # For proportions (absolute difference)
    ni_margin_hr: float = 1.33      # For survival (hazard ratio)

    # Expected treatment effect
    expected_difference: float = 0.0  # Expected exp - control (for sample size)
    expected_hr: float = 1.0          # Expected HR

    # Endpoint type
    endpoint_type: EndpointClass = EndpointClass.BINARY

    # Other parameters (depend on endpoint)
    control_rate: float = 0.60      # For binary
    control_median: float = 12.0    # For survival

    allocation_ratio: float = 1.0
    dropout_rate: float = 0.10

    # Results
    required_sample_size: int = 0
    required_events: int = 0

    def calculate_sample_size(self) -> int:
        """Calculate sample size for non-inferiority"""

        if self.endpoint_type == EndpointClass.BINARY:
            return self._calculate_binary_ni()
        elif self.endpoint_type == EndpointClass.TIME_TO_EVENT:
            return self._calculate_survival_ni()
        else:
            logger.error(f"Endpoint type {self.endpoint_type} not supported for NI")
            return 0

    def _calculate_binary_ni(self) -> int:
        """Non-inferiority sample size for binary endpoint"""
        p1 = self.control_rate
        p2 = p1 + self.expected_difference  # Expected experimental rate
        delta = self.ni_margin
        r = self.allocation_ratio

        z_alpha = self._inverse_normal(1 - self.power_params.alpha)
        z_beta = self._inverse_normal(self.power_params.power)

        # Farrington-Manning method for NI
        p_bar = (p1 + r * p2) / (1 + r)
        p1_ni = p1
        p2_ni = p1 - delta  # Under H0 (at NI margin)
        p_bar_ni = (p1_ni + r * p2_ni) / (1 + r)

        numerator = (z_alpha * math.sqrt(p_bar_ni * (1 - p_bar_ni) * (1 + 1/r)) +
                    z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2) / r)) ** 2

        denominator = (p2 - p1 + delta) ** 2

        n_control = numerator / denominator

        # Adjust for dropout
        n_control = n_control / (1 - self.dropout_rate)

        self.required_sample_size = math.ceil(n_control * (1 + r))
        return self.required_sample_size

    def _calculate_survival_ni(self) -> int:
        """Non-inferiority sample size for survival endpoint"""
        # Use log-rank test approach
        hr = self.expected_hr
        hr_ni = self.ni_margin_hr
        r = self.allocation_ratio

        z_alpha = self._inverse_normal(1 - self.power_params.alpha)
        z_beta = self._inverse_normal(self.power_params.power)

        # Events required
        numerator = (z_alpha + z_beta) ** 2 * (r + 1) ** 2
        denominator = r * (math.log(hr) - math.log(hr_ni)) ** 2

        self.required_events = math.ceil(numerator / denominator)

        # Convert to sample size (simplified - assumes ~80% event rate)
        self.required_sample_size = math.ceil(self.required_events / 0.80 * (1 + r))

        return self.required_sample_size

    @staticmethod
    def _inverse_normal(p: float) -> float:
        """Approximate inverse normal CDF"""
        if p <= 0.5:
            return -NonInferioritySampleSize._inverse_normal(1 - p)

        t = math.sqrt(-2 * math.log(1 - p))
        z = t - (2.30753 + 0.27061 * t) / (1 + 0.99229 * t + 0.04481 * t ** 2)
        return z


class SampleSizeService:
    """
    Service for sample size calculations and power analysis.

    Provides methods for calculating sample sizes and generating SAP text.
    """

    def __init__(self):
        """Initialize sample size service"""
        pass

    def generate_sample_size_section(
        self,
        endpoint_type: EndpointClass,
        design_type: DesignType,
        parameters: any  # SurvivalSampleSize, BinarySampleSize, etc.
    ) -> str:
        """
        Generate sample size section for SAP.

        Args:
            endpoint_type: Type of endpoint
            design_type: Type of design
            parameters: Calculation parameters

        Returns:
            Formatted SAP text
        """
        text = """
## Sample Size Determination

### Study Design

"""

        if design_type == DesignType.SUPERIORITY:
            text += f"This is a randomized, controlled **superiority trial** designed to demonstrate that the experimental treatment is superior to the control.\n\n"
        elif design_type == DesignType.NON_INFERIORITY:
            text += f"This is a randomized, controlled **non-inferiority trial** designed to demonstrate that the experimental treatment is not inferior to the control by more than a pre-specified margin.\n\n"

        text += self._generate_endpoint_specific_text(endpoint_type, parameters)
        text += self._generate_assumptions_table(parameters)
        text += self._generate_calculation_details(endpoint_type, parameters)
        text += self._generate_justification_section(parameters)

        return text.strip()

    def _generate_endpoint_specific_text(
        self,
        endpoint_type: EndpointClass,
        parameters: any
    ) -> str:
        """Generate endpoint-specific methodology"""

        if endpoint_type == EndpointClass.TIME_TO_EVENT:
            if isinstance(parameters, SurvivalSampleSize):
                return f"""
### Primary Endpoint

The primary endpoint is {parameters.__class__.__name__.replace('SampleSize', '').replace('Survival', 'time-to-event')},
analyzed using the log-rank test.

**Sample Size Calculation:**
The sample size is based on detecting a hazard ratio of {parameters.hazard_ratio} with
{parameters.power_params.power * 100:.0f}% power at a one-sided significance level of α = {parameters.power_params.alpha}.

"""

        elif endpoint_type == EndpointClass.BINARY:
            if isinstance(parameters, BinarySampleSize):
                return f"""
### Primary Endpoint

The primary endpoint is a binary outcome (response/non-response).

**Sample Size Calculation:**
The sample size is based on comparing response rates using a two-sample test of proportions.
The calculation assumes:
- Control group response rate: {parameters.control_rate * 100:.1f}%
- Experimental group response rate: {parameters.experimental_rate * 100:.1f}%
- Absolute difference: {parameters.risk_difference * 100:.1f} percentage points

"""

        return ""

    def _generate_assumptions_table(self, parameters: any) -> str:
        """Generate table of assumptions"""
        text = """
### Assumptions

| Parameter | Value | Rationale |
|-----------|-------|-----------|
"""

        if isinstance(parameters, SurvivalSampleSize):
            text += f"| Type I error (one-sided) | α = {parameters.power_params.alpha} | Standard for superiority trials |\n"
            text += f"| Power | {parameters.power_params.power * 100:.0f}% | Standard for Phase 3 trials |\n"
            text += f"| Hazard ratio | {parameters.hazard_ratio} | Based on Phase 2 data / literature |\n"
            text += f"| Control median survival | {parameters.control_median_survival} months | Based on historical data |\n"
            text += f"| Accrual period | {parameters.accrual_period} months | Feasibility assessment |\n"
            text += f"| Follow-up period | {parameters.follow_up_period} months | Sufficient for maturity |\n"
            text += f"| Dropout rate | {parameters.annual_dropout_rate * 100:.1f}% per year | Historical experience |\n"
            text += f"| Allocation ratio | {parameters.allocation_ratio}:1 | " + ("Balanced randomization |\n" if parameters.allocation_ratio == 1.0 else "Unbalanced for ethical/efficiency reasons |\n")

        elif isinstance(parameters, BinarySampleSize):
            text += f"| Type I error (one-sided) | α = {parameters.power_params.alpha} | Standard for superiority trials |\n"
            text += f"| Power | {parameters.power_params.power * 100:.0f}% | Standard for Phase 3 trials |\n"
            text += f"| Control response rate | {parameters.control_rate * 100:.1f}% | Based on historical data |\n"
            text += f"| Experimental response rate | {parameters.experimental_rate * 100:.1f}% | Target from Phase 2 |\n"
            text += f"| Dropout rate | {parameters.dropout_rate * 100:.1f}% | Expected discontinuation |\n"
            text += f"| Allocation ratio | {parameters.allocation_ratio}:1 | " + ("Balanced randomization |\n" if parameters.allocation_ratio == 1.0 else "Unbalanced |\n")

        text += "\n"
        return text

    def _generate_calculation_details(
        self,
        endpoint_type: EndpointClass,
        parameters: any
    ) -> str:
        """Generate calculation details and results"""
        text = """
### Sample Size Calculation

"""

        if isinstance(parameters, SurvivalSampleSize):
            # Calculate if not already done
            if parameters.required_events == 0:
                parameters.calculate_events()
            if parameters.required_sample_size == 0:
                parameters.calculate_sample_size()

            text += f"""
**Number of Events Required:** {parameters.required_events}

The required number of events was calculated using the Schoenfeld formula:

d = (Z_α + Z_β)² × (r+1)² / [r × (ln(HR))²]

where:
- Z_α = {self._get_z_value(1 - parameters.power_params.alpha):.3f} (one-sided α = {parameters.power_params.alpha})
- Z_β = {self._get_z_value(parameters.power_params.power):.3f} (power = {parameters.power_params.power * 100:.0f}%)
- r = {parameters.allocation_ratio} (allocation ratio)
- HR = {parameters.hazard_ratio} (hazard ratio)

**Total Sample Size:** {parameters.required_sample_size} subjects

The sample size accounts for:
- Average probability of event: {parameters.probability_of_event * 100:.1f}%
- Dropout rate: {parameters.annual_dropout_rate * 100:.1f}% per year
- Accrual and follow-up duration

**Randomization Allocation:**
- Experimental arm: {math.ceil(parameters.required_sample_size * parameters.allocation_ratio / (1 + parameters.allocation_ratio))} subjects
- Control arm: {math.floor(parameters.required_sample_size / (1 + parameters.allocation_ratio))} subjects

"""

        elif isinstance(parameters, BinarySampleSize):
            if parameters.required_sample_size == 0:
                parameters.calculate_sample_size()

            text += f"""
**Total Sample Size:** {parameters.required_sample_size} subjects

The sample size was calculated using a two-sample test of proportions with arcsin transformation
for improved accuracy.

**Key Quantities:**
- Risk difference: {parameters.risk_difference * 100:.1f} percentage points
- Odds ratio: {parameters.odds_ratio:.2f}

**Randomization Allocation:**
- Experimental arm: {math.ceil(parameters.required_sample_size * parameters.allocation_ratio / (1 + parameters.allocation_ratio))} subjects
- Control arm: {math.floor(parameters.required_sample_size / (1 + parameters.allocation_ratio))} subjects

"""

        return text

    def _generate_justification_section(self, parameters: any) -> str:
        """Generate justification for assumptions"""
        return """
### Justification of Assumptions

**Effect Size:**
The assumed treatment effect is based on Phase 2 clinical data and is considered clinically meaningful
by regulatory standards and clinical experts.

**Dropout Rate:**
The assumed dropout rate is conservative based on historical experience in similar trials.
All efforts will be made to minimize dropout through careful patient selection and follow-up procedures.

**Power:**
90% power is standard for confirmatory Phase 3 trials, providing high probability of detecting
the specified treatment effect if it truly exists.

**Significance Level:**
A one-sided α = 0.025 is standard for superiority trials where the direction of effect is specified a priori.

### Regulatory Considerations

This sample size calculation complies with:
- **ICH E9:** Statistical Principles for Clinical Trials (Section 3.5)
- **FDA Guidance:** Relevant endpoint-specific guidances

The sample size ensures adequate power to address the primary objective while balancing
ethical considerations and feasibility.
"""

    def _get_z_value(self, p: float) -> float:
        """Get Z-value for probability"""
        # Standard normal quantiles
        if abs(p - 0.975) < 0.001:
            return 1.96
        elif abs(p - 0.95) < 0.001:
            return 1.645
        elif abs(p - 0.90) < 0.001:
            return 1.282

        # Approximate
        if p <= 0.5:
            return -self._get_z_value(1 - p)

        t = math.sqrt(-2 * math.log(1 - p))
        return t - (2.30753 + 0.27061 * t) / (1 + 0.99229 * t + 0.04481 * t ** 2)


# Singleton instance
_sample_size_service: Optional[SampleSizeService] = None


def get_sample_size_service() -> SampleSizeService:
    """
    Get sample size service instance.

    Returns:
        SampleSizeService instance
    """
    global _sample_size_service

    if _sample_size_service is None:
        _sample_size_service = SampleSizeService()

    return _sample_size_service
