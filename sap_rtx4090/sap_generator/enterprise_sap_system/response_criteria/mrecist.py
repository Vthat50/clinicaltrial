"""
Modified RECIST (mRECIST) for Hepatocellular Carcinoma
=======================================================

Response assessment criteria specifically for HCC trials.

Published: Lencioni R, Llovet JM. J Hepatol. 2010;52(5):745-746.

Key features:
- Modified for HCC-specific imaging characteristics
- Viable tumor assessment (not just size)
- Post-treatment necrosis/lack of enhancement = response
- Accounts for locoregional therapies (TACE, ablation)
- Based on arterial phase enhancement

Response categories:
- CR: Complete response
- PR: Partial response
- SD: Stable disease
- PD: Progressive disease

Differences from RECIST 1.1:
- Uses viable tumor (enhancement) not total tumor diameter
- Post-ablation/TACE necrosis = response
- HCC-specific imaging criteria
- Accounts for vascular characteristics

Applications:
- Hepatocellular carcinoma trials
- Locoregional therapy studies
- Systemic therapy for HCC
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class mRECIST_Response(Enum):
    """mRECIST response categories"""
    CR = "CR"  # Complete Response
    PR = "PR"  # Partial Response
    SD = "SD"  # Stable Disease
    PD = "PD"  # Progressive Disease
    NE = "Not Evaluable"


@dataclass
class HCCLesion:
    """
    HCC lesion with viable tumor assessment.

    mRECIST focuses on viable (enhancing) tumor, not total size.
    """
    lesion_id: str
    assessment_date: str

    # Total lesion measurements
    total_longest_diameter: float = 0.0  # mm (entire lesion)

    # Viable tumor measurements (arterial enhancement)
    viable_longest_diameter: float = 0.0  # mm (only enhancing portion)

    # Enhancement characteristics
    arterial_enhancement: bool = False
    portal_venous_washout: bool = False

    # Lesion type
    is_target: bool = True
    is_new: bool = False

    # Treatment history
    prior_locoregional_therapy: bool = False  # TACE, ablation, etc.


@dataclass
class mRECIST_Assessment:
    """
    Single mRECIST assessment at a timepoint.

    Uses sum of viable tumor diameters, not total lesion size.
    """
    assessment_date: str
    assessment_number: int

    # Viable tumor measurements (KEY difference from RECIST)
    sum_viable_diameters: float = 0.0  # Sum of viable portions only
    individual_lesions: List[HCCLesion] = field(default_factory=list)

    # New lesions
    new_lesions_present: bool = False
    new_intrahepatic: int = 0
    new_extrahepatic: int = 0

    # Non-target lesions
    non_target_progression: bool = False

    # Calculated from baseline
    percent_change: float = 0.0

    # Response
    response: mRECIST_Response = mRECIST_Response.NE


@dataclass
class mRECIST_Criteria:
    """
    Complete mRECIST criteria implementation.

    Manages HCC-specific response assessment.
    """
    study_id: str
    baseline_assessment: mRECIST_Assessment
    assessments: List[mRECIST_Assessment] = field(default_factory=list)

    # Baseline values
    baseline_viable_sum: float = 0.0

    # Response tracking
    best_response: mRECIST_Response = mRECIST_Response.NE
    nadir_viable_sum: float = float('inf')

    def __post_init__(self):
        """Initialize baseline values"""
        self.baseline_viable_sum = self.baseline_assessment.sum_viable_diameters
        self.nadir_viable_sum = self.baseline_viable_sum

    def add_assessment(self, assessment: mRECIST_Assessment):
        """Add new assessment and determine response"""
        # Calculate percent change
        if self.baseline_viable_sum > 0:
            assessment.percent_change = (
                (assessment.sum_viable_diameters - self.baseline_viable_sum) /
                self.baseline_viable_sum * 100
            )

        # Determine response
        assessment.response = self._determine_response(assessment)

        self.assessments.append(assessment)

        # Update nadir
        if assessment.sum_viable_diameters < self.nadir_viable_sum:
            self.nadir_viable_sum = assessment.sum_viable_diameters

        # Update best response
        self._update_best_response()

    def _determine_response(self, assessment: mRECIST_Assessment) -> mRECIST_Response:
        """
        Determine mRECIST response.

        KEY: Uses viable tumor diameter, not total lesion size.
        """
        # Complete Response (CR)
        if self._meets_cr_criteria(assessment):
            return mRECIST_Response.CR

        # Progressive Disease (PD) - check before PR
        if self._meets_pd_criteria(assessment):
            return mRECIST_Response.PD

        # Partial Response (PR)
        if self._meets_pr_criteria(assessment):
            return mRECIST_Response.PR

        # Stable Disease (SD)
        return mRECIST_Response.SD

    def _meets_cr_criteria(self, assessment: mRECIST_Assessment) -> bool:
        """
        CR Criteria:
        - Disappearance of all arterial enhancement in target lesions
        - No new lesions
        """
        # No viable tumor (no enhancement)
        if assessment.sum_viable_diameters > 0:
            return False

        # No new lesions
        if assessment.new_lesions_present:
            return False

        # All target lesions show no arterial enhancement
        for lesion in assessment.individual_lesions:
            if lesion.is_target and lesion.arterial_enhancement:
                return False

        return True

    def _meets_pr_criteria(self, assessment: mRECIST_Assessment) -> bool:
        """
        PR Criteria:
        - ≥30% decrease in sum of viable tumor diameters
        - No new lesions
        - No progression of non-target lesions
        """
        # ≥30% decrease in viable tumor
        if assessment.percent_change > -30:
            return False

        # No new lesions
        if assessment.new_lesions_present:
            return False

        # No non-target progression
        if assessment.non_target_progression:
            return False

        return True

    def _meets_pd_criteria(self, assessment: mRECIST_Assessment) -> bool:
        """
        PD Criteria (any of following):
        - ≥20% increase in sum of viable diameters from nadir
        - New lesion(s)
        - Unequivocal progression of non-target lesions
        """
        # ≥20% increase from nadir
        if self.nadir_viable_sum > 0:
            increase_from_nadir = (
                (assessment.sum_viable_diameters - self.nadir_viable_sum) /
                self.nadir_viable_sum * 100
            )

            if increase_from_nadir >= 20:
                return True

        # New lesions
        if assessment.new_lesions_present:
            return True

        # Non-target progression
        if assessment.non_target_progression:
            return True

        return False

    def _update_best_response(self):
        """Update best overall response"""
        hierarchy = [mRECIST_Response.CR, mRECIST_Response.PR,
                    mRECIST_Response.SD, mRECIST_Response.PD]

        for response in hierarchy:
            if any(a.response == response for a in self.assessments):
                self.best_response = response
                return


class mRECIST_Service:
    """
    Service for mRECIST criteria.

    Provides methodology and documentation for HCC trials.
    """

    def __init__(self):
        """Initialize mRECIST service"""
        pass

    def generate_mrecist_methodology(self) -> str:
        """
        Generate mRECIST methodology for SAP.

        Returns:
            Formatted SAP text
        """
        text = """
