#!/usr/bin/env python3
"""
ADSL (Subject-Level Analysis Dataset) Generator
=================================================

Generates production-ready SAS code for ADSL dataset.
ADSL is the foundation dataset that all other ADaM datasets merge with.

Key variables generated:
- Treatment: TRTP, TRTA, TRTPN, TRTAN
- Population flags: ITTFL, SAFFL, FASFL, PPROTFL
- Dates: TRTSDT, TRTEDT, RANDDT
- Stratification: Study-specific strat variables
- Demographics: AGEGR1, AGEGR1N, BMIBL, BMIGR1
"""

from typing import Any, Dict, List, Optional
from ..base import SASCodeGenerator


class ADSLGenerator(SASCodeGenerator):
    """
    Generates ADSL.sas program from protocol facts.

    ADSL contains one row per subject and includes:
    - Subject identifiers
    - Treatment information
    - Population flags
    - Demographic variables
    - Baseline characteristics
    - Stratification factors
    """

    @property
    def program_name(self) -> str:
        return "adsl.sas"

    @property
    def program_purpose(self) -> str:
        return "Create ADSL (Subject-Level Analysis Dataset)"

    def generate(self, facts: Any) -> str:
        """
        Generate complete ADSL.sas program.

        Args:
            facts: FullProtocolFacts object with extracted protocol information

        Returns:
            Complete SAS program as string
        """
        # Extract key information from facts
        nct_id = getattr(facts, 'nct_id', '') or 'UNKNOWN'
        study_id = getattr(facts, 'study_id', '') or nct_id
        drug_name = getattr(facts, 'drug_name', '') or 'STUDY_DRUG'
        indication = getattr(facts, 'indication', '') or 'Target Indication'
        therapeutic_area = getattr(facts, 'therapeutic_area', '') or 'Not Specified'

        # Treatment arms
        arm_names = getattr(facts, 'arm_names', []) or ['Treatment', 'Placebo']
        arm_doses = getattr(facts, 'arm_doses', []) or []
        num_arms = getattr(facts, 'num_arms', len(arm_names)) or 2
        ratio = getattr(facts, 'ratio', '1:1') or '1:1'

        # Sample size
        total_n = getattr(facts, 'total_n', 100) or 100

        # Stratification
        strat_factors = getattr(facts, 'stratification_factors', []) or []

        # Population definitions
        itt_def = getattr(facts, 'itt_definition', 'All randomized patients') or 'All randomized patients'
        safety_def = getattr(facts, 'safety_definition', 'All patients who received at least one dose') or 'All patients who received at least one dose'
        fas_def = 'All randomized patients who received at least one dose and have at least one post-baseline efficacy assessment'

        # Validate required fields
        self.validate_required_facts(facts, ['drug_name', 'arm_names', 'total_n'])

        # Build program sections
        sections = []

        # 1. Header
        sections.append(self.generate_header(
            study_id=study_id,
            nct_id=nct_id,
            additional_info={
                'Drug': drug_name,
                'Indication': indication,
                'Arms': ', '.join(arm_names),
                'Planned N': str(total_n),
                'Ratio': ratio
            }
        ))

        # 2. Macro variables
        sections.append(self._generate_macro_variables(
            study_id=study_id,
            drug_name=drug_name,
            arm_names=arm_names,
            total_n=total_n
        ))

        # 3. Libnames
        sections.append(self.generate_libname_statements())

        # 4. Main data step
        sections.append(self._generate_main_data_step(
            arm_names=arm_names,
            arm_doses=arm_doses,
            strat_factors=strat_factors,
            itt_def=itt_def,
            safety_def=safety_def,
            fas_def=fas_def,
            therapeutic_area=therapeutic_area
        ))

        # 5. QC checks
        sections.append(self._generate_qc_section(arm_names, total_n))

        # 6. Documentation
        sections.append(self.generate_proc_contents("adam.adsl"))

        return "\n".join(sections)

    def _generate_macro_variables(
        self,
        study_id: str,
        drug_name: str,
        arm_names: List[str],
        total_n: int
    ) -> str:
        """Generate macro variable definitions"""

        arm_list = ", ".join(f'"{arm}"' for arm in arm_names)

        return f"""
{self.generate_section_comment("Macro Variables", 1)}

%let STUDYID = {study_id};
%let DRUG = {drug_name};
%let N_PLANNED = {total_n};
%let N_ARMS = {len(arm_names)};

/* Treatment arm labels */
%let ARM1 = {arm_names[0] if len(arm_names) > 0 else 'Treatment A'};
%let ARM2 = {arm_names[1] if len(arm_names) > 1 else 'Treatment B'};
%let ARM3 = {arm_names[2] if len(arm_names) > 2 else 'Placebo'};

/* Output paths - modify as needed */
%let outpath = /output/&STUDYID.;
"""

    def _generate_main_data_step(
        self,
        arm_names: List[str],
        arm_doses: List[str],
        strat_factors: List[str],
        itt_def: str,
        safety_def: str,
        fas_def: str,
        therapeutic_area: str
    ) -> str:
        """Generate the main DATA step for ADSL"""

        # Build treatment assignment logic
        trt_assignment = self._build_treatment_assignment(arm_names, arm_doses)

        # Build stratification variable derivations
        strat_derivation = self._build_stratification_derivation(strat_factors)

        # Build therapeutic area specific variables
        ta_specific = self._build_ta_specific_vars(therapeutic_area)

        return f"""
{self.generate_section_comment("ADSL Creation", 1)}

data adam.adsl;
    set sdtm.dm;

{self.generate_section_comment("Variable Lengths", 2)}
    length
        STUDYID $20
        USUBJID $40
        SUBJID $20
        SITEID $10
        TRTP TRTA $60
        TRTPN TRTAN 8
        ITTFL SAFFL FASFL PPROTFL $1
        RANDFL ENRLFL COMPLFL $1
        AGEGR1 $20
        AGEGR1N 8
        RACEN SEXN 8
    ;

{self.generate_section_comment("Subject Identifiers", 2)}
    /* Subject identifiers from DM */
    STUDYID = strip(STUDYID);
    USUBJID = strip(USUBJID);
    SUBJID = strip(SUBJID);
    SITEID = strip(SITEID);

{self.generate_section_comment("Treatment Variables", 2)}
    /* Treatment assignment per protocol */
    /* Arms: {', '.join(arm_names)} */
{trt_assignment}

{self.generate_section_comment("Date Variables", 2)}
    /* Key dates */
    /* TRTSDT: First date of study treatment */
    if not missing(RFXSTDTC) then do;
        if length(RFXSTDTC) >= 10 then
            TRTSDT = input(substr(RFXSTDTC, 1, 10), e8601da.);
    end;

    /* TRTEDT: Last date of study treatment */
    if not missing(RFXENDTC) then do;
        if length(RFXENDTC) >= 10 then
            TRTEDT = input(substr(RFXENDTC, 1, 10), e8601da.);
    end;

    /* RANDDT: Randomization date */
    if not missing(RFSTDTC) then do;
        if length(RFSTDTC) >= 10 then
            RANDDT = input(substr(RFSTDTC, 1, 10), e8601da.);
    end;

    /* Treatment duration */
    if not missing(TRTSDT) and not missing(TRTEDT) then
        TRTDUR = TRTEDT - TRTSDT + 1;

{self.generate_section_comment("Population Flags", 2)}
    /* ITT: {itt_def} */
    if not missing(ARM) then ITTFL = 'Y';
    else ITTFL = 'N';

    /* Randomized flag */
    RANDFL = ITTFL;

    /* Safety: {safety_def} */
    if not missing(TRTSDT) then SAFFL = 'Y';
    else SAFFL = 'N';

    /* FAS: {fas_def} */
    /* Note: Post-baseline assessment flag would come from efficacy domain */
    /* For now, set equal to SAFFL - update when merging with efficacy data */
    FASFL = SAFFL;

    /* Per-Protocol: Modify based on protocol deviation criteria */
    /* Default: All FAS patients without major protocol deviations */
    PPROTFL = FASFL;

    /* Enrolled flag */
    ENRLFL = 'Y';

    /* Completed flag - would come from DS domain */
    /* Placeholder - update when merging disposition */
    COMPLFL = '';

{self.generate_section_comment("Demographic Derivations", 2)}
    /* Age at randomization (or screening if no randomization date) */
    /* AGE should come from DM */

    /* Age group */
    if AGE ne . then do;
        if AGE < 18 then do;
            AGEGR1 = '<18';
            AGEGR1N = 1;
        end;
        else if AGE < 65 then do;
            AGEGR1 = '18 to <65';
            AGEGR1N = 2;
        end;
        else do;
            AGEGR1 = '>=65';
            AGEGR1N = 3;
        end;
    end;

    /* Sex numeric */
    select(upcase(SEX));
        when('M', 'MALE') SEXN = 1;
        when('F', 'FEMALE') SEXN = 2;
        otherwise SEXN = 99;
    end;

    /* Race numeric */
    select(upcase(RACE));
        when('WHITE') RACEN = 1;
        when('BLACK OR AFRICAN AMERICAN') RACEN = 2;
        when('ASIAN') RACEN = 3;
        when('AMERICAN INDIAN OR ALASKA NATIVE') RACEN = 4;
        when('NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER') RACEN = 5;
        when('MULTIPLE') RACEN = 6;
        otherwise RACEN = 99;
    end;

{self.generate_section_comment("Stratification Variables", 2)}
{strat_derivation}

{self.generate_section_comment("Therapeutic Area Specific Variables", 2)}
{ta_specific}

{self.generate_section_comment("Labels", 2)}
    label
        STUDYID = "Study Identifier"
        USUBJID = "Unique Subject Identifier"
        SUBJID = "Subject Identifier for the Study"
        SITEID = "Study Site Identifier"
        TRTP = "Planned Treatment"
        TRTA = "Actual Treatment"
        TRTPN = "Planned Treatment (N)"
        TRTAN = "Actual Treatment (N)"
        TRTSDT = "Date of First Exposure to Treatment"
        TRTEDT = "Date of Last Exposure to Treatment"
        RANDDT = "Date of Randomization"
        TRTDUR = "Treatment Duration (days)"
        ITTFL = "Intent-to-Treat Population Flag"
        SAFFL = "Safety Population Flag"
        FASFL = "Full Analysis Set Population Flag"
        PPROTFL = "Per-Protocol Population Flag"
        RANDFL = "Randomized Population Flag"
        ENRLFL = "Enrolled Population Flag"
        COMPLFL = "Completed Study Flag"
        AGEGR1 = "Age Group 1"
        AGEGR1N = "Age Group 1 (N)"
        SEXN = "Sex (N)"
        RACEN = "Race (N)"
    ;

    format TRTSDT TRTEDT RANDDT date9.;

run;

/* Sort by subject */
proc sort data=adam.adsl;
    by USUBJID;
run;
"""

    def _build_treatment_assignment(self, arm_names: List[str], arm_doses: List[str]) -> str:
        """Build treatment variable assignment logic"""

        lines = []
        lines.append("    /* Map treatment from DM.ARM to analysis variables */")
        lines.append("    TRTP = strip(ARM);")
        lines.append("    TRTA = strip(ACTARM);")
        lines.append("")
        lines.append("    /* Numeric treatment coding for analysis */")
        lines.append("    select(upcase(strip(ARM)));")

        for i, arm in enumerate(arm_names, 1):
            # Handle both exact match and pattern matching
            arm_upper = arm.upper()
            lines.append(f"        when('{arm_upper}') TRTPN = {i};")

        lines.append("        otherwise TRTPN = 99;")
        lines.append("    end;")
        lines.append("")
        lines.append("    /* Actual treatment numeric - same logic */")
        lines.append("    select(upcase(strip(ACTARM)));")

        for i, arm in enumerate(arm_names, 1):
            arm_upper = arm.upper()
            lines.append(f"        when('{arm_upper}') TRTAN = {i};")

        lines.append("        otherwise TRTAN = 99;")
        lines.append("    end;")

        # Add dose information if available
        if arm_doses and any(arm_doses):
            lines.append("")
            lines.append("    /* Dose information from protocol */")
            for i, (arm, dose) in enumerate(zip(arm_names, arm_doses), 1):
                if dose:
                    lines.append(f"    /* Arm {i} ({arm}): {dose} */")

        return "\n".join(lines)

    def _build_stratification_derivation(self, strat_factors: List[str]) -> str:
        """Build stratification variable derivations"""

        if not strat_factors:
            return """    /* No stratification factors specified in protocol */
    /* Add stratification variable derivations here when available */
    /* Example:
    if STRATUM1 = '...' then APTS001 = 1;
    else APTS001 = 2;
    */"""

        lines = []
        lines.append(f"    /* Stratification factors from protocol: {', '.join(strat_factors)} */")
        lines.append("")

        for i, factor in enumerate(strat_factors, 1):
            var_name = f"APTS{i:03d}"
            safe_factor = self.sanitize_var_name(factor)[:20]

            lines.append(f"    /* Stratification {i}: {factor} */")
            lines.append(f"    /* Source: Protocol stratification factor */")
            lines.append(f"    /* Derivation: Map from randomization strata */")
            lines.append(f"    /* {var_name} = <derive from SDTM or IRT data>; */")
            lines.append(f"    {var_name} = .;  /* Placeholder - update with actual mapping */")
            lines.append(f"    {var_name}C = '';  /* Character version */")
            lines.append("")
            lines.append(f"    label {var_name} = 'Stratification Factor {i} ({factor[:30]})'")
            lines.append(f"          {var_name}C = 'Stratification Factor {i} ({factor[:30]}) (C)';")
            lines.append("")

        return "\n".join(lines)

    def _build_ta_specific_vars(self, therapeutic_area: str) -> str:
        """Build therapeutic area specific variable derivations"""

        ta = therapeutic_area.upper() if therapeutic_area else ""

        if "IBD" in ta or "ULCERATIVE" in ta or "CROHN" in ta:
            return self._build_ibd_vars()
        elif "ONCOL" in ta or "CANCER" in ta:
            return self._build_oncology_vars()
        elif "RHEUM" in ta or "ARTHRITIS" in ta:
            return self._build_rheumatology_vars()
        elif "CARDIO" in ta or "CV" in ta:
            return self._build_cardiovascular_vars()
        else:
            return """    /* Standard baseline variables */
    /* Add therapeutic area-specific derivations as needed */
    /* Baseline values would typically come from VS, LB, or other SDTM domains */
"""

    def _build_ibd_vars(self) -> str:
        """IBD-specific variables (UC, Crohn's)"""
        return """    /* IBD-Specific Baseline Variables */
    /* These would typically come from QS domain with Mayo Score or CDAI */

    /* Baseline Mayo Score (UC) - placeholder */
    /* MAYOBL = <derive from baseline Mayo score assessment>; */
    MAYOBL = .;

    /* Baseline Endoscopic Subscore */
    /* ENDOSBL = <derive from baseline endoscopy>; */
    ENDOSBL = .;

    /* Prior Anti-TNF exposure - common stratification factor */
    /* ATNTFFL = <derive from medical history>; */
    ATNTFFL = '';

    /* Prior biologic failure */
    /* BIOFAFL = <derive from medical history>; */
    BIOFAFL = '';

    /* Disease duration */
    /* DISDRBL = <derive from medical history>; */
    DISDRBL = .;

    /* Corticosteroid use at baseline */
    /* CORTBL = <derive from CM domain>; */
    CORTBL = '';

    label
        MAYOBL = "Baseline Mayo Score"
        ENDOSBL = "Baseline Endoscopic Subscore"
        ATNTFFL = "Prior Anti-TNF Exposure Flag"
        BIOFAFL = "Prior Biologic Failure Flag"
        DISDRBL = "Disease Duration at Baseline (years)"
        CORTBL = "Corticosteroid Use at Baseline"
    ;
"""

    def _build_oncology_vars(self) -> str:
        """Oncology-specific variables"""
        return """    /* Oncology-Specific Baseline Variables */

    /* ECOG Performance Status at baseline */
    /* ECOGBL = <derive from QS domain>; */
    ECOGBL = .;

    /* Number of prior therapies */
    /* NPRTHER = <derive from medical history>; */
    NPRTHER = .;

    /* Disease stage */
    /* DSSTAGE = <derive from baseline assessment>; */
    DSSTAGE = '';

    /* Measurable disease flag */
    /* MEASFL = <derive from tumor assessments>; */
    MEASFL = '';

    /* Biomarker status (e.g., PD-L1, HER2) */
    /* BIOMMFL = <derive from central lab>; */
    BIOMMFL = '';

    label
        ECOGBL = "Baseline ECOG Performance Status"
        NPRTHER = "Number of Prior Therapies"
        DSSTAGE = "Disease Stage at Baseline"
        MEASFL = "Measurable Disease at Baseline Flag"
        BIOMMFL = "Biomarker Positive Flag"
    ;
"""

    def _build_rheumatology_vars(self) -> str:
        """Rheumatology-specific variables (RA)"""
        return """    /* Rheumatology-Specific Baseline Variables */

    /* Baseline DAS28 */
    /* DAS28BL = <derive from efficacy assessments>; */
    DAS28BL = .;

    /* Baseline tender joint count */
    /* TJC28BL = <derive from efficacy assessments>; */
    TJC28BL = .;

    /* Baseline swollen joint count */
    /* SJC28BL = <derive from efficacy assessments>; */
    SJC28BL = .;

    /* RF positive flag */
    /* RFPOSFL = <derive from central lab>; */
    RFPOSFL = '';

    /* Anti-CCP positive flag */
    /* ACCPFL = <derive from central lab>; */
    ACCPFL = '';

    /* Prior DMARD count */
    /* NDMARD = <derive from medical history>; */
    NDMARD = .;

    label
        DAS28BL = "Baseline DAS28-CRP Score"
        TJC28BL = "Baseline Tender Joint Count (28)"
        SJC28BL = "Baseline Swollen Joint Count (28)"
        RFPOSFL = "Rheumatoid Factor Positive Flag"
        ACCPFL = "Anti-CCP Positive Flag"
        NDMARD = "Number of Prior DMARDs"
    ;
"""

    def _build_cardiovascular_vars(self) -> str:
        """Cardiovascular-specific variables"""
        return """    /* Cardiovascular-Specific Baseline Variables */

    /* Baseline ejection fraction */
    /* LVEFBL = <derive from ECHO assessments>; */
    LVEFBL = .;

    /* NYHA class at baseline */
    /* NYHABL = <derive from assessments>; */
    NYHABL = .;

    /* Baseline systolic BP */
    /* SYSBPBL = <derive from VS domain>; */
    SYSBPBL = .;

    /* Baseline diastolic BP */
    /* DIABPBL = <derive from VS domain>; */
    DIABPBL = .;

    /* Prior MI flag */
    /* PRIMIFL = <derive from medical history>; */
    PRIMIFL = '';

    /* Diabetes flag */
    /* DIABFL = <derive from medical history>; */
    DIABFL = '';

    label
        LVEFBL = "Baseline Left Ventricular Ejection Fraction (%)"
        NYHABL = "Baseline NYHA Functional Class"
        SYSBPBL = "Baseline Systolic Blood Pressure (mmHg)"
        DIABPBL = "Baseline Diastolic Blood Pressure (mmHg)"
        PRIMIFL = "Prior Myocardial Infarction Flag"
        DIABFL = "Diabetes History Flag"
    ;
"""

    def _generate_qc_section(self, arm_names: List[str], total_n: int) -> str:
        """Generate QC frequency tables"""

        return f"""
{self.generate_section_comment("QC Checks", 1)}

/* Verify treatment arm counts */
title "QC: Treatment Arm Distribution";
title2 "Expected: ~{total_n} total across {len(arm_names)} arms";
proc freq data=adam.adsl;
    tables TRTP TRTA / missing;
    tables TRTPN TRTAN / missing;
run;

/* Verify population flags */
title "QC: Population Flag Summary";
proc freq data=adam.adsl;
    tables ITTFL SAFFL FASFL PPROTFL / missing;
    tables ITTFL * SAFFL * FASFL / list missing;
run;

/* Check treatment date completeness */
title "QC: Key Date Completeness";
proc freq data=adam.adsl;
    tables (TRTSDT TRTEDT RANDDT) * SAFFL / missing norow nocol nopercent;
run;

/* Demographics summary */
title "QC: Demographics Overview";
proc freq data=adam.adsl;
    tables AGEGR1 SEX RACE / missing;
    tables AGEGR1 * TRTP / missing;
run;

proc means data=adam.adsl n mean std min max;
    class TRTP;
    var AGE TRTDUR;
run;

title;
"""
