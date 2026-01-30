#!/usr/bin/env python3
"""
Enterprise SAP Generation System - ADaM Derivation Specifications
==================================================================
PRODUCTION-LEVEL derivation specifications for biostatisticians.

Generates detailed, implementable derivation rules for ADaM variables
based on endpoint type, therapeutic area, and protocol requirements.

These are real specifications that programmers can implement directly.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

try:
    from ..core.schemas import ParsedProtocol, EndpointType, Estimand
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from core.schemas import ParsedProtocol, EndpointType, Estimand


@dataclass
class VariableDerivation:
    """Detailed derivation specification for a single ADaM variable"""
    variable: str
    label: str
    type: str  # Num, Char
    length: Optional[int]
    format: Optional[str]
    source_variables: List[str]  # SDTM source variables
    derivation_algorithm: str  # Detailed SAS-like pseudocode
    derivation_type: str  # "Direct Copy", "Computed", "Assigned", "Derived"
    controlled_terminology: Optional[str]
    comments: str

    def to_dict(self) -> Dict:
        return {
            "variable": self.variable,
            "label": self.label,
            "type": self.type,
            "length": self.length,
            "format": self.format,
            "source_variables": self.source_variables,
            "derivation_algorithm": self.derivation_algorithm,
            "derivation_type": self.derivation_type,
            "controlled_terminology": self.controlled_terminology,
            "comments": self.comments
        }


@dataclass
class DatasetDerivationSpec:
    """Complete derivation specification for an ADaM dataset"""
    dataset_name: str
    dataset_label: str
    structure: str  # ADSL, BDS, OCCDS
    key_variables: List[str]
    source_datasets: List[str]
    variables: List[VariableDerivation]
    general_notes: List[str]

    def to_markdown(self) -> str:
        """Generate markdown documentation"""
        lines = [
            f"## {self.dataset_name}: {self.dataset_label}",
            "",
            f"**Structure:** {self.structure}",
            f"**Key Variables:** {', '.join(self.key_variables)}",
            f"**Source Datasets:** {', '.join(self.source_datasets)}",
            "",
            "### Variable Specifications",
            "",
            "| Variable | Label | Type | Derivation Type | Source |",
            "|----------|-------|------|-----------------|--------|",
        ]

        for var in self.variables:
            sources = ", ".join(var.source_variables[:3]) if var.source_variables else "Derived"
            lines.append(f"| {var.variable} | {var.label[:30]} | {var.type} | {var.derivation_type} | {sources} |")

        lines.append("")
        lines.append("### Detailed Derivations")
        lines.append("")

        for var in self.variables:
            if var.derivation_algorithm and var.derivation_type != "Direct Copy":
                lines.append(f"#### {var.variable}: {var.label}")
                lines.append("")
                lines.append(f"**Type:** {var.type}" + (f"({var.length})" if var.length else ""))
                if var.format:
                    lines.append(f"**Format:** {var.format}")
                lines.append(f"**Source:** {', '.join(var.source_variables)}")
                lines.append("")
                lines.append("**Derivation Algorithm:**")
                lines.append("```")
                lines.append(var.derivation_algorithm)
                lines.append("```")
                if var.comments:
                    lines.append(f"**Note:** {var.comments}")
                lines.append("")

        if self.general_notes:
            lines.append("### General Notes")
            lines.append("")
            for note in self.general_notes:
                lines.append(f"- {note}")
            lines.append("")

        return "\n".join(lines)


class DerivationSpecGenerator:
    """
    Generates production-level ADaM derivation specifications.
    These are real specifications that biostatisticians/programmers can implement.
    """

    # Baseline flag derivation patterns by therapeutic area
    BASELINE_DEFINITIONS = {
        "ONCOLOGY": {
            "definition": "Last non-missing assessment on or prior to the first dose date of study treatment",
            "algorithm": """
/* Baseline Definition: Last non-missing value on or prior to first dose */
ABLFL = 'Y' WHERE:
  1. ADT <= TRTSDT (assessment date <= treatment start date)
  2. AVAL is not missing
  3. ADT = max(ADT) among all qualifying records for the subject/parameter

IF no pre-dose assessment exists:
  ABLFL = 'Y' for the first post-baseline assessment (flag with ABLFL = 'Y' and set BASETYPE = 'FIRST POST-DOSE')
"""
        },
        "IBD": {
            "definition": "Last non-missing assessment prior to the first dose of induction therapy",
            "algorithm": """
/* Baseline Definition for IBD: Last assessment before first induction dose */
ABLFL = 'Y' WHERE:
  1. ADT < TRTSDT (assessment date strictly before treatment start)
  2. AVAL is not missing
  3. ADT = max(ADT) among all qualifying pre-treatment records

For Mayo Score and components:
  Baseline = Screening visit assessment if within 14 days of first dose
  If multiple screening assessments, use the one closest to first dose
"""
        },
        "CARDIOVASCULAR": {
            "definition": "Average of the last two assessments prior to randomization, if available; otherwise the last assessment",
            "algorithm": """
/* Baseline Definition for CV: Average of last 2 pre-randomization assessments */
ABLFL = 'Y' for the derived baseline record WHERE:
  IF 2+ assessments exist with ADT <= RANDDT:
    AVAL = mean(last 2 non-missing values before RANDDT)
    BASE = AVAL
  ELSE IF 1 assessment exists:
    AVAL = the single pre-randomization value
    BASE = AVAL
  ABLFL always set on derived baseline record, not source records
"""
        },
        "DEFAULT": {
            "definition": "Last non-missing assessment prior to the first dose of study treatment",
            "algorithm": """
