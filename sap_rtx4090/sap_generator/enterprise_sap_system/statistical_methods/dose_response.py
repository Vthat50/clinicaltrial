"""
Dose-Response Analysis Methods
===============================

Methods for analyzing dose-response relationships in clinical trials.

Key method: MCP-Mod (Multiple Comparison Procedure - Modeling)
- FDA-qualified drug development tool
- Efficient dose-finding methodology
- Combines multiple comparison and modeling

Other methods:
- Monotone dose-response models
- Emax models
- Sigmoid Emax models
- Linear/quadratic models
- Umbrella/plateau models

Regulatory:
- FDA Guidance: "Adaptive Designs for Clinical Trials" (2019)
- ICH E4: Dose-Response Information (1994)
- EMA: Guideline on Dose-Response Studies (2017)

Applications:
- Phase 2 dose-finding
- Phase 2b dose-ranging
- Proof-of-concept with dose-response
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


class DoseResponseModel(Enum):
    """Dose-response model types"""
    LINEAR = "Linear"
    QUADRATIC = "Quadratic"
    EMAX = "Emax"
    EXPONENTIAL = "Exponential"
    SIGMOID_EMAX = "Sigmoid Emax"
    LOG_LINEAR = "Log-Linear"
    LOGISTIC = "Logistic"
    BETA = "Beta Model"
    UMBRELLA = "Umbrella (Non-monotone)"


class ContrastType(Enum):
    """Types of contrast tests"""
    WILLIAMS = "Williams Trend"
    DUNNETT = "Dunnett"
    MCP_MOD = "MCP-Mod"
    PAIRWISE = "Pairwise Comparisons"


@dataclass
class DoseLevel:
    """Specification for a single dose level"""
    dose: float                        # Dose amount (mg, mg/kg, etc.)
    dose_label: str                    # e.g., "Placebo", "10 mg", "50 mg"
    is_placebo: bool = False
    sample_size: int = 0


@dataclass
class DoseResponseCurve:
    """Specification for a candidate dose-response model"""
    model_type: DoseResponseModel
    model_name: str                    # User-friendly name

    # Model parameters (for simulation/prior specification)
    parameters: Dict[str, float] = field(default_factory=dict)

    # Interpretation
    clinical_rationale: str = ""       # Why this shape is plausible
    biological_mechanism: str = ""

    # For MCP-Mod
    standardized: bool = False         # Whether standardized to unit scale
    guessing_factor: Optional[float] = None  # For standardization


@dataclass
class MCPModSpec:
    """
    MCP-Mod (Multiple Comparison Procedure - Modeling) specification.

    Two-stage approach:
    1. MCP: Test for dose-response signal using multiple contrasts
    2. Mod: Model dose-response to estimate target dose
    """
    # Dose levels
    dose_levels: List[DoseLevel] = field(default_factory=list)

    # Candidate models
    candidate_models: List[DoseResponseCurve] = field(default_factory=list)

    # MCP stage
    family_wise_error: float = 0.05    # One-sided
    contrast_method: str = "optimal"   # "optimal" or "user-defined"

    # Modeling stage
    model_selection_criterion: str = "AIC"  # "AIC", "BIC", "Both"
    model_averaging: bool = True       # Average over top models

    # Target dose
    target_effect: Optional[float] = None     # e.g., 50% of maximum effect
    target_dose_method: str = "ED50"          # "ED50", "EDT", "MED"

    # Confidence intervals
    confidence_level: float = 0.95
    bootstrap_ci: bool = True
    num_bootstrap: int = 1000

    # Multiple testing
    multiplicity_adjustment: str = "max-T"  # Max-T multiple testing


@dataclass
class EmaxModel:
    """
    Emax (Michaelis-Menten) model specification.

    E(d) = E0 + Emax × d / (ED50 + d)

    Common in pharmacology for saturable processes.
    """
    # Parameters
    e0: float = 0.0                    # Baseline response (placebo)
    emax: float = 10.0                 # Maximum effect
    ed50: float = 50.0                 # Dose giving 50% of Emax

    # Constraints
    e0_fixed: bool = False             # Fix E0 to placebo response
    monotone_increasing: bool = True


@dataclass
class SigmoidEmaxModel:
    """
    Sigmoid Emax (Hill) model specification.

    E(d) = E0 + Emax × d^h / (ED50^h + d^h)

    Allows for steep dose-response curves (h > 1).
    """
    e0: float = 0.0
    emax: float = 10.0
    ed50: float = 50.0
    hill: float = 1.0                  # Hill parameter (sigmoidicity)

    # Constraints
    hill_lower: float = 0.5
    hill_upper: float = 5.0


@dataclass
class MonotoneTrendTest:
    """
    Monotone trend test specification.

    Tests for monotone increasing or decreasing dose-response.
    """
    # Test type
    test_type: str = "Williams"        # "Williams", "Modified Williams", "Cochran-Armitage"

    # Direction
    increasing: bool = True

    # Multiplicity
    adjust_multiple_doses: bool = True
    alpha: float = 0.05


@dataclass
class TargetDoseEstimation:
    """
    Target dose estimation specification.

    Estimates dose achieving a target effect (e.g., ED50, TD, MED).
    """
    # Target definition
    target_type: str = "ED50"          # "ED50", "TD" (target dose), "MED" (minimum effective)
    target_effect: Optional[float] = None  # For TD: specify target effect size

    # Estimation method
    estimation_method: str = "model-based"  # "model-based" or "interpolation"

    # For MED
    med_comparison: str = "placebo"    # Compare to "placebo" or "baseline"
    med_delta: float = 0.0             # Minimum clinically important difference
    med_ci_method: str = "delta"       # "delta" or "bootstrap"

    # Confidence intervals
    confidence_level: float = 0.95


class DoseResponseService:
    """
    Service for dose-response analysis specifications.

    Implements MCP-Mod and related dose-finding methods.
    """

    def __init__(self):
        """Initialize dose-response service"""
        pass

    def create_mcpmod_spec(
        self,
        dose_levels: List[float],
        placebo_included: bool = True,
        alpha: float = 0.05
    ) -> MCPModSpec:
        """
        Create standard MCP-Mod specification.

        Args:
            dose_levels: List of dose levels (include 0 for placebo)
            placebo_included: Whether placebo is in dose_levels
            alpha: One-sided family-wise error rate

        Returns:
            MCPModSpec with standard candidate models
        """
        # Create dose level objects
        dose_objs = []
        for dose in dose_levels:
            dose_objs.append(DoseLevel(
                dose=dose,
                dose_label=f"{dose} mg" if dose > 0 else "Placebo",
                is_placebo=(dose == 0.0)
            ))

        # Standard candidate models for oncology
        candidate_models = [
            DoseResponseCurve(
                model_type=DoseResponseModel.LINEAR,
                model_name="Linear",
                clinical_rationale="Simple linear dose-response, no saturation"
            ),
            DoseResponseCurve(
                model_type=DoseResponseModel.EMAX,
                model_name="Emax",
                clinical_rationale="Saturable response typical of receptor binding",
                parameters={"ed50": max(dose_levels) / 2}
            ),
            DoseResponseCurve(
                model_type=DoseResponseModel.SIGMOID_EMAX,
                model_name="Sigmoid Emax",
                clinical_rationale="Steep dose-response with threshold",
                parameters={"ed50": max(dose_levels) / 2, "hill": 2.0}
            ),
            DoseResponseCurve(
                model_type=DoseResponseModel.EXPONENTIAL,
                model_name="Exponential",
                clinical_rationale="Gradual approach to asymptote"
            ),
        ]

        spec = MCPModSpec(
            dose_levels=dose_objs,
            candidate_models=candidate_models,
            family_wise_error=alpha,
            model_selection_criterion="AIC",
            model_averaging=True,
            bootstrap_ci=True
        )

        return spec

    def generate_mcpmod_methodology(
        self,
        spec: MCPModSpec,
        endpoint_name: str
    ) -> str:
        """
        Generate MCP-Mod methodology text for SAP.

        Args:
            spec: MCP-Mod specification
            endpoint_name: Name of endpoint

        Returns:
            Formatted SAP text
        """
        dose_range = [d.dose for d in spec.dose_levels]
        dose_labels = [d.dose_label for d in spec.dose_levels]

        text = f"""
