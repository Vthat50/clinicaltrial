#!/usr/bin/env python3
"""
Convert INSTRUCTIONS.md files → generation_rules.yaml additions.

This script reads all INSTRUCTIONS.md files from the skills/ directory and
produces a therapeutic_area_rules.yaml that the Python engine can load
alongside the core generation_rules.yaml.

Usage:
    python convert_to_yaml.py [--output therapeutic_area_rules.yaml]

The output YAML can be loaded by the rules engine to add area-specific
mandatory/common tables on top of the global rules.

Architecture:
    INSTRUCTIONS.md (human-editable Markdown)
        ↓  this script
    therapeutic_area_rules.yaml (machine-readable)
        ↓  Python engine
    Deterministic TLF generation
"""

import argparse
import os
import re
import yaml
from collections import OrderedDict


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Reverse map: human-readable label → YAML type key
LABEL_TO_TYPE = {
    "Subject Disposition": "disposition",
    "Demographics and Baseline Characteristics": "demographics",
    "Medical History": "medical_history",
    "Disease Characteristics": "disease_characteristics",
    "Baseline Values": "baseline",
    "Prior Therapies / Anticancer Treatment": "prior_therapy",
    "Protocol Deviations": "protocol_deviations",
    "Study Drug Exposure": "exposure",
    "Concomitant Medications": "concomitant_medications",
    "Overview of TEAEs": "ae_overview",
    "TEAEs by SOC and PT": "ae_by_soc_pt",
    "Serious TEAEs by SOC and PT": "ae_serious",
    "TEAEs Grade ≥3 by SOC and PT": "ae_grade3plus",
    "TEAEs Leading to Death": "ae_death",
    "TEAEs Leading to Discontinuation": "ae_discontinuation",
    "TEAEs with Incidence ≥5%": "ae_common",
    "Adverse Events of Special Interest": "aesi",
    "Binary Efficacy Endpoint (e.g., response rate)": "efficacy_binary",
    "Continuous Efficacy Endpoint (e.g., change from baseline)": "efficacy_continuous",
    "Time-to-Event Efficacy (e.g., OS, PFS, EFS)": "efficacy_tte",
    "Subgroup Analyses": "subgroup",
    "Laboratory Parameters — Summary Statistics": "labs_summary",
    "Laboratory Parameters — Shift Tables": "labs_shift",
    "Laboratory Parameters — CTCAE Grade": "labs_ctcae",
    "Vital Signs": "vitals",
    "ECG Parameters": "ecg",
    "ECOG Performance Status": "ecog",
    "Pharmacokinetic Parameters": "pk_parameters",
    "PK Concentration — Summary Statistics": "pk_concentration",
    "Immunogenicity (ADA / NAb)": "immunogenicity",
    "Quality of Life / PRO": "qol",
    "Physical Examination": "physical_exam",
    "Pregnancy Test": "pregnancy_test",
    "Kaplan-Meier Plot": "km_plot",
    "Forest Plot (Subgroup Analysis)": "forest_plot",
    "Waterfall Plot (Tumor Response)": "waterfall_plot",
    "Swimmer Plot (Duration of Response)": "swimmer_plot",
    "Other / Study-Specific": "other",
}

# Condition expressions for conditional types
TYPE_CONDITIONS = {
    "pk_parameters": "facts.assessments_collected.pk == true",
    "pk_concentration": "facts.assessments_collected.pk == true",
    "immunogenicity": "facts.assessments_collected.immunogenicity == true",
    "qol": "facts.assessments_collected.qol | is_list_with_items",
    "ecg": "facts.assessments_collected.ecg == true",
    "ecog": "facts.assessments_collected.ecog_ps == true",
    "vitals": "facts.assessments_collected.vitals == true",
    "labs_summary": "facts.assessments_collected.labs == true",
    "labs_shift": "facts.assessments_collected.labs == true",
    "labs_ctcae": "facts.assessments_collected.labs == true",
    "physical_exam": "facts.assessments_collected.physical_exam == true",
    "pregnancy_test": "facts.assessments_collected.pregnancy_test == true",
    "aesi": "facts.aesis | length > 0",
    "subgroup": "facts.subgroups | length > 0",
}


def parse_instructions_md(filepath):
    """Parse an INSTRUCTIONS.md file and extract structured data."""
    with open(filepath) as f:
        content = f.read()

    result = {
        "therapeutic_area": None,
        "reference_saps": 0,
        "mandatory_tables": [],
        "common_tables": [],
        "conditional_tables": [],
        "figures": [],
        "area_notes": [],
    }

    # Parse YAML frontmatter
    fm_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
    if fm_match:
        fm = yaml.safe_load(fm_match.group(1))
        result["therapeutic_area"] = fm.get("therapeutic_area")
        result["reference_saps"] = fm.get("reference_saps", 0)

    # Parse table entries: "- **Label** — X/Y SAPs (Z%)"
    entry_re = re.compile(
        r'- \*\*(.+?)\*\* — (\d+)/(\d+) SAPs \((\d+)%\)(.*?)$',
        re.MULTILINE
    )

    # Determine which section each entry is in
    current_section = None
    for line in content.split("\n"):
        if "Mandatory Tables" in line:
            current_section = "mandatory"
        elif "Common Tables" in line and "40" in line:
            current_section = "common"
        elif "Conditional Tables" in line:
            current_section = "conditional"
        elif line.startswith("## Figures"):
            current_section = "figures"
        elif line.startswith("## Listings"):
            current_section = "listings"
        elif line.startswith("## Area-Specific"):
            current_section = "notes"
        elif line.startswith("## ") and current_section not in (None,):
            current_section = None

        match = entry_re.match(line)
        if match and current_section in ("mandatory", "common", "conditional", "figures"):
            label = match.group(1)
            count = int(match.group(2))
            total = int(match.group(3))
            pct = int(match.group(4))
            hint = match.group(5).strip()

            type_key = LABEL_TO_TYPE.get(label, label.lower().replace(" ", "_"))

            entry = {
                "type": type_key,
                "label": label,
                "count": count,
                "total": total,
                "pct": pct,
            }

            if current_section == "mandatory":
                result["mandatory_tables"].append(entry)
            elif current_section == "common":
                result["common_tables"].append(entry)
            elif current_section == "conditional":
                result["conditional_tables"].append(entry)
            elif current_section == "figures":
                result["figures"].append(entry)

        # Area-specific notes
        if current_section == "notes" and line.startswith("- "):
            result["area_notes"].append(line[2:].strip())

    return result