/* Baseline Definition: Last non-missing value prior to first dose */
ABLFL = 'Y' WHERE:
  1. ADT <= TRTSDT (assessment date on or before first dose)
  2. AVAL is not missing
  3. No subsequent assessments on same day with ADT = TRTSDT
  4. ADT = max(ADT) among qualifying records

IF subject never received treatment:
  ABLFL = 'Y' for last assessment prior to randomization date
"""
        }
    }

    # Analysis record flag patterns
    ANALYSIS_FLAG_PATTERNS = {
        "ANL01FL": {
            "label": "Analysis Record Flag 01",
            "description": "Primary analysis record within each visit window",
            "algorithm": """
/* ANL01FL: Primary Analysis Record Flag */
ANL01FL = 'Y' WHERE:
  1. Record falls within defined visit window (AVISIT is not missing)
  2. If multiple records in same window:
     - Use record closest to target day
     - If equidistant, use earlier record
     - If same day, use record with non-missing AVAL
  3. Baseline record (ABLFL = 'Y') also gets ANL01FL = 'Y'
  4. Records outside any defined window: ANL01FL = '' (missing)
"""
        },
        "ANL02FL": {
            "label": "Analysis Record Flag 02",
            "description": "Records eligible for response assessment",
            "algorithm": """
/* ANL02FL: Response Analysis Flag (for oncology/responder endpoints) */
ANL02FL = 'Y' WHERE:
  1. Record has evaluable tumor assessment
  2. Assessment performed per protocol schedule (within window)
  3. For Best Overall Response:
     ANL02FL = 'Y' only for the BOR record per subject
  4. Missing or NE assessments: ANL02FL = '' (missing)
"""
        },
        "CRIT1FL": {
            "label": "Criterion 1 Evaluation Flag",
            "description": "Flag for subjects meeting primary endpoint criterion",
            "algorithm": """
/* CRIT1FL: Primary Endpoint Criterion Flag */
CRIT1FL = 'Y' WHERE subject meets primary endpoint definition:
  For binary endpoints (e.g., response, remission):
    CRIT1FL = 'Y' if AVALC in ('CR', 'PR', 'REMISSION', 'RESPONSE') per endpoint definition
    CRIT1FL = 'N' if evaluable but did not meet criterion
    CRIT1FL = '' (missing) if not evaluable

  CRIT1 = Description of the criterion (e.g., "Clinical Remission at Week 8")
  CRIT1FN = Numeric version: 1 = 'Y', 0 = 'N', missing = not evaluable
"""
        }
    }

    def __init__(self, llm_client=None):
        """Initialize the derivation spec generator"""
        self.llm_client = llm_client

    def generate_adsl_derivations(
        self,
        protocol: ParsedProtocol,
        estimands: Dict[str, Any]
    ) -> DatasetDerivationSpec:
        """
        Generate complete ADSL derivation specifications.

        Args:
            protocol: Parsed protocol information
            estimands: Estimand definitions

        Returns:
            Complete ADSL derivation specification
        """
        # Get therapeutic area for baseline definition
        ta = protocol.therapeutic_area or "DEFAULT"
        baseline_def = self.BASELINE_DEFINITIONS.get(ta, self.BASELINE_DEFINITIONS["DEFAULT"])

        # Build treatment variables based on design
        design_str = str(protocol.design_type.value) if hasattr(protocol.design_type, 'value') else str(protocol.design_type or "")
        is_crossover = "crossover" in design_str.lower()

        variables = [
            # Identifiers
            VariableDerivation(
                variable="STUDYID",
                label="Study Identifier",
                type="Char",
                length=20,
                format=None,
                source_variables=["DM.STUDYID"],
                derivation_algorithm="STUDYID = DM.STUDYID",
                derivation_type="Direct Copy",
                controlled_terminology=None,
                comments="Unique study identifier across all datasets"
            ),
            VariableDerivation(
                variable="USUBJID",
                label="Unique Subject Identifier",
                type="Char",
                length=40,
                format=None,
                source_variables=["DM.USUBJID"],
                derivation_algorithm="USUBJID = DM.USUBJID",
                derivation_type="Direct Copy",
                controlled_terminology=None,
                comments="Unique subject identifier: STUDYID-SITEID-SUBJID"
            ),
            VariableDerivation(
                variable="SUBJID",
                label="Subject Identifier for the Study",
                type="Char",
                length=20,
                format=None,
                source_variables=["DM.SUBJID"],
                derivation_algorithm="SUBJID = DM.SUBJID",
                derivation_type="Direct Copy",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="SITEID",
                label="Study Site Identifier",
                type="Char",
                length=10,
                format=None,
                source_variables=["DM.SITEID"],
                derivation_algorithm="SITEID = DM.SITEID",
                derivation_type="Direct Copy",
                controlled_terminology=None,
                comments=""
            ),

            # Demographics
            VariableDerivation(
                variable="AGE",
                label="Age",
                type="Num",
                length=8,
                format=None,
                source_variables=["DM.AGE", "DM.AGEU"],
                derivation_algorithm="""
/* Age in years at informed consent */
IF DM.AGEU = 'YEARS' THEN AGE = DM.AGE;
ELSE IF DM.AGEU = 'MONTHS' THEN AGE = floor(DM.AGE / 12);
ELSE IF DM.AGEU = 'DAYS' THEN AGE = floor(DM.AGE / 365.25);
""",
                derivation_type="Computed",
                controlled_terminology=None,
                comments="Age at time of informed consent in years"
            ),
            VariableDerivation(
                variable="AGEGR1",
                label="Pooled Age Group 1",
                type="Char",
                length=20,
                format=None,
                source_variables=["ADSL.AGE"],
                derivation_algorithm="""
