"""
International Working Group (IWG) Response Criteria for Leukemia
================================================================

Response assessment criteria for acute leukemias (AML, ALL).

Published:
- Döhner H, et al. Blood. 2017;129(4):424-447 (AML)
- Cheson BD, et al. Blood. 2003;102(12):4008-4013 (earlier IWG)

Key features:
- Bone marrow blast percentage
- Peripheral blood counts
- Extramedullary disease assessment
- Minimal residual disease (MRD) considerations
- Duration requirements for response categories

Response categories:
- CR: Complete remission
- CRi: CR with incomplete hematologic recovery
- MLFS: Morphologic leukemia-free state
- PR: Partial remission
- NR: No response/Refractory
- Relapse: After achieving CR

Applications:
- Acute myeloid leukemia (AML) trials
- Acute lymphoblastic leukemia (ALL) trials
- Myelodysplastic syndromes (MDS) - modified criteria
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IWG_Response(Enum):
    """IWG response categories for acute leukemia"""
    CR = "CR"      # Complete Remission
    CRi = "CRi"    # CR with incomplete hematologic recovery
    MLFS = "MLFS"  # Morphologic leukemia-free state
    PR = "PR"      # Partial Remission
    NR = "NR"      # No Response
    RELAPSE = "Relapse"
    NE = "Not Evaluable"


class MRDStatus(Enum):
    """Minimal Residual Disease status"""
    NEGATIVE = "MRD-negative"  # <0.1% by flow cytometry
    POSITIVE = "MRD-positive"  # ≥0.1%
    NOT_ASSESSED = "Not assessed"


@dataclass
class BoneMarrowAssessment:
    """Bone marrow assessment for leukemia response"""
    assessment_date: str
    assessment_day: int  # Days from treatment start

    # Morphology
    blast_percentage: float = 0.0  # % blasts in BM
    cellularity: str = ""  # Hypocellular, normocellular, hypercellular

    # Maturation
    normal_maturation: bool = False

    # Cytogenetics
    normal_karyotype: bool = False
    clonal_abnormality_present: bool = False

    # MRD assessment (if performed)
    mrd_status: MRDStatus = MRDStatus.NOT_ASSESSED
    mrd_method: str = ""  # Flow cytometry, PCR, NGS


@dataclass
class PeripheralBloodCounts:
    """Peripheral blood count requirements"""
    assessment_date: str

    # Absolute counts
    anc: float = 0.0  # Absolute neutrophil count (×10⁹/L)
    platelets: float = 0.0  # Platelet count (×10⁹/L)
    hemoglobin: float = 0.0  # g/dL

    # Blast assessment
    peripheral_blasts: float = 0.0  # % blasts in peripheral blood

    # Transfusion independence
    transfusion_independent: bool = False


@dataclass
class ExtramedullarydiseaseAssessment:
    """Extramedullary disease assessment"""
    assessment_date: str

    # Sites
    cns_involvement: bool = False
    testicular_involvement: bool = False
    skin_involvement: bool = False
    lymph_node_involvement: bool = False
    organomegaly: bool = False  # Liver, spleen

    # Resolution status
    all_sites_resolved: bool = False


@dataclass
class IWG_Assessment:
    """
    Complete IWG assessment at a timepoint.

    Integrates bone marrow, peripheral blood, and extramedullary disease.
    """
    assessment_date: str
    assessment_number: int
    assessment_day: int  # Days from treatment start

    # Component assessments
    bone_marrow: Optional[BoneMarrowAssessment] = None
    peripheral_blood: Optional[PeripheralBloodCounts] = None
    extramedullary: Optional[ExtramedullarydiseaseAssessment] = None

    # Response determination
    response: IWG_Response = IWG_Response.NE
    response_duration_days: int = 0  # For CR/CRi duration tracking


@dataclass
class IWG_Criteria:
    """
    Complete IWG criteria implementation for acute leukemia.
    """
    study_id: str
    baseline_assessment: IWG_Assessment
    assessments: List[IWG_Assessment] = field(default_factory=list)

    # Response tracking
    best_response: IWG_Response = IWG_Response.NE
    first_cr_date: Optional[str] = None
    relapse_date: Optional[str] = None

    # Duration requirements
    min_cr_duration_days: int = 28  # Minimum 4 weeks to confirm CR

    def add_assessment(self, assessment: IWG_Assessment):
        """Add new assessment and determine response"""
        assessment.response = self._determine_response(assessment)

        self.assessments.append(assessment)

        # Track first CR
        if assessment.response in [IWG_Response.CR, IWG_Response.CRi]:
            if self.first_cr_date is None:
                self.first_cr_date = assessment.assessment_date

        # Check for relapse
        if self.first_cr_date and assessment.response == IWG_Response.NR:
            if self._check_relapse(assessment):
                assessment.response = IWG_Response.RELAPSE
                if self.relapse_date is None:
                    self.relapse_date = assessment.assessment_date

        self._update_best_response()

    def _determine_response(self, assessment: IWG_Assessment) -> IWG_Response:
        """
        Determine IWG response category.

        Requires integration of BM, peripheral blood, and extramedullary disease.
        """
        # Complete Remission (CR)
        if self._meets_cr_criteria(assessment):
            return IWG_Response.CR

        # CR with incomplete hematologic recovery (CRi)
        if self._meets_cri_criteria(assessment):
            return IWG_Response.CRi

        # Morphologic leukemia-free state (MLFS)
        if self._meets_mlfs_criteria(assessment):
            return IWG_Response.MLFS

        # Partial Remission (PR)
        if self._meets_pr_criteria(assessment):
            return IWG_Response.PR

        # No Response
        return IWG_Response.NR

    def _meets_cr_criteria(self, assessment: IWG_Assessment) -> bool:
        """
        Complete Remission Criteria:

        1. Bone marrow: <5% blasts with normal maturation
        2. Peripheral blood:
           - ANC ≥1.0 × 10⁹/L
           - Platelets ≥100 × 10⁹/L
           - No circulating blasts
        3. No extramedullary disease
        4. Transfusion independent
        """
        # Check bone marrow
        if not assessment.bone_marrow:
            return False

        if assessment.bone_marrow.blast_percentage >= 5:
            return False

        if not assessment.bone_marrow.normal_maturation:
            return False

        # Check peripheral blood
        if not assessment.peripheral_blood:
            return False

        pb = assessment.peripheral_blood
        if pb.anc < 1.0:
            return False

        if pb.platelets < 100:
            return False

        if pb.peripheral_blasts > 0:
            return False

        if not pb.transfusion_independent:
            return False

        # Check extramedullary disease
        if assessment.extramedullary:
            if not assessment.extramedullary.all_sites_resolved:
                return False

        return True

    def _meets_cri_criteria(self, assessment: IWG_Assessment) -> bool:
        """
        CR with incomplete hematologic recovery (CRi):

        All CR criteria EXCEPT:
        - ANC may be <1.0 × 10⁹/L, OR
        - Platelets may be <100 × 10⁹/L

        Still requires <5% blasts and no circulating blasts.
        """
        if not assessment.bone_marrow or not assessment.peripheral_blood:
            return False

        # Bone marrow requirements same as CR
        if assessment.bone_marrow.blast_percentage >= 5:
            return False

        if not assessment.bone_marrow.normal_maturation:
            return False

        # Peripheral blood: NO circulating blasts (key requirement)
        if assessment.peripheral_blood.peripheral_blasts > 0:
            return False

        # But counts may be lower than CR
        # (Either ANC <1.0 OR Platelets <100, otherwise would be CR)
        pb = assessment.peripheral_blood
        incomplete_recovery = (pb.anc < 1.0 or pb.platelets < 100)

        if not incomplete_recovery:
            # If counts are good, this should be CR, not CRi
            return False

        # No extramedullary disease
        if assessment.extramedullary:
            if not assessment.extramedullary.all_sites_resolved:
                return False

        return True

    def _meets_mlfs_criteria(self, assessment: IWG_Assessment) -> bool:
        """
        Morphologic leukemia-free state (MLFS):

        - Bone marrow: <5% blasts
        - No peripheral blood requirements
        - Used when counts have not recovered yet
        """
        if not assessment.bone_marrow:
            return False

        return assessment.bone_marrow.blast_percentage < 5

    def _meets_pr_criteria(self, assessment: IWG_Assessment) -> bool:
        """
        Partial Remission (PR):

        - Bone marrow: 5-25% blasts AND decrease by ≥50% from baseline
        - Peripheral blood: As for CR
        - No extramedullary disease
        """
        if not assessment.bone_marrow or not assessment.peripheral_blood:
            return False

        # Bone marrow: 5-25% blasts
        blast_pct = assessment.bone_marrow.blast_percentage
        if blast_pct < 5 or blast_pct > 25:
            return False

        # ≥50% decrease from baseline
        baseline_blasts = self.baseline_assessment.bone_marrow.blast_percentage
        if baseline_blasts > 0:
            decrease_pct = (baseline_blasts - blast_pct) / baseline_blasts * 100
            if decrease_pct < 50:
                return False

        # Peripheral blood requirements
        pb = assessment.peripheral_blood
        if pb.anc < 1.0 or pb.platelets < 100:
            return False

        # No extramedullary disease
        if assessment.extramedullary:
            if not assessment.extramedullary.all_sites_resolved:
                return False

        return True

    def _check_relapse(self, assessment: IWG_Assessment) -> bool:
        """
        Check if assessment represents relapse after prior CR/CRi.

        Relapse criteria:
        - Bone marrow: ≥5% blasts, OR
        - Reappearance of circulating blasts, OR
        - Development of extramedullary disease
        """
        if self.first_cr_date is None:
            return False  # No prior CR to relapse from

        # Check for increased blasts
        if assessment.bone_marrow:
            if assessment.bone_marrow.blast_percentage >= 5:
                return True

        # Check for circulating blasts
        if assessment.peripheral_blood:
            if assessment.peripheral_blood.peripheral_blasts > 0:
                return True

        # Check for extramedullary disease
        if assessment.extramedullary:
            if not assessment.extramedullary.all_sites_resolved:
                return True

        return False

    def _update_best_response(self):
        """Update best overall response"""
        # Response hierarchy (best to worst)
        hierarchy = [IWG_Response.CR, IWG_Response.CRi, IWG_Response.MLFS,
                    IWG_Response.PR, IWG_Response.NR]

        for response in hierarchy:
            if any(a.response == response for a in self.assessments):
                self.best_response = response
                return


class IWG_Service:
    """
    Service for IWG leukemia response criteria.

    Provides methodology and documentation for acute leukemia trials.
    """

    def __init__(self):
        """Initialize IWG service"""
        pass

    def generate_iwg_methodology(self) -> str:
        """
        Generate IWG methodology for SAP.

        Returns:
            Formatted SAP text
        """
        text = """
