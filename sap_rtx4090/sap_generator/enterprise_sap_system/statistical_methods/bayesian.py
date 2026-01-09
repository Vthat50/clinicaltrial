"""
Bayesian Statistical Methods
=============================

Bayesian approaches for clinical trial design and analysis.

Regulatory acceptance:
- FDA Guidance: "Bayesian Statistics in Medical Device Clinical Trials" (2010)
- FDA: "Adaptive Designs for Clinical Trials of Drugs and Biologics" (2019)
- FDA: "Complex Innovative Trial Designs" (2020)

Methods:
- Bayesian adaptive designs
- Hierarchical Bayesian models
- Bayesian survival analysis
- Predictive probability
- Posterior probability of success
- Credible intervals

Software:
- Stan, JAGS, WinBUGS
- R packages: rstan, brms, BayesFactor
- SAS PROC MCMC
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


class PriorType(Enum):
    """Types of prior distributions"""
    NONINFORMATIVE = "Non-informative"
    WEAKLY_INFORMATIVE = "Weakly Informative"
    INFORMATIVE = "Informative"
    SKEPTICAL = "Skeptical"
    ENTHUSIASTIC = "Enthusiastic"
    HISTORICAL = "Historical Control"


class PosteriorSummary(Enum):
    """Posterior summary statistics"""
    MEAN = "Posterior Mean"
    MEDIAN = "Posterior Median"
    MODE = "Posterior Mode (MAP)"


class MCMCAlgorithm(Enum):
    """MCMC sampling algorithms"""
    GIBBS = "Gibbs Sampling"
    METROPOLIS_HASTINGS = "Metropolis-Hastings"
    HAMILTONIAN = "Hamiltonian Monte Carlo (HMC)"
    NUTS = "No-U-Turn Sampler (NUTS)"


@dataclass
class PriorDistribution:
    """
    Specification for a prior distribution.

    Represents prior belief about a parameter before observing data.
    """
    parameter_name: str                # e.g., "log_HR", "response_rate"
    distribution: str                  # "normal", "beta", "gamma", "uniform"

    # Distribution parameters
    parameters: Dict[str, float] = field(default_factory=dict)  # e.g., {"mean": 0, "sd": 1}

    # Prior type and justification
    prior_type: PriorType = PriorType.NONINFORMATIVE
    justification: str = ""            # Why this prior is appropriate

    # For informative priors
    source: str = ""                   # e.g., "Phase 2 trial NCT12345"
    historical_data: Dict = field(default_factory=dict)

    # Prior sensitivity
    sensitivity_priors: List[Dict] = field(default_factory=list)  # Alternative priors


@dataclass
class BayesianDesignSpec:
    """
    Specification for Bayesian adaptive design.

    Defines decision rules, priors, and adaptation mechanisms.
    """
    # Design type
    design_name: str
    design_description: str

    # Priors
    priors: List[PriorDistribution] = field(default_factory=list)

    # Decision rules
    success_threshold: float = 0.975   # P(θ > θ₀ | data) > threshold
    futility_threshold: float = 0.10   # P(θ > θ₀ | data) < threshold

    # Interim analyses
    interim_analyses: List[int] = field(default_factory=list)  # Sample sizes
    look_at_every_n: Optional[int] = None  # Continuous monitoring

    # Adaptation rules
    sample_size_adaptation: bool = False
    randomization_adaptation: bool = False  # Response-adaptive randomization
    dose_adaptation: bool = False

    # Type I error control
    control_type_i_error: bool = True
    frequentist_alpha: float = 0.025   # If controlling Type I error

    # MCMC
    mcmc_algorithm: MCMCAlgorithm = MCMCAlgorithm.NUTS
    num_chains: int = 4
    warmup_iterations: int = 1000
    sampling_iterations: int = 2000


@dataclass
class PredictiveProbabilitySpec:
    """
    Predictive probability specification.

    Predicts probability of trial success at final analysis.
    """
    # Success definition
    success_criterion: str             # e.g., "P(HR < 1 | final data) > 0.975"

    # Prediction assumptions
    assume_current_trend: bool = True  # Use current treatment effect
    assume_null: bool = False          # Conservative: assume null for remaining data

    # Thresholds
    favorable_threshold: float = 0.80  # PP > 80% considered favorable
    unfavorable_threshold: float = 0.10  # PP < 10% suggests futility

    # For sample size adaptation
    target_predictive_prob: float = 0.90  # Target PP for SSR


@dataclass
class BayesianSurvivalSpec:
    """
    Bayesian survival analysis specification.

    Bayesian Cox or parametric survival models.
    """
    # Model type
    model_type: str = "cox"            # "cox", "weibull", "exponential", "log-normal"

    # Priors on parameters
    log_hr_prior: PriorDistribution = None
    baseline_hazard_prior: Optional[PriorDistribution] = None

    # Credible interval
    credible_level: float = 0.95

    # Posterior summaries
    posterior_summary: PosteriorSummary = PosteriorSummary.MEDIAN

    # Hypothesis testing
    test_null_value: float = 1.0       # HR = 1 (null)
    two_sided: bool = False


@dataclass
class BayesianResponseRateSpec:
    """
    Bayesian analysis for binary response rates.

    Uses beta-binomial conjugate analysis.
    """
    # Priors (beta distribution)
    control_prior: PriorDistribution = None
    experimental_prior: PriorDistribution = None

    # Success criterion
    superiority_threshold: float = 0.975  # P(p_exp > p_ctrl | data)

    # Credible intervals
    credible_level: float = 0.95

    # For single-arm
    historical_control_rate: Optional[float] = None
    historical_control_n: Optional[int] = None


@dataclass
class ResponseAdaptiveRandomization:
    """
    Response-adaptive randomization specification.

    Allocates more patients to better-performing arms.
    """
    # Starting allocation
    initial_allocation: Dict[str, float] = field(default_factory=dict)  # arm -> probability

    # Adaptation
    adaptation_start: int = 50         # Start adapting after N patients
    adaptation_frequency: int = 10     # Re-calculate every N patients

    # Allocation rule
    allocation_rule: str = "thompson_sampling"  # "thompson_sampling", "RSIHR"

    # Constraints
    min_allocation: float = 0.10       # Minimum 10% to any arm
    max_allocation: float = 0.80       # Maximum 80% to any arm


class BayesianService:
    """
    Service for Bayesian analysis specifications.

    Provides methodology text and design guidance.
    """

    def __init__(self):
        """Initialize Bayesian service"""
        pass

    def create_noninformative_prior(
        self,
        parameter_name: str,
        parameter_type: str = "log_HR"
    ) -> PriorDistribution:
        """
        Create non-informative prior.

        Args:
            parameter_name: Parameter name
            parameter_type: Type of parameter

        Returns:
            PriorDistribution with non-informative specification
        """
        if parameter_type == "log_HR":
            # Normal(0, 100) is essentially flat for log-HR
            return PriorDistribution(
                parameter_name=parameter_name,
                distribution="normal",
                parameters={"mean": 0.0, "sd": 100.0},
                prior_type=PriorType.NONINFORMATIVE,
                justification="Flat prior allowing data to dominate"
            )

        elif parameter_type == "proportion":
            # Beta(1, 1) = Uniform(0, 1)
            return PriorDistribution(
                parameter_name=parameter_name,
                distribution="beta",
                parameters={"alpha": 1.0, "beta": 1.0},
                prior_type=PriorType.NONINFORMATIVE,
                justification="Uniform prior on [0,1]"
            )

        else:
            return PriorDistribution(
                parameter_name=parameter_name,
                distribution="uniform",
                parameters={"lower": -1e6, "upper": 1e6},
                prior_type=PriorType.NONINFORMATIVE
            )

    def create_weakly_informative_prior(
        self,
        parameter_name: str,
        parameter_type: str = "log_HR",
        expected_direction: str = "beneficial"
    ) -> PriorDistribution:
        """
        Create weakly informative prior.

        Regularizes without being too restrictive.
        """
        if parameter_type == "log_HR":
            # Weakly informative: centered at slightly beneficial
            if expected_direction == "beneficial":
                mean = -0.2  # Mild benefit (HR ~ 0.82)
            else:
                mean = 0.0

            return PriorDistribution(
                parameter_name=parameter_name,
                distribution="normal",
                parameters={"mean": mean, "sd": 1.0},
                prior_type=PriorType.WEAKLY_INFORMATIVE,
                justification="Regularizing prior allowing wide range of effects"
            )

        elif parameter_type == "proportion":
            # Beta(2, 2) slightly favors middle values
            return PriorDistribution(
                parameter_name=parameter_name,
                distribution="beta",
                parameters={"alpha": 2.0, "beta": 2.0},
                prior_type=PriorType.WEAKLY_INFORMATIVE,
                justification="Mildly informative, favors moderate rates"
            )

        return self.create_noninformative_prior(parameter_name, parameter_type)

    def generate_bayesian_methodology(
        self,
        spec: BayesianDesignSpec,
        endpoint_name: str
    ) -> str:
        """
        Generate Bayesian methodology text for SAP.

        Args:
            spec: Bayesian design specification
            endpoint_name: Name of endpoint

        Returns:
            Formatted SAP text
        """
        text = f"""
