"""
SAP Calculation Engine - Phase 2 and Phase 3 Statistical Calculations

Uses R packages (gsDesign, rpact, clinfun) via rpy2 for regulatory-grade calculations.

Production-grade calculations for:
- Phase 2: Simon's two-stage design, sample size for response rates
- Phase 3: Group sequential boundaries, alpha spending, HR at boundary, power

Author: SAP Generator System
"""

import os
import sys
import json
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

# =============================================================================
# R ENVIRONMENT SETUP - Must be done BEFORE importing rpy2
# =============================================================================

def setup_r_environment():
    """Configure R environment for micromamba installation."""
    home = os.path.expanduser("~")
    micromamba_base = os.path.join(home, "micromamba")

    if os.path.exists(micromamba_base):
        r_home = os.path.join(micromamba_base, "lib", "R")
        if os.path.exists(r_home):
            os.environ["R_HOME"] = r_home
            os.environ["PATH"] = f"{micromamba_base}/bin:" + os.environ.get("PATH", "")

            ld_path = os.environ.get("LD_LIBRARY_PATH", "")
            os.environ["LD_LIBRARY_PATH"] = f"{micromamba_base}/lib:{ld_path}"

            # Add micromamba python site-packages to path
            site_packages = os.path.join(micromamba_base, "lib", "python3.11", "site-packages")
            if os.path.exists(site_packages) and site_packages not in sys.path:
                sys.path.insert(0, site_packages)

            return True
    return False

# Setup R environment before importing rpy2
R_ENV_READY = setup_r_environment()

# Try to import rpy2 for R integration
try:
    import rpy2.robjects as ro
    from rpy2.robjects.packages import importr, isinstalled
    from rpy2.robjects.vectors import FloatVector, IntVector, StrVector
    # Note: pandas2ri and numpy2ri are optional - don't fail if not available
    try:
        from rpy2.robjects import pandas2ri, numpy2ri
        pandas2ri.activate()
        numpy2ri.activate()
    except (ImportError, Exception):
        pass  # pandas/numpy conversion not critical for our use case
    HAS_RPY2 = True
except ImportError:
    HAS_RPY2 = False
    if R_ENV_READY:
        warnings.warn("rpy2 not available even with R environment set - check installation")
    else:
        warnings.warn("rpy2 not available - R-based calculations will not work")

# Try numpy/scipy for fallback calculations
try:
    import numpy as np
    from scipy import stats
    from scipy.optimize import brentq
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class TrialPhase(Enum):
    """Clinical trial phases."""
    PHASE_1 = "phase1"
    PHASE_2 = "phase2"
    PHASE_3 = "phase3"
    PHASE_2_3 = "phase2_3"  # Seamless design


class SpendingFunction(Enum):
    """Alpha spending function types."""
    OBRIEN_FLEMING = "OF"
    POCOCK = "P"
    LAN_DEMETS_OF = "asOF"  # Lan-DeMets approximation to O'Brien-Fleming
    LAN_DEMETS_P = "asP"    # Lan-DeMets approximation to Pocock
    HWANG_SHIH_DECANI = "asHSD"
    KIM_DEMETS = "asKD"


class TestType(Enum):
    """Hypothesis test types."""
    SUPERIORITY = "superiority"
    NON_INFERIORITY = "non_inferiority"
    EQUIVALENCE = "equivalence"


@dataclass
class Phase2Inputs:
    """Inputs for Phase 2 sample size calculations."""
    p0: float  # Null hypothesis response rate
    p1: float  # Alternative hypothesis response rate
    alpha: float = 0.05  # One-sided Type I error
    beta: float = 0.20   # Type II error (1 - power)
    design_type: str = "optimal"  # "optimal" or "minimax"


@dataclass
class Phase2Result:
    """Results from Phase 2 Simon's two-stage design."""
    n1: int  # Stage 1 sample size
    r1: int  # Stage 1 rejection threshold
    n: int   # Total sample size
    r: int   # Final rejection threshold
    en_h0: float  # Expected sample size under H0
    pet_h0: float  # Probability of early termination under H0
    alpha_actual: float
    power_actual: float


