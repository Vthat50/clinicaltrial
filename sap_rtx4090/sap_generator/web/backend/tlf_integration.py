"""
TLF Shell Integration Module v2
================================
Bridges the modular TLF shell system with SAP generation.

v2 Features:
- Universal shell generator with automatic expansion
- Period stratification (Induction/Maintenance/Follow-up)
- Population × Assessment matrix (ITT/PP × IRC/Local)
- Region-aware demographics (Race/Ethnicity for FDA)
- Auto-detected PK/Immunogenicity tables

Detects study type from protocol extraction and generates appropriate TLF shells.
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Add specs directory to path for TLF generator
SPECS_DIR = Path(__file__).parent.parent.parent / "enterprise_sap_system" / "specs"
TLF_CONFIGS_DIR = SPECS_DIR / "tlf_configs"
sys.path.insert(0, str(SPECS_DIR))
sys.path.insert(0, str(TLF_CONFIGS_DIR))

try:
    from tlf_config_generator_v2 import TLFConfigGeneratorV2, StudyConfig
    TLF_GENERATOR_AVAILABLE = True
    print("[TLF Integration] TLF Generator v2 loaded successfully")
except ImportError as e:
    TLF_GENERATOR_AVAILABLE = False
    print(f"[TLF Integration] TLF Generator not available: {e}")

# Try to load universal shell generator
try:
    from universal_shell_generator import UniversalShellGenerator, calculate_table_multiplier
    UNIVERSAL_GENERATOR_AVAILABLE = True
    print("[TLF Integration] Universal Shell Generator loaded successfully")
except ImportError as e:
    UNIVERSAL_GENERATOR_AVAILABLE = False
    print(f"[TLF Integration] Universal Shell Generator not available: {e}")


def detect_study_type(extraction: Dict[str, Any]) -> str:
    """
    Detect study type from protocol extraction.

    Returns: biosimilar, immuno_oncology, or targeted_therapy
    """
    if not extraction:
        return "biosimilar"  # Default

    # Check for biosimilar indicators
    study_title = extraction.get("trial_identification", {}).get("study_title", "").lower()
    study_design = extraction.get("study_design", {})
    immunotherapy = extraction.get("immunotherapy_specific", {})

    # Biosimilar detection
    biosimilar_keywords = ["biosimilar", "reference product", "avastin", "herceptin", "rituximab"]
    if any(kw in study_title for kw in biosimilar_keywords):
        return "biosimilar"

    # Immuno-oncology detection
    io_keywords = ["pembrolizumab", "nivolumab", "atezolizumab", "durvalumab", "ipilimumab",
                   "pd-1", "pd-l1", "ctla-4", "checkpoint", "immunotherapy"]
    if any(kw in study_title for kw in io_keywords):
        return "immuno_oncology"
    if immunotherapy.get("is_immunotherapy"):
        return "immuno_oncology"

    # Targeted therapy detection
    targeted_keywords = ["tki", "inhibitor", "osimertinib", "erlotinib", "gefitinib",
                        "crizotinib", "alectinib", "olaparib", "palbociclib"]
    if any(kw in study_title for kw in targeted_keywords):
        return "targeted_therapy"

    # Default to biosimilar for oncology studies
    return "biosimilar"


def detect_drug_class(extraction: Dict[str, Any]) -> List[str]:
    """
    Detect drug class for AESI selection from protocol extraction.
    """
    if not extraction:
        return ["anti_vegf"]  # Default

    study_title = extraction.get("trial_identification", {}).get("study_title", "").lower()

    drug_classes = []

    # Anti-VEGF (bevacizumab, etc.)
    if any(kw in study_title for kw in ["avastin", "bevacizumab", "vegf"]):
        drug_classes.append("anti_vegf")

    # Checkpoint inhibitors
    if any(kw in study_title for kw in ["pembrolizumab", "nivolumab", "atezolizumab",
                                         "durvalumab", "ipilimumab", "pd-1", "pd-l1"]):
        drug_classes.append("checkpoint_inhibitor")

    # EGFR inhibitors
    if any(kw in study_title for kw in ["osimertinib", "erlotinib", "gefitinib", "egfr"]):
        drug_classes.append("egfr_inhibitor")

    # ALK/ROS1 inhibitors
    if any(kw in study_title for kw in ["crizotinib", "alectinib", "lorlatinib", "alk"]):
        drug_classes.append("alk_ros1_inhibitor")

    # HER2 inhibitors
    if any(kw in study_title for kw in ["trastuzumab", "herceptin", "her2"]):
        drug_classes.append("her2_inhibitor")

    # PARP inhibitors
    if any(kw in study_title for kw in ["olaparib", "niraparib", "rucaparib", "parp"]):
        drug_classes.append("parp_inhibitor")

    # Cytotoxic chemo (common combinations)
    if any(kw in study_title for kw in ["paclitaxel", "carboplatin", "cisplatin", "docetaxel"]):
        drug_classes.append("cytotoxic_chemotherapy")

    return drug_classes if drug_classes else ["anti_vegf"]


def detect_study_design(extraction: Dict[str, Any]) -> str:
    """
    Detect study design pattern from protocol extraction.
    """
    if not extraction:
        return "continuous"

    study_title = extraction.get("trial_identification", {}).get("study_title", "").lower()
    study_design = extraction.get("study_design", {})

    # Check for induction-maintenance pattern
    if "induction" in study_title or "maintenance" in study_title:
        return "induction_maintenance"

    # Check for adjuvant
    if "adjuvant" in study_title:
        return "adjuvant"

    # Check for neoadjuvant
    if "neoadjuvant" in study_title:
        return "neoadjuvant"

    # Check for perioperative
    if "perioperative" in study_title:
        return "perioperative"

    # Check for crossover
    design_type = study_design.get("design_type", "").lower()
    if "crossover" in design_type:
        return "crossover"

    # Check for dose escalation
    if "dose-escalation" in study_title or "dose escalation" in study_title:
        return "dose_escalation"

    # Check for single arm
    if "single-arm" in study_title or "single arm" in study_title:
        return "single_arm"

    return "continuous"


# =============================================================================
# UNIVERSAL SHELL GENERATOR DETECTION FUNCTIONS
# =============================================================================

def detect_period_stratification(extraction: Dict[str, Any], protocol_text: str = "") -> Tuple[bool, str]:
    """
    Detect if study requires period stratification (Induction/Maintenance/Follow-up).

    Returns:
        Tuple of (requires_stratification, period_config_name)
    """
    if not extraction and not protocol_text:
        return False, "single_period"

    # Combine sources for keyword search
    study_title = extraction.get("trial_identification", {}).get("study_title", "").lower() if extraction else ""
    full_text = (study_title + " " + protocol_text).lower()

    # Strong indicators for induction-maintenance
    induction_maintenance_patterns = [
        r"induction\s+(?:and|phase|period|study)",
        r"maintenance\s+(?:phase|period|treatment|therapy)",
        r"induction.*maintenance",
        r"followed\s+by\s+maintenance",
        r"continue.*maintenance.*until\s+(?:progression|pd)",
    ]

    for pattern in induction_maintenance_patterns:
        if re.search(pattern, full_text):
            return True, "induction_maintenance"

    # Adjuvant indicators
    if re.search(r"\badjuvant\b", full_text) and not re.search(r"\bneoadjuvant\b", full_text):
        return True, "adjuvant"

    # Neoadjuvant/perioperative
    if re.search(r"\bneoadjuvant\b", full_text) or re.search(r"\bperioperative\b", full_text):
        return True, "perioperative"

    # Crossover
    if re.search(r"\bcrossover\b|\bcross-over\b", full_text):
        return True, "crossover"

    # Check for explicit period mentions in protocol text
    if protocol_text:
        period_mentions = [
            "whole study period",
            "induction study period",
            "maintenance study period",
            "follow-up period",
            "by study period",
            "each period",
        ]
        if any(mention in full_text for mention in period_mentions):
            return True, "induction_maintenance"

    return False, "single_period"


def detect_study_regions(extraction: Dict[str, Any], protocol_text: str = "") -> List[str]:
    """
    Detect study regions from protocol extraction.

    Returns:
        List of region identifiers (e.g., ["united_states", "europe", "asia_pacific"])
    """
    regions = []

    if not extraction and not protocol_text:
        return ["global"]  # Default to global

    # Check trial identification
    trial_id = extraction.get("trial_identification", {}) if extraction else {}
    sponsor_country = trial_id.get("sponsor_country", "").lower()

    # Check for explicit country/region mentions
    full_text = protocol_text.lower() if protocol_text else ""

    # US indicators
    us_patterns = ["united states", "usa", "us sites", "fda", "ind number", "nct"]
    if any(p in full_text or p in sponsor_country for p in us_patterns):
        regions.append("united_states")

    # EU indicators
    eu_patterns = ["european union", "europe", "eu sites", "ema", "eudract"]
    if any(p in full_text for p in eu_patterns):
        regions.append("europe")

    # Japan indicators
    japan_patterns = ["japan", "pmda", "japanese"]
    if any(p in full_text for p in japan_patterns):
        regions.append("japan")

    # Asia-Pacific
    apac_patterns = ["asia-pacific", "apac", "korea", "taiwan", "china", "australia"]
    if any(p in full_text for p in apac_patterns):
        regions.append("asia_pacific")

    # If nothing detected, default to global
    if not regions:
        regions = ["global"]

    return regions


def detect_pk_immunogenicity_required(extraction: Dict[str, Any], study_type: str) -> Tuple[bool, bool]:
    """
    Detect if PK and immunogenicity analyses are required.

    Returns:
        Tuple of (pk_required, immunogenicity_required)
    """
    # Biosimilars always need PK and immunogenicity
    if study_type == "biosimilar":
        return True, True

    if not extraction:
        return False, False

    study_title = extraction.get("trial_identification", {}).get("study_title", "").lower()

    # Check for biologic drugs (need immunogenicity)
    biologic_keywords = [
        "mab", "umab", "zumab", "ximab",  # Monoclonal antibodies
        "trastuzumab", "bevacizumab", "rituximab", "pembrolizumab", "nivolumab",
        "atezolizumab", "durvalumab", "ipilimumab", "cetuximab",
        "biosimilar", "biologic", "monoclonal",
    ]

    is_biologic = any(kw in study_title for kw in biologic_keywords)

    # ADCs need special PK (multiple analytes)
    adc_keywords = ["adc", "antibody-drug conjugate", "t-dxd", "t-dm1", "enhertu"]
    is_adc = any(kw in study_title for kw in adc_keywords)

    # PK is common for most studies with new drugs
    pk_required = is_biologic or is_adc or study_type in ["biosimilar", "dose_escalation"]

    # Immunogenicity for biologics
    immunogenicity_required = is_biologic or is_adc

    return pk_required, immunogenicity_required


def detect_assessment_types(extraction: Dict[str, Any], study_type: str) -> List[str]:
    """
    Detect which assessment types (IRC/Local) are needed.

    Returns:
        List of assessment types needed (e.g., ["irc", "local"])
    """
    # Biosimilars need both IRC and Local for comparison
    if study_type == "biosimilar":
        return ["irc", "local"]

    # Most oncology studies need IRC as primary, local as sensitivity
    if study_type in ["immuno_oncology", "targeted_therapy"]:
        return ["irc", "local"]

    # Single arm studies often just use IRC
    if study_type == "single_arm":
        return ["irc"]

    # Default
    return ["irc"]


def detect_efficacy_populations(extraction: Dict[str, Any], study_type: str) -> List[str]:
    """
    Detect which populations are needed for efficacy analyses.

    Returns:
        List of population IDs (e.g., ["itt", "pp", "mitt"])
    """
    populations = ["itt"]  # ITT is always included

    # PP for all confirmatory studies
    if study_type in ["biosimilar", "immuno_oncology", "targeted_therapy"]:
        populations.append("pp")

    # Biomarker populations for targeted therapy
    if study_type == "targeted_therapy":
        populations.append("biomarker_positive")

    # mITT/Evaluable for response-based endpoints
    if study_type in ["immuno_oncology", "single_arm"]:
        populations.append("evaluable")

    return populations


def build_universal_config(extraction: Dict[str, Any], protocol_text: str = "") -> Dict[str, Any]:
    """
    Build a complete configuration for the universal shell generator.

    Args:
        extraction: Protocol extraction from KG pipeline
        protocol_text: Full protocol text for additional detection

    Returns:
        Dictionary configuration for UniversalShellGenerator
    """
    # Base detection
    study_type = detect_study_type(extraction)
    drug_classes = detect_drug_class(extraction)
    study_design = detect_study_design(extraction)

    # Universal generator-specific detection
    requires_period_strat, period_config = detect_period_stratification(extraction, protocol_text)
    regions = detect_study_regions(extraction, protocol_text)
    pk_required, immuno_required = detect_pk_immunogenicity_required(extraction, study_type)
    assessment_types = detect_assessment_types(extraction, study_type)
    efficacy_populations = detect_efficacy_populations(extraction, study_type)

    # Get study info
    trial_id = extraction.get("trial_identification", {}) if extraction else {}
    study_id = trial_id.get("protocol_number", "STUDY-001")
    indication = extraction.get("disease_classification", {}).get("indication", "Oncology") if extraction else "Oncology"

    # Build config
    config = {
        "study_config": {
            "study_id": study_id,
            "study_type": study_type,
            "indication": indication,
            "phase": trial_id.get("phase", "III"),
            "regions": regions,
            "drug_classes": drug_classes,
            "study_design": study_design,
            "period_config": period_config,
            "require_period_stratification": requires_period_strat,
            "include_pk_immunogenicity": pk_required or immuno_required,
            "efficacy_populations": efficacy_populations,
            "efficacy_assessments": assessment_types,
            "treatment_arms": extraction.get("treatment_arms", []) if extraction else [],
            "stratification_factors": extraction.get("stratification_factors", []) if extraction else [],
            "populations": [
                {"code": "ITT", "name": "Intent-to-Treat", "flag": "ITTFL"},
                {"code": "Safety", "name": "Safety Population", "flag": "SAFFL"},
                {"code": "PP", "name": "Per-Protocol", "flag": "PPROTFL"},
            ],
        },
        "endpoints": extraction.get("endpoints", {}) if extraction else {},
    }

    return config


def calculate_expected_table_count(extraction: Dict[str, Any], protocol_text: str = "") -> Dict[str, Any]:
    """
    Calculate the expected number of tables after expansion.

    Returns:
        Dictionary with table counts by category and total
    """
    config = build_universal_config(extraction, protocol_text)
    study_config = config["study_config"]

    # Period multiplier
    period_mult = 1
    if study_config["require_period_stratification"]:
        if study_config["period_config"] == "induction_maintenance":
            period_mult = 4  # Whole, Induction, Maintenance, Follow-up
        elif study_config["period_config"] in ["perioperative", "adjuvant"]:
            period_mult = 3
        elif study_config["period_config"] == "crossover":
            period_mult = 2

    # Population × Assessment multiplier
    pop_count = len(study_config.get("efficacy_populations", ["itt"]))
    assess_count = len(study_config.get("efficacy_assessments", ["irc"]))
    efficacy_mult = pop_count * assess_count

    # Base table counts (typical for oncology)
    base_counts = {
        "Demographics": 1,
        "Disposition": 1,
        "Disease Characteristics": 1,
        "Medical History": 1,
        "Prior Medications": 1,
        "Primary Efficacy": 2,  # ORR, PFS or similar
        "Secondary Efficacy": 3,  # DOR, OS, etc.
        "Subgroup Analysis": 2,
        "Safety Overview": 1,
        "TEAEs by SOC/PT": 2,
        "AESIs": 1,
        "SAEs": 1,
        "Laboratory": 3,  # Actual, Change, Shift
        "Vital Signs": 1,
        "Exposure": 1,
    }

    # Apply multipliers
    expanded_counts = {}
    total = 0

    for category, base_count in base_counts.items():
        if category in ["Safety Overview", "TEAEs by SOC/PT", "AESIs", "SAEs", "Laboratory", "Vital Signs", "Exposure"]:
            count = base_count * period_mult
        elif "Efficacy" in category or "Subgroup" in category:
            count = base_count * efficacy_mult
        else:
            count = base_count

        expanded_counts[category] = count
        total += count

    # Add PK/Immunogenicity if required
    if study_config.get("include_pk_immunogenicity"):
        pk_immuno_count = 7  # Typical PK + ADA tables
        expanded_counts["PK/Immunogenicity"] = pk_immuno_count
        total += pk_immuno_count

    return {
        "total_tables": total,
        "by_category": expanded_counts,
        "multipliers": {
            "period": period_mult,
            "efficacy_population_assessment": efficacy_mult,
        },
        "config_summary": {
            "period_stratification": study_config["require_period_stratification"],
            "period_config": study_config["period_config"],
            "regions": study_config["regions"],
            "pk_immunogenicity": study_config.get("include_pk_immunogenicity", False),
        }
    }


def generate_tlf_shells_for_protocol(
    extraction: Dict[str, Any],
    study_id: Optional[str] = None,
    priority: Optional[int] = None,
    protocol_text: str = "",
    apply_universal_expansion: bool = True
) -> str:
    """
    Generate TLF shells for a protocol based on its extraction.

    v2: Now applies universal shell expansion including:
    - Period stratification (Induction/Maintenance/Follow-up)
    - Population × Assessment matrix (ITT/PP × IRC/Local)
    - Region-aware demographics
    - PK/Immunogenicity tables

    Args:
        extraction: Protocol extraction from KG pipeline
        study_id: Optional study ID for lookup (e.g., "ct_p16")
        priority: Optional priority level (1, 2, or 3)
        protocol_text: Full protocol text for enhanced detection
        apply_universal_expansion: Whether to apply period/population expansion

    Returns:
        Markdown string with TLF shells
    """
    if not TLF_GENERATOR_AVAILABLE:
        return _generate_fallback_shells(extraction)

    try:
        generator = TLFConfigGeneratorV2()

        # Check if we have a predefined study config
        available_studies = generator.list_available_studies()

        if study_id and study_id.lower() in [s.lower() for s in available_studies]:
            # Use predefined study config
            print(f"[TLF Integration] Using predefined study: {study_id}")
            base_shells = generator.generate_study_document(study_id.lower(), priority=priority)

            # Apply universal expansion if enabled
            if apply_universal_expansion:
                return _apply_universal_expansion(base_shells, extraction, protocol_text)
            return base_shells

        # Build universal config for auto-detection
        universal_config = build_universal_config(extraction, protocol_text)
        study_config_dict = universal_config["study_config"]

        # Log detection results
        print(f"[TLF Integration v2] Detected configuration:")
        print(f"  Study type: {study_config_dict['study_type']}")
        print(f"  Period stratification: {study_config_dict['require_period_stratification']} ({study_config_dict['period_config']})")
        print(f"  Regions: {study_config_dict['regions']}")
        print(f"  PK/Immunogenicity: {study_config_dict.get('include_pk_immunogenicity', False)}")
        print(f"  Efficacy populations: {study_config_dict.get('efficacy_populations', ['itt'])}")
        print(f"  Assessments: {study_config_dict.get('efficacy_assessments', ['irc'])}")

        # Calculate expected table count
        expected = calculate_expected_table_count(extraction, protocol_text)
        print(f"  Expected tables: {expected['total_tables']} (period mult: {expected['multipliers']['period']}×, efficacy mult: {expected['multipliers']['efficacy_population_assessment']}×)")

        # Get treatment arms from extraction
        treatment_arms = {}
        arms = extraction.get("treatment_arms", [])
        for i, arm in enumerate(arms):
            arm_name = arm.get("arm_name", f"Arm {i+1}")
            arm_type = arm.get("arm_type", "experimental")
            treatment_arms[arm_name] = arm_type

        if not treatment_arms:
            treatment_arms = {"Study Drug": "experimental", "Control": "comparator"}

        # Create study config for base generator
        study_title = extraction.get("trial_identification", {}).get("study_title", "Protocol Study")
        indication = extraction.get("disease_classification", {}).get("indication", "Oncology")

        config = StudyConfig(
            study_id=study_id or "dynamic_study",
            study_type=study_config_dict["study_type"],
            indication=indication,
            drug_class=study_config_dict.get("drug_classes", ["anti_vegf"]),
            study_design=study_config_dict.get("study_design", "continuous"),
            treatment_arms=treatment_arms,
            review_types=study_config_dict.get("efficacy_assessments", ["central"]),
            populations=["ITT", "PP", "Safety"]
        )

        # Generate base shells
        base_shells = generator.generate_from_study_config(config)

        # Apply universal expansion
        if apply_universal_expansion:
            return _apply_universal_expansion(
                base_shells,
                extraction,
                protocol_text,
                universal_config=universal_config
            )

        return base_shells

    except Exception as e:
        print(f"[TLF Integration] Error generating shells: {e}")
        import traceback
        traceback.print_exc()
        return _generate_fallback_shells(extraction)


def _apply_universal_expansion(
    base_shells: str,
    extraction: Dict[str, Any],
    protocol_text: str = "",
    universal_config: Optional[Dict] = None
) -> str:
    """
    Apply universal expansion to base shells.

    This adds:
    - Period-specific versions of safety/lab tables
    - Population × Assessment versions of efficacy tables
    - Region-appropriate demographics
    - PK/Immunogenicity tables if needed
    """
    if not universal_config:
        universal_config = build_universal_config(extraction, protocol_text)

    study_config = universal_config["study_config"]

    # Start with base shells
    result_parts = [base_shells]

    # Add expansion header
    expansion_notes = []

    # 1. Period Stratification Note
    if study_config["require_period_stratification"]:
        period_config = study_config["period_config"]
        if period_config == "induction_maintenance":
            periods = ["Whole Study", "Induction", "Maintenance", "Follow-up"]
        elif period_config == "perioperative":
            periods = ["Whole Study", "Neoadjuvant", "Surgery", "Adjuvant"]
        elif period_config == "adjuvant":
            periods = ["Whole Study", "On-Treatment", "Post-Treatment"]
        elif period_config == "crossover":
            periods = ["Pre-Crossover", "Post-Crossover"]
        else:
            periods = ["Whole Study"]

        expansion_notes.append(f"""
