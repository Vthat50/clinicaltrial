"""
Response Assessment in Neuro-Oncology (RANO) Criteria
=====================================================

Response assessment criteria for brain tumor trials, particularly glioblastoma.

Published: Wen PY, et al. J Clin Oncol. 2010;28(11):1963-1972.
Updated: Wen PY, et al. Lancet Oncol. 2017;18(3):e143-e152. (iRANO for immunotherapy)

Key features:
- Incorporates both imaging and clinical assessment
- Accounts for pseudoprogression (early increase mimicking progression)
- Distinguishes true progression from pseudoresponse/pseudoprogression
- Corticosteroid use affects response determination
- T1 gadolinium-enhanced and T2/FLAIR sequences required

Response categories:
- CR: Complete response
- PR: Partial response
- SD: Stable disease
- PD: Progressive disease

Differences from RECIST:
- Brain-specific considerations (edema, pseudoprogression)
- Corticosteroid dose impacts assessment
- Clinical status required (not imaging alone)
- Bidimensional measurements (product of diameters)
- T2/FLAIR changes considered for non-enhancing tumors

Applications:
- Glioblastoma trials
- High-grade glioma studies
- Brain metastases trials
- CNS lymphoma (modified RANO)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RANO_Response(Enum):
    """RANO response categories"""
    CR = "CR"   # Complete Response
    PR = "PR"   # Partial Response
    SD = "SD"   # Stable Disease
    PD = "PD"   # Progressive Disease
    NE = "Not Evaluable"


class ClinicalStatus(Enum):
    """Patient clinical status"""
    IMPROVED = "Improved"
    STABLE = "Stable"
    WORSENED = "Worsened"


class CorticosteroidUse(Enum):
    """Corticosteroid use status"""
    NONE = "None"
    STABLE = "Stable or Decreasing"
    INCREASED = "Increased"


@dataclass
class MRILesionMeasurement:
    """
    Single MRI lesion measurement for RANO.
    Bidimensional: product of longest diameter × perpendicular diameter.
    """
    lesion_id: str
    assessment_date: str

    # T1 Gadolinium-enhanced (enhancing tumor)
    t1_gad_longest_diameter: float = 0.0      # mm
    t1_gad_perpendicular_diameter: float = 0.0  # mm
    t1_gad_product: float = 0.0               # mm²

    # T2/FLAIR (non-enhancing tumor/edema)
    t2_flair_longest_diameter: float = 0.0
    t2_flair_perpendicular_diameter: float = 0.0
    t2_flair_product: float = 0.0

    # New lesions
    is_new_lesion: bool = False

    def calculate_products(self):
        """Calculate bidimensional products"""
        self.t1_gad_product = (self.t1_gad_longest_diameter *
                               self.t1_gad_perpendicular_diameter)
        self.t2_flair_product = (self.t2_flair_longest_diameter *
                                 self.t2_flair_perpendicular_diameter)


@dataclass
class RANO_Assessment:
    """
    Single RANO assessment at a timepoint.

    Requires integration of:
    - MRI imaging (T1+Gad and T2/FLAIR)
    - Clinical status
    - Corticosteroid dose
    """
    assessment_date: str
    assessment_number: int

    # Imaging measurements
    sum_t1_gad_products: float = 0.0          # Sum of products for enhancing lesions
    sum_t2_flair_products: float = 0.0        # Sum for non-enhancing
    new_lesions_present: bool = False

    # Clinical assessment
    clinical_status: ClinicalStatus = ClinicalStatus.STABLE
    corticosteroid_status: CorticosteroidUse = CorticosteroidUse.STABLE

    # Calculated from baseline
    percent_change_t1_gad: float = 0.0        # From baseline
    percent_change_t2_flair: float = 0.0

    # Response determination
    response: RANO_Response = RANO_Response.NE
    confirmed: bool = False
    confirmation_date: Optional[str] = None

    # Pseudoprogression flag
    possible_pseudoprogression: bool = False


@dataclass
class RANO_Criteria:
    """
    Complete RANO criteria implementation.

    Manages sequence of assessments and response determination.
    """
    study_id: str
    baseline_assessment: RANO_Assessment
    assessments: List[RANO_Assessment] = field(default_factory=list)

    # Baseline values
    baseline_t1_gad: float = 0.0
    baseline_t2_flair: float = 0.0

    # Response tracking
    best_response: RANO_Response = RANO_Response.NE

    # Time windows
    min_duration_weeks: int = 4               # Minimum duration for CR/PR
    pseudoprogression_window_weeks: int = 12  # Within 12 weeks of RT

    def __post_init__(self):
        """Initialize baseline values"""
        self.baseline_t1_gad = self.baseline_assessment.sum_t1_gad_products
        self.baseline_t2_flair = self.baseline_assessment.sum_t2_flair_products

    def add_assessment(self, assessment: RANO_Assessment):
        """Add new assessment and determine response"""
        # Calculate percent changes
        if self.baseline_t1_gad > 0:
            assessment.percent_change_t1_gad = (
                (assessment.sum_t1_gad_products - self.baseline_t1_gad) /
                self.baseline_t1_gad * 100
            )

        if self.baseline_t2_flair > 0:
            assessment.percent_change_t2_flair = (
                (assessment.sum_t2_flair_products - self.baseline_t2_flair) /
                self.baseline_t2_flair * 100
            )

        # Determine response
        assessment.response = self._determine_response(assessment)

        # Check for pseudoprogression
        if assessment.response == RANO_Response.PD:
            assessment.possible_pseudoprogression = self._check_pseudoprogression(
                assessment
            )

        self.assessments.append(assessment)
        self._update_best_response()

    def _determine_response(self, assessment: RANO_Assessment) -> RANO_Response:
        """
        Determine RANO response category.

        Integrates imaging, clinical status, and corticosteroid use.
        """
        # Complete Response (CR)
        if self._meets_cr_criteria(assessment):
            return RANO_Response.CR

        # Progressive Disease (PD) - check first to catch progression
        if self._meets_pd_criteria(assessment):
            return RANO_Response.PD

        # Partial Response (PR)
        if self._meets_pr_criteria(assessment):
            return RANO_Response.PR

        # Stable Disease (SD)
        return RANO_Response.SD

    def _meets_cr_criteria(self, assessment: RANO_Assessment) -> bool:
        """
        CR Criteria:
        - Complete disappearance of all enhancing disease (T1+Gad)
        - No new lesions
        - Stable or improved T2/FLAIR
        - Clinical stability or improvement
        - Off corticosteroids (or only physiologic replacement)
        - Confirmed on consecutive assessment ≥4 weeks later
        """
        # No enhancing tumor
        if assessment.sum_t1_gad_products > 0:
            return False

        # No new lesions
        if assessment.new_lesions_present:
            return False

        # T2/FLAIR stable or improved
        if assessment.percent_change_t2_flair > 25:  # Increased by >25%
            return False

        # Clinical status
        if assessment.clinical_status == ClinicalStatus.WORSENED:
            return False

        # Corticosteroid requirement
        if assessment.corticosteroid_status == CorticosteroidUse.INCREASED:
            return False

        return True

    def _meets_pr_criteria(self, assessment: RANO_Assessment) -> bool:
        """
        PR Criteria:
        - ≥50% decrease in sum of products of enhancing lesions (T1+Gad)
        - No new lesions
        - Stable or improved T2/FLAIR
        - Clinical stability or improvement
        - Stable or decreased corticosteroids
        - Confirmed on consecutive assessment ≥4 weeks later
        """
        # ≥50% decrease in enhancing tumor
        if assessment.percent_change_t1_gad > -50:  # Not ≥50% decrease
            return False

        # No new lesions
        if assessment.new_lesions_present:
            return False

        # T2/FLAIR stable or improved
        if assessment.percent_change_t2_flair > 25:
            return False

        # Clinical status
        if assessment.clinical_status == ClinicalStatus.WORSENED:
            return False

        # Corticosteroid requirement
        if assessment.corticosteroid_status == CorticosteroidUse.INCREASED:
            return False

        return True

    def _meets_pd_criteria(self, assessment: RANO_Assessment) -> bool:
        """
        PD Criteria (any of the following):
        - ≥25% increase in sum of products of enhancing lesions
        - Significant increase in T2/FLAIR non-enhancing lesion
        - New lesion
        - Clinical deterioration not attributable to other causes
        - Failure to return for evaluation due to death or deterioration
        """
        # ≥25% increase in enhancing tumor
        if assessment.percent_change_t1_gad >= 25:
            return True

        # Significant increase in T2/FLAIR
        if assessment.percent_change_t2_flair >= 25:
            return True

        # New lesions
        if assessment.new_lesions_present:
            return True

        # Clinical deterioration
        if assessment.clinical_status == ClinicalStatus.WORSENED:
            # Must consider if deterioration is due to tumor vs other causes
            # This would require clinical judgment
            return True

        return False

    def _check_pseudoprogression(self, assessment: RANO_Assessment) -> bool:
        """
        Check if apparent PD might be pseudoprogression.

        Pseudoprogression is common within 12 weeks of radiotherapy completion,
        seen in ~20-30% of patients.
        """
        # If within 12 weeks of RT completion, consider pseudoprogression
        # (Would need RT completion date from study data)

        # For now, flag any PD in early assessments
        if assessment.assessment_number <= 2:
            logger.info(f"Possible pseudoprogression at assessment {assessment.assessment_number}")
            return True

        return False

    def _update_best_response(self):
        """Update best overall response"""
        # Response hierarchy (best to worst)
        hierarchy = [RANO_Response.CR, RANO_Response.PR,
                    RANO_Response.SD, RANO_Response.PD]

        # Check for confirmed responses
        for response in hierarchy:
            if any(a.response == response and a.confirmed for a in self.assessments):
                self.best_response = response
                return

        # If no confirmed, use best unconfirmed
        for response in hierarchy:
            if any(a.response == response for a in self.assessments):
                self.best_response = response
                return

    def check_confirmation(self) -> List[RANO_Assessment]:
        """
        Check for response confirmation.

        CR and PR require confirmation ≥4 weeks later.
        PD does not require confirmation (unlike iRECIST).
        """
        needing_confirmation = []

        for i, assessment in enumerate(self.assessments):
            if assessment.response in [RANO_Response.CR, RANO_Response.PR]:
                if not assessment.confirmed:
                    # Check if next assessment confirms
                    if i + 1 < len(self.assessments):
                        next_assessment = self.assessments[i + 1]

                        # If same or better response, confirm
                        if (next_assessment.response == assessment.response or
                            (assessment.response == RANO_Response.PR and
                             next_assessment.response == RANO_Response.CR)):
                            assessment.confirmed = True
                            assessment.confirmation_date = next_assessment.assessment_date
                        else:
                            needing_confirmation.append(assessment)

        return needing_confirmation


class RANO_Service:
    """
    Service for RANO criteria.

    Provides methodology and documentation for brain tumor trials.
    """

    def __init__(self):
        """Initialize RANO service"""
        pass

    def generate_rano_methodology(self) -> str:
        """
        Generate RANO methodology for SAP.

        Returns:
            Formatted SAP text
        """
        text = """
