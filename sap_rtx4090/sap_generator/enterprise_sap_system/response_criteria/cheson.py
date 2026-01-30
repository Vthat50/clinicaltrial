"""
Cheson Criteria for Lymphoma Response Assessment
================================================

Response assessment criteria for lymphoma (Hodgkin and non-Hodgkin).

Published: Cheson BD, et al. J Clin Oncol. 2007;25(5):579-586.
Updated: Cheson BD, et al. J Clin Oncol. 2014;32(27):3059-3068. (Lugano Classification)

Key features:
- Integrates CT and PET imaging (FDG-PET)
- Deauville 5-point scale for PET interpretation
- Bone marrow assessment for complete response
- Bulky disease considerations
- Clinical symptoms (B symptoms) tracked

Response categories:
- CR: Complete metabolic response
- PR: Partial metabolic response
- SD: Stable disease
- PD: Progressive disease/relapse

PET-based assessment (Lugano):
- Deauville score 1-3: Complete metabolic response
- Deauville score 4-5: Residual metabolic activity
- Interim PET and end-of-treatment PET interpreted differently

Applications:
- Hodgkin lymphoma
- Diffuse large B-cell lymphoma (DLBCL)
- Follicular lymphoma
- Other lymphoid malignancies
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ChesonResponse(Enum):
    """Cheson/Lugano response categories"""
    CMR = "CMR"  # Complete Metabolic Response
    PMR = "PMR"  # Partial Metabolic Response
    NMR = "No Metabolic Response"
    PMD = "Progressive Metabolic Disease"
    NE = "Not Evaluable"


class DeauvilleScore(Enum):
    """
    Deauville 5-point scale for PET interpretation.

    Standardized visual assessment comparing lesion uptake to reference organs.
    """
    SCORE_1 = "1"  # No uptake
    SCORE_2 = "2"  # Uptake ≤ mediastinum
    SCORE_3 = "3"  # Uptake > mediastinum but ≤ liver
    SCORE_4 = "4"  # Uptake moderately > liver
    SCORE_5 = "5"  # Uptake markedly > liver and/or new lesions
    SCORE_X = "X"  # New areas of uptake unlikely to be lymphoma


class BSymptoms(Enum):
    """B symptoms (constitutional symptoms)"""
    NONE = "None"
    FEVER = "Fever (>38°C)"
    NIGHT_SWEATS = "Night sweats"
    WEIGHT_LOSS = "Weight loss (>10% in 6 months)"
    MULTIPLE = "Multiple B symptoms"


@dataclass
class LymphomaLesion:
    """Single lymphoma lesion measurement"""
    lesion_id: str
    assessment_date: str

    # CT measurements (bidimensional)
    longest_diameter: float = 0.0          # cm
    perpendicular_diameter: float = 0.0    # cm
    product: float = 0.0                   # cm²

    # PET assessment
    pet_avid: bool = False                 # FDG-avid at baseline
    deauville_score: Optional[DeauvilleScore] = None
    suv_max: Optional[float] = None        # Optional quantitative

    # Lesion characteristics
    is_nodal: bool = True                  # vs extranodal
    is_bulky: bool = False                 # ≥10 cm or ≥1/3 thoracic diameter
    is_new: bool = False

    def calculate_product(self):
        """Calculate bidimensional product"""
        self.product = self.longest_diameter * self.perpendicular_diameter


@dataclass
class ChesonAssessment:
    """
    Single Cheson/Lugano assessment at a timepoint.

    Integrates CT imaging, PET imaging, and clinical assessment.
    """
    assessment_date: str
    assessment_number: int
    assessment_type: str = "On-treatment"  # Baseline, Interim, End-of-treatment

    # CT measurements (sum of products of perpendicular diameters)
    sum_of_products: float = 0.0           # SPD for up to 6 lesions
    individual_lesions: List[LymphomaLesion] = field(default_factory=list)

    # PET assessment
    pet_performed: bool = False
    overall_deauville: Optional[DeauvilleScore] = None  # Highest score
    complete_metabolic_response: bool = False

    # Bone marrow
    bone_marrow_involved: bool = False
    bone_marrow_assessed: bool = False

    # Clinical
    b_symptoms: BSymptoms = BSymptoms.NONE

    # Calculated from baseline
    percent_change_spd: float = 0.0

    # Response
    response: ChesonResponse = ChesonResponse.NE


@dataclass
class ChesonCriteria:
    """
    Complete Cheson/Lugano criteria implementation.

    Manages lymphoma response assessment with PET integration.
    """
    study_id: str
    baseline_assessment: ChesonAssessment
    assessments: List[ChesonAssessment] = field(default_factory=list)

    # Baseline values
    baseline_spd: float = 0.0
    baseline_pet_avid: bool = False        # Disease FDG-avid at baseline

    # Response tracking
    best_response: ChesonResponse = ChesonResponse.NE

    # Assessment timing
    interim_pet_timepoint: int = 2         # Usually after 2-4 cycles
    end_of_treatment_timepoint: int = 6

    def __post_init__(self):
        """Initialize baseline values"""
        self.baseline_spd = self.baseline_assessment.sum_of_products
        self.baseline_pet_avid = any(
            lesion.pet_avid for lesion in self.baseline_assessment.individual_lesions
        )

    def add_assessment(self, assessment: ChesonAssessment):
        """Add new assessment and determine response"""
        # Calculate percent change in SPD
        if self.baseline_spd > 0:
            assessment.percent_change_spd = (
                (assessment.sum_of_products - self.baseline_spd) /
                self.baseline_spd * 100
            )

        # Determine response
        assessment.response = self._determine_response(assessment)

        self.assessments.append(assessment)
        self._update_best_response()

    def _determine_response(self, assessment: ChesonAssessment) -> ChesonResponse:
        """
        Determine Cheson/Lugano response.

        Uses PET if disease was FDG-avid at baseline.
        Falls back to CT criteria if PET not done or disease not PET-avid.
        """
        # If PET performed and disease was PET-avid, use PET criteria
        if assessment.pet_performed and self.baseline_pet_avid:
            return self._determine_response_by_pet(assessment)
        else:
            # Use CT criteria (IWC - International Working Criteria)
            return self._determine_response_by_ct(assessment)

    def _determine_response_by_pet(self, assessment: ChesonAssessment) -> ChesonResponse:
        """
        PET-based response assessment using Deauville scale.

        Interpretation depends on timing (interim vs end-of-treatment).
        """
        if not assessment.overall_deauville:
            return ChesonResponse.NE

        deauville = assessment.overall_deauville

        # Complete Metabolic Response (CMR)
        if deauville in [DeauvilleScore.SCORE_1, DeauvilleScore.SCORE_2,
                         DeauvilleScore.SCORE_3]:
            # Score 1-3: Complete metabolic response
            # Must also check bone marrow if initially involved
            if self.baseline_assessment.bone_marrow_involved:
                if not assessment.bone_marrow_assessed:
                    logger.warning("Bone marrow assessment required for CMR")
                    return ChesonResponse.NE
                if assessment.bone_marrow_involved:
                    return ChesonResponse.PMR  # Residual BM involvement

            return ChesonResponse.CMR

        # Partial Metabolic Response (PMR)
        elif deauville == DeauvilleScore.SCORE_4:
            # Score 4: Residual uptake > liver but decreased from baseline
            # Check if uptake has decreased
            if assessment.assessment_type == "Interim":
                # Interim PET: Score 4 may still indicate response
                return ChesonResponse.PMR
            else:
                # End of treatment: Score 4 is concerning
                # Need CT correlation
                if assessment.percent_change_spd <= -50:
                    return ChesonResponse.PMR
                else:
                    return ChesonResponse.NMR

        # Progressive Metabolic Disease (PMD) or No Metabolic Response
        elif deauville == DeauvilleScore.SCORE_5:
            # Score 5: Markedly increased uptake or new lesions
            return ChesonResponse.PMD

        return ChesonResponse.NE

    def _determine_response_by_ct(self, assessment: ChesonAssessment) -> ChesonResponse:
        """
        CT-based response assessment (International Working Criteria).

        Used when PET not available or disease not FDG-avid.
        """
        # Complete Response (CR)
        if self._meets_cr_by_ct(assessment):
            return ChesonResponse.CMR

        # Progressive Disease (PD)
        if self._meets_pd_by_ct(assessment):
            return ChesonResponse.PMD

        # Partial Response (PR)
        if self._meets_pr_by_ct(assessment):
            return ChesonResponse.PMR

        # Stable Disease
        return ChesonResponse.NMR

    def _meets_cr_by_ct(self, assessment: ChesonAssessment) -> bool:
        """
        CT criteria for complete response:
        - All lymph nodes ≤1.5 cm in longest diameter
        - Spleen/liver not enlarged
        - No extranodal sites
        - Bone marrow negative (if initially positive)
        - B symptoms absent
        """
        # All nodes must be ≤1.5 cm
        for lesion in assessment.individual_lesions:
            if lesion.longest_diameter > 1.5:
                return False

        # No new lesions
        if any(lesion.is_new for lesion in assessment.individual_lesions):
            return False

        # Bone marrow check
        if self.baseline_assessment.bone_marrow_involved:
            if not assessment.bone_marrow_assessed or assessment.bone_marrow_involved:
                return False

        # B symptoms resolved
        if assessment.b_symptoms != BSymptoms.NONE:
            return False

        return True

    def _meets_pr_by_ct(self, assessment: ChesonAssessment) -> bool:
        """
        CT criteria for partial response:
        - ≥50% decrease in SPD of up to 6 largest nodes/masses
        - No new lesions
        - Spleen/liver regression
        """
        # ≥50% decrease
        if assessment.percent_change_spd > -50:
            return False

        # No new lesions
        if any(lesion.is_new for lesion in assessment.individual_lesions):
            return False

        # No increase in other nodes
        for lesion in assessment.individual_lesions:
            if not lesion.is_new and lesion.longest_diameter > 1.5:
                # Check if this node grew
                baseline_lesion = next(
                    (l for l in self.baseline_assessment.individual_lesions
                     if l.lesion_id == lesion.lesion_id), None
                )
                if baseline_lesion:
                    if lesion.product > baseline_lesion.product * 1.5:
                        return False

        return True

    def _meets_pd_by_ct(self, assessment: ChesonAssessment) -> bool:
        """
        CT criteria for progressive disease:
        - ≥50% increase in SPD from nadir, OR
        - New lesion >1.5 cm, OR
        - ≥50% increase in longest diameter of any lesion >1 cm
        """
        # New lesion
        if any(lesion.is_new and lesion.longest_diameter > 1.5
               for lesion in assessment.individual_lesions):
            return True

        # ≥50% increase from nadir (would need to track nadir)
        # For simplicity, check from baseline
        if assessment.percent_change_spd >= 50:
            return True

        # Individual lesion progression
        for lesion in assessment.individual_lesions:
            baseline_lesion = next(
                (l for l in self.baseline_assessment.individual_lesions
                 if l.lesion_id == lesion.lesion_id), None
            )
            if baseline_lesion and baseline_lesion.longest_diameter >= 1.0:
                if lesion.longest_diameter >= baseline_lesion.longest_diameter * 1.5:
                    return True

        return False

    def _update_best_response(self):
        """Update best overall response"""
        hierarchy = [ChesonResponse.CMR, ChesonResponse.PMR,
                    ChesonResponse.NMR, ChesonResponse.PMD]

        for response in hierarchy:
            if any(a.response == response for a in self.assessments):
                self.best_response = response
                return


class ChesonService:
    """
    Service for Cheson/Lugano lymphoma response criteria.

    Provides methodology and documentation for lymphoma trials.
    """

    def __init__(self):
        """Initialize Cheson service"""
        pass

    def generate_cheson_methodology(self) -> str:
        """
        Generate Cheson/Lugano methodology for SAP.

        Returns:
            Formatted SAP text
        """
        text = """