/* Age Group for Subgroup Analysis */
IF AGE < 18 THEN AGEGR1 = '<18 years';
ELSE IF 18 <= AGE < 65 THEN AGEGR1 = '18-64 years';
ELSE IF AGE >= 65 THEN AGEGR1 = '>=65 years';

AGEGR1N = 1 for '<18 years', 2 for '18-64 years', 3 for '>=65 years';
""",
                derivation_type="Derived",
                controlled_terminology=None,
                comments="Age categories for subgroup analysis"
            ),
            VariableDerivation(
                variable="SEX",
                label="Sex",
                type="Char",
                length=1,
                format=None,
                source_variables=["DM.SEX"],
                derivation_algorithm="SEX = DM.SEX",
                derivation_type="Direct Copy",
                controlled_terminology="CDISC Sex: M, F, U, UNDIFFERENTIATED",
                comments=""
            ),
            VariableDerivation(
                variable="RACE",
                label="Race",
                type="Char",
                length=60,
                format=None,
                source_variables=["DM.RACE"],
                derivation_algorithm="RACE = DM.RACE",
                derivation_type="Direct Copy",
                controlled_terminology="CDISC Race CT",
                comments="If multiple races, use MULTIPLE"
            ),
            VariableDerivation(
                variable="ETHNIC",
                label="Ethnicity",
                type="Char",
                length=60,
                format=None,
                source_variables=["DM.ETHNIC"],
                derivation_algorithm="ETHNIC = DM.ETHNIC",
                derivation_type="Direct Copy",
                controlled_terminology="HISPANIC OR LATINO, NOT HISPANIC OR LATINO",
                comments=""
            ),

            # Treatment Variables
            VariableDerivation(
                variable="TRT01P",
                label="Planned Treatment for Period 01",
                type="Char",
                length=200,
                format=None,
                source_variables=["DM.ARM", "DM.ARMCD"],
                derivation_algorithm="""
/* Planned Treatment - as randomized */
TRT01P = DM.ARM (full arm description);
TRT01PN = Numeric code based on ARM order in protocol;

/* For blinded studies, treatment codes remain blinded until DBL */
""",
                derivation_type="Direct Copy",
                controlled_terminology=None,
                comments="Treatment as randomized (ITT principle)"
            ),
            VariableDerivation(
                variable="TRT01A",
                label="Actual Treatment for Period 01",
                type="Char",
                length=200,
                format=None,
                source_variables=["EX.EXTRT", "DM.ARM"],
                derivation_algorithm="""
/* Actual Treatment - as received */
IF subject received any dose of study treatment:
  TRT01A = Treatment actually received (from EX domain);
ELSE:
  TRT01A = 'NOT TREATED';
TRT01AN = Numeric code matching TRT01A;

/* Note: For Safety population analysis, use TRT01A */
""",
                derivation_type="Derived",
                controlled_terminology=None,
                comments="Treatment actually received (for Safety analysis)"
            ),

            # Key Dates
            VariableDerivation(
                variable="RANDDT",
                label="Date of Randomization",
                type="Num",
                length=8,
                format="DATE9.",
                source_variables=["DS.DSSTDTC", "DM.RFSTDTC"],
                derivation_algorithm="""
/* Randomization Date */
RANDDT = input from DS domain where DSTERM = 'RANDOMIZED' or DSDECOD = 'RANDOMIZED';
IF RANDDT is missing:
  RANDDT = input(DM.RFSTDTC, yymmdd10.) where DM.RFSTDTC represents randomization;

/* Convert ISO 8601 to SAS date */
RANDDT = input(substr(DSSTDTC, 1, 10), yymmdd10.);
""",
                derivation_type="Derived",
                controlled_terminology=None,
                comments="Date subject was randomized to treatment"
            ),
            VariableDerivation(
                variable="TRTSDT",
                label="Date of First Exposure to Treatment",
                type="Num",
                length=8,
                format="DATE9.",
                source_variables=["EX.EXSTDTC"],
                derivation_algorithm="""
/* First Treatment Date */
TRTSDT = min(input(EX.EXSTDTC, yymmdd10.))
         WHERE EX.EXDOSE > 0 or EX.EXADJ ne 'NOT APPLICABLE';

/* Handle partial dates */
IF EXSTDTC has missing day:
  Impute to first of month for first dose;

/* If no treatment received */
IF no valid EX records:
  TRTSDT = . (missing);
""",
                derivation_type="Computed",
                controlled_terminology=None,
                comments="First date of any study drug exposure"
            ),
            VariableDerivation(
                variable="TRTEDT",
                label="Date of Last Exposure to Treatment",
                type="Num",
                length=8,
                format="DATE9.",
                source_variables=["EX.EXENDTC"],
                derivation_algorithm="""
/* Last Treatment Date */
TRTEDT = max(input(EX.EXENDTC, yymmdd10.))
         WHERE EX.EXDOSE > 0;

/* If EXENDTC missing for ongoing treatment */
IF EXENDTC missing and treatment ongoing:
  TRTEDT = data cutoff date or last known treatment date;

/* Handle partial dates */
IF EXENDTC has missing day:
  Impute to last day of month;
""",
                derivation_type="Computed",
                controlled_terminology=None,
                comments="Last date of study drug exposure (including partial doses)"
            ),

            # Population Flags
            VariableDerivation(
                variable="ITTFL",
                label="Intent-To-Treat Population Flag",
                type="Char",
                length=1,
                format=None,
                source_variables=["ADSL.RANDDT"],
                derivation_algorithm="""
/* ITT Population: All Randomized Subjects */
IF RANDDT is not missing THEN ITTFL = 'Y';
ELSE ITTFL = 'N';