## Response Assessment: RANO Criteria

### Background

The Response Assessment in Neuro-Oncology (RANO) criteria were developed specifically
for brain tumor trials to address limitations of MacDonald criteria and account for
unique challenges in neuro-oncology imaging assessment.

**Key Differences from RECIST:**

1. **Bidimensional Measurement:** Product of perpendicular diameters (not unidimensional)
2. **T2/FLAIR Required:** Non-enhancing tumor component assessed
3. **Clinical Status:** Neurological examination required for response
4. **Corticosteroids:** Dose affects response determination
5. **Pseudoprogression:** Common after chemoradiation (20-30% of patients)

**References:**

Wen PY, Macdonald DR, Reardon DA, et al. Updated response assessment criteria for
high-grade gliomas: response assessment in neuro-oncology working group. J Clin Oncol.
2010;28(11):1963-1972.

### Imaging Requirements

**Required MRI Sequences:**

- **T1 post-gadolinium:** Assessment of enhancing tumor
- **T2/FLAIR:** Assessment of non-enhancing tumor and edema
- Same scanner and protocol throughout study
- Central review required for pivotal trials

**Timing:**

- Baseline: Within 2 weeks before treatment start
- On-treatment: Every 8 weeks (or per protocol)
- Progressive disease confirmation: Repeat scan ≥4 weeks if needed
- End of treatment

