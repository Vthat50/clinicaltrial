"""
Oncology Reference Data for Knowledge Graph v1.0
=================================================

Comprehensive reference data to reach 80%+ oncology trial coverage.

Contains:
1. Response Criteria (PCWG3, IMWG, GCIG, CML, CLL)
2. Study Type Templates (Adjuvant, Neoadjuvant, Basket, Umbrella, Phase 1)
3. Emerging Therapy Modules (CAR-T, Bispecifics, ADCs)
4. Biomarker Endpoints
5. Missing Baseline Variables
6. TFL Templates
"""

# =============================================================================
# 1. RESPONSE CRITERIA
# =============================================================================

PCWG3_CRITERIA = {
    "name": "PCWG3",
    "full_name": "Prostate Cancer Working Group 3",
    "indication": "Prostate Cancer",
    "version": "2016",
    "response_categories": {
        "PSA_response": {
            "definition": "≥50% decline from baseline, confirmed ≥3 weeks later",
            "categories": ["PSA response", "No PSA response"]
        },
        "PSA_progression": {
            "definition": "≥25% increase and ≥2 ng/mL above nadir (confirmed)",
            "requires_confirmation": True,
            "minimum_timepoint": "12 weeks"
        },
        "soft_tissue_response": {
            "assessment": "RECIST 1.1",
            "categories": ["CR", "PR", "SD", "PD"]
        },
        "bone_response": {
            "assessment": "Bone scan",
            "progression": "≥2 new lesions confirmed on subsequent scan",
            "flare_exclusion": "First scan at 8-9 weeks may show flare"
        }
    },
    "endpoints": [
        {"name": "rPFS", "definition": "Radiographic progression-free survival"},
        {"name": "PSA-PFS", "definition": "PSA progression-free survival"},
        {"name": "Time to PSA progression", "definition": "Time from randomization to PSA progression"},
        {"name": "PSA response rate", "definition": "Proportion with ≥50% PSA decline"},
        {"name": "Time to first SRE", "definition": "Time to first skeletal-related event"}
    ],
    "baseline_variables": [
        {"name": "Baseline PSA", "unit": "ng/mL"},
        {"name": "Gleason score", "categories": ["≤6", "7", "8-10"]},
        {"name": "Prior docetaxel", "categories": ["Yes", "No"]},
        {"name": "Visceral metastases", "categories": ["Present", "Absent"]},
        {"name": "Number of bone metastases", "categories": ["<4", "4-10", ">10"]},
        {"name": "ECOG PS", "categories": ["0", "1", "2"]}
    ]
}

IMWG_CRITERIA = {
    "name": "IMWG",
    "full_name": "International Myeloma Working Group",
    "indication": "Multiple Myeloma",
    "version": "2016",
    "response_categories": {
        "sCR": {
            "definition": "Stringent Complete Response",
            "criteria": [
                "Normal FLC ratio",
                "Absence of clonal cells in bone marrow by immunohistochemistry or flow cytometry",
                "Negative serum and urine immunofixation"
            ]
        },
        "CR": {
            "definition": "Complete Response",
            "criteria": [
                "Negative serum and urine immunofixation",
                "<5% plasma cells in bone marrow",
                "Disappearance of soft tissue plasmacytomas"
            ]
        },
        "VGPR": {
            "definition": "Very Good Partial Response",
            "criteria": [
                "Serum and urine M-protein detectable by immunofixation but not electrophoresis",
                "OR ≥90% reduction in serum M-protein plus urine M-protein <100 mg/24h"
            ]
        },
        "PR": {
            "definition": "Partial Response",
            "criteria": [
                "≥50% reduction in serum M-protein",
                "≥90% reduction in 24-hour urine M-protein or <200 mg/24h",
                "≥50% reduction in difference between involved and uninvolved FLC levels"
            ]
        },
        "MR": {
            "definition": "Minimal Response",
            "criteria": ["25-49% reduction in serum M-protein"]
        },
        "SD": {
            "definition": "Stable Disease",
            "criteria": ["Not meeting criteria for CR, VGPR, PR, MR, or PD"]
        },
        "PD": {
            "definition": "Progressive Disease",
            "criteria": [
                "≥25% increase from lowest response in serum M-protein (absolute ≥0.5 g/dL)",
                "≥25% increase in urine M-protein (absolute ≥200 mg/24h)",
                "≥25% increase in difference between involved and uninvolved FLC (absolute >10 mg/dL)",
                "New bone lesions or soft tissue plasmacytomas",
                "≥50% increase in circulating plasma cells"
            ]
        }
    },
    "MRD_assessment": {
        "methods": ["Next-generation sequencing", "Next-generation flow cytometry"],
        "sensitivity": "10^-5 or 10^-6",
        "timing": "At suspected CR"
    },
    "endpoints": [
        {"name": "ORR", "definition": "≥PR rate"},
        {"name": "≥VGPR rate", "definition": "Rate of VGPR or better"},
        {"name": "CR rate", "definition": "Complete response rate"},
        {"name": "MRD negativity rate", "definition": "Rate of MRD-negative status"},
        {"name": "PFS", "definition": "Time to progression or death"},
        {"name": "DOR", "definition": "Duration of response"},
        {"name": "TTP", "definition": "Time to progression"}
    ],
    "baseline_variables": [
        {"name": "Serum M-protein", "unit": "g/dL"},
        {"name": "Urine M-protein", "unit": "mg/24h"},
        {"name": "Serum FLC", "unit": "mg/L"},
        {"name": "FLC ratio", "unit": "ratio"},
        {"name": "Bone marrow plasma cells", "unit": "%"},
        {"name": "ISS stage", "categories": ["I", "II", "III"]},
        {"name": "R-ISS stage", "categories": ["I", "II", "III"]},
        {"name": "Cytogenetics", "categories": ["Standard risk", "High risk"]},
        {"name": "Prior lines of therapy", "categories": ["1", "2", "3", "≥4"]}
    ]
}

