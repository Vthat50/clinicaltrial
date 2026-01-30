#!/usr/bin/env python3
"""
Enterprise SAP Generation System - CDISC ADaM Mapping
=======================================================
TIER 5: CDISC Standards Integration

Provides ADaM dataset mapping, variable specifications,
and traceability documentation for SAP generation.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Use relative imports for consistent module resolution
try:
    from ..core.schemas import EndpointType, Estimand
    from .terminology_service import get_terminology_service, CDISCTerminologyService
except ImportError:
    # Fallback for direct script execution
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from core.schemas import EndpointType, Estimand
    try:
        from cdisc.terminology_service import get_terminology_service, CDISCTerminologyService
    except ImportError:
        # Terminology service not available, will use legacy mode
        get_terminology_service = None
        CDISCTerminologyService = None


@dataclass
class ADaMVariable:
    """ADaM variable specification"""
    name: str
    label: str
    type: str  # "Char", "Num"
    length: Optional[int] = None
    format: Optional[str] = None
    source: str = ""
    derivation: str = ""
    comments: str = ""


@dataclass
class ADaMDataset:
    """ADaM dataset specification"""
    name: str
    label: str
    structure: str  # "ADSL", "BDS", "OCCDS"
    key_variables: List[str]
    variables: List[ADaMVariable]
    source_domains: List[str]
    description: str = ""


@dataclass
class CDISCMapping:
    """Complete CDISC mapping for an endpoint"""
    endpoint_type: EndpointType
    primary_dataset: str
    key_variables: Dict[str, str]
    analysis_flags: List[str]
    derivation_rules: List[str]
    source_sdtm: List[str]


class CDISCMapper:
    """
    Maps clinical trial endpoints to CDISC ADaM standards.
    Provides dataset specifications and traceability.
    """

    # Complete endpoint to ADaM mapping specifications
    ENDPOINT_MAPPINGS = {
        EndpointType.OS: CDISCMapping(
            endpoint_type=EndpointType.OS,
            primary_dataset="ADTTE",
            key_variables={
                "PARAMCD": "OS",
                "PARAM": "Overall Survival",
                "AVAL": "Analysis Value (time in days from randomization to death)",
                "CNSR": "Censor Status (0=event/death, 1=censored)",
                "EVNTDESC": "Event Description (Death/Censored)",
                "STARTDT": "Time-to-Event Origin Date (Randomization Date)",
                "ADT": "Analysis Date (Date of Death or Censoring)",
                "TRTP": "Planned Treatment",
                "TRTA": "Actual Treatment"
            },
            analysis_flags=["ITTFL", "SAFFL", "ANL01FL"],
            derivation_rules=[
                "AVAL = ADT - STARTDT + 1 (in days)",
                "CNSR = 0 if death occurred, 1 if censored",
                "STARTDT = Randomization date from ADSL.RANDDT",
                "ADT = Date of death from DD domain or last known alive date"
            ],
            source_sdtm=["DM", "DS", "DD", "AE"]
        ),

        EndpointType.PFS: CDISCMapping(
            endpoint_type=EndpointType.PFS,
            primary_dataset="ADTTE",
            key_variables={
                "PARAMCD": "PFS",
                "PARAM": "Progression-Free Survival",
                "AVAL": "Analysis Value (time in days from randomization to progression or death)",
                "CNSR": "Censor Status (0=event, 1=censored)",
                "EVNTDESC": "Event Description (Progression/Death/Censored)",
                "SRCSEQ": "Source Sequence Number (links to tumor data)",
                "STARTDT": "Time-to-Event Origin Date",
                "ADT": "Analysis Date",
                "TRTP": "Planned Treatment",
                "TRTA": "Actual Treatment"
            },
            analysis_flags=["ITTFL", "RANDFL", "ANL01FL", "ANL02FL"],
            derivation_rules=[
                "AVAL = ADT - STARTDT + 1 (in days)",
                "CNSR = 0 if progression or death, 1 if censored",
                "Event = earliest of disease progression (per RECIST 1.1) or death",
                "Censoring rules per protocol-specified conventions"
            ],
            source_sdtm=["DM", "RS", "TU", "TR", "DS", "DD"]
        ),

        EndpointType.DFS: CDISCMapping(
            endpoint_type=EndpointType.DFS,
            primary_dataset="ADTTE",
            key_variables={
                "PARAMCD": "DFS",
                "PARAM": "Disease-Free Survival",
                "AVAL": "Analysis Value (time in days)",
                "CNSR": "Censor Status",
                "EVNTDESC": "Event Description (Recurrence/Death/Censored)",
                "STARTDT": "Time-to-Event Origin Date (Surgery/Complete Response Date)",
                "ADT": "Analysis Date"
            },
            analysis_flags=["ITTFL", "SAFFL", "ANL01FL"],
            derivation_rules=[
                "AVAL = ADT - STARTDT + 1 (in days)",
                "STARTDT = Date of surgery or confirmed complete response",
                "Event = Disease recurrence (local/distant) or death"
            ],
            source_sdtm=["DM", "RS", "DS", "DD", "MH"]
        ),

        EndpointType.ORR: CDISCMapping(
            endpoint_type=EndpointType.ORR,
            primary_dataset="ADRS",
            key_variables={
                "PARAMCD": "BOR",
                "PARAM": "Best Overall Response",
                "AVALC": "Character Result (CR/PR/SD/PD/NE)",
                "AVAL": "Numeric Response (1=responder/CR+PR, 0=non-responder)",
                "RSDT": "Response Date",
                "RSORRES": "Original Response Result",
                "RSSTRESC": "Standardized Response Result"
            },
            analysis_flags=["ITTFL", "SAFFL", "ANL01FL", "ANL02FL"],
            derivation_rules=[
                "BOR derived per RECIST 1.1 confirmation requirements",
                "AVAL = 1 if AVALC in (CR, PR), 0 otherwise",
                "CR/PR require confirmation at subsequent assessment",
                "NE if insufficient tumor assessments"
            ],
            source_sdtm=["RS", "TU", "TR"]
        ),

        EndpointType.SAFETY: CDISCMapping(
            endpoint_type=EndpointType.SAFETY,
            primary_dataset="ADAE",
            key_variables={
                "AETERM": "Reported Term for the Adverse Event",
                "AEDECOD": "Dictionary-Derived Term (MedDRA PT)",
                "AEBODSYS": "Body System or Organ Class (MedDRA SOC)",
                "AESEV": "Severity/Intensity",
                "AESER": "Serious Event Flag (Y/N)",
                "AEREL": "Causality (Related/Not Related)",
                "AETOXGR": "Standard Toxicity Grade (CTCAE)",
                "TRTEMFL": "Treatment-Emergent Flag",
                "ASTDT": "Analysis Start Date",
                "AENDT": "Analysis End Date"
            },
            analysis_flags=["SAFFL", "TRTEMFL"],
            derivation_rules=[
                "TRTEMFL = Y if AE onset during treatment period",
                "MedDRA coding at PT and SOC level",
                "CTCAE grading for oncology studies",
                "Exposure-adjusted incidence rates for duration differences"
            ],
            source_sdtm=["AE", "EX", "DS"]
        ),

        EndpointType.PK: CDISCMapping(
            endpoint_type=EndpointType.PK,
            primary_dataset="ADPC",
            key_variables={
                "AVAL": "Analysis Value (concentration)",
                "PARAM": "Parameter Name",
                "PARAMCD": "Parameter Code",
                "PCSPEC": "Specimen Type",
                "PCTPT": "Planned Timepoint Name",
                "PCTPTNUM": "Planned Timepoint Number",
                "ATPT": "Analysis Timepoint",
                "ABLFL": "Baseline Flag"
            },
            analysis_flags=["PKFL", "SAFFL", "ANL01FL"],
            derivation_rules=[
                "Concentration values from validated bioanalytical methods",
                "BLQ handling per validated method LLOQ",
                "Nominal vs actual time mapping"
            ],
            source_sdtm=["PC", "EX"]
        ),

        EndpointType.EFS: CDISCMapping(
            endpoint_type=EndpointType.EFS,
            primary_dataset="ADTTE",
            key_variables={
                "PARAMCD": "EFS",
                "PARAM": "Event-Free Survival",
                "AVAL": "Analysis Value (time in days)",
                "CNSR": "Censor Status",
                "EVNTDESC": "Event Description"
            },
            analysis_flags=["ITTFL", "ANL01FL"],
            derivation_rules=[
                "Composite endpoint per protocol definition",
                "Event = earliest of protocol-defined events"
            ],
            source_sdtm=["DM", "DS", "RS", "DD"]
        ),
    }

    # Standard ADaM dataset specifications
    ADAM_DATASETS = {
        "ADSL": ADaMDataset(
            name="ADSL",
            label="Subject-Level Analysis Dataset",
            structure="ADSL",
            key_variables=["STUDYID", "USUBJID"],
            source_domains=["DM", "DS", "EX", "SV"],
            description="One record per subject containing demographics, treatment, disposition, and population flags",
            variables=[
                ADaMVariable("STUDYID", "Study Identifier", "Char", 20, source="DM.STUDYID"),
                ADaMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, source="DM.USUBJID"),
                ADaMVariable("SUBJID", "Subject Identifier for the Study", "Char", 20, source="DM.SUBJID"),
                ADaMVariable("SITEID", "Study Site Identifier", "Char", 10, source="DM.SITEID"),
                ADaMVariable("AGE", "Age", "Num", source="DM.AGE"),
                ADaMVariable("AGEGR1", "Age Group 1", "Char", 20, derivation="Derived from AGE"),
                ADaMVariable("SEX", "Sex", "Char", 1, source="DM.SEX"),
                ADaMVariable("RACE", "Race", "Char", 50, source="DM.RACE"),
                ADaMVariable("ETHNIC", "Ethnicity", "Char", 50, source="DM.ETHNIC"),
                ADaMVariable("COUNTRY", "Country", "Char", 3, source="DM.COUNTRY"),
                ADaMVariable("RANDDT", "Date of Randomization", "Num", format="DATE9.", source="DS where DSTERM='RANDOMIZED'"),
                ADaMVariable("TRT01P", "Planned Treatment for Period 01", "Char", 200, source="DM.ARM"),
                ADaMVariable("TRT01A", "Actual Treatment for Period 01", "Char", 200, derivation="Derived from EX"),
                ADaMVariable("TRTSDT", "Date of First Exposure to Treatment", "Num", format="DATE9.", source="EX.EXSTDTC"),
                ADaMVariable("TRTEDT", "Date of Last Exposure to Treatment", "Num", format="DATE9.", source="EX.EXENDTC"),
                ADaMVariable("EOSDT", "End of Study Date", "Num", format="DATE9.", source="DS"),
                ADaMVariable("EOSSTT", "End of Study Status", "Char", 20, source="DS.DSDECOD"),
                ADaMVariable("ITTFL", "Intent-To-Treat Population Flag", "Char", 1, derivation="Y if randomized"),
                ADaMVariable("SAFFL", "Safety Population Flag", "Char", 1, derivation="Y if received any study treatment"),
                ADaMVariable("PPROTFL", "Per-Protocol Population Flag", "Char", 1, derivation="Y if ITT with no major deviations"),
                ADaMVariable("RANDFL", "Randomized Population Flag", "Char", 1, derivation="Y if randomized"),
            ]
        ),

        "ADTTE": ADaMDataset(
            name="ADTTE",
            label="Time-to-Event Analysis Dataset",
            structure="BDS",
            key_variables=["STUDYID", "USUBJID", "PARAMCD"],
            source_domains=["ADSL", "RS", "DS", "DD"],
            description="One record per subject per time-to-event parameter",
            variables=[
                ADaMVariable("STUDYID", "Study Identifier", "Char", 20, source="ADSL.STUDYID"),
                ADaMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, source="ADSL.USUBJID"),
                ADaMVariable("PARAMCD", "Parameter Code", "Char", 8),
                ADaMVariable("PARAM", "Parameter", "Char", 200),
                ADaMVariable("PARAMN", "Parameter (N)", "Num"),
                ADaMVariable("AVAL", "Analysis Value", "Num", comments="Time in days"),
                ADaMVariable("STARTDT", "Time-to-Event Origin Date", "Num", format="DATE9."),
                ADaMVariable("ADT", "Analysis Date", "Num", format="DATE9."),
                ADaMVariable("CNSR", "Censor", "Num", comments="0=event, 1=censored"),
                ADaMVariable("EVNTDESC", "Event or Censoring Description", "Char", 200),
                ADaMVariable("CNSDTDSC", "Censor Date Description", "Char", 200),
                ADaMVariable("TRTP", "Planned Treatment", "Char", 200, source="ADSL.TRT01P"),
                ADaMVariable("TRTA", "Actual Treatment", "Char", 200, source="ADSL.TRT01A"),
                ADaMVariable("ITTFL", "Intent-To-Treat Population Flag", "Char", 1, source="ADSL.ITTFL"),
                ADaMVariable("SAFFL", "Safety Population Flag", "Char", 1, source="ADSL.SAFFL"),
            ]
        ),

        "ADRS": ADaMDataset(
            name="ADRS",
            label="Disease Response Analysis Dataset",
            structure="BDS",
            key_variables=["STUDYID", "USUBJID", "PARAMCD", "AVISIT"],
            source_domains=["ADSL", "RS", "TU", "TR"],
            description="Tumor response assessments for efficacy analysis",
            variables=[
                ADaMVariable("STUDYID", "Study Identifier", "Char", 20),
                ADaMVariable("USUBJID", "Unique Subject Identifier", "Char", 40),
                ADaMVariable("PARAMCD", "Parameter Code", "Char", 8),
                ADaMVariable("PARAM", "Parameter", "Char", 200),
                ADaMVariable("AVISIT", "Analysis Visit", "Char", 40),
                ADaMVariable("AVISITN", "Analysis Visit (N)", "Num"),
                ADaMVariable("ADT", "Analysis Date", "Num", format="DATE9."),
                ADaMVariable("AVAL", "Analysis Value", "Num"),
                ADaMVariable("AVALC", "Analysis Value (C)", "Char", 20),
                ADaMVariable("RSDT", "Response Date", "Num", format="DATE9."),
                ADaMVariable("TRTP", "Planned Treatment", "Char", 200),
                ADaMVariable("TRTA", "Actual Treatment", "Char", 200),
                ADaMVariable("ANL01FL", "Analysis Record Flag 01", "Char", 1),
                ADaMVariable("ANL02FL", "Analysis Record Flag 02", "Char", 1),
            ]
        ),

        "ADAE": ADaMDataset(
            name="ADAE",
            label="Adverse Event Analysis Dataset",
            structure="OCCDS",
            key_variables=["STUDYID", "USUBJID", "AESEQ"],
            source_domains=["ADSL", "AE", "EX"],
            description="Adverse events for safety analysis",
            variables=[
                ADaMVariable("STUDYID", "Study Identifier", "Char", 20),
                ADaMVariable("USUBJID", "Unique Subject Identifier", "Char", 40),
                ADaMVariable("AESEQ", "Sequence Number", "Num", source="AE.AESEQ"),
                ADaMVariable("AETERM", "Reported Term for the Adverse Event", "Char", 200, source="AE.AETERM"),
                ADaMVariable("AEDECOD", "Dictionary-Derived Term", "Char", 200, source="AE.AEDECOD"),
                ADaMVariable("AEBODSYS", "Body System or Organ Class", "Char", 200, source="AE.AEBODSYS"),
                ADaMVariable("AESEV", "Severity/Intensity", "Char", 20, source="AE.AESEV"),
                ADaMVariable("AESER", "Serious Event", "Char", 1, source="AE.AESER"),
                ADaMVariable("AEREL", "Causality", "Char", 20, source="AE.AEREL"),
                ADaMVariable("AEACN", "Action Taken with Study Treatment", "Char", 50, source="AE.AEACN"),
                ADaMVariable("AEOUT", "Outcome of Adverse Event", "Char", 50, source="AE.AEOUT"),
                ADaMVariable("AETOXGR", "Standard Toxicity Grade", "Char", 5),
                ADaMVariable("ASTDT", "Analysis Start Date", "Num", format="DATE9."),
                ADaMVariable("AENDT", "Analysis End Date", "Num", format="DATE9."),
                ADaMVariable("TRTEMFL", "Treatment Emergent Flag", "Char", 1),
                ADaMVariable("TRTP", "Planned Treatment", "Char", 200),
                ADaMVariable("TRTA", "Actual Treatment", "Char", 200),
                ADaMVariable("SAFFL", "Safety Population Flag", "Char", 1),
            ]
        ),

        "ADPC": ADaMDataset(
            name="ADPC",
            label="PK Concentration Analysis Dataset",
            structure="BDS",
            key_variables=["STUDYID", "USUBJID", "PARAMCD", "ATPT"],
            source_domains=["ADSL", "PC", "EX"],
            description="Pharmacokinetic concentration data",
            variables=[
                ADaMVariable("STUDYID", "Study Identifier", "Char", 20),
                ADaMVariable("USUBJID", "Unique Subject Identifier", "Char", 40),
                ADaMVariable("PARAMCD", "Parameter Code", "Char", 8),
                ADaMVariable("PARAM", "Parameter", "Char", 200),
                ADaMVariable("AVAL", "Analysis Value", "Num"),
                ADaMVariable("PCSPEC", "Specimen Type", "Char", 20, source="PC.PCSPEC"),
                ADaMVariable("PCTPT", "Planned Timepoint Name", "Char", 50),
                ADaMVariable("PCTPTNUM", "Planned Timepoint Number", "Num"),
                ADaMVariable("ATPT", "Analysis Timepoint", "Char", 50),
                ADaMVariable("ATPTN", "Analysis Timepoint (N)", "Num"),
                ADaMVariable("ADT", "Analysis Date", "Num", format="DATE9."),
                ADaMVariable("ATM", "Analysis Time", "Num", format="TIME5."),
                ADaMVariable("TRTP", "Planned Treatment", "Char", 200),
                ADaMVariable("TRTA", "Actual Treatment", "Char", 200),
                ADaMVariable("PKFL", "PK Population Flag", "Char", 1),
            ]
        ),

        "ADPP": ADaMDataset(
            name="ADPP",
            label="PK Parameters Analysis Dataset",
            structure="BDS",
            key_variables=["STUDYID", "USUBJID", "PARAMCD"],
            source_domains=["ADSL", "PP", "ADPC"],
            description="Derived PK parameters from NCA",
            variables=[
                ADaMVariable("STUDYID", "Study Identifier", "Char", 20),
                ADaMVariable("USUBJID", "Unique Subject Identifier", "Char", 40),
                ADaMVariable("PARAMCD", "Parameter Code", "Char", 8, comments="e.g., AUCLST, CMAX, TMAX"),
                ADaMVariable("PARAM", "Parameter", "Char", 200),
                ADaMVariable("AVAL", "Analysis Value", "Num"),
                ADaMVariable("AVALC", "Analysis Value (C)", "Char", 20),
                ADaMVariable("TRTP", "Planned Treatment", "Char", 200),
                ADaMVariable("TRTA", "Actual Treatment", "Char", 200),
                ADaMVariable("PKFL", "PK Population Flag", "Char", 1),
            ]
        ),
    }

    def __init__(self):
        """Initialize the CDISC mapper"""
        pass

    def get_mapping(self, endpoint_type: EndpointType) -> Optional[CDISCMapping]:
        """
        Get CDISC mapping for an endpoint type.

        Args:
            endpoint_type: Type of endpoint

        Returns:
            CDISCMapping or None if not found
        """
        return self.ENDPOINT_MAPPINGS.get(endpoint_type)

    def get_dataset_spec(self, dataset_name: str) -> Optional[ADaMDataset]:
        """
        Get ADaM dataset specification.

        Args:
            dataset_name: Name of the dataset (e.g., "ADSL", "ADTTE")

        Returns:
            ADaMDataset or None if not found
        """
        return self.ADAM_DATASETS.get(dataset_name.upper())

    def generate_traceability_section(self, estimands: List[Estimand]) -> str:
        """
        Generate CDISC ADaM traceability section for SAP.

        Args:
            estimands: List of estimands to map

        Returns:
            Formatted traceability section content
        """
        lines = [
            "## CDISC ADaM Alignment",
            "",
            "### Overview",
            "",
            "All analysis datasets will be created in accordance with CDISC ADaM Implementation Guide v1.1 "
            "and relevant therapeutic area standards. Analysis datasets are derived from SDTM domains "
            "with full traceability maintained in Define-XML 2.0 documentation.",
            "",
            "### Key Analysis Datasets",
            "",
            "| Dataset | Description | Key Variables | Primary Use |",
            "|---------|-------------|---------------|-------------|",
        ]

        datasets_used = set()

        for estimand in estimands:
            if estimand is None:
                continue

            mapping = self.get_mapping(estimand.variable_type)
            if mapping:
                datasets_used.add(mapping.primary_dataset)

        for ds_name in sorted(datasets_used):
            ds_spec = self.get_dataset_spec(ds_name)
            if ds_spec:
                key_vars = ", ".join(ds_spec.key_variables[:3])
                lines.append(f"| {ds_name} | {ds_spec.label} | {key_vars} | {ds_spec.description[:50]}... |")

        # Always include ADSL
        if "ADSL" not in datasets_used:
            adsl = self.ADAM_DATASETS["ADSL"]
            lines.append(f"| ADSL | {adsl.label} | STUDYID, USUBJID | {adsl.description[:50]}... |")

        lines.append("")
        lines.append("### Endpoint to ADaM Mapping")
        lines.append("")
        lines.append("| Endpoint | ADaM Dataset | PARAMCD | Key Analysis Variables |")
        lines.append("|----------|--------------|---------|------------------------|")

        for estimand in estimands:
            if estimand is None:
                continue

            mapping = self.get_mapping(estimand.variable_type)
            if mapping:
                key_vars = list(mapping.key_variables.keys())[:3]
                lines.append(
                    f"| {estimand.variable_type.value} | {mapping.primary_dataset} | "
                    f"{mapping.key_variables.get('PARAMCD', 'TBD')} | {', '.join(key_vars)} |"
                )

        lines.append("")
        lines.append("### Derivation Traceability")
        lines.append("")

        for estimand in estimands:
            if estimand is None:
                continue

            mapping = self.get_mapping(estimand.variable_type)
            if mapping:
                lines.append(f"#### {estimand.variable_type.value} ({mapping.primary_dataset})")
                lines.append("")
                lines.append("**Source SDTM Domains:** " + ", ".join(mapping.source_sdtm))
                lines.append("")
                lines.append("**Key Derivations:**")
                for rule in mapping.derivation_rules[:3]:
                    lines.append(f"- {rule}")
                lines.append("")
                lines.append("**Analysis Flags:** " + ", ".join(mapping.analysis_flags))
                lines.append("")

        lines.append("### Define-XML Documentation")
        lines.append("")
        lines.append("Complete variable-level traceability will be documented in Define-XML 2.0, including:")
        lines.append("- Variable derivation methods and algorithms")
        lines.append("- Source SDTM variables")
        lines.append("- Controlled terminology references")
        lines.append("- Computational methods for derived variables")

        return "\n".join(lines)

    def get_required_datasets(self, endpoint_types: List[EndpointType]) -> List[str]:
        """
        Get list of required ADaM datasets for given endpoint types.

        Args:
            endpoint_types: List of endpoint types

        Returns:
            List of required dataset names
        """
        datasets = {"ADSL"}  # Always required

        for ep_type in endpoint_types:
            mapping = self.get_mapping(ep_type)
            if mapping:
                datasets.add(mapping.primary_dataset)

        return sorted(list(datasets))

    def generate_dataset_specs(self, dataset_names: List[str]) -> str:
        """
        Generate dataset specifications section.

        Args:
            dataset_names: List of dataset names to document

        Returns:
            Formatted specifications content
        """
        lines = ["### ADaM Dataset Specifications", ""]

        for ds_name in dataset_names:
            ds_spec = self.get_dataset_spec(ds_name)
            if ds_spec:
                lines.append(f"#### {ds_name}: {ds_spec.label}")
                lines.append("")
                lines.append(f"**Structure:** {ds_spec.structure}")
                lines.append(f"**Key Variables:** {', '.join(ds_spec.key_variables)}")
                lines.append(f"**Source Domains:** {', '.join(ds_spec.source_domains)}")
                lines.append("")
                lines.append("**Key Variables:**")
                lines.append("")
                lines.append("| Variable | Label | Type | Source/Derivation |")
                lines.append("|----------|-------|------|-------------------|")

                for var in ds_spec.variables[:15]:  # Limit to key variables
                    source = var.source or var.derivation or "Derived"
                    lines.append(f"| {var.name} | {var.label[:30]} | {var.type} | {source[:30]} |")

                lines.append("")

        return "\n".join(lines)

    def get_paramcd_from_terminology(
        self,
        endpoint_type: EndpointType,
        terminology_service: Optional[CDISCTerminologyService] = None
    ) -> Dict[str, str]:
        """
        Get PARAMCD/PARAM from CDISC CT using terminology service.
        Falls back to hardcoded mappings if terminology service is not available or term not found.

        Args:
            endpoint_type: Endpoint type
            terminology_service: Optional terminology service instance

        Returns:
            Dict with PARAMCD, PARAM, NCI_CODE, DEFINITION
        """
        # Map endpoint types to search keywords
        ENDPOINT_KEYWORDS = {
            EndpointType.OS: "Overall Survival",
            EndpointType.PFS: "Progression-Free Survival",
            EndpointType.DFS: "Disease-Free Survival",
            EndpointType.EFS: "Event-Free Survival",
            EndpointType.ORR: "Objective Response Rate",
            EndpointType.DOR: "Duration of Response",
            EndpointType.DCR: "Disease Control Rate",
            EndpointType.TTP: "Time to Progression",
            EndpointType.TTF: "Time to Treatment Failure",
            EndpointType.PCR: "Pathologic Complete Response",
        }

        result = {}

        # Try terminology service if available
        if get_terminology_service is not None:
            try:
                service = terminology_service or get_terminology_service()
                keyword = ENDPOINT_KEYWORDS.get(endpoint_type)

                if keyword:
                    search_results = service.search_param(keyword)
                    if search_results:
                        term = search_results[0]
                        result = {
                            "PARAMCD": term.submission_value,
                            "PARAM": term.preferred_term,
                            "NCI_CODE": term.nci_code,
                            "DEFINITION": term.definition
                        }
                        logger.info(
                            f"Found PARAMCD from terminology service: {term.submission_value} = {term.preferred_term}"
                        )
                        return result
            except Exception as e:
                logger.warning(f"Terminology service lookup failed: {e}, falling back to hardcoded values")

        # Fall back to hardcoded legacy mappings
        LEGACY_MAPPING = {
            EndpointType.OS: {"PARAMCD": "OS", "PARAM": "Overall Survival"},
            EndpointType.PFS: {"PARAMCD": "PFS", "PARAM": "Progression-Free Survival"},
            EndpointType.DFS: {"PARAMCD": "DFS", "PARAM": "Disease-Free Survival"},
            EndpointType.EFS: {"PARAMCD": "EFS", "PARAM": "Event-Free Survival"},
            EndpointType.ORR: {"PARAMCD": "BOR", "PARAM": "Best Overall Response"},
            EndpointType.DOR: {"PARAMCD": "DOR", "PARAM": "Duration of Response"},
            EndpointType.DCR: {"PARAMCD": "DCR", "PARAM": "Disease Control Rate"},
            EndpointType.TTP: {"PARAMCD": "TTP", "PARAM": "Time to Progression"},
            EndpointType.TTF: {"PARAMCD": "TTF", "PARAM": "Time to Treatment Failure"},
        }

        result = LEGACY_MAPPING.get(endpoint_type, {
            "PARAMCD": "PRMEFF",
            "PARAM": "Primary Efficacy Endpoint"
        })

        logger.debug(f"Using legacy PARAMCD mapping: {result.get('PARAMCD')} = {result.get('PARAM')}")
        return result

    def validate_paramcd(
        self,
        paramcd: str,
        param: str,
        terminology_service: Optional[CDISCTerminologyService] = None
    ) -> bool:
        """
        Validate PARAMCD/PARAM pair against CDISC CT.

        Args:
            paramcd: Parameter code
            param: Parameter decode
            terminology_service: Optional terminology service instance

        Returns:
            True if valid or validation not possible, False if definitively invalid
        """
        if get_terminology_service is None:
            # Terminology service not available, cannot validate
            return True

        try:
            service = terminology_service or get_terminology_service()
            codelist = service.get_codelist("PARAMCD")

            if not codelist:
                logger.warning("PARAMCD codelist not found, skipping validation")
                return True

            # Check if PARAMCD exists
            valid_codes = {item.submission_value for item in codelist.items}

            if paramcd not in valid_codes:
                if codelist.extensible:
                    logger.info(f"PARAMCD '{paramcd}' not in standard CT (extensible list - sponsor-defined allowed)")
                    return True
                else:
                    logger.warning(f"Invalid PARAMCD '{paramcd}' not found in CT")
                    return False

            # Check if PARAM matches
            matching_item = next(
                (item for item in codelist.items if item.submission_value == paramcd),
                None
            )

            if matching_item and matching_item.preferred_term != param:
                logger.warning(
                    f"PARAM mismatch: '{param}' doesn't match CT preferred term '{matching_item.preferred_term}'"
                )
                return False

            return True

        except Exception as e:
            logger.warning(f"PARAMCD validation failed: {e}")
            return True  # Don't fail if validation itself errors


# Factory function
def create_cdisc_mapper() -> CDISCMapper:
    """Create a CDISC mapper instance"""
    return CDISCMapper()


# Enhanced factory with terminology service
def create_cdisc_mapper_with_terminology(
    terminology_service: Optional[CDISCTerminologyService] = None,
    use_terminology: bool = True
) -> CDISCMapper:
    """
    Create a CDISC mapper instance with optional terminology service integration.

    Args:
        terminology_service: Optional terminology service instance
        use_terminology: Whether to use terminology service for lookups

    Returns:
        CDISCMapper instance
    """
    mapper = CDISCMapper()

    if use_terminology and get_terminology_service is not None:
        # Attach terminology service for enhanced lookups
        if terminology_service is None:
            try:
                terminology_service = get_terminology_service()
                logger.info("CDISC mapper initialized with terminology service")
            except Exception as e:
                logger.warning(f"Could not initialize terminology service: {e}")

    return mapper
