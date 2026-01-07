#!/usr/bin/env python3
"""
Protocol → SAP Section Mapping
==============================

Based on analysis of real protocol/SAP pairs from:
- NCT03558139, NCT01515748, NCT02129205, NCT03422848, etc.

This mapping tells us which protocol section(s) contain the information
needed to generate each SAP section.

TWO EXTRACTION METHODS:
1. Header-based: Find sections by their headers (e.g., "Sample Size")
2. Content-based: Search full text for patterns (e.g., "RECIST", "interim analysis")
"""

import re
from typing import Optional, List, Tuple


# =============================================================================
# CONTENT-BASED EXTRACTION PATTERNS
# =============================================================================
# For sections that may not have explicit headers, search by content patterns

SECTION_CONTENT_PATTERNS = {
    "efficacy_analysis": [
        r"response.*(?:assess|evaluat|criteria)",
        r"(?:primary|secondary).*endpoint.*(?:will|shall).*(?:be\s+)?(?:analy[zs]ed|evaluated)",
        r"RECIST",
        r"tumor.*(?:assessment|response|evaluation)",
        r"(?:complete|partial)\s+response",
        r"(?:ORR|DCR|DOR|CBR)",  # Response rate acronyms
    ],
    "interim_analysis": [
        r"interim.*analysis",
        r"(?:early|interim).*stopping",
        r"(?:futility|efficacy).*bound",
        r"alpha.*spend",
        r"(?:Lan-DeMets|O'Brien-Fleming|Pocock)",
        r"(?:IDMC|DMC|DSMB).*(?:review|meeting)",
        r"group\s+sequential",
    ],
    "missing_data": [
        r"missing.*(?:data|values?)",
        r"(?:censor|censoring)",
        r"(?:imputation|imputed)",
        r"(?:LOCF|BOCF|MMRM)",  # Imputation methods
        r"lost.*follow.*up",
        r"(?:MAR|MCAR|MNAR)",  # Missing data mechanisms
        r"(?:discontinu|withdraw).*(?:handl|treat)",
    ],
    "sensitivity_analysis": [
        r"sensitivity.*analysis",
        r"(?:tipping.*point)",
        r"(?:robust|alternative).*(?:method|analysis)",
        r"per.?protocol.*analysis",
        r"supportive.*analysis",
    ],
    "subgroup_analysis": [
        r"subgroup.*analysis",
        r"(?:pre-?specified|exploratory).*subgroup",
        r"forest.*plot",
        r"(?:by|stratified\s+by).*(?:age|sex|gender|region|race)",
        r"interaction.*(?:test|term)",
    ],
    "multiplicity": [
        r"multiplic",
        r"(?:type\s+I|alpha).*(?:control|adjust|error)",
        r"(?:familywise|FWER)",
        r"(?:hierarchical|gatekeeping|fallback).*(?:test|procedure)",
        r"(?:Bonferroni|Hochberg|Holm)",
    ],
}


def extract_section_by_content(full_text: str, section_name: str) -> Optional[str]:
    """
    Extract content for a section by searching for relevant patterns.
    Used when header-based extraction doesn't find a dedicated section.

    Args:
        full_text: Full protocol text
        section_name: SAP section to extract

    Returns:
        Extracted paragraphs containing relevant content, or None
    """
    patterns = SECTION_CONTENT_PATTERNS.get(section_name, [])
    if not patterns:
        return None

    # Split into paragraphs
    paragraphs = re.split(r'\n\s*\n', full_text)
    relevant_paragraphs = []
    seen_content = set()  # Avoid duplicates

    for para in paragraphs:
        para = para.strip()
        if len(para) < 50:  # Skip very short paragraphs
            continue

        # Check if paragraph matches any pattern
        for pattern in patterns:
            if re.search(pattern, para, re.IGNORECASE):
                # Avoid duplicates
                para_key = para[:100]
                if para_key not in seen_content:
                    relevant_paragraphs.append(para)
                    seen_content.add(para_key)
                break

    if relevant_paragraphs:
        return '\n\n'.join(relevant_paragraphs)
    return None

# =============================================================================
# PROTOCOL SECTION → SAP SECTION MAPPING
# =============================================================================
# Key: SAP section name (what we're generating)
# Value: List of protocol section names to look for (in priority order)