/* ITT subjects analyzed as randomized regardless of:
   - Treatment actually received
   - Protocol deviations
   - Early discontinuation
*/
""",
                derivation_type="Derived",
                controlled_terminology="Y, N",
                comments="ITT = All randomized subjects"
            ),
            VariableDerivation(
                variable="SAFFL",
                label="Safety Population Flag",
                type="Char",
                length=1,
                format=None,
                source_variables=["ADSL.TRTSDT"],
                derivation_algorithm="""
/* Safety Population: Received at least one dose */
IF TRTSDT is not missing THEN SAFFL = 'Y';
ELSE SAFFL = 'N';

/* Safety subjects analyzed as treated:
   - Use TRT01A (actual treatment) not TRT01P (planned)
   - Include subjects who received partial dose
*/
""",
                derivation_type="Derived",
                controlled_terminology="Y, N",
                comments="Safety = Received any study treatment"
            ),
            VariableDerivation(
                variable="PPROTFL",
                label="Per-Protocol Population Flag",
                type="Char",
                length=1,
                format=None,
                source_variables=["ADSL.ITTFL", "DV domain"],
                derivation_algorithm="""
/* Per-Protocol Population */
PPROTFL = 'Y' WHERE ALL of the following are true:
  1. ITTFL = 'Y' (subject is in ITT)
  2. Received >= 80% of planned treatment doses
  3. No major protocol deviations affecting efficacy assessment:
     - Check DV domain for DVCAT = 'MAJOR' and affects efficacy
     - Violations of inclusion/exclusion criteria
     - Prohibited concomitant medications
     - Missing primary endpoint not due to documented event
  4. Has at least one post-baseline efficacy assessment

PPROTFL = 'N' otherwise;

/* Document reason for PP exclusion in PPROTRN variable */
""",
                derivation_type="Derived",
                controlled_terminology="Y, N",
                comments="PP = ITT without major deviations"
            ),
        ]

        # Add crossover-specific variables if applicable
        if is_crossover:
            variables.extend([
                VariableDerivation(
                    variable="TRT02P",
                    label="Planned Treatment for Period 02",
                    type="Char",
                    length=200,
                    format=None,
                    source_variables=["DM.ARM"],
                    derivation_algorithm="/* Crossover treatment assignment */",
                    derivation_type="Derived",
                    controlled_terminology=None,
                    comments="Treatment in second period of crossover"
                ),
            ])

        return DatasetDerivationSpec(
            dataset_name="ADSL",
            dataset_label="Subject-Level Analysis Dataset",
            structure="ADSL",
            key_variables=["STUDYID", "USUBJID"],
            source_datasets=["DM", "DS", "EX", "DV", "SV"],
            variables=variables,
            general_notes=[
                "One record per subject",
                "Contains all subject-level variables needed across analysis datasets",
                f"Baseline definition: {baseline_def['definition']}",
                "Population flags derived in order: RANDFL -> ITTFL -> SAFFL -> PPROTFL",
                "All dates stored as SAS numeric dates (days since 01JAN1960)"
            ]
        )

    def generate_efficacy_derivations(
        self,
        protocol: ParsedProtocol,
        estimands: Dict[str, Any],
        endpoint_type: EndpointType
    ) -> DatasetDerivationSpec:
        """
        Generate efficacy dataset derivation specifications based on endpoint type.

        Args:
            protocol: Parsed protocol
            estimands: Estimand definitions
            endpoint_type: Type of primary endpoint

        Returns:
            Dataset derivation specification (ADEFF, ADRS, or ADTTE)
        """
        ta = protocol.therapeutic_area or "DEFAULT"
        baseline_def = self.BASELINE_DEFINITIONS.get(ta, self.BASELINE_DEFINITIONS["DEFAULT"])

        if endpoint_type in [EndpointType.OS, EndpointType.PFS, EndpointType.DFS, EndpointType.EFS]:
            return self._generate_adtte_derivations(protocol, estimands, endpoint_type, baseline_def)
        elif endpoint_type == EndpointType.ORR:
            return self._generate_adrs_derivations(protocol, estimands, baseline_def)
        else:
            return self._generate_adeff_derivations(protocol, estimands, endpoint_type, baseline_def)

    def _generate_adtte_derivations(
        self,
        protocol: ParsedProtocol,
        estimands: Dict,
        endpoint_type: EndpointType,
        baseline_def: Dict
    ) -> DatasetDerivationSpec:
        """Generate ADTTE (time-to-event) derivations"""

        # Define event and censoring rules based on endpoint
        event_rules = {
            EndpointType.OS: {
                "event": "Death from any cause",
                "censoring": "Last known alive date",
                "paramcd": "OS"
            },
            EndpointType.PFS: {
                "event": "Disease progression (per RECIST 1.1) or death",
                "censoring": "Last adequate tumor assessment date",
                "paramcd": "PFS"
            },
            EndpointType.DFS: {
                "event": "Disease recurrence (local or distant) or death",
                "censoring": "Last disease assessment date",
                "paramcd": "DFS"
            },
            EndpointType.EFS: {
                "event": "Protocol-defined composite event",
                "censoring": "Last disease evaluation date",
                "paramcd": "EFS"
            }
        }

        rules = event_rules.get(endpoint_type, event_rules[EndpointType.OS])

        variables = [
            VariableDerivation(
                variable="STUDYID",
                label="Study Identifier",
                type="Char",
                length=20,
                format=None,
                source_variables=["ADSL.STUDYID"],
                derivation_algorithm="STUDYID = ADSL.STUDYID",
                derivation_type="Direct Copy",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="USUBJID",
                label="Unique Subject Identifier",
                type="Char",
                length=40,
                format=None,
                source_variables=["ADSL.USUBJID"],
                derivation_algorithm="USUBJID = ADSL.USUBJID",
                derivation_type="Direct Copy",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="PARAMCD",
                label="Parameter Code",
                type="Char",
                length=8,
                format=None,
                source_variables=[],
                derivation_algorithm=f"PARAMCD = '{rules['paramcd']}'",
                derivation_type="Assigned",
                controlled_terminology=None,
                comments=f"Parameter code for {endpoint_type.value}"
            ),
            VariableDerivation(
                variable="PARAM",
                label="Parameter",
                type="Char",
                length=200,
                format=None,
                source_variables=[],
                derivation_algorithm=f"PARAM = '{endpoint_type.value} ({rules['event']})'",
                derivation_type="Assigned",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="STARTDT",
                label="Time-to-Event Origin Date",
                type="Num",
                length=8,
                format="DATE9.",
                source_variables=["ADSL.RANDDT", "ADSL.TRTSDT"],
                derivation_algorithm="""