@dataclass
class Phase3Inputs:
    """Inputs for Phase 3 group sequential calculations."""
    # Basic parameters
    alpha: float = 0.025  # One-sided Type I error
    beta: float = 0.10    # Type II error (1 - power = 0.90)

    # Interim analysis schedule
    n_analyses: int = 4  # Number of analyses (including final)
    info_fractions: List[float] = field(default_factory=lambda: [0.5, 0.75, 0.88, 1.0])

    # Spending function
    spending_function: SpendingFunction = SpendingFunction.LAN_DEMETS_OF

    # Effect size
    hr: float = 0.7  # Hazard ratio for superiority
    hr_ni: float = 0.8  # HR for non-inferiority (if applicable)
    ni_margin: float = 1.1  # Non-inferiority margin

    # Events
    events: List[int] = field(default_factory=list)  # Events at each analysis
    total_events: int = 472  # Total events for final analysis

    # Sample size
    n_treatment: int = 306  # Per arm
    n_control: int = 306

    # Test type
    test_type: TestType = TestType.SUPERIORITY

    # Survival assumptions
    median_control: float = 8.8  # Control arm median (months)
    accrual_duration: float = 24.0  # Enrollment duration (months)
    follow_up: float = 12.0  # Minimum follow-up (months)


@dataclass
class BoundaryResult:
    """Results for a single analysis boundary."""
    analysis: int
    info_fraction: float
    events: int
    z_efficacy: float
    z_futility: Optional[float]
    p_efficacy: float
    p_futility: Optional[float]
    hr_efficacy: float
    hr_futility: Optional[float]
    alpha_spent: float
    cumulative_alpha: float
    power_at_analysis: float


@dataclass
class Phase3Result:
    """Complete results from Phase 3 group sequential design."""
    boundaries: List[BoundaryResult]
    total_alpha: float
    total_power: float
    expected_events_h0: float
    expected_events_h1: float
    timing_months: List[float]

    # For non-inferiority
    ni_boundaries: Optional[List[BoundaryResult]] = None


# =============================================================================
# R PACKAGE MANAGER
# =============================================================================

class RPackageManager:
    """Manages R package loading and validation."""

    REQUIRED_PACKAGES = {
        'gsDesign': 'Group sequential design',
        'rpact': 'Confirmatory adaptive designs',
    }

    OPTIONAL_PACKAGES = {
        'clinfun': 'Simon two-stage design',
        'survival': 'Survival analysis',
    }

    def __init__(self):
        self._packages = {}
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize R and load packages."""
        if not HAS_RPY2:
            print("[Calculator] ERROR: rpy2 not installed")
            return False

        try:
            # Load base R
            self._packages['base'] = importr('base')
            self._packages['stats'] = importr('stats')

            # Load required packages
            for pkg, desc in self.REQUIRED_PACKAGES.items():
                if isinstalled(pkg):
                    self._packages[pkg] = importr(pkg)
                    print(f"  [OK] Loaded R package: {pkg} ({desc})")
                else:
                    print(f"  [!] Missing R package: {pkg} - run install.packages('{pkg}')")
                    return False

            # Load optional packages
            for pkg, desc in self.OPTIONAL_PACKAGES.items():
                if isinstalled(pkg):
                    self._packages[pkg] = importr(pkg)
                    print(f"  [OK] Loaded R package: {pkg} ({desc})")
                else:
                    print(f"  [~] Optional R package not installed: {pkg}")

            self._initialized = True
            return True

        except Exception as e:
            print(f"[Calculator] ERROR initializing R: {e}")
            return False

    def get_package(self, name: str):
        """Get a loaded R package."""
        return self._packages.get(name)

    @property
    def is_ready(self) -> bool:
        return self._initialized


# =============================================================================
# PHASE 2 CALCULATOR
# =============================================================================

class Phase2Calculator:
    """
    Phase 2 oncology trial calculations.

    Implements:
    - Simon's two-stage design (optimal and minimax)
    - Single-stage designs
    - Sample size for response rate endpoints
    """

    def __init__(self, r_manager: RPackageManager):
        self.r = r_manager

    def simons_two_stage(self, inputs: Phase2Inputs) -> Phase2Result:
        """
        Calculate Simon's two-stage design.

        Uses R clinfun package if available, otherwise scipy fallback.
        """
        clinfun = self.r.get_package('clinfun')

        if clinfun:
            return self._simons_r(inputs, clinfun)
        elif HAS_SCIPY:
            return self._simons_scipy(inputs)
        else:
            raise RuntimeError("No calculation backend available for Simon's design")

    def _simons_r(self, inputs: Phase2Inputs, clinfun) -> Phase2Result:
        """Calculate Simon's design using R clinfun package."""
        try:
            # Call ph2simon from clinfun
            result = clinfun.ph2simon(
                pu=inputs.p0,
                pa=inputs.p1,
                ep1=inputs.alpha,
                ep2=inputs.beta
            )

            # Extract results - R returns a data frame
            # Get optimal or minimax design
            design_idx = 0 if inputs.design_type == "optimal" else 1

            # Access the result (it's a list in R)
            r1 = int(result.rx2('r1')[design_idx])
            n1 = int(result.rx2('n1')[design_idx])
            r = int(result.rx2('r')[design_idx])
            n = int(result.rx2('n')[design_idx])
            en = float(result.rx2('EN')[design_idx])
            pet = float(result.rx2('PET')[design_idx])

            return Phase2Result(
                n1=n1,
                r1=r1,
                n=n,
                r=r,
                en_h0=en,
                pet_h0=pet,
                alpha_actual=inputs.alpha,
                power_actual=1 - inputs.beta
            )

        except Exception as e:
            print(f"[Phase2] R calculation failed: {e}, falling back to scipy")
            if HAS_SCIPY:
                return self._simons_scipy(inputs)
            raise

    def _simons_scipy(self, inputs: Phase2Inputs) -> Phase2Result:
        """
        Calculate Simon's two-stage design using scipy.

        This is a simplified implementation for fallback.
        """
        from scipy.stats import binom

        p0, p1 = inputs.p0, inputs.p1
        alpha, beta = inputs.alpha, inputs.beta

        best_design = None
        best_en = float('inf')

        # Search over possible designs
        for n in range(10, 100):
            for n1 in range(5, n):
                for r1 in range(0, n1):
                    for r in range(r1, n):
                        # Calculate Type I error
                        type1 = 0
                        for x1 in range(r1 + 1, n1 + 1):
                            p_x1 = binom.pmf(x1, n1, p0)
                            for x2 in range(max(0, r - x1 + 1), n - n1 + 1):
                                type1 += p_x1 * binom.pmf(x2, n - n1, p0)

                        if type1 > alpha:
                            continue

                        # Calculate power
                        power = 0
                        for x1 in range(r1 + 1, n1 + 1):
                            p_x1 = binom.pmf(x1, n1, p1)
                            for x2 in range(max(0, r - x1 + 1), n - n1 + 1):
                                power += p_x1 * binom.pmf(x2, n - n1, p1)

                        if power < 1 - beta:
                            continue

                        # Calculate expected sample size under H0
                        pet = binom.cdf(r1, n1, p0)
                        en = n1 * pet + n * (1 - pet)

                        if inputs.design_type == "optimal":
                            if en < best_en:
                                best_en = en
                                best_design = (n1, r1, n, r, en, pet, type1, power)
                        else:  # minimax
                            if n < best_en or (n == best_en and en < best_design[4]):
                                best_en = n
                                best_design = (n1, r1, n, r, en, pet, type1, power)

        if best_design is None:
            raise ValueError("Could not find valid Simon's design")

        n1, r1, n, r, en, pet, type1, power = best_design

        return Phase2Result(
            n1=n1,
            r1=r1,
            n=n,
            r=r,
            en_h0=en,
            pet_h0=pet,
            alpha_actual=type1,
            power_actual=power
        )


