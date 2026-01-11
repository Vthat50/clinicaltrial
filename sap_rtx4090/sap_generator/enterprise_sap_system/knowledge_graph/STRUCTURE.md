# Knowledge Graph System Structure (v78)
## Complete File Inventory with All Named Elements

---

## 1. COMPREHENSIVE SAP ELEMENTS (35 Categories)

**File:** `comprehensive_sap_elements.py` (1,851 lines)

### Study Framework (4)
```
STUDY_DEFINITIONS          → Study Day 1, baseline, TEAE, follow-up definitions
ESTIMAND_FRAMEWORK         → ICH E9(R1) treatment policy, composite, hypothetical
BLINDING_CONSIDERATIONS    → Unblinding procedures, IWRS, emergency codes
RANDOMIZATION_SPECS        → Block sizes, stratification, IVRS/IWRS
```

### Baseline & Demographics (7)
```
DEMOGRAPHICS_BASELINE      → Age, sex, race, ethnicity, weight, height, BSA, BMI
PRIOR_THERAPY_ANALYSIS     → Prior lines (1, 2, 3, ≥4), specific agents, refractory status
CONCOMITANT_MEDICATIONS    → WHO Drug dictionary, ATC classification
MEDICAL_HISTORY            → MedDRA SOC/PT coding, relevant vs non-relevant
ORGAN_FUNCTION_SPECS       → Hepatic (Child-Pugh A/B/C), renal (CrCl), cardiac (LVEF)
BIOMARKER_SUBGROUPS        → PD-L1, TMB, MSI, HER2, BRCA status
STRATIFICATION_BALANCE     → Balance assessment, re-stratification
```

### Efficacy Analysis (5)
```
TUMOR_RESPONSE_ASSESSMENT  → RECIST 1.1, Lugano, IWCLL, IMWG methodology
CONCORDANCE_ANALYSIS       → IRC vs Investigator, kappa statistic, discordance
MRD_ASSESSMENT             → Flow cytometry, NGS, sensitivity thresholds
SENSITIVITY_ANALYSES       → Per-protocol, tipping point, MNAR patterns
SUBGROUP_ANALYSIS_SPECS    → Pre-specified subgroups, forest plot specs
```

### Safety Analysis (8)
```
EXPOSURE_ANALYSIS          → Duration, dose intensity, BSA-adjusted, cumulative
AE_PERIOD_ANALYSIS         → TEAE windows, pre-treatment, 30-day follow-up, 90-day
DEATH_ANALYSIS             → Death summary, cause of death, last known alive (16 modules)
TREATMENT_COMPLIANCE       → Dose modifications, interruptions, reductions
IMMUNOGENICITY_ANALYSIS    → ADA incidence, neutralizing Ab, impact on PK/efficacy
HEALTHCARE_UTILIZATION     → Hospitalization, ICU days, length of stay
PROTOCOL_DEVIATIONS        → Major/minor classification, impact assessment
SUBSEQUENT_THERAPY         → Post-study anti-cancer therapy by class
```

### CAR-T Specific (2)
```
CART_MANUFACTURING_METRICS → Leukapheresis date, vein-to-vein time, bridging therapy
ENROLLMENT_SUMMARIES       → By region, by site, screening vs enrolled
```

### Statistical Methods (5)
```
MULTIPLICITY_ADJUSTMENTS   → Hochberg, Holm, gatekeeping, alpha spending
INTERIM_ANALYSIS           → O'Brien-Fleming, Lan-DeMets, futility, DMC
QOL_PRO_ANALYSIS           → EORTC QLQ-C30, FACT-G, EQ-5D, PGIC, TTD
PK_PD_ANALYSIS             → Cmax, Tmax, AUC, exposure-response
DATA_HANDLING_RULES        → Missing data conventions, LOCF, MMRM
```

### Programming (4)
```
DATA_CUTOFF_SPECS          → Event-driven cutoff, calendar cutoff, maturity
ANALYSIS_TIMING            → Visit windows, assessment timing, nominal visits
```

---

## 2. METHODOLOGY KNOWLEDGE BASE (15 Categories)

**File:** `methodology_knowledge_base.py` (1,813 lines)