### Tumor Measurements

**Target Lesions:**

- Up to 5 lesions total
- Measured bidimensionally on T1 post-gadolinium images
- Longest diameter × greatest perpendicular diameter
- Sum of products (SPD) = total enhancing tumor burden

**Non-Enhancing Tumor:**

- Assessed on T2/FLAIR sequences
- Measured bidimensionally if discrete
- Qualitative assessment if diffuse

**Measurable Disease:**

- Enhancing lesion: ≥10 mm × 10 mm on T1+Gad
- Non-enhancing: ≥20 mm × 20 mm on T2/FLAIR

### Response Definitions

#### Complete Response (CR)

**Imaging:**
- Complete disappearance of all enhancing disease on T1+Gad
- No new lesions
- T2/FLAIR stable or improved

**Clinical:**
- Neurologic status stable or improved
- Off corticosteroids (except physiologic replacement doses)

**Confirmation:**
- Confirmed on repeat imaging ≥4 weeks later

#### Partial Response (PR)

**Imaging:**
- ≥50% decrease in sum of products of enhancing lesions (T1+Gad)
- Compared to baseline
- No new lesions
- T2/FLAIR stable or improved

**Clinical:**
- Neurologic status stable or improved
- Corticosteroid dose stable or decreased

**Confirmation:**
- Confirmed on repeat imaging ≥4 weeks later

