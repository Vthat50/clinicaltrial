#!/usr/bin/env python3
"""
Convert TLF SKILL.md files → SKILL.yaml structured rules.

Reads each SKILL.md from the tlf_skills/ directory and produces a
SKILL.yaml that the generic Python engine can load and execute.

Usage:
    python convert_skills_to_yaml.py

Architecture:
    SKILL.md (human-editable plain English)
        ↓  this script
    SKILL.yaml (machine-readable structured rules)
        ↓  tlf_skills.py generic engine
    Deterministic TLF shell generation

The SKILL.md files are the source of truth. Edit them, re-run this script,
and the runtime engine picks up the changes. No Python code changes needed.
"""

import argparse
import os
import re
import yaml
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent

# ─────────────────────────────────────────────────────────────────────────────
# TABLE TYPE MAPPING: title keywords → YAML type key
# ─────────────────────────────────────────────────────────────────────────────
# The engine uses these type keys to determine formatting (categorical vs
# continuous), ICH section numbers, and column layouts.

TITLE_TO_TYPE = {
    # 14.1
    "Subject Disposition": "disposition",
    "Protocol Deviations": "protocol_deviations",
    "Demographics and Baseline Characteristics": "demographics",
    "Medical History": "medical_history",
    "Prior and Concomitant Therapies": "prior_therapy",
    "Biomarker and Genomic Screening": "demographics",
    "Disease Characteristics": "disease_characteristics",
    # 14.3 — Labs
    "Hematology Parameters - Summary Statistics": "labs_hematology",
    "Clinical Chemistry Parameters - Summary Statistics": "labs_chemistry",
    "Urinalysis Parameters - Summary Statistics": "labs_urinalysis",
    "Hematology Parameters - Shift Table": "lab_shift",
    "Clinical Chemistry Parameters - Shift Table": "lab_shift",
    "Laboratory Parameters - CTCAE Grade Summary": "labs",
    "Laboratory Parameters - CTCAE Grade Shift": "lab_shift",
    "Subjects with Markedly Abnormal Laboratory Values": "labs",
    "Liver Function Tests - Summary Statistics": "labs_liver",
    "Potential Hy's Law Cases": "labs_liver",
    "Coagulation Parameters - Summary Statistics": "labs",
    "Thyroid Function Tests - Summary Statistics": "labs",
    # 14.3 — Vitals / ECG
    "Vital Signs - Summary Statistics by Visit": "vitals",
    "Vital Signs - Change from Baseline by Visit": "vitals",
    "Subjects with Markedly Abnormal Vital Sign Values": "vitals",
    "Electrocardiogram Parameters - Summary by Visit": "ecg",
    "Electrocardiogram - Qualitative Results": "ecg",
    "QTcF Change from Baseline - Categorical Analysis": "ecg",
    # 14.3 — AE
    "Overview of Treatment-Emergent Adverse Events": "ae_overview",
    "TEAEs by SOC and PT": "ae_by_soc_pt",
    "Treatment-Related TEAEs by SOC and PT": "ae_by_soc_pt",
    "TEAEs Grade >=3 by SOC and PT": "ae_by_soc_pt",
    "Serious TEAEs by SOC and PT": "ae_by_soc_pt",
    "TEAEs Leading to Discontinuation of Study Treatment": "ae_by_soc_pt",
    "TEAEs Leading to Death": "ae_by_soc_pt",
    "TEAEs Leading to Dose Modification": "ae_by_soc_pt",
    "TEAEs with Incidence >=5% in Any Treatment Group": "ae_by_soc_pt",
    "TEAEs by SOC, PT, and Maximum Severity": "ae_by_severity",
    "TEAEs Related to Study Drug": "ae_by_soc_pt",
    "TEAEs Related to Study Drug Grade >=3": "ae_by_soc_pt",
    "Dose Reductions": "dose_modification",
    "Dose Interruptions": "dose_modification",
    # 14.3 — Exposure
    "Study Drug Exposure": "exposure",
    "Concomitant Medications": "concomitant_medications",
    # Biosimilar
    "Tipping Point Analysis": "sensitivity_analysis",
    "Equivalence / Biosimilarity Margins Summary": "other",
    "Salvage Treatment by Category": "prior_therapy",
    "Salvage Treatment": "prior_therapy",
    "Prior Cancer Therapy": "prior_therapy",
    # 14.3 — Other
    "Physical Examination - Shift Table": "labs",
    "ECOG Performance Status by Visit": "labs",
    "ECOG Performance Status - Shift Table": "lab_shift",
    "Pregnancy Test Summary": "labs",
    "Viral Serology": "labs",
    # 14.4
    "Plasma Drug Concentration": "pk_concentration",
    "PK Parameters - Summary Statistics": "pk_parameters",
    "Immunogenicity - Anti-Drug Antibody Incidence": "immunogenicity",
    "Immunogenicity - Neutralizing Antibody Status": "immunogenicity",
    "TEAEs by ADA Status": "ae_by_soc_pt",
}