## Response Assessment: Cheson/Lugano Criteria for Lymphoma

### Background

The Lugano Classification (2014) represents the current standard for response assessment
in lymphoma trials, building upon the earlier Cheson 2007 criteria and incorporating
PET/CT imaging.

**Key Features:**

1. **PET Integration:** FDG-PET now standard for FDG-avid lymphomas
2. **Deauville Scale:** 5-point visual scale for PET interpretation
3. **Interim Assessment:** PET after 2-4 cycles prognostic/predictive
4. **Simplified Bone Marrow:** PET can replace BM biopsy in many cases

**References:**

Cheson BD, Fisher RI, Barrington SF, et al. Recommendations for initial evaluation,
staging, and response assessment of Hodgkin and non-Hodgkin lymphoma: the Lugano
classification. J Clin Oncol. 2014;32(27):3059-3068.

### Imaging Requirements

**Required Imaging:**

- **CT with contrast:** Neck, chest, abdomen, pelvis
  - Slice thickness ≤5 mm
  - Same scanner throughout study
- **FDG-PET/CT:** For FDG-avid lymphomas
  - Fasting ≥6 hours
  - Blood glucose <200 mg/dL
  - Same protocol throughout

**Timing:**

- Baseline: Within 4 weeks before treatment
- Interim PET: After 2-4 cycles (optional, prognostic)
- End-of-treatment: 6-8 weeks after completion
- Follow-up: Per protocol (typically every 3-6 months)

