"""
Knowledge Base Source Mapping - TRACED TO ACTUAL SAP DOCUMENTS
================================================================

Maps each KB structure to the actual reference SAP documents it was extracted from.
Each source is the full official title of the SAP document.

This provides full traceability for regulatory and validation purposes.

Usage:
    from kb_source_mapping import get_sources, get_all_sources_for_file

    sources = get_sources("CENSORING_RULES")
    # Returns: {"trials": [...], "note": "..."}
"""

# =============================================================================
# ACTUAL SAP TITLES - Full official titles from reference documents
# =============================================================================

KB_SOURCES = {
    # -------------------------------------------------------------------------
    # methodology_knowledge_base.py - CENSORING AND TIME-TO-EVENT METHODS
    # -------------------------------------------------------------------------
    "CENSORING_RULES": {
        "trials": [
            "ADAURA: A Phase III, Double-blind, Randomised Study to Assess the Efficacy and Safety of AZD9291 versus Placebo in Patients with Stage IB-IIIA Non-small Cell Lung Cancer Following Complete Tumour Resection with or without Adjuvant Chemotherapy (D5164C00001)",
            "ALEX: A Randomized, Multicenter, Phase III, Open-Label Study of Alectinib versus Crizotinib in Asian Patients with Treatment-Naive Anaplastic Lymphoma Kinase-Positive Advanced Non-Small Cell Lung Cancer (NCT02838420)",
            "BEACON CRC: A Multicenter, Randomized, Open-label, 3-Arm Phase 3 Study of Encorafenib + Cetuximab Plus or Minus Binimetinib vs. Irinotecan/Cetuximab in BRAF V600E-mutant Metastatic Colorectal Cancer (ARRAY-818-302)",
            "CheckMate-214: A Phase 3, Randomized, Open-Label Study of Nivolumab Combined with Ipilimumab versus Sunitinib Monotherapy in Subjects with Previously Untreated, Advanced or Metastatic Renal Cell Carcinoma (CA209214)",
            "CheckMate-649: A Randomized, Multicenter, Open-Label, Phase 3 Study of Nivolumab plus Ipilimumab or Nivolumab in Combination with Oxaliplatin plus Fluoropyrimidine in Subjects with Previously Untreated Advanced Gastric Cancer (CA209649)",
            "DESTINY-Breast03: A Phase 3, Multicenter, Randomized, Open-Label, Active-Controlled Study of Trastuzumab Deruxtecan versus Trastuzumab Emtansine for HER2-Positive Unresectable and/or Metastatic Breast Cancer (DS8201-A-U302)",
            "KEYNOTE-024: A Randomized Open-Label Phase III Trial of Pembrolizumab versus Platinum-based Chemotherapy in 1L Subjects with PD-L1 Strong Metastatic Non-Small Cell Lung Cancer (MK-3475-024)",
            "IMpower133: A Phase I/III, Randomized, Double-Blind, Placebo-Controlled Study of Carboplatin Plus Etoposide With or Without Atezolizumab in Patients With Untreated Extensive-Stage Small Cell Lung Cancer (NCT02763579)",
            "CASSIOPEIA: Study of Daratumumab in Combination with Bortezomib, Thalidomide, and Dexamethasone in First Line Treatment of Transplant Eligible Subjects with Newly Diagnosed Multiple Myeloma (NCT02541383)",
            "ClarIDHy: A Phase 3, Multicenter, Randomized, Double-Blind, Placebo-Controlled Study of AG-120 in Previously Treated Subjects with Nonresectable or Metastatic Cholangiocarcinoma with an IDH1 Mutation (AG120-C-005)",
            "POLO: A Phase III, Randomised, Double Blind, Placebo Controlled Study of Olaparib Maintenance Monotherapy in Patients with gBRCA Mutated Metastatic Pancreatic Cancer (D081FC00001)",
            "PRIMA: A Phase 3, Randomized, Double-Blind, Placebo-Controlled Study of Niraparib Maintenance Treatment in Patients with Advanced Ovarian Cancer Following Response on Front-Line Platinum-Based Chemotherapy (PR-30-5017-C)",
            "TOPAZ-1: A Phase III Randomized, Double-Blind, Placebo-Controlled Study of Durvalumab in Combination with Gemcitabine plus Cisplatin for Patients with First-Line Advanced Biliary Tract Cancers (D933AC00001)",
            "ENGOT-OV44/FIRST: A Randomized, Double-Blind, Phase 3 Comparison of Platinum-Based Therapy with TSR-042 and Niraparib versus Standard of Care as First-Line Treatment of Stage III or IV Nonmucinous Epithelial Ovarian Cancer (3000-03-005)",
            "EAA171/OPTIMUM: Optimizing Prolonged Treatment In Myeloma Using MRD Assessment",
            "ELARA: Tisagenlecleucel in Adult Patients with Relapsed or Refractory Follicular Lymphoma (CCTL019E2202)"
        ],
        "regulatory": [
            "ICH E9(R1): Addendum on Estimands and Sensitivity Analysis in Clinical Trials",
            "FDA Guidance: Clinical Trial Endpoints for the Approval of Cancer Drugs and Biologics"
        ],
        "note": "PFS/OS/DOR censoring rules extracted from 16 Phase 2/3 oncology SAPs"
    },

    "TIME_TO_EVENT_ANALYSIS": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC Study (D5164C00001)",
            "ALEX: Alectinib vs Crizotinib in ALK+ NSCLC (NCT02838420)",
            "BEACON CRC: Encorafenib + Cetuximab in BRAF V600E mCRC (ARRAY-818-302)",
            "BMT CTN 0901: Reduced Intensity Conditioning vs Myeloablative Conditioning for MDS/AML Transplant",
            "CASSIOPEIA: Daratumumab + VTD in Newly Diagnosed Multiple Myeloma (NCT02541383)",
            "CheckMate-214: Nivolumab + Ipilimumab vs Sunitinib in Renal Cell Carcinoma (CA209214)",
            "CheckMate-649: Nivolumab + Chemo in Gastric/GEJ Cancer (CA209649)",
            "DESTINY-Breast03: Trastuzumab Deruxtecan vs T-DM1 in HER2+ Breast Cancer (DS8201-A-U302)",
            "IMpower133: Atezolizumab + Chemo in ES-SCLC (NCT02763579)",
            "KEYNOTE-024: Pembrolizumab vs Chemotherapy in PD-L1+ NSCLC (MK-3475-024)",
            "PACIFIC: Durvalumab Sequential Therapy in Stage III NSCLC (D4191C00001)",
            "POLO: Olaparib Maintenance in gBRCA+ Pancreatic Cancer (D081FC00001)",
            "PROfound: Olaparib vs Enzalutamide/Abiraterone in mCRPC with HRR Mutations (D081DC00007)",
            "VISION: 177Lu-PSMA-617 in Progressive PSMA-positive mCRPC (NCT03511664)"
        ],
        "note": "Kaplan-Meier, Cox regression, stratified log-rank from 14 Phase 2/3 TTE trials"
    },

    "STATISTICAL_METHODS": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC Study (D5164C00001)",
            "ALEX: Alectinib vs Crizotinib in ALK+ NSCLC (NCT02838420)",
            "BEACON CRC: Encorafenib + Cetuximab in BRAF V600E mCRC (ARRAY-818-302)",
            "CASSIOPEIA: Daratumumab + VTD in NDMM (NCT02541383)",
            "ClarIDHy: AG-120 in IDH1-mutant Cholangiocarcinoma (AG120-C-005)",
            "ENGOT-OV44/FIRST: Niraparib + TSR-042 in First-Line Ovarian Cancer (3000-03-005)",
            "IMpower133: Atezolizumab + Chemo in ES-SCLC (NCT02763579)",
            "InnovaTV 301: Tisotumab Vedotin in Recurrent/Metastatic Cervical Cancer (SGNTV-003)",
            "KATHERINE: Trastuzumab Emtansine vs Trastuzumab as Adjuvant Therapy in HER2+ Breast Cancer with Residual Disease (NCT01772472)",
            "MONALEESA-3: Ribociclib + Fulvestrant in HR+/HER2- Advanced Breast Cancer (CLEE011F2301)"
        ],
        "regulatory": [
            "ICH E9: Statistical Principles for Clinical Trials",
            "ICH E9(R1): Addendum on Estimands and Sensitivity Analysis"
        ],
        "note": "Stratified log-rank, CMH, Cox regression from 10 Phase 3 trials"
    },

    "STRATIFICATION_SPECIFICATIONS": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001) - Stage, EGFR mutation type",
            "ALEX: Alectinib vs Crizotinib (NCT02838420) - CNS metastases, ECOG PS",
            "BEACON CRC: Encorafenib + Cetuximab (ARRAY-818-302) - ECOG PS, prior irinotecan",
            "CASSIOPEIA: Daratumumab + VTD (NCT02541383) - ISS stage, region",
            "CheckMate-214: Nivolumab + Ipilimumab (CA209214) - IMDC risk, region",
            "DESTINY-Breast03: T-DXd vs T-DM1 (DS8201-A-U302) - HR status, prior pertuzumab, visceral disease",
            "IMpower133: Atezolizumab + Chemo (NCT02763579) - Sex, ECOG PS, brain metastases",
            "KEYNOTE-024: Pembrolizumab (MK-3475-024) - ECOG PS, region, histology",
            "MONALEESA-3: Ribociclib + Fulvestrant (CLEE011F2301) - Lung/liver metastases, prior endocrine therapy"
        ],
        "note": "Randomization stratification factors from 9 Phase 3 trials"
    },

    "MISSING_DATA_HANDLING": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001)",
            "BEACON CRC: Encorafenib + Cetuximab (ARRAY-818-302)",
            "CASSIOPEIA: Daratumumab + VTD (NCT02541383)",
            "ClarIDHy: AG-120 in Cholangiocarcinoma (AG120-C-005)",
            "ENGOT-OV44/FIRST: Niraparib + TSR-042 (3000-03-005)",
            "IMpower133: Atezolizumab + Chemo (NCT02763579)",
            "MissingData-PatternMixture: Pattern Mixture Models Reference SAP"
        ],
        "regulatory": [
            "ICH E9(R1): Estimands and Sensitivity Analysis",
            "EMA Guideline on Missing Data in Confirmatory Clinical Trials"
        ],
        "note": "LOCF, MMRM, multiple imputation, pattern mixture from 7 Phase 3 SAPs"
    },

    "SENSITIVITY_ANALYSES": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001)",
            "BEACON CRC: Encorafenib + Cetuximab (ARRAY-818-302)",
            "CASSIOPEIA: Daratumumab + VTD (NCT02541383)",
            "ClarIDHy: AG-120 in Cholangiocarcinoma (AG120-C-005)",
            "ENGOT-OV44/FIRST: Niraparib + TSR-042 (3000-03-005)",
            "IMpower133: Atezolizumab + Chemo (NCT02763579)",
            "KEYNOTE-024: Pembrolizumab (MK-3475-024)"
        ],
        "regulatory": ["ICH E9(R1): Estimands and Sensitivity Analysis"],
        "note": "Tipping point, per-protocol, treatment policy estimand from 7 Phase 3 SAPs"
    },

    "MULTIPLICITY_ADJUSTMENT": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001) - Hierarchical testing",
            "CASSIOPEIA: Daratumumab + VTD (NCT02541383) - Sequential testing",
            "ClarIDHy: AG-120 in Cholangiocarcinoma (AG120-C-005) - Hierarchical testing",
            "ENGOT-OV44/FIRST: Niraparib + TSR-042 (3000-03-005) - Graphical approach",
            "IMpower133: Atezolizumab + Chemo (NCT02763579) - Hierarchical testing",
            "InnovaTV 301: Tisotumab Vedotin (SGNTV-003) - Alpha spending",
            "KEYNOTE-024: Pembrolizumab (MK-3475-024) - O'Brien-Fleming",
            "MONALEESA-3: Ribociclib + Fulvestrant (CLEE011F2301) - Alpha allocation",
            "Multiplicity-Graphical: Graphical Approaches Reference SAP"
        ],
        "regulatory": [
            "EMA Guideline on Multiplicity Issues",
            "FDA Guidance: Multiple Endpoints in Clinical Trials"
        ],
        "note": "Graphical approaches, alpha spending, hierarchical testing from 9 sources"
    },

    "SUBGROUP_ANALYSIS_SPECIFICATIONS": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001)",
            "ALEX: Alectinib vs Crizotinib (NCT02838420)",
            "BEACON CRC: Encorafenib + Cetuximab (ARRAY-818-302)",
            "CASSIOPEIA: Daratumumab + VTD (NCT02541383)",
            "CheckMate-214: Nivolumab + Ipilimumab (CA209214)",
            "DESTINY-Breast03: T-DXd vs T-DM1 (DS8201-A-U302)",
            "IMpower133: Atezolizumab + Chemo (NCT02763579)",
            "ForestPlot-Shells: Forest Plot Template SAP"
        ],
        "note": "Subgroup analysis and forest plot specifications from 8 sources"
    },

    "INTERIM_ANALYSIS_SPECIFICATIONS": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001) - 2 interim analyses",
            "ALEX: Alectinib vs Crizotinib (NCT02838420) - 1 interim analysis",
            "BEACON CRC: Encorafenib + Cetuximab (ARRAY-818-302) - 1 interim analysis",
            "CASSIOPEIA: Daratumumab + VTD (NCT02541383) - 2 interim analyses",
            "ClarIDHy: AG-120 in Cholangiocarcinoma (AG120-C-005) - 1 interim analysis",
            "DESTINY-Breast03: T-DXd vs T-DM1 (DS8201-A-U302) - 1 interim analysis",
            "MONALEESA-3: Ribociclib + Fulvestrant (CLEE011F2301) - 2 interim analyses",
            "Interim-OBF: O'Brien-Fleming Alpha Spending Reference SAP"
        ],
        "regulatory": ["FDA Guidance: Adaptive Designs for Clinical Trials"],
        "note": "O'Brien-Fleming, Lan-DeMets alpha spending from 8 sources"
    },

    "CONFIDENCE_INTERVAL_METHODS": {
        "trials": [
            "ZUMA-3: KTE-X19 in Relapsed/Refractory B-precursor ALL - Clopper-Pearson exact CI",
            "ELIANA: CTL019 in Pediatric/Young Adult r/r B-ALL (CTL019B2202) - Exact binomial CI",
            "ELARA: Tisagenlecleucel in r/r Follicular Lymphoma (CCTL019E2202) - Clopper-Pearson CI",
            "EMPOWER-CSCC1: Cemiplimab in Advanced Cutaneous Squamous Cell Carcinoma (R2810-ONC-1540) - Exact CI",
            "NCI Anti-CD19 CAR: Anti-CD19 CAR T-Cells in B-Cell Lymphoma (09-C-0082) - Exact CI"
        ],
        "note": "Clopper-Pearson exact CI methods from 5 single-arm trials"
    },

    "HEALTHCARE_UTILIZATION": {
        "trials": [
            "ZUMA-3: KTE-X19 in r/r ALL - ICU days, hospitalization",
            "ELIANA: CTL019 in r/r B-ALL (CTL019B2202) - ICU days, hospital LOS",
            "EQ5D-HealthUtility: Health Utility Assessment Reference SAP"
        ],
        "note": "ICU days, hospitalization, healthcare resource use from CAR-T trials"
    },

    # -------------------------------------------------------------------------
    # disease_specific_criteria.py - RESPONSE CRITERIA
    # -------------------------------------------------------------------------
    "RECIST_1_1": {
        "trials": [
            "ALEX: Alectinib vs Crizotinib in ALK+ NSCLC (NCT02838420)",
            "BEACON CRC: Encorafenib + Cetuximab in BRAF V600E mCRC (ARRAY-818-302)",
            "CheckMate-214: Nivolumab + Ipilimumab in RCC (CA209214)",
            "CheckMate-649: Nivolumab + Chemo in Gastric Cancer (CA209649)",
            "ClarIDHy: AG-120 in IDH1-mutant Cholangiocarcinoma (AG120-C-005)",
            "DESTINY-Breast03: T-DXd vs T-DM1 in HER2+ Breast Cancer (DS8201-A-U302)",
            "IMpower133: Atezolizumab + Chemo in ES-SCLC (NCT02763579)",
            "KEYNOTE-024: Pembrolizumab vs Chemo in PD-L1+ NSCLC (MK-3475-024)",
            "PACIFIC: Durvalumab in Stage III NSCLC (D4191C00001)",
            "POLO: Olaparib in gBRCA+ Pancreatic Cancer (D081FC00001)",
            "TOPAZ-1: Durvalumab + Chemo in Biliary Tract Cancer (D933AC00001)"
        ],
        "regulatory": ["Eisenhauer EA, et al. Eur J Cancer 2009;45:228-247 (RECIST 1.1)"],
        "note": "RECIST 1.1 response criteria from 11 solid tumor SAPs"
    },

    "LUGANO_CRITERIA": {
        "trials": [
            "ELARA: Tisagenlecleucel in r/r Follicular Lymphoma (CCTL019E2202)",
            "L-MIND: Tafasitamab + Lenalidomide in r/r DLBCL (MOR208C203)",
            "Lugano-Lymphoma/COASTAL: Zandelisib + Rituximab in Relapsed iNHL (NCT04745832)",
            "SHINE: Ibrutinib + BR in Newly Diagnosed Mantle Cell Lymphoma (PCI-32765MCL3002)"
        ],
        "regulatory": ["Cheson BD, et al. J Clin Oncol 2014;32:3059-3068 (Lugano Classification)"],
        "note": "Lugano 2014 lymphoma response criteria from 4 lymphoma SAPs"
    },

    "IMWG_CRITERIA": {
        "trials": [
            "CASSIOPEIA: Daratumumab + VTD in NDMM (NCT02541383)",
            "EAA171/OPTIMUM: MRD-Based Treatment Duration in Multiple Myeloma",
            "Elo-KRd-MRD: Elotuzumab + Carfilzomib + Lenalidomide + Dexamethasone MRD Study"
        ],
        "regulatory": ["Kumar S, et al. Lancet Oncol 2016;17:e328-e346 (IMWG Criteria)"],
        "note": "IMWG myeloma response criteria from 3 multiple myeloma SAPs"
    },

    "PCWG3_CRITERIA": {
        "trials": [
            "PROfound: Olaparib vs Enzalutamide/Abiraterone in mCRPC with HRR Mutations (D081DC00007)",
            "VISION: 177Lu-PSMA-617 in Progressive PSMA-positive mCRPC (NCT03511664)"
        ],
        "regulatory": ["Scher HI, et al. J Clin Oncol 2016;34:1402-1418 (PCWG3)"],
        "note": "PCWG3 prostate cancer response criteria from 2 mCRPC SAPs"
    },

    "GCIG_CA125_CRITERIA": {
        "trials": [
            "ENGOT-OV44/FIRST: Niraparib + TSR-042 in First-Line Ovarian Cancer (3000-03-005)",
            "Durva-Olaparib/DORA: Durvalumab + Olaparib in Platinum-Treated TNBC (ESR-15-11311)",
            "PRIMA: Niraparib Maintenance in Advanced Ovarian Cancer (PR-30-5017-C)"
        ],
        "regulatory": ["Rustin GJ, et al. Int J Gynecol Cancer 2011;21:419-423 (GCIG CA-125)"],
        "note": "GCIG CA-125 ovarian cancer response criteria from 3 ovarian cancer SAPs"
    },

    "irRECIST": {
        "trials": [
            "Avelumab-IO: Avelumab vs Docetaxel in NSCLC That Has Progressed After Platinum-Containing Doublet (EMR100070-004)",
            "CheckMate-214: Nivolumab + Ipilimumab in RCC (CA209214)",
            "CheckMate-649: Nivolumab + Chemo in Gastric Cancer (CA209649)",
            "EMPOWER-CSCC1: Cemiplimab in Advanced CSCC (R2810-ONC-1540)"
        ],
        "regulatory": ["iRECIST Guidelines (Lancet Oncology 2017)"],
        "note": "Immune-related RECIST from 4 immunotherapy SAPs"
    },

    # -------------------------------------------------------------------------
    # oncology_reference_data.py - THERAPY-SPECIFIC MODULES
    # -------------------------------------------------------------------------
    "CAR_T_MODULE": {
        "trials": [
            "ZUMA-1: Axicabtagene Ciloleucel in Refractory Large B-Cell Lymphoma",
            "ZUMA-3: KTE-X19 in Relapsed/Refractory B-precursor Acute Lymphoblastic Leukemia",
            "ELIANA: CTL019 in Pediatric/Young Adult r/r B-ALL (CTL019B2202)",
            "ELARA: Tisagenlecleucel in r/r Follicular Lymphoma (CCTL019E2202)",
            "NCI Anti-CD19 CAR: Anti-CD19 CAR T-Cells in B-Cell Lymphoma (09-C-0082)"
        ],
        "note": "CAR-T specific endpoints: CRS grading, bridging therapy, manufacturing from 5 CAR-T SAPs"
    },

    "BISPECIFIC_MODULE": {
        "trials": [
            "CD19-CD22 BiCART: Bispecific CD19/CD22 CAR-T Study",
            "FDA Elranatamab Review: Bispecific T-cell Engager in Multiple Myeloma",
            "FDA Teclistamab Review: Bispecific T-cell Engager in Multiple Myeloma"
        ],
        "note": "Bispecific antibody endpoints: CRS, step-up dosing from 3 bispecific sources"
    },

    "ADC_MODULE": {
        "trials": [
            "DESTINY-Breast03: Trastuzumab Deruxtecan vs T-DM1 in HER2+ Breast Cancer (DS8201-A-U302)",
            "EV-301: Enfortumab Vedotin in Locally Advanced or Metastatic Urothelial Cancer",
            "InnovaTV 301: Tisotumab Vedotin in Recurrent/Metastatic Cervical Cancer (SGNTV-003)",
            "KATHERINE: Trastuzumab Emtansine vs Trastuzumab as Adjuvant (NCT01772472)"
        ],
        "note": "ADC-specific endpoints: ocular toxicity, ILD monitoring from 4 ADC SAPs"
    },

    "CHECKPOINT_INHIBITOR_MODULE": {
        "trials": [
            "CheckMate-214: Nivolumab + Ipilimumab in RCC (CA209214)",
            "CheckMate-649: Nivolumab + Chemo in Gastric Cancer (CA209649)",
            "IMpower133: Atezolizumab + Chemo in ES-SCLC (NCT02763579)",
            "KEYNOTE-024: Pembrolizumab vs Chemo in PD-L1+ NSCLC (MK-3475-024)",
            "PACIFIC: Durvalumab in Stage III NSCLC (D4191C00001)",
            "EMPOWER-CSCC1: Cemiplimab in Advanced CSCC (R2810-ONC-1540)",
            "Avelumab-IO: Avelumab vs Docetaxel in NSCLC (EMR100070-004)"
        ],
        "note": "Checkpoint inhibitor irAE monitoring, pseudoprogression from 7 IO SAPs"
    },

    "PARP_INHIBITOR_MODULE": {
        "trials": [
            "POLO: Olaparib in gBRCA+ Pancreatic Cancer (D081FC00001)",
            "PROfound: Olaparib in mCRPC with HRR Mutations (D081DC00007)",
            "PRIMA: Niraparib Maintenance in Advanced Ovarian Cancer (PR-30-5017-C)",
            "ENGOT-OV44/FIRST: Niraparib + TSR-042 in Ovarian Cancer (3000-03-005)",
            "Durva-Olaparib/DORA: Durvalumab + Olaparib in TNBC (ESR-15-11311)"
        ],
        "note": "PARP inhibitor-specific: MDS/AML monitoring, dose modifications from 5 PARP SAPs"
    },

    "CDK4_6_INHIBITOR_MODULE": {
        "trials": [
            "MONALEESA-3: Ribociclib + Fulvestrant in HR+/HER2- ABC (CLEE011F2301)",
            "MONALEESA-7: Ribociclib + NSAI/Tamoxifen in Pre/Perimenopausal HR+ ABC",
            "PALOMA-3: Palbociclib + Fulvestrant in HR+/HER2- mBC After Prior Endocrine (A5481023)"
        ],
        "note": "CDK4/6 inhibitor: neutropenia management, QTc monitoring from 3 CDK4/6 SAPs"
    },

    # -------------------------------------------------------------------------
    # complete_tfl_inventory.py - TFL SHELLS
    # -------------------------------------------------------------------------
    "DISPOSITION_TABLES": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001)",
            "CASSIOPEIA: Daratumumab + VTD (NCT02541383)",
            "KEYNOTE-024: Pembrolizumab (MK-3475-024)",
            "DMC-TFL-Shells: Data Monitoring Committee TFL Template"
        ],
        "note": "Patient disposition table shells from 4 sources"
    },

    "EFFICACY_TABLES": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001)",
            "BEACON CRC: Encorafenib + Cetuximab (ARRAY-818-302)",
            "CheckMate-214: Nivolumab + Ipilimumab (CA209214)",
            "DESTINY-Breast03: T-DXd vs T-DM1 (DS8201-A-U302)",
            "IMpower133: Atezolizumab + Chemo (NCT02763579)",
            "KEYNOTE-024: Pembrolizumab (MK-3475-024)",
            "TFL-Shells-Template: Standard TFL Shell Template"
        ],
        "note": "Efficacy table shells (PFS, OS, ORR) from 7 sources"
    },

    "SAFETY_TABLES": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001)",
            "CASSIOPEIA: Daratumumab + VTD (NCT02541383)",
            "DESTINY-Breast03: T-DXd vs T-DM1 (DS8201-A-U302)",
            "IMpower133: Atezolizumab + Chemo (NCT02763579)",
            "ZUMA-3: KTE-X19 in r/r ALL"
        ],
        "regulatory": ["CTCAE v5.0 Quick Reference"],
        "note": "AE summary, SAE, AESI table shells from 5 Phase 2/3 SAPs"
    },

    "KAPLAN_MEIER_FIGURES": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001)",
            "CheckMate-214: Nivolumab + Ipilimumab (CA209214)",
            "CheckMate-649: Nivolumab + Chemo (CA209649)",
            "DESTINY-Breast03: T-DXd vs T-DM1 (DS8201-A-U302)",
            "IMpower133: Atezolizumab + Chemo (NCT02763579)",
            "KEYNOTE-024: Pembrolizumab (MK-3475-024)"
        ],
        "note": "Kaplan-Meier figure specifications from 6 Phase 3 SAPs"
    },

    "FOREST_PLOT_FIGURES": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001)",
            "CheckMate-214: Nivolumab + Ipilimumab (CA209214)",
            "DESTINY-Breast03: T-DXd vs T-DM1 (DS8201-A-U302)",
            "ForestPlot-Shells: Forest Plot Template SAP"
        ],
        "note": "Forest plot subgroup analysis specifications from 4 sources"
    },

    "WATERFALL_PLOT_FIGURES": {
        "trials": [
            "ZUMA-3: KTE-X19 in r/r ALL",
            "ELIANA: CTL019 in r/r B-ALL (CTL019B2202)",
            "DESTINY-Breast03: T-DXd vs T-DM1 (DS8201-A-U302)"
        ],
        "note": "Waterfall plot tumor response specifications from 3 SAPs"
    },

    "SWIMMER_PLOT_FIGURES": {
        "trials": [
            "ZUMA-3: KTE-X19 in r/r ALL",
            "ELIANA: CTL019 in r/r B-ALL (CTL019B2202)",
            "ELARA: Tisagenlecleucel in r/r FL (CCTL019E2202)"
        ],
        "note": "Swimmer plot duration of response specifications from 3 CAR-T SAPs"
    },

    # -------------------------------------------------------------------------
    # comprehensive_sap_elements.py - BASELINE COVARIATES
    # -------------------------------------------------------------------------
    "BASELINE_COVARIATES_SOLID_TUMOR": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001)",
            "ALEX: Alectinib vs Crizotinib (NCT02838420)",
            "BEACON CRC: Encorafenib + Cetuximab (ARRAY-818-302)",
            "CheckMate-214: Nivolumab + Ipilimumab (CA209214)",
            "DESTINY-Breast03: T-DXd vs T-DM1 (DS8201-A-U302)",
            "IMpower133: Atezolizumab + Chemo (NCT02763579)",
            "KEYNOTE-024: Pembrolizumab (MK-3475-024)"
        ],
        "note": "Solid tumor baseline covariates from 7 Phase 3 SAPs"
    },

    "BASELINE_COVARIATES_HEMATOLOGIC": {
        "trials": [
            "CASSIOPEIA: Daratumumab + VTD (NCT02541383)",
            "ZUMA-3: KTE-X19 in r/r ALL",
            "ELIANA: CTL019 in r/r B-ALL (CTL019B2202)",
            "ELARA: Tisagenlecleucel in r/r FL (CCTL019E2202)",
            "VIALE-A: Venetoclax + Azacitidine in Treatment-Naive AML (M15-656)"
        ],
        "note": "Hematologic malignancy baseline covariates from 5 SAPs"
    },

    "BASELINE_COVARIATES_LYMPHOMA": {
        "trials": [
            "ELARA: Tisagenlecleucel in r/r Follicular Lymphoma (CCTL019E2202)",
            "L-MIND: Tafasitamab + Lenalidomide in r/r DLBCL (MOR208C203)",
            "SHINE: Ibrutinib + BR in Newly Diagnosed MCL (PCI-32765MCL3002)",
            "Lugano-Lymphoma/COASTAL: Zandelisib + Rituximab in Relapsed iNHL (NCT04745832)"
        ],
        "note": "Lymphoma-specific covariates: Ann Arbor stage, IPI, prior lines from 4 lymphoma SAPs"
    },

    "BASELINE_COVARIATES_MYELOMA": {
        "trials": [
            "CASSIOPEIA: Daratumumab + VTD (NCT02541383)",
            "EAA171/OPTIMUM: MRD-Based Treatment in Multiple Myeloma"
        ],
        "note": "Myeloma-specific covariates: ISS stage, cytogenetics, renal function from 2 MM SAPs"
    },

    "BASELINE_COVARIATES_AML": {
        "trials": [
            "VIALE-A: Venetoclax + Azacitidine in Treatment-Naive AML (M15-656)",
            "BMT CTN 0901: RIC vs MAC for MDS/AML Transplant",
            "QUAZAR: Oral Azacitidine Maintenance in AML"
        ],
        "note": "AML-specific covariates: ELN risk, cytogenetics, FLT3/NPM1 from 3 AML SAPs"
    },

    "BASELINE_COVARIATES_CLL": {
        "trials": [
            "CLL-MRD: LOXO-305 in Previously Treated CLL/SLL (J2N-MC-JZNJ)"
        ],
        "note": "CLL-specific covariates: Rai stage, del(17p), TP53 mutation, IGHV from 1 CLL SAP"
    },

    "BASELINE_COVARIATES_BREAST": {
        "trials": [
            "DESTINY-Breast03: T-DXd vs T-DM1 (DS8201-A-U302)",
            "KATHERINE: T-DM1 vs Trastuzumab as Adjuvant (NCT01772472)",
            "MONALEESA-3: Ribociclib + Fulvestrant (CLEE011F2301)",
            "PALOMA-3: Palbociclib + Fulvestrant (A5481023)"
        ],
        "note": "Breast cancer covariates: HR/HER2 status, visceral disease, prior therapy from 4 SAPs"
    },

    "BASELINE_COVARIATES_LUNG": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001)",
            "ALEX: Alectinib vs Crizotinib (NCT02838420)",
            "IMpower133: Atezolizumab + Chemo (NCT02763579)",
            "KEYNOTE-024: Pembrolizumab (MK-3475-024)",
            "PACIFIC: Durvalumab in Stage III NSCLC (D4191C00001)"
        ],
        "note": "Lung cancer covariates: histology, EGFR/ALK status, PD-L1, brain mets from 5 SAPs"
    },

    "BASELINE_COVARIATES_GI": {
        "trials": [
            "BEACON CRC: Encorafenib + Cetuximab (ARRAY-818-302)",
            "CheckMate-649: Nivolumab + Chemo (CA209649)",
            "POLO: Olaparib in gBRCA+ Pancreatic (D081FC00001)",
            "TOPAZ-1: Durvalumab + Chemo in BTC (D933AC00001)",
            "ClarIDHy: AG-120 in Cholangiocarcinoma (AG120-C-005)"
        ],
        "note": "GI cancer covariates: primary tumor location, MSI status, BRAF/KRAS from 5 SAPs"
    },

    "BASELINE_COVARIATES_GU": {
        "trials": [
            "CheckMate-214: Nivolumab + Ipilimumab (CA209214)",
            "PROfound: Olaparib in mCRPC (D081DC00007)",
            "VISION: 177Lu-PSMA-617 in mCRPC (NCT03511664)",
            "EV-301: Enfortumab Vedotin in Urothelial Cancer"
        ],
        "note": "GU cancer covariates: IMDC risk, HRR mutation, PSMA status from 4 SAPs"
    },

    "BASELINE_COVARIATES_GYN": {
        "trials": [
            "ENGOT-OV44/FIRST: Niraparib + TSR-042 (3000-03-005)",
            "PRIMA: Niraparib Maintenance (PR-30-5017-C)",
            "InnovaTV 301: Tisotumab Vedotin in Cervical (SGNTV-003)"
        ],
        "note": "GYN cancer covariates: BRCA status, HRD, platinum sensitivity from 3 SAPs"
    },

    # -------------------------------------------------------------------------
    # production_sap_specifications.py - ESTIMANDS AND ADaM
    # -------------------------------------------------------------------------
    "ESTIMANDS_FRAMEWORK": {
        "trials": [
            "ADAURA: AZD9291 Adjuvant NSCLC (D5164C00001)",
            "CASSIOPEIA: Daratumumab + VTD (NCT02541383)",
            "ENGOT-OV44/FIRST: Niraparib + TSR-042 (3000-03-005)"
        ],
        "regulatory": ["ICH E9(R1): Addendum on Estimands and Sensitivity Analysis"],
        "note": "Treatment policy, composite, hypothetical estimands from 3 SAPs + ICH E9(R1)"
    },

    "ADAM_SPECIFICATIONS": {
        "trials": [
            "CDISC ADaM TTE: Analysis Data Model for Time-to-Event",
            "KEYNOTE-024: Pembrolizumab (MK-3475-024)",
            "CheckMate-214: Nivolumab + Ipilimumab (CA209214)"
        ],
        "regulatory": ["CDISC ADaM Implementation Guide"],
        "note": "ADTTE, ADRS, ADSL specifications from 3 sources"
    },

    "MRD_SPECIFICATIONS": {
        "trials": [
            "CASSIOPEIA: Daratumumab + VTD (NCT02541383)",
            "EAA171/OPTIMUM: MRD-Based Treatment in Multiple Myeloma",
            "CLL-MRD: LOXO-305 in CLL/SLL (J2N-MC-JZNJ)"
        ],
        "regulatory": ["FDA Guidance: Use of Minimal Residual Disease in Heme Malignancies"],
        "note": "MRD negativity rate, sensitivity thresholds from 3 SAPs"
    },

    # -------------------------------------------------------------------------
    # regulatory_standards.py - REGULATORY SOURCES
    # -------------------------------------------------------------------------
    "ICH_E9_R1": {
        "regulatory": ["ICH E9(R1): Addendum on Estimands and Sensitivity Analysis in Clinical Trials to the Guideline on Statistical Principles for Clinical Trials"],
        "note": "Estimand framework: population, treatment, variable, intercurrent events, summary measure"
    },

    "FDA_ONCOLOGY_ENDPOINTS": {
        "regulatory": ["FDA Guidance for Industry: Clinical Trial Endpoints for the Approval of Cancer Drugs and Biologics (December 2018)"],
        "note": "OS, PFS, ORR, DOR endpoint definitions and regulatory requirements"
    },

    "EMA_ANTICANCER_GUIDELINE": {
        "regulatory": ["EMA Guideline on the Evaluation of Anticancer Medicinal Products in Man (Rev. 6)"],
        "note": "European regulatory requirements for oncology trials"
    },

    "CTCAE_V5": {
        "regulatory": ["CTCAE v5.0: Common Terminology Criteria for Adverse Events Version 5.0"],
        "note": "Adverse event grading criteria for safety reporting"
    },

    "MEDDRA": {
        "regulatory": ["MedDRA Version 26.1: Medical Dictionary for Regulatory Activities"],
        "note": "Standardized medical terminology for AE coding"
    }
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_sources(source_key: str) -> dict:
    """
    Get source information for a KB structure.

    Args:
        source_key: The structure name (e.g., "CENSORING_RULES")

    Returns:
        Dict with trials, regulatory sources, and note
    """
    # Direct lookup
    if source_key in KB_SOURCES:
        return KB_SOURCES[source_key]

    # Try uppercase
    upper_key = source_key.upper().replace(" ", "_").replace("-", "_")
    if upper_key in KB_SOURCES:
        return KB_SOURCES[upper_key]

    # Pattern matching for descriptive source_key strings
    source_key_lower = source_key.lower()

    pattern_mappings = {
        "censoring": "CENSORING_RULES",
        "time-to-event": "TIME_TO_EVENT_ANALYSIS",
        "time_to_event": "TIME_TO_EVENT_ANALYSIS",
        "kaplan": "TIME_TO_EVENT_ANALYSIS",
        "statistical_methods": "STATISTICAL_METHODS",
        "stratification": "STRATIFICATION_SPECIFICATIONS",
        "missing_data": "MISSING_DATA_HANDLING",
        "missing data": "MISSING_DATA_HANDLING",
        "sensitivity": "SENSITIVITY_ANALYSES",
        "multiplicity": "MULTIPLICITY_ADJUSTMENT",
        "subgroup": "SUBGROUP_ANALYSIS_SPECIFICATIONS",
        "interim": "INTERIM_ANALYSIS_SPECIFICATIONS",
        "confidence_interval": "CONFIDENCE_INTERVAL_METHODS",
        "recist": "RECIST_1_1",
        "lugano": "LUGANO_CRITERIA",
        "imwg": "IMWG_CRITERIA",
        "pcwg": "PCWG3_CRITERIA",
        "ca125": "GCIG_CA125_CRITERIA",
        "car_t": "CAR_T_MODULE",
        "car-t": "CAR_T_MODULE",
        "bispecific": "BISPECIFIC_MODULE",
        "adc": "ADC_MODULE",
        "antibody drug conjugate": "ADC_MODULE",
        "checkpoint": "CHECKPOINT_INHIBITOR_MODULE",
        "parp": "PARP_INHIBITOR_MODULE",
        "cdk4": "CDK4_6_INHIBITOR_MODULE",
        "disposition": "DISPOSITION_TABLES",
        "efficacy_table": "EFFICACY_TABLES",
        "safety_table": "SAFETY_TABLES",
        "kaplan_meier_figure": "KAPLAN_MEIER_FIGURES",
        "forest_plot": "FOREST_PLOT_FIGURES",
        "waterfall": "WATERFALL_PLOT_FIGURES",
        "swimmer": "SWIMMER_PLOT_FIGURES",
        "solid_tumor": "BASELINE_COVARIATES_SOLID_TUMOR",
        "hematologic": "BASELINE_COVARIATES_HEMATOLOGIC",
        "lymphoma": "BASELINE_COVARIATES_LYMPHOMA",
        "myeloma": "BASELINE_COVARIATES_MYELOMA",
        "aml": "BASELINE_COVARIATES_AML",
        "cll": "BASELINE_COVARIATES_CLL",
        "breast": "BASELINE_COVARIATES_BREAST",
        "lung": "BASELINE_COVARIATES_LUNG",
        "gi_cancer": "BASELINE_COVARIATES_GI",
        "gu_cancer": "BASELINE_COVARIATES_GU",
        "gyn": "BASELINE_COVARIATES_GYN",
        "estimand": "ESTIMANDS_FRAMEWORK",
        "adam": "ADAM_SPECIFICATIONS",
        "mrd": "MRD_SPECIFICATIONS",
        "ich_e9": "ICH_E9_R1",
        "fda_oncology": "FDA_ONCOLOGY_ENDPOINTS",
        "ema_anticancer": "EMA_ANTICANCER_GUIDELINE",
        "ctcae": "CTCAE_V5",
        "meddra": "MEDDRA"
    }

    for pattern, mapped_key in pattern_mappings.items():
        if pattern in source_key_lower:
            return KB_SOURCES.get(mapped_key, {})

    return {}