### Statistical Methods
```
STATISTICAL_METHODS:
├── kaplan_meier           → K-M survival estimates, median, 95% CI
├── cox_regression         → Hazard ratio, stratified Cox, covariates
├── log_rank               → Stratified log-rank, unstratified
├── clopper_pearson        → Exact binomial CI for response rates
├── wilson_score           → Wilson score CI
├── cmh_test               → Cochran-Mantel-Haenszel stratified analysis
├── mmrm                   → Mixed model repeated measures
├── ancova                 → Analysis of covariance
├── fisher_exact           → Fisher's exact test for 2x2 tables
└── chi_square             → Chi-square test for categorical

CONFIDENCE_INTERVAL_METHODS:
├── clopper_pearson        → Exact method (conservative)
├── wilson                 → Wilson score method
├── jeffreys               → Bayesian method
├── agresti_coull          → Adjusted Wald
├── wald                   → Standard Wald
└── exact_binomial         → Exact binomial

MISSING_DATA_HANDLING:
├── locf                   → Last observation carried forward
├── mmrm                   → Mixed model (preferred)
├── multiple_imputation    → MI under MAR
├── tipping_point          → Sensitivity for MNAR
└── pattern_mixture        → Pattern mixture models

MULTIPLICITY_ADJUSTMENT:
├── hochberg               → Hochberg step-up
├── holm                   → Holm step-down
├── bonferroni             → Bonferroni correction
├── fixed_sequence         → Fixed sequence testing
├── gatekeeping            → Gatekeeping procedures
├── fallback               → Fallback procedures
└── graphical              → Graphical approaches
```

### Censoring Rules (4 endpoint types)
```
CENSORING_RULES:
├── PFS (12 circumstances):
│   ├── Disease progression     → Event
│   ├── Death without progression → Event
│   ├── Adequate assessment, no PD → Censor at last assessment
│   ├── No baseline assessment  → Censor at randomization
│   ├── No post-baseline assessment → Censor at randomization
│   ├── New anti-cancer therapy → Censor at last assessment before
│   ├── Two or more missed assessments → Censor at last assessment
│   ├── Progression after 2+ missed → Event at progression date
│   ├── Lost to follow-up      → Censor at last assessment
│   ├── Withdrawal of consent  → Censor at last assessment
│   ├── Death > 12 weeks after assessment → Censor at last assessment
│   └── Study termination      → Censor at last assessment
│
├── OS (8 circumstances):
│   ├── Death                  → Event
│   ├── Alive at analysis      → Censor at last known alive
│   ├── Lost to follow-up      → Censor at last contact
│   ├── Withdrawal of consent  → Censor at last contact
│   └── Study termination      → Censor at last contact
│
├── DOR (10 circumstances):
│   ├── Disease progression    → Event
│   ├── Death without progression → Event (or censor per protocol)
│   ├── Ongoing response       → Censor at last assessment
│   └── [Similar to PFS]
│
└── EFS (8 circumstances):
    ├── Progression            → Event
    ├── Death                  → Event
    ├── Treatment discontinuation → Event (or censor)
    └── New therapy            → Event
```

### Time-to-Event Analysis
```
TIME_TO_EVENT_ANALYSIS:
├── kaplan_meier_estimates    → Survival function, median, quartiles
├── cox_proportional_hazards  → HR, stratified, time-varying
├── restricted_mean           → RMST differences
├── landmark_analysis         → Conditional survival at landmarks
├── cure_rate_models          → Mixture cure models
└── competing_risks           → Cumulative incidence, Fine-Gray
```

### Interim Analysis
```
INTERIM_ANALYSIS_SPECIFICATIONS:
├── obrien_fleming           → O'Brien-Fleming boundaries
├── lan_demets               → Lan-DeMets alpha spending
├── pocock                   → Pocock boundaries
├── haybittle_peto           → Haybittle-Peto rule
├── beta_spending            → Futility boundaries
└── conditional_power        → Conditional power for futility
```

---

## 3. TFL INVENTORY (80+ Tables/Figures/Listings)

**File:** `complete_tfl_inventory.py` (1,686 lines)

### Disposition Tables (12)
```
Subject Disposition
Demographics and Baseline Characteristics (ITT Population)
Disease Characteristics at Baseline (ITT Population)
Biomarker Status at Baseline (ITT Population)
Prior Anti-Cancer Therapy (ITT Population)
Medical History by System Organ Class and Preferred Term (Safety Population)
Prior Medications (Safety Population)
Concomitant Medications (Safety Population)
Protocol Deviations (ITT Population)
Analysis Populations
Stratification Factors as Randomized vs CRF Derived (ITT Population)
Screen Failures
```

### Efficacy Tables (25)
```
Summary of Progression-Free Survival (ITT Population, IRC Assessment)
Summary of Progression-Free Survival (ITT Population, Investigator Assessment)
Summary of PFS by Censoring Reason (ITT Population, IRC Assessment)
Summary of Overall Survival (ITT Population)
Summary of OS Follow-up (ITT Population)
Best Overall Response (ITT Population, IRC Assessment)
Best Overall Response (ITT Population, Investigator Assessment)
Confirmed vs Unconfirmed Response (ITT Population, IRC)
Duration of Response (Responder Population, IRC Assessment)
Time to Response (Responder Population, IRC Assessment)
Target Lesion Assessment Over Time (ITT Population, IRC)
Non-Target Lesion Assessment Over Time (ITT Population, IRC)
New Lesion Assessment Over Time (ITT Population, IRC)
Sensitivity Analyses for PFS (ITT Population)
Sensitivity Analyses for OS (ITT Population)
Subgroup Analysis of PFS (ITT Population, IRC)
Subgroup Analysis of OS (ITT Population)
Subgroup Analysis of ORR (ITT Population, IRC)
Subsequent Anti-Cancer Therapy (ITT Population)
Time to Subsequent Therapy (ITT Population)
PFS2 - Progression-Free Survival on Next-Line Therapy (ITT Population)
Time to Deterioration in PRO Scores (ITT Population)
PRO Scores Over Time (ITT Population)
RECIST 1.1 Response by Baseline Characteristics (ITT Population, IRC)
```