### Tumor Measurements

**CT-Based Assessment:**

- Measure up to 6 of the largest nodes/masses
- Bidimensional measurement (longest × perpendicular diameter)
- Sum of products of perpendicular diameters (SPD)
- Nodes must be >1.5 cm in longest diameter to be measurable

**Bulky Disease:**

- Nodal mass ≥10 cm, OR
- Mediastinal mass ≥1/3 intrathoracic diameter
- Prognostic significance
- Tracked separately in analysis

### PET Assessment - Deauville 5-Point Scale

**Visual Interpretation:**

Compare lesion uptake to reference organs:

**Score 1:** No uptake above background

**Score 2:** Uptake ≤ mediastinum

**Score 3:** Uptake > mediastinum but ≤ liver

**Score 4:** Uptake moderately increased compared to liver

**Score 5:** Uptake markedly increased compared to liver and/or new lesions

**Score X:** New areas of uptake unlikely to be related to lymphoma

**Interpretation:**

- **Scores 1-3:** Complete metabolic response (CMR)
- **Score 4:** Equivocal; depends on context (interim vs end-of-treatment)
- **Score 5:** No response or progression

**Interim vs End-of-Treatment:**

- **Interim PET (after 2-4 cycles):**
  - Score 1-3: Excellent prognosis, continue planned therapy
  - Score 4-5: Poor prognosis, consider intensification

