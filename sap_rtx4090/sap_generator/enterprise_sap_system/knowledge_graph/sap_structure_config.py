"""
Dynamic SAP Structure Configuration
====================================

Based on:
- TransCelerate 2024 SAP Template (16 sections)
- Gamble et al. 2017 JAMA Guidelines (55 items, 6 categories)
- ICH E9 / E9(R1) Statistical Principles
- FDA/EMA regulatory requirements

The SAP structure is DYNAMIC based on protocol characteristics:
- Study design (randomized, single-arm, crossover, adaptive)
- Therapeutic area (oncology, hematology, CAR-T, etc.)
- Trial phase (1, 2, 3, 4)
- Specific features (interim analysis, biomarkers, PRO/QoL)
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
import json


@dataclass
class SAPSection:
    """Definition of a SAP section."""
    number: str  # e.g., "1", "7.1", "A1"
    title: str
    required: bool = True  # Always include vs conditional
    condition: Optional[str] = None  # Condition key for inclusion
    subsections: List['SAPSection'] = field(default_factory=list)
    description: str = ""
    kb_tools: List[str] = field(default_factory=list)  # Tools to call for this section


# =============================================================================
# MASTER SAP STRUCTURE (TransCelerate + Extensions)
# =============================================================================

MASTER_SAP_SECTIONS = [
    # -------------------------------------------------------------------------
    # ADMINISTRATIVE (Always Required)
    # -------------------------------------------------------------------------
    SAPSection(
        number="1",
        title="TITLE PAGE & ADMINISTRATIVE INFORMATION",
        required=True,
        description="Protocol identification, SAP version, signatures, amendment history",
        kb_tools=[]
    ),

    # -------------------------------------------------------------------------
    # INTRODUCTION & OBJECTIVES
    # -------------------------------------------------------------------------
    SAPSection(
        number="2",
        title="INTRODUCTION",
        required=True,
        description="Background, rationale, study synopsis",
        subsections=[
            SAPSection("2.1", "Study Background", required=True),
            SAPSection("2.2", "Study Objectives", required=True),
            SAPSection("2.3", "Study Endpoints", required=True,
                      kb_tools=["get_oncology_tfl_templates"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # STUDY DESIGN
    # -------------------------------------------------------------------------
    SAPSection(
        number="3",
        title="STUDY DESIGN",
        required=True,
        description="Design type, treatment arms, stratification, blinding",
        kb_tools=["get_study_design_specs", "get_study_type_template"],
        subsections=[
            SAPSection("3.1", "Overall Design", required=True,
                      kb_tools=["get_study_design_specs", "get_study_type_template"]),
            SAPSection("3.2", "Treatment Arms", required=True,
                      condition="has_multiple_arms"),
            SAPSection("3.3", "Randomization", required=False,
                      condition="is_randomized",
                      kb_tools=["get_stratification_specs", "get_stratification_balance_specs"]),
            SAPSection("3.4", "Blinding", required=False,
                      condition="is_blinded",
                      kb_tools=["get_blinding_specifications"]),
            SAPSection("3.5", "Stratification Factors", required=False,
                      condition="has_stratification",
                      kb_tools=["get_stratification_specs", "get_stratification_balance_specs"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # SAMPLE SIZE & POWER
    # -------------------------------------------------------------------------
    SAPSection(
        number="4",
        title="SAMPLE SIZE & POWER",
        required=True,
        description="Sample size justification, power calculations, assumptions",
        kb_tools=["get_statistical_method"],
        subsections=[
            SAPSection("4.1", "Primary Endpoint Sample Size", required=True),
            SAPSection("4.2", "Assumptions", required=True),
            SAPSection("4.3", "Power Calculation Details", required=True),
        ]
    ),

    # -------------------------------------------------------------------------
    # ANALYSIS POPULATIONS
    # -------------------------------------------------------------------------
    SAPSection(
        number="5",
        title="ANALYSIS POPULATIONS",
        required=True,
        description="ITT, mITT, Safety, Per-Protocol, Evaluable populations",
        kb_tools=["get_population_definitions"],
        subsections=[
            SAPSection("5.1", "Intent-to-Treat (ITT) Population", required=True),
            SAPSection("5.2", "Safety Population", required=True),
            SAPSection("5.3", "Per-Protocol Population", required=True),
            SAPSection("5.4", "Response-Evaluable Population", required=False,
                      condition="has_response_endpoint"),
            SAPSection("5.5", "Pharmacokinetic Population", required=False,
                      condition="has_pk_endpoints"),
            # CAR-T specific populations
            SAPSection("5.6", "Modified ITT (mITT) Population", required=False,
                      condition="is_cart",
                      description="Subjects who received CAR-T infusion"),
            SAPSection("5.7", "Safety Re-treatment Analysis Set", required=False,
                      condition="is_cart_with_retreatment",
                      kb_tools=["get_cart_specifications"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # BASELINE CHARACTERISTICS (v77 - comprehensive coverage)
    # -------------------------------------------------------------------------
    SAPSection(
        number="5A",
        title="BASELINE CHARACTERISTICS AND DISEASE HISTORY",
        required=True,
        description="Demographics, baseline disease, prior therapy, medical history, concomitant medications",
        kb_tools=["get_demographics_baseline_specs", "get_prior_therapy_specs", "get_performance_status_scales", "get_prognostic_scores"],
        subsections=[
            SAPSection("5A.1", "Demographics", required=True,
                      description="Age, sex, race, ethnicity, weight, height, BSA, BMI",
                      kb_tools=["get_demographics_baseline_specs"]),
            SAPSection("5A.2", "Baseline Disease Characteristics", required=True,
                      description="ECOG PS, disease stage, time since diagnosis, measurable disease",
                      kb_tools=["get_demographics_baseline_specs", "get_organ_function_specs", "get_performance_status_scales", "get_organ_function_scores"]),
            SAPSection("5A.3", "Prognostic Scores", required=False,
                      description="IPI, FLIPI, ISS, IMDC and other disease-specific scores",
                      kb_tools=["get_prognostic_scores"]),
            SAPSection("5A.4", "Prior Anti-Cancer Therapy", required=True,
                      description="Number of prior lines, types, specific agents, refractory status",
                      kb_tools=["get_prior_therapy_specs"]),
            SAPSection("5A.5", "Medical History", required=True,
                      description="By MedDRA SOC and PT",
                      kb_tools=["get_medical_history_specs"]),
            SAPSection("5A.6", "Prior and Concomitant Medications", required=True,
                      description="By WHO Drug/ATC classification",
                      kb_tools=["get_concomitant_medication_specs"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # ENDPOINTS & ESTIMANDS
    # -------------------------------------------------------------------------
    SAPSection(
        number="6",
        title="ENDPOINTS & ESTIMANDS",
        required=True,
        description="Primary, secondary, exploratory endpoints with ICH E9(R1) estimands",
        kb_tools=["get_estimand_framework", "get_oncology_tfl_templates", "get_tumor_response_specs"],
        subsections=[
            SAPSection("6.1", "Primary Endpoint(s)", required=True,
                      kb_tools=["get_tumor_response_specs"]),
            SAPSection("6.2", "Secondary Endpoint(s)", required=True),
            SAPSection("6.3", "Exploratory Endpoint(s)", required=False,
                      condition="has_exploratory_endpoints"),
            SAPSection("6.4", "Estimand Framework", required=True,
                      description="ICH E9(R1) estimands for each endpoint",
                      kb_tools=["get_estimand_specifications"]),
            SAPSection("6.5", "Response Assessment Methodology", required=False,
                      condition="has_response_endpoint",
                      description="RECIST 1.1, Lugano, IWCLL, IMWG criteria",
                      kb_tools=["get_tumor_response_specs", "get_response_criteria", "get_all_response_criteria"]),
            SAPSection("6.6", "IRC vs Investigator Concordance", required=False,
                      condition="is_randomized",
                      description="Kappa statistic, concordance matrix, discordance analysis",
                      kb_tools=["get_concordance_specs", "get_concordance_analysis"]),
            # CAR-T specific endpoints
            SAPSection("6.7", "Retreatment Endpoints (DORR)", required=False,
                      condition="is_cart_with_retreatment",
                      kb_tools=["get_cart_specifications"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # STATISTICAL METHODS
    # -------------------------------------------------------------------------
    SAPSection(
        number="7",
        title="STATISTICAL METHODS",
        required=True,
        description="Analysis methods for each endpoint type",
        kb_tools=["get_statistical_method", "get_time_to_event_analysis"],
        subsections=[
            SAPSection("7.1", "General Considerations", required=True,
                      kb_tools=["get_blinding_specifications"]),
            SAPSection("7.2", "Time-to-Event Analyses", required=False,
                      condition="has_tte_endpoints",
                      kb_tools=["get_time_to_event_analysis", "get_censoring_rules"]),
            SAPSection("7.3", "Binary Endpoint Analyses", required=False,
                      condition="has_response_endpoint",
                      kb_tools=["get_confidence_interval_methods"]),
            SAPSection("7.4", "Continuous Endpoint Analyses", required=False,
                      condition="has_continuous_endpoints"),
            SAPSection("7.5", "Multiplicity Adjustment", required=False,
                      condition="has_multiple_primary_endpoints",
                      kb_tools=["get_multiplicity_adjustment", "get_multiplicity_methods"]),
            # Single-arm specific
            SAPSection("7.6", "Single-Arm Response Rate Analysis", required=False,
                      condition="is_single_arm",
                      description="Clopper-Pearson CI, Simon two-stage",
                      kb_tools=["get_single_arm_tables", "get_phase2_design_specs"]),
            # MRD for hematologic malignancies
            SAPSection("7.7", "MRD Assessment", required=False,
                      condition="has_mrd_endpoint",
                      description="Minimal residual disease analysis",
                      kb_tools=["get_mrd_assessment_specs"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # CENSORING RULES (Critical for Oncology)
    # -------------------------------------------------------------------------
    SAPSection(
        number="8",
        title="CENSORING RULES",
        required=False,
        condition="has_tte_endpoints",
        description="Detailed censoring rules for each TTE endpoint",
        kb_tools=["get_censoring_rules", "get_similar_trials"],
        subsections=[
            SAPSection("8.1", "Progression-Free Survival Censoring", required=False,
                      condition="has_pfs_endpoint"),
            SAPSection("8.2", "Overall Survival Censoring", required=False,
                      condition="has_os_endpoint"),
            SAPSection("8.3", "Duration of Response Censoring", required=False,
                      condition="has_dor_endpoint"),
            SAPSection("8.4", "Event-Free Survival Censoring", required=False,
                      condition="has_efs_endpoint"),
        ]
    ),

    # -------------------------------------------------------------------------
    # MISSING DATA & SENSITIVITY ANALYSES
    # -------------------------------------------------------------------------
    SAPSection(
        number="9",
        title="MISSING DATA HANDLING",
        required=True,
        description="Missing data conventions, imputation methods",
        kb_tools=["get_missing_data_method", "get_data_handling_rules"],
        subsections=[
            SAPSection("9.1", "Missing Data Conventions", required=True),
            SAPSection("9.2", "Date Imputation Rules", required=True,
                      description="Partial date handling for AEs, prior therapies"),
            SAPSection("9.3", "Missing Endpoint Data", required=True),
        ]
    ),

    SAPSection(
        number="10",
        title="SENSITIVITY ANALYSES",
        required=True,
        description="Robustness analyses for primary conclusions",
        kb_tools=["get_sensitivity_analysis", "get_sensitivity_analysis_catalog"],
        subsections=[
            SAPSection("10.1", "Primary Endpoint Sensitivity Analyses", required=True,
                      kb_tools=["get_sensitivity_analysis_catalog"]),
            SAPSection("10.2", "Per-Protocol Analysis", required=True),
            SAPSection("10.3", "Tipping Point Analysis", required=False,
                      condition="has_missing_data_concerns"),
            SAPSection("10.4", "COVID-19 Sensitivity Analyses", required=False,
                      condition="has_covid_impact",
                      kb_tools=["get_covid19_variations"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # SUBGROUP ANALYSES
    # -------------------------------------------------------------------------
    SAPSection(
        number="11",
        title="SUBGROUP ANALYSES",
        required=True,
        description="Pre-specified subgroup analyses",
        kb_tools=["get_subgroup_analysis_specs", "get_subgroup_specifications"],
        subsections=[
            SAPSection("11.1", "Pre-specified Subgroups", required=True,
                      kb_tools=["get_subgroup_specifications"]),
            SAPSection("11.2", "Subgroup Analysis Methods", required=True,
                      kb_tools=["get_subgroup_specifications"]),
            SAPSection("11.3", "Forest Plot Specifications", required=False,
                      condition="is_randomized",
                      kb_tools=["get_subgroup_specifications"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # SAFETY ANALYSIS
    # -------------------------------------------------------------------------
    SAPSection(
        number="12",
        title="SAFETY ANALYSIS",
        required=True,
        description="Adverse events, laboratory, vital signs, ECG analyses",
        kb_tools=["get_safety_analysis_specs", "get_safety_tables", "get_safety_specifications", "get_ae_period_specifications"],
        subsections=[
            SAPSection("12.1", "Adverse Events", required=True,
                      kb_tools=["get_ae_period_specifications"]),
            SAPSection("12.2", "Deaths and Survival", required=True,
                      description="Death summary, cause of death, last known alive derivation",
                      kb_tools=["get_death_analysis_specs"]),
            SAPSection("12.3", "Laboratory Parameters", required=True),
            SAPSection("12.4", "Vital Signs", required=True),
            SAPSection("12.5", "ECG Parameters", required=False,
                      condition="has_ecg_monitoring"),
            SAPSection("12.6", "Exposure and Treatment Compliance", required=True,
                      description="Dose compliance, treatment duration, dose modifications",
                      kb_tools=["get_exposure_specifications", "get_treatment_compliance_specs"]),
            SAPSection("12.7", "Subsequent Therapy", required=True,
                      kb_tools=["get_subsequent_therapy_specs"]),
            # CAR-T specific safety
            SAPSection("12.8", "Cytokine Release Syndrome (CRS)", required=False,
                      condition="is_cart",
                      kb_tools=["get_cart_specifications", "get_cart_tables", "get_ae_period_specifications"]),
            SAPSection("12.9", "Immune Effector Cell-Associated Neurotoxicity (ICANS)", required=False,
                      condition="is_cart",
                      kb_tools=["get_cart_specifications", "get_cart_tables"]),
            SAPSection("12.10", "CAR-T Cellular Kinetics", required=False,
                      condition="is_cart",
                      kb_tools=["get_cart_specifications", "get_pkpd_analysis_specs"]),
            SAPSection("12.11", "CAR-T Manufacturing Metrics", required=False,
                      condition="is_cart",
                      description="Leukapheresis timing, vein-to-vein time, bridging therapy",
                      kb_tools=["get_cart_manufacturing_specs"]),
            SAPSection("12.12", "Prolonged Cytopenias", required=False,
                      condition="is_cart"),
            SAPSection("12.13", "B-Cell Aplasia & Hypogammaglobulinemia", required=False,
                      condition="is_cart"),
            SAPSection("12.14", "Healthcare Resource Utilization", required=False,
                      condition="has_hru_endpoints",
                      kb_tools=["get_healthcare_utilization_specs"]),
            SAPSection("12.15", "Immunogenicity", required=False,
                      condition="is_biologic",
                      description="ADA incidence, neutralizing antibodies, impact on PK/efficacy",
                      kb_tools=["get_immunogenicity_specs"]),
            # ADC-specific safety
            SAPSection("12.16", "ADC-Specific Toxicities", required=False,
                      condition="is_adc",
                      description="Payload-related toxicities, ocular toxicity, peripheral neuropathy",
                      kb_tools=["get_adc_specifications", "get_safety_specifications"]),
            # Bispecific-specific safety
            SAPSection("12.17", "Bispecific Antibody Safety", required=False,
                      condition="is_bispecific",
                      description="CRS grading for bispecifics, step-up dosing safety",
                      kb_tools=["get_bispecific_specifications", "get_safety_specifications"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # INTERIM ANALYSIS (Conditional)
    # -------------------------------------------------------------------------
    SAPSection(
        number="13",
        title="INTERIM ANALYSIS",
        required=False,
        condition="has_interim_analysis",
        description="Interim analysis timing, stopping boundaries, alpha spending",
        kb_tools=["get_interim_analysis", "get_interim_analysis_specs"],
        subsections=[
            SAPSection("13.1", "Timing and Information Fractions", required=True,
                      kb_tools=["get_interim_analysis_specs"]),
            SAPSection("13.2", "Alpha Spending Function", required=True,
                      kb_tools=["get_interim_analysis_specs", "get_multiplicity_methods"]),
            SAPSection("13.3", "Stopping Boundaries", required=True,
                      kb_tools=["get_interim_analysis_specs"]),
            SAPSection("13.4", "Futility Assessment", required=True,
                      kb_tools=["get_interim_analysis_specs"]),
            SAPSection("13.5", "DMC/DSMB Charter Reference", required=True,
                      kb_tools=["get_interim_analysis_specs"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # BIOMARKER ANALYSIS (Conditional)
    # -------------------------------------------------------------------------
    SAPSection(
        number="14",
        title="BIOMARKER ANALYSIS",
        required=False,
        condition="has_biomarker_endpoints",
        description="Biomarker endpoints and correlative analyses",
        kb_tools=["get_biomarker_endpoints"],
        subsections=[
            SAPSection("14.1", "Biomarker Endpoints", required=True),
            SAPSection("14.2", "Biomarker-Efficacy Correlations", required=True),
            SAPSection("14.3", "Biomarker Subgroup Analyses", required=False),
        ]
    ),

    # -------------------------------------------------------------------------
    # PRO/QoL ANALYSIS (Conditional)
    # -------------------------------------------------------------------------
    SAPSection(
        number="15",
        title="PATIENT-REPORTED OUTCOMES",
        required=False,
        condition="has_pro_endpoints",
        description="PRO instruments, scoring, analysis methods",
        kb_tools=["get_pro_qol_analysis", "get_qol_analysis_specs"],
        subsections=[
            SAPSection("15.1", "PRO Instruments", required=True,
                      kb_tools=["get_qol_analysis_specs"]),
            SAPSection("15.2", "Scoring Algorithms", required=True,
                      kb_tools=["get_qol_analysis_specs"]),
            SAPSection("15.3", "Missing PRO Data Handling", required=True,
                      kb_tools=["get_qol_analysis_specs"]),
            SAPSection("15.4", "PRO Analysis Methods", required=True,
                      description="MMRM, time-to-deterioration, responder analysis",
                      kb_tools=["get_qol_analysis_specs"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # DEFINITIONS (Required for all SAPs)
    # -------------------------------------------------------------------------
    SAPSection(
        number="16",
        title="DEFINITIONS",
        required=True,
        description="Standard study definitions - Study Day, baseline, TEAE, follow-up time",
        kb_tools=["get_study_definitions"],
        subsections=[
            SAPSection("16.1", "Time Point Definitions", required=True,
                      description="Study Day 0, baseline, on-study period, end of study",
                      kb_tools=["get_study_definitions"]),
            SAPSection("16.2", "Safety Event Definitions", required=True,
                      description="TEAE, treatment-related AE, SAE, AESI definitions",
                      kb_tools=["get_study_definitions"]),
            SAPSection("16.3", "Follow-up Time Definitions", required=True,
                      description="Actual vs potential follow-up, reverse K-M method",
                      kb_tools=["get_study_definitions"]),
            SAPSection("16.4", "Enrollment Definition", required=True,
                      description="Date of enrollment (consent, randomization, or leukapheresis)",
                      kb_tools=["get_study_definitions"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # PROGRAMMING SPECIFICATIONS
    # -------------------------------------------------------------------------
    SAPSection(
        number="17",
        title="PROGRAMMING SPECIFICATIONS",
        required=True,
        description="Analysis windows, visit definitions, derived variables",
        kb_tools=["get_programming_specifications", "get_derived_variables", "get_analysis_windows", "get_analysis_timing_specs"],
        subsections=[
            SAPSection("17.1", "Analysis Windows", required=True),
            SAPSection("17.2", "Baseline Value Derivations", required=True),
            SAPSection("17.3", "Derived Variable Specifications", required=True),
            SAPSection("17.4", "Data Cutoff Rules", required=True,
                      kb_tools=["get_data_cutoff_specs"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # TFL SHELLS
    # -------------------------------------------------------------------------
    SAPSection(
        number="18",
        title="TABLE, FIGURE, AND LISTING SHELLS",
        required=True,
        description="Complete TFL inventory with shells",
        kb_tools=["get_disposition_tables", "get_efficacy_tables", "get_safety_tables",
                  "get_tfl_shells", "get_all_figures", "get_listings", "get_figure_template", "get_table_template"],
        subsections=[
            SAPSection("18.1", "Disposition Tables", required=True,
                      kb_tools=["get_disposition_tables", "get_single_arm_tables", "get_enrollment_specifications"]),
            SAPSection("18.2", "Demographics and Baseline Tables", required=True,
                      kb_tools=["get_lymphoma_tables"]),
            SAPSection("18.3", "Efficacy Tables", required=True,
                      kb_tools=["get_efficacy_tables"]),
            SAPSection("18.4", "Safety Tables", required=True,
                      kb_tools=["get_safety_tables", "get_cart_tables"]),
            SAPSection("18.5", "Figures", required=True,
                      kb_tools=["get_all_figures"]),
            SAPSection("18.6", "Listings", required=True,
                      kb_tools=["get_listings"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # DATA SCREENING AND ACCEPTANCE
    # -------------------------------------------------------------------------
    SAPSection(
        number="19",
        title="DATA SCREENING AND ACCEPTANCE",
        required=True,
        description="Data quality, edit checks, outliers, validation procedures",
        kb_tools=["get_protocol_deviation_specs"],
        subsections=[
            SAPSection("19.1", "General Data Handling Principles", required=True),
            SAPSection("19.2", "Electronic Data Transfer", required=True,
                      description="CRO to sponsor data transfer procedures"),
            SAPSection("19.3", "Detection of Bias and Protocol Deviations", required=True,
                      kb_tools=["get_protocol_deviation_specs"]),
            SAPSection("19.4", "Outlier Detection and Handling", required=True),
            SAPSection("19.5", "Distributional Characteristics Assessment", required=True),
        ]
    ),

    # -------------------------------------------------------------------------
    # FOLLOW-UP ANALYSIS
    # -------------------------------------------------------------------------
    SAPSection(
        number="20",
        title="FOLLOW-UP ANALYSIS",
        required=False,
        condition="has_follow_up_analyses",
        description="Planned descriptive analyses at specified timepoints after primary analysis",
        kb_tools=["get_similar_trials"],
        subsections=[
            SAPSection("20.1", "Follow-up Analysis Schedule", required=True,
                      description="Timing of follow-up analyses (e.g., 18 months, 24 months)"),
            SAPSection("20.2", "Follow-up Analysis Objectives", required=True,
                      description="Safety and efficacy updates - descriptive only"),
        ]
    ),

    # -------------------------------------------------------------------------
    # CHANGES FROM PROTOCOL-SPECIFIED ANALYSES
    # -------------------------------------------------------------------------
    SAPSection(
        number="21",
        title="CHANGES FROM PROTOCOL-SPECIFIED ANALYSES",
        required=True,
        description="Documentation of any deviations from protocol-specified statistical methods",
        subsections=[
            SAPSection("21.1", "Summary of Changes", required=True,
                      description="List changes or state 'No changes from protocol-specified analyses'"),
        ]
    ),

    # -------------------------------------------------------------------------
    # REFERENCES
    # -------------------------------------------------------------------------
    SAPSection(
        number="22",
        title="REFERENCES",
        required=True,
        description="Citations for statistical methods, response criteria, grading scales",
        kb_tools=["get_required_references"],
        subsections=[
            SAPSection("22.1", "Response Criteria References", required=False,
                      condition="has_response_endpoint"),
            SAPSection("22.2", "Statistical Methodology References", required=True),
            SAPSection("22.3", "Safety Grading References", required=True,
                      description="CTCAE version, CRS grading, etc."),
        ]
    ),

    # -------------------------------------------------------------------------
    # APPENDICES
    # -------------------------------------------------------------------------
    SAPSection(
        number="A",
        title="APPENDICES",
        required=True,
        description="Reference tables and detailed specifications",
        subsections=[
            SAPSection("A.1", "Date Imputation Algorithm", required=True,
                      kb_tools=["get_date_imputation_rules"]),
            SAPSection("A.2", "Time-to-Event Derivation Rules", required=False,
                      condition="has_tte_endpoints",
                      description="Circumstance tables for each TTE endpoint (DOR, PFS, OS)",
                      kb_tools=["get_tte_derivation_tables"]),
            SAPSection("A.3", "MedDRA Search Strategies", required=False,
                      condition="is_cart",
                      description="SMQ, MST for CRS, ICANS, cytopenias, infections",
                      kb_tools=["get_meddra_search_strategies"]),
            SAPSection("A.4", "Response Criteria Reference", required=False,
                      condition="has_response_endpoint",
                      kb_tools=["get_response_criteria", "get_recist_specifications", "get_all_response_criteria", "get_cml_criteria", "get_iwcll_criteria"]),
            SAPSection("A.5", "ADaM Dataset Specifications", required=True,
                      kb_tools=["get_adam_dataset_spec"]),
        ]
    ),
]


# =============================================================================
# CONDITION DETECTION FUNCTIONS
# =============================================================================

def detect_sap_conditions(protocol_extraction: Dict) -> Dict[str, bool]:
    """
    Detect which conditions apply based on protocol extraction.

    Returns dict of condition_name -> bool for section inclusion logic.
    """
    conditions = {}

    # Study Design Conditions
    study_design = protocol_extraction.get("study_design", {})
    design_type = (study_design.get("design_type", {}).get("value") or "").lower()

    conditions["is_randomized"] = design_type in ["randomized", "randomised", "rct"]
    conditions["is_single_arm"] = design_type == "single_arm" or design_type == "single-arm"
    conditions["is_blinded"] = "blind" in design_type or "double" in design_type
    conditions["is_adaptive"] = "adaptive" in design_type

    # Treatment Arms
    arms = protocol_extraction.get("treatment_arms", [])
    conditions["has_multiple_arms"] = len(arms) > 1

    # Stratification
    strat = protocol_extraction.get("stratification_factors", [])
    conditions["has_stratification"] = len(strat) > 0

    # Endpoint Conditions
    endpoints = protocol_extraction.get("endpoints", {})
    primary = endpoints.get("primary", []) if endpoints else []
    secondary = endpoints.get("secondary", []) if endpoints else []
    exploratory = endpoints.get("exploratory", []) if endpoints else []

    all_endpoints = primary + secondary + exploratory

    # Extract endpoint names/text for searching
    def extract_endpoint_text(ep):
        if isinstance(ep, dict):
            return ep.get("name", "") or ep.get("value", "") or str(ep)
        return str(ep)

    endpoint_names = [extract_endpoint_text(e).lower() for e in all_endpoints]
    endpoint_str = " ".join(endpoint_names)

    conditions["has_tte_endpoints"] = any(x in endpoint_str for x in ["survival", "pfs", "efs", "dfs", "rfs", "ttp", "duration"])
    conditions["has_pfs_endpoint"] = "pfs" in endpoint_str or "progression-free" in endpoint_str
    # Check for OS as standalone or in "overall survival"
    conditions["has_os_endpoint"] = any(n.strip() == "os" or "overall survival" in n for n in endpoint_names)
    conditions["has_dor_endpoint"] = "dor" in endpoint_str or "duration of response" in endpoint_str
    conditions["has_efs_endpoint"] = "efs" in endpoint_str or "event-free" in endpoint_str
    conditions["has_response_endpoint"] = any(x in endpoint_str for x in ["orr", "response rate", "cr", "pr", "objective response"])
    conditions["has_continuous_endpoints"] = any(x in endpoint_str for x in ["change from baseline", "cfb", "mean", "qol", "pro"])
    conditions["has_exploratory_endpoints"] = len(exploratory) > 0
    conditions["has_multiple_primary_endpoints"] = len(primary) > 1
    conditions["has_biomarker_endpoints"] = any(x in endpoint_str for x in ["biomarker", "pd-l1", "tmb", "msi", "ctdna", "mrd"])
    # Note: Use word boundaries to avoid "pro" matching "progression"
    conditions["has_pro_endpoints"] = any(x in endpoint_str for x in ["qol", "quality of life", "patient-reported", "eortc", "fact-", "sf-36", "eq-5d", "eortc qlq"])
    conditions["has_pk_endpoints"] = any(x in endpoint_str for x in ["pharmacokinetic", "pk", "auc", "cmax", "tmax"])

    # Therapy Type Conditions
    treatment = protocol_extraction.get("investigational_product", {})
    product_type = (treatment.get("product_type", {}).get("value") or "").lower() if treatment else ""
    product_name = (treatment.get("name", {}).get("value") or "").lower() if treatment else ""

    conditions["is_cart"] = any(x in product_type + product_name for x in ["car-t", "cart", "car t", "cell therapy", "axicabtagene", "tisagenlecleucel", "liso-cel", "brexucabtagene"])
    conditions["is_cart_with_retreatment"] = conditions["is_cart"]  # CAR-T often allows retreatment
    conditions["is_bispecific"] = "bispecific" in product_type or "bite" in product_type
    conditions["is_adc"] = "adc" in product_type or "antibody-drug conjugate" in product_type
    conditions["is_immunotherapy"] = any(x in product_type + product_name for x in ["checkpoint", "pd-1", "pd-l1", "ctla-4", "immunotherapy"])
    conditions["is_biologic"] = any(x in product_type + product_name for x in [
        "antibody", "mab", "monoclonal", "biologic", "biosimilar",
        "car-t", "cell therapy", "bispecific", "adc"
    ]) or conditions["is_cart"] or conditions["is_bispecific"] or conditions["is_adc"]

    # Disease Conditions
    disease = protocol_extraction.get("disease_classification", {})
    tumor_type = (disease.get("tumor_type", {}).get("value") or "").lower() if disease else ""

    conditions["is_lymphoma"] = any(x in tumor_type for x in ["lymphoma", "nhl", "dlbcl", "follicular", "mantle"])
    conditions["is_hematologic"] = any(x in tumor_type for x in ["lymphoma", "leukemia", "myeloma", "hematologic"])
    conditions["is_solid_tumor"] = not conditions["is_hematologic"] and tumor_type != ""

    # Study Features - Interim Analysis Detection (Improved)
    # Check if interim_analysis field exists AND has content (not None/empty)
    interim_field = protocol_extraction.get("interim_analysis")
    has_explicit_interim = interim_field is not None and interim_field != {} and interim_field != []

    # Check for interim-related keywords in endpoint/design text (NOT the whole extraction
    # to avoid matching the field name "interim_analysis")
    design_str = json.dumps(study_design, default=str).lower() if study_design else ""
    endpoint_full_str = json.dumps(endpoints, default=str).lower() if endpoints else ""
    search_str = design_str + " " + endpoint_full_str

    has_interim_keywords = any(x in search_str for x in [
        "interim", "idmc", "dmc", "data monitoring", "futility",
        "efficacy boundary", "o'brien", "fleming", "alpha spending",
        "lan-demets", "group sequential", "stopping rule"
    ])

    # Phase 3 randomized TTE studies typically have interim analyses
    phase = protocol_extraction.get("phase", {})
    phase_value = (phase.get("value") or "").lower() if isinstance(phase, dict) else str(phase).lower()
    is_phase_3 = "3" in phase_value or "iii" in phase_value

    # Infer interim for randomized Phase 3 with PFS/OS primary endpoint
    infer_interim = (
        is_phase_3 and
        conditions.get("is_randomized") and
        (conditions.get("has_pfs_endpoint") or conditions.get("has_os_endpoint"))
    )

    conditions["has_interim_analysis"] = has_explicit_interim or has_interim_keywords or infer_interim

    # Other study features
    conditions["has_ecg_monitoring"] = True  # Assume yes for most oncology trials
    conditions["has_missing_data_concerns"] = True  # Always include sensitivity analyses

    # Follow-up analysis detection (from discovery)
    discovered = protocol_extraction.get("discovered_structure", {})
    protocol_sections = discovered.get("protocol_specific_sections", {}) if discovered else {}
    follow_ups = protocol_sections.get("follow_up_analyses", [])
    conditions["has_follow_up_analyses"] = bool(follow_ups and any(f.get("name") or f.get("timing") for f in follow_ups))

    # Phase detection for logging
    conditions["is_phase_2"] = "2" in phase_value or "ii" in phase_value
    conditions["is_phase_3"] = is_phase_3

    # MRD endpoint detection (hematologic malignancies)
    conditions["has_mrd_endpoint"] = any(x in endpoint_str for x in ["mrd", "minimal residual", "measurable residual"])

    # Healthcare resource utilization endpoint detection
    conditions["has_hru_endpoints"] = any(x in endpoint_str for x in [
        "hospitalization", "healthcare utilization", "resource utilization",
        "hospital", "icu", "length of stay", "healthcare resource"
    ])

    # COVID-19 impact detection (studies with enrollment during pandemic era)
    # Check for COVID-related keywords in protocol or note that 2020-2023 enrollment likely had COVID impact
    all_text = json.dumps(protocol_extraction, default=str).lower()
    conditions["has_covid_impact"] = any(x in all_text for x in [
        "covid", "pandemic", "sars-cov", "coronavirus",
        "remote assessment", "telemedicine", "virtual visit"
    ])

    return conditions


def get_required_sections(protocol_extraction: Dict) -> List[SAPSection]:
    """
    Get the list of required SAP sections based on protocol extraction.

    Returns filtered list of SAPSection objects that should be included.
    """
    conditions = detect_sap_conditions(protocol_extraction)

    def section_is_required(section: SAPSection) -> bool:
        """Check if a section should be included."""
        if section.required:
            return True
        if section.condition and conditions.get(section.condition, False):
            return True
        return False

    def filter_subsections(section: SAPSection) -> SAPSection:
        """Filter subsections recursively."""
        if not section.subsections:
            return section

        filtered_subs = []
        for sub in section.subsections:
            if section_is_required(sub):
                filtered_subs.append(filter_subsections(sub))

        # Create new section with filtered subsections
        return SAPSection(
            number=section.number,
            title=section.title,
            required=section.required,
            condition=section.condition,
            subsections=filtered_subs,
            description=section.description,
            kb_tools=section.kb_tools
        )

    required_sections = []
    for section in MASTER_SAP_SECTIONS:
        if section_is_required(section):
            required_sections.append(filter_subsections(section))

    return required_sections


def format_section_outline(sections: List[SAPSection], include_tools: bool = False) -> str:
    """
    Format sections as a markdown outline for the SAP generation prompt.
    """
    lines = []

    for section in sections:
        # Main section header
        line = f"## {section.number}. {section.title}"
        lines.append(line)

        if section.description:
            lines.append(f"   _{section.description}_")

        if include_tools and section.kb_tools:
            tools_str = ", ".join(section.kb_tools)
            lines.append(f"   **KB Tools:** {tools_str}")

        # Subsections
        for sub in section.subsections:
            sub_line = f"   ### {sub.number} {sub.title}"
            lines.append(sub_line)

            if include_tools and sub.kb_tools:
                tools_str = ", ".join(sub.kb_tools)
                lines.append(f"      **KB Tools:** {tools_str}")

    return "\n".join(lines)


def get_all_kb_tools_for_sections(sections: List[SAPSection]) -> Set[str]:
    """
    Get all KB tools that should be called for the given sections.
    """
    tools = set()

    def collect_tools(section: SAPSection):
        tools.update(section.kb_tools)
        for sub in section.subsections:
            collect_tools(sub)

    for section in sections:
        collect_tools(section)

    return tools


# =============================================================================
# QUICK SECTION COUNT BY PROTOCOL TYPE
# =============================================================================

def get_section_summary(protocol_extraction: Dict) -> Dict:
    """
    Get a summary of how many sections will be generated.
    """
    sections = get_required_sections(protocol_extraction)
    conditions = detect_sap_conditions(protocol_extraction)

    main_sections = len(sections)
    total_subsections = sum(len(s.subsections) for s in sections)

    special_sections = []
    if conditions.get("is_cart"):
        special_sections.append("CAR-T Safety (CRS, ICANS, Kinetics)")
    if conditions.get("is_single_arm"):
        special_sections.append("Single-Arm Analysis Methods")
    if conditions.get("is_lymphoma"):
        special_sections.append("Lymphoma-Specific (Ann Arbor, Lugano)")
    if conditions.get("has_interim_analysis"):
        special_sections.append("Interim Analysis")
    if conditions.get("has_biomarker_endpoints"):
        special_sections.append("Biomarker Analysis")
    if conditions.get("has_pro_endpoints"):
        special_sections.append("PRO/QoL Analysis")

    return {
        "main_sections": main_sections,
        "total_subsections": total_subsections,
        "special_sections": special_sections,
        "conditions_detected": {k: v for k, v in conditions.items() if v}
    }


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Example: ZUMA-5 like protocol (Phase 2, single-arm, CAR-T, lymphoma)
    zuma5_extraction = {
        "phase": {"value": "Phase 2"},
        "study_design": {"design_type": {"value": "single_arm"}},
        "treatment_arms": [{"name": "Axicabtagene ciloleucel"}],
        "investigational_product": {
            "product_type": {"value": "CAR-T cell therapy"},
            "name": {"value": "Axicabtagene ciloleucel"}
        },
        "disease_classification": {
            "tumor_type": {"value": "Follicular Lymphoma"}
        },
        "endpoints": {
            "primary": [{"name": "Overall Response Rate (ORR)"}],
            "secondary": [
                {"name": "Duration of Response (DOR)"},
                {"name": "Progression-Free Survival (PFS)"},
                {"name": "Overall Survival (OS)"}
            ]
        },
        "interim_analysis": None  # No interim for single-arm
    }

    print("=" * 70)
    print("ZUMA-5 LIKE PROTOCOL - DYNAMIC SAP STRUCTURE")
    print("=" * 70)

    summary = get_section_summary(zuma5_extraction)
    print(f"\nMain Sections: {summary['main_sections']}")
    print(f"Total Subsections: {summary['total_subsections']}")
    print(f"\nSpecial Sections Included:")
    for s in summary['special_sections']:
        print(f"  - {s}")

    print(f"\nConditions Detected:")
    for k, v in summary['conditions_detected'].items():
        print(f"  - {k}: {v}")

    sections = get_required_sections(zuma5_extraction)
    print("\n" + "=" * 70)
    print("SECTION OUTLINE:")
    print("=" * 70)
    print(format_section_outline(sections, include_tools=True))

    tools = get_all_kb_tools_for_sections(sections)
    print("\n" + "=" * 70)
    print("KB TOOLS TO CALL:")
    print("=" * 70)
    for tool in sorted(tools):
        print(f"  - {tool}")

    # =========================================================================
    # Example 2: Randomized Phase 3 NSCLC (like KEYNOTE-024)
    # =========================================================================
    print("\n\n" + "=" * 70)
    print("RANDOMIZED PHASE 3 NSCLC - DYNAMIC SAP STRUCTURE")
    print("=" * 70)

    phase3_nsclc = {
        "phase": {"value": "Phase 3"},
        "study_design": {"design_type": {"value": "randomized"}},
        "treatment_arms": [
            {"name": "Pembrolizumab"},
            {"name": "Platinum-based chemotherapy"}
        ],
        "stratification_factors": [
            {"name": "ECOG PS (0 vs 1)"},
            {"name": "Region (East Asia vs non-East Asia)"}
        ],
        "investigational_product": {
            "product_type": {"value": "PD-1 inhibitor"},
            "name": {"value": "Pembrolizumab"}
        },
        "disease_classification": {
            "tumor_type": {"value": "Non-Small Cell Lung Cancer"}
        },
        "endpoints": {
            "primary": [{"name": "Progression-Free Survival (PFS)"}],
            "secondary": [
                {"name": "Overall Survival (OS)"},
                {"name": "Overall Response Rate (ORR)"},
                {"name": "Duration of Response (DOR)"}
            ],
            "exploratory": [{"name": "PD-L1 biomarker analysis"}]
        },
        "interim_analysis": {"planned": True}  # Explicit interim
    }

    summary2 = get_section_summary(phase3_nsclc)
    print(f"\nMain Sections: {summary2['main_sections']}")
    print(f"Special Sections: {', '.join(summary2['special_sections'])}")
    print(f"\nKey Conditions:")
    for k in ["is_randomized", "is_phase_3", "has_interim_analysis", "has_stratification", "has_biomarker_endpoints"]:
        if summary2['conditions_detected'].get(k):
            print(f"  - {k}: True")

    # =========================================================================
    # Example 3: Single-arm Phase 2 Solid Tumor with PRO
    # =========================================================================
    print("\n\n" + "=" * 70)
    print("SINGLE-ARM PHASE 2 WITH PRO - DYNAMIC SAP STRUCTURE")
    print("=" * 70)

    phase2_pro = {
        "phase": {"value": "Phase 2"},
        "study_design": {"design_type": {"value": "single_arm"}},
        "treatment_arms": [{"name": "Drug X"}],
        "investigational_product": {
            "product_type": {"value": "Small molecule"},
            "name": {"value": "Drug X"}
        },
        "disease_classification": {
            "tumor_type": {"value": "Breast Cancer"}
        },
        "endpoints": {
            "primary": [{"name": "Overall Response Rate (ORR)"}],
            "secondary": [
                {"name": "Duration of Response (DOR)"},
                {"name": "EORTC QLQ-C30 Quality of Life"},
                {"name": "Patient-reported pain scores"}
            ]
        }
    }

    summary3 = get_section_summary(phase2_pro)
    print(f"\nMain Sections: {summary3['main_sections']}")
    print(f"Special Sections: {', '.join(summary3['special_sections'])}")
    print(f"\nKey Conditions:")
    for k in ["is_single_arm", "is_phase_2", "has_pro_endpoints", "has_interim_analysis"]:
        val = summary3['conditions_detected'].get(k, False)
        print(f"  - {k}: {val}")

    # =========================================================================
    # Summary Table
    # =========================================================================
    print("\n\n" + "=" * 70)
    print("SUMMARY: SECTION COUNTS BY STUDY TYPE")
    print("=" * 70)
    print(f"{'Study Type':<40} {'Main':<8} {'Special Sections'}")
    print("-" * 70)
    print(f"{'ZUMA-5 (CAR-T, Lymphoma, Single-arm)':<40} {summary['main_sections']:<8} {len(summary['special_sections'])} special")
    print(f"{'KEYNOTE-like (Phase 3, Randomized, IO)':<40} {summary2['main_sections']:<8} {len(summary2['special_sections'])} special")
    print(f"{'Phase 2 with PRO (Single-arm)':<40} {summary3['main_sections']:<8} {len(summary3['special_sections'])} special")
