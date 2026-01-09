"""
Comprehensive Safety Analysis Integration Module
================================================

Orchestrates all safety analyses for clinical trials, integrating:
- Adverse event analysis (TEAE, SAE, Grade 3+)
- Laboratory safety (hematology, chemistry, liver function)
- Vital signs analysis
- ECG analysis
- CTCAE grading system
- MedDRA coding system

Provides unified safety assessment and reporting for SAP generation.

Regulatory Framework:
- ICH E2A: Clinical Safety Data Management
- ICH E3: Structure and Content of Clinical Study Reports
- FDA Guidance: Safety Reporting Requirements (2012)
- FDA Guidance: Evaluation of Safety Data from Controlled Trials (2017)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum
import logging

from .adverse_event_analysis import (
    get_adverse_event_service,
    AEAnalysisSpec,
    AESISpec,
    DLTSpec
)
from .laboratory_analysis import (
    get_laboratory_analysis_service,
    LaboratoryAnalysisSpec,
    HysLawAnalysis
)
from .ctcae_model import CTCAEVersion

logger = logging.getLogger(__name__)


class SafetyAnalysisLevel(Enum):
    """Level of safety analysis detail"""
    MINIMAL = "minimal"           # Basic TEAE and SAE only
    STANDARD = "standard"         # Standard Phase 2/3 safety package
    COMPREHENSIVE = "comprehensive"  # Full safety package with all analyses
    REGULATORY = "regulatory"     # Registration-ready with enhanced detail


class SafetyReportingPeriod(Enum):
    """Safety data collection periods"""
    TREATMENT = "Treatment Period"
    FOLLOW_UP = "Safety Follow-up"
    LONG_TERM = "Long-term Follow-up"
    ALL = "All Periods"


@dataclass
class VitalSignsSpec:
    """Specification for vital signs analysis"""
    parameters: List[str] = field(default_factory=lambda: [
        "Systolic Blood Pressure",
        "Diastolic Blood Pressure",
        "Heart Rate",
        "Respiratory Rate",
        "Temperature",
        "Weight",
        "BMI"
    ])

    # Analysis methods
    descriptive_statistics: bool = True
    shift_tables: bool = True
    outlier_analysis: bool = True

    # Clinical significance thresholds
    bp_high_threshold: int = 140  # mmHg systolic
    bp_low_threshold: int = 90    # mmHg systolic
    hr_high_threshold: int = 100  # bpm
    hr_low_threshold: int = 50    # bpm


@dataclass
class ECGSpec:
    """Specification for ECG analysis"""
    parameters: List[str] = field(default_factory=lambda: [
        "Heart Rate",
        "PR Interval",
        "QRS Duration",
        "QT Interval",
        "QTcF (Fridericia)",
        "QTcB (Bazett)"
    ])

    # QT analysis (FDA guidance)
    perform_qtc_analysis: bool = True
    qtc_formula: str = "Fridericia"  # or "Bazett"

    # Clinical thresholds
    qtcf_prolongation_threshold: int = 450  # ms for males
    qtcf_prolongation_threshold_female: int = 470  # ms for females
    qtcf_change_threshold: int = 60  # ms change from baseline

    # Categorical analysis
    perform_categorical: bool = True  # QTcF >450, >480, >500 ms


@dataclass
class ExposureAnalysisSpec:
    """Specification for drug exposure analysis"""
    # Duration of exposure
    analyze_treatment_duration: bool = True
    analyze_dose_intensity: bool = True
    analyze_dose_modifications: bool = True

    # Compliance
    analyze_compliance: bool = True
    compliance_threshold: float = 80.0  # Percent

    # Dose modifications
    track_reductions: bool = True
    track_delays: bool = True
    track_interruptions: bool = True
    track_discontinuations: bool = True


@dataclass
class ComprehensiveSafetySpec:
    """
    Complete specification for comprehensive safety analysis package.

    Orchestrates all safety analyses for SAP.
    """
    study_id: str
    study_phase: str = "Phase 2/3"
    analysis_level: SafetyAnalysisLevel = SafetyAnalysisLevel.STANDARD

    # Component specifications
    ae_analysis: AEAnalysisSpec = field(default_factory=AEAnalysisSpec)
    lab_analysis: LaboratoryAnalysisSpec = field(default_factory=LaboratoryAnalysisSpec)
    vital_signs: VitalSignsSpec = field(default_factory=VitalSignsSpec)
    ecg_analysis: ECGSpec = field(default_factory=ECGSpec)
    exposure_analysis: ExposureAnalysisSpec = field(default_factory=ExposureAnalysisSpec)

    # CTCAE version
    ctcae_version: CTCAEVersion = CTCAEVersion.V5_0

    # Safety populations
    safety_population: str = "Safety Population"
    safety_population_definition: str = "All subjects who received at least one dose of study treatment"

    # Reporting periods
    reporting_periods: List[SafetyReportingPeriod] = field(
        default_factory=lambda: [SafetyReportingPeriod.TREATMENT]
    )

    # Special analyses
    perform_dmc_reporting: bool = False
    perform_dsur: bool = False  # Development Safety Update Report
    perform_psur: bool = False  # Periodic Safety Update Report


class ComprehensiveSafetyService:
    """
    Service for comprehensive safety analysis integration.

    Orchestrates all safety components and generates unified SAP sections.
    """

    def __init__(self):
        """Initialize safety integration service"""
        self.ae_service = get_adverse_event_service()
        self.lab_service = get_laboratory_analysis_service()

    def generate_complete_safety_section(
        self,
        spec: ComprehensiveSafetySpec
    ) -> str:
        """
        Generate complete safety analysis section for SAP.

        Integrates all safety components into comprehensive SAP text.

        Args:
            spec: Comprehensive safety specification

        Returns:
            Complete SAP safety section text
        """
        text = """
