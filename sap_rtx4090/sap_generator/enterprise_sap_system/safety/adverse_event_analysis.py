"""
Adverse Event Analysis Methods
===============================

Comprehensive statistical methods for safety analysis in clinical trials.

Required by:
- FDA Guidance: "Safety Assessment for IND Safety Reporting" (2015)
- ICH E2A: Clinical Safety Data Management (1994)
- ICH E2C(R2): Periodic Benefit-Risk Evaluation Report (2012)
- ICH E3: Structure and Content of Clinical Study Reports (1995, Section 12.2)

Key analyses:
- Treatment-Emergent Adverse Events (TEAEs)
- Serious Adverse Events (SAEs)
- Adverse Events of Special Interest (AESI)
- Dose-limiting toxicities (DLTs)
- Grade 3+ events
- Deaths
- Study discontinuations due to AEs

Analysis methods:
- Incidence rates with exact confidence intervals
- Risk difference and relative risk
- Time to first occurrence
- Exposure-adjusted incidence rates (per patient-year)
- Cochran-Mantel-Haenszel tests
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


class AECategory(Enum):
    """Categories of adverse events for analysis"""
    TEAE = "Treatment-Emergent AE"
    SAE = "Serious AE"
    GRADE_3_PLUS = "Grade 3 or Higher"
    AESI = "AE of Special Interest"
    DLT = "Dose-Limiting Toxicity"
    DISCONTINUATION = "Leading to Discontinuation"
    DEATH = "Leading to Death"
    RELATED = "Treatment-Related"


class SeriousnessCriteria(Enum):
    """ICH E2A seriousness criteria"""
    DEATH = "Results in death"
    LIFE_THREATENING = "Life-threatening"
    HOSPITALIZATION = "Requires hospitalization or prolongs existing hospitalization"
    DISABILITY = "Results in persistent or significant disability/incapacity"
    CONGENITAL_ANOMALY = "Congenital anomaly/birth defect"
    MEDICALLY_IMPORTANT = "Medically important event"


class CausalityAssessment(Enum):
    """Causality assessment categories"""
    RELATED = "Related"
    PROBABLY_RELATED = "Probably Related"
    POSSIBLY_RELATED = "Possibly Related"
    UNLIKELY_RELATED = "Unlikely Related"
    NOT_RELATED = "Not Related"
    UNASSESSABLE = "Unassessable"


@dataclass
class AdverseEvent:
    """Single adverse event occurrence"""
    subject_id: str
    ae_term: str                       # Verbatim or preferred term
    meddra_pt: str                     # MedDRA preferred term
    meddra_soc: str                    # MedDRA system organ class
    ctcae_term: str = ""               # CTCAE term if applicable

    # Severity/Grade
    ctcae_grade: int = 0               # 1-5 per CTCAE
    severity: str = ""                 # "Mild", "Moderate", "Severe"

    # Seriousness
    serious: bool = False
    seriousness_criteria: List[SeriousnessCriteria] = field(default_factory=list)

    # Causality
    causality: CausalityAssessment = CausalityAssessment.UNASSESSABLE

    # Timing
    onset_day: int = 0                 # Study day of onset
    resolution_day: Optional[int] = None
    treatment_emergent: bool = False

    # Action taken
    drug_interrupted: bool = False
    drug_reduced: bool = False
    drug_withdrawn: bool = False
    led_to_death: bool = False

    # Treatment
    treatment_arm: str = ""


@dataclass
class AEAnalysisSpec:
    """
    Specification for adverse event analysis.

    Defines which AE summaries and analyses to perform.
    """
    # Population
    safety_population: str = "Safety"  # "Safety", "ITT", "Treated"

    # Categories to analyze
    analyze_teae: bool = True
    analyze_sae: bool = True
    analyze_grade_3_plus: bool = True
    analyze_related: bool = True
    analyze_aesi: bool = False
    analyze_dlt: bool = False

    # Thresholds for reporting
    min_incidence_percent: float = 5.0  # Report AEs occurring in ≥5%
    report_any_grade_3_plus: bool = True  # Report all grade 3+ regardless of frequency

    # Statistical testing
    perform_hypothesis_tests: bool = False  # Usually descriptive only
    test_method: str = "Fisher"        # "Fisher", "Chi-square", "CMH"

    # Exposure adjustment
    exposure_adjusted_rates: bool = True
    exposure_unit: str = "patient-years"

    # Special interests
    aesi_terms: List[str] = field(default_factory=list)  # Preferred terms of special interest

    # DLT (for Phase 1/2)
    dlt_definition: Optional[str] = None
    dlt_observation_period: int = 28   # Days


@dataclass
class AESummaryTable:
    """
    Specification for AE summary table.

    Defines structure and content of standard AE tables.
    """
    table_name: str
    table_description: str

    # Grouping
    group_by_soc: bool = True          # Group by MedDRA SOC
    group_by_severity: bool = False    # Separate by grade

    # Filtering
    ae_category: AECategory = AECategory.TEAE
    min_incidence: float = 0.0         # Minimum incidence to include

    # Sorting
    sort_by: str = "frequency"         # "frequency", "alphabetical", "severity"
    sort_order: str = "descending"

    # Display
    show_percentages: bool = True
    show_confidence_intervals: bool = False
    confidence_level: float = 0.95

    # Treatment columns
    treatment_groups: List[str] = field(default_factory=list)
    include_total_column: bool = False


@dataclass
class DLTAnalysis:
    """
    Dose-Limiting Toxicity analysis for Phase 1/2.

    Defines DLT criteria and evaluation period.
    """
    # DLT definition
    dlt_criteria: List[str] = field(default_factory=list)
    observation_period_days: int = 28

    # Specific toxicities
    hematologic_dlts: List[str] = field(default_factory=list)
    non_hematologic_dlts: List[str] = field(default_factory=list)

    # Dose escalation rules
    max_tolerated_dose_rule: str = ""  # e.g., "≤1/6 DLTs"

    # Analysis
    estimate_mtd: bool = True
    mtd_method: str = "3+3"            # "3+3", "CRM", "BOIN"


@dataclass
class TEAEIncidenceTable:
    """Results from TEAE incidence analysis"""
    soc_name: str
    pt_name: str

    # Counts by treatment
    treatment_counts: Dict[str, int] = field(default_factory=dict)
    treatment_n: Dict[str, int] = field(default_factory=dict)

    # Rates
    treatment_rates: Dict[str, float] = field(default_factory=dict)

    # Statistics
    risk_difference: Optional[float] = None
    risk_ratio: Optional[float] = None
    p_value: Optional[float] = None


class AdverseEventAnalysisService:
    """
    Service for adverse event analysis specifications.

    Provides comprehensive safety analysis methodology.
    """

    def __init__(self):
        """Initialize AE analysis service"""
        pass

    def create_standard_safety_spec(
        self,
        phase: str = "Phase 3"
    ) -> AEAnalysisSpec:
        """
        Create standard safety analysis specification.

        Args:
            phase: Trial phase ("Phase 1", "Phase 2", "Phase 3")

        Returns:
            AEAnalysisSpec with standard settings
        """
        if phase == "Phase 1":
            return AEAnalysisSpec(
                analyze_teae=True,
                analyze_sae=True,
                analyze_grade_3_plus=True,
                analyze_related=True,
                analyze_dlt=True,
                min_incidence_percent=0.0,  # Report all in Phase 1
                perform_hypothesis_tests=False,
                exposure_adjusted_rates=False
            )

        elif phase == "Phase 2":
            return AEAnalysisSpec(
                analyze_teae=True,
                analyze_sae=True,
                analyze_grade_3_plus=True,
                analyze_related=True,
                analyze_aesi=True,
                min_incidence_percent=5.0,
                perform_hypothesis_tests=False,
                exposure_adjusted_rates=True
            )

        else:  # Phase 3
            return AEAnalysisSpec(
                analyze_teae=True,
                analyze_sae=True,
                analyze_grade_3_plus=True,
                analyze_related=True,
                analyze_aesi=True,
                min_incidence_percent=5.0,
                perform_hypothesis_tests=False,  # Descriptive unless pre-specified
                exposure_adjusted_rates=True
            )

    def generate_safety_methodology(
        self,
        spec: AEAnalysisSpec,
        phase: str = "Phase 3"
    ) -> str:
        """
        Generate safety analysis methodology for SAP.

        Args:
            spec: AE analysis specification
            phase: Trial phase

        Returns:
            Formatted SAP text
        """
        text = f"""