## Response Assessment: Modified RECIST (mRECIST) for HCC

### Background

Modified RECIST (mRECIST) was developed specifically for hepatocellular carcinoma
trials to account for unique imaging characteristics and treatment responses in HCC.

**Key Differences from RECIST 1.1:**

1. **Viable Tumor Assessment:** Measures only viable (enhancing) tumor, not total size
2. **Post-Treatment Response:** Necrosis/lack of enhancement = response
3. **Locoregional Therapies:** Accounts for TACE, ablation, Y90
4. **Vascular Enhancement:** Based on arterial phase imaging

**Reference:**

Lencioni R, Llovet JM. Modified RECIST (mRECIST) assessment for hepatocellular
carcinoma. Semin Liver Dis. 2010;30(1):52-60.

### Imaging Requirements

**Required Imaging:**

- **Multiphasic CT or MRI:**
  - Arterial phase (key for viability)
  - Portal venous phase
  - Delayed phase
- **Same modality throughout study**
- **Same scanner/protocol preferred**

**Timing:**

- Baseline: Within 4 weeks before treatment
- On-treatment: Every 6-8 weeks (per protocol)
- Disease progression confirmation
- End of treatment

### Tumor Measurements

**Target Lesions:**

- Up to 2 lesions per organ
- Up to 5 lesions total
- **Measure only viable (enhancing) tumor portion**
- Viable tumor = arterial phase hyperenhancement

**Viable Tumor Definition:**

Intratumoral areas showing arterial phase hyperenhancement.
- **Measure:** Only the enhancing portion
- **Exclude:** Necrotic/non-enhancing areas
- **Method:** Longest diameter of viable tumor

**Non-Viable Tumor:**

- Necrotic areas (no enhancement)
- Post-treatment changes (TACE, ablation)
- These areas are NOT measured

### Response Definitions

#### Complete Response (CR)

