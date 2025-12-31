#!/usr/bin/env python3
"""
Specialized Oncology Templates
==============================

Extends SAP generation to cover:
1. Hematologic malignancies (Lugano, IMWG, ELN criteria)
2. Phase 1 dose-escalation (3+3, CRM, BOIN, mTPI)
3. Basket/umbrella/platform trials
4. CAR-T and cell therapy (CRS, ICANS, neurotoxicity)

These fill gaps in the RAG training data for specialized oncology trials.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# HEMATOLOGIC MALIGNANCIES
# =============================================================================

class HematologicCriteria(Enum):
    """Response criteria for hematologic malignancies"""
    LUGANO = "lugano"           # Lymphoma (NHL, HL)
    IMWG = "imwg"               # Multiple Myeloma
    ELN = "eln"                 # AML
    IWCLL = "iwcll"             # CLL
    IWG_MDS = "iwg_mds"         # MDS


HEMATOLOGIC_TEMPLATES = {
    HematologicCriteria.LUGANO: {
        "name": "Lugano Classification (2014)",
        "indication": ["Non-Hodgkin Lymphoma", "Hodgkin Lymphoma", "NHL", "HL", "DLBCL", "Follicular Lymphoma"],
        "primary_endpoints": ["Overall Response Rate (ORR)", "Complete Response (CR)", "Progression-Free Survival (PFS)"],
        "response_categories": {
            "CR": "Complete Metabolic Response - Deauville Score 1-3 with no new lesions",
            "PR": "Partial Metabolic Response - Deauville Score 4-5 with reduced uptake from baseline",
            "SD": "Stable Disease - No metabolic response, no progression",
            "PD": "Progressive Disease - Deauville Score 4-5 with increased uptake or new lesions"
        },
        "assessment_method": "PET-CT using Deauville 5-point scale",
        "timepoints": ["End of Treatment", "Week 12", "Week 24"],
        "statistical_methods": """
### Primary Analysis: Overall Response Rate (ORR)

**Definition:** ORR = CR + PR per Lugano 2014 criteria assessed by Independent Review Committee (IRC)

**Response Assessment:**
| Category | Lugano Criteria | Deauville Score |
|----------|-----------------|-----------------|
| CR | Complete metabolic response | 1, 2, or 3 |
| PR | Partial metabolic response | 4 or 5 (reduced from baseline) |
| SD | No metabolic response | 4 or 5 (no change) |
| PD | Progressive metabolic disease | 4 or 5 (increased) or new lesions |

**Analysis Method:**
- Point estimate with exact 95% Clopper-Pearson CI
- Stratified by IPI risk score (Low/Intermediate/High)
- CMH test for treatment comparison (if applicable)

**Minimal Residual Disease (MRD) Assessment:**
- Flow cytometry (sensitivity 10⁻⁴)
- Next-generation sequencing (sensitivity 10⁻⁶)
- MRD negativity rate as secondary endpoint
""",
        "sample_size_considerations": """
**Sample Size for ORR:**
- H₀: ORR ≤ 40% (historical control)
- H₁: ORR ≥ 60% (clinically meaningful)
- Simon's two-stage optimal design:
  - Stage 1: n₁ = 19, r₁ = 7 (≥8 responses to continue)
  - Stage 2: n = 54, r = 27 (≥28 responses to reject H₀)
  - α = 0.05 (one-sided), Power = 80%
"""
    },

    HematologicCriteria.IMWG: {
        "name": "International Myeloma Working Group (IMWG) Criteria",
        "indication": ["Multiple Myeloma", "Myeloma", "Plasma Cell Neoplasm"],
        "primary_endpoints": ["Overall Response Rate (ORR)", "Very Good Partial Response or better (≥VGPR)",
                             "Complete Response (CR)", "Stringent Complete Response (sCR)", "PFS", "MRD negativity"],
        "response_categories": {
            "sCR": "Stringent CR - CR + normal FLC ratio + absence of clonal plasma cells by immunohistochemistry",
            "CR": "Complete Response - Negative immunofixation, <5% plasma cells, disappearance of soft tissue plasmacytomas",
            "VGPR": "Very Good PR - M-protein detectable by immunofixation but not electrophoresis, or ≥90% reduction in serum M-protein",
            "PR": "Partial Response - ≥50% reduction in serum M-protein and ≥90% reduction in 24-hr urine M-protein",
            "MR": "Minimal Response - 25-49% reduction in serum M-protein",
            "SD": "Stable Disease - Not meeting criteria for CR, VGPR, PR, MR, or PD",
            "PD": "Progressive Disease - ≥25% increase in serum or urine M-protein, or new bone lesions"
        },
        "assessment_method": "Serum/urine protein electrophoresis, immunofixation, FLC assay, bone marrow biopsy",
        "statistical_methods": """