### Safety Tables (20)
```
Overview of Treatment-Emergent Adverse Events (Safety Population)
TEAEs by System Organ Class and Preferred Term (Safety Population)
Grade ≥3 TEAEs by System Organ Class and Preferred Term (Safety Population)
Treatment-Related TEAEs (Safety Population)
Serious Adverse Events (Safety Population)
Adverse Events Leading to Discontinuation (Safety Population)
Adverse Events Leading to Dose Modification (Safety Population)
Deaths (Safety Population)
Adverse Events of Special Interest (Safety Population)
Study Drug Exposure (Safety Population)
Dose Modifications by Reason (Safety Population)
Baseline Laboratory Values (Safety Population)
Laboratory Abnormalities by CTCAE Grade (Safety Population)
Laboratory Shift Tables (Safety Population)
Baseline Vital Signs and Physical Examination (Safety Population)
Vital Signs Over Time (Safety Population)
ECG Results (Safety Population)
Potentially Clinically Significant Laboratory Values
Concomitant Medications During Treatment (Safety Population)
Subsequent Anti-Cancer Therapy (Safety Population)
```

### Figures (12)
```
Kaplan-Meier Plot of Progression-Free Survival (IRC)
Kaplan-Meier Plot of Progression-Free Survival (Investigator)
Kaplan-Meier Plot of Overall Survival
Kaplan-Meier Plot of Duration of Response
Forest Plot of PFS by Subgroup
Forest Plot of OS by Subgroup
Forest Plot of ORR by Subgroup
Waterfall Plot of Best Change in Target Lesions
Spider Plot of Change in Target Lesions Over Time
Swimmer Plot of Response Duration
Mean Change from Baseline in PRO Scores Over Time
Event-Free Probability Plot
```

### Listings (15)
```
Study Completion and Discontinuation
Screen Failures
Protocol Deviations
Tumor Assessment Data - All Visits
Best Overall Response
PFS Event/Censoring Data
OS Event/Censoring Data
Duration of Response Data
Adverse Events - All
Serious Adverse Events
Deaths
Adverse Events Leading to Discontinuation
Adverse Events Leading to Dose Modification
Study Drug Exposure
Subsequent Anti-Cancer Therapy
```

### Single-Arm Tables (3)
```
Subject Disposition (Single-Arm)
Demographics (Single-Arm)
Best Overall Response (Single-Arm)
```

### Lymphoma-Specific Tables (4)
```
Baseline Disease Characteristics - Lymphoma (Ann Arbor Stage, B symptoms)
Prognostic Index Scores - Lymphoma (IPI, FLIPI, MIPI)
Best Overall Response per Lugano Classification
Response by Deauville Score (PET Assessment)
```

### CAR-T Specific Tables (10)
```
Summary of Cytokine Release Syndrome (CRS) by Grade
Summary of ICANS (Neurotoxicity) by Grade
CRS Management (Tocilizumab, Corticosteroids)
ICANS Management
CAR-T Cell Kinetics Summary (Cmax, Tmax, AUC, persistence)
Prolonged Cytopenias (Day 30, Day 90)
Infections Summary by Type
Hypogammaglobulinemia and B-Cell Aplasia
Response to Retreatment
Duration of Response to Retreatment (DORR)
```

---

## 4. ONCOLOGY REFERENCE DATA (16 Modules)

**File:** `oncology_reference_data.py` (1,265 lines)

### Response Criteria (4)
```
IMWG_CRITERIA (Multiple Myeloma):
├── sCR  → Stringent Complete Response
├── CR   → Complete Response
├── VGPR → Very Good Partial Response
├── PR   → Partial Response
├── MR   → Minimal Response
├── SD   → Stable Disease
└── PD   → Progressive Disease

CML_CRITERIA (ELN 2020):
├── CHR  → Complete Hematologic Response
├── PCyR → Partial Cytogenetic Response
├── CCyR → Complete Cytogenetic Response
├── MMR  → Major Molecular Response
├── MR4  → Deep Molecular Response (4-log)
├── MR4.5 → Deep Molecular Response (4.5-log)
└── CMR  → Complete Molecular Response

IWCLL_CRITERIA (CLL 2018):
├── CR   → Complete Response
├── CRi  → Complete Response with incomplete marrow recovery
├── nPR  → Nodular Partial Response
├── PR   → Partial Response
├── PR-L → Partial Response with Lymphocytosis
├── SD   → Stable Disease
└── PD   → Progressive Disease
```