# Safety Analyses

## Overview

Safety will be assessed through:
- Adverse events (AEs)
- Clinical laboratory tests
- Vital signs
- Electrocardiograms (ECGs)
- Physical examinations
- Other safety assessments per protocol

All safety analyses will be performed on the Safety Population unless otherwise specified.

"""

        # Add safety population definition
        text += self._generate_safety_population_section(spec)

        # Add adverse event analysis
        text += self._generate_ae_section(spec)

        # Add laboratory analysis
        text += self._generate_laboratory_section(spec)

        # Add vital signs analysis
        text += self._generate_vital_signs_section(spec)

        # Add ECG analysis
        text += self._generate_ecg_section(spec)

        # Add exposure analysis
        text += self._generate_exposure_section(spec)

        # Add integrated safety assessment
        text += self._generate_integrated_safety_section(spec)

        # Add special reporting
        if spec.perform_dmc_reporting:
            text += self._generate_dmc_reporting_section()

        return text.strip()

    def _generate_safety_population_section(
        self,
        spec: ComprehensiveSafetySpec
    ) -> str:
        """Generate safety population definition section"""
        return f"""
## Safety Population

**Definition:** {spec.safety_population_definition}

**Analysis Sets:**

- **Safety Population:** {spec.safety_population_definition}
- **Evaluable for Safety:** Subjects with at least one post-baseline safety assessment

All safety analyses will use the Safety Population as the denominator unless
otherwise specified.

**Treatment Groups:**

Safety data will be summarized by treatment group as randomized/assigned.

"""

    def _generate_ae_section(self, spec: ComprehensiveSafetySpec) -> str:
        """Generate adverse event analysis section"""
        ae_text = self.ae_service.generate_ae_methodology(spec.ae_analysis)

        # Add CTCAE version information
        ctcae_info = f"""
### CTCAE Grading

Adverse events will be graded according to the National Cancer Institute (NCI)
Common Terminology Criteria for Adverse Events (CTCAE) version {spec.ctcae_version.value}.

**CTCAE Severity Grades:**

- **Grade 1:** Mild; asymptomatic or mild symptoms; clinical or diagnostic observations only; intervention not indicated
- **Grade 2:** Moderate; minimal, local or noninvasive intervention indicated; limiting age-appropriate instrumental ADL
- **Grade 3:** Severe or medically significant but not immediately life-threatening; hospitalization or prolongation indicated; disabling; limiting self care ADL
- **Grade 4:** Life-threatening consequences; urgent intervention indicated
- **Grade 5:** Death related to adverse event

**ADL** = Activities of Daily Living