# Condition strings for "When X is collected" sections
CONDITION_PATTERNS = {
    "laboratory data is collected": "facts.assessments_collected.labs == true",
    "labs": "facts.assessments_collected.labs == true",
    "liver function monitoring is collected": "facts.assessments_collected.liver_function == true",
    "liver function": "facts.assessments_collected.liver_function == true",
    "coagulation is collected": "facts.assessments_collected.coagulation == true",
    "coagulation": "facts.assessments_collected.coagulation == true",
    "thyroid function is collected": "facts.assessments_collected.thyroid == true",
    "thyroid": "facts.assessments_collected.thyroid == true",
    "vital signs are collected": "facts.assessments_collected.vitals == true",
    "vital signs": "facts.assessments_collected.vitals == true",
    "ecg is collected": "facts.assessments_collected.ecg == true",
    "ecg": "facts.assessments_collected.ecg == true",
    "pk samples are collected": "facts.assessments_collected.pk == true",
    "pk data is collected": "facts.assessments_collected.pk == true",
    "pk": "facts.assessments_collected.pk == true",
    "immunogenicity is assessed": "facts.assessments_collected.immunogenicity == true",
    "immunogenicity": "facts.assessments_collected.immunogenicity == true",
    "qol instruments are specified": "facts.assessments_collected.qol | is_list_with_items",
    "qol": "facts.assessments_collected.qol | is_list_with_items",
    "physical exam is collected": "facts.assessments_collected.physical_exam == true",
    "physical exam": "facts.assessments_collected.physical_exam == true",
    "ecog ps is assessed": "facts.assessments_collected.ecog_ps == true",
    "ecog": "facts.assessments_collected.ecog_ps == true",
    "pregnancy test is collected": "facts.assessments_collected.pregnancy_test == true",
    "pregnancy": "facts.assessments_collected.pregnancy_test == true",
    "viral serology is collected": "facts.assessments_collected.viral_serology == true",
    "viral serology": "facts.assessments_collected.viral_serology == true",
    "gene/biomarker screening is collected": "facts.assessments_collected.gene_screening == true",
    "gene": "facts.assessments_collected.gene_screening == true",
    "dose modifications are collected": "facts.assessments_collected.dose_modifications == true",
    "dose modification": "facts.assessments_collected.dose_modifications == true",
    "biosimilar or equivalence": "facts.study_design.type in [biosimilar, equivalence]",
    "biosimilar": "facts.study_design.type in [biosimilar, equivalence]",
    "biosimilar/equivalence and therapeutic area is oncology": "facts.study_design.type in [biosimilar, equivalence] and facts.therapeutic_area == oncology",
    "biosimilar oncology": "facts.study_design.type in [biosimilar, equivalence] and facts.therapeutic_area == oncology",
    "subgroups are pre-specified": "facts.subgroups | length > 0",
    "subgroups": "facts.subgroups | length > 0",
    "more than one treatment period": "facts.treatment_periods | length > 1",
    "randomized studies": "facts.study_design.type in [superiority, non_inferiority, equivalence, biosimilar]",
}