GCIG_CA125_CRITERIA = {
    "name": "GCIG CA-125",
    "full_name": "Gynecologic Cancer InterGroup CA-125 Criteria",
    "indication": "Ovarian Cancer",
    "version": "2011",
    "response_categories": {
        "CA125_response": {
            "definition": "≥50% reduction from pretreatment sample, confirmed ≥28 days",
            "requires": "Two pretreatment samples at least 2 weeks apart"
        },
        "CA125_progression": {
            "from_elevated_baseline": "≥2x ULN on two occasions ≥1 week apart",
            "from_normalized": "≥2x nadir on two occasions ≥1 week apart"
        }
    },
    "endpoints": [
        {"name": "CA-125 response rate", "definition": "Proportion with ≥50% CA-125 reduction"},
        {"name": "CA-125 PFS", "definition": "Time to CA-125 progression or death"},
        {"name": "Combined PFS", "definition": "RECIST + CA-125 progression"}
    ],
    "baseline_variables": [
        {"name": "Baseline CA-125", "unit": "U/mL"},
        {"name": "FIGO stage", "categories": ["I", "II", "III", "IV"]},
        {"name": "Histology", "categories": ["High-grade serous", "Low-grade serous", "Endometrioid", "Clear cell", "Mucinous"]},
        {"name": "BRCA status", "categories": ["BRCA1 mutant", "BRCA2 mutant", "Wild-type", "Unknown"]},
        {"name": "Platinum sensitivity", "categories": ["Platinum-sensitive", "Platinum-resistant", "Platinum-refractory"]}
    ]
}

CML_CRITERIA = {
    "name": "ELN CML",
    "full_name": "European LeukemiaNet CML Response Criteria",
    "indication": "Chronic Myeloid Leukemia",
    "version": "2020",
    "response_categories": {
        "CHR": {
            "definition": "Complete Hematologic Response",
            "criteria": [
                "WBC <10 x 10^9/L",
                "Platelet count <450 x 10^9/L",
                "No immature granulocytes",
                "Basophils <5%",
                "No palpable spleen"
            ]
        },
        "CCyR": {
            "definition": "Complete Cytogenetic Response",
            "criteria": ["0% Ph+ metaphases"]
        },
        "PCyR": {
            "definition": "Partial Cytogenetic Response",
            "criteria": ["1-35% Ph+ metaphases"]
        },
        "MMR": {
            "definition": "Major Molecular Response",
            "criteria": ["BCR-ABL1 ≤0.1% IS (≥3-log reduction)"]
        },
        "MR4": {
            "definition": "Deep Molecular Response 4",
            "criteria": ["BCR-ABL1 ≤0.01% IS (≥4-log reduction)"]
        },
        "MR4.5": {
            "definition": "Deep Molecular Response 4.5",
            "criteria": ["BCR-ABL1 ≤0.0032% IS (≥4.5-log reduction)"]
        },
        "MR5": {
            "definition": "Deep Molecular Response 5",
            "criteria": ["BCR-ABL1 ≤0.001% IS (≥5-log reduction)"]
        }
    },
    "milestones": {
        "3_months": {"optimal": "BCR-ABL1 ≤10%", "warning": ">10%", "failure": ">10% if confirmed"},
        "6_months": {"optimal": "BCR-ABL1 ≤1%", "warning": "1-10%", "failure": ">10%"},
        "12_months": {"optimal": "BCR-ABL1 ≤0.1%", "warning": "0.1-1%", "failure": ">1%"}
    },
    "endpoints": [
        {"name": "MMR rate at 12 months", "definition": "Proportion achieving MMR by 12 months"},
        {"name": "CCyR rate at 12 months", "definition": "Proportion achieving CCyR by 12 months"},
        {"name": "Time to MMR", "definition": "Time to major molecular response"},
        {"name": "EFS", "definition": "Event-free survival"},
        {"name": "PFS", "definition": "Progression-free survival"},
        {"name": "TFR rate", "definition": "Treatment-free remission rate"}
    ],
    "baseline_variables": [
        {"name": "Sokal score", "categories": ["Low", "Intermediate", "High"]},
        {"name": "Hasford score", "categories": ["Low", "Intermediate", "High"]},
        {"name": "ELTS score", "categories": ["Low", "Intermediate", "High"]},
        {"name": "Disease phase", "categories": ["Chronic phase", "Accelerated phase", "Blast crisis"]},
        {"name": "Prior TKI", "categories": ["TKI-naive", "1 prior TKI", "2+ prior TKIs"]}
    ]
}

IWCLL_CRITERIA = {
    "name": "iwCLL",
    "full_name": "International Workshop on CLL Criteria",
    "indication": "Chronic Lymphocytic Leukemia",
    "version": "2018",
    "response_categories": {
        "CR": {
            "definition": "Complete Remission",
            "criteria": [
                "Lymphocytes <4 x 10^9/L",
                "No lymphadenopathy (nodes <1.5 cm)",
                "No hepatomegaly/splenomegaly",
                "Neutrophils >1.5 x 10^9/L",
                "Platelets >100 x 10^9/L",
                "Hemoglobin >11 g/dL (untransfused)",
                "<30% lymphocytes in bone marrow"
            ]
        },
        "CRi": {
            "definition": "CR with incomplete marrow recovery",
            "criteria": ["CR criteria except persistent cytopenia due to drug toxicity"]
        },
        "PR": {
            "definition": "Partial Remission",
            "criteria": [
                "≥50% decrease in lymphocyte count",
                "≥50% reduction in lymphadenopathy",
                "≥50% reduction in liver/spleen enlargement",
                "Plus one of: neutrophils >1.5, platelets >100, Hgb >11"
            ]
        },
        "PD": {
            "definition": "Progressive Disease",
            "criteria": [
                "≥50% increase in lymphocytes",
                "New lymphadenopathy or ≥50% increase",
                "≥50% increase in liver/spleen",
                "Richter transformation",
                "New cytopenia due to CLL"
            ]
        },
        "uMRD": {
            "definition": "Undetectable MRD",
            "criteria": ["<1 CLL cell per 10,000 leukocytes (10^-4)"]
        }
    },
    "endpoints": [
        {"name": "ORR", "definition": "CR + CRi + PR rate"},
        {"name": "CR rate", "definition": "Complete remission rate"},
        {"name": "uMRD rate", "definition": "Undetectable MRD rate"},
        {"name": "PFS", "definition": "Progression-free survival"},
        {"name": "TTNT", "definition": "Time to next treatment"},
        {"name": "DOR", "definition": "Duration of response"}
    ],
    "baseline_variables": [
        {"name": "Rai stage", "categories": ["0", "I", "II", "III", "IV"]},
        {"name": "Binet stage", "categories": ["A", "B", "C"]},
        {"name": "IGHV mutation status", "categories": ["Mutated", "Unmutated"]},
        {"name": "Del(17p)", "categories": ["Present", "Absent"]},
        {"name": "TP53 mutation", "categories": ["Mutated", "Wild-type"]},
        {"name": "Del(11q)", "categories": ["Present", "Absent"]},
        {"name": "Complex karyotype", "categories": ["Yes", "No"]},
        {"name": "Beta-2 microglobulin", "unit": "mg/L"}
    ]
}

