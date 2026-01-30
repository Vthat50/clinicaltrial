#!/usr/bin/env python3
"""
ADEFF (Efficacy Analysis Dataset) Generator
=============================================

Generates production-ready SAS code for efficacy analysis dataset.
ADEFF is a BDS (Basic Data Structure) for efficacy endpoints.

Key variables generated:
- Response: AVAL, AVALC (numeric and character results)
- Baseline: BASE, BASEC, ABLFL
- Change: CHG, PCHG (change and percent change from baseline)
- Visits: AVISIT, AVISITN, ADT, ADY
- Analysis flags: ANL01FL, CRIT1, CRIT1FL
"""

from typing import Any, Dict, List, Optional
from ..base import SASCodeGenerator


class ADEFFGenerator(SASCodeGenerator):
    """
    Generates ADEFF.sas program from protocol facts.

    ADEFF contains efficacy data in BDS format with:
    - Primary endpoint response/remission
    - Secondary efficacy endpoints
    - Baseline and change calculations
    - Responder analyses
    """

    @property
    def program_name(self) -> str:
        return "adeff.sas"

    @property
    def program_purpose(self) -> str:
        return "Create ADEFF (Efficacy Analysis Dataset)"

    def _get_fact(self, facts: Any, key: str, default: Any = None) -> Any:
        """Get a fact from either dict or object."""
        if isinstance(facts, dict):
            return facts.get(key, default)
        return getattr(facts, key, default)

    def generate(self, facts: Any) -> str:
        """
        Generate complete ADEFF.sas program.

        Args:
            facts: FullProtocolFacts object or dictionary with protocol information

        Returns:
            Complete SAS program as string
        """
        # Extract key information (supports both dict and object)
        nct_id = self._get_fact(facts, 'nct_id', '') or self._get_fact(facts, 'protocol_id', '') or 'UNKNOWN'
        study_id = self._get_fact(facts, 'study_id', '') or nct_id
        drug_name = self._get_fact(facts, 'drug_name', '') or 'STUDY_DRUG'
        therapeutic_area = self._get_fact(facts, 'therapeutic_area', '') or ''

        primary_endpoint = self._get_fact(facts, 'primary_endpoint', '')
        if isinstance(primary_endpoint, dict):
            primary_endpoint = primary_endpoint.get('name', 'Primary Endpoint')
        primary_endpoint = primary_endpoint or 'Primary Endpoint'

        primary_timepoint = self._get_fact(facts, 'primary_timepoint', '')
        if isinstance(primary_timepoint, dict):
            primary_timepoint = primary_timepoint.get('visit', 'Week 12')
        primary_timepoint = primary_timepoint or 'Week 12'

        secondary_endpoints = self._get_fact(facts, 'secondary_endpoints', []) or []

        # Build program sections
        sections = []

        # 1. Header
        sections.append(self.generate_header(
            study_id=study_id,
            nct_id=nct_id,
            additional_info={
                'Drug': drug_name,
                'Structure': 'BDS (Basic Data Structure)',
                'Primary Endpoint': primary_endpoint[:60],
                'Primary Timepoint': primary_timepoint
            }
        ))

        # 2. Macro variables
        sections.append(self._generate_macro_variables(
            study_id, drug_name, primary_endpoint, primary_timepoint
        ))

        # 3. Libnames
        sections.append(self.generate_libname_statements())

        # 4. Main data step
        sections.append(self._generate_main_data_step(
            therapeutic_area, primary_endpoint, primary_timepoint, secondary_endpoints
        ))

        # 5. Responder derivation
        sections.append(self._generate_responder_derivation(primary_endpoint))

        # 6. QC checks
        sections.append(self._generate_qc_section(primary_timepoint))

        # 7. Documentation
        sections.append(self.generate_proc_contents("adam.adeff"))

        return "\n".join(sections)

    def _generate_macro_variables(
        self,
        study_id: str,
        drug_name: str,
        primary_endpoint: str,
        primary_timepoint: str
    ) -> str:
        """Generate macro variable definitions"""

        # Parse timepoint to get week number
        import re
        week_match = re.search(r'week\s*(\d+)', primary_timepoint, re.I)
        week_num = week_match.group(1) if week_match else '12'

        return f"""
{self.generate_section_comment("Macro Variables", 1)}

%let STUDYID = {study_id};
%let DRUG = {drug_name};
%let PRIMARY_ENDPOINT = {primary_endpoint[:50]};
%let PRIMARY_TIMEPOINT = {primary_timepoint};
%let PRIMARY_WEEK = {week_num};

/* Output paths */
%let outpath = /output/&STUDYID.;
"""

    def _generate_main_data_step(
        self,
        therapeutic_area: str,
        primary_endpoint: str,
        primary_timepoint: str,
        secondary_endpoints: List[str]
    ) -> str:
        """Generate the main DATA step for ADEFF"""

        ta = therapeutic_area.upper() if therapeutic_area else ""

        # Determine parameter structure based on therapeutic area
        if "IBD" in ta or "ULCERATIVE" in ta or "CROHN" in ta:
            param_section = self._generate_ibd_parameters()
        elif "RHEUM" in ta or "ARTHRITIS" in ta:
            param_section = self._generate_rheum_parameters()
        elif "ONCOL" in ta or "CANCER" in ta:
            param_section = self._generate_oncology_parameters()
        else:
            param_section = self._generate_generic_parameters(primary_endpoint)

        return f"""
{self.generate_section_comment("ADEFF Creation", 1)}

/* Get required variables from ADSL */
proc sort data=adam.adsl out=adsl_eff(keep=
    USUBJID STUDYID SITEID
    TRTP TRTA TRTPN TRTAN
    TRTSDT TRTEDT RANDDT
    ITTFL SAFFL FASFL PPROTFL
    AGE AGEGR1 SEX RACE
);
    by USUBJID;
run;

/* Source efficacy data - typically from QS (Questionnaires) domain */
/* Modify based on actual SDTM structure */

data efficacy_source;
    set sdtm.qs(where=(QSCAT in ('EFFICACY', 'PRIMARY', 'MAYO', 'CDAI', 'DAS28', 'ACR')));
    /* Keep relevant variables */
    keep USUBJID QSSEQ QSTESTCD QSTEST QSCAT QSSCAT QSORRES QSSTRESC QSSTRESN QSBLFL VISITNUM VISIT QSDTC;
run;

/* If QS domain not available, create placeholder structure */
/* This allows the program to run even without source data */
%macro check_source;
    %let dsid = %sysfunc(exist(efficacy_source));
    %if &dsid = 0 %then %do;
        data efficacy_source;
            length USUBJID $40 QSTESTCD $8 QSTEST $100 QSORRES $200 QSSTRESC $200;
            length QSSTRESN QSSEQ VISITNUM 8 VISIT $40 QSDTC $20 QSBLFL $1 QSCAT $40 QSSCAT $40;
            stop;
        run;
    %end;
%mend;
%check_source;

data adam.adeff;
    merge efficacy_source(in=a)
          adsl_eff(in=b);
    by USUBJID;
    if a and b;

{self.generate_section_comment("Variable Lengths", 2)}
    length
        PARAMCD $8
        PARAM $200
        PARCAT1 $40
        PARCAT2 $40
        AVAL 8
        AVALC $200
        BASE 8
        BASEC $200
        CHG 8
        PCHG 8
        AVISIT $40
        AVISITN 8
        ADT 8
        ADY 8
        ABLFL $1
        ANL01FL $1
        ANL02FL $1
        CRIT1 $200
        CRIT1FL $1
        DTYPE $20
    ;

{self.generate_section_comment("Parameter Mapping", 2)}
{param_section}

{self.generate_section_comment("Visit Mapping", 2)}
    /* Map visits to analysis visits */
    /* Modify mapping based on protocol visit schedule */

    select(upcase(strip(VISIT)));
        when('SCREENING', 'SCREEN') do;
            AVISIT = 'Screening';
            AVISITN = -1;
        end;
        when('BASELINE', 'DAY 1', 'WEEK 0') do;
            AVISIT = 'Baseline';
            AVISITN = 0;
        end;
        when('WEEK 2', 'DAY 14') do;
            AVISIT = 'Week 2';
            AVISITN = 2;
        end;
        when('WEEK 4', 'DAY 28') do;
            AVISIT = 'Week 4';
            AVISITN = 4;
        end;
        when('WEEK 6', 'DAY 42') do;
            AVISIT = 'Week 6';
            AVISITN = 6;
        end;
        when('WEEK 8', 'DAY 56') do;
            AVISIT = 'Week 8';
            AVISITN = 8;
        end;
        when('WEEK 10', 'DAY 70') do;
            AVISIT = 'Week 10';
            AVISITN = 10;
        end;
        when('WEEK 12', 'DAY 84') do;
            AVISIT = 'Week 12';
            AVISITN = 12;
        end;
        when('WEEK 14', 'DAY 98') do;
            AVISIT = 'Week 14';
            AVISITN = 14;
        end;
        when('WEEK 24', 'DAY 168') do;
            AVISIT = 'Week 24';
            AVISITN = 24;
        end;
        when('WEEK 52', 'DAY 364') do;
            AVISIT = 'Week 52';
            AVISITN = 52;
        end;
        when('END OF TREATMENT', 'EOT') do;
            AVISIT = 'End of Treatment';
            AVISITN = 98;
        end;
        when('FOLLOW-UP', 'SAFETY FOLLOW-UP') do;
            AVISIT = 'Follow-up';
            AVISITN = 99;
        end;
        otherwise do;
            /* Try to extract week number */
            if prxmatch('/WEEK\s*(\d+)/i', VISIT) then do;
                _wk = input(prxposn(prxparse('/WEEK\s*(\d+)/i'), 1, VISIT), best.);
                AVISIT = catx(' ', 'Week', _wk);
                AVISITN = _wk;
            end;
            else do;
                AVISIT = VISIT;
                AVISITN = VISITNUM;
            end;
        end;
    end;

{self.generate_section_comment("Date and Day Derivations", 2)}
    /* Analysis date */
    if not missing(QSDTC) and length(QSDTC) >= 10 then
        ADT = input(substr(QSDTC, 1, 10), e8601da.);

    /* Study day relative to first dose */
    if not missing(ADT) and not missing(TRTSDT) then do;
        if ADT >= TRTSDT then ADY = ADT - TRTSDT + 1;
        else ADY = ADT - TRTSDT;
    end;

{self.generate_section_comment("Analysis Values", 2)}
    /* Numeric value */
    if not missing(QSSTRESN) then AVAL = QSSTRESN;

    /* Character value */
    if not missing(QSSTRESC) then AVALC = strip(QSSTRESC);
    else if not missing(QSORRES) then AVALC = strip(QSORRES);

{self.generate_section_comment("Baseline Flag and Value", 2)}
    /* Baseline flag - typically last non-missing value before first dose */
    if upcase(QSBLFL) = 'Y' then ABLFL = 'Y';
    else if AVISITN = 0 then ABLFL = 'Y';  /* Fallback: use baseline visit */
    else ABLFL = '';

    /* Note: BASE and BASEC will be populated in second pass */

{self.generate_section_comment("Labels", 2)}
    label
        PARAMCD = "Parameter Code"
        PARAM = "Parameter"
        PARCAT1 = "Parameter Category 1"
        PARCAT2 = "Parameter Category 2"
        AVAL = "Analysis Value"
        AVALC = "Analysis Value (C)"
        BASE = "Baseline Value"
        BASEC = "Baseline Value (C)"
        CHG = "Change from Baseline"
        PCHG = "Percent Change from Baseline"
        AVISIT = "Analysis Visit"
        AVISITN = "Analysis Visit (N)"
        ADT = "Analysis Date"
        ADY = "Analysis Relative Day"
        ABLFL = "Baseline Record Flag"
        ANL01FL = "Analysis Record Flag 01"
        ANL02FL = "Analysis Record Flag 02"
        CRIT1 = "Analysis Criterion 1"
        CRIT1FL = "Criterion 1 Evaluation Result Flag"
        DTYPE = "Derivation Type"
    ;

    format ADT date9.;

    drop _:;
run;

{self.generate_section_comment("Derive Baseline and Change", 1)}

/* Get baseline values */
proc sort data=adam.adeff;
    by USUBJID PARAMCD AVISITN;
run;

data adam.adeff;
    set adam.adeff;
    by USUBJID PARAMCD;

    /* Retain baseline */
    retain _base _basec;
    length _basec $200;

    if first.PARAMCD then do;
        _base = .;
        _basec = '';
    end;

    /* Capture baseline */
    if ABLFL = 'Y' then do;
        _base = AVAL;
        _basec = AVALC;
    end;

    /* Assign baseline */
    BASE = _base;
    BASEC = _basec;

    /* Calculate change from baseline */
    if not missing(AVAL) and not missing(BASE) then do;
        CHG = AVAL - BASE;
        if BASE ne 0 then PCHG = ((AVAL - BASE) / BASE) * 100;
    end;

    drop _base _basec;
run;
"""

    def _generate_ibd_parameters(self) -> str:
        """Generate IBD-specific parameter mappings (UC/Crohn's)"""

        return """    /* IBD-Specific Parameters (Ulcerative Colitis / Crohn's Disease) */

    select(upcase(strip(QSTESTCD)));
        /* Mayo Score components */
        when('MAYO', 'MAYOTOT') do;
            PARAMCD = 'MAYOTOT';
            PARAM = 'Total Mayo Score';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'MAYO SCORE';
        end;
        when('MAYOSF', 'SFSUBSC') do;
            PARAMCD = 'MAYOSF';
            PARAM = 'Mayo Stool Frequency Subscore';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'MAYO SCORE';
        end;
        when('MAYORB', 'RBSUBSC') do;
            PARAMCD = 'MAYORB';
            PARAM = 'Mayo Rectal Bleeding Subscore';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'MAYO SCORE';
        end;
        when('MAYOEND', 'ENDOSC') do;
            PARAMCD = 'MAYOEND';
            PARAM = 'Mayo Endoscopic Subscore';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'MAYO SCORE';
        end;
        when('MAYOPGA', 'PGASUBC') do;
            PARAMCD = 'MAYOPGA';
            PARAM = 'Mayo Physician Global Assessment';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'MAYO SCORE';
        end;

        /* Modified Mayo (without PGA) */
        when('MMAYO') do;
            PARAMCD = 'MMAYO';
            PARAM = 'Modified Mayo Score (9-point)';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'MAYO SCORE';
        end;

        /* Partial Mayo (without endoscopy) */
        when('PMAYO') do;
            PARAMCD = 'PMAYO';
            PARAM = 'Partial Mayo Score';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'MAYO SCORE';
        end;

        /* Response/Remission (binary) */
        when('CLINREM') do;
            PARAMCD = 'CLINREM';
            PARAM = 'Clinical Remission';
            PARCAT1 = 'RESPONDER';
            PARCAT2 = 'PRIMARY';
        end;
        when('CLINRSP') do;
            PARAMCD = 'CLINRSP';
            PARAM = 'Clinical Response';
            PARCAT1 = 'RESPONDER';
            PARCAT2 = 'SECONDARY';
        end;
        when('ENDOIMP') do;
            PARAMCD = 'ENDOIMP';
            PARAM = 'Endoscopic Improvement';
            PARCAT1 = 'RESPONDER';
            PARCAT2 = 'SECONDARY';
        end;
        when('ENDOREM') do;
            PARAMCD = 'ENDOREM';
            PARAM = 'Endoscopic Remission';
            PARCAT1 = 'RESPONDER';
            PARCAT2 = 'SECONDARY';
        end;
        when('MUHEAL') do;
            PARAMCD = 'MUHEAL';
            PARAM = 'Mucosal Healing';
            PARCAT1 = 'RESPONDER';
            PARCAT2 = 'SECONDARY';
        end;

        otherwise do;
            PARAMCD = substr(QSTESTCD, 1, 8);
            PARAM = QSTEST;
            PARCAT1 = 'EFFICACY';
            PARCAT2 = '';
        end;
    end;
"""

    def _generate_rheum_parameters(self) -> str:
        """Generate Rheumatology-specific parameter mappings (RA)"""

        return """    /* Rheumatology-Specific Parameters (Rheumatoid Arthritis) */

    select(upcase(strip(QSTESTCD)));
        /* ACR response criteria */
        when('ACR20') do;
            PARAMCD = 'ACR20';
            PARAM = 'ACR20 Response';
            PARCAT1 = 'RESPONDER';
            PARCAT2 = 'ACR';
        end;
        when('ACR50') do;
            PARAMCD = 'ACR50';
            PARAM = 'ACR50 Response';
            PARCAT1 = 'RESPONDER';
            PARCAT2 = 'ACR';
        end;
        when('ACR70') do;
            PARAMCD = 'ACR70';
            PARAM = 'ACR70 Response';
            PARCAT1 = 'RESPONDER';
            PARCAT2 = 'ACR';
        end;

        /* DAS28 score */
        when('DAS28', 'DAS28CRP') do;
            PARAMCD = 'DAS28';
            PARAM = 'DAS28-CRP Score';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'DISEASE ACTIVITY';
        end;
        when('DAS28ESR') do;
            PARAMCD = 'DAS28ESR';
            PARAM = 'DAS28-ESR Score';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'DISEASE ACTIVITY';
        end;

        /* Joint counts */
        when('TJC28', 'TJC') do;
            PARAMCD = 'TJC28';
            PARAM = 'Tender Joint Count (28 joints)';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'JOINT ASSESSMENT';
        end;
        when('SJC28', 'SJC') do;
            PARAMCD = 'SJC28';
            PARAM = 'Swollen Joint Count (28 joints)';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'JOINT ASSESSMENT';
        end;

        /* Other efficacy measures */
        when('HAQ', 'HAQDI') do;
            PARAMCD = 'HAQDI';
            PARAM = 'HAQ-DI Score';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'FUNCTION';
        end;
        when('CDAI') do;
            PARAMCD = 'CDAI';
            PARAM = 'Clinical Disease Activity Index';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'DISEASE ACTIVITY';
        end;
        when('SDAI') do;
            PARAMCD = 'SDAI';
            PARAM = 'Simplified Disease Activity Index';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'DISEASE ACTIVITY';
        end;

        otherwise do;
            PARAMCD = substr(QSTESTCD, 1, 8);
            PARAM = QSTEST;
            PARCAT1 = 'EFFICACY';
            PARCAT2 = '';
        end;
    end;
"""

    def _generate_oncology_parameters(self) -> str:
        """Generate Oncology-specific parameter mappings"""

        return """    /* Oncology-Specific Parameters */

    select(upcase(strip(QSTESTCD)));
        /* RECIST response */
        when('BOR', 'BESTRESP') do;
            PARAMCD = 'BOR';
            PARAM = 'Best Overall Response';
            PARCAT1 = 'RESPONDER';
            PARCAT2 = 'RECIST';
        end;
        when('ORR') do;
            PARAMCD = 'ORR';
            PARAM = 'Objective Response Rate';
            PARCAT1 = 'RESPONDER';
            PARCAT2 = 'RECIST';
        end;
        when('DCR') do;
            PARAMCD = 'DCR';
            PARAM = 'Disease Control Rate';
            PARCAT1 = 'RESPONDER';
            PARCAT2 = 'RECIST';
        end;
        when('CR') do;
            PARAMCD = 'CR';
            PARAM = 'Complete Response';
            PARCAT1 = 'RESPONDER';
            PARCAT2 = 'RECIST';
        end;
        when('PR') do;
            PARAMCD = 'PR';
            PARAM = 'Partial Response';
            PARCAT1 = 'RESPONDER';
            PARCAT2 = 'RECIST';
        end;

        /* Tumor measurements */
        when('TUMSIZE', 'SLD') do;
            PARAMCD = 'SLD';
            PARAM = 'Sum of Longest Diameters';
            PARCAT1 = 'EFFICACY';
            PARCAT2 = 'TUMOR';
        end;

        otherwise do;
            PARAMCD = substr(QSTESTCD, 1, 8);
            PARAM = QSTEST;
            PARCAT1 = 'EFFICACY';
            PARCAT2 = '';
        end;
    end;
"""

    def _generate_generic_parameters(self, primary_endpoint: str) -> str:
        """Generate generic parameter mappings"""

        return f"""    /* Generic Parameter Mapping */
    /* Primary endpoint: {primary_endpoint} */

    if not missing(QSTESTCD) then do;
        PARAMCD = substr(upcase(strip(QSTESTCD)), 1, 8);
        PARAM = coalescec(QSTEST, QSTESTCD);
        PARCAT1 = coalescec(QSCAT, 'EFFICACY');
        PARCAT2 = QSSCAT;
    end;
    else do;
        PARAMCD = 'PARAM1';
        PARAM = 'Efficacy Endpoint';
        PARCAT1 = 'EFFICACY';
        PARCAT2 = '';
    end;
"""

    def _generate_responder_derivation(self, primary_endpoint: str) -> str:
        """Generate responder/criterion flag derivation"""

        return f"""
{self.generate_section_comment("Responder Analysis Flags", 1)}

/* Define response criteria and derive responder flags */
data adam.adeff;
    set adam.adeff;

    /* Primary analysis record flag */
    /* ANL01FL: Records included in primary analysis */
    /* Typically: Post-baseline records at scheduled visits for primary population */

    if FASFL = 'Y' and AVISITN > 0 and not missing(AVAL) then ANL01FL = 'Y';
    else ANL01FL = '';

    /* Secondary analysis flag */
    if ITTFL = 'Y' and AVISITN > 0 and not missing(AVAL) then ANL02FL = 'Y';
    else ANL02FL = '';

    /* Criterion 1: Primary responder definition */
    /* Modify based on protocol-specific response criteria */
    /* Example for IBD: Clinical remission = Mayo score <=2, no subscore >1 */

    CRIT1 = '';
    CRIT1FL = '';

    if PARCAT1 = 'RESPONDER' then do;
        /* For binary response parameters, AVAL typically = 1 (responder) or 0 (non-responder) */
        if AVAL = 1 then do;
            CRIT1 = "Responder per protocol criteria";
            CRIT1FL = 'Y';
        end;
        else if AVAL = 0 then do;
            CRIT1 = "Non-responder";
            CRIT1FL = 'N';
        end;
    end;

    /* For continuous endpoints, can derive responder based on threshold */
    /* Example: CHG <= -3 for Mayo score improvement */
    /*
    if PARAMCD = 'MAYOTOT' and not missing(CHG) then do;
        if CHG <= -3 then do;
            CRIT1 = 'Mayo score decrease >= 3 points';
            CRIT1FL = 'Y';
        end;
        else do;
            CRIT1 = 'Mayo score decrease < 3 points';
            CRIT1FL = 'N';
        end;
    end;
    */

run;
"""

    def _generate_qc_section(self, primary_timepoint: str) -> str:
        """Generate QC frequency tables"""

        return f"""
{self.generate_section_comment("QC Checks", 1)}

/* Parameter summary */
title "QC: ADEFF Parameter Summary";
proc freq data=adam.adeff;
    tables PARAMCD * PARAM / list missing;
    tables PARCAT1 * PARCAT2 / list missing;
run;

/* Visit structure */
title "QC: Visit Structure";
proc freq data=adam.adeff;
    tables AVISIT * AVISITN / list missing;
run;

/* Baseline completeness */
title "QC: Baseline Flag Distribution";
proc freq data=adam.adeff;
    tables ABLFL * PARAMCD / missing;
run;

/* Analysis flags */
title "QC: Analysis Population Flags";
proc freq data=adam.adeff;
    tables ANL01FL * FASFL / missing;
    tables ANL02FL * ITTFL / missing;
run;

/* Primary endpoint at primary timepoint */
title "QC: Primary Endpoint Summary at {primary_timepoint}";
proc freq data=adam.adeff;
    where PARCAT2 = 'PRIMARY' and AVISIT = "{primary_timepoint}" and ANL01FL = 'Y';
    tables CRIT1FL * TRTA / missing;
run;

/* Change from baseline */
title "QC: Change from Baseline Summary";
proc means data=adam.adeff n mean std median min max;
    where ANL01FL = 'Y' and not missing(CHG);
    class PARAMCD AVISIT TRTA;
    var BASE AVAL CHG PCHG;
run;

/* Responder rates by treatment */
title "QC: Responder Rates by Treatment";
proc freq data=adam.adeff;
    where PARCAT1 = 'RESPONDER' and ANL01FL = 'Y';
    tables PARAMCD * AVISIT * TRTA * CRIT1FL / list missing;
run;

title;
"""