## Dose-Response Analysis

### Method: MCP-Mod (Multiple Comparison Procedure - Modeling)

The dose-response relationship for {endpoint_name} will be analyzed using MCP-Mod,
an FDA-qualified method for efficient dose finding.

**FDA Qualification:** MCP-Mod is a qualified drug development tool per FDA's DDT
program (2024), recognized for its efficiency in dose-response studies.

### Study Design

**Dose Levels:** {', '.join(dose_labels)}

**Dose Range:** {min(dose_range)} to {max(dose_range)} mg

### MCP-Mod Methodology

MCP-Mod is a two-stage procedure:

**Stage 1: Multiple Comparison Procedure (MCP)**
- Tests for presence of dose-response signal
- Uses optimal contrasts derived from candidate models
- Controls family-wise error rate at α = {spec.family_wise_error}

**Stage 2: Modeling (Mod)**
- If dose-response signal detected, fit dose-response models
- Select best model(s) based on {spec.model_selection_criterion}
- Estimate target dose(s)

### Candidate Models

The following candidate dose-response models will be considered:

"""

        for i, model in enumerate(spec.candidate_models, 1):
            text += f"""
#### {i}. {model.model_name} Model

**Model Type:** {model.model_type.value}

**Clinical Rationale:** {model.clinical_rationale}