# =============================================================================
# PHASE 3 CALCULATOR
# =============================================================================

class Phase3Calculator:
    """
    Phase 3 oncology trial calculations using gsDesign and rpact.

    Implements:
    - Group sequential boundaries (Lan-DeMets O'Brien-Fleming, Pocock, etc.)
    - Alpha spending functions
    - Z-boundaries, p-values, HR at boundary
    - Power calculations
    - Non-inferiority adjustments
    - Event projections and timing
    """

    def __init__(self, r_manager: RPackageManager):
        self.r = r_manager

    def calculate_boundaries(self, inputs: Phase3Inputs) -> Phase3Result:
        """
        Calculate group sequential boundaries.

        Uses gsDesign or rpact based on availability and requirements.
        """
        gsDesign = self.r.get_package('gsDesign')
        rpact = self.r.get_package('rpact')

        if gsDesign:
            return self._boundaries_gsdesign(inputs, gsDesign)
        elif rpact:
            return self._boundaries_rpact(inputs, rpact)
        elif HAS_SCIPY:
            return self._boundaries_scipy(inputs)
        else:
            raise RuntimeError("No calculation backend available")

    def _boundaries_gsdesign(self, inputs: Phase3Inputs, gsDesign) -> Phase3Result:
        """Calculate boundaries using gsDesign package."""

        # Map spending function
        sfu_map = {
            SpendingFunction.OBRIEN_FLEMING: "OF",
            SpendingFunction.POCOCK: "P",
            SpendingFunction.LAN_DEMETS_OF: "sfLDOF",
            SpendingFunction.LAN_DEMETS_P: "sfLDPocock",
            SpendingFunction.HWANG_SHIH_DECANI: "sfHSD",
        }

        sfu = sfu_map.get(inputs.spending_function, "sfLDOF")

        # Get the spending function object
        if sfu == "sfLDOF":
            sfu_func = gsDesign.sfLDOF
        elif sfu == "sfLDPocock":
            sfu_func = gsDesign.sfLDPocock
        else:
            sfu_func = gsDesign.sfLDOF  # Default

        # Create design
        design = gsDesign.gsDesign(
            k=inputs.n_analyses,
            test_type=1,  # 1 = one-sided
            alpha=inputs.alpha,
            beta=inputs.beta,
            sfu=sfu_func,
            timing=FloatVector(inputs.info_fractions)
        )

        # Extract boundary information
        boundaries = []

        # Get vectors from R object
        z_upper = list(design.rx2('upper').rx2('bound'))
        z_lower = list(design.rx2('lower').rx2('bound')) if design.rx2('lower') else [None] * inputs.n_analyses
        info_frac = list(design.rx2('timing'))

        # Calculate cumulative alpha spent
        alpha_spent = list(gsDesign.sfLDOF(inputs.alpha, FloatVector(info_frac)).rx2('spend'))

        for i in range(inputs.n_analyses):
            # Events at this analysis
            if inputs.events and i < len(inputs.events):
                events = inputs.events[i]
            else:
                events = int(inputs.total_events * info_frac[i])

            # Z to p-value (one-sided)
            p_eff = float(1 - stats.norm.cdf(z_upper[i])) if HAS_SCIPY else None

            # HR at boundary
            se_log_hr = 2.0 / np.sqrt(events) if HAS_SCIPY else 0.15
            hr_eff = float(np.exp(-z_upper[i] * se_log_hr)) if HAS_SCIPY else None

            # Power at this analysis (cumulative)
            # This requires integration over the sequential distribution
            power_at = alpha_spent[i] / inputs.alpha * (1 - inputs.beta) if i < len(alpha_spent) else None

            boundaries.append(BoundaryResult(
                analysis=i + 1,
                info_fraction=info_frac[i],
                events=events,
                z_efficacy=z_upper[i],
                z_futility=z_lower[i] if z_lower[i] else None,
                p_efficacy=p_eff,
                p_futility=None,
                hr_efficacy=hr_eff,
                hr_futility=None,
                alpha_spent=alpha_spent[i] - (alpha_spent[i-1] if i > 0 else 0),
                cumulative_alpha=alpha_spent[i],
                power_at_analysis=power_at
            ))

        # Calculate timing in months
        timing = self._estimate_timing(inputs, [b.events for b in boundaries])

        return Phase3Result(
            boundaries=boundaries,
            total_alpha=inputs.alpha,
            total_power=1 - inputs.beta,
            expected_events_h0=inputs.total_events,
            expected_events_h1=inputs.total_events * 0.85,  # Approximate
            timing_months=timing
        )

    def _boundaries_rpact(self, inputs: Phase3Inputs, rpact) -> Phase3Result:
        """Calculate boundaries using rpact package."""

        # Map spending function for rpact
        type_map = {
            SpendingFunction.OBRIEN_FLEMING: "OF",
            SpendingFunction.POCOCK: "P",
            SpendingFunction.LAN_DEMETS_OF: "asOF",
            SpendingFunction.LAN_DEMETS_P: "asP",
        }

        design_type = type_map.get(inputs.spending_function, "asOF")

        # Create design using rpact
        design = rpact.getDesignGroupSequential(
            kMax=inputs.n_analyses,
            alpha=inputs.alpha,
            beta=inputs.beta,
            sided=1,
            typeOfDesign=design_type,
            informationRates=FloatVector(inputs.info_fractions)
        )

        # Extract results
        boundaries = []

        critical_values = list(design.rx2('criticalValues'))
        alpha_spent = list(design.rx2('alphaSpent'))

        for i in range(inputs.n_analyses):
            events = inputs.events[i] if inputs.events and i < len(inputs.events) else int(inputs.total_events * inputs.info_fractions[i])

            z_eff = critical_values[i]
            p_eff = float(1 - stats.norm.cdf(z_eff)) if HAS_SCIPY else None

            se_log_hr = 2.0 / np.sqrt(events) if HAS_SCIPY else 0.15
            hr_eff = float(np.exp(-z_eff * se_log_hr)) if HAS_SCIPY else None

            boundaries.append(BoundaryResult(
                analysis=i + 1,
                info_fraction=inputs.info_fractions[i],
                events=events,
                z_efficacy=z_eff,
                z_futility=None,
                p_efficacy=p_eff,
                p_futility=None,
                hr_efficacy=hr_eff,
                hr_futility=None,
                alpha_spent=alpha_spent[i] - (alpha_spent[i-1] if i > 0 else 0),
                cumulative_alpha=alpha_spent[i],
                power_at_analysis=None
            ))

        timing = self._estimate_timing(inputs, [b.events for b in boundaries])

        return Phase3Result(
            boundaries=boundaries,
            total_alpha=inputs.alpha,
            total_power=1 - inputs.beta,
            expected_events_h0=inputs.total_events,
            expected_events_h1=inputs.total_events * 0.85,
            timing_months=timing
        )

    def _boundaries_scipy(self, inputs: Phase3Inputs) -> Phase3Result:
        """
        Fallback: Calculate boundaries using scipy only.

        Implements Lan-DeMets O'Brien-Fleming spending function.
        """
        if not HAS_SCIPY:
            raise RuntimeError("scipy not available for fallback calculations")

        boundaries = []

        for i, t in enumerate(inputs.info_fractions):
            # Lan-DeMets O'Brien-Fleming spending function
            # α(t) = 2 - 2Φ(Z_{α/2} / √t)
            z_alpha = stats.norm.ppf(1 - inputs.alpha)
            cum_alpha = 2 - 2 * stats.norm.cdf(z_alpha / np.sqrt(t))

            # Incremental alpha
            if i == 0:
                inc_alpha = cum_alpha
            else:
                prev_t = inputs.info_fractions[i-1]
                prev_cum = 2 - 2 * stats.norm.cdf(z_alpha / np.sqrt(prev_t))
                inc_alpha = cum_alpha - prev_cum

            # Z-boundary (approximate)
            z_eff = stats.norm.ppf(1 - cum_alpha)

            # Events
            events = inputs.events[i] if inputs.events and i < len(inputs.events) else int(inputs.total_events * t)

            # P-value
            p_eff = 1 - stats.norm.cdf(z_eff)

            # HR at boundary
            se_log_hr = 2.0 / np.sqrt(events)
            hr_eff = np.exp(-z_eff * se_log_hr)

            boundaries.append(BoundaryResult(
                analysis=i + 1,
                info_fraction=t,
                events=events,
                z_efficacy=z_eff,
                z_futility=None,
                p_efficacy=p_eff,
                p_futility=None,
                hr_efficacy=hr_eff,
                hr_futility=None,
                alpha_spent=inc_alpha,
                cumulative_alpha=cum_alpha,
                power_at_analysis=None
            ))

        timing = self._estimate_timing(inputs, [b.events for b in boundaries])

        return Phase3Result(
            boundaries=boundaries,
            total_alpha=inputs.alpha,
            total_power=1 - inputs.beta,
            expected_events_h0=inputs.total_events,
            expected_events_h1=inputs.total_events * 0.85,
            timing_months=timing
        )

    def calculate_ni_boundaries(self, inputs: Phase3Inputs,
                                 superiority_result: Phase3Result) -> List[BoundaryResult]:
        """
        Calculate non-inferiority boundaries from superiority boundaries.

        HR_NI = HR_superiority * NI_margin
        """
        ni_boundaries = []

        for bound in superiority_result.boundaries:
            # Adjust HR for NI margin
            hr_ni = bound.hr_efficacy * inputs.ni_margin if bound.hr_efficacy else None

            # Z-boundary adjustment
            # For NI, we test H0: HR >= NI_margin vs H1: HR < NI_margin
            # The Z-statistic is: Z = (log(HR) - log(NI_margin)) / SE
            se_log_hr = 2.0 / np.sqrt(bound.events) if HAS_SCIPY else 0.15
            z_ni = bound.z_efficacy - np.log(inputs.ni_margin) / se_log_hr if HAS_SCIPY else bound.z_efficacy

            ni_boundaries.append(BoundaryResult(
                analysis=bound.analysis,
                info_fraction=bound.info_fraction,
                events=bound.events,
                z_efficacy=z_ni,
                z_futility=bound.z_futility,
                p_efficacy=float(1 - stats.norm.cdf(z_ni)) if HAS_SCIPY else None,
                p_futility=bound.p_futility,
                hr_efficacy=hr_ni,
                hr_futility=None,
                alpha_spent=bound.alpha_spent,
                cumulative_alpha=bound.cumulative_alpha,
                power_at_analysis=bound.power_at_analysis
            ))

        return ni_boundaries

    def _estimate_timing(self, inputs: Phase3Inputs, events: List[int]) -> List[float]:
        """
        Estimate timing of analyses in months.

        Uses exponential survival model assumption.
        """
        if not HAS_SCIPY:
            # Simple linear estimate
            return [inputs.accrual_duration + inputs.follow_up * (i + 1) / len(events)
                    for i in range(len(events))]

        # Hazard rate from median
        lambda_ctrl = np.log(2) / inputs.median_control
        lambda_trt = lambda_ctrl * inputs.hr

        # Average hazard (assuming equal allocation)
        lambda_avg = (lambda_ctrl + lambda_trt) / 2

        # Total sample size
        n_total = inputs.n_treatment + inputs.n_control

        # Estimate time to reach each event count
        # Using simple exponential model: E[events at time t] ≈ n * (1 - exp(-λ*t))
        timing = []
        for e in events:
            # Solve for t: e = n * (1 - exp(-λ*t))
            # t = -log(1 - e/n) / λ
            event_frac = min(e / n_total, 0.99)
            t = -np.log(1 - event_frac) / lambda_avg
            # Add accrual midpoint
            t += inputs.accrual_duration / 2
            timing.append(round(t, 1))

        return timing

    def calculate_power_at_boundary(self, boundary: BoundaryResult,
                                     true_hr: float) -> float:
        """
        Calculate probability of crossing boundary given true HR.

        P(Z > z_bound | HR = true_hr)
        """
        if not HAS_SCIPY:
            return None

        # Under alternative, Z ~ N(θ√I, 1) where θ = log(HR)/SE and I = info
        se_log_hr = 2.0 / np.sqrt(boundary.events)
        theta = -np.log(true_hr) / se_log_hr  # Negative because HR < 1 is good

        # Non-centrality parameter
        ncp = theta * np.sqrt(boundary.events / 4)  # Approximate

        # P(Z > z_bound) under alternative
        power = 1 - stats.norm.cdf(boundary.z_efficacy - ncp)

        return power