- **End-of-Treatment PET:**
  - Score 1-3: CMR (complete response)
  - Score 4-5: Residual disease (may need biopsy)

### Response Definitions (Lugano)

#### Complete Metabolic Response (CMR)

**PET-Based (if FDG-avid at baseline):**
- Deauville score 1, 2, or 3
- No new lesions
- Bone marrow PET-negative (if initially involved)

**CT-Based (if not FDG-avid):**
- All lymph nodes ≤1.5 cm in longest diameter
- Spleen/liver not enlarged
- No extranodal disease
- Bone marrow biopsy negative (if initially positive)

**Clinical:**
- B symptoms resolved

#### Partial Metabolic Response (PMR)

**PET-Based:**
- Deauville score 4 or 5 with reduced uptake compared to baseline
- No new lesions
- Residual mass of any size permitted if metabolically improved

**CT-Based:**
- ≥50% decrease in SPD of up to 6 largest nodes/masses
- No increase in size of other nodes
- Spleen/liver must have regressed by >50% if enlarged at baseline
- No new lesions

#### No Metabolic Response (NMR)

**PET-Based:**
- Deauville score 4 or 5 with no significant change from baseline
- No new lesions

**CT-Based:**
- <50% decrease in SPD
- Does not meet criteria for PMR or PMD

#### Progressive Metabolic Disease (PMD)

**PET-Based:**
- Deauville score 4 or 5 with increased uptake from baseline, OR
- New FDG-avid foci consistent with lymphoma

**CT-Based:**
- ≥50% increase in SPD from nadir, OR
- New lesion >1.5 cm in any axis, OR
- ≥50% increase in longest diameter of any previously identified lesion >1 cm
- Splenic/hepatic nodules

### Bone Marrow Assessment

**Baseline:**
- Bone marrow biopsy required if involvement would change stage
- Not required if Stage IV already confirmed by other means

**Response Assessment:**

**For CMR:**
- If PET-negative at end of treatment: No biopsy required
- If PET-positive at end of treatment: Biopsy recommended

**Rationale:**
- PET has high negative predictive value (>90%)
- Positive PET less specific (false positives from inflammation)

### B Symptoms

**Definition:**

- **Fever:** Unexplained fever >38°C
- **Night sweats:** Drenching night sweats
- **Weight loss:** Unintentional weight loss >10% of body weight over 6 months

**Assessment:**
- Document at baseline
- Assess at each visit
- Required for complete response determination

### Best Overall Response

**Determination:**

BOR is the best response achieved from treatment start until disease progression.

**Hierarchy:**
1. CMR (complete metabolic response)
2. PMR (partial metabolic response)
3. NMR (no metabolic response)
4. PMD (progressive metabolic disease)

**Duration:**
- CMR/PMR should be confirmed on repeat imaging ≥4 weeks later for trials
  (not required in clinical practice)

### Statistical Analysis

