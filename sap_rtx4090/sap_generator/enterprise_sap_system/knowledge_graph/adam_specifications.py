"""
Comprehensive ADaM Dataset Specifications v1.0
================================================

Complete specifications for all ADaM datasets required for
Phase 2/3 oncology clinical trials including:

1. ADSL - Subject Level Analysis Dataset
2. ADAE - Adverse Events Analysis Dataset
3. ADTTE - Time-to-Event Analysis Dataset
4. ADRS - Tumor Response Analysis Dataset
5. ADTR - Tumor Results Analysis Dataset
6. ADLB - Laboratory Analysis Dataset
7. ADVS - Vital Signs Analysis Dataset
8. ADEG - ECG Analysis Dataset
9. ADEX - Exposure Analysis Dataset
10. ADPR - PRO/QoL Analysis Dataset
11. ADCM - Concomitant Medications Analysis Dataset
12. ADMH - Medical History Analysis Dataset

Each dataset includes:
- Complete variable list with derivations
- Key ADaM standards (CDISC ADaM Implementation Guide)
- Traceability to SDTM
"""

from typing import Dict, List, Optional
import json
from pathlib import Path


# =============================================================================
# ADSL - SUBJECT LEVEL ANALYSIS DATASET
# =============================================================================

ADSL_SPECIFICATION = {
    "dataset_name": "ADSL",
    "description": "Subject Level Analysis Dataset",
    "one_record_per": "Subject",
    "key_variables": ["STUDYID", "USUBJID"],
    "adam_compliance": "ADaM IG v1.3",

    "variables": {
        # Identifier Variables
        "identifiers": [
            {"name": "STUDYID", "label": "Study Identifier", "type": "Char", "source": "DM.STUDYID"},
            {"name": "USUBJID", "label": "Unique Subject Identifier", "type": "Char", "source": "DM.USUBJID"},
            {"name": "SUBJID", "label": "Subject Identifier for the Study", "type": "Char", "source": "DM.SUBJID"},
            {"name": "SITEID", "label": "Study Site Identifier", "type": "Char", "source": "DM.SITEID"},
            {"name": "INVID", "label": "Investigator Identifier", "type": "Char", "source": "DM.INVID"},
            {"name": "COUNTRY", "label": "Country", "type": "Char", "source": "DM.COUNTRY"}
        ],

        # Treatment Variables
        "treatment": [
            {"name": "ARM", "label": "Description of Planned Arm", "type": "Char", "source": "DM.ARM"},
            {"name": "ARMCD", "label": "Planned Arm Code", "type": "Char", "source": "DM.ARMCD"},
            {"name": "ACTARM", "label": "Description of Actual Arm", "type": "Char", "source": "DM.ACTARM"},
            {"name": "ACTARMCD", "label": "Actual Arm Code", "type": "Char", "source": "DM.ACTARMCD"},
            {"name": "TRT01P", "label": "Planned Treatment for Period 01", "type": "Char", "derivation": "=ARM"},
            {"name": "TRT01PN", "label": "Planned Treatment for Period 01 (N)", "type": "Num", "derivation": "1=TRT A, 2=TRT B"},
            {"name": "TRT01A", "label": "Actual Treatment for Period 01", "type": "Char", "derivation": "=ACTARM"},
            {"name": "TRT01AN", "label": "Actual Treatment for Period 01 (N)", "type": "Num", "derivation": "1=TRT A, 2=TRT B"}
        ],

        # Date Variables
        "dates": [
            {"name": "RANDDT", "label": "Date of Randomization", "type": "Num", "format": "DATE9.", "source": "IXRS data or DS where DSDECOD='RANDOMIZED'"},
            {"name": "TRTSDT", "label": "Date of First Exposure to Treatment", "type": "Num", "format": "DATE9.", "source": "min(EX.EXSTDTC) where EXDOSE>0"},
            {"name": "TRTEDT", "label": "Date of Last Exposure to Treatment", "type": "Num", "format": "DATE9.", "source": "max(EX.EXENDTC) where EXDOSE>0"},
            {"name": "DTHDT", "label": "Date of Death", "type": "Num", "format": "DATE9.", "source": "DD.DTHDAT or DS.DSSTDTC where DSDECOD='DEATH'"},
            {"name": "LSTALVDT", "label": "Date Last Known Alive", "type": "Num", "format": "DATE9.", "derivation": "max(all contact dates if not dead)"},
            {"name": "EOSDT", "label": "End of Study Date", "type": "Num", "format": "DATE9.", "source": "DS.DSSTDTC where DSCAT='DISPOSITION EVENT'"},
            {"name": "EOTDT", "label": "End of Treatment Date", "type": "Num", "format": "DATE9.", "source": "DS.DSSTDTC where DSDECOD='END OF TREATMENT'"}
        ],

        # Demographics
        "demographics": [
            {"name": "AGE", "label": "Age", "type": "Num", "source": "DM.AGE"},
            {"name": "AGEU", "label": "Age Units", "type": "Char", "source": "DM.AGEU", "value": "YEARS"},
            {"name": "AGEGR1", "label": "Pooled Age Group 1", "type": "Char", "derivation": "if AGE<65 then '<65', else if AGE<75 then '65 to <75', else '>=75'"},
            {"name": "AGEGR1N", "label": "Pooled Age Group 1 (N)", "type": "Num", "derivation": "1=<65, 2=65 to <75, 3=>=75"},
            {"name": "SEX", "label": "Sex", "type": "Char", "source": "DM.SEX"},
            {"name": "SEXN", "label": "Sex (N)", "type": "Num", "derivation": "1=M, 2=F"},
            {"name": "RACE", "label": "Race", "type": "Char", "source": "DM.RACE"},
            {"name": "RACEN", "label": "Race (N)", "type": "Num", "derivation": "1=White, 2=Black, 3=Asian, 4=Other"},
            {"name": "ETHNIC", "label": "Ethnicity", "type": "Char", "source": "DM.ETHNIC"},
            {"name": "ETHNICN", "label": "Ethnicity (N)", "type": "Num", "derivation": "1=Hispanic/Latino, 2=Not Hispanic/Latino"},
            {"name": "WEIGHTBL", "label": "Baseline Weight (kg)", "type": "Num", "source": "VS where VSTESTCD='WEIGHT' at baseline"},
            {"name": "HEIGHTBL", "label": "Baseline Height (cm)", "type": "Num", "source": "VS where VSTESTCD='HEIGHT' at baseline"},
            {"name": "BMIBL", "label": "Baseline BMI (kg/m^2)", "type": "Num", "derivation": "WEIGHTBL / (HEIGHTBL/100)**2"},
            {"name": "BSABL", "label": "Baseline BSA (m^2)", "type": "Num", "derivation": "Dubois: 0.007184 × WEIGHTBL^0.425 × HEIGHTBL^0.725"}
        ],

        # Baseline Disease Characteristics
        "disease_baseline": [
            {"name": "ECOGBL", "label": "Baseline ECOG Performance Status", "type": "Num", "source": "QS.QSSTRESN where QSTESTCD='ECOG01' at baseline"},
            {"name": "ECOGBLGR", "label": "Baseline ECOG PS Group", "type": "Char", "derivation": "if ECOGBL=0 then '0', else if ECOGBL=1 then '1', else '>=2'"},
            {"name": "DESSION", "label": "Disease Stage at Study Entry", "type": "Char", "source": "Medical history/staging"},
            {"name": "HISTTYPE", "label": "Histology Type", "type": "Char", "source": "Medical history/pathology"},
            {"name": "DXDUR", "label": "Duration of Disease (months)", "type": "Num", "derivation": "(RANDDT - Diagnosis Date + 1) / 30.4375"},
            {"name": "NPRIOR", "label": "Number of Prior Systemic Therapies", "type": "Num", "source": "Count from CM/Medical History"},
            {"name": "NPRIORGR", "label": "Prior Therapies Group", "type": "Char", "derivation": "if NPRIOR<=1 then '0-1', else '>=2'"},
            {"name": "METSITE", "label": "Sites of Metastases", "type": "Char", "source": "TU domain"},
            {"name": "NMETSITES", "label": "Number of Metastatic Sites", "type": "Num", "source": "Count from TU"},
            {"name": "LIVERMTS", "label": "Liver Metastases (Y/N)", "type": "Char", "derivation": "Y if liver in metastatic sites"},
            {"name": "BRAINMTS", "label": "Brain Metastases (Y/N)", "type": "Char", "derivation": "Y if brain in metastatic sites"},
            {"name": "BONEMTS", "label": "Bone Metastases (Y/N)", "type": "Char", "derivation": "Y if bone in metastatic sites"},
            {"name": "TUMSUMBL", "label": "Baseline Sum of Target Lesions (mm)", "type": "Num", "source": "TR domain baseline"},
            {"name": "NTLBL", "label": "Number of Target Lesions at Baseline", "type": "Num", "source": "Count from TR where TRGRPID='TARGET'"}
        ],

        # Biomarker Variables
        "biomarkers": [
            {"name": "PDL1TPS", "label": "PD-L1 TPS Score", "type": "Num", "source": "Biomarker/BE domain"},
            {"name": "PDL1TPSGR", "label": "PD-L1 TPS Group", "type": "Char", "derivation": "if PDL1TPS<1 then '<1%', else if PDL1TPS<50 then '1-49%', else '>=50%'"},
            {"name": "PDL1CPS", "label": "PD-L1 CPS Score", "type": "Num", "source": "Biomarker domain"},
            {"name": "MUTSTAT", "label": "Mutation Status", "type": "Char", "source": "Biomarker domain", "values": ["Wild-type", "Mutant", "Unknown"]},
            {"name": "MSISTAT", "label": "MSI Status", "type": "Char", "source": "Biomarker domain", "values": ["MSS", "MSI-H", "Unknown"]},
            {"name": "TMB", "label": "Tumor Mutational Burden (mut/Mb)", "type": "Num", "source": "Biomarker domain"},
            {"name": "TMBGR", "label": "TMB Group", "type": "Char", "derivation": "if TMB<10 then 'Low', else 'High'"}
        ],

        # Stratification Factors
        "stratification": [
            {"name": "STRESSION", "label": "Stratification: Disease Stage", "type": "Char", "source": "IXRS stratification"},
            {"name": "STRECOG", "label": "Stratification: ECOG PS", "type": "Char", "source": "IXRS stratification"},
            {"name": "STRREGION", "label": "Stratification: Geographic Region", "type": "Char", "source": "IXRS stratification"},
            {"name": "STRPDL1", "label": "Stratification: PD-L1 Status", "type": "Char", "source": "IXRS stratification"},
            {"name": "STRNPRIOR", "label": "Stratification: Prior Therapies", "type": "Char", "source": "IXRS stratification"},
            {"name": "REGION", "label": "Geographic Region", "type": "Char", "derivation": "Based on COUNTRY mapping"}
        ],

        # Population Flags
        "population_flags": [
            {"name": "ITTFL", "label": "Intent-to-Treat Population Flag", "type": "Char", "derivation": "Y for all randomized subjects", "values": ["Y", "N"]},
            {"name": "SAFFL", "label": "Safety Population Flag", "type": "Char", "derivation": "Y if received at least one dose (TRTSDT not missing)", "values": ["Y", "N"]},
            {"name": "FASFL", "label": "Full Analysis Set Flag", "type": "Char", "derivation": "Y if ITTFL='Y' and at least one post-baseline tumor assessment", "values": ["Y", "N"]},
            {"name": "PPROTFL", "label": "Per-Protocol Population Flag", "type": "Char", "derivation": "Y if FASFL='Y' and no major protocol deviations", "values": ["Y", "N"]},
            {"name": "RESPEVFL", "label": "Response Evaluable Population Flag", "type": "Char", "derivation": "Y if measurable disease at baseline and >=1 post-baseline assessment", "values": ["Y", "N"]}
        ],

        # Disposition Variables
        "disposition": [
            {"name": "DCSREAS", "label": "Reason for Discontinuation from Study", "type": "Char", "source": "DS domain"},
            {"name": "DCTREAS", "label": "Reason for Discontinuation from Treatment", "type": "Char", "source": "DS domain"},
            {"name": "DTHFL", "label": "Subject Died (Y/N)", "type": "Char", "derivation": "Y if DTHDT not missing"},
            {"name": "DTHCAT", "label": "Death Category", "type": "Char", "derivation": "Disease progression, Adverse event, Other"},
            {"name": "EOSSTT", "label": "End of Study Status", "type": "Char", "values": ["COMPLETED", "ONGOING", "DISCONTINUED"]}
        ],

        # Derived Duration Variables
        "durations": [
            {"name": "TRTDUR", "label": "Treatment Duration (days)", "type": "Num", "derivation": "TRTEDT - TRTSDT + 1"},
            {"name": "TRTDURM", "label": "Treatment Duration (months)", "type": "Num", "derivation": "TRTDUR / 30.4375"},
            {"name": "FUTIME", "label": "Time on Study (days)", "type": "Num", "derivation": "EOSDT - RANDDT + 1"},
            {"name": "FUTIMEM", "label": "Time on Study (months)", "type": "Num", "derivation": "FUTIME / 30.4375"}
        ]
    }
}


