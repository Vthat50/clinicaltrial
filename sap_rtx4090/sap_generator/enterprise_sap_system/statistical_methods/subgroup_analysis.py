"""
Subgroup Analysis Framework
============================

Framework for pre-specified subgroup analyses in oncology trials.

Required by FDA for exploratory assessment of treatment effects
across patient characteristics.

Methods:
- Forest plots
- Interaction testing
- Treatment-by-subgroup analysis
- Consistency assessment
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SubgroupType(Enum):
    """Types of subgroup variables"""
    DEMOGRAPHIC = "Demographic"          # Age, sex, race, ethnicity
    DISEASE = "Disease Characteristic"   # Stage, histology, biomarker status
    BASELINE = "Baseline Clinical"       # ECOG, prior therapy, baseline tumor burden
    STRATIFICATION = "Stratification"    # Protocol stratification factors
    PROGNOSTIC = "Prognostic"           # Known prognostic factors
    PREDICTIVE = "Predictive Biomarker" # Potential treatment effect modifiers


@dataclass
class SubgroupVariable:
    """
    Definition of a subgroup variable for analysis.

    Each variable defines how subjects are categorized for subgroup analysis.
    """
    variable_name: str                   # e.g., "AGEGR1", "SEX", "PDLSCR"
    variable_label: str                  # Display name
    subgroup_type: SubgroupType

    # Categories
    levels: List[str] = field(default_factory=list)  # e.g., ["<65", ">=65"]
    level_labels: List[str] = field(default_factory=list)

    # Reference level for interaction test
    reference_level: Optional[str] = None

    # Analysis flags
    perform_interaction_test: bool = True
    interaction_threshold: float = 0.10   # p-value threshold

    # Special handling
    is_continuous: bool = False
    cutpoint: Optional[float] = None      # For continuous variables

    # Interpretation
    hypothesis: str = ""                  # Pre-specified hypothesis (if any)
    clinical_relevance: str = ""


@dataclass
class SubgroupAnalysisSpec:
    """
    Complete specification for subgroup analysis.

    Defines which subgroups to analyze and how.
    """
    endpoint_name: str
    endpoint_type: str                    # "time-to-event", "binary", "continuous"

    # Subgroup variables
    subgroup_variables: List[SubgroupVariable] = field(default_factory=list)

    # Analysis method
    primary_analysis_method: str = "Cox proportional hazards"  # or "CMH test", "Logistic regression"

    # Interaction testing
    test_interactions: bool = True
    interaction_significance: float = 0.10
    adjustment_for_multiplicity: bool = False

    # Presentation
    forest_plot: bool = True
    include_overall_effect: bool = True
    order_by_effect_size: bool = False

    # Interpretation guidance
    consistency_assessment: bool = True
    qualitative_interaction_threshold: float = 0.05  # For declaring qualitative interaction


class SubgroupAnalysisService:
    """
    Service for generating subgroup analysis specifications.

    Provides standardized methodology for exploratory subgroup analyses.
    """

    # Standard oncology subgroups (FDA guidance)
    STANDARD_SUBGROUPS = {
        "age": SubgroupVariable(
            variable_name="AGEGR1",
            variable_label="Age Group",
            subgroup_type=SubgroupType.DEMOGRAPHIC,
            levels=["<65", ">=65"],
            level_labels=["<65 years", "≥65 years"]
        ),
        "sex": SubgroupVariable(
            variable_name="SEX",
            variable_label="Sex",
            subgroup_type=SubgroupType.DEMOGRAPHIC,
            levels=["M", "F"],
            level_labels=["Male", "Female"]
        ),
        "race": SubgroupVariable(
            variable_name="RACE",
            variable_label="Race",
            subgroup_type=SubgroupType.DEMOGRAPHIC,
            levels=["WHITE", "ASIAN", "BLACK OR AFRICAN AMERICAN", "OTHER"],
            level_labels=["White", "Asian", "Black or African American", "Other"]
        ),
        "ecog": SubgroupVariable(
            variable_name="ECOG",
            variable_label="ECOG Performance Status",
            subgroup_type=SubgroupType.BASELINE,
            levels=["0", "1", "2+"],
            level_labels=["0", "1", "≥2"]
        ),
        "disease_stage": SubgroupVariable(
            variable_name="DSSTAGE",
            variable_label="Disease Stage",
            subgroup_type=SubgroupType.DISEASE,
            levels=["III", "IV"],
            level_labels=["Stage III", "Stage IV"]
        ),
        "prior_therapy": SubgroupVariable(
            variable_name="PRIORTHER",
            variable_label="Prior Systemic Therapy",
            subgroup_type=SubgroupType.BASELINE,
            levels=["Yes", "No"],
            level_labels=["Yes", "No"]
        ),
        "pdl1_status": SubgroupVariable(
            variable_name="PDLSCR",
            variable_label="PD-L1 Expression",
            subgroup_type=SubgroupType.PREDICTIVE,
            levels=["<1%", "1-49%", ">=50%"],
            level_labels=["<1%", "1-49%", "≥50%"],
            hypothesis="Higher PD-L1 may predict greater benefit from immunotherapy"
        ),
    }

    def __init__(self):
        """Initialize subgroup analysis service"""
        pass

    def create_standard_oncology_subgroups(self) -> List[SubgroupVariable]:
        """
        Get standard set of subgroups for oncology trials.

        Returns FDA-recommended demographic and disease subgroups.
        """
        return [
            self.STANDARD_SUBGROUPS["age"],
            self.STANDARD_SUBGROUPS["sex"],
            self.STANDARD_SUBGROUPS["race"],
            self.STANDARD_SUBGROUPS["ecog"],
            self.STANDARD_SUBGROUPS["disease_stage"],
        ]

    def add_biomarker_subgroup(
        self,
        biomarker_name: str,
        levels: List[str],
        hypothesis: str = ""
    ) -> SubgroupVariable:
        """
        Create biomarker subgroup variable.

        Args:
            biomarker_name: Biomarker name
            levels: Biomarker levels (e.g., ["Positive", "Negative"])
            hypothesis: Pre-specified hypothesis

        Returns:
            SubgroupVariable for biomarker
        """
        return SubgroupVariable(
            variable_name=biomarker_name.upper().replace(" ", ""),
            variable_label=biomarker_name,
            subgroup_type=SubgroupType.PREDICTIVE,
            levels=levels,
            level_labels=levels,
            hypothesis=hypothesis
        )

    def generate_subgroup_methodology(self, spec: SubgroupAnalysisSpec) -> str:
        """
        Generate subgroup analysis methodology text for SAP.

        Args:
            spec: Subgroup analysis specification

        Returns:
            Formatted methodology text
        """
        text = f"""