### Primary Analysis: ≥VGPR Rate or MRD Negativity

**IMWG Response Categories:**
| Response | Criteria |
|----------|----------|
| sCR | CR + normal FLC ratio + no clonal PCs by IHC/IF |
| CR | Negative IF serum/urine, ≤5% BM PCs, no plasmacytomas |
| VGPR | IF+ but SPEP-, or ≥90% M-protein reduction |
| PR | ≥50% M-protein reduction |
| MR | 25-49% M-protein reduction |
| SD | Not meeting other criteria |
| PD | ≥25% increase from nadir |

**MRD Assessment (IMWG 2016):**
- Method: Next-generation flow cytometry (NGF) or NGS
- Sensitivity: 10⁻⁵ or 10⁻⁶
- Sustained MRD negativity: Negative at ≥1 year apart

**Analysis:**
- ORR (≥PR): Point estimate with 95% CI
- ≥VGPR rate: Key secondary endpoint
- MRD negativity rate at 10⁻⁵ sensitivity
- Duration of response (DOR) using Kaplan-Meier
- Time to next treatment (TTNT)
""",
    },

    HematologicCriteria.ELN: {
        "name": "European LeukemiaNet (ELN) 2022 Criteria",
        "indication": ["Acute Myeloid Leukemia", "AML"],
        "primary_endpoints": ["Complete Remission (CR)", "CR with incomplete hematologic recovery (CRi)",
                             "Event-Free Survival (EFS)", "Overall Survival (OS)", "MRD negativity"],
        "response_categories": {
            "CR": "Complete Remission - <5% blasts, ANC ≥1.0×10⁹/L, platelets ≥100×10⁹/L, no Auer rods",
            "CRi": "CR with incomplete recovery - CR criteria but ANC <1.0×10⁹/L or platelets <100×10⁹/L",
            "CRh": "CR with partial hematologic recovery - <5% blasts, ANC ≥0.5×10⁹/L, platelets ≥50×10⁹/L",
            "MLFS": "Morphologic Leukemia-Free State - <5% blasts, no hematologic requirements",
            "PR": "Partial Remission - 5-25% blasts with ≥50% decrease",
            "PD": "Progressive Disease - >25% increase in blasts or new extramedullary disease"
        },
        "risk_stratification": {
            "Favorable": ["t(8;21), inv(16), NPM1 mutated without FLT3-ITD"],
            "Intermediate": ["NPM1 mutated with FLT3-ITD, Wild-type NPM1 without FLT3-ITD"],
            "Adverse": ["Complex karyotype, TP53 mutation, RUNX1 mutation, ASXL1 mutation"]
        },
        "statistical_methods": """
### Primary Analysis: CR/CRi Rate and EFS

**ELN 2022 Response Categories:**
| Response | Bone Marrow | ANC | Platelets |
|----------|-------------|-----|-----------|
| CR | <5% blasts | ≥1.0×10⁹/L | ≥100×10⁹/L |
| CRi | <5% blasts | <1.0×10⁹/L or | <100×10⁹/L |
| CRh | <5% blasts | ≥0.5×10⁹/L | ≥50×10⁹/L |
| MLFS | <5% blasts | No requirement | No requirement |

**Event-Free Survival (EFS):**
- Events: Failure to achieve CR/CRi, relapse, death
- Kaplan-Meier estimation with 95% CI
- Stratified log-rank test by ELN risk category