### Study Design Templates (4)
```
ADJUVANT_TRIAL_TEMPLATE:
├── Primary endpoint    → DFS, RFS, EFS
├── Key secondary       → OS, distant recurrence
├── Population          → Post-surgical resection
└── Duration            → 3-5 years follow-up

NEOADJUVANT_TRIAL_TEMPLATE:
├── Primary endpoint    → pCR (pathologic complete response)
├── Key secondary       → EFS, OS, breast conservation rate
└── Assessment          → Surgery timing, residual disease

BASKET_TRIAL_TEMPLATE:
├── Design              → Biomarker-selected, multiple tumor types
├── Primary endpoint    → ORR by tumor type
└── Analysis            → By histology, pooled

UMBRELLA_TRIAL_TEMPLATE:
├── Design              → Single tumor type, multiple biomarker arms
├── Primary endpoint    → ORR by biomarker arm
└── Master protocol     → Shared control arm option
```

### Therapy-Specific Modules (3)
```
CAR_T_MODULE:
├── CRS Grading:
│   ├── ASTCT 2019     → Grade 1-4 (fever, hypotension, hypoxia)
│   ├── Lee 2014       → Grade 1-4 (original scale)
│   └── Penn Scale     → Grade 1-4 (institutional)
├── ICANS Grading:
│   ├── ICE Score      → 10-point assessment
│   ├── CARTOX-10      → Encephalopathy grading
│   └── Grade 1-4      → Based on ICE, consciousness, seizure, motor
├── Cellular Kinetics:
│   ├── Cmax           → Peak CAR-T expansion
│   ├── Tmax           → Time to peak
│   ├── AUC0-28        → Exposure over 28 days
│   └── Persistence    → CAR-T detection at Day 90, 180, 365
└── Manufacturing:
    ├── Leukapheresis  → Collection date, cell count
    ├── Vein-to-vein   → Manufacturing time
    └── Bridging       → Therapy during manufacturing

BISPECIFIC_ANTIBODY_MODULE:
├── Step-up Dosing     → Dose escalation schedule
├── CRS Management     → Different from CAR-T (typically milder)
├── Target Engagement  → CD20, CD3, BCMA binding
└── Hospitalization    → Monitoring requirements

ADC_MODULE:
├── Payload Toxicities:
│   ├── MMAE          → Peripheral neuropathy, neutropenia
│   ├── DM1           → Thrombocytopenia, hepatotoxicity
│   └── Topoisomerase → Neutropenia, diarrhea
├── Ocular Toxicity   → Keratopathy, dry eye (for some ADCs)
├── Infusion Reactions → Pre-medication requirements
└── Dose Modifications → By toxicity type
```

### Baseline Variables (4)
```
PERFORMANCE_STATUS_SCALES:
├── ECOG (0-5):
│   ├── 0 → Fully active
│   ├── 1 → Restricted in strenuous activity
│   ├── 2 → Ambulatory, capable of self-care
│   ├── 3 → Limited self-care, >50% in bed/chair
│   ├── 4 → Completely disabled
│   └── 5 → Dead
└── Karnofsky (0-100):
    ├── 100 → Normal, no complaints
    ├── 90  → Able to carry on normal activity
    ├── 80  → Normal activity with effort
    └── ... → [decreasing function]

ORGAN_FUNCTION_SCORES:
├── Child-Pugh (Hepatic):
│   ├── Class A (5-6 points)  → Well-compensated
│   ├── Class B (7-9 points)  → Significant compromise
│   └── Class C (10-15 points) → Decompensated
├── CrCl (Renal):
│   ├── ≥90 mL/min   → Normal
│   ├── 60-89 mL/min → Mild impairment
│   ├── 30-59 mL/min → Moderate impairment
│   ├── 15-29 mL/min → Severe impairment
│   └── <15 mL/min   → Kidney failure
└── LVEF (Cardiac):
    ├── ≥55%  → Normal
    ├── 45-54% → Mildly reduced
    ├── 30-44% → Moderately reduced
    └── <30%   → Severely reduced

PROGNOSTIC_SCORES:
├── IPI (DLBCL):
│   ├── Factors: Age>60, Stage III/IV, ECOG≥2, LDH elevated, >1 extranodal
│   ├── Low (0-1), Low-Int (2), High-Int (3), High (4-5)
├── FLIPI (Follicular):
│   ├── Factors: Age>60, Stage III/IV, Hgb<12, LDH elevated, >4 nodal
│   ├── Low (0-1), Intermediate (2), High (≥3)
├── ISS (Myeloma):
│   ├── Stage I: β2M<3.5, Albumin≥3.5
│   ├── Stage II: Neither I nor III
│   └── Stage III: β2M≥5.5
├── R-ISS (Myeloma):
│   ├── Adds: LDH, high-risk cytogenetics
└── IMDC (RCC):
    ├── Factors: KPS<80, <1yr diagnosis-treatment, Hgb<LLN, Ca>ULN, Neutrophils>ULN, Platelets>ULN
    ├── Favorable (0), Intermediate (1-2), Poor (≥3)
```