#### Stable Disease (SD)

**Criteria:**
- Does not meet criteria for CR, PR, or PD
- Includes minor increases or decreases that don't meet PR or PD thresholds

#### Progressive Disease (PD)

**Any of the following:**

**Imaging:**
- ≥25% increase in sum of products of enhancing lesions, OR
- Significant increase in T2/FLAIR non-enhancing lesion, OR
- Appearance of new lesion(s)

**Clinical:**
- Clear clinical deterioration not attributable to:
  - Comorbid conditions
  - Concomitant medications (e.g., steroids)
  - Toxicity
  - Other treatment effects

**Confirmation:**
- PD does NOT require confirmation
- However, consider pseudoprogression if within 12 weeks of chemoradiation

### Pseudoprogression

**Definition:**
Transient increase in contrast enhancement and/or T2/FLAIR abnormality following
chemoradiation, mimicking tumor progression but representing treatment effect.

**Frequency:**
- Occurs in 20-30% of patients
- Most common within 12 weeks of completing radiotherapy
- More common with concurrent temozolomide

**Clinical Management:**

If PD diagnosed within 12 weeks of chemoradiation completion:
- Consider repeating MRI in 4 weeks
- If imaging stabilizes or improves → Pseudoprogression (not true PD)
- If imaging worsens → Confirm as true PD
- Continue treatment pending confirmation if patient clinically stable

**Statistical Handling:**

Document cases of pseudoprogression separately:
- Initial PD designation
- Subsequent reclassification
- Sensitivity analysis including/excluding these cases

### Corticosteroid Assessment

**Importance:**
Corticosteroids reduce vascular permeability and can decrease contrast enhancement,
potentially masking tumor or creating pseudoresponse.

**Assessment:**

For response determination, document:
- Corticosteroid dose at baseline
- Corticosteroid dose at each assessment
- Change from baseline

**Response Requirements:**

- **CR:** Patient must be off corticosteroids (except replacement)
- **PR:** Corticosteroid dose stable or decreased
- **PD:** Can be determined even with increasing steroids