**MRD Assessment:**
- Multiparameter flow cytometry (MFC): sensitivity 10⁻³ to 10⁻⁴
- RT-qPCR for fusion transcripts (if applicable): 10⁻⁴ to 10⁻⁵
- NGS for NPM1/other mutations: 10⁻³ to 10⁻⁴

**Stratification Factors:**
- ELN 2022 risk category (Favorable/Intermediate/Adverse)
- Age (<60 vs ≥60 years)
- De novo vs secondary AML
"""
    }
}


# =============================================================================
# PHASE 1 DOSE-ESCALATION DESIGNS
# =============================================================================

class Phase1Design(Enum):
    """Phase 1 dose-escalation designs"""
    RULE_3_3 = "3+3"
    CRM = "crm"                 # Continual Reassessment Method
    BOIN = "boin"               # Bayesian Optimal Interval
    MTPI = "mtpi"               # Modified Toxicity Probability Interval
    KEYBOARD = "keyboard"       # Keyboard design
    I3_3 = "i3+3"               # Interval 3+3


PHASE1_TEMPLATES = {
    Phase1Design.RULE_3_3: {
        "name": "Traditional 3+3 Design",
        "description": "Rule-based dose escalation with cohorts of 3 patients",
        "primary_endpoint": "Maximum Tolerated Dose (MTD)",
        "dlt_window": "Cycle 1 (typically 21-28 days)",
        "escalation_rules": """
### 3+3 Dose Escalation Rules

**Decision Rules:**
| DLTs in 3 pts | Action |
|---------------|--------|
| 0/3 | Escalate to next dose level |
| 1/3 | Expand cohort to 6 patients |
| ≥2/3 | De-escalate or stop |

**After Expansion to 6:**
| DLTs in 6 pts | Action |
|---------------|--------|
| ≤1/6 | Escalate to next dose level |
| ≥2/6 | MTD exceeded; de-escalate |

**MTD Definition:** Highest dose with <33% DLT rate (≤1/6 DLTs)
""",
        "statistical_methods": """
### Statistical Analysis for 3+3 Design

**Primary Objective:** Determine MTD and recommended Phase 2 dose (RP2D)

**DLT Evaluation:**
- DLT window: Cycle 1 (Day 1-28)
- DLT-evaluable population: Received ≥80% of planned dose OR experienced DLT

**Dose-Toxicity Analysis:**
- DLT rate with exact 95% CI at each dose level
- Isotonic regression for dose-toxicity relationship
- No formal statistical model (rule-based)

**Safety Analysis:**
- All AEs by dose level, grade, and relationship
- SAEs and DLTs summarized separately
- Exposure-response analysis (optional)

**Sample Size:**
- Minimum: 2-6 patients per dose level
- Expected: 15-30 patients total (depending on dose levels)
- No formal power calculation (exploratory)
"""
    },

    Phase1Design.CRM: {
        "name": "Continual Reassessment Method (CRM)",
        "description": "Model-based Bayesian dose-finding design",
        "primary_endpoint": "Maximum Tolerated Dose (MTD)",
        "target_dlt_rate": "20-33% (typically 25%)",
        "statistical_methods": """
### Continual Reassessment Method (CRM)

**Model:** Single-parameter power model
```
P(DLT | dose_i) = p_i^exp(β)
```
Where p_i = prior skeleton probability for dose i

**Prior Skeleton (Example for 5 dose levels):**
| Dose Level | Prior P(DLT) |
|------------|--------------|
| 1 | 0.05 |
| 2 | 0.10 |
| 3 | 0.20 |
| 4 | 0.30 |
| 5 | 0.50 |

**Target DLT Rate:** θ = 0.25 (25%)

**Escalation Rules:**
1. Treat first patient at starting dose (typically Level 1 or 2)
2. After each patient, update posterior estimate of β
3. Assign next patient to dose with P(DLT) closest to target θ
4. Apply safety constraints:
   - No skipping untested doses (modified CRM)
   - Stop if P(DLT at lowest dose) > 0.95