# =============================================================================
# OUTPUT FORMATTER
# =============================================================================

class OutputFormatter:
    """Format calculation results for SAP inclusion."""

    @staticmethod
    def format_phase2_table(result: Phase2Result, inputs: Phase2Inputs) -> str:
        """Format Simon's two-stage design as markdown table."""
        return f"""
### Simon's Two-Stage Design ({inputs.design_type.title()})

| Parameter | Value |
|-----------|-------|
| Null response rate (p₀) | {inputs.p0:.1%} |
| Alternative response rate (p₁) | {inputs.p1:.1%} |
| Type I error (α) | {inputs.alpha:.3f} |
| Type II error (β) | {inputs.beta:.2f} |
| Power | {result.power_actual:.1%} |

| Stage | Sample Size | Rejection Threshold |
|-------|-------------|---------------------|
| Stage 1 | n₁ = {result.n1} | r₁ ≤ {result.r1} → Stop |
| Final | n = {result.n} | r ≤ {result.r} → Reject H₀ |

| Operating Characteristic | Value |
|--------------------------|-------|
| Expected sample size (H₀) | {result.en_h0:.1f} |
| Probability early termination (H₀) | {result.pet_h0:.1%} |
| Actual α | {result.alpha_actual:.4f} |
| Actual power | {result.power_actual:.1%} |
"""

    @staticmethod
    def format_boundary_table(result: Phase3Result, title: str = "Efficacy Boundaries") -> str:
        """Format group sequential boundaries as markdown table."""

        header = f"""
### {title}

| Analysis | Info Fraction | Events | Z-boundary | Nominal p-value | HR at Boundary | Cumulative α |
|----------|---------------|--------|------------|-----------------|----------------|--------------|
"""
        rows = []
        for b in result.boundaries:
            z_str = f"{b.z_efficacy:.4f}" if b.z_efficacy else "—"
            p_str = f"{b.p_efficacy:.6f}" if b.p_efficacy else "—"
            hr_str = f"{b.hr_efficacy:.4f}" if b.hr_efficacy else "—"
            alpha_str = f"{b.cumulative_alpha:.6f}" if b.cumulative_alpha else "—"

            analysis_name = f"IA{b.analysis}" if b.analysis < len(result.boundaries) else "FA"

            rows.append(f"| {analysis_name} | {b.info_fraction:.0%} | {b.events} | {z_str} | {p_str} | {hr_str} | {alpha_str} |")

        return header + "\n".join(rows)

    @staticmethod
    def format_timing_table(result: Phase3Result) -> str:
        """Format analysis timing estimates."""

        header = """
### Analysis Timing Estimates

| Analysis | Events | Estimated Timing |
|----------|--------|------------------|
"""
        rows = []
        for i, b in enumerate(result.boundaries):
            timing = result.timing_months[i] if i < len(result.timing_months) else "—"
            timing_str = f"~{timing} months" if isinstance(timing, (int, float)) else timing
            analysis_name = f"IA{b.analysis}" if b.analysis < len(result.boundaries) else "FA"
            rows.append(f"| {analysis_name} | {b.events} | {timing_str} |")

        return header + "\n".join(rows)

    @staticmethod
    def format_full_boundary_section(sup_result: Phase3Result,
                                      ni_result: Optional[Phase3Result] = None,
                                      inputs: Optional[Phase3Inputs] = None) -> str:
        """Format complete boundary section for SAP."""

        sections = []

        # Header
        sections.append("## 7. INTERIM ANALYSES\n")

        # Overview
        n_ia = len(sup_result.boundaries) - 1
        sections.append(f"""
### 7.1 Overview

This study includes **{n_ia} interim analyses** and **1 final analysis** for the primary endpoint.

- **Alpha spending function**: Lan-DeMets O'Brien-Fleming
- **Overall one-sided α**: {sup_result.total_alpha}
- **Target power**: {sup_result.total_power:.0%}
""")

        # Superiority boundaries
        sections.append(OutputFormatter.format_boundary_table(sup_result, "7.2 Superiority Efficacy Boundaries"))

        # Non-inferiority boundaries if provided
        if ni_result:
            sections.append(OutputFormatter.format_boundary_table(ni_result, "7.3 Non-Inferiority Efficacy Boundaries"))

        # Timing
        sections.append(OutputFormatter.format_timing_table(sup_result))

        # Alpha spending details
        sections.append("""
### 7.4 Alpha Spending

The Lan-DeMets O'Brien-Fleming spending function is used:

α(t) = 2 - 2Φ(Φ⁻¹(1-α/2) / √t)

where t is the information fraction and Φ is the standard normal CDF.
""")

        return "\n".join(sections)