### Clinical Status Assessment

**Neurologic Examination:**

Assess at each visit:
- Karnofsky Performance Status (KPS) or ECOG
- Neurologic deficits (motor, sensory, cognitive, cranial nerves)
- Seizure frequency

**Impact on Response:**

- **CR/PR:** Requires stable or improved clinical status
- **PD:** Clinical deterioration may indicate PD even without imaging progression

### Best Overall Response (BOR)

**Determination:**

BOR is the best response recorded from treatment start until disease progression,
taking as reference for PD the smallest measurements recorded since baseline.

**Hierarchy:**
1. CR (confirmed)
2. PR (confirmed)
3. SD
4. PD

**Duration Requirements:**

- CR and PR must be confirmed ≥4 weeks later
- SD must be maintained for minimum interval (e.g., ≥8 weeks from baseline)

### Statistical Analysis

#### Objective Response Rate (ORR)

**Definition:** ORR = (CR + PR) / Evaluable Population

**Analysis:**
- Exact 95% confidence interval (Clopper-Pearson)
- Comparison between arms using Cochran-Mantel-Haenszel test
- Stratified by baseline KPS and other factors

#### Secondary Endpoints

**Progression-Free Survival (PFS):**
- Time from randomization to PD or death
- Kaplan-Meier method
- Log-rank test for comparison
- Cox proportional hazards model for adjusted analysis

**Duration of Response (DOR):**
- Time from first CR or PR to PD or death
- Estimated for responders only
- Kaplan-Meier method

**Disease Control Rate (DCR):**
- DCR = (CR + PR + SD) / Evaluable Population
- SD must be maintained for minimum duration (e.g., ≥12 weeks)

### Special Considerations

#### Non-Measurable Disease

**Assessment:**
- Present/absent
- Unequivocal progression

**Examples:**
- Leptomeningeal disease
- Multifocal disease too numerous to measure
- Surgical cavity only

#### Post-Treatment Changes

**Radiation Necrosis:**
- Can mimic progressive disease
- May require advanced imaging (PET, perfusion MRI)
- Biopsy may be necessary

**Post-Surgical Changes:**
- Blood products can enhance, mimicking tumor
- Wait 48-72 hours post-op for baseline MRI

#### Brain Metastases

Modified RANO can be applied:
- RECIST 1.1 often used instead
- Unidimensional measurement acceptable
- Clinical status still important
- Steroids documented

### Comparison: RANO vs MacDonald vs RECIST

| Feature | RANO | MacDonald | RECIST 1.1 |
|---------|------|-----------|------------|
| Measurement | Bidimensional | Bidimensional | Unidimensional |
| T2/FLAIR | Required | Not required | Not applicable |
| New lesions | Always PD | Always PD | Always PD |
| Clinical status | Required | Required | Not required |
| Steroids | Required | Recommended | Not considered |
| Confirmation | CR/PR only | All responses | CR/PR only |

### iRANO for Immunotherapy

For immunotherapy trials, consider **iRANO** (immunotherapy RANO):

**Key Modifications:**
- Allows continuation past initial PD if clinically stable
- Confirmation required for PD (after 3 months minimum treatment)
- Accounts for pseudoprogression more explicitly
- Same imaging requirements as RANO

**Reference:**
Okada H, Weller M, Huang R, et al. Immunotherapy response assessment in neuro-oncology:
a report of the RANO working group. Lancet Oncol. 2015;16(15):e534-e542.

### Quality Control

**Central Review:**

For pivotal trials:
- Blinded independent central review (BICR)
- Duplicate reads
- Adjudication of discrepancies
- Concordance between investigator and BICR reported

**Image Quality:**
- Pre-specified imaging protocol
- Same scanner type throughout
- Adherence to acquisition parameters
- Quality control before each visit

### Regulatory Considerations

**FDA/EMA Acceptance:**
- RANO is accepted for brain tumor trials
- Must be pre-specified in protocol
- Central review strongly recommended for registration trials
- Patient-reported outcomes increasingly important