**Stopping Rules:**
- Maximum sample size reached (typically 24-36 patients)
- MTD identified with adequate precision (95% CI width <0.20)
- All doses too toxic: P(DLT at dose 1) > θ + 0.10

**MTD Selection:** Dose with posterior P(DLT) closest to target θ

**Software:** dfcrm (R), bcrm (R), FACTS
""",
        "sample_size": "24-36 patients (model-based, more efficient than 3+3)"
    },

    Phase1Design.BOIN: {
        "name": "Bayesian Optimal Interval (BOIN) Design",
        "description": "Interval-based design with Bayesian optimization",
        "primary_endpoint": "Maximum Tolerated Dose (MTD)",
        "target_dlt_rate": "Configurable (typically 0.25-0.30)",
        "statistical_methods": """
### BOIN Design

**Target DLT Rate:** θ = 0.30 (or study-specific)

**Interval Boundaries (for θ=0.30):**
- λ₁ = 0.236 (escalation boundary)
- λ₂ = 0.359 (de-escalation boundary)

**Decision Rules:**
| Observed DLT Rate | Action |
|-------------------|--------|
| p̂ ≤ λ₁ (≤0.236) | Escalate to next dose |
| λ₁ < p̂ < λ₂ | Stay at current dose |
| p̂ ≥ λ₂ (≥0.359) | De-escalate |

**Equivalently (for cohort of 3):**
| DLTs | Action |
|------|--------|
| 0/3 | Escalate |
| 1/3 | Stay |
| ≥2/3 | De-escalate |

**Early Stopping (Dose Elimination):**
- P(p_j > θ | data) > 0.95 → Eliminate dose j and higher

**MTD Selection:**
- Isotonic regression to estimate DLT probabilities
- Select dose with estimated P(DLT) closest to θ
- Require ≥6 patients treated at MTD

**Advantages over 3+3:**
- Pre-specified operating characteristics
- Better MTD selection accuracy
- Transparent design boundaries

**Software:** BOIN R package, web app (www.trialdesign.org)
""",
        "sample_size": "24-36 patients"
    },

    Phase1Design.MTPI: {
        "name": "Modified Toxicity Probability Interval (mTPI)",
        "description": "Interval-based design using posterior probability",
        "primary_endpoint": "Maximum Tolerated Dose (MTD)",
        "statistical_methods": """
### mTPI Design

**Target Interval:** (θ - ε₁, θ + ε₂)
- Example: θ = 0.25, ε₁ = 0.05, ε₂ = 0.05
- Target interval: (0.20, 0.30)

**Unit Probability Mass (UPM):**
Calculate posterior probability in three regions:
1. Under-dosing: (0, θ - ε₁)
2. Target: (θ - ε₁, θ + ε₂)
3. Over-dosing: (θ + ε₂, 1)

**Decision Rule:**
- Escalate if UPM(under-dosing) is highest
- Stay if UPM(target) is highest
- De-escalate if UPM(over-dosing) is highest

**Prior:** Beta(1, 1) - non-informative

**Software:** mTPI R package
"""
    }
}


# =============================================================================
# BASKET/UMBRELLA/PLATFORM TRIALS
# =============================================================================

class MasterProtocolType(Enum):
    """Types of master protocol designs"""
    BASKET = "basket"
    UMBRELLA = "umbrella"
    PLATFORM = "platform"


MASTER_PROTOCOL_TEMPLATES = {
    MasterProtocolType.BASKET: {
        "name": "Basket Trial Design",
        "description": "Single drug tested across multiple tumor types with common molecular alteration",
        "example": "Drug X in BRAF V600E+ tumors (melanoma, CRC, NSCLC, thyroid)",
        "statistical_methods": """
### Basket Trial Statistical Methods

**Design:** Multiple parallel cohorts (baskets) by tumor type

**Primary Endpoint:** ORR per cohort

**Statistical Approach Options:**

**1. Independent Analysis (No Borrowing):**
- Analyze each basket separately
- Simon's two-stage design per basket
- α = 0.05 per basket (or adjusted)