# =============================================================================
# 2. STUDY TYPE TEMPLATES
# =============================================================================

ADJUVANT_TRIAL_TEMPLATE = {
    "study_type": "Adjuvant",
    "description": "Treatment after primary therapy to reduce recurrence risk",
    "primary_endpoints": [
        {
            "name": "DFS",
            "definition": "Disease-Free Survival",
            "events": ["Local recurrence", "Distant recurrence", "Second primary cancer", "Death from any cause"]
        },
        {
            "name": "iDFS",
            "definition": "Invasive Disease-Free Survival (breast cancer)",
            "events": ["Invasive local/regional recurrence", "Distant recurrence", "Death from any cause", "Invasive contralateral breast cancer"]
        },
        {
            "name": "RFS",
            "definition": "Recurrence-Free Survival",
            "events": ["Local recurrence", "Distant recurrence", "Death from disease"]
        }
    ],
    "secondary_endpoints": [
        {"name": "OS", "definition": "Overall Survival"},
        {"name": "DRFS", "definition": "Distant Recurrence-Free Survival"},
        {"name": "LRRFS", "definition": "Locoregional Recurrence-Free Survival"}
    ],
    "special_considerations": [
        "No baseline tumor for response assessment",
        "Long follow-up required (5-10 years)",
        "Event-driven analysis",
        "Quality of life important secondary endpoint"
    ]
}

NEOADJUVANT_TRIAL_TEMPLATE = {
    "study_type": "Neoadjuvant",
    "description": "Treatment before primary surgery",
    "primary_endpoints": [
        {
            "name": "pCR",
            "definition": "Pathological Complete Response",
            "breast_definitions": {
                "ypT0/is ypN0": "No invasive cancer in breast or nodes",
                "ypT0 ypN0": "No invasive or in situ cancer in breast or nodes"
            }
        },
        {
            "name": "RCB",
            "definition": "Residual Cancer Burden",
            "categories": ["RCB-0 (pCR)", "RCB-I (minimal)", "RCB-II (moderate)", "RCB-III (extensive)"]
        },
        {
            "name": "MPR",
            "definition": "Major Pathological Response (NSCLC)",
            "criteria": "≤10% viable tumor cells"
        }
    ],
    "secondary_endpoints": [
        {"name": "EFS", "definition": "Event-Free Survival"},
        {"name": "DFS", "definition": "Disease-Free Survival"},
        {"name": "OS", "definition": "Overall Survival"},
        {"name": "Surgical outcomes", "definition": "R0 resection rate, organ preservation"}
    ],
    "special_considerations": [
        "pCR as accelerated approval endpoint",
        "EFS/DFS for full approval",
        "Surgery timing affects analysis",
        "Patients who don't go to surgery"
    ]
}

BASKET_TRIAL_TEMPLATE = {
    "study_type": "Basket",
    "description": "Single drug across multiple tumor types with common biomarker",
    "design_features": [
        "Multiple tumor-specific cohorts",
        "Common molecular alteration (e.g., BRAF V600E, NTRK fusion)",
        "Simon 2-stage or Bayesian adaptive design per cohort"
    ],
    "primary_endpoints": [
        {"name": "ORR by tumor type", "definition": "Objective response rate in each cohort"},
        {"name": "Pooled ORR", "definition": "Response rate across all cohorts (exploratory)"}
    ],
    "statistical_considerations": [
        "Control of Type I error across cohorts",
        "Borrowing information across cohorts (Bayesian)",
        "Sample size per cohort typically 20-40",
        "Futility rules per cohort"
    ]
}

UMBRELLA_TRIAL_TEMPLATE = {
    "study_type": "Umbrella",
    "description": "Single tumor type with multiple biomarker-driven treatment arms",
    "design_features": [
        "Central screening/molecular profiling",
        "Biomarker-matched treatment arms",
        "Common control arm possible",
        "Adaptive randomization"
    ],
    "primary_endpoints": [
        {"name": "PFS per arm", "definition": "Progression-free survival by treatment arm"},
        {"name": "ORR per arm", "definition": "Response rate by treatment arm"}
    ],
    "statistical_considerations": [
        "Master protocol with multiple sub-studies",
        "Graduated alpha allocation",
        "Arms can open/close independently",
        "Shared control arm efficiency"
    ]
}

PHASE1_DOSE_FINDING_TEMPLATE = {
    "study_type": "Phase 1 Dose-Finding",
    "description": "First-in-human dose escalation",
    "designs": {
        "3+3": {
            "description": "Rule-based, 3 patients per dose level",
            "escalation": "If 0/3 DLT: escalate. If 1/3 DLT: expand to 6. If 2+/3 DLT: de-escalate",
            "mtd_definition": "Highest dose with <33% DLT rate"
        },
        "BOIN": {
            "description": "Bayesian Optimal Interval design",
            "parameters": ["Target DLT rate (e.g., 0.30)", "Escalation boundary", "De-escalation boundary"],
            "advantages": ["Better operating characteristics than 3+3", "Simple decision rules"]
        },
        "CRM": {
            "description": "Continual Reassessment Method",
            "parameters": ["Target DLT rate", "Prior toxicity probabilities", "Skeleton"],
            "advantages": ["Model-based", "More efficient", "Better MTD estimation"]
        },
        "mTPI": {
            "description": "Modified Toxicity Probability Interval",
            "parameters": ["Target DLT rate", "Equivalence interval"],
            "advantages": ["Bayesian", "Transparent decisions"]
        }
    },
    "primary_endpoints": [
        {"name": "DLT rate", "definition": "Dose-limiting toxicity rate per dose level"},
        {"name": "MTD", "definition": "Maximum Tolerated Dose"},
        {"name": "RP2D", "definition": "Recommended Phase 2 Dose"}
    ],
    "dlt_evaluation": {
        "window": "Typically Cycle 1 (21 or 28 days)",
        "common_dlts": [
            "Grade 4 neutropenia >7 days",
            "Febrile neutropenia",
            "Grade 4 thrombocytopenia or Grade 3 with bleeding",
            "Grade 3-4 non-hematologic toxicity (excluding nausea/vomiting without maximal antiemetics)",
            "Treatment delay >2 weeks due to toxicity"
        ]
    }
}

