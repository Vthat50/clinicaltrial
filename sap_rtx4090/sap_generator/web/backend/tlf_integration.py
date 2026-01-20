"""
TLF Shell Integration Module
=============================
Bridges the modular TLF shell system with SAP generation.

Detects study type from protocol extraction and generates appropriate TLF shells.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add specs directory to path for TLF generator
SPECS_DIR = Path(__file__).parent.parent.parent / "enterprise_sap_system" / "specs"
sys.path.insert(0, str(SPECS_DIR))

try:
    from tlf_config_generator_v2 import TLFConfigGeneratorV2, StudyConfig
    TLF_GENERATOR_AVAILABLE = True
    print("[TLF Integration] TLF Generator v2 loaded successfully")
except ImportError as e:
    TLF_GENERATOR_AVAILABLE = False
    print(f"[TLF Integration] TLF Generator not available: {e}")


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


def generate_tlf_shells_for_protocol(
    extraction: Dict[str, Any],
    study_id: Optional[str] = None,
    priority: Optional[int] = None
) -> str:
    """
    Generate TLF shells for a protocol based on its extraction.

    Args:
        extraction: Protocol extraction from KG pipeline
        study_id: Optional study ID for lookup (e.g., "ct_p16")
        priority: Optional priority level (1, 2, or 3)

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
            return generator.generate_study_document(study_id.lower(), priority=priority)

        # Auto-detect study type and generate dynamic config
        study_type = detect_study_type(extraction)
        drug_classes = detect_drug_class(extraction)
        study_design = detect_study_design(extraction)

        print(f"[TLF Integration] Detected: type={study_type}, drugs={drug_classes}, design={study_design}")

        # Get treatment arms from extraction
        treatment_arms = {}
        arms = extraction.get("treatment_arms", [])
        for i, arm in enumerate(arms):
            arm_name = arm.get("arm_name", f"Arm {i+1}")
            arm_type = arm.get("arm_type", "experimental")
            treatment_arms[arm_name] = arm_type

        if not treatment_arms:
            treatment_arms = {"Study Drug": "experimental", "Control": "comparator"}

        # Create study config
        study_title = extraction.get("trial_identification", {}).get("study_title", "Protocol Study")
        indication = extraction.get("disease_classification", {}).get("indication", "Oncology")

        config = StudyConfig(
            study_id=study_id or "dynamic_study",
            study_type=study_type,
            indication=indication,
            drug_class=drug_classes,
            study_design=study_design,
            treatment_arms=treatment_arms,
            review_types=["central", "local"] if study_type == "biosimilar" else ["central"],
            populations=["ITT", "PP", "Safety"]
        )

        # Generate shells from config
        # Note: generate_from_study_config doesn't support priority filtering
        # Priority is only for predefined study configs (generate_study_document)
        return generator.generate_from_study_config(config)

    except Exception as e:
        print(f"[TLF Integration] Error generating shells: {e}")
        import traceback
        traceback.print_exc()
        return _generate_fallback_shells(extraction)


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


def get_tlf_shell_summary(extraction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a summary of what TLF shells would be generated for a protocol.
    """
    study_type = detect_study_type(extraction)
    drug_classes = detect_drug_class(extraction)
    study_design = detect_study_design(extraction)

    return {
        "detected_study_type": study_type,
        "detected_drug_classes": drug_classes,
        "detected_study_design": study_design,
        "generator_available": TLF_GENERATOR_AVAILABLE,
    }
