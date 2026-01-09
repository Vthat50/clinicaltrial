"""
Patient-Reported Outcome (PRO) and Quality of Life (QoL) Analysis Methods
===========================================================================

Statistical methods for PRO and QoL endpoints in oncology trials.

Regulatory guidance:
- FDA: "Patient-Reported Outcome Measures: Use in Medical Product Development" (2009)
- FDA: "Core Patient-Reported Outcomes in Cancer Clinical Trials" (Draft 2021)
- EMA: "Reflection Paper on the Use of Health-Related Quality of Life" (2005)

Common instruments:
- EORTC QLQ-C30 (European Organisation for Research and Treatment of Cancer)
- FACT-G (Functional Assessment of Cancer Therapy - General)
- EQ-5D (EuroQol)
- SF-36 (Short Form Health Survey)
- PRO-CTCAE (Patient-Reported Outcomes Common Terminology Criteria)

Analysis methods:
- Mixed models for repeated measures (MMRM)
- Time to deterioration (TTD)
- Responder analysis
- Minimal Important Difference (MID)
- Area under curve (AUC)
- Pattern mixture models for missing data
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PROInstrument(Enum):
    """Standard PRO instruments"""
    EORTC_QLQ_C30 = "EORTC QLQ-C30"
    FACT_G = "FACT-G"
    EQ_5D = "EQ-5D"
    SF_36 = "SF-36"
    PRO_CTCAE = "PRO-CTCAE"
    MDASI = "MD Anderson Symptom Inventory"
    PGIC = "Patient Global Impression of Change"


class PRO_Domain(Enum):
    """PRO domains/dimensions"""
    PHYSICAL_FUNCTIONING = "Physical Functioning"
    ROLE_FUNCTIONING = "Role Functioning"
    EMOTIONAL_FUNCTIONING = "Emotional Functioning"
    COGNITIVE_FUNCTIONING = "Cognitive Functioning"
    SOCIAL_FUNCTIONING = "Social Functioning"
    GLOBAL_HEALTH = "Global Health Status/QoL"
    PAIN = "Pain"
    FATIGUE = "Fatigue"
    NAUSEA = "Nausea and Vomiting"
    DYSPNEA = "Dyspnea"


class MissingPROHandling(Enum):
    """Handling of missing PRO data"""
    MAR_LIKELIHOOD = "MAR - Likelihood-based (MMRM)"
    MNAR_PATTERN_MIXTURE = "MNAR - Pattern Mixture Model"
    LOCF = "Last Observation Carried Forward"
    MULTIPLE_IMPUTATION = "Multiple Imputation"
    WORST_CASE = "Worst Case Sensitivity"


@dataclass
class PROScale:
    """
    Specification for a PRO scale/subscale.

    Defines a specific measurement from a PRO instrument.
    """
    scale_name: str                    # e.g., "Global Health Status", "Physical Functioning"
    instrument: PROInstrument
    domain: PRO_Domain

    # Scoring
    item_numbers: List[int] = field(default_factory=list)
    score_range: Tuple[float, float] = (0, 100)
    higher_better: bool = True         # True if higher scores are better

    # Minimal Important Difference
    mid_value: Optional[float] = None  # Points change considered clinically meaningful
    mid_source: str = ""               # Literature reference for MID

    # Analysis priority
    primary_scale: bool = False
    key_secondary: bool = False


@dataclass
class TimeToDeterioration:
    """
    Time to deterioration (TTD) specification.

    TTD is time-to-event endpoint: time from baseline to first clinically
    meaningful deterioration in PRO score.
    """
    # Definition
    scale: PROScale
    deterioration_threshold: float     # Points decrease (if higher_better=True)

    # Confirmation
    require_confirmation: bool = True
    confirmation_visits: int = 1       # Sustained over N consecutive visits

    # Censoring
    censor_at_death: bool = False      # Death is competing event
    censor_at_progression: bool = False

    # Analysis method
    analysis_method: str = "Cox"       # "Cox", "Kaplan-Meier", "Fine-Gray"


@dataclass
class ResponderAnalysis:
    """
    Responder analysis specification.

    Binary classification: responder vs. non-responder based on MID.
    """
    scale: PROScale

    # Responder definition
    improvement_threshold: float       # Points improvement ≥ MID
    time_point: str                    # When to assess (e.g., "Week 12")

    # Alternative: sustained response
    sustained_response: bool = False
    sustained_duration: str = ""       # e.g., "At least 2 consecutive visits"

    # Analysis
    test_method: str = "CMH"           # "CMH", "Chi-square", "Fisher"


@dataclass
class PROAnalysisSpec:
    """
    Complete PRO analysis specification.

    Defines all aspects of PRO endpoint analysis.
    """
    # Instrument
    instrument: PROInstrument
    instrument_version: str = ""

    # Scales analyzed
    scales: List[PROScale] = field(default_factory=list)
    primary_scale: Optional[PROScale] = None

    # Assessment schedule
    assessment_times: List[str] = field(default_factory=list)  # e.g., ["Baseline", "Week 4", "Week 8"]
    assessment_window: Dict[str, int] = field(default_factory=dict)  # Time window (days)

    # Analysis methods
    continuous_analysis: bool = True   # MMRM for continuous scores
    ttd_analysis: bool = True          # Time to deterioration
    responder_analysis: bool = True    # Responder/non-responder

    # Missing data
    missing_data_method: MissingPROHandling = MissingPROHandling.MAR_LIKELIHOOD

    # Compliance
    minimum_completion_rate: float = 0.70  # Target ≥70% completion
    compliance_monitoring: bool = True

    # Multiplicity
    adjust_for_multiplicity: bool = False  # Usually not adjusted (exploratory)


@dataclass
class EORTC_QLQ_C30_Spec:
    """
    Specification for EORTC QLQ-C30 instrument.

    Standard oncology QoL instrument with 30 items.
    """
    # Functional scales (items 1-15)
    analyze_physical: bool = True      # Items 1-5
    analyze_role: bool = True          # Items 6-7
    analyze_emotional: bool = True     # Items 21-24
    analyze_cognitive: bool = True     # Items 20, 25
    analyze_social: bool = True        # Items 26-27

    # Global health / QoL (items 29-30)
    analyze_global: bool = True        # PRIMARY for many trials

    # Symptom scales (items 8-19, 28)
    analyze_fatigue: bool = True       # Items 10, 12, 18
    analyze_pain: bool = True          # Items 9, 19
    analyze_nausea: bool = True        # Items 14-15

    # Single items
    analyze_dyspnea: bool = True       # Item 8
    analyze_insomnia: bool = True      # Item 11
    analyze_appetite: bool = True      # Item 13
    analyze_constipation: bool = True  # Item 16
    analyze_diarrhea: bool = True      # Item 17
    analyze_financial: bool = True     # Item 28

    # Scoring
    use_linear_transformation: bool = True  # Transform to 0-100 scale

    # MIDs (from literature)
    functional_scales_mid: float = 5.0  # 5-10 points
    symptom_scales_mid: float = 10.0    # 10 points
    global_qol_mid: float = 10.0        # 10 points


class PROQoLService:
    """
    Service for PRO/QoL analysis specifications.

    Provides standardized methods for common PRO instruments.
    """

    def __init__(self):
        """Initialize PRO/QoL service"""
        pass

    def create_eortc_qlq_c30_spec(
        self,
        primary_scale: str = "Global Health Status"
    ) -> PROAnalysisSpec:
        """
        Create standard EORTC QLQ-C30 analysis specification.

        Args:
            primary_scale: Primary PRO endpoint

        Returns:
            PROAnalysisSpec for EORTC QLQ-C30
        """
        scales = []

        # Global Health Status / QoL (most common primary)
        global_qol = PROScale(
            scale_name="Global Health Status / QoL",
            instrument=PROInstrument.EORTC_QLQ_C30,
            domain=PRO_Domain.GLOBAL_HEALTH,
            item_numbers=[29, 30],
            score_range=(0, 100),
            higher_better=True,
            mid_value=10.0,
            mid_source="Osoba et al. 1998; Cocks et al. 2011",
            primary_scale=(primary_scale == "Global Health Status")
        )
        scales.append(global_qol)

        # Physical Functioning
        scales.append(PROScale(
            scale_name="Physical Functioning",
            instrument=PROInstrument.EORTC_QLQ_C30,
            domain=PRO_Domain.PHYSICAL_FUNCTIONING,
            item_numbers=[1, 2, 3, 4, 5],
            score_range=(0, 100),
            higher_better=True,
            mid_value=7.0,
            key_secondary=True
        ))

        # Fatigue (most common symptom in oncology)
        scales.append(PROScale(
            scale_name="Fatigue",
            instrument=PROInstrument.EORTC_QLQ_C30,
            domain=PRO_Domain.FATIGUE,
            item_numbers=[10, 12, 18],
            score_range=(0, 100),
            higher_better=False,  # Lower fatigue is better
            mid_value=10.0,
            key_secondary=True
        ))

        # Pain
        scales.append(PROScale(
            scale_name="Pain",
            instrument=PROInstrument.EORTC_QLQ_C30,
            domain=PRO_Domain.PAIN,
            item_numbers=[9, 19],
            score_range=(0, 100),
            higher_better=False,
            mid_value=10.0,
            key_secondary=True
        ))

        spec = PROAnalysisSpec(
            instrument=PROInstrument.EORTC_QLQ_C30,
            instrument_version="3.0",
            scales=scales,
            primary_scale=global_qol if primary_scale == "Global Health Status" else scales[0],
            assessment_times=["Baseline", "Week 4", "Week 8", "Week 12", "Week 16", "Week 24"],
            continuous_analysis=True,
            ttd_analysis=True,
            responder_analysis=True,
            missing_data_method=MissingPROHandling.MAR_LIKELIHOOD
        )

        return spec

    def generate_pro_methodology(
        self,
        spec: PROAnalysisSpec
    ) -> str:
        """
        Generate PRO analysis methodology for SAP.

        Args:
            spec: PRO analysis specification

        Returns:
            Formatted SAP text
        """
        text = f"""
