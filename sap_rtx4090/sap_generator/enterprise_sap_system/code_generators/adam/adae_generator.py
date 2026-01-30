#!/usr/bin/env python3
"""
ADAE (Adverse Events Analysis Dataset) Generator
==================================================

Generates production-ready SAS code for ADAE dataset.
ADAE is an occurrence data structure (OCCDS) containing one row per AE per subject.

Key variables generated:
- Treatment-Emergent: TRTEMFL
- Severity: AESEV, AESEVN
- Relationship: AEREL, AERELN, RELFL
- Dates: ASTDT, AENDT, AESTDY, AEENDY
- Outcomes: AEOUT, AEACN
- Serious: AESER, AESCAN, AESCONG, AESDISAB, AESDTH, AESHOSP, AESLIFE, AESMIE
"""

from typing import Any, Dict, List, Optional
from ..base import SASCodeGenerator


class ADAEGenerator(SASCodeGenerator):
    """
    Generates ADAE.sas program from protocol facts.

    ADAE is an occurrence data structure containing one row per adverse event.
    Merges with ADSL for subject-level information including treatment and population flags.
    """

    @property
    def program_name(self) -> str:
        return "adae.sas"

    @property
    def program_purpose(self) -> str:
        return "Create ADAE (Adverse Events Analysis Dataset)"

    def _get_fact(self, facts: Any, key: str, default: Any = None) -> Any:
        """Get a fact from either dict or object."""
        if isinstance(facts, dict):
            return facts.get(key, default)
        return getattr(facts, key, default)

    def generate(self, facts: Any) -> str:
        """
        Generate complete ADAE.sas program.

        Args:
            facts: FullProtocolFacts object or dictionary with protocol information

        Returns:
            Complete SAS program as string
        """
        # Extract key information (supports both dict and object)
        nct_id = self._get_fact(facts, 'nct_id', '') or self._get_fact(facts, 'protocol_id', '') or 'UNKNOWN'
        study_id = self._get_fact(facts, 'study_id', '') or nct_id
        drug_name = self._get_fact(facts, 'drug_name', '') or 'STUDY_DRUG'
        treatments = self._get_fact(facts, 'treatments', [])
        if treatments:
            arm_names = [t.get('name', t) if isinstance(t, dict) else t for t in treatments]
        else:
            arm_names = self._get_fact(facts, 'arm_names', []) or ['Treatment', 'Placebo']

        # Build program sections
        sections = []

        # 1. Header
        sections.append(self.generate_header(
            study_id=study_id,
            nct_id=nct_id,
            additional_info={
                'Drug': drug_name,
                'Structure': 'OCCDS (One record per AE per subject)',
                'Key Variables': 'TRTEMFL, AESEVN, AERELN'
            }
        ))

        # 2. Macro variables
        sections.append(self._generate_macro_variables(study_id, drug_name))

        # 3. Libnames
        sections.append(self.generate_libname_statements())

        # 4. Main data step
        sections.append(self._generate_main_data_step(arm_names))

        # 5. QC checks
        sections.append(self._generate_qc_section())

        # 6. Documentation
        sections.append(self.generate_proc_contents("adam.adae"))

        return "\n".join(sections)

    def _generate_macro_variables(self, study_id: str, drug_name: str) -> str:
        """Generate macro variable definitions"""

        return f"""
{self.generate_section_comment("Macro Variables", 1)}

%let STUDYID = {study_id};
%let DRUG = {drug_name};

/* Treatment-emergent window: AEs starting from first dose */
/* through 30 days (or study-specific window) after last dose */
%let TE_WINDOW = 30;  /* Days after last dose to consider TE */

/* Output paths */
%let outpath = /output/&STUDYID.;
"""

    def _generate_main_data_step(self, arm_names: List[str]) -> str:
        """Generate the main DATA step for ADAE"""

        return f"""
{self.generate_section_comment("ADAE Creation", 1)}

/* First, get required variables from ADSL */
proc sort data=adam.adsl out=adsl_ae(keep=
    USUBJID STUDYID SITEID
    TRTP TRTA TRTPN TRTAN
    TRTSDT TRTEDT
    SAFFL ITTFL
    AGE AGEGR1 SEX RACE
);
    by USUBJID;
run;

data adam.adae;
    merge sdtm.ae(in=a)
          adsl_ae(in=b);
    by USUBJID;
    if a and b;

{self.generate_section_comment("Variable Lengths", 2)}
    length
        ASTDT AENDT 8
        ASTDTF AENDTF $1
        AESTDY AEENDY 8
        TRTEMFL $1
        AESEVN 8
        AERELN 8
        RELFL $1
        AEOUTN 8
        AEACNN 8
        AOCCFL AOCCSFL AOCCPFL $1
        AOTEFFL AOTESFL AOTEPFL $1
        CQ01NAM $200
    ;

{self.generate_section_comment("Date Derivations", 2)}
    /* AE Start Date */
    if not missing(AESTDTC) then do;
        if length(AESTDTC) >= 10 then do;
            ASTDT = input(substr(AESTDTC, 1, 10), e8601da.);
            ASTDTF = '';
        end;
        else if length(AESTDTC) >= 7 then do;
            /* Partial date - impute to first of month */
            ASTDT = input(substr(AESTDTC, 1, 7) || '-01', e8601da.);
            ASTDTF = 'D';
        end;
        else if length(AESTDTC) >= 4 then do;
            /* Year only - impute to January 1 */
            ASTDT = input(substr(AESTDTC, 1, 4) || '-01-01', e8601da.);
            ASTDTF = 'M';
        end;
    end;

    /* AE End Date */
    if not missing(AEENDTC) then do;
        if length(AEENDTC) >= 10 then do;
            AENDT = input(substr(AEENDTC, 1, 10), e8601da.);
            AENDTF = '';
        end;
        else if length(AEENDTC) >= 7 then do;
            /* Partial date - impute to last of month */
            AENDT = intnx('month', input(substr(AEENDTC, 1, 7) || '-01', e8601da.), 0, 'E');
            AENDTF = 'D';
        end;
    end;

    /* Study days relative to first dose */
    if not missing(ASTDT) and not missing(TRTSDT) then do;
        if ASTDT >= TRTSDT then AESTDY = ASTDT - TRTSDT + 1;
        else AESTDY = ASTDT - TRTSDT;
    end;

    if not missing(AENDT) and not missing(TRTSDT) then do;
        if AENDT >= TRTSDT then AEENDY = AENDT - TRTSDT + 1;
        else AEENDY = AENDT - TRTSDT;
    end;

    /* AE Duration */
    if not missing(ASTDT) and not missing(AENDT) then
        AEDUR = AENDT - ASTDT + 1;

{self.generate_section_comment("Treatment-Emergent Flag", 2)}
    /* TRTEMFL: Treatment-Emergent AE Flag */
    /* Definition: AE with start date on or after first dose date */
    /*             and on or before last dose date + TE_WINDOW days */

    TRTEMFL = 'N';

    if not missing(ASTDT) and not missing(TRTSDT) then do;
        /* AE started on or after first dose */
        if ASTDT >= TRTSDT then do;
            /* Check if within window after last dose */
            if missing(TRTEDT) then
                TRTEMFL = 'Y';  /* No end date, consider all post-dose as TE */
            else if ASTDT <= TRTEDT + &TE_WINDOW then
                TRTEMFL = 'Y';
        end;

        /* Handle pre-existing AEs that worsen */
        /* If AE started before first dose but severity worsened after, may still be TE */
        /* Note: This logic would need AESTDTC vs. worsening date - simplified here */
    end;

{self.generate_section_comment("Severity Numeric", 2)}
    /* AESEVN: Severity Numeric */
    /* Standard CTCAE grades or Mild/Moderate/Severe */

    select(upcase(strip(AESEV)));
        when('MILD', '1', 'GRADE 1') AESEVN = 1;
        when('MODERATE', '2', 'GRADE 2') AESEVN = 2;
        when('SEVERE', '3', 'GRADE 3') AESEVN = 3;
        when('LIFE-THREATENING', 'LIFE THREATENING', '4', 'GRADE 4') AESEVN = 4;
        when('DEATH', 'FATAL', '5', 'GRADE 5') AESEVN = 5;
        otherwise AESEVN = .;
    end;

{self.generate_section_comment("Relationship to Treatment", 2)}
    /* AERELN: Causality Numeric */
    /* RELFL: Related Flag (for treatment-related summaries) */

    select(upcase(strip(AEREL)));
        when('NOT RELATED', 'UNRELATED', 'NONE') do;
            AERELN = 1;
            RELFL = 'N';
        end;
        when('UNLIKELY', 'UNLIKELY RELATED') do;
            AERELN = 2;
            RELFL = 'N';
        end;
        when('POSSIBLE', 'POSSIBLY RELATED') do;
            AERELN = 3;
            RELFL = 'Y';
        end;
        when('PROBABLE', 'PROBABLY RELATED') do;
            AERELN = 4;
            RELFL = 'Y';
        end;
        when('DEFINITE', 'DEFINITELY RELATED', 'RELATED', 'YES') do;
            AERELN = 5;
            RELFL = 'Y';
        end;
        otherwise do;
            AERELN = .;
            RELFL = '';
        end;
    end;

{self.generate_section_comment("Outcome and Action", 2)}
    /* AEOUTN: Outcome Numeric */
    select(upcase(strip(AEOUT)));
        when('RECOVERED/RESOLVED', 'RECOVERED', 'RESOLVED') AEOUTN = 1;
        when('RECOVERING/RESOLVING', 'RECOVERING', 'RESOLVING') AEOUTN = 2;
        when('NOT RECOVERED/NOT RESOLVED', 'NOT RECOVERED', 'NOT RESOLVED') AEOUTN = 3;
        when('RECOVERED/RESOLVED WITH SEQUELAE', 'RECOVERED WITH SEQUELAE') AEOUTN = 4;
        when('FATAL', 'DEATH') AEOUTN = 5;
        when('UNKNOWN') AEOUTN = 6;
        otherwise AEOUTN = .;
    end;

    /* AEACNN: Action Taken Numeric */
    select(upcase(strip(AEACN)));
        when('DRUG WITHDRAWN', 'WITHDRAWN') AEACNN = 1;
        when('DRUG INTERRUPTED', 'INTERRUPTED', 'DOSE REDUCED') AEACNN = 2;
        when('DOSE NOT CHANGED', 'NOT CHANGED', 'NONE') AEACNN = 3;
        when('DOSE INCREASED') AEACNN = 4;
        when('NOT APPLICABLE', 'N/A') AEACNN = 5;
        when('UNKNOWN') AEACNN = 6;
        otherwise AEACNN = .;
    end;

{self.generate_section_comment("Serious AE Flags", 2)}
    /* Convert SAE criteria to flags if not already done in SDTM */
    /* Standard serious criteria per ICH */

    /* Death */
    if upcase(AESDTH) = 'Y' then AESDTH = 'Y'; else AESDTH = 'N';

    /* Life-threatening */
    if upcase(AESLIFE) = 'Y' then AESLIFE = 'Y'; else AESLIFE = 'N';

    /* Hospitalization */
    if upcase(AESHOSP) = 'Y' then AESHOSP = 'Y'; else AESHOSP = 'N';

    /* Disability */
    if upcase(AESDISAB) = 'Y' then AESDISAB = 'Y'; else AESDISAB = 'N';

    /* Congenital anomaly */
    if upcase(AESCONG) = 'Y' then AESCONG = 'Y'; else AESCONG = 'N';

    /* Medically important */
    if upcase(AESMIE) = 'Y' then AESMIE = 'Y'; else AESMIE = 'N';

    /* Overall serious flag */
    if upcase(AESER) = 'Y' then AESER = 'Y'; else AESER = 'N';

{self.generate_section_comment("Occurrence Flags", 2)}
    /* AOCCFL: First occurrence of any AE */
    /* AOCCSFL: First occurrence within SOC */
    /* AOCCPFL: First occurrence within PT */
    /* These are set in a second pass below */

    AOCCFL = '';
    AOCCSFL = '';
    AOCCPFL = '';

    /* TE-specific occurrence flags */
    AOTEFFL = '';  /* First TE occurrence overall */
    AOTESFL = '';  /* First TE occurrence within SOC */
    AOTEPFL = '';  /* First TE occurrence within PT */

{self.generate_section_comment("Custom Query Variables", 2)}
    /* CQ01NAM: Custom query for AEs of special interest */
    /* Populate based on study-specific criteria */
    /* Examples: Infections, Injection site reactions, etc. */

    CQ01NAM = '';

    /* Example: Flag injection site reactions */
    if index(upcase(AEDECOD), 'INJECTION SITE') > 0 then
        CQ01NAM = 'Injection Site Reactions';

    /* Example: Flag infections */
    if index(upcase(AEBODSYS), 'INFECTION') > 0 then
        CQ01NAM = catx('; ', CQ01NAM, 'Infections');

{self.generate_section_comment("Labels", 2)}
    label
        ASTDT = "Analysis Start Date"
        AENDT = "Analysis End Date"
        ASTDTF = "Analysis Start Date Imputation Flag"
        AENDTF = "Analysis End Date Imputation Flag"
        AESTDY = "Analysis Start Relative Day"
        AEENDY = "Analysis End Relative Day"
        AEDUR = "AE Duration (days)"
        TRTEMFL = "Treatment-Emergent Flag"
        AESEVN = "Severity/Intensity (N)"
        AERELN = "Causality (N)"
        RELFL = "Treatment-Related Flag"
        AEOUTN = "Outcome (N)"
        AEACNN = "Action Taken with Study Treatment (N)"
        AOCCFL = "First Occurrence of Any AE Flag"
        AOCCSFL = "First Occurrence of SOC Flag"
        AOCCPFL = "First Occurrence of PT Flag"
        AOTEFFL = "First Occurrence of TE AE Flag"
        AOTESFL = "First Occurrence of TE SOC Flag"
        AOTEPFL = "First Occurrence of TE PT Flag"
        CQ01NAM = "Customized Query 01 Name"
    ;

    format ASTDT AENDT date9.;

run;

{self.generate_section_comment("Set Occurrence Flags", 1)}

/* Sort for occurrence flag derivation */
proc sort data=adam.adae;
    by USUBJID ASTDT AESTDY AESEQ;
run;

/* Set first occurrence flags */
data adam.adae;
    set adam.adae;
    by USUBJID;

    /* Retain flags for first occurrence tracking */
    retain _any_flag _soc_flag _pt_flag;
    retain _te_any _te_soc _te_pt;
    length _prev_soc _prev_pt $200;
    retain _prev_soc _prev_pt;

    if first.USUBJID then do;
        _any_flag = 0;
        _soc_flag = 0;
        _pt_flag = 0;
        _te_any = 0;
        _te_soc = 0;
        _te_pt = 0;
        _prev_soc = '';
        _prev_pt = '';
    end;

    /* First any AE */
    if _any_flag = 0 then do;
        AOCCFL = 'Y';
        _any_flag = 1;
    end;

    /* First occurrence within SOC */
    if AEBODSYS ne _prev_soc then do;
        AOCCSFL = 'Y';
        _prev_soc = AEBODSYS;
    end;

    /* First occurrence within PT */
    if AEDECOD ne _prev_pt then do;
        AOCCPFL = 'Y';
        _prev_pt = AEDECOD;
    end;

    /* TE-specific first occurrence flags */
    if TRTEMFL = 'Y' then do;
        if _te_any = 0 then do;
            AOTEFFL = 'Y';
            _te_any = 1;
        end;
    end;

    drop _any_flag _soc_flag _pt_flag _te_any _te_soc _te_pt _prev_soc _prev_pt;
run;

/* Final sort */
proc sort data=adam.adae;
    by USUBJID ASTDT AESEQ;
run;
"""

    def _generate_qc_section(self) -> str:
        """Generate QC frequency tables"""

        return f"""
{self.generate_section_comment("QC Checks", 1)}

/* Overall AE counts */
title "QC: Overall AE Counts by Treatment";
proc freq data=adam.adae;
    where SAFFL = 'Y';
    tables TRTA / missing;
    tables TRTEMFL * TRTA / missing nocol nopercent;
run;

/* TE AE by severity */
title "QC: Treatment-Emergent AEs by Severity";
proc freq data=adam.adae;
    where SAFFL = 'Y' and TRTEMFL = 'Y';
    tables AESEV * TRTA / missing nocol;
    tables AESEVN / missing;
run;

/* AE relationship */
title "QC: AE Relationship to Treatment";
proc freq data=adam.adae;
    where SAFFL = 'Y' and TRTEMFL = 'Y';
    tables AEREL * TRTA / missing nocol;
    tables RELFL * TRTA / missing nocol;
run;

/* Serious AEs */
title "QC: Serious Adverse Events";
proc freq data=adam.adae;
    where SAFFL = 'Y' and TRTEMFL = 'Y' and AESER = 'Y';
    tables AEBODSYS * TRTA / missing nocol;
run;

/* Check date derivations */
title "QC: Date Completeness";
proc freq data=adam.adae;
    tables ASTDTF AENDTF / missing;
run;

proc means data=adam.adae n mean std min max;
    where SAFFL = 'Y' and TRTEMFL = 'Y';
    var AESTDY AEENDY AEDUR;
run;

/* Top AEs by PT */
title "QC: Top 20 AEs by Preferred Term (TE AEs)";
proc freq data=adam.adae order=freq;
    where SAFFL = 'Y' and TRTEMFL = 'Y';
    tables AEDECOD / maxlevels=20;
run;

title;
"""