## Response Assessment: IWG Criteria for Acute Leukemia

### Background

The International Working Group (IWG) criteria provide standardized response
assessment for acute myeloid leukemia (AML) and acute lymphoblastic leukemia (ALL) trials.

**Key Components:**

1. **Bone Marrow Assessment:** Blast percentage, morphology, maturation
2. **Peripheral Blood Counts:** ANC, platelets, hemoglobin
3. **Extramedullary Disease:** CNS, testicular, other sites
4. **Minimal Residual Disease:** Increasingly important prognostic marker

**References:**

Döhner H, Estey E, Grimwade D, et al. Diagnosis and management of AML in adults:
2017 ELN recommendations from an international expert panel. Blood. 2017;129(4):424-447.

Cheson BD, Bennett JM, Kopecky KJ, et al. Revised recommendations of the International
Working Group for Diagnosis, Standardization of Response Criteria, Treatment Outcomes,
and Reporting Standards for Therapeutic Trials in Acute Myeloid Leukemia.
J Clin Oncol. 2003;21(24):4642-4649.

### Assessment Schedule

**Bone Marrow Aspirate/Biopsy:**

- Day 14-21: Early assessment (for hypoplastic marrow vs persistent disease)
- Day 28-35: End of induction
- Prior to each consolidation cycle
- At suspected relapse
- End of treatment