---

## PERIOD STRATIFICATION NOTE

**This study requires tables stratified by study period.**

The following safety and laboratory tables should be produced for EACH period:
- {', '.join(periods)}

Tables requiring period stratification:
- Overview of Treatment-Emergent Adverse Events
- TEAEs by System Organ Class and Preferred Term
- Adverse Events of Special Interest
- Serious Adverse Events
- Laboratory Actual Values and Change from Baseline
- Vital Signs Summary
- Treatment Exposure

**Total table multiplier: {len(periods)}×**

Example naming convention:
- Table 14.3.1: Overview of TEAEs (Whole Study Period)
- Table 14.3.1a: Overview of TEAEs (Induction Study Period)
- Table 14.3.1b: Overview of TEAEs (Maintenance Study Period)
- Table 14.3.1c: Overview of TEAEs (Follow-up Period)
""")

    # 2. Population × Assessment Matrix Note
    efficacy_pops = study_config.get("efficacy_populations", ["itt"])
    assessments = study_config.get("efficacy_assessments", ["irc"])

    if len(efficacy_pops) > 1 or len(assessments) > 1:
        pop_names = {
            "itt": "ITT Population",
            "pp": "Per-Protocol Population",
            "evaluable": "Evaluable Population",
            "biomarker_positive": "Biomarker-Positive Population",
        }
        assess_names = {
            "irc": "IRC Assessment",
            "local": "Investigator Assessment",
        }

        combinations = []
        for pop in efficacy_pops:
            for assess in assessments:
                pop_name = pop_names.get(pop, pop.upper())
                assess_name = assess_names.get(assess, assess.upper())
                combinations.append(f"  - {pop_name}, {assess_name}")

        expansion_notes.append(f"""