def build_yaml_rules(parsed_areas):
    """Convert parsed INSTRUCTIONS.md data into YAML rule structure."""
    rules = {
        "version": "1.0",
        "config_type": "therapeutic_area_rules",
        "description": (
            "Therapeutic-area-specific TLF rules derived from INSTRUCTIONS.md files. "
            "These supplement the core generation_rules.yaml with area-specific "
            "mandatory/common/conditional table types and clinical notes."
        ),
        "areas": {},
    }

    for area_data in parsed_areas:
        area = area_data["therapeutic_area"]
        if not area:
            continue

        area_key = area.lower()
        area_rules = {
            "reference_saps": area_data["reference_saps"],
            "notes": area_data["area_notes"],
        }

        # Mandatory: always generate for this area
        if area_data["mandatory_tables"]:
            area_rules["mandatory_table_types"] = []
            for entry in area_data["mandatory_tables"]:
                if entry["type"] == "other":
                    continue
                rule = {"type": entry["type"], "frequency": f"{entry['pct']}%"}
                area_rules["mandatory_table_types"].append(rule)

        # Common: generate when condition met (or always if no condition)
        if area_data["common_tables"]:
            area_rules["common_table_types"] = []
            for entry in area_data["common_tables"]:
                if entry["type"] == "other":
                    continue
                rule = {"type": entry["type"], "frequency": f"{entry['pct']}%"}
                if entry["type"] in TYPE_CONDITIONS:
                    rule["condition"] = TYPE_CONDITIONS[entry["type"]]
                area_rules["common_table_types"].append(rule)

        # Conditional: generate only when explicitly specified
        if area_data["conditional_tables"]:
            area_rules["conditional_table_types"] = []
            for entry in area_data["conditional_tables"]:
                if entry["type"] == "other":
                    continue
                rule = {"type": entry["type"], "frequency": f"{entry['pct']}%"}
                if entry["type"] in TYPE_CONDITIONS:
                    rule["condition"] = TYPE_CONDITIONS[entry["type"]]
                area_rules["conditional_table_types"].append(rule)

        # Figures
        if area_data["figures"]:
            area_rules["figure_types"] = []
            for entry in area_data["figures"]:
                if entry["type"] == "other":
                    continue
                rule = {"type": entry["type"], "frequency": f"{entry['pct']}%"}
                area_rules["figure_types"].append(rule)

        rules["areas"][area_key] = area_rules

    return rules


def main():
    parser = argparse.ArgumentParser(description="Convert INSTRUCTIONS.md → YAML rules")
    parser.add_argument(
        "--output", "-o",
        default=os.path.join(SCRIPT_DIR, "..", "core", "therapeutic_area_rules.yaml"),
        help="Output YAML file path"
    )
    args = parser.parse_args()

    # Find all INSTRUCTIONS.md files
    parsed = []
    for area_dir in sorted(os.listdir(SCRIPT_DIR)):
        instr_path = os.path.join(SCRIPT_DIR, area_dir, "INSTRUCTIONS.md")
        if os.path.isfile(instr_path):
            print(f"  Parsing {area_dir}/INSTRUCTIONS.md")
            data = parse_instructions_md(instr_path)
            parsed.append(data)

    if not parsed:
        print("No INSTRUCTIONS.md files found!")
        return

    # Build YAML
    rules = build_yaml_rules(parsed)

    # Write
    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Custom YAML representer for clean output
    class CleanDumper(yaml.SafeDumper):
        pass

    def str_representer(dumper, data):
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    CleanDumper.add_representer(str, str_representer)

    with open(output_path, "w") as f:
        f.write("# =============================================================================\n")
        f.write("# THERAPEUTIC AREA RULES (auto-generated from INSTRUCTIONS.md files)\n")
        f.write("# =============================================================================\n")
        f.write("# DO NOT EDIT DIRECTLY. Edit the INSTRUCTIONS.md files in skills/\n")
        f.write("# and re-run: python skills/convert_to_yaml.py\n")
        f.write("# =============================================================================\n\n")
        yaml.dump(rules, f, Dumper=CleanDumper, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"\n  Written: {output_path}")
    print(f"  Areas: {len(rules['areas'])}")
    for area_key, area_rules in rules["areas"].items():
        m = len(area_rules.get("mandatory_table_types", []))
        c = len(area_rules.get("common_table_types", []))
        d = len(area_rules.get("conditional_table_types", []))
        fig = len(area_rules.get("figure_types", []))
        print(f"    {area_key}: {m} mandatory, {c} common, {d} conditional, {fig} figures")


if __name__ == "__main__":
    main()