#### Overall Response Rate (ORR)

**Definition:** ORR = (CMR + PMR) / Evaluable Population

**Analysis:**
- Exact 95% confidence interval (Clopper-Pearson)
- Comparison between arms using Cochran-Mantel-Haenszel test
- Stratified by IPI score, bulky disease, histology

#### Complete Response Rate (CRR)

**Definition:** CRR = CMR / Evaluable Population

**Analysis:**
- Primary endpoint for some lymphoma trials
- Exact 95% CI
- Same comparative methods as ORR

#### Secondary Endpoints

**Progression-Free Survival (PFS):**
- Time from randomization to progression (PMD) or death
- Kaplan-Meier estimation
- Log-rank test
- Cox proportional hazards model

**Duration of Response (DOR):**
- Time from first CMR or PMR to progression or death
- Estimated for responders only
- Kaplan-Meier method

**Event-Free Survival (EFS):**
- Time to progression, relapse, additional therapy, or death
- More comprehensive than PFS
- Recommended for Hodgkin lymphoma

### Interim PET Assessment

**Purpose:**
- Prognostic/predictive marker after 2-4 cycles
- May guide treatment adaptation

**Interpretation:**

**Hodgkin Lymphoma:**
- Negative interim PET (Deauville 1-3): Excellent prognosis
- Positive interim PET (Deauville 4-5): Consider treatment intensification

**DLBCL:**
- Negative interim PET: Favorable prognosis
- Positive interim PET: Poor prognosis, but less clear treatment modification

**Analysis:**
- Association with outcome (PFS, OS)
- Sensitivity analysis excluding interim PET-positive patients
- Subgroup analysis by interim PET result

### Bulky Disease Analysis

**Definition:**
- Nodal mass ≥10 cm in longest diameter, OR
- Mediastinal mass ≥1/3 of intrathoracic diameter on PA chest X-ray

**Analysis:**
- Subgroup analysis by bulky vs non-bulky
- Interaction test
- May predict differential treatment benefit

### Quality Control and Central Review

**PET Reading:**
- Requires trained nuclear medicine physician
- Deauville scale training essential
- Central review recommended for trials
- Inter-reader reliability assessment

**CT Measurements:**
- Same radiologist throughout if possible
- Blinded independent central review for registration trials
- Concordance analysis

### Comparison: Lugano vs Cheson 2007 vs IWC

| Feature | Lugano (2014) | Cheson (2007) | IWC (1999) |
|---------|---------------|---------------|------------|
| PET integration | Standard | Optional | Not included |
| Interpretation | Deauville scale | Visual ± SUV | N/A |
| Bone marrow | PET can replace | Biopsy required | Biopsy required |
| Measurements | Bidimensional | Bidimensional | Bidimensional |
| Response categories | 4 (CMR/PMR/NMR/PMD) | 4 (CR/PR/SD/PD) | 4 (CR/PR/SD/PD) |

### Special Considerations

#### Histology-Specific Guidelines

**Hodgkin Lymphoma:**
- Always FDG-avid → PET mandatory
- Interim PET highly prognostic
- CMR rate typically 70-85%

**DLBCL:**
- Usually FDG-avid (>95%)
- Interim PET less clearly actionable
- CMR rate 50-70% depending on IPI

**Follicular Lymphoma:**
- FDG-avid in >90%
- PFS primary endpoint (ORR less useful)
- Consider PET at progression to confirm

**Mantle Cell Lymphoma:**
- FDG-avid
- PET useful for distinguishing CR from MRD

#### Indolent vs Aggressive Lymphomas

**Aggressive (DLBCL, Hodgkin):**
- PET essential
- End-of-treatment assessment ~6-8 weeks post-therapy
- CMR goal of therapy

**Indolent (Follicular, MZL):**
- PET useful but less established
- May have prolonged PR rather than CMR
- Focus on PFS rather than ORR

### Regulatory Considerations

**FDA/EMA Acceptance:**
- Lugano criteria accepted for lymphoma trials
- PET-based endpoints increasingly accepted
- Must be pre-specified in protocol
- Central review strongly recommended for registration trials

**Endpoint Selection:**
- CMR rate acceptable for aggressive lymphomas
- PFS preferred for indolent lymphomas
- OS ultimate endpoint but requires long follow-up

"""

        return text.strip()

    def generate_cheson_sas_code(self, dataset_name: str = "ADEFF") -> str:
        """
        Generate SAS code for Cheson/Lugano analysis.

        Args:
            dataset_name: Name of ADaM efficacy dataset

        Returns:
            SAS code
        """
        code = f"""