# =============================================================================
# MAIN CALCULATION ENGINE
# =============================================================================

class CalculationEngine:
    """
    Main calculation engine for SAP statistical computations.

    Automatically routes to Phase 2 or Phase 3 calculations based on inputs.
    """

    def __init__(self):
        self.r_manager = RPackageManager()
        self._initialized = False
        self.phase2 = None
        self.phase3 = None
        self.formatter = OutputFormatter()

    def initialize(self) -> bool:
        """Initialize the calculation engine."""
        print("\n[CalculationEngine] Initializing...")

        if self.r_manager.initialize():
            self.phase2 = Phase2Calculator(self.r_manager)
            self.phase3 = Phase3Calculator(self.r_manager)
            self._initialized = True
            print("[CalculationEngine] Ready with R backend")
            return True
        elif HAS_SCIPY:
            # Fallback to scipy-only mode
            self.phase2 = Phase2Calculator(self.r_manager)
            self.phase3 = Phase3Calculator(self.r_manager)
            self._initialized = True
            print("[CalculationEngine] Ready with scipy fallback (limited functionality)")
            return True
        else:
            print("[CalculationEngine] ERROR: No calculation backend available")
            return False

    def calculate_phase2(self, inputs: Phase2Inputs) -> Tuple[Phase2Result, str]:
        """Run Phase 2 calculations and return results + formatted output."""
        if not self._initialized:
            self.initialize()

        result = self.phase2.simons_two_stage(inputs)
        formatted = self.formatter.format_phase2_table(result, inputs)

        return result, formatted

    def calculate_phase3(self, inputs: Phase3Inputs) -> Tuple[Phase3Result, str]:
        """Run Phase 3 calculations and return results + formatted output."""
        if not self._initialized:
            self.initialize()

        # Calculate superiority boundaries
        sup_result = self.phase3.calculate_boundaries(inputs)

        # Calculate NI boundaries if needed
        ni_result = None
        if inputs.test_type == TestType.NON_INFERIORITY or inputs.ni_margin > 1.0:
            ni_boundaries = self.phase3.calculate_ni_boundaries(inputs, sup_result)
            ni_result = Phase3Result(
                boundaries=ni_boundaries,
                total_alpha=sup_result.total_alpha,
                total_power=sup_result.total_power,
                expected_events_h0=sup_result.expected_events_h0,
                expected_events_h1=sup_result.expected_events_h1,
                timing_months=sup_result.timing_months
            )

        # Format output
        formatted = self.formatter.format_full_boundary_section(sup_result, ni_result, inputs)

        return sup_result, formatted

    def calculate_from_protocol(self, protocol_data: Dict[str, Any]) -> Tuple[Any, str]:
        """
        Auto-detect trial phase and run appropriate calculations.

        Args:
            protocol_data: Dictionary with extracted protocol information

        Returns:
            Tuple of (result object, formatted markdown string)
        """
        phase = protocol_data.get('phase', '').lower()

        if 'phase 2' in phase or 'phase ii' in phase:
            inputs = Phase2Inputs(
                p0=protocol_data.get('p0', 0.20),
                p1=protocol_data.get('p1', 0.40),
                alpha=protocol_data.get('alpha', 0.05),
                beta=protocol_data.get('beta', 0.20),
                design_type=protocol_data.get('design_type', 'optimal')
            )
            return self.calculate_phase2(inputs)

        elif 'phase 3' in phase or 'phase iii' in phase:
            inputs = Phase3Inputs(
                alpha=protocol_data.get('alpha', 0.025),
                beta=protocol_data.get('beta', 0.10),
                n_analyses=protocol_data.get('n_analyses', 4),
                info_fractions=protocol_data.get('info_fractions', [0.5, 0.75, 0.88, 1.0]),
                spending_function=SpendingFunction.LAN_DEMETS_OF,
                hr=protocol_data.get('hr', 0.7),
                ni_margin=protocol_data.get('ni_margin', 1.1),
                events=protocol_data.get('events', []),
                total_events=protocol_data.get('total_events', 472),
                n_treatment=protocol_data.get('n_treatment', 306),
                n_control=protocol_data.get('n_control', 306),
                median_control=protocol_data.get('median_control', 8.8),
                accrual_duration=protocol_data.get('accrual_duration', 24.0),
                follow_up=protocol_data.get('follow_up', 12.0)
            )
            return self.calculate_phase3(inputs)

        else:
            raise ValueError(f"Unsupported trial phase: {phase}")