## Patient-Reported Outcome (PRO) Analysis

### PRO Instrument

**Instrument:** {spec.instrument.value}
**Version:** {spec.instrument_version}

"""

        if spec.instrument == PROInstrument.EORTC_QLQ_C30:
            text += """
The EORTC QLQ-C30 is a 30-item questionnaire developed to assess quality of life
in cancer patients. It is one of the most widely used and validated instruments
in oncology clinical trials.

**Domains:**
- 5 functional scales (physical, role, emotional, cognitive, social)
- 1 global health status / QoL scale
- 3 symptom scales (fatigue, nausea/vomiting, pain)
- 6 single-item symptom measures

**Scoring:** All scales are linearly transformed to 0-100 scale:
- Functional scales: Higher scores = better functioning
- Symptom scales: Higher scores = more symptoms (worse)

"""

        # Assessment schedule
        text += f"""
### Assessment Schedule

PRO assessments will be completed at:
{self._format_assessment_schedule(spec.assessment_times)}

**Timing:**
- Assessments completed before clinical procedures
- Electronic data capture (ePRO) preferred for compliance
- Paper backup available

**Compliance Target:** ≥{spec.minimum_completion_rate * 100:.0f}% completion rate

"""

        # Primary PRO endpoint
        if spec.primary_scale:
            text += self._generate_primary_pro_section(spec)

        # Analysis methods
        text += self._generate_analysis_methods_section(spec)

        # Missing data
        text += self._generate_pro_missing_data_section(spec)

        # MID
        text += self._generate_mid_section(spec)

        # Interpretation
        text += self._generate_pro_interpretation_section()

        return text.strip()

    def _format_assessment_schedule(self, times: List[str]) -> str:
        """Format assessment schedule as bullet list"""
        return "\n".join([f"- {time}" for time in times])

    def _generate_primary_pro_section(self, spec: PROAnalysisSpec) -> str:
        """Generate primary PRO endpoint section"""
        scale = spec.primary_scale

        text = f"""