# =============================================================================
# 3. EMERGING THERAPY MODULES
# =============================================================================

CAR_T_MODULE = {
    "therapy_type": "CAR-T Cell Therapy",
    "description": "Chimeric Antigen Receptor T-cell therapy",

    # ==========================================================================
    # TOXICITY GRADING
    # ==========================================================================
    "unique_toxicities": {
        "CRS": {
            "name": "Cytokine Release Syndrome",
            "grading": "ASTCT 2019 Consensus",
            "reference": "{Lee 2019}",
            "grades": {
                "1": "Fever only (≥38°C)",
                "2": "Fever + hypotension not requiring vasopressors and/or hypoxia requiring low-flow O2",
                "3": "Fever + hypotension requiring 1 vasopressor ± vasopressin and/or hypoxia requiring high-flow O2",
                "4": "Fever + hypotension requiring multiple vasopressors and/or hypoxia requiring positive pressure"
            },
            "management": ["Tocilizumab", "Corticosteroids"],
            "collection_method": "Collected via specific CRF, neurologic AEs reported separately on AE log"
        },
        "ICANS": {
            "name": "Immune Effector Cell-Associated Neurotoxicity Syndrome",
            "grading": "ICE score (Immune Effector Cell-Associated Encephalopathy)",
            "reference": "{Topp 2015}",
            "grades": {
                "1": "ICE 7-9",
                "2": "ICE 3-6",
                "3": "ICE 0-2",
                "4": "ICE 0 + cerebral edema/seizure/motor weakness"
            },
            "pediatric_grading": "CAPD (Cornell Assessment of Pediatric Delirium) for age <12 years"
        }
    },

    # ==========================================================================
    # ANALYSIS POPULATIONS (Including Re-treatment)
    # ==========================================================================
    "analysis_populations": {
        "safety_analysis_set": {
            "name": "Safety Analysis Set",
            "definition": "All subjects treated with any dose of CAR-T product",
            "use_for": "All safety analyses"
        },
        "full_analysis_set": {
            "name": "Full Analysis Set (FAS)",
            "definition": "All enrolled patients",
            "use_for": "Subject disposition summaries"
        },
        "inferential_analysis_set": {
            "name": "Inferential Analysis Set",
            "definition": "Enrolled subjects meeting pivotal cohort eligibility criteria and treated with CAR-T product",
            "use_for": "Primary efficacy analyses"
        },
        "safety_retreatment_analysis_set": {
            "name": "Safety Re-treatment Analysis Set",
            "definition": "All subjects who undergo retreatment with CAR-T product. This set will be used for all retreatment safety and efficacy analyses.",
            "use_for": "Retreatment safety and efficacy analyses",
            "note": "Only applicable if protocol allows retreatment"
        }
    },

    # ==========================================================================
    # EFFICACY ENDPOINTS (Including DORR)
    # ==========================================================================
    "efficacy_endpoints": [
        {"name": "ORR", "definition": "CR + CRi + PR (varies by indication)"},
        {"name": "CR/CRi rate", "definition": "Complete response with/without count recovery"},
        {"name": "DOR", "definition": "Duration of response from first response to progression or death"},
        {"name": "PFS", "definition": "Progression-free survival"},
        {"name": "OS", "definition": "Overall survival"},
        {"name": "MRD negativity", "definition": "Minimal residual disease negativity rate"}
    ],
    "retreatment_endpoints": {
        "DORR": {
            "name": "Duration of Response to Retreatment (DORR)",
            "definition": "DORR is defined only for subjects who receive retreatment following progression of disease per Investigator Read and then go on to experience an objective response to retreatment.",
            "start": "Date of first response to retreatment",
            "end": "Date of progression or death after retreatment response",
            "censoring": "Subjects without progression censored at last disease assessment"
        },
        "ORR_retreatment": {
            "name": "ORR to Retreatment",
            "definition": "Objective response rate among subjects who received retreatment"
        }
    },

    # ==========================================================================
    # CELLULAR KINETICS ENDPOINTS
    # ==========================================================================
    "cellular_kinetics": {
        "parameters": [
            {"name": "Cmax", "definition": "Maximum CAR-T cell level attained"},
            {"name": "Tmax", "definition": "Time at which maximum level was attained"},
            {"name": "AUC_0_28", "definition": "AUC of CAR-T cell levels from Day 0 to Day 28"},
            {"name": "Peak_0_28", "definition": "Peak value from Day 0 to Day 28"},
            {"name": "Time_to_undetectable", "definition": "Time at which no detectable CAR-T cells in blood"},
            {"name": "Persistence", "definition": "Duration of detectable CAR-T cells"}
        ],
        "measurement_timepoints": [
            "Day 7", "Week 2", "Week 4", "Month 3", "Month 6", "Month 12", "Month 24"
        ],
        "summary_statistics": [
            "n, Mean, SD, Median, Min, Max for each parameter",
            "Geometric mean and CV% for Cmax and AUC"
        ]
    },
    "special_endpoints": [
        {"name": "B-cell aplasia duration", "definition": "Time without B-cells (CD19 CAR-T)"},
        {"name": "Immunoglobulin levels", "definition": "IgG, IgA, IgM over time"}
    ],

    # ==========================================================================
    # SAFETY MONITORING & MedDRA STRATEGIES
    # ==========================================================================
    "safety_monitoring": [
        "CRS grade and timing",
        "ICANS grade and timing",
        "Cytopenias (prolonged)",
        "Infections (hypogammaglobulinemia)",
        "Secondary malignancies"
    ],
    "meddra_search_strategies": {
        "neurological_toxicity": {
            "description": "Search strategy based on {Topp 2015}, focused on CNS toxicity",
            "meddra_socs": ["Psychiatric Disorders", "Nervous System Disorders"],
            "search_type": "MST (MedDRA Search Terms)"
        },
        "CRS": {
            "description": "Collected via specific CRF, graded per ASTCT 2019",
            "collection": "Specific CRF for CRS events",
            "note": "Neurologic AEs reported separately on AE log"
        },
        "thrombocytopenia": {
            "search_type": "SMQ",
            "smq_name": "Haematopoietic thrombocytopenia",
            "scope": "narrow"
        },
        "neutropenia": {
            "search_type": "MST",
            "description": "Sponsor-specified MedDRA search terms"
        },
        "anemia": {
            "search_type": "SMQ",
            "smq_name": "Haematopoietic erythropenia",
            "scope": "broad"
        },
        "hypogammaglobulinemia": {
            "search_type": "MST",
            "description": "Sponsor-specified search strategy"
        },
        "infections": {
            "search_type": "HLGT",
            "hltgs": ["Bacterial infectious disorders", "Viral infectious disorders",
                      "Fungal infectious disorders", "Infections - pathogen unspecified"]
        },
        "secondary_malignancy": {
            "search_type": "SOC",
            "soc": "Neoplasms benign, malignant and unspecified"
        },
        "tumor_lysis_syndrome": {
            "search_type": "SMQ",
            "smq_name": "Tumour lysis syndrome",
            "scope": "narrow"
        },
        "GVHD": {
            "search_type": "MST",
            "description": "Using subsets of PT from HLGT and HLT for graft versus host disease"
        },
        "immunogenicity": {
            "search_type": "SMQ",
            "smq_names": ["Anaphylactic reaction", "Hypersensitivity"],
            "scope": "narrow"
        }
    },

    # ==========================================================================
    # TIME-TO-EVENT DERIVATION RULES
    # ==========================================================================
    "tte_derivation_rules": {
        "DOR": {
            "description": "Duration of Response derivation circumstances",
            "circumstances": [
                {"situation": "Responder with subsequent PD", "event": 1, "date": "Date of PD"},
                {"situation": "Responder dies without PD", "event": 1, "date": "Date of death"},
                {"situation": "Responder with no PD, still on study", "event": 0, "date": "Date of last adequate disease assessment"},
                {"situation": "Responder starts new anticancer therapy without PD", "event": 0, "date": "Date of last adequate disease assessment before new therapy"},
                {"situation": "Responder has SCT without prior PD", "event": 0, "date": "Date of last adequate disease assessment before SCT"},
                {"situation": "Responder lost to follow-up", "event": 0, "date": "Date of last adequate disease assessment"}
            ],
            "sensitivity_analysis": "Include disease assessments after SCT"
        },
        "DORR": {
            "description": "Duration of Response to Retreatment derivation",
            "circumstances": [
                {"situation": "Retreatment responder with subsequent PD", "event": 1, "date": "Date of PD after retreatment response"},
                {"situation": "Retreatment responder dies without PD", "event": 1, "date": "Date of death"},
                {"situation": "Retreatment responder with no PD", "event": 0, "date": "Date of last adequate disease assessment"},
                {"situation": "Retreatment responder starts new therapy without PD", "event": 0, "date": "Date of last adequate assessment before new therapy"},
                {"situation": "Retreatment responder has SCT without PD", "event": 0, "date": "Date of last adequate assessment before SCT"},
                {"situation": "Retreatment responder lost to follow-up", "event": 0, "date": "Date of last adequate disease assessment"}
            ]
        },
        "PFS": {
            "description": "Progression-Free Survival derivation",
            "circumstances": [
                {"situation": "Subject has PD", "event": 1, "date": "Date of PD"},
                {"situation": "Subject dies without PD", "event": 1, "date": "Date of death"},
                {"situation": "Subject alive without PD, on study", "event": 0, "date": "Date of last adequate disease assessment"},
                {"situation": "Subject starts new anticancer therapy without PD", "event": 0, "date": "Date of last adequate assessment before new therapy"},
                {"situation": "Subject has SCT without prior PD", "event": 0, "date": "Date of last adequate assessment before SCT"},
                {"situation": "Subject lost to follow-up without PD", "event": 0, "date": "Date of last adequate disease assessment"},
                {"situation": "Subject withdraws consent without PD", "event": 0, "date": "Date of last adequate disease assessment"}
            ]
        },
        "OS": {
            "description": "Overall Survival derivation",
            "circumstances": [
                {"situation": "Subject dies", "event": 1, "date": "Date of death"},
                {"situation": "Subject alive at data cutoff", "event": 0, "date": "Last date known to be alive"},
                {"situation": "Subject lost to follow-up", "event": 0, "date": "Last date known to be alive"},
                {"situation": "Subject withdraws consent", "event": 0, "date": "Last date known to be alive"},
                {"situation": "Death date unknown (partial)", "event": 0, "date": "Last date known to be alive (do not impute)"}
            ]
        },
        "last_known_alive_sources": [
            "Subject visit dates", "AE dates", "Concomitant medication dates",
            "Laboratory dates", "Tumor assessment dates", "Survival follow-up contact dates",
            "Study drug administration dates", "Vital signs dates", "ECG dates"
        ]
    },

    # ==========================================================================
    # DATE IMPUTATION RULES
    # ==========================================================================
    "date_imputation_rules": {
        "description": "Standard date imputation algorithms for partial dates",
        "ae_start_date": [
            {
                "scenario": "Partial (yyyymm) = Study Day 0 month",
                "stop_date": "Complete/Partial/Missing",
                "rule": "Impute date of Study Day 0"
            },
            {
                "scenario": "Partial (yyyymm) ≠ Study Day 0 month",
                "stop_date": "Any",
                "rule": "Impute first day of month"
            },
            {
                "scenario": "Partial (yyyy) = Study Day 0 year, month missing",
                "stop_date": "Complete stop date in same year",
                "rule": "Impute Study Day 0 if ≤ stop month, else impute first of stop month"
            },
            {
                "scenario": "Partial (yyyy) = Study Day 0 year, month missing",
                "stop_date": "Partial/Missing",
                "rule": "Impute Study Day 0"
            },
            {
                "scenario": "Missing start date",
                "stop_date": "Complete",
                "rule": "Impute Study Day 0 or January 1 of stop year (whichever is later)"
            },
            {
                "scenario": "Missing start date",
                "stop_date": "Missing",
                "rule": "Impute Study Day 0"
            }
        ],
        "death_date": [
            {
                "scenario": "Year and month available, day missing",
                "condition": "mmyyyy for last contact = mmyyyy for death",
                "rule": "Set to day after last known alive date"
            },
            {
                "scenario": "Year and month available, day missing",
                "condition": "mmyyyy last known alive < mmyyyy death",
                "rule": "Set to first day of death month"
            },
            {
                "scenario": "Month and day missing (only year known)",
                "rule": "Do NOT impute - censor at last known alive date"
            }
        ],
        "conmed_start_date": [
            {
                "scenario": "Partial (yyyymm)",
                "rule": "Impute first day of month"
            },
            {
                "scenario": "Partial (yyyy)",
                "rule": "Impute January 1 of year"
            },
            {
                "scenario": "Missing",
                "rule": "Impute Study Day 0"
            }
        ]
    },

    # ==========================================================================
    # OPERATIONAL DEFINITIONS
    # ==========================================================================
    "operational_definitions": {
        "study_enrollment": "Occurs at commencement of leukapheresis",
        "study_day_0": "Day subject received first CAR-T infusion",
        "baseline": "Last value taken prior to first dose of conditioning chemotherapy",
        "study_therapy": "Conditioning chemotherapy or CAR-T product",
        "on_study": "Time from enrollment to last date of contact",
        "end_of_study": "After all subjects followed for 15 years post-infusion",
        "actual_follow_up_time": "Time from first dose to death/last known alive/LTFU/withdrawal",
        "potential_follow_up_time": "Time from infusion to data cutoff date",
        "follow_up_time_for_response": "Calculated using reverse Kaplan-Meier approach {Schemper 1996}",
        "TEAE": "Any AE with onset on or after CAR-T infusion",
        "deaths_reporting": "All deaths after leukapheresis through end of study"
    },

    # ==========================================================================
    # SINGLE-ARM STUDY CONSIDERATIONS
    # ==========================================================================
    "single_arm_considerations": {
        "primary_analysis": "Exact binomial test comparing observed rate to historical control",
        "confidence_interval": "Clopper-Pearson 95% CI (2-sided)",
        "hypothesis_testing": "One-sided test at α = 0.025",
        "no_randomization": True,
        "no_hazard_ratios": True,
        "no_treatment_comparison": True,
        "table_format": "Single column for treated subjects (no comparator)"
    }
}