"""

        return text.strip()

    def generate_rano_sas_code(self, dataset_name: str = "ADEFF") -> str:
        """
        Generate SAS code for RANO analysis.

        Args:
            dataset_name: Name of ADaM efficacy dataset

        Returns:
            SAS code
        """
        code = f"""
/******************************************************************************
* RANO Response Assessment Analysis
* Generated by SAP Generator Enterprise System
******************************************************************************/

* Calculate sum of products for each assessment;
data rano_measurements;
    set {dataset_name};
    where PARAMCD in ('RANOT1', 'RANOT2');  /* T1+Gad and T2/FLAIR */

    * Sum of products by visit and measurement type;
    sum_products = sum(of AVAL1-AVAL5);  /* Products of perpendicular diameters */
run;

* Transpose to wide format;
proc transpose data=rano_measurements out=rano_wide prefix=SPD_;
    by USUBJID VISIT AVISITN;
    id PARAMCD;
    var sum_products;
run;

* Calculate percent change from baseline;
data rano_changes;
    merge rano_wide (where=(AVISITN=0) rename=(SPD_RANOT1=BASE_T1 SPD_RANOT2=BASE_T2))
          rano_wide (where=(AVISITN>0));
    by USUBJID;

    * Percent change for T1+Gad (enhancing);
    if BASE_T1 > 0 then do;
        pct_change_t1 = 100 * (SPD_RANOT1 - BASE_T1) / BASE_T1;
    end;

    * Percent change for T2/FLAIR (non-enhancing);
    if BASE_T2 > 0 then do;
        pct_change_t2 = 100 * (SPD_RANOT2 - BASE_T2) / BASE_T2;
    end;

    * Determine response category;
    length response $4;

    * Complete Response;
    if SPD_RANOT1 = 0 and not NEW_LESION and
       pct_change_t2 <= 25 and CLINSTATUS ne 'WORSENED' and
       STEROID_USE ne 'INCREASED' then response = 'CR';

    * Partial Response;
    else if pct_change_t1 <= -50 and not NEW_LESION and
            pct_change_t2 <= 25 and CLINSTATUS ne 'WORSENED' and
            STEROID_USE ne 'INCREASED' then response = 'PR';

    * Progressive Disease;
    else if pct_change_t1 >= 25 or pct_change_t2 >= 25 or
            NEW_LESION or CLINSTATUS = 'WORSENED' then response = 'PD';

    * Stable Disease;
    else response = 'SD';
run;

* Best Overall Response;
proc sql;
    create table best_response as
    select USUBJID,
           case
               when sum(response='CR' and CONFIRMED=1) > 0 then 'CR'
               when sum(response='PR' and CONFIRMED=1) > 0 then 'PR'
               when sum(response='SD') > 0 then 'SD'
               when sum(response='PD') > 0 then 'PD'
               else 'NE'
           end as best_response
    from rano_changes
    group by USUBJID;
quit;

* Objective Response Rate;
proc freq data=best_response;
    tables TRTA*best_response / out=orr_freq;
    where best_response in ('CR', 'PR');
run;

* Calculate ORR with exact CI;
proc freq data=best_response;
    tables TRTA*best_response / binomial(level='1');
    where best_response in ('CR', 'PR');
    exact binomial;
run;

* Pseudoprogression analysis;
data pseudoprog;
    set rano_changes;
    where response='PD' and AVISITN <= 2;  /* Within first 2 assessments */

    * Flag for potential pseudoprogression;
    pseudo_flag = 1;

    * Would need follow-up assessment to confirm;
run;

proc print data=pseudoprog;
    title 'Potential Pseudoprogression Cases';
    var USUBJID VISIT pct_change_t1 pct_change_t2 CLINSTATUS;
run;
"""
        return code.strip()


# Singleton instance
_rano_service: Optional[RANO_Service] = None


def get_rano_service() -> RANO_Service:
    """
    Get RANO service instance.

    Returns:
        RANO_Service instance
    """
    global _rano_service

    if _rano_service is None:
        _rano_service = RANO_Service()

    return _rano_service