"""

        return ae_text + "\n" + ctcae_info

    def _generate_laboratory_section(
        self,
        spec: ComprehensiveSafetySpec
    ) -> str:
        """Generate laboratory safety section"""
        return self.lab_service.generate_laboratory_methodology(spec.lab_analysis)

    def _generate_vital_signs_section(
        self,
        spec: ComprehensiveSafetySpec
    ) -> str:
        """Generate vital signs analysis section"""
        return """
## Vital Signs Analysis

### Vital Signs Assessments

Vital signs will be measured at:
- Screening
- Baseline (Day 1 pre-dose)
- On-treatment visits per schedule
- End of treatment
- Safety follow-up

**Parameters:**

"""+ "\n".join(f"- {param}" for param in spec.vital_signs.parameters) + """

### Statistical Analysis

#### Descriptive Statistics

Vital signs will be summarized by treatment group and visit using descriptive
statistics:
- N (number of subjects with data)
- Mean
- Standard deviation
- Median
- Minimum, Maximum
- Q1, Q3

**Change from Baseline:**
- Change = Post-baseline value - Baseline value
- Summarized for all post-baseline visits

#### Shift Tables

Shift tables will show movement between normal/abnormal categories from baseline
to worst post-baseline.

**Categories:**
- **Low:** Below lower limit of normal
- **Normal:** Within reference range
- **High:** Above upper limit of normal

#### Potentially Clinically Significant Values

**Blood Pressure:**
- Systolic BP ≥{sbp_high} mmHg
- Systolic BP ≤{sbp_low} mmHg
- Diastolic BP ≥{dbp_high} mmHg
- Diastolic BP ≤{dbp_low} mmHg

**Heart Rate:**
- Heart rate ≥{hr_high} bpm
- Heart rate ≤{hr_low} bpm

Subjects meeting these criteria will be listed with values and dates.

#### Time Course Plots

Mean (±SE) vital signs over time will be plotted by treatment group to visualize
trends and identify systematic changes.

""".format(
            sbp_high=spec.vital_signs.bp_high_threshold,
            sbp_low=spec.vital_signs.bp_low_threshold,
            dbp_high=90,
            dbp_low=60,
            hr_high=spec.vital_signs.hr_high_threshold,
            hr_low=spec.vital_signs.hr_low_threshold
        )

    def _generate_ecg_section(self, spec: ComprehensiveSafetySpec) -> str:
        """Generate ECG analysis section"""
        return f"""
## Electrocardiogram (ECG) Analysis

### ECG Assessments

12-lead ECGs will be obtained at:
- Screening
- Baseline (Day 1 pre-dose)
- On-treatment visits per protocol schedule
- End of treatment
- Safety follow-up if clinically indicated

**Timing:** ECGs obtained in triplicate at each visit with subject in supine position
after ≥5 minutes rest.

**Parameters:**

"""+ "\n".join(f"- {param}" for param in spec.ecg_analysis.parameters) + f"""

### QTc Prolongation Analysis

**Rationale:**
QT interval prolongation may indicate risk of Torsades de Pointes, a potentially
fatal ventricular arrhythmia. FDA requires thorough QT assessment for new drugs.

**QTc Formula:** {spec.ecg_analysis.qtc_formula} correction will be used:
- **Fridericia (QTcF):** QTc = QT / RR^(1/3)
- More accurate at higher heart rates

**Reference:** FDA Guidance - E14 Clinical Evaluation of QT/QTc Interval Prolongation (2012)

### Statistical Analysis

#### Descriptive Statistics

ECG parameters will be summarized by treatment group and visit:
- N, Mean, SD, Median, Min, Max
- Change from baseline

#### Categorical Analysis

**Absolute QTcF Values:**
- QTcF >450 ms (males) / >470 ms (females): Prolonged
- QTcF >480 ms: Markedly prolonged
- QTcF >500 ms: Severely prolonged (high risk)

**Change from Baseline:**
- ΔQTcF >30 ms
- ΔQTcF >60 ms (regulatory concern)

#### Central Tendency Analysis

Plot mean ΔQTcF (90% CI) by time point to assess time course of QT effect.

**Threshold of Regulatory Concern:**
- Upper bound of 90% CI for ΔQTcF >10 ms: QT liability possible

#### Outlier Analysis

