"""
Interim Analysis Specifications
================================

Framework for interim analyses in Phase 2/3 trials with data monitoring.

Required by:
- FDA Guidance: "Adaptive Designs for Clinical Trials of Drugs and Biologics" (2019)
- ICH E9: Statistical Principles for Clinical Trials (Section 4.5)

Methods:
- Group sequential designs
- Spending functions (O'Brien-Fleming, Pocock, Lan-DeMets)
- Alpha spending approach
- Stopping boundaries (efficacy, futility)
- Sample size re-estimation
- Conditional power calculations
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


class InterimType(Enum):
    """Types of interim analyses"""
    EFFICACY = "Efficacy"           # Early stopping for benefit
    FUTILITY = "Futility"           # Early stopping for lack of benefit
    EFFICACY_FUTILITY = "Efficacy and Futility"
    SAMPLE_SIZE_REESTIMATION = "Sample Size Re-estimation"
    ADAPTIVE = "Adaptive Design"


class SpendingFunction(Enum):
    """Alpha spending functions"""
    OBRIEN_FLEMING = "O'Brien-Fleming"
    POCOCK = "Pocock"
    HWANG_SHIH_DECANI = "Hwang-Shih-DeCani"
    KIM_DEMETS = "Kim-DeMets"
    CUSTOM = "Custom"


class StoppingRule(Enum):
    """Stopping rule types"""
    BINDING = "Binding"             # Must stop if boundary crossed
    NON_BINDING = "Non-binding"     # May continue despite boundary


@dataclass
class InterimAnalysis:
    """
    Specification for a single interim analysis.

    Represents one planned look at the data.
    """
    analysis_number: int            # 1, 2, 3, ...
    information_fraction: float     # Proportion of total information (0-1)

    # Timing
    planned_events: Optional[int] = None       # For time-to-event
    planned_sample_size: Optional[int] = None  # For fixed designs
    calendar_time: Optional[str] = None        # e.g., "12 months"

    # Boundaries
    efficacy_boundary: Optional[float] = None  # Z-score or p-value
    futility_boundary: Optional[float] = None

    # Alpha spent
    alpha_spent_cumulative: float = 0.0
    alpha_spent_incremental: float = 0.0

    # Decisions
    test_efficacy: bool = True
    test_futility: bool = False
    allow_sample_size_increase: bool = False

    # DMC recommendations
    possible_actions: List[str] = field(default_factory=lambda: [
        "Continue as planned",
        "Stop for efficacy",
        "Stop for futility",
        "Modify sample size"
    ])


@dataclass
class GroupSequentialDesign:
    """
    Complete group sequential design specification.

    Defines multiple interim analyses with alpha spending control.
    """
    # Design parameters
    total_analyses: int = 2              # Including final
    one_sided_alpha: float = 0.025
    power: float = 0.90

    # Information times
    information_fractions: List[float] = field(default_factory=list)

    # Spending function
    efficacy_spending: SpendingFunction = SpendingFunction.OBRIEN_FLEMING
    futility_spending: SpendingFunction = SpendingFunction.POCOCK

    # Spending function parameters
    efficacy_spending_param: Optional[float] = None  # e.g., gamma for HSD
    futility_spending_param: Optional[float] = None

    # Stopping rules
    efficacy_stopping: StoppingRule = StoppingRule.NON_BINDING
    futility_stopping: StoppingRule = StoppingRule.NON_BINDING

    # Interim analyses
    interim_analyses: List[InterimAnalysis] = field(default_factory=list)

    # Sample size inflation
    inflation_factor: float = 1.0  # Multiplier due to interim analyses

    def calculate_boundaries(self):
        """Calculate stopping boundaries for all analyses"""
        if not self.information_fractions:
            # Default: equally spaced
            self.information_fractions = [
                (i + 1) / self.total_analyses
                for i in range(self.total_analyses)
            ]

        # Calculate alpha spending at each analysis
        alpha_spending = self._calculate_alpha_spending(
            self.information_fractions,
            self.efficacy_spending,
            self.one_sided_alpha,
            self.efficacy_spending_param
        )

        # Calculate Z-score boundaries
        boundaries = self._spending_to_boundaries(
            alpha_spending,
            self.information_fractions
        )

        # Create interim analysis objects
        self.interim_analyses = []
        for i, (info_frac, boundary, alpha) in enumerate(
            zip(self.information_fractions, boundaries, alpha_spending), 1
        ):
            analysis = InterimAnalysis(
                analysis_number=i,
                information_fraction=info_frac,
                efficacy_boundary=boundary,
                alpha_spent_cumulative=alpha,
                alpha_spent_incremental=alpha - (alpha_spending[i-2] if i > 1 else 0)
            )
            self.interim_analyses.append(analysis)

    def _calculate_alpha_spending(
        self,
        info_fractions: List[float],
        spending_func: SpendingFunction,
        total_alpha: float,
        param: Optional[float] = None
    ) -> List[float]:
        """Calculate cumulative alpha spent at each analysis"""
        alpha_spent = []

        for t in info_fractions:
            if spending_func == SpendingFunction.OBRIEN_FLEMING:
                # O'Brien-Fleming: alpha(t) = 2 - 2*Phi(Z_alpha / sqrt(t))
                z_alpha = self._inverse_normal(1 - total_alpha)
                alpha_t = 2 * (1 - self._normal_cdf(z_alpha / math.sqrt(t)))

            elif spending_func == SpendingFunction.POCOCK:
                # Pocock: alpha(t) = alpha * log(1 + (e-1)*t)
                alpha_t = total_alpha * math.log(1 + (math.e - 1) * t)

            elif spending_func == SpendingFunction.HWANG_SHIH_DECANI:
                # HSD: alpha(t) = alpha * (1 - exp(-gamma*t)) / (1 - exp(-gamma))
                gamma = param if param else 1.0
                if abs(gamma) < 0.001:
                    alpha_t = total_alpha * t
                else:
                    alpha_t = total_alpha * (1 - math.exp(-gamma * t)) / (1 - math.exp(-gamma))

            else:
                # Linear spending (default)
                alpha_t = total_alpha * t

            alpha_spent.append(min(alpha_t, total_alpha))

        return alpha_spent

    def _spending_to_boundaries(
        self,
        alpha_spending: List[float],
        info_fractions: List[float]
    ) -> List[float]:
        """Convert alpha spending to Z-score boundaries"""
        boundaries = []

        for i, (alpha_cum, t) in enumerate(zip(alpha_spending, info_fractions)):
            # Incremental alpha for this analysis
            alpha_inc = alpha_cum - (alpha_spending[i-1] if i > 0 else 0)

            # Z-score boundary
            z = self._inverse_normal(1 - alpha_inc)
            boundaries.append(z)

        return boundaries

    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Standard normal CDF approximation"""
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

    @staticmethod
    def _inverse_normal(p: float) -> float:
        """Inverse normal CDF (approximate)"""
        if p <= 0 or p >= 1:
            raise ValueError("p must be between 0 and 1")

        # Approximation for standard normal quantile
        # This is a simplified version; production would use scipy.stats
        if p == 0.5:
            return 0.0

        # Rough approximation
        if p < 0.5:
            return -InterimAnalysisService._approx_quantile(1 - p)
        else:
            return InterimAnalysisService._approx_quantile(p)

    @staticmethod
    def _approx_quantile(p: float) -> float:
        """Approximation of standard normal quantile"""
        # Simplified - production would use exact algorithm
        t = math.sqrt(-2 * math.log(1 - p))
        return t - (2.30753 + 0.27061 * t) / (1 + 0.99229 * t + 0.04481 * t * t)


