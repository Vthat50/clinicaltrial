#!/usr/bin/env python3
"""
Adverse Event Summary Table Generator (t_ae_summary.sas)
========================================================

Generates SAS code for Table 14.3.1: Adverse Event Summary.
Standard regulatory safety table required for all clinical trials.

Output: Production-ready SAS program that creates:
- Overall AE summary (subjects with any AE, SAE, etc.)
- AE by System Organ Class (SOC)
- AE by Preferred Term (PT)
- Treatment-emergent AE analysis
"""

import re
from typing import Dict, List, Any, Optional
from ..base import SASCodeGenerator, CodeGenerationResult


class AESummaryTableGenerator(SASCodeGenerator):
    """Generates SAS code for adverse event summary tables."""

    def __init__(self):
        super().__init__()
        self.output_name = "t_ae_summary"
        self.table_number = "14.3.1"
        self.table_title = "Summary of Adverse Events"

    def generate(self, protocol_facts: Dict[str, Any]) -> CodeGenerationResult:
        """Generate complete AE summary table SAS program."""

        code_sections = []

        # Header
        code_sections.append(self.generate_header(
            program_name=f"{self.output_name}.sas",
            description=f"Table {self.table_number}: {self.table_title}",
            input_datasets=["ADSL", "ADAE"],
            output_datasets=[self.output_name.upper()],
            macros_used=["ae_count", "ae_soc_pt", "rtftable"]
        ))

        # Extract protocol information
        treatments = self._extract_treatments(protocol_facts)
        population = self._extract_population(protocol_facts)

        # Program setup
        code_sections.append(self._generate_setup())

        # Population and data preparation
        code_sections.append(self._generate_data_prep(population))

        # Overall AE summary counts
        code_sections.append(self._generate_overall_summary())

        # AE by SOC and PT
        code_sections.append(self._generate_soc_pt_summary())

        # Combine and format results
        code_sections.append(self._generate_combine_results())

        # RTF output
        code_sections.append(self._generate_rtf_output(treatments))

        full_code = "\n".join(code_sections)

        return CodeGenerationResult(
            program_name=f"{self.output_name}.sas",
            code=full_code,
            description=f"Table {self.table_number}: {self.table_title}",
            input_datasets=["ADSL", "ADAE"],
            output_datasets=[self.output_name.upper()],
            dependencies=["adsl.sas", "adae.sas"],
            validation_notes=[
                "Verify TEAE flag derivation matches protocol definition",
                "Check SOC ordering follows MedDRA conventions",
                "Confirm subject counts are unique (no double-counting)",
                "Validate percentage calculations use correct denominator",
                "Review SAE and severe AE identification"
            ]
        )

    def _extract_treatments(self, protocol_facts: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract treatment arm information."""
        treatments = []

        if "treatments" in protocol_facts:
            for trt in protocol_facts["treatments"]:
                treatments.append({
                    "name": trt.get("name", "Treatment"),
                    "code": trt.get("code", "TRT"),
                    "n": trt.get("n", "1")
                })
        elif "arms" in protocol_facts:
            for i, arm in enumerate(protocol_facts["arms"], 1):
                treatments.append({
                    "name": arm.get("name", f"Arm {i}"),
                    "code": f"TRT{i}",
                    "n": str(i)
                })
        else:
            treatments = [
                {"name": "Placebo", "code": "PBO", "n": "1"},
                {"name": "Active Treatment", "code": "TRT", "n": "2"}
            ]

        return treatments

    def _extract_population(self, protocol_facts: Dict[str, Any]) -> str:
        """Extract analysis population."""
        return protocol_facts.get("safety_population", "SAFFL").upper()

    def _generate_setup(self) -> str:
        """Generate program setup section."""
        return self.generate_section_comment("Program Setup") + """
*-- Program options --;
options nodate nonumber orientation=landscape;
ods escapechar='^';

*-- Libname assignments --;
libname adam "&adam_path" access=readonly;
libname output "&output_path";

*-- Macro variables --;
%let population = Safety Population;
%let popflag = SAFFL;

*-- Format for severity --;
proc format;
    value $sevfmt
        'MILD' = 'Mild'
        'MODERATE' = 'Moderate'
        'SEVERE' = 'Severe'
        'LIFE THREATENING' = 'Life Threatening'
        'DEATH' = 'Death'
        other = 'Unknown'
    ;
    value $relfmt
        'RELATED' = 'Related'
        'POSSIBLY RELATED' = 'Possibly Related'
        'PROBABLY RELATED' = 'Probably Related'
        'UNLIKELY RELATED' = 'Unlikely Related'
        'NOT RELATED' = 'Not Related'
        other = 'Unknown'
    ;
run;
"""

    def _generate_data_prep(self, population: str) -> str:
        """Generate data preparation code."""
        return self.generate_section_comment("Data Preparation") + f"""
*-- Get analysis population from ADSL --;
data work.pop;
    set adam.adsl;
    where {population} = 'Y';
    keep USUBJID TRTAN TRTA;
run;

*-- Get treatment counts for denominators --;
proc sql noprint;
    select count(*) into :n_total trimmed from work.pop;

    create table work.trt_counts as
    select TRTAN, count(*) as n
    from work.pop
    group by TRTAN;

    *-- Store in macro variables --;
    select count(*) into :n_trt1 trimmed
    from work.pop where TRTAN = 1;

    select count(*) into :n_trt2 trimmed
    from work.pop where TRTAN = 2;
quit;

*-- Prepare ADAE data --;
data work.adae;
    merge adam.adae(in=a) work.pop(in=b);
    by USUBJID;
    if a and b;

    *-- Ensure TRTEMFL exists --;
    if TRTEMFL = '' then TRTEMFL = 'Y';  /* Default to treatment-emergent */

    *-- Derive additional flags if needed --;
    length AESERFL $1 AESEVFL $1 AERELFL $1 AEDISCFL $1;

    *-- Serious AE flag --;
    if AESER = 'Y' then AESERFL = 'Y';
    else AESERFL = 'N';

    *-- Severe AE flag --;
    if upcase(AESEV) in ('SEVERE' 'LIFE THREATENING' 'DEATH') then AESEVFL = 'Y';
    else AESEVFL = 'N';

    *-- Related AE flag --;
    if upcase(AEREL) in ('RELATED' 'POSSIBLY RELATED' 'PROBABLY RELATED') then AERELFL = 'Y';
    else AERELFL = 'N';

    *-- Discontinuation due to AE --;
    if AEACN = 'DRUG WITHDRAWN' then AEDISCFL = 'Y';
    else AEDISCFL = 'N';
run;

*-- Treatment-emergent AEs only --;
data work.teae;
    set work.adae;
    where TRTEMFL = 'Y';
run;
"""

    def _generate_overall_summary(self) -> str:
        """Generate overall AE summary section."""
        return self.generate_section_comment("Overall AE Summary") + """
*-- Macro to count unique subjects --;
%macro ae_subj_count(inds=, flag=, flagval=, rownum=, rowlabel=);
    *-- Count unique subjects by treatment --;
    proc sql;
        create table work.cnt_&rownum as
        select TRTAN, count(distinct USUBJID) as n
        from &inds
        %if &flag ne %then %do;
            where &flag = "&flagval"
        %end;
        group by TRTAN;
    quit;

    *-- Add total --;
    proc sql;
        insert into work.cnt_&rownum
        select 99 as TRTAN, count(distinct USUBJID) as n
        from &inds
        %if &flag ne %then %do;
            where &flag = "&flagval"
        %end;
        ;
    quit;

    *-- Format results --;
    data work.row_&rownum;
        length category $100 value $50;
        set work.cnt_&rownum;

        roworder = &rownum;
        category = "&rowlabel";
        trt = TRTAN;

        *-- Calculate percentage --;
        if trt = 99 then denom = &n_total;
        else if trt = 1 then denom = &n_trt1;
        else if trt = 2 then denom = &n_trt2;
        else denom = .;

        if denom > 0 then pct = (n / denom) * 100;
        else pct = 0;

        value = strip(put(n, 8.)) || ' (' || strip(put(pct, 5.1)) || '%)';

        keep roworder category trt value;
    run;
%mend ae_subj_count;

*-- Generate overall summary counts --;
%ae_subj_count(inds=work.teae, flag=, flagval=, rownum=1, rowlabel=Subjects with at least one TEAE);
%ae_subj_count(inds=work.teae, flag=AESERFL, flagval=Y, rownum=2, rowlabel=Subjects with at least one serious AE);
%ae_subj_count(inds=work.teae, flag=AESEVFL, flagval=Y, rownum=3, rowlabel=Subjects with at least one severe AE);
%ae_subj_count(inds=work.teae, flag=AERELFL, flagval=Y, rownum=4, rowlabel=Subjects with at least one related AE);
%ae_subj_count(inds=work.teae, flag=AEDISCFL, flagval=Y, rownum=5, rowlabel=Subjects discontinued due to AE);

*-- Subjects with no AE --;
proc sql;
    create table work.noae as
    select a.TRTAN, count(distinct a.USUBJID) as n
    from work.pop a
    where a.USUBJID not in (select distinct USUBJID from work.teae)
    group by a.TRTAN;

    insert into work.noae
    select 99 as TRTAN, count(distinct a.USUBJID) as n
    from work.pop a
    where a.USUBJID not in (select distinct USUBJID from work.teae);
quit;

data work.row_0;
    length category $100 value $50;
    set work.noae;

    roworder = 0;
    category = 'Subjects with no TEAE';
    trt = TRTAN;

    if trt = 99 then denom = &n_total;
    else if trt = 1 then denom = &n_trt1;
    else if trt = 2 then denom = &n_trt2;
    else denom = .;

    if denom > 0 then pct = (n / denom) * 100;
    else pct = 0;

    value = strip(put(n, 8.)) || ' (' || strip(put(pct, 5.1)) || '%)';

    keep roworder category trt value;
run;

*-- Combine overall summary --;
data work.overall_summary;
    set work.row_0 work.row_1 work.row_2 work.row_3 work.row_4 work.row_5;
run;

proc sort data=work.overall_summary; by roworder trt; run;

*-- Transpose to wide format --;
proc transpose data=work.overall_summary out=work.overall_wide(drop=_name_) prefix=col;
    by roworder category;
    id trt;
    var value;
run;
"""

    def _generate_soc_pt_summary(self) -> str:
        """Generate SOC and PT level summary."""
        return self.generate_section_comment("AE by System Organ Class and Preferred Term") + """
*-- Get unique SOC/PT combinations with counts --;
proc sql;
    create table work.soc_pt_counts as
    select AEBODSYS, AEDECOD, TRTAN, count(distinct USUBJID) as n
    from work.teae
    group by AEBODSYS, AEDECOD, TRTAN;
quit;

*-- Add total column --;
proc sql;
    create table work.soc_pt_total as
    select AEBODSYS, AEDECOD, 99 as TRTAN, count(distinct USUBJID) as n
    from work.teae
    group by AEBODSYS, AEDECOD;
quit;

data work.soc_pt_all;
    set work.soc_pt_counts work.soc_pt_total;
run;

*-- SOC level counts (any PT within SOC) --;
proc sql;
    create table work.soc_counts as
    select AEBODSYS, TRTAN, count(distinct USUBJID) as n
    from work.teae
    group by AEBODSYS, TRTAN;

    create table work.soc_total as
    select AEBODSYS, 99 as TRTAN, count(distinct USUBJID) as n
    from work.teae
    group by AEBODSYS;
quit;

data work.soc_all;
    set work.soc_counts work.soc_total;
run;

*-- Format SOC level results --;
data work.soc_fmt;
    length category $200 sublabel $200 value $50;
    set work.soc_all;

    category = propcase(AEBODSYS);
    sublabel = '';
    rowtype = 'SOC';
    trt = TRTAN;

    if trt = 99 then denom = &n_total;
    else if trt = 1 then denom = &n_trt1;
    else if trt = 2 then denom = &n_trt2;
    else denom = .;

    if denom > 0 then pct = (n / denom) * 100;
    else pct = 0;

    value = strip(put(n, 8.)) || ' (' || strip(put(pct, 5.1)) || '%)';

    keep category sublabel rowtype trt value AEBODSYS n;
run;

*-- Format PT level results --;
data work.pt_fmt;
    length category $200 sublabel $200 value $50;
    set work.soc_pt_all;

    category = propcase(AEBODSYS);
    sublabel = '  ' || propcase(AEDECOD);
    rowtype = 'PT';
    trt = TRTAN;

    if trt = 99 then denom = &n_total;
    else if trt = 1 then denom = &n_trt1;
    else if trt = 2 then denom = &n_trt2;
    else denom = .;

    if denom > 0 then pct = (n / denom) * 100;
    else pct = 0;

    value = strip(put(n, 8.)) || ' (' || strip(put(pct, 5.1)) || '%)';

    keep category sublabel rowtype trt value AEBODSYS AEDECOD n;
run;

*-- Combine and sort --;
*-- Sort by total column descending (most frequent SOC first) --;
proc sql;
    create table work.soc_order as
    select distinct AEBODSYS, n as soc_n
    from work.soc_fmt
    where trt = 99
    order by n desc;
quit;

data work.soc_order;
    set work.soc_order;
    soc_order = _n_;
run;

proc sql;
    create table work.pt_order as
    select distinct AEBODSYS, AEDECOD, n as pt_n
    from work.pt_fmt
    where trt = 99
    order by AEBODSYS, n desc;
quit;

data work.pt_order;
    set work.pt_order;
    by AEBODSYS;
    if first.AEBODSYS then pt_order = 0;
    pt_order + 1;
run;

*-- Merge order variables --;
proc sql;
    create table work.soc_sorted as
    select a.*, b.soc_order
    from work.soc_fmt a
    left join work.soc_order b on a.AEBODSYS = b.AEBODSYS
    order by soc_order, trt;

    create table work.pt_sorted as
    select a.*, b.soc_order, c.pt_order
    from work.pt_fmt a
    left join work.soc_order b on a.AEBODSYS = b.AEBODSYS
    left join work.pt_order c on a.AEBODSYS = c.AEBODSYS and a.AEDECOD = c.AEDECOD
    order by soc_order, pt_order, trt;
quit;

*-- Transpose SOC --;
proc transpose data=work.soc_sorted out=work.soc_wide(drop=_name_) prefix=col;
    by soc_order category sublabel rowtype;
    id trt;
    var value;
run;

*-- Transpose PT --;
proc transpose data=work.pt_sorted out=work.pt_wide(drop=_name_) prefix=col;
    by soc_order pt_order category sublabel rowtype;
    id trt;
    var value;
run;

*-- Interleave SOC and PT --;
data work.soc_pt_combined;
    set work.soc_wide(in=a) work.pt_wide(in=b);
    if a then pt_order = 0;
run;

proc sort data=work.soc_pt_combined;
    by soc_order pt_order;
run;
"""

    def _generate_combine_results(self) -> str:
        """Generate code to combine all results."""
        return self.generate_section_comment("Combine All Results") + """
*-- Add section headers --;
data work.overall_final;
    length section $50 category $200 sublabel $200;
    set work.overall_wide;
    section = 'Overall Summary';
    sublabel = '';
    rowtype = 'OVERALL';
    soc_order = 0;
    pt_order = roworder;
run;

data work.soc_pt_final;
    length section $50;
    set work.soc_pt_combined;
    section = 'AE by System Organ Class and Preferred Term';
run;

*-- Final combined table --;
data work.final_table;
    set work.overall_final work.soc_pt_final;
run;

proc sort data=work.final_table;
    by section soc_order pt_order;
run;

*-- Add display row number --;
data work.final_table;
    set work.final_table;
    display_row + 1;
run;
"""

    def _generate_rtf_output(self, treatments: List[Dict]) -> str:
        """Generate RTF output code."""
        return self.generate_section_comment("Generate RTF Output") + """
*-- Define output location --;
%let outpath = &output_path;
%let outname = t_ae_summary;

*-- Create RTF output --;
options orientation=landscape;
ods listing close;
ods rtf file="&outpath./&outname..rtf" style=journal;

title1 "Table 14.3.1";
title2 "Summary of Adverse Events";
title3 "&population";
title4 "Treatment-Emergent Adverse Events";

footnote1 "TEAE = Treatment-emergent adverse event";
footnote2 "MedDRA version XX.X";
footnote3 "Percentages are based on the number of subjects in the Safety Population";

proc report data=work.final_table nowd split='~'
    style(report)=[outputwidth=9.5in]
    style(column)=[asis=on];

    column display_row section category sublabel
           ("Treatment Group" col1 col2) col99;

    define display_row / order noprint;
    define section / order noprint;
    define category / order style(column)=[width=2.5in];
    define sublabel / display ' ' style(column)=[width=2in];
    define col1 / display "Placebo~(N=&n_trt1)" style(column)=[width=1.2in just=c];
    define col2 / display "Active~(N=&n_trt2)" style(column)=[width=1.2in just=c];
    define col99 / display "Total~(N=&n_total)" style(column)=[width=1.2in just=c];

    break before section / contents='' page;

    compute before section;
        line ' ';
        line @1 section $50.;
        line ' ';
    endcomp;

    compute before category;
        line ' ';
    endcomp;
run;

ods rtf close;
ods listing;

*-- Save permanent dataset --;
data output.t_ae_summary;
    set work.final_table;
run;

*-- Cleanup --;
proc datasets library=work nolist;
    delete pop trt_counts adae teae cnt_: row_: noae overall_:
           soc_: pt_: final_table;
quit;

%put NOTE: Table 14.3.1 Summary of Adverse Events completed successfully.;
"""