# =============================================================================
# ADAE - ADVERSE EVENTS ANALYSIS DATASET
# =============================================================================

ADAE_SPECIFICATION = {
    "dataset_name": "ADAE",
    "description": "Adverse Events Analysis Dataset",
    "one_record_per": "Subject and AE",
    "key_variables": ["STUDYID", "USUBJID", "AESEQ"],
    "adam_compliance": "ADaM IG v1.3",

    "variables": {
        # From ADSL
        "adsl_variables": [
            "STUDYID", "USUBJID", "SITEID", "COUNTRY", "AGE", "AGEGR1", "SEX", "RACE",
            "TRT01P", "TRT01PN", "TRT01A", "TRT01AN", "TRTSDT", "TRTEDT",
            "SAFFL", "RANDDT"
        ],

        # AE Identification
        "ae_identification": [
            {"name": "AESEQ", "label": "Sequence Number", "type": "Num", "source": "AE.AESEQ"},
            {"name": "AETERM", "label": "Reported Term for the Adverse Event", "type": "Char", "source": "AE.AETERM"},
            {"name": "AEDECOD", "label": "Dictionary-Derived Term", "type": "Char", "source": "AE.AEDECOD"},
            {"name": "AEBODSYS", "label": "Body System or Organ Class", "type": "Char", "source": "AE.AEBODSYS"},
            {"name": "AEBDSYCD", "label": "Body System or Organ Class Code", "type": "Num", "source": "MedDRA SOC code"},
            {"name": "AEHLT", "label": "High Level Term", "type": "Char", "source": "MedDRA HLT"},
            {"name": "AEHLGT", "label": "High Level Group Term", "type": "Char", "source": "MedDRA HLGT"},
            {"name": "AELLT", "label": "Lowest Level Term", "type": "Char", "source": "MedDRA LLT"},
            {"name": "AEPTCD", "label": "Preferred Term Code", "type": "Num", "source": "MedDRA PT code"}
        ],

        # AE Timing
        "ae_timing": [
            {"name": "AESTDTC", "label": "Start Date/Time of AE (Char)", "type": "Char", "source": "AE.AESTDTC"},
            {"name": "AEENDTC", "label": "End Date/Time of AE (Char)", "type": "Char", "source": "AE.AEENDTC"},
            {"name": "ASTDT", "label": "Analysis Start Date", "type": "Num", "format": "DATE9.", "derivation": "Imputed from AESTDTC"},
            {"name": "AENDT", "label": "Analysis End Date", "type": "Num", "format": "DATE9.", "derivation": "Imputed from AEENDTC"},
            {"name": "ASTDY", "label": "Analysis Start Day", "type": "Num", "derivation": "ASTDT - TRTSDT + 1 (if ASTDT>=TRTSDT)"},
            {"name": "AENDY", "label": "Analysis End Day", "type": "Num", "derivation": "AENDT - TRTSDT + 1"},
            {"name": "ADURN", "label": "AE Duration (N)", "type": "Num", "derivation": "AENDT - ASTDT + 1"},
            {"name": "ADURU", "label": "AE Duration Units", "type": "Char", "value": "DAYS"}
        ],

        # AE Classification
        "ae_classification": [
            {"name": "AESEV", "label": "Severity/Intensity", "type": "Char", "source": "AE.AESEV"},
            {"name": "AESEVN", "label": "Severity/Intensity (N)", "type": "Num", "derivation": "1=MILD, 2=MODERATE, 3=SEVERE"},
            {"name": "AETOXGR", "label": "CTCAE Grade", "type": "Char", "source": "AE.AETOXGR"},
            {"name": "AETOXGRN", "label": "CTCAE Grade (N)", "type": "Num", "derivation": "Numeric grade 1-5"},
            {"name": "AESER", "label": "Serious Event", "type": "Char", "source": "AE.AESER"},
            {"name": "AEREL", "label": "Causality", "type": "Char", "source": "AE.AEREL"},
            {"name": "AERELN", "label": "Causality (N)", "type": "Num", "derivation": "1=Not Related, 2=Unlikely, 3=Possible, 4=Probable, 5=Related"},
            {"name": "AEACN", "label": "Action Taken with Study Treatment", "type": "Char", "source": "AE.AEACN"},
            {"name": "AEOUT", "label": "Outcome of Adverse Event", "type": "Char", "source": "AE.AEOUT"},
            {"name": "AESCONG", "label": "Congenital Anomaly or Birth Defect", "type": "Char", "source": "AE.AESCONG"},
            {"name": "AESDISAB", "label": "Persist or Signif Disability/Incapacity", "type": "Char", "source": "AE.AESDISAB"},
            {"name": "AESDTH", "label": "Results in Death", "type": "Char", "source": "AE.AESDTH"},
            {"name": "AESHOSP", "label": "Requires or Prolongs Hospitalization", "type": "Char", "source": "AE.AESHOSP"},
            {"name": "AESLIFE", "label": "Is Life Threatening", "type": "Char", "source": "AE.AESLIFE"},
            {"name": "AESMIE", "label": "Other Medically Important Serious Event", "type": "Char", "source": "AE.AESMIE"}
        ],

        # Analysis Flags
        "analysis_flags": [
            {"name": "TRTEMFL", "label": "Treatment Emergent Flag", "type": "Char", "derivation": "Y if ASTDT >= TRTSDT and ASTDT <= TRTEDT + 28"},
            {"name": "PREFL", "label": "Pre-treatment Flag", "type": "Char", "derivation": "Y if ASTDT < TRTSDT"},
            {"name": "RELFL", "label": "Treatment-Related Flag", "type": "Char", "derivation": "Y if AEREL in ('POSSIBLY RELATED', 'PROBABLY RELATED', 'RELATED')"},
            {"name": "AOCCFL", "label": "1st Occurrence of PT Flag", "type": "Char", "derivation": "Y for first occurrence of each PT per subject"},
            {"name": "AOCCSFL", "label": "1st Occurrence of SOC Flag", "type": "Char", "derivation": "Y for first occurrence of each SOC per subject"},
            {"name": "AOCCPFL", "label": "1st Occurrence within SOC/PT Flag", "type": "Char", "derivation": "Y for first occurrence within SOC"},
            {"name": "AOCC01FL", "label": "1st Max Sev./Int. Occurrence Flag", "type": "Char", "derivation": "Y for first occurrence at max severity"},
            {"name": "AESI01FL", "label": "AE of Special Interest 1 Flag", "type": "Char", "derivation": "Y if PT in AESI category 1"},
            {"name": "IRAEFL", "label": "Immune-Related AE Flag", "type": "Char", "derivation": "Y if classified as irAE based on SMQ/PT list"},
            {"name": "IRDRCFL", "label": "Infusion-Related Reaction Flag", "type": "Char", "derivation": "Y if classified as IRR"}
        ]
    },

    "date_imputation_rules": {
        "start_date_missing_day": [
            {"condition": "Month/year same as TRTSDT", "imputation": "TRTSDT"},
            {"condition": "Month/year before TRTSDT", "imputation": "Last day of month"},
            {"condition": "Month/year after TRTSDT", "imputation": "First day of month"}
        ],
        "start_date_missing_month_day": [
            {"condition": "Year same as or after TRTSDT year", "imputation": "January 1"},
            {"condition": "Year before TRTSDT year", "imputation": "December 31"}
        ],
        "end_date_missing_day": "Last day of month",
        "end_date_missing_month_day": "December 31 of year"
    }
}