**Criteria:**
- Disappearance of any intratumoral arterial enhancement in all target lesions
- No new lesions

**Note:** Lesions may still be visible on imaging, but must show no arterial enhancement.

#### Partial Response (PR)

**Criteria:**
- ≥30% decrease in sum of diameters of viable (enhancing) target lesions
- Compared to baseline
- No new lesions
- No unequivocal progression of non-target lesions

**Calculation:**
- Sum only the viable (enhancing) portions
- Baseline sum = reference for percentage decrease

#### Stable Disease (SD)

**Criteria:**
- Does not meet criteria for CR, PR, or PD
- May have minor increases or decreases in viable tumor

#### Progressive Disease (PD)

**Criteria (any of following):**

1. **≥20% increase** in sum of diameters of viable tumor, compared to nadir, OR
2. **New lesion(s)** (intrahepatic or extrahepatic), OR
3. **Unequivocal progression** of non-target lesions

**Minimum Increase:** In addition to 20% relative increase, must have ≥5mm absolute increase.

### Viable Tumor Assessment

**How to Measure Viable Tumor:**

1. **Arterial Phase Imaging:**
   - Identify areas of hyperenhancement
   - Measure longest diameter of enhancing portion

2. **Exclude Non-Viable Areas:**
   - Necrotic regions (no enhancement)
   - Cystic/liquefied areas
   - Post-treatment scars

3. **Examples:**

**Example 1: Post-TACE Response**
- Baseline: 50mm lesion, fully enhancing → 50mm viable
- Follow-up: 50mm lesion, 20mm enhancing → 20mm viable
- Change: -60% (Partial Response)
- Total size unchanged, but viable tumor decreased 60%

**Example 2: Systemic Therapy**
- Baseline: 40mm + 30mm = 70mm viable tumor
- Follow-up: 30mm + 20mm = 50mm viable tumor
- Change: -29% (near PR threshold)

### Special Considerations

#### Locoregional Therapies

**TACE (Transarterial Chemoembolization):**
- Success = devascularization (loss of enhancement)
- mRECIST captures this as tumor reduction
- RECIST 1.1 would miss response (size may be stable)

**Ablation (RFA, MWA):**
- Ablation zone should show no enhancement
- Residual enhancement at margin = residual tumor

**Y90 Radioembolization:**
- Radiation effect reduces enhancement
- May take longer than TACE (8-12 weeks)

#### Vascular Invasion

**Portal Vein Thrombosis:**
- If tumor thrombus shows enhancement → measure viable portion
- Loss of enhancement in thrombus = response

**Hepatic Vein/IVC Invasion:**
- Treated similarly to portal vein involvement

#### New Lesions

**Intrahepatic:**
- New enhancing lesion >10mm
- Document separately from target lesions

**Extrahepatic:**
- Lung, lymph nodes, bone, peritoneum
- Any size if definitively malignant

### Best Overall Response (BOR)

**Determination:**

BOR is the best response recorded from treatment start until disease progression,
taking as reference for PD the smallest measurements recorded.

**Hierarchy:**
1. CR
2. PR
3. SD
4. PD

**Duration Requirements:**

- CR/PR should be confirmed ≥4 weeks later (for trials)
- SD must persist for minimum period (e.g., ≥6-8 weeks from baseline)

### Statistical Analysis

#### Objective Response Rate (ORR)

**Definition:** ORR = (CR + PR) / Evaluable Population

**Analysis:**
- Exact 95% confidence interval (Clopper-Pearson)
- Comparison between arms using CMH test (if randomized)
- Stratified by baseline tumor burden, Child-Pugh score, ECOG

#### Secondary Endpoints

**Disease Control Rate (DCR):**
- DCR = (CR + PR + SD) / Evaluable Population
- SD must be maintained for minimum duration

**Time to Progression (TTP):**
- Time from randomization to PD
- Deaths without progression censored
- Kaplan-Meier estimation

**Progression-Free Survival (PFS):**
- Time from randomization to PD or death
- Includes death without progression
- Primary endpoint in many HCC trials

**Overall Survival (OS):**
- Ultimate endpoint for HCC trials
- Time from randomization to death from any cause

### Comparison: mRECIST vs RECIST 1.1

| Feature | mRECIST | RECIST 1.1 |
|---------|---------|------------|
| Measurement | Viable tumor only | Total lesion size |
| Enhancement | Arterial phase key | Not considered |
| Post-TACE | Captures response | May miss response |
| Necrosis | Not measured | Included in size |
| Imaging | Multiphasic required | Single phase OK |
| HCC-specific | Yes | No |