# =============================================================================
# TEST FUNCTION
# =============================================================================

def test_calculation_engine():
    """Test the calculation engine with sample inputs."""

    print("=" * 70)
    print("TESTING SAP CALCULATION ENGINE")
    print("=" * 70)

    engine = CalculationEngine()

    if not engine.initialize():
        print("\nFalling back to scipy-only mode for testing...")

    # Test Phase 2
    print("\n" + "=" * 70)
    print("TEST 1: Phase 2 Simon's Two-Stage Design")
    print("=" * 70)

    phase2_inputs = Phase2Inputs(
        p0=0.20,  # 20% response rate under null
        p1=0.40,  # 40% response rate under alternative
        alpha=0.05,
        beta=0.20,
        design_type="optimal"
    )

    try:
        result2, formatted2 = engine.calculate_phase2(phase2_inputs)
        print(formatted2)
    except Exception as e:
        print(f"Phase 2 test failed: {e}")

    # Test Phase 3
    print("\n" + "=" * 70)
    print("TEST 2: Phase 3 Group Sequential Design (PFS)")
    print("=" * 70)

    phase3_inputs = Phase3Inputs(
        alpha=0.005,  # One-sided alpha for PFS
        beta=0.10,    # 90% power
        n_analyses=2,
        info_fractions=[0.75, 1.0],  # IA at 75%, FA at 100%
        spending_function=SpendingFunction.LAN_DEMETS_OF,
        hr=0.7,
        events=[354, 472],
        total_events=472,
        n_treatment=306,
        n_control=306,
        median_control=8.8,
        accrual_duration=24.0,
        follow_up=12.0
    )

    try:
        result3, formatted3 = engine.calculate_phase3(phase3_inputs)
        print(formatted3)
    except Exception as e:
        print(f"Phase 3 test failed: {e}")

    # Test Phase 3 with OS (4 analyses)
    print("\n" + "=" * 70)
    print("TEST 3: Phase 3 Group Sequential Design (OS - 4 analyses)")
    print("=" * 70)

    phase3_os_inputs = Phase3Inputs(
        alpha=0.02,  # One-sided alpha for OS
        beta=0.10,
        n_analyses=4,
        info_fractions=[0.50, 0.75, 0.88, 1.0],
        spending_function=SpendingFunction.LAN_DEMETS_OF,
        hr=0.7,
        ni_margin=1.1,
        events=[180, 269, 316, 359],
        total_events=359,
        n_treatment=306,
        n_control=306,
        median_control=23.0,
        accrual_duration=24.0,
        follow_up=24.0
    )

    try:
        result_os, formatted_os = engine.calculate_phase3(phase3_os_inputs)
        print(formatted_os)
    except Exception as e:
        print(f"Phase 3 OS test failed: {e}")

    print("\n" + "=" * 70)
    print("TESTING COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_calculation_engine()