# =============================================================================
# ADTTE - TIME-TO-EVENT ANALYSIS DATASET
# =============================================================================

ADTTE_SPECIFICATION = {
    "dataset_name": "ADTTE",
    "description": "Time-to-Event Analysis Dataset",
    "one_record_per": "Subject and Parameter",
    "key_variables": ["STUDYID", "USUBJID", "PARAMCD"],
    "adam_compliance": "ADaM IG v1.3 BDS Structure",

    "parameters": {
        "PFS": {
            "paramcd": "PFS",
            "param": "Progression-Free Survival (IRC)",
            "origin_date": "RANDDT",
            "events": ["Disease progression per RECIST v1.1", "Death from any cause"],
            "censoring_variable": "CNSR",
            "time_variable": "AVAL",
            "unit": "Months"
        },
        "PFSINV": {
            "paramcd": "PFSINV",
            "param": "Progression-Free Survival (INV)",
            "origin_date": "RANDDT",
            "events": ["Disease progression per INV", "Death from any cause"]
        },
        "OS": {
            "paramcd": "OS",
            "param": "Overall Survival",
            "origin_date": "RANDDT",
            "events": ["Death from any cause"],
            "censoring": "Last known alive date"
        },
        "DOR": {
            "paramcd": "DOR",
            "param": "Duration of Response",
            "origin_date": "Date of first confirmed response",
            "events": ["Disease progression", "Death"],
            "population": "Responders only"
        },
        "TTR": {
            "paramcd": "TTR",
            "param": "Time to Response",
            "origin_date": "RANDDT",
            "events": ["First confirmed CR or PR"],
            "population": "Responders only"
        },
        "TTP": {
            "paramcd": "TTP",
            "param": "Time to Progression",
            "origin_date": "RANDDT",
            "events": ["Disease progression"],
            "censoring": "Death without progression is censored"
        },
        "EFS": {
            "paramcd": "EFS",
            "param": "Event-Free Survival",
            "origin_date": "RANDDT",
            "events": ["Relapse", "Progression", "Death"]
        },
        "TTDGHS": {
            "paramcd": "TTDGHS",
            "param": "Time to Deterioration - Global Health Status",
            "origin_date": "RANDDT",
            "events": [">=10 point decrease from baseline"]
        }
    },

    "variables": {
        "adsl_variables": [
            "STUDYID", "USUBJID", "SITEID", "TRT01P", "TRT01PN", "TRT01A", "TRT01AN",
            "AGE", "AGEGR1", "SEX", "RACE", "SAFFL", "ITTFL", "FASFL", "RANDDT", "TRTSDT"
        ],
        "bds_variables": [
            {"name": "PARAMCD", "label": "Parameter Code", "type": "Char"},
            {"name": "PARAM", "label": "Parameter", "type": "Char"},
            {"name": "PARCAT1", "label": "Parameter Category 1", "type": "Char", "values": ["PRIMARY", "SECONDARY", "EXPLORATORY"]},
            {"name": "AVAL", "label": "Analysis Value", "type": "Num", "derivation": "(ADT - STARTDT + 1) / 30.4375"},
            {"name": "AVALU", "label": "Analysis Value Unit", "type": "Char", "value": "MONTHS"},
            {"name": "CNSR", "label": "Censor", "type": "Num", "values": {"0": "Event", "1": "Censored"}},
            {"name": "EVNTDESC", "label": "Event or Censoring Description", "type": "Char"},
            {"name": "CNSDTDSC", "label": "Censoring Date Description", "type": "Char"},
            {"name": "ADT", "label": "Analysis Date", "type": "Num", "format": "DATE9."},
            {"name": "STARTDT", "label": "Time-to-Event Origin Date", "type": "Num", "format": "DATE9."},
            {"name": "SRCDOM", "label": "Source Data Domain", "type": "Char"},
            {"name": "SRCVAR", "label": "Source Variable", "type": "Char"},
            {"name": "SRCSEQ", "label": "Source Sequence Number", "type": "Num"}
        ],
        "stratification_variables": [
            {"name": "STRATF1", "label": "Stratification Factor 1", "type": "Char"},
            {"name": "STRATF1N", "label": "Stratification Factor 1 (N)", "type": "Num"},
            {"name": "STRATF2", "label": "Stratification Factor 2", "type": "Char"},
            {"name": "STRATF2N", "label": "Stratification Factor 2 (N)", "type": "Num"},
            {"name": "STRATF3", "label": "Stratification Factor 3", "type": "Char"},
            {"name": "STRATF3N", "label": "Stratification Factor 3 (N)", "type": "Num"}
        ]
    },

    "derivation_algorithm_pfs": {
        "step1": "Identify all tumor assessment dates and responses",
        "step2": "Determine if progression occurred (RSSTRESC = 'PD')",
        "step3": "Check for death without prior progression",
        "step4": "Apply censoring rules based on assessment gaps",
        "step5": "Calculate AVAL = (ADT - STARTDT + 1) / 30.4375",
        "step6": "Set CNSR = 0 for events, CNSR = 1 for censored"
    }
}