---

## 5. DISEASE-SPECIFIC CRITERIA (4 Criteria Sets)

**File:** `disease_specific_criteria.py` (679 lines)

```
RANO_CRITERIA (Brain Tumors):
├── CR  → No enhancing tumor, stable/improved non-enhancing, no new lesions, stable/improved clinically, off steroids
├── PR  → ≥50% decrease in enhancing tumor, no new lesions, stable/improved non-enhancing
├── SD  → <50% decrease to <25% increase in enhancing tumor
└── PD  → ≥25% increase in enhancing tumor, or new lesions, or clinical deterioration

LUGANO_CRITERIA (Lymphoma):
├── CMR → Complete Metabolic Response (Deauville 1-3, no new lesions)
├── PMR → Partial Metabolic Response (Deauville 4-5 with reduced uptake)
├── NMR → No Metabolic Response (Deauville 4-5, no change)
├── PMD → Progressive Metabolic Disease (Deauville 4-5 with increased uptake or new lesions)
│
├── CT-Based:
│   ├── CR  → Target nodes ≤1.5cm, no extranodal disease
│   ├── PR  → ≥50% decrease in SPD of up to 6 nodes
│   ├── SD  → <50% decrease to <50% increase
│   └── PD  → ≥50% increase or new lesions

IMWG_CRITERIA (Multiple Myeloma):
├── sCR → CR + normal FLC ratio + no clonal cells by IHC/flow
├── CR  → Negative IF on serum/urine, <5% plasma cells, no soft tissue plasmacytomas
├── VGPR → ≥90% reduction in serum M-protein + urine <100mg/24h
├── PR  → ≥50% reduction in serum M-protein + ≥90% reduction in 24h urine
├── MR  → 25-49% reduction in serum M-protein (for relapsed only)
├── SD  → Not meeting CR, VGPR, PR, MR, or PD criteria
└── PD  → ≥25% increase from nadir in serum/urine M-protein, or new lesions

RANO_BM_CRITERIA (Brain Metastases):
├── CR  → Disappearance of all CNS target lesions
├── PR  → ≥30% decrease in sum of longest diameters
├── SD  → Neither PR nor PD criteria met
└── PD  → ≥20% increase in sum or new lesions
```

---

## 6. ADaM DATASET SPECIFICATIONS (11 Datasets)

**File:** `adam_specifications.py` (668 lines)

```
ADSL (Subject-Level):
├── USUBJID, STUDYID, SITEID
├── AGE, AGEGR1, SEX, RACE, ETHNIC
├── ARM, ACTARM, TRT01P, TRT01A
├── RANDDT, TRTSDT, TRTEDT
├── SAFFL, ITTFL, PPROTFL, FASFL
├── DTHFL, DTHDT, DTH30FL, DTH90FL
└── EOSSTT, EOSDT, DCSREAS

ADAE (Adverse Events):
├── USUBJID, AESEQ, AETERM, AEDECOD
├── AEBODSYS, AESOC, AEHLT, AELLT
├── AESTDTC, AEENDTC, ASTDT, AENDT
├── AETOXGR, ATOXGRN, AEREL, AESER
├── AEACN, AEOUT, AESCONG, AESDISAB
├── AEDTC, TRTEMFL, PREFL, FUPFL
└── CQ01NAM (CRS), CQ02NAM (ICANS) [for CAR-T]

ADTTE (Time-to-Event):
├── USUBJID, PARAMCD, PARAM
├── STARTDT, ADT, AVAL (days)
├── CNSR (0=event, 1=censor)
├── EVNTDESC, CNSDTDSC
├── SRCDOM, SRCVAR, SRCSEQ
└── Params: PFS, PFSIRC, PFSINV, OS, DOR, TTR, EFS

ADRS (Response):
├── USUBJID, PARAMCD, PARAM
├── AVALC (CR, PR, SD, PD, NE)
├── AVAL (numeric), ADT
├── VISITNUM, VISIT
├── RSSTRESC, RSORRES
└── Params: BOR, CBOR, OVRLRESP

ADLB (Laboratory):
├── USUBJID, PARAMCD, PARAM, PARCAT1
├── AVAL, AVALC, BASE, CHG, PCHG
├── ANRLO, ANRHI, ANRIND
├── ATOXGR, BTOXGR, ATOXGRN
├── SHIFT1 (baseline to worst)
└── ABLFL, AVISIT, ADT

ADEX (Exposure):
├── USUBJID, PARAMCD, PARAM
├── AVAL, AVALC, ADT
├── EXDOSE, EXDOSU, EXDOSFRQ
├── EXSTDTC, EXENDTC
├── Params: TRTDUR, CUMDOSE, AVGDOSE, RELINT

ADVS (Vital Signs):
├── USUBJID, PARAMCD, PARAM
├── AVAL, BASE, CHG, PCHG
├── ATPT, ATPTN, AVISIT
└── ABLFL, ANRLO, ANRHI

ADEG (ECG):
├── USUBJID, PARAMCD, PARAM
├── AVAL, BASE, CHG
├── ATPT, AVISIT
└── Params: QT, QTcF, QTcB, HR, PR, QRS

ADPR (PRO):
├── USUBJID, PARAMCD, PARAM
├── AVAL, BASE, CHG
├── QSTESTCD, QSTEST, QSCAT
└── DTYPE (derived types: TTD, responder)

ADCM (Concomitant Medications):
├── USUBJID, CMSEQ
├── CMTRT, CMDECOD, CMCLAS, CMCLASCD
├── CMSTDTC, CMENDTC, ASTDT, AENDT
└── CMINDC, CMDOSE, CMDOSU

ADMH (Medical History):
├── USUBJID, MHSEQ
├── MHTERM, MHDECOD, MHBODSYS
├── MHSTDTC, MHENDTC
└── MHENRF (ongoing flag)
```