Subjects with QTcF values meeting criteria above will be listed with:
- Subject ID
- Visit
- QTcF value (ms)
- Change from baseline (ms)
- Heart rate
- Concomitant medications (QT-prolonging drugs)

### Clinical ECG Interpretation

Investigator interpretation of ECGs will be summarized:
- Normal
- Abnormal, not clinically significant
- Abnormal, clinically significant

Abnormal clinically significant findings will be listed.

"""

    def _generate_exposure_section(
        self,
        spec: ComprehensiveSafetySpec
    ) -> str:
        """Generate drug exposure analysis section"""
        return f"""
## Drug Exposure Analysis

### Rationale

Exposure to study treatment is essential context for interpreting safety data.
Longer exposure provides more opportunity for adverse events to occur.

### Assessments

**Duration of Exposure:**
Time from first dose to last dose of study treatment.

**Dose Intensity:**
Actual dose delivered relative to planned dose:
- Relative Dose Intensity (RDI) = (Actual cumulative dose / Planned cumulative dose) × 100%

**Dose Modifications:**
- Dose reductions
- Dose delays
- Dose interruptions
- Treatment discontinuations

### Statistical Analysis

#### Duration of Exposure

Summarized by treatment group:
- N
- Mean (SD)
- Median
- Min, Max
- Q1, Q3

**Units:** Days or cycles

**Graphical Display:**
Distribution of exposure duration (histogram or box plot).

#### Dose Intensity

**Relative Dose Intensity (RDI):**
Percentage of planned dose actually received.

**Analysis:**
- Mean RDI by treatment group
- Proportion with RDI ≥80% (compliant)
- Proportion with RDI ≥90% (high compliance)

#### Dose Modifications

**Summary Tables:**

Number and percentage of subjects with:
- Any dose modification
- Dose reduction
- Dose delay
- Dose interruption
- Treatment discontinuation

**Reasons for Modifications:**

Tabulate reasons for dose modifications by treatment group:
- Adverse event
- Laboratory abnormality
- Disease progression
- Subject request
- Other

#### Treatment Discontinuation

**Time to Treatment Discontinuation:**
Kaplan-Meier plot by treatment group.

**Reasons for Discontinuation:**
- Adverse event
- Disease progression
- Subject request
- Physician decision
- Protocol violation
- Death
- Lost to follow-up
- Other

Summarized by treatment group (N, %).

#### Exposure-Adjusted Incidence Rates

For key safety endpoints (e.g., SAEs, Grade 3+ AEs):

**Incidence Rate:** Events per person-year of exposure

**Formula:**
Rate = (Number of subjects with event / Total exposure in person-years) × 100

**Comparison:**
Incidence rate ratio with 95% CI using Poisson regression.

"""

    def _generate_integrated_safety_section(
        self,
        spec: ComprehensiveSafetySpec
    ) -> str:
        """Generate integrated safety assessment section"""
        return """
## Integrated Safety Assessment

### Overview

An integrated assessment will synthesize findings across all safety domains to
provide a comprehensive safety profile of the investigational treatment.

### Components

**Integrated Review Includes:**

1. **Adverse Events:** Incidence, severity, causality, outcomes
2. **Laboratory Data:** Clinically significant abnormalities, trends
3. **Vital Signs:** Clinically significant changes
4. **ECG:** QTc prolongation, other abnormalities
5. **Exposure:** Duration, dose intensity, modifications
6. **Deaths:** All deaths with narratives
7. **Serious Adverse Events:** All SAEs with narratives

### Safety Narratives

**Required Narratives:**

- All deaths
- All serious adverse events
- Adverse events leading to treatment discontinuation
- Grade 4 and 5 adverse events
- Adverse events of special interest (AESI)
- Potential Hy's Law cases (hepatotoxicity)

**Narrative Content:**

Each narrative will include:
- Subject demographics (age, sex, race)
- Medical history and concomitant conditions
- Study treatment details (dose, duration, modifications)
- Event description (onset, course, outcome)
- Relevant laboratory values
- Concomitant medications
- Investigator causality assessment
- Actions taken (treatment, dose modification)
- Event outcome and resolution

### Safety Signals

**Signal Detection:**