### Primary PRO Endpoint

**Scale:** {scale.scale_name}

**Domain:** {scale.domain.value}

**Score Range:** {scale.score_range[0]}-{scale.score_range[1]}

**Interpretation:** {'Higher scores indicate better' if scale.higher_better else 'Lower scores indicate better'} {scale.domain.value.lower()}

"""

        if scale.mid_value:
            text += f"""
**Minimal Important Difference (MID):** {scale.mid_value} points

A change of ≥{scale.mid_value} points is considered clinically meaningful based
on anchor-based and distribution-based methods reported in the literature.

**Reference:** {scale.mid_source}

"""

        return text

    def _generate_analysis_methods_section(self, spec: PROAnalysisSpec) -> str:
        """Generate analysis methods section"""
        text = """
### Statistical Analysis Methods

Multiple complementary approaches will be used to analyze PRO data:

"""

        if spec.continuous_analysis:
            text += """
#### 1. Mixed Model for Repeated Measures (MMRM)

PRO scores as continuous outcomes will be analyzed using MMRM.

**Model:**
```
PRO_score = Baseline + Treatment + Time + Treatment×Time + Stratification + ε
```

**Covariance Structure:** Unstructured (or selected by AIC/BIC)

**Primary Comparison:** Least squares mean difference at primary time point