**Peripheral Blood:**

- Daily during induction (hospitalized patients)
- Weekly during consolidation
- Monthly during maintenance (if applicable)

**Extramedullary Sites:**

- Baseline: LP for CNS, imaging for masses
- Follow-up: Per clinical indication

### Response Definitions

#### Complete Remission (CR)

**Bone Marrow:**
- <5% blasts with normal maturation of all cell lines
- No Auer rods
- No extramedullary leukemia

**Peripheral Blood:**
- Absolute neutrophil count (ANC) ≥1.0 × 10⁹/L
- Platelet count ≥100 × 10⁹/L
- No circulating blasts
- Hemoglobin (optional criterion, often low post-chemo)

**Transfusion Independence:**
- No RBC or platelet transfusions

**Duration:**
- Must persist for ≥4 weeks (28 days)

#### CR with Incomplete Hematologic Recovery (CRi)

**Same as CR EXCEPT:**

Peripheral blood counts have not fully recovered:
- ANC <1.0 × 10⁹/L, OR
- Platelets <100 × 10⁹/L

**Key Requirements:**
- Still requires <5% BM blasts
- No circulating blasts (critical)
- May require ongoing transfusions

**Clinical Significance:**
- Represents response but slower count recovery
- Prognostic value similar to CR in some contexts
- Important for elderly/prior therapy patients