---

## 7. REGULATORY STANDARDS (7 Classes)

**File:** `regulatory_standards.py` (691 lines)

```
CodingStandards:
├── MEDDRA_VERSION = "26.0"
├── WHODRUG_VERSION = "March 2024"
├── CTCAE_VERSION = "5.0"
├── RECIST_VERSION = "1.1"
├── LUGANO_VERSION = "2014"
└── CDISC_ADAM_VERSION = "1.3"

EstimandFramework (ICH E9 R1):
├── Treatment Policy Strategy:
│   ├── All events counted regardless of intercurrent events
│   └── ITT analysis, includes deaths, discontinuations
├── Composite Strategy:
│   ├── Intercurrent event becomes part of endpoint
│   └── e.g., death counted as progression for PFS
├── Hypothetical Strategy:
│   ├── Estimate effect if intercurrent event hadn't occurred
│   └── e.g., PFS if patient hadn't switched therapy
├── Principal Stratum Strategy:
│   ├── Effect in subpopulation defined by intercurrent event
│   └── e.g., effect in those who would complete therapy
└── While-on-Treatment Strategy:
    ├── Response while on treatment only
    └── Censoring at treatment discontinuation

OncologyStandards:
├── RECIST 1.1 Requirements
├── Lugano 2014 Requirements
├── iwCLL 2018 Requirements
├── IMWG Requirements
├── PCWG3 (Prostate) Requirements
└── RANO Requirements

Phase1Standards:
├── 3+3 Design
├── CRM Design
├── BOIN Design
└── mTPI Design

LaboratoryStandards:
├── CTCAE Grading
├── Shift Tables (Normal/Abnormal, Grade shifts)
└── PCS Criteria (Potentially Clinically Significant)
```

---

## 8. SAP STRUCTURE CONFIG (24 Main Sections)

**File:** `sap_structure_config.py` (1,031 lines)

### Main Sections
```
1.  TITLE PAGE & ADMINISTRATIVE INFORMATION
2.  INTRODUCTION
    └── 2.1-2.3: Background, Objectives, Endpoints
3.  STUDY DESIGN
    └── 3.1-3.5: Design, Arms, Randomization, Blinding, Stratification
4.  SAMPLE SIZE & POWER
    └── 4.1-4.3: Primary Sample Size, Assumptions, Power Details
5.  ANALYSIS POPULATIONS
    └── 5.1-5.7: ITT, Safety, PP, Response-Evaluable, PK, mITT, Re-treatment
5A. BASELINE CHARACTERISTICS AND DISEASE HISTORY
    └── 5A.1-5A.6: Demographics, Disease, Prognostic, Prior Therapy, Medical History, Concomitant Meds
6.  ENDPOINTS & ESTIMANDS
    └── 6.1-6.7: Primary, Secondary, Exploratory, Estimands, Response, Concordance, Retreatment
7.  STATISTICAL METHODS
    └── 7.1-7.7: General, TTE, Binary, Continuous, Multiplicity, Single-Arm, MRD
8.  CENSORING RULES
    └── 8.1-8.4: PFS, OS, DOR, EFS Censoring
9.  MISSING DATA HANDLING
    └── 9.1-9.3: Conventions, Date Imputation, Missing Endpoint
10. SENSITIVITY ANALYSES
    └── 10.1-10.4: Primary Endpoint, Per-Protocol, Tipping Point, COVID-19
11. SUBGROUP ANALYSES
    └── 11.1-11.3: Pre-specified, Methods, Forest Plots
12. SAFETY ANALYSIS
    └── 12.1-12.17: AE, Deaths, Labs, Vitals, ECG, Exposure, Subsequent, CRS, ICANS, Kinetics, Manufacturing, Cytopenias, B-Cell Aplasia, HRU, Immunogenicity, ADC, Bispecific
13. INTERIM ANALYSIS
    └── 13.1-13.5: Timing, Alpha Spending, Boundaries, Futility, DMC
14. BIOMARKER ANALYSIS
    └── 14.1-14.3: Endpoints, Correlations, Subgroups
15. PATIENT-REPORTED OUTCOMES
    └── 15.1-15.4: Instruments, Scoring, Missing PRO, Methods
16. DEFINITIONS
    └── 16.1-16.4: Time Points, Safety Events, Follow-up, Enrollment
17. PROGRAMMING SPECIFICATIONS
    └── 17.1-17.4: Windows, Baseline, Derived Variables, Cutoff
18. TABLE, FIGURE, AND LISTING SHELLS
    └── 18.1-18.6: Disposition, Demographics, Efficacy, Safety, Figures, Listings
19. DATA SCREENING AND ACCEPTANCE
    └── 19.1-19.5: Handling, Transfer, Bias, Outliers, Distributions
20. FOLLOW-UP ANALYSIS
    └── 20.1-20.2: Schedule, Objectives
21. CHANGES FROM PROTOCOL-SPECIFIED ANALYSES
    └── 21.1: Summary of Changes
22. REFERENCES
    └── 22.1-22.3: Response Criteria, Statistical, Safety Grading
A.  APPENDICES
    └── A.1-A.5: Date Imputation, TTE Derivation, MedDRA Search, Response Criteria, ADaM Specs
```