**2. Bayesian Hierarchical Model (BHM):**
```
θᵢ ~ N(μ, τ²)      # Basket-specific response rate
μ ~ N(0, 10²)       # Overall mean
τ ~ Half-Cauchy(1)  # Between-basket heterogeneity
```
- Borrow strength across baskets
- Shrinkage toward overall mean
- More borrowing when baskets similar

**3. Exchangeability-Non-Exchangeability (EXNEX):**
- Mixture model allowing partial exchangeability
- Weight parameter for borrowing vs independence
- Robust to heterogeneous baskets

**Multiplicity Considerations:**
- Family-wise error rate vs per-basket α
- Hochberg or Holm adjustment if needed
- Pre-specify primary vs exploratory baskets

**Sample Size per Basket:**
- Simon's optimal: n = 20-30 per basket
- Bayesian: n = 15-25 with borrowing
- Minimum 10 patients per basket for reliable estimates

**Poolability Assessment:**
- Cochran's Q test for heterogeneity
- I² statistic (I² > 50% suggests heterogeneity)
- If heterogeneous: reduce or eliminate borrowing
""",
        "efficacy_thresholds": {
            "promising": "ORR ≥ 30% in molecularly-selected population",
            "active": "ORR ≥ 50%",
            "highly_active": "ORR ≥ 70%"
        }
    },

    MasterProtocolType.UMBRELLA: {
        "name": "Umbrella Trial Design",
        "description": "Single tumor type with multiple drugs matched to molecular subtypes",
        "example": "NSCLC umbrella: EGFR+ → Drug A, ALK+ → Drug B, KRAS+ → Drug C",
        "statistical_methods": """
### Umbrella Trial Statistical Methods

**Design:** Multiple parallel arms by molecular subtype within one tumor type

**Molecular Screening:**
- Central molecular profiling (NGS panel)
- Allocation to treatment arm based on biomarker
- Non-match cohort for patients without actionable alterations

**Primary Endpoint:** ORR or PFS within each molecular subtype

**Per-Arm Analysis:**
- Independent analysis per biomarker-drug pair
- Simon's two-stage or single-arm Phase 2 design
- Randomized comparison to SOC (if applicable)

**Sample Size Considerations:**
- Prevalence of each biomarker affects accrual
- Common alterations (KRAS): larger arms
- Rare alterations (RET, NTRK): smaller arms, external controls

**Bayesian Adaptive Randomization (Optional):**
- Response-adaptive allocation within tumor type
- Increase allocation to promising arms
- Drop futile arms early

**Master Protocol Infrastructure:**
- Common eligibility (except biomarker)
- Centralized screening
- Standardized safety reporting
"""
    },

    MasterProtocolType.PLATFORM: {
        "name": "Platform Trial Design",
        "description": "Perpetual trial allowing arms to enter and exit over time",
        "example": "I-SPY 2, GBM AGILE",
        "statistical_methods": """
### Platform Trial Statistical Methods

**Design Features:**
- Common control arm (shared across treatments)
- Arms enter/exit based on interim analyses
- Adaptive randomization
- Biomarker-stratified populations

**Statistical Framework:**

**1. Response-Adaptive Randomization (RAR):**
- Initial: Equal randomization
- Adapt based on posterior probability of success
- More patients assigned to promising arms
- Thompson sampling or similar algorithm

**2. Bayesian Predictive Probability:**
- Calculate P(success | current data, future enrollment)
- Graduate arm if predictive probability > 0.85
- Drop arm if predictive probability < 0.10

**3. Shared Control:**
- Use concurrent + historical controls
- Time-machine approach for contemporaneous comparison
- Adjust for temporal trends

**Graduation Criteria:**
- P(treatment effect > δ) > threshold (e.g., 0.85)
- Predictive probability of Phase 3 success > 0.80

**Futility Stopping:**
- P(treatment effect > δ) < 0.10 at interim
- Predictive probability < 0.05

**Type I Error Control:**
- Per-comparison α (not family-wise)
- Simulation-based validation
- Publish operating characteristics