"""

            # Add model equation
            if model.model_type == DoseResponseModel.LINEAR:
                text += "**Equation:** E(d) = E₀ + β × d\n\n"
            elif model.model_type == DoseResponseModel.EMAX:
                text += "**Equation:** E(d) = E₀ + Emax × d / (ED₅₀ + d)\n\n"
            elif model.model_type == DoseResponseModel.SIGMOID_EMAX:
                text += "**Equation:** E(d) = E₀ + Emax × d^h / (ED₅₀^h + d^h)\n\n"
            elif model.model_type == DoseResponseModel.EXPONENTIAL:
                text += "**Equation:** E(d) = E₀ + E₁ × (exp(d/δ) - 1)\n\n"

        text += """
### Stage 1: Multiple Comparison Procedure

**Objective:** Test global null hypothesis H₀: No dose-response signal

**Method:**
1. For each candidate model, derive optimal contrast weights
2. Calculate test statistics for each contrast
3. Combine using maximum statistic: T_max = max{T₁, T₂, ..., T_k}
4. Compare to critical value accounting for correlation between tests

**Critical Value:** Determined by simulation to control family-wise error at α

**Decision Rule:**
- If T_max > critical value: Reject H₀, proceed to modeling stage
- Otherwise: Conclude insufficient evidence of dose-response

"""

        text += f"""
### Stage 2: Modeling

**Model Fitting:**
All candidate models will be fit to the observed dose-response data.

**Model Selection:** {spec.model_selection_criterion}

"""

        if spec.model_selection_criterion == "AIC":
            text += """
**Akaike Information Criterion (AIC):**
AIC = -2 × log-likelihood + 2 × number of parameters

Lower AIC indicates better balance of fit and parsimony.

"""
        elif spec.model_selection_criterion == "BIC":
            text += """
**Bayesian Information Criterion (BIC):**
BIC = -2 × log-likelihood + log(n) × number of parameters

BIC penalizes complexity more heavily than AIC.

"""

        if spec.model_averaging:
            text += """
**Model Averaging:**
Rather than selecting a single "best" model, predictions will be averaged across
multiple well-fitting models weighted by their relative likelihood (AIC weights).

**AIC Weight for model i:**
w_i = exp(-½ΔAICᵢ) / Σⱼ exp(-½ΔAICⱼ)

where ΔAICᵢ = AICᵢ - min(AIC)

**Model-Averaged Estimate:**
Ê(d) = Σᵢ wᵢ × Êᵢ(d)

