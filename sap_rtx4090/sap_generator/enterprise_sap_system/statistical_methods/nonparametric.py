"""
Non-Parametric Statistical Methods
===================================

Distribution-free methods for clinical trial analysis.

Used when:
- Parametric assumptions (normality) violated
- Small sample sizes
- Ordinal outcomes (e.g., ECOG status, tumor grade)
- Skewed distributions
- Outliers present

Methods:
- Wilcoxon rank-sum test (Mann-Whitney U)
- Wilcoxon signed-rank test (paired)
- Kruskal-Wallis test (multi-group)
- Friedman test (repeated measures)
- Hodges-Lehmann estimator
- Bootstrap confidence intervals
- Permutation tests
- Rank-based ANCOVA
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


class NonParametricTest(Enum):
    """Non-parametric test types"""
    WILCOXON_RANK_SUM = "Wilcoxon Rank-Sum (Mann-Whitney U)"
    WILCOXON_SIGNED_RANK = "Wilcoxon Signed-Rank"
    KRUSKAL_WALLIS = "Kruskal-Wallis"
    FRIEDMAN = "Friedman"
    SIGN_TEST = "Sign Test"
    VAN_ELTEREN = "Van Elteren (Stratified Wilcoxon)"
    JONCKHEERE_TERPSTRA = "Jonckheere-Terpstra Trend"


class LocationEstimator(Enum):
    """Location estimators for non-parametric methods"""
    MEDIAN = "Median"
    HODGES_LEHMANN = "Hodges-Lehmann Estimator"
    TRIMMED_MEAN = "Trimmed Mean"


@dataclass
class WilcoxonSpec:
    """
    Wilcoxon rank-sum test specification.

    Non-parametric alternative to two-sample t-test.
    """
    # Test parameters
    one_sided: bool = False
    alpha: float = 0.05

    # Location estimator
    location_estimator: LocationEstimator = LocationEstimator.HODGES_LEHMANN
    confidence_level: float = 0.95

    # Tie handling
    tie_handling: str = "average"      # "average", "random", "min", "max"

    # Exact vs asymptotic
    use_exact: bool = False            # Exact p-values for small samples
    exact_threshold: int = 50          # Use exact if n1 + n2 < threshold

    # Effect size
    report_effect_size: bool = True    # Report rank-biserial correlation


@dataclass
class StratifiedWilcoxonSpec:
    """
    Van Elteren test (stratified Wilcoxon) specification.

    Extension of Wilcoxon test accounting for stratification.
    """
    stratification_factors: List[str]

    # Combining method
    combining_weights: str = "sample_size"  # "equal", "sample_size", "variance"

    # Test parameters
    one_sided: bool = False
    alpha: float = 0.05

    # Homogeneity
    test_homogeneity: bool = True      # Test consistency across strata


@dataclass
class KruskalWallisSpec:
    """
    Kruskal-Wallis test specification.

    Non-parametric alternative to one-way ANOVA for 3+ groups.
    """
    # Groups
    num_groups: int = 3

    # Post-hoc comparisons
    perform_pairwise: bool = True
    pairwise_method: str = "Dunn"      # "Dunn", "Conover", "Nemenyi"
    adjust_pairwise: bool = True       # Multiple comparison adjustment

    # Effect size
    epsilon_squared: bool = True       # Effect size measure


@dataclass
class FriedmanSpec:
    """
    Friedman test specification.

    Non-parametric alternative to repeated measures ANOVA.
    """
    # Time points
    time_points: List[str]

    # Post-hoc
    perform_pairwise: bool = True
    pairwise_method: str = "Nemenyi"

    # Kendall's W
    report_concordance: bool = True    # Kendall's coefficient of concordance


@dataclass
class BootstrapSpec:
    """
    Bootstrap confidence interval specification.

    Non-parametric bootstrap for any estimator.
    """
    # Bootstrap parameters
    num_bootstrap: int = 10000
    confidence_level: float = 0.95

    # Bootstrap method
    method: str = "percentile"         # "percentile", "bca", "normal"

    # Seed
    random_seed: int = 12345

    # Stratification
    stratified_sampling: bool = True   # Stratify by treatment


@dataclass
class PermutationTestSpec:
    """
    Permutation test specification.

    Exact test based on all possible permutations or Monte Carlo sampling.
    """
    # Test statistic
    test_statistic: str = "mean_difference"  # User-defined

    # Method
    exact: bool = False                # True for complete enumeration
    num_permutations: int = 10000      # For Monte Carlo

    # Seed
    random_seed: int = 12345

    # Stratification
    permute_within_strata: bool = True
    stratification_factors: List[str] = field(default_factory=list)


class NonParametricService:
    """
    Service for non-parametric analysis specifications.

    Provides methodology text and implementation guidance.
    """

    def __init__(self):
        """Initialize non-parametric service"""
        pass

    def generate_wilcoxon_methodology(
        self,
        spec: WilcoxonSpec,
        endpoint_name: str,
        context: str = "primary"
    ) -> str:
        """
        Generate Wilcoxon methodology text.

        Args:
            spec: Wilcoxon specification
            endpoint_name: Name of endpoint
            context: "primary", "secondary", or "sensitivity"

        Returns:
            Formatted SAP text
        """
        text = f"""
