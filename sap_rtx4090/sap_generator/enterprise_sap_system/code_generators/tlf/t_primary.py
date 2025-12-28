#!/usr/bin/env python3
"""
Primary Efficacy Table Generator (t_primary.sas)
================================================

Generates SAS code for Table 14.2.1: Primary Efficacy Analysis.
Key regulatory efficacy table - supports multiple therapeutic areas.

Output: Production-ready SAS program that creates:
- Primary endpoint analysis with statistical testing
- Change from baseline summaries
- Responder analyses
- Treatment comparisons with confidence intervals
"""

import re
from typing import Dict, List, Any, Optional
from ..base import SASCodeGenerator, CodeGenerationResult


class PrimaryEfficacyTableGenerator(SASCodeGenerator):
    """Generates SAS code for primary efficacy analysis tables."""

    def __init__(self):
        super().__init__()
        self.output_name = "t_primary"
        self.table_number = "14.2.1"
        self.table_title = "Primary Efficacy Analysis"

    def generate(self, protocol_facts: Dict[str, Any]) -> CodeGenerationResult:
        """Generate complete primary efficacy table SAS program."""

        code_sections = []

        # Extract protocol information
        therapeutic_area = self._extract_therapeutic_area(protocol_facts)
        primary_endpoint = self._extract_primary_endpoint(protocol_facts)
        treatments = self._extract_treatments(protocol_facts)
        population = self._extract_population(protocol_facts)
        timepoint = self._extract_timepoint(protocol_facts)

        # Header
        code_sections.append(self.generate_header(
            program_name=f"{self.output_name}.sas",
            description=f"Table {self.table_number}: {self.table_title}",
            input_datasets=["ADSL", "ADEFF"],
            output_datasets=[self.output_name.upper()],
            macros_used=["mmrm_analysis", "responder_analysis", "ci_diff"]
        ))

        # Program setup
        code_sections.append(self._generate_setup(primary_endpoint))

        # Data preparation
        code_sections.append(self._generate_data_prep(population, primary_endpoint, timepoint))

        # Analysis based on endpoint type
        endpoint_type = self._determine_endpoint_type(primary_endpoint, therapeutic_area)

        if endpoint_type == "continuous":
            code_sections.append(self._generate_continuous_analysis(primary_endpoint, timepoint))
        elif endpoint_type == "binary":
            code_sections.append(self._generate_binary_analysis(primary_endpoint, timepoint))
        elif endpoint_type == "time_to_event":
            code_sections.append(self._generate_tte_analysis(primary_endpoint))

        # Combine results
        code_sections.append(self._generate_combine_results(endpoint_type))

        # RTF output
        code_sections.append(self._generate_rtf_output(treatments, primary_endpoint, endpoint_type))

        full_code = "\n".join(code_sections)

        return CodeGenerationResult(
            program_name=f"{self.output_name}.sas",
            code=full_code,
            description=f"Table {self.table_number}: {self.table_title} - {primary_endpoint.get('name', 'Primary Endpoint')}",
            input_datasets=["ADSL", "ADEFF"],
            output_datasets=[self.output_name.upper()],
            dependencies=["adsl.sas", "adeff.sas"],
            validation_notes=[
                "Verify primary endpoint definition matches protocol",
                "Check analysis population (ITT/mITT/PP)",
                "Validate statistical model matches SAP",
                "Confirm handling of missing data",
                "Review multiplicity adjustments if applicable"
            ]
        )

    def _extract_therapeutic_area(self, protocol_facts: Dict[str, Any]) -> str:
        """Extract therapeutic area."""
        return protocol_facts.get("therapeutic_area", "general").lower()

    def _extract_primary_endpoint(self, protocol_facts: Dict[str, Any]) -> Dict[str, Any]:
        """Extract primary endpoint information."""
        endpoint = protocol_facts.get("primary_endpoint", {})

        if not endpoint:
            # Default based on therapeutic area
            ta = protocol_facts.get("therapeutic_area", "general").lower()
            if ta == "ibd":
                endpoint = {
                    "name": "Clinical Remission",
                    "parameter": "CLREMIS",
                    "type": "binary",
                    "definition": "Mayo score <=2 with no subscore >1"
                }
            elif ta == "oncology":
                endpoint = {
                    "name": "Overall Response Rate",
                    "parameter": "ORR",
                    "type": "binary",
                    "definition": "CR or PR per RECIST 1.1"
                }
            elif ta == "rheumatology":
                endpoint = {
                    "name": "ACR20 Response",
                    "parameter": "ACR20",
                    "type": "binary",
                    "definition": "20% improvement in ACR criteria"
                }
            else:
                endpoint = {
                    "name": "Change from Baseline",
                    "parameter": "CHG",
                    "type": "continuous",
                    "definition": "Change from baseline in primary score"
                }

        return endpoint

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
        else:
            treatments = [
                {"name": "Placebo", "code": "PBO", "n": "1"},
                {"name": "Active Treatment", "code": "TRT", "n": "2"}
            ]

        return treatments

    def _extract_population(self, protocol_facts: Dict[str, Any]) -> str:
        """Extract analysis population."""
        return protocol_facts.get("efficacy_population", "ITTFL").upper()

    def _extract_timepoint(self, protocol_facts: Dict[str, Any]) -> Dict[str, Any]:
        """Extract primary analysis timepoint."""
        return protocol_facts.get("primary_timepoint", {
            "visit": "Week 12",
            "avisit": "WEEK 12",
            "avisitn": 12
        })

    def _determine_endpoint_type(self, endpoint: Dict, therapeutic_area: str) -> str:
        """Determine the type of analysis needed."""
        if "type" in endpoint:
            return endpoint["type"]

        param = endpoint.get("parameter", "").upper()

        # Binary endpoints
        if any(x in param for x in ["REMIS", "RESP", "ACR", "ORR", "CR", "PR"]):
            return "binary"

        # Time-to-event endpoints
        if any(x in param for x in ["OS", "PFS", "DFS", "TTE", "SURV"]):
            return "time_to_event"

        return "continuous"

    def _generate_setup(self, endpoint: Dict) -> str:
        """Generate program setup section."""
        return self.generate_section_comment("Program Setup") + f"""
*-- Program options --;
options nodate nonumber orientation=landscape;
ods escapechar='^';

*-- Libname assignments --;
libname adam "&adam_path" access=readonly;
libname output "&output_path";

*-- Macro variables for primary endpoint --;
%let endpoint_name = {endpoint.get('name', 'Primary Endpoint')};
%let endpoint_param = {endpoint.get('parameter', 'CHG')};
%let endpoint_def = {endpoint.get('definition', '')};

*-- Analysis population --;
%let population = Intent-to-Treat Population;
%let popflag = ITTFL;

*-- Significance level --;
%let alpha = 0.05;
%let conf_level = 95;
"""

    def _generate_data_prep(self, population: str, endpoint: Dict, timepoint: Dict) -> str:
        """Generate data preparation code."""
        param = endpoint.get("parameter", "CHG")
        avisit = timepoint.get("avisit", "WEEK 12")

        return self.generate_section_comment("Data Preparation") + f"""
*-- Get analysis population from ADSL --;
data work.pop;
    set adam.adsl;
    where {population} = 'Y';
    keep USUBJID TRTAN TRTA SITEID;
run;

*-- Get treatment counts --;
proc sql noprint;
    select count(*) into :n_total trimmed from work.pop;
    select count(*) into :n_trt1 trimmed from work.pop where TRTAN = 1;
    select count(*) into :n_trt2 trimmed from work.pop where TRTAN = 2;
quit;

*-- Prepare efficacy data --;
data work.eff;
    merge adam.adeff(in=a where=(PARAMCD = "{param}"))
          work.pop(in=b);
    by USUBJID;
    if a and b;
run;

*-- Primary analysis timepoint --;
data work.eff_primary;
    set work.eff;
    where upcase(AVISIT) = "{avisit}";
run;

*-- All post-baseline for repeated measures --;
data work.eff_all;
    set work.eff;
    where AVISITN > 0;
run;

*-- Baseline values --;
data work.eff_base;
    set work.eff;
    where ABLFL = 'Y';
    keep USUBJID BASE;
run;

*-- Merge baseline --;
data work.eff_primary;
    merge work.eff_primary(in=a) work.eff_base;
    by USUBJID;
    if a;
run;

proc sort data=work.eff_primary; by TRTAN; run;
"""

    def _generate_continuous_analysis(self, endpoint: Dict, timepoint: Dict) -> str:
        """Generate analysis for continuous endpoints."""
        return self.generate_section_comment("Continuous Endpoint Analysis") + """
*-- Descriptive statistics by treatment --;
proc means data=work.eff_primary noprint;
    class TRTAN;
    var BASE AVAL CHG;
    output out=work.desc_stats
        n=n_base n_aval n_chg
        mean=mean_base mean_aval mean_chg
        std=std_base std_aval std_chg
        median=median_base median_aval median_chg
        min=min_base min_aval min_chg
        max=max_base max_aval max_chg;
run;

*-- ANCOVA analysis: Change from baseline with baseline as covariate --;
proc mixed data=work.eff_primary;
    class TRTAN SITEID;
    model CHG = TRTAN BASE SITEID / solution ddfm=kr;
    lsmeans TRTAN / diff cl alpha=&alpha;
    ods output LSMeans=work.lsmeans Diffs=work.diffs;
run;

*-- Format LS means --;
data work.lsmeans_fmt;
    length stat $50 value $50;
    set work.lsmeans;

    roworder = 1;
    category = 'LS Mean Change from Baseline';
    trt = TRTAN;

    stat = 'lsmean';
    value = strip(put(Estimate, 8.2)) || ' (' || strip(put(StdErr, 8.3)) || ')';
    output;

    stat = 'ci';
    value = '(' || strip(put(Lower, 8.2)) || ', ' || strip(put(Upper, 8.2)) || ')';
    output;

    keep roworder category stat trt value;
run;

*-- Format treatment difference --;
data work.diff_fmt;
    length stat $50 value $50;
    set work.diffs;
    where TRTAN = 2 and _TRTAN = 1;  /* Active vs Placebo */

    roworder = 2;
    category = 'Treatment Difference (Active - Placebo)';
    trt = 99;

    stat = 'diff';
    value = strip(put(Estimate, 8.2)) || ' (' || strip(put(StdErr, 8.3)) || ')';
    output;

    stat = 'ci';
    value = '(' || strip(put(Lower, 8.2)) || ', ' || strip(put(Upper, 8.2)) || ')';
    output;

    stat = 'pvalue';
    if Probt < 0.001 then value = '<0.001';
    else value = strip(put(Probt, pvalue6.4));
    output;

    keep roworder category stat trt value;
run;

*-- Format descriptive statistics --;
data work.desc_fmt;
    length category $100 stat $50 value $50;
    set work.desc_stats;
    where _TYPE_ = 1;

    *-- Baseline --;
    roworder = 0.1;
    category = 'Baseline';
    trt = TRTAN;

    stat = 'n';
    value = strip(put(n_base, 8.));
    output;

    stat = 'mean_sd';
    value = strip(put(mean_base, 8.2)) || ' (' || strip(put(std_base, 8.3)) || ')';
    output;

    stat = 'median';
    value = strip(put(median_base, 8.2));
    output;

    stat = 'range';
    value = strip(put(min_base, 8.1)) || ', ' || strip(put(max_base, 8.1));
    output;

    *-- Post-baseline --;
    roworder = 0.2;
    category = 'Week 12';

    stat = 'n';
    value = strip(put(n_aval, 8.));
    output;

    stat = 'mean_sd';
    value = strip(put(mean_aval, 8.2)) || ' (' || strip(put(std_aval, 8.3)) || ')';
    output;

    stat = 'median';
    value = strip(put(median_aval, 8.2));
    output;

    stat = 'range';
    value = strip(put(min_aval, 8.1)) || ', ' || strip(put(max_aval, 8.1));
    output;

    *-- Change --;
    roworder = 0.3;
    category = 'Change from Baseline';

    stat = 'n';
    value = strip(put(n_chg, 8.));
    output;

    stat = 'mean_sd';
    value = strip(put(mean_chg, 8.2)) || ' (' || strip(put(std_chg, 8.3)) || ')';
    output;

    stat = 'median';
    value = strip(put(median_chg, 8.2));
    output;

    stat = 'range';
    value = strip(put(min_chg, 8.1)) || ', ' || strip(put(max_chg, 8.1));
    output;

    keep roworder category stat trt value;
run;

*-- Combine continuous analysis results --;
data work.analysis_results;
    set work.desc_fmt work.lsmeans_fmt work.diff_fmt;
run;
"""

    def _generate_binary_analysis(self, endpoint: Dict, timepoint: Dict) -> str:
        """Generate analysis for binary endpoints."""
        return self.generate_section_comment("Binary Endpoint Analysis") + """
*-- Derive responder flag if not present --;
data work.eff_resp;
    set work.eff_primary;

    *-- Assume AVALC contains response category or use CRIT1FL --;
    if CRIT1FL = 'Y' then responder = 1;
    else if CRIT1FL = 'N' then responder = 0;
    else if upcase(AVALC) in ('Y' 'YES' 'RESPONDER' 'CR' 'PR') then responder = 1;
    else responder = 0;
run;

*-- Response rates by treatment --;
proc freq data=work.eff_resp noprint;
    tables TRTAN * responder / out=work.resp_freq outpct;
run;

*-- Calculate response rates --;
data work.resp_rates;
    set work.resp_freq;
    where responder = 1;
    rate = COUNT / (COUNT + (select(COUNT) from work.resp_freq
                    where TRTAN = work.resp_freq.TRTAN and responder = 0));
run;

*-- CMH test stratified by site --;
proc freq data=work.eff_resp;
    tables SITEID * TRTAN * responder / cmh noprint;
    output out=work.cmh_test cmh;
run;

*-- Cochran-Mantel-Haenszel test --;
proc freq data=work.eff_resp;
    tables TRTAN * responder / riskdiff(cl=exact) cmh;
    ods output CrossTabFreqs=work.crosstab
               RiskDiffCol1=work.riskdiff
               CMH=work.cmh;
run;

*-- Format response rates --;
data work.resp_fmt;
    length category $100 stat $50 value $50;
    set work.resp_freq;
    where responder = 1;

    roworder = 1;
    category = 'Response Rate';
    trt = TRTAN;

    *-- n/N (%) --;
    stat = 'n_pct';
    value = strip(put(COUNT, 8.)) || '/' ||
            strip(put(COUNT + (sum(COUNT) - COUNT), 8.)) || ' (' ||
            strip(put(PCT_ROW, 5.1)) || '%)';
    output;

    keep roworder category stat trt value;
run;

*-- Risk difference and CI --;
data work.diff_fmt;
    length category $100 stat $50 value $50;
    set work.riskdiff;

    roworder = 2;
    category = 'Treatment Difference (Active - Placebo)';
    trt = 99;

    stat = 'diff';
    value = strip(put(Risk * 100, 8.1)) || '%';
    output;

    stat = 'ci';
    value = '(' || strip(put(LowerCL * 100, 8.1)) || '%, ' ||
            strip(put(UpperCL * 100, 8.1)) || '%)';
    output;

    keep roworder category stat trt value;
run;

*-- P-value from CMH --;
data work.pval_fmt;
    length category $100 stat $50 value $50;
    set work.cmh;
    where Statistic = 'CMH';

    roworder = 2;
    category = 'Treatment Difference (Active - Placebo)';
    trt = 99;
    stat = 'pvalue';

    if Prob < 0.001 then value = '<0.001';
    else value = strip(put(Prob, pvalue6.4));

    keep roworder category stat trt value;
run;

*-- Combine binary analysis results --;
data work.analysis_results;
    set work.resp_fmt work.diff_fmt work.pval_fmt;
run;
"""

    def _generate_tte_analysis(self, endpoint: Dict) -> str:
        """Generate analysis for time-to-event endpoints."""
        return self.generate_section_comment("Time-to-Event Analysis") + """
*-- Prepare TTE data --;
data work.tte;
    merge adam.adtte(in=a where=(PARAMCD = "&endpoint_param"))
          work.pop(in=b);
    by USUBJID;
    if a and b;
run;

*-- Kaplan-Meier estimates --;
proc lifetest data=work.tte method=km plots=none outsurv=work.km_est;
    time AVAL * CNSR(1);
    strata TRTAN;
run;

*-- Median survival and CI --;
proc lifetest data=work.tte method=km;
    time AVAL * CNSR(1);
    strata TRTAN;
    ods output Quartiles=work.medians;
run;

*-- Cox regression for hazard ratio --;
proc phreg data=work.tte;
    class TRTAN(ref='1') SITEID;
    model AVAL * CNSR(1) = TRTAN SITEID / risklimits;
    hazardratio TRTAN / diff=ref;
    ods output HazardRatios=work.hr ParameterEstimates=work.cox_est;
run;

*-- Log-rank test --;
proc lifetest data=work.tte method=km;
    time AVAL * CNSR(1);
    strata TRTAN;
    ods output HomTests=work.logrank;
run;

*-- Format median survival --;
data work.median_fmt;
    length category $100 stat $50 value $50;
    set work.medians;
    where Percent = 50;

    roworder = 1;
    category = 'Median Survival (months)';
    trt = input(scan(Stratum, 2, '='), best.);

    stat = 'median';
    value = strip(put(Estimate, 8.1)) || ' (' ||
            strip(put(LowerLimit, 8.1)) || ', ' ||
            strip(put(UpperLimit, 8.1)) || ')';

    keep roworder category stat trt value;
run;

*-- Format hazard ratio --;
data work.hr_fmt;
    length category $100 stat $50 value $50;
    set work.hr;

    roworder = 2;
    category = 'Hazard Ratio (Active vs Placebo)';
    trt = 99;

    stat = 'hr';
    value = strip(put(HazardRatio, 8.3)) || ' (' ||
            strip(put(HRLowerCL, 8.3)) || ', ' ||
            strip(put(HRUpperCL, 8.3)) || ')';

    keep roworder category stat trt value;
run;

*-- Format p-value --;
data work.pval_fmt;
    length category $100 stat $50 value $50;
    set work.logrank;
    where Test = 'Log-Rank';

    roworder = 2;
    category = 'Hazard Ratio (Active vs Placebo)';
    trt = 99;
    stat = 'pvalue';

    if ProbChiSq < 0.001 then value = '<0.001';
    else value = strip(put(ProbChiSq, pvalue6.4));

    keep roworder category stat trt value;
run;

*-- Event counts --;
proc sql;
    create table work.events as
    select TRTAN as trt,
           sum(case when CNSR = 0 then 1 else 0 end) as events,
           count(*) as n
    from work.tte
    group by TRTAN;
quit;

data work.event_fmt;
    length category $100 stat $50 value $50;
    set work.events;

    roworder = 0;
    category = 'Events / N';
    stat = 'events';
    value = strip(put(events, 8.)) || ' / ' || strip(put(n, 8.));

    keep roworder category stat trt value;
run;

*-- Combine TTE analysis results --;
data work.analysis_results;
    set work.event_fmt work.median_fmt work.hr_fmt work.pval_fmt;
run;
"""

    def _generate_combine_results(self, endpoint_type: str) -> str:
        """Generate code to combine all results."""
        return self.generate_section_comment("Combine and Format Results") + """
*-- Sort analysis results --;
proc sort data=work.analysis_results;
    by roworder stat trt;
run;

*-- Transpose to wide format --;
proc transpose data=work.analysis_results out=work.results_wide(drop=_name_) prefix=col;
    by roworder category stat;
    id trt;
    var value;
run;

*-- Create display labels --;
data work.final_table;
    length display_cat $100 display_stat $50;
    set work.results_wide;

    display_cat = category;

    select(stat);
        when('n') display_stat = '  n';
        when('mean_sd') display_stat = '  Mean (SD)';
        when('median') display_stat = '  Median';
        when('range') display_stat = '  Min, Max';
        when('lsmean') display_stat = '  LS Mean (SE)';
        when('ci') display_stat = '  95% CI';
        when('diff') display_stat = '  Difference (SE)';
        when('pvalue') display_stat = '  p-value';
        when('n_pct') display_stat = '  n/N (%)';
        when('hr') display_stat = '  HR (95% CI)';
        when('events') display_stat = '  Events/N';
        otherwise display_stat = '  ' || stat;
    end;
run;

proc sort data=work.final_table;
    by roworder stat;
run;
"""

    def _generate_rtf_output(self, treatments: List[Dict], endpoint: Dict, endpoint_type: str) -> str:
        """Generate RTF output code."""
        return self.generate_section_comment("Generate RTF Output") + f"""
*-- Define output location --;
%let outpath = &output_path;
%let outname = t_primary;

*-- Create RTF output --;
options orientation=landscape;
ods listing close;
ods rtf file="&outpath./&outname..rtf" style=journal;

title1 "Table 14.2.1";
title2 "Primary Efficacy Analysis: &endpoint_name";
title3 "&population";
title4 "Analysis at Primary Timepoint";

footnote1 "Primary endpoint: &endpoint_def";
%if {endpoint_type} = continuous %then %do;
    footnote2 "Analysis: ANCOVA with baseline as covariate and site as fixed effect";
    footnote3 "LS = Least squares; SE = Standard error; CI = Confidence interval";
%end;
%else %if {endpoint_type} = binary %then %do;
    footnote2 "Analysis: Cochran-Mantel-Haenszel test stratified by site";
    footnote3 "CI = Confidence interval for risk difference";
%end;
%else %do;
    footnote2 "Analysis: Cox proportional hazards model stratified by site";
    footnote3 "HR = Hazard ratio; CI = Confidence interval";
%end;

proc report data=work.final_table nowd split='~'
    style(report)=[outputwidth=9.5in]
    style(column)=[asis=on];

    column roworder display_cat display_stat
           ("Treatment Group" col1 col2) col99;

    define roworder / order noprint;
    define display_cat / order style(column)=[width=2in];
    define display_stat / display ' ' style(column)=[width=1.5in];
    define col1 / display "Placebo~(N=&n_trt1)" style(column)=[width=1.5in just=c];
    define col2 / display "Active~(N=&n_trt2)" style(column)=[width=1.5in just=c];
    define col99 / display "Difference" style(column)=[width=1.5in just=c];

    compute before display_cat;
        line ' ';
    endcomp;
run;

ods rtf close;
ods listing;

*-- Save permanent dataset --;
data output.t_primary;
    set work.final_table;
run;

*-- Cleanup --;
proc datasets library=work nolist;
    delete pop eff: desc_: lsmeans: diff_: resp_: hr_: median_: pval_:
           event_: km_: cox_: cmh: logrank crosstab riskdiff
           analysis_results results_wide final_table;
quit;

%put NOTE: Table 14.2.1 Primary Efficacy Analysis completed successfully.;
"""