BISPECIFIC_ANTIBODY_MODULE = {
    "therapy_type": "Bispecific Antibody",
    "description": "T-cell engaging bispecific antibodies",
    "unique_considerations": {
        "step_up_dosing": "Gradual dose escalation to mitigate CRS",
        "crs_risk": "Similar to CAR-T but generally lower",
        "hospitalization": "Often required for initial doses"
    },
    "efficacy_endpoints": [
        {"name": "ORR", "definition": "Objective response rate"},
        {"name": "CR rate", "definition": "Complete response rate"},
        {"name": "DOR", "definition": "Duration of response"},
        {"name": "PFS", "definition": "Progression-free survival"}
    ],
    "safety_endpoints": [
        {"name": "CRS rate by grade", "definition": "Cytokine release syndrome incidence"},
        {"name": "Neurotoxicity rate", "definition": "Neurologic adverse events"},
        {"name": "Infection rate", "definition": "Including opportunistic infections"}
    ]
}

ADC_MODULE = {
    "therapy_type": "Antibody-Drug Conjugate",
    "description": "Antibody linked to cytotoxic payload",
    "unique_toxicities": {
        "payload_specific": {
            "MMAE/MMAF": ["Peripheral neuropathy", "Neutropenia"],
            "DXd": ["Interstitial lung disease", "Nausea"],
            "SN-38": ["Diarrhea", "Neutropenia"],
            "Calicheamicin": ["Hepatotoxicity", "VOD/SOS"]
        },
        "ocular_toxicity": "Common with many ADCs",
        "ild_monitoring": "Especially with DXd payload"
    },
    "efficacy_endpoints": [
        {"name": "ORR", "definition": "Objective response rate"},
        {"name": "PFS", "definition": "Progression-free survival"},
        {"name": "OS", "definition": "Overall survival"},
        {"name": "DOR", "definition": "Duration of response"}
    ],
    "pk_endpoints": [
        {"name": "Total antibody", "definition": "Conjugated + unconjugated antibody"},
        {"name": "Conjugated antibody", "definition": "ADC with payload attached"},
        {"name": "Free payload", "definition": "Released cytotoxic drug"}
    ]
}