PROTOCOL_TO_SAP_MAPPING = {
    # ---------------------------------------------------------------------
    # ADMINISTRATIVE / INTRO
    # ---------------------------------------------------------------------
    "introduction": [
        "introduction",
        "background",
        "background and rationale",
        "study background",
        "theoretical background",
        "clinical trial outline",
        "protocol synopsis",
        "study synopsis",
    ],

    # ---------------------------------------------------------------------
    # OBJECTIVES & ENDPOINTS
    # ---------------------------------------------------------------------
    "objectives": [
        "study objectives",
        "objectives",
        "primary objective",
        "secondary objectives",
        "objectives and endpoints",
        "study objectives and endpoints",
    ],

    "endpoints": [
        "endpoints",
        "study endpoints",
        "primary endpoint",
        "secondary endpoints",
        "efficacy endpoints",
        "outcome measures",
        "objectives and endpoints",
    ],

    # ---------------------------------------------------------------------
    # STUDY DESIGN
    # ---------------------------------------------------------------------
    "study_design": [
        "study design",
        "study design and randomization",
        "design",
        "study overview",
        "investigational plan",
        "study design schema",
        "flow chart",
        "protocol synopsis",
    ],

    # ---------------------------------------------------------------------
    # SAMPLE SIZE
    # ---------------------------------------------------------------------
    "sample_size": [
        "sample size",
        "sample size justification",
        "sample size determination",
        "sample size calculation",
        "prearranged sample size",
        "statistical considerations",
        "power calculation",
        "sample size and power",
    ],

    # ---------------------------------------------------------------------
    # ANALYSIS POPULATIONS
    # ---------------------------------------------------------------------
    "analysis_populations": [
        "analysis populations",
        "analysis sets",
        "study populations",
        "patient populations",
        "analysis population",
        "population for analysis",
        "itt population",
        "full analysis set",
        "safety population",
    ],

    # ---------------------------------------------------------------------
    # STATISTICAL METHODS
    # ---------------------------------------------------------------------
    "statistical_methods": [
        "statistical methods",
        "statistical analysis",
        "statistical and analytical procedures",
        "statistical considerations",
        "analysis methods",
        "primary analysis",
        "efficacy analysis",
        "data analysis",
    ],

    # ---------------------------------------------------------------------
    # EFFICACY ANALYSIS
    # ---------------------------------------------------------------------
    "efficacy_analysis": [
        "efficacy analysis",
        "efficacy",
        "efficacy evaluation",
        "efficacy assessments",
        "primary efficacy",
        "analysis of efficacy",
        "tumor assessment",
        "response assessment",
    ],

    # ---------------------------------------------------------------------
    # SAFETY ANALYSIS
    # ---------------------------------------------------------------------
    "safety_analysis": [
        "safety analysis",
        "safety",
        "safety evaluation",
        "safety assessments",
        "adverse events",
        "safety endpoints",
        "analysis of safety",
    ],

    # ---------------------------------------------------------------------
    # INTERIM ANALYSIS
    # ---------------------------------------------------------------------
    "interim_analysis": [
        "interim analysis",
        "interim analyses",
        "interim evaluation",
        "data monitoring",
        "independent data monitoring committee",
        "idmc",
        "dmc",
        "stopping rules",
    ],

    # ---------------------------------------------------------------------
    # MISSING DATA
    # ---------------------------------------------------------------------
    "missing_data": [
        "missing data",
        "handling of missing values",
        "missing values",
        "data handling conventions",
        "data handling",
        "censoring",
        "imputation",
    ],

    # ---------------------------------------------------------------------
    # PHARMACOKINETICS
    # ---------------------------------------------------------------------
    "pharmacokinetics": [
        "pharmacokinetic",
        "pharmacokinetics",
        "pk analysis",
        "pk assessments",
        "pk endpoints",
        "pharmacokinetic analysis",
    ],

    # ---------------------------------------------------------------------
    # MULTIPLICITY
    # ---------------------------------------------------------------------
    "multiplicity": [
        "multiplicity",
        "multiple comparisons",
        "alpha adjustment",
        "type i error",
        "hypothesis testing",
        "hierarchical testing",
        "gatekeeping",
    ],

    # ---------------------------------------------------------------------
    # SUBGROUP ANALYSIS
    # ---------------------------------------------------------------------
    "subgroup_analysis": [
        "subgroup analysis",
        "subgroup analyses",
        "subgroups",
        "exploratory analyses",
        "subset analysis",
    ],

    # ---------------------------------------------------------------------
    # SENSITIVITY ANALYSIS
    # ---------------------------------------------------------------------
    "sensitivity_analysis": [
        "sensitivity analysis",
        "sensitivity analyses",
        "supportive analyses",
        "robustness",
    ],
}