#### Morphologic Leukemia-Free State (MLFS)

**Criteria:**
- Bone marrow <5% blasts
- No peripheral blood count requirements
- May have cytopenias

**Use:**
- Early timepoint assessment
- Patients with slow count recovery
- Not a formal response endpoint (descriptive)

#### Partial Remission (PR)

**Rarely used in AML, but defined as:**

**Bone Marrow:**
- 5-25% blasts (decrease of ≥50% from baseline)

**Peripheral Blood:**
- As for CR (ANC ≥1.0, Platelets ≥100)

**Extramedullary:**
- Resolution of extramedullary disease

#### No Response (NR)/Refractory Disease

**Criteria:**
- Failure to achieve CR, CRi, or MLFS
- Bone marrow blasts ≥5% (or >25% for PR)

**Subcategories:**
- **Primary refractory:** No CR after 1-2 induction courses
- **Resistant relapse:** No CR after relapse therapy

### Relapse

**Definition:**

Relapse after achieving CR/CRi, defined by ANY of:

1. **Bone marrow:** ≥5% blasts (confirmed on repeat)
2. **Circulating blasts:** Reappearance in peripheral blood
3. **Extramedullary disease:** New extramedullary leukemia
4. **Chloroma:** Biopsy-proven myeloid sarcoma

**Documentation:**

Date of relapse = date of first bone marrow showing ≥5% blasts or first
documentation of extramedullary disease.

### Minimal Residual Disease (MRD)

**Importance:**

MRD status is the strongest predictor of relapse risk in AML.

**MRD-Negative CR:**
- CR criteria met
- MRD <0.1% by multiparameter flow cytometry, OR
- MRD negative by molecular methods (NPM1, FLT3-ITD, etc.)

**Assessment Methods:**

1. **Flow Cytometry:**
   - 10-color panel
   - Sensitivity: 0.01-0.1%
   - Most common method

2. **Molecular (PCR/NGS):**
   - For patients with targetable mutations
   - Sensitivity varies by method
   - Quantitative assessment

3. **Timing:**
   - Post-induction (most important)
   - Pre-transplant
   - Post-transplant surveillance

**Prognostic Value:**

- MRD-negative post-induction: 60-70% long-term survival
- MRD-positive post-induction: 20-30% long-term survival

**Reporting:**

MRD status should be reported alongside morphologic response:
- CR MRD-negative
- CR MRD-positive
- CRi MRD-negative
- CRi MRD-positive

### Statistical Analysis

#### Complete Remission Rate (CRR)

**Definition:** CRR = CR / Evaluable Population

**Variations:**
- **CR rate:** CR only
- **CRi rate:** CRi only
- **CR/CRi rate:** Combined (common in AML)

**Analysis:**
- Exact 95% confidence interval (Clopper-Pearson)
- Comparison using Cochran-Mantel-Haenszel test
- Stratified by age, cytogenetic risk, prior therapy

#### Event-Free Survival (EFS)

**Definition:**

Time from randomization to:
- Treatment failure (no CR), OR
- Relapse from CR/CRi, OR
- Death from any cause

Whichever occurs first.

**Analysis:**
- Kaplan-Meier method
- Log-rank test for comparison
- Cox proportional hazards model

#### Relapse-Free Survival (RFS)

**Population:** Patients achieving CR/CRi

**Definition:**

Time from CR/CRi to:
- Relapse, OR
- Death from any cause

**Analysis:**
- Kaplan-Meier (in CR/CRi population only)
- Landmark analysis from CR date

#### Overall Survival (OS)

**Definition:**

Time from randomization to death from any cause.

**Analysis:**
- Primary endpoint for most AML trials
- Kaplan-Meier estimation
- Log-rank test, stratified Cox model

### Special Populations

#### Older Adults (Age ≥60)

**Modified Criteria:**

- CRi more common (slower count recovery)
- Combined CR/CRi rate often primary endpoint
- MRD assessment challenging (older assays less sensitive)

#### Relapsed/Refractory AML

**Considerations:**

- CR/CRi rate primary endpoint
- Duration of remission important
- Bridging to transplant key goal

#### Acute Promyelocytic Leukemia (APL)

**Special Considerations:**

- Molecular CR (PML-RARA negativity) required
- Differentiation syndrome monitoring
- Hematologic CR criteria same