# =============================================================================
# 4. BIOMARKER ENDPOINTS
# =============================================================================

BIOMARKER_ENDPOINTS = {
    "PSA": {
        "indication": "Prostate Cancer",
        "endpoints": [
            {"name": "PSA response", "definition": "≥50% decline from baseline"},
            {"name": "PSA90", "definition": "≥90% decline from baseline"},
            {"name": "PSA progression", "definition": "≥25% and ≥2 ng/mL above nadir"},
            {"name": "PSA-PFS", "definition": "Time to PSA progression"},
            {"name": "PSA doubling time", "definition": "Time for PSA to double"}
        ],
        "baseline_collection": "Two values at least 1 week apart"
    },
    "M_protein": {
        "indication": "Multiple Myeloma",
        "endpoints": [
            {"name": "M-protein response", "definition": "≥50% reduction from baseline"},
            {"name": "VGPR", "definition": "≥90% reduction or immunofixation+ only"},
            {"name": "CR by M-protein", "definition": "Negative immunofixation"}
        ],
        "methods": ["SPEP", "UPEP", "Immunofixation"]
    },
    "FLC": {
        "indication": "Multiple Myeloma (oligosecretory)",
        "endpoints": [
            {"name": "FLC response", "definition": "≥50% reduction in dFLC"},
            {"name": "FLC-based CR", "definition": "Normal FLC ratio"}
        ],
        "baseline_collection": "Involved and uninvolved FLC"
    },
    "CA125": {
        "indication": "Ovarian Cancer",
        "endpoints": [
            {"name": "CA-125 response", "definition": "≥50% reduction, confirmed at 28 days"},
            {"name": "CA-125 progression", "definition": "≥2x nadir or ULN"}
        ],
        "baseline_collection": "Two samples at least 1 week apart"
    },
    "BCR_ABL": {
        "indication": "CML",
        "endpoints": [
            {"name": "MMR", "definition": "BCR-ABL1 ≤0.1% IS"},
            {"name": "MR4", "definition": "BCR-ABL1 ≤0.01% IS"},
            {"name": "MR4.5", "definition": "BCR-ABL1 ≤0.0032% IS"},
            {"name": "Time to MMR", "definition": "Time to BCR-ABL1 ≤0.1%"}
        ],
        "methods": ["RT-qPCR on International Scale"]
    },
    "ctDNA": {
        "indication": "Multiple solid tumors",
        "endpoints": [
            {"name": "ctDNA clearance", "definition": "Undetectable ctDNA post-treatment"},
            {"name": "ctDNA response", "definition": "≥50% or log-reduction in VAF"},
            {"name": "Molecular response", "definition": "ctDNA reduction correlating with outcome"}
        ],
        "methods": ["ddPCR", "NGS panels", "WES"]
    },
    "AFP": {
        "indication": "Hepatocellular Carcinoma",
        "endpoints": [
            {"name": "AFP response", "definition": "≥50% or ≥20% reduction from baseline"},
            {"name": "AFP progression", "definition": "Defined increase from nadir"}
        ]
    }
}