---

## POPULATION × ASSESSMENT MATRIX NOTE

**Efficacy tables should be produced for the following combinations:**

{chr(10).join(combinations)}

**Total efficacy table multiplier: {len(efficacy_pops)}× populations × {len(assessments)}× assessments = {len(efficacy_pops) * len(assessments)}×**

Tables requiring matrix expansion:
- Best Overall Response
- Objective Response Rate
- Progression-Free Survival
- Overall Survival
- Duration of Response
- Subgroup Analyses
""")

    # 3. Region-Aware Demographics Note
    regions = study_config.get("regions", ["global"])
    if "united_states" in regions or "global" in regions:
        expansion_notes.append(f"""
---

## REGION-AWARE DEMOGRAPHICS NOTE

**Study regions detected: {', '.join(regions)}**

Based on regulatory requirements, demographics should include:

**Core Variables (Always):**
- Age (continuous and categorical: <65, ≥65, <75, ≥75)
- Sex
- Weight, Height, BMI, BSA

**Region-Specific Variables:**
- Race (required for FDA/US submissions)
- Ethnicity (required for FDA/US submissions)
- Note: Include "Not Allowed by Country Regulations" category for EU sites

**Indication-Specific Variables:**
{_get_indication_specific_vars(study_config.get("indication", ""))}