**Advantage:** Accounts for model uncertainty, more robust estimates

"""

        text += self._generate_target_dose_section(spec)
        text += self._generate_ci_section(spec)
        text += self._generate_interpretation_section()

        return text.strip()

    def _generate_target_dose_section(self, spec: MCPModSpec) -> str:
        """Generate target dose estimation section"""
        text = """
### Target Dose Estimation

"""

        if spec.target_effect:
            text += f"""
**Target Effect:** {spec.target_effect}

The dose achieving the target effect will be estimated from the fitted dose-response
model(s).

"""

        text += """
**ED50 (Effective Dose 50):**
The dose achieving 50% of the maximum effect will be estimated.

For Emax model: ED50 is a direct parameter
For other models: ED50 is derived from fitted curve

**Minimum Effective Dose (MED):**
The lowest dose demonstrating clinically meaningful improvement over placebo.

**Target Dose (TD):**
The dose achieving a pre-specified target effect level.

"""

        return text

    def _generate_ci_section(self, spec: MCPModSpec) -> str:
        """Generate confidence interval section"""
        text = f"""
### Confidence Intervals

{spec.confidence_level * 100:.0f}% confidence intervals will be calculated for:
- Dose-response curve across dose range
- Target doses (ED50, MED, TD)
- Treatment effect at each dose level

"""

        if spec.bootstrap_ci:
            text += f"""
**Method:** Bootstrap ({spec.num_bootstrap:,} resamples)

Bootstrap confidence intervals account for:
- Parameter estimation uncertainty
- Model selection uncertainty (if model averaging)
- Non-normality of dose estimates

**Procedure:**
1. Draw bootstrap sample from observed data
2. Perform full MCP-Mod procedure (testing + modeling)
3. Estimate target dose in bootstrap sample
4. Repeat {spec.num_bootstrap:,} times
5. Calculate percentile-based CI from bootstrap distribution

"""
        else:
            text += """
**Method:** Delta method (asymptotic approximation)

Standard errors calculated from model fit and propagated to dose estimates.

"""

        return text

    def _generate_interpretation_section(self) -> str:
        """Generate interpretation guidance"""
        return """
### Interpretation Framework

**If Dose-Response Signal Detected (Stage 1 significant):**

1. **Dose-Response Relationship Confirmed**
   - Provides evidence that treatment effect varies with dose
   - Supports biological activity and pharmacological rationale

2. **Dose Selection for Phase 3**
   - Use model to identify optimal dose(s)
   - Balance efficacy (from dose-response) with safety
   - Consider plateau of response curve

3. **Regulatory Implications**
   - Demonstrates dose-finding effort per ICH E4
   - Supports chosen Phase 3 dose(s)
   - May support dose flexibility in labeling

**If No Dose-Response Signal (Stage 1 not significant):**

1. **Possible Explanations**
   - True absence of dose-response in studied range
   - Insufficient sample size or dose levels
   - High variability masking signal
   - Narrow therapeutic window

2. **Actions**
   - Review dose selection rationale
   - Consider exploratory analyses (individual models)
   - Examine safety data for dose effects
   - Plan additional dose-finding if needed

### Regulatory Compliance

This dose-response analysis complies with:

- **ICH E4 (1994):** Dose-Response Information to Support Drug Registration
- **FDA Guidance (2019):** Adaptive Designs for Clinical Trials
- **EMA Guideline (2017):** Guideline on the Investigation of Dose-Response Relationship

**Key Principles:**
1. Multiple candidate models pre-specified
2. Family-wise error rate controlled
3. Model uncertainty quantified
4. Target dose estimation with confidence intervals
5. Clinical interpretation integrated with statistical findings

### Software Implementation

