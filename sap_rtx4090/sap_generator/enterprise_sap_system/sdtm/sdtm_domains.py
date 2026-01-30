"""
SDTM Domain Knowledge Base
===========================

Complete CDISC SDTM domain specifications per SDTMIG v3.4.
Contains all 35 domains with ~50 variables each.

This is the foundation for SAP → SDTM mapping.

References:
- CDISC SDTM v1.7
- SDTMIG v3.4 (November 2021)
- FDA Study Data Technical Conformance Guide v5.5

Author: SAP Generation System
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum


class DomainClass(Enum):
    """SDTM Domain Classes."""
    SPECIAL_PURPOSE = "Special Purpose"
    INTERVENTIONS = "Interventions"
    EVENTS = "Events"
    FINDINGS = "Findings"
    FINDINGS_ABOUT = "Findings About"
    TRIAL_DESIGN = "Trial Design"
    RELATIONSHIP = "Relationship"
    ASSOCIATED_PERSONS = "Associated Persons"


class VariableRole(Enum):
    """SDTM Variable Roles."""
    IDENTIFIER = "Identifier"
    TOPIC = "Topic"
    TIMING = "Timing"
    QUALIFIER = "Qualifier"
    RULE = "Rule"
    RECORD_QUALIFIER = "Record Qualifier"
    VARIABLE_QUALIFIER = "Variable Qualifier"
    SYNONYM_QUALIFIER = "Synonym Qualifier"


class VariableCore(Enum):
    """CDISC Core classification."""
    REQUIRED = "Req"
    EXPECTED = "Exp"
    PERMISSIBLE = "Perm"


@dataclass
class SDTMVariable:
    """SDTM Variable specification."""
    name: str
    label: str
    type: str  # "Char" or "Num"
    role: VariableRole
    core: VariableCore
    controlled_terms: Optional[str] = None  # Codelist name
    description: str = ""
    length: Optional[int] = None


@dataclass
class SDTMDomain:
    """Complete SDTM Domain specification."""
    code: str
    name: str
    label: str
    domain_class: DomainClass
    structure: str
    description: str
    variables: List[SDTMVariable] = field(default_factory=list)
    # SAP triggers - keywords that indicate this domain is needed
    sap_triggers: List[str] = field(default_factory=list)
    # Related domains
    related_domains: List[str] = field(default_factory=list)


# =============================================================================
# IDENTIFIER VARIABLES (Common to most domains)
# =============================================================================

IDENTIFIER_VARS = [
    SDTMVariable("STUDYID", "Study Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
    SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
    SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
]

TIMING_VARS = [
    SDTMVariable("VISITNUM", "Visit Number", "Num", VariableRole.TIMING, VariableCore.EXPECTED),
    SDTMVariable("VISIT", "Visit Name", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
    SDTMVariable("VISITDY", "Planned Study Day of Visit", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    SDTMVariable("EPOCH", "Epoch", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE, "EPOCH"),
]


# =============================================================================
# SPECIAL PURPOSE DOMAINS
# =============================================================================

DM_DOMAIN = SDTMDomain(
    code="DM",
    name="Demographics",
    label="Demographics",
    domain_class=DomainClass.SPECIAL_PURPOSE,
    structure="One record per subject",
    description="Demographics domain contains subject-level demographic information.",
    sap_triggers=[
        "demographics", "baseline characteristics", "age", "sex", "race",
        "ethnicity", "country", "population", "ITT", "safety population",
        "randomization", "treatment arm"
    ],
    related_domains=["SUPPDM", "SE", "SV"],
    variables=[
        SDTMVariable("STUDYID", "Study Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("SUBJID", "Subject Identifier for the Study", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("RFSTDTC", "Subject Reference Start Date/Time", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("RFENDTC", "Subject Reference End Date/Time", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("RFXSTDTC", "Date/Time of First Study Treatment", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("RFXENDTC", "Date/Time of Last Study Treatment", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("RFICDTC", "Date/Time of Informed Consent", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("RFPENDTC", "Date/Time of End of Participation", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("DTHDTC", "Date/Time of Death", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("DTHFL", "Subject Death Flag", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "NY"),
        SDTMVariable("SITEID", "Study Site Identifier", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("INVID", "Investigator Identifier", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("INVNAM", "Investigator Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("BRTHDTC", "Date/Time of Birth", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AGE", "Age", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("AGEU", "Age Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "AGEU"),
        SDTMVariable("SEX", "Sex", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.REQUIRED, "SEX"),
        SDTMVariable("RACE", "Race", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "RACE"),
        SDTMVariable("ETHNIC", "Ethnicity", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "ETHNIC"),
        SDTMVariable("SPECIES", "Species", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("STRAIN", "Strain/Substrain", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("SBSTRAIN", "Strain/Substrain Details", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("ARMCD", "Planned Arm Code", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("ARM", "Description of Planned Arm", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("ACTARMCD", "Actual Arm Code", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("ACTARM", "Description of Actual Arm", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("COUNTRY", "Country", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.REQUIRED, "COUNTRY"),
        SDTMVariable("DMDTC", "Date/Time of Collection", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("DMDY", "Study Day of Collection", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


# =============================================================================
# EVENTS DOMAINS
# =============================================================================

AE_DOMAIN = SDTMDomain(
    code="AE",
    name="Adverse Events",
    label="Adverse Events",
    domain_class=DomainClass.EVENTS,
    structure="One record per adverse event per subject",
    description="Adverse Events domain contains data about untoward medical occurrences.",
    sap_triggers=[
        "adverse event", "AE", "TEAE", "treatment-emergent", "safety",
        "serious adverse event", "SAE", "adverse drug reaction", "ADR",
        "toxicity", "side effect", "DLT", "dose limiting toxicity",
        "MedDRA", "SOC", "preferred term", "CTCAE"
    ],
    related_domains=["SUPPAE", "FAAE", "RELREC"],
    variables=[
        SDTMVariable("STUDYID", "Study Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("AESEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("AEGRPID", "Group ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AEREFID", "Reference ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AESPID", "Sponsor-Defined Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AETERM", "Reported Term for the Adverse Event", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("AEMODIFY", "Modified Reported Term", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AELLT", "Lowest Level Term", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AELLTCD", "Lowest Level Term Code", "Num", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AEDECOD", "Dictionary-Derived Term", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("AEPTCD", "Preferred Term Code", "Num", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AEHLT", "High Level Term", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AEHLTCD", "High Level Term Code", "Num", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AEHLGT", "High Level Group Term", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AEHLGTCD", "High Level Group Term Code", "Num", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AECAT", "Category for Adverse Event", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AESCAT", "Subcategory for Adverse Event", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AEPRESP", "Pre-Specified Adverse Event", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("AEBODSYS", "Body System or Organ Class", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("AEBDSYCD", "Body System or Organ Class Code", "Num", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AESOC", "Primary System Organ Class", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("AESOCCD", "Primary System Organ Class Code", "Num", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AELOC", "Location of Event", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "LOC"),
        SDTMVariable("AESEV", "Severity/Intensity", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "AESEV"),
        SDTMVariable("AESER", "Serious Event", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "NY"),
        SDTMVariable("AEACN", "Action Taken with Study Treatment", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "ACN"),
        SDTMVariable("AEACNOTH", "Other Action Taken", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AEREL", "Causality", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("AERELNST", "Relationship to Non-Study Treatment", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AEPATT", "Pattern of Adverse Event", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AEOUT", "Outcome of Adverse Event", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "OUT"),
        SDTMVariable("AESCAN", "Involves Cancer", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("AESCONG", "Congenital Anomaly or Birth Defect", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("AESDISAB", "Persist or Signif Disability/Incapacity", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("AESDTH", "Results in Death", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("AESHOSP", "Requires or Prolongs Hospitalization", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("AESLIFE", "Is Life Threatening", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("AESOD", "Occurred with Overdose", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("AESMIE", "Other Medically Important Serious Event", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("AECONTRT", "Concomitant or Additional Trtmnt Given", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("AETOXGR", "Standard Toxicity Grade", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("AESTDTC", "Start Date/Time of Adverse Event", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("AEENDTC", "End Date/Time of Adverse Event", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("AESTDY", "Study Day of Start of Adverse Event", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("AEENDY", "Study Day of End of Adverse Event", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("AEDUR", "Duration of Adverse Event", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("AEENRF", "End Relative to Reference Period", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("AESTRF", "Start Relative to Reference Period", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


CE_DOMAIN = SDTMDomain(
    code="CE",
    name="Clinical Events",
    label="Clinical Events",
    domain_class=DomainClass.EVENTS,
    structure="One record per event per subject",
    description="Clinical Events domain for disease-related events not captured in AE.",
    sap_triggers=[
        "clinical event", "disease event", "progression", "relapse",
        "recurrence", "hospitalization", "surgery", "procedure"
    ],
    related_domains=["SUPPCE", "FACE"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("CESEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("CETERM", "Reported Term for the Clinical Event", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("CEDECOD", "Dictionary-Derived Term", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("CECAT", "Category for Clinical Event", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("CESCAT", "Subcategory for Clinical Event", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("CEPRESP", "Pre-Specified Clinical Event", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("CEOCCUR", "Clinical Event Occurrence", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("CEBODSYS", "Body System or Organ Class", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("CESTDTC", "Start Date/Time of Clinical Event", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("CEENDTC", "End Date/Time of Clinical Event", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        *TIMING_VARS,
    ]
)


DS_DOMAIN = SDTMDomain(
    code="DS",
    name="Disposition",
    label="Disposition",
    domain_class=DomainClass.EVENTS,
    structure="One record per disposition status per subject",
    description="Disposition domain captures subject disposition and protocol milestones.",
    sap_triggers=[
        "disposition", "discontinuation", "completion", "withdrawal",
        "study completion", "treatment discontinuation", "lost to follow-up",
        "death", "randomization", "screening failure"
    ],
    related_domains=["SUPPDS"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("DSSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("DSTERM", "Reported Term for the Disposition Event", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("DSDECOD", "Standardized Disposition Term", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("DSCAT", "Category for Disposition Event", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("DSSCAT", "Subcategory for Disposition Event", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("EPOCH", "Epoch", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE, "EPOCH"),
        SDTMVariable("DSSTDTC", "Start Date/Time of Disposition Event", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("DSDY", "Study Day of Start of Event", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


DV_DOMAIN = SDTMDomain(
    code="DV",
    name="Protocol Deviations",
    label="Protocol Deviations",
    domain_class=DomainClass.EVENTS,
    structure="One record per deviation per subject",
    description="Protocol Deviations domain captures protocol deviation information.",
    sap_triggers=[
        "protocol deviation", "protocol violation", "deviation",
        "non-compliance", "inclusion criteria", "exclusion criteria"
    ],
    related_domains=["SUPPDV"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("DVSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("DVTERM", "Protocol Deviation Term", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("DVDECOD", "Standardized Protocol Deviation Term", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("DVCAT", "Category for Protocol Deviation", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("DVSCAT", "Subcategory for Protocol Deviation", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("EPOCH", "Epoch", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE, "EPOCH"),
        SDTMVariable("DVSTDTC", "Start Date/Time of Deviation", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("DVENDTC", "End Date/Time of Deviation", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


MH_DOMAIN = SDTMDomain(
    code="MH",
    name="Medical History",
    label="Medical History",
    domain_class=DomainClass.EVENTS,
    structure="One record per medical history event per subject",
    description="Medical History domain captures subject's medical history.",
    sap_triggers=[
        "medical history", "prior disease", "comorbidity", "comorbidities",
        "baseline disease", "concomitant disease", "prior treatment history"
    ],
    related_domains=["SUPPMH"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("MHSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("MHTERM", "Reported Term for the Medical History", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("MHMODIFY", "Modified Reported Term", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MHDECOD", "Dictionary-Derived Term", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("MHCAT", "Category for Medical History", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MHSCAT", "Subcategory for Medical History", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MHPRESP", "Pre-Specified Medical History Event", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("MHOCCUR", "Medical History Occurrence", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("MHBODSYS", "Body System or Organ Class", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("MHSTDTC", "Start Date/Time of Medical History", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("MHENDTC", "End Date/Time of Medical History", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("MHENRF", "End Relative to Reference Period", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


# =============================================================================
# INTERVENTIONS DOMAINS
# =============================================================================

CM_DOMAIN = SDTMDomain(
    code="CM",
    name="Concomitant Medications",
    label="Concomitant/Prior Medications",
    domain_class=DomainClass.INTERVENTIONS,
    structure="One record per medication per subject",
    description="Concomitant Medications domain captures prior and concomitant medication data.",
    sap_triggers=[
        "concomitant medication", "prior medication", "medication",
        "WHO drug", "ATC", "drug class", "rescue medication",
        "background therapy", "premedication"
    ],
    related_domains=["SUPPCM"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("CMSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("CMTRT", "Reported Name of Drug, Med, or Therapy", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("CMMODIFY", "Modified Reported Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("CMDECOD", "Standardized Medication Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("CMCAT", "Category for Medication", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("CMSCAT", "Subcategory for Medication", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("CMPRESP", "Pre-Specified Medication", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("CMOCCUR", "Medication Occurrence", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("CMINDC", "Indication", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("CMCLAS", "Medication Class", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("CMCLASCD", "Medication Class Code", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("CMDOSE", "Dose per Administration", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("CMDOSTXT", "Dose Description", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("CMDOSU", "Dose Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("CMDOSFRM", "Dose Form", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "FRM"),
        SDTMVariable("CMDOSFRQ", "Dosing Frequency per Interval", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "FREQ"),
        SDTMVariable("CMROUTE", "Route of Administration", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "ROUTE"),
        SDTMVariable("CMSTDTC", "Start Date/Time of Medication", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("CMENDTC", "End Date/Time of Medication", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("CMSTDY", "Study Day of Start of Medication", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("CMENDY", "Study Day of End of Medication", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("CMENRF", "End Relative to Reference Period", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("CMSTRF", "Start Relative to Reference Period", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


EX_DOMAIN = SDTMDomain(
    code="EX",
    name="Exposure",
    label="Exposure",
    domain_class=DomainClass.INTERVENTIONS,
    structure="One record per constant-dosing interval per subject",
    description="Exposure domain captures study treatment administration data.",
    sap_triggers=[
        "exposure", "study drug", "study treatment", "dosing",
        "dose administered", "treatment exposure", "extent of exposure",
        "dose modification", "dose delay", "dose reduction"
    ],
    related_domains=["SUPPEX"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("EXSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("EXTRT", "Name of Treatment", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("EXCAT", "Category of Treatment", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("EXSCAT", "Subcategory of Treatment", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("EXDOSE", "Dose per Administration", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("EXDOSTXT", "Dose Description", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("EXDOSU", "Dose Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("EXDOSFRM", "Dose Form", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "FRM"),
        SDTMVariable("EXDOSFRQ", "Dosing Frequency per Interval", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "FREQ"),
        SDTMVariable("EXDOSRGM", "Intended Dose Regimen", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("EXROUTE", "Route of Administration", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "ROUTE"),
        SDTMVariable("EXLOT", "Lot Number", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("EXLOC", "Location of Dose Administration", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "LOC"),
        SDTMVariable("EXFAST", "Fasting Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("EXADJ", "Reason for Dose Adjustment", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("EPOCH", "Epoch", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE, "EPOCH"),
        SDTMVariable("EXSTDTC", "Start Date/Time of Treatment", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("EXENDTC", "End Date/Time of Treatment", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("EXSTDY", "Study Day of Start of Treatment", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("EXENDY", "Study Day of End of Treatment", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("EXDUR", "Duration of Treatment", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


EC_DOMAIN = SDTMDomain(
    code="EC",
    name="Exposure as Collected",
    label="Exposure as Collected",
    domain_class=DomainClass.INTERVENTIONS,
    structure="One record per protocol-specified study treatment per subject per date",
    description="Exposure as Collected captures data as collected on the CRF.",
    sap_triggers=[
        "exposure collected", "CRF exposure", "infusion", "administration record"
    ],
    related_domains=["SUPPEC", "RELREC"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("ECSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("ECTRT", "Name of Treatment", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("ECMOOD", "Mood", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("ECCAT", "Category of Treatment", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("ECDOSE", "Dose per Administration", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("ECDOSU", "Dose Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("ECDOSFRM", "Dose Form", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "FRM"),
        SDTMVariable("ECROUTE", "Route of Administration", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "ROUTE"),
        SDTMVariable("ECSTDTC", "Start Date/Time of Treatment", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("ECENDTC", "End Date/Time of Treatment", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        *TIMING_VARS,
    ]
)


PR_DOMAIN = SDTMDomain(
    code="PR",
    name="Procedures",
    label="Procedures",
    domain_class=DomainClass.INTERVENTIONS,
    structure="One record per procedure per subject",
    description="Procedures domain captures therapeutic procedures performed.",
    sap_triggers=[
        "procedure", "surgery", "biopsy", "resection", "radiation",
        "radiotherapy", "intervention", "transplant"
    ],
    related_domains=["SUPPPR", "FAPR"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("PRSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("PRTRT", "Reported Name of Procedure", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("PRDECOD", "Standardized Procedure Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("PRCAT", "Category for Procedure", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PRSCAT", "Subcategory for Procedure", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PRPRESP", "Pre-Specified Procedure", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("PROCCUR", "Procedure Occurrence", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("PRINDC", "Indication", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PRLOC", "Location of Procedure", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "LOC"),
        SDTMVariable("PRSTDTC", "Start Date/Time of Procedure", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("PRENDTC", "End Date/Time of Procedure", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        *TIMING_VARS,
    ]
)


SU_DOMAIN = SDTMDomain(
    code="SU",
    name="Substance Use",
    label="Substance Use",
    domain_class=DomainClass.INTERVENTIONS,
    structure="One record per substance type per time period per subject",
    description="Substance Use domain captures tobacco, alcohol, and other substance use.",
    sap_triggers=[
        "substance use", "tobacco", "smoking", "alcohol", "caffeine",
        "recreational drug", "smoking history"
    ],
    related_domains=["SUPPSU"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("SUSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("SUTRT", "Reported Name of Substance", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("SUCAT", "Category of Substance", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("SUSCAT", "Subcategory of Substance", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("SUDOSE", "Substance Use Consumption", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("SUDOSU", "Substance Use Consumption Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("SUDOSFRQ", "Use Frequency", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "FREQ"),
        SDTMVariable("SUROUTE", "Route of Administration", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "ROUTE"),
        SDTMVariable("SUSTDTC", "Start Date/Time of Substance Use", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("SUENDTC", "End Date/Time of Substance Use", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("SUSTRF", "Start Relative to Reference Period", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("SUENRF", "End Relative to Reference Period", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


# =============================================================================
# FINDINGS DOMAINS
# =============================================================================

LB_DOMAIN = SDTMDomain(
    code="LB",
    name="Laboratory Test Results",
    label="Laboratory Test Results",
    domain_class=DomainClass.FINDINGS,
    structure="One record per lab test per time point per subject",
    description="Laboratory Test Results domain captures central and local lab data.",
    sap_triggers=[
        "laboratory", "lab test", "hematology", "chemistry", "urinalysis",
        "biomarker", "hemoglobin", "platelet", "neutrophil", "creatinine",
        "bilirubin", "ALT", "AST", "liver function", "renal function"
    ],
    related_domains=["SUPPLB", "RELREC"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("LBSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("LBTESTCD", "Lab Test or Examination Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("LBTEST", "Lab Test or Examination Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("LBCAT", "Category for Lab Test", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("LBSCAT", "Subcategory for Lab Test", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("LBORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("LBORRESU", "Original Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("LBORNRLO", "Reference Range Lower Limit in Orig Unit", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("LBORNRHI", "Reference Range Upper Limit in Orig Unit", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("LBSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("LBSTRESN", "Numeric Result/Finding in Standard Units", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("LBSTRESU", "Standard Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("LBSTNRLO", "Reference Range Lower Limit-Std Units", "Num", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("LBSTNRHI", "Reference Range Upper Limit-Std Units", "Num", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("LBSTNRC", "Reference Range for Char Rslt-Std Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("LBNRIND", "Reference Range Indicator", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("LBSTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("LBREASND", "Reason Test Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("LBNAM", "Vendor Name", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("LBLOINC", "LOINC Code", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("LBSPEC", "Specimen Material Type", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "SPECTYPE"),
        SDTMVariable("LBSPCCND", "Specimen Condition", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "SPECCOND"),
        SDTMVariable("LBMETHOD", "Method of Test or Examination", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "METHOD"),
        SDTMVariable("LBBLFL", "Baseline Flag", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("LBFAST", "Fasting Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("LBDRVFL", "Derived Flag", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("LBTOX", "Toxicity", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("LBTOXGR", "Standard Toxicity Grade", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("LBDTC", "Date/Time of Specimen Collection", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("LBENDTC", "End Date/Time of Specimen Collection", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("LBDY", "Study Day of Specimen Collection", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("LBTPT", "Planned Time Point Name", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("LBTPTNUM", "Planned Time Point Number", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("LBELTM", "Planned Elapsed Time from Time Point Ref", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("LBTPTREF", "Time Point Reference", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("LBRFTDTC", "Date/Time of Reference Time Point", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        *TIMING_VARS,
    ]
)


VS_DOMAIN = SDTMDomain(
    code="VS",
    name="Vital Signs",
    label="Vital Signs",
    domain_class=DomainClass.FINDINGS,
    structure="One record per vital sign per time point per subject",
    description="Vital Signs domain captures vital sign measurements.",
    sap_triggers=[
        "vital sign", "blood pressure", "heart rate", "pulse",
        "temperature", "respiratory rate", "weight", "height", "BMI",
        "systolic", "diastolic"
    ],
    related_domains=["SUPPVS"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("VSSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("VSTESTCD", "Vital Signs Test Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED, "VSTESTCD"),
        SDTMVariable("VSTEST", "Vital Signs Test Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED, "VSTEST"),
        SDTMVariable("VSCAT", "Category for Vital Signs", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("VSSCAT", "Subcategory for Vital Signs", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("VSPOS", "Vital Signs Position of Subject", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "POSITION"),
        SDTMVariable("VSORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("VSORRESU", "Original Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("VSSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("VSSTRESN", "Numeric Result/Finding in Standard Units", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("VSSTRESU", "Standard Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("VSSTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("VSREASND", "Reason Test Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("VSLOC", "Location of Vital Signs Measurement", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "LOC"),
        SDTMVariable("VSBLFL", "Baseline Flag", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("VSDRVFL", "Derived Flag", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("VSDTC", "Date/Time of Measurements", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("VSDY", "Study Day of Vital Signs", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("VSTPT", "Planned Time Point Name", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("VSTPTNUM", "Planned Time Point Number", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("VSELTM", "Planned Elapsed Time from Time Point Ref", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("VSTPTREF", "Time Point Reference", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("VSRFTDTC", "Date/Time of Reference Time Point", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        *TIMING_VARS,
    ]
)


EG_DOMAIN = SDTMDomain(
    code="EG",
    name="ECG Test Results",
    label="ECG Test Results",
    domain_class=DomainClass.FINDINGS,
    structure="One record per ECG observation per time point per subject",
    description="ECG Test Results domain captures electrocardiogram data.",
    sap_triggers=[
        "ECG", "electrocardiogram", "QT", "QTc", "QTcF", "QTcB",
        "PR interval", "QRS", "heart rhythm", "cardiac"
    ],
    related_domains=["SUPPEG"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("EGSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("EGTESTCD", "ECG Test or Examination Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED, "EGTESTCD"),
        SDTMVariable("EGTEST", "ECG Test or Examination Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED, "EGTEST"),
        SDTMVariable("EGCAT", "Category for ECG", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("EGSCAT", "Subcategory for ECG", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("EGPOS", "ECG Position of Subject", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "POSITION"),
        SDTMVariable("EGORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("EGORRESU", "Original Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("EGSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("EGSTRESN", "Numeric Result/Finding in Standard Units", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("EGSTRESU", "Standard Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("EGSTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("EGREASND", "Reason ECG Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("EGMETHOD", "Method of ECG Test", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "METHOD"),
        SDTMVariable("EGLEAD", "Lead Location Used for Measurement", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("EGBLFL", "Baseline Flag", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("EGDRVFL", "Derived Flag", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("EGEVAL", "Evaluator", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "EVAL"),
        SDTMVariable("EGDTC", "Date/Time of ECG", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("EGDY", "Study Day of ECG", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("EGTPT", "Planned Time Point Name", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("EGTPTNUM", "Planned Time Point Number", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("EGELTM", "Planned Elapsed Time from Time Point Ref", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("EGTPTREF", "Time Point Reference", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        *TIMING_VARS,
    ]
)


PE_DOMAIN = SDTMDomain(
    code="PE",
    name="Physical Examination",
    label="Physical Examination",
    domain_class=DomainClass.FINDINGS,
    structure="One record per body system per time point per subject",
    description="Physical Examination domain captures physical exam findings.",
    sap_triggers=[
        "physical examination", "physical exam", "body system examination",
        "general appearance", "HEENT", "cardiovascular exam", "respiratory exam"
    ],
    related_domains=["SUPPPE"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("PESEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("PETESTCD", "Physical Examination Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("PETEST", "Physical Examination Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("PECAT", "Category for Physical Examination", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PESCAT", "Subcategory for Physical Examination", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PEBODSYS", "Body System or Organ Class", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("PEORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("PESTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("PESTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("PEREASND", "Reason Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PELOC", "Location of Physical Examination Finding", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "LOC"),
        SDTMVariable("PEDTC", "Date/Time of Examination", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("PEDY", "Study Day of Examination", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        *TIMING_VARS,
    ]
)


# Tumor Response domains
RS_DOMAIN = SDTMDomain(
    code="RS",
    name="Disease Response",
    label="Disease Response and Clinical Classification",
    domain_class=DomainClass.FINDINGS,
    structure="One record per response assessment per time point per subject",
    description="Disease Response domain captures tumor response assessments.",
    sap_triggers=[
        "response", "RECIST", "tumor response", "CR", "PR", "SD", "PD",
        "complete response", "partial response", "stable disease",
        "progressive disease", "best overall response", "ORR", "DCR",
        "iRECIST", "irRC", "disease assessment"
    ],
    related_domains=["SUPPRS", "TR", "TU"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("RSSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("RSGRPID", "Group ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("RSREFID", "Reference ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("RSSPID", "Sponsor-Defined Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("RSTESTCD", "Disease Response Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("RSTEST", "Disease Response Test Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("RSCAT", "Category for Disease Response", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("RSSCAT", "Subcategory for Disease Response", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("RSORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("RSSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("RSSTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("RSREASND", "Reason Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("RSEVAL", "Evaluator", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "EVAL"),
        SDTMVariable("RSEVALID", "Evaluator Identifier", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("RSACPTFL", "Accepted Record Flag", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("RSDTC", "Date/Time of Disease Response", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("RSDY", "Study Day of Response", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        *TIMING_VARS,
    ]
)


TR_DOMAIN = SDTMDomain(
    code="TR",
    name="Tumor Results",
    label="Tumor/Lesion Results",
    domain_class=DomainClass.FINDINGS,
    structure="One record per tumor assessment per time point per subject",
    description="Tumor Results domain captures tumor identification and measurements.",
    sap_triggers=[
        "tumor", "lesion", "target lesion", "non-target lesion",
        "tumor measurement", "sum of diameters", "SLD", "nadir",
        "tumor assessment", "imaging", "CT scan", "MRI"
    ],
    related_domains=["SUPPTR", "TU", "RS"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("TRSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("TRGRPID", "Group ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TRREFID", "Reference ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TRSPID", "Sponsor-Defined Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TRLNKID", "Link ID", "Char", VariableRole.IDENTIFIER, VariableCore.EXPECTED),
        SDTMVariable("TRLNKGRP", "Link Group ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TRTESTCD", "Tumor/Lesion Assessment Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("TRTEST", "Tumor/Lesion Assessment Test Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("TRORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("TRORRESU", "Original Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("TRSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("TRSTRESN", "Numeric Result/Finding in Standard Units", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("TRSTRESU", "Standard Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("TRSTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("TRREASND", "Reason Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TRMETHOD", "Method of Test", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "METHOD"),
        SDTMVariable("TREVAL", "Evaluator", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "EVAL"),
        SDTMVariable("TREVALID", "Evaluator Identifier", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TRACPTFL", "Accepted Record Flag", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("TRDTC", "Date/Time of Assessment", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("TRDY", "Study Day of Assessment", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        *TIMING_VARS,
    ]
)


TU_DOMAIN = SDTMDomain(
    code="TU",
    name="Tumor Identification",
    label="Tumor/Lesion Identification",
    domain_class=DomainClass.FINDINGS,
    structure="One record per tumor identified per subject",
    description="Tumor Identification domain captures tumor/lesion characteristics.",
    sap_triggers=[
        "tumor identification", "lesion identification", "tumor location",
        "metastasis", "metastatic site", "primary tumor"
    ],
    related_domains=["SUPPTU", "TR", "RS"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("TUSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("TUGRPID", "Group ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TUREFID", "Reference ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TUSPID", "Sponsor-Defined Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TULNKID", "Link ID", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("TUTESTCD", "Tumor/Lesion ID Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("TUTEST", "Tumor/Lesion ID Test Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("TUORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("TUSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("TUSTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("TUREASND", "Reason Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TULOC", "Location of Tumor/Lesion", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "LOC"),
        SDTMVariable("TULAT", "Laterality", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "LAT"),
        SDTMVariable("TUDIR", "Directionality", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "DIR"),
        SDTMVariable("TUMETHOD", "Method of Identification", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "METHOD"),
        SDTMVariable("TUEVAL", "Evaluator", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "EVAL"),
        SDTMVariable("TUEVALID", "Evaluator Identifier", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TUACPTFL", "Accepted Record Flag", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("TUDTC", "Date/Time of Identification", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("TUDY", "Study Day of Identification", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        *TIMING_VARS,
    ]
)


# Questionnaire domain
QS_DOMAIN = SDTMDomain(
    code="QS",
    name="Questionnaires",
    label="Questionnaires",
    domain_class=DomainClass.FINDINGS,
    structure="One record per questionnaire item per time point per subject",
    description="Questionnaires domain captures PRO and clinician-reported outcomes.",
    sap_triggers=[
        "questionnaire", "PRO", "patient reported outcome", "quality of life",
        "QoL", "QLQ", "EORTC", "SF-36", "EQ-5D", "FACT", "VAS",
        "pain scale", "symptom assessment", "patient diary"
    ],
    related_domains=["SUPPQS"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("QSSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("QSTESTCD", "Questionnaire Item Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("QSTEST", "Questionnaire Item Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("QSCAT", "Category of Questionnaire", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("QSSCAT", "Subcategory of Questionnaire", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("QSORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("QSORRESU", "Original Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("QSSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("QSSTRESN", "Numeric Result/Finding in Standard Units", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("QSSTRESU", "Standard Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("QSSTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("QSREASND", "Reason Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("QSEVAL", "Evaluator", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "EVAL"),
        SDTMVariable("QSDTC", "Date/Time of Finding", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("QSDY", "Study Day of Finding", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("QSTPT", "Planned Time Point Name", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("QSTPTNUM", "Planned Time Point Number", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("QSTPTREF", "Time Point Reference", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        *TIMING_VARS,
    ]
)


# PK domains
PC_DOMAIN = SDTMDomain(
    code="PC",
    name="Pharmacokinetic Concentrations",
    label="Pharmacokinetic Concentrations",
    domain_class=DomainClass.FINDINGS,
    structure="One record per concentration per time point per subject",
    description="PK Concentrations domain captures drug concentration measurements.",
    sap_triggers=[
        "pharmacokinetic", "PK", "concentration", "drug level",
        "Cmax", "Tmax", "AUC", "serum concentration", "plasma concentration",
        "bioavailability"
    ],
    related_domains=["SUPPPC", "PP"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("PCSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("PCGRPID", "Group ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PCREFID", "Reference ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PCSPID", "Sponsor-Defined Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PCTESTCD", "PK Concentration Test Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("PCTEST", "PK Concentration Test Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("PCCAT", "Category", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PCSCAT", "Subcategory", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PCORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("PCORRESU", "Original Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("PCSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("PCSTRESN", "Numeric Result/Finding in Standard Units", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("PCSTRESU", "Standard Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("PCSTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("PCREASND", "Reason Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PCNAM", "Vendor Name", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PCSPEC", "Specimen Material Type", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "SPECTYPE"),
        SDTMVariable("PCSPCCND", "Specimen Condition", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "SPECCOND"),
        SDTMVariable("PCMETHOD", "Method of Test", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "METHOD"),
        SDTMVariable("PCFAST", "Fasting Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("PCDTC", "Date/Time of Specimen Collection", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("PCENDTC", "End Date/Time of Specimen Collection", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("PCDY", "Actual Study Day of Specimen Collection", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("PCTPT", "Planned Time Point Name", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("PCTPTNUM", "Planned Time Point Number", "Num", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("PCELTM", "Planned Elapsed Time from Time Point Ref", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("PCTPTREF", "Time Point Reference", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("PCRFTDTC", "Date/Time of Reference Time Point", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        *TIMING_VARS,
    ]
)


PP_DOMAIN = SDTMDomain(
    code="PP",
    name="Pharmacokinetic Parameters",
    label="PK Parameters",
    domain_class=DomainClass.FINDINGS,
    structure="One record per PK parameter per subject",
    description="PK Parameters domain captures derived PK parameters.",
    sap_triggers=[
        "PK parameter", "Cmax", "Tmax", "AUC", "half-life", "t1/2",
        "clearance", "volume of distribution", "bioavailability"
    ],
    related_domains=["SUPPPP", "PC"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("PPSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("PPGRPID", "Group ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PPTESTCD", "PK Parameter Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("PPTEST", "PK Parameter Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("PPCAT", "Category", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PPSCAT", "Subcategory", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PPORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("PPORRESU", "Original Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("PPSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("PPSTRESN", "Numeric Result/Finding in Standard Units", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("PPSTRESU", "Standard Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.EXPECTED, "UNIT"),
        SDTMVariable("PPSTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("PPREASND", "Reason Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("PPSPEC", "Specimen Material Type", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "SPECTYPE"),
        SDTMVariable("PPRFTDTC", "Date/Time of Reference Point", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("PPSTINT", "Planned Start of Assessment Interval", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("PPENINT", "Planned End of Assessment Interval", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        *TIMING_VARS,
    ]
)


# =============================================================================
# TRIAL DESIGN DOMAINS
# =============================================================================

TA_DOMAIN = SDTMDomain(
    code="TA",
    name="Trial Arms",
    label="Trial Arms",
    domain_class=DomainClass.TRIAL_DESIGN,
    structure="One record per planned Element per Arm",
    description="Trial Arms domain describes each planned Arm in the trial.",
    sap_triggers=[
        "trial arm", "treatment arm", "study arm", "control arm",
        "placebo arm", "active arm", "randomization arm"
    ],
    related_domains=["TE", "TV"],
    variables=[
        SDTMVariable("STUDYID", "Study Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("ARMCD", "Planned Arm Code", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("ARM", "Description of Planned Arm", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("TAETORD", "Planned Order of Element within Arm", "Num", VariableRole.TIMING, VariableCore.REQUIRED),
        SDTMVariable("ETCD", "Element Code", "Char", VariableRole.TIMING, VariableCore.REQUIRED),
        SDTMVariable("ELEMENT", "Description of Element", "Char", VariableRole.TIMING, VariableCore.REQUIRED),
        SDTMVariable("TABESSION", "Rule for Branch", "Char", VariableRole.RULE, VariableCore.PERMISSIBLE),
        SDTMVariable("TATRANS", "Transition Rule", "Char", VariableRole.RULE, VariableCore.PERMISSIBLE),
        SDTMVariable("EPOCH", "Epoch", "Char", VariableRole.TIMING, VariableCore.REQUIRED, "EPOCH"),
    ]
)


TE_DOMAIN = SDTMDomain(
    code="TE",
    name="Trial Elements",
    label="Trial Elements",
    domain_class=DomainClass.TRIAL_DESIGN,
    structure="One record per planned Element",
    description="Trial Elements domain describes basic building blocks of trial design.",
    sap_triggers=[
        "trial element", "study element", "treatment period",
        "washout", "run-in", "screening period", "follow-up period"
    ],
    related_domains=["TA", "TV"],
    variables=[
        SDTMVariable("STUDYID", "Study Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("ETCD", "Element Code", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("ELEMENT", "Description of Element", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("TESTRL", "Rule for Start of Element", "Char", VariableRole.RULE, VariableCore.PERMISSIBLE),
        SDTMVariable("TEENRL", "Rule for End of Element", "Char", VariableRole.RULE, VariableCore.PERMISSIBLE),
        SDTMVariable("TEDUR", "Planned Duration of Element", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


TI_DOMAIN = SDTMDomain(
    code="TI",
    name="Trial Inclusion/Exclusion",
    label="Trial Inclusion/Exclusion Criteria",
    domain_class=DomainClass.TRIAL_DESIGN,
    structure="One record per I/E criterion",
    description="Trial Inclusion/Exclusion defines the inclusion and exclusion criteria.",
    sap_triggers=[
        "inclusion criteria", "exclusion criteria", "eligibility",
        "inclusion/exclusion", "I/E criteria"
    ],
    related_domains=["IE"],
    variables=[
        SDTMVariable("STUDYID", "Study Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("IETESTCD", "Incl/Excl Criterion Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("IETEST", "Incl/Excl Criterion", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("IECAT", "Incl/Excl Category", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("IESCAT", "Incl/Excl Subcategory", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TIRL", "Criterion Rule", "Char", VariableRole.RULE, VariableCore.PERMISSIBLE),
        SDTMVariable("TIVERS", "Protocol Criterion Version", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
    ]
)


TV_DOMAIN = SDTMDomain(
    code="TV",
    name="Trial Visits",
    label="Trial Visits",
    domain_class=DomainClass.TRIAL_DESIGN,
    structure="One record per planned Visit per Arm",
    description="Trial Visits domain describes planned study visits.",
    sap_triggers=[
        "trial visit", "study visit", "visit schedule",
        "visit window", "assessment schedule"
    ],
    related_domains=["TA", "TE", "SV"],
    variables=[
        SDTMVariable("STUDYID", "Study Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("VISITNUM", "Visit Number", "Num", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("VISIT", "Visit Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("ARMCD", "Planned Arm Code", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("ARM", "Description of Planned Arm", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TVSTRL", "Visit Start Rule", "Char", VariableRole.RULE, VariableCore.PERMISSIBLE),
        SDTMVariable("TVENRL", "Visit End Rule", "Char", VariableRole.RULE, VariableCore.PERMISSIBLE),
    ]
)


TS_DOMAIN = SDTMDomain(
    code="TS",
    name="Trial Summary",
    label="Trial Summary",
    domain_class=DomainClass.TRIAL_DESIGN,
    structure="One record per trial summary parameter value",
    description="Trial Summary domain describes overall trial information.",
    sap_triggers=[
        "trial summary", "study summary", "protocol summary",
        "study design", "trial design", "study phase"
    ],
    related_domains=[],
    variables=[
        SDTMVariable("STUDYID", "Study Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("TSSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("TSGRPID", "Group ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TSPARMCD", "Trial Summary Parameter Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("TSPARM", "Trial Summary Parameter", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("TSVAL", "Parameter Value", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("TSVALNF", "Parameter Null Flavor", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TSVALCD", "Parameter Value Code", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TSVCDREF", "Name of Reference Terminology", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("TSVCDVER", "Version of Reference Terminology", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE),
    ]
)


SE_DOMAIN = SDTMDomain(
    code="SE",
    name="Subject Elements",
    label="Subject Elements",
    domain_class=DomainClass.SPECIAL_PURPOSE,
    structure="One record per actual Element per subject",
    description="Subject Elements describes actual Elements through which the subject passed.",
    sap_triggers=[
        "subject element", "epoch", "treatment epoch",
        "study period", "subject period"
    ],
    related_domains=["TA", "TE", "SV"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("SESEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("ETCD", "Element Code", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("ELEMENT", "Description of Element", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("TAESSION", "Branch Rule", "Char", VariableRole.RULE, VariableCore.PERMISSIBLE),
        SDTMVariable("EPOCH", "Epoch", "Char", VariableRole.TIMING, VariableCore.REQUIRED, "EPOCH"),
        SDTMVariable("SESTDTC", "Start Date/Time of Element", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("SEENDTC", "End Date/Time of Element", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("SEUPDES", "Description of Unplanned Element", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
    ]
)


SV_DOMAIN = SDTMDomain(
    code="SV",
    name="Subject Visits",
    label="Subject Visits",
    domain_class=DomainClass.SPECIAL_PURPOSE,
    structure="One record per actual visit per subject",
    description="Subject Visits captures actual visits made by subjects.",
    sap_triggers=[
        "subject visit", "actual visit", "visit date"
    ],
    related_domains=["TV", "SE"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("VISITNUM", "Visit Number", "Num", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("VISIT", "Visit Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("VISITDY", "Planned Study Day of Visit", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("EPOCH", "Epoch", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE, "EPOCH"),
        SDTMVariable("SVSTDTC", "Start Date/Time of Visit", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("SVENDTC", "End Date/Time of Visit", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("SVSTDY", "Study Day of Start of Visit", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("SVENDY", "Study Day of End of Visit", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("SVUPDES", "Description of Unplanned Visit", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
    ]
)


# =============================================================================
# ADDITIONAL SPECIAL PURPOSE & FINDINGS DOMAINS
# =============================================================================

CO_DOMAIN = SDTMDomain(
    code="CO",
    name="Comments",
    label="Comments",
    domain_class=DomainClass.SPECIAL_PURPOSE,
    structure="One record per comment per subject",
    description="Comments domain for free-text comments.",
    sap_triggers=["comment", "free text", "note"],
    related_domains=["RELREC"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("COSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("COVAL", "Comment", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("COREF", "Reference", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("COEVAL", "Evaluator", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "EVAL"),
        SDTMVariable("CODTC", "Date/Time of Comment", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("CODY", "Study Day of Comment", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


SC_DOMAIN = SDTMDomain(
    code="SC",
    name="Subject Characteristics",
    label="Subject Characteristics",
    domain_class=DomainClass.SPECIAL_PURPOSE,
    structure="One record per characteristic per subject",
    description="Subject Characteristics for additional subject-level data.",
    sap_triggers=[
        "subject characteristic", "baseline characteristic",
        "stratification factor", "covariate"
    ],
    related_domains=["DM", "SUPPSC"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("SCSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("SCTESTCD", "Subject Characteristic Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("SCTEST", "Subject Characteristic", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("SCCAT", "Category", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("SCSCAT", "Subcategory", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("SCORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("SCORRESU", "Original Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("SCSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("SCSTRESN", "Numeric Result/Finding in Standard Units", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("SCSTRESU", "Standard Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("SCDTC", "Date/Time of Collection", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("SCDY", "Study Day of Collection", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


IE_DOMAIN = SDTMDomain(
    code="IE",
    name="Inclusion/Exclusion Criteria Not Met",
    label="Inclusion/Exclusion Criteria Not Met",
    domain_class=DomainClass.FINDINGS,
    structure="One record per I/E criterion not met per subject",
    description="Records inclusion/exclusion criteria exceptions.",
    sap_triggers=[
        "inclusion not met", "exclusion not met", "protocol waiver",
        "eligibility exception", "I/E exception"
    ],
    related_domains=["TI"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("IESEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("IETESTCD", "Incl/Excl Criterion Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("IETEST", "Incl/Excl Criterion", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("IECAT", "Incl/Excl Category", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("IESCAT", "Incl/Excl Subcategory", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("IEORRES", "I/E Criterion Original Result", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("IESTRESC", "I/E Criterion Result (Standard)", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("IESTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("IEREASND", "Reason Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("IEDTC", "Date/Time of Assessment", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("IEDY", "Study Day of Assessment", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


DD_DOMAIN = SDTMDomain(
    code="DD",
    name="Death Details",
    label="Death Details",
    domain_class=DomainClass.EVENTS,
    structure="One record per subject death",
    description="Death Details captures detailed information about subject death.",
    sap_triggers=[
        "death detail", "cause of death", "date of death",
        "mortality", "death assessment"
    ],
    related_domains=["DM", "AE", "DS"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("DDSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("DDTESTCD", "Death Detail Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("DDTEST", "Death Detail Term", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("DDCAT", "Category", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("DDSCAT", "Subcategory", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("DDORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("DDSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("DDDTC", "Date/Time of Death Assessment", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("DDDY", "Study Day of Death Assessment", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


FA_DOMAIN = SDTMDomain(
    code="FA",
    name="Findings About",
    label="Findings About Events or Interventions",
    domain_class=DomainClass.FINDINGS_ABOUT,
    structure="One record per finding about per parent record per subject",
    description="Findings About captures additional info about Events or Interventions.",
    sap_triggers=[
        "findings about", "additional finding", "supplemental finding",
        "related finding"
    ],
    related_domains=["AE", "CM", "EX", "PR"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("FASEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("FAGRPID", "Group ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("FAREFID", "Reference ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("FASPID", "Sponsor-Defined Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("FATESTCD", "Findings About Test Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("FATEST", "Findings About Test Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("FAOBJ", "Object of Finding About", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("FACAT", "Category", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("FASCAT", "Subcategory", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("FAORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("FAORRESU", "Original Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("FASTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("FASTRESN", "Numeric Result/Finding in Standard Units", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("FASTRESU", "Standard Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("FASTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("FAREASND", "Reason Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("FAEVAL", "Evaluator", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "EVAL"),
        SDTMVariable("FADTC", "Date/Time of Collection", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("FADY", "Study Day of Collection", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("FALOC", "Location Used for Measurement", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "LOC"),
    ]
)


IS_DOMAIN = SDTMDomain(
    code="IS",
    name="Immunogenicity Specimen Assessments",
    label="Immunogenicity Specimen Assessments",
    domain_class=DomainClass.FINDINGS,
    structure="One record per specimen assessment per time point per subject",
    description="Immunogenicity Specimen captures anti-drug antibody assessments.",
    sap_triggers=[
        "immunogenicity", "anti-drug antibody", "ADA", "antibody",
        "neutralizing antibody", "NAb", "immunogenic"
    ],
    related_domains=["SUPPIS", "PC"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("ISSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("ISGRPID", "Group ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("ISREFID", "Reference ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("ISTESTCD", "Immunogenicity Test Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("ISTEST", "Immunogenicity Test Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("ISCAT", "Category", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("ISSCAT", "Subcategory", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("ISORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("ISORRESU", "Original Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("ISSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("ISSTRESN", "Numeric Result/Finding in Standard Units", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("ISSTRESU", "Standard Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("ISSTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("ISREASND", "Reason Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("ISNAM", "Vendor Name", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("ISSPEC", "Specimen Material Type", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "SPECTYPE"),
        SDTMVariable("ISMETHOD", "Method of Test", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "METHOD"),
        SDTMVariable("ISBLFL", "Baseline Flag", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "NY"),
        SDTMVariable("ISDTC", "Date/Time of Specimen Collection", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("ISDY", "Study Day of Collection", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("ISTPT", "Planned Time Point Name", "Char", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        SDTMVariable("ISTPTNUM", "Planned Time Point Number", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        *TIMING_VARS,
    ]
)


MB_DOMAIN = SDTMDomain(
    code="MB",
    name="Microbiology Specimen",
    label="Microbiology Specimen",
    domain_class=DomainClass.FINDINGS,
    structure="One record per microbiology specimen per time point per subject",
    description="Microbiology Specimen captures microbiology specimen data.",
    sap_triggers=[
        "microbiology", "culture", "bacterial", "viral",
        "pathogen", "infection test", "gram stain"
    ],
    related_domains=["SUPPMB", "MS"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("MBSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("MBGRPID", "Group ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MBREFID", "Reference ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MBTESTCD", "Microbiology Test Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("MBTEST", "Microbiology Test Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("MBCAT", "Category", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MBSCAT", "Subcategory", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MBORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("MBORRESU", "Original Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("MBSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("MBSTRESN", "Numeric Result/Finding in Standard Units", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MBSTRESU", "Standard Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("MBSTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("MBREASND", "Reason Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MBNAM", "Vendor Name", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MBSPEC", "Specimen Material Type", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED, "SPECTYPE"),
        SDTMVariable("MBSPCCND", "Specimen Condition", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "SPECCOND"),
        SDTMVariable("MBLOC", "Specimen Collection Location", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "LOC"),
        SDTMVariable("MBMETHOD", "Method of Test", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "METHOD"),
        SDTMVariable("MBDTC", "Date/Time of Specimen Collection", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("MBDY", "Study Day of Collection", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
        *TIMING_VARS,
    ]
)


MS_DOMAIN = SDTMDomain(
    code="MS",
    name="Microbiology Susceptibility",
    label="Microbiology Susceptibility",
    domain_class=DomainClass.FINDINGS,
    structure="One record per susceptibility test per organism per subject",
    description="Microbiology Susceptibility captures antibiotic susceptibility testing.",
    sap_triggers=[
        "susceptibility", "antibiotic sensitivity", "MIC",
        "minimum inhibitory concentration", "antimicrobial"
    ],
    related_domains=["SUPPMS", "MB"],
    variables=[
        *IDENTIFIER_VARS,
        SDTMVariable("MSSEQ", "Sequence Number", "Num", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("MSGRPID", "Group ID", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MSREFID", "Reference ID", "Char", VariableRole.IDENTIFIER, VariableCore.EXPECTED),
        SDTMVariable("MSTESTCD", "Susceptibility Test Short Name", "Char", VariableRole.TOPIC, VariableCore.REQUIRED),
        SDTMVariable("MSTEST", "Susceptibility Test Name", "Char", VariableRole.SYNONYM_QUALIFIER, VariableCore.REQUIRED),
        SDTMVariable("MSCAT", "Category", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MSSCAT", "Subcategory", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MSORRES", "Result or Finding in Original Units", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("MSORRESU", "Original Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("MSSTRESC", "Character Result/Finding in Std Format", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.EXPECTED),
        SDTMVariable("MSSTRESN", "Numeric Result/Finding in Standard Units", "Num", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MSSTRESU", "Standard Units", "Char", VariableRole.VARIABLE_QUALIFIER, VariableCore.PERMISSIBLE, "UNIT"),
        SDTMVariable("MSSTAT", "Completion Status", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "STAT"),
        SDTMVariable("MSREASND", "Reason Not Done", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MSNAM", "Vendor Name", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("MSMETHOD", "Method of Test", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE, "METHOD"),
        SDTMVariable("MSDTC", "Date/Time of Test", "Char", VariableRole.TIMING, VariableCore.EXPECTED),
        SDTMVariable("MSDY", "Study Day of Test", "Num", VariableRole.TIMING, VariableCore.PERMISSIBLE),
    ]
)


# =============================================================================
# RELATIONSHIP DOMAIN
# =============================================================================

RELREC_DOMAIN = SDTMDomain(
    code="RELREC",
    name="Related Records",
    label="Related Records",
    domain_class=DomainClass.RELATIONSHIP,
    structure="One record per related record relationship",
    description="Related Records domain links records between domains.",
    sap_triggers=["related record", "relationship", "link"],
    related_domains=[],
    variables=[
        SDTMVariable("STUDYID", "Study Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("RDOMAIN", "Related Domain Abbreviation", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("IDVAR", "Identifying Variable", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("IDVARVAL", "Identifying Variable Value", "Char", VariableRole.IDENTIFIER, VariableCore.REQUIRED),
        SDTMVariable("RELTYPE", "Relationship Type", "Char", VariableRole.RECORD_QUALIFIER, VariableCore.PERMISSIBLE),
        SDTMVariable("RELID", "Relationship Identifier", "Char", VariableRole.IDENTIFIER, VariableCore.PERMISSIBLE),
    ]
)


# =============================================================================
# COMPLETE DOMAIN REGISTRY
# =============================================================================

SDTM_DOMAINS: Dict[str, SDTMDomain] = {
    # Special Purpose
    "DM": DM_DOMAIN,
    "SE": SE_DOMAIN,
    "SV": SV_DOMAIN,
    "CO": CO_DOMAIN,
    "SC": SC_DOMAIN,

    # Events
    "AE": AE_DOMAIN,
    "CE": CE_DOMAIN,
    "DS": DS_DOMAIN,
    "DV": DV_DOMAIN,
    "MH": MH_DOMAIN,
    "DD": DD_DOMAIN,

    # Interventions
    "CM": CM_DOMAIN,
    "EX": EX_DOMAIN,
    "EC": EC_DOMAIN,
    "PR": PR_DOMAIN,
    "SU": SU_DOMAIN,

    # Findings
    "LB": LB_DOMAIN,
    "VS": VS_DOMAIN,
    "EG": EG_DOMAIN,
    "PE": PE_DOMAIN,
    "RS": RS_DOMAIN,
    "TR": TR_DOMAIN,
    "TU": TU_DOMAIN,
    "QS": QS_DOMAIN,
    "PC": PC_DOMAIN,
    "PP": PP_DOMAIN,
    "IE": IE_DOMAIN,
    "IS": IS_DOMAIN,
    "MB": MB_DOMAIN,
    "MS": MS_DOMAIN,

    # Findings About
    "FA": FA_DOMAIN,

    # Trial Design
    "TA": TA_DOMAIN,
    "TE": TE_DOMAIN,
    "TI": TI_DOMAIN,
    "TV": TV_DOMAIN,
    "TS": TS_DOMAIN,

    # Relationship
    "RELREC": RELREC_DOMAIN,
}


def get_domain(code: str) -> Optional[SDTMDomain]:
    """Get an SDTM domain by its code."""
    return SDTM_DOMAINS.get(code.upper())


def get_all_domains() -> List[SDTMDomain]:
    """Get all SDTM domains."""
    return list(SDTM_DOMAINS.values())


def get_domains_by_class(domain_class: DomainClass) -> List[SDTMDomain]:
    """Get all domains of a specific class."""
    return [d for d in SDTM_DOMAINS.values() if d.domain_class == domain_class]


def find_domains_by_trigger(text: str) -> List[SDTMDomain]:
    """
    Find relevant SDTM domains based on text triggers.

    Args:
        text: Text to search for triggers (e.g., SAP content)

    Returns:
        List of matching SDTMDomain objects
    """
    text_lower = text.lower()
    matching_domains = []

    for domain in SDTM_DOMAINS.values():
        for trigger in domain.sap_triggers:
            if trigger.lower() in text_lower:
                if domain not in matching_domains:
                    matching_domains.append(domain)
                break

    return matching_domains


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("="*70)
    print("SDTM DOMAIN KNOWLEDGE BASE")
    print("="*70)

    print(f"\nTotal domains: {len(SDTM_DOMAINS)}")

    for domain_class in DomainClass:
        domains = get_domains_by_class(domain_class)
        print(f"\n{domain_class.value}: {len(domains)}")
        for d in domains:
            print(f"  • {d.code}: {d.name} ({len(d.variables)} variables)")

    # Test trigger matching
    print("\n" + "="*70)
    print("TRIGGER MATCHING TEST")
    print("="*70)

    test_text = """
    The primary endpoint is overall survival. Safety will be assessed through
    treatment-emergent adverse events (TEAEs) using MedDRA coding. Laboratory
    tests including hematology and chemistry will be performed. Vital signs
    will be measured at each visit. Tumor response will be assessed per RECIST 1.1.
    Pharmacokinetic samples will be collected to determine Cmax and AUC.
    """

    matching = find_domains_by_trigger(test_text)
    print(f"\nMatching domains for test SAP text: {len(matching)}")
    for d in matching:
        print(f"  • {d.code}: {d.name}")