**Software:** FACTS, ADDPLAN, custom R/Stan
"""
    }
}


# =============================================================================
# CAR-T AND CELL THERAPY
# =============================================================================

CART_TEMPLATES = {
    "CRS_grading": {
        "name": "Cytokine Release Syndrome (CRS) Grading",
        "criteria": "ASTCT Consensus Grading (Lee 2019)",
        "grades": {
            "Grade 1": "Temperature ≥38°C; No hypotension; No hypoxia",
            "Grade 2": "Temperature ≥38°C with hypotension not requiring vasopressors OR hypoxia requiring low-flow O₂",
            "Grade 3": "Temperature ≥38°C with hypotension requiring vasopressor(s) OR hypoxia requiring high-flow O₂",
            "Grade 4": "Temperature ≥38°C with hypotension requiring multiple vasopressors OR hypoxia requiring mechanical ventilation"
        },
        "management": {
            "Grade 1": "Supportive care, antipyretics",
            "Grade 2": "Tocilizumab ± corticosteroids",
            "Grade 3": "Tocilizumab + corticosteroids, ICU transfer",
            "Grade 4": "Tocilizumab + high-dose corticosteroids, ICU management"
        }
    },

    "ICANS_grading": {
        "name": "Immune Effector Cell-Associated Neurotoxicity Syndrome (ICANS)",
        "criteria": "ASTCT Consensus Grading using ICE Score",
        "ice_score": {
            "Orientation": "4 points (year, month, city, hospital)",
            "Naming": "3 points (3 objects)",
            "Following commands": "1 point",
            "Writing": "1 point",
            "Attention": "1 point (count backwards)",
            "Total": "10 points (10 = normal)"
        },
        "grades": {
            "Grade 1": "ICE score 7-9",
            "Grade 2": "ICE score 3-6",
            "Grade 3": "ICE score 0-2 OR depressed consciousness OR seizure OR motor weakness",
            "Grade 4": "ICE score 0 with coma OR status epilepticus OR life-threatening cerebral edema"
        }
    },

    "statistical_methods": """
### CAR-T Cell Therapy Statistical Methods

**Primary Endpoints:**
- Overall Response Rate (ORR) per disease-specific criteria
- Complete Response (CR) rate
- Duration of Response (DOR)
- Event-Free Survival (EFS)

**Key Safety Endpoints:**
- CRS incidence (any grade, Grade ≥3)
- ICANS incidence (any grade, Grade ≥3)
- Time to CRS onset
- Duration of CRS
- Tocilizumab/corticosteroid use

**Efficacy Analysis:**
```
ORR = (CR + PR) / N evaluable
- 95% CI: Clopper-Pearson exact
- Per Lugano (lymphoma) or IMWG (myeloma)
```

**DOR Analysis:**
- From first response to progression/death
- Kaplan-Meier with 95% CI
- Censoring at last disease assessment

**CRS/ICANS Analysis:**
| Endpoint | Analysis Method |
|----------|-----------------|
| Incidence (any grade) | n/N with 95% CI |
| Incidence (Grade ≥3) | n/N with 95% CI |
| Time to onset | Median (range) |
| Duration | Median (range) |
| Resolution rate | n/N with 95% CI |

**Subgroup Analyses:**
- By tumor burden (high vs low)
- By prior lines of therapy
- By lymphodepletion regimen
- By CAR-T dose level (if applicable)

**Bridging Therapy:**
- Patients receiving bridging: separate summary
- Impact on efficacy/safety assessed

**Cellular Kinetics:**
- CAR-T expansion (peak, AUC)
- Persistence (Day 28, 90, 180, 365)
- Correlation with response/toxicity
""",

    "sample_size": """
### Sample Size for CAR-T Trials

