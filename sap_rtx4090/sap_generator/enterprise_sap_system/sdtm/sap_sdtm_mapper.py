"""
SAP to SDTM Domain Mapper
=========================

Parses a generated SAP document and maps the data requirements
to SDTM domains with full variable specifications.

This implements the SAP → SDTM step of Sandy's pipeline:
Protocol → SAP → SDTM → ADaM → TLFs

Author: SAP Generation System
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path

# Import the SDTM knowledge base
try:
    from .sdtm_domains import (
        SDTMDomain, SDTMVariable, SDTM_DOMAINS,
        find_domains_by_trigger, get_domain, get_all_domains,
        DomainClass, VariableCore
    )
except ImportError:
    from sdtm_domains import (
        SDTMDomain, SDTMVariable, SDTM_DOMAINS,
        find_domains_by_trigger, get_domain, get_all_domains,
        DomainClass, VariableCore
    )


@dataclass
class DataRequirement:
    """A data requirement extracted from the SAP."""
    category: str  # e.g., "endpoint", "safety", "efficacy", "pk"
    description: str
    source_section: str
    source_text: str
    mapped_domains: List[str] = field(default_factory=list)
    mapped_variables: List[Tuple[str, str]] = field(default_factory=list)  # (domain, variable)


@dataclass
class SDTMSpec:
    """SDTM specification for a study based on SAP requirements."""
    study_id: str
    domains: List[SDTMDomain]
    domain_justifications: Dict[str, str]  # domain code -> why needed
    variable_selections: Dict[str, List[SDTMVariable]]  # domain -> required vars
    data_requirements: List[DataRequirement]
    metadata: Dict[str, str] = field(default_factory=dict)


class SAPParser:
    """Parses SAP documents to extract data requirements."""

    # Section patterns to identify SAP sections
    SECTION_PATTERNS = {
        "objectives": r"(?:##?\s*\d*\.?\d*\s*)?(STUDY\s+)?OBJECTIVES?",
        "endpoints": r"(?:##?\s*\d*\.?\d*\s*)?(?:PRIMARY|SECONDARY|EXPLORATORY)?\s*ENDPOINTS?",
        "populations": r"(?:##?\s*\d*\.?\d*\s*)?(?:ANALYSIS\s+)?POPULATIONS?|(?:ANALYSIS\s+)?SETS?",
        "efficacy": r"(?:##?\s*\d*\.?\d*\s*)?EFFICACY\s+(?:ANALYSIS|ANALYSES|ENDPOINTS?)?",
        "safety": r"(?:##?\s*\d*\.?\d*\s*)?SAFETY\s+(?:ANALYSIS|ANALYSES)?",
        "pk": r"(?:##?\s*\d*\.?\d*\s*)?PHARMACOKINETIC|PK\s+(?:ANALYSIS|ANALYSES)?",
        "biomarker": r"(?:##?\s*\d*\.?\d*\s*)?BIOMARKER|EXPLORATORY\s+(?:ANALYSIS|ANALYSES)?",
        "demographics": r"(?:##?\s*\d*\.?\d*\s*)?DEMOGRAPHIC|BASELINE\s+CHARACTERISTICS?",
        "disposition": r"(?:##?\s*\d*\.?\d*\s*)?DISPOSITION|SUBJECT\s+ACCOUNTABILITY",
        "exposure": r"(?:##?\s*\d*\.?\d*\s*)?EXPOSURE|TREATMENT\s+(?:EXPOSURE|ADMINISTRATION)",
        "tlf": r"(?:##?\s*\d*\.?\d*\s*)?(?:TLF|TABLE|LISTING|FIGURE|APPENDIX)",
    }

    # Keyword patterns that indicate specific data needs
    DATA_KEYWORDS = {
        "adverse_events": [
            r"adverse\s+event", r"TEAE", r"treatment[\-\s]emergent",
            r"SAE", r"serious\s+adverse", r"toxicity", r"DLT",
            r"MedDRA", r"SOC", r"preferred\s+term", r"CTCAE"
        ],
        "laboratory": [
            r"laboratory", r"lab\s+test", r"hematology", r"chemistry",
            r"urinalysis", r"hemoglobin", r"platelet", r"neutrophil",
            r"creatinine", r"bilirubin", r"ALT", r"AST", r"liver\s+function"
        ],
        "vital_signs": [
            r"vital\s+sign", r"blood\s+pressure", r"heart\s+rate",
            r"pulse", r"temperature", r"respiratory", r"weight", r"height",
            r"BMI", r"systolic", r"diastolic"
        ],
        "tumor_response": [
            r"RECIST", r"tumor\s+response", r"objective\s+response",
            r"complete\s+response", r"partial\s+response", r"stable\s+disease",
            r"progressive\s+disease", r"ORR", r"DCR", r"BOR",
            r"target\s+lesion", r"non-target", r"new\s+lesion"
        ],
        "survival": [
            r"survival", r"overall\s+survival", r"progression[\-\s]free",
            r"PFS", r"OS", r"event[\-\s]free", r"DFS", r"time[\-\s]to[\-\s]event",
            r"Kaplan[\-\s]Meier", r"hazard\s+ratio", r"death"
        ],
        "pharmacokinetics": [
            r"pharmacokinetic", r"PK", r"concentration", r"Cmax",
            r"Tmax", r"AUC", r"half[\-\s]life", r"clearance", r"bioavailability",
            r"serum\s+concentration", r"plasma"
        ],
        "immunogenicity": [
            r"immunogenicity", r"anti[\-\s]drug\s+antibody", r"ADA",
            r"neutralizing\s+antibody", r"NAb", r"antibody\s+titer"
        ],
        "questionnaire": [
            r"questionnaire", r"PRO", r"patient[\-\s]reported",
            r"quality\s+of\s+life", r"QoL", r"QLQ", r"EORTC",
            r"SF[\-\s]36", r"EQ[\-\s]5D", r"FACT"
        ],
        "demographics": [
            r"age", r"sex", r"gender", r"race", r"ethnicity",
            r"baseline\s+characteristic", r"demographic"
        ],
        "concomitant_meds": [
            r"concomitant\s+medication", r"prior\s+medication",
            r"WHO\s+drug", r"ATC", r"background\s+therapy"
        ],
        "medical_history": [
            r"medical\s+history", r"prior\s+disease", r"comorbid",
            r"baseline\s+disease"
        ],
        "exposure": [
            r"exposure", r"dose\s+administered", r"treatment\s+duration",
            r"dose\s+modification", r"dose\s+intensity"
        ],
        "ecg": [
            r"ECG", r"electrocardiogram", r"QT", r"QTc",
            r"PR\s+interval", r"QRS", r"cardiac"
        ],
        "disposition": [
            r"disposition", r"discontinuation", r"completion",
            r"withdrawal", r"lost\s+to\s+follow[\-\s]up"
        ],
    }

    # Map keyword categories to primary SDTM domains
    KEYWORD_TO_DOMAINS = {
        "adverse_events": ["AE", "FA"],
        "laboratory": ["LB"],
        "vital_signs": ["VS"],
        "tumor_response": ["RS", "TR", "TU"],
        "survival": ["DS", "DD"],
        "pharmacokinetics": ["PC", "PP"],
        "immunogenicity": ["IS"],
        "questionnaire": ["QS"],
        "demographics": ["DM", "SC"],
        "concomitant_meds": ["CM"],
        "medical_history": ["MH"],
        "exposure": ["EX", "EC"],
        "ecg": ["EG"],
        "disposition": ["DS"],
    }

    def __init__(self):
        """Initialize the SAP parser."""
        self.compiled_keywords = {}
        for category, patterns in self.DATA_KEYWORDS.items():
            self.compiled_keywords[category] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def parse_sap(self, sap_content: str) -> List[DataRequirement]:
        """
        Parse SAP content and extract data requirements.

        Args:
            sap_content: The SAP document text

        Returns:
            List of DataRequirement objects
        """
        requirements = []

        # Split into sections
        sections = self._split_into_sections(sap_content)

        # Analyze each section for data requirements
        for section_name, section_content in sections.items():
            section_reqs = self._extract_requirements_from_section(
                section_name, section_content
            )
            requirements.extend(section_reqs)

        # De-duplicate and merge requirements
        requirements = self._deduplicate_requirements(requirements)

        return requirements

    def _split_into_sections(self, content: str) -> Dict[str, str]:
        """Split SAP content into sections."""
        sections = {}
        lines = content.split('\n')
        current_section = "header"
        current_content = []

        for line in lines:
            # Check if this line is a section header
            for section_name, pattern in self.SECTION_PATTERNS.items():
                if re.search(pattern, line, re.IGNORECASE):
                    # Save previous section
                    if current_content:
                        sections[current_section] = '\n'.join(current_content)
                    current_section = section_name
                    current_content = [line]
                    break
            else:
                current_content.append(line)

        # Don't forget the last section
        if current_content:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _extract_requirements_from_section(
        self, section_name: str, content: str
    ) -> List[DataRequirement]:
        """Extract data requirements from a section."""
        requirements = []

        # Find all keyword matches
        for category, patterns in self.compiled_keywords.items():
            for pattern in patterns:
                matches = pattern.finditer(content)
                for match in matches:
                    # Get surrounding context (100 chars before and after)
                    start = max(0, match.start() - 100)
                    end = min(len(content), match.end() + 100)
                    context = content[start:end].strip()

                    # Create data requirement
                    req = DataRequirement(
                        category=category,
                        description=f"{category.replace('_', ' ').title()} analysis",
                        source_section=section_name,
                        source_text=context,
                        mapped_domains=self.KEYWORD_TO_DOMAINS.get(category, [])
                    )
                    requirements.append(req)
                    break  # Only one match per category per section

        return requirements

    def _deduplicate_requirements(
        self, requirements: List[DataRequirement]
    ) -> List[DataRequirement]:
        """Remove duplicate requirements."""
        seen = set()
        unique = []

        for req in requirements:
            key = (req.category, req.source_section)
            if key not in seen:
                seen.add(key)
                unique.append(req)

        return unique


class SDTMMapper:
    """Maps SAP data requirements to SDTM domains and variables."""

    # Domain selection rules based on analysis type
    ANALYSIS_TYPE_DOMAINS = {
        "safety": {
            "required": ["DM", "AE", "DS", "EX"],
            "conditional": ["LB", "VS", "EG", "CM", "MH"],
            "optional": ["PE", "FA", "DD"]
        },
        "efficacy_oncology": {
            "required": ["DM", "RS", "TR", "TU", "DS"],
            "conditional": ["AE", "EX", "LB"],
            "optional": ["PC", "IS"]
        },
        "pk_study": {
            "required": ["DM", "PC", "PP", "EX"],
            "conditional": ["AE", "CM", "LB", "VS"],
            "optional": ["IS"]
        },
        "vaccine": {
            "required": ["DM", "IS", "AE", "EX"],
            "conditional": ["LB", "VS", "CM"],
            "optional": ["MB", "MS"]
        }
    }

    def __init__(self):
        """Initialize the SDTM mapper."""
        self.parser = SAPParser()

    def map_sap_to_sdtm(
        self,
        sap_content: str,
        study_id: str,
        therapeutic_area: str = "oncology"
    ) -> SDTMSpec:
        """
        Map SAP content to SDTM specification.

        Args:
            sap_content: The SAP document text
            study_id: Study identifier
            therapeutic_area: e.g., "oncology", "vaccine", "pk_study"

        Returns:
            SDTMSpec with all required domains and variables
        """
        # Parse SAP to extract requirements
        requirements = self.parser.parse_sap(sap_content)

        # Get domains from trigger matching
        trigger_domains = find_domains_by_trigger(sap_content)

        # Determine required domains based on requirements and TA
        required_domain_codes = self._determine_required_domains(
            requirements, trigger_domains, therapeutic_area
        )

        # Build domain justifications
        justifications = self._build_justifications(
            requirements, required_domain_codes
        )

        # Get full domain objects
        domains = [get_domain(code) for code in required_domain_codes if get_domain(code)]

        # Select required variables for each domain
        variable_selections = self._select_variables(domains, requirements)

        # Build the SDTM spec
        spec = SDTMSpec(
            study_id=study_id,
            domains=domains,
            domain_justifications=justifications,
            variable_selections=variable_selections,
            data_requirements=requirements,
            metadata={
                "therapeutic_area": therapeutic_area,
                "total_domains": str(len(domains)),
                "total_variables": str(sum(len(v) for v in variable_selections.values()))
            }
        )

        return spec

    def _determine_required_domains(
        self,
        requirements: List[DataRequirement],
        trigger_domains: List[SDTMDomain],
        therapeutic_area: str
    ) -> List[str]:
        """Determine which domains are required based on requirements."""
        required = set()

        # Always include core domains
        required.add("DM")  # Demographics always required
        required.add("DS")  # Disposition always required

        # Add domains from requirements
        for req in requirements:
            required.update(req.mapped_domains)

        # Add domains from trigger matching
        for domain in trigger_domains:
            required.add(domain.code)

        # Add TA-specific domains
        ta_key = f"efficacy_{therapeutic_area}" if therapeutic_area in ["oncology"] else therapeutic_area
        if ta_key in self.ANALYSIS_TYPE_DOMAINS:
            ta_domains = self.ANALYSIS_TYPE_DOMAINS[ta_key]
            required.update(ta_domains.get("required", []))
            # Add conditional domains if mentioned in SAP
            for domain_code in ta_domains.get("conditional", []):
                if any(domain_code in req.mapped_domains for req in requirements):
                    required.add(domain_code)

        # Add trial design domains if study design mentioned
        if "trial" in " ".join(r.source_text.lower() for r in requirements):
            required.update(["TA", "TE", "TV", "TS"])

        return sorted(required)

    def _build_justifications(
        self,
        requirements: List[DataRequirement],
        domain_codes: List[str]
    ) -> Dict[str, str]:
        """Build justification text for each domain."""
        justifications = {}

        for code in domain_codes:
            domain = get_domain(code)
            if not domain:
                continue

            # Find requirements that map to this domain
            related_reqs = [
                r for r in requirements if code in r.mapped_domains
            ]

            if related_reqs:
                justifications[code] = (
                    f"Required for {', '.join(r.category for r in related_reqs)} analysis. "
                    f"Referenced in SAP sections: {', '.join(set(r.source_section for r in related_reqs))}"
                )
            else:
                # Standard justifications for always-required domains
                if code == "DM":
                    justifications[code] = "Required for subject demographics and baseline characteristics"
                elif code == "DS":
                    justifications[code] = "Required for disposition and subject accountability"
                elif code in ["TA", "TE", "TV", "TS"]:
                    justifications[code] = "Required for trial design documentation"
                else:
                    justifications[code] = f"Required based on therapeutic area standards"

        return justifications

    def _select_variables(
        self,
        domains: List[SDTMDomain],
        requirements: List[DataRequirement]
    ) -> Dict[str, List[SDTMVariable]]:
        """Select required and expected variables for each domain."""
        selections = {}

        for domain in domains:
            # Start with required and expected variables
            required_vars = [
                v for v in domain.variables
                if v.core in [VariableCore.REQUIRED, VariableCore.EXPECTED]
            ]

            # Check if we need specific permissible variables
            # based on SAP content
            sap_text = ' '.join(r.source_text for r in requirements).lower()

            for var in domain.variables:
                if var.core == VariableCore.PERMISSIBLE:
                    # Check if variable name or label is mentioned in SAP
                    if (var.name.lower() in sap_text or
                        var.label.lower() in sap_text):
                        if var not in required_vars:
                            required_vars.append(var)

            selections[domain.code] = required_vars

        return selections


def generate_sdtm_spec(
    sap_path: str,
    study_id: str,
    therapeutic_area: str = "oncology"
) -> SDTMSpec:
    """
    Generate SDTM specification from a SAP file.

    Args:
        sap_path: Path to the SAP markdown file
        study_id: Study identifier
        therapeutic_area: Therapeutic area (oncology, vaccine, etc.)

    Returns:
        SDTMSpec object with all specifications
    """
    # Read SAP content
    sap_content = Path(sap_path).read_text()

    # Create mapper and generate spec
    mapper = SDTMMapper()
    spec = mapper.map_sap_to_sdtm(sap_content, study_id, therapeutic_area)

    return spec


def format_sdtm_spec_as_markdown(spec: SDTMSpec) -> str:
    """
    Format SDTM specification as markdown.

    Args:
        spec: SDTMSpec object

    Returns:
        Markdown formatted specification
    """
    lines = [
        f"# SDTM Domain Specification",
        f"",
        f"**Study ID:** {spec.study_id}",
        f"**Therapeutic Area:** {spec.metadata.get('therapeutic_area', 'N/A')}",
        f"**Total Domains:** {spec.metadata.get('total_domains', len(spec.domains))}",
        f"**Total Variables:** {spec.metadata.get('total_variables', 'N/A')}",
        f"",
        f"---",
        f"",
        f"## Required SDTM Domains",
        f"",
    ]

    # Group domains by class
    domains_by_class: Dict[str, List[SDTMDomain]] = {}
    for domain in spec.domains:
        class_name = domain.domain_class.value
        if class_name not in domains_by_class:
            domains_by_class[class_name] = []
        domains_by_class[class_name].append(domain)

    for class_name, domains in domains_by_class.items():
        lines.append(f"### {class_name}")
        lines.append("")

        for domain in domains:
            justification = spec.domain_justifications.get(domain.code, "")
            vars_selected = spec.variable_selections.get(domain.code, [])

            lines.append(f"#### {domain.code} - {domain.name}")
            lines.append(f"")
            lines.append(f"**Description:** {domain.description}")
            lines.append(f"**Structure:** {domain.structure}")
            lines.append(f"**Justification:** {justification}")
            lines.append(f"")

            # List selected variables
            lines.append(f"**Selected Variables ({len(vars_selected)}):**")
            lines.append("")
            lines.append("| Variable | Label | Type | Core |")
            lines.append("|----------|-------|------|------|")

            for var in vars_selected[:20]:  # Limit to first 20 for readability
                lines.append(
                    f"| {var.name} | {var.label} | {var.type} | {var.core.value} |"
                )

            if len(vars_selected) > 20:
                lines.append(f"| ... | *(+{len(vars_selected)-20} more variables)* | | |")

            lines.append("")

    # Add data requirements section
    lines.append("---")
    lines.append("")
    lines.append("## Data Requirements Extracted from SAP")
    lines.append("")

    for req in spec.data_requirements:
        lines.append(f"### {req.category.replace('_', ' ').title()}")
        lines.append(f"")
        lines.append(f"**Source Section:** {req.source_section}")
        lines.append(f"**Mapped Domains:** {', '.join(req.mapped_domains)}")
        lines.append(f"")

    return '\n'.join(lines)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    import sys

    print("="*70)
    print("SAP TO SDTM MAPPER TEST")
    print("="*70)

    # Test with a sample SAP
    test_sap = """
    # STATISTICAL ANALYSIS PLAN

    ## 1. STUDY OBJECTIVES

    The primary objective is to evaluate the objective response rate (ORR)
    per RECIST 1.1 in patients with advanced solid tumors.

    ## 2. ENDPOINTS

    ### 2.1 Primary Endpoint
    - Objective Response Rate (ORR) by RECIST 1.1

    ### 2.2 Secondary Endpoints
    - Progression-free Survival (PFS)
    - Overall Survival (OS)
    - Duration of Response (DOR)

    ## 5. SAFETY ANALYSES

    Safety will be assessed through:
    - Treatment-emergent adverse events (TEAEs) coded using MedDRA
    - Laboratory assessments (hematology, chemistry)
    - Vital signs
    - ECG parameters including QTc

    ## 6. PHARMACOKINETIC ANALYSES

    Serum concentrations will be analyzed to determine Cmax, Tmax, and AUC.

    ## 7. IMMUNOGENICITY

    Anti-drug antibodies (ADA) will be assessed.
    """

    # Parse and map
    mapper = SDTMMapper()
    spec = mapper.map_sap_to_sdtm(test_sap, "NCT00000000", "oncology")

    print(f"\nStudy: {spec.study_id}")
    print(f"Domains required: {len(spec.domains)}")
    print(f"Data requirements found: {len(spec.data_requirements)}")

    print("\n--- Required Domains ---")
    for domain in spec.domains:
        vars_count = len(spec.variable_selections.get(domain.code, []))
        print(f"  {domain.code}: {domain.name} ({vars_count} variables)")

    print("\n--- Data Requirements ---")
    for req in spec.data_requirements:
        print(f"  [{req.source_section}] {req.category} -> {req.mapped_domains}")

    # Test with real SAP file if available
    sap_file = Path("output/generated_saps/NCT03558139_sap.md")
    if sap_file.exists():
        print("\n" + "="*70)
        print("TESTING WITH REAL SAP: NCT03558139")
        print("="*70)

        spec = generate_sdtm_spec(str(sap_file), "NCT03558139", "oncology")

        print(f"\nDomains required: {len(spec.domains)}")
        for domain in spec.domains:
            vars_count = len(spec.variable_selections.get(domain.code, []))
            print(f"  {domain.code}: {domain.name} ({vars_count} variables)")

        # Generate markdown
        md = format_sdtm_spec_as_markdown(spec)

        # Save to file
        output_path = Path("output/sdtm_specs/NCT03558139_sdtm_spec.md")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md)
        print(f"\nSDTM spec saved to: {output_path}")