@dataclass
class ConditionalPowerSpec:
    """
    Specification for conditional power calculations.

    Conditional power: probability of rejecting H0 at final analysis
    given current data and assumptions about remaining data.
    """
    # Current information
    current_z_statistic: float = 0.0
    current_information_fraction: float = 0.5

    # Assumptions for remaining data
    assumed_treatment_effect: Optional[float] = None  # If None, use observed
    assume_null: bool = False                          # For futility assessment

    # Thresholds
    favorable_threshold: float = 0.80   # CP ≥ 80% considered favorable
    unfavorable_threshold: float = 0.20  # CP < 20% considered futile

    def calculate_conditional_power(self) -> float:
        """
        Calculate conditional power.

        Returns:
            Conditional power (0-1)
        """
        if self.assume_null:
            # Under null hypothesis
            drift = 0.0
        elif self.assumed_treatment_effect is not None:
            # Use specified effect
            drift = self.assumed_treatment_effect
        else:
            # Use observed effect
            drift = self.current_z_statistic / math.sqrt(self.current_information_fraction)

        # Calculate conditional power
        # CP = Φ(Z_α - (θ̂ - θ_1)*sqrt(I))
        remaining_info = 1.0 - self.current_information_fraction

        z_alpha = 1.96  # Two-sided 0.05
        z_current = self.current_z_statistic

        # Conditional power calculation
        cp_z = z_current + drift * math.sqrt(remaining_info) - z_alpha
        cp = self._normal_cdf(cp_z)

        return max(0.0, min(1.0, cp))

    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Standard normal CDF"""
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


@dataclass
class SampleSizeReestimation:
    """
    Sample size re-estimation specification.

    Allows adjustment of sample size based on interim data.
    """
    # Triggers
    reestimation_at_info_fraction: float = 0.5

    # Parameters to re-estimate
    reestimate_effect_size: bool = True
    reestimate_variance: bool = True
    reestimate_event_rate: bool = False

    # Constraints
    max_sample_size_increase: float = 0.5  # Max 50% increase
    min_conditional_power: float = 0.80    # Target conditional power

    # Blinding
    maintain_treatment_blinding: bool = True  # Use pooled estimates only

    # Decision rules
    decision_rules: List[str] = field(default_factory=list)


class InterimAnalysisService:
    """
    Service for interim analysis specifications.

    Provides methods for generating SAP text and analysis specifications.
    """

    def __init__(self):
        """Initialize interim analysis service"""
        pass

    def create_two_stage_design(
        self,
        interim_info_fraction: float = 0.5,
        one_sided_alpha: float = 0.025,
        power: float = 0.90,
        spending_function: SpendingFunction = SpendingFunction.OBRIEN_FLEMING
    ) -> GroupSequentialDesign:
        """
        Create standard two-stage design (1 interim + final).

        Args:
            interim_info_fraction: Information fraction at interim (default 0.5)
            one_sided_alpha: One-sided significance level
            power: Target power
            spending_function: Alpha spending function

        Returns:
            GroupSequentialDesign
        """
        design = GroupSequentialDesign(
            total_analyses=2,
            one_sided_alpha=one_sided_alpha,
            power=power,
            information_fractions=[interim_info_fraction, 1.0],
            efficacy_spending=spending_function,
            efficacy_stopping=StoppingRule.NON_BINDING
        )

        design.calculate_boundaries()
        return design

    def generate_interim_methodology(
        self,
        design: GroupSequentialDesign
    ) -> str:
        """
        Generate interim analysis methodology text for SAP.

        Args:
            design: Group sequential design specification

        Returns:
            Formatted SAP text
        """
        text = f"""