## Safety Analysis

### Safety Population

The safety population consists of all subjects who received at least one dose of
study treatment, analyzed according to the treatment received (as-treated principle).

**Definition:** {spec.safety_population} population

### Adverse Event Definitions

**Treatment-Emergent Adverse Event (TEAE):**
An AE that:
- Starts on or after first dose of study treatment, OR
- Was present at baseline and worsened in severity during treatment

**Serious Adverse Event (SAE):**
Per ICH E2A, an AE that:
- Results in death
- Is life-threatening
- Requires inpatient hospitalization or prolongation of existing hospitalization
- Results in persistent or significant disability/incapacity
- Is a congenital anomaly/birth defect
- Is a medically important event

**Treatment-Related AE:**
An AE assessed by the investigator as related (Related, Probably Related, or
Possibly Related) to study treatment.

"""

        # Coding section
        text += self._generate_coding_section()

        # Analysis methods
        text += self._generate_analysis_methods_section(spec)

        # Standard tables
        text += self._generate_standard_tables_section(spec)

        # Special analyses
        if spec.analyze_aesi:
            text += self._generate_aesi_section(spec)

        if spec.analyze_dlt:
            text += self._generate_dlt_section(spec)

        # Statistical testing
        if spec.perform_hypothesis_tests:
            text += self._generate_testing_section(spec)

        # Regulatory
        text += self._generate_safety_regulatory_section()

        return text.strip()

    def _generate_coding_section(self) -> str:
        """Generate coding and grading section"""
        return """