## Bayesian Analysis

### Overview

A Bayesian approach will be used for analyzing {endpoint_name}, incorporating prior
information and providing probabilistic inference about treatment effects.

**Design:** {spec.design_name}

{spec.design_description}

### Bayesian Framework

**Key Concepts:**

- **Prior Distribution:** Represents knowledge/beliefs before seeing current trial data
- **Likelihood:** Probability of observed data given parameters
- **Posterior Distribution:** Updated beliefs after observing data

  Posterior ∝ Prior × Likelihood (Bayes' Theorem)

- **Credible Interval:** Bayesian analog of confidence interval
  - 95% credible interval: 95% probability parameter is in this range

"""

        # Prior specifications
        text += self._generate_priors_section(spec)

        # Decision rules
        text += self._generate_decision_rules(spec)

        # MCMC
        text += self._generate_mcmc_section(spec)

        # Type I error
        if spec.control_type_i_error:
            text += self._generate_type_i_error_section(spec)

        # Interpretation
        text += self._generate_interpretation_section()

        # Regulatory
        text += self._generate_regulatory_section()

        return text.strip()

    def _generate_priors_section(self, spec: BayesianDesignSpec) -> str:
        """Generate prior distributions section"""
        text = """
### Prior Distributions

The following prior distributions will be used:

"""

        for prior in spec.priors:
            text += f"""
#### {prior.parameter_name}

**Distribution:** {prior.distribution.capitalize()}
**Parameters:** {', '.join([f'{k}={v}' for k, v in prior.parameters.items()])}
**Type:** {prior.prior_type.value}

**Justification:**
{prior.justification}

"""

            if prior.source:
                text += f"**Source:** {prior.source}\n\n"

            if prior.prior_type in [PriorType.INFORMATIVE, PriorType.HISTORICAL]:
                text += """
**Note:** Informative priors will be based on previous data. Sensitivity analyses
with alternative priors will be conducted to assess robustness.

"""

        text += """
### Prior Sensitivity

To assess the influence of prior specifications, the following sensitivity analyses
will be performed:

1. **Non-informative prior:** Essentially flat prior, data-dominated
2. **Weakly informative prior:** Regularizing prior (reference analysis)
3. **Informative prior:** Based on historical data (primary analysis)
4. **Skeptical prior:** Prior favoring null hypothesis
5. **Enthusiastic prior:** Prior favoring treatment benefit

**Interpretation:**
- If results are consistent across priors → Robust to prior choice
- If results vary substantially → Prior has meaningful impact; interpret cautiously

"""

        return text

    def _generate_decision_rules(self, spec: BayesianDesignSpec) -> str:
        """Generate decision rules section"""
        text = f"""
### Decision Rules

**Success Criterion:**
The trial will be declared successful if:

P(Treatment Effect > Null Value | Data) > {spec.success_threshold}

"""

        if spec.futility_threshold:
            text += f"""
**Futility Criterion:**
The trial may be stopped for futility if:

P(Treatment Effect > Null Value | Data) < {spec.futility_threshold}

"""

        if spec.interim_analyses:
            text += f"""
**Interim Analyses:**
Planned at: {', '.join([f'N={n}' for n in spec.interim_analyses])}

At each interim:
1. Calculate posterior distribution given current data
2. Evaluate success/futility criteria
3. DMC reviews and makes recommendation

"""

        text += """
**Interpretation of Posterior Probability:**

- P > 0.975: Strong evidence of benefit (analogous to p < 0.025 one-sided)
- 0.95 < P ≤ 0.975: Moderate evidence of benefit
- 0.80 < P ≤ 0.95: Some evidence of benefit
- P ≤ 0.80: Insufficient evidence

"""

        return text

    def _generate_mcmc_section(self, spec: BayesianDesignSpec) -> str:
        """Generate MCMC section"""
        text = f"""
### Computational Methods

**Algorithm:** {spec.mcmc_algorithm.value}

**MCMC Sampling:**
- Number of chains: {spec.num_chains}
- Warmup iterations: {spec.warmup_iterations:,}
- Sampling iterations: {spec.sampling_iterations:,}
- Total samples: {spec.num_chains * spec.sampling_iterations:,}

**Convergence Diagnostics:**
- R-hat statistic (potential scale reduction factor) < 1.1
- Effective sample size (ESS) > 400 per chain
- Visual inspection of trace plots
- Geweke diagnostic

**Software:** Stan (via rstan or cmdstanr)

"""

        if spec.mcmc_algorithm == MCMCAlgorithm.NUTS:
            text += """
**No-U-Turn Sampler (NUTS):**
- Extension of Hamiltonian Monte Carlo (HMC)
- Automatically tunes step size and trajectory length
- More efficient than Gibbs or Metropolis-Hastings
- Default in Stan, well-suited for complex models

"""

        return text

    def _generate_type_i_error_section(self, spec: BayesianDesignSpec) -> str:
        """Generate Type I error control section"""
        return f"""
### Type I Error Control

Although Bayesian inference does not formally require Type I error control,
this trial will calibrate decision rules to maintain frequentist Type I error
at α = {spec.frequentist_alpha}.

**Calibration Method:**
Simulation under null hypothesis (no treatment effect) to ensure:

P(Declare Success | H₀ true) ≤ α

**Implementation:**
1. Simulate trials under H₀
2. Calculate posterior probabilities at each interim
3. Apply decision rules
4. Measure false positive rate
5. Adjust success threshold if needed to achieve α

This hybrid approach provides:
- Bayesian interpretation (posterior probabilities)
- Frequentist operating characteristics (Type I error control)
- Regulatory acceptability

**Reference:** FDA Guidance on Adaptive Designs (2019) - Bayesian approaches

"""

    def _generate_interpretation_section(self) -> str:
        """Generate interpretation guidance"""
        return """
### Interpretation of Bayesian Results

**Posterior Probability:**
The posterior probability P(θ > θ₀ | data) directly answers:
"What is the probability the treatment effect exceeds the null value?"

**Example:**
If P(HR < 1 | data) = 0.98, there is a 98% probability that the experimental
treatment reduces hazard compared to control.

**Credible Intervals:**
A 95% credible interval [L, U] means:
"There is a 95% probability the true parameter is between L and U"

This is a direct probability statement, unlike frequentist confidence intervals.

**Advantages of Bayesian Approach:**

1. **Probabilistic Statements:** Direct interpretation of results
2. **Incorporation of Prior Information:** Uses all available knowledge
3. **Natural for Adaptive Designs:** Update beliefs sequentially
4. **Flexible:** Can accommodate complex models and missing data
5. **Decision-Theoretic:** Naturally integrates with decision-making

**Limitations:**

1. **Prior Sensitivity:** Results may depend on prior choice
2. **Computational:** Requires MCMC, more intensive than closed-form
3. **Regulatory:** Requires justification of priors and hybrid Type I error control

"""

    def _generate_regulatory_section(self) -> str:
        """Generate regulatory considerations"""
        return """
### Regulatory Considerations

This Bayesian design complies with FDA guidance:

**FDA Guidance: "Adaptive Designs for Clinical Trials of Drugs and Biologics" (2019)**
- Section on Bayesian Adaptive Designs
- Acceptable with proper justification

**FDA Guidance: "Bayesian Statistics in Medical Device Trials" (2010)**
- Provides framework for Bayesian inference
- Emphasizes prior justification and sensitivity

**Key FDA Requirements:**

1. **Prior Justification**
   - Clear rationale for prior choice
   - Sensitivity to prior specifications
   - Document source of informative priors

2. **Type I Error Control**
   - Calibrate to maintain α (hybrid approach)
   - OR: Argue from Bayesian perspective with strong justification

3. **Transparency**
   - Pre-specify all aspects (priors, decision rules, adaptation)
   - SAP locked before unblinding
   - Clear documentation

4. **Simulation**
   - Operating characteristics under various scenarios
   - Type I error, power, sample size distribution
   - Impact of priors

**EMA Position:**
Similar to FDA; accepts Bayesian methods with proper justification.
- EMA Reflection Paper on Bayesian Methods (2018)

**Recommendation:**
Early engagement with regulatory agencies (pre-IND, Type B meeting) to discuss
Bayesian design and ensure alignment.

"""

    def generate_predictive_probability_methodology(
        self,
        spec: PredictiveProbabilitySpec
    ) -> str:
        """Generate predictive probability methodology"""
        text = f"""
## Predictive Probability

### Definition

Predictive probability (PP) is the probability of achieving success at the final
analysis, given current data and assumptions about remaining data.

**Success Criterion:** {spec.success_criterion}

### Calculation

At an interim analysis with nᵢₙₜ subjects observed:

1. Calculate current posterior distribution P(θ | data_current)
2. For each value of θ, simulate remaining data under that θ
3. Calculate final posterior given complete data
4. Determine if success criterion met
5. Average over θ values weighted by current posterior

**Formula:**
PP = ∫ P(Success at end | θ, data_current) × P(θ | data_current) dθ

"""

        if spec.assume_null:
            text += """
**Conservative Assumption:**
For futility assessment, PP calculated assuming null hypothesis (θ = θ₀) for
remaining data. This provides a lower bound on PP.

"""
        elif spec.assume_current_trend:
            text += """
**Current Trend Assumption:**
PP calculated assuming current observed treatment effect continues for remaining
data. This is the most common approach.

"""

        text += f"""
### Decision Thresholds

**Favorable:** PP > {spec.favorable_threshold * 100:.0f}%
- High probability of success
- Continue trial with confidence

**Unfavorable:** PP < {spec.unfavorable_threshold * 100:.0f}%
- Low probability of success even if trial continues
- Consider stopping for futility

**Intermediate:** {spec.unfavorable_threshold * 100:.0f}% ≤ PP ≤ {spec.favorable_threshold * 100:.0f}%
- Uncertain outcome
- Continue with caution or consider sample size increase

"""

        if spec.target_predictive_prob:
            text += f"""
### Sample Size Re-estimation

If PP is in the intermediate range, sample size may be increased to achieve
target PP = {spec.target_predictive_prob * 100:.0f}%.

**Procedure:**
1. Calculate PP with current sample size
2. If PP < target, simulate additional sample sizes
3. Find minimum N to achieve target PP
4. Increase sample size (within pre-specified maximum)

"""

        return text


# Singleton instance
_bayesian_service: Optional[BayesianService] = None


def get_bayesian_service() -> BayesianService:
    """
    Get Bayesian service instance.

    Returns:
        BayesianService instance
    """
    global _bayesian_service

    if _bayesian_service is None:
        _bayesian_service = BayesianService()

    return _bayesian_service