## Interim Analysis

### Overview

This trial includes {design.total_analyses - 1} planned interim analysis(es) and one final analysis.
The interim analyses will be conducted by an independent Data Monitoring Committee (DMC) to
assess efficacy and/or futility while controlling the overall Type I error rate.

### Type I Error Control

The overall one-sided Type I error rate of α = {design.one_sided_alpha} will be controlled
using a group sequential design with the {design.efficacy_spending.value} alpha spending function.

### Timing of Interim Analyses

The following interim analyses are planned:

"""

        for analysis in design.interim_analyses[:-1]:  # Exclude final
            text += f"""
**Interim Analysis {analysis.analysis_number}:**
- Information fraction: {analysis.information_fraction * 100:.1f}%
"""
            if analysis.planned_events:
                text += f"- Planned events: {analysis.planned_events}\n"
            if analysis.calendar_time:
                text += f"- Approximate timing: {analysis.calendar_time}\n"

            text += f"- Efficacy boundary (Z-score): {analysis.efficacy_boundary:.3f}\n"
            text += f"- Alpha spent (cumulative): {analysis.alpha_spent_cumulative:.5f}\n"

        text += f"""
**Final Analysis:**
- Information fraction: 100%
- Adjusted alpha level: {design.interim_analyses[-1].alpha_spent_cumulative:.5f}

### Stopping Boundaries

**Efficacy Boundary:**
The trial may be stopped early for efficacy if the test statistic crosses the efficacy boundary
at an interim analysis. The efficacy boundary is {design.efficacy_stopping.value.lower()}.