## Subgroup Analysis

### Objectives

Subgroup analyses will be performed to explore the consistency of treatment effect across patient subgroups. These analyses are exploratory and hypothesis-generating.

### Pre-specified Subgroups

The following subgroups have been pre-specified for analysis:

"""

        # List subgroups by type
        subgroups_by_type = {}
        for var in spec.subgroup_variables:
            type_name = var.subgroup_type.value
            if type_name not in subgroups_by_type:
                subgroups_by_type[type_name] = []
            subgroups_by_type[type_name].append(var)

        for type_name, variables in sorted(subgroups_by_type.items()):
            text += f"\n**{type_name} Subgroups:**\n"
            for var in variables:
                levels_str = ", ".join(var.level_labels)
                text += f"- {var.variable_label}: {levels_str}\n"
                if var.hypothesis:
                    text += f"  - *Hypothesis*: {var.hypothesis}\n"

        text += f"""
### Analysis Method

"""

        if spec.endpoint_type == "time-to-event":
            text += f"""
For time-to-event endpoints, subgroup analyses will use the Cox proportional hazards model:
- Hazard ratio and 95% confidence interval will be estimated for each subgroup
- Forest plots will display treatment effects across subgroups
"""
        elif spec.endpoint_type == "binary":
            text += """
For binary endpoints, subgroup analyses will use:
- Cochran-Mantel-Haenszel test stratified by subgroup
- Risk difference or odds ratio with 95% confidence intervals
"""

        if spec.test_interactions:
            text += f"""