Safety data will be reviewed for potential safety signals:
- Adverse events with unexpected frequency or severity
- Unexpected patterns across safety domains
- Dose-response relationships
- Cumulative toxicities

**Analysis Methods:**

- Comparative incidence rates between treatment groups
- Bayesian methods for signal detection (if applicable)
- Subgroup analyses to identify at-risk populations

### Overall Safety Conclusions

An overall safety assessment will integrate findings to characterize:
- Most common adverse events
- Most serious adverse events
- Adverse events leading to discontinuation
- Laboratory, vital signs, and ECG findings
- Dose-response relationships
- Exposure considerations
- Special populations (elderly, renal/hepatic impairment)

**Risk-Benefit Assessment:**

The integrated safety assessment will inform the overall risk-benefit profile
considering efficacy outcomes.

"""

    def _generate_dmc_reporting_section(self) -> str:
        """Generate Data Monitoring Committee reporting section"""
        return """
## Data Monitoring Committee (DMC) Reporting

### DMC Safety Reports

Safety data will be provided to an independent Data Monitoring Committee (DMC)
at regular intervals per DMC charter.

**Report Contents:**

- Summary of enrollment and follow-up
- Adverse event summary (overall and by treatment group)
- Serious adverse events (blinded or unblinded per charter)
- Deaths
- Laboratory, vital signs, ECG summaries
- Protocol deviations
- Interim efficacy results (if specified)

**Frequency:**

DMC reports will be prepared:
- After enrollment milestones (e.g., 25%, 50%, 75%)
- After event milestones (for event-driven trials)
- Annually (minimum)
- Ad hoc if safety concern arises

**Format:**

Reports will be prepared in accordance with DMC charter specifications.

**Unblinding:**

Unblinded safety data may be provided to DMC per charter, while maintaining
study blind for investigators and sponsor.

### DMC Recommendations

The DMC may recommend:
- Continue study as planned
- Modify protocol (e.g., enrollment criteria, dose)
- Suspend enrollment pending further review
- Terminate study for safety or futility

All DMC recommendations will be documented and acted upon promptly.

"""

    def generate_safety_analysis_code(
        self,
        spec: ComprehensiveSafetySpec,
        language: str = "SAS"
    ) -> str:
        """
        Generate statistical code for comprehensive safety analysis.

        Args:
            spec: Safety specification
            language: "SAS" or "R"

        Returns:
            Complete analysis code
        """
        if language.upper() == "SAS":
            return self._generate_sas_code(spec)
        elif language.upper() == "R":
            return self._generate_r_code(spec)
        else:
            raise ValueError(f"Unsupported language: {language}")

    def _generate_sas_code(self, spec: ComprehensiveSafetySpec) -> str:
        """Generate comprehensive SAS code for safety analysis"""
        code = """
/******************************************************************************
* Comprehensive Safety Analysis
* Generated by SAP Generator Enterprise System
******************************************************************************/

* Setup libraries and formats;
libname adam "/path/to/adam";
libname output "/path/to/output";

* Define safety population;
data safety_pop;
    set adam.adsl;
    where SAFFL = 'Y';  /* Safety population flag */
run;

/******************************************************************************
* ADVERSE EVENT ANALYSIS
******************************************************************************/

* TEAE summary;
proc freq data=adam.adae;
    where SAFFL='Y' and TRTEMFL='Y';
    tables TRTA*AEDECOD / out=teae_summary;
    by AESOC;
run;

* Grade 3+ AEs;
proc freq data=adam.adae;
    where SAFFL='Y' and TRTEMFL='Y' and AETOXGR in ('3', '4', '5');
    tables TRTA*AEDECOD / out=grade3plus;
    by AESOC;
run;

* SAE summary;
proc freq data=adam.adae;
    where SAFFL='Y' and AESER='Y';
    tables TRTA*AEDECOD / out=sae_summary;
run;

/******************************************************************************
* LABORATORY ANALYSIS
******************************************************************************/

* Descriptive statistics;
proc means data=adam.adlb n mean std median min max;
    where SAFFL='Y' and AVISITN > 0;
    class TRTA AVISITN PARAM;
    var AVAL CHG;
    output out=lab_stats;
run;

* Shift tables;
proc freq data=adam.adlb;
    where SAFFL='Y';
    tables BNRIND*ANRIND / out=shift_table;
    by TRTA PARAM;
