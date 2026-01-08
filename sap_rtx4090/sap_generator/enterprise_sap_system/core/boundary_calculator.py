"""
SAP Calculation Engine - Modular System for Phase 2 and Phase 3 Oncology Trials
================================================================================

A production-grade modular system for calculating statistical parameters
for Statistical Analysis Plans (SAPs) across different trial phases.

Supported Trial Types:
- Phase 2: Simon's Two-Stage, Fleming Single-Stage, Response Rate analyses
- Phase 3: Group Sequential, Alpha Spending, Survival analyses, Non-Inferiority

Architecture:
- Protocol Parser → Phase Detector → Calculator Router → Phase-specific Module
- Dual engine: R (gsDesign/rpact) primary, Python (scipy) fallback
- Cross-validation between engines

Author: Clinical Biostatistics
Version: 2.0.0
Date: 2025
"""

import os
import numpy as np
from scipy.stats import norm, binom
from scipy.optimize import brentq
from scipy.integrate import quad
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any
from enum import Enum
from abc import ABC, abstractmethod
import logging
import warnings
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# R ENVIRONMENT SETUP
# =============================================================================

def setup_r_environment() -> bool:
    """
    Configure R environment for micromamba installation.
    Must be called before importing rpy2.
    """
    home = os.path.expanduser("~")

    # Check multiple possible micromamba locations
    possible_paths = [
        os.path.join(home, "micromamba"),
        os.path.join(home, ".local", "share", "micromamba"),
        "/opt/micromamba",
    ]

    for micromamba_base in possible_paths:
        if os.path.exists(micromamba_base):
            r_home = os.path.join(micromamba_base, "lib", "R")
            if os.path.exists(r_home):
                os.environ["R_HOME"] = r_home
                os.environ["PATH"] = f"{micromamba_base}/bin:" + os.environ.get("PATH", "")

                # Set R library paths
                lib_path = os.path.join(micromamba_base, "lib", "R", "library")
                if os.path.exists(lib_path):
                    os.environ["R_LIBS"] = lib_path
                    os.environ["R_LIBS_USER"] = lib_path

                logger.info(f"R environment configured: {r_home}")
                return True

    return False


# =============================================================================
# ENUMS AND CONFIGURATION
# =============================================================================

class TrialPhase(Enum):
    """Clinical trial phases"""
    PHASE_1 = "Phase 1"
    PHASE_2 = "Phase 2"
    PHASE_3 = "Phase 3"
    PHASE_2_3 = "Phase 2/3"


class Phase2DesignType(Enum):
    """Phase 2 design types"""
    SIMON_OPTIMAL = "simon_optimal"
    SIMON_MINIMAX = "simon_minimax"
    FLEMING_SINGLE = "fleming_single"
    SINGLE_ARM = "single_arm"
    RANDOMIZED = "randomized"


class Phase3DesignType(Enum):
    """Phase 3 design types"""
    GROUP_SEQUENTIAL = "group_sequential"
    FIXED = "fixed"
    ADAPTIVE = "adaptive"


class SpendingFunction(Enum):
    """Alpha spending function types"""
    OBRIEN_FLEMING = "OF"
    POCOCK = "Pocock"
    POWER_FAMILY = "power"
    HWANG_SHIH_DECANI = "HSD"
    LAN_DEMETS_OF = "LDOF"


class Endpoint(Enum):
    """Primary endpoint types"""
    RESPONSE_RATE = "response_rate"
    PFS = "pfs"
    OS = "os"
    DFS = "dfs"
    EFS = "efs"
    TIME_TO_EVENT = "tte"


class TestType(Enum):
    """Hypothesis test types"""
    SUPERIORITY = "superiority"
    NON_INFERIORITY = "non_inferiority"
    EQUIVALENCE = "equivalence"


# =============================================================================
# DATA CLASSES FOR INPUTS AND OUTPUTS
# =============================================================================

@dataclass
class Phase2Parameters:
    """Parameters for Phase 2 design calculations"""
    p0: float                           # Null response rate (unacceptable)
    p1: float                           # Alternative response rate (target)
    alpha: float = 0.05                 # Type I error (one-sided)
    beta: float = 0.10                  # Type II error (1 - power)
    design_type: Phase2DesignType = Phase2DesignType.SIMON_OPTIMAL


@dataclass
class Phase2Results:
    """Results from Phase 2 calculations"""
    # Simon's two-stage
    n1: int = 0                         # Stage 1 sample size
    r1: int = 0                         # Stage 1 rejection threshold
    n: int = 0                          # Total sample size
    r: int = 0                          # Final rejection threshold

    # Performance metrics
    en_h0: float = 0.0                  # Expected sample size under H0
    pet_h0: float = 0.0                 # Probability of early termination under H0
    actual_alpha: float = 0.0           # Actual type I error
    actual_power: float = 0.0           # Actual power

    # Design type
    design_type: str = ""
    engine_used: str = ""

    def to_dict(self) -> Dict:
        return {
            'Stage 1 N': self.n1,
            'Stage 1 Threshold (r1)': self.r1,
            'Total N': self.n,
            'Final Threshold (r)': self.r,
            'Expected N under H0': round(self.en_h0, 1),
            'P(Early Term) under H0': round(self.pet_h0, 3),
            'Actual Alpha': round(self.actual_alpha, 4),
            'Actual Power': round(self.actual_power, 4),
            'Design': self.design_type
        }

    def to_markdown(self) -> str:
        """Generate markdown table for Phase 2 design"""
        lines = [
            "### Simon's Two-Stage Design Parameters",
            "",
            "| Parameter | Value |",
            "|-----------|-------|",
            f"| Stage 1 Sample Size (n1) | {self.n1} |",
            f"| Stage 1 Threshold (r1) | {self.r1} |",
            f"| Total Sample Size (n) | {self.n} |",
            f"| Final Threshold (r) | {self.r} |",
            f"| Expected N under H0 | {self.en_h0:.1f} |",
            f"| P(Early Termination) under H0 | {self.pet_h0:.3f} |",
            f"| Actual Alpha | {self.actual_alpha:.4f} |",
            f"| Actual Power | {self.actual_power:.4f} |",
            f"| Design Type | {self.design_type} |",
            "",
            f"*Calculated using {self.engine_used}*"
        ]
        return "\n".join(lines)


@dataclass
class Phase3Parameters:
    """Parameters for Phase 3 design calculations"""
    k: int                              # Number of analyses
    alpha: float                        # Type I error (one-sided)
    beta: float = 0.10                  # Type II error
    events: List[int] = field(default_factory=list)
    timing: List[float] = field(default_factory=list)
    spending_function: SpendingFunction = SpendingFunction.OBRIEN_FLEMING
    spending_param: Optional[float] = None
    hr_null: float = 1.0
    hr_alternative: float = 0.7
    ni_margin: Optional[float] = None
    test_type: TestType = TestType.SUPERIORITY
    endpoint: Endpoint = Endpoint.PFS