def get_all_sources_for_file(filename: str) -> dict:
    """
    Get all source mappings for structures in a specific KB file.

    Args:
        filename: The KB file name (e.g., "methodology_knowledge_base.py")

    Returns:
        Dict mapping structure names to their sources
    """
    file_structures = {
        "methodology_knowledge_base.py": [
            "CENSORING_RULES", "TIME_TO_EVENT_ANALYSIS", "STATISTICAL_METHODS",
            "STRATIFICATION_SPECIFICATIONS", "MISSING_DATA_HANDLING",
            "SENSITIVITY_ANALYSES", "MULTIPLICITY_ADJUSTMENT",
            "SUBGROUP_ANALYSIS_SPECIFICATIONS", "INTERIM_ANALYSIS_SPECIFICATIONS",
            "CONFIDENCE_INTERVAL_METHODS", "HEALTHCARE_UTILIZATION"
        ],
        "disease_specific_criteria.py": [
            "RECIST_1_1", "LUGANO_CRITERIA", "IMWG_CRITERIA",
            "PCWG3_CRITERIA", "GCIG_CA125_CRITERIA", "irRECIST"
        ],
        "oncology_reference_data.py": [
            "CAR_T_MODULE", "BISPECIFIC_MODULE", "ADC_MODULE",
            "CHECKPOINT_INHIBITOR_MODULE", "PARP_INHIBITOR_MODULE",
            "CDK4_6_INHIBITOR_MODULE"
        ],
        "complete_tfl_inventory.py": [
            "DISPOSITION_TABLES", "EFFICACY_TABLES", "SAFETY_TABLES",
            "KAPLAN_MEIER_FIGURES", "FOREST_PLOT_FIGURES",
            "WATERFALL_PLOT_FIGURES", "SWIMMER_PLOT_FIGURES"
        ],
        "comprehensive_sap_elements.py": [
            "BASELINE_COVARIATES_SOLID_TUMOR", "BASELINE_COVARIATES_HEMATOLOGIC",
            "BASELINE_COVARIATES_LYMPHOMA", "BASELINE_COVARIATES_MYELOMA",
            "BASELINE_COVARIATES_AML", "BASELINE_COVARIATES_CLL",
            "BASELINE_COVARIATES_BREAST", "BASELINE_COVARIATES_LUNG",
            "BASELINE_COVARIATES_GI", "BASELINE_COVARIATES_GU",
            "BASELINE_COVARIATES_GYN"
        ],
        "production_sap_specifications.py": [
            "ESTIMANDS_FRAMEWORK", "ADAM_SPECIFICATIONS", "MRD_SPECIFICATIONS"
        ],
        "regulatory_standards.py": [
            "ICH_E9_R1", "FDA_ONCOLOGY_ENDPOINTS", "EMA_ANTICANCER_GUIDELINE",
            "CTCAE_V5", "MEDDRA"
        ]
    }

    structures = file_structures.get(filename, [])
    return {s: KB_SOURCES.get(s, {}) for s in structures if s in KB_SOURCES}