"""

        if design.efficacy_stopping == StoppingRule.BINDING:
            text += "If the efficacy boundary is crossed, the trial MUST be stopped.\n\n"
        else:
            text += "If the efficacy boundary is crossed, the DMC will consider recommending early termination, but the decision is non-binding and will consider totality of evidence.\n\n"

        # Add spending function details
        text += self._generate_spending_function_text(design)

        # Add DMC section
        text += self._generate_dmc_section()

        # Add statistical properties
        text += self._generate_statistical_properties(design)

        return text.strip()

    def _generate_spending_function_text(self, design: GroupSequentialDesign) -> str:
        """Generate spending function description"""
        text = f"""
### Alpha Spending Function

**Function:** {design.efficacy_spending.value}

"""

        if design.efficacy_spending == SpendingFunction.OBRIEN_FLEMING:
            text += """
The O'Brien-Fleming spending function provides conservative boundaries at early analyses
and allocates most alpha to the final analysis. This approach:
- Preserves power
- Requires strong evidence for early stopping
- Is appropriate when early stopping is not desired unless evidence is overwhelming

**Formula:** α(t) = 2 - 2Φ(Z_α / √t) where t is information fraction

"""
        elif design.efficacy_spending == SpendingFunction.POCOCK:
            text += """
The Pocock spending function provides equal boundaries at all analyses (on the p-value scale).
This approach:
- Facilitates early stopping with moderate evidence
- Spends alpha more uniformly across analyses
- May reduce average study duration

**Formula:** α(t) = α × ln[1 + (e-1)t]

"""
        elif design.efficacy_spending == SpendingFunction.HWANG_SHIH_DECANI:
            gamma = design.efficacy_spending_param or 1.0
            text += f"""
