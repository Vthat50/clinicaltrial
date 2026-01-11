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
        subsections=[
            SAPSection("3.1", "Overall Design", required=True),
            SAPSection("3.2", "Treatment Arms", required=True,
                      condition="has_multiple_arms"),
            SAPSection("3.3", "Randomization", required=False,
                      condition="is_randomized",
                      kb_tools=["get_stratification_specs"]),
            SAPSection("3.4", "Blinding", required=False,
                      condition="is_blinded"),
            SAPSection("3.5", "Stratification Factors", required=False,
                      condition="has_stratification",
                      kb_tools=["get_stratification_specs"]),
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
    # ENDPOINTS & ESTIMANDS
    # -------------------------------------------------------------------------
    SAPSection(
        number="6",
        title="ENDPOINTS & ESTIMANDS",
        required=True,
        description="Primary, secondary, exploratory endpoints with ICH E9(R1) estimands",
        kb_tools=["get_estimand_framework", "get_oncology_tfl_templates"],
        subsections=[
            SAPSection("6.1", "Primary Endpoint(s)", required=True),
            SAPSection("6.2", "Secondary Endpoint(s)", required=True),
            SAPSection("6.3", "Exploratory Endpoint(s)", required=False,
                      condition="has_exploratory_endpoints"),
            SAPSection("6.4", "Estimand Framework", required=True,
                      description="ICH E9(R1) estimands for each endpoint"),
            # CAR-T specific endpoints
            SAPSection("6.5", "Retreatment Endpoints (DORR)", required=False,
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
            SAPSection("7.1", "General Considerations", required=True),
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
                      kb_tools=["get_multiplicity_adjustment"]),
            # Single-arm specific
            SAPSection("7.6", "Single-Arm Response Rate Analysis", required=False,
                      condition="is_single_arm",
                      description="Clopper-Pearson CI, Simon two-stage",
                      kb_tools=["get_single_arm_tables"]),
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
        kb_tools=["get_sensitivity_analysis"],
        subsections=[
            SAPSection("10.1", "Primary Endpoint Sensitivity Analyses", required=True),
            SAPSection("10.2", "Per-Protocol Analysis", required=True),
            SAPSection("10.3", "Tipping Point Analysis", required=False,
                      condition="has_missing_data_concerns"),
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
        kb_tools=["get_subgroup_analysis_specs"],
        subsections=[
            SAPSection("11.1", "Pre-specified Subgroups", required=True),
            SAPSection("11.2", "Subgroup Analysis Methods", required=True),
            SAPSection("11.3", "Forest Plot Specifications", required=False,
                      condition="is_randomized"),
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
        kb_tools=["get_safety_analysis_specs", "get_safety_tables", "get_safety_specifications"],
        subsections=[
            SAPSection("12.1", "Adverse Events", required=True),
            SAPSection("12.2", "Laboratory Parameters", required=True),
            SAPSection("12.3", "Vital Signs", required=True),
            SAPSection("12.4", "ECG Parameters", required=False,
                      condition="has_ecg_monitoring"),
            SAPSection("12.5", "Exposure Analysis", required=True),
            # CAR-T specific safety
            SAPSection("12.6", "Cytokine Release Syndrome (CRS)", required=False,
                      condition="is_cart",
                      kb_tools=["get_cart_specifications", "get_cart_tables"]),
            SAPSection("12.7", "Immune Effector Cell-Associated Neurotoxicity (ICANS)", required=False,
                      condition="is_cart",
                      kb_tools=["get_cart_specifications", "get_cart_tables"]),
            SAPSection("12.8", "CAR-T Cellular Kinetics", required=False,
                      condition="is_cart",
                      kb_tools=["get_cart_specifications"]),
            SAPSection("12.9", "Prolonged Cytopenias", required=False,
                      condition="is_cart"),
            SAPSection("12.10", "B-Cell Aplasia & Hypogammaglobulinemia", required=False,
                      condition="is_cart"),
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
        kb_tools=["get_interim_analysis"],
        subsections=[
            SAPSection("13.1", "Timing and Information Fractions", required=True),
            SAPSection("13.2", "Alpha Spending Function", required=True),
            SAPSection("13.3", "Stopping Boundaries", required=True),
            SAPSection("13.4", "DMC Charter Reference", required=True),
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
        kb_tools=["get_pro_qol_analysis"],
        subsections=[
            SAPSection("15.1", "PRO Instruments", required=True),
            SAPSection("15.2", "Scoring Algorithms", required=True),
            SAPSection("15.3", "Missing PRO Data Handling", required=True),
            SAPSection("15.4", "PRO Analysis Methods", required=True),
        ]
    ),

    # -------------------------------------------------------------------------
    # PROGRAMMING SPECIFICATIONS
    # -------------------------------------------------------------------------
    SAPSection(
        number="16",
        title="PROGRAMMING SPECIFICATIONS",
        required=True,
        description="Analysis windows, visit definitions, derived variables",
        kb_tools=["get_programming_specifications", "get_derived_variables", "get_analysis_windows"],
        subsections=[
            SAPSection("16.1", "Analysis Windows", required=True),
            SAPSection("16.2", "Baseline Definitions", required=True),
            SAPSection("16.3", "Derived Variable Specifications", required=True),
            SAPSection("16.4", "Data Cutoff Rules", required=True,
                      kb_tools=["get_data_cutoff_specs"]),
        ]
    ),

    # -------------------------------------------------------------------------
    # TFL SHELLS
    # -------------------------------------------------------------------------
    SAPSection(
        number="17",
        title="TABLE, FIGURE, AND LISTING SHELLS",
        required=True,
        description="Complete TFL inventory with shells",
        kb_tools=["get_disposition_tables", "get_efficacy_tables", "get_safety_tables",
                  "get_tfl_shells", "get_all_figures", "get_listings"],
        subsections=[
            SAPSection("17.1", "Disposition Tables", required=True,
                      kb_tools=["get_disposition_tables", "get_single_arm_tables"]),
            SAPSection("17.2", "Demographics and Baseline Tables", required=True,
                      kb_tools=["get_lymphoma_tables"]),
            SAPSection("17.3", "Efficacy Tables", required=True,
                      kb_tools=["get_efficacy_tables"]),
            SAPSection("17.4", "Safety Tables", required=True,
                      kb_tools=["get_safety_tables", "get_cart_tables"]),
            SAPSection("17.5", "Figures", required=True,
                      kb_tools=["get_all_figures"]),
            SAPSection("17.6", "Listings", required=True,
                      kb_tools=["get_listings"]),
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
            SAPSection("A.1", "Date Imputation Algorithm", required=True),
            SAPSection("A.2", "Time-to-Event Derivation Rules", required=False,
                      condition="has_tte_endpoints",
                      description="Circumstance tables for each TTE endpoint"),
            SAPSection("A.3", "MedDRA Search Strategies", required=False,
                      condition="is_cart",
                      description="SMQ, MST for CRS, ICANS, infections",
                      kb_tools=["get_cart_specifications"]),
            SAPSection("A.4", "Response Criteria Reference", required=False,
                      condition="has_response_endpoint",
                      kb_tools=["get_response_criteria", "get_recist_specifications"]),
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
    endpoint_str = " ".join([str(e) for e in all_endpoints]).lower()

    conditions["has_tte_endpoints"] = any(x in endpoint_str for x in ["survival", "pfs", "efs", "dfs", "rfs", "ttp", "duration"])
    conditions["has_pfs_endpoint"] = "pfs" in endpoint_str or "progression-free" in endpoint_str
    conditions["has_os_endpoint"] = " os " in endpoint_str or "overall survival" in endpoint_str
    conditions["has_dor_endpoint"] = "dor" in endpoint_str or "duration of response" in endpoint_str
    conditions["has_efs_endpoint"] = "efs" in endpoint_str or "event-free" in endpoint_str
    conditions["has_response_endpoint"] = any(x in endpoint_str for x in ["orr", "response rate", "cr", "pr", "objective response"])
    conditions["has_continuous_endpoints"] = any(x in endpoint_str for x in ["change from baseline", "cfb", "mean", "qol", "pro"])
    conditions["has_exploratory_endpoints"] = len(exploratory) > 0
    conditions["has_multiple_primary_endpoints"] = len(primary) > 1
    conditions["has_biomarker_endpoints"] = any(x in endpoint_str for x in ["biomarker", "pd-l1", "tmb", "msi", "ctdna", "mrd"])
    conditions["has_pro_endpoints"] = any(x in endpoint_str for x in ["qol", "quality of life", "pro", "patient-reported", "eortc", "fact", "sf-36"])
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

    # Disease Conditions
    disease = protocol_extraction.get("disease_classification", {})
    tumor_type = (disease.get("tumor_type", {}).get("value") or "").lower() if disease else ""

    conditions["is_lymphoma"] = any(x in tumor_type for x in ["lymphoma", "nhl", "dlbcl", "follicular", "mantle"])
    conditions["is_hematologic"] = any(x in tumor_type for x in ["lymphoma", "leukemia", "myeloma", "hematologic"])
    conditions["is_solid_tumor"] = not conditions["is_hematologic"] and tumor_type != ""

    # Study Features
    conditions["has_interim_analysis"] = protocol_extraction.get("interim_analysis") is not None
    conditions["has_ecg_monitoring"] = True  # Assume yes for most oncology trials
    conditions["has_missing_data_concerns"] = True  # Always include sensitivity analyses

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
    # Example: ZUMA-5 like protocol
    zuma5_extraction = {
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