# =============================================================================
# 5. BASELINE VARIABLES
# =============================================================================

PERFORMANCE_STATUS_SCALES = {
    "ECOG": {
        "name": "ECOG Performance Status",
        "categories": ["0", "1", "2", "3", "4", "5"],
        "definitions": {
            "0": "Fully active, no restrictions",
            "1": "Restricted in strenuous activity, ambulatory",
            "2": "Ambulatory, capable of self-care, up >50% of waking hours",
            "3": "Capable of limited self-care, confined to bed/chair >50%",
            "4": "Completely disabled, no self-care",
            "5": "Dead"
        }
    },
    "Karnofsky": {
        "name": "Karnofsky Performance Status",
        "categories": ["100", "90", "80", "70", "60", "50", "40", "30", "20", "10", "0"],
        "conversion_to_ecog": {
            "100": "0", "90": "0",
            "80": "1", "70": "1",
            "60": "2", "50": "2",
            "40": "3", "30": "3",
            "20": "4", "10": "4",
            "0": "5"
        }
    },
    "Lansky": {
        "name": "Lansky Play-Performance Scale (pediatric)",
        "categories": ["100", "90", "80", "70", "60", "50", "40", "30", "20", "10", "0"]
    },
    "ASA": {
        "name": "ASA Physical Status Classification",
        "categories": ["I", "II", "III", "IV", "V", "VI"],
        "definitions": {
            "I": "Normal healthy patient",
            "II": "Mild systemic disease",
            "III": "Severe systemic disease",
            "IV": "Severe systemic disease, constant threat to life",
            "V": "Moribund, not expected to survive without operation",
            "VI": "Brain-dead organ donor"
        }
    }
}

ORGAN_FUNCTION_SCORES = {
    "Child_Pugh": {
        "name": "Child-Pugh Score",
        "indication": "HCC, liver metastases",
        "parameters": ["Bilirubin", "Albumin", "INR", "Ascites", "Encephalopathy"],
        "classes": {
            "A": "5-6 points",
            "B": "7-9 points",
            "C": "10-15 points"
        }
    },
    "ALBI": {
        "name": "Albumin-Bilirubin Grade",
        "indication": "HCC",
        "formula": "(log10 bilirubin × 0.66) + (albumin × -0.085)",
        "grades": {
            "1": "≤-2.60",
            "2": ">-2.60 to ≤-1.39",
            "3": ">-1.39"
        }
    },
    "eGFR_thresholds": {
        "name": "Renal Function Categories",
        "categories": {
            "Normal": "≥90 mL/min/1.73m²",
            "Mild impairment": "60-89 mL/min/1.73m²",
            "Moderate impairment": "30-59 mL/min/1.73m²",
            "Severe impairment": "15-29 mL/min/1.73m²",
            "ESRD": "<15 mL/min/1.73m²"
        }
    }
}

PROGNOSTIC_SCORES = {
    "IMDC": {
        "name": "International Metastatic RCC Database Consortium",
        "indication": "Metastatic RCC",
        "factors": [
            "Karnofsky PS <80%",
            "Time from diagnosis to treatment <1 year",
            "Hemoglobin < LLN",
            "Corrected calcium > ULN",
            "Neutrophils > ULN",
            "Platelets > ULN"
        ],
        "risk_groups": {
            "Favorable": "0 factors",
            "Intermediate": "1-2 factors",
            "Poor": "3-6 factors"
        }
    },
    "IPI": {
        "name": "International Prognostic Index",
        "indication": "DLBCL",
        "factors": [
            "Age >60",
            "Stage III/IV",
            "Elevated LDH",
            "ECOG PS ≥2",
            "Extranodal sites >1"
        ],
        "risk_groups": {
            "Low": "0-1",
            "Low-intermediate": "2",
            "High-intermediate": "3",
            "High": "4-5"
        }
    }
}

# =============================================================================
# 6. TFL TEMPLATES
# =============================================================================

