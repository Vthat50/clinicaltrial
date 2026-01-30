"""
Missing Data Handling Methods
==============================

Methods for handling missing data in clinical trials per ICH E9(R1).

FDA Guidance: "Missing Data in Clinical Trials" (2019)
ICH E9(R1): Estimands and sensitivity analysis framework

Methods:
- Multiple Imputation
- Tipping Point Analysis
- Pattern Mixture Models
- Selection Models
- Worst/Best Case Scenarios
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MissingDataMechanism(Enum):
    """Missing data mechanisms (Rubin's framework)"""
    MCAR = "Missing Completely At Random"  # Missing independent of observed and unobserved data
    MAR = "Missing At Random"              # Missing depends only on observed data
    MNAR = "Missing Not At Random"         # Missing depends on unobserved data


class ImputationMethod(Enum):
    """Imputation methods"""
    MULTIPLE_IMPUTATION = "Multiple Imputation"
    SINGLE_IMPUTATION = "Single Imputation"
    WORST_CASE = "Worst Case Imputation"
    BEST_CASE = "Best Case Imputation"
    LAST_OBSERVATION = "Last Observation Carried Forward (LOCF)"
    BASELINE_OBSERVATION = "Baseline Observation Carried Forward (BOCF)"


@dataclass
class MissingDataAssumption:
    """
    Assumption about missing data mechanism.

    Critical for interpretation and sensitivity analysis planning.
    """
    mechanism: MissingDataMechanism
    justification: str
    variables_affected: List[str] = field(default_factory=list)

    # Expected missingness
    expected_rate: float = 0.0  # Percentage
    expected_pattern: str = ""  # e.g., "Monotone (dropout)", "Intermittent", "Random"

    # Sensitivity analysis implications
    requires_sensitivity: bool = True
    sensitivity_methods: List[str] = field(default_factory=list)


@dataclass
class MultipleImputationSpec:
    """
    Specification for multiple imputation analysis.

    Primary analysis for MAR mechanism per FDA guidance.
    """
    # MI parameters
    num_imputations: int = 100  # FDA recommends 100-200 for pivotal trials
    imputation_model: str = "Fully conditional specification (FCS)"

    # Variables
    imputation_variables: List[str] = field(default_factory=list)
    auxiliary_variables: List[str] = field(default_factory=list)  # Predictors of missingness

    # Model specification
    imputation_method_by_var: Dict[str, str] = field(default_factory=dict)  # var -> method

    # Pooling
    pooling_method: str = "Rubin's rules"

    # Software
    software: str = "SAS PROC MI / PROC MIANALYZE"  # or "R mice package"


@dataclass
class TippingPointSpec:
    """
    Tipping point analysis specification.

    Evaluates how much departure from MAR is needed to change conclusions.
    """
    # Control parameter
    control_assumption: str = "MAR"  # Assumption for control group

    # Experimental group scenarios
    experimental_scenarios: List[str] = field(default_factory=list)  # e.g., ["MAR", "MNAR (worse)", "MNAR (better)"]

    # Delta parameters
    delta_range: List[float] = field(default_factory=list)  # Range of delta values to test
    delta_interpretation: str = ""  # What delta represents clinically

    # Decision rule
    clinical_relevance_threshold: float = 0.0  # Threshold for clinical significance


@dataclass
class SensitivityAnalysisSpec:
    """
    Complete sensitivity analysis specification for missing data.

    Required by FDA for primary efficacy analyses.
    """
    primary_assumption: MissingDataMechanism
    primary_method: str

    # Sensitivity scenarios
    sensitivity_scenarios: List[str] = field(default_factory=list)

    # Methods for each scenario
    scenario_methods: Dict[str, str] = field(default_factory=dict)

    # Interpretation criteria
    robustness_criteria: str = ""


class MissingDataService:
    """
    Service for missing data handling specifications.

    Provides FDA-compliant missing data analysis plans.
    """

    def __init__(self):
        """Initialize missing data service"""
        pass

    def generate_missing_data_section(
        self,
        endpoint_name: str,
        assumption: MissingDataAssumption,
        mi_spec: MultipleImputationSpec,
        sensitivity_spec: SensitivityAnalysisSpec
    ) -> str:
        """
        Generate complete missing data section for SAP.

        Args:
            endpoint_name: Primary endpoint name
            assumption: Missing data assumption
            mi_spec: Multiple imputation specification
            sensitivity_spec: Sensitivity analysis specification

        Returns:
            Formatted SAP text
        """
        text = f"""
## Handling of Missing Data

### Missing Data Mechanism

**Primary Assumption:** {assumption.mechanism.value}

**Justification:**
{assumption.justification}

**Expected Missingness:**
- Expected rate: ~{assumption.expected_rate}%
- Expected pattern: {assumption.expected_pattern}
- Variables affected: {', '.join(assumption.variables_affected)}

"""

        text += self._generate_primary_analysis_text(assumption, mi_spec)
        text += "\n\n"
        text += self._generate_sensitivity_analysis_text(sensitivity_spec)
        text += "\n\n"
        text += self._generate_interpretation_section()

        return text.strip()

    def _generate_primary_analysis_text(
        self,
        assumption: MissingDataAssumption,
        mi_spec: MultipleImputationSpec
    ) -> str:
        """Generate primary analysis section"""
        text = """
### Primary Analysis Method

"""

        if assumption.mechanism == MissingDataMechanism.MAR:
            text += f"""
**Multiple Imputation** will be used for the primary analysis, consistent with the MAR assumption.

**Imputation Specification:**
- Number of imputations: {mi_spec.num_imputations}
- Imputation model: {mi_spec.imputation_model}
- Imputation method: Predictive mean matching for continuous variables, logistic regression for binary variables
- Auxiliary variables: {', '.join(mi_spec.auxiliary_variables) if mi_spec.auxiliary_variables else 'None'}

**Imputation Model:**
The imputation model will include:
- Treatment group
- Stratification factors
- Baseline covariates predictive of the outcome
- Variables predictive of missingness

**Pooling:**
Results from {mi_spec.num_imputations} imputed datasets will be combined using {mi_spec.pooling_method}. Standard errors will account for both within-imputation and between-imputation variability.

**Software:**
{mi_spec.software}
"""

        elif assumption.mechanism == MissingDataMechanism.MCAR:
            text += """
**Complete Case Analysis** will be used for the primary analysis, as missing data is assumed to be completely at random.

Subjects with complete data for the endpoint will be included in the analysis. No imputation will be performed for the primary analysis.

**Justification:**
Complete case analysis is unbiased under MCAR. The validity of this assumption will be assessed by comparing baseline characteristics between subjects with and without missing data.
"""

        return text.strip()

    def _generate_sensitivity_analysis_text(self, spec: SensitivityAnalysisSpec) -> str:
        """Generate sensitivity analysis section"""
        text = f"""
### Sensitivity Analyses for Missing Data

To assess the robustness of the primary analysis to the MAR assumption, the following sensitivity analyses will be performed:

"""

        # Standard sensitivity analyses
        text += """
#### 1. Tipping Point Analysis

Tipping point analysis will evaluate how much departure from the MAR assumption would be needed to change the study conclusions.

**Method:**
- Control group: Impute under MAR assumption
- Experimental group: Systematically vary assumptions from MAR to increasingly pessimistic MNAR scenarios
- Identify the "tipping point" where statistical significance is lost

**Parameters:**
- δ (delta): Departure from MAR, expressed as mean difference in outcome for missing vs observed values
- Range: δ = 0 (MAR) to δ = [clinically relevant difference]

**Interpretation:**
- If tipping point requires large, clinically implausible δ → Results robust
- If tipping point requires small, plausible δ → Results sensitive to MAR assumption

#### 2. Worst Case / Best Case Analysis

**Worst Case:**
- Missing outcomes in experimental arm imputed as treatment failures/events
- Missing outcomes in control arm imputed as successes/non-events

**Best Case:**
- Missing outcomes in experimental arm imputed as successes/non-events
- Missing outcomes in control arm imputed as treatment failures/events

**Interpretation:**
If primary analysis conclusion holds under both worst and best case scenarios, results are considered robust.

#### 3. Pattern Mixture Model

A pattern mixture model will be fit, stratifying by missing data patterns:
- Completers (no missing data)
- Early dropouts (missing data before key timepoint)
- Late dropouts (missing data after key timepoint)

Treatment effects will be estimated within each pattern and combined.

#### 4. Comparison with Complete Case Analysis

Results from multiple imputation will be compared with complete case analysis. Large differences suggest sensitivity to missing data assumptions.
"""

        text += f"""
### Assessment of Robustness

{spec.robustness_criteria if spec.robustness_criteria else '''
The primary analysis will be considered robust if:
1. All sensitivity analyses support the same clinical conclusion as the primary analysis
2. Tipping point analysis shows that implausible assumptions about MNAR are needed to change conclusions
3. Results are consistent across different missing data patterns
'''}

### Regulatory Considerations

This missing data analysis plan follows:
- **FDA Guidance (2019):** "Missing Data in Clinical Trials - Guidance for Industry"
- **ICH E9(R1) (2019):** "Addendum on Estimands and Sensitivity Analysis"
- **NRC Report (2010):** "The Prevention and Treatment of Missing Data in Clinical Trials"

**Key Principles:**
1. Missing data mechanism should be explicitly stated
2. Primary analysis should be appropriate for the assumed mechanism
3. Sensitivity analyses should evaluate departures from primary assumption
4. Interpretation should consider totality of evidence across all analyses
"""

        return text.strip()

    def _generate_interpretation_section(self) -> str:
        """Generate interpretation guidance"""
        return """
### Interpretation Framework

**Primary Conclusion:**
The primary conclusion will be based on the primary analysis under the pre-specified MAR assumption.

**Robustness:**
Sensitivity analyses will be used to assess whether conclusions are robust to departures from MAR. If sensitivity analyses show materially different results, this will be clearly stated and clinical implications discussed.

**Reporting:**
All missing data analyses (primary and sensitivity) will be reported in the clinical study report. The pattern and reasons for missing data will be summarized and compared between treatment groups.

**Regulatory Expectation:**
Per FDA guidance, if the primary analysis is based on MAR and missingness rates differ substantially between arms or are related to outcome, sensitivity analyses under MNAR assumptions are expected to support the primary conclusions.
"""

    def generate_imputation_code_example(
        self,
        spec: MultipleImputationSpec,
        language: str = "SAS"
    ) -> str:
        """
        Generate example code for multiple imputation.

        Args:
            spec: MI specification
            language: "SAS" or "R"

        Returns:
            Example code
        """
        if language == "SAS":
            return f"""
/* Multiple Imputation for Missing Data */

/* Step 1: Create imputed datasets */
proc mi data=adtte
    nimpute={spec.num_imputations}
    seed=54321
    out=adtte_imputed;

    class trt01p stratification_factors;

    var aval cnsr trt01p
        baseline_var1 baseline_var2
        {' '.join(spec.auxiliary_variables)};

    fcs nbiter=100 plots=none;

run;

/* Step 2: Analyze each imputed dataset */
proc phreg data=adtte_imputed;
    by _imputation_;
    class trt01p (ref='Control');
    model aval*cnsr(1) = trt01p / risklimits;
    ods output ParameterEstimates=parms;
run;

/* Step 3: Combine results using Rubin's rules */
proc mianalyze data=parms;
    modeleffects trt01p;
    stderr stderr;
run;
"""
        elif language == "R":
            return f"""
# Multiple Imputation for Missing Data

library(mice)
library(survival)
library(mitools)

# Step 1: Create imputed datasets
imputation_model <- mice(
    data = adtte,
    m = {spec.num_imputations},
    method = 'pmm',  # Predictive mean matching
    seed = 54321,
    maxit = 10,
    print = FALSE
)

# Step 2: Analyze each imputed dataset
fit_list <- with(
    imputation_model,
    coxph(Surv(AVAL, 1-CNSR) ~ TRT01P)
)

# Step 3: Pool results using Rubin's rules
pooled_results <- pool(fit_list)
summary(pooled_results)

# Extract hazard ratio and CI
exp(coef(pooled_results))
exp(confint(pooled_results))
"""
        else:
            return ""


# Singleton instance
_missing_data_service: Optional[MissingDataService] = None


def get_missing_data_service() -> MissingDataService:
    """
    Get missing data service instance.

    Returns:
        MissingDataService instance
    """
    global _missing_data_service

    if _missing_data_service is None:
        _missing_data_service = MissingDataService()

    return _missing_data_service