run;

* Grade 3/4 lab abnormalities;
proc freq data=adam.adlb;
    where SAFFL='Y' and ATOXGR in ('3', '4');
    tables TRTA*PARAM / out=grade34_lab;
run;

* Hy's Law analysis;
data hys_law_screen;
    set adam.adlb;
    where SAFFL='Y' and PARAMCD in ('ALT', 'AST', 'BILI', 'ALP');

    * Identify potential cases;
    if (PARAMCD in ('ALT', 'AST') and AVAL/ANRHI > 3) or
       (PARAMCD = 'BILI' and AVAL/ANRHI > 2);

    keep USUBJID PARAMCD AVAL ANRHI ADY;
run;

* Identify concurrent elevations;
proc sql;
    create table hys_law_cases as
    select a.USUBJID,
           a.AVAL as ALT_value,
           b.AVAL as BILI_value,
           a.ADY as ALT_day,
           b.ADY as BILI_day
    from hys_law_screen(where=(PARAMCD in ('ALT', 'AST'))) as a
    inner join hys_law_screen(where=(PARAMCD='BILI')) as b
        on a.USUBJID = b.USUBJID
        and abs(a.ADY - b.ADY) <= 14;  /* Within 14 days */
quit;

/******************************************************************************
* VITAL SIGNS ANALYSIS
******************************************************************************/

* Descriptive statistics;
proc means data=adam.advs n mean std median min max;
    where SAFFL='Y' and AVISITN > 0;
    class TRTA AVISITN PARAM;
    var AVAL CHG;
    output out=vs_stats;
run;

* Shift tables;
proc freq data=adam.advs;
    where SAFFL='Y' and PARAMCD in ('SYSBP', 'DIABP', 'PULSE');
    tables BNRIND*ANRIND / out=vs_shift;
    by TRTA PARAM;
run;

* Outlier analysis;
data vs_outliers;
    set adam.advs;
    where SAFFL='Y';

    * Define outlier criteria;
    if PARAMCD = 'SYSBP' and (AVAL >= 140 or AVAL <= 90) then outlier = 1;
    else if PARAMCD = 'DIABP' and (AVAL >= 90 or AVAL <= 60) then outlier = 1;
    else if PARAMCD = 'PULSE' and (AVAL >= 100 or AVAL <= 50) then outlier = 1;
    else outlier = 0;

    if outlier = 1;
run;

/******************************************************************************
* ECG ANALYSIS
******************************************************************************/

* QTcF analysis;
proc means data=adam.adeg n mean std median min max;
    where SAFFL='Y' and PARAMCD = 'QTCF';
    class TRTA AVISITN;
    var AVAL CHG;
    output out=qtcf_stats;
run;

* Categorical QTcF;
data qtcf_categorical;
    set adam.adeg;
    where SAFFL='Y' and PARAMCD = 'QTCF';

    length qtcf_cat $30;

    * Absolute categories;
    if SEX = 'M' then do;
        if AVAL > 500 then qtcf_cat = '>500 ms';
        else if AVAL > 480 then qtcf_cat = '>480-500 ms';
        else if AVAL > 450 then qtcf_cat = '>450-480 ms';
        else qtcf_cat = '<=450 ms';
    end;
    else if SEX = 'F' then do;
        if AVAL > 500 then qtcf_cat = '>500 ms';
        else if AVAL > 480 then qtcf_cat = '>480-500 ms';
        else if AVAL > 470 then qtcf_cat = '>470-480 ms';
        else qtcf_cat = '<=470 ms';
    end;

    * Change categories;
    if CHG > 60 then chg_cat = '>60 ms increase';
    else if CHG > 30 then chg_cat = '>30-60 ms increase';
    else chg_cat = '<=30 ms';
run;

proc freq data=qtcf_categorical;
    tables TRTA*qtcf_cat*chg_cat;
run;

/******************************************************************************
* EXPOSURE ANALYSIS
******************************************************************************/

* Duration of exposure;
proc means data=adam.adex n mean std median min max;
    where SAFFL='Y';
    class TRTA;
    var EXDUR;  /* Duration of exposure in days */
    output out=exposure_duration;
run;