EFFICACY_TFL_TEMPLATES = {
    "OS_5year": {
        "table_id": "14.2.1.1",
        "title": "Overall Survival at 5 Years (ITT Population)",
        "columns": ["Treatment A", "Treatment B", "Hazard Ratio (95% CI)", "P-value"],
        "rows": [
            "Number of subjects",
            "Number of events (%)",
            "Median OS, months (95% CI)",
            "OS rate at 1 year (95% CI)",
            "OS rate at 2 years (95% CI)",
            "OS rate at 3 years (95% CI)",
            "OS rate at 5 years (95% CI)"
        ],
        "footnotes": [
            "Kaplan-Meier estimates",
            "Stratified Cox proportional hazards model",
            "Two-sided p-value from stratified log-rank test"
        ]
    },
    "exploratory_endpoints": {
        "table_id": "14.2.4",
        "title": "Summary of Exploratory Efficacy Endpoints (ITT Population)",
        "sections": [
            {
                "name": "Biomarker Endpoints",
                "endpoints": ["ctDNA response", "Biomarker X change from baseline"]
            },
            {
                "name": "Patient-Reported Outcomes",
                "endpoints": ["EORTC QLQ-C30", "Disease-specific PRO"]
            },
            {
                "name": "Subgroup Analyses",
                "endpoints": ["PFS by biomarker status", "ORR by prior therapy"]
            }
        ]
    },
    "endpoint_specifications": {
        "table_id": "Table 9",
        "title": "Endpoint Variable Specifications",
        "columns": ["Endpoint", "Definition", "Event", "Censoring", "Analysis Population"],
        "standard_endpoints": [
            {
                "endpoint": "PFS",
                "definition": "Time from randomization to progression or death",
                "event": "Progression per RECIST 1.1 or death",
                "censoring": "Last adequate tumor assessment",
                "population": "ITT"
            },
            {
                "endpoint": "OS",
                "definition": "Time from randomization to death",
                "event": "Death from any cause",
                "censoring": "Last known alive date",
                "population": "ITT"
            },
            {
                "endpoint": "ORR",
                "definition": "Proportion with CR or PR",
                "event": "Best response of CR or PR",
                "censoring": "N/A",
                "population": "ITT with measurable disease"
            },
            {
                "endpoint": "DOR",
                "definition": "Time from first response to progression",
                "event": "Progression or death",
                "censoring": "Last adequate tumor assessment",
                "population": "Responders"
            }
        ]
    },
    "exploratory_specifications": {
        "table_id": "Table 10",
        "title": "Exploratory Endpoint Specifications",
        "endpoints": [
            {"name": "Landmark PFS", "timepoints": ["6 months", "12 months", "24 months"]},
            {"name": "TTR", "definition": "Time to response"},
            {"name": "DCR", "definition": "Disease control rate (CR+PR+SD)"},
            {"name": "CBR", "definition": "Clinical benefit rate"}
        ]
    }
}

SAFETY_TFL_TEMPLATES = {
    "ae_by_visit": {
        "table_id": "Supp Table 1",
        "title": "Treatment-Emergent Adverse Events by Visit (Safety Population)",
        "structure": {
            "rows": "System Organ Class / Preferred Term",
            "columns": ["Baseline", "Cycle 1", "Cycle 2", "Cycle 3", "...", "End of Treatment", "Follow-up"],
            "cells": "n (%)"
        },
        "footnotes": [
            "Multiple occurrences of same AE counted once per visit",
            "Grading per CTCAE v5.0"
        ]
    },
    "ae_leading_to_modification": {
        "table_id": "14.3.2.7",
        "title": "Adverse Events Leading to Dose Modification (Safety Population)",
        "sections": [
            "AEs leading to dose reduction",
            "AEs leading to dose interruption",
            "AEs leading to discontinuation"
        ]
    }
}

# =============================================================================
# EXPORT ALL DATA
# =============================================================================

def get_all_response_criteria():
    """Return all response criteria."""
    return {
        "PCWG3": PCWG3_CRITERIA,
        "IMWG": IMWG_CRITERIA,
        "GCIG_CA125": GCIG_CA125_CRITERIA,
        "ELN_CML": CML_CRITERIA,
        "iwCLL": IWCLL_CRITERIA
    }

def get_all_study_templates():
    """Return all study type templates."""
    return {
        "Adjuvant": ADJUVANT_TRIAL_TEMPLATE,
        "Neoadjuvant": NEOADJUVANT_TRIAL_TEMPLATE,
        "Basket": BASKET_TRIAL_TEMPLATE,
        "Umbrella": UMBRELLA_TRIAL_TEMPLATE,
        "Phase1_Dose_Finding": PHASE1_DOSE_FINDING_TEMPLATE
    }

def get_all_therapy_modules():
    """Return all emerging therapy modules."""
    return {
        "CAR_T": CAR_T_MODULE,
        "Bispecific": BISPECIFIC_ANTIBODY_MODULE,
        "ADC": ADC_MODULE
    }

def get_all_biomarker_endpoints():
    """Return all biomarker endpoints."""
    return BIOMARKER_ENDPOINTS

def get_all_baseline_variables():
    """Return all baseline variable reference data."""
    return {
        "performance_status": PERFORMANCE_STATUS_SCALES,
        "organ_function": ORGAN_FUNCTION_SCORES,
        "prognostic_scores": PROGNOSTIC_SCORES
    }

def get_all_tfl_templates():
    """Return all TFL templates."""
    return {
        "efficacy": EFFICACY_TFL_TEMPLATES,
        "safety": SAFETY_TFL_TEMPLATES
    }


if __name__ == "__main__":
    import json
    from pathlib import Path

    print("=" * 70)
    print("ONCOLOGY REFERENCE DATA SUMMARY")
    print("=" * 70)

    print("\n1. RESPONSE CRITERIA:")
    for name in get_all_response_criteria():
        print(f"   - {name}")

    print("\n2. STUDY TYPE TEMPLATES:")
    for name in get_all_study_templates():
        print(f"   - {name}")

    print("\n3. EMERGING THERAPY MODULES:")
    for name in get_all_therapy_modules():
        print(f"   - {name}")

    print("\n4. BIOMARKER ENDPOINTS:")
    for name in get_all_biomarker_endpoints():
        print(f"   - {name}")

    print("\n5. BASELINE VARIABLES:")
    for cat, items in get_all_baseline_variables().items():
        print(f"   {cat}: {list(items.keys())}")

    print("\n6. TFL TEMPLATES:")
    for cat, items in get_all_tfl_templates().items():
        print(f"   {cat}: {list(items.keys())}")

    # Export to JSON
    all_data = {
        "response_criteria": get_all_response_criteria(),
        "study_templates": get_all_study_templates(),
        "therapy_modules": get_all_therapy_modules(),
        "biomarker_endpoints": get_all_biomarker_endpoints(),
        "baseline_variables": get_all_baseline_variables(),
        "tfl_templates": get_all_tfl_templates()
    }

    output_path = Path(__file__).parent / "output" / "oncology_reference_data.json"
    with open(output_path, 'w') as f:
        json.dump(all_data, f, indent=2)

    print(f"\n✅ Exported to: {output_path}")
