"""ICH E3-compliant TLF numbering assignment.

Tables:  14.1.x (disposition/demographics), 14.2.x (efficacy), 14.3.x (safety)
Figures: F-14.2.x, F-14.3.x, etc.
Listings: 16.2.x
"""

# Map table types to ICH E3 sections
_TYPE_TO_SECTION = {
    # 14.1 — Disposition and Demographics
    "disposition": "14.1",
    "screening_failures": "14.1",
    "demographics": "14.1",
    "baseline": "14.1",
    "medical_history": "14.1",
    "disease_characteristics": "14.1",
    # 14.2 — Efficacy
    "efficacy_binary": "14.2",
    "efficacy_continuous": "14.2",
    "efficacy_tte": "14.2",
    "subgroup": "14.2",
    "qol": "14.2",
    # 14.3 — Safety
    "ae_overview": "14.3",
    "ae_by_soc_pt": "14.3",
    "ae_serious": "14.3",
    "ae_death": "14.3",
    "ae_discontinuation": "14.3",
    "ae_grade3plus": "14.3",
    "aesi": "14.3",
    "exposure": "14.3",
    "concomitant_medications": "14.3",
    "labs_summary": "14.3",
    "labs_shift": "14.3",
    "vitals": "14.3",
    "ecg": "14.3",
    "physical_exam": "14.3",
    "pk_parameters": "14.3",
    "pk_concentration": "14.3",
    "immunogenicity": "14.3",
}


def assign_numbers(
    tables: list[dict],
    figures: list[dict],
    listings: list[dict],
) -> None:
    """Assign ICH E3-compliant numbers to all TLF entries in-place.

    Tables get:   Table 14.1.1, Table 14.1.2, ..., Table 14.2.1, ...
    Figures get:  Figure 14.2.1, Figure 14.3.1, ...
    Listings get: Listing 16.2.1, Listing 16.2.2, ...
    """
    # --- Tables ---
    section_counters: dict[str, int] = {}
    for entry in tables:
        section = _resolve_section(entry)
        section_counters.setdefault(section, 0)
        section_counters[section] += 1
        entry["number"] = f"Table {section}.{section_counters[section]}"
        entry["section"] = section

    # --- Figures ---
    section_counters = {}
    for entry in figures:
        section = _resolve_section(entry)
        section_counters.setdefault(section, 0)
        section_counters[section] += 1
        entry["number"] = f"Figure {section}.{section_counters[section]}"
        entry["section"] = section

    # --- Listings ---
    for i, entry in enumerate(listings, start=1):
        entry["number"] = f"Listing 16.2.{i}"
        entry["section"] = "16.2"


def _resolve_section(entry: dict) -> str:
    """Determine the ICH section for an entry based on its type or existing section."""
    # If the LLM already assigned a valid section, use it
    section = entry.get("section", "")
    if section and section.startswith("14."):
        return section

    # Fall back to type-based mapping
    entry_type = entry.get("type", "")
    return _TYPE_TO_SECTION.get(entry_type, "14.3")