### Adverse Event Coding and Grading

**Coding:**
- **MedDRA:** All AEs coded using Medical Dictionary for Regulatory Activities (MedDRA) version 26.1
- **Hierarchy:** Preferred Term (PT) → High Level Term (HLT) → High Level Group Term (HLGT) → System Organ Class (SOC)
- **Primary SOC:** Used for primary system affected

**Grading:**
- **CTCAE:** Severity graded using Common Terminology Criteria for Adverse Events (CTCAE) version 5.0
- **Grades:**
  - Grade 1: Mild; asymptomatic or mild symptoms; clinical or diagnostic observations only
  - Grade 2: Moderate; minimal, local, or noninvasive intervention indicated
  - Grade 3: Severe or medically significant but not immediately life-threatening
  - Grade 4: Life-threatening consequences; urgent intervention indicated
  - Grade 5: Death related to AE

**Multiple Occurrences:**
When a subject experiences the same AE multiple times:
- Count subject once at the maximum grade observed
- For incidence tables: subject counted once per PT per treatment
- For listings: all occurrences listed

"""

    def _generate_analysis_methods_section(self, spec: AEAnalysisSpec) -> str:
        """Generate analysis methods section"""
        text = """
### Statistical Analysis Methods

**Incidence Rates:**
AE incidence will be summarized as:
- Number of subjects experiencing at least one event
- Percentage: (subjects with AE / subjects in safety population) × 100%

"""

        if spec.show_confidence_intervals:
            text += f"""
**Confidence Intervals:**
{spec.confidence_level * 100:.0f}% exact confidence intervals (Clopper-Pearson method) will be
calculated for incidence rates in each treatment group.

"""

        if spec.exposure_adjusted_rates:
            text += f"""
**Exposure-Adjusted Incidence Rates:**
To account for differences in treatment duration:

Rate = (Number of events / Total exposure) × Multiplier

where:
- Total exposure = Sum of treatment durations for all subjects
- Multiplier = 100 {spec.exposure_unit} (for interpretability)
- Unit: Events per 100 {spec.exposure_unit}