**Advantages:**
- Uses all available data (no imputation needed under MAR)
- Accounts for correlation between time points
- Provides estimates at each assessment time

"""

        if spec.ttd_analysis:
            text += """
#### 2. Time to Deterioration (TTD)

TTD is defined as time from randomization to first clinically meaningful
deterioration in PRO score.

**Deterioration:** Decrease ≥MID points (if higher=better) from baseline

**Confirmation:** Deterioration confirmed at next scheduled assessment

**Censoring:**
- Last adequate PRO assessment without deterioration
- Study discontinuation without deterioration
- Death (may be treated as competing event)

**Analysis:**
- Kaplan-Meier curves by treatment group
- Stratified log-rank test
- Cox proportional hazards model for hazard ratio

**Interpretation:**
- HR < 1 indicates delayed deterioration (favorable for experimental)
- Median TTD: time by which 50% of patients deteriorated

"""

        if spec.responder_analysis:
            text += """
#### 3. Responder Analysis

Binary outcome: responder vs. non-responder based on clinically meaningful improvement.

**Responder Definition:**
Improvement ≥MID points at pre-specified time point

**Analysis:**
- Response rates with exact 95% confidence intervals
- Cochran-Mantel-Haenszel test stratified by randomization factors
- Odds ratio with 95% CI

**Interpretation:**
- Proportion achieving clinically meaningful improvement
- Complements continuous analysis
- Clinically intuitive

"""

        text += """
#### 4. Area Under Curve (AUC)

For overall burden/benefit over time:

**Calculation:**
AUC = ∫ PRO_score(t) dt

approximated using trapezoidal rule.

**Analysis:** Compare AUC between treatment groups using t-test or Wilcoxon

**Interpretation:** Higher AUC indicates sustained better QoL over study period

"""

        return text

    def _generate_pro_missing_data_section(self, spec: PROAnalysisSpec) -> str:
        """Generate PRO-specific missing data section"""
        text = f"""
### Missing PRO Data

**Challenge:** PRO data often have substantial missing data due to:
- Patient burden / questionnaire fatigue
- Clinical deterioration preventing completion
- Death or study discontinuation
- Administrative reasons

**Primary Analysis:** {spec.missing_data_method.value}

"""

        if spec.missing_data_method == MissingPROHandling.MAR_LIKELIHOOD:
            text += """
**MAR Assumption:**
MMRM assumes missing data are Missing At Random (MAR) - missingness may depend
on observed data (baseline, previous assessments) but not on unobserved data.

**Validity:**
- Appropriate if missingness related to baseline characteristics, treatment, time
- Questionable if missingness related to unobserved declining health

"""

        text += """
**Sensitivity Analyses:**

1. **Pattern Mixture Model**
   - Stratify by missing data pattern (completers vs. early dropouts)
   - Estimate treatment effect within each pattern
   - Combine using weighted average

2. **Tipping Point Analysis**
   - Assess how much departure from MAR needed to change conclusions
   - Vary assumptions about missing values

3. **Multiple Imputation under MNAR**
   - Impute missing values under pessimistic assumptions
   - Re-analyze imputed datasets

4. **Completers Analysis**
   - Restricted to patients with data at primary time point
   - May be biased but provides comparison

**Compliance Monitoring:**
- PRO completion rates monitored throughout trial
- Rates compared between treatment groups
- Differential missingness investigated

"""

        return text

    def _generate_mid_section(self, spec: PROAnalysisSpec) -> str:
        """Generate MID interpretation section"""
        return """
### Minimal Important Difference (MID)

The MID is the smallest change in PRO score that patients perceive as beneficial
or harmful and that would lead to a change in management.

**Determination Methods:**

1. **Anchor-Based:** Link PRO changes to external anchors (e.g., clinician rating, ECOG change)
2. **Distribution-Based:** Often 0.5 SD or 1 SEM of baseline score
3. **Literature:** Published MIDs from previous studies

**Application:**

- **Responder Analysis:** Classify individuals as improved/stable/deteriorated
- **Time to Deterioration:** Define event as MID worsening
- **Clinical Significance:** Interpret whether statistically significant differences are clinically meaningful