### Interaction Testing

Treatment-by-subgroup interactions will be tested by including an interaction term in the model.

**Statistical Test:**
- Interaction p-value will be calculated for each subgroup variable
- Interaction considered notable if p < {spec.interaction_significance}
- No multiplicity adjustment will be applied (exploratory analysis)

**Interpretation:**
- p < {spec.qualitative_interaction_threshold}: Strong evidence of differential treatment effect
- {spec.qualitative_interaction_threshold} ≤ p < {spec.interaction_significance}: Moderate evidence
- p ≥ {spec.interaction_significance}: Insufficient evidence of differential effect

**Caution:**
Subgroup analyses are exploratory and should be interpreted with caution. Apparent differences may be due to chance, especially when multiple subgroups are examined.
"""

        if spec.consistency_assessment:
            text += """
### Consistency Assessment

The overall consistency of treatment effect will be assessed by:
1. Visual inspection of forest plot confidence intervals
2. Formal interaction tests
3. Clinical plausibility of any observed differences

**Interpretation Guidelines:**
- Treatment effect is considered broadly consistent if confidence intervals for all subgroups overlap
- Qualitative interactions (treatment beneficial in one subgroup, harmful in another) require strong statistical evidence and biological plausibility
- Quantitative interactions (degree of benefit varies but direction consistent) are common and may not alter clinical interpretation
"""

        text += """
### Presentation

Subgroup results will be presented as:
- Forest plot showing hazard ratios (or risk differences) and 95% CIs for each subgroup
- Overall treatment effect included for reference
- Interaction p-values displayed
"""

        if not spec.adjustment_for_multiplicity:
            text += """
### Multiplicity Considerations

**Important Note:** No adjustment for multiplicity will be made for subgroup analyses, as these are exploratory. All p-values should be interpreted descriptively, not as formal hypothesis tests. Results should be considered hypothesis-generating for future studies.
"""

        text += """
### Regulatory Guidance

These subgroup analyses follow FDA guidance on the collection and analysis of subgroup data:
- FDA (2014): "Collection of Race and Ethnicity Data in Clinical Trials"
- ICH E9 (1998): "Statistical Principles for Clinical Trials" - Section 5.7

**FDA Recommendations:**
1. Pre-specify subgroups in the protocol/SAP
2. Limit the number of subgroups examined
3. Provide rationale for subgroup selection
4. Interpret results cautiously, especially for post-hoc analyses
5. Consider consistency of effects, not just p-values
"""

        return text.strip()

    def generate_forest_plot_spec(self, spec: SubgroupAnalysisSpec) -> Dict:
        """
        Generate forest plot specification.

        Args:
            spec: Subgroup analysis specification

        Returns:
            Dictionary with forest plot specifications
        """
        plot_spec = {
            "title": f"Treatment Effect by Subgroup - {spec.endpoint_name}",
            "subtitle": "Hazard Ratio and 95% Confidence Interval",

            # Axes
            "x_axis_label": "Hazard Ratio" if spec.endpoint_type == "time-to-event" else "Risk Ratio",
            "x_axis_log_scale": True if spec.endpoint_type == "time-to-event" else False,
            "reference_line": 1.0,

            # Labels
            "left_label": "Favors Experimental",
            "right_label": "Favors Control",

            # Columns
            "display_columns": [
                "Subgroup",
                "N (Exp/Ctrl)",
                "Events (Exp/Ctrl)",
                "HR (95% CI)",
                "P-interaction"
            ],

            # Formatting
            "point_size_by_n": True,
            "show_heterogeneity_test": True,

            # Ordering
            "group_by_type": True,
            "include_overall": spec.include_overall_effect,

            # Statistical note
            "footnote": "Subgroup analyses are exploratory. Interaction p-values not adjusted for multiplicity."
        }

        return plot_spec

    def generate_interaction_test_code(
        self,
        spec: SubgroupAnalysisSpec,
        programming_language: str = "SAS"
    ) -> str:
        """
        Generate example code for interaction testing.

        Args:
            spec: Subgroup analysis specification
            programming_language: "SAS" or "R"

        Returns:
            Example code string
        """
        if programming_language == "SAS":
            return self._generate_sas_interaction_code(spec)
        elif programming_language == "R":
            return self._generate_r_interaction_code(spec)
        else:
            return ""

    def _generate_sas_interaction_code(self, spec: SubgroupAnalysisSpec) -> str:
        """Generate SAS code for interaction testing"""
        code = f"""