/* Origin date for time-to-event calculation */
STARTDT = ADSL.RANDDT; /* Randomization date for ITT analysis */

/* Alternative origins (specify in STARTDTF):
   TRTSDT for as-treated analysis
   Surgery date for DFS
   Complete response date for DFS post-CR
*/
""",
                derivation_type="Derived",
                controlled_terminology=None,
                comments="Time origin is randomization date per protocol"
            ),
            VariableDerivation(
                variable="ADT",
                label="Analysis Date",
                type="Num",
                length=8,
                format="DATE9.",
                source_variables=["DD.DTHDTC", "DS.DSSTDTC", "RS.RSDTC"],
                derivation_algorithm=f"""
/* Event/Censoring Date Derivation for {endpoint_type.value} */

/* Step 1: Check for event */
IF event occurred:
  {rules['event']}:
  ADT = date of event (death date from DD, progression date from RS);
  CNSR = 0;
  EVNTDESC = '{rules['event']}';

/* Step 2: If no event, apply censoring */
ELSE:
  ADT = {rules['censoring']};
  CNSR = 1;
  CNSDTDSC = '{rules['censoring']}';

/* Censoring hierarchy (use earliest applicable):
   1. Start of subsequent anti-cancer therapy
   2. Last adequate tumor assessment
   3. Last known alive date
   4. Randomization date (if no other date available)
*/
""",
                derivation_type="Computed",
                controlled_terminology=None,
                comments="Date of event or censoring"
            ),
            VariableDerivation(
                variable="AVAL",
                label="Analysis Value",
                type="Num",
                length=8,
                format=None,
                source_variables=["ADTTE.ADT", "ADTTE.STARTDT"],
                derivation_algorithm="""
/* Time-to-event in days */
AVAL = ADT - STARTDT + 1;

/* +1 ensures subjects with event on same day as origin have AVAL >= 1 */

/* For months conversion (if needed):
   AVAL_MONTHS = AVAL / 30.4375;
*/
""",
                derivation_type="Computed",
                controlled_terminology=None,
                comments="Time to event in days from origin"
            ),
            VariableDerivation(
                variable="CNSR",
                label="Censor",
                type="Num",
                length=8,
                format=None,
                source_variables=[],
                derivation_algorithm="""
/* Censoring indicator */
CNSR = 0 if subject experienced the event;
CNSR = 1 if subject was censored (did not experience event);

/* Censoring reasons tracked in CNSDTDSC */
""",
                derivation_type="Derived",
                controlled_terminology="0=Event, 1=Censored",
                comments="0=Event occurred, 1=Censored"
            ),
            VariableDerivation(
                variable="EVNTDESC",
                label="Event or Censoring Description",
                type="Char",
                length=200,
                format=None,
                source_variables=[],
                derivation_algorithm="""
/* Description of what happened */
IF CNSR = 0 (event):
  EVNTDESC = Description of event (e.g., 'Death', 'PD per RECIST 1.1');
IF CNSR = 1 (censored):
  EVNTDESC = 'Censored - ' || censoring reason;
""",
                derivation_type="Derived",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="SRCSEQ",
                label="Source Sequence Number",
                type="Num",
                length=8,
                format=None,
                source_variables=["RS.RSSEQ", "DD.DDSEQ"],
                derivation_algorithm="SRCSEQ = sequence number from source record",
                derivation_type="Direct Copy",
                controlled_terminology=None,
                comments="Links back to source SDTM record"
            ),
            # Population flags
            VariableDerivation(
                variable="ITTFL",
                label="Intent-To-Treat Population Flag",
                type="Char",
                length=1,
                format=None,
                source_variables=["ADSL.ITTFL"],
                derivation_algorithm="ITTFL = ADSL.ITTFL",
                derivation_type="Direct Copy",
                controlled_terminology="Y, N",
                comments=""
            ),
            VariableDerivation(
                variable="ANL01FL",
                label="Analysis Record Flag 01",
                type="Char",
                length=1,
                format=None,
                source_variables=[],
                derivation_algorithm="""
/* Analysis Flag - one record per subject per parameter */
ANL01FL = 'Y' for the single analysis record per USUBJID/PARAMCD;

/* For ADTTE with one record per subject per parameter,
   all records should have ANL01FL = 'Y' */