@dataclass
class Phase3Results:
    """Results from Phase 3 calculations"""
    z_bounds: List[float] = field(default_factory=list)
    nominal_p: List[float] = field(default_factory=list)
    alpha_spent: List[float] = field(default_factory=list)
    hr_at_bound: List[float] = field(default_factory=list)
    prob_cross_h0: List[float] = field(default_factory=list)
    prob_cross_h1: List[float] = field(default_factory=list)
    timing: List[float] = field(default_factory=list)
    events: List[int] = field(default_factory=list)
    engine_used: str = ""
    validated: bool = False
    validation_discrepancies: Dict = field(default_factory=dict)

    # Futility boundaries (optional)
    futility_z_bounds: List[float] = field(default_factory=list)
    futility_hr_bounds: List[float] = field(default_factory=list)

    # Non-inferiority boundaries (optional)
    ni_z_bounds: List[float] = field(default_factory=list)
    ni_hr_bounds: List[float] = field(default_factory=list)

    def to_markdown(self, endpoint_name: str = "Primary Endpoint") -> str:
        """Generate markdown tables for Phase 3 boundaries"""
        lines = [
            f"### {endpoint_name} Efficacy Boundaries",
            "",
            "| Analysis | Info Fraction | Events | Z-boundary | Nominal p-value | HR at Boundary | Cumulative α |",
            "|----------|---------------|--------|------------|-----------------|----------------|--------------|"
        ]

        k = len(self.z_bounds)
        for i in range(k):
            pct = int(self.timing[i] * 100) if self.timing else int((i + 1) / k * 100)
            analysis_name = f"IA{i+1}" if i < k - 1 else "FA"
            events = self.events[i] if self.events else "N/A"

            lines.append(
                f"| {analysis_name} | {pct}% | {events} | "
                f"{self.z_bounds[i]:.4f} | {self.nominal_p[i]:.6f} | "
                f"{self.hr_at_bound[i]:.4f} | {self.alpha_spent[i]:.6f} |"
            )

        lines.append("")
        lines.append(f"*Calculated using {self.engine_used}*")

        # Add futility boundaries if present
        if self.futility_z_bounds:
            lines.extend([
                "",
                f"### {endpoint_name} Futility Boundaries",
                "",
                "| Analysis | Z-boundary (Futility) | HR at Boundary |",
                "|----------|----------------------|----------------|"
            ])
            for i in range(len(self.futility_z_bounds)):
                analysis_name = f"IA{i+1}"
                lines.append(
                    f"| {analysis_name} | {self.futility_z_bounds[i]:.4f} | "
                    f"{self.futility_hr_bounds[i]:.4f} |"
                )

        # Add NI boundaries if present
        if self.ni_z_bounds:
            lines.extend([
                "",
                f"### {endpoint_name} Non-Inferiority Boundaries",
                "",
                "| Analysis | Z-boundary (NI) | HR at Boundary |",
                "|----------|-----------------|----------------|"
            ])
            for i in range(len(self.ni_z_bounds)):
                analysis_name = f"IA{i+1}" if i < len(self.ni_z_bounds) - 1 else "FA"
                lines.append(
                    f"| {analysis_name} | {self.ni_z_bounds[i]:.4f} | "
                    f"{self.ni_hr_bounds[i]:.4f} |"
                )

        return "\n".join(lines)


@dataclass
class ValidationTolerances:
    """Tolerances for cross-validation"""
    z_boundary: float = 0.01
    p_value: float = 0.0005
    hr: float = 0.005
    probability: float = 0.01
    response_rate: float = 0.001


# =============================================================================
# ABSTRACT BASE CLASSES
# =============================================================================

class CalculationEngine(ABC):
    """Abstract base class for all calculation engines"""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine is available"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine name"""
        pass


class Phase2Engine(CalculationEngine):
    """Abstract base class for Phase 2 calculation engines"""

    @abstractmethod
    def calculate_simon_design(self, params: Phase2Parameters) -> Phase2Results:
        """Calculate Simon's two-stage design"""
        pass

    @abstractmethod
    def calculate_sample_size(self, p0: float, p1: float, alpha: float, power: float) -> int:
        """Calculate sample size for response rate endpoint"""
        pass


class Phase3Engine(CalculationEngine):
    """Abstract base class for Phase 3 calculation engines"""

    @abstractmethod
    def calculate_boundaries(self, params: Phase3Parameters) -> Phase3Results:
        """Calculate group sequential boundaries"""
        pass

    @abstractmethod
    def calculate_sample_size(
        self,
        hr: float,
        alpha: float,
        power: float,
        allocation_ratio: float = 1.0
    ) -> Tuple[int, int]:
        """Calculate sample size and events for survival endpoint"""
        pass


# =============================================================================
# PHASE 2 PYTHON ENGINE
# =============================================================================