**Female Subjects:**
- Fertility Status (required for all studies with female subjects)
""")

    # 4. PK/Immunogenicity Note
    if study_config.get("include_pk_immunogenicity"):
        expansion_notes.append(f"""
---

## PK/IMMUNOGENICITY TABLES NOTE

**This study requires PK and/or immunogenicity analyses.**

### Pharmacokinetic Tables:
- Table 14.4.1.1: Summary of PK Parameters (Cmax, Ctrough, AUC)
- Table 14.4.1.2: Serum Concentrations by Visit
- Table 14.4.2.1: PK Parameters by ADA Status

### Immunogenicity Tables:
- Table 14.4.3.1: Anti-Drug Antibody (ADA) Incidence Summary
  - Baseline ADA status
  - Post-baseline ADA status
  - Treatment-emergent ADA (induced + boosted)
  - Transient vs Persistent
  - Neutralizing Antibody (NAb) status
- Table 14.4.3.2: ADA Titer Summary
- Table 14.4.3.3: Efficacy by ADA Status
- Table 14.4.3.4: Safety by ADA Status

### Populations:
- PK Population: Subjects with ≥1 evaluable PK sample
- Immunogenicity Population: Subjects with ≥1 post-baseline ADA sample
""")

    # Combine all parts
    if expansion_notes:
        result_parts.append("\n\n# UNIVERSAL SHELL EXPANSION REQUIREMENTS\n")
        result_parts.append("*The following sections describe additional tables required based on protocol analysis.*\n")
        result_parts.extend(expansion_notes)

        # Add summary
        expected = calculate_expected_table_count(extraction, protocol_text)
        result_parts.append(f"""
