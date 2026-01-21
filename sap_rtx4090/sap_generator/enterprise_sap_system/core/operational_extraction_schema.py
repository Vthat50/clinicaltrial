#!/usr/bin/env python3
"""
Operational Extraction Schema - TIER 1: Protocol-Specific Rules
================================================================

This module defines data structures for extracting protocol-specific
operational rules that vary by study and MUST come from the protocol.

These are NOT industry standards (Tier 2) or study-type defaults (Tier 3).
These are facts that can only be determined by reading the specific protocol.

Key extractions:
- Visit windows and schedules
- Stratification factors with actual levels
- Model covariates explicitly mentioned
- Population criteria (PK, PP exclusions)
- Period definitions (induction, maintenance)
- ICE specifications per endpoint
- Censoring rules if non-standard
- Interim analysis triggers
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


# =============================================================================
# VISIT AND WINDOWING SPECIFICATIONS
# =============================================================================

@dataclass
class VisitWindow:
    """Single visit window specification extracted from protocol."""
    visit_name: str                         # e.g., "Week 4", "Cycle 2 Day 1"
    target_day: int                         # Target study day
    window_minus: int                       # Days before target (e.g., 3 for ±3)
    window_plus: int                        # Days after target
    min_day: int = 0                        # Computed: target_day - window_minus
    max_day: int = 0                        # Computed: target_day + window_plus

    # Assessment types at this visit
    assessments: List[str] = field(default_factory=list)  # e.g., ["tumor", "labs", "vitals"]

    # Period this visit belongs to
    period: str = ""                        # e.g., "Induction", "Maintenance"

    def __post_init__(self):
        """Compute min/max days from target and window."""
        self.min_day = self.target_day - self.window_minus
        self.max_day = self.target_day + self.window_plus


@dataclass
class VisitSchedule:
    """Complete visit schedule extracted from protocol."""
    # All visits with windows
    visits: List[VisitWindow] = field(default_factory=list)

    # Schedule metadata
    schedule_basis: str = ""                # "weekly", "q2w", "q3w", "q4w"
    cycle_length_days: int = 0              # e.g., 21 for q3w

    # Tumor assessment schedule
    tumor_assessment_frequency: str = ""    # e.g., "Every 8 weeks"
    tumor_assessment_visits: List[str] = field(default_factory=list)

    # Special visits
    baseline_visit: str = "Day 1"
    end_of_treatment_visit: str = ""
    follow_up_schedule: str = ""            # e.g., "Every 3 months for 2 years"


# =============================================================================
# POPULATION SPECIFICATIONS
# =============================================================================

@dataclass
class PKPopulationCriteria:
    """PK population definition extracted from protocol."""
    included: bool = False                  # Whether PK endpoints exist

    definition: str = ""                    # Full definition text

    # Inclusion criteria
    minimum_samples: int = 1                # Minimum evaluable samples required
    required_timepoints: List[str] = field(default_factory=list)  # Required sampling times

    # Exclusion criteria for PK population
    exclusion_criteria: List[str] = field(default_factory=list)

    # PK sampling windows
    sampling_windows: Dict[str, str] = field(default_factory=dict)
    # e.g., {"pre_dose": "Within 30 min before infusion", "EOI": "Within 15 min after"}


@dataclass
class PPExclusionCriteria:
    """Per-Protocol population exclusion criteria from protocol."""
    # Major protocol deviations that exclude from PP
    exclusion_criteria: List[str] = field(default_factory=list)
    # e.g., ["Wrong randomization stratum", "Less than 80% dose intensity",
    #        "Major GCP violation", "Missing primary endpoint assessment"]

    # Minimum treatment exposure for PP
    minimum_exposure: str = ""              # e.g., "At least 2 cycles" or "80% of planned dose"


@dataclass
class DualPopulationRequirement:
    """For biosimilars: explicit dual population success requirement."""
    required: bool = False

    primary_population: str = "ITT"
    co_primary_population: str = "PP"

    success_criterion: str = ""             # e.g., "Equivalence in BOTH populations"

    # Explicit text to include in SAP
    sap_text: str = ""


@dataclass
class PopulationSpecifications:
    """All population specifications extracted from protocol."""
    # Standard populations
    itt_definition: str = "All randomized subjects"
    safety_definition: str = "All subjects who received at least one dose"

    # PK population (if applicable)
    pk_population: Optional[PKPopulationCriteria] = None

    # PP exclusions
    pp_exclusions: Optional[PPExclusionCriteria] = None

    # Dual population requirement (biosimilars)
    dual_population: Optional[DualPopulationRequirement] = None

    # Biomarker populations
    biomarker_populations: List[Dict[str, str]] = field(default_factory=list)
    # e.g., [{"name": "PD-L1 High", "definition": "TPS ≥50%"}]


# =============================================================================
# PERIOD DEFINITIONS
# =============================================================================

@dataclass
class StudyPeriod:
    """Single study period definition."""
    name: str                               # e.g., "Induction", "Maintenance"

    # Period timing
    start_criterion: str = ""               # e.g., "First dose", "End of induction"
    end_criterion: str = ""                 # e.g., "Completion of 6 cycles", "Disease progression"

    # Duration
    planned_duration: str = ""              # e.g., "24 weeks", "Until progression"

    # Period-specific population
    population_criterion: str = ""          # e.g., "Controlled disease at end of induction"


@dataclass
class ControlledDiseaseCriteria:
    """Definition of controlled disease for maintenance eligibility."""
    definition: str = ""                    # Full definition text

    # Response categories that qualify
    qualifying_responses: List[str] = field(default_factory=list)
    # e.g., ["CR", "PR", "SD"]

    # Assessment timing
    assessment_timing: str = ""             # e.g., "Week 24 assessment"

    # Additional criteria
    additional_criteria: List[str] = field(default_factory=list)
    # e.g., ["No dose-limiting toxicity", "ECOG ≤2"]


@dataclass
class PeriodDefinitions:
    """All study period definitions from protocol."""
    periods: List[StudyPeriod] = field(default_factory=list)

    # Controlled disease (for maintenance studies)
    controlled_disease: Optional[ControlledDiseaseCriteria] = None

    # Period boundaries
    induction_to_maintenance: str = ""      # e.g., "Week 24"
    treatment_to_followup: str = ""         # e.g., "30 days after last dose"


# =============================================================================
# COVARIATE SPECIFICATIONS
# =============================================================================

@dataclass
class ModelCovariates:
    """Explicit covariates mentioned in protocol for statistical models."""
    # Stratification factors (used in randomization)
    stratification_factors: List[str] = field(default_factory=list)
    stratification_factor_levels: Dict[str, List[str]] = field(default_factory=dict)
    # e.g., {"PD-L1": ["<1%", "1-49%", "≥50%"], "ECOG": ["0", "1"]}

    # Covariates explicitly mentioned for models
    primary_analysis_covariates: List[str] = field(default_factory=list)
    # e.g., ["Treatment", "ECOG", "PD-L1 status", "Region"]

    # Specify whether stratification used in both log-rank AND Cox
    stratification_in_logrank: bool = True
    stratification_in_cox: bool = True

    # Additional covariates for Cox model (beyond stratification)
    additional_cox_covariates: List[str] = field(default_factory=list)

    # Baseline covariates for adjustment
    baseline_adjustment_covariates: List[str] = field(default_factory=list)
    # e.g., ["Baseline tumor burden", "Prior lines of therapy"]


# =============================================================================
# ICE SPECIFICATIONS
# =============================================================================

class ICEStrategy(Enum):
    """Intercurrent event handling strategies per ICH E9(R1)."""
    TREATMENT_POLICY = "treatment_policy"
    COMPOSITE = "composite"
    HYPOTHETICAL = "hypothetical"
    PRINCIPAL_STRATUM = "principal_stratum"
    WHILE_ON_TREATMENT = "while_on_treatment"


@dataclass
class ICESpecification:
    """Single intercurrent event specification."""
    event_name: str                         # e.g., "Treatment discontinuation due to AE"
    strategy: ICEStrategy

    # Detailed handling description
    handling_description: str = ""

    # For hypothetical strategy: what's the counterfactual?
    counterfactual: str = ""                # e.g., "If treatment had not been discontinued"

    # Sensitivity analysis for this ICE
    sensitivity_strategy: Optional[ICEStrategy] = None
    sensitivity_description: str = ""


@dataclass
class EndpointICEMapping:
    """ICE specifications for a single endpoint."""
    endpoint: str                           # e.g., "PFS", "OS"
    ice_specifications: List[ICESpecification] = field(default_factory=list)


@dataclass
class ICEFramework:
    """Complete ICE framework extracted from protocol."""
    # Per-endpoint ICE handling
    endpoint_ice_mapping: List[EndpointICEMapping] = field(default_factory=list)

    # Common ICEs across endpoints
    common_ices: List[ICESpecification] = field(default_factory=list)

    # Protocol-specified text for estimand section
    estimand_text: str = ""


# =============================================================================
# CENSORING RULES (NON-STANDARD)
# =============================================================================

@dataclass
class CensoringRule:
    """Single censoring rule specification."""
    situation: str                          # e.g., "Started new anticancer therapy"
    event_or_censor: str                    # "Event" or "Censored"
    date_used: str                          # e.g., "Date of last adequate assessment"
    cnsr_value: int                         # 0 for event, 1 for censored
    note: str = ""                          # Additional context


@dataclass
class EndpointCensoringRules:
    """Censoring rules for a specific endpoint."""
    endpoint: str                           # e.g., "PFS"
    rules: List[CensoringRule] = field(default_factory=list)

    # Non-standard rules from protocol (override defaults)
    protocol_specific_rules: List[CensoringRule] = field(default_factory=list)


@dataclass
class CensoringSpecifications:
    """All censoring specifications extracted from protocol."""
    # Per-endpoint censoring
    endpoint_rules: List[EndpointCensoringRules] = field(default_factory=list)

    # Protocol specifies non-standard handling?
    has_nonstandard_rules: bool = False
    nonstandard_rules_text: str = ""


# =============================================================================
# INTERIM ANALYSIS TIMING
# =============================================================================

@dataclass
class InterimTrigger:
    """Specific interim analysis trigger from protocol."""
    analysis_number: int                    # 1, 2, 3...

    # Trigger type
    trigger_type: str                       # "events", "time", "information_fraction"

    # Trigger value
    event_count: Optional[int] = None       # e.g., 250 PFS events
    calendar_time: str = ""                 # e.g., "12 months after LPI"
    information_fraction: Optional[float] = None  # e.g., 0.6 for 60%

    # Expected timing
    expected_date: str = ""                 # e.g., "Q4 2026"

    # What endpoints analyzed
    endpoints_analyzed: List[str] = field(default_factory=list)

    # Alpha spent
    alpha_spent: Optional[float] = None
    cumulative_alpha: Optional[float] = None


@dataclass
class InterimAnalysisSpecification:
    """Complete interim analysis specification from protocol."""
    # Number of analyses
    num_interim: int = 0
    has_final_analysis: bool = True

    # Triggers for each analysis
    triggers: List[InterimTrigger] = field(default_factory=list)

    # Boundary method
    alpha_spending_function: str = ""       # e.g., "Lan-DeMets O'Brien-Fleming"
    futility_boundary: str = ""             # "binding", "non-binding", "none"

    # Calendar timeline
    one_year_report: str = ""               # e.g., "12 months after last patient enrolled"
    regulatory_submission_analysis: str = ""  # e.g., "After 382 PFS events"

    # DSMB
    dsmb_review: bool = True
    dsmb_frequency: str = ""                # e.g., "Every 6 months"


# =============================================================================
# COMPLETE OPERATIONAL SPECIFICATIONS
# =============================================================================

@dataclass
class OperationalSpecifications:
    """
    Complete operational specifications extracted from protocol.

    This is the main data structure that combines all Tier 1 extractions.
    It is merged with Tier 2 (industry standards) and Tier 3 (study-type defaults)
    in the pipeline to generate the complete SAP.
    """
    # Visit and windowing
    visit_schedule: Optional[VisitSchedule] = None

    # Populations
    populations: Optional[PopulationSpecifications] = None

    # Study periods
    periods: Optional[PeriodDefinitions] = None

    # Model covariates
    covariates: Optional[ModelCovariates] = None

    # ICE handling
    ice_framework: Optional[ICEFramework] = None

    # Censoring rules (non-standard)
    censoring: Optional[CensoringSpecifications] = None

    # Interim analysis
    interim_analysis: Optional[InterimAnalysisSpecification] = None

    # Study type detection (for loading Tier 3 defaults)
    detected_study_type: str = ""           # "biosimilar", "immuno_oncology", etc.

    # Protocol-specific text to preserve verbatim
    verbatim_sections: Dict[str, str] = field(default_factory=dict)
    # e.g., {"baseline_definition": "Baseline is defined as the last...",
    #        "response_criteria": "RECIST 1.1 will be used..."}


# =============================================================================
# EXTRACTION FUNCTIONS
# =============================================================================

def create_default_operational_specs() -> OperationalSpecifications:
    """Create empty operational specifications for population."""
    return OperationalSpecifications(
        visit_schedule=VisitSchedule(),
        populations=PopulationSpecifications(),
        periods=PeriodDefinitions(),
        covariates=ModelCovariates(),
        ice_framework=ICEFramework(),
        censoring=CensoringSpecifications(),
        interim_analysis=InterimAnalysisSpecification()
    )


def detect_study_type(
    hypothesis_framework: str,
    has_pk_endpoints: bool,
    drug_class: str,
    treatment_setting: str
) -> str:
    """
    Detect study type for loading appropriate Tier 3 defaults.

    Args:
        hypothesis_framework: "superiority", "equivalence", "non_inferiority"
        has_pk_endpoints: Whether PK endpoints are present
        drug_class: "immunotherapy", "chemotherapy", "targeted", "biosimilar"
        treatment_setting: "first-line", "adjuvant", "maintenance", etc.

    Returns:
        Study type string: "biosimilar", "immuno_oncology", "targeted_therapy",
                          "adjuvant", "maintenance", "single_arm"
    """
    # Biosimilar detection
    if hypothesis_framework == "equivalence" or drug_class == "biosimilar":
        return "biosimilar"

    # Maintenance study
    if treatment_setting == "maintenance":
        return "maintenance"

    # Adjuvant study
    if treatment_setting == "adjuvant":
        return "adjuvant"

    # Immuno-oncology
    if drug_class == "immunotherapy":
        return "immuno_oncology"

    # Targeted therapy
    if drug_class == "targeted":
        return "targeted_therapy"

    # Default to general oncology
    return "general_oncology"


# =============================================================================
# VALIDATION
# =============================================================================

def validate_operational_specs(specs: OperationalSpecifications) -> List[str]:
    """
    Validate operational specifications for completeness.

    Returns list of warnings/errors for incomplete extractions.
    """
    warnings = []

    # Check visit schedule
    if specs.visit_schedule and not specs.visit_schedule.visits:
        warnings.append("WARNING: No visit windows extracted from protocol")

    # Check populations
    if specs.populations:
        if not specs.populations.itt_definition:
            warnings.append("WARNING: ITT population definition not extracted")

        # Check PK population if PK endpoints exist
        if specs.populations.pk_population and specs.populations.pk_population.included:
            if not specs.populations.pk_population.definition:
                warnings.append("WARNING: PK population defined but criteria not extracted")

    # Check covariates
    if specs.covariates:
        if not specs.covariates.stratification_factors:
            warnings.append("WARNING: Stratification factors not extracted")
        elif not specs.covariates.stratification_factor_levels:
            warnings.append("WARNING: Stratification factor levels not extracted")

    # Check ICE framework
    if specs.ice_framework:
        if not specs.ice_framework.endpoint_ice_mapping:
            warnings.append("INFO: No endpoint-specific ICE handling extracted")

    # Check interim analysis
    if specs.interim_analysis and specs.interim_analysis.num_interim > 0:
        if not specs.interim_analysis.triggers:
            warnings.append("WARNING: Interim analysis count specified but triggers not extracted")

    return warnings