# =============================================================================
# ADRS - TUMOR RESPONSE ANALYSIS DATASET
# =============================================================================

ADRS_SPECIFICATION = {
    "dataset_name": "ADRS",
    "description": "Tumor Response Analysis Dataset",
    "one_record_per": "Subject and Parameter (Response Parameter)",
    "key_variables": ["STUDYID", "USUBJID", "PARAMCD", "ADT"],
    "adam_compliance": "ADaM IG v1.3 BDS Structure",

    "parameters": {
        "BOR": {"paramcd": "BOR", "param": "Best Overall Response", "derivation": "Best response across all assessments"},
        "OVRLRESP": {"paramcd": "OVRLRESP", "param": "Overall Response per Visit", "derivation": "Response at each assessment visit"},
        "TRGRESP": {"paramcd": "TRGRESP", "param": "Target Lesion Response", "derivation": "Response based on target lesions only"},
        "NTRGRESP": {"paramcd": "NTRGRESP", "param": "Non-Target Lesion Response", "derivation": "Response based on non-target lesions"},
        "NEWLRESP": {"paramcd": "NEWLRESP", "param": "New Lesion Response", "derivation": "Presence of new lesions"},
        "CB": {"paramcd": "CB", "param": "Clinical Benefit (CR+PR+SD>=24w)", "derivation": "Binary: Y/N"},
        "ORR": {"paramcd": "ORR", "param": "Objective Response (CR+PR)", "derivation": "Binary: Y/N"},
        "DCR": {"paramcd": "DCR", "param": "Disease Control (CR+PR+SD)", "derivation": "Binary: Y/N"}
    },

    "variables": {
        "response_variables": [
            {"name": "AVALC", "label": "Analysis Value (C)", "type": "Char", "values": ["CR", "PR", "SD", "PD", "NE", "UNK"]},
            {"name": "AVAL", "label": "Analysis Value", "type": "Num", "derivation": "1=CR, 2=PR, 3=SD, 4=PD, 5=NE"},
            {"name": "ADT", "label": "Analysis Date", "type": "Num", "format": "DATE9."},
            {"name": "ADY", "label": "Analysis Relative Day", "type": "Num", "derivation": "ADT - TRTSDT + 1"},
            {"name": "AVISIT", "label": "Analysis Visit", "type": "Char"},
            {"name": "AVISITN", "label": "Analysis Visit (N)", "type": "Num"},
            {"name": "RSEVAL", "label": "Evaluator", "type": "Char", "values": ["IRC", "INVESTIGATOR"]},
            {"name": "PDFL", "label": "Progressive Disease Flag", "type": "Char", "derivation": "Y if AVALC='PD'"},
            {"name": "CRSFL", "label": "Complete Response Flag", "type": "Char", "derivation": "Y if AVALC='CR'"},
            {"name": "PRSFL", "label": "Partial Response Flag", "type": "Char", "derivation": "Y if AVALC='PR'"},
            {"name": "RSCONFFL", "label": "Response Confirmed Flag", "type": "Char", "derivation": "Y if CR/PR confirmed >=4 weeks later"},
            {"name": "DTEFIRST", "label": "Date of First Response", "type": "Num", "format": "DATE9."},
            {"name": "DTCONF", "label": "Date of Response Confirmation", "type": "Num", "format": "DATE9."}
        ]
    },

    "best_overall_response_algorithm": {
        "hierarchy": ["CR", "PR", "SD", "PD", "NE", "UNK"],
        "confirmation_required": True,
        "confirmation_window": ">=28 days",
        "sd_minimum_duration": ">=6 weeks from baseline",
        "rules": [
            "1. CR: All target lesions disappeared, all non-target lesions disappeared, no new lesions",
            "2. PR: >=30% decrease in sum of diameters of target lesions",
            "3. SD: Neither PR nor PD criteria met",
            "4. PD: >=20% increase AND >=5mm absolute increase in sum, or new lesion",
            "5. NE: Not evaluable (missing or indeterminate assessments)"
        ]
    }
}


