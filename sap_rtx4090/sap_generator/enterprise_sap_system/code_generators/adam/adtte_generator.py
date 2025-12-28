#!/usr/bin/env python3
"""
ADTTE (Time-to-Event Analysis Dataset) Generator
==================================================

Generates production-ready SAS code for ADTTE dataset.
ADTTE is a BDS (Basic Data Structure) for time-to-event analyses.

Key variables generated:
- Time: AVAL (time to event in days), AVALU
- Censoring: CNSR (0=event, 1=censored), EVNTDESC
- Dates: STARTDT, ADT (event/censor date)
- Parameters: PARAMCD, PARAM for each TTE endpoint
- Analysis flags: ANL01FL, ANL02FL
"""

from typing import Any, Dict, List, Optional
from ..base import SASCodeGenerator


class ADTTEGenerator(SASCodeGenerator):
    """
    Generates ADTTE.sas program from protocol facts.

    ADTTE contains time-to-event data for survival analyses including:
    - Overall Survival (OS)
    - Progression-Free Survival (PFS)
    - Disease-Free Survival (DFS)
    - Time to Response
    - Duration of Response
    """

    @property
    def program_name(self) -> str:
        return "adtte.sas"

    @property
    def program_purpose(self) -> str:
        return "Create ADTTE (Time-to-Event Analysis Dataset)"

    def generate(self, facts: Any) -> str:
        """
        Generate complete ADTTE.sas program.

        Args:
            facts: FullProtocolFacts object with extracted protocol information

        Returns:
            Complete SAS program as string
        """
        # Extract key information
        nct_id = getattr(facts, 'nct_id', '') or 'UNKNOWN'
        study_id = getattr(facts, 'study_id', '') or nct_id
        drug_name = getattr(facts, 'drug_name', '') or 'STUDY_DRUG'
        therapeutic_area = getattr(facts, 'therapeutic_area', '') or ''
        primary_endpoint = getattr(facts, 'primary_endpoint', '') or ''

        # Determine which TTE endpoints to include
        tte_endpoints = self._determine_tte_endpoints(therapeutic_area, primary_endpoint)

        # Build program sections
        sections = []

        # 1. Header
        sections.append(self.generate_header(
            study_id=study_id,
            nct_id=nct_id,
            additional_info={
                'Drug': drug_name,
                'Structure': 'BDS (Basic Data Structure)',
                'Endpoints': ', '.join([ep['paramcd'] for ep in tte_endpoints])
            }
        ))

        # 2. Macro variables
        sections.append(self._generate_macro_variables(study_id, drug_name))

        # 3. Libnames
        sections.append(self.generate_libname_statements())

        # 4. Main data steps for each endpoint
        sections.append(self._generate_main_data_steps(tte_endpoints))

        # 5. Combine all endpoints
        sections.append(self._generate_combine_step(tte_endpoints))

        # 6. QC checks
        sections.append(self._generate_qc_section(tte_endpoints))

        # 7. Documentation
        sections.append(self.generate_proc_contents("adam.adtte"))

        return "\n".join(sections)

    def _determine_tte_endpoints(self, therapeutic_area: str, primary_endpoint: str) -> List[Dict]:
        """Determine which TTE endpoints to include based on therapeutic area"""

        ta = therapeutic_area.upper() if therapeutic_area else ""
        pe = primary_endpoint.upper() if primary_endpoint else ""

        endpoints = []

        # Oncology studies typically have OS, PFS
        if "ONCOL" in ta or "CANCER" in ta or "TUMOR" in ta:
            endpoints.append({
                'paramcd': 'OS',
                'param': 'Overall Survival',
                'event': 'Death',
                'censor': 'Last known alive date'
            })
            endpoints.append({
                'paramcd': 'PFS',
                'param': 'Progression-Free Survival',
                'event': 'Disease progression or death',
                'censor': 'Last tumor assessment date'
            })
            endpoints.append({
                'paramcd': 'DOR',
                'param': 'Duration of Response',
                'event': 'Disease progression or death',
                'censor': 'Last tumor assessment (responders only)'
            })

        # IBD/GI studies might have time to response/remission
        elif "IBD" in ta or "ULCERATIVE" in ta or "CROHN" in ta or "GI" in ta:
            endpoints.append({
                'paramcd': 'TTRESP',
                'param': 'Time to Clinical Response',
                'event': 'First clinical response',
                'censor': 'Last assessment without response'
            })
            endpoints.append({
                'paramcd': 'TTREM',
                'param': 'Time to Clinical Remission',
                'event': 'First clinical remission',
                'censor': 'Last assessment without remission'
            })
            endpoints.append({
                'paramcd': 'DOREMIS',
                'param': 'Duration of Remission',
                'event': 'Loss of remission',
                'censor': 'Last assessment in remission'
            })

        # Cardiovascular - time to MACE, etc.
        elif "CARDIO" in ta or "CV" in ta:
            endpoints.append({
                'paramcd': 'TTMACE',
                'param': 'Time to First MACE',
                'event': 'CV death, MI, or stroke',
                'censor': 'Last contact without MACE'
            })
            endpoints.append({
                'paramcd': 'TTCVD',
                'param': 'Time to CV Death',
                'event': 'Cardiovascular death',
                'censor': 'Last known alive'
            })

        # Default: generic event-free survival
        else:
            endpoints.append({
                'paramcd': 'TTEVNT',
                'param': 'Time to Event',
                'event': 'Primary event',
                'censor': 'Last assessment without event'
            })
            endpoints.append({
                'paramcd': 'OS',
                'param': 'Overall Survival',
                'event': 'Death',
                'censor': 'Last known alive date'
            })

        return endpoints

    def _generate_macro_variables(self, study_id: str, drug_name: str) -> str:
        """Generate macro variable definitions"""

        return f"""
{self.generate_section_comment("Macro Variables", 1)}

%let STUDYID = {study_id};
%let DRUG = {drug_name};

/* Analysis cutoff date - update before each analysis */
%let CUTOFF = %sysfunc(today(), date9.);

/* Output paths */
%let outpath = /output/&STUDYID.;
"""

    def _generate_main_data_steps(self, tte_endpoints: List[Dict]) -> str:
        """Generate data steps for each TTE endpoint"""

        sections = []

        sections.append(self.generate_section_comment("Get Subject-Level Data from ADSL", 1))
        sections.append("""
/* Get required variables from ADSL */
proc sort data=adam.adsl out=adsl_tte(keep=
    USUBJID STUDYID
    TRTP TRTA TRTPN TRTAN
    TRTSDT TRTEDT RANDDT
    ITTFL SAFFL FASFL
    AGE AGEGR1 SEX RACE
);
    by USUBJID;
run;
""")

        # Generate each endpoint
        for i, ep in enumerate(tte_endpoints, 1):
            sections.append(self._generate_endpoint_data_step(ep, i, len(tte_endpoints)))

        return "\n".join(sections)

    def _generate_endpoint_data_step(self, endpoint: Dict, index: int, total: int) -> str:
        """Generate data step for a single TTE endpoint"""

        paramcd = endpoint['paramcd']
        param = endpoint['param']
        event_desc = endpoint['event']
        censor_desc = endpoint['censor']

        # Different source logic based on endpoint type
        if paramcd == 'OS':
            return self._generate_os_data_step(paramcd, param, event_desc, censor_desc)
        elif paramcd == 'PFS':
            return self._generate_pfs_data_step(paramcd, param, event_desc, censor_desc)
        elif paramcd in ('TTRESP', 'TTREM', 'DOREMIS'):
            return self._generate_response_tte_data_step(paramcd, param, event_desc, censor_desc)
        else:
            return self._generate_generic_tte_data_step(paramcd, param, event_desc, censor_desc)

    def _generate_os_data_step(self, paramcd: str, param: str, event_desc: str, censor_desc: str) -> str:
        """Generate OS (Overall Survival) data step"""

        return f"""
{self.generate_section_comment(f"{paramcd}: {param}", 1)}

/* {paramcd} - {param}
   Event: {event_desc}
   Censoring: {censor_desc}
*/

data tte_{paramcd.lower()};
    merge adsl_tte(in=a)
          sdtm.dm(keep=USUBJID DTHDTC in=dm)
          sdtm.ds(keep=USUBJID DSDECOD DSSTDTC where=(upcase(DSDECOD) in ('DEATH', 'COMPLETED', 'LOST TO FOLLOW-UP', 'WITHDRAWAL BY SUBJECT')) in=ds);
    by USUBJID;
    if a;

    length PARAMCD $8 PARAM $200 PARCAT1 $40 EVNTDESC $200 CNSDTDSC $200;
    length STARTDT ADT AVAL 8 CNSR 8 ANL01FL $1 AVALU $20;

    /* Parameter identification */
    PARAMCD = "{paramcd}";
    PARAM = "{param}";
    PARCAT1 = "TIME TO EVENT";

    /* Start date: Randomization date */
    if not missing(RANDDT) then STARTDT = RANDDT;
    else if not missing(TRTSDT) then STARTDT = TRTSDT;

    /* Event date: Death */
    if not missing(DTHDTC) and length(DTHDTC) >= 10 then do;
        ADT = input(substr(DTHDTC, 1, 10), e8601da.);
        CNSR = 0;  /* Event occurred */
        EVNTDESC = "Death";
    end;
    else do;
        /* Censored: Use last known alive date */
        /* This would typically come from last contact date */
        /* Using disposition date or treatment end as proxy */
        if not missing(DSSTDTC) and length(DSSTDTC) >= 10 then
            ADT = input(substr(DSSTDTC, 1, 10), e8601da.);
        else if not missing(TRTEDT) then
            ADT = TRTEDT;
        else
            ADT = "&CUTOFF"d;  /* Use cutoff if no other date available */

        CNSR = 1;  /* Censored */
        EVNTDESC = "Censored";
        CNSDTDSC = "{censor_desc}";
    end;

    /* Calculate time to event */
    if not missing(STARTDT) and not missing(ADT) then do;
        AVAL = ADT - STARTDT + 1;  /* Time in days */
        if AVAL < 1 then AVAL = 1; /* Minimum 1 day */
    end;

    AVALU = "DAYS";

    /* Analysis flag: ITT population with valid time */
    if ITTFL = 'Y' and not missing(AVAL) and AVAL > 0 then ANL01FL = 'Y';
    else ANL01FL = '';

    /* Keep only subjects in analysis population */
    if ITTFL = 'Y';

    label
        PARAMCD = "Parameter Code"
        PARAM = "Parameter"
        PARCAT1 = "Parameter Category 1"
        STARTDT = "Time-to-Event Origin Date"
        ADT = "Analysis Date"
        AVAL = "Analysis Value"
        AVALU = "Analysis Value Unit"
        CNSR = "Censor (0=Event, 1=Censored)"
        EVNTDESC = "Event or Censoring Description"
        CNSDTDSC = "Censoring Description"
        ANL01FL = "Analysis Record Flag 01"
    ;

    format STARTDT ADT date9.;

    keep USUBJID STUDYID TRTP TRTA TRTPN TRTAN ITTFL SAFFL
         PARAMCD PARAM PARCAT1 STARTDT ADT AVAL AVALU CNSR EVNTDESC CNSDTDSC ANL01FL
         AGE AGEGR1 SEX RACE;
run;
"""

    def _generate_pfs_data_step(self, paramcd: str, param: str, event_desc: str, censor_desc: str) -> str:
        """Generate PFS (Progression-Free Survival) data step"""

        return f"""
{self.generate_section_comment(f"{paramcd}: {param}", 1)}

/* {paramcd} - {param}
   Event: {event_desc}
   Censoring: {censor_desc}
*/

data tte_{paramcd.lower()};
    merge adsl_tte(in=a)
          sdtm.dm(keep=USUBJID DTHDTC in=dm)
          sdtm.rs(keep=USUBJID RSSTRESC RSDTC where=(upcase(RSSTRESC) = 'PD') in=rs);
    by USUBJID;
    if a;

    length PARAMCD $8 PARAM $200 PARCAT1 $40 EVNTDESC $200 CNSDTDSC $200;
    length STARTDT ADT PDDT DTHDT AVAL 8 CNSR 8 ANL01FL $1 AVALU $20;

    /* Parameter identification */
    PARAMCD = "{paramcd}";
    PARAM = "{param}";
    PARCAT1 = "TIME TO EVENT";

    /* Start date: Randomization date */
    if not missing(RANDDT) then STARTDT = RANDDT;
    else if not missing(TRTSDT) then STARTDT = TRTSDT;

    /* Parse progression date from RS domain */
    if not missing(RSDTC) and length(RSDTC) >= 10 then
        PDDT = input(substr(RSDTC, 1, 10), e8601da.);

    /* Parse death date */
    if not missing(DTHDTC) and length(DTHDTC) >= 10 then
        DTHDT = input(substr(DTHDTC, 1, 10), e8601da.);

    /* Event: Earlier of progression or death */
    if not missing(PDDT) and not missing(DTHDT) then do;
        if PDDT <= DTHDT then do;
            ADT = PDDT;
            EVNTDESC = "Disease Progression";
        end;
        else do;
            ADT = DTHDT;
            EVNTDESC = "Death";
        end;
        CNSR = 0;
    end;
    else if not missing(PDDT) then do;
        ADT = PDDT;
        CNSR = 0;
        EVNTDESC = "Disease Progression";
    end;
    else if not missing(DTHDT) then do;
        ADT = DTHDT;
        CNSR = 0;
        EVNTDESC = "Death without Progression";
    end;
    else do;
        /* Censored at last tumor assessment */
        /* Would typically come from TU domain last assessment date */
        if not missing(TRTEDT) then ADT = TRTEDT;
        else ADT = "&CUTOFF"d;
        CNSR = 1;
        EVNTDESC = "Censored";
        CNSDTDSC = "{censor_desc}";
    end;

    /* Calculate time to event */
    if not missing(STARTDT) and not missing(ADT) then do;
        AVAL = ADT - STARTDT + 1;
        if AVAL < 1 then AVAL = 1;
    end;

    AVALU = "DAYS";

    /* Analysis flag */
    if ITTFL = 'Y' and not missing(AVAL) and AVAL > 0 then ANL01FL = 'Y';
    else ANL01FL = '';

    if ITTFL = 'Y';

    label
        PARAMCD = "Parameter Code"
        PARAM = "Parameter"
        PARCAT1 = "Parameter Category 1"
        STARTDT = "Time-to-Event Origin Date"
        ADT = "Analysis Date"
        AVAL = "Analysis Value"
        AVALU = "Analysis Value Unit"
        CNSR = "Censor (0=Event, 1=Censored)"
        EVNTDESC = "Event or Censoring Description"
        CNSDTDSC = "Censoring Description"
        ANL01FL = "Analysis Record Flag 01"
    ;

    format STARTDT ADT PDDT DTHDT date9.;

    keep USUBJID STUDYID TRTP TRTA TRTPN TRTAN ITTFL SAFFL
         PARAMCD PARAM PARCAT1 STARTDT ADT AVAL AVALU CNSR EVNTDESC CNSDTDSC ANL01FL
         AGE AGEGR1 SEX RACE;
run;
"""

    def _generate_response_tte_data_step(self, paramcd: str, param: str, event_desc: str, censor_desc: str) -> str:
        """Generate response-based TTE data step (for IBD/autoimmune)"""

        return f"""
{self.generate_section_comment(f"{paramcd}: {param}", 1)}

/* {paramcd} - {param}
   Event: {event_desc}
   Censoring: {censor_desc}
*/

data tte_{paramcd.lower()};
    merge adsl_tte(in=a);
    by USUBJID;
    if a;

    length PARAMCD $8 PARAM $200 PARCAT1 $40 EVNTDESC $200 CNSDTDSC $200;
    length STARTDT ADT AVAL 8 CNSR 8 ANL01FL $1 AVALU $20;

    /* Parameter identification */
    PARAMCD = "{paramcd}";
    PARAM = "{param}";
    PARCAT1 = "TIME TO EVENT";

    /* Start date: First dose date (for time to response) */
    if not missing(TRTSDT) then STARTDT = TRTSDT;
    else if not missing(RANDDT) then STARTDT = RANDDT;

    /* Event detection would come from efficacy assessments */
    /* This is a placeholder - actual derivation depends on */
    /* disease-specific response criteria (e.g., Mayo score, CDAI) */

    /* Placeholder: Set all as censored for now */
    /* Update with actual response/remission dates from QS/efficacy data */
    if not missing(TRTEDT) then ADT = TRTEDT;
    else ADT = "&CUTOFF"d;

    CNSR = 1;  /* Censored - update when event data available */
    EVNTDESC = "Censored";
    CNSDTDSC = "{censor_desc}";

    /* Note: Update CNSR=0 and EVNTDESC when response/remission achieved */
    /* Example logic:
    if RESPONSE_DATE ne . then do;
        ADT = RESPONSE_DATE;
        CNSR = 0;
        EVNTDESC = "{event_desc}";
    end;
    */

    /* Calculate time to event */
    if not missing(STARTDT) and not missing(ADT) then do;
        AVAL = ADT - STARTDT + 1;
        if AVAL < 1 then AVAL = 1;
    end;

    AVALU = "DAYS";

    /* Analysis flag */
    if FASFL = 'Y' and not missing(AVAL) and AVAL > 0 then ANL01FL = 'Y';
    else ANL01FL = '';

    if FASFL = 'Y';

    label
        PARAMCD = "Parameter Code"
        PARAM = "Parameter"
        PARCAT1 = "Parameter Category 1"
        STARTDT = "Time-to-Event Origin Date"
        ADT = "Analysis Date"
        AVAL = "Analysis Value"
        AVALU = "Analysis Value Unit"
        CNSR = "Censor (0=Event, 1=Censored)"
        EVNTDESC = "Event or Censoring Description"
        CNSDTDSC = "Censoring Description"
        ANL01FL = "Analysis Record Flag 01"
    ;

    format STARTDT ADT date9.;

    keep USUBJID STUDYID TRTP TRTA TRTPN TRTAN ITTFL SAFFL FASFL
         PARAMCD PARAM PARCAT1 STARTDT ADT AVAL AVALU CNSR EVNTDESC CNSDTDSC ANL01FL
         AGE AGEGR1 SEX RACE;
run;
"""

    def _generate_generic_tte_data_step(self, paramcd: str, param: str, event_desc: str, censor_desc: str) -> str:
        """Generate generic TTE data step"""

        return f"""
{self.generate_section_comment(f"{paramcd}: {param}", 1)}

/* {paramcd} - {param}
   Event: {event_desc}
   Censoring: {censor_desc}
*/

data tte_{paramcd.lower()};
    merge adsl_tte(in=a);
    by USUBJID;
    if a;

    length PARAMCD $8 PARAM $200 PARCAT1 $40 EVNTDESC $200 CNSDTDSC $200;
    length STARTDT ADT AVAL 8 CNSR 8 ANL01FL $1 AVALU $20;

    /* Parameter identification */
    PARAMCD = "{paramcd}";
    PARAM = "{param}";
    PARCAT1 = "TIME TO EVENT";

    /* Start date */
    if not missing(RANDDT) then STARTDT = RANDDT;
    else if not missing(TRTSDT) then STARTDT = TRTSDT;

    /* Event/censor date - placeholder */
    /* Update with actual event detection logic */
    if not missing(TRTEDT) then ADT = TRTEDT;
    else ADT = "&CUTOFF"d;

    CNSR = 1;  /* Default censored - update with event logic */
    EVNTDESC = "Censored";
    CNSDTDSC = "{censor_desc}";

    /* Calculate time */
    if not missing(STARTDT) and not missing(ADT) then do;
        AVAL = ADT - STARTDT + 1;
        if AVAL < 1 then AVAL = 1;
    end;

    AVALU = "DAYS";

    if ITTFL = 'Y' and not missing(AVAL) then ANL01FL = 'Y';
    else ANL01FL = '';

    if ITTFL = 'Y';

    format STARTDT ADT date9.;

    keep USUBJID STUDYID TRTP TRTA TRTPN TRTAN ITTFL SAFFL
         PARAMCD PARAM PARCAT1 STARTDT ADT AVAL AVALU CNSR EVNTDESC CNSDTDSC ANL01FL
         AGE AGEGR1 SEX RACE;
run;
"""

    def _generate_combine_step(self, tte_endpoints: List[Dict]) -> str:
        """Generate step to combine all TTE endpoints"""

        dataset_list = " ".join([f"tte_{ep['paramcd'].lower()}" for ep in tte_endpoints])

        return f"""
{self.generate_section_comment("Combine All TTE Parameters", 1)}

/* Stack all TTE parameters into final ADTTE */
data adam.adtte;
    set {dataset_list};
run;

/* Sort by subject and parameter */
proc sort data=adam.adtte;
    by USUBJID PARAMCD;
run;
"""

    def _generate_qc_section(self, tte_endpoints: List[Dict]) -> str:
        """Generate QC frequency tables"""

        return f"""
{self.generate_section_comment("QC Checks", 1)}

/* Parameter summary */
title "QC: ADTTE Parameter Summary";
proc freq data=adam.adtte;
    tables PARAMCD * PARAM / list missing;
run;

/* Event vs Censoring by treatment */
title "QC: Event/Censoring by Treatment and Parameter";
proc freq data=adam.adtte;
    where ANL01FL = 'Y';
    tables PARAMCD * CNSR * TRTA / list missing;
run;

/* Time summary by parameter */
title "QC: Time to Event Summary (days)";
proc means data=adam.adtte n mean std median min max;
    where ANL01FL = 'Y';
    class PARAMCD TRTA;
    var AVAL;
run;

/* Kaplan-Meier estimates for each parameter */
title "QC: Kaplan-Meier Median Estimates";
%macro km_check(param);
    title2 "Parameter: &param";
    proc lifetest data=adam.adtte method=km plots=none;
        where ANL01FL = 'Y' and PARAMCD = "&param";
        time AVAL * CNSR(1);
        strata TRTA;
    run;
%mend;

{chr(10).join([f"%km_check({ep['paramcd']});" for ep in tte_endpoints])}

title;
"""
