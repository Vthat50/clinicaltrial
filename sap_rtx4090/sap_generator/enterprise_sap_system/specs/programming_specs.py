#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Programming Specifications
================================================================
PRODUCTION-LEVEL SAS programming specifications and code templates.

Generates detailed, executable SAS code templates that programmers
can use directly with minimal modification.

This includes:
- Analysis procedure templates
- Macro calls with parameters
- QC specifications
- Output dataset requirements
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
class SASMacroCall:
    """SAS macro call specification"""
    macro_name: str
    parameters: Dict[str, str]
    description: str
    output_datasets: List[str]
    output_files: List[str]


@dataclass
class SASProcedure:
    """SAS procedure template"""
    procedure: str  # PROC name
    purpose: str
    input_dataset: str
    code_template: str
    key_statements: List[str]
    options: Dict[str, str]
    output_description: str


@dataclass
class AnalysisProgramSpec:
    """Complete specification for an analysis program"""
    program_name: str
    title: str
    purpose: str
    input_datasets: List[str]
    output_datasets: List[str]
    output_tlf: List[str]
    statistical_method: str
    sas_code_template: str
    validation_requirements: List[str]
    qc_checks: List[str]


class ProgrammingSpecGenerator:
    """
    Generates production-level SAS programming specifications.
    These are executable code templates that programmers can adapt.
    """

    # MMRM (Mixed Model for Repeated Measures) template
    MMRM_TEMPLATE = """
/*============================================================================*/
/* Program: {program_name}                                                     */
/* Purpose: {purpose}                                                          */
/* Analysis: Mixed Model for Repeated Measures (MMRM)                         */
/* Author: [Programmer Name]                                                   */
/* Date: [Date]                                                                */
/*============================================================================*/

/* Input datasets: {input_datasets} */
/* Output datasets: {output_datasets} */

/*--- Libnames and options ---*/
libname adam "/path/to/adam" access=readonly;
libname output "/path/to/output";

options mprint symbolgen;

/*--- Create analysis dataset ---*/
proc sql;
    create table work.analysis as
    select a.usubjid,
           a.trtp,
           a.trtpn,
           a.paramcd,
           a.param,
           a.avisit,
           a.avisitn,
           a.aval,
           a.chg,
           a.base,
           a.ablfl,
           b.{strat1} as strat1,
           b.{strat2} as strat2
    from adam.{efficacy_dataset} a
    inner join adam.adsl b
        on a.usubjid = b.usubjid
    where a.paramcd = "{paramcd}"
      and a.ittfl = "Y"
      and a.anl01fl = "Y"
    order by a.usubjid, a.avisitn;
quit;

/*--- MMRM Analysis ---*/
/* Model: CHG = TRT VISIT TRT*VISIT BASE STRAT1 STRAT2 */
/* Covariance: Unstructured */
/* Degrees of Freedom: Kenward-Roger */

ods output LSMeans=lsmeans
           Diffs=diffs
           CovParms=covparms
           Tests3=tests3;

proc mixed data=work.analysis method=reml;
    class usubjid trtp(ref="{ref_trt}") avisit strat1 strat2;
    model chg = trtp avisit trtp*avisit base strat1 strat2 / ddfm=kr;
    repeated avisit / subject=usubjid type=un r rcorr;
    lsmeans trtp*avisit / cl diff;
run;

ods output close;

/*--- Extract results at primary timepoint ---*/
proc sql;
    create table work.primary_results as
    select a.avisit,
           a.trtp,
           a.estimate as lsmean,
           a.stderr,
           a.lower as lsmean_lcl,
           a.upper as lsmean_ucl,
           b.estimate as diff,
           b.stderr as diff_se,
           b.lower as diff_lcl,
           b.upper as diff_ucl,
           b.probt as pvalue
    from lsmeans a
    left join diffs b
        on a.avisit = b.avisit
        and a.trtp = b._trtp
    where a.avisit = "{primary_timepoint}";
quit;

/*--- Create output dataset ---*/
data output.{output_dataset};
    set work.primary_results;
    format lsmean lsmean_lcl lsmean_ucl diff diff_lcl diff_ucl 8.2
           pvalue pvalue6.4;
    label lsmean = "LS Mean"
          diff = "LS Mean Difference"
          diff_lcl = "95% CI Lower"
          diff_ucl = "95% CI Upper"
          pvalue = "p-value";
run;

/*--- QC Output ---*/
proc print data=output.{output_dataset};
    title "MMRM Results - {param}";
run;
"""

    # Kaplan-Meier / Log-rank template
    SURVIVAL_TEMPLATE = """
/*============================================================================*/
/* Program: {program_name}                                                     */
/* Purpose: {purpose}                                                          */
/* Analysis: Time-to-Event (Kaplan-Meier, Log-rank, Cox)                      */
/* Author: [Programmer Name]                                                   */
/* Date: [Date]                                                                */
/*============================================================================*/

/* Input datasets: ADTTE, ADSL */
/* Output datasets: {output_datasets} */

/*--- Libnames ---*/
libname adam "/path/to/adam" access=readonly;
libname output "/path/to/output";

options mprint symbolgen;

/*--- Create analysis dataset ---*/
proc sql;
    create table work.tte_analysis as
    select a.usubjid,
           a.trtp,
           a.trtpn,
           a.paramcd,
           a.param,
           a.aval,
           a.aval / 30.4375 as aval_months,  /* Convert days to months */
           a.cnsr,
           a.evntdesc,
           a.startdt,
           a.adt,
           b.{strat1} as strat1,
           b.{strat2} as strat2
    from adam.adtte a
    inner join adam.adsl b
        on a.usubjid = b.usubjid
    where a.paramcd = "{paramcd}"
      and a.ittfl = "Y"
    order by a.trtpn, a.aval;
quit;

/*--- Kaplan-Meier Estimates ---*/
ods output ProductLimitEstimates=km_est
           Quartiles=km_quartiles
           HomTests=logrank_test;

proc lifetest data=work.tte_analysis
              plots=survival(atrisk cb=hw test)
              method=km
              alpha=0.05;
    time aval_months*cnsr(1);
    strata trtp / test=logrank;
    ods select ProductLimitEstimates Quartiles HomTests SurvivalPlot;
run;

ods output close;

/*--- Cox Proportional Hazards (Stratified) ---*/
ods output ParameterEstimates=cox_params
           HazardRatios=hazard_ratios;

proc phreg data=work.tte_analysis;
    class trtp(ref="{ref_trt}") strat1 strat2;
    model aval_months*cnsr(1) = trtp / ties=efron rl=wald;
    strata strat1 strat2;
    hazardratio trtp / diff=ref;
run;

ods output close;

/*--- Extract median survival and event rates ---*/
proc sql;
    /* Median survival by treatment */
    create table work.median_surv as
    select trtp,
           estimate as median_months,
           lowerlimit as median_lcl,
           upperlimit as median_ucl
    from km_quartiles
    where percent = 50;

    /* Event counts */
    create table work.event_counts as
    select trtp,
           sum(cnsr = 0) as n_events,
           sum(cnsr = 1) as n_censored,
           count(*) as n_total,
           sum(cnsr = 0) / count(*) * 100 as event_pct format=5.1
    from work.tte_analysis
    group by trtp;
quit;

/*--- Survival rates at specific timepoints ---*/
%macro surv_rate(timepoint=, var_suffix=);
    proc sql;
        create table work.surv_&var_suffix as
        select trtp,
               1 - failure as surv_rate_&var_suffix,
               1 - (failure + stderr_f) as surv_lcl_&var_suffix,
               1 - (failure - stderr_f) as surv_ucl_&var_suffix
        from km_est
        where timelist = &timepoint
        group by trtp
        having aval_months = max(aval_months);
    quit;
%mend;

%surv_rate(timepoint=6, var_suffix=6mo);
%surv_rate(timepoint=12, var_suffix=12mo);

/*--- Combine results ---*/
data output.{output_dataset};
    merge work.event_counts
          work.median_surv
          work.surv_6mo
          work.surv_12mo
          ;
    by trtp;

    /* Add hazard ratio from Cox model */
    if _n_ = 1 then set hazard_ratios(rename=(hazardratio=hr pointestimate=hr2
                                               waldlower=hr_lcl waldupper=hr_ucl));

    /* Add log-rank p-value */
    if _n_ = 1 then set logrank_test(where=(test="Log-Rank") keep=test probchisq
                                      rename=(probchisq=logrank_pvalue));

    format hr hr_lcl hr_ucl 5.2
           median_months median_lcl median_ucl 5.1
           surv_rate_6mo surv_rate_12mo percent7.1
           logrank_pvalue pvalue6.4;
run;

/*--- Generate Kaplan-Meier Plot ---*/
ods graphics on / width=10in height=8in imagefmt=png;
ods listing gpath="/path/to/figures";

proc lifetest data=work.tte_analysis
              plots=survival(atrisk(atrisktickonly outside)
                            cb=hw nocensor
                            test);
    time aval_months*cnsr(1);
    strata trtp;
    ods select SurvivalPlot;
run;

ods graphics off;
"""

    # Binary endpoint (response rate) template
    BINARY_TEMPLATE = """
/*============================================================================*/
/* Program: {program_name}                                                     */
/* Purpose: {purpose}                                                          */
/* Analysis: Binary Endpoint (Response Rate, CMH Test)                        */
/* Author: [Programmer Name]                                                   */
/* Date: [Date]                                                                */
/*============================================================================*/

/* Input datasets: {efficacy_dataset}, ADSL */
/* Output datasets: {output_datasets} */

/*--- Libnames ---*/
libname adam "/path/to/adam" access=readonly;
libname output "/path/to/output";

/*--- Create analysis dataset ---*/
proc sql;
    create table work.response_analysis as
    select a.usubjid,
           a.trtp,
           a.trtpn,
           a.paramcd,
           a.param,
           a.avisit,
           a.avalc,
           a.crit1fl,
           case when a.crit1fl = "Y" then 1
                when a.crit1fl = "N" then 0
                else . end as response,
           b.{strat1} as strat1,
           b.{strat2} as strat2
    from adam.{efficacy_dataset} a
    inner join adam.adsl b
        on a.usubjid = b.usubjid
    where a.paramcd = "{paramcd}"
      and a.avisit = "{primary_timepoint}"
      and a.ittfl = "Y"
      and a.anl01fl = "Y";
quit;

/*--- Response rates by treatment ---*/
proc freq data=work.response_analysis;
    tables trtp * response / nocum nopercent;
    ods output CrossTabFreqs=response_counts;
run;

proc sql;
    create table work.response_rates as
    select trtp,
           sum(response = 1) as n_responders,
           count(*) as n_total,
           sum(response = 1) / count(*) * 100 as response_rate,
           (select count(*) from work.response_analysis
            where trtp = a.trtp and response is not null) as n_evaluable
    from work.response_analysis a
    where response is not null
    group by trtp;
quit;

/*--- CMH test (stratified) ---*/
ods output CMH=cmh_test;

proc freq data=work.response_analysis;
    tables strat1 * strat2 * trtp * response / cmh noprint;
run;

ods output close;

/*--- Exact 95% CI for response rates (Clopper-Pearson) ---*/
%macro exact_ci(data=, group=, n=, response=);
    proc freq data=&data;
        where &group = "&response";
        tables response / binomial(exact cl=clopperpearson);
        ods output BinomialCLs=ci_&response;
    run;
%mend;

/*--- Difference in proportions with Newcombe-Wilson CI ---*/
proc freq data=work.response_analysis;
    tables trtp * response / riskdiff(cl=newcombe) norow nocol;
    ods output RiskDiffCol1=risk_diff;
run;

/*--- Combine results ---*/
data output.{output_dataset};
    length statistic $50;

    /* Response rates */
    set work.response_rates;

    /* Add CIs and difference */
    /* [Further processing to add exact CIs and CMH p-value] */

    format response_rate 5.1;
run;

/*--- Display results ---*/
proc print data=output.{output_dataset} noobs;
    title "Response Rate Analysis - {param}";
    title2 "Primary Timepoint: {primary_timepoint}";
run;
"""

    # Subgroup analysis template
    SUBGROUP_TEMPLATE = """
/*============================================================================*/
/* Program: {program_name}                                                     */
/* Purpose: Subgroup Analysis - Forest Plot Data                              */
/* Author: [Programmer Name]                                                   */
/*============================================================================*/

/*--- Define subgroups ---*/
%let subgroups = AGEGR1 SEX RACE REGION ECOG;

/*--- Macro to calculate subgroup effect ---*/
%macro subgroup_analysis(var=, label=);

    proc sort data=work.analysis out=work.temp_&var;
        by &var;
    run;

    /* For time-to-event endpoints */
    ods output ParameterEstimates=pe_&var;
    proc phreg data=work.temp_&var;
        by &var;
        class trtp(ref="{ref_trt}");
        model aval*cnsr(1) = trtp / rl;
        hazardratio trtp / diff=ref;
    run;
    ods output close;

    /* Compile results */
    data subgroup_&var;
        set pe_&var;
        length subgroup subgroup_level $100;
        subgroup = "&label";
        subgroup_level = &var;
        hr = exp(estimate);
        hr_lcl = exp(estimate - 1.96 * stderr);
        hr_ucl = exp(estimate + 1.96 * stderr);
        keep subgroup subgroup_level hr hr_lcl hr_ucl;
    run;

%mend;

/*--- Run for all subgroups ---*/
%subgroup_analysis(var=agegr1, label=Age Group);
%subgroup_analysis(var=sex, label=Sex);
%subgroup_analysis(var=race, label=Race);

/*--- Combine all subgroup results ---*/
data output.subgroup_forest;
    set subgroup_:;
run;

/*--- Create forest plot ---*/
ods graphics on / width=10in height=8in;
ods listing gpath="/path/to/figures";

proc sgplot data=output.subgroup_forest;
    scatter y=subgroup_level x=hr / xerrorlower=hr_lcl xerrorupper=hr_ucl
            markerattrs=(symbol=squarefilled size=10);
    refline 1 / axis=x lineattrs=(pattern=dash);
    xaxis type=log label="Hazard Ratio (95% CI)" values=(0.25 0.5 1 2 4);
    yaxis label=" " discreteorder=data;
    title "Subgroup Analysis - Forest Plot";
run;

ods graphics off;
"""

    def __init__(self, llm_client=None):
        """Initialize the programming spec generator"""
        self.llm_client = llm_client

    def generate_mmrm_spec(
        self,
        protocol: ParsedProtocol,
        estimands: Dict[str, Any],
        paramcd: str = "PRIMARY",
        primary_timepoint: str = "Week 12"
    ) -> AnalysisProgramSpec:
        """Generate MMRM analysis programming specification"""

        # Determine stratification factors
        strat_factors = protocol.stratification_factors or ["REGION", "BASELINE_SEVERITY"]

        code = self.MMRM_TEMPLATE.format(
            program_name="an_mmrm_primary",
            purpose="Primary Efficacy Analysis - Change from Baseline (MMRM)",
            input_datasets="ADEFF, ADSL",
            output_datasets="an_mmrm_primary",
            efficacy_dataset="ADEFF",
            paramcd=paramcd,
            ref_trt="Placebo",
            strat1=strat_factors[0] if len(strat_factors) > 0 else "REGION",
            strat2=strat_factors[1] if len(strat_factors) > 1 else "BLSEV",
            primary_timepoint=primary_timepoint,
            output_dataset="an_mmrm_primary",
            param="Primary Endpoint"
        )

        return AnalysisProgramSpec(
            program_name="an_mmrm_primary.sas",
            title="MMRM Analysis for Primary Efficacy Endpoint",
            purpose="Analyze change from baseline in primary endpoint using Mixed Model for Repeated Measures",
            input_datasets=["ADEFF", "ADSL"],
            output_datasets=["an_mmrm_primary"],
            output_tlf=["14.2.1", "14.2.2"],
            statistical_method="Mixed Model for Repeated Measures with unstructured covariance",
            sas_code_template=code,
            validation_requirements=[
                "Double programming by independent programmer",
                "Compare LS means, standard errors, and p-values to 4 decimal places",
                "Verify model convergence (check ODS output)",
                "Validate subject counts match ADSL population counts"
            ],
            qc_checks=[
                "N in analysis matches ITTFL = 'Y' count in ADSL",
                "Baseline values match ABLFL = 'Y' records in ADEFF",
                "No duplicate subjects in analysis",
                "Model converged successfully",
                "Residual diagnostics acceptable"
            ]
        )

    def generate_survival_spec(
        self,
        protocol: ParsedProtocol,
        estimands: Dict[str, Any],
        endpoint_type: EndpointType,
        paramcd: str = "OS"
    ) -> AnalysisProgramSpec:
        """Generate time-to-event analysis programming specification"""

        strat_factors = protocol.stratification_factors or ["REGION", "ECOG"]

        code = self.SURVIVAL_TEMPLATE.format(
            program_name=f"an_tte_{paramcd.lower()}",
            purpose=f"Time-to-Event Analysis - {endpoint_type.value}",
            output_datasets=f"an_tte_{paramcd.lower()}",
            paramcd=paramcd,
            ref_trt="Control",
            strat1=strat_factors[0] if len(strat_factors) > 0 else "REGION",
            strat2=strat_factors[1] if len(strat_factors) > 1 else "ECOG",
            output_dataset=f"an_tte_{paramcd.lower()}"
        )

        return AnalysisProgramSpec(
            program_name=f"an_tte_{paramcd.lower()}.sas",
            title=f"Time-to-Event Analysis: {endpoint_type.value}",
            purpose=f"Kaplan-Meier, log-rank test, and Cox PH analysis for {endpoint_type.value}",
            input_datasets=["ADTTE", "ADSL"],
            output_datasets=[f"an_tte_{paramcd.lower()}"],
            output_tlf=["14.2.1", "14.2.F1"],
            statistical_method="Kaplan-Meier, Stratified Log-rank, Stratified Cox PH",
            sas_code_template=code,
            validation_requirements=[
                "Double programming by independent programmer",
                "Compare median survival to 1 decimal place",
                "Compare HR and 95% CI to 2 decimal places",
                "Verify event/censoring counts match source data",
                "Validate Kaplan-Meier curve against raw data"
            ],
            qc_checks=[
                "N events + N censored = N in population",
                "All subjects have valid AVAL > 0",
                "CNSR values are only 0 or 1",
                "Stratification factors match protocol",
                "Log-rank and Cox model use same strata"
            ]
        )

    def generate_binary_spec(
        self,
        protocol: ParsedProtocol,
        estimands: Dict[str, Any],
        paramcd: str = "RESPONSE",
        primary_timepoint: str = "Week 8"
    ) -> AnalysisProgramSpec:
        """Generate binary endpoint analysis programming specification"""

        strat_factors = protocol.stratification_factors or ["REGION"]

        code = self.BINARY_TEMPLATE.format(
            program_name="an_response_primary",
            purpose="Response Rate Analysis at Primary Timepoint",
            efficacy_dataset="ADEFF",
            output_datasets="an_response_primary",
            paramcd=paramcd,
            primary_timepoint=primary_timepoint,
            ref_trt="Placebo",
            strat1=strat_factors[0] if len(strat_factors) > 0 else "REGION",
            strat2=strat_factors[1] if len(strat_factors) > 1 else "BASELINE",
            output_dataset="an_response_primary",
            param="Response Rate"
        )

        return AnalysisProgramSpec(
            program_name="an_response_primary.sas",
            title="Binary Endpoint Analysis - Response Rate",
            purpose=f"Analyze response rate at {primary_timepoint} with stratified CMH test",
            input_datasets=["ADEFF", "ADSL"],
            output_datasets=["an_response_primary"],
            output_tlf=["14.2.1"],
            statistical_method="Cochran-Mantel-Haenszel test, Newcombe-Wilson CI for difference",
            sas_code_template=code,
            validation_requirements=[
                "Double programming by independent programmer",
                "Compare response rates and 95% CIs",
                "Verify CMH p-value matches",
                "Validate n responders against source records"
            ],
            qc_checks=[
                "Response defined correctly per CRIT1FL",
                "Denominator includes all evaluable subjects",
                "Non-evaluable subjects not counted in rate",
                "Stratification factors match randomization strata"
            ]
        )

    def generate_all_specs(
        self,
        protocol: ParsedProtocol,
        estimands: Dict[str, Any]
    ) -> List[AnalysisProgramSpec]:
        """Generate all analysis programming specifications"""

        specs = []

        endpoint_type = EndpointType.OTHER
        if protocol.primary_estimand:
            endpoint_type = protocol.primary_estimand.variable_type

        # Generate based on endpoint type
        if endpoint_type in [EndpointType.OS, EndpointType.PFS, EndpointType.DFS, EndpointType.EFS]:
            # Time-to-event analysis
            paramcd = endpoint_type.value.replace(" ", "").upper()[:3]
            specs.append(self.generate_survival_spec(protocol, estimands, endpoint_type, paramcd))

        elif endpoint_type == EndpointType.ORR:
            # Binary response analysis
            specs.append(self.generate_binary_spec(protocol, estimands, "BOR", "End of Treatment"))

        elif endpoint_type == EndpointType.EFFICACY:
            # Continuous outcome (MMRM)
            specs.append(self.generate_mmrm_spec(protocol, estimands))
            # Also add response rate if applicable
            specs.append(self.generate_binary_spec(protocol, estimands, "RESPONSE", "Week 8"))

        else:
            # Default to MMRM
            specs.append(self.generate_mmrm_spec(protocol, estimands))

        return specs

    def generate_programming_document(
        self,
        protocol: ParsedProtocol,
        estimands: Dict[str, Any]
    ) -> str:
        """Generate complete programming specifications document"""

        specs = self.generate_all_specs(protocol, estimands)

        lines = [
            "# SAS PROGRAMMING SPECIFICATIONS",
            "",
            f"**Study:** {protocol.nct_id}",
            f"**Date:** Generated",
            "",
            "---",
            "",
            "## Overview",
            "",
            "This document contains SAS code templates for statistical analyses.",
            "These templates should be adapted with actual paths and macro references.",
            "",
            "### Programs Included",
            "",
            "| Program | Purpose | Key Output |",
            "|---------|---------|------------|",
        ]

        for spec in specs:
            tlfs = ", ".join(spec.output_tlf)
            lines.append(f"| {spec.program_name} | {spec.purpose[:40]}... | {tlfs} |")

        lines.append("")
        lines.append("---")
        lines.append("")

        for spec in specs:
            lines.append(f"## {spec.title}")
            lines.append("")
            lines.append(f"**Program:** `{spec.program_name}`")
            lines.append("")
            lines.append(f"**Purpose:** {spec.purpose}")
            lines.append("")
            lines.append(f"**Statistical Method:** {spec.statistical_method}")
            lines.append("")
            lines.append("**Input Datasets:**")
            for ds in spec.input_datasets:
                lines.append(f"- {ds}")
            lines.append("")
            lines.append("**Output:**")
            for ds in spec.output_datasets:
                lines.append(f"- Dataset: {ds}")
            for tlf in spec.output_tlf:
                lines.append(f"- TLF: {tlf}")
            lines.append("")
            lines.append("### SAS Code Template")
            lines.append("")
            lines.append("```sas")
            lines.append(spec.sas_code_template)
            lines.append("```")
            lines.append("")
            lines.append("### Validation Requirements")
            lines.append("")
            for req in spec.validation_requirements:
                lines.append(f"- {req}")
            lines.append("")
            lines.append("### QC Checks")
            lines.append("")
            for check in spec.qc_checks:
                lines.append(f"- [ ] {check}")
            lines.append("")
            lines.append("---")
            lines.append("")

        # Add general programming standards
        lines.extend([
            "## General Programming Standards",
            "",
            "### Naming Conventions",
            "",
            "| Type | Convention | Example |",
            "|------|------------|---------|",
            "| Analysis Programs | an_[type]_[endpoint].sas | an_mmrm_primary.sas |",
            "| TLF Programs | t_[number].sas, l_[number].sas, f_[number].sas | t_14_2_1.sas |",
            "| Output Datasets | an_[description] | an_mmrm_primary |",
            "| Work Datasets | work.[descriptive_name] | work.analysis |",
            "",
            "### Required Macro Variables",
            "",
            "```sas",
            "%let study = STUDYID;",
            "%let cutoff = DDMMMYYYY;  /* Data cutoff date */",
            "%let ver = 1.0;           /* Analysis version */",
            "```",
            "",
            "### Standard Headers",
            "",
            "All programs must include:",
            "- Program name and purpose",
            "- Author and date",
            "- Input and output datasets",
            "- Modification history",
            "",
            "### Validation Approach",
            "",
            "1. **Independent Double Programming:** Key analyses require independent programming",
            "2. **Code Review:** All programs reviewed by senior programmer",
            "3. **Log Review:** Confirm no errors/warnings in log",
            "4. **Output Review:** Compare to mock shells",
            ""
        ])

        return "\n".join(lines)


# Factory function
def create_programming_generator(llm_client=None) -> ProgrammingSpecGenerator:
    """Create a programming specification generator instance"""
    return ProgrammingSpecGenerator(llm_client=llm_client)