def get_source_summary() -> dict:
    """Get summary statistics of source coverage."""
    total = len(KB_SOURCES)
    with_trials = sum(1 for v in KB_SOURCES.values() if v.get("trials"))
    with_regulatory = sum(1 for v in KB_SOURCES.values() if v.get("regulatory"))

    # Count unique trials
    all_trials = set()
    for v in KB_SOURCES.values():
        for t in v.get("trials", []):
            # Extract trial name from full title
            trial_name = t.split(":")[0].strip() if ":" in t else t.split("(")[0].strip()
            all_trials.add(trial_name)

    # Count unique regulatory docs
    all_regulatory = set()
    for v in KB_SOURCES.values():
        all_regulatory.update(v.get("regulatory", []))

    return {
        "total_structures": total,
        "with_trial_sources": with_trials,
        "with_regulatory_sources": with_regulatory,
        "unique_trials": len(all_trials),
        "unique_regulatory_docs": len(all_regulatory)
    }


if __name__ == "__main__":
    summary = get_source_summary()
    print("KB Source Mapping Summary - FULL SAP TITLES")
    print("=" * 60)
    print(f"Total structures mapped: {summary['total_structures']}")
    print(f"With trial sources: {summary['with_trial_sources']}")
    print(f"With regulatory sources: {summary['with_regulatory_sources']}")
    print(f"Unique trials referenced: {summary['unique_trials']}")
    print(f"Unique regulatory docs: {summary['unique_regulatory_docs']}")

    print("\n" + "=" * 60)
    print("Sample Source Lookup:")
    print("=" * 60)

    example = get_sources("CENSORING_RULES")
    print(f"\nCENSORING_RULES has {len(example.get('trials', []))} source trials:")
    for i, trial in enumerate(example.get("trials", [])[:3], 1):
        print(f"  {i}. {trial}")
    print(f"  ... and {len(example.get('trials', [])) - 3} more")