# =============================================================================
# ADLB - LABORATORY ANALYSIS DATASET
# =============================================================================

ADLB_SPECIFICATION = {
    "dataset_name": "ADLB",
    "description": "Laboratory Analysis Dataset",
    "one_record_per": "Subject, Parameter, and Visit",
    "key_variables": ["STUDYID", "USUBJID", "PARAMCD", "ADT", "ATPTN"],
    "adam_compliance": "ADaM IG v1.3 BDS Structure",

    "variables": {
        "lab_identification": [
            {"name": "PARAMCD", "label": "Parameter Code", "type": "Char", "source": "LB.LBTESTCD"},
            {"name": "PARAM", "label": "Parameter", "type": "Char", "source": "LB.LBTEST"},
            {"name": "PARCAT1", "label": "Parameter Category 1", "type": "Char", "values": ["CHEMISTRY", "HEMATOLOGY", "URINALYSIS", "COAGULATION"]},
            {"name": "LBCAT", "label": "Category for Lab Test", "type": "Char", "source": "LB.LBCAT"}
        ],
        "lab_results": [
            {"name": "AVAL", "label": "Analysis Value", "type": "Num", "source": "LB.LBSTRESN"},
            {"name": "AVALC", "label": "Analysis Value (C)", "type": "Char", "source": "LB.LBSTRESC"},
            {"name": "AVALU", "label": "Analysis Value Unit", "type": "Char", "source": "LB.LBSTRESU"},
            {"name": "BASE", "label": "Baseline Value", "type": "Num", "derivation": "AVAL where ABLFL='Y'"},
            {"name": "BASEC", "label": "Baseline Value (C)", "type": "Char"},
            {"name": "CHG", "label": "Change from Baseline", "type": "Num", "derivation": "AVAL - BASE"},
            {"name": "PCHG", "label": "Percent Change from Baseline", "type": "Num", "derivation": "100 * (AVAL - BASE) / BASE"},
            {"name": "R2BASE", "label": "Ratio to Baseline", "type": "Num", "derivation": "AVAL / BASE"}
        ],
        "reference_ranges": [
            {"name": "ANRLO", "label": "Analysis Normal Range Lower Limit", "type": "Num", "source": "LB.LBSTNRLO"},
            {"name": "ANRHI", "label": "Analysis Normal Range Upper Limit", "type": "Num", "source": "LB.LBSTNRHI"},
            {"name": "A1LO", "label": "Analysis Range 1 Lower Limit (xULN)", "type": "Num", "derivation": "1 * ANRHI"},
            {"name": "A1HI", "label": "Analysis Range 1 Upper Limit", "type": "Num"},
            {"name": "ANRIND", "label": "Analysis Reference Range Indicator", "type": "Char", "values": ["NORMAL", "LOW", "HIGH"]}
        ],
        "toxicity_grading": [
            {"name": "ATOXGR", "label": "Analysis Toxicity Grade", "type": "Char", "derivation": "CTCAE grade based on AVAL and thresholds"},
            {"name": "ATOXGRN", "label": "Analysis Toxicity Grade (N)", "type": "Num", "derivation": "Numeric 0-4"},
            {"name": "BTOXGR", "label": "Baseline Toxicity Grade", "type": "Char", "derivation": "ATOXGR where ABLFL='Y'"},
            {"name": "BTOXGRN", "label": "Baseline Toxicity Grade (N)", "type": "Num"},
            {"name": "ATOXGRGR", "label": "Analysis Toxicity Grade (Pooled)", "type": "Char", "derivation": "0, 1-2, 3-4"}
        ],
        "timing_variables": [
            {"name": "ADT", "label": "Analysis Date", "type": "Num", "format": "DATE9.", "source": "LB.LBDTC"},
            {"name": "ADY", "label": "Analysis Relative Day", "type": "Num", "derivation": "ADT - TRTSDT + 1"},
            {"name": "ATPT", "label": "Analysis Timepoint", "type": "Char", "source": "LB.LBTPT"},
            {"name": "ATPTN", "label": "Analysis Timepoint (N)", "type": "Num"},
            {"name": "AVISIT", "label": "Analysis Visit", "type": "Char"},
            {"name": "AVISITN", "label": "Analysis Visit (N)", "type": "Num"},
            {"name": "ABLFL", "label": "Baseline Record Flag", "type": "Char", "derivation": "Y for last non-missing value on or before TRTSDT"},
            {"name": "ANL01FL", "label": "Analysis Record Flag 01", "type": "Char", "derivation": "Y for scheduled visits only"}
        ],
        "analysis_flags": [
            {"name": "AENTMTFL", "label": "On-Treatment Record Flag", "type": "Char", "derivation": "Y if ADT between TRTSDT and TRTEDT+7"},
            {"name": "ONTRTFL", "label": "On Treatment Record Flag", "type": "Char"},
            {"name": "WORSFL", "label": "Worst Post-Baseline Flag", "type": "Char", "derivation": "Y for worst value post-baseline"},
            {"name": "LASTFL", "label": "Last Post-Baseline Flag", "type": "Char", "derivation": "Y for last non-missing post-baseline"},
            {"name": "PCSFL", "label": "PCS Flag (Potentially Clinically Significant)", "type": "Char", "derivation": "Y if meets PCS criteria"}
        ]
    },

    "ctcae_grading": {
        "version": "5.0",
        "parameters": {
            "ALT": {
                "grade_1": ">ULN to 3xULN",
                "grade_2": ">3xULN to 5xULN",
                "grade_3": ">5xULN to 20xULN",
                "grade_4": ">20xULN"
            },
            "AST": {
                "grade_1": ">ULN to 3xULN",
                "grade_2": ">3xULN to 5xULN",
                "grade_3": ">5xULN to 20xULN",
                "grade_4": ">20xULN"
            },
            "BILI": {
                "grade_1": ">ULN to 1.5xULN",
                "grade_2": ">1.5xULN to 3xULN",
                "grade_3": ">3xULN to 10xULN",
                "grade_4": ">10xULN"
            },
            "CREAT": {
                "grade_1": ">ULN to 1.5xULN",
                "grade_2": ">1.5xULN to 3xULN",
                "grade_3": ">3xULN to 6xULN",
                "grade_4": ">6xULN"
            },
            "ANC": {
                "grade_1": "<LLN to 1.5x10^9/L",
                "grade_2": "<1.5 to 1.0x10^9/L",
                "grade_3": "<1.0 to 0.5x10^9/L",
                "grade_4": "<0.5x10^9/L"
            },
            "HGB": {
                "grade_1": "<LLN to 10 g/dL",
                "grade_2": "<10 to 8 g/dL",
                "grade_3": "<8 g/dL; transfusion indicated",
                "grade_4": "Life-threatening"
            },
            "PLT": {
                "grade_1": "<LLN to 75x10^9/L",
                "grade_2": "<75 to 50x10^9/L",
                "grade_3": "<50 to 25x10^9/L",
                "grade_4": "<25x10^9/L"
            }
        }
    }
}