def guess_type(title: str) -> str:
    """Guess the YAML type key from a table title."""
    # Exact match first
    for pattern, ttype in TITLE_TO_TYPE.items():
        if pattern.lower() in title.lower():
            return ttype
    # Fallback
    return "other"


def guess_condition(section_header: str) -> str:
    """Extract a condition expression from a section header like 'When laboratory data is collected'."""
    header_lower = section_header.lower()
    # Try longest match first
    for pattern in sorted(CONDITION_PATTERNS.keys(), key=len, reverse=True):
        if pattern in header_lower:
            return CONDITION_PATTERNS[pattern]
    return ""


def parse_population(text: str) -> str:
    """Extract population from text like 'ITT population' or '— Safety population'."""
    pop_match = re.search(r'(\w+)\s+population', text, re.IGNORECASE)
    if pop_match:
        return pop_match.group(1)
    if "All Screened" in text:
        return "All Screened"
    if "All Enrolled" in text:
        return "All Enrolled"
    if "PK" in text:
        return "PK"
    return "Safety"


def parse_columns(text: str) -> list:
    """Extract column list from text like 'Columns: Subject ID, Treatment, ...'."""
    col_match = re.search(r'Columns?:\s*(.+)', text)
    if col_match:
        return [c.strip() for c in col_match.group(1).split(",")]
    return []