**Instrument-Specific MIDs:**

| Instrument | Scale | MID |
|------------|-------|-----|
| EORTC QLQ-C30 | Global Health/QoL | 10 points |
| EORTC QLQ-C30 | Functional scales | 5-10 points |
| EORTC QLQ-C30 | Symptom scales | 10 points |
| FACT-G | Total score | 5-7 points |
| EQ-5D | Utility index | 0.074 |

**Note:** MIDs may vary by:
- Cancer type
- Disease severity
- Patient population
- Direction of change (improvement vs. deterioration)

"""

    def _generate_pro_interpretation_section(self) -> str:
        """Generate interpretation guidance for PRO"""
        return """
### Interpretation Framework

**Statistical Significance vs. Clinical Meaning:**

A statistically significant difference may not be clinically meaningful if:
- Difference < MID
- Not sustained over time
- Affected by missing data

Conversely, a non-significant result may still be clinically relevant if:
- Confidence interval overlaps MID
- Trend favors treatment
- Small sample size (power issue)

**Multiplicity:**

PRO endpoints are typically secondary/exploratory. Multiple PRO scales analyzed
without formal multiplicity adjustment.

**Interpretation:**
- Focus on consistency across analyses (MMRM, TTD, responders)
- Consider pattern across related scales
- Integrate with efficacy and safety
- Report effect sizes and confidence intervals, not just p-values

**Regulatory Considerations:**

Per FDA PRO Guidance (2009):
- Pre-specify PRO endpoints and analysis methods
- Justify instrument selection and validation
- Define MID and responder criteria
- Plan for missing data
- Consider multiplicity if PRO is co-primary

**Reporting:**

Per CONSORT PRO Extension:
- Report completion rates at each time point
- Compare completion rates between groups
- Report reasons for missing data
- Present both statistical and clinical significance

**Clinical Context:**

PRO results should be interpreted alongside:
- Survival outcomes (OS, PFS)
- Response rates
- Safety profile
- Treatment duration and compliance

Favorable PRO profile supports treatment benefit even if survival gains are modest.

"""

    def generate_ttd_code(self, ttd_spec: TimeToDeterioration, language: str = "SAS") -> str:
        """Generate code for time to deterioration analysis"""

        if language == "SAS":
            return f"""
/* Time to Deterioration Analysis */

/* Create TTD endpoint */
data adqs_ttd;
    set adqs;
    where PARAMCD = '{ttd_spec.scale.scale_name[:8].upper()}' and ANL01FL = 'Y';

    /* Flag deterioration (change from baseline) */
    DETERIOR = 0;
    if CHG <= -{ttd_spec.deterioration_threshold} then DETERIOR = 1;  /* Assuming higher=better */

    /* Time to event */
    retain TTD_EVENT TTD_CENSOR TTD_TIME;

    by USUBJID;
    if first.USUBJID then do;
        TTD_EVENT = 0;
        TTD_CENSOR = 1;
        TTD_TIME = .;
    end;

    if DETERIOR = 1 and TTD_EVENT = 0 then do;
        TTD_EVENT = 1;
        TTD_CENSOR = 0;
        TTD_TIME = ADY;  /* Analysis day */
    end;

    if last.USUBJID and TTD_EVENT = 0 then do;
        /* Censored at last assessment */
        TTD_TIME = ADY;
    end;

    if last.USUBJID;
run;

/* Kaplan-Meier analysis */
proc lifetest data=adqs_ttd plots=survival(atrisk=0 to 365 by 30);
    time TTD_TIME * TTD_CENSOR(1);
    strata TRT01P;
    title "Time to Deterioration: {ttd_spec.scale.scale_name}";
run;

/* Cox model */
proc phreg data=adqs_ttd;
    class TRT01P (ref='Control') STRATA1;
    model TTD_TIME * TTD_CENSOR(1) = TRT01P / risklimits;
    hazardratio TRT01P / diff=ref;
    title "Cox Model for TTD";
run;
"""

        return ""


# Singleton instance
_pro_qol_service: Optional[PROQoLService] = None


def get_pro_qol_service() -> PROQoLService:
    """
    Get PRO/QoL service instance.

    Returns:
        PROQoLService instance
    """
    global _pro_qol_service

    if _pro_qol_service is None:
        _pro_qol_service = PROQoLService()

    return _pro_qol_service