/******************************************************************************
* Cheson/Lugano Lymphoma Response Assessment
* Generated by SAP Generator Enterprise System
******************************************************************************/

* Calculate sum of products of perpendicular diameters;
data lymphoma_measurements;
    set {dataset_name};
    where PARAMCD = 'LYMSPD';  /* Sum of products */

    * Individual lesion products;
    array lesions {{*}} AVAL1-AVAL6;  /* Up to 6 target lesions */

    sum_of_products = sum(of lesions{{*}});
run;

* Merge with PET data;
data lymphoma_pet;
    set {dataset_name};
    where PARAMCD = 'DEAUV';  /* Deauville score */

    * Interpret Deauville score;
    length pet_interpretation $20;
    if AVALC in ('1', '2', '3') then pet_interpretation = 'CMR';
    else if AVALC = '4' then pet_interpretation = 'Equivocal';
    else if AVALC = '5' then pet_interpretation = 'No Response/PD';
run;

* Combine CT and PET;
data lymphoma_response;
    merge lymphoma_measurements (rename=(AVAL=SPD))
          lymphoma_pet (keep=USUBJID AVISITN AVALC pet_interpretation);
    by USUBJID AVISITN;

    * Calculate percent change from baseline;
    if AVISITN = 0 then baseline_spd = SPD;
    retain baseline_spd;

    if baseline_spd > 0 then do;
        pct_change_spd = 100 * (SPD - baseline_spd) / baseline_spd;
    end;

    * Determine response by PET if available;
    length response $10;

    if pet_interpretation ne '' then do;
        * PET-based response;
        if pet_interpretation = 'CMR' and NEW_LESION ne 'Y' then response = 'CMR';
        else if pet_interpretation = 'Equivocal' or
                (pet_interpretation = 'No Response/PD' and pct_change_spd < 0)
            then response = 'PMR';
        else if pet_interpretation = 'No Response/PD' then response = 'PMD';
        else response = 'NMR';
    end;
    else do;
        * CT-based response (IWC);
        if SPD = 0 and NEW_LESION ne 'Y' then response = 'CMR';
        else if pct_change_spd <= -50 and NEW_LESION ne 'Y' then response = 'PMR';
        else if pct_change_spd >= 50 or NEW_LESION = 'Y' then response = 'PMD';
        else response = 'NMR';
    end;
run;

* Best Overall Response;
proc sql;
    create table best_response as
    select USUBJID,
           case
               when sum(response='CMR') > 0 then 'CMR'
               when sum(response='PMR') > 0 then 'PMR'
               when sum(response='NMR') > 0 then 'NMR'
               when sum(response='PMD') > 0 then 'PMD'
               else 'NE'
           end as best_response
    from lymphoma_response
    where AVISITN > 0
    group by USUBJID;
quit;

* Overall Response Rate (CMR + PMR);
proc freq data=best_response;
    tables TRTA*best_response / out=orr_freq;
    where best_response in ('CMR', 'PMR');
run;

* ORR with exact confidence interval;
proc freq data=best_response;
    tables TRTA / binomial(level='CMR' 'PMR');
    exact binomial;
run;

* Complete Response Rate;
proc freq data=best_response;
    tables TRTA / binomial(level='CMR');
    where best_response = 'CMR';
    exact binomial;
run;

* Interim PET analysis;
data interim_pet;
    set lymphoma_pet;
    where AVISITN in (2, 3, 4);  /* After 2-4 cycles */

    * Binary outcome: negative (1-3) vs positive (4-5);
    interim_pet_negative = (AVALC in ('1', '2', '3'));
run;

* Association with PFS;
proc lifetest data=pfs_data plots=survival;
    time AVAL*CNSR(1);
    strata interim_pet_negative;
    title 'PFS by Interim PET Result';
run;

* Bulky disease subgroup;
proc freq data=best_response;
    tables BULKY*TRTA*best_response / cmh;
    where best_response in ('CMR', 'PMR');
    title 'ORR by Bulky Disease Status';
run;
"""
        return code.strip()


# Singleton instance
_cheson_service: Optional[ChesonService] = None


def get_cheson_service() -> ChesonService:
    """
    Get Cheson service instance.

    Returns:
        ChesonService instance
    """
    global _cheson_service

    if _cheson_service is None:
        _cheson_service = ChesonService()

    return _cheson_service