def parse_skill_md(filepath: Path) -> dict:
    """Parse a SKILL.md file into structured data."""
    content = filepath.read_text()

    # Parse YAML frontmatter
    fm = {}
    fm_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
    if fm_match:
        fm = yaml.safe_load(fm_match.group(1)) or {}

    result = {
        "name": fm.get("name", ""),
        "description": fm.get("description", ""),
        "ich_section": fm.get("ich_section", ""),
        "display_order": fm.get("display_order", 99),
        "version": fm.get("version", "1.0.0"),
        "tables": [],
        "figures": [],
        "listings": [],
        # Special sections (endpoint_tables, aesi_tables, etc.)
        "_has_endpoint_tables": False,
        "_endpoint_filter": "",
        "_has_aesi": False,
        "_has_subgroup": False,
        "_has_period_split": False,
        "_has_backbone": False,
        "_has_for_each_qol": False,
    }

    # Detect special skill types from content + frontmatter name
    skill_name_lower = fm.get("name", "").lower()

    # Figures skill — detected by name, NOT by endpoint keywords
    if skill_name_lower == "figures" or "figures" in fm.get("description", "").lower() and "km plot" in content.lower():
        result["_is_figures_skill"] = True

    # Endpoint tables — only for primary/secondary efficacy skills
    elif "primary efficacy" in skill_name_lower:
        result["_has_endpoint_tables"] = True
        result["_endpoint_filter"] = "endpoint.primary == true"
    elif "secondary efficacy" in skill_name_lower:
        result["_has_endpoint_tables"] = True
        result["_endpoint_filter"] = "endpoint.primary != true"

    # Subgroup — detected by name
    if "subgroup" in skill_name_lower:
        result["_has_subgroup"] = True
        result["_has_endpoint_tables"] = False  # override
    # AESI
    if "for each aesi" in content.lower() or "aesi" in skill_name_lower:
        result["_has_aesi"] = True
    # Period split
    if "for each treatment period" in content.lower() or "period-split" in skill_name_lower:
        result["_has_period_split"] = True
    # Backbone
    if "for each backbone therapy" in content.lower() or "backbone" in skill_name_lower:
        result["_has_backbone"] = True
    # QoL for_each
    if "for each qol instrument" in content.lower() or "for each instrument" in content.lower():
        result["_has_for_each_qol"] = True

    # Parse table/figure/listing entries from markdown
    current_condition = ""
    current_section = None  # "tables", "figures", "listings"
    current_population = "Safety"

    for line in content.split("\n"):
        stripped = line.strip()

        # Detect section type
        if re.match(r'^#{1,3}\s+Tables?\b', stripped, re.IGNORECASE):
            current_section = "tables"
        elif re.match(r'^#{1,3}\s+Figures?\b', stripped, re.IGNORECASE):
            current_section = "figures"
        elif re.match(r'^#{1,3}\s+Listings?\b', stripped, re.IGNORECASE):
            current_section = "listings"
        elif re.match(r'^#{1,3}\s+How Tables', stripped, re.IGNORECASE):
            current_section = "meta"
        elif re.match(r'^#{1,3}\s+Title Format', stripped, re.IGNORECASE):
            current_section = "meta"
        elif re.match(r'^#{1,3}\s+Analysis Method', stripped, re.IGNORECASE):
            current_section = "meta"
        elif re.match(r'^#{1,3}\s+Footnotes', stripped, re.IGNORECASE):
            current_section = "meta"
        elif re.match(r'^#{1,3}\s+When Included', stripped, re.IGNORECASE):
            current_section = "meta"
        elif re.match(r'^#{1,3}\s+What a Subgroup', stripped, re.IGNORECASE):
            current_section = "meta"

        # Detect condition from headers like "## Tables — When Laboratory Data Is Collected"
        # or "## Conditional Tables — Dose Modifications"
        # or "## Conditional Tables — Biosimilar / Equivalence Studies"
        header_match = re.match(r'^#{1,4}\s+(.+)', stripped)
        if header_match:
            header_text = header_match.group(1)
            cond = guess_condition(header_text)
            if cond:
                current_condition = cond
            elif "always included" in header_text.lower() or "mandatory" in header_text.lower():
                current_condition = ""

            # Population from header
            pop = parse_population(header_text)
            if pop:
                current_population = pop

        # Parse bullet items: "- **Title** — Population. ..."
        bullet_match = re.match(r'^- \*\*(.+?)\*\*(?:\s*[—–-]\s*(.+))?', stripped)
        if bullet_match and current_section in ("tables", "figures", "listings", None):
            title = bullet_match.group(1).strip()
            rest = bullet_match.group(2) or ""

            # Determine population
            pop = parse_population(rest) if rest else current_population

            # Determine type
            ttype = guess_type(title)

            if current_section == "listings" or ("listing" in title.lower() and current_section != "figures"):
                # Parse columns
                columns = parse_columns(rest)
                entry = {
                    "title": title,
                    "population": pop,
                }
                if columns:
                    entry["columns"] = columns
                if current_condition:
                    entry["condition"] = current_condition
                result["listings"].append(entry)
            elif current_section == "figures":
                entry = {
                    "type": ttype,
                    "title": title,
                }
                if current_condition:
                    entry["condition"] = current_condition
                result["figures"].append(entry)
            else:
                entry = {
                    "type": ttype,
                    "title": title,
                    "population": pop,
                }
                if current_condition:
                    entry["condition"] = current_condition
                result["tables"].append(entry)

        # Also handle non-bold bullet items in listings with "Listing of" prefix
        listing_bullet = re.match(r'^- Listing of (.+?)(?:\s*[—–-]\s*(.+))?$', stripped)
        if listing_bullet and current_section == "listings":
            title = listing_bullet.group(1).strip()
            rest = listing_bullet.group(2) or ""
            pop = parse_population(rest) if rest else current_population
            columns = parse_columns(rest)
            entry = {"title": title, "population": pop}
            if columns:
                entry["columns"] = columns
            if current_condition:
                entry["condition"] = current_condition
            result["listings"].append(entry)

    return result