### Condition Detection (30+ Conditions)
```
Study Design:
├── is_randomized, is_single_arm, is_blinded, is_adaptive
├── has_multiple_arms, has_stratification

Endpoints:
├── has_tte_endpoints, has_pfs_endpoint, has_os_endpoint
├── has_dor_endpoint, has_efs_endpoint, has_response_endpoint
├── has_continuous_endpoints, has_exploratory_endpoints
├── has_multiple_primary_endpoints, has_biomarker_endpoints
├── has_pro_endpoints, has_pk_endpoints, has_mrd_endpoint
├── has_hru_endpoints

Therapy Type:
├── is_cart, is_cart_with_retreatment
├── is_bispecific, is_adc, is_immunotherapy, is_biologic

Disease:
├── is_lymphoma, is_hematologic, is_solid_tumor

Study Features:
├── has_interim_analysis, has_ecg_monitoring
├── has_missing_data_concerns, has_follow_up_analyses
├── has_covid_impact, is_phase_2, is_phase_3
```

---

## 9. KB TOOLS (83 Tools by Category)

**File:** `kb_tools.py` (3,844 lines)

### Statistical Methods (15)
```
get_statistical_method()           → Cox, log-rank, CMH, K-M, MMRM
get_missing_data_method()          → LOCF, MMRM, MI, tipping point
get_sensitivity_analysis()         → Per-protocol, MNAR patterns
get_sensitivity_analysis_catalog() → Full sensitivity catalog
get_multiplicity_adjustment()      → Hochberg, Holm, gatekeeping
get_multiplicity_methods()         → Extended multiplicity methods
get_confidence_interval_methods()  → Clopper-Pearson, Wilson, Jeffreys
get_interim_analysis()             → O'Brien-Fleming, Lan-DeMets
get_interim_analysis_specs()       → Detailed interim specifications
get_time_to_event_analysis()       → K-M, Cox, RMST, landmark
get_censoring_rules()              → PFS, OS, DOR, EFS censoring
get_subgroup_analysis_specs()      → Forest plots, interaction tests
get_stratification_specs()         → Stratified analyses
get_stratification_balance_specs() → Balance assessment
get_phase2_design_specs()          → Simon two-stage, Fleming
```

### Population & Baseline (10)
```
get_population_definitions()       → ITT, mITT, Safety, PP definitions
get_demographics_baseline_specs()  → Age, sex, race, ECOG specs
get_prior_therapy_specs()          → Prior lines, refractory status
get_concomitant_medication_specs() → WHO Drug, ATC classification
get_medical_history_specs()        → MedDRA coding specs
get_organ_function_specs()         → Hepatic, renal, cardiac
get_organ_function_scores()        → Child-Pugh, CrCl, LVEF
get_performance_status_scales()    → ECOG, Karnofsky definitions
get_prognostic_scores()            → IPI, FLIPI, ISS, IMDC
get_enrollment_specifications()    → Enrollment summaries
```

### Endpoint & Response (12)
```
get_tumor_response_specs()         → Response assessment methodology
get_response_criteria()            → RECIST, Lugano by name
get_all_response_criteria()        → All criteria combined
get_recist_specifications()        → RECIST 1.1 details
get_cml_criteria()                 → CML ELN 2020 criteria
get_iwcll_criteria()               → iwCLL 2018 criteria
get_concordance_analysis()         → IRC vs Investigator analysis
get_concordance_specs()            → Kappa, concordance matrix
get_estimand_framework()           → ICH E9(R1) estimands
get_estimand_specifications()      → Detailed estimand specs
get_mrd_assessment_specs()         → MRD analysis methods
get_biomarker_endpoints()          → Biomarker analysis specs
```