The Hwang-Shih-DeCani spending function is a flexible family with parameter γ = {gamma}.
- γ = 1: approximately linear spending
- γ > 1: more conservative early, liberal late (O'Brien-Fleming-like)
- γ < 1: more liberal early, conservative late (Pocock-like)

**Formula:** α(t) = α × [1 - exp(-γt)] / [1 - exp(-γ)]

"""

        return text

    def _generate_dmc_section(self) -> str:
        """Generate DMC charter elements"""
        return """
### Data Monitoring Committee (DMC)

An independent Data Monitoring Committee will review interim analysis results and make
recommendations regarding trial continuation.

**DMC Composition:**
- Minimum 3 members (statistician, clinical experts)
- No financial or intellectual conflicts of interest with sponsor
- Independent from sponsor and investigators

**DMC Responsibilities:**
- Review accumulating safety and efficacy data
- Recommend whether to continue, modify, or terminate the trial
- Assess data quality and protocol compliance

**DMC Recommendations:**
At each interim analysis, the DMC may recommend to:
1. Continue the trial as planned
2. Stop the trial early for efficacy (treatment benefit demonstrated)
3. Stop the trial early for futility (unlikely to demonstrate benefit)
4. Modify the sample size (if adaptive design allows)
5. Modify trial conduct (without unblinding)

**DMC Charter:**
A detailed DMC Charter will be prepared that specifies:
- DMC membership and responsibilities
- Meeting schedule
- Statistical guidelines for decision-making
- Safety monitoring plan
- Communication procedures

"""

    def _generate_statistical_properties(self, design: GroupSequentialDesign) -> str:
        """Generate statistical properties section"""
        text = f"""
### Statistical Properties

**Sample Size Inflation:**
The maximum sample size has been increased by a factor of {design.inflation_factor:.3f} to
account for the interim analyses and maintain the desired power of {design.power * 100:.0f}%.

**Expected Study Duration:**
If the trial stops at the first interim analysis for efficacy, the expected study duration
will be reduced. The expected sample size under various scenarios:
- If H0 true: E[N] ≈ {design.information_fractions[0] * 100:.0f}% - 100% of planned
- If HA true: E[N] ≈ {self._estimate_expected_sample_size(design):.0f}% of planned

**Regulatory Considerations:**
This interim analysis plan complies with:
- **FDA Guidance (2019):** "Adaptive Designs for Clinical Trials of Drugs and Biologics"
- **ICH E9:** "Statistical Principles for Clinical Trials" (Section 4.5)
- **PhRMA Working Group (2006):** "Principles for Implementation of Interim Analyses in Confirmatory Clinical Trials"

**Key Principles:**
1. Type I error rate is strictly controlled at pre-specified level
2. Interim analysis plan is pre-specified in protocol/SAP before unblinding
3. DMC is independent and makes recommendations based on pre-specified guidelines
4. Sponsor remains blinded to interim results to preserve trial integrity
"""

        return text

    def _estimate_expected_sample_size(self, design: GroupSequentialDesign) -> float:
        """Estimate expected sample size as percentage of planned"""
        # Simplified estimate - would use exact calculations in production
        return 85.0  # Typical 85% of planned under alternative

    def generate_conditional_power_section(
        self,
        cp_spec: ConditionalPowerSpec
    ) -> str:
        """Generate conditional power methodology"""
        text = f"""
### Conditional Power Analysis

At interim analyses, conditional power will be calculated to assess the probability of
demonstrating efficacy at the final analysis.

**Definition:**
Conditional power is the probability of rejecting H0 at the final analysis given:
- Current observed data
- Assumptions about the treatment effect in remaining subjects

**Calculation:**
- Current Z-statistic and information fraction
- Assumed treatment effect for remaining data
"""

        if cp_spec.assume_null:
            text += "- Under null hypothesis (for futility assessment)\n"
        else:
            text += "- Under observed treatment effect (for sample size re-estimation)\n"

        text += f"""
**Decision Thresholds:**
- Conditional power ≥ {cp_spec.favorable_threshold * 100:.0f}%: Favorable prognosis, continue as planned
- {cp_spec.unfavorable_threshold * 100:.0f}% ≤ CP < {cp_spec.favorable_threshold * 100:.0f}%: Uncertain, continue with caution
- Conditional power < {cp_spec.unfavorable_threshold * 100:.0f}%: Unfavorable, consider stopping for futility

**Interpretation:**
Low conditional power (< {cp_spec.unfavorable_threshold * 100:.0f}%) suggests that even if the trial
continues to full enrollment, the probability of success is low. This may warrant consideration
of early termination for futility to avoid exposing additional patients to an ineffective treatment.
"""

        return text

    def generate_sample_size_reestimation_section(
        self,
        ssr_spec: SampleSizeReestimation
    ) -> str:
        """Generate sample size re-estimation methodology"""
        text = f"""
### Sample Size Re-estimation

The trial design allows for sample size re-estimation at the interim analysis based on
blinded aggregate data.

**Timing:**
Sample size re-estimation will be performed when approximately {ssr_spec.reestimation_at_info_fraction * 100:.0f}%
of the planned information has been observed.

**Parameters to Re-estimate:**
"""

        if ssr_spec.reestimate_effect_size:
            text += "- Treatment effect size (using blinded pooled estimate)\n"
        if ssr_spec.reestimate_variance:
            text += "- Variance/standard deviation\n"
        if ssr_spec.reestimate_event_rate:
            text += "- Event rate (for time-to-event endpoints)\n"

        text += f"""
**Constraints:**
- Maximum sample size increase: {ssr_spec.max_sample_size_increase * 100:.0f}%
- Target conditional power: {ssr_spec.min_conditional_power * 100:.0f}%
"""

        if ssr_spec.maintain_treatment_blinding:
            text += "- Treatment assignment remains blinded (pooled estimates only)\n"

        text += """
**Decision Rules:**
The sample size may be increased if:
1. Blinded re-estimation suggests original assumptions were optimistic
2. Conditional power falls below target threshold
3. Increase is within pre-specified maximum

The sample size will NOT be decreased, to preserve Type I error control.

**Implementation:**
- Independent statistician performs blinded re-estimation
- Recommendation provided to DMC without unblinding treatment groups
- DMC recommends whether to increase sample size
- Sponsor implements recommendation while remaining blinded

**Statistical Validity:**
This approach maintains Type I error rate because:
- Decision is based on blinded aggregate data only
- Sample size can only be increased (not decreased)
- Maximum increase is pre-specified
- Satisfies information-based design principles
"""

        return text


# Singleton instance
_interim_service: Optional[InterimAnalysisService] = None


def get_interim_analysis_service() -> InterimAnalysisService:
    """
    Get interim analysis service instance.

    Returns:
        InterimAnalysisService instance
    """
    global _interim_service

    if _interim_service is None:
        _interim_service = InterimAnalysisService()

    return _interim_service