def build_skill_yaml(parsed: dict) -> dict:
    """Convert parsed SKILL.md data into SKILL.yaml structure."""
    skill = {
        "name": parsed["name"],
        "description": parsed["description"],
        "ich_section": parsed["ich_section"],
        "display_order": parsed["display_order"],
        "version": parsed["version"],
    }

    # ── Figures skill — uses figure_rules from generation_rules.yaml ──
    if parsed.get("_is_figures_skill"):
        # The figures skill is special — it references figure_rules from generation_rules.yaml
        # We store figure definitions parsed from the SKILL.md
        skill["figure_rules"] = []

        # Parse the figures from the tables list (they were parsed as tables)
        # and from any figures list
        all_figs = parsed.get("tables", []) + parsed.get("figures", [])
        for fig in all_figs:
            entry = {
                "type": guess_type(fig["title"]),
                "title_pattern": fig["title"],
            }
            if fig.get("condition"):
                entry["global_condition"] = fig["condition"]
            # Detect for_each patterns
            title_lower = fig["title"].lower()
            if "endpoint" in title_lower or "{endpoint" in title_lower:
                entry["for_each"] = "facts.endpoints"
                entry["endpoint_field"] = "endpoint.name"
            if "instrument" in title_lower or "{instrument" in title_lower:
                entry["for_each"] = "facts.assessments_collected.qol"
            skill["figure_rules"].append(entry)

        return skill

    # ── Endpoint tables (primary/secondary efficacy) ──
    if parsed["_has_endpoint_tables"]:
        skill["endpoint_tables"] = {
            "filter": parsed["_endpoint_filter"],
            "type_mapping": {
                "time_to_event": "time_to_event",
                "binary": "binary_response",
                "continuous": "continuous_endpoint",
                "count": "continuous_endpoint",
                "ordinal": "continuous_endpoint",
                "rate": "continuous_endpoint",
            },
            "title_pattern": "{endpoint.name} ({population} Population)",
            "title_with_review_pattern": "{endpoint.name} ({review} Review) ({population} Population)",
            "generate_footnotes": True,
        }
        return skill

    # ── AESI tables ──
    if parsed["_has_aesi"]:
        skill["aesi_tables"] = {
            "for_each": "facts.aesis",
            "type": "ae_special",
            "title_pattern": "AESI - {aesi.name}",
            "population": "Safety",
            "extra_rows_from": "aesi.definition",
        }
        return skill

    # ── Subgroup tables ──
    if parsed["_has_subgroup"]:
        skill["subgroup_tables"] = {
            "for_each": "facts.endpoints",
            "condition": "endpoint.primary == true or endpoint.key_secondary == true",
            "global_condition": "facts.subgroups | length > 0",
            "type": "subgroup_forest",
            "title_pattern": "Subgroup Analysis of {endpoint.name}",
            "population": "ITT",
        }
        return skill

    # ── Period-split tables ──
    if parsed["_has_period_split"]:
        # Group tables by condition
        tables_list = []
        for tbl in parsed["tables"]:
            t = {
                "type": tbl["type"],
                "title_pattern": tbl["title"],
                "population": tbl["population"],
            }
            if tbl.get("condition"):
                t["condition"] = tbl["condition"]
            tables_list.append(t)

        skill["period_split_tables"] = {
            "condition": "facts.treatment_periods | length > 1",
            "for_each": "facts.treatment_periods",
            "tables": tables_list,
        }
        return skill

    # ── Backbone therapy ──
    if parsed["_has_backbone"]:
        skill["backbone_therapy_tables"] = {
            "for_each": "facts.backbone_therapies",
            "type": "exposure",
            "title_pattern": "{therapy.drug_name} Exposure",
            "population": "Safety",
        }
        if parsed["listings"]:
            skill["backbone_therapy_listings"] = {
                "listings": []
            }
            for lst in parsed["listings"]:
                entry = {
                    "title": lst["title"],
                    "population": lst["population"],
                }
                if lst.get("columns"):
                    entry["columns"] = lst["columns"]
                skill["backbone_therapy_listings"]["listings"].append(entry)
        return skill

    # ── QoL / PRO with for_each instrument (only for the dedicated QoL skill) ──
    if parsed["_has_for_each_qol"] and not parsed["tables"] and "quality" in parsed["name"].lower():
        # QoL skill has {Instrument Name} patterns that don't parse as regular tables
        skill["tables"] = [{
            "condition": "facts.assessments_collected.qol | is_list_with_items",
            "for_each": "facts.assessments_collected.qol",
            "items": [
                {"type": "pro_qol", "title": "{instrument} - Summary by Visit", "population": "ITT"},
                {"type": "pro_qol", "title": "{instrument} - Change from Baseline", "population": "ITT"},
            ],
        }]
        return skill

    # ── Standard tables/figures/listings (grouped by condition) ──
    if parsed["tables"]:
        # Group tables by condition
        groups = {}
        for tbl in parsed["tables"]:
            cond = tbl.get("condition", "")
            if cond not in groups:
                groups[cond] = []
            groups[cond].append(tbl)

        skill["tables"] = []
        for cond, tbls in groups.items():
            group = {"items": []}
            if cond:
                group["condition"] = cond
            # Check if any table has for_each QoL
            if parsed["_has_for_each_qol"] and "qol" in cond.lower():
                group["for_each"] = "facts.assessments_collected.qol"
            for tbl in tbls:
                item = {
                    "type": tbl["type"],
                    "title": tbl["title"],
                    "population": tbl["population"],
                }
                group["items"].append(item)
            skill["tables"].append(group)

    # ── Figures ──
    if parsed["figures"]:
        skill["figures"] = []
        for fig in parsed["figures"]:
            entry = {
                "type": fig["type"],
                "title": fig["title"],
            }
            if fig.get("condition"):
                entry["condition"] = fig["condition"]
            skill["figures"].append(entry)

    # ── Listings ──
    if parsed["listings"]:
        # Group listings by condition
        groups = {}
        for lst in parsed["listings"]:
            cond = lst.get("condition", "")
            if cond not in groups:
                groups[cond] = []
            groups[cond].append(lst)

        skill["listings"] = []
        for cond, lsts in groups.items():
            group = {"items": []}
            if cond:
                group["condition"] = cond
            # Check for QoL for_each
            if parsed["_has_for_each_qol"] and "qol" in cond.lower():
                group["for_each"] = "facts.assessments_collected.qol"
            for lst in lsts:
                item = {
                    "title": lst["title"],
                    "population": lst["population"],
                }
                if lst.get("columns"):
                    item["columns"] = lst["columns"]
                group["items"].append(item)
            skill["listings"].append(group)

    return skill