## Non-Parametric Analysis: Wilcoxon Rank-Sum Test

### Rationale

{"The primary" if context == "primary" else "A non-parametric"} analysis of {endpoint_name}
will use the Wilcoxon rank-sum test (also called Mann-Whitney U test).

**Reasons for Non-Parametric Approach:**
- Distribution may be skewed (not normal)
- Presence of outliers
- Small sample size
- Ordinal outcome scale
- Robust alternative to t-test

### Method: Wilcoxon Rank-Sum Test

The Wilcoxon rank-sum test is a distribution-free test comparing two groups based on ranks.

**Null Hypothesis:** The distributions of the outcome are identical in the two groups

**Alternative Hypothesis:** The distribution in one group is stochastically {'larger' if spec.one_sided else 'different'}

**Test Procedure:**
1. Combine all observations and rank from smallest to largest
2. Calculate sum of ranks in each treatment group (R₁, R₂)
3. Calculate test statistic:
   - W = R₁ - n₁(n₁+1)/2 (or equivalently, Mann-Whitney U statistic)
4. Compare to null distribution

"""

        if spec.use_exact:
            text += f"""
**P-value Calculation:** Exact p-values (for n₁ + n₂ < {spec.exact_threshold})

Exact p-values are calculated by enumerating all possible rankings under the null hypothesis.
This provides the most accurate inference for small samples.

"""
        else:
            text += """
**P-value Calculation:** Large-sample normal approximation

For larger samples, the test statistic is approximately normal:
Z = (W - E[W]) / √Var(W)

where E[W] and Var(W) are calculated under the null hypothesis, with adjustment for ties.

"""

        text += f"""
**Significance Level:** {'One-sided' if spec.one_sided else 'Two-sided'} α = {spec.alpha}

### Location Estimator

**Estimator:** {spec.location_estimator.value}

"""

        if spec.location_estimator == LocationEstimator.HODGES_LEHMANN:
            text += """
The Hodges-Lehmann estimator provides a robust estimate of location shift:

**Definition:** Median of all pairwise differences between groups
HL = median{{Yᵢ - Xⱼ : for all i, j}}

where Y = experimental group, X = control group

**Properties:**
- Non-parametric point estimate consistent with Wilcoxon test
- Robust to outliers
- Interpretable as median treatment effect

"""

        elif spec.location_estimator == LocationEstimator.MEDIAN:
            text += """
The median difference will be reported for each group, along with the difference in medians.

**Note:** The difference in medians is NOT equivalent to the Hodges-Lehmann estimator
and may not align precisely with the Wilcoxon test p-value.

"""

        text += f"""
**Confidence Interval:** {spec.confidence_level * 100:.0f}% CI for location shift

The CI will be calculated using the distribution of Walsh averages, consistent with
the Wilcoxon test.

"""

        if spec.report_effect_size:
            text += """
### Effect Size

**Rank-Biserial Correlation:** r_rb = 1 - (2U)/(n₁n₂)

where U = Mann-Whitney U statistic