### Safety Analysis (12)
```
get_safety_analysis_specs()        → AE, SAE, AESI analysis
get_safety_specifications()        → Safety methodology
get_safety_tables()                → Safety TFL shells
get_ae_period_specifications()     → TEAE windows
get_death_analysis_specs()         → Death summaries, last alive
get_exposure_specifications()      → Dose, duration, compliance
get_treatment_compliance_specs()   → Dose modifications
get_subsequent_therapy_specs()     → Post-study therapy
get_immunogenicity_specs()         → ADA analysis
get_meddra_search_strategies()     → SMQ, MST, custom queries
get_healthcare_utilization_specs() → HRU analysis
get_covid19_variations()           → COVID-19 sensitivity
```

### TFL Templates (12)
```
get_disposition_tables()           → Disposition shells
get_efficacy_tables()              → Efficacy shells
get_safety_tables()                → Safety shells
get_all_figures()                  → All figure specs
get_figure_template()              → Figure by ID
get_table_template()               → Table by ID
get_listings()                     → Listing shells
get_tfl_shells()                   → Combined TFL shells
get_oncology_tfl_templates()       → Oncology-specific TFL
get_single_arm_tables()            → Phase 2 tables
get_lymphoma_tables()              → Lymphoma-specific
get_cart_tables()                  → CAR-T specific
```

### Therapy-Specific (6)
```
get_cart_specifications()          → CRS, ICANS, kinetics
get_cart_manufacturing_specs()     → Leukapheresis, V2V time
get_bispecific_specifications()    → Bispecific safety
get_adc_specifications()           → ADC toxicities
get_pkpd_analysis_specs()          → PK/PD analysis
get_blinding_specifications()      → Blinding procedures
```

### Data & Programming (10)
```
get_adam_dataset_spec()            → ADSL, ADAE, ADTTE specs
get_data_handling_rules()          → Data conventions
get_programming_specifications()   → Programming specs
get_derived_variables()            → Derived variable specs
get_analysis_windows()             → Visit windows
get_analysis_timing_specs()        → Assessment timing
get_data_cutoff_specs()            → Data cutoff rules
get_date_imputation_rules()        → Partial date handling
get_tte_derivation_tables()        → DOR, PFS, OS circumstance tables
get_protocol_deviation_specs()     → Protocol deviations
```

### Study Design & References (6)
```
get_study_design_specs()           → Design methodology
get_study_type_template()          → Adjuvant, basket, umbrella
get_study_definitions()            → Study Day, baseline, TEAE
get_required_references()          → ICH, FDA citations
get_qol_analysis_specs()           → PRO/QoL instruments
get_pro_qol_analysis()             → PRO analysis methods
```

---

## 10. IMPORT CHAIN

```
main.py
└── kg_enhanced_pipeline.py
    │
    ├── kb_tools.py (83 tools)
    │   ├── methodology_knowledge_base.py
    │   │   └── 15 categories: STATISTICAL_METHODS, CENSORING_RULES, etc.
    │   │
    │   ├── complete_tfl_inventory.py
    │   │   └── 80+ TFL shells: Disposition, Efficacy, Safety, Figures, Listings
    │   │
    │   ├── production_sap_specifications.py
    │   │   └── 8 categories: TFL_SHELLS, ADAM_SPECIFICATIONS, etc.
    │   │
    │   ├── adam_specifications.py
    │   │   └── 11 datasets: ADSL, ADAE, ADTTE, ADRS, ADLB, ADEX, ADVS, ADEG, ADPR, ADCM, ADMH
    │   │
    │   ├── disease_specific_criteria.py
    │   │   └── 4 criteria: RANO, LUGANO, IMWG, RANO_BM
    │   │
    │   ├── oncology_reference_data.py
    │   │   └── 16 modules: IMWG, CML, IWCLL, CAR_T_MODULE, BISPECIFIC, ADC, etc.
    │   │
    │   └── comprehensive_sap_elements.py
    │       └── 35 categories: STUDY_DEFINITIONS, DEMOGRAPHICS, DEATH_ANALYSIS, etc.
    │
    ├── sap_structure_config.py
    │   └── 24 main sections, 30+ conditions
    │
    └── regulatory_standards.py
        └── 7 classes: CodingStandards, EstimandFramework, OncologyStandards, etc.
```

---

## SUMMARY STATISTICS

| Component | Count |
|-----------|-------|
| Total Python files | 26 |
| Total lines of code | 25,886 |
| KB Tools | 83 |
| SAP Main Sections | 24 |
| SAP Subsections | 70+ |
| Comprehensive SAP Categories | 35 |
| Methodology Categories | 15 |
| TFL Shells | 80+ |
| Disease Modules | 16 |
| Response Criteria | 4 |
| ADaM Datasets | 11 |
| Condition Detections | 30+ |