""",
                derivation_type="Derived",
                controlled_terminology="Y",
                comments="Y for all records in ADTTE"
            ),
        ]

        return DatasetDerivationSpec(
            dataset_name="ADTTE",
            dataset_label="Time-to-Event Analysis Dataset",
            structure="BDS",
            key_variables=["STUDYID", "USUBJID", "PARAMCD"],
            source_datasets=["ADSL", "RS", "DD", "DS", "AE"],
            variables=variables,
            general_notes=[
                "One record per subject per time-to-event parameter",
                f"Primary endpoint: {endpoint_type.value}",
                f"Event definition: {rules['event']}",
                f"Censoring: {rules['censoring']}",
                "Time origin: Randomization date (STARTDT = RANDDT)",
                "AVAL in days; for months, divide by 30.4375"
            ]
        )

    def _generate_adrs_derivations(
        self,
        protocol: ParsedProtocol,
        estimands: Dict,
        baseline_def: Dict
    ) -> DatasetDerivationSpec:
        """Generate ADRS (tumor response) derivations for oncology"""

        variables = [
            VariableDerivation(
                variable="STUDYID",
                label="Study Identifier",
                type="Char",
                length=20,
                format=None,
                source_variables=["ADSL.STUDYID"],
                derivation_algorithm="STUDYID = ADSL.STUDYID",
                derivation_type="Direct Copy",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="USUBJID",
                label="Unique Subject Identifier",
                type="Char",
                length=40,
                format=None,
                source_variables=["ADSL.USUBJID"],
                derivation_algorithm="USUBJID = ADSL.USUBJID",
                derivation_type="Direct Copy",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="PARAMCD",
                label="Parameter Code",
                type="Char",
                length=8,
                format=None,
                source_variables=["RS.RSTESTCD"],
                derivation_algorithm="""
/* Response Parameter Codes */
PARAMCD = 'OVRLRESP' for overall response at each visit;
PARAMCD = 'BOR' for best overall response;
PARAMCD = 'CBOR' for confirmed best overall response;
""",
                derivation_type="Derived",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="AVISIT",
                label="Analysis Visit",
                type="Char",
                length=40,
                format=None,
                source_variables=["RS.VISIT", "RS.VISITNUM"],
                derivation_algorithm="""
/* Analysis Visit Assignment */
Map RS.VISIT to protocol-defined analysis visits;
AVISIT = 'Baseline' for screening/baseline assessments;
AVISIT = 'Week X' for scheduled tumor assessments;
AVISIT = 'Best Overall Response' for BOR record;
""",
                derivation_type="Derived",
                controlled_terminology=None,
                comments="Analysis visit windowed to protocol schedule"
            ),
            VariableDerivation(
                variable="AVALC",
                label="Analysis Value (C)",
                type="Char",
                length=20,
                format=None,
                source_variables=["RS.RSSTRESC", "RS.RSORRES"],
                derivation_algorithm="""
/* Overall Response per RECIST 1.1 */
AVALC values:
  'CR'  = Complete Response
  'PR'  = Partial Response
  'SD'  = Stable Disease
  'PD'  = Progressive Disease
  'NE'  = Not Evaluable

/* Best Overall Response derivation */
FOR PARAMCD = 'BOR':
  IF any confirmed CR: AVALC = 'CR';
  ELSE IF any confirmed PR (and no PD before): AVALC = 'PR';
  ELSE IF SD maintained >= minimum duration: AVALC = 'SD';
  ELSE IF PD as best response: AVALC = 'PD';
  ELSE: AVALC = 'NE';
""",
                derivation_type="Computed",
                controlled_terminology="RECIST 1.1 Response Criteria",
                comments="Response per RECIST 1.1 or protocol criteria"
            ),
            VariableDerivation(
                variable="AVAL",
                label="Analysis Value",
                type="Num",
                length=8,
                format=None,
                source_variables=["ADRS.AVALC"],
                derivation_algorithm="""
/* Numeric response for analysis */
AVAL = 1 if AVALC in ('CR', 'PR');  /* Responder */
AVAL = 0 if AVALC in ('SD', 'PD'); /* Non-responder */
AVAL = . if AVALC = 'NE';          /* Not evaluable */

/* For ORR analysis: proportion with AVAL = 1 */
""",
                derivation_type="Derived",
                controlled_terminology=None,
                comments="1=Responder (CR/PR), 0=Non-responder"
            ),
            VariableDerivation(
                variable="ANL01FL",
                label="Analysis Record Flag 01",
                type="Char",
                length=1,
                format=None,
                source_variables=[],
                derivation_algorithm=self.ANALYSIS_FLAG_PATTERNS["ANL01FL"]["algorithm"],
                derivation_type="Derived",
                controlled_terminology="Y",
                comments="Primary analysis record per visit window"
            ),
            VariableDerivation(
                variable="ANL02FL",
                label="Analysis Record Flag 02",
                type="Char",
                length=1,
                format=None,
                source_variables=[],
                derivation_algorithm="""
/* Confirmed Response Analysis Flag */
ANL02FL = 'Y' for BOR record only (PARAMCD = 'BOR' or 'CBOR');
Used to identify the single BOR record per subject for ORR analysis;
""",
                derivation_type="Derived",
                controlled_terminology="Y",
                comments="Flag for BOR/ORR analysis"
            ),
            VariableDerivation(
                variable="CRIT1FL",
                label="Criterion 1 Evaluation Flag",
                type="Char",
                length=1,
                format=None,
                source_variables=["ADRS.AVALC"],
                derivation_algorithm="""