---

## TOTAL TABLE COUNT SUMMARY

| Category | Base Count | Multiplier | Expanded Count |
|----------|------------|------------|----------------|
| Demographics/Disposition | 5 | 1× | 5 |
| Primary Efficacy | 2 | {expected['multipliers']['efficacy_population_assessment']}× | {2 * expected['multipliers']['efficacy_population_assessment']} |
| Secondary Efficacy | 3 | {expected['multipliers']['efficacy_population_assessment']}× | {3 * expected['multipliers']['efficacy_population_assessment']} |
| Safety Overview | 1 | {expected['multipliers']['period']}× | {expected['multipliers']['period']} |
| TEAEs by SOC/PT | 2 | {expected['multipliers']['period']}× | {2 * expected['multipliers']['period']} |
| AESIs | 1 | {expected['multipliers']['period']}× | {expected['multipliers']['period']} |
| Laboratory | 3 | {expected['multipliers']['period']}× | {3 * expected['multipliers']['period']} |
| PK/Immunogenicity | {'7' if study_config.get('include_pk_immunogenicity') else '0'} | 1× | {'7' if study_config.get('include_pk_immunogenicity') else '0'} |
| **TOTAL** | ~20 | - | **~{expected['total_tables']}** |

*Note: Actual count may vary based on study-specific requirements.*
""")

    return "\n".join(result_parts)


def _get_indication_specific_vars(indication: str) -> str:
    """Get indication-specific demographic variables."""
    indication_lower = indication.lower()

    vars_list = []

    if any(kw in indication_lower for kw in ["lung", "nsclc", "sclc"]):
        vars_list.append("- Smoking History (Never/Former/Current)")
        vars_list.append("- Pack-Years (for smokers)")

    if any(kw in indication_lower for kw in ["liver", "hepato", "hcc"]):
        vars_list.append("- Alcohol Use History")
        vars_list.append("- Hepatitis Status (B/C)")

    if any(kw in indication_lower for kw in ["breast", "ovarian", "endometrial"]):
        vars_list.append("- Menopausal Status")
        vars_list.append("- Hormone Receptor Status")

    if not vars_list:
        vars_list.append("- ECOG Performance Status (0, 1, 2)")

    return "\n".join(vars_list)


def _generate_fallback_shells(extraction: Dict[str, Any]) -> str:
    """
    Generate basic TLF shells when generator is not available.
    """
    arms = extraction.get("treatment_arms", []) if extraction else []
    if len(arms) >= 2:
        arm1 = arms[0].get("arm_name", "Treatment")
        arm2 = arms[1].get("arm_name", "Control")
    else:
        arm1 = "Treatment"
        arm2 = "Control"

    return f"""## TABLE AND FIGURE SHELLS

