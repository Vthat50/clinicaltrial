#!/usr/bin/env python3
"""
ICE and Sensitivity Analysis Generator
======================================

Generates detailed ICH E9(R1) compliant Intercurrent Event handling
and comprehensive sensitivity analysis sections for SAP documents.

This module provides:
1. Endpoint-specific ICE specifications with strategies
2. Complete sensitivity analysis registries by endpoint type
3. Study-type-aware defaults (IO, biosimilar, targeted, etc.)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import yaml
from pathlib import Path


# =============================================================================
# ICE STRATEGY DEFINITIONS
# =============================================================================

class ICEStrategy(Enum):
    """ICH E9(R1) Intercurrent Event handling strategies."""
    TREATMENT_POLICY = "treatment_policy"
    COMPOSITE = "composite"
    HYPOTHETICAL = "hypothetical"
    PRINCIPAL_STRATUM = "principal_stratum"
    WHILE_ON_TREATMENT = "while_on_treatment"


@dataclass
class ICEDefinition:
    """Complete ICE definition with strategy and text."""
    event_name: str
    strategy: ICEStrategy
    description: str
    sensitivity_strategy: Optional[ICEStrategy] = None
    sensitivity_description: str = ""
    applicable_endpoints: List[str] = field(default_factory=list)


# =============================================================================
# ICE TEMPLATES BY ENDPOINT TYPE
# =============================================================================

ICE_TEMPLATES = {
    # Time-to-event endpoints (PFS, OS, DFS)
    "PFS": [
        ICEDefinition(
            event_name="Treatment discontinuation due to adverse event",
            strategy=ICEStrategy.TREATMENT_POLICY,
            description="PFS assessed regardless of treatment discontinuation. Subjects continue to be followed for disease progression and survival after discontinuation.",
            sensitivity_strategy=ICEStrategy.HYPOTHETICAL,
            sensitivity_description="Censor at treatment discontinuation (hypothetical: if AE had not occurred)."
        ),
        ICEDefinition(
            event_name="Treatment discontinuation due to disease progression",
            strategy=ICEStrategy.COMPOSITE,
            description="Disease progression is the endpoint event; discontinuation due to progression is captured in the primary analysis."
        ),
        ICEDefinition(
            event_name="Initiation of subsequent anticancer therapy",
            strategy=ICEStrategy.TREATMENT_POLICY,
            description="PFS assessed regardless of subsequent therapy initiation. Events occurring after subsequent therapy are included.",
            sensitivity_strategy=ICEStrategy.HYPOTHETICAL,
            sensitivity_description="Censor at initiation of subsequent therapy (hypothetical: if subsequent therapy had not been given)."
        ),
        ICEDefinition(
            event_name="Death before documented disease progression",
            strategy=ICEStrategy.COMPOSITE,
            description="Death from any cause before documented progression is included as a PFS event (composite strategy: death is part of the endpoint definition)."
        ),
        ICEDefinition(
            event_name="Treatment crossover (control to experimental)",
            strategy=ICEStrategy.TREATMENT_POLICY,
            description="Primary ITT analysis includes all events regardless of crossover.",
            sensitivity_strategy=ICEStrategy.HYPOTHETICAL,
            sensitivity_description="RPSFT or IPE adjustment to estimate treatment effect without crossover (hypothetical strategy)."
        ),
    ],

    "OS": [
        ICEDefinition(
            event_name="Treatment discontinuation",
            strategy=ICEStrategy.TREATMENT_POLICY,
            description="OS assessed regardless of treatment discontinuation. All subjects followed for survival regardless of treatment status."
        ),
        ICEDefinition(
            event_name="Initiation of subsequent anticancer therapy",
            strategy=ICEStrategy.TREATMENT_POLICY,
            description="OS assessed regardless of subsequent therapy. Deaths after subsequent therapy are included in the primary analysis.",
            sensitivity_strategy=ICEStrategy.HYPOTHETICAL,
            sensitivity_description="RPSFT/IPE adjustment to estimate OS effect without subsequent therapy confounding."
        ),
        ICEDefinition(
            event_name="Treatment crossover (control to experimental)",
            strategy=ICEStrategy.TREATMENT_POLICY,
            description="Primary ITT analysis includes all deaths regardless of crossover.",
            sensitivity_strategy=ICEStrategy.HYPOTHETICAL,
            sensitivity_description="RPSFT, IPE, or two-stage method to adjust for crossover effect."
        ),
    ],

    "DFS": [
        ICEDefinition(
            event_name="Treatment discontinuation",
            strategy=ICEStrategy.TREATMENT_POLICY,
            description="DFS assessed regardless of treatment discontinuation."
        ),
        ICEDefinition(
            event_name="Second primary malignancy",
            strategy=ICEStrategy.COMPOSITE,
            description="Second primary malignancy included as a DFS event (for iDFS endpoint).",
            sensitivity_description="Sensitivity excluding second primary malignancies (for DFS without 'i')."
        ),
        ICEDefinition(
            event_name="Death without recurrence",
            strategy=ICEStrategy.COMPOSITE,
            description="Death from any cause without prior recurrence is included as a DFS event."
        ),
    ],

    # Binary endpoints (ORR, pCR)
    "ORR": [
        ICEDefinition(
            event_name="Treatment discontinuation before response assessment",
            strategy=ICEStrategy.COMPOSITE,
            description="Subjects who discontinue before response assessment are considered non-responders (composite: non-response is part of endpoint definition)."
        ),
        ICEDefinition(
            event_name="Missing response assessment",
            strategy=ICEStrategy.COMPOSITE,
            description="Missing response assessments imputed as non-response in primary analysis.",
            sensitivity_description="Sensitivity analysis excluding subjects with missing assessments."
        ),
        ICEDefinition(
            event_name="Unconfirmed response",
            strategy=ICEStrategy.COMPOSITE,
            description="Unconfirmed responses counted as non-response per RECIST 1.1 confirmation requirements."
        ),
    ],

    # Duration endpoints (DOR)
    "DOR": [
        ICEDefinition(
            event_name="Initiation of subsequent therapy while responding",
            strategy=ICEStrategy.TREATMENT_POLICY,
            description="DOR continues to be assessed regardless of subsequent therapy.",
            sensitivity_strategy=ICEStrategy.HYPOTHETICAL,
            sensitivity_description="Censor at initiation of subsequent therapy."
        ),
        ICEDefinition(
            event_name="Death while still responding",
            strategy=ICEStrategy.COMPOSITE,
            description="Death in responders is included as end of response (DOR event)."
        ),
    ],
}


# =============================================================================
# SENSITIVITY ANALYSIS REGISTRY
# =============================================================================

@dataclass
class SensitivityAnalysis:
    """Definition of a sensitivity analysis."""
    name: str
    description: str
    required: bool = False
    required_if: str = ""  # Condition when required (e.g., "crossover_permitted")
    endpoint_types: List[str] = field(default_factory=list)  # e.g., ["PFS", "OS"]
    study_types: List[str] = field(default_factory=list)  # e.g., ["immuno_oncology"]


# Complete registry of standard sensitivity analyses
SENSITIVITY_ANALYSIS_REGISTRY = [
    # Universal sensitivity analyses
    SensitivityAnalysis(
        name="Per-Protocol Population",
        description="Primary analysis repeated in Per-Protocol population excluding subjects with major protocol deviations",
        required=True,
        endpoint_types=["PFS", "OS", "DFS", "ORR", "DOR"]
    ),
    SensitivityAnalysis(
        name="Unstratified Analysis",
        description="Log-rank test and Cox model without stratification factors to assess impact of stratification",
        required=True,
        endpoint_types=["PFS", "OS", "DFS"]
    ),
    SensitivityAnalysis(
        name="Investigator Assessment",
        description="Analysis using local investigator tumor assessments instead of IRC/BICR",
        required=True,
        endpoint_types=["PFS", "ORR", "DOR"]
    ),

    # Time-to-event specific
    SensitivityAnalysis(
        name="Per-Protocol Censoring",
        description="Subjects censored at date of major protocol deviation affecting endpoint",
        required=False,
        endpoint_types=["PFS", "OS", "DFS"]
    ),
    SensitivityAnalysis(
        name="Alternative Censoring for Missed Assessments",
        description="Count progression at actual date (vs censor at last adequate assessment) for subjects with ≥2 missed assessments",
        required=False,
        endpoint_types=["PFS"]
    ),
    SensitivityAnalysis(
        name="Censor at Subsequent Therapy",
        description="Censor at initiation of subsequent anticancer therapy (hypothetical strategy)",
        required=False,
        endpoint_types=["PFS", "OS"]
    ),

    # Non-proportional hazards
    SensitivityAnalysis(
        name="RMST Analysis",
        description="Restricted mean survival time analysis at 24/36 months when PH assumption may be violated",
        required_if="non_proportional_hazards_expected",
        endpoint_types=["PFS", "OS"],
        study_types=["immuno_oncology"]
    ),
    SensitivityAnalysis(
        name="Fleming-Harrington Weighted Analysis",
        description="G(rho=0, gamma=1) weighted log-rank test giving more weight to late differences",
        required_if="delayed_treatment_effect_expected",
        endpoint_types=["PFS", "OS"],
        study_types=["immuno_oncology"]
    ),
    SensitivityAnalysis(
        name="Max-Combo Test",
        description="Maximum of unweighted and weighted log-rank statistics for robust inference",
        required_if="delayed_treatment_effect_expected",
        endpoint_types=["PFS", "OS"],
        study_types=["immuno_oncology"]
    ),
    SensitivityAnalysis(
        name="Landmark Analysis",
        description="Survival rates at landmark timepoints (6, 12, 18, 24, 36 months)",
        required=True,
        endpoint_types=["PFS", "OS"]
    ),

    # Treatment crossover/switching
    SensitivityAnalysis(
        name="RPSFT Adjustment",
        description="Rank-preserving structural failure time model to adjust for treatment crossover effect",
        required_if="crossover_permitted",
        endpoint_types=["OS"],
        study_types=["immuno_oncology", "targeted_therapy"]
    ),
    SensitivityAnalysis(
        name="IPE Method",
        description="Iterative parameter estimation method for crossover adjustment",
        required_if="crossover_permitted",
        endpoint_types=["OS"]
    ),
    SensitivityAnalysis(
        name="Two-Stage Method",
        description="Two-stage adjustment method for treatment switching",
        required_if="crossover_permitted",
        endpoint_types=["OS"]
    ),

    # Missing data
    SensitivityAnalysis(
        name="Tipping Point Analysis",
        description="Assess sensitivity to missing data assumptions by systematically varying imputation",
        required=True,
        endpoint_types=["PFS", "OS", "ORR"]
    ),
    SensitivityAnalysis(
        name="Multiple Imputation",
        description="Multiple imputation under MAR assumption with 100+ imputations",
        required=False,
        endpoint_types=["ORR"]
    ),

    # Binary endpoint specific
    SensitivityAnalysis(
        name="Non-Responder Imputation",
        description="All missing responses imputed as non-responders (worst-case)",
        required=True,
        endpoint_types=["ORR"]
    ),
    SensitivityAnalysis(
        name="Evaluable Population Analysis",
        description="ORR in subjects with evaluable response assessments only",
        required=True,
        endpoint_types=["ORR"]
    ),
    SensitivityAnalysis(
        name="Best Response (Unconfirmed)",
        description="ORR including unconfirmed responses",
        required=False,
        endpoint_types=["ORR"]
    ),

    # Biosimilar specific
    SensitivityAnalysis(
        name="ITT and PP Dual Analysis",
        description="Equivalence demonstrated in both ITT and PP populations (co-primary for biosimilars)",
        required=True,
        endpoint_types=["ORR", "PFS"],
        study_types=["biosimilar"]
    ),
    SensitivityAnalysis(
        name="PK Population Analysis",
        description="PK equivalence in PK-evaluable population",
        required=True,
        endpoint_types=["PK"],
        study_types=["biosimilar"]
    ),
]


# =============================================================================
# ICE GENERATOR CLASS
# =============================================================================

class ICEGenerator:
    """
    Generates ICH E9(R1) compliant ICE handling sections.

    Combines protocol-specific ICE extractions with endpoint-type templates
    and study-type defaults.
    """

    def __init__(
        self,
        study_type: str = "general_oncology",
        crossover_permitted: bool = False,
        delayed_effect_expected: bool = False
    ):
        """
        Initialize ICE generator.

        Args:
            study_type: Study type for loading defaults
            crossover_permitted: Whether treatment crossover is allowed
            delayed_effect_expected: Whether delayed treatment effect is expected (IO)
        """
        self.study_type = study_type
        self.crossover_permitted = crossover_permitted
        self.delayed_effect_expected = delayed_effect_expected

    def generate_estimand_section(
        self,
        primary_endpoint: str,
        primary_endpoint_type: str,
        population: str,
        treatment: str,
        summary_measure: str
    ) -> str:
        """
        Generate complete estimand section with ICE handling.

        Args:
            primary_endpoint: Name of primary endpoint
            primary_endpoint_type: Type (PFS, OS, ORR, etc.)
            population: Target population description
            treatment: Treatment description
            summary_measure: Summary measure (HR, proportion, etc.)

        Returns:
            Formatted estimand section text
        """
        ice_list = ICE_TEMPLATES.get(primary_endpoint_type, [])

        text = f"""## Estimand Framework [ICH]