/* Objective Response Criterion */
CRIT1 = 'Objective Response (CR or PR)';
CRIT1FL = 'Y' if AVALC in ('CR', 'PR') and response confirmed;
CRIT1FL = 'N' if evaluable but AVALC in ('SD', 'PD');
CRIT1FL = '' if not evaluable (AVALC = 'NE' or missing);
""",
                derivation_type="Derived",
                controlled_terminology="Y, N",
                comments="Responder flag for ORR endpoint"
            ),
        ]

        return DatasetDerivationSpec(
            dataset_name="ADRS",
            dataset_label="Tumor Response Analysis Dataset",
            structure="BDS",
            key_variables=["STUDYID", "USUBJID", "PARAMCD", "AVISIT"],
            source_datasets=["ADSL", "RS", "TU", "TR"],
            variables=variables,
            general_notes=[
                "One record per subject per response parameter per analysis visit",
                "Response criteria: RECIST 1.1 (or per protocol if different)",
                "Best Overall Response (BOR) requires confirmation per RECIST 1.1",
                "ORR = proportion of subjects with BOR of CR or PR",
                "ANL02FL = 'Y' flags the BOR record for ORR analysis"
            ]
        )

    def _generate_adeff_derivations(
        self,
        protocol: ParsedProtocol,
        estimands: Dict,
        endpoint_type: EndpointType,
        baseline_def: Dict
    ) -> DatasetDerivationSpec:
        """Generate ADEFF (general efficacy BDS) derivations"""

        # Determine endpoint-specific parameters
        if endpoint_type == EndpointType.EFFICACY:
            # IBD/general efficacy
            param_info = {
                "paramcd": "EFFRESP",
                "param": "Efficacy Response",
                "criterion": "Clinical Response/Remission per protocol definition"
            }
        else:
            param_info = {
                "paramcd": "EFFEND",
                "param": f"{endpoint_type.value} Endpoint",
                "criterion": f"{endpoint_type.value} per protocol"
            }

        variables = [
            VariableDerivation(
                variable="STUDYID",
                label="Study Identifier",
                type="Char",
                length=20,
                format=None,
                source_variables=["ADSL.STUDYID"],
                derivation_algorithm="STUDYID = ADSL.STUDYID",
                derivation_type="Direct Copy",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="USUBJID",
                label="Unique Subject Identifier",
                type="Char",
                length=40,
                format=None,
                source_variables=["ADSL.USUBJID"],
                derivation_algorithm="USUBJID = ADSL.USUBJID",
                derivation_type="Direct Copy",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="PARAMCD",
                label="Parameter Code",
                type="Char",
                length=8,
                format=None,
                source_variables=[],
                derivation_algorithm=f"PARAMCD = '{param_info['paramcd']}'",
                derivation_type="Assigned",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="PARAM",
                label="Parameter",
                type="Char",
                length=200,
                format=None,
                source_variables=[],
                derivation_algorithm=f"PARAM = '{param_info['param']}'",
                derivation_type="Assigned",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="AVISIT",
                label="Analysis Visit",
                type="Char",
                length=40,
                format=None,
                source_variables=["SDTM.VISIT"],
                derivation_algorithm="""
/* Analysis Visit from visit windowing */
Apply visit windows to map raw visits to analysis visits;
AVISIT = 'Baseline' for AVISITN = 0;
AVISIT = 'Week X' for scheduled visits;
""",
                derivation_type="Derived",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="AVISITN",
                label="Analysis Visit (N)",
                type="Num",
                length=8,
                format=None,
                source_variables=[],
                derivation_algorithm="""
/* Numeric analysis visit */
AVISITN = 0 for Baseline;
AVISITN = 1 for Week 1, etc.;
AVISITN = 99 for End of Treatment;
AVISITN = 999 for unscheduled;
""",
                derivation_type="Derived",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="ADT",
                label="Analysis Date",
                type="Num",
                length=8,
                format="DATE9.",
                source_variables=["SDTM domain.xxDTC"],
                derivation_algorithm="""
/* Analysis date from source assessment */
ADT = input(source_date, yymmdd10.);
For partial dates, apply imputation per Section 7.3;
""",
                derivation_type="Computed",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="AVAL",
                label="Analysis Value",
                type="Num",
                length=8,
                format=None,
                source_variables=["Source domain"],
                derivation_algorithm="""
/* Primary efficacy value */
AVAL = numeric efficacy score/measurement;
For composite scores, sum component values;
For continuous endpoints, use measured value;
""",
                derivation_type="Derived",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="AVALC",
                label="Analysis Value (C)",
                type="Char",
                length=200,
                format=None,
                source_variables=[],
                derivation_algorithm="""
/* Character response for categorical endpoints */
For responder endpoints:
  AVALC = 'RESPONDER' if meets response criteria;
  AVALC = 'NON-RESPONDER' if does not meet criteria;
  AVALC = 'NOT EVALUABLE' if insufficient data;
""",
                derivation_type="Derived",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="BASE",
                label="Baseline Value",
                type="Num",
                length=8,
                format=None,
                source_variables=["ADEFF.AVAL where ABLFL='Y'"],
                derivation_algorithm=f"""
/* Baseline Value */
{baseline_def['algorithm']}

BASE = AVAL where ABLFL = 'Y' for the same USUBJID/PARAMCD;
Propagate BASE to all records for same subject/parameter;
""",
                derivation_type="Derived",
                controlled_terminology=None,
                comments=baseline_def['definition']
            ),
            VariableDerivation(
                variable="CHG",
                label="Change from Baseline",
                type="Num",
                length=8,
                format=None,
                source_variables=["ADEFF.AVAL", "ADEFF.BASE"],
                derivation_algorithm="""
/* Change from Baseline */
IF AVISIT ne 'Baseline' and BASE is not missing:
  CHG = AVAL - BASE;
ELSE:
  CHG = . (missing for baseline records);
""",
                derivation_type="Computed",
                controlled_terminology=None,
                comments="Change from baseline (post-baseline only)"
            ),
            VariableDerivation(
                variable="PCHG",
                label="Percent Change from Baseline",
                type="Num",
                length=8,
                format=None,
                source_variables=["ADEFF.CHG", "ADEFF.BASE"],
                derivation_algorithm="""
/* Percent Change from Baseline */
IF BASE ne 0 and BASE is not missing:
  PCHG = (CHG / BASE) * 100;