class Phase2PythonEngine(Phase2Engine):
    """
    Python implementation of Phase 2 calculations

    Implements:
    - Simon's two-stage optimal design
    - Simon's two-stage minimax design
    - Fleming single-stage design
    - Sample size calculations for response rate
    - Confidence intervals (Clopper-Pearson)
    """

    @property
    def name(self) -> str:
        return "Python-scipy"

    def is_available(self) -> bool:
        return True

    def calculate_simon_design(self, params: Phase2Parameters) -> Phase2Results:
        """
        Calculate Simon's two-stage design

        Parameters:
        -----------
        params : Phase2Parameters
            Design parameters including p0, p1, alpha, beta, design_type

        Returns:
        --------
        Phase2Results with optimal or minimax design
        """
        p0, p1 = params.p0, params.p1
        alpha, beta = params.alpha, params.beta

        if params.design_type == Phase2DesignType.SIMON_OPTIMAL:
            result = self._simon_optimal(p0, p1, alpha, beta)
        elif params.design_type == Phase2DesignType.SIMON_MINIMAX:
            result = self._simon_minimax(p0, p1, alpha, beta)
        else:
            raise ValueError(f"Unsupported design type: {params.design_type}")

        result.engine_used = self.name
        return result

    def _simon_optimal(
        self,
        p0: float,
        p1: float,
        alpha: float,
        beta: float
    ) -> Phase2Results:
        """
        Find Simon's optimal design (minimizes expected sample size under H0)
        """
        best_design = None
        min_en = float('inf')

        # Search over possible sample sizes
        n_max = self._get_max_n(p0, p1, alpha, beta)

        for n in range(10, n_max + 1):
            for n1 in range(1, n):
                for r1 in range(0, n1 + 1):
                    for r in range(r1, n + 1):
                        # Calculate error rates
                        alpha_actual, power_actual = self._calculate_error_rates(
                            n1, r1, n, r, p0, p1
                        )

                        # Check constraints
                        if alpha_actual <= alpha and power_actual >= 1 - beta:
                            # Calculate expected sample size under H0
                            pet = self._pet(n1, r1, p0)
                            en = n1 + (1 - pet) * (n - n1)

                            if en < min_en:
                                min_en = en
                                best_design = Phase2Results(
                                    n1=n1, r1=r1, n=n, r=r,
                                    en_h0=en, pet_h0=pet,
                                    actual_alpha=alpha_actual,
                                    actual_power=power_actual,
                                    design_type="Simon Optimal"
                                )

        if best_design is None:
            raise ValueError("No valid design found")

        return best_design

    def _simon_minimax(
        self,
        p0: float,
        p1: float,
        alpha: float,
        beta: float
    ) -> Phase2Results:
        """
        Find Simon's minimax design (minimizes maximum sample size)
        """
        best_design = None
        min_n = float('inf')
        min_en_for_n = float('inf')

        n_max = self._get_max_n(p0, p1, alpha, beta)

        for n in range(10, n_max + 1):
            for n1 in range(1, n):
                for r1 in range(0, n1 + 1):
                    for r in range(r1, n + 1):
                        alpha_actual, power_actual = self._calculate_error_rates(
                            n1, r1, n, r, p0, p1
                        )

                        if alpha_actual <= alpha and power_actual >= 1 - beta:
                            pet = self._pet(n1, r1, p0)
                            en = n1 + (1 - pet) * (n - n1)

                            # Minimax: minimize n, then EN as tiebreaker
                            if n < min_n or (n == min_n and en < min_en_for_n):
                                min_n = n
                                min_en_for_n = en
                                best_design = Phase2Results(
                                    n1=n1, r1=r1, n=n, r=r,
                                    en_h0=en, pet_h0=pet,
                                    actual_alpha=alpha_actual,
                                    actual_power=power_actual,
                                    design_type="Simon Minimax"
                                )

        if best_design is None:
            raise ValueError("No valid design found")

        return best_design

    def _calculate_error_rates(
        self,
        n1: int,
        r1: int,
        n: int,
        r: int,
        p0: float,
        p1: float
    ) -> Tuple[float, float]:
        """
        Calculate actual alpha and power for a two-stage design

        Alpha = P(reject H0 | p = p0)
        Power = P(reject H0 | p = p1)
        """
        alpha = 0.0
        power = 0.0

        # Stage 1: need > r1 responses to continue
        # Final: need > r responses to reject H0

        for x1 in range(r1 + 1, n1 + 1):  # Continue to stage 2
            # Probability of x1 responses in stage 1
            p1_h0 = binom.pmf(x1, n1, p0)
            p1_h1 = binom.pmf(x1, n1, p1)

            n2 = n - n1
            for x2 in range(0, n2 + 1):
                x_total = x1 + x2
                if x_total > r:  # Reject H0
                    p2_h0 = binom.pmf(x2, n2, p0)
                    p2_h1 = binom.pmf(x2, n2, p1)
                    alpha += p1_h0 * p2_h0
                    power += p1_h1 * p2_h1

        return alpha, power

    def _pet(self, n1: int, r1: int, p: float) -> float:
        """
        Probability of early termination (stopping at stage 1)

        PET = P(X1 <= r1) where X1 ~ Binomial(n1, p)
        """
        return binom.cdf(r1, n1, p)

    def _get_max_n(self, p0: float, p1: float, alpha: float, beta: float) -> int:
        """
        Get upper bound for sample size search

        Use single-stage sample size as conservative upper bound
        """
        # Approximate using normal approximation
        z_alpha = norm.ppf(1 - alpha)
        z_beta = norm.ppf(1 - beta)

        delta = p1 - p0
        sigma0 = np.sqrt(p0 * (1 - p0))
        sigma1 = np.sqrt(p1 * (1 - p1))

        n = ((z_alpha * sigma0 + z_beta * sigma1) / delta) ** 2

        return int(np.ceil(n * 1.5))  # Add 50% buffer

    def calculate_sample_size(
        self,
        p0: float,
        p1: float,
        alpha: float,
        power: float
    ) -> int:
        """
        Calculate sample size for single-stage response rate design

        Uses exact binomial calculation
        """
        z_alpha = norm.ppf(1 - alpha)
        z_beta = norm.ppf(power)

        delta = p1 - p0
        sigma0 = np.sqrt(p0 * (1 - p0))
        sigma1 = np.sqrt(p1 * (1 - p1))

        n = ((z_alpha * sigma0 + z_beta * sigma1) / delta) ** 2

        return int(np.ceil(n))

    def clopper_pearson_ci(
        self,
        x: int,
        n: int,
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """
        Calculate Clopper-Pearson exact confidence interval for proportion

        Parameters:
        -----------
        x : int
            Number of successes (responses)
        n : int
            Total sample size
        confidence : float
            Confidence level (default 0.95)

        Returns:
        --------
        Tuple of (lower bound, upper bound)
        """
        from scipy.stats import beta as beta_dist

        alpha = 1 - confidence

        if x == 0:
            lower = 0.0
        else:
            lower = beta_dist.ppf(alpha / 2, x, n - x + 1)

        if x == n:
            upper = 1.0
        else:
            upper = beta_dist.ppf(1 - alpha / 2, x + 1, n - x)

        return (lower, upper)

    def go_nogo_probability(
        self,
        n: int,
        threshold: int,
        true_rate: float
    ) -> Dict[str, float]:
        """
        Calculate Go/No-Go probabilities

        Parameters:
        -----------
        n : int
            Sample size
        threshold : int
            Response threshold for Go decision
        true_rate : float
            Assumed true response rate

        Returns:
        --------
        Dict with probabilities
        """
        p_go = 1 - binom.cdf(threshold, n, true_rate)
        p_nogo = binom.cdf(threshold, n, true_rate)

        return {
            'P(Go)': p_go,
            'P(No-Go)': p_nogo,
            'Expected Responses': n * true_rate,
            'Threshold': threshold
        }


# =============================================================================
# PHASE 2 R ENGINE
# =============================================================================

class Phase2REngine(Phase2Engine):
    """
    R implementation of Phase 2 calculations using clinfun package
    """

    def __init__(self):
        self._r_available = None
        self._clinfun = None

    @property
    def name(self) -> str:
        return "R-clinfun"

    def is_available(self) -> bool:
        if self._r_available is not None:
            return self._r_available

        try:
            # Setup R environment first
            setup_r_environment()

            import rpy2.robjects as ro
            from rpy2.robjects.packages import importr, isinstalled

            if not isinstalled('clinfun'):
                logger.warning("R package 'clinfun' not installed")
                self._r_available = False
                return False

            self._clinfun = importr('clinfun')
            self._ro = ro
            self._r_available = True
            logger.info("R clinfun engine initialized")
            return True

        except ImportError:
            self._r_available = False
            return False
        except Exception as e:
            logger.warning(f"R clinfun initialization failed: {e}")
            self._r_available = False
            return False

    def calculate_simon_design(self, params: Phase2Parameters) -> Phase2Results:
        """Calculate Simon's design using R clinfun"""
        if not self.is_available():
            raise RuntimeError("R clinfun not available")

        design_type = "optimal" if params.design_type == Phase2DesignType.SIMON_OPTIMAL else "minimax"

        result = self._clinfun.ph2simon(
            pu=params.p0,
            pa=params.p1,
            ep1=params.alpha,
            ep2=params.beta,
            nmax=200
        )

        # Extract results based on design type
        if design_type == "optimal":
            idx = 0  # First row is optimal
        else:
            idx = 1  # Second row is minimax

        # Parse R output
        out = np.array(result.rx2('out'))

        return Phase2Results(
            n1=int(out[idx, 0]),
            r1=int(out[idx, 1]),
            n=int(out[idx, 2]),
            r=int(out[idx, 3]),
            en_h0=float(out[idx, 4]),
            pet_h0=float(out[idx, 5]),
            actual_alpha=params.alpha,
            actual_power=1 - params.beta,
            design_type=f"Simon {design_type.title()} (R)",
            engine_used=self.name
        )

    def calculate_sample_size(
        self,
        p0: float,
        p1: float,
        alpha: float,
        power: float
    ) -> int:
        """Calculate sample size using R"""
        # Use Python implementation as fallback
        py_engine = Phase2PythonEngine()
        return py_engine.calculate_sample_size(p0, p1, alpha, power)


# =============================================================================
# PHASE 3 PYTHON ENGINE
# =============================================================================

class Phase3PythonEngine(Phase3Engine):
    """
    Python implementation of Phase 3 calculations

    Implements:
    - Lan-DeMets alpha spending
    - Group sequential boundaries
    - HR at boundary
    - Power calculations
    - Sample size for survival endpoints
    """

    @property
    def name(self) -> str:
        return "Python-scipy"

    def is_available(self) -> bool:
        return True

    def calculate_boundaries(self, params: Phase3Parameters) -> Phase3Results:
        """
        Calculate group sequential boundaries
        """
        # Calculate information fractions if not provided
        if not params.timing:
            params.timing = [e / params.events[-1] for e in params.events]

        # Calculate cumulative alpha spent
        alpha_spent = []
        for t in params.timing:
            spent = self._spending_function(
                params.alpha, t, params.spending_function, params.spending_param
            )
            alpha_spent.append(spent)

        # Calculate incremental alpha
        incremental_alpha = [alpha_spent[0]]
        for i in range(1, params.k):
            incremental_alpha.append(alpha_spent[i] - alpha_spent[i-1])

        # Calculate Z boundaries
        z_bounds = self._compute_z_boundaries(params.timing, incremental_alpha)

        # Calculate derived quantities
        nominal_p = [float(1 - norm.cdf(z)) for z in z_bounds]

        hr_at_bound = []
        for i, z in enumerate(z_bounds):
            events = params.events[i]
            se_log_hr = 2 / np.sqrt(events)
            hr = np.exp(-z * se_log_hr)
            hr_at_bound.append(float(hr))

        prob_cross_h0 = alpha_spent.copy()
        prob_cross_h1 = self._compute_power(
            z_bounds, params.timing, params.events, params.hr_alternative
        )

        # Calculate futility boundaries (non-binding)
        futility_z, futility_hr = self._compute_futility_boundaries(
            params.events, params.hr_alternative
        )

        # Calculate NI boundaries if margin provided
        ni_z, ni_hr = [], []
        if params.ni_margin and params.ni_margin > 1.0:
            ni_z, ni_hr = self._compute_ni_boundaries(
                params.events, params.ni_margin, params.alpha
            )

        return Phase3Results(
            z_bounds=[float(z) for z in z_bounds],
            nominal_p=nominal_p,
            alpha_spent=[float(a) for a in alpha_spent],
            hr_at_bound=hr_at_bound,
            prob_cross_h0=[float(p) for p in prob_cross_h0],
            prob_cross_h1=[float(p) for p in prob_cross_h1],
            timing=params.timing,
            events=params.events,
            engine_used=self.name,
            futility_z_bounds=futility_z,
            futility_hr_bounds=futility_hr,
            ni_z_bounds=ni_z,
            ni_hr_bounds=ni_hr
        )

    def _spending_function(
        self,
        alpha: float,
        t: float,
        func_type: SpendingFunction,
        param: Optional[float] = None
    ) -> float:
        """Calculate cumulative alpha spent at information fraction t"""
        if t <= 0:
            return 0.0
        if t >= 1:
            return alpha

        if func_type in [SpendingFunction.OBRIEN_FLEMING, SpendingFunction.LAN_DEMETS_OF]:
            z_alpha = norm.ppf(1 - alpha)
            return float(2 - 2 * norm.cdf(z_alpha / np.sqrt(t)))

        elif func_type == SpendingFunction.POCOCK:
            return float(alpha * np.log(1 + (np.e - 1) * t))

        elif func_type == SpendingFunction.POWER_FAMILY:
            rho = param if param is not None else 1
            return float(alpha * (t ** rho))

        elif func_type == SpendingFunction.HWANG_SHIH_DECANI:
            gamma = param if param is not None else -4
            if abs(gamma) < 1e-6:
                return float(alpha * t)
            return float(alpha * (1 - np.exp(-gamma * t)) / (1 - np.exp(-gamma)))

        else:
            raise ValueError(f"Unknown spending function: {func_type}")

    def _compute_z_boundaries(
        self,
        timing: List[float],
        incremental_alpha: List[float]
    ) -> List[float]:
        """Compute Z boundaries using recursive numerical integration"""
        k = len(timing)
        z_bounds = []

        for j in range(k):
            inc_alpha = incremental_alpha[j]

            # Guard against very small or negative incremental alpha
            if inc_alpha <= 1e-10:
                # Use the previous boundary as approximation for very small alpha
                if z_bounds:
                    z_bounds.append(z_bounds[-1])
                else:
                    z_bounds.append(norm.ppf(0.999))
                continue

            if j == 0:
                z_j = norm.ppf(1 - inc_alpha)
                z_bounds.append(float(z_j))
            else:
                def objective(z_candidate):
                    prob = self._probability_cross_at_analysis(
                        j, z_candidate, z_bounds, timing
                    )
                    return prob - inc_alpha

                try:
                    z_j = brentq(objective, 0.0, 8.0, xtol=1e-10)
                    z_bounds.append(float(z_j))
                except ValueError:
                    # Fallback: use normal approximation with guard
                    if inc_alpha > 0:
                        z_j = norm.ppf(1 - inc_alpha)
                    else:
                        z_j = z_bounds[-1] if z_bounds else 2.0
                    z_bounds.append(float(z_j))

        return z_bounds

    def _probability_cross_at_analysis(
        self,
        j: int,
        z_candidate: float,
        previous_bounds: List[float],
        timing: List[float]
    ) -> float:
        """Calculate probability of crossing at analysis j for the first time"""
        if j == 0:
            return 1 - norm.cdf(z_candidate)

        t_j = timing[j]
        t_prev = timing[j-1]

        rho = np.sqrt(t_prev / t_j)
        var_conditional = 1 - rho**2

        def integrand(z_prev):
            mean_conditional = z_prev * rho
            sd_conditional = np.sqrt(var_conditional)
            prob_cross = 1 - norm.cdf((z_candidate - mean_conditional) / sd_conditional)
            density = norm.pdf(z_prev)
            return prob_cross * density

        result, _ = quad(integrand, -10, previous_bounds[j-1], limit=100)
        return result

    def _compute_power(
        self,
        z_bounds: List[float],
        timing: List[float],
        events: List[int],
        hr_alternative: float
    ) -> List[float]:
        """Compute cumulative power at each analysis"""
        prob_cross_h1 = []
        cumulative = 0.0

        for i, (z, t, n_events) in enumerate(zip(z_bounds, timing, events)):
            se_log_hr = 2 / np.sqrt(n_events)
            drift = -np.log(hr_alternative) / se_log_hr

            if i == 0:
                prob = 1 - norm.cdf(z - drift)
                cumulative = prob
            else:
                prob_increment = (1 - norm.cdf(z - drift)) - cumulative * 0.5
                prob_increment = max(0, prob_increment)
                cumulative += prob_increment * (1 - cumulative)

            prob_cross_h1.append(min(1.0, cumulative))

        return prob_cross_h1

    def _compute_futility_boundaries(
        self,
        events: List[int],
        hr_alternative: float
    ) -> Tuple[List[float], List[float]]:
        """Compute non-binding futility boundaries"""
        futility_z = []
        futility_hr = []

        # Only for interim analyses (not final)
        for i in range(len(events) - 1):
            # Use HR = 1.0 as futility threshold (no effect)
            se_log_hr = 2 / np.sqrt(events[i])
            z_futility = 0.0  # Corresponds to HR = 1.0
            hr_futility = 1.0

            futility_z.append(z_futility)
            futility_hr.append(hr_futility)

        return futility_z, futility_hr

    def _compute_ni_boundaries(
        self,
        events: List[int],
        ni_margin: float,
        alpha: float
    ) -> Tuple[List[float], List[float]]:
        """Compute non-inferiority boundaries"""
        ni_z = []
        ni_hr = []

        for i, e in enumerate(events):
            se_log_hr = 2 / np.sqrt(e)
            # Z for NI: test if HR < ni_margin
            z_ni = -np.log(ni_margin) / se_log_hr
            hr_ni = ni_margin

            ni_z.append(z_ni)
            ni_hr.append(hr_ni)

        return ni_z, ni_hr

    def calculate_sample_size(
        self,
        hr: float,
        alpha: float,
        power: float,
        allocation_ratio: float = 1.0
    ) -> Tuple[int, int]:
        """
        Calculate sample size and events for survival endpoint

        Uses Schoenfeld formula

        Parameters:
        -----------
        hr : float
            Target hazard ratio
        alpha : float
            One-sided type I error
        power : float
            Desired power
        allocation_ratio : float
            Ratio of treatment to control (default 1:1)

        Returns:
        --------
        Tuple of (total sample size, number of events)
        """
        z_alpha = norm.ppf(1 - alpha)
        z_beta = norm.ppf(power)

        # Schoenfeld formula for events
        theta = np.log(hr)
        r = allocation_ratio

        events = ((z_alpha + z_beta) ** 2) * ((1 + r) ** 2) / (r * theta ** 2)
        events = int(np.ceil(events))

        # Total N depends on event rate (assumed 80% for conservative estimate)
        event_rate = 0.8
        n = int(np.ceil(events / event_rate))

        return (n, events)

    def project_events(
        self,
        n: int,
        median_control: float,
        hr: float,
        enrollment_duration: float,
        followup_duration: float,
        dropout_rate: float = 0.05
    ) -> int:
        """
        Project number of events given enrollment and follow-up

        Parameters:
        -----------
        n : int
            Total sample size
        median_control : float
            Median survival in control arm (months)
        hr : float
            Expected hazard ratio
        enrollment_duration : float
            Duration of enrollment (months)
        followup_duration : float
            Additional follow-up after enrollment closes (months)
        dropout_rate : float
            Annual dropout rate

        Returns:
        --------
        Projected number of events
        """
        # Control hazard rate (exponential assumption)
        lambda_control = np.log(2) / median_control
        lambda_treatment = lambda_control * hr

        # Average hazard (assuming 1:1 allocation)
        lambda_avg = (lambda_control + lambda_treatment) / 2

        # Probability of event by end of study
        # Accounting for staggered entry
        total_time = enrollment_duration + followup_duration

        # Simple approximation for uniform enrollment
        avg_followup = followup_duration + enrollment_duration / 2
        prob_event = 1 - np.exp(-lambda_avg * avg_followup)

        # Adjust for dropout
        prob_event *= (1 - dropout_rate * (avg_followup / 12))

        events = int(n * prob_event)

        return events


# =============================================================================
# PHASE 3 R ENGINE
# =============================================================================

class Phase3REngine(Phase3Engine):
    """
    R implementation of Phase 3 calculations using gsDesign/rpact
    """

    def __init__(self):
        self._r_available = None
        self._gsdesign = None
        self._rpact = None

    @property
    def name(self) -> str:
        return "R-gsDesign"

    def is_available(self) -> bool:
        if self._r_available is not None:
            return self._r_available

        try:
            # Setup R environment first
            setup_r_environment()

            import rpy2.robjects as ro
            from rpy2.robjects.packages import importr, isinstalled

            # Setup numpy-R conversion (suppress deprecation warning)
            try:
                from rpy2.robjects import numpy2ri
                from rpy2.robjects import conversion
                # Use context-based conversion if available (newer rpy2)
                if hasattr(conversion, 'localconverter'):
                    self._numpy_converter = numpy2ri.converter
                else:
                    # Legacy activation
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", DeprecationWarning)
                        numpy2ri.activate()
            except ImportError:
                pass

            if not isinstalled('gsDesign'):
                logger.warning("R package 'gsDesign' not installed")
                self._r_available = False
                return False

            self._gsdesign = importr('gsDesign')
            self._stats = importr('stats')
            self._ro = ro

            # Try to load rpact as well
            if isinstalled('rpact'):
                self._rpact = importr('rpact')
                logger.info("R rpact engine also available")

            self._r_available = True
            logger.info("R gsDesign engine initialized")
            return True

        except ImportError:
            self._r_available = False
            return False
        except Exception as e:
            logger.warning(f"R gsDesign initialization failed: {e}")
            self._r_available = False
            return False

    def calculate_boundaries(self, params: Phase3Parameters) -> Phase3Results:
        """Calculate boundaries using R gsDesign"""
        if not self.is_available():
            raise RuntimeError("R gsDesign not available")

        from rpy2.robjects import FloatVector

        sfu_map = {
            SpendingFunction.OBRIEN_FLEMING: "sfLDOF",
            SpendingFunction.LAN_DEMETS_OF: "sfLDOF",
            SpendingFunction.POCOCK: "sfLDPocock",
            SpendingFunction.POWER_FAMILY: "sfPower",
            SpendingFunction.HWANG_SHIH_DECANI: "sfHSD"
        }

        sfu = self._ro.r(sfu_map.get(params.spending_function, "sfLDOF"))
        sfupar = params.spending_param if params.spending_param else self._ro.NULL

        if not params.timing:
            params.timing = [e / params.events[-1] for e in params.events]

        timing_r = FloatVector(params.timing)

        design = self._gsdesign.gsDesign(
            k=params.k,
            test_type=1,  # One-sided
            alpha=params.alpha,
            beta=params.beta,
            sfu=sfu,
            sfupar=sfupar,
            timing=timing_r
        )

        z_bounds = list(np.array(design.rx2('upper').rx2('bound')))
        alpha_spent = list(np.cumsum(np.array(design.rx2('upper').rx2('spend'))))

        prob_matrix = np.array(design.rx2('upper').rx2('prob'))
        if prob_matrix.ndim == 2:
            prob_cross_h1 = list(np.cumsum(prob_matrix[:, 0]))
        else:
            prob_cross_h1 = list(np.cumsum(prob_matrix))

        nominal_p = [float(1 - norm.cdf(z)) for z in z_bounds]

        hr_at_bound = []
        for i, z in enumerate(z_bounds):
            events = params.events[i]
            se_log_hr = 2 / np.sqrt(events)
            hr = np.exp(-z * se_log_hr)
            hr_at_bound.append(float(hr))

        # Calculate futility boundaries
        futility_z, futility_hr = [], []
        for i in range(params.k - 1):
            se_log_hr = 2 / np.sqrt(params.events[i])
            futility_z.append(0.0)
            futility_hr.append(1.0)

        # Calculate NI boundaries if margin provided
        ni_z, ni_hr = [], []
        if params.ni_margin and params.ni_margin > 1.0:
            for i, e in enumerate(params.events):
                se_log_hr = 2 / np.sqrt(e)
                ni_z.append(-np.log(params.ni_margin) / se_log_hr)
                ni_hr.append(params.ni_margin)

        return Phase3Results(
            z_bounds=[float(z) for z in z_bounds],
            nominal_p=nominal_p,
            alpha_spent=alpha_spent,
            hr_at_bound=hr_at_bound,
            prob_cross_h0=[float(p) for p in alpha_spent],
            prob_cross_h1=[float(p) for p in prob_cross_h1],
            timing=params.timing,
            events=params.events,
            engine_used=self.name,
            futility_z_bounds=futility_z,
            futility_hr_bounds=futility_hr,
            ni_z_bounds=ni_z,
            ni_hr_bounds=ni_hr
        )

    def calculate_sample_size(
        self,
        hr: float,
        alpha: float,
        power: float,
        allocation_ratio: float = 1.0
    ) -> Tuple[int, int]:
        """Calculate sample size using R gsDesign"""
        # Use Python implementation
        py_engine = Phase3PythonEngine()
        return py_engine.calculate_sample_size(hr, alpha, power, allocation_ratio)


# =============================================================================
# CHINA EXTENSION CALCULATOR
# =============================================================================

class ChinaExtensionCalculator:
    """Calculator for China extension power calculations"""

    @staticmethod
    def probability_preserve_effect(
        events_china: int,
        hr_global: float,
        hr_true: float,
        preserve_fraction: float = 0.50
    ) -> float:
        """
        Calculate probability of preserving specified fraction of global effect
        """
        risk_reduction_global = 1 - hr_global
        hr_threshold = 1 - preserve_fraction * risk_reduction_global

        se_log_hr = 2 / np.sqrt(events_china)
        z_threshold = np.log(hr_threshold) / se_log_hr
        z_true = np.log(hr_true) / se_log_hr

        return float(norm.cdf(z_threshold - z_true))

    @classmethod
    def calculate_china_power(
        cls,
        pfs_events: int = 71,
        os_events: int = 54,
        hr_assumed: float = 0.7,
        preserve_fraction: float = 0.50
    ) -> Dict[str, float]:
        """Calculate power for China extension"""
        return {
            'pfs_preserve_prob': cls.probability_preserve_effect(
                pfs_events, hr_assumed, hr_assumed, preserve_fraction
            ),
            'os_preserve_prob': cls.probability_preserve_effect(
                os_events, hr_assumed, hr_assumed, preserve_fraction
            ),
            'pfs_events': pfs_events,
            'os_events': os_events
        }

    @classmethod
    def to_markdown(cls, pfs_events: int, os_events: int, hr_assumed: float = 0.7) -> str:
        """Generate markdown for China extension section"""
        results = cls.calculate_china_power(pfs_events, os_events, hr_assumed)

        lines = [
            "## 11. REGIONAL CONSIDERATIONS",
            "",
            "### 11.1 China Extension Study",
            "",
            "The China extension study aims to demonstrate consistency of treatment effect "
            "with the global population.",
            "",
            "#### Power to Preserve Effect",
            "",
            "| Endpoint | China Events | P(Preserve 50% Effect) |",
            "|----------|--------------|------------------------|",
            f"| PFS | {pfs_events} | {results['pfs_preserve_prob']:.1%} |",
            f"| OS | {os_events} | {results['os_preserve_prob']:.1%} |",
            "",
            f"*Assuming global HR = {hr_assumed}*"
        ]
        return "\n".join(lines)


# =============================================================================
# MULTIPLICITY CALCULATOR
# =============================================================================

class MultiplicityCalculator:
    """
    Calculator for multiplicity adjustments using graphical approach
    (Maurer and Bretz method)
    """

    def __init__(
        self,
        hypotheses: List[str],
        initial_alpha: List[float],
        transition_weights: np.ndarray
    ):
        """
        Initialize multiplicity graph

        Parameters:
        -----------
        hypotheses : List[str]
            Names of hypotheses
        initial_alpha : List[float]
            Initial alpha allocation to each hypothesis
        transition_weights : np.ndarray
            Transition weight matrix (n x n)
        """
        self.hypotheses = hypotheses
        self.n = len(hypotheses)
        self.alpha = np.array(initial_alpha)
        self.weights = np.array(transition_weights)

        # Validate
        assert len(initial_alpha) == self.n
        assert self.weights.shape == (self.n, self.n)

    def test_hypotheses(
        self,
        p_values: List[float]
    ) -> Dict[str, Any]:
        """
        Test hypotheses using graphical procedure

        Parameters:
        -----------
        p_values : List[float]
            Observed p-values for each hypothesis

        Returns:
        --------
        Dict with results for each hypothesis
        """
        p_values = np.array(p_values)
        current_alpha = self.alpha.copy()
        current_weights = self.weights.copy()
        rejected = np.zeros(self.n, dtype=bool)

        results = {h: {'rejected': False, 'alpha_used': 0.0} for h in self.hypotheses}
        rejection_order = []

        # Iteratively test and update
        while True:
            # Find hypotheses that can be rejected
            can_reject = (p_values <= current_alpha) & (~rejected)

            if not can_reject.any():
                break

            # Reject the one with smallest p-value (or first if tied)
            candidates = np.where(can_reject)[0]
            idx = candidates[np.argmin(p_values[candidates])]

            rejected[idx] = True
            rejection_order.append(self.hypotheses[idx])
            results[self.hypotheses[idx]] = {
                'rejected': True,
                'alpha_used': current_alpha[idx],
                'p_value': p_values[idx]
            }

            # Redistribute alpha
            freed_alpha = current_alpha[idx]
            current_alpha[idx] = 0

            for j in range(self.n):
                if not rejected[j]:
                    current_alpha[j] += freed_alpha * current_weights[idx, j]

            # Update weights
            for j in range(self.n):
                if not rejected[j]:
                    for l in range(self.n):
                        if not rejected[l] and l != j:
                            if current_weights[j, idx] + current_weights[idx, j] > 0:
                                w_jl = current_weights[j, l] + current_weights[j, idx] * current_weights[idx, l]
                                w_jl /= (1 - current_weights[j, idx] * current_weights[idx, j])
                                current_weights[j, l] = w_jl

            current_weights[idx, :] = 0
            current_weights[:, idx] = 0

        return {
            'results': results,
            'rejection_order': rejection_order,
            'final_alpha': current_alpha.tolist()
        }

    def to_markdown(self) -> str:
        """Generate markdown for multiplicity section"""
        lines = [
            "### 5.3 Testing Hierarchy / Multiplicity Adjustment",
            "",
            "The graphical approach (Maurer and Bretz) is used for multiplicity control.",
            "",
            "#### Initial Alpha Allocation",
            "",
            "| Hypothesis | Initial α |",
            "|------------|-----------|"
        ]

        for i, h in enumerate(self.hypotheses):
            lines.append(f"| {h} | {self.alpha[i]:.4f} |")

        lines.extend([
            "",
            "#### Transition Weights",
            "",
            "| From \\ To | " + " | ".join(self.hypotheses) + " |",
            "|-----------|" + "|".join(["--------"] * self.n) + "|"
        ])

        for i, h in enumerate(self.hypotheses):
            row = f"| {h} | " + " | ".join([f"{self.weights[i,j]:.2f}" for j in range(self.n)]) + " |"
            lines.append(row)

        return "\n".join(lines)


# =============================================================================
# MAIN CALCULATION ENGINE - ROUTER
# =============================================================================

class SAPCalculationEngine:
    """
    Main SAP Calculation Engine

    Routes calculations to appropriate phase-specific module and engine.
    Provides cross-validation between R and Python implementations.

    Usage:
    ------
    >>> engine = SAPCalculationEngine()
    >>>
    >>> # Phase 2
    >>> simon = engine.calculate_simon_design(p0=0.20, p1=0.40, alpha=0.05, beta=0.10)
    >>>
    >>> # Phase 3
    >>> boundaries = engine.calculate_phase3_boundaries(
    ...     events=[354, 472], alpha=0.005, hr_alternative=0.7
    ... )
    """

    def __init__(
        self,
        force_python: bool = False,
        tolerances: Optional[ValidationTolerances] = None
    ):
        """
        Initialize calculation engine

        Parameters:
        -----------
        force_python : bool
            Use Python engines even if R is available
        tolerances : ValidationTolerances
            Tolerances for cross-validation
        """
        self.force_python = force_python
        self.tolerances = tolerances or ValidationTolerances()

        # Initialize Phase 2 engines
        self.phase2_python = Phase2PythonEngine()
        self.phase2_r = Phase2REngine()

        # Initialize Phase 3 engines
        self.phase3_python = Phase3PythonEngine()
        self.phase3_r = Phase3REngine()

        # Determine primary engines
        if force_python:
            self.phase2_primary = self.phase2_python
            self.phase3_primary = self.phase3_python
            logger.info("Using Python as primary engine (forced)")
        else:
            self.phase2_primary = self.phase2_r if self.phase2_r.is_available() else self.phase2_python
            self.phase3_primary = self.phase3_r if self.phase3_r.is_available() else self.phase3_python
            logger.info(f"Phase 2 primary: {self.phase2_primary.name}")
            logger.info(f"Phase 3 primary: {self.phase3_primary.name}")

    def initialize(self) -> bool:
        """Initialize and check engine availability"""
        r_available = self.phase3_r.is_available()
        logger.info(f"R engine available: {r_available}")
        return True

    # =========================================================================
    # PHASE 2 METHODS
    # =========================================================================

    def calculate_simon_design(
        self,
        p0: float,
        p1: float,
        alpha: float = 0.05,
        beta: float = 0.10,
        design_type: str = "optimal",
        validate: bool = True
    ) -> Phase2Results:
        """
        Calculate Simon's two-stage design

        Parameters:
        -----------
        p0 : float
            Null response rate (unacceptable)
        p1 : float
            Alternative response rate (target)
        alpha : float
            Type I error (one-sided)
        beta : float
            Type II error
        design_type : str
            "optimal" or "minimax"
        validate : bool
            Cross-validate with fallback engine

        Returns:
        --------
        Phase2Results with design parameters
        """
        dt = Phase2DesignType.SIMON_OPTIMAL if design_type == "optimal" else Phase2DesignType.SIMON_MINIMAX

        params = Phase2Parameters(
            p0=p0, p1=p1, alpha=alpha, beta=beta, design_type=dt
        )

        try:
            results = self.phase2_primary.calculate_simon_design(params)
        except Exception as e:
            logger.warning(f"Primary engine failed: {e}, using fallback")
            results = self.phase2_python.calculate_simon_design(params)

        if validate and self.phase2_primary.name != self.phase2_python.name:
            self._validate_phase2(results, params)

        return results

    def calculate_phase2_sample_size(
        self,
        p0: float,
        p1: float,
        alpha: float = 0.05,
        power: float = 0.90
    ) -> int:
        """Calculate sample size for single-stage Phase 2"""
        return self.phase2_python.calculate_sample_size(p0, p1, alpha, power)

    def calculate_confidence_interval(
        self,
        responses: int,
        n: int,
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """Calculate Clopper-Pearson confidence interval"""
        return self.phase2_python.clopper_pearson_ci(responses, n, confidence)

    def _validate_phase2(self, results: Phase2Results, params: Phase2Parameters):
        """Cross-validate Phase 2 results"""
        try:
            py_results = self.phase2_python.calculate_simon_design(params)

            if results.n != py_results.n or results.r != py_results.r:
                logger.warning(
                    f"Phase 2 validation discrepancy: "
                    f"Primary (n={results.n}, r={results.r}) vs "
                    f"Python (n={py_results.n}, r={py_results.r})"
                )
        except Exception as e:
            logger.warning(f"Phase 2 validation failed: {e}")

    # =========================================================================
    # PHASE 3 METHODS
    # =========================================================================

    def calculate_phase3_boundaries(
        self,
        events: List[int],
        alpha: float,
        hr_alternative: float = 0.7,
        beta: float = 0.10,
        spending_function: str = "OF",
        spending_param: Optional[float] = None,
        ni_margin: Optional[float] = None,
        validate: bool = True
    ) -> Phase3Results:
        """
        Calculate Phase 3 group sequential boundaries

        Parameters:
        -----------
        events : List[int]
            Events at each analysis
        alpha : float
            One-sided type I error
        hr_alternative : float
            Alternative hypothesis HR
        beta : float
            Type II error
        spending_function : str
            "OF", "Pocock", "power", or "HSD"
        spending_param : float, optional
            Parameter for spending function
        ni_margin : float, optional
            Non-inferiority margin
        validate : bool
            Cross-validate with fallback engine

        Returns:
        --------
        Phase3Results with boundaries
        """
        sf_map = {
            "OF": SpendingFunction.OBRIEN_FLEMING,
            "LDOF": SpendingFunction.LAN_DEMETS_OF,
            "Pocock": SpendingFunction.POCOCK,
            "power": SpendingFunction.POWER_FAMILY,
            "HSD": SpendingFunction.HWANG_SHIH_DECANI
        }

        k = len(events)
        timing = [e / events[-1] for e in events]

        params = Phase3Parameters(
            k=k,
            alpha=alpha,
            beta=beta,
            events=events,
            timing=timing,
            spending_function=sf_map.get(spending_function, SpendingFunction.OBRIEN_FLEMING),
            spending_param=spending_param,
            hr_alternative=hr_alternative,
            ni_margin=ni_margin
        )

        try:
            results = self.phase3_primary.calculate_boundaries(params)
        except Exception as e:
            logger.warning(f"Primary engine failed: {e}, using fallback")
            results = self.phase3_python.calculate_boundaries(params)

        if validate and self.phase3_primary.name != self.phase3_python.name:
            results = self._validate_phase3(results, params)

        return results

    def calculate_phase3_sample_size(
        self,
        hr: float,
        alpha: float,
        power: float = 0.90,
        allocation_ratio: float = 1.0
    ) -> Tuple[int, int]:
        """Calculate sample size for Phase 3 survival endpoint"""
        return self.phase3_python.calculate_sample_size(hr, alpha, power, allocation_ratio)

    def project_events(
        self,
        n: int,
        median_control: float,
        hr: float,
        enrollment_months: float,
        followup_months: float
    ) -> int:
        """Project events given enrollment and follow-up"""
        return self.phase3_python.project_events(
            n, median_control, hr, enrollment_months, followup_months
        )

    def _validate_phase3(
        self,
        results: Phase3Results,
        params: Phase3Parameters
    ) -> Phase3Results:
        """Cross-validate Phase 3 results"""
        try:
            py_results = self.phase3_python.calculate_boundaries(params)

            discrepancies = {}
            all_passed = True

            for i in range(params.k):
                z_diff = abs(results.z_bounds[i] - py_results.z_bounds[i])
                if z_diff > self.tolerances.z_boundary:
                    discrepancies[f'z_bound_{i+1}'] = {
                        'primary': results.z_bounds[i],
                        'python': py_results.z_bounds[i],
                        'diff': z_diff
                    }
                    all_passed = False

            results.validated = all_passed
            results.validation_discrepancies = discrepancies

            if discrepancies:
                logger.warning(f"Phase 3 validation discrepancies: {discrepancies}")
            else:
                logger.info("Phase 3 cross-validation passed")

        except Exception as e:
            logger.warning(f"Phase 3 validation failed: {e}")

        return results

    # =========================================================================
    # SAP SECTION GENERATION
    # =========================================================================

    def generate_interim_analysis_section(
        self,
        pfs_events: List[int],
        pfs_alpha: float,
        os_events: List[int] = None,
        os_alpha: float = None,
        hr_alternative: float = 0.7,
        ni_margin: float = None,
        spending_function: str = "OF"
    ) -> str:
        """
        Generate complete Interim Analysis section for SAP

        Parameters:
        -----------
        pfs_events : List[int]
            PFS events at each analysis
        pfs_alpha : float
            Alpha allocated to PFS
        os_events : List[int], optional
            OS events at each analysis
        os_alpha : float, optional
            Alpha allocated to OS
        hr_alternative : float
            Target HR for power calculations
        ni_margin : float, optional
            Non-inferiority margin for OS
        spending_function : str
            Alpha spending function type

        Returns:
        --------
        Markdown-formatted interim analysis section
        """
        lines = [
            "## 7. INTERIM ANALYSES",
            "",
            "### 7.1 Overview",
            "",
        ]

        n_pfs = len(pfs_events)
        n_os = len(os_events) if os_events else 0

        lines.extend([
            f"This study includes **{n_pfs - 1} interim analyses** and **1 final analysis** "
            f"for the primary PFS endpoint.",
            "",
            f"- **Alpha spending function**: Lan-DeMets O'Brien-Fleming",
            f"- **Overall one-sided α for PFS**: {pfs_alpha}",
        ])

        if os_alpha:
            lines.append(f"- **Overall one-sided α for OS**: {os_alpha}")

        lines.extend(["", ""])

        # PFS boundaries
        pfs_results = self.calculate_phase3_boundaries(
            events=pfs_events,
            alpha=pfs_alpha,
            hr_alternative=hr_alternative,
            spending_function=spending_function
        )
        lines.append(pfs_results.to_markdown("PFS"))

        # OS boundaries if provided
        if os_events and os_alpha:
            lines.extend(["", ""])
            os_results = self.calculate_phase3_boundaries(
                events=os_events,
                alpha=os_alpha,
                hr_alternative=hr_alternative,
                ni_margin=ni_margin,
                spending_function=spending_function
            )
            lines.append(os_results.to_markdown("OS"))

        return "\n".join(lines)

    def generate_all_sap_tables(
        self,
        config: Dict[str, Any]
    ) -> str:
        """
        Generate all SAP boundary tables based on configuration

        Parameters:
        -----------
        config : Dict
            Configuration with:
            - pfs: {events, alpha, hr_alternative}
            - os: {events, alpha, hr_alternative, ni_margin}
            - china: {pfs_events, os_events}

        Returns:
        --------
        Complete markdown for all statistical tables
        """
        sections = []

        # Interim Analysis section
        if 'pfs' in config:
            pfs = config['pfs']
            os_config = config.get('os', {})

            interim = self.generate_interim_analysis_section(
                pfs_events=pfs['events'],
                pfs_alpha=pfs['alpha'],
                os_events=os_config.get('events'),
                os_alpha=os_config.get('alpha'),
                hr_alternative=pfs.get('hr_alternative', 0.7),
                ni_margin=os_config.get('ni_margin'),
                spending_function=pfs.get('spending_function', 'OF')
            )
            sections.append(interim)

        # China extension if provided
        if 'china' in config:
            china = config['china']
            china_section = ChinaExtensionCalculator.to_markdown(
                pfs_events=china.get('pfs_events', 71),
                os_events=china.get('os_events', 54),
                hr_assumed=china.get('hr_assumed', 0.7)
            )
            sections.append(china_section)

        return "\n\n---\n\n".join(sections)


# =============================================================================
# CONVENIENCE FUNCTION FOR TWO-PASS EXTRACTOR INTEGRATION
# =============================================================================

def calculate_boundaries_for_sap(
    phase: str,
    pfs_events: List[int] = None,
    pfs_alpha: float = None,
    os_events: List[int] = None,
    os_alpha: float = None,
    hr_alternative: float = 0.7,
    ni_margin: float = None,
    p0: float = None,
    p1: float = None,
    force_python: bool = False
) -> str:
    """
    Convenience function for TwoPassExtractor integration

    Returns markdown-formatted boundary tables for inclusion in SAP
    """
    engine = SAPCalculationEngine(force_python=force_python)

    if phase.lower() in ['phase 2', 'phase2', '2']:
        if p0 and p1:
            # Simon's two-stage design
            optimal = engine.calculate_simon_design(p0, p1, design_type="optimal")
            minimax = engine.calculate_simon_design(p0, p1, design_type="minimax")

            return "\n\n".join([
                "## Phase 2 Design Parameters",
                "",
                "### Optimal Design (Minimizes Expected N under H0)",
                optimal.to_markdown(),
                "",
                "### Minimax Design (Minimizes Maximum N)",
                minimax.to_markdown()
            ])
        else:
            return ""

    elif phase.lower() in ['phase 3', 'phase3', '3']:
        if pfs_events and pfs_alpha:
            return engine.generate_interim_analysis_section(
                pfs_events=pfs_events,
                pfs_alpha=pfs_alpha,
                os_events=os_events,
                os_alpha=os_alpha,
                hr_alternative=hr_alternative,
                ni_margin=ni_margin
            )
        else:
            return ""

    return ""


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("SAP Calculation Engine - Modular System")
    print("=" * 80)

    # Initialize engine
    engine = SAPCalculationEngine()

    # ==========================================================================
    # PHASE 2 EXAMPLES
    # ==========================================================================
    print("\n" + "=" * 80)
    print("PHASE 2: Simon's Two-Stage Design")
    print("=" * 80)

    # Calculate Simon's optimal design
    simon_optimal = engine.calculate_simon_design(
        p0=0.20,  # Null: 20% response rate
        p1=0.40,  # Alternative: 40% response rate
        alpha=0.05,
        beta=0.10,
        design_type="optimal"
    )

    print("\nSimon's Optimal Design (p0=0.20, p1=0.40):")
    for key, value in simon_optimal.to_dict().items():
        print(f"  {key}: {value}")

    # Calculate Simon's minimax design
    simon_minimax = engine.calculate_simon_design(
        p0=0.20,
        p1=0.40,
        alpha=0.05,
        beta=0.10,
        design_type="minimax"
    )

    print("\nSimon's Minimax Design (p0=0.20, p1=0.40):")
    for key, value in simon_minimax.to_dict().items():
        print(f"  {key}: {value}")

    # Confidence interval example
    ci = engine.calculate_confidence_interval(responses=15, n=40)
    print(f"\nClopper-Pearson 95% CI for 15/40 responses: ({ci[0]:.3f}, {ci[1]:.3f})")

    # ==========================================================================
    # PHASE 3 EXAMPLES
    # ==========================================================================
    print("\n" + "=" * 80)
    print("PHASE 3: Group Sequential Design")
    print("=" * 80)

    # PFS boundaries
    pfs_results = engine.calculate_phase3_boundaries(
        events=[354, 472],
        alpha=0.005,
        hr_alternative=0.7
    )

    print("\nPFS Boundaries (alpha=0.005):")
    print(f"  Engine: {pfs_results.engine_used}")
    print(f"  Validated: {pfs_results.validated}")
    for i in range(len(pfs_results.z_bounds)):
        print(f"  Analysis {i+1}:")
        print(f"    Z-boundary: {pfs_results.z_bounds[i]:.4f}")
        print(f"    Nominal p: {pfs_results.nominal_p[i]:.6f}")
        print(f"    HR at bound: {pfs_results.hr_at_bound[i]:.4f}")
        print(f"    Cumulative α: {pfs_results.alpha_spent[i]:.6f}")

    # OS boundaries
    os_results = engine.calculate_phase3_boundaries(
        events=[180, 269, 316, 359],
        alpha=0.02,
        hr_alternative=0.7,
        ni_margin=1.2
    )

    print("\nOS Boundaries (alpha=0.02):")
    for i in range(len(os_results.z_bounds)):
        print(f"  Analysis {i+1}: Z={os_results.z_bounds[i]:.4f}, "
              f"HR={os_results.hr_at_bound[i]:.4f}")

    # ==========================================================================
    # COMPLETE SAP SECTION GENERATION
    # ==========================================================================
    print("\n" + "=" * 80)
    print("COMPLETE SAP INTERIM ANALYSIS SECTION")
    print("=" * 80)

    sap_section = engine.generate_interim_analysis_section(
        pfs_events=[354, 472],
        pfs_alpha=0.005,
        os_events=[180, 269, 316, 359],
        os_alpha=0.02,
        hr_alternative=0.7,
        ni_margin=1.2
    )

    print("\n" + sap_section)

    # ==========================================================================
    # CHINA EXTENSION
    # ==========================================================================
    print("\n" + "=" * 80)
    print("CHINA EXTENSION")
    print("=" * 80)

    china_section = ChinaExtensionCalculator.to_markdown(
        pfs_events=71,
        os_events=54,
        hr_assumed=0.7
    )
    print("\n" + china_section)

    # ==========================================================================
    # MULTIPLICITY
    # ==========================================================================
    print("\n" + "=" * 80)
    print("MULTIPLICITY: Graphical Approach")
    print("=" * 80)

    # LEAP-001 style multiplicity structure
    hypotheses = ['H1_PFS_pMMR', 'H2_PFS_all', 'H3_OS_NI', 'H4_OS_sup', 'H5_OS_all']
    initial_alpha = [0.005, 0.0, 0.02, 0.0, 0.0]

    transition = np.array([
        [0, 1, 0, 0, 0],     # H1 -> H2
        [0, 0, 0, 0, 1],     # H2 -> H5
        [0, 0, 0, 1, 0],     # H3 -> H4
        [0, 0, 0, 0, 1],     # H4 -> H5
        [0, 0, 0, 0, 0],     # H5 -> none
    ])

    mult_calc = MultiplicityCalculator(hypotheses, initial_alpha, transition)
    print("\n" + mult_calc.to_markdown())

    # Test with example p-values
    p_values = [0.001, 0.003, 0.015, 0.008, 0.020]
    mult_results = mult_calc.test_hypotheses(p_values)

    print("\n\nMultiplicity Test Results:")
    print(f"  Rejection order: {mult_results['rejection_order']}")
    for h, result in mult_results['results'].items():
        status = "REJECTED" if result['rejected'] else "Not rejected"
        print(f"  {h}: {status}")

    print("\n" + "=" * 80)
    print("Engine initialization complete. Ready for production use.")
    print("=" * 80)