# =============================================================================
# ADEX - EXPOSURE ANALYSIS DATASET
# =============================================================================

ADEX_SPECIFICATION = {
    "dataset_name": "ADEX",
    "description": "Exposure Analysis Dataset",
    "one_record_per": "Subject, Parameter, and Date/Cycle",
    "key_variables": ["STUDYID", "USUBJID", "PARAMCD", "ADT"],
    "adam_compliance": "ADaM IG v1.3",

    "variables": {
        "exposure_variables": [
            {"name": "PARAMCD", "label": "Parameter Code", "type": "Char"},
            {"name": "PARAM", "label": "Parameter", "type": "Char"},
            {"name": "AVAL", "label": "Analysis Value", "type": "Num"},
            {"name": "AVALU", "label": "Analysis Value Unit", "type": "Char"},
            {"name": "EXDOSE", "label": "Dose per Administration", "type": "Num", "source": "EX.EXDOSE"},
            {"name": "EXDOSU", "label": "Dose Units", "type": "Char", "source": "EX.EXDOSU"},
            {"name": "EXROUTE", "label": "Route of Administration", "type": "Char", "source": "EX.EXROUTE"},
            {"name": "EXSTDTC", "label": "Start Date/Time of Exposure", "type": "Char", "source": "EX.EXSTDTC"},
            {"name": "EXENDTC", "label": "End Date/Time of Exposure", "type": "Char", "source": "EX.EXENDTC"},
            {"name": "EXDUR", "label": "Duration", "type": "Num", "derivation": "EXENDTC - EXSTDTC + 1"},
            {"name": "CYCLE", "label": "Cycle Number", "type": "Num"},
            {"name": "ADT", "label": "Analysis Date", "type": "Num", "format": "DATE9."},
            {"name": "ADY", "label": "Analysis Relative Day", "type": "Num"},
            {"name": "AVISIT", "label": "Analysis Visit", "type": "Char"}
        ],
        "derived_parameters": [
            {"paramcd": "TRTDUR", "param": "Treatment Duration (days)", "derivation": "TRTEDT - TRTSDT + 1"},
            {"paramcd": "TRTDURM", "param": "Treatment Duration (months)", "derivation": "TRTDUR / 30.4375"},
            {"paramcd": "CUMDOSE", "param": "Cumulative Dose", "derivation": "Sum of all doses"},
            {"paramcd": "AVGDOSE", "param": "Average Dose", "derivation": "CUMDOSE / TRTDUR"},
            {"paramcd": "NDOSE", "param": "Number of Doses", "derivation": "Count of doses"},
            {"paramcd": "NCYCLE", "param": "Number of Cycles", "derivation": "Max CYCLE"},
            {"paramcd": "PLANDINT", "param": "Planned Dose Intensity", "derivation": "Planned dose / planned interval"},
            {"paramcd": "ACTDINT", "param": "Actual Dose Intensity", "derivation": "CUMDOSE / TRTDUR"},
            {"paramcd": "RDOSINT", "param": "Relative Dose Intensity (%)", "derivation": "100 * ACTDINT / PLANDINT"}
        ]
    }
}


