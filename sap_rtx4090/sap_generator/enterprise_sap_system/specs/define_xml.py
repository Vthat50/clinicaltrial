#!/usr/bin/env python3
"""
Define-XML Generator - CDISC Define-XML 2.1 Compliant Metadata
==============================================================
Generates regulatory-compliant Define-XML metadata for:
- SDTM datasets (Study Data Tabulation Model)
- ADaM datasets (Analysis Data Model)

Follows CDISC Define-XML 2.1 specification with support for:
- Dataset definitions with labels and structures
- Variable definitions with types, lengths, origins
- Value level metadata for coded variables
- Codelists and controlled terminology
- Computational methods and derivations
- Comments and annotations
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime


class DataType(Enum):
    """Define-XML data types"""
    TEXT = "text"
    INTEGER = "integer"
    FLOAT = "float"
    DATE = "date"
    DATETIME = "datetime"
    TIME = "time"
    PARTIAL_DATE = "partialDate"
    PARTIAL_DATETIME = "partialDatetime"
    INCOMPLETE_DATE = "incompleteDate"
    INCOMPLETE_DATETIME = "incompleteDatetime"
    DURATION_DATETIME = "durationDatetime"


class VariableRole(Enum):
    """CDISC variable roles"""
    IDENTIFIER = "Identifier"
    TOPIC = "Topic"
    TIMING = "Timing"
    QUALIFIER = "Qualifier"
    RULE = "Rule"
    GROUPING = "Grouping Qualifier"
    RESULT = "Result Qualifier"
    SYNONYM = "Synonym Qualifier"
    RECORD = "Record Qualifier"
    VARIABLE = "Variable Qualifier"


class Origin(Enum):
    """Variable origin types"""
    CRF = "CRF"
    DERIVED = "Derived"
    ASSIGNED = "Assigned"
    PROTOCOL = "Protocol"
    EDC = "eDT"
    PREDECESSOR = "Predecessor"


@dataclass
class CodeListItem:
    """Individual codelist value"""
    coded_value: str
    decode: str
    order_number: int = 0
    extended_value: bool = False


@dataclass
class CodeList:
    """Codelist definition"""
    oid: str
    name: str
    data_type: DataType
    items: List[CodeListItem] = field(default_factory=list)
    external_codelist: Optional[str] = None  # For CT references


@dataclass
class ValueListItem:
    """Value level metadata item"""
    oid: str
    where_clause: str
    data_type: DataType
    length: int
    significant_digits: Optional[int] = None
    codelist_oid: Optional[str] = None
    origin: Origin = Origin.DERIVED
    comment: Optional[str] = None


@dataclass
class VariableDefinition:
    """Variable definition for Define-XML"""
    oid: str
    name: str
    label: str
    data_type: DataType
    length: int
    role: VariableRole
    order_number: int
    origin: Origin = Origin.CRF
    significant_digits: Optional[int] = None
    codelist_oid: Optional[str] = None
    value_list_oid: Optional[str] = None
    mandatory: bool = False
    comment: Optional[str] = None
    method_oid: Optional[str] = None
    crf_page: Optional[str] = None
    predecessor: Optional[str] = None


@dataclass
class DatasetDefinition:
    """Dataset definition"""
    oid: str
    name: str
    label: str
    domain: str
    structure: str  # e.g., "One record per subject"
    purpose: str  # "Tabulation" or "Analysis"
    class_name: str  # "FINDINGS", "EVENTS", "INTERVENTIONS", etc.
    sas_dataset_name: str
    variables: List[VariableDefinition] = field(default_factory=list)
    comment: Optional[str] = None
    is_reference: bool = False
    repeating: bool = True
    keys: List[str] = field(default_factory=list)


@dataclass
class ComputationalMethod:
    """Method definition for derived variables"""
    oid: str
    name: str
    type: str  # "Computation" or "Imputation"
    description: str
    formal_expression: Optional[str] = None
    document_ref: Optional[str] = None


@dataclass
class WhereClause:
    """Where clause for value level metadata"""
    oid: str
    comparator: str  # "EQ", "NE", "LT", "LE", "GT", "GE", "IN", "NOTIN"
    variable_oid: str
    check_values: List[str]
    soft_hard: str = "Soft"


class DefineXMLGenerator:
    """
    Production Define-XML 2.1 Generator

    Generates complete Define-XML metadata from SAP and protocol information.
    Supports both SDTM and ADaM standards with full CDISC compliance.
    """

    # CDISC Controlled Terminology version
    CT_VERSION = "2024-06-28"

    # Standard SDTM domains with metadata
    SDTM_DOMAINS = {
        "DM": {
            "label": "Demographics",
            "class": "SPECIAL PURPOSE",
            "structure": "One record per subject",
            "keys": ["STUDYID", "USUBJID"],
            "variables": [
                ("STUDYID", "Study Identifier", DataType.TEXT, 20, VariableRole.IDENTIFIER, True),
                ("DOMAIN", "Domain Abbreviation", DataType.TEXT, 2, VariableRole.IDENTIFIER, True),
                ("USUBJID", "Unique Subject Identifier", DataType.TEXT, 50, VariableRole.IDENTIFIER, True),
                ("SUBJID", "Subject Identifier for the Study", DataType.TEXT, 20, VariableRole.TOPIC, True),
                ("RFSTDTC", "Subject Reference Start Date/Time", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("RFENDTC", "Subject Reference End Date/Time", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("RFXSTDTC", "Date/Time of First Study Treatment", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("RFXENDTC", "Date/Time of Last Study Treatment", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("RFICDTC", "Date/Time of Informed Consent", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("RFPENDTC", "Date/Time of End of Participation", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("DTHDTC", "Date/Time of Death", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("DTHFL", "Subject Death Flag", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("SITEID", "Study Site Identifier", DataType.TEXT, 10, VariableRole.RECORD, False),
                ("INVID", "Investigator Identifier", DataType.TEXT, 20, VariableRole.RECORD, False),
                ("INVNAM", "Investigator Name", DataType.TEXT, 100, VariableRole.SYNONYM, False),
                ("BRTHDTC", "Date/Time of Birth", DataType.DATE, 10, VariableRole.RECORD, False),
                ("AGE", "Age", DataType.INTEGER, 8, VariableRole.RECORD, False),
                ("AGEU", "Age Units", DataType.TEXT, 10, VariableRole.VARIABLE, False),
                ("SEX", "Sex", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("RACE", "Race", DataType.TEXT, 100, VariableRole.RECORD, False),
                ("ETHNIC", "Ethnicity", DataType.TEXT, 50, VariableRole.RECORD, False),
                ("ARMCD", "Planned Arm Code", DataType.TEXT, 20, VariableRole.RECORD, False),
                ("ARM", "Description of Planned Arm", DataType.TEXT, 200, VariableRole.SYNONYM, False),
                ("ACTARMCD", "Actual Arm Code", DataType.TEXT, 20, VariableRole.RECORD, False),
                ("ACTARM", "Description of Actual Arm", DataType.TEXT, 200, VariableRole.SYNONYM, False),
                ("COUNTRY", "Country", DataType.TEXT, 3, VariableRole.RECORD, False),
                ("DMDTC", "Date/Time of Collection", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("DMDY", "Study Day of Collection", DataType.INTEGER, 8, VariableRole.TIMING, False),
            ]
        },
        "AE": {
            "label": "Adverse Events",
            "class": "EVENTS",
            "structure": "One record per adverse event per subject",
            "keys": ["STUDYID", "USUBJID", "AESEQ"],
            "variables": [
                ("STUDYID", "Study Identifier", DataType.TEXT, 20, VariableRole.IDENTIFIER, True),
                ("DOMAIN", "Domain Abbreviation", DataType.TEXT, 2, VariableRole.IDENTIFIER, True),
                ("USUBJID", "Unique Subject Identifier", DataType.TEXT, 50, VariableRole.IDENTIFIER, True),
                ("AESEQ", "Sequence Number", DataType.INTEGER, 8, VariableRole.IDENTIFIER, True),
                ("AEGRPID", "Group ID", DataType.TEXT, 20, VariableRole.IDENTIFIER, False),
                ("AETERM", "Reported Term for the Adverse Event", DataType.TEXT, 200, VariableRole.TOPIC, True),
                ("AEMODIFY", "Modified Reported Term", DataType.TEXT, 200, VariableRole.SYNONYM, False),
                ("AEDECOD", "Dictionary-Derived Term", DataType.TEXT, 200, VariableRole.SYNONYM, False),
                ("AEBODSYS", "Body System or Organ Class", DataType.TEXT, 200, VariableRole.RECORD, False),
                ("AESOC", "Primary System Organ Class", DataType.TEXT, 200, VariableRole.RECORD, False),
                ("AEHLT", "High Level Term", DataType.TEXT, 200, VariableRole.RECORD, False),
                ("AEHLGT", "High Level Group Term", DataType.TEXT, 200, VariableRole.RECORD, False),
                ("AELLT", "Lowest Level Term", DataType.TEXT, 200, VariableRole.RECORD, False),
                ("AELLTCD", "Lowest Level Term Code", DataType.INTEGER, 8, VariableRole.RECORD, False),
                ("AEPTCD", "Preferred Term Code", DataType.INTEGER, 8, VariableRole.RECORD, False),
                ("AESEV", "Severity/Intensity", DataType.TEXT, 20, VariableRole.RECORD, False),
                ("AESER", "Serious Event", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("AEACN", "Action Taken with Study Treatment", DataType.TEXT, 50, VariableRole.RECORD, False),
                ("AEREL", "Causality", DataType.TEXT, 50, VariableRole.RECORD, False),
                ("AEOUT", "Outcome of Adverse Event", DataType.TEXT, 50, VariableRole.RECORD, False),
                ("AESCAN", "Involves Cancer", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("AESCONG", "Congenital Anomaly or Birth Defect", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("AESDISAB", "Persist or Signif Disability/Incapacity", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("AESDTH", "Results in Death", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("AESHOSP", "Requires or Prolongs Hospitalization", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("AESLIFE", "Is Life Threatening", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("AESOD", "Occurred with Overdose", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("AESTDTC", "Start Date/Time of Adverse Event", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("AEENDTC", "End Date/Time of Adverse Event", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("AESTDY", "Study Day of Start of Adverse Event", DataType.INTEGER, 8, VariableRole.TIMING, False),
                ("AEENDY", "Study Day of End of Adverse Event", DataType.INTEGER, 8, VariableRole.TIMING, False),
            ]
        },
        "EX": {
            "label": "Exposure",
            "class": "INTERVENTIONS",
            "structure": "One record per constant dosing interval per subject",
            "keys": ["STUDYID", "USUBJID", "EXSEQ"],
            "variables": [
                ("STUDYID", "Study Identifier", DataType.TEXT, 20, VariableRole.IDENTIFIER, True),
                ("DOMAIN", "Domain Abbreviation", DataType.TEXT, 2, VariableRole.IDENTIFIER, True),
                ("USUBJID", "Unique Subject Identifier", DataType.TEXT, 50, VariableRole.IDENTIFIER, True),
                ("EXSEQ", "Sequence Number", DataType.INTEGER, 8, VariableRole.IDENTIFIER, True),
                ("EXTRT", "Name of Treatment", DataType.TEXT, 200, VariableRole.TOPIC, True),
                ("EXCAT", "Category of Treatment", DataType.TEXT, 100, VariableRole.GROUPING, False),
                ("EXDOSE", "Dose", DataType.FLOAT, 8, VariableRole.RECORD, False),
                ("EXDOSTXT", "Dose Description", DataType.TEXT, 200, VariableRole.RECORD, False),
                ("EXDOSU", "Dose Units", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("EXDOSFRM", "Dose Form", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("EXDOSFRQ", "Dosing Frequency per Interval", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("EXROUTE", "Route of Administration", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("EXLOT", "Lot Number", DataType.TEXT, 40, VariableRole.RECORD, False),
                ("EXSTDTC", "Start Date/Time of Treatment", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("EXENDTC", "End Date/Time of Treatment", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("EXSTDY", "Study Day of Start of Treatment", DataType.INTEGER, 8, VariableRole.TIMING, False),
                ("EXENDY", "Study Day of End of Treatment", DataType.INTEGER, 8, VariableRole.TIMING, False),
                ("EXDUR", "Duration of Treatment", DataType.TEXT, 20, VariableRole.TIMING, False),
            ]
        },
        "LB": {
            "label": "Laboratory Test Results",
            "class": "FINDINGS",
            "structure": "One record per lab test per time point per subject",
            "keys": ["STUDYID", "USUBJID", "LBSEQ"],
            "variables": [
                ("STUDYID", "Study Identifier", DataType.TEXT, 20, VariableRole.IDENTIFIER, True),
                ("DOMAIN", "Domain Abbreviation", DataType.TEXT, 2, VariableRole.IDENTIFIER, True),
                ("USUBJID", "Unique Subject Identifier", DataType.TEXT, 50, VariableRole.IDENTIFIER, True),
                ("LBSEQ", "Sequence Number", DataType.INTEGER, 8, VariableRole.IDENTIFIER, True),
                ("LBTESTCD", "Lab Test or Examination Short Name", DataType.TEXT, 8, VariableRole.TOPIC, True),
                ("LBTEST", "Lab Test or Examination Name", DataType.TEXT, 40, VariableRole.SYNONYM, True),
                ("LBCAT", "Category for Lab Test", DataType.TEXT, 100, VariableRole.GROUPING, False),
                ("LBSCAT", "Subcategory for Lab Test", DataType.TEXT, 100, VariableRole.GROUPING, False),
                ("LBORRES", "Result or Finding in Original Units", DataType.TEXT, 200, VariableRole.RESULT, False),
                ("LBORRESU", "Original Units", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("LBORNRLO", "Reference Range Lower Limit in Orig Unit", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("LBORNRHI", "Reference Range Upper Limit in Orig Unit", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("LBSTRESC", "Character Result/Finding in Std Format", DataType.TEXT, 200, VariableRole.RESULT, False),
                ("LBSTRESN", "Numeric Result/Finding in Std Units", DataType.FLOAT, 8, VariableRole.RESULT, False),
                ("LBSTRESU", "Standard Units", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("LBSTNRLO", "Reference Range Lower Limit-Std Units", DataType.FLOAT, 8, VariableRole.VARIABLE, False),
                ("LBSTNRHI", "Reference Range Upper Limit-Std Units", DataType.FLOAT, 8, VariableRole.VARIABLE, False),
                ("LBNRIND", "Reference Range Indicator", DataType.TEXT, 20, VariableRole.VARIABLE, False),
                ("LBSTAT", "Completion Status", DataType.TEXT, 8, VariableRole.RECORD, False),
                ("LBREASND", "Reason Test Not Done", DataType.TEXT, 200, VariableRole.RECORD, False),
                ("LBSPEC", "Specimen Type", DataType.TEXT, 40, VariableRole.RECORD, False),
                ("LBMETHOD", "Method of Test or Examination", DataType.TEXT, 100, VariableRole.RECORD, False),
                ("LBBLFL", "Baseline Flag", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("LBDRVFL", "Derived Flag", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("VISITNUM", "Visit Number", DataType.FLOAT, 8, VariableRole.TIMING, False),
                ("VISIT", "Visit Name", DataType.TEXT, 40, VariableRole.TIMING, False),
                ("VISITDY", "Planned Study Day of Visit", DataType.INTEGER, 8, VariableRole.TIMING, False),
                ("LBDTC", "Date/Time of Specimen Collection", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("LBDY", "Study Day of Specimen Collection", DataType.INTEGER, 8, VariableRole.TIMING, False),
            ]
        },
        "VS": {
            "label": "Vital Signs",
            "class": "FINDINGS",
            "structure": "One record per vital sign measurement per time point per subject",
            "keys": ["STUDYID", "USUBJID", "VSSEQ"],
            "variables": [
                ("STUDYID", "Study Identifier", DataType.TEXT, 20, VariableRole.IDENTIFIER, True),
                ("DOMAIN", "Domain Abbreviation", DataType.TEXT, 2, VariableRole.IDENTIFIER, True),
                ("USUBJID", "Unique Subject Identifier", DataType.TEXT, 50, VariableRole.IDENTIFIER, True),
                ("VSSEQ", "Sequence Number", DataType.INTEGER, 8, VariableRole.IDENTIFIER, True),
                ("VSTESTCD", "Vital Signs Test Short Name", DataType.TEXT, 8, VariableRole.TOPIC, True),
                ("VSTEST", "Vital Signs Test Name", DataType.TEXT, 40, VariableRole.SYNONYM, True),
                ("VSCAT", "Category for Vital Signs", DataType.TEXT, 100, VariableRole.GROUPING, False),
                ("VSPOS", "Vital Signs Position of Subject", DataType.TEXT, 40, VariableRole.RECORD, False),
                ("VSORRES", "Result or Finding in Original Units", DataType.TEXT, 200, VariableRole.RESULT, False),
                ("VSORRESU", "Original Units", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("VSSTRESC", "Character Result/Finding in Std Format", DataType.TEXT, 200, VariableRole.RESULT, False),
                ("VSSTRESN", "Numeric Result/Finding in Standard Units", DataType.FLOAT, 8, VariableRole.RESULT, False),
                ("VSSTRESU", "Standard Units", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("VSSTAT", "Completion Status", DataType.TEXT, 8, VariableRole.RECORD, False),
                ("VSREASND", "Reason Test Not Done", DataType.TEXT, 200, VariableRole.RECORD, False),
                ("VSBLFL", "Baseline Flag", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("VISITNUM", "Visit Number", DataType.FLOAT, 8, VariableRole.TIMING, False),
                ("VISIT", "Visit Name", DataType.TEXT, 40, VariableRole.TIMING, False),
                ("VISITDY", "Planned Study Day of Visit", DataType.INTEGER, 8, VariableRole.TIMING, False),
                ("VSDTC", "Date/Time of Measurements", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("VSDY", "Study Day of Measurements", DataType.INTEGER, 8, VariableRole.TIMING, False),
            ]
        },
        "CM": {
            "label": "Concomitant Medications",
            "class": "INTERVENTIONS",
            "structure": "One record per recorded medication occurrence per subject",
            "keys": ["STUDYID", "USUBJID", "CMSEQ"],
            "variables": [
                ("STUDYID", "Study Identifier", DataType.TEXT, 20, VariableRole.IDENTIFIER, True),
                ("DOMAIN", "Domain Abbreviation", DataType.TEXT, 2, VariableRole.IDENTIFIER, True),
                ("USUBJID", "Unique Subject Identifier", DataType.TEXT, 50, VariableRole.IDENTIFIER, True),
                ("CMSEQ", "Sequence Number", DataType.INTEGER, 8, VariableRole.IDENTIFIER, True),
                ("CMTRT", "Reported Name of Drug, Med, or Therapy", DataType.TEXT, 200, VariableRole.TOPIC, True),
                ("CMMODIFY", "Modified Reported Name", DataType.TEXT, 200, VariableRole.SYNONYM, False),
                ("CMDECOD", "Standardized Medication Name", DataType.TEXT, 200, VariableRole.SYNONYM, False),
                ("CMCAT", "Category for Medication", DataType.TEXT, 100, VariableRole.GROUPING, False),
                ("CMSCAT", "Subcategory for Medication", DataType.TEXT, 100, VariableRole.GROUPING, False),
                ("CMINDC", "Indication", DataType.TEXT, 200, VariableRole.RECORD, False),
                ("CMDOSE", "Dose per Administration", DataType.FLOAT, 8, VariableRole.RECORD, False),
                ("CMDOSTXT", "Dose Description", DataType.TEXT, 200, VariableRole.RECORD, False),
                ("CMDOSU", "Dose Units", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("CMDOSFRM", "Dose Form", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("CMDOSFRQ", "Dosing Frequency per Interval", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("CMROUTE", "Route of Administration", DataType.TEXT, 40, VariableRole.VARIABLE, False),
                ("CMSTDTC", "Start Date/Time of Medication", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("CMENDTC", "End Date/Time of Medication", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("CMSTDY", "Study Day of Start of Medication", DataType.INTEGER, 8, VariableRole.TIMING, False),
                ("CMENDY", "Study Day of End of Medication", DataType.INTEGER, 8, VariableRole.TIMING, False),
            ]
        },
        "MH": {
            "label": "Medical History",
            "class": "EVENTS",
            "structure": "One record per medical history event per subject",
            "keys": ["STUDYID", "USUBJID", "MHSEQ"],
            "variables": [
                ("STUDYID", "Study Identifier", DataType.TEXT, 20, VariableRole.IDENTIFIER, True),
                ("DOMAIN", "Domain Abbreviation", DataType.TEXT, 2, VariableRole.IDENTIFIER, True),
                ("USUBJID", "Unique Subject Identifier", DataType.TEXT, 50, VariableRole.IDENTIFIER, True),
                ("MHSEQ", "Sequence Number", DataType.INTEGER, 8, VariableRole.IDENTIFIER, True),
                ("MHTERM", "Reported Term for the Medical History", DataType.TEXT, 200, VariableRole.TOPIC, True),
                ("MHMODIFY", "Modified Reported Term", DataType.TEXT, 200, VariableRole.SYNONYM, False),
                ("MHDECOD", "Dictionary-Derived Term", DataType.TEXT, 200, VariableRole.SYNONYM, False),
                ("MHCAT", "Category for Medical History", DataType.TEXT, 100, VariableRole.GROUPING, False),
                ("MHSCAT", "Subcategory for Medical History", DataType.TEXT, 100, VariableRole.GROUPING, False),
                ("MHBODSYS", "Body System or Organ Class", DataType.TEXT, 200, VariableRole.RECORD, False),
                ("MHSOC", "Primary System Organ Class", DataType.TEXT, 200, VariableRole.RECORD, False),
                ("MHPRESP", "Pre-Specified", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("MHOCCUR", "Medical History Occurrence", DataType.TEXT, 1, VariableRole.RECORD, False),
                ("MHSTDTC", "Start Date/Time of Medical History", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("MHENDTC", "End Date/Time of Medical History", DataType.DATETIME, 20, VariableRole.TIMING, False),
            ]
        },
        "DS": {
            "label": "Disposition",
            "class": "EVENTS",
            "structure": "One record per disposition status or protocol milestone per subject",
            "keys": ["STUDYID", "USUBJID", "DSSEQ"],
            "variables": [
                ("STUDYID", "Study Identifier", DataType.TEXT, 20, VariableRole.IDENTIFIER, True),
                ("DOMAIN", "Domain Abbreviation", DataType.TEXT, 2, VariableRole.IDENTIFIER, True),
                ("USUBJID", "Unique Subject Identifier", DataType.TEXT, 50, VariableRole.IDENTIFIER, True),
                ("DSSEQ", "Sequence Number", DataType.INTEGER, 8, VariableRole.IDENTIFIER, True),
                ("DSTERM", "Reported Term for the Disposition Event", DataType.TEXT, 200, VariableRole.TOPIC, True),
                ("DSDECOD", "Standardized Disposition Term", DataType.TEXT, 200, VariableRole.SYNONYM, False),
                ("DSCAT", "Category for Disposition Event", DataType.TEXT, 100, VariableRole.GROUPING, False),
                ("DSSCAT", "Subcategory for Disposition Event", DataType.TEXT, 100, VariableRole.GROUPING, False),
                ("EPOCH", "Epoch", DataType.TEXT, 40, VariableRole.TIMING, False),
                ("DSSTDTC", "Start Date/Time of Disposition Event", DataType.DATETIME, 20, VariableRole.TIMING, False),
                ("DSDY", "Study Day of Start of Disposition Event", DataType.INTEGER, 8, VariableRole.TIMING, False),
            ]
        },
    }

    # Standard ADaM datasets with metadata
    ADAM_DATASETS = {
        "ADSL": {
            "label": "Subject-Level Analysis Dataset",
            "structure": "One record per subject",
            "class": "SUBJECT LEVEL ANALYSIS DATASET",
            "keys": ["STUDYID", "USUBJID"],
            "variables": [
                ("STUDYID", "Study Identifier", DataType.TEXT, 20, VariableRole.IDENTIFIER, True, Origin.ASSIGNED),
                ("USUBJID", "Unique Subject Identifier", DataType.TEXT, 50, VariableRole.IDENTIFIER, True, Origin.ASSIGNED),
                ("SUBJID", "Subject Identifier for the Study", DataType.TEXT, 20, VariableRole.IDENTIFIER, False, Origin.ASSIGNED),
                ("SITEID", "Study Site Identifier", DataType.TEXT, 10, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("AGE", "Age", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("AGEU", "Age Units", DataType.TEXT, 10, VariableRole.VARIABLE, False, Origin.ASSIGNED),
                ("AGEGR1", "Pooled Age Group 1", DataType.TEXT, 20, VariableRole.RECORD, False, Origin.DERIVED),
                ("AGEGR1N", "Pooled Age Group 1 (N)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("SEX", "Sex", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("SEXN", "Sex (N)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("RACE", "Race", DataType.TEXT, 100, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("RACEN", "Race (N)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("ETHNIC", "Ethnicity", DataType.TEXT, 50, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("ETHNICN", "Ethnicity (N)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("COUNTRY", "Country", DataType.TEXT, 3, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("ARM", "Description of Planned Arm", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("ARMCD", "Planned Arm Code", DataType.TEXT, 20, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("ACTARM", "Description of Actual Arm", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("ACTARMCD", "Actual Arm Code", DataType.TEXT, 20, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("TRT01P", "Planned Treatment for Period 01", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.DERIVED),
                ("TRT01PN", "Planned Treatment for Period 01 (N)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("TRT01A", "Actual Treatment for Period 01", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.DERIVED),
                ("TRT01AN", "Actual Treatment for Period 01 (N)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("TRTSDT", "Date of First Exposure to Treatment", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("TRTEDT", "Date of Last Exposure to Treatment", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("TRTDURD", "Total Treatment Duration (Days)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("RANDDT", "Date of Randomization", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("EOSDT", "End of Study Date", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("EOSSTT", "End of Study Status", DataType.TEXT, 50, VariableRole.RECORD, False, Origin.DERIVED),
                ("DCSREAS", "Reason for Discontinuation from Study", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.DERIVED),
                ("DTHDT", "Date of Death", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("DTHFL", "Subject Death Flag", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
                ("SAFFL", "Safety Population Flag", DataType.TEXT, 1, VariableRole.RECORD, True, Origin.DERIVED),
                ("ITTFL", "Intent-to-Treat Population Flag", DataType.TEXT, 1, VariableRole.RECORD, True, Origin.DERIVED),
                ("FASFL", "Full Analysis Set Population Flag", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
                ("PPROTFL", "Per-Protocol Population Flag", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
                ("RANDFL", "Randomized Population Flag", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
            ]
        },
        "ADAE": {
            "label": "Adverse Event Analysis Dataset",
            "structure": "One record per adverse event per subject",
            "class": "BASIC DATA STRUCTURE",
            "keys": ["STUDYID", "USUBJID", "AESEQ"],
            "variables": [
                ("STUDYID", "Study Identifier", DataType.TEXT, 20, VariableRole.IDENTIFIER, True, Origin.ASSIGNED),
                ("USUBJID", "Unique Subject Identifier", DataType.TEXT, 50, VariableRole.IDENTIFIER, True, Origin.ASSIGNED),
                ("AESEQ", "Sequence Number", DataType.INTEGER, 8, VariableRole.IDENTIFIER, True, Origin.ASSIGNED),
                ("TRTA", "Actual Treatment", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.DERIVED),
                ("TRTAN", "Actual Treatment (N)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("AEDECOD", "Dictionary-Derived Term", DataType.TEXT, 200, VariableRole.TOPIC, True, Origin.ASSIGNED),
                ("AEBODSYS", "Body System or Organ Class", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("AESOC", "Primary System Organ Class", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("AESEV", "Severity/Intensity", DataType.TEXT, 20, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("AESER", "Serious Event", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("AEREL", "Causality", DataType.TEXT, 50, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("AEOUT", "Outcome of Adverse Event", DataType.TEXT, 50, VariableRole.RECORD, False, Origin.ASSIGNED),
                ("ASTDT", "Analysis Start Date", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("AENDT", "Analysis End Date", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("ASTDY", "Analysis Start Relative Day", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("AENDY", "Analysis End Relative Day", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("AEDUR", "AE Duration (Days)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("AETRTEMFL", "Treatment Emergent Flag", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
                ("AOCCFL", "1st Occurrence within Subject Flag", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
                ("AOCCSFL", "1st Occurrence of SOC Flag", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
                ("AOCCPFL", "1st Occurrence of Preferred Term Flag", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
                ("ANL01FL", "Analysis Record Flag 01", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
            ]
        },
        "ADLB": {
            "label": "Laboratory Analysis Dataset",
            "structure": "One record per subject per parameter per analysis visit",
            "class": "BASIC DATA STRUCTURE",
            "keys": ["STUDYID", "USUBJID", "PARAMCD", "AVISIT"],
            "variables": [
                ("STUDYID", "Study Identifier", DataType.TEXT, 20, VariableRole.IDENTIFIER, True, Origin.ASSIGNED),
                ("USUBJID", "Unique Subject Identifier", DataType.TEXT, 50, VariableRole.IDENTIFIER, True, Origin.ASSIGNED),
                ("TRTA", "Actual Treatment", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.DERIVED),
                ("TRTAN", "Actual Treatment (N)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("PARAMCD", "Parameter Code", DataType.TEXT, 8, VariableRole.IDENTIFIER, True, Origin.DERIVED),
                ("PARAM", "Parameter", DataType.TEXT, 200, VariableRole.RECORD, True, Origin.DERIVED),
                ("PARAMN", "Parameter (N)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("PARCAT1", "Parameter Category 1", DataType.TEXT, 100, VariableRole.GROUPING, False, Origin.DERIVED),
                ("AVAL", "Analysis Value", DataType.FLOAT, 8, VariableRole.RESULT, False, Origin.DERIVED),
                ("AVALC", "Analysis Value (C)", DataType.TEXT, 200, VariableRole.RESULT, False, Origin.DERIVED),
                ("BASE", "Baseline Value", DataType.FLOAT, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("BASEC", "Baseline Value (C)", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.DERIVED),
                ("CHG", "Change from Baseline", DataType.FLOAT, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("PCHG", "Percent Change from Baseline", DataType.FLOAT, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("A1LO", "Analysis Range 1 Lower Limit", DataType.FLOAT, 8, VariableRole.VARIABLE, False, Origin.DERIVED),
                ("A1HI", "Analysis Range 1 Upper Limit", DataType.FLOAT, 8, VariableRole.VARIABLE, False, Origin.DERIVED),
                ("ANRIND", "Analysis Reference Range Indicator", DataType.TEXT, 20, VariableRole.RECORD, False, Origin.DERIVED),
                ("BNRIND", "Baseline Reference Range Indicator", DataType.TEXT, 20, VariableRole.RECORD, False, Origin.DERIVED),
                ("SHIFT1", "Shift 1", DataType.TEXT, 50, VariableRole.RECORD, False, Origin.DERIVED),
                ("AVISIT", "Analysis Visit", DataType.TEXT, 40, VariableRole.TIMING, True, Origin.DERIVED),
                ("AVISITN", "Analysis Visit (N)", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("ADT", "Analysis Date", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("ADY", "Analysis Relative Day", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("ABLFL", "Baseline Record Flag", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
                ("ANL01FL", "Analysis Record Flag 01", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
            ]
        },
        "ADEFF": {
            "label": "Efficacy Analysis Dataset",
            "structure": "One record per subject per parameter per analysis visit",
            "class": "BASIC DATA STRUCTURE",
            "keys": ["STUDYID", "USUBJID", "PARAMCD", "AVISIT"],
            "variables": [
                ("STUDYID", "Study Identifier", DataType.TEXT, 20, VariableRole.IDENTIFIER, True, Origin.ASSIGNED),
                ("USUBJID", "Unique Subject Identifier", DataType.TEXT, 50, VariableRole.IDENTIFIER, True, Origin.ASSIGNED),
                ("TRTA", "Actual Treatment", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.DERIVED),
                ("TRTAN", "Actual Treatment (N)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("PARAMCD", "Parameter Code", DataType.TEXT, 8, VariableRole.IDENTIFIER, True, Origin.DERIVED),
                ("PARAM", "Parameter", DataType.TEXT, 200, VariableRole.RECORD, True, Origin.DERIVED),
                ("PARAMN", "Parameter (N)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("PARCAT1", "Parameter Category 1", DataType.TEXT, 100, VariableRole.GROUPING, False, Origin.DERIVED),
                ("AVAL", "Analysis Value", DataType.FLOAT, 8, VariableRole.RESULT, False, Origin.DERIVED),
                ("AVALC", "Analysis Value (C)", DataType.TEXT, 200, VariableRole.RESULT, False, Origin.DERIVED),
                ("BASE", "Baseline Value", DataType.FLOAT, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("CHG", "Change from Baseline", DataType.FLOAT, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("PCHG", "Percent Change from Baseline", DataType.FLOAT, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("AVISIT", "Analysis Visit", DataType.TEXT, 40, VariableRole.TIMING, True, Origin.DERIVED),
                ("AVISITN", "Analysis Visit (N)", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("ADT", "Analysis Date", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("ADY", "Analysis Relative Day", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("ABLFL", "Baseline Record Flag", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
                ("ANL01FL", "Analysis Record Flag 01", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
                ("CRIT1", "Analysis Criterion 1", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.DERIVED),
                ("CRIT1FL", "Criterion 1 Evaluation Result Flag", DataType.TEXT, 1, VariableRole.RECORD, False, Origin.DERIVED),
            ]
        },
        "ADTTE": {
            "label": "Time-to-Event Analysis Dataset",
            "structure": "One record per subject per parameter",
            "class": "TIME-TO-EVENT",
            "keys": ["STUDYID", "USUBJID", "PARAMCD"],
            "variables": [
                ("STUDYID", "Study Identifier", DataType.TEXT, 20, VariableRole.IDENTIFIER, True, Origin.ASSIGNED),
                ("USUBJID", "Unique Subject Identifier", DataType.TEXT, 50, VariableRole.IDENTIFIER, True, Origin.ASSIGNED),
                ("TRTA", "Actual Treatment", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.DERIVED),
                ("TRTAN", "Actual Treatment (N)", DataType.INTEGER, 8, VariableRole.RECORD, False, Origin.DERIVED),
                ("PARAMCD", "Parameter Code", DataType.TEXT, 8, VariableRole.IDENTIFIER, True, Origin.DERIVED),
                ("PARAM", "Parameter", DataType.TEXT, 200, VariableRole.RECORD, True, Origin.DERIVED),
                ("PARCAT1", "Parameter Category 1", DataType.TEXT, 100, VariableRole.GROUPING, False, Origin.DERIVED),
                ("STARTDT", "Time-to-Event Origin Date", DataType.INTEGER, 8, VariableRole.TIMING, True, Origin.DERIVED),
                ("ADT", "Analysis Date", DataType.INTEGER, 8, VariableRole.TIMING, False, Origin.DERIVED),
                ("AVAL", "Analysis Value", DataType.FLOAT, 8, VariableRole.RESULT, True, Origin.DERIVED),
                ("AVALU", "Analysis Value Unit", DataType.TEXT, 40, VariableRole.VARIABLE, False, Origin.DERIVED),
                ("CNSR", "Censor", DataType.INTEGER, 8, VariableRole.RECORD, True, Origin.DERIVED),
                ("EVNTDESC", "Event Description", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.DERIVED),
                ("CNSDTDSC", "Censor Date Description", DataType.TEXT, 200, VariableRole.RECORD, False, Origin.DERIVED),
            ]
        },
    }

    # Standard codelists
    STANDARD_CODELISTS = {
        "SEX": [
            CodeListItem("F", "Female", 1),
            CodeListItem("M", "Male", 2),
            CodeListItem("U", "Unknown", 3),
            CodeListItem("UNDIFFERENTIATED", "Undifferentiated", 4),
        ],
        "NY": [
            CodeListItem("N", "No", 1),
            CodeListItem("Y", "Yes", 2),
        ],
        "AESSION": [
            CodeListItem("MILD", "Mild", 1),
            CodeListItem("MODERATE", "Moderate", 2),
            CodeListItem("SEVERE", "Severe", 3),
        ],
        "NRIND": [
            CodeListItem("NORMAL", "Normal", 1),
            CodeListItem("LOW", "Low", 2),
            CodeListItem("HIGH", "High", 3),
        ],
        "AGEGR1": [
            CodeListItem("<65", "<65 years", 1),
            CodeListItem(">=65", ">=65 years", 2),
        ],
    }

    def __init__(self, study_id: str, study_name: str):
        """
        Initialize Define-XML generator.

        Args:
            study_id: Protocol/study identifier
            study_name: Full study name/title
        """
        self.study_id = study_id
        self.study_name = study_name
        self.datasets: List[DatasetDefinition] = []
        self.codelists: Dict[str, CodeList] = {}
        self.methods: Dict[str, ComputationalMethod] = {}
        self.where_clauses: Dict[str, WhereClause] = {}
        self.comments: Dict[str, str] = {}

        # XML namespaces
        self.namespaces = {
            "": "http://www.cdisc.org/ns/odm/v1.3",
            "def": "http://www.cdisc.org/ns/def/v2.1",
            "xlink": "http://www.w3.org/1999/xlink",
            "arm": "http://www.cdisc.org/ns/arm/v1.0",
        }

    def add_sdtm_domains(self, domains: List[str]) -> None:
        """
        Add standard SDTM domains to the Define-XML.

        Args:
            domains: List of domain codes (e.g., ["DM", "AE", "EX"])
        """
        for domain in domains:
            if domain in self.SDTM_DOMAINS:
                self._add_sdtm_domain(domain)

    def add_adam_datasets(self, datasets: List[str]) -> None:
        """
        Add standard ADaM datasets to the Define-XML.

        Args:
            datasets: List of dataset names (e.g., ["ADSL", "ADAE", "ADLB"])
        """
        for dataset in datasets:
            if dataset in self.ADAM_DATASETS:
                self._add_adam_dataset(dataset)

    def _add_sdtm_domain(self, domain: str) -> None:
        """Add a standard SDTM domain"""
        domain_info = self.SDTM_DOMAINS[domain]

        variables = []
        for i, var_info in enumerate(domain_info["variables"], 1):
            name, label, dtype, length, role, mandatory = var_info
            variables.append(VariableDefinition(
                oid=f"IT.{domain}.{name}",
                name=name,
                label=label,
                data_type=dtype,
                length=length,
                role=role,
                order_number=i,
                mandatory=mandatory,
                origin=Origin.CRF if role != VariableRole.IDENTIFIER else Origin.ASSIGNED,
            ))

        dataset = DatasetDefinition(
            oid=f"IG.{domain}",
            name=domain,
            label=domain_info["label"],
            domain=domain,
            structure=domain_info["structure"],
            purpose="Tabulation",
            class_name=domain_info["class"],
            sas_dataset_name=domain.lower(),
            variables=variables,
            keys=domain_info["keys"],
            repeating=domain != "DM",
        )
        self.datasets.append(dataset)

    def _add_adam_dataset(self, dataset_name: str) -> None:
        """Add a standard ADaM dataset"""
        ds_info = self.ADAM_DATASETS[dataset_name]

        variables = []
        for i, var_info in enumerate(ds_info["variables"], 1):
            name, label, dtype, length, role, mandatory, origin = var_info

            # Add method reference for derived variables
            method_oid = None
            if origin == Origin.DERIVED and name not in ["STUDYID", "USUBJID"]:
                method_oid = f"MT.{dataset_name}.{name}"
                self._add_derivation_method(method_oid, name, dataset_name)

            variables.append(VariableDefinition(
                oid=f"IT.{dataset_name}.{name}",
                name=name,
                label=label,
                data_type=dtype,
                length=length,
                role=role,
                order_number=i,
                mandatory=mandatory,
                origin=origin,
                method_oid=method_oid,
            ))

        dataset = DatasetDefinition(
            oid=f"IG.{dataset_name}",
            name=dataset_name,
            label=ds_info["label"],
            domain=dataset_name[:2] if len(dataset_name) > 2 else dataset_name,
            structure=ds_info["structure"],
            purpose="Analysis",
            class_name=ds_info["class"],
            sas_dataset_name=dataset_name.lower(),
            variables=variables,
            keys=ds_info["keys"],
            repeating=dataset_name != "ADSL",
        )
        self.datasets.append(dataset)

    def _add_derivation_method(self, method_oid: str, var_name: str, dataset: str) -> None:
        """Add derivation method for a variable"""
        # Generate appropriate derivation description
        descriptions = {
            # ADSL derivations
            "AGEGR1": "Derived from AGE using protocol-defined age groups: <65 = '<65', >=65 = '>=65'",
            "AGEGR1N": "Numeric representation of AGEGR1: 1 = '<65', 2 = '>=65'",
            "SEXN": "Numeric representation of SEX: 1 = 'F', 2 = 'M'",
            "RACEN": "Numeric representation of RACE based on protocol-defined coding",
            "ETHNICN": "Numeric representation of ETHNIC: 1 = 'HISPANIC OR LATINO', 2 = 'NOT HISPANIC OR LATINO'",
            "TRT01P": "Set to ARM from DM domain",
            "TRT01PN": "Numeric representation of TRT01P based on protocol-defined treatment ordering",
            "TRT01A": "Set to ACTARM from DM domain",
            "TRT01AN": "Numeric representation of TRT01A based on protocol-defined treatment ordering",
            "TRTSDT": "Earliest date from EX.EXSTDTC where EXDOSE > 0, converted to SAS date",
            "TRTEDT": "Latest date from EX.EXENDTC where EXDOSE > 0, converted to SAS date",
            "TRTDURD": "Calculated as TRTEDT - TRTSDT + 1",
            "RANDDT": "Date of randomization from DS domain where DSDECOD = 'RANDOMIZED'",
            "EOSDT": "End of study date from DS domain",
            "EOSSTT": "End of study status derived from DS.DSDECOD",
            "DCSREAS": "Reason for discontinuation from DS.DSTERM where DSCAT = 'DISPOSITION EVENT'",
            "DTHDT": "Date of death from DM.DTHDTC, converted to SAS date",
            "DTHFL": "Set to 'Y' if DTHDT is not missing, otherwise null",
            "SAFFL": "Set to 'Y' if subject received at least one dose of study treatment (TRTSDT not missing)",
            "ITTFL": "Set to 'Y' if subject was randomized (RANDFL = 'Y')",
            "FASFL": "Set to 'Y' if ITTFL = 'Y' and subject has at least one post-baseline efficacy assessment",
            "PPROTFL": "Set to 'Y' if no major protocol deviations that affect efficacy assessment",
            "RANDFL": "Set to 'Y' if subject was randomized (RANDDT not missing)",

            # ADAE derivations
            "TRTA": "Actual treatment at time of AE onset, derived from ADSL.TRT01A",
            "TRTAN": "Numeric representation of TRTA",
            "ASTDT": "Analysis start date derived from AE.AESTDTC, converted to SAS date",
            "AENDT": "Analysis end date derived from AE.AEENDTC, converted to SAS date",
            "ASTDY": "Analysis start relative day = ASTDT - TRTSDT + 1 (if ASTDT >= TRTSDT) or ASTDT - TRTSDT (if ASTDT < TRTSDT)",
            "AENDY": "Analysis end relative day = AENDT - TRTSDT + 1 (if AENDT >= TRTSDT) or AENDT - TRTSDT (if AENDT < TRTSDT)",
            "AEDUR": "AE duration in days = AENDT - ASTDT + 1",
            "AETRTEMFL": "Treatment-emergent flag: 'Y' if AE started on or after first dose and within 30 days of last dose",
            "AOCCFL": "Set to 'Y' for first occurrence of any AE within subject",
            "AOCCSFL": "Set to 'Y' for first occurrence of each SOC within subject",
            "AOCCPFL": "Set to 'Y' for first occurrence of each preferred term within subject",
            "ANL01FL": "Analysis record flag: 'Y' for records to include in primary AE analysis",

            # ADLB derivations
            "PARAMCD": "Derived from LBTESTCD",
            "PARAM": "Derived from LBTEST with units: LBTEST || ' (' || LBSTRESU || ')'",
            "PARAMN": "Numeric parameter code assigned sequentially",
            "PARCAT1": "Derived from LBCAT",
            "AVAL": "Analysis value set to LBSTRESN",
            "AVALC": "Character analysis value set to LBSTRESC",
            "BASE": "Baseline value: AVAL where ABLFL = 'Y'",
            "BASEC": "Baseline character value: AVALC where ABLFL = 'Y'",
            "CHG": "Change from baseline = AVAL - BASE",
            "PCHG": "Percent change from baseline = ((AVAL - BASE) / BASE) * 100",
            "A1LO": "Analysis reference range lower limit derived from LBSTNRLO",
            "A1HI": "Analysis reference range upper limit derived from LBSTNRHI",
            "ANRIND": "Analysis reference range indicator: 'NORMAL', 'LOW', 'HIGH' based on AVAL vs A1LO/A1HI",
            "BNRIND": "Baseline reference range indicator",
            "SHIFT1": "Shift from baseline to post-baseline: concatenation of BNRIND and ANRIND",
            "AVISIT": "Analysis visit derived from VISIT with windowing applied per SAP",
            "AVISITN": "Numeric analysis visit for ordering",
            "ADT": "Analysis date derived from LBDTC, converted to SAS date",
            "ADY": "Analysis relative day = ADT - TRTSDT + 1",
            "ABLFL": "Baseline flag: 'Y' for last non-missing value on or before TRTSDT",

            # ADEFF derivations
            "CRIT1": "Analysis criterion 1 as defined in SAP",
            "CRIT1FL": "Set to 'Y' if CRIT1 is met, 'N' otherwise",

            # ADTTE derivations
            "STARTDT": "Time-to-event origin date, typically RANDDT or TRTSDT per SAP",
            "CNSR": "Censor indicator: 0 = event occurred, 1 = censored",
            "EVNTDESC": "Description of event that occurred",
            "CNSDTDSC": "Description of censoring (e.g., 'Last known alive date', 'End of study')",
            "AVALU": "Analysis value unit: 'DAYS', 'WEEKS', or 'MONTHS' per SAP",
        }

        description = descriptions.get(var_name, f"Derived variable - see SAP for derivation details")

        self.methods[method_oid] = ComputationalMethod(
            oid=method_oid,
            name=f"{var_name} Derivation",
            type="Computation",
            description=description,
        )

    def add_custom_codelist(self, name: str, data_type: DataType,
                           items: List[tuple]) -> str:
        """
        Add a custom codelist.

        Args:
            name: Codelist name
            data_type: Data type for coded values
            items: List of (coded_value, decode) tuples

        Returns:
            OID of created codelist
        """
        oid = f"CL.{name}"
        codelist_items = [
            CodeListItem(coded_value=str(cv), decode=decode, order_number=i+1)
            for i, (cv, decode) in enumerate(items)
        ]
        self.codelists[oid] = CodeList(
            oid=oid,
            name=name,
            data_type=data_type,
            items=codelist_items,
        )
        return oid

    def add_standard_codelists(self) -> None:
        """Add all standard CDISC codelists"""
        for name, items in self.STANDARD_CODELISTS.items():
            self.codelists[f"CL.{name}"] = CodeList(
                oid=f"CL.{name}",
                name=name,
                data_type=DataType.TEXT,
                items=items,
            )

    def generate_xml(self) -> str:
        """
        Generate complete Define-XML 2.1 document.

        Returns:
            Formatted XML string
        """
        # Register namespaces (prefix only, not default)
        ET.register_namespace("def", self.namespaces["def"])
        ET.register_namespace("xlink", self.namespaces["xlink"])
        ET.register_namespace("arm", self.namespaces["arm"])

        # Create root ODM element with explicit namespace
        root = ET.Element("{%s}ODM" % self.namespaces[""])
        root.set("ODMVersion", "1.3.2")
        root.set("FileOID", f"DEF.{self.study_id}")
        root.set("FileType", "Snapshot")
        root.set("CreationDateTime", datetime.now().isoformat())
        root.set("Originator", "SAP Generator System")
        root.set("SourceSystem", "Enterprise SAP System")
        root.set("SourceSystemVersion", "1.0")

        # Define namespace prefix for cleaner code
        ns = self.namespaces[""]

        # Study element
        study = ET.SubElement(root, "{%s}Study" % ns)
        study.set("OID", f"STUDY.{self.study_id}")

        # GlobalVariables
        global_vars = ET.SubElement(study, "{%s}GlobalVariables" % ns)
        study_name_elem = ET.SubElement(global_vars, "{%s}StudyName" % ns)
        study_name_elem.text = self.study_name
        study_desc = ET.SubElement(global_vars, "{%s}StudyDescription" % ns)
        study_desc.text = f"Define-XML metadata for {self.study_id}"
        protocol_name = ET.SubElement(global_vars, "{%s}ProtocolName" % ns)
        protocol_name.text = self.study_id

        # MetaDataVersion
        mdv = ET.SubElement(study, "{%s}MetaDataVersion" % ns)
        mdv.set("OID", f"MDV.{self.study_id}.001")
        mdv.set("Name", f"Study {self.study_id} Data Definition")
        mdv.set("Description", f"Define-XML v2.1 metadata for {self.study_id}")
        mdv.set("{%s}DefineVersion" % self.namespaces["def"], "2.1.0")
        mdv.set("{%s}StandardName" % self.namespaces["def"], "CDISC-Define-XML")
        mdv.set("{%s}StandardVersion" % self.namespaces["def"], "2.1")

        # Add Standards
        self._add_standards(mdv)

        # Add ItemGroupDefs (datasets)
        for dataset in self.datasets:
            self._add_item_group_def(mdv, dataset)

        # Add ItemDefs (variables)
        for dataset in self.datasets:
            for var in dataset.variables:
                self._add_item_def(mdv, var, dataset.name)

        # Add CodeLists
        for codelist in self.codelists.values():
            self._add_codelist(mdv, codelist)

        # Add MethodDefs
        for method in self.methods.values():
            self._add_method_def(mdv, method)

        # Add CommentDefs
        for oid, text in self.comments.items():
            self._add_comment_def(mdv, oid, text)

        # Pretty print XML
        xml_string = ET.tostring(root, encoding="unicode")
        dom = minidom.parseString(xml_string)
        return dom.toprettyxml(indent="  ")

    def _add_standards(self, parent: ET.Element) -> None:
        """Add Standards element"""
        standards = ET.SubElement(parent, "{%s}Standards" % self.namespaces["def"])

        # SDTM-IG standard
        sdtm_std = ET.SubElement(standards, "{%s}Standard" % self.namespaces["def"])
        sdtm_std.set("OID", "STD.SDTM.3.4")
        sdtm_std.set("Name", "SDTM-IG")
        sdtm_std.set("Type", "IG")
        sdtm_std.set("Version", "3.4")
        sdtm_std.set("Status", "Final")

        # ADaM-IG standard
        adam_std = ET.SubElement(standards, "{%s}Standard" % self.namespaces["def"])
        adam_std.set("OID", "STD.ADAM.1.3")
        adam_std.set("Name", "ADaM-IG")
        adam_std.set("Type", "IG")
        adam_std.set("Version", "1.3")
        adam_std.set("Status", "Final")

        # CDISC CT
        ct_std = ET.SubElement(standards, "{%s}Standard" % self.namespaces["def"])
        ct_std.set("OID", f"STD.CT.{self.CT_VERSION}")
        ct_std.set("Name", "CDISC/NCI CT")
        ct_std.set("Type", "CT")
        ct_std.set("Version", self.CT_VERSION)
        ct_std.set("Status", "Final")

    def _add_item_group_def(self, parent: ET.Element, dataset: DatasetDefinition) -> None:
        """Add ItemGroupDef element for a dataset"""
        ns = self.namespaces[""]
        ig = ET.SubElement(parent, "{%s}ItemGroupDef" % ns)
        ig.set("OID", dataset.oid)
        ig.set("Name", dataset.name)
        ig.set("Repeating", "Yes" if dataset.repeating else "No")
        ig.set("IsReferenceData", "Yes" if dataset.is_reference else "No")
        ig.set("SASDatasetName", dataset.sas_dataset_name)
        ig.set("{%s}Structure" % self.namespaces["def"], dataset.structure)
        ig.set("Purpose", dataset.purpose)
        ig.set("{%s}Class" % self.namespaces["def"], dataset.class_name)

        # Description
        desc = ET.SubElement(ig, "{%s}Description" % ns)
        translated_text = ET.SubElement(desc, "{%s}TranslatedText" % ns)
        translated_text.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        translated_text.text = dataset.label

        # ItemRefs
        for var in dataset.variables:
            item_ref = ET.SubElement(ig, "{%s}ItemRef" % ns)
            item_ref.set("ItemOID", var.oid)
            item_ref.set("OrderNumber", str(var.order_number))
            item_ref.set("Mandatory", "Yes" if var.mandatory else "No")
            if var.name in dataset.keys:
                item_ref.set("KeySequence", str(dataset.keys.index(var.name) + 1))
            if var.method_oid:
                item_ref.set("MethodOID", var.method_oid)

        # def:leaf for transport file
        leaf = ET.SubElement(ig, "{%s}leaf" % self.namespaces["def"])
        leaf.set("ID", f"LF.{dataset.name}")
        leaf.set("{%s}href" % self.namespaces["xlink"], f"{dataset.sas_dataset_name}.xpt")
        title = ET.SubElement(leaf, "{%s}title" % self.namespaces["def"])
        title.text = f"{dataset.name}.xpt"

    def _add_item_def(self, parent: ET.Element, var: VariableDefinition,
                      dataset_name: str) -> None:
        """Add ItemDef element for a variable"""
        ns = self.namespaces[""]
        item = ET.SubElement(parent, "{%s}ItemDef" % ns)
        item.set("OID", var.oid)
        item.set("Name", var.name)
        item.set("SASFieldName", var.name[:8] if len(var.name) > 8 else var.name)
        item.set("DataType", var.data_type.value)

        if var.data_type in [DataType.TEXT]:
            item.set("Length", str(var.length))
        elif var.data_type in [DataType.FLOAT]:
            item.set("Length", str(var.length))
            if var.significant_digits:
                item.set("SignificantDigits", str(var.significant_digits))
        elif var.data_type in [DataType.INTEGER]:
            item.set("Length", str(var.length))

        # Description/Label
        desc = ET.SubElement(item, "{%s}Description" % ns)
        translated_text = ET.SubElement(desc, "{%s}TranslatedText" % ns)
        translated_text.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        translated_text.text = var.label

        # CodeListRef
        if var.codelist_oid:
            codelist_ref = ET.SubElement(item, "{%s}CodeListRef" % ns)
            codelist_ref.set("CodeListOID", var.codelist_oid)

        # Origin
        origin = ET.SubElement(item, "{%s}Origin" % self.namespaces["def"])
        origin.set("Type", var.origin.value)
        if var.origin == Origin.CRF and var.crf_page:
            doc_ref = ET.SubElement(origin, "{%s}DocumentRef" % self.namespaces["def"])
            doc_ref.set("leafID", "LF.blankcrf")
            pdf_page = ET.SubElement(doc_ref, "{%s}PDFPageRef" % self.namespaces["def"])
            pdf_page.set("PageRefs", var.crf_page)
            pdf_page.set("Type", "NamedDestination")
        elif var.origin == Origin.PREDECESSOR and var.predecessor:
            desc_elem = ET.SubElement(origin, "{%s}Description" % ns)
            translated = ET.SubElement(desc_elem, "{%s}TranslatedText" % ns)
            translated.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
            translated.text = var.predecessor

    def _add_codelist(self, parent: ET.Element, codelist: CodeList) -> None:
        """Add CodeList element"""
        ns = self.namespaces[""]
        cl = ET.SubElement(parent, "{%s}CodeList" % ns)
        cl.set("OID", codelist.oid)
        cl.set("Name", codelist.name)
        cl.set("DataType", codelist.data_type.value)

        if codelist.external_codelist:
            ext_cl = ET.SubElement(cl, "{%s}ExternalCodeList" % ns)
            ext_cl.set("Dictionary", codelist.external_codelist)
        else:
            for item in codelist.items:
                cli = ET.SubElement(cl, "{%s}CodeListItem" % ns)
                cli.set("CodedValue", item.coded_value)
                cli.set("OrderNumber", str(item.order_number))
                if item.extended_value:
                    cli.set("{%s}ExtendedValue" % self.namespaces["def"], "Yes")
                decode = ET.SubElement(cli, "{%s}Decode" % ns)
                translated = ET.SubElement(decode, "{%s}TranslatedText" % ns)
                translated.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
                translated.text = item.decode

    def _add_method_def(self, parent: ET.Element, method: ComputationalMethod) -> None:
        """Add MethodDef element"""
        ns = self.namespaces[""]
        md = ET.SubElement(parent, "{%s}MethodDef" % ns)
        md.set("OID", method.oid)
        md.set("Name", method.name)
        md.set("Type", method.type)

        desc = ET.SubElement(md, "{%s}Description" % ns)
        translated = ET.SubElement(desc, "{%s}TranslatedText" % ns)
        translated.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        translated.text = method.description

        if method.formal_expression:
            formal = ET.SubElement(md, "{%s}FormalExpression" % ns)
            formal.set("Context", "SAS")
            formal.text = method.formal_expression

    def _add_comment_def(self, parent: ET.Element, oid: str, text: str) -> None:
        """Add CommentDef element"""
        ns = self.namespaces[""]
        comment = ET.SubElement(parent, "{%s}CommentDef" % self.namespaces["def"])
        comment.set("OID", oid)
        desc = ET.SubElement(comment, "{%s}Description" % ns)
        translated = ET.SubElement(desc, "{%s}TranslatedText" % ns)
        translated.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
        translated.text = text


def create_define_xml_generator(study_id: str, study_name: str) -> DefineXMLGenerator:
    """
    Factory function to create a Define-XML generator.

    Args:
        study_id: Protocol/study identifier
        study_name: Full study name/title

    Returns:
        Configured DefineXMLGenerator instance
    """
    return DefineXMLGenerator(study_id, study_name)


def generate_sdtm_define_xml(study_id: str, study_name: str,
                             domains: List[str] = None) -> str:
    """
    Generate SDTM Define-XML.

    Args:
        study_id: Protocol identifier
        study_name: Full study name
        domains: List of SDTM domains to include (default: standard set)

    Returns:
        Define-XML string
    """
    if domains is None:
        domains = ["DM", "AE", "CM", "DS", "EX", "LB", "MH", "VS"]

    generator = create_define_xml_generator(study_id, study_name)
    generator.add_standard_codelists()
    generator.add_sdtm_domains(domains)
    return generator.generate_xml()


def generate_adam_define_xml(study_id: str, study_name: str,
                             datasets: List[str] = None) -> str:
    """
    Generate ADaM Define-XML.

    Args:
        study_id: Protocol identifier
        study_name: Full study name
        datasets: List of ADaM datasets to include (default: standard set)

    Returns:
        Define-XML string
    """
    if datasets is None:
        datasets = ["ADSL", "ADAE", "ADLB", "ADEFF", "ADTTE"]

    generator = create_define_xml_generator(study_id, study_name)
    generator.add_standard_codelists()
    generator.add_adam_datasets(datasets)
    return generator.generate_xml()