### Table 14.1.1: Subject Disposition

| Category | {arm1} (N=xxx) | {arm2} (N=xxx) | Total (N=xxx) |
|----------|----------------|----------------|---------------|
| Screened | xxx | xxx | xxx |
| Screen Failures | xxx | xxx | xxx |
| Randomized | xxx | xxx | xxx |
| Treated | xxx | xxx | xxx |
| Completed Treatment | xxx | xxx | xxx |
| Discontinued | xxx | xxx | xxx |

### Table 14.2.1: Primary Efficacy Analysis

| Parameter | {arm1} (N=xxx) | {arm2} (N=xxx) |
|-----------|----------------|----------------|
| Responders, n (%) | xxx (xx.x) | xxx (xx.x) |
| Non-responders, n (%) | xxx (xx.x) | xxx (xx.x) |
| Difference [95% CI] | xx.x [xx.x, xx.x] | -- |
| P-value | x.xxxx | -- |

### Table 14.3.1: Overview of Adverse Events

| Category | {arm1} (N=xxx) n (%) | {arm2} (N=xxx) n (%) |
|----------|----------------------|----------------------|
| Any TEAE | xxx (xx.x) | xxx (xx.x) |
| Treatment-related TEAE | xxx (xx.x) | xxx (xx.x) |
| Grade ≥3 TEAE | xxx (xx.x) | xxx (xx.x) |
| Serious AE | xxx (xx.x) | xxx (xx.x) |
| TEAE Leading to D/C | xxx (xx.x) | xxx (xx.x) |
| Deaths | xxx (xx.x) | xxx (xx.x) |