**R Package: DoseFinding**
```r
library(DoseFinding)

# Define doses
doses <- c(0, 10, 25, 50, 100)

# Define candidate models
models <- Mods(
    linear = NULL,
    emax = c(25),
    sigEmax = rbind(c(25, 2), c(50, 3)),
    exponential = c(10),
    doses = doses,
    placEff = 0,
    maxEff = 1
)

# MCP step
MCTtest(
    dose = data$dose,
    resp = data$response,
    models = models,
    alpha = 0.05,
    pVal = TRUE
)

# Modeling step
fitMod(
    dose = data$dose,
    resp = data$response,
    model = "sigEmax",
    bnds = c(0.01, max(doses))
)

# Target dose
TD(fit, Delta = 0.5, direction = "increasing")
```

**SAS Macro: MCPMod**
Available from FDA website as qualified DDT.

"""

    def generate_monotone_trend_methodology(
        self,
        spec: MonotoneTrendTest
    ) -> str:
        """Generate monotone trend test methodology"""
        text = f"""
## Monotone Trend Test

### Method: {spec.test_type} Test

A test for monotone {'increasing' if spec.increasing else 'decreasing'} dose-response
trend will be performed.

"""

        if spec.test_type == "Williams":
            text += """
**Williams Test:**

A step-down procedure testing:
- H_k: Dose k = Dose k+1 = ... = Maximum dose
- Start with highest dose, step down if not significant

**Advantages:**
- Controls family-wise error rate
- More powerful than Dunnett for monotone trends
- Provides ordering information

**Test Statistic:**
For each step, compares pooled higher doses vs. control.

"""

        elif spec.test_type == "Cochran-Armitage":
            text += """
**Cochran-Armitage Trend Test:**

Tests for linear trend in proportions across ordered dose groups.

**Test Statistic:**
T = Σᵢ wᵢ(Rᵢ - nᵢp̄)

where:
- wᵢ = weight (typically dose level)
- Rᵢ = number of responses in group i
- nᵢ = sample size in group i
- p̄ = overall response rate

**Advantages:**
- Simple, intuitive
- Powerful for linear trends
- Commonly used in oncology

"""

        text += f"""
**Significance Level:** α = {spec.alpha}

**Interpretation:**
- Significant trend supports dose-response relationship
- Monotone assumption appropriate for most pharmacological effects
- Guides dose selection for later development

"""

        return text

    def generate_emax_model_code(self, model: EmaxModel, language: str = "R") -> str:
        """Generate code for fitting Emax model"""

        if language == "R":
            return f"""
# Fit Emax Model
library(drc)

# Emax model (Michaelis-Menten)
fit_emax <- drm(
    response ~ dose,
    data = dose_data,
    fct = DRC.emax(
        fixed = c(NA, NA, NA),  # E0, Emax, ED50
        names = c("E0", "Emax", "ED50")
    )
)

# Summary
summary(fit_emax)

# ED50 with confidence interval
ED(fit_emax, 50, interval = "delta", level = 0.95)

# Plot
plot(fit_emax, type = "all", log = "",
     xlab = "Dose (mg)", ylab = "Response")

# Predict
new_doses <- seq(0, 100, by = 1)
predictions <- predict(fit_emax, newdata = data.frame(dose = new_doses))
"""

        elif language == "SAS":
            return f"""
/* Fit Emax Model using PROC NLIN */

proc nlin data=dose_data method=gauss;
    parameters
        E0 = {model.e0}
        Emax = {model.emax}
        ED50 = {model.ed50};

    /* Emax equation */
    model response = E0 + Emax * dose / (ED50 + dose);

    /* Output predictions */
    output out=predictions predicted=pred residual=resid;
run;

/* Calculate ED50 confidence interval */
proc nlmixed data=dose_data;
    parms E0={model.e0} Emax={model.emax} ED50={model.ed50};

    mu = E0 + Emax * dose / (ED50 + dose);
    model response ~ normal(mu, sigma);

    /* Estimate ED50 */
    estimate "ED50" ED50;
run;
"""

        return ""


# Singleton instance
_dose_response_service: Optional[DoseResponseService] = None


def get_dose_response_service() -> DoseResponseService:
    """
    Get dose-response service instance.

    Returns:
        DoseResponseService instance
    """
    global _dose_response_service

    if _dose_response_service is None:
        _dose_response_service = DoseResponseService()

    return _dose_response_service