**Purpose:** Adjusts for subjects discontinuing early or having different follow-up times.

"""

        text += f"""
**Reporting Threshold:**
TEAEs will be reported if occurring in ≥{spec.min_incidence_percent}% of subjects in any treatment
group, with the following exceptions:
- All Grade 3 or higher TEAEs reported regardless of frequency
- All serious TEAEs reported regardless of frequency
- All TEAEs leading to death, discontinuation, or dose modification

**Presentation:**
- Tables sorted by decreasing frequency in the experimental treatment group
- Within each SOC, PTs sorted by frequency
- SOCs sorted by frequency of any AE within that SOC

"""

        return text

    def _generate_standard_tables_section(self, spec: AEAnalysisSpec) -> str:
        """Generate standard tables specification"""
        text = """
### Standard Safety Tables

The following tables will be generated:

"""

        if spec.analyze_teae:
            text += f"""
#### Table X.1: Overview of Treatment-Emergent Adverse Events

Summary of:
- Any TEAE
- Treatment-related TEAE
- Grade 3+ TEAE
- Serious TEAE
- TEAE leading to death
- TEAE leading to treatment discontinuation
- TEAE leading to dose interruption
- TEAE leading to dose reduction

**Format:** N (%) by treatment group

#### Table X.2: TEAEs by System Organ Class and Preferred Term

All TEAEs occurring in ≥{spec.min_incidence_percent}% of subjects in any treatment group, presented as:
- Grouped by MedDRA SOC (alphabetical)
- Within SOC: PTs sorted by decreasing frequency
- N (%) for each treatment group

#### Table X.3: Treatment-Related TEAEs by SOC and PT

Subset of Table X.2 restricted to treatment-related events.

"""

        if spec.analyze_grade_3_plus:
            text += """
#### Table X.4: Grade 3 or Higher TEAEs by SOC and PT

All Grade 3, 4, or 5 TEAEs regardless of frequency.

**Separate columns for:**
- Grade 3
- Grade 4
- Grade 5 (deaths)
- Any Grade 3+ (summary)

"""

        if spec.analyze_sae:
            text += """
#### Table X.5: Serious Adverse Events by SOC and PT

All SAEs regardless of frequency.

**Presentation:**
- Grouped by MedDRA SOC
- N (%) with 95% exact CI

"""

        text += """
#### Table X.6: Most Common TEAEs (≥10% in Any Group)

Focus on frequent events for summary.

#### Table X.7: TEAEs Leading to Study Treatment Discontinuation

AEs that led to permanent discontinuation of study treatment.

#### Table X.8: Deaths

All deaths with:
- On-treatment deaths
- Deaths within 30 days of last dose
- Deaths after 30 days (with suspected relationship)

**Listings:**
- SAE Listing: All SAEs with full details
- Death Listing: Narrative description of all deaths
- AE Leading to Discontinuation: Detailed listing

"""

        return text

    def _generate_aesi_section(self, spec: AEAnalysisSpec) -> str:
        """Generate AESI section"""
        text = """
### Adverse Events of Special Interest (AESI)

AESIs are pre-specified AEs of scientific or medical interest specific to the
study treatment, disease, or patient population.

**AESI for this study:**

"""

        if spec.aesi_terms:
            for aesi in spec.aesi_terms:
                text += f"- {aesi}\n"
        else:
            text += """
- [To be specified based on drug class and mechanism]
- Examples: Hepatotoxicity, QT prolongation, immunogenicity

"""

        text += """
**AESI Analysis:**
1. Incidence of each AESI by treatment group
2. Time to onset (median and range)
3. Duration of AESI events
4. Severity distribution (CTCAE grade)
5. Outcome and resolution
6. Relationship to treatment

**Search Strategy:**
AESIs identified using:
- Standardized MedDRA Queries (SMQs) where applicable
- Custom search of relevant PT combinations
- Case-by-case medical review

**Reporting:**
Separate detailed table for each AESI category.

"""

        return text

    def _generate_dlt_section(self, spec: AEAnalysisSpec) -> str:
        """Generate DLT analysis section"""
        return f"""