*Note: Additional TLF shells available with full TLF configuration system.*
"""


def get_tlf_shell_summary(extraction: Dict[str, Any], protocol_text: str = "") -> Dict[str, Any]:
    """
    Get a comprehensive summary of TLF shells including universal expansion info.

    Returns:
        Dictionary with detection results and expected table counts
    """
    # Basic detection
    study_type = detect_study_type(extraction)
    drug_classes = detect_drug_class(extraction)
    study_design = detect_study_design(extraction)

    # Universal expansion detection
    requires_period_strat, period_config = detect_period_stratification(extraction, protocol_text)
    regions = detect_study_regions(extraction, protocol_text)
    pk_required, immuno_required = detect_pk_immunogenicity_required(extraction, study_type)
    assessment_types = detect_assessment_types(extraction, study_type)
    efficacy_populations = detect_efficacy_populations(extraction, study_type)

    # Calculate expected tables
    expected_counts = calculate_expected_table_count(extraction, protocol_text)

    return {
        "detected_study_type": study_type,
        "detected_drug_classes": drug_classes,
        "detected_study_design": study_design,
        "generator_available": TLF_GENERATOR_AVAILABLE,
        "universal_generator_available": UNIVERSAL_GENERATOR_AVAILABLE,
        "universal_expansion": {
            "period_stratification": {
                "required": requires_period_strat,
                "config": period_config,
                "multiplier": expected_counts["multipliers"]["period"],
            },
            "population_assessment_matrix": {
                "populations": efficacy_populations,
                "assessments": assessment_types,
                "multiplier": expected_counts["multipliers"]["efficacy_population_assessment"],
            },
            "regions": regions,
            "pk_required": pk_required,
            "immunogenicity_required": immuno_required,
        },
        "expected_table_count": expected_counts["total_tables"],
        "table_counts_by_category": expected_counts["by_category"],
    }