**Interpretation:**
- r_rb = 0: No effect
- r_rb = ±1: Complete separation
- |r_rb| < 0.3: Small effect
- 0.3 ≤ |r_rb| < 0.5: Medium effect
- |r_rb| ≥ 0.5: Large effect

"""

        text += self._generate_assumptions_section()
        text += self._generate_ties_section(spec)

        return text.strip()

    def generate_stratified_wilcoxon_methodology(
        self,
        spec: StratifiedWilcoxonSpec
    ) -> str:
        """Generate Van Elteren test methodology"""
        factors_str = ", ".join(spec.stratification_factors)

        text = f"""
## Stratified Non-Parametric Analysis: Van Elteren Test

### Method

The Van Elteren test is a stratified extension of the Wilcoxon rank-sum test,
accounting for stratification factors: {factors_str}.

**Procedure:**
1. Perform Wilcoxon rank-sum test within each stratum
2. Combine stratum-specific statistics using weights
3. Test overall null hypothesis of no treatment difference

**Test Statistic:**
VE = Σₛ wₛ (Wₛ - E[Wₛ]) / √(Σₛ wₛ² Var[Wₛ])

where:
- s indexes strata
- Wₛ = Wilcoxon statistic in stratum s
- wₛ = weight for stratum s

**Weights:** {spec.combining_weights}
"""

        if spec.combining_weights == "sample_size":
            text += "- Proportional to sample size in each stratum (recommended)\n"
        elif spec.combining_weights == "variance":
            text += "- Inversely proportional to variance (optimal)\n"
        else:
            text += "- Equal weight to each stratum\n"

        if spec.test_homogeneity:
            text += f"""
### Homogeneity Test

A test of homogeneity across strata will assess whether the treatment effect
is consistent across stratification levels.

**Null Hypothesis:** Treatment effect is homogeneous across strata

If heterogeneity is detected (p < 0.10), stratum-specific results will be reported
and clinical interpretation will consider potential effect modification.

"""

        text += """
### Interpretation

The Van Elteren test provides:
- Single overall p-value accounting for stratification
- More powerful than unstratified Wilcoxon when prognostic strata exist
- Consistent with stratification used in randomization

"""

        return text

    def generate_kruskal_wallis_methodology(
        self,
        spec: KruskalWallisSpec
    ) -> str:
        """Generate Kruskal-Wallis methodology"""
        text = f"""
## Multi-Group Non-Parametric Analysis: Kruskal-Wallis Test

### Method

The Kruskal-Wallis test extends the Wilcoxon rank-sum test to {spec.num_groups} or more groups.

**Null Hypothesis:** All groups have identical distributions

**Test Statistic:**
H = (12 / (N(N+1))) Σᵢ (Rᵢ²/nᵢ) - 3(N+1)

where:
- N = total sample size
- nᵢ = sample size in group i
- Rᵢ = sum of ranks in group i

**Distribution:** Chi-square with k-1 degrees of freedom

"""

        if spec.perform_pairwise:
            text += f"""
### Post-Hoc Pairwise Comparisons

If the overall Kruskal-Wallis test is significant (p < 0.05), pairwise comparisons
will be performed using the {spec.pairwise_method} method.

"""

            if spec.pairwise_method == "Dunn":
                text += """
**Dunn's Test:**
Compares all pairs of groups using rank sums, with adjustment for multiple comparisons.

"""

            if spec.adjust_pairwise:
                text += """
**Multiple Comparison Adjustment:** Bonferroni correction will be applied to
control family-wise error rate.

"""

        if spec.epsilon_squared:
            text += """
### Effect Size: Epsilon-Squared (ε²)

ε² = (H - k + 1) / (N - k)

**Interpretation:**
- ε² ≈ 0.01: Small effect
- ε² ≈ 0.06: Medium effect
- ε² ≈ 0.14: Large effect

"""

        return text

    def generate_friedman_methodology(
        self,
        spec: FriedmanSpec
    ) -> str:
        """Generate Friedman test methodology"""
        time_str = ", ".join(spec.time_points)

        text = f"""
## Repeated Measures Non-Parametric Analysis: Friedman Test

### Method

The Friedman test is a non-parametric alternative to repeated measures ANOVA
for comparing outcomes across time points: {time_str}.

**Null Hypothesis:** The distributions are identical at all time points