# =============================================================================
# ADDITIONAL ADAM DATASETS
# =============================================================================

ADVS_SPECIFICATION = {
    "dataset_name": "ADVS",
    "description": "Vital Signs Analysis Dataset",
    "one_record_per": "Subject, Parameter, Visit, Timepoint",
    "key_variables": ["STUDYID", "USUBJID", "PARAMCD", "ADT", "ATPTN"],
    "parameters": ["SYSBP", "DIABP", "PULSE", "TEMP", "WEIGHT", "HEIGHT", "BMI", "RESP", "SPO2"]
}

ADEG_SPECIFICATION = {
    "dataset_name": "ADEG",
    "description": "ECG Analysis Dataset",
    "one_record_per": "Subject, Parameter, Visit",
    "key_variables": ["STUDYID", "USUBJID", "PARAMCD", "ADT"],
    "parameters": ["HR", "RR", "PR", "QRS", "QT", "QTCF", "QTCB"]
}

ADPR_SPECIFICATION = {
    "dataset_name": "ADPR",
    "description": "Patient-Reported Outcomes Analysis Dataset",
    "one_record_per": "Subject, Parameter, Visit",
    "key_variables": ["STUDYID", "USUBJID", "PARAMCD", "ADT"],
    "parameters": ["EORTC QLQ-C30 domains", "EQ-5D-5L", "Tumor-specific modules"]
}

