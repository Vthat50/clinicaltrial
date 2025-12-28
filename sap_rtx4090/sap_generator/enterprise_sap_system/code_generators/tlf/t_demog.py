#!/usr/bin/env python3
"""
Demographics Table Generator (t_demog.sas)
==========================================

Generates SAS code for Table 14.1.1: Demographics and Baseline Characteristics.
Standard regulatory table required for all clinical trials.

Output: Production-ready SAS program that creates:
- Summary statistics for continuous variables (age, weight, BMI)
- Frequency counts for categorical variables (sex, race, ethnicity)
- Treatment group comparisons
- Overall population summary
"""

import re
from typing import Dict, List, Any, Optional
from ..base import SASCodeGenerator, CodeGenerationResult


class DemographicsTableGenerator(SASCodeGenerator):
    """Generates SAS code for demographics and baseline characteristics table."""

    def __init__(self):
        super().__init__()
        self.output_name = "t_demog"
        self.table_number = "14.1.1"
        self.table_title = "Demographics and Baseline Characteristics"

    def generate(self, protocol_facts: Dict[str, Any]) -> CodeGenerationResult:
        """Generate complete demographics table SAS program."""

        code_sections = []

        # Header
        code_sections.append(self.generate_header(
            program_name=f"{self.output_name}.sas",
            description=f"Table {self.table_number}: {self.table_title}",
            input_datasets=["ADSL"],
            output_datasets=[self.output_name.upper()],
            macros_used=["statrow", "catrow", "rtftable"]
        ))

        # Extract protocol information
        treatments = self._extract_treatments(protocol_facts)
        population = self._extract_population(protocol_facts)
        therapeutic_area = self._extract_therapeutic_area(protocol_facts)

        # Libname and options
        code_sections.append(self._generate_setup())

        # Population selection
        code_sections.append(self._generate_population_selection(population))

        # Continuous variables analysis
        code_sections.append(self._generate_continuous_stats(treatments, therapeutic_area))

        # Categorical variables analysis
        code_sections.append(self._generate_categorical_stats(treatments))

        # Combine results
        code_sections.append(self._generate_combine_results())

        # Create RTF output
        code_sections.append(self._generate_rtf_output(treatments))

        full_code = "\n".join(code_sections)

        return CodeGenerationResult(
            program_name=f"{self.output_name}.sas",
            code=full_code,
            description=f"Table {self.table_number}: {self.table_title}",
            input_datasets=["ADSL"],
            output_datasets=[self.output_name.upper()],
            dependencies=["adsl.sas"],
            validation_notes=[
                "Verify population counts match disposition",
                "Check continuous variable statistics against raw data",
                "Confirm categorical percentages sum correctly",
                "Review treatment group assignments"
            ]
        )

    def _extract_treatments(self, protocol_facts: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract treatment arm information."""
        treatments = []

        # Try to get from protocol facts
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
            # Default two-arm trial
            treatments = [
                {"name": "Placebo", "code": "PBO", "n": "1"},
                {"name": "Active Treatment", "code": "TRT", "n": "2"}
            ]

        return treatments

    def _extract_population(self, protocol_facts: Dict[str, Any]) -> str:
        """Extract analysis population."""
        population = protocol_facts.get("demographics_population", "SAFFL")
        return population.upper()

    def _extract_therapeutic_area(self, protocol_facts: Dict[str, Any]) -> str:
        """Extract therapeutic area for disease-specific variables."""
        return protocol_facts.get("therapeutic_area", "general").lower()

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

*-- Output formats --;
proc format;
    value $sexfmt
        'M' = 'Male'
        'F' = 'Female'
        other = 'Unknown'
    ;
    value $racefmt
        'WHITE' = 'White'
        'BLACK OR AFRICAN AMERICAN' = 'Black or African American'
        'ASIAN' = 'Asian'
        'AMERICAN INDIAN OR ALASKA NATIVE' = 'American Indian or Alaska Native'
        'NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER' = 'Native Hawaiian or Other Pacific Islander'
        'MULTIPLE' = 'Multiple'
        'OTHER' = 'Other'
        'UNKNOWN' = 'Unknown'
        'NOT REPORTED' = 'Not Reported'
        other = 'Other'
    ;
    value $ethfmt
        'HISPANIC OR LATINO' = 'Hispanic or Latino'
        'NOT HISPANIC OR LATINO' = 'Not Hispanic or Latino'
        'UNKNOWN' = 'Unknown'
        'NOT REPORTED' = 'Not Reported'
        other = 'Unknown'
    ;
run;
"""

    def _generate_population_selection(self, population: str) -> str:
        """Generate population selection code."""
        return self.generate_section_comment("Population Selection") + f"""
*-- Select analysis population --;
data work.adsl_pop;
    set adam.adsl;
    where {population} = 'Y';

    *-- Create numeric treatment variable for ordering --;
    trtord = input(TRTAN, best.);

    *-- Derive age group --;
    length AGEGR1 $20;
    if AGE < 18 then AGEGR1 = '<18';
    else if AGE < 65 then AGEGR1 = '18-64';
    else if AGE >= 65 then AGEGR1 = '>=65';
    else AGEGR1 = 'Unknown';

    *-- Derive BMI category --;
    length BMICAT $20;
    if BMIBL ne . then do;
        if BMIBL < 18.5 then BMICAT = 'Underweight (<18.5)';
        else if BMIBL < 25 then BMICAT = 'Normal (18.5-<25)';
        else if BMIBL < 30 then BMICAT = 'Overweight (25-<30)';
        else BMICAT = 'Obese (>=30)';
    end;
    else BMICAT = 'Missing';
run;

*-- Get treatment counts for denominators --;
proc sql noprint;
    select count(*) into :n_total trimmed from work.adsl_pop;

    *-- Treatment-specific counts --;
    create table work.trt_counts as
    select TRTAN, count(*) as n
    from work.adsl_pop
    group by TRTAN;
quit;

*-- Store counts in macro variables --;
data _null_;
    set work.trt_counts;
    call symputx(cats('n_trt', TRTAN), n);
run;
"""

    def _generate_continuous_stats(self, treatments: List[Dict], therapeutic_area: str) -> str:
        """Generate continuous variable statistics."""

        # Base continuous variables
        cont_vars = [
            ("AGE", "Age (years)"),
            ("WEIGHTBL", "Weight (kg)"),
            ("HEIGHTBL", "Height (cm)"),
            ("BMIBL", "BMI (kg/m^{2})")
        ]

        # Add therapeutic area-specific variables
        if therapeutic_area == "ibd":
            cont_vars.extend([
                ("MAYOBL", "Mayo Score at Baseline"),
                ("CALPROBL", "Fecal Calprotectin at Baseline (mcg/g)")
            ])
        elif therapeutic_area == "oncology":
            cont_vars.extend([
                ("ECOGBL", "ECOG Performance Status at Baseline"),
                ("TUMSIZBL", "Total Tumor Size at Baseline (mm)")
            ])
        elif therapeutic_area == "rheumatology":
            cont_vars.extend([
                ("DAS28BL", "DAS28-CRP at Baseline"),
                ("SJCBL", "Swollen Joint Count at Baseline"),
                ("TJCBL", "Tender Joint Count at Baseline")
            ])
        elif therapeutic_area == "cardiovascular":
            cont_vars.extend([
                ("LVEFBL", "LVEF at Baseline (%)"),
                ("SBPBL", "Systolic BP at Baseline (mmHg)"),
                ("DBPBL", "Diastolic BP at Baseline (mmHg)")
            ])

        var_list = " ".join([v[0] for v in cont_vars])

        code = self.generate_section_comment("Continuous Variables Statistics") + f"""
*-- Calculate summary statistics for continuous variables --;
%macro cont_stats(var=, label=, order=);
    proc means data=work.adsl_pop noprint;
        class TRTAN;
        var &var;
        output out=work.stats_&var
            n=n mean=mean std=std median=median min=min max=max q1=q1 q3=q3;
    run;

    data work.row_&var;
        length category $100 col1-col10 $50;
        set work.stats_&var;

        category = "&label";
        roworder = &order;

        *-- Format statistics --;
        if _TYPE_ = 0 then trt = 99;  /* Total */
        else trt = TRTAN;

        *-- N --;
        suborder = 1;
        stat = 'n';
        value = strip(put(n, 8.));
        output;

        *-- Mean (SD) --;
        suborder = 2;
        stat = 'mean_sd';
        if n > 0 then value = strip(put(mean, 8.1)) || ' (' || strip(put(std, 8.2)) || ')';
        else value = 'NA';
        output;

        *-- Median --;
        suborder = 3;
        stat = 'median';
        if n > 0 then value = strip(put(median, 8.1));
        else value = 'NA';
        output;

        *-- Q1, Q3 --;
        suborder = 4;
        stat = 'q1_q3';
        if n > 0 then value = strip(put(q1, 8.1)) || ', ' || strip(put(q3, 8.1));
        else value = 'NA';
        output;

        *-- Min, Max --;
        suborder = 5;
        stat = 'min_max';
        if n > 0 then value = strip(put(min, 8.1)) || ', ' || strip(put(max, 8.1));
        else value = 'NA';
        output;

        keep category roworder suborder stat trt value;
    run;

    proc sort data=work.row_&var; by roworder suborder trt; run;

    *-- Transpose to wide format --;
    proc transpose data=work.row_&var out=work.wide_&var(drop=_name_) prefix=col;
        by roworder suborder stat category;
        id trt;
        var value;
    run;
%mend cont_stats;

*-- Generate statistics for each continuous variable --;
"""
        # Add macro calls for each variable
        for i, (var, label) in enumerate(cont_vars, 1):
            code += f"%cont_stats(var={var}, label={label}, order={i});\n"

        # Combine all continuous results
        code += """
*-- Combine continuous variable results --;
data work.all_cont;
    set"""
        for var, _ in cont_vars:
            code += f"\n        work.wide_{var}"
        code += """
    ;
run;
"""
        return code

    def _generate_categorical_stats(self, treatments: List[Dict]) -> str:
        """Generate categorical variable statistics."""
        return self.generate_section_comment("Categorical Variables Statistics") + """
*-- Macro for categorical variable frequency counts --;
%macro cat_stats(var=, label=, fmt=, order=);
    proc freq data=work.adsl_pop noprint;
        tables TRTAN * &var / out=work.freq_&var outpct;
    run;

    *-- Add total column --;
    proc freq data=work.adsl_pop noprint;
        tables &var / out=work.freq_total_&var;
    run;

    data work.freq_total_&var;
        set work.freq_total_&var;
        TRTAN = 99;
        PCT_ROW = (COUNT / &n_total) * 100;
    run;

    data work.freq_all_&var;
        set work.freq_&var work.freq_total_&var;
    run;

    *-- Format output --;
    data work.row_&var;
        length category $100 value $50;
        set work.freq_all_&var;

        category = "&label";
        roworder = &order;

        %if &fmt ne %then %do;
            sublabel = put(&var, &fmt..);
        %end;
        %else %do;
            sublabel = strip(vvalue(&var));
        %end;

        trt = TRTAN;

        *-- n (%) format --;
        value = strip(put(COUNT, 8.)) || ' (' || strip(put(PCT_ROW, 5.1)) || '%)';

        keep category roworder sublabel trt value;
    run;

    proc sort data=work.row_&var; by roworder sublabel trt; run;

    *-- Transpose to wide format --;
    proc transpose data=work.row_&var out=work.wide_&var(drop=_name_) prefix=col;
        by roworder category sublabel;
        id trt;
        var value;
    run;
%mend cat_stats;

*-- Generate statistics for categorical variables --;
%cat_stats(var=SEX, label=Sex, fmt=$sexfmt, order=100);
%cat_stats(var=RACE, label=Race, fmt=$racefmt, order=200);
%cat_stats(var=ETHNIC, label=Ethnicity, fmt=$ethfmt, order=300);
%cat_stats(var=AGEGR1, label=Age Group, fmt=, order=400);
%cat_stats(var=BMICAT, label=BMI Category, fmt=, order=500);

*-- Combine categorical results --;
data work.all_cat;
    set work.wide_sex
        work.wide_race
        work.wide_ethnic
        work.wide_agegr1
        work.wide_bmicat
    ;
run;
"""

    def _generate_combine_results(self) -> str:
        """Generate code to combine all results."""
        return self.generate_section_comment("Combine All Results") + """
*-- Combine continuous and categorical results --;
data work.all_results;
    length row_type $10 category $100 sublabel $100 stat $20;

    *-- Continuous variables --;
    set work.all_cont(in=a);
    row_type = 'CONT';
    if a then do;
        select(stat);
            when('n') sublabel = '  n';
            when('mean_sd') sublabel = '  Mean (SD)';
            when('median') sublabel = '  Median';
            when('q1_q3') sublabel = '  Q1, Q3';
            when('min_max') sublabel = '  Min, Max';
            otherwise sublabel = stat;
        end;
        output;
    end;
run;

data work.all_cat2;
    length row_type $10 category $100 stat $20;
    set work.all_cat;
    row_type = 'CAT';
    stat = 'freq';
    *-- Indent sublabels --;
    sublabel = '  ' || strip(sublabel);
run;

data work.final_table;
    set work.all_results work.all_cat2;
run;

proc sort data=work.final_table;
    by roworder suborder;
run;

*-- Add row numbers for output --;
data work.final_table;
    set work.final_table;
    by roworder;
    if first.roworder then row_num + 1;
run;
"""

    def _generate_rtf_output(self, treatments: List[Dict]) -> str:
        """Generate RTF output code."""

        # Build column headers
        col_headers = []
        for i, trt in enumerate(treatments, 1):
            col_headers.append(f'"{trt["name"]}^n(N=&n_trt{i})"')
        col_headers.append('"Total^n(N=&n_total)"')

        return self.generate_section_comment("Generate RTF Output") + f"""
*-- Define output location --;
%let outpath = &output_path;
%let outname = t_demog;

*-- Create RTF output --;
options orientation=landscape;
ods listing close;
ods rtf file="&outpath./&outname..rtf" style=journal;

title1 "Table 14.1.1";
title2 "Demographics and Baseline Characteristics";
title3 "&population";

proc report data=work.final_table nowd split='~'
    style(report)=[outputwidth=9.5in]
    style(column)=[asis=on];

    column row_num category sublabel
           ("Treatment Group" col1 col2) col99;

    define row_num / order noprint;
    define category / order style(column)=[width=2in];
    define sublabel / display ' ' style(column)=[width=1.5in];
    define col1 / display {col_headers[0]} style(column)=[width=1.5in just=c];
    define col2 / display {col_headers[1]} style(column)=[width=1.5in just=c];
    define col99 / display {col_headers[-1]} style(column)=[width=1.5in just=c];

    compute before category;
        line ' ';
    endcomp;

    compute after category;
        line ' ';
    endcomp;
run;

ods rtf close;
ods listing;

*-- Save permanent dataset --;
data output.t_demog;
    set work.final_table;
run;

*-- Cleanup --;
proc datasets library=work nolist;
    delete adsl_pop trt_counts stats_: freq_: row_: wide_: all_:;
quit;

%put NOTE: Table 14.1.1 Demographics and Baseline Characteristics completed successfully.;
"""