ELSE:
  PCHG = . (missing if BASE = 0 or missing);
""",
                derivation_type="Computed",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="ABLFL",
                label="Baseline Record Flag",
                type="Char",
                length=1,
                format=None,
                source_variables=[],
                derivation_algorithm=baseline_def['algorithm'],
                derivation_type="Derived",
                controlled_terminology="Y",
                comments=baseline_def['definition']
            ),
            VariableDerivation(
                variable="ANL01FL",
                label="Analysis Record Flag 01",
                type="Char",
                length=1,
                format=None,
                source_variables=[],
                derivation_algorithm=self.ANALYSIS_FLAG_PATTERNS["ANL01FL"]["algorithm"],
                derivation_type="Derived",
                controlled_terminology="Y",
                comments="Primary analysis record per visit"
            ),
            VariableDerivation(
                variable="CRIT1FL",
                label="Criterion 1 Evaluation Flag",
                type="Char",
                length=1,
                format=None,
                source_variables=[],
                derivation_algorithm=f"""
/* {param_info['criterion']} */
{self.ANALYSIS_FLAG_PATTERNS['CRIT1FL']['algorithm']}
""",
                derivation_type="Derived",
                controlled_terminology="Y, N",
                comments=f"Flag for {param_info['criterion']}"
            ),
            # Treatment and population flags
            VariableDerivation(
                variable="TRTP",
                label="Planned Treatment",
                type="Char",
                length=200,
                format=None,
                source_variables=["ADSL.TRT01P"],
                derivation_algorithm="TRTP = ADSL.TRT01P",
                derivation_type="Direct Copy",
                controlled_terminology=None,
                comments=""
            ),
            VariableDerivation(
                variable="ITTFL",
                label="Intent-To-Treat Population Flag",
                type="Char",
                length=1,
                format=None,
                source_variables=["ADSL.ITTFL"],
                derivation_algorithm="ITTFL = ADSL.ITTFL",
                derivation_type="Direct Copy",
                controlled_terminology="Y, N",
                comments=""
            ),
        ]

        return DatasetDerivationSpec(
            dataset_name="ADEFF",
            dataset_label="Efficacy Analysis Dataset",
            structure="BDS",
            key_variables=["STUDYID", "USUBJID", "PARAMCD", "AVISIT"],
            source_datasets=["ADSL"] + self._get_efficacy_source_domains(endpoint_type),
            variables=variables,
            general_notes=[
                "One record per subject per parameter per analysis visit",
                f"Baseline: {baseline_def['definition']}",
                "CHG and PCHG only calculated for post-baseline records",
                "ANL01FL = 'Y' for primary analysis record per visit window",
                f"CRIT1FL evaluates: {param_info['criterion']}"
            ]
        )

    def _get_efficacy_source_domains(self, endpoint_type: EndpointType) -> List[str]:
        """Get source SDTM domains based on endpoint type"""
        domain_map = {
            EndpointType.EFFICACY: ["QS", "FA", "LB"],  # Questionnaires, Findings About, Labs
            EndpointType.SAFETY: ["AE", "LB", "VS"],
            EndpointType.PK: ["PC", "PP"],
            EndpointType.ORR: ["RS", "TU", "TR"],
            EndpointType.OS: ["DD", "DS"],
            EndpointType.PFS: ["RS", "TU", "DD", "DS"],
            EndpointType.OTHER: ["FA", "QS"]
        }
        return domain_map.get(endpoint_type, ["FA"])

    def generate_all_derivations(
        self,
        protocol: ParsedProtocol,
        estimands: Dict[str, Any]
    ) -> Dict[str, DatasetDerivationSpec]:
        """
        Generate all required derivation specifications.

        Args:
            protocol: Parsed protocol
            estimands: Estimand definitions

        Returns:
            Dictionary of dataset name -> derivation specification
        """
        specs = {}

        # Always generate ADSL
        specs["ADSL"] = self.generate_adsl_derivations(protocol, estimands)

        # Generate efficacy dataset based on endpoint
        endpoint_type = EndpointType.OTHER
        if protocol.primary_estimand:
            endpoint_type = protocol.primary_estimand.variable_type

        efficacy_spec = self.generate_efficacy_derivations(protocol, estimands, endpoint_type)
        specs[efficacy_spec.dataset_name] = efficacy_spec

        return specs

    def generate_derivation_document(
        self,
        protocol: ParsedProtocol,
        estimands: Dict[str, Any]
    ) -> str:
        """
        Generate complete derivation specifications document.

        Args:
            protocol: Parsed protocol
            estimands: Estimand definitions

        Returns:
            Complete markdown document with all derivations
        """
        specs = self.generate_all_derivations(protocol, estimands)

        lines = [
            "# ADaM DERIVATION SPECIFICATIONS",
            "",
            f"**Study:** {protocol.nct_id}",
            f"**Date:** Generated",
            "",
            "---",
            "",
            "## Overview",
            "",
            "This document contains detailed derivation specifications for all ADaM analysis datasets.",
            "These specifications are intended for statistical programmers implementing the analysis datasets.",
            "",
            "### Datasets Included",
            "",
            "| Dataset | Label | Structure |",
            "|---------|-------|-----------|",
        ]

        for name, spec in sorted(specs.items()):
            lines.append(f"| {name} | {spec.dataset_label} | {spec.structure} |")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Add each dataset specification
        for name in sorted(specs.keys()):
            spec = specs[name]
            lines.append(spec.to_markdown())
            lines.append("---")
            lines.append("")

        return "\n".join(lines)


# Factory function
def create_derivation_generator(llm_client=None) -> DerivationSpecGenerator:
    """Create a derivation specification generator"""
    return DerivationSpecGenerator(llm_client=llm_client)