### Dose-Limiting Toxicity (DLT) Analysis

**DLT Observation Period:** {spec.dlt_observation_period} days from first dose

**DLT Definition:**
A DLT is defined as any of the following events occurring during the DLT observation
period and considered related to study treatment:

**Hematologic DLTs:**
- Grade 4 neutropenia lasting >7 days
- Febrile neutropenia (ANC <1000/μL with fever ≥38.3°C)
- Grade 4 thrombocytopenia or Grade 3 with bleeding
- Grade 3 or 4 anemia

**Non-Hematologic DLTs:**
- Any Grade 3 or 4 non-hematologic toxicity (with specified exceptions)
- Exceptions: Grade 3 nausea/vomiting/diarrhea controlled within 48h

**DLT Evaluation:**
- All subjects in DLT-evaluable population assessed
- DLT-evaluable: Completed DLT observation period OR experienced DLT
- Subjects discontinuing for reasons other than DLT before completing observation
  period replaced

**Analysis:**
- DLT rate by dose level
- 95% exact binomial confidence interval
- Dose-toxicity relationship assessment

"""

    def _generate_testing_section(self, spec: AEAnalysisSpec) -> str:
        """Generate hypothesis testing section"""
        text = f"""
### Statistical Testing of Safety Endpoints

**Note:** Safety analyses are primarily descriptive. Hypothesis testing is generally
not performed for AEs unless pre-specified.

"""

        if spec.perform_hypothesis_tests:
            text += f"""
**Pre-specified Hypothesis Tests:**

For selected key safety endpoints, treatment groups will be compared using:

**Method:** {spec.test_method}

"""

            if spec.test_method == "Fisher":
                text += """
**Fisher's Exact Test:**
Appropriate for small expected cell counts.
- Two-sided test
- No continuity correction needed
- Exact p-values

"""
            elif spec.test_method == "Chi-square":
                text += """
**Chi-Square Test:**
For larger sample sizes with adequate expected cell counts (≥5).
- Two-sided test
- Continuity correction applied when appropriate

"""
            elif spec.test_method == "CMH":
                text += """
**Cochran-Mantel-Haenszel Test:**
Accounts for stratification factors from randomization.
- Stratified by randomization strata
- General association test

"""

            text += """
**Interpretation:**
- p-values are descriptive, not for regulatory decision-making
- No multiplicity adjustment (exploratory)
- Focus on clinical significance, not just statistical significance
- Compare incidence rates and confidence intervals

"""
        else:
            text += """
No formal hypothesis testing will be performed. Safety assessment will be based on:
- Clinical review of all AEs
- Comparison of incidence rates
- Assessment of severity and seriousness
- Temporal patterns
- Dose-response relationships (if applicable)

"""

        return text

    def _generate_safety_regulatory_section(self) -> str:
        """Generate regulatory considerations"""
        return """
### Regulatory Considerations

This safety analysis plan complies with:

**ICH Guidelines:**
- **ICH E2A:** Clinical Safety Data Management (Definitions, standards)
- **ICH E2C(R2):** Periodic Benefit-Risk Evaluation Report (PBRER)
- **ICH E3:** Structure and Content of Clinical Study Reports (Section 12.2 - Safety)

**FDA Guidance:**
- "Safety Assessment for IND Safety Reporting" (2015)
- "Integrated Summaries of Effectiveness and Safety" (2015)
- Pre-marketing Safety Data

**Key Principles:**

1. **Comprehensive Reporting:** All AEs reported regardless of causality assessment
2. **Coding Standards:** MedDRA for consistent terminology across trials
3. **Severity Grading:** CTCAE for objective, reproducible grading
4. **Exposure Adjustment:** Account for different treatment durations
5. **Descriptive Focus:** Emphasize clinical patterns, not hypothesis testing
6. **Special Populations:** Analyze safety in subgroups (age, organ function)

**Safety Stopping Rules:**

The trial may be stopped for safety if:
- Unexpected serious adverse reactions
- Unacceptable toxicity rate
- Unfavorable benefit-risk assessment
- Recommendation by Data Monitoring Committee (DMC)