### Quality Control

**Bone Marrow Review:**

- Central pathology review recommended for pivotal trials
- Blast count concordance assessment
- Images archived

**MRD Standardization:**

- Central laboratory for flow cytometry MRD
- Validated assays for molecular MRD
- Timing consistency across sites

### Comparison: IWG vs Other Criteria

| Feature | IWG (AML) | ELN 2017 | Older Criteria |
|---------|-----------|----------|----------------|
| CR blast threshold | <5% | <5% | <5% |
| CRi category | Yes | Yes | No (older) |
| MRD | Prognostic | Required reporting | Not included |
| Count recovery | ANC ≥1.0, Plt ≥100 | Same | Same |
| Extramedullary | Must resolve | Must resolve | Variable |

### Regulatory Considerations

**FDA/EMA Acceptance:**

- CR rate acceptable endpoint for accelerated approval
- OS required for regular approval
- MRD increasingly important (FDA guidance 2018)
- CRi controversial (some trials combine CR/CRi, others separate)

**Endpoint Selection:**

- **Induction trials:** CR/CRi rate, EFS
- **Post-remission trials:** RFS, OS
- **Relapsed/refractory:** CR/CRi rate, bridging to transplant

"""

        return text.strip()

    def generate_iwg_sas_code(self, dataset_name: str = "ADEFF") -> str:
        """Generate SAS code for IWG analysis"""
        code = f"""
/******************************************************************************
* IWG Response Assessment for Acute Leukemia
* Generated by SAP Generator Enterprise System
******************************************************************************/

* Bone marrow assessment;
data bm_assessment;
    set {dataset_name};
    where PARAMCD = 'BMBLAST';  /* Bone marrow blast percentage */

    * CR bone marrow criteria;
    bm_cr = (AVAL < 5 and NORMAL_MAT = 'Y');
run;

* Peripheral blood counts;
data pb_counts;
    set {dataset_name};
    where PARAMCD in ('ANC', 'PLAT', 'PBBLAST');

    * Transpose to wide;
proc transpose data=pb_counts out=pb_wide prefix=PB_;
    by USUBJID AVISITN VISIT;
    id PARAMCD;
    var AVAL;
run;

* Determine response;
data iwg_response;
    merge bm_assessment (keep=USUBJID AVISITN bm_cr AVAL rename=(AVAL=bm_blast))
          pb_wide;
    by USUBJID AVISITN;

    length response $10;

    * Complete Remission;
    if bm_cr = 1 and PB_ANC >= 1.0 and PB_PLAT >= 100 and
       PB_PBBLAST = 0 then response = 'CR';

    * CR with incomplete recovery;
    else if bm_cr = 1 and (PB_ANC < 1.0 or PB_PLAT < 100) and
            PB_PBBLAST = 0 then response = 'CRi';

    * Morphologic leukemia-free state;
    else if bm_blast < 5 then response = 'MLFS';

    * No response;
    else response = 'NR';
run;

* Best Overall Response;
proc sql;
    create table best_response as
    select USUBJID,
           case
               when sum(response='CR') > 0 then 'CR'
               when sum(response='CRi') > 0 then 'CRi'
               when sum(response='MLFS') > 0 then 'MLFS'
               else 'NR'
           end as best_response
    from iwg_response
    where AVISITN > 0
    group by USUBJID;
quit;

* Complete Remission Rate (CR + CRi);
proc freq data=best_response;
    tables TRTA / binomial(level='CR' 'CRi');
    where best_response in ('CR', 'CRi');
    exact binomial;
    title 'Complete Remission Rate (CR/CRi)';
run;

* Event-Free Survival;
data efs_data;
    set {dataset_name};
    where PARAMCD = 'EFS';
run;

proc lifetest data=efs_data plots=survival;
    time AVAL*CNSR(1);
    strata TRTA;
    title 'Event-Free Survival';
run;

* Overall Survival;
data os_data;
    set {dataset_name};
    where PARAMCD = 'OS';
run;

proc lifetest data=os_data plots=survival;
    time AVAL*CNSR(1);
    strata TRTA;
    title 'Overall Survival';
run;
"""
        return code.strip()


# Singleton instance
_iwg_service: Optional[IWG_Service] = None


def get_iwg_service() -> IWG_Service:
    """
    Get IWG service instance.

    Returns:
        IWG_Service instance
    """
    global _iwg_service

    if _iwg_service is None:
        _iwg_service = IWG_Service()

    return _iwg_service