**Clinical Scenario:**

50mm HCC lesion post-TACE:
- Total size: 50mm (unchanged)
- Viable tumor: 10mm (80% necrotic)

**mRECIST:** -80% (Partial Response)
**RECIST 1.1:** 0% (Stable Disease)

mRECIST correctly captures the treatment benefit.

### Quality Control

**Central Imaging Review:**

Recommended for registration trials:
- Blinded independent central review (BICR)
- Experienced hepatobiliary radiologist
- Arterial phase review critical

**Image Quality:**
- Optimal arterial timing essential
- Portal venous phase for context
- Same protocol throughout

### Regulatory Considerations

**FDA/EMA Acceptance:**
- mRECIST accepted for HCC trials
- Must be pre-specified in protocol
- RECIST 1.1 may be assessed in parallel for comparison

**Documentation:**
- All images archived
- Enhancement patterns documented
- Treatment modifications recorded (TACE, ablation timing)

### Clinical Considerations

**When to Use mRECIST:**
- All HCC trials
- Locoregional therapy studies
- Systemic therapy for HCC
- Combination studies (systemic + locoregional)

**Child-Pugh Score Considerations:**
- Response assessment separate from hepatic function
- Child-Pugh deterioration may warrant discontinuation
- Document both tumor response and liver function

**Alpha-Fetoprotein (AFP):**
- Often assessed alongside imaging
- AFP decrease may precede imaging response
- Not part of mRECIST but important biomarker

"""

        return text.strip()

    def generate_mrecist_sas_code(self, dataset_name: str = "ADEFF") -> str:
        """Generate SAS code for mRECIST analysis"""
        code = f"""
/******************************************************************************
* mRECIST Response Assessment for HCC
* Generated by SAP Generator Enterprise System
******************************************************************************/

* Calculate sum of viable tumor diameters;
data hcc_viable;
    set {dataset_name};
    where PARAMCD = 'HCCVIAB';  /* Viable tumor measurements */

    * Sum viable diameters for target lesions;
    array lesions {{*}} AVAL1-AVAL5;  /* Up to 5 target lesions */

    sum_viable = sum(of lesions{{*}});
run;

* Calculate percent change from baseline;
data hcc_response;
    merge hcc_viable (where=(AVISITN=0) rename=(sum_viable=baseline_viable))
          hcc_viable (where=(AVISITN>0));
    by USUBJID;

    retain baseline_viable;

    if baseline_viable > 0 then do;
        pct_change = 100 * (sum_viable - baseline_viable) / baseline_viable;
    end;

    * Determine mRECIST response;
    length response $4;

    * Complete Response (no viable tumor);
    if sum_viable = 0 and NEW_LESION ne 'Y' then response = 'CR';

    * Partial Response (>=30% decrease);
    else if pct_change <= -30 and NEW_LESION ne 'Y' then response = 'PR';

    * Progressive Disease (>=20% increase or new lesions);
    else if pct_change >= 20 or NEW_LESION = 'Y' then response = 'PD';

    * Stable Disease;
    else response = 'SD';
run;

* Best Overall Response;
proc sql;
    create table best_response as
    select USUBJID,
           case
               when sum(response='CR') > 0 then 'CR'
               when sum(response='PR') > 0 then 'PR'
               when sum(response='SD') > 0 then 'SD'
               when sum(response='PD') > 0 then 'PD'
               else 'NE'
           end as best_response
    from hcc_response
    where AVISITN > 0
    group by USUBJID;
quit;

* Objective Response Rate;
proc freq data=best_response;
    tables TRTA*best_response / out=orr_freq;
    where best_response in ('CR', 'PR');
run;

* ORR with exact CI;
proc freq data=best_response;
    tables TRTA / binomial(level='CR' 'PR');
    exact binomial;
run;

* Time to Progression (TTP);
data ttp_data;
    set {dataset_name};
    where PARAMCD = 'TTP';
    * TTP censors deaths without progression;
run;

proc lifetest data=ttp_data plots=survival;
    time AVAL*CNSR(1);
    strata TRTA;
    title 'Time to Progression (mRECIST)';
run;
"""
        return code.strip()


# Singleton instance
_mrecist_service: Optional[mRECIST_Service] = None


def get_mrecist_service() -> mRECIST_Service:
    """
    Get mRECIST service instance.

    Returns:
        mRECIST_Service instance
    """
    global _mrecist_service

    if _mrecist_service is None:
        _mrecist_service = mRECIST_Service()

    return _mrecist_service