**Safety Review:**
- Ongoing safety monitoring throughout trial
- Real-time SAE reporting to sponsor and regulatory authorities
- Periodic aggregate safety reviews
- DMC reviews at planned intervals

"""

    def generate_sas_code(self, spec: AEAnalysisSpec) -> str:
        """Generate SAS code for AE analysis"""
        return f"""
/* Adverse Event Analysis */

/* Safety population */
data adsl_safety;
    set adsl;
    where SAFFL = 'Y';  /* Safety population flag */
run;

/* Treatment-Emergent AEs */
data adae_teae;
    set adae;
    where TRTEMFL = 'Y';  /* Treatment-emergent flag */

    /* Create analysis flags */
    ANY_AE = 1;
    GRADE3_PLUS = (AETOXGR in ('3', '4', '5'));
    SERIOUS = (AESER = 'Y');
    RELATED = (AEREL in ('RELATED', 'PROBABLY RELATED', 'POSSIBLY RELATED'));
    DISC_AE = (AEACN = 'DRUG WITHDRAWN');
run;

/* Overall TEAE summary */
proc sql;
    create table ae_summary as
    select TRT01A,
           count(distinct USUBJID) as N_SUBJ,

           /* Any TEAE */
           sum(ANY_AE > 0) as ANY_TEAE,
           calculated ANY_TEAE / calculated N_SUBJ * 100 as PCT_ANY_TEAE,

           /* Grade 3+ */
           sum(GRADE3_PLUS) as N_GRADE3,
           calculated N_GRADE3 / calculated N_SUBJ * 100 as PCT_GRADE3,

           /* Serious */
           sum(SERIOUS) as N_SAE,
           calculated N_SAE / calculated N_SUBJ * 100 as PCT_SAE,

           /* Related */
           sum(RELATED) as N_RELATED,
           calculated N_RELATED / calculated N_SUBJ * 100 as PCT_RELATED,

           /* Discontinuation */
           sum(DISC_AE) as N_DISC,
           calculated N_DISC / calculated N_SUBJ * 100 as PCT_DISC

    from adae_teae
    group by TRT01A;
quit;

/* TEAEs by SOC and PT */
proc sql;
    create table ae_by_soc_pt as
    select TRT01A, AESOC, AEDECOD,
           count(distinct USUBJID) as N,
           calculated N / (select count(*) from adsl_safety where TRT01A = a.TRT01A) * 100 as PCT
    from adae_teae as a
    group by TRT01A, AESOC, AEDECOD
    having calculated PCT >= {spec.min_incidence_percent}
    order by AESOC, calculated PCT desc;
quit;

/* Exact confidence intervals using PROC FREQ */
proc freq data=adae_teae;
    tables TRT01A * GRADE3_PLUS / binomial(level='1');
    exact binomial;
    by TRT01A;
    title "Exact CI for Grade 3+ AE Rate";
run;

/* Exposure-adjusted rates */
data exposure;
    set adsl_safety;
    EXPOSURE_YEARS = TRTDUR / 365.25;  /* Convert days to years */
run;

proc sql;
    create table ae_exposure_adj as
    select TRT01A,
           count(distinct USUBJID) as N_EVENTS,
           sum(EXPOSURE_YEARS) as TOTAL_EXPOSURE,
           calculated N_EVENTS / calculated TOTAL_EXPOSURE * 100 as RATE_PER_100PY
    from adae_teae as a
    left join exposure as e
    on a.USUBJID = e.USUBJID
    group by TRT01A;
quit;
"""


# Singleton instance
_ae_analysis_service: Optional[AdverseEventAnalysisService] = None


def get_ae_analysis_service() -> AdverseEventAnalysisService:
    """
    Get adverse event analysis service instance.

    Returns:
        AdverseEventAnalysisService instance
    """
    global _ae_analysis_service

    if _ae_analysis_service is None:
        _ae_analysis_service = AdverseEventAnalysisService()

    return _ae_analysis_service
