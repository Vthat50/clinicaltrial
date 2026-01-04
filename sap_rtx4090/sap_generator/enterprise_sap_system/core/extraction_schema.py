#!/usr/bin/env python3
"""
Extraction Schema for Oncology SAP Generation
==============================================

COMPREHENSIVE SCHEMA based on:
- Gamble et al. 2017 (JAMA): 55-item SAP checklist
- ICH E9 / E9(R1): Statistical principles and estimand framework
- FDA Oncology Guidance: Endpoint definitions
- CDISC ADaM: Data structure standards

CRITICAL FIELDS ADDED (2025-01 refactor):
- treatment_setting: neoadjuvant, adjuvant, first-line, etc.
- disease_type, tumor_type, histology: specific disease details
- stratification_factor_levels: actual values, not just names
- estimand fields (ICH E9 R1): 5 required attributes
- alpha_per_hypothesis: explicit alpha allocation per endpoint
- interim_by_endpoint: per-endpoint IA structure

All method choices come from EXTRACTION, not inference.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class TreatmentSetting(Enum):
    """Treatment setting classification."""
    FIRST_LINE = "first-line"
    SECOND_LINE = "second-line"
    THIRD_LINE_PLUS = "third-line or later"
    NEOADJUVANT = "neoadjuvant"
    ADJUVANT = "adjuvant"
    MAINTENANCE = "maintenance"
    SALVAGE = "salvage"
    UNKNOWN = "unknown"


class TrialDesignType(Enum):
    """Trial design types."""
    PARALLEL = "parallel"
    CROSSOVER = "crossover"
    FACTORIAL = "factorial"
    SINGLE_ARM = "single_arm"


class HypothesisFramework(Enum):
    """Hypothesis testing framework."""
    SUPERIORITY = "superiority"
    NON_INFERIORITY = "non_inferiority"
    EQUIVALENCE = "equivalence"


class OncologyEndpointType(Enum):
    """Standard FDA oncology endpoints."""
    OS = "Overall Survival"
    PFS = "Progression-Free Survival"
    ORR = "Objective Response Rate"
    DOR = "Duration of Response"
    DCR = "Disease Control Rate"
    TTP = "Time to Progression"
    DFS = "Disease-Free Survival"
    EFS = "Event-Free Survival"
    TTF = "Time to Treatment Failure"
    PCR = "Pathologic Complete Response"


class ICEStrategy(Enum):
    """Intercurrent event handling strategies (ICH E9 R1)."""
    TREATMENT_POLICY = "treatment_policy"
    COMPOSITE = "composite"
    HYPOTHETICAL = "hypothetical"
    PRINCIPAL_STRATUM = "principal_stratum"
    WHILE_ON_TREATMENT = "while_on_treatment"


# =============================================================================
# SECTION 1: ADMINISTRATIVE (Gamble Items 1-6)
# =============================================================================

@dataclass
class AdministrativeInfo:
    """Administrative information from Gamble et al. Section 1."""
    nct_id: str = ""                              # Trial registration number
    protocol_number: Optional[str] = None         # Protocol version reference
    protocol_title: Optional[str] = None          # Full protocol title
    sponsor: Optional[str] = None                 # Sponsor organization
    sap_version: Optional[str] = None             # SAP version if exists
    sap_date: Optional[str] = None                # SAP finalization date


# =============================================================================
# SECTION 2: STUDY DESIGN (Gamble Items 7-15 + FDA Oncology)
# =============================================================================

@dataclass
class StudyDesign:
    """Study design from Gamble et al. Section 3 + FDA Oncology Guidance."""
    # Item 9: Trial design (NO DEFAULTS - must be extracted)
    design_type: str = ""                         # parallel, crossover, factorial, single_arm
    phase: str = ""                               # 1, 2, 3, 4
    is_randomized: Optional[bool] = None          # None if not extracted
    is_blinded: Optional[bool] = None             # None if not extracted
    blinding_type: str = ""                       # double-blind, open-label, etc.

    # Treatment arms
    drug_name: str = ""
    drug_class: Optional[str] = None              # immunotherapy, chemotherapy, targeted
    comparator: str = ""
    comparator_type: str = ""                     # active, placebo, SOC

    # Item 10: Randomization (NO DEFAULTS)
    allocation_ratio: str = ""                    # MUST be extracted: "1:1", "2:1", etc.
    stratification_factors: List[str] = field(default_factory=list)

    # Item 11: Sample size
    sample_size: int = 0
    sample_size_per_arm: Optional[List[int]] = None
    sample_size_rationale: Optional[str] = None

    # Item 12: Framework (NO DEFAULTS)
    hypothesis_framework: str = ""                # superiority, non_inferiority, equivalence

    # ==========================================================================
    # NEW FIELDS (2025-01 refactor) - CRITICAL FOR ACCURACY
    # ==========================================================================

    # Treatment setting (was missing - caused neoadjuvant vs first-line errors)
    treatment_setting: str = ""                   # CRITICAL: first-line, neoadjuvant, adjuvant, etc.

    # Disease-specific fields (was missing - caused generic disease errors)
    disease_type: str = ""                        # e.g., "Non-small cell lung cancer (NSCLC)"
    tumor_type: str = ""                          # e.g., "Lung cancer"
    histology: str = ""                           # e.g., "Squamous", "Non-squamous", "Adenocarcinoma"
    disease_stage: str = ""                       # e.g., "Stage IIIB-IV", "Locally advanced or metastatic"
    biomarker_status: str = ""                    # e.g., "PD-L1 ≥50%", "EGFR mutation negative"

    # Stratification factor LEVELS (not just names)
    # e.g., {"PD-L1": ["<1%", "1-49%", "≥50%"], "ECOG": ["0", "1"]}
    stratification_factor_levels: Dict[str, List[str]] = field(default_factory=dict)


# =============================================================================
# SECTION 3: ESTIMAND FRAMEWORK (ICH E9 R1) - NEW SECTION
# =============================================================================

@dataclass
class Estimand:
    """
    ICH E9(R1) Estimand Framework - 5 required attributes.
    This section was entirely missing from the previous schema.
    """
    # Attribute 1: Population
    population: str = ""                          # e.g., "Adult patients with advanced NSCLC"

    # Attribute 2: Variable (endpoint)
    variable: str = ""                            # e.g., "Overall Survival"
    variable_definition: str = ""                 # e.g., "Time from randomization to death"

    # Attribute 3: Intercurrent events and strategies
    intercurrent_events: List[Dict[str, str]] = field(default_factory=list)
    # Each dict: {"event": "Treatment discontinuation", "strategy": "treatment_policy"}

    # Attribute 4: Population-level summary
    population_summary: str = ""                  # e.g., "Hazard ratio"

    # Pre-specified estimand for each endpoint
    primary_estimand: str = ""                    # Full estimand statement
    secondary_estimands: List[str] = field(default_factory=list)


# =============================================================================
# SECTION 4: ENDPOINTS (FDA Oncology Guidance + CDISC ADaM)
# =============================================================================

@dataclass
class Endpoint:
    """Endpoint definition from FDA Oncology Guidance + CDISC."""
    name: str = ""
    endpoint_type: str = ""                       # OS, PFS, ORR, DOR, etc.
    is_primary: bool = False
    definition: Optional[str] = None
    assessment_criteria: str = "RECIST 1.1"       # RECIST, irRECIST, mRECIST, Lugano
    assessment_method: str = "investigator"       # investigator, BICR, both
    assessment_schedule: Optional[str] = None
    timepoint: Optional[str] = None               # e.g., "Week 12", "Month 6"

    # For pathologic endpoints (neoadjuvant)
    pathologic_criteria: Optional[str] = None     # e.g., "Miller-Payne", "RCB"


@dataclass
class EndpointConfiguration:
    """Complete endpoint setup for the trial."""
    primary_endpoint: Optional[Endpoint] = None
    primary_endpoint_text: str = ""               # Simple text version
    secondary_endpoints: List[str] = field(default_factory=list)
    exploratory_endpoints: List[str] = field(default_factory=list)

    # Co-primary structure (was missing)
    is_co_primary: bool = False                   # Are there co-primary endpoints?
    co_primary_endpoints: List[str] = field(default_factory=list)
    co_primary_success_rule: str = ""             # e.g., "Both must be significant"


# =============================================================================
# SECTION 5: INTERIM ANALYSIS (ICH E9 + Lan-DeMets) - ENHANCED
# =============================================================================

@dataclass
class InterimAnalysisPerEndpoint:
    """Per-endpoint interim analysis structure (was missing)."""
    endpoint: str = ""                            # e.g., "PFS" or "OS"
    timing: str = ""                              # e.g., "60% information fraction"
    events_required: Optional[int] = None
    alpha_spent: Optional[float] = None
    boundary_type: str = ""                       # efficacy, futility, both


@dataclass
class InterimAnalysis:
    """
    Interim analysis specification from ICH E9 Section 4.5 + Gamble Items 13a-13c.
    ENHANCED with per-endpoint structure.
    """
    # Item 13a: Number and timing (NO DEFAULTS - must be extracted)
    has_interim_analysis: Optional[bool] = None   # None if not extracted
    num_interim_analyses: Optional[int] = None    # CRITICAL: must be extracted

    # Event counts - CRITICAL numerical fields
    interim_events: Optional[List[int]] = None    # Events at each interim look
    final_events: Optional[int] = None            # CRITICAL: 382 vs 639 bug

    # Information fractions
    information_fractions: Optional[List[float]] = None  # e.g., [0.5, 0.75, 1.0]

    # Item 13b: Alpha adjustment - CRITICAL numerical fields (NO DEFAULTS)
    alpha_spending_function: str = ""             # O'Brien-Fleming, Lan-DeMets, etc.
    overall_alpha: Optional[float] = None         # CRITICAL: must be extracted, NEVER default 0.05
    alpha_sidedness: str = ""                     # one-sided or two-sided - must be extracted
    alpha_at_interim: Optional[List[float]] = None  # CRITICAL: 0.020 vs 0.05 bug
    alpha_at_final: Optional[float] = None        # CRITICAL: 0.044 vs 0.05 bug

    # Item 13c: Stopping guidelines (NO DEFAULTS)
    efficacy_stopping: Optional[bool] = None      # None if not extracted
    futility_stopping: Optional[bool] = None      # None if not extracted
    futility_boundary_type: Optional[str] = None  # binding, non-binding
    stopping_boundaries: Optional[str] = None     # Description of boundaries

    # ==========================================================================
    # NEW: Per-endpoint IA structure (was missing - caused IA details errors)
    # ==========================================================================
    interim_by_endpoint: List[InterimAnalysisPerEndpoint] = field(default_factory=list)
    # e.g., [{"endpoint": "PFS", "timing": "60% IF", "alpha_spent": 0.005},
    #        {"endpoint": "OS", "timing": "70% IF", "alpha_spent": 0.015}]


# =============================================================================
# SECTION 6: STATISTICAL METHODS (Gamble Items 16-20, 27a-27f) - ENHANCED
# =============================================================================

@dataclass
class StatisticalMethods:
    """Statistical methods from Gamble Section 6 + FDA Oncology."""
    # Item 27a: Primary analysis
    primary_test: str = ""                        # e.g., "stratified log-rank"
    primary_test_details: Optional[str] = None    # e.g., "G(ρ=0, γ=1)" for F-H

    # Effect estimation
    hazard_ratio_method: str = "Cox regression"
    expected_hazard_ratio: Optional[float] = None
    confidence_interval_level: float = 0.95
    power: Optional[float] = None                 # e.g., 0.90 for 90%

    # Item 27b: Covariates
    stratification_in_analysis: List[str] = field(default_factory=list)

    # Item 27d: Alternative methods (non-PH)
    proportional_hazards_check: str = "Schoenfeld residuals"
    non_ph_alternatives: List[str] = field(default_factory=list)

    # Item 27e: Sensitivity analyses
    sensitivity_analyses: List[str] = field(default_factory=list)

    # Item 27f: Subgroup analyses
    subgroup_analyses: List[str] = field(default_factory=list)

    # ==========================================================================
    # NEW: Explicit hypothesis statements (was missing)
    # ==========================================================================
    null_hypothesis: str = ""                     # e.g., "HR = 1.0"
    alternative_hypothesis: str = ""              # e.g., "HR < 1.0 (superiority)"
    test_sidedness: str = "one-sided"             # one-sided or two-sided


# =============================================================================
# SECTION 7: MULTIPLICITY (Gamble Item 17 + FDA) - ENHANCED
# =============================================================================

@dataclass
class MultiplicityAdjustment:
    """Multiplicity adjustment from Gamble Item 17 + FDA FWER requirements."""
    has_multiplicity: Optional[bool] = None       # None if not extracted
    adjustment_method: Optional[str] = None       # Hierarchical, Hochberg, Holm, Graphical
    testing_sequence: List[str] = field(default_factory=list)
    alpha_allocation: Optional[str] = None        # Text description

    # ==========================================================================
    # NEW: Explicit alpha per hypothesis (was missing - caused alpha errors)
    # ==========================================================================
    alpha_per_hypothesis: Dict[str, float] = field(default_factory=dict)
    # e.g., {"PFS": 0.0125, "OS": 0.0125, "ORR": 0.025}

    # For graphical approach (Maurer & Bretz)
    graphical_weights: Optional[Dict[str, float]] = None
    graphical_transitions: Optional[Dict[str, Dict[str, float]]] = None

    # ==========================================================================
    # NEW: Structured hypothesis list (H1-H5 with descriptions and alpha)
    # ==========================================================================
    hypotheses_list: List[Dict[str, Any]] = field(default_factory=list)
    # e.g., [
    #   {"id": "H1", "description": "PFS superiority pMMR", "alpha": 0.005, "endpoint": "PFS", "population": "pMMR"},
    #   {"id": "H2", "description": "PFS superiority all-comers", "alpha": 0.0, "endpoint": "PFS", "population": "all"},
    #   {"id": "H3", "description": "OS non-inferiority pMMR", "alpha": 0.020, "endpoint": "OS", "population": "pMMR"},
    # ]


# =============================================================================
# SECTION 8: MISSING DATA & CENSORING (Gamble Item 28 + ICH E9(R1)) - ENHANCED
# =============================================================================

@dataclass
class MissingDataHandling:
    """Missing data handling from ICH E9(R1) Estimand Framework + Gamble Item 28."""
    # Intercurrent events (ICH E9(R1)) - NO DEFAULTS
    treatment_discontinuation_strategy: str = ""  # Must be extracted
    subsequent_therapy_handling: str = ""         # Must be extracted

    # Censoring rules (FDA PFS guidance)
    censoring_rules: List[str] = field(default_factory=list)

    # Missing tumor assessments
    missing_assessment_handling: str = ""         # Must be extracted

    # Sensitivity for missing data
    sensitivity_methods: List[str] = field(default_factory=list)

    # ==========================================================================
    # NEW: Missing data assumptions and methods - NO DEFAULTS
    # ==========================================================================
    missing_at_random_assumption: Optional[bool] = None   # None if not extracted
    tipping_point_analysis: Optional[bool] = None         # None if not extracted
    pattern_mixture_models: Optional[bool] = None         # None if not extracted
    multiple_imputation: Optional[bool] = None            # None if not extracted


# =============================================================================
# SECTION 9: ANALYSIS POPULATIONS (Gamble Item 20) - ENHANCED
# =============================================================================

@dataclass
class AnalysisPopulations:
    """Analysis populations from Gamble Item 20."""
    itt_definition: str = "All randomized subjects"
    per_protocol_definition: Optional[str] = None
    safety_population_definition: str = "All subjects who received at least one dose"

    # ==========================================================================
    # NEW: FAS and additional populations (was missing)
    # ==========================================================================
    fas_definition: str = ""                      # Full Analysis Set (often = ITT)

    # Oncology-specific
    efficacy_evaluable_definition: Optional[str] = None
    biomarker_evaluable_definition: Optional[str] = None
    pk_population_definition: Optional[str] = None  # For PK analysis


# =============================================================================
# SECTION 10: CROSSOVER / TREATMENT SWITCHING
# =============================================================================

@dataclass
class CrossoverHandling:
    """Treatment switching/crossover handling."""
    has_crossover: Optional[bool] = None          # None if not extracted
    crossover_description: Optional[str] = None
    crossover_adjustment_methods: List[str] = field(default_factory=list)  # RPSFT, IPCW


# =============================================================================
# SECTION 11: SAFETY ANALYSES (ICH E2A, E6) - NEW
# =============================================================================

@dataclass
class SafetyAnalyses:
    """
    Safety analysis specifications from ICH E2A/E6 and FDA Safety Reporting Guidance.
    Source: ICH E2A Clinical Safety Data Management
    """
    # Safety population
    safety_population_definition: str = ""

    # Adverse Events
    ae_coding_dictionary: str = "MedDRA"          # MedDRA version
    ae_grading_scale: str = "CTCAE"               # NCI-CTCAE version
    ae_collection_period: str = ""                # e.g., "From first dose to 30 days after last dose"
    teae_definition: str = ""                     # Treatment-emergent AE definition

    # AE Summaries
    ae_summary_by_soc: Optional[bool] = None      # By System Organ Class
    ae_summary_by_pt: Optional[bool] = None       # By Preferred Term
    ae_summary_by_severity: Optional[bool] = None # By severity grade
    ae_summary_by_relationship: Optional[bool] = None  # By relationship to treatment

    # Serious AEs
    sae_definition: str = ""
    sae_reporting_period: str = ""

    # Deaths
    death_reporting: str = ""                     # How deaths are analyzed

    # AEs of Special Interest (AESI)
    aesi_list: List[str] = field(default_factory=list)  # e.g., ["Immune-related AEs", "Infusion reactions"]
    aesi_definitions: Dict[str, str] = field(default_factory=dict)

    # Immune-related AEs (for immunotherapy)
    irae_categories: List[str] = field(default_factory=list)  # e.g., ["Pneumonitis", "Colitis", "Hepatitis"]
    irae_management_algorithms: Optional[bool] = None

    # Dose modifications
    dose_reduction_rules: List[str] = field(default_factory=list)
    dose_delay_rules: List[str] = field(default_factory=list)
    dose_discontinuation_rules: List[str] = field(default_factory=list)


# =============================================================================
# SECTION 12: PHARMACOKINETIC ANALYSES - NEW
# =============================================================================

@dataclass
class PharmacokineticAnalyses:
    """
    PK analysis specifications.
    Source: FDA Population PK Guidance, ICH E4
    """
    # PK Population
    pk_population_definition: str = ""
    pk_evaluable_criteria: List[str] = field(default_factory=list)

    # PK Parameters
    pk_parameters: List[str] = field(default_factory=list)  # e.g., ["Cmax", "Tmax", "AUC0-inf", "t1/2"]
    pk_sampling_timepoints: List[str] = field(default_factory=list)

    # Analysis Methods
    pk_analysis_method: str = ""                  # Non-compartmental, Population PK
    population_pk_model: Optional[str] = None     # e.g., "Two-compartment with first-order absorption"
    pk_software: str = ""                         # e.g., "NONMEM", "Phoenix WinNonlin"

    # PK/PD
    exposure_response_analysis: Optional[bool] = None
    exposure_efficacy_relationship: Optional[str] = None
    exposure_safety_relationship: Optional[str] = None

    # Covariates
    pk_covariates: List[str] = field(default_factory=list)  # e.g., ["Weight", "Age", "Renal function"]


# =============================================================================
# SECTION 13: BIOMARKER ANALYSES - NEW
# =============================================================================

@dataclass
class BiomarkerAnalyses:
    """
    Biomarker and correlative analyses specifications.
    Source: FDA Biomarker Guidance, Companion Diagnostic Guidance
    """
    # Biomarker Types
    predictive_biomarkers: List[str] = field(default_factory=list)  # e.g., ["PD-L1", "TMB"]
    prognostic_biomarkers: List[str] = field(default_factory=list)
    pharmacodynamic_biomarkers: List[str] = field(default_factory=list)

    # PD-L1 Specific (common in IO trials)
    pdl1_assay: Optional[str] = None              # e.g., "22C3 pharmDx", "SP263"
    pdl1_cutoffs: List[str] = field(default_factory=list)  # e.g., ["<1%", "1-49%", "≥50%"]
    pdl1_scoring_method: Optional[str] = None     # e.g., "TPS", "CPS", "IC"

    # TMB
    tmb_assay: Optional[str] = None
    tmb_cutoff: Optional[str] = None              # e.g., "≥10 mut/Mb"

    # MSI/MMR
    msi_testing_method: Optional[str] = None      # e.g., "IHC", "PCR", "NGS"
    mmr_proteins_tested: List[str] = field(default_factory=list)  # e.g., ["MLH1", "MSH2", "MSH6", "PMS2"]

    # Genomic Analyses
    genomic_platform: Optional[str] = None        # e.g., "FoundationOne CDx", "MSK-IMPACT"
    genes_analyzed: List[str] = field(default_factory=list)
    ctdna_analysis: Optional[bool] = None         # Circulating tumor DNA

    # Companion Diagnostic
    companion_diagnostic_required: Optional[bool] = None
    companion_diagnostic_name: Optional[str] = None
    companion_diagnostic_fda_status: Optional[str] = None  # Approved, Pending


# =============================================================================
# SECTION 14: LABORATORY ANALYSES - NEW
# =============================================================================

@dataclass
class LaboratoryAnalyses:
    """
    Laboratory evaluation specifications.
    Source: ICH E3 Structure and Content of Clinical Study Reports
    """
    # Lab Parameters
    hematology_parameters: List[str] = field(default_factory=list)  # e.g., ["Hemoglobin", "WBC", "Platelets"]
    chemistry_parameters: List[str] = field(default_factory=list)   # e.g., ["ALT", "AST", "Bilirubin", "Creatinine"]
    urinalysis_parameters: List[str] = field(default_factory=list)

    # Analysis Methods
    shift_table_analysis: Optional[bool] = None   # Baseline to worst post-baseline
    ctcae_grading: Optional[bool] = None          # Grade by CTCAE

    # Notable Abnormalities
    clinically_notable_criteria: Dict[str, str] = field(default_factory=dict)
    # e.g., {"ALT": ">3x ULN", "Neutrophils": "<1000/mm3"}

    # Hy's Law
    hys_law_analysis: Optional[bool] = None       # For hepatotoxicity


# =============================================================================
# SECTION 15: EXPOSURE ANALYSES - NEW
# =============================================================================

@dataclass
class ExposureAnalyses:
    """
    Study drug exposure and accountability.
    Source: ICH E3, FDA Guidance
    """
    # Exposure Metrics
    exposure_metrics: List[str] = field(default_factory=list)
    # e.g., ["Duration of treatment", "Number of cycles", "Cumulative dose", "Relative dose intensity"]

    # Dose Modifications
    dose_delay_definition: str = ""
    dose_reduction_definition: str = ""
    dose_interruption_definition: str = ""

    # Relative Dose Intensity
    rdi_calculation_method: str = ""
    rdi_categories: List[str] = field(default_factory=list)  # e.g., ["<80%", "80-100%", ">100%"]


# =============================================================================
# SECTION 16: CONCOMITANT MEDICATIONS - NEW
# =============================================================================

@dataclass
class ConcomitantMedications:
    """
    Prior and concomitant medication analyses.
    Source: ICH E3
    """
    medication_coding: str = "WHO Drug Dictionary"
    prior_therapy_collection: Optional[bool] = None
    concomitant_therapy_collection: Optional[bool] = None

    # Categories of Interest
    prohibited_medications: List[str] = field(default_factory=list)
    medications_of_interest: List[str] = field(default_factory=list)  # e.g., ["Steroids", "Immunosuppressants"]

    # Prior Anticancer Therapy
    prior_lines_of_therapy: Optional[bool] = None
    prior_immunotherapy: Optional[bool] = None
    prior_targeted_therapy: Optional[bool] = None


# =============================================================================
# SECTION 17: IMMUNOGENICITY - NEW (for biologics/immunotherapy)
# =============================================================================

@dataclass
class Immunogenicity:
    """
    Immunogenicity analysis for therapeutic proteins.
    Source: FDA Immunogenicity Guidance (2019)
    """
    ada_testing_performed: Optional[bool] = None  # Anti-drug antibodies
    ada_assay_type: Optional[str] = None          # e.g., "Screening", "Confirmatory", "Titer"
    ada_sampling_timepoints: List[str] = field(default_factory=list)

    nab_testing_performed: Optional[bool] = None  # Neutralizing antibodies
    nab_assay_type: Optional[str] = None

    # Analysis
    ada_incidence_analysis: Optional[bool] = None
    ada_impact_on_efficacy: Optional[bool] = None
    ada_impact_on_safety: Optional[bool] = None
    ada_impact_on_pk: Optional[bool] = None


# =============================================================================
# SECTION 18: CONVENTIONS & DATE IMPUTATION - NEW
# =============================================================================

@dataclass
class Conventions:
    """
    Analysis conventions and date imputation rules.
    Source: CDISC ADaM, ICH E9
    """
    # Baseline Definition
    baseline_definition: str = ""                 # e.g., "Last non-missing value before first dose"
    baseline_window: str = ""                     # e.g., "Within 28 days of randomization"

    # Date Imputation
    partial_date_imputation_rules: Dict[str, str] = field(default_factory=dict)
    # e.g., {"AE start": "First of month", "AE end": "Last of month"}

    # Visit Windows
    visit_windows: Dict[str, str] = field(default_factory=dict)
    # e.g., {"Week 6": "Day 36-50", "Week 12": "Day 78-92"}

    # Analysis Windows
    on_treatment_definition: str = ""
    post_treatment_definition: str = ""

    # Rounding Rules
    rounding_convention: str = ""                 # e.g., "Round to 1 decimal place"


# =============================================================================
# SECTION 19: PROTOCOL DEVIATIONS - NEW
# =============================================================================

@dataclass
class ProtocolDeviations:
    """
    Protocol deviation handling.
    Source: ICH E6 (GCP), ICH E9
    """
    # Deviation Categories
    important_deviation_categories: List[str] = field(default_factory=list)
    # e.g., ["Eligibility violations", "Prohibited medication use", "Wrong treatment"]

    # Handling
    deviation_impact_on_populations: str = ""     # How deviations affect PP population
    deviation_documentation: str = ""


# =============================================================================
# SECTION 20: PATIENT-REPORTED OUTCOMES (PROs) - NEW
# =============================================================================

@dataclass
class PatientReportedOutcomes:
    """
    PRO analysis specifications.
    Source: FDA PRO Guidance (2009), FDA Oncology PRO Guidance, CDISC PRO standards
    """
    # PRO Instruments
    pro_instruments: List[str] = field(default_factory=list)
    # e.g., ["EORTC QLQ-C30", "EORTC QLQ-LC13", "EQ-5D-5L"]

    # Instrument Details
    instrument_scoring_rules: Dict[str, str] = field(default_factory=dict)
    # e.g., {"EORTC QLQ-C30": "Linear transformation 0-100", "EQ-5D-5L": "Index value -0.5 to 1.0"}

    # Endpoints
    pro_primary_endpoint: Optional[str] = None     # If PRO is primary endpoint
    pro_secondary_endpoints: List[str] = field(default_factory=list)
    pro_exploratory_endpoints: List[str] = field(default_factory=list)

    # Key PRO Analyses
    time_to_deterioration: Optional[bool] = None   # TTD analysis planned
    ttd_threshold: Optional[str] = None            # e.g., "≥10-point decrease from baseline"
    responder_definition: Optional[str] = None     # MID for responder analysis

    # Missing PRO Data
    pro_missing_data_handling: str = ""            # e.g., "MMRM", "Pattern mixture"
    pro_compliance_threshold: Optional[float] = None  # e.g., 0.80 for 80%

    # Multiplicity
    pro_multiplicity_handling: str = ""            # How PROs fit into testing hierarchy

    # Administration
    pro_collection_schedule: List[str] = field(default_factory=list)
    # e.g., ["Baseline", "Week 6", "Week 12", "End of Treatment"]
    pro_electronic_capture: Optional[bool] = None  # ePRO vs paper


# =============================================================================
# SECTION 21: DATA MONITORING COMMITTEE (DMC) - NEW
# =============================================================================

@dataclass
class DataMonitoringCommittee:
    """
    DMC and safety oversight specifications.
    Source: FDA DMC Guidance (2006), ICH E9, ICH E6
    """
    # DMC Structure
    has_dmc: Optional[bool] = None
    dmc_charter_exists: Optional[bool] = None
    dmc_membership: List[str] = field(default_factory=list)  # Roles, not names

    # Review Schedule
    dmc_review_frequency: str = ""                 # e.g., "Every 6 months", "After 50 events"
    dmc_unblinded: Optional[bool] = None           # DMC has access to unblinded data

    # Safety Stopping Rules
    safety_stopping_rules: List[str] = field(default_factory=list)
    safety_boundary_type: str = ""                 # e.g., "Pocock", "Custom"

    # Futility
    futility_review_planned: Optional[bool] = None
    futility_boundary: str = ""                    # e.g., "Conditional power <20%"

    # Interim Recommendations
    dmc_recommendation_options: List[str] = field(default_factory=list)
    # e.g., ["Continue", "Modify", "Stop for safety", "Stop for efficacy", "Stop for futility"]

    # Blinding
    sponsor_blinded: Optional[bool] = None         # Sponsor blind to interim results
    independent_statistician: Optional[bool] = None  # Unblinded stats separate from sponsor


# =============================================================================
# SECTION 22: CDISC DATA STANDARDS - NEW
# =============================================================================

@dataclass
class CDISCAlignment:
    """
    CDISC data standard alignment.
    Source: CDISC SDTM, ADaM, CDASH, Oncology Therapeutic Area Supplements
    """
    # SDTM Domains Used
    sdtm_version: str = ""                         # e.g., "SDTM-IG 3.3"
    sdtm_domains: List[str] = field(default_factory=list)
    # e.g., ["DM", "AE", "LB", "VS", "EX", "TU", "TR", "RS"]

    # ADaM Datasets
    adam_version: str = ""                         # e.g., "ADaM-IG 1.2"
    adam_datasets: List[str] = field(default_factory=list)
    # e.g., ["ADSL", "ADTTE", "ADRS", "ADAE", "ADLB"]

    # Oncology-Specific
    oncology_response_domains: List[str] = field(default_factory=list)
    # e.g., ["TU", "TR", "RS"] - Tumor identification, Tumor results, Response
    response_criteria: str = ""                    # e.g., "RECIST 1.1", "iRECIST"

    # Derived Variables
    key_derivations: Dict[str, str] = field(default_factory=dict)
    # e.g., {"AVAL": "Numeric analysis value", "CHG": "Change from baseline"}

    # Submission Readiness
    submission_standard: str = ""                  # e.g., "FDA", "PMDA", "EMA"
    define_xml_version: str = ""                   # e.g., "Define-XML 2.0"


# =============================================================================
# SECTION 23: SPECIAL DESIGNS - NEW
# =============================================================================

@dataclass
class SpecialDesigns:
    """
    Special trial design elements.
    Source: FDA Master Protocol Guidance, FDA Adaptive Design Guidance, ICH E9(R1)
    """
    # Master Protocol Elements
    is_master_protocol: Optional[bool] = None
    master_protocol_type: str = ""                 # basket, umbrella, platform

    # Basket Trial
    is_basket_trial: Optional[bool] = None
    basket_tumor_types: List[str] = field(default_factory=list)
    basket_shared_biomarker: str = ""              # e.g., "NTRK fusion", "MSI-H"

    # Umbrella Trial
    is_umbrella_trial: Optional[bool] = None
    umbrella_biomarker_arms: List[Dict[str, str]] = field(default_factory=list)
    # e.g., [{"biomarker": "EGFR", "treatment": "Erlotinib"}, ...]

    # Platform Trial
    is_platform_trial: Optional[bool] = None
    arms_can_be_added: Optional[bool] = None
    shared_control_arm: Optional[bool] = None

    # Adaptive Elements
    is_adaptive: Optional[bool] = None
    adaptive_features: List[str] = field(default_factory=list)
    # e.g., ["Sample size re-estimation", "Adaptive enrichment", "Response-adaptive randomization"]
    adaptation_timing: List[str] = field(default_factory=list)
    adaptation_rules: str = ""

    # Seamless Design
    is_seamless: Optional[bool] = None
    seamless_phases: str = ""                      # e.g., "Phase 2/3"
    phase2_to_phase3_criteria: str = ""            # Go/no-go criteria


# =============================================================================
# SECTION 24: TUMOR ASSESSMENT & IMAGING - NEW
# =============================================================================

@dataclass
class TumorAssessment:
    """
    Tumor assessment and imaging specifications.
    Source: RECIST 1.1, iRECIST, Lugano, RANO, FDA Oncology Endpoints
    """
    # Response Criteria
    response_criteria: str = ""                    # RECIST 1.1, iRECIST, Lugano, RANO
    response_criteria_version: str = ""

    # Imaging Schedule
    assessment_schedule: str = ""                  # e.g., "Every 6 weeks for 48 weeks, then Q12W"
    baseline_imaging_window: str = ""              # e.g., "Within 28 days of randomization"

    # Lesion Selection
    target_lesion_selection: str = ""              # Rules for selecting target lesions
    max_target_lesions: Optional[int] = None       # e.g., 5 total, 2 per organ
    min_lesion_size: Optional[str] = None          # e.g., "≥10mm longest diameter"

    # Adjudication
    assessment_method: str = ""                    # investigator, BICR, both
    bicr_primary: Optional[bool] = None            # BICR as primary for regulatory
    discrepancy_resolution: str = ""               # How investigator vs BICR discrepancies handled

    # Confirmation
    confirmation_required: Optional[bool] = None   # CR/PR confirmation scan required
    confirmation_window: str = ""                  # e.g., "≥4 weeks after initial response"

    # Special Considerations
    pseudoprogression_handling: str = ""           # For immunotherapy trials
    new_lesion_confirmation: Optional[bool] = None # iRECIST iUPD → ICPD

    # Progression Date
    progression_date_definition: str = ""          # Date of first documented PD


# =============================================================================
# SECTION 25: EXTRACTION CONFIDENCE
# =============================================================================

@dataclass
class ExtractionConfidence:
    """
    Per-field confidence scores for extraction.
    Enables section-by-section extraction with quality tracking.
    """
    overall_confidence: float = 0.0               # 0-1 overall extraction quality

    # Per-section confidence
    section_confidence: Dict[str, float] = field(default_factory=dict)
    # e.g., {"study_design": 0.95, "interim_analysis": 0.80, "multiplicity": 0.60}

    # Fields that need review
    needs_review: List[str] = field(default_factory=list)
    # e.g., ["alpha_per_hypothesis", "interim_events"]

    # Fields not found in protocol
    not_found: List[str] = field(default_factory=list)

    # Extraction notes
    notes: List[str] = field(default_factory=list)


# =============================================================================
# MASTER SCHEMA - COMPLETE EXTRACTION
# =============================================================================

@dataclass
class ExtractedProtocolFacts:
    """
    Complete schema combining all authoritative sources.
    This is the SINGLE SOURCE OF TRUTH for generation.

    If a field is not extracted, it should be None (not defaulted).
    Generation should only use values that were actually extracted.

    CRITICAL: All fields defined here should be passed through the pipeline.
    """
    # Administrative
    admin: AdministrativeInfo = field(default_factory=AdministrativeInfo)

    # Design (ENHANCED with treatment_setting, disease details)
    design: StudyDesign = field(default_factory=StudyDesign)

    # Estimand (NEW - ICH E9 R1)
    estimand: Estimand = field(default_factory=Estimand)

    # Endpoints (ENHANCED with co-primary structure)
    endpoints: EndpointConfiguration = field(default_factory=EndpointConfiguration)

    # Interim Analysis (ENHANCED with per-endpoint structure)
    interim: InterimAnalysis = field(default_factory=InterimAnalysis)

    # Statistical Methods (ENHANCED with hypothesis statements)
    methods: StatisticalMethods = field(default_factory=StatisticalMethods)

    # Multiplicity (ENHANCED with alpha_per_hypothesis)
    multiplicity: MultiplicityAdjustment = field(default_factory=MultiplicityAdjustment)

    # Missing Data (ENHANCED with sensitivity methods)
    missing_data: MissingDataHandling = field(default_factory=MissingDataHandling)

    # Populations (ENHANCED with FAS)
    populations: AnalysisPopulations = field(default_factory=AnalysisPopulations)

    # Crossover
    crossover: CrossoverHandling = field(default_factory=CrossoverHandling)

    # =========================================================================
    # NEW SECTIONS (2025-01) - Based on comprehensive regulatory sources
    # =========================================================================

    # Safety (ICH E2A, E2B, E6, FDA Safety Guidance)
    safety: SafetyAnalyses = field(default_factory=SafetyAnalyses)

    # Pharmacokinetics (FDA Population PK Guidance, ICH E4, M10)
    pharmacokinetics: PharmacokineticAnalyses = field(default_factory=PharmacokineticAnalyses)

    # Biomarkers (FDA Biomarker/CDx Guidance, FDA-NIH BEST)
    biomarkers: BiomarkerAnalyses = field(default_factory=BiomarkerAnalyses)

    # Laboratory (ICH E3, CTCAE)
    laboratory: LaboratoryAnalyses = field(default_factory=LaboratoryAnalyses)

    # Exposure (ICH E3)
    exposure: ExposureAnalyses = field(default_factory=ExposureAnalyses)

    # Concomitant Medications (ICH E3)
    concomitant_meds: ConcomitantMedications = field(default_factory=ConcomitantMedications)

    # Immunogenicity (FDA Immunogenicity Guidance)
    immunogenicity: Immunogenicity = field(default_factory=Immunogenicity)

    # Conventions (CDISC ADaM, ICH E9)
    conventions: Conventions = field(default_factory=Conventions)

    # Protocol Deviations (ICH E6, E9)
    deviations: ProtocolDeviations = field(default_factory=ProtocolDeviations)

    # Patient-Reported Outcomes (FDA PRO Guidance)
    pro: PatientReportedOutcomes = field(default_factory=PatientReportedOutcomes)

    # Data Monitoring Committee (FDA DMC Guidance)
    dmc: DataMonitoringCommittee = field(default_factory=DataMonitoringCommittee)

    # CDISC Standards (SDTM, ADaM, CDASH)
    cdisc: CDISCAlignment = field(default_factory=CDISCAlignment)

    # Special Designs (FDA Adaptive/Master Protocol Guidance)
    special_design: SpecialDesigns = field(default_factory=SpecialDesigns)

    # Tumor Assessment (RECIST, iRECIST, FDA Oncology)
    tumor_assessment: TumorAssessment = field(default_factory=TumorAssessment)

    # Extraction Confidence
    confidence: ExtractionConfidence = field(default_factory=ExtractionConfidence)

    def get_critical_numerical_fields(self) -> Dict[str, Any]:
        """
        Returns all numerical fields that MUST match the protocol exactly.
        """
        return {
            # Sample size
            'sample_size': self.design.sample_size,

            # Event counts - CRITICAL
            'final_events': self.interim.final_events,
            'interim_events': self.interim.interim_events,

            # Interim structure
            'num_interim_analyses': self.interim.num_interim_analyses,
            'information_fractions': self.interim.information_fractions,

            # Alpha values - CRITICAL
            'overall_alpha': self.interim.overall_alpha,
            'alpha_at_interim': self.interim.alpha_at_interim,
            'alpha_at_final': self.interim.alpha_at_final,
            'alpha_per_hypothesis': self.multiplicity.alpha_per_hypothesis,

            # Effect size
            'expected_hazard_ratio': self.methods.expected_hazard_ratio,
            'power': self.methods.power,
        }

    def validate_completeness(self) -> List[str]:
        """Check which critical fields are missing."""
        missing = []
        critical = self.get_critical_numerical_fields()
        for field_name, value in critical.items():
            if value is None or value == 0 or value == [] or value == {}:
                missing.append(field_name)
        return missing

    def to_flat_dict(self) -> Dict[str, Any]:
        """
        Convert to flat dictionary for prompt formatting.
        This is what gets passed to _format_facts().
        """
        return {
            # Administrative
            'nct_id': self.admin.nct_id,
            'protocol_number': self.admin.protocol_number,
            'sponsor': self.admin.sponsor,

            # Design - CORE
            'drug_name': self.design.drug_name,
            'comparator': self.design.comparator,
            'indication': self.design.drug_class,
            'phase': self.design.phase,
            'sample_size': self.design.sample_size,
            'allocation_ratio': self.design.allocation_ratio,
            'stratification_factors': self.design.stratification_factors,
            'design_type': self.design.design_type,

            # Design - NEW CRITICAL FIELDS
            'treatment_setting': self.design.treatment_setting,
            'disease_type': self.design.disease_type,
            'tumor_type': self.design.tumor_type,
            'histology': self.design.histology,
            'disease_stage': self.design.disease_stage,
            'biomarker_status': self.design.biomarker_status,
            'stratification_factor_levels': self.design.stratification_factor_levels,

            # Estimand (ICH E9 R1) - NEW
            'estimand_population': self.estimand.population,
            'estimand_variable': self.estimand.variable,
            'intercurrent_events': self.estimand.intercurrent_events,
            'primary_estimand': self.estimand.primary_estimand,

            # Endpoints
            'primary_endpoint': self.endpoints.primary_endpoint_text,
            'secondary_endpoints': self.endpoints.secondary_endpoints,
            'is_co_primary': self.endpoints.is_co_primary,
            'co_primary_endpoints': self.endpoints.co_primary_endpoints,

            # Interim Analysis - CRITICAL NUMERICAL FIELDS
            'has_interim_analysis': self.interim.has_interim_analysis,
            'num_interim_analyses': self.interim.num_interim_analyses,
            'interim_events': self.interim.interim_events,
            'final_events': self.interim.final_events,
            'information_fractions': self.interim.information_fractions,
            'alpha_spending_function': self.interim.alpha_spending_function,
            'overall_alpha': self.interim.overall_alpha,
            'alpha_sidedness': self.interim.alpha_sidedness,
            'alpha_at_interim': self.interim.alpha_at_interim,
            'alpha_at_final': self.interim.alpha_at_final,
            'stopping_boundaries': self.interim.stopping_boundaries,
            'interim_by_endpoint': [
                {'endpoint': ia.endpoint, 'timing': ia.timing, 'events': ia.events_required, 'alpha': ia.alpha_spent}
                for ia in self.interim.interim_by_endpoint
            ],

            # Methods
            'primary_test': self.methods.primary_test,
            'statistical_method': self.methods.primary_test,  # Alias
            'expected_hazard_ratio': self.methods.expected_hazard_ratio,
            'power': self.methods.power,
            'sensitivity_analyses': self.methods.sensitivity_analyses,
            'subgroup_analyses': self.methods.subgroup_analyses,
            'null_hypothesis': self.methods.null_hypothesis,
            'alternative_hypothesis': self.methods.alternative_hypothesis,

            # Multiplicity - ENHANCED
            'multiplicity_method': self.multiplicity.adjustment_method,
            'testing_sequence': self.multiplicity.testing_sequence,
            'alpha_per_hypothesis': self.multiplicity.alpha_per_hypothesis,
            'hypotheses_list': self.multiplicity.hypotheses_list,
            'graphical_weights': self.multiplicity.graphical_weights,
            'graphical_transitions': self.multiplicity.graphical_transitions,

            # Missing Data
            'treatment_discontinuation_strategy': self.missing_data.treatment_discontinuation_strategy,
            'censoring_rules': self.missing_data.censoring_rules,
            'tipping_point_analysis': self.missing_data.tipping_point_analysis,

            # Crossover
            'has_crossover': self.crossover.has_crossover,
            'crossover_adjustment_methods': self.crossover.crossover_adjustment_methods,

            # Populations
            'itt_definition': self.populations.itt_definition,
            'fas_definition': self.populations.fas_definition,
            'safety_definition': self.populations.safety_population_definition,

            # =========================================================================
            # NEW SECTIONS (2025-01)
            # =========================================================================

            # Safety (ICH E2A, E6, FDA)
            'ae_coding_dictionary': self.safety.ae_coding_dictionary,
            'ae_grading_scale': self.safety.ae_grading_scale,
            'ae_collection_period': self.safety.ae_collection_period,
            'teae_definition': self.safety.teae_definition,
            'sae_definition': self.safety.sae_definition,
            'aesi_list': self.safety.aesi_list,
            'irae_categories': self.safety.irae_categories,
            'dose_reduction_rules': self.safety.dose_reduction_rules,
            'dose_discontinuation_rules': self.safety.dose_discontinuation_rules,

            # Pharmacokinetics (FDA Population PK)
            'pk_population_definition': self.pharmacokinetics.pk_population_definition,
            'pk_parameters': self.pharmacokinetics.pk_parameters,
            'pk_sampling_timepoints': self.pharmacokinetics.pk_sampling_timepoints,
            'pk_analysis_method': self.pharmacokinetics.pk_analysis_method,
            'exposure_response_analysis': self.pharmacokinetics.exposure_response_analysis,
            'pk_covariates': self.pharmacokinetics.pk_covariates,

            # Biomarkers (FDA CDx Guidance)
            'predictive_biomarkers': self.biomarkers.predictive_biomarkers,
            'prognostic_biomarkers': self.biomarkers.prognostic_biomarkers,
            'pdl1_assay': self.biomarkers.pdl1_assay,
            'pdl1_cutoffs': self.biomarkers.pdl1_cutoffs,
            'pdl1_scoring_method': self.biomarkers.pdl1_scoring_method,
            'tmb_assay': self.biomarkers.tmb_assay,
            'tmb_cutoff': self.biomarkers.tmb_cutoff,
            'msi_testing_method': self.biomarkers.msi_testing_method,
            'companion_diagnostic_required': self.biomarkers.companion_diagnostic_required,
            'companion_diagnostic_name': self.biomarkers.companion_diagnostic_name,

            # Laboratory (ICH E3, CTCAE)
            'hematology_parameters': self.laboratory.hematology_parameters,
            'chemistry_parameters': self.laboratory.chemistry_parameters,
            'shift_table_analysis': self.laboratory.shift_table_analysis,
            'hys_law_analysis': self.laboratory.hys_law_analysis,
            'clinically_notable_criteria': self.laboratory.clinically_notable_criteria,

            # Exposure
            'exposure_metrics': self.exposure.exposure_metrics,
            'rdi_calculation_method': self.exposure.rdi_calculation_method,
            'rdi_categories': self.exposure.rdi_categories,

            # Concomitant Medications
            'medication_coding': self.concomitant_meds.medication_coding,
            'prohibited_medications': self.concomitant_meds.prohibited_medications,
            'medications_of_interest': self.concomitant_meds.medications_of_interest,

            # Immunogenicity (FDA Immunogenicity Guidance)
            'ada_testing_performed': self.immunogenicity.ada_testing_performed,
            'ada_assay_type': self.immunogenicity.ada_assay_type,
            'ada_sampling_timepoints': self.immunogenicity.ada_sampling_timepoints,
            'nab_testing_performed': self.immunogenicity.nab_testing_performed,
            'ada_impact_on_efficacy': self.immunogenicity.ada_impact_on_efficacy,
            'ada_impact_on_safety': self.immunogenicity.ada_impact_on_safety,

            # Conventions (CDISC ADaM)
            'baseline_definition': self.conventions.baseline_definition,
            'baseline_window': self.conventions.baseline_window,
            'partial_date_imputation_rules': self.conventions.partial_date_imputation_rules,
            'visit_windows': self.conventions.visit_windows,
            'on_treatment_definition': self.conventions.on_treatment_definition,

            # Protocol Deviations (ICH E6)
            'important_deviation_categories': self.deviations.important_deviation_categories,
            'deviation_impact_on_populations': self.deviations.deviation_impact_on_populations,

            # PRO (FDA PRO Guidance)
            'pro_instruments': self.pro.pro_instruments,
            'pro_primary_endpoint': self.pro.pro_primary_endpoint,
            'pro_secondary_endpoints': self.pro.pro_secondary_endpoints,
            'time_to_deterioration': self.pro.time_to_deterioration,
            'ttd_threshold': self.pro.ttd_threshold,
            'pro_missing_data_handling': self.pro.pro_missing_data_handling,
            'pro_collection_schedule': self.pro.pro_collection_schedule,

            # DMC (FDA DMC Guidance)
            'has_dmc': self.dmc.has_dmc,
            'dmc_review_frequency': self.dmc.dmc_review_frequency,
            'dmc_unblinded': self.dmc.dmc_unblinded,
            'safety_stopping_rules': self.dmc.safety_stopping_rules,
            'futility_review_planned': self.dmc.futility_review_planned,
            'futility_boundary': self.dmc.futility_boundary,
            'dmc_recommendation_options': self.dmc.dmc_recommendation_options,

            # CDISC Standards
            'sdtm_version': self.cdisc.sdtm_version,
            'sdtm_domains': self.cdisc.sdtm_domains,
            'adam_version': self.cdisc.adam_version,
            'adam_datasets': self.cdisc.adam_datasets,
            'oncology_response_domains': self.cdisc.oncology_response_domains,
            'cdisc_response_criteria': self.cdisc.response_criteria,

            # Special Designs (FDA Adaptive/Master Protocol)
            'is_master_protocol': self.special_design.is_master_protocol,
            'master_protocol_type': self.special_design.master_protocol_type,
            'is_basket_trial': self.special_design.is_basket_trial,
            'is_umbrella_trial': self.special_design.is_umbrella_trial,
            'is_adaptive': self.special_design.is_adaptive,
            'adaptive_features': self.special_design.adaptive_features,
            'is_seamless': self.special_design.is_seamless,
            'seamless_phases': self.special_design.seamless_phases,

            # Tumor Assessment (RECIST, iRECIST)
            'response_criteria': self.tumor_assessment.response_criteria,
            'assessment_schedule': self.tumor_assessment.assessment_schedule,
            'assessment_method': self.tumor_assessment.assessment_method,
            'bicr_primary': self.tumor_assessment.bicr_primary,
            'confirmation_required': self.tumor_assessment.confirmation_required,
            'confirmation_window': self.tumor_assessment.confirmation_window,
            'pseudoprogression_handling': self.tumor_assessment.pseudoprogression_handling,
            'progression_date_definition': self.tumor_assessment.progression_date_definition,

            # Confidence
            'extraction_confidence': self.confidence.overall_confidence,
            'needs_review': self.confidence.needs_review,
        }


# =============================================================================
# CONVERSION FUNCTIONS
# =============================================================================

def from_claude_extraction(extracted: Dict[str, Any]) -> ExtractedProtocolFacts:
    """
    Convert Claude LLM extraction output to structured schema.

    This function ensures all extracted fields are properly mapped
    to the schema, fixing the "fields not passed through" bug.
    """
    facts = ExtractedProtocolFacts()

    # Administrative
    facts.admin.nct_id = extracted.get('nct_id', '')
    facts.admin.protocol_title = extracted.get('protocol_title', '')
    facts.admin.sponsor = extracted.get('sponsor', '')

    # Design - CORE
    facts.design.drug_name = extracted.get('drug_name', '')
    facts.design.comparator = extracted.get('comparator', '')
    facts.design.phase = extracted.get('phase', '')
    facts.design.sample_size = extracted.get('sample_size', 0)
    facts.design.allocation_ratio = extracted.get('allocation_ratio') or extracted.get('randomization_ratio') or ''
    facts.design.stratification_factors = extracted.get('stratification_factors', [])
    facts.design.design_type = extracted.get('design_type', '')
    facts.design.is_randomized = extracted.get('is_randomized')  # None if not found

    # Design - NEW CRITICAL FIELDS
    facts.design.treatment_setting = extracted.get('treatment_setting', '')
    facts.design.disease_type = extracted.get('disease_type', '') or extracted.get('indication', '')
    facts.design.tumor_type = extracted.get('tumor_type', '')
    facts.design.histology = extracted.get('histology', '')
    facts.design.disease_stage = extracted.get('disease_stage', '')
    facts.design.biomarker_status = extracted.get('biomarker_status', '')
    facts.design.stratification_factor_levels = extracted.get('stratification_factor_levels', {})

    # Estimand (ICH E9 R1) - NEW
    facts.estimand.population = extracted.get('estimand_population', '')
    facts.estimand.variable = extracted.get('estimand_variable', '')
    facts.estimand.intercurrent_events = extracted.get('intercurrent_events', [])
    facts.estimand.primary_estimand = extracted.get('primary_estimand', '')

    # Endpoints
    facts.endpoints.primary_endpoint_text = extracted.get('primary_endpoint', '')
    facts.endpoints.secondary_endpoints = extracted.get('secondary_endpoints', [])
    facts.endpoints.is_co_primary = extracted.get('is_co_primary')  # None if not found
    facts.endpoints.co_primary_endpoints = extracted.get('co_primary_endpoints', [])

    # Interim Analysis - CRITICAL (NO DEFAULTS - must be extracted)
    facts.interim.has_interim_analysis = extracted.get('has_interim_analysis')  # None if not found
    facts.interim.num_interim_analyses = extracted.get('num_interim_analyses')  # None if not found
    facts.interim.interim_events = extracted.get('interim_events', [])
    facts.interim.final_events = extracted.get('final_events') or extracted.get('final_analysis_events')
    facts.interim.information_fractions = extracted.get('interim_information_fraction', [])
    facts.interim.alpha_spending_function = extracted.get('error_spending_function', '') or extracted.get('alpha_spending_function', '')
    facts.interim.overall_alpha = extracted.get('alpha_level') or extracted.get('overall_alpha')  # None if not found - NEVER default 0.05
    facts.interim.alpha_at_interim = extracted.get('interim_alpha_spent', []) or extracted.get('alpha_at_interim', [])
    facts.interim.alpha_at_final = extracted.get('alpha_at_final')
    facts.interim.stopping_boundaries = extracted.get('stopping_boundaries', '')

    # Per-endpoint IA - NEW
    interim_by_ep = extracted.get('interim_by_endpoint', [])
    for ia in interim_by_ep:
        facts.interim.interim_by_endpoint.append(InterimAnalysisPerEndpoint(
            endpoint=ia.get('endpoint', ''),
            timing=ia.get('timing', ''),
            events_required=ia.get('events'),
            alpha_spent=ia.get('alpha')
        ))

    # Methods
    facts.methods.primary_test = extracted.get('statistical_method', '') or extracted.get('primary_test', '')
    facts.methods.expected_hazard_ratio = extracted.get('hazard_ratio')
    facts.methods.power = extracted.get('power')
    facts.methods.sensitivity_analyses = extracted.get('sensitivity_methods', [])
    facts.methods.null_hypothesis = extracted.get('null_hypothesis', '')
    facts.methods.alternative_hypothesis = extracted.get('alternative_hypothesis', '')

    # Multiplicity - ENHANCED
    facts.multiplicity.adjustment_method = extracted.get('multiplicity_method', '')
    facts.multiplicity.testing_sequence = extracted.get('testing_sequence', [])
    facts.multiplicity.alpha_per_hypothesis = extracted.get('alpha_per_hypothesis', {})
    facts.multiplicity.hypotheses_list = extracted.get('hypotheses_list', [])
    facts.multiplicity.graphical_weights = extracted.get('graphical_weights', None)
    facts.multiplicity.graphical_transitions = extracted.get('graphical_transitions', None)

    # Missing Data
    facts.missing_data.tipping_point_analysis = extracted.get('tipping_point_analysis')  # None if not found
    facts.missing_data.censoring_rules = extracted.get('censoring_rules', [])

    # Crossover
    facts.crossover.has_crossover = extracted.get('crossover_permitted') or extracted.get('has_crossover')  # None if not found
    facts.crossover.crossover_adjustment_methods = extracted.get('crossover_adjustment_methods', [])

    # Populations
    facts.populations.fas_definition = extracted.get('fas_definition', '')

    # =========================================================================
    # NEW SECTIONS (2025-01)
    # =========================================================================

    # Safety (ICH E2A, E6)
    facts.safety.ae_coding_dictionary = extracted.get('ae_coding_dictionary', 'MedDRA')
    facts.safety.ae_grading_scale = extracted.get('ae_grading_scale', 'CTCAE')
    facts.safety.ae_collection_period = extracted.get('ae_collection_period', '')
    facts.safety.teae_definition = extracted.get('teae_definition', '')
    facts.safety.sae_definition = extracted.get('sae_definition', '')
    facts.safety.sae_reporting_period = extracted.get('sae_reporting_period', '')
    facts.safety.aesi_list = extracted.get('aesi_list', [])
    facts.safety.aesi_definitions = extracted.get('aesi_definitions', {})
    facts.safety.irae_categories = extracted.get('irae_categories', [])
    facts.safety.dose_reduction_rules = extracted.get('dose_reduction_rules', [])
    facts.safety.dose_delay_rules = extracted.get('dose_delay_rules', [])
    facts.safety.dose_discontinuation_rules = extracted.get('dose_discontinuation_rules', [])

    # Pharmacokinetics
    facts.pharmacokinetics.pk_population_definition = extracted.get('pk_population_definition', '')
    facts.pharmacokinetics.pk_evaluable_criteria = extracted.get('pk_evaluable_criteria', [])
    facts.pharmacokinetics.pk_parameters = extracted.get('pk_parameters', [])
    facts.pharmacokinetics.pk_sampling_timepoints = extracted.get('pk_sampling_timepoints', [])
    facts.pharmacokinetics.pk_analysis_method = extracted.get('pk_analysis_method', '')
    facts.pharmacokinetics.population_pk_model = extracted.get('population_pk_model')
    facts.pharmacokinetics.pk_software = extracted.get('pk_software', '')
    facts.pharmacokinetics.exposure_response_analysis = extracted.get('exposure_response_analysis')
    facts.pharmacokinetics.pk_covariates = extracted.get('pk_covariates', [])

    # Biomarkers
    facts.biomarkers.predictive_biomarkers = extracted.get('predictive_biomarkers', [])
    facts.biomarkers.prognostic_biomarkers = extracted.get('prognostic_biomarkers', [])
    facts.biomarkers.pharmacodynamic_biomarkers = extracted.get('pharmacodynamic_biomarkers', [])
    facts.biomarkers.pdl1_assay = extracted.get('pdl1_assay')
    facts.biomarkers.pdl1_cutoffs = extracted.get('pdl1_cutoffs', [])
    facts.biomarkers.pdl1_scoring_method = extracted.get('pdl1_scoring_method')
    facts.biomarkers.tmb_assay = extracted.get('tmb_assay')
    facts.biomarkers.tmb_cutoff = extracted.get('tmb_cutoff')
    facts.biomarkers.msi_testing_method = extracted.get('msi_testing_method')
    facts.biomarkers.mmr_proteins_tested = extracted.get('mmr_proteins_tested', [])
    facts.biomarkers.genomic_platform = extracted.get('genomic_platform')
    facts.biomarkers.ctdna_analysis = extracted.get('ctdna_analysis')
    facts.biomarkers.companion_diagnostic_required = extracted.get('companion_diagnostic_required')
    facts.biomarkers.companion_diagnostic_name = extracted.get('companion_diagnostic_name')

    # Laboratory
    facts.laboratory.hematology_parameters = extracted.get('hematology_parameters', [])
    facts.laboratory.chemistry_parameters = extracted.get('chemistry_parameters', [])
    facts.laboratory.urinalysis_parameters = extracted.get('urinalysis_parameters', [])
    facts.laboratory.shift_table_analysis = extracted.get('shift_table_analysis')
    facts.laboratory.ctcae_grading = extracted.get('lab_ctcae_grading')
    facts.laboratory.clinically_notable_criteria = extracted.get('clinically_notable_criteria', {})
    facts.laboratory.hys_law_analysis = extracted.get('hys_law_analysis')

    # Exposure
    facts.exposure.exposure_metrics = extracted.get('exposure_metrics', [])
    facts.exposure.dose_delay_definition = extracted.get('dose_delay_definition', '')
    facts.exposure.dose_reduction_definition = extracted.get('dose_reduction_definition', '')
    facts.exposure.rdi_calculation_method = extracted.get('rdi_calculation_method', '')
    facts.exposure.rdi_categories = extracted.get('rdi_categories', [])

    # Concomitant Medications
    facts.concomitant_meds.medication_coding = extracted.get('medication_coding', 'WHO Drug Dictionary')
    facts.concomitant_meds.prohibited_medications = extracted.get('prohibited_medications', [])
    facts.concomitant_meds.medications_of_interest = extracted.get('medications_of_interest', [])
    facts.concomitant_meds.prior_lines_of_therapy = extracted.get('prior_lines_of_therapy')
    facts.concomitant_meds.prior_immunotherapy = extracted.get('prior_immunotherapy')

    # Immunogenicity
    facts.immunogenicity.ada_testing_performed = extracted.get('ada_testing_performed')
    facts.immunogenicity.ada_assay_type = extracted.get('ada_assay_type')
    facts.immunogenicity.ada_sampling_timepoints = extracted.get('ada_sampling_timepoints', [])
    facts.immunogenicity.nab_testing_performed = extracted.get('nab_testing_performed')
    facts.immunogenicity.nab_assay_type = extracted.get('nab_assay_type')
    facts.immunogenicity.ada_incidence_analysis = extracted.get('ada_incidence_analysis')
    facts.immunogenicity.ada_impact_on_efficacy = extracted.get('ada_impact_on_efficacy')
    facts.immunogenicity.ada_impact_on_safety = extracted.get('ada_impact_on_safety')
    facts.immunogenicity.ada_impact_on_pk = extracted.get('ada_impact_on_pk')

    # Conventions
    facts.conventions.baseline_definition = extracted.get('baseline_definition', '')
    facts.conventions.baseline_window = extracted.get('baseline_window', '')
    facts.conventions.partial_date_imputation_rules = extracted.get('partial_date_imputation_rules', {})
    facts.conventions.visit_windows = extracted.get('visit_windows', {})
    facts.conventions.on_treatment_definition = extracted.get('on_treatment_definition', '')
    facts.conventions.post_treatment_definition = extracted.get('post_treatment_definition', '')
    facts.conventions.rounding_convention = extracted.get('rounding_convention', '')

    # Protocol Deviations
    facts.deviations.important_deviation_categories = extracted.get('important_deviation_categories', [])
    facts.deviations.deviation_impact_on_populations = extracted.get('deviation_impact_on_populations', '')

    # PRO
    facts.pro.pro_instruments = extracted.get('pro_instruments', [])
    facts.pro.instrument_scoring_rules = extracted.get('instrument_scoring_rules', {})
    facts.pro.pro_primary_endpoint = extracted.get('pro_primary_endpoint')
    facts.pro.pro_secondary_endpoints = extracted.get('pro_secondary_endpoints', [])
    facts.pro.time_to_deterioration = extracted.get('time_to_deterioration')
    facts.pro.ttd_threshold = extracted.get('ttd_threshold')
    facts.pro.responder_definition = extracted.get('pro_responder_definition')
    facts.pro.pro_missing_data_handling = extracted.get('pro_missing_data_handling', '')
    facts.pro.pro_compliance_threshold = extracted.get('pro_compliance_threshold')
    facts.pro.pro_collection_schedule = extracted.get('pro_collection_schedule', [])
    facts.pro.pro_electronic_capture = extracted.get('pro_electronic_capture')

    # DMC
    facts.dmc.has_dmc = extracted.get('has_dmc')
    facts.dmc.dmc_charter_exists = extracted.get('dmc_charter_exists')
    facts.dmc.dmc_review_frequency = extracted.get('dmc_review_frequency', '')
    facts.dmc.dmc_unblinded = extracted.get('dmc_unblinded')
    facts.dmc.safety_stopping_rules = extracted.get('safety_stopping_rules', [])
    facts.dmc.safety_boundary_type = extracted.get('safety_boundary_type', '')
    facts.dmc.futility_review_planned = extracted.get('futility_review_planned')
    facts.dmc.futility_boundary = extracted.get('futility_boundary', '')
    facts.dmc.dmc_recommendation_options = extracted.get('dmc_recommendation_options', [])
    facts.dmc.sponsor_blinded = extracted.get('sponsor_blinded')
    facts.dmc.independent_statistician = extracted.get('independent_statistician')

    # CDISC
    facts.cdisc.sdtm_version = extracted.get('sdtm_version', '')
    facts.cdisc.sdtm_domains = extracted.get('sdtm_domains', [])
    facts.cdisc.adam_version = extracted.get('adam_version', '')
    facts.cdisc.adam_datasets = extracted.get('adam_datasets', [])
    facts.cdisc.oncology_response_domains = extracted.get('oncology_response_domains', [])
    facts.cdisc.response_criteria = extracted.get('cdisc_response_criteria', '')
    facts.cdisc.key_derivations = extracted.get('key_derivations', {})
    facts.cdisc.submission_standard = extracted.get('submission_standard', '')
    facts.cdisc.define_xml_version = extracted.get('define_xml_version', '')

    # Special Designs
    facts.special_design.is_master_protocol = extracted.get('is_master_protocol')
    facts.special_design.master_protocol_type = extracted.get('master_protocol_type', '')
    facts.special_design.is_basket_trial = extracted.get('is_basket_trial')
    facts.special_design.basket_tumor_types = extracted.get('basket_tumor_types', [])
    facts.special_design.basket_shared_biomarker = extracted.get('basket_shared_biomarker', '')
    facts.special_design.is_umbrella_trial = extracted.get('is_umbrella_trial')
    facts.special_design.umbrella_biomarker_arms = extracted.get('umbrella_biomarker_arms', [])
    facts.special_design.is_platform_trial = extracted.get('is_platform_trial')
    facts.special_design.shared_control_arm = extracted.get('shared_control_arm')
    facts.special_design.is_adaptive = extracted.get('is_adaptive')
    facts.special_design.adaptive_features = extracted.get('adaptive_features', [])
    facts.special_design.adaptation_timing = extracted.get('adaptation_timing', [])
    facts.special_design.adaptation_rules = extracted.get('adaptation_rules', '')
    facts.special_design.is_seamless = extracted.get('is_seamless')
    facts.special_design.seamless_phases = extracted.get('seamless_phases', '')
    facts.special_design.phase2_to_phase3_criteria = extracted.get('phase2_to_phase3_criteria', '')

    # Tumor Assessment
    facts.tumor_assessment.response_criteria = extracted.get('response_criteria', '')
    facts.tumor_assessment.response_criteria_version = extracted.get('response_criteria_version', '')
    facts.tumor_assessment.assessment_schedule = extracted.get('assessment_schedule', '')
    facts.tumor_assessment.baseline_imaging_window = extracted.get('baseline_imaging_window', '')
    facts.tumor_assessment.target_lesion_selection = extracted.get('target_lesion_selection', '')
    facts.tumor_assessment.max_target_lesions = extracted.get('max_target_lesions')
    facts.tumor_assessment.min_lesion_size = extracted.get('min_lesion_size')
    facts.tumor_assessment.assessment_method = extracted.get('assessment_method', '')
    facts.tumor_assessment.bicr_primary = extracted.get('bicr_primary')
    facts.tumor_assessment.discrepancy_resolution = extracted.get('discrepancy_resolution', '')
    facts.tumor_assessment.confirmation_required = extracted.get('confirmation_required')
    facts.tumor_assessment.confirmation_window = extracted.get('confirmation_window', '')
    facts.tumor_assessment.pseudoprogression_handling = extracted.get('pseudoprogression_handling', '')
    facts.tumor_assessment.new_lesion_confirmation = extracted.get('new_lesion_confirmation')
    facts.tumor_assessment.progression_date_definition = extracted.get('progression_date_definition', '')

    # Confidence
    facts.confidence.overall_confidence = extracted.get('extraction_confidence', 0.0)
    facts.confidence.needs_review = extracted.get('needs_review', [])
    facts.confidence.section_confidence = extracted.get('section_confidence', {})

    return facts


# =============================================================================
# VALIDATION
# =============================================================================

def validate_extraction(facts: ExtractedProtocolFacts) -> Dict[str, Any]:
    """
    Validate extracted facts for completeness and consistency.

    Returns:
        Dict with 'valid' bool, 'missing' list, 'warnings' list
    """
    result = {
        'valid': True,
        'missing': [],
        'warnings': []
    }

    # Check critical numerical fields
    critical = facts.get_critical_numerical_fields()

    for field_name, value in critical.items():
        if value is None:
            result['missing'].append(field_name)
        elif isinstance(value, (int, float)) and value == 0:
            if field_name not in ['num_interim_analyses']:  # 0 interim is valid
                result['warnings'].append(f"{field_name} is 0 - verify this is correct")

    # Check critical text fields
    if not facts.design.treatment_setting:
        result['warnings'].append("treatment_setting not extracted - may cause setting errors")
    if not facts.design.disease_type:
        result['warnings'].append("disease_type not extracted - may cause generic disease errors")
    if not facts.methods.primary_test:
        result['missing'].append("statistical_method (primary_test)")

    # Validate interim analysis consistency
    if facts.interim.has_interim_analysis:
        if facts.interim.num_interim_analyses == 0:
            result['warnings'].append("has_interim_analysis=True but num_interim_analyses=0")
        if not facts.interim.interim_events:
            result['missing'].append("interim_events (required when has_interim_analysis=True)")
        if not facts.interim.alpha_at_interim:
            result['missing'].append("alpha_at_interim (required when has_interim_analysis=True)")

    # Check for default alpha being used
    if facts.interim.overall_alpha == 0.05:
        result['warnings'].append("alpha=0.05 may be default - verify from protocol")

    result['valid'] = len(result['missing']) == 0

    return result


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Enhanced Extraction Schema")
    print("=" * 60)

    # Create sample facts with new fields
    facts = ExtractedProtocolFacts()
    facts.admin.nct_id = "NCT02041533"
    facts.design.drug_name = "Nivolumab"
    facts.design.comparator = "Docetaxel"
    facts.design.sample_size = 504

    # NEW CRITICAL FIELDS
    facts.design.treatment_setting = "second-line"
    facts.design.disease_type = "Non-small cell lung cancer (NSCLC)"
    facts.design.histology = "Squamous"
    facts.design.stratification_factor_levels = {
        "PD-L1": ["<1%", "1-49%", "≥50%"],
        "ECOG": ["0", "1"]
    }

    # Interim
    facts.interim.has_interim_analysis = True
    facts.interim.num_interim_analyses = 1
    facts.interim.interim_events = [291]
    facts.interim.final_events = 382
    facts.interim.alpha_at_interim = [0.020]
    facts.interim.alpha_at_final = 0.044

    # Multiplicity with explicit alpha
    facts.multiplicity.alpha_per_hypothesis = {
        "OS": 0.025,
        "ORR": 0.025
    }

    # Get critical fields
    print("\nCritical Numerical Fields:")
    for field, value in facts.get_critical_numerical_fields().items():
        print(f"  {field}: {value}")

    # Validate
    print("\nValidation:")
    validation = validate_extraction(facts)
    print(f"  Valid: {validation['valid']}")
    print(f"  Missing: {validation['missing']}")
    print(f"  Warnings: {validation['warnings']}")

    # Convert to flat dict
    print("\nFlat Dict (for prompt):")
    flat = facts.to_flat_dict()
    print(f"  Total fields: {len(flat)}")
    for key in ['treatment_setting', 'disease_type', 'histology', 'alpha_per_hypothesis', 'stratification_factor_levels']:
        print(f"  {key}: {flat.get(key)}")