* Dose intensity;
data dose_intensity;
    set adam.adex;
    where SAFFL='Y';

    * Calculate relative dose intensity;
    rdi = (EXDOSE_TOTAL / EXDOSE_PLANNED) * 100;

    * Compliance categories;
    if rdi >= 90 then compliance = 'High (>=90%)';
    else if rdi >= 80 then compliance = 'Adequate (80-90%)';
    else compliance = 'Low (<80%)';
run;

proc freq data=dose_intensity;
    tables TRTA*compliance;
run;

* Dose modifications;
proc freq data=adam.adex;
    where SAFFL='Y';
    tables TRTA*(EXDOSFRQ EXADJ) / missing;
run;

/******************************************************************************
* INTEGRATED SAFETY TABLES
******************************************************************************/

* Overall safety summary;
proc sql;
    create table safety_summary as
    select TRTA,
           count(distinct USUBJID) as n_subjects,
           sum(ANY_AE) as n_any_ae,
           sum(ANY_SAE) as n_any_sae,
           sum(GRADE3_AE) as n_grade3_ae,
           sum(AE_DEATH) as n_ae_death,
           sum(AEWITHDR) as n_ae_discontinuation
    from adam.adsl
    where SAFFL = 'Y'
    group by TRTA;
quit;

* Export to RTF;
ods rtf file="output/safety_summary.rtf";
proc print data=safety_summary noobs;
    title "Overall Safety Summary";
run;
ods rtf close;
"""
        return code.strip()

    def _generate_r_code(self, spec: ComprehensiveSafetySpec) -> str:
        """Generate comprehensive R code for safety analysis"""
        code = """
################################################################################
# Comprehensive Safety Analysis
# Generated by SAP Generator Enterprise System
################################################################################

library(tidyverse)
library(survival)
library(gtsummary)
library(gt)

# Load ADaM datasets
adsl <- read_sas("/path/to/adam/adsl.sas7bdat")
adae <- read_sas("/path/to/adam/adae.sas7bdat")
adlb <- read_sas("/path/to/adam/adlb.sas7bdat")
advs <- read_sas("/path/to/adam/advs.sas7bdat")
adeg <- read_sas("/path/to/adam/adeg.sas7bdat")

# Safety population
safety_pop <- adsl %>% filter(SAFFL == "Y")

################################################################################
# ADVERSE EVENT ANALYSIS
################################################################################

# TEAE summary
teae_summary <- adae %>%
  filter(SAFFL == "Y", TRTEMFL == "Y") %>%
  group_by(TRTA, AESOC, AEDECOD) %>%
  summarise(
    n = n_distinct(USUBJID),
    .groups = "drop"
  ) %>%
  left_join(
    safety_pop %>% count(TRTA, name = "N"),
    by = "TRTA"
  ) %>%
  mutate(
    pct = (n / N) * 100,
    n_pct = sprintf("%d (%.1f%%)", n, pct)
  )

# Grade 3+ AEs
grade3plus_summary <- adae %>%
  filter(SAFFL == "Y", TRTEMFL == "Y", AETOXGR %in% c("3", "4", "5")) %>%
  group_by(TRTA, AEDECOD) %>%
  summarise(
    n = n_distinct(USUBJID),
    .groups = "drop"
  ) %>%
  left_join(
    safety_pop %>% count(TRTA, name = "N"),
    by = "TRTA"
  ) %>%
  mutate(
    pct = (n / N) * 100,
    n_pct = sprintf("%d (%.1f%%)", n, pct)
  )

################################################################################
# LABORATORY ANALYSIS
################################################################################

# Descriptive statistics
lab_stats <- adlb %>%
  filter(SAFFL == "Y", AVISITN > 0) %>%
  group_by(TRTA, AVISITN, PARAM) %>%
  summarise(
    N = n(),
    Mean = mean(AVAL, na.rm = TRUE),
    SD = sd(AVAL, na.rm = TRUE),
    Median = median(AVAL, na.rm = TRUE),
    Min = min(AVAL, na.rm = TRUE),
    Max = max(AVAL, na.rm = TRUE),
    .groups = "drop"
  )

# Shift tables
shift_table <- adlb %>%
  filter(SAFFL == "Y") %>%
  group_by(TRTA, PARAM, BNRIND, ANRIND) %>%
  summarise(n = n(), .groups = "drop")