/* Subgroup Analysis with Interaction Testing */
/* Endpoint: {spec.endpoint_name} */

%macro subgroup_analysis(subgroup_var=, subgroup_label=);

    /* Overall treatment effect */
    proc phreg data=adtte;
        class trt01p (ref='Control');
        model aval*cnsr(1) = trt01p / risklimits;
        hazardratio trt01p / diff=ref;
        title "Overall: &subgroup_label";
    run;

    /* Treatment effect by subgroup */
    proc phreg data=adtte;
        class trt01p (ref='Control') &subgroup_var;
        model aval*cnsr(1) = trt01p &subgroup_var / risklimits;
        by &subgroup_var;
        hazardratio trt01p / diff=ref;
        title "By Subgroup: &subgroup_label";
    run;

    /* Interaction test */
    proc phreg data=adtte;
        class trt01p (ref='Control') &subgroup_var;
        model aval*cnsr(1) = trt01p &subgroup_var trt01p*&subgroup_var / risklimits;
        title "Interaction Test: &subgroup_label";
        ods output ParameterEstimates=parms_&subgroup_var;
    run;

%mend;

/* Run for each subgroup */
"""
        for var in spec.subgroup_variables:
            code += f"%subgroup_analysis(subgroup_var={var.variable_name}, subgroup_label={var.variable_label});\n"

        return code

    def _generate_r_interaction_code(self, spec: SubgroupAnalysisSpec) -> str:
        """Generate R code for interaction testing"""
        code = f"""
# Subgroup Analysis with Interaction Testing
# Endpoint: {spec.endpoint_name}

library(survival)
library(forestplot)

# Overall treatment effect
fit_overall <- coxph(Surv(AVAL, 1-CNSR) ~ TRT01P, data=adtte)
summary(fit_overall)

# Function for subgroup analysis
analyze_subgroup <- function(data, subgroup_var) {{

  # Treatment effect by subgroup
  formula_by <- as.formula(paste("Surv(AVAL, 1-CNSR) ~ TRT01P"))
  results_by <- list()

  for(level in unique(data[[subgroup_var]])) {{
    subset_data <- data[data[[subgroup_var]] == level, ]
    fit <- coxph(formula_by, data=subset_data)
    results_by[[level]] <- summary(fit)
  }}

  # Interaction test
  formula_int <- as.formula(paste("Surv(AVAL, 1-CNSR) ~ TRT01P *", subgroup_var))
  fit_int <- coxph(formula_int, data=data)

  # Extract interaction p-value
  p_interaction <- summary(fit_int)$coefficients[grep(":", rownames(summary(fit_int)$coefficients)), "Pr(>|z|)"]

  return(list(by_subgroup=results_by, p_interaction=p_interaction))
}}

# Run for each subgroup
"""
        for var in spec.subgroup_variables:
            code += f'results_{var.variable_name} <- analyze_subgroup(adtte, "{var.variable_name}")\n'

        return code


# Singleton instance
_subgroup_service: Optional[SubgroupAnalysisService] = None


def get_subgroup_analysis_service() -> SubgroupAnalysisService:
    """
    Get subgroup analysis service instance.

    Returns:
        SubgroupAnalysisService instance
    """
    global _subgroup_service

    if _subgroup_service is None:
        _subgroup_service = SubgroupAnalysisService()

    return _subgroup_service