# =============================================================================
# SAP SECTION ORDER (based on ICH E9 / Gamble et al. guidelines)
# =============================================================================
SAP_SECTION_ORDER = [
    "introduction",
    "objectives",
    "endpoints",
    "study_design",
    "sample_size",
    "analysis_populations",
    "statistical_methods",
    "efficacy_analysis",
    "safety_analysis",
    "pharmacokinetics",
    "interim_analysis",
    "multiplicity",
    "missing_data",
    "sensitivity_analysis",
    "subgroup_analysis",
]


# =============================================================================
# SECTION ALIASES (normalize different naming conventions)
# =============================================================================
SECTION_ALIASES = {
    # Normalize to lowercase, underscore format
    "statistical analysis": "statistical_methods",
    "statistical and analytical procedures": "statistical_methods",
    "analysis methods": "statistical_methods",

    "sample size justification": "sample_size",
    "sample size determination": "sample_size",
    "sample size calculation": "sample_size",

    "analysis sets": "analysis_populations",
    "study populations": "analysis_populations",

    "efficacy": "efficacy_analysis",
    "safety": "safety_analysis",

    "pk analysis": "pharmacokinetics",
    "pharmacokinetic analysis": "pharmacokinetics",

    "interim analyses": "interim_analysis",

    "subgroup analyses": "subgroup_analysis",
    "sensitivity analyses": "sensitivity_analysis",

    "objectives and endpoints": "objectives",
    "study objectives and endpoints": "objectives",

    "missing values": "missing_data",
    "handling of missing values": "missing_data",
}


def normalize_section_name(name: str) -> str:
    """Normalize a section name to canonical form."""
    name = name.lower().strip()
    name = name.replace("-", " ").replace("_", " ")

    # Check aliases
    if name in SECTION_ALIASES:
        return SECTION_ALIASES[name]

    # Convert to underscore format
    return name.replace(" ", "_")


def find_protocol_sections_for_sap(sap_section: str, protocol_sections: dict) -> list:
    """
    Find which protocol sections contain info for a given SAP section.

    Args:
        sap_section: The SAP section we want to generate
        protocol_sections: Dict of {section_name: section_content} from protocol

    Returns:
        List of (section_name, content) tuples, in priority order
    """
    sap_section = normalize_section_name(sap_section)

    if sap_section not in PROTOCOL_TO_SAP_MAPPING:
        return []

    search_terms = PROTOCOL_TO_SAP_MAPPING[sap_section]
    results = []

    # Normalize protocol section names for matching
    normalized_protocol = {
        normalize_section_name(k): (k, v)
        for k, v in protocol_sections.items()
    }

    # Track which protocol sections we've already added
    seen_sections = set()

    # Search in priority order
    for term in search_terms:
        term_normalized = normalize_section_name(term)

        # Exact match
        if term_normalized in normalized_protocol:
            orig_name, content = normalized_protocol[term_normalized]
            if orig_name not in seen_sections:
                results.append((orig_name, content))
                seen_sections.add(orig_name)
            continue

        # Partial match
        for norm_name, (orig_name, content) in normalized_protocol.items():
            if term_normalized in norm_name or norm_name in term_normalized:
                if orig_name not in seen_sections:
                    results.append((orig_name, content))
                    seen_sections.add(orig_name)

    return results


# =============================================================================
# TEST
# =============================================================================
if __name__ == "__main__":
    print("Protocol → SAP Section Mapping")
    print("=" * 50)

    for sap_section in SAP_SECTION_ORDER:
        search_terms = PROTOCOL_TO_SAP_MAPPING.get(sap_section, [])
        print(f"\n{sap_section}:")
        print(f"  Looks for: {search_terms[:3]}...")