def main():
    parser = argparse.ArgumentParser(description="Convert SKILL.md → SKILL.yaml for TLF skills")
    parser.add_argument("--skill", "-s", help="Convert only this skill (directory name)", default=None)
    args = parser.parse_args()

    converted = 0
    for skill_dir in sorted(SCRIPT_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        if args.skill and skill_dir.name != args.skill:
            continue

        print(f"  Converting {skill_dir.name}/SKILL.md → SKILL.yaml")

        parsed = parse_skill_md(skill_md)
        skill_yaml = build_skill_yaml(parsed)

        # Write SKILL.yaml
        output_path = skill_dir / "SKILL.yaml"

        class CleanDumper(yaml.SafeDumper):
            pass

        def str_representer(dumper, data):
            if "\n" in data:
                return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
            return dumper.represent_scalar("tag:yaml.org,2002:str", data)

        CleanDumper.add_representer(str, str_representer)

        with open(output_path, "w") as f:
            f.write(f"# Auto-generated from {skill_dir.name}/SKILL.md\n")
            f.write("# DO NOT EDIT DIRECTLY. Edit SKILL.md and re-run:\n")
            f.write("#   python convert_skills_to_yaml.py\n\n")
            yaml.dump(skill_yaml, f, Dumper=CleanDumper, default_flow_style=False, sort_keys=False, allow_unicode=True)

        # Count outputs
        tc = sum(len(g.get("items", [])) for g in skill_yaml.get("tables", []))
        fc = len(skill_yaml.get("figures", []))
        lc = sum(len(g.get("items", [])) for g in skill_yaml.get("listings", []))
        # Special types
        for key in ("endpoint_tables", "aesi_tables", "subgroup_tables", "period_split_tables", "backbone_therapy_tables"):
            if key in skill_yaml:
                tc = f"dynamic ({key})"
                break

        print(f"    → {output_path.name}: tables={tc}, figures={fc}, listings={lc}")
        converted += 1

    print(f"\n  Converted {converted} skills")


if __name__ == "__main__":
    main()