**Test Procedure:**
1. Rank outcomes within each subject across time points
2. Calculate sum of ranks for each time point
3. Compute test statistic:

Q = (12 / (nk(k+1))) Σⱼ Rⱼ² - 3n(k+1)

where:
- n = number of subjects
- k = number of time points
- Rⱼ = sum of ranks for time point j

**Distribution:** Chi-square with k-1 degrees of freedom

"""

        if spec.report_concordance:
            text += """
### Kendall's Coefficient of Concordance (W)

W = Q / (n(k-1))

**Interpretation:**
- W = 0: No agreement (complete randomness)
- W = 1: Perfect agreement
- Higher W indicates stronger concordance across time

"""

        if spec.perform_pairwise:
            text += f"""
### Post-Hoc Pairwise Comparisons

If the overall Friedman test is significant, pairwise comparisons between time points
will be performed using {spec.pairwise_method}'s method with appropriate adjustment
for multiple comparisons.

"""

        return text

    def _generate_assumptions_section(self) -> str:
        """Generate assumptions for non-parametric tests"""
        return """
### Assumptions

**Non-Parametric Test Assumptions:**

1. **Independence:** Observations are independent between subjects
   - Satisfied by randomized design

2. **Ordinal or Continuous:** Outcome can be ranked
   - Satisfied for continuous and ordinal outcomes

3. **Similar Shape:** Distribution shapes are similar between groups
   - Allows interpretation as location shift
   - If violated, test becomes a test of general distributional difference

**Note:** Non-parametric tests do NOT assume:
- Normality
- Equal variances
- Specific distributional form

This makes them robust alternatives when parametric assumptions fail.

"""

    def _generate_ties_section(self, spec: WilcoxonSpec) -> str:
        """Generate section on handling ties"""
        return f"""
### Handling of Tied Values

When multiple observations have the same value, ties are handled by {spec.tie_handling}:
"""  + ("""
- **Average ranks:** Tied values receive the average of the ranks they would occupy
- Most common method, provides continuity correction in variance

""" if spec.tie_handling == "average" else """
- Alternative tie-handling method as specified

""") + """
The test statistic variance is adjusted for the presence of ties to maintain validity.

"""

    def generate_bootstrap_methodology(
        self,
        spec: BootstrapSpec
    ) -> str:
        """Generate bootstrap CI methodology"""
        text = f"""
## Bootstrap Confidence Intervals

### Method

Bootstrap resampling will be used to construct {spec.confidence_level * 100:.0f}%
confidence intervals for treatment effects.

**Procedure:**
1. Draw {spec.num_bootstrap:,} bootstrap samples with replacement
2. Calculate treatment effect in each bootstrap sample
3. Construct CI from bootstrap distribution

**Bootstrap Method:** {spec.method}

"""

        if spec.method == "percentile":
            text += f"""
**Percentile Method:**
- Order bootstrap estimates from smallest to largest
- Lower limit = {(1 - spec.confidence_level) / 2 * 100:.1f}th percentile
- Upper limit = {(1 + spec.confidence_level) / 2 * 100:.1f}th percentile

**Advantages:** Simple, transformation-respecting

"""

        elif spec.method == "bca":
            text += """
**BCa (Bias-Corrected and Accelerated) Method:**
- Adjusts for bias and skewness in bootstrap distribution
- More accurate for small samples or skewed distributions
- Recommended when available

"""

        if spec.stratified_sampling:
            text += """
**Stratified Bootstrap:**
Bootstrap samples will be drawn separately within each treatment group to preserve
the randomization ratio and ensure sufficient representation.

"""

        text += f"""
**Reproducibility:**
Random seed = {spec.random_seed} for reproducible results

### Advantages

- No distributional assumptions
- Works for any estimator (mean, median, ratio, etc.)
- Automatically accounts for skewness
- Valid for complex study designs

"""

        return text


# Singleton instance
_nonparametric_service: Optional[NonParametricService] = None


def get_nonparametric_service() -> NonParametricService:
    """
    Get non-parametric service instance.

    Returns:
        NonParametricService instance
    """
    global _nonparametric_service

    if _nonparametric_service is None:
        _nonparametric_service = NonParametricService()

    return _nonparametric_service