# Hy's Law screening
hys_law_candidates <- adlb %>%
  filter(
    SAFFL == "Y",
    PARAMCD %in% c("ALT", "AST", "BILI"),
    ((PARAMCD %in% c("ALT", "AST") & (AVAL / ANRHI) > 3) |
     (PARAMCD == "BILI" & (AVAL / ANRHI) > 2))
  )

################################################################################
# VITAL SIGNS ANALYSIS
################################################################################

# Descriptive statistics
vs_stats <- advs %>%
  filter(SAFFL == "Y", AVISITN > 0) %>%
  group_by(TRTA, AVISITN, PARAM) %>%
  summarise(
    N = n(),
    Mean = mean(AVAL, na.rm = TRUE),
    SD = sd(AVAL, na.rm = TRUE),
    Median = median(AVAL, na.rm = TRUE),
    .groups = "drop"
  )

# Outlier detection
vs_outliers <- advs %>%
  filter(SAFFL == "Y") %>%
  mutate(
    outlier = case_when(
      PARAMCD == "SYSBP" & (AVAL >= 140 | AVAL <= 90) ~ TRUE,
      PARAMCD == "DIABP" & (AVAL >= 90 | AVAL <= 60) ~ TRUE,
      PARAMCD == "PULSE" & (AVAL >= 100 | AVAL <= 50) ~ TRUE,
      TRUE ~ FALSE
    )
  ) %>%
  filter(outlier)

################################################################################
# ECG ANALYSIS
################################################################################

# QTcF categorical analysis
qtcf_categorical <- adeg %>%
  filter(SAFFL == "Y", PARAMCD == "QTCF") %>%
  mutate(
    qtcf_cat = case_when(
      AVAL > 500 ~ ">500 ms",
      AVAL > 480 ~ ">480-500 ms",
      SEX == "M" & AVAL > 450 ~ ">450-480 ms",
      SEX == "F" & AVAL > 470 ~ ">470-480 ms",
      TRUE ~ "Normal"
    ),
    chg_cat = case_when(
      CHG > 60 ~ ">60 ms increase",
      CHG > 30 ~ ">30-60 ms increase",
      TRUE ~ "<=30 ms"
    )
  )

# Summary table
qtcf_summary <- qtcf_categorical %>%
  group_by(TRTA, qtcf_cat) %>%
  summarise(n = n(), .groups = "drop")

################################################################################
# OUTPUT TABLES
################################################################################

# Create gt tables
teae_table <- teae_summary %>%
  select(AESOC, AEDECOD, TRTA, n_pct) %>%
  pivot_wider(names_from = TRTA, values_from = n_pct) %>%
  gt() %>%
  tab_header(
    title = "Treatment-Emergent Adverse Events",
    subtitle = "Safety Population"
  )

# Export to Word
gtsave(teae_table, "teae_summary.docx")
"""
        return code.strip()

    def validate_safety_spec(
        self,
        spec: ComprehensiveSafetySpec
    ) -> List[str]:
        """
        Validate comprehensive safety specification.

        Args:
            spec: Safety specification to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required components based on analysis level
        if spec.analysis_level == SafetyAnalysisLevel.COMPREHENSIVE:
            if not spec.ae_analysis.analyze_teae:
                errors.append("TEAE analysis required for comprehensive safety")
            if not spec.lab_analysis.perform_hys_law:
                errors.append("Hy's Law analysis recommended for comprehensive safety")

        # Check CTCAE version
        if spec.ctcae_version not in [CTCAEVersion.V5_0, CTCAEVersion.V6_0]:
            errors.append(f"Unsupported CTCAE version: {spec.ctcae_version}")

        # Check safety population definition
        if not spec.safety_population_definition:
            errors.append("Safety population definition required")

        return errors


# Singleton instance
_comprehensive_safety_service: Optional[ComprehensiveSafetyService] = None


def get_comprehensive_safety_service() -> ComprehensiveSafetyService:
    """
    Get comprehensive safety service instance.

    Returns:
        ComprehensiveSafetyService instance
    """
    global _comprehensive_safety_service

    if _comprehensive_safety_service is None:
        _comprehensive_safety_service = ComprehensiveSafetyService()

    return _comprehensive_safety_service