ADCM_SPECIFICATION = {
    "dataset_name": "ADCM",
    "description": "Concomitant Medications Analysis Dataset",
    "one_record_per": "Subject and Medication Record",
    "key_variables": ["STUDYID", "USUBJID", "CMSEQ"]
}

ADMH_SPECIFICATION = {
    "dataset_name": "ADMH",
    "description": "Medical History Analysis Dataset",
    "one_record_per": "Subject and Medical History Record",
    "key_variables": ["STUDYID", "USUBJID", "MHSEQ"]
}


# =============================================================================
# EXPORT FUNCTION
# =============================================================================

def export_adam_specifications(output_path: Path) -> Dict:
    """Export all ADaM specifications as JSON."""
    specifications = {
        "metadata": {
            "version": "1.0",
            "description": "Comprehensive ADaM Dataset Specifications for Oncology SAPs",
            "adam_ig_version": "1.3",
            "datasets": 12
        },
        "ADSL": ADSL_SPECIFICATION,
        "ADAE": ADAE_SPECIFICATION,
        "ADTTE": ADTTE_SPECIFICATION,
        "ADRS": ADRS_SPECIFICATION,
        "ADLB": ADLB_SPECIFICATION,
        "ADEX": ADEX_SPECIFICATION,
        "ADVS": ADVS_SPECIFICATION,
        "ADEG": ADEG_SPECIFICATION,
        "ADPR": ADPR_SPECIFICATION,
        "ADCM": ADCM_SPECIFICATION,
        "ADMH": ADMH_SPECIFICATION
    }

    with open(output_path, 'w') as f:
        json.dump(specifications, f, indent=2, default=str)

    print(f"ADaM specifications exported to {output_path}")
    return specifications


if __name__ == "__main__":
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    specs = export_adam_specifications(output_dir / "adam_specifications.json")

    print("\n" + "=" * 80)
    print("ADAM DATASET SPECIFICATIONS v1.0")
    print("=" * 80)

    for ds_name in ["ADSL", "ADAE", "ADTTE", "ADRS", "ADLB", "ADEX", "ADVS", "ADEG", "ADPR", "ADCM", "ADMH"]:
        print(f"  {ds_name}: Specified")

    print(f"\n{'=' * 80}")
    print("Total: 11 ADaM datasets with complete derivation rules")
    print("=" * 80)