**Single-Arm Phase 2 (ORR Primary):**
- H₀: ORR ≤ 20% (historical control)
- H₁: ORR ≥ 50% (target)
- α = 0.05 (one-sided), Power = 90%
- n = 25-35 patients (Simon's two-stage)

**Pivotal Single-Arm:**
- Typically 50-100 patients
- Pre-specified ORR threshold (e.g., lower 95% CI > 30%)
- Support with external control if needed
"""
}


# =============================================================================
# INTEGRATION WITH CONSTRAINED PIPELINE
# =============================================================================

class SpecializedOncologyGenerator:
    """
    Generate specialized oncology SAP sections

    Usage:
        generator = SpecializedOncologyGenerator()

        # Hematologic trial
        if generator.is_hematologic(indication):
            methods = generator.get_hematologic_methods(indication)

        # Phase 1 trial
        if phase == "Phase 1":
            methods = generator.get_phase1_methods(design_type)

        # CAR-T trial
        if generator.is_cart_trial(treatment):
            safety = generator.get_cart_safety_section()
    """

    def __init__(self):
        self.hematologic_keywords = [
            'leukemia', 'lymphoma', 'myeloma', 'aml', 'all', 'cll', 'cml',
            'dlbcl', 'follicular', 'mantle cell', 'hodgkin', 'nhl', 'mds',
            'myelodysplastic', 'multiple myeloma', 'plasma cell'
        ]
        self.cart_keywords = [
            'car-t', 'cart', 'car t', 'chimeric antigen receptor',
            'cell therapy', 'adoptive cell', 'til', 'tcr-t'
        ]

    def is_hematologic(self, indication: str) -> bool:
        """Check if indication is hematologic malignancy"""
        indication_lower = indication.lower()
        return any(kw in indication_lower for kw in self.hematologic_keywords)

    def is_cart_trial(self, treatment: str, indication: str = "") -> bool:
        """Check if trial involves CAR-T or cell therapy"""
        text = f"{treatment} {indication}".lower()
        return any(kw in text for kw in self.cart_keywords)

    def is_phase1(self, phase: str) -> bool:
        """Check if Phase 1 trial"""
        return 'phase 1' in phase.lower() or 'phase i' in phase.lower()

    def get_hematologic_criteria(self, indication: str) -> Optional[Dict]:
        """Get appropriate response criteria for hematologic indication"""
        indication_lower = indication.lower()

        if any(kw in indication_lower for kw in ['lymphoma', 'hodgkin', 'dlbcl', 'follicular', 'nhl']):
            return HEMATOLOGIC_TEMPLATES[HematologicCriteria.LUGANO]
        elif any(kw in indication_lower for kw in ['myeloma', 'plasma cell']):
            return HEMATOLOGIC_TEMPLATES[HematologicCriteria.IMWG]
        elif any(kw in indication_lower for kw in ['aml', 'acute myeloid']):
            return HEMATOLOGIC_TEMPLATES[HematologicCriteria.ELN]

        return None

    def get_phase1_methods(self, design: str = "3+3") -> Dict:
        """Get Phase 1 dose-escalation methods"""
        design_map = {
            "3+3": Phase1Design.RULE_3_3,
            "crm": Phase1Design.CRM,
            "boin": Phase1Design.BOIN,
            "mtpi": Phase1Design.MTPI
        }
        design_key = design_map.get(design.lower(), Phase1Design.RULE_3_3)
        return PHASE1_TEMPLATES[design_key]

    def get_cart_safety_section(self) -> str:
        """Get CAR-T specific safety section"""
        return f"""
### CAR-T Specific Safety Monitoring

#### Cytokine Release Syndrome (CRS) - ASTCT Grading
{self._format_grades(CART_TEMPLATES['CRS_grading']['grades'])}

#### ICANS (Neurotoxicity) - ASTCT Grading
{self._format_grades(CART_TEMPLATES['ICANS_grading']['grades'])}

{CART_TEMPLATES['statistical_methods']}
"""

    def get_basket_methods(self) -> str:
        """Get basket trial statistical methods"""
        return MASTER_PROTOCOL_TEMPLATES[MasterProtocolType.BASKET]['statistical_methods']

    def get_umbrella_methods(self) -> str:
        """Get umbrella trial statistical methods"""
        return MASTER_PROTOCOL_TEMPLATES[MasterProtocolType.UMBRELLA]['statistical_methods']

    def get_platform_methods(self) -> str:
        """Get platform trial statistical methods"""
        return MASTER_PROTOCOL_TEMPLATES[MasterProtocolType.PLATFORM]['statistical_methods']

    def _format_grades(self, grades: Dict[str, str]) -> str:
        """Format grading table"""
        lines = ["| Grade | Criteria |", "|-------|----------|"]
        for grade, criteria in grades.items():
            lines.append(f"| {grade} | {criteria} |")
        return "\n".join(lines)

    def enhance_sap_section(self, section_name: str, content: str,
                           indication: str, phase: str, treatment: str) -> str:
        """
        Enhance SAP section with specialized oncology content

        Args:
            section_name: Name of section (endpoints, statistical_methods, safety)
            content: Existing section content
            indication: Disease indication
            phase: Trial phase
            treatment: Treatment name

        Returns:
            Enhanced section content
        """
        enhancements = []

        # Hematologic enhancements
        if self.is_hematologic(indication):
            criteria = self.get_hematologic_criteria(indication)
            if criteria:
                if section_name == "endpoints":
                    enhancements.append(f"\n\n### Hematologic Response Criteria: {criteria['name']}\n")
                    enhancements.append(self._format_response_categories(criteria['response_categories']))
                elif section_name == "statistical_methods":
                    enhancements.append(criteria.get('statistical_methods', ''))

        # Phase 1 enhancements
        if self.is_phase1(phase) and section_name == "statistical_methods":
            phase1_methods = self.get_phase1_methods()
            enhancements.append(phase1_methods.get('statistical_methods', ''))

        # CAR-T enhancements
        if self.is_cart_trial(treatment, indication):
            if section_name == "safety":
                enhancements.append(self.get_cart_safety_section())
            elif section_name == "statistical_methods":
                enhancements.append(CART_TEMPLATES['statistical_methods'])

        if enhancements:
            return content + "\n" + "\n".join(enhancements)
        return content

    def _format_response_categories(self, categories: Dict[str, str]) -> str:
        """Format response categories as table"""
        lines = ["| Response | Definition |", "|----------|------------|"]
        for resp, defn in categories.items():
            lines.append(f"| {resp} | {defn} |")
        return "\n".join(lines)


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    generator = SpecializedOncologyGenerator()

    print("="*70)
    print("SPECIALIZED ONCOLOGY TEMPLATES")
    print("="*70)

    print("\n### Hematologic Criteria Available:")
    for criteria in HematologicCriteria:
        template = HEMATOLOGIC_TEMPLATES.get(criteria)
        if template:
            print(f"  - {template['name']}: {', '.join(template['indication'][:3])}")

    print("\n### Phase 1 Designs Available:")
    for design in Phase1Design:
        template = PHASE1_TEMPLATES.get(design)
        if template:
            print(f"  - {template['name']}")

    print("\n### Master Protocol Types:")
    for mtype in MasterProtocolType:
        template = MASTER_PROTOCOL_TEMPLATES.get(mtype)
        if template:
            print(f"  - {template['name']}: {template['description'][:50]}...")

    print("\n### CAR-T Templates:")
    print(f"  - CRS Grading: {CART_TEMPLATES['CRS_grading']['criteria']}")
    print(f"  - ICANS Grading: {CART_TEMPLATES['ICANS_grading']['criteria']}")

    print("\n" + "="*70)
    print("TEST: Detecting trial types")
    print("="*70)

    test_cases = [
        ("DLBCL", "Phase 2", "Rituximab"),
        ("Multiple Myeloma", "Phase 3", "Daratumumab"),
        ("AML", "Phase 1", "Venetoclax"),
        ("NSCLC", "Phase 1", "Drug X"),
        ("B-ALL", "Phase 2", "Tisagenlecleucel CAR-T"),
    ]

    for indication, phase, treatment in test_cases:
        print(f"\n  {indication} / {phase} / {treatment}:")
        print(f"    Hematologic: {generator.is_hematologic(indication)}")
        print(f"    Phase 1: {generator.is_phase1(phase)}")
        print(f"    CAR-T: {generator.is_cart_trial(treatment, indication)}")
        if generator.is_hematologic(indication):
            criteria = generator.get_hematologic_criteria(indication)
            if criteria:
                print(f"    Criteria: {criteria['name']}")
