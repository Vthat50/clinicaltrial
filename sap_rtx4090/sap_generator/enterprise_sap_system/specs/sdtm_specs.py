#!/usr/bin/env python3
"""
SDTM Specification Generator
=============================

Generates CDISC SDTM domain specifications from protocol facts.
Based on SDTM Implementation Guide v3.4 and FDA Technical Conformance Guide.

This module implements Sandy's vision: Protocol → SAP → SDTM Specs
The SDTM specs define what standardized data domains are needed for the study.

References:
- CDISC SDTM v1.7: https://www.cdisc.org/standards/foundational/sdtm
- SDTMIG v3.4: https://www.cdisc.org/standards/foundational/sdtmig
- FDA Study Data Technical Conformance Guide

Domain Classes:
- Special Purpose: DM, CO, SE, SV
- Trial Design: TS, TA, TV, TI, TE
- Interventions: EX, CM, SU, EC, PR
- Events: AE, DS, MH, DV, CE
- Findings: VS, LB, PE, EG, QS, SC
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class VariableCore(Enum):
    """CDISC Core classification for variables."""
    REQUIRED = "Req"      # Cannot be null
    EXPECTED = "Exp"      # Must include, can be null
    PERMISSIBLE = "Perm"  # Optional based on data collected


class DomainClass(Enum):
    """SDTM Domain Classes per CDISC."""
    SPECIAL_PURPOSE = "Special Purpose"
    TRIAL_DESIGN = "Trial Design"
    INTERVENTIONS = "Interventions"
    EVENTS = "Events"
    FINDINGS = "Findings"
    FINDINGS_ABOUT = "Findings About"
    RELATIONSHIP = "Relationship"


@dataclass
class SDTMVariable:
    """Specification for a single SDTM variable."""
    name: str
    label: str
    type: str  # "Char" or "Num"
    length: Optional[int] = None
    core: VariableCore = VariableCore.PERMISSIBLE
    codelist: Optional[str] = None
    description: str = ""
    source: str = ""  # Where data comes from (CRF, derived, etc.)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "length": self.length,
            "core": self.core.value,
            "codelist": self.codelist,
            "description": self.description,
            "source": self.source
        }


@dataclass
class SDTMDomain:
    """Specification for a complete SDTM domain."""
    code: str  # Two-letter domain code (DM, AE, etc.)
    name: str
    label: str
    domain_class: DomainClass
    structure: str  # "One record per subject", etc.
    variables: List[SDTMVariable] = field(default_factory=list)
    description: str = ""
    purpose: str = ""
    required_for: List[str] = field(default_factory=list)  # Which TLFs need this

    def get_required_variables(self) -> List[SDTMVariable]:
        """Return only required variables."""
        return [v for v in self.variables if v.core == VariableCore.REQUIRED]

    def get_expected_variables(self) -> List[SDTMVariable]:
        """Return expected variables."""
        return [v for v in self.variables if v.core == VariableCore.EXPECTED]

    def to_dict(self) -> Dict:
        return {
            "code": self.code,
            "name": self.name,
            "label": self.label,
            "class": self.domain_class.value,
            "structure": self.structure,
            "description": self.description,
            "purpose": self.purpose,
            "required_for": self.required_for,
            "variables": [v.to_dict() for v in self.variables]
        }

    def to_markdown(self) -> str:
        """Generate markdown documentation for this domain."""
        lines = [
            f"### {self.code} - {self.name}",
            "",
            f"**Label:** {self.label}",
            f"**Class:** {self.domain_class.value}",
            f"**Structure:** {self.structure}",
            "",
            f"**Purpose:** {self.purpose}",
            "",
            "#### Variables",
            "",
            "| Variable | Label | Type | Core | Codelist |",
            "|----------|-------|------|------|----------|",
        ]

        for var in self.variables:
            codelist = var.codelist or "-"
            lines.append(f"| {var.name} | {var.label} | {var.type} | {var.core.value} | {codelist} |")

        if self.required_for:
            lines.extend([
                "",
                f"**Required for TLFs:** {', '.join(self.required_for)}"
            ])

        return "\n".join(lines)


@dataclass
class SDTMSpecification:
    """Complete SDTM specification for a study."""
    protocol_id: str
    generated_at: str
    sdtm_version: str = "3.4"
    domains: List[SDTMDomain] = field(default_factory=list)
    define_xml_notes: List[str] = field(default_factory=list)

    def get_domain(self, code: str) -> Optional[SDTMDomain]:
        """Get domain by code."""
        for domain in self.domains:
            if domain.code == code:
                return domain
        return None

    def get_all_domain_codes(self) -> List[str]:
        """Return list of all domain codes."""
        return [d.code for d in self.domains]

    def to_markdown(self) -> str:
        """Generate full markdown specification document."""
        lines = [
            f"# SDTM Specification",
            f"## Protocol: {self.protocol_id}",
            "",
            f"**Generated:** {self.generated_at}",
            f"**SDTM Version:** {self.sdtm_version}",
            "",
            "---",
            "",
            "## Domains Required for This Study",
            "",
            "| Domain | Name | Class | Purpose |",
            "|--------|------|-------|---------|",
        ]

        for domain in self.domains:
            lines.append(f"| {domain.code} | {domain.name} | {domain.domain_class.value} | {domain.purpose[:50]}... |")

        lines.extend(["", "---", ""])

        # Add each domain specification
        for domain in self.domains:
            lines.append(domain.to_markdown())
            lines.append("")
            lines.append("---")
            lines.append("")

        # Add Define-XML notes
        if self.define_xml_notes:
            lines.extend([
                "## Define-XML Notes",
                "",
            ])
            for note in self.define_xml_notes:
                lines.append(f"- {note}")

        return "\n".join(lines)


class SDTMSpecGenerator:
    """
    Generates SDTM specifications from protocol facts.

    This implements the biostatistician's workflow:
    1. Analyze protocol/SAP requirements
    2. Determine which SDTM domains are needed
    3. Specify variables for each domain
    4. Document for Define-XML preparation
    """

    # Standard domain templates with CDISC-compliant variables
    DOMAIN_TEMPLATES = {}

    def __init__(self):
        """Initialize with standard domain templates."""
        self._init_domain_templates()

    def _init_domain_templates(self):
        """Initialize all standard SDTM domain templates."""

        # ===== SPECIAL PURPOSE DOMAINS =====

        self.DOMAIN_TEMPLATES["DM"] = SDTMDomain(
            code="DM",
            name="Demographics",
            label="Demographics",
            domain_class=DomainClass.SPECIAL_PURPOSE,
            structure="One record per subject",
            purpose="Parent domain for all subject observations",
            description="Contains demographic information for each subject in the study",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("SUBJID", "Subject Identifier for the Study", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("RFSTDTC", "Subject Reference Start Date/Time", "Char", 19, VariableCore.EXPECTED,
                            description="First dose date for most studies"),
                SDTMVariable("RFENDTC", "Subject Reference End Date/Time", "Char", 19, VariableCore.EXPECTED,
                            description="Last dose date or study completion"),
                SDTMVariable("RFXSTDTC", "Date/Time of First Study Treatment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("RFXENDTC", "Date/Time of Last Study Treatment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("RFICDTC", "Date/Time of Informed Consent", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("RFPENDTC", "Date/Time of End of Participation", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("SITEID", "Study Site Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("INVID", "Investigator Identifier", "Char", 20, VariableCore.PERMISSIBLE),
                SDTMVariable("INVNAM", "Investigator Name", "Char", 100, VariableCore.PERMISSIBLE),
                SDTMVariable("BRTHDTC", "Date/Time of Birth", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("AGE", "Age", "Num", 8, VariableCore.EXPECTED, description="Age at informed consent"),
                SDTMVariable("AGEU", "Age Units", "Char", 10, VariableCore.EXPECTED, codelist="AGEU"),
                SDTMVariable("SEX", "Sex", "Char", 1, VariableCore.REQUIRED, codelist="SEX"),
                SDTMVariable("RACE", "Race", "Char", 60, VariableCore.EXPECTED, codelist="RACE"),
                SDTMVariable("ETHNIC", "Ethnicity", "Char", 40, VariableCore.EXPECTED, codelist="ETHNIC"),
                SDTMVariable("ARMCD", "Planned Arm Code", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("ARM", "Description of Planned Arm", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("ACTARMCD", "Actual Arm Code", "Char", 20, VariableCore.EXPECTED),
                SDTMVariable("ACTARM", "Description of Actual Arm", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("COUNTRY", "Country", "Char", 3, VariableCore.REQUIRED, codelist="COUNTRY"),
                SDTMVariable("DTHFL", "Subject Death Flag", "Char", 1, VariableCore.EXPECTED, codelist="NY"),
                SDTMVariable("DTHDTC", "Date/Time of Death", "Char", 19, VariableCore.EXPECTED),
            ]
        )

        # ===== TRIAL DESIGN DOMAINS =====

        self.DOMAIN_TEMPLATES["TS"] = SDTMDomain(
            code="TS",
            name="Trial Summary",
            label="Trial Summary",
            domain_class=DomainClass.TRIAL_DESIGN,
            structure="One record per trial summary parameter",
            purpose="Contains trial-level metadata required by FDA",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("TSSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("TSGRPID", "Group ID", "Char", 20, VariableCore.PERMISSIBLE),
                SDTMVariable("TSPARMCD", "Trial Summary Parameter Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("TSPARM", "Trial Summary Parameter", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("TSVAL", "Parameter Value", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("TSVALNF", "Parameter Null Flavor", "Char", 2, VariableCore.EXPECTED),
                SDTMVariable("TSVALCD", "Parameter Value Code", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("TSVCDREF", "Name of Reference Terminology", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("TSVCDVER", "Version of Reference Terminology", "Char", 200, VariableCore.PERMISSIBLE),
            ]
        )

        self.DOMAIN_TEMPLATES["TA"] = SDTMDomain(
            code="TA",
            name="Trial Arms",
            label="Trial Arms",
            domain_class=DomainClass.TRIAL_DESIGN,
            structure="One record per planned Element per Arm",
            purpose="Describes treatment arms and their elements",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("ARMCD", "Planned Arm Code", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("ARM", "Description of Planned Arm", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("TAESSION", "Planned Arm Code", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("ETCD", "Element Code", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("ELEMENT", "Description of Element", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("TABESSION", "Branch", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("TATRANS", "Transition Rule", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.REQUIRED, codelist="EPOCH"),
            ]
        )

        # ===== INTERVENTIONS DOMAINS =====

        self.DOMAIN_TEMPLATES["EX"] = SDTMDomain(
            code="EX",
            name="Exposure",
            label="Exposure",
            domain_class=DomainClass.INTERVENTIONS,
            structure="One record per constant-dosing interval per subject",
            purpose="Documents study treatment administration",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("EXSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("EXSPID", "Sponsor-Defined Identifier", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("EXTRT", "Name of Treatment", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("EXCAT", "Category for Treatment", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("EXDOSE", "Dose", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("EXDOSTXT", "Dose Description", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("EXDOSU", "Dose Units", "Char", 40, VariableCore.EXPECTED, codelist="UNIT"),
                SDTMVariable("EXDOSFRM", "Dose Form", "Char", 40, VariableCore.EXPECTED, codelist="FRM"),
                SDTMVariable("EXDOSFRQ", "Dosing Frequency per Interval", "Char", 40, VariableCore.EXPECTED, codelist="FREQ"),
                SDTMVariable("EXROUTE", "Route of Administration", "Char", 40, VariableCore.EXPECTED, codelist="ROUTE"),
                SDTMVariable("EXLOT", "Lot Number", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("EXLOC", "Location of Dose Administration", "Char", 40, VariableCore.PERMISSIBLE, codelist="LOC"),
                SDTMVariable("EXSTDTC", "Start Date/Time of Treatment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EXENDTC", "End Date/Time of Treatment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EXDY", "Study Day of Start of Treatment", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("EXENDY", "Study Day of End of Treatment", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("EXDUR", "Duration", "Char", 20, VariableCore.PERMISSIBLE),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["CM"] = SDTMDomain(
            code="CM",
            name="Concomitant Medications",
            label="Concomitant/Prior Medications",
            domain_class=DomainClass.INTERVENTIONS,
            structure="One record per medication per subject",
            purpose="Documents prior and concomitant medications",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("CMSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("CMSPID", "Sponsor-Defined Identifier", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("CMTRT", "Reported Name of Drug or Therapy", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("CMMODIFY", "Modified Reported Name", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("CMDECOD", "Standardized Medication Name", "Char", 200, VariableCore.EXPECTED,
                            description="WHODrug preferred name"),
                SDTMVariable("CMCAT", "Category for Medication", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("CMSCAT", "Subcategory for Medication", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("CMPRESP", "Pre-Specified", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("CMOCCUR", "Occurrence", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("CMDOSE", "Dose per Administration", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("CMDOSU", "Dose Units", "Char", 40, VariableCore.EXPECTED, codelist="UNIT"),
                SDTMVariable("CMDOSFRM", "Dose Form", "Char", 40, VariableCore.PERMISSIBLE, codelist="FRM"),
                SDTMVariable("CMDOSFRQ", "Dosing Frequency per Interval", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("CMROUTE", "Route of Administration", "Char", 40, VariableCore.EXPECTED, codelist="ROUTE"),
                SDTMVariable("CMSTDTC", "Start Date/Time of Medication", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("CMENDTC", "End Date/Time of Medication", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("CMSTDY", "Study Day of Start of Medication", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("CMENDY", "Study Day of End of Medication", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("CMINDC", "Indication", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("CMCLAS", "Medication Class", "Char", 200, VariableCore.PERMISSIBLE,
                            description="ATC class"),
                SDTMVariable("CMCLASCD", "Medication Class Code", "Char", 40, VariableCore.PERMISSIBLE),
            ]
        )

        # ===== EVENTS DOMAINS =====

        self.DOMAIN_TEMPLATES["AE"] = SDTMDomain(
            code="AE",
            name="Adverse Events",
            label="Adverse Events",
            domain_class=DomainClass.EVENTS,
            structure="One record per adverse event per subject",
            purpose="Documents all adverse events during the study",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("AESEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("AESPID", "Sponsor-Defined Identifier", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("AETERM", "Reported Term for the Adverse Event", "Char", 200, VariableCore.REQUIRED,
                            description="Verbatim term as reported"),
                SDTMVariable("AEMODIFY", "Modified Reported Term", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("AELLT", "Lowest Level Term", "Char", 200, VariableCore.PERMISSIBLE,
                            description="MedDRA LLT"),
                SDTMVariable("AELLTCD", "Lowest Level Term Code", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("AEDECOD", "Dictionary-Derived Term", "Char", 200, VariableCore.REQUIRED,
                            description="MedDRA Preferred Term"),
                SDTMVariable("AEPTCD", "Preferred Term Code", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("AEHLT", "High Level Term", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("AEHLTCD", "High Level Term Code", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("AEHLGT", "High Level Group Term", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("AEHLGTCD", "High Level Group Term Code", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("AEBODSYS", "Body System or Organ Class", "Char", 200, VariableCore.EXPECTED,
                            description="MedDRA System Organ Class"),
                SDTMVariable("AEBDSYCD", "Body System or Organ Class Code", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("AESOC", "Primary System Organ Class", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("AESOCCD", "Primary System Organ Class Code", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("AELOC", "Location of Event", "Char", 40, VariableCore.PERMISSIBLE, codelist="LOC"),
                SDTMVariable("AESEV", "Severity/Intensity", "Char", 20, VariableCore.EXPECTED, codelist="AESEV"),
                SDTMVariable("AESER", "Serious Event", "Char", 1, VariableCore.REQUIRED, codelist="NY"),
                SDTMVariable("AEACN", "Action Taken with Study Treatment", "Char", 40, VariableCore.EXPECTED, codelist="ACN"),
                SDTMVariable("AEACNOTH", "Other Action Taken", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("AEREL", "Causality", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("AEPATT", "Pattern of Event", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("AEOUT", "Outcome of Adverse Event", "Char", 40, VariableCore.EXPECTED, codelist="OUT"),
                SDTMVariable("AESCAN", "Involves Cancer", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("AESCONG", "Congenital Anomaly or Birth Defect", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("AESDISAB", "Persist/Signif Disability/Incapacity", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("AESDTH", "Results in Death", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("AESHOSP", "Requires or Prolongs Hospitalization", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("AESLIFE", "Is Life Threatening", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("AESOD", "Other Serious Event", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("AESMIE", "Other Medically Important Event", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("AECONTRT", "Concomitant Treatment Given", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("AESTDTC", "Start Date/Time of Adverse Event", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("AEENDTC", "End Date/Time of Adverse Event", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("AESTDY", "Study Day of Start of Event", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("AEENDY", "Study Day of End of Event", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("AEDUR", "Duration of Event", "Char", 20, VariableCore.PERMISSIBLE),
                SDTMVariable("AEENRF", "End Relative to Reference Period", "Char", 10, VariableCore.PERMISSIBLE),
                SDTMVariable("AEENRTPT", "End Relative to Reference Time Point", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("AEENTPT", "End Reference Time Point", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["DS"] = SDTMDomain(
            code="DS",
            name="Disposition",
            label="Disposition",
            domain_class=DomainClass.EVENTS,
            structure="One record per disposition status per subject",
            purpose="Documents subject disposition and study completion status",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("DSSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("DSSPID", "Sponsor-Defined Identifier", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("DSTERM", "Reported Term for Disposition Event", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("DSDECOD", "Standardized Disposition Term", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("DSCAT", "Category for Disposition Event", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("DSSCAT", "Subcategory for Disposition Event", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("DSSTDTC", "Start Date/Time of Disposition Event", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("DSSTDY", "Study Day of Start of Event", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["MH"] = SDTMDomain(
            code="MH",
            name="Medical History",
            label="Medical History",
            domain_class=DomainClass.EVENTS,
            structure="One record per medical history event per subject",
            purpose="Documents prior medical history",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("MHSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("MHSPID", "Sponsor-Defined Identifier", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("MHTERM", "Reported Term for the Medical History", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("MHMODIFY", "Modified Reported Term", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("MHDECOD", "Dictionary-Derived Term", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("MHCAT", "Category for Medical History", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("MHSCAT", "Subcategory for Medical History", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("MHPRESP", "Pre-Specified", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("MHOCCUR", "Occurrence", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("MHBODSYS", "Body System or Organ Class", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("MHSTDTC", "Start Date/Time of History Event", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("MHENDTC", "End Date/Time of History Event", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("MHENRF", "End Relative to Reference Period", "Char", 10, VariableCore.EXPECTED),
            ]
        )

        self.DOMAIN_TEMPLATES["DV"] = SDTMDomain(
            code="DV",
            name="Protocol Deviations",
            label="Protocol Deviations",
            domain_class=DomainClass.EVENTS,
            structure="One record per protocol deviation per subject",
            purpose="Documents protocol deviations for BIMO review",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("DVSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("DVSPID", "Sponsor-Defined Identifier", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("DVTERM", "Protocol Deviation Term", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("DVDECOD", "Standardized Protocol Deviation Term", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("DVCAT", "Category for Protocol Deviation", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("DVSCAT", "Subcategory for Protocol Deviation", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("DVSTDTC", "Start Date/Time of Deviation", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("DVENDTC", "End Date/Time of Deviation", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        # ===== FINDINGS DOMAINS =====

        self.DOMAIN_TEMPLATES["LB"] = SDTMDomain(
            code="LB",
            name="Laboratory Test Results",
            label="Laboratory Test Results",
            domain_class=DomainClass.FINDINGS,
            structure="One record per lab test per time point per subject",
            purpose="Documents laboratory test results",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("LBSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("LBSPID", "Sponsor-Defined Identifier", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("LBTESTCD", "Lab Test or Examination Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("LBTEST", "Lab Test or Examination Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("LBCAT", "Category for Lab Test", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("LBSCAT", "Subcategory for Lab Test", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("LBORRES", "Result or Finding in Original Units", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("LBORRESU", "Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("LBORNRLO", "Reference Range Lower Limit-Orig Unit", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("LBORNRHI", "Reference Range Upper Limit-Orig Unit", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("LBSTRESC", "Character Result/Finding in Std Format", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("LBSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("LBSTRESU", "Standard Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("LBSTNRLO", "Reference Range Lower Limit-Std Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("LBSTNRHI", "Reference Range Upper Limit-Std Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("LBSTNRC", "Reference Range for Char Rslt-Std Units", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("LBNRIND", "Reference Range Indicator", "Char", 10, VariableCore.EXPECTED),
                SDTMVariable("LBSTAT", "Completion Status", "Char", 10, VariableCore.PERMISSIBLE),
                SDTMVariable("LBREASND", "Reason Not Done", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("LBNAM", "Vendor Name", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("LBSPEC", "Specimen Type", "Char", 40, VariableCore.EXPECTED, codelist="SPECTYPE"),
                SDTMVariable("LBSPCCND", "Specimen Condition", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("LBMETHOD", "Method of Test or Examination", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("LBBLFL", "Baseline Flag", "Char", 1, VariableCore.EXPECTED, codelist="NY"),
                SDTMVariable("LBFAST", "Fasting Status", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("LBDRVFL", "Derived Flag", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("LBTOX", "Toxicity", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("LBTOXGR", "Standard Toxicity Grade", "Char", 10, VariableCore.PERMISSIBLE),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VISITDY", "Planned Study Day of Visit", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("LBDTC", "Date/Time of Specimen Collection", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("LBDY", "Study Day of Specimen Collection", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("LBTPT", "Planned Time Point Name", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("LBTPTNUM", "Planned Time Point Number", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["VS"] = SDTMDomain(
            code="VS",
            name="Vital Signs",
            label="Vital Signs",
            domain_class=DomainClass.FINDINGS,
            structure="One record per vital sign per time point per subject",
            purpose="Documents vital sign measurements",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("VSSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("VSSPID", "Sponsor-Defined Identifier", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("VSTESTCD", "Vital Signs Test Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("VSTEST", "Vital Signs Test Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("VSCAT", "Category for Vital Signs", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("VSSCAT", "Subcategory for Vital Signs", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("VSPOS", "Vital Signs Position of Subject", "Char", 40, VariableCore.EXPECTED, codelist="POSITION"),
                SDTMVariable("VSORRES", "Result or Finding in Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VSORRESU", "Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VSSTRESC", "Character Result/Finding in Std Format", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VSSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VSSTRESU", "Standard Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VSSTAT", "Completion Status", "Char", 10, VariableCore.PERMISSIBLE),
                SDTMVariable("VSREASND", "Reason Not Done", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("VSLOC", "Location of Vital Signs Measurement", "Char", 40, VariableCore.EXPECTED, codelist="LOC"),
                SDTMVariable("VSBLFL", "Baseline Flag", "Char", 1, VariableCore.EXPECTED, codelist="NY"),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VISITDY", "Planned Study Day of Visit", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("VSDTC", "Date/Time of Measurements", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("VSDY", "Study Day of Vital Signs", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VSTPT", "Planned Time Point Name", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("VSTPTNUM", "Planned Time Point Number", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["EG"] = SDTMDomain(
            code="EG",
            name="ECG Test Results",
            label="ECG Test Results",
            domain_class=DomainClass.FINDINGS,
            structure="One record per ECG observation per time point per subject",
            purpose="Documents electrocardiogram findings",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("EGSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("EGTESTCD", "ECG Test Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("EGTEST", "ECG Test Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("EGCAT", "Category for ECG", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("EGORRES", "Result or Finding in Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("EGORRESU", "Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("EGSTRESC", "Character Result/Finding in Std Format", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("EGSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("EGSTRESU", "Standard Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("EGSTAT", "Completion Status", "Char", 10, VariableCore.PERMISSIBLE),
                SDTMVariable("EGREASND", "Reason Not Done", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("EGBLFL", "Baseline Flag", "Char", 1, VariableCore.EXPECTED, codelist="NY"),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("EGDTC", "Date/Time of ECG", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EGDY", "Study Day of ECG", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        # Questionnaires domain for patient-reported outcomes
        self.DOMAIN_TEMPLATES["QS"] = SDTMDomain(
            code="QS",
            name="Questionnaires",
            label="Questionnaires",
            domain_class=DomainClass.FINDINGS,
            structure="One record per questionnaire item per time point per subject",
            purpose="Documents patient-reported outcomes and questionnaires",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("QSSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("QSSPID", "Sponsor-Defined Identifier", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("QSTESTCD", "Question Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("QSTEST", "Question Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("QSCAT", "Category for Questionnaire", "Char", 40, VariableCore.REQUIRED,
                            description="Questionnaire name, e.g., 'MAYO SCORE', 'SF-36'"),
                SDTMVariable("QSSCAT", "Subcategory for Questionnaire", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("QSORRES", "Result or Finding in Original Units", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("QSORRESU", "Original Units", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("QSSTRESC", "Character Result/Finding in Std Format", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("QSSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("QSSTRESU", "Standard Units", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("QSSTAT", "Completion Status", "Char", 10, VariableCore.PERMISSIBLE),
                SDTMVariable("QSREASND", "Reason Not Done", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("QSBLFL", "Baseline Flag", "Char", 1, VariableCore.EXPECTED, codelist="NY"),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("QSDTC", "Date/Time of Assessment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("QSDY", "Study Day of Assessment", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        # Tumor Results for oncology
        self.DOMAIN_TEMPLATES["TR"] = SDTMDomain(
            code="TR",
            name="Tumor Results",
            label="Tumor/Lesion Results",
            domain_class=DomainClass.FINDINGS,
            structure="One record per tumor assessment per time point per subject",
            purpose="Documents tumor measurements for RECIST evaluation",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("TRSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("TRGRPID", "Group ID", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("TRREFID", "Reference ID", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("TRSPID", "Sponsor-Defined Identifier", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("TRLNKID", "Link ID", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TRLNKGRP", "Link Group ID", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("TRTESTCD", "Tumor Test Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("TRTEST", "Tumor Test Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("TRORRES", "Result or Finding in Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TRORRESU", "Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TRSTRESC", "Character Result/Finding in Std Format", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TRSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("TRSTRESU", "Standard Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TRMETHOD", "Method of Test", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TREVAL", "Evaluator", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TRDTC", "Date/Time of Tumor Assessment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("TRDY", "Study Day of Tumor Assessment", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        # Tumor Response for oncology
        self.DOMAIN_TEMPLATES["RS"] = SDTMDomain(
            code="RS",
            name="Disease Response",
            label="Disease Response",
            domain_class=DomainClass.FINDINGS,
            structure="One record per response assessment per subject",
            purpose="Documents overall disease response (RECIST)",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("RSSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("RSGRPID", "Group ID", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("RSREFID", "Reference ID", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("RSSPID", "Sponsor-Defined Identifier", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("RSTESTCD", "Response Test Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("RSTEST", "Response Test Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("RSCAT", "Category for Response", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("RSORRES", "Result or Finding in Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("RSSTRESC", "Character Result in Standard Format", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("RSEVAL", "Evaluator", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("RSEVALID", "Evaluator Identifier", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("RSACPTFL", "Accepted Record Flag", "Char", 1, VariableCore.PERMISSIBLE, codelist="NY"),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("RSDTC", "Date/Time of Response Assessment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("RSDY", "Study Day of Response Assessment", "Num", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

    def generate(self, protocol_facts: Dict[str, Any]) -> SDTMSpecification:
        """
        Generate SDTM specification from protocol facts.

        Args:
            protocol_facts: Dictionary containing protocol/SAP information

        Returns:
            SDTMSpecification with all required domains
        """
        protocol_id = protocol_facts.get('protocol_id', 'UNKNOWN')

        spec = SDTMSpecification(
            protocol_id=protocol_id,
            generated_at=datetime.now().isoformat(),
            sdtm_version="3.4"
        )

        # Determine which domains are needed
        required_domains = self._determine_required_domains(protocol_facts)

        # Generate specification for each domain
        for domain_code in required_domains:
            domain = self._generate_domain_spec(domain_code, protocol_facts)
            if domain:
                spec.domains.append(domain)

        # Add Define-XML notes
        spec.define_xml_notes = self._generate_define_notes(protocol_facts, required_domains)

        return spec

    def _determine_required_domains(self, protocol_facts: Dict[str, Any]) -> List[str]:
        """Determine which SDTM domains are required based on protocol."""
        required = set()

        # ===== ALWAYS REQUIRED =====
        # These are required for every FDA submission
        required.add("DM")   # Demographics - always required
        required.add("AE")   # Adverse Events - always required for safety
        required.add("DS")   # Disposition - always required
        required.add("EX")   # Exposure - always required
        required.add("TS")   # Trial Summary - required by FDA
        required.add("TA")   # Trial Arms - required for randomized studies

        # ===== USUALLY REQUIRED =====
        required.add("CM")   # Concomitant Meds - almost always needed
        required.add("MH")   # Medical History - usually collected
        required.add("VS")   # Vital Signs - standard safety measure
        required.add("LB")   # Labs - standard safety measure

        # ===== CONDITIONAL BASED ON PROTOCOL =====

        # Therapeutic area specific
        therapeutic_area = protocol_facts.get('therapeutic_area', '').lower()

        if 'oncology' in therapeutic_area or 'cancer' in therapeutic_area:
            required.add("TR")  # Tumor Results
            required.add("RS")  # Disease Response (RECIST)

        if 'cardio' in therapeutic_area or 'cardiac' in therapeutic_area:
            required.add("EG")  # ECG

        # Check endpoints for PRO/questionnaires
        endpoints = protocol_facts.get('endpoints', [])
        primary_endpoint = protocol_facts.get('primary_endpoint', {})

        # IBD/GI studies often use Mayo Score, other questionnaires
        indication = protocol_facts.get('indication', '').lower()
        if any(term in therapeutic_area for term in ['ibd', 'colitis', 'crohn', 'gastro']):
            required.add("QS")  # Questionnaires for Mayo Score etc.
        elif any(term in indication for term in ['colitis', 'crohn', 'ibd', 'inflammatory bowel']):
            required.add("QS")  # Questionnaires for IBD assessments

        # Check for PRO endpoints
        endpoint_names = []
        if isinstance(primary_endpoint, dict):
            endpoint_names.append(primary_endpoint.get('name', '').lower())
        if isinstance(endpoints, list):
            for ep in endpoints:
                if isinstance(ep, dict):
                    endpoint_names.append(ep.get('name', '').lower())

        for name in endpoint_names:
            if any(term in name for term in ['score', 'questionnaire', 'pro', 'quality of life', 'qol', 'mayo']):
                required.add("QS")

        # Protocol deviations - required by FDA for BIMO
        required.add("DV")

        return sorted(list(required))

    def _generate_domain_spec(self, domain_code: str, protocol_facts: Dict[str, Any]) -> Optional[SDTMDomain]:
        """Generate specification for a specific domain."""
        if domain_code not in self.DOMAIN_TEMPLATES:
            return None

        # Get template and customize based on protocol
        template = self.DOMAIN_TEMPLATES[domain_code]

        # Create a copy with protocol-specific customizations
        domain = SDTMDomain(
            code=template.code,
            name=template.name,
            label=template.label,
            domain_class=template.domain_class,
            structure=template.structure,
            purpose=template.purpose,
            description=template.description,
            variables=template.variables.copy()
        )

        # Customize based on protocol
        domain = self._customize_domain(domain, protocol_facts)

        # Map to TLFs
        domain.required_for = self._map_domain_to_tlf(domain_code, protocol_facts)

        return domain

    def _customize_domain(self, domain: SDTMDomain, protocol_facts: Dict[str, Any]) -> SDTMDomain:
        """Customize domain based on protocol specifics."""

        # Add treatment arm values to DM
        if domain.code == "DM":
            treatments = protocol_facts.get('treatments', [])
            if treatments:
                arm_values = [t.get('name', '') for t in treatments if isinstance(t, dict)]
                # Update ARM variable description with actual values
                for var in domain.variables:
                    if var.name == "ARM":
                        var.description = f"Values: {', '.join(arm_values)}"

        # Add stratification factors to supplemental qualifiers note
        if domain.code == "DM":
            strat_factors = protocol_facts.get('stratification_factors', [])
            if strat_factors:
                domain.description += f"\n\nStratification factors (capture in SUPPDM): {', '.join(strat_factors)}"

        return domain

    def _map_domain_to_tlf(self, domain_code: str, protocol_facts: Dict[str, Any]) -> List[str]:
        """Map domain to TLFs that require it."""
        mapping = {
            "DM": ["Table 14.1.1 Demographics", "Listing 16.2.1 Demographics"],
            "AE": ["Table 14.3.1 AE Summary", "Table 14.3.2 AE by SOC/PT", "Listing 16.2.7 Adverse Events"],
            "DS": ["Table 14.1.2 Disposition"],
            "EX": ["Table 14.1.3 Exposure Summary"],
            "CM": ["Listing 16.2.4 Concomitant Medications"],
            "MH": ["Table 14.1.4 Medical History"],
            "LB": ["Table 14.3.8 Laboratory Shift Tables"],
            "VS": ["Table 14.3.9 Vital Signs Summary"],
            "EG": ["Table 14.3.10 ECG Findings"],
            "QS": ["Table 14.2.x Efficacy Endpoints (PRO)"],
            "TR": ["Table 14.2.x Tumor Response"],
            "RS": ["Table 14.2.x Disease Response (RECIST)"],
            "DV": ["Listing 16.1.2 Protocol Deviations"],
        }
        return mapping.get(domain_code, [])

    def _generate_define_notes(self, protocol_facts: Dict[str, Any], domains: List[str]) -> List[str]:
        """Generate notes for Define-XML preparation."""
        notes = [
            "Define-XML v2.1 should be used for FDA submissions",
            f"Total domains: {len(domains)}",
            "Ensure all codelists are mapped to NCI CDISC controlled terminology",
            "MedDRA version should be documented in Define-XML",
            "WHODrug version should be documented for CM domain",
        ]

        # Protocol-specific notes
        protocol_id = protocol_facts.get('protocol_id', '')
        if protocol_id:
            notes.append(f"Study identifier: {protocol_id}")

        # Add therapeutic area specific notes
        ta = protocol_facts.get('therapeutic_area', '').lower()
        if 'oncology' in ta:
            notes.append("RECIST version should be documented for tumor assessments")
        if 'ibd' in ta or 'colitis' in ta:
            notes.append("Mayo Score components should be mapped to QS domain")

        return notes

    def save_specification(self, spec: SDTMSpecification, output_dir: str) -> Dict[str, str]:
        """Save specification to files."""
        import os
        import json

        os.makedirs(output_dir, exist_ok=True)
        saved_files = {}

        # Save markdown documentation
        md_path = os.path.join(output_dir, "sdtm_specification.md")
        with open(md_path, 'w') as f:
            f.write(spec.to_markdown())
        saved_files['markdown'] = md_path

        # Save JSON for programmatic use
        json_path = os.path.join(output_dir, "sdtm_specification.json")
        with open(json_path, 'w') as f:
            json.dump({
                "protocol_id": spec.protocol_id,
                "generated_at": spec.generated_at,
                "sdtm_version": spec.sdtm_version,
                "domains": [d.to_dict() for d in spec.domains],
                "define_xml_notes": spec.define_xml_notes
            }, f, indent=2)
        saved_files['json'] = json_path

        return saved_files


# Factory function
def create_sdtm_spec_generator() -> SDTMSpecGenerator:
    """Create an SDTM specification generator."""
    return SDTMSpecGenerator()