**Source:** Per ICH E9(R1) Addendum on estimands and sensitivity analysis in clinical trials.

### Primary Estimand

The primary estimand for this trial is defined by the following five attributes (per ICH E9 R1):

**1. Population:**
{population}

**2. Treatment:**
{treatment}

**3. Variable (Endpoint):**
{primary_endpoint}

**4. Intercurrent Events and Handling Strategies:**

"""
        # Add ICE table
        text += "| Intercurrent Event | Strategy | Handling |\n"
        text += "|-------------------|----------|----------|\n"

        for ice in ice_list:
            strategy_name = ice.strategy.value.replace("_", " ").title()
            # Truncate description for table
            desc = ice.description[:80] + "..." if len(ice.description) > 80 else ice.description
            text += f"| {ice.event_name} | {strategy_name} | {desc} |\n"

        text += f"""
**5. Population-Level Summary Measure:**
{summary_measure}

### Detailed ICE Handling

"""
        # Add detailed ICE descriptions
        for ice in ice_list:
            strategy_name = ice.strategy.value.replace("_", " ").title()
            text += f"**{ice.event_name}:**\n"
            text += f"- Strategy: {strategy_name}\n"
            text += f"- Handling: {ice.description}\n"
            if ice.sensitivity_strategy:
                sens_name = ice.sensitivity_strategy.value.replace("_", " ").title()
                text += f"- Sensitivity Analysis: {sens_name} - {ice.sensitivity_description}\n"
            text += "\n"

        return text

    def generate_ice_table_for_endpoint(self, endpoint_type: str) -> str:
        """Generate ICE handling table for a specific endpoint type."""
        ice_list = ICE_TEMPLATES.get(endpoint_type, [])

        if not ice_list:
            return f"No standard ICE definitions for {endpoint_type}. Protocol-specific handling will be applied.\n"

        text = f"### Intercurrent Events for {endpoint_type}\n\n"
        text += "| Intercurrent Event | Strategy | Description |\n"
        text += "|-------------------|----------|-------------|\n"

        for ice in ice_list:
            strategy_name = ice.strategy.value.replace("_", " ").title()
            text += f"| {ice.event_name} | {strategy_name} | {ice.description} |\n"

        return text


# =============================================================================
# SENSITIVITY ANALYSIS GENERATOR CLASS
# =============================================================================

class SensitivityAnalysisGenerator:
    """
    Generates comprehensive sensitivity analysis sections.

    Selects appropriate sensitivity analyses based on:
    - Endpoint type
    - Study type
    - Study characteristics (crossover, delayed effects, etc.)
    """

    def __init__(
        self,
        study_type: str = "general_oncology",
        crossover_permitted: bool = False,
        delayed_effect_expected: bool = False,
        biomarker_defined: bool = False
    ):
        """
        Initialize sensitivity analysis generator.

        Args:
            study_type: Study type
            crossover_permitted: Whether crossover is allowed
            delayed_effect_expected: Whether delayed effect expected
            biomarker_defined: Whether biomarker population is defined
        """
        self.study_type = study_type
        self.crossover_permitted = crossover_permitted
        self.delayed_effect_expected = delayed_effect_expected
        self.biomarker_defined = biomarker_defined

    def get_applicable_analyses(self, endpoint_type: str) -> List[SensitivityAnalysis]:
        """
        Get list of applicable sensitivity analyses for an endpoint.

        Args:
            endpoint_type: Endpoint type (PFS, OS, ORR, etc.)

        Returns:
            List of applicable SensitivityAnalysis objects
        """
        applicable = []

        for analysis in SENSITIVITY_ANALYSIS_REGISTRY:
            # Check endpoint type
            if analysis.endpoint_types and endpoint_type not in analysis.endpoint_types:
                continue

            # Check study type
            if analysis.study_types and self.study_type not in analysis.study_types:
                continue

            # Check conditional requirements
            if analysis.required_if:
                if analysis.required_if == "crossover_permitted" and not self.crossover_permitted:
                    continue
                if analysis.required_if == "delayed_treatment_effect_expected" and not self.delayed_effect_expected:
                    continue
                if analysis.required_if == "non_proportional_hazards_expected" and not self.delayed_effect_expected:
                    continue

            applicable.append(analysis)

        return applicable

    def generate_sensitivity_section(self, endpoint_type: str, endpoint_name: str) -> str:
        """
        Generate complete sensitivity analysis section for an endpoint.

        Args:
            endpoint_type: Endpoint type (PFS, OS, ORR, etc.)
            endpoint_name: Full endpoint name

        Returns:
            Formatted sensitivity analysis section
        """
        analyses = self.get_applicable_analyses(endpoint_type)

        text = f"### Sensitivity Analyses for {endpoint_name}\n\n"

        if not analyses:
            text += "Standard sensitivity analyses will be defined in the detailed SAP.\n"
            return text

        # Separate required and conditional
        required = [a for a in analyses if a.required]
        conditional = [a for a in analyses if not a.required]

        text += "#### Required Sensitivity Analyses\n\n"
        text += "| # | Analysis | Description |\n"
        text += "|---|----------|-------------|\n"

        for i, analysis in enumerate(required, 1):
            text += f"| {i} | {analysis.name} | {analysis.description} |\n"

        if conditional:
            text += "\n#### Additional Sensitivity Analyses (As Applicable)\n\n"
            text += "| # | Analysis | Description | Condition |\n"
            text += "|---|----------|-------------|----------|\n"

            for i, analysis in enumerate(conditional, 1):
                condition = analysis.required_if.replace("_", " ").title() if analysis.required_if else "If applicable"
                text += f"| {i} | {analysis.name} | {analysis.description} | {condition} |\n"

        return text

    def generate_complete_sensitivity_section(
        self,
        primary_endpoint_type: str,
        secondary_endpoint_types: List[str]
    ) -> str:
        """
        Generate complete sensitivity analysis section for all endpoints.

        Args:
            primary_endpoint_type: Primary endpoint type
            secondary_endpoint_types: List of secondary endpoint types

        Returns:
            Complete sensitivity analysis section
        """
        text = "## Sensitivity Analyses [ICH/DEFAULT]\n\n"
        text += f"**Source:** Per ICH E9(R1) guidance on sensitivity analyses. Study-type specific analyses included for {self.study_type}.\n\n"
        text += "The following sensitivity analyses will be performed to assess the robustness of primary and key secondary analyses.\n\n"

        # Primary endpoint
        text += f"### Primary Endpoint ({primary_endpoint_type})\n\n"
        text += self.generate_sensitivity_section(primary_endpoint_type, f"Primary ({primary_endpoint_type})")

        # Secondary endpoints
        for sec_type in secondary_endpoint_types:
            text += f"\n### {sec_type}\n\n"
            text += self.generate_sensitivity_section(sec_type, sec_type)

        return text


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_ice_section(
    endpoint_type: str,
    study_type: str = "general_oncology"
) -> str:
    """Generate ICE section for an endpoint."""
    generator = ICEGenerator(study_type=study_type)
    return generator.generate_ice_table_for_endpoint(endpoint_type)


def generate_sensitivity_analyses(
    endpoint_type: str,
    study_type: str = "general_oncology",
    crossover_permitted: bool = False,
    delayed_effect: bool = False
) -> str:
    """Generate sensitivity analyses for an endpoint."""
    generator = SensitivityAnalysisGenerator(
        study_type=study_type,
        crossover_permitted=crossover_permitted,
        delayed_effect_expected=delayed_effect
    )
    return generator.generate_sensitivity_section(endpoint_type, endpoint_type)
