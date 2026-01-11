"""
Comprehensive SAP Elements for ALL Phase 2/3 Oncology Studies

This module contains ALL required SAP elements based on:
- JAMA 55-item SAP guideline (Gamble et al. 2017)
- ICH E9/E9(R1) requirements
- FDA Oncology Guidance Documents
- EMA scientific guidelines
- Industry best practices (TransCelerate SAP template)

For complete SAP generation across all oncology study types.
"""

# =============================================================================
# STUDY DEFINITIONS (Required for all studies)
# =============================================================================
STUDY_DEFINITIONS = {
    "description": "Standard study definitions required in every SAP (Section 5 equivalent)",

    "time_definitions": {
        "study_day_0": {
            "definition": "Day of first dose of study treatment",
            "variants": {
                "standard": "Day of first dose of investigational product",
                "cart": "Day of CAR-T cell infusion",
                "conditioning": "Day of first dose of conditioning chemotherapy"
            }
        },
        "study_day_minus_1": {
            "definition": "Day prior to Study Day 0 (last day before treatment)"
        },
        "baseline": {
            "definition": "Last non-missing value prior to first dose of study treatment",
            "variants": {
                "efficacy": "Last assessment prior to first dose",
                "safety": "Last value prior to first dose of study treatment",
                "cart": "Last value prior to conditioning chemotherapy OR prior to infusion (specify)"
            }
        },
        "on_study_period": {
            "definition": "Time from first dose (or enrollment) to last contact/death",
            "components": ["enrollment", "treatment period", "follow-up period"]
        },
        "end_of_study": {
            "definition": "Last subject last visit OR end of follow-up period",
            "variants": {
                "standard": "Last subject completes end-of-treatment visit",
                "ltfu": "End of long-term follow-up (e.g., 5 years, 15 years for CAR-T)"
            }
        },
        "study_enrollment": {
            "variants": {
                "standard": "Date of informed consent",
                "randomized": "Date of randomization",
                "cart": "Date of leukapheresis/apheresis"
            }
        }
    },

    "follow_up_definitions": {
        "actual_follow_up_time": {
            "definition": "Time from first dose to death or last known contact",
            "calculation": "Date of death or last contact - Date of first dose + 1"
        },
        "potential_follow_up_time": {
            "definition": "Time from first dose to data cutoff date (all subjects)",
            "calculation": "Data cutoff date - Date of first dose + 1"
        },
        "follow_up_time_for_response": {
            "method": "Reverse Kaplan-Meier",
            "reference": "Schemper M, Smith TL. Control Clin Trials. 1996;17:343-346",
            "description": "Censoring patients at time of event (PD/death) to estimate follow-up"
        }
    },

    "safety_definitions": {
        "teae": {
            "definition": "Treatment-emergent adverse event",
            "criteria": "AE with onset on or after first dose of study treatment",
            "variants": {
                "standard": "Onset on/after first dose through [X days] after last dose",
                "cart": "Onset on/after CAR-T infusion (Day 0)",
                "conditioning": "Onset on/after first dose of conditioning chemotherapy"
            }
        },
        "related_ae": {
            "definition": "AE assessed by investigator as related to study treatment",
            "categories": ["related", "possibly related", "not related"]
        },
        "sae": {
            "definition": "Serious adverse event meeting ICH criteria",
            "criteria": ["death", "life-threatening", "hospitalization", "disability",
                        "congenital anomaly", "medically important"]
        },
        "aesi": {
            "definition": "Adverse event of special interest",
            "description": "Protocol-defined AEs requiring special monitoring"
        }
    },

    "event_derivations": {
        "time_to_onset": {
            "definition": "Time from first dose to AE onset",
            "calculation": "AE start date - Date of first dose"
        },
        "duration_of_event": {
            "definition": "Duration of adverse event",
            "calculation": "AE end date - AE start date + 1",
            "note": "Set to missing if ongoing or end date missing"
        }
    }
}

# =============================================================================
# EXPOSURE ANALYSIS SPECIFICATIONS
# =============================================================================
EXPOSURE_ANALYSIS = {
    "description": "Drug exposure analysis specifications",

    "dose_summaries": {
        "actual_dose": {
            "definition": "Total amount of drug actually administered",
            "statistics": ["mean", "SD", "median", "range", "IQR"]
        },
        "planned_dose": {
            "definition": "Protocol-specified dose",
            "calculation": "Per protocol dose × planned cycles/duration"
        },
        "relative_dose_intensity": {
            "definition": "Actual dose / Planned dose × 100%",
            "interpretation": "Measure of dose compliance"
        },
        "dose_modifications": {
            "categories": ["dose reductions", "dose delays", "dose interruptions"]
        }
    },

    "bsa_adjusted_dosing": {
        "description": "Body surface area adjusted dosing (for chemotherapy)",
        "formula": "Actual dose (mg) = Dose per m² × BSA",
        "bsa_calculation": {
            "Mosteller": "√(height_cm × weight_kg / 3600)",
            "DuBois": "0.007184 × height_cm^0.725 × weight_kg^0.425"
        },
        "summaries": [
            "Total dose administered (mg)",
            "Dose per m² (mg/m²)",
            "Number of cycles",
            "% of planned dose received"
        ]
    },

    "weight_adjusted_dosing": {
        "description": "Weight-based dosing (for biologics, CAR-T)",
        "formula": "Actual dose = Dose per kg × weight",
        "summaries": [
            "Total cells/mg administered",
            "Dose per kg",
            "% within ±10% of planned dose"
        ]
    },

    "cart_specific_exposure": {
        "total_car_t_cells": {
            "definition": "Total number of CAR-positive T cells infused",
            "units": "cells or ×10^6 cells"
        },
        "total_t_cells": {
            "definition": "Total number of T cells (CAR+ and CAR-) infused"
        },
        "car_t_dose_per_kg": {
            "definition": "CAR-T cells per kilogram body weight",
            "units": "cells/kg or ×10^6 cells/kg"
        }
    }
}

# =============================================================================
# CAR-T MANUFACTURING METRICS
# =============================================================================
CART_MANUFACTURING_METRICS = {
    "description": "CAR-T manufacturing and logistics metrics",

    "timing_metrics": {
        "leukapheresis_to_receipt": {
            "definition": "Days from leukapheresis to product receipt at site",
            "statistics": ["mean", "SD", "median", "range"]
        },
        "leukapheresis_to_release": {
            "definition": "Days from leukapheresis to product release from manufacturing",
            "statistics": ["mean", "SD", "median", "range"]
        },
        "leukapheresis_to_infusion": {
            "definition": "Days from leukapheresis to CAR-T infusion (turnaround time)",
            "statistics": ["mean", "SD", "median", "range"],
            "also_called": "Vein-to-vein time"
        },
        "receipt_to_infusion": {
            "definition": "Days from product receipt at site to infusion"
        }
    },

    "manufacturing_success": {
        "definition": "Proportion of subjects with successful product manufacturing",
        "formula": "N subjects with product released / N subjects leukapheresed × 100%",
        "out_of_spec": {
            "definition": "Product manufactured but not meeting specifications",
            "summary": "N and % with out-of-spec product"
        }
    },

    "bridging_therapy": {
        "definition": "Therapy given between leukapheresis and conditioning",
        "summaries": [
            "Type of bridging (chemotherapy, radiation, none)",
            "Response to bridging therapy",
            "Duration of bridging"
        ]
    }
}

# =============================================================================
# SUBSEQUENT THERAPY TRACKING
# =============================================================================
SUBSEQUENT_THERAPY = {
    "description": "Subsequent anti-cancer therapy and stem cell transplant tracking",

    "subsequent_anticancer_therapy": {
        "definition": "Any anti-cancer therapy initiated after discontinuation of study treatment",
        "coding": "WHO Drug Dictionary coded term",
        "summaries": [
            "N (%) receiving any subsequent therapy",
            "Time to subsequent therapy",
            "Type of subsequent therapy (by drug class)"
        ]
    },

    "subsequent_sct": {
        "definition": "Stem cell transplant after study treatment",
        "categories": {
            "autologous": "Autologous SCT",
            "allogeneic": "Allogeneic SCT"
        },
        "summaries": [
            "N (%) receiving SCT",
            "Time from last dose to SCT",
            "Type of SCT"
        ]
    },

    "time_to_next_therapy": {
        "definition": "Time from first dose to start of next anti-cancer therapy",
        "analysis": "Kaplan-Meier, median with 95% CI"
    }
}

# =============================================================================
# ENROLLMENT SUMMARIES
# =============================================================================
ENROLLMENT_SUMMARIES = {
    "description": "Subject enrollment tracking specifications",

    "by_country": {
        "definition": "Number of subjects enrolled per country",
        "display": "N and % by country"
    },
    "by_site": {
        "definition": "Number of subjects enrolled per site",
        "display": "N and % by site (or site ranges for blinding)"
    },
    "by_region": {
        "definition": "Number of subjects enrolled per geographic region",
        "common_regions": ["North America", "Europe", "Asia-Pacific", "Rest of World"]
    },
    "enrollment_over_time": {
        "definition": "Cumulative enrollment by month",
        "display": "Line plot or table"
    }
}

# =============================================================================
# AE PERIOD ANALYSIS (CAR-T specific but applicable to others)
# =============================================================================
AE_PERIOD_ANALYSIS = {
    "description": "Adverse event analysis by time period",

    "cart_periods": {
        "early": {"days": "0-30", "description": "Acute period (CRS, ICANS peak)"},
        "intermediate": {"days": "31-92", "description": "Recovery period"},
        "late": {"days": "≥93", "description": "Long-term period"}
    },

    "standard_periods": {
        "on_treatment": {"definition": "First dose to last dose + 30 days"},
        "post_treatment": {"definition": "After on-treatment period to end of study"}
    },

    "analyses": [
        "TEAEs by period (N, %)",
        "Grade ≥3 TEAEs by period",
        "SAEs by period",
        "Fatal AEs by period",
        "AESIs by period"
    ]
}

# =============================================================================
# PROTOCOL DEVIATIONS ANALYSIS
# =============================================================================
PROTOCOL_DEVIATIONS = {
    "description": "Protocol deviation tracking and analysis",

    "categories": {
        "major": {
            "definition": "Deviations affecting subject safety or data integrity",
            "types": [
                "Entry/eligibility criteria violations",
                "Excluded medication use",
                "Non-compliance with study procedures",
                "Incorrect treatment assignment"
            ]
        },
        "minor": {
            "definition": "Deviations not affecting safety or integrity",
            "types": [
                "Visit window violations",
                "Missing assessments",
                "Administrative errors"
            ]
        }
    },

    "analysis": {
        "summary": "N (%) subjects with any deviation by category",
        "per_protocol_exclusion": "List criteria for PP population exclusion"
    }
}

# =============================================================================
# MRD ASSESSMENT (Hematologic malignancies)
# =============================================================================
MRD_ASSESSMENT = {
    "description": "Minimal residual disease assessment specifications",

    "methods": {
        "flow_cytometry": {
            "sensitivity": "10^-4 to 10^-5",
            "sample": "Bone marrow aspirate"
        },
        "ngs": {
            "sensitivity": "10^-5 to 10^-6",
            "sample": "Bone marrow aspirate or peripheral blood"
        },
        "pcr": {
            "sensitivity": "10^-4 to 10^-5",
            "sample": "Bone marrow aspirate"
        }
    },

    "endpoints": {
        "mrd_negativity_rate": {
            "definition": "Proportion achieving MRD-negative status",
            "thresholds": ["10^-4", "10^-5", "10^-6"]
        },
        "mrd_negativity_in_responders": {
            "definition": "MRD-negative rate among CR/CRi responders"
        }
    },

    "timing": {
        "assessments": "Per protocol-specified schedule",
        "typical": ["End of induction", "End of consolidation", "Month 6", "Month 12"]
    }
}

# =============================================================================
# BIOMARKER SUBGROUPS (For all tumor types)
# =============================================================================
BIOMARKER_SUBGROUPS = {
    "description": "Common biomarker-based subgroup analyses",

    "solid_tumors": {
        "PD-L1": {
            "assays": ["22C3", "28-8", "SP142", "SP263", "73-10"],
            "cutoffs": ["<1%", "1-49%", "≥50%", "TPS vs CPS"],
            "indications": ["NSCLC", "bladder", "gastric", "HNSCC"]
        },
        "TMB": {
            "definition": "Tumor mutational burden",
            "cutoffs": ["<10 mut/Mb", "≥10 mut/Mb"],
            "assays": ["FoundationOne CDx", "F1CDx"]
        },
        "MSI": {
            "categories": ["MSI-H", "MSS"],
            "assays": ["IHC", "PCR", "NGS"]
        },
        "EGFR": {
            "mutations": ["exon 19 del", "L858R", "T790M", "exon 20 ins"],
            "applicable": "NSCLC"
        },
        "ALK": {
            "categories": ["ALK-positive", "ALK-negative"],
            "applicable": "NSCLC"
        },
        "HER2": {
            "categories": ["IHC 3+", "IHC 2+/FISH+", "HER2-low"],
            "applicable": ["breast", "gastric"]
        },
        "BRCA": {
            "categories": ["BRCA mutant", "BRCA wild-type"],
            "applicable": ["breast", "ovarian", "prostate", "pancreatic"]
        },
        "KRAS": {
            "categories": ["KRAS G12C", "other KRAS", "KRAS wild-type"],
            "applicable": ["NSCLC", "colorectal"]
        }
    },

    "hematologic": {
        "cytogenetics": {
            "lymphoma": ["double-hit", "triple-hit", "MYC rearrangement"],
            "myeloma": ["high-risk: t(4;14), t(14;16), del(17p)", "standard-risk"],
            "aml": ["favorable", "intermediate", "adverse per ELN"]
        },
        "cell_of_origin": {
            "definition": "Molecular classification of DLBCL",
            "categories": ["GCB", "ABC/non-GCB", "unclassified"]
        },
        "bcma_expression": {
            "applicable": "Multiple myeloma (BCMA-directed therapy)",
            "assessment": "Flow cytometry or IHC"
        }
    }
}

# =============================================================================
# PHASE 2 SPECIFIC DESIGNS
# =============================================================================
PHASE2_DESIGNS = {
    "description": "Phase 2 specific statistical designs",

    "simon_two_stage": {
        "definition": "Optimal or minimax two-stage design for response rate",
        "parameters": {
            "p0": "Null response rate (unacceptable)",
            "p1": "Alternative response rate (acceptable)",
            "alpha": "Type I error rate",
            "beta": "Type II error rate (1 - power)"
        },
        "stages": {
            "stage1": {
                "n1": "Number of subjects in stage 1",
                "r1": "Rejection boundary (stop if ≤r1 responses)"
            },
            "stage2": {
                "n": "Total sample size",
                "r": "Final rejection boundary (reject if ≤r responses)"
            }
        },
        "analysis": "Exact binomial test against null response rate"
    },

    "flemings_single_stage": {
        "definition": "Single-stage design with exact binomial test",
        "parameters": ["p0", "p1", "alpha", "power", "n"]
    },

    "gehan_two_stage": {
        "definition": "Two-stage design for response rate estimation",
        "stage1": "Fixed sample size for precision",
        "stage2": "Additional enrollment based on stage 1 results"
    },

    "bayesian_phase2": {
        "definition": "Bayesian adaptive design with posterior probability",
        "parameters": ["prior distribution", "posterior threshold", "interim analyses"]
    }
}

# =============================================================================
# RANDOMIZATION AND STRATIFICATION (Phase 3)
# =============================================================================
RANDOMIZATION_SPECS = {
    "description": "Randomization and stratification specifications",

    "randomization_methods": {
        "permuted_blocks": {
            "definition": "Block randomization with random block sizes",
            "block_sizes": "Typically 4, 6, or 8 (or combination)"
        },
        "stratified": {
            "definition": "Randomization stratified by key prognostic factors",
            "implementation": "IRT/IWRS system"
        },
        "dynamic": {
            "definition": "Minimization or covariate-adaptive randomization",
            "use": "When many stratification factors"
        }
    },

    "stratification_in_analysis": {
        "stratified_log_rank": {
            "definition": "Log-rank test stratified by randomization factors",
            "use": "Primary analysis of TTE endpoints"
        },
        "stratified_cmh": {
            "definition": "Cochran-Mantel-Haenszel test stratified",
            "use": "Response rate comparisons"
        },
        "stratified_cox": {
            "definition": "Stratified Cox model",
            "use": "HR estimation with stratification"
        }
    }
}

# =============================================================================
# COVID-19 PROTOCOL VARIATIONS
# =============================================================================
COVID19_VARIATIONS = {
    "description": "COVID-19 pandemic adaptations for clinical trials",

    "assessment_modifications": {
        "remote_assessments": {
            "definition": "Assessments conducted via telemedicine or phone",
            "applicable": ["safety calls", "QoL assessments", "symptom checks"]
        },
        "delayed_assessments": {
            "definition": "Assessments with extended visit windows due to COVID",
            "handling": "Document as protocol deviation, include in sensitivity analyses"
        },
        "local_labs": {
            "definition": "Lab assessments performed at local/home facilities",
            "handling": "Document in data collection, note in baseline tables"
        }
    },

    "treatment_modifications": {
        "treatment_delays": {
            "definition": "Treatment delays due to COVID-19 restrictions",
            "summary": "Median duration of COVID-related delays"
        },
        "dose_modifications": {
            "definition": "Dose changes due to COVID-19 exposure/infection",
            "summary": "N (%) with COVID-related dose modifications"
        }
    },

    "analysis_considerations": {
        "sensitivity_analyses": [
            "Exclude subjects with treatment delays >X weeks due to COVID",
            "Exclude COVID-19 deaths from efficacy analysis",
            "Censor at COVID-19-related treatment discontinuation"
        ],
        "covid_ae_reporting": {
            "definition": "COVID-19 as adverse event or separate section",
            "coding": "COVID-19 MedDRA PTs: COVID-19, SARS-CoV-2 test positive"
        }
    }
}

# =============================================================================
# SENSITIVITY ANALYSES CATALOG
# =============================================================================
SENSITIVITY_ANALYSES = {
    "description": "Standard sensitivity analyses for oncology trials",

    "tte_sensitivity": {
        "censoring_alternatives": [
            {"name": "Censor at new therapy", "description": "Censor PFS at start of new anti-cancer therapy"},
            {"name": "Censor at missed visits", "description": "Censor if >2 consecutive missed assessments"},
            {"name": "Treat as event", "description": "Count death without documented PD as event"},
            {"name": "Investigator assessment", "description": "Use investigator assessment instead of IRC"}
        ],
        "population_alternatives": [
            {"name": "Per protocol", "description": "Subjects without major protocol deviations"},
            {"name": "Completers", "description": "Subjects completing minimum treatment cycles"},
            {"name": "As randomized", "description": "Analyze by assigned arm (ITT principle)"}
        ],
        "model_alternatives": [
            {"name": "Unstratified", "description": "Without stratification factors"},
            {"name": "Multivariate Cox", "description": "Adjust for baseline covariates"},
            {"name": "Parametric", "description": "Weibull, log-normal, or other parametric models"}
        ]
    },

    "response_sensitivity": {
        "evaluability": [
            {"name": "Evaluable for response", "description": "At least one post-baseline assessment"},
            {"name": "Full analysis set", "description": "All treated subjects, non-evaluable = non-responder"}
        ],
        "confirmation": [
            {"name": "Unconfirmed response", "description": "Best response regardless of confirmation"},
            {"name": "Confirmed response", "description": "CR/PR confirmed ≥4 weeks apart"}
        ]
    },

    "missing_data_sensitivity": [
        {"name": "Complete case", "description": "Exclude subjects with missing data"},
        {"name": "LOCF", "description": "Last observation carried forward"},
        {"name": "BOCF", "description": "Baseline observation carried forward"},
        {"name": "WOCF", "description": "Worst observation carried forward"},
        {"name": "Multiple imputation", "description": "MI with appropriate assumptions"},
        {"name": "Tipping point", "description": "Vary imputation assumptions to find decision boundary"}
    ]
}

# =============================================================================
# MULTIPLICITY ADJUSTMENTS
# =============================================================================
MULTIPLICITY_ADJUSTMENTS = {
    "description": "Multiple testing correction methods",

    "hierarchical_testing": {
        "definition": "Fixed sequence testing of ordered hypotheses",
        "procedure": "Test H1, if rejected test H2, etc.",
        "use_case": "Multiple endpoints with clinical priority ordering",
        "example": "Test OS first, if significant then test PFS, then ORR"
    },

    "gatekeeping": {
        "definition": "Structured hypothesis testing with logical constraints",
        "types": {
            "serial": "Sequential gates - must pass all previous",
            "parallel": "Simultaneous gates with alpha splitting",
            "tree": "Complex structures with branches"
        }
    },

    "alpha_splitting": {
        "bonferroni": {
            "formula": "α/k for k tests",
            "conservativeness": "Most conservative"
        },
        "holm": {
            "definition": "Step-down Bonferroni",
            "procedure": "Order p-values, compare to α/(k-i+1)"
        },
        "hochberg": {
            "definition": "Step-up procedure",
            "assumption": "Requires non-negative dependence"
        },
        "hommel": {
            "definition": "Modified Hochberg procedure",
            "benefit": "More powerful than Hochberg"
        },
        "fallback": {
            "definition": "Weighted Bonferroni with recycling",
            "use_case": "When endpoints have different importance weights"
        }
    },

    "graphical_approaches": {
        "definition": "Visual representation of alpha propagation",
        "reference": "Bretz et al. 2009",
        "components": ["nodes (hypotheses)", "edges (alpha transfer)", "weights"]
    },

    "group_sequential": {
        "definition": "Alpha spending at interim analyses",
        "spending_functions": {
            "OBrien_Fleming": "Conservative early, liberal late",
            "Pocock": "Equal alpha at each look",
            "Hwang_Shih_DeCani": "Flexible parameter γ"
        }
    }
}

# =============================================================================
# INTERIM ANALYSIS AND DSMB
# =============================================================================
INTERIM_ANALYSIS = {
    "description": "Interim analysis specifications",

    "timing": {
        "event_driven": {
            "definition": "Interim at target number of events",
            "example": "IA at 50%, 75% of target OS events"
        },
        "calendar_driven": {
            "definition": "Interim at fixed calendar times",
            "example": "Every 6 months after FPI"
        },
        "information_fraction": {
            "definition": "Based on accumulated statistical information",
            "calculation": "Events observed / Total planned events"
        }
    },

    "futility": {
        "binding": {
            "definition": "Must stop if futility boundary crossed",
            "impact": "Preserves Type I error exactly"
        },
        "non_binding": {
            "definition": "Option to continue despite futility",
            "impact": "May inflate Type I error slightly"
        },
        "conditional_power": {
            "definition": "Probability of significant result given current data",
            "threshold": "Typically stop if CP <10-20%"
        }
    },

    "dsmb_charter_elements": [
        "Frequency of meetings",
        "Access to unblinded data",
        "Stopping guidelines (efficacy, futility, safety)",
        "Recommendation procedures",
        "Communication with sponsor"
    ]
}

# =============================================================================
# QoL AND PRO ANALYSIS
# =============================================================================
QOL_PRO_ANALYSIS = {
    "description": "Quality of Life and Patient-Reported Outcomes analysis",

    "common_instruments": {
        "oncology_general": {
            "EORTC_QLQ_C30": {
                "domains": ["Global QoL", "Functional scales (5)", "Symptom scales (9)"],
                "scoring": "Linear transformation to 0-100",
                "MID": "5-10 points typically"
            },
            "FACT_G": {
                "domains": ["Physical", "Social", "Emotional", "Functional"],
                "scoring": "Sum of items",
                "MID": "3-7 points"
            }
        },
        "disease_specific": {
            "FACT_Lym": "Lymphoma-specific module",
            "EORTC_QLQ_MY20": "Multiple myeloma module",
            "FACT_L": "Lung cancer module",
            "FACT_B": "Breast cancer module"
        },
        "symptom_scales": {
            "BFI": "Brief Fatigue Inventory",
            "BPI": "Brief Pain Inventory",
            "MDASI": "MD Anderson Symptom Inventory"
        },
        "utility": {
            "EQ_5D_5L": {
                "domains": ["Mobility", "Self-care", "Activities", "Pain", "Anxiety"],
                "output": "Health utility index (0-1)",
                "use": "Health economic analysis, QALY calculation"
            }
        }
    },

    "analysis_methods": {
        "change_from_baseline": {
            "method": "Mixed model repeated measures (MMRM)",
            "model": "Change ~ Treatment + Time + Treatment×Time + Baseline + Strata",
            "endpoint": "Mean change at each timepoint"
        },
        "time_to_deterioration": {
            "definition": "Time from randomization to confirmed clinically meaningful decline",
            "decline_definition": "Drop ≥MID from baseline with confirmation",
            "analysis": "Kaplan-Meier, stratified log-rank"
        },
        "responder_analysis": {
            "definition": "Proportion with improvement ≥MID",
            "method": "CMH test or logistic regression"
        }
    },

    "compliance_handling": {
        "definition": "Address missing PRO assessments",
        "methods": [
            "Report compliance rates by visit and arm",
            "Pattern mixture models",
            "Sensitivity analyses for informative missingness"
        ]
    }
}

# =============================================================================
# HEALTHCARE UTILIZATION
# =============================================================================
HEALTHCARE_UTILIZATION = {
    "description": "Healthcare resource utilization analysis",

    "hospitalization": {
        "metrics": [
            "N (%) subjects hospitalized",
            "Number of hospitalizations per subject",
            "Length of stay (days)",
            "ICU admissions (N, %)",
            "ICU length of stay"
        ],
        "analysis": "Negative binomial regression for counts, Kaplan-Meier for time to first"
    },

    "emergency_visits": {
        "metrics": [
            "N (%) with ED visits",
            "Number of ED visits per subject"
        ]
    },

    "outpatient_visits": {
        "metrics": [
            "Number of outpatient visits",
            "Telephone/telemedicine contacts"
        ]
    },

    "cart_specific": {
        "hospitalization_for_crs_icans": {
            "definition": "Hospitalization specifically for CRS or neurologic toxicity management",
            "metrics": ["N (%)", "Duration", "ICU admission"]
        },
        "tocilizumab_use": {
            "definition": "Tocilizumab doses for CRS management",
            "metrics": ["N (%) receiving", "Number of doses"]
        },
        "corticosteroid_use": {
            "definition": "Corticosteroid use for CRS/ICANS",
            "metrics": ["N (%) receiving", "Duration", "Peak dose"]
        }
    }
}

# =============================================================================
# ESTIMAND FRAMEWORK (ICH E9 R1)
# =============================================================================
ESTIMAND_FRAMEWORK = {
    "description": "ICH E9(R1) Estimand framework components",

    "components": {
        "population": {
            "definition": "Target population for inference",
            "examples": ["All randomized", "Treated", "Biomarker positive"]
        },
        "treatment": {
            "definition": "Treatment conditions being compared",
            "examples": ["Assigned treatment", "Treatment actually received"]
        },
        "endpoint": {
            "definition": "Variable measured for each subject",
            "examples": ["Survival time", "Response status", "Change in score"]
        },
        "intercurrent_events": {
            "definition": "Events affecting interpretation or existence of endpoint",
            "examples": ["Treatment discontinuation", "Use of rescue therapy", "Death"]
        },
        "summary_measure": {
            "definition": "Population-level summary",
            "examples": ["Hazard ratio", "Difference in means", "Odds ratio"]
        }
    },

    "strategies_for_intercurrent_events": {
        "treatment_policy": {
            "definition": "Value of endpoint used regardless of intercurrent event",
            "example": "Include all deaths in OS analysis regardless of cause",
            "analysis": "Standard ITT"
        },
        "composite": {
            "definition": "Intercurrent event is part of endpoint",
            "example": "Death (any cause) is included as PFS event"
        },
        "hypothetical": {
            "definition": "Estimate what would happen if intercurrent event had not occurred",
            "example": "Estimate PFS if subsequent therapy not given",
            "analysis": "G-computation, inverse probability weighting"
        },
        "principal_stratum": {
            "definition": "Estimate effect in subgroup where IE would not occur",
            "example": "Effect in patients who would not discontinue treatment",
            "analysis": "Principal stratification methods"
        },
        "while_on_treatment": {
            "definition": "Response up to time of intercurrent event",
            "example": "PFS while on assigned treatment (censor at discontinuation)"
        }
    }
}

# =============================================================================
# PK/PD ANALYSIS (for applicable studies)
# =============================================================================
PK_PD_ANALYSIS = {
    "description": "Pharmacokinetic and pharmacodynamic analysis",

    "pk_parameters": {
        "exposure_metrics": {
            "Cmax": "Maximum observed concentration",
            "Cmin": "Minimum observed (trough) concentration",
            "AUC": "Area under the concentration-time curve",
            "AUCtau": "AUC over dosing interval",
            "AUCinf": "AUC extrapolated to infinity",
            "Tmax": "Time to maximum concentration",
            "t_half": "Terminal elimination half-life",
            "CL": "Clearance",
            "Vd": "Volume of distribution"
        },
        "calculation_methods": {
            "NCA": "Non-compartmental analysis (standard)",
            "population_PK": "Population pharmacokinetic modeling (nonlinear mixed effects)"
        }
    },

    "pk_populations": {
        "pk_analysis_set": "Subjects with at least one evaluable PK sample",
        "pk_evaluable": "Subjects with complete PK sampling"
    },

    "exposure_response": {
        "efficacy": {
            "definition": "Relationship between exposure and efficacy endpoint",
            "methods": ["Logistic regression", "Cox regression", "E-R modeling"]
        },
        "safety": {
            "definition": "Relationship between exposure and safety outcomes",
            "methods": ["Logistic regression", "Poisson regression"]
        }
    },

    "cart_specific_pk": {
        "transgene_levels": {
            "definition": "CAR transgene copies per μg genomic DNA or per mL blood",
            "parameters": ["Cmax", "Tmax", "AUC0-28d", "persistence"]
        },
        "expansion_kinetics": {
            "definition": "CAR-T cell expansion pattern",
            "metrics": ["Peak expansion", "Time to peak", "Duration of persistence"]
        }
    }
}

# =============================================================================
# SUBGROUP ANALYSIS SPECIFICATIONS
# =============================================================================
SUBGROUP_ANALYSIS_SPECS = {
    "description": "Standard subgroup analysis specifications",

    "pre_specified_subgroups": {
        "demographic": [
            {"factor": "Age", "categories": ["<65 vs ≥65", "<75 vs ≥75"]},
            {"factor": "Sex", "categories": ["Male vs Female"]},
            {"factor": "Race", "categories": ["White", "Black", "Asian", "Other"]},
            {"factor": "ECOG PS", "categories": ["0 vs 1", "0-1 vs 2"]},
            {"factor": "Region", "categories": ["North America", "Europe", "Asia", "ROW"]}
        ],
        "disease": [
            {"factor": "Stage", "categories": "Per disease staging system"},
            {"factor": "Histology", "categories": "Disease-specific"},
            {"factor": "Number of prior therapies", "categories": ["1", "2", "≥3"]},
            {"factor": "Refractory status", "categories": ["Refractory to last therapy", "Relapsed"]}
        ]
    },

    "forest_plot": {
        "definition": "Visual display of subgroup treatment effects",
        "elements": [
            "Subgroup definition",
            "N per arm",
            "HR/OR with 95% CI",
            "P-value for interaction"
        ],
        "interpretation": "Exploratory - not powered for individual subgroups"
    },

    "interaction_testing": {
        "definition": "Test for treatment × subgroup interaction",
        "method": "Add interaction term to model",
        "caution": "Multiple comparisons - interpret with caution"
    }
}

# =============================================================================
# DATA HANDLING RULES
# =============================================================================
DATA_HANDLING_RULES = {
    "description": "Standard data handling and derivation rules",

    "date_imputation": {
        "partial_dates": {
            "description": "Imputation for incomplete dates",
            "rules": {
                "start_dates": {
                    "missing_day": "Use day 1 of month (conservative for duration)",
                    "missing_month_day": "Use January 1 of year",
                    "alternative": "Use day 15 (midpoint imputation)"
                },
                "end_dates": {
                    "missing_day": "Use last day of month (conservative for duration)",
                    "missing_month_day": "Use December 31 of year"
                },
                "ae_start": {
                    "rule": "Impute to make AE treatment-emergent if ambiguous",
                    "rationale": "Conservative for safety reporting"
                }
            }
        },
        "completely_missing": {
            "ae_dates": "Exclude from time-to-onset calculations, include in incidence",
            "lab_dates": "Use scheduled visit date if available"
        }
    },

    "lab_data": {
        "unit_conversion": {
            "definition": "Convert all values to standard units",
            "requirement": "Use single standard unit per parameter"
        },
        "reference_ranges": {
            "definition": "Use central lab reference ranges for grading",
            "alternative": "CTC/CTCAE criteria for toxicity grading"
        },
        "multiple_values": {
            "same_day": "Use worst value for toxicity, mean for continuous endpoints",
            "baseline": "Use last non-missing value before first dose"
        }
    },

    "outliers": {
        "detection": [
            "Box-plot method (>1.5 IQR from Q1/Q3)",
            "Studentized residuals (|r| > 3)",
            "Medical plausibility review"
        ],
        "handling": {
            "document": "List all values flagged as outliers",
            "primary": "Include in primary analysis (ITT principle)",
            "sensitivity": "Repeat analysis excluding outliers"
        }
    }
}

# =============================================================================
# BLINDING CONSIDERATIONS
# =============================================================================
BLINDING_CONSIDERATIONS = {
    "description": "Blinding and unblinding specifications",

    "maintained_blinding": {
        "irc_assessment": {
            "definition": "Independent radiology review maintains treatment blind",
            "use": "Primary efficacy endpoint in randomized studies"
        },
        "endpoint_adjudication": {
            "definition": "Blinded endpoint adjudication committee",
            "use": "Cause of death, cardiovascular events"
        }
    },

    "unblinding_triggers": {
        "safety": "Emergency unblinding for subject safety",
        "interim": "DSMB unblinding for interim analysis",
        "regulatory": "Regulatory request"
    },

    "open_label_considerations": {
        "assessment_bias": {
            "mitigation": "IRC for response assessment",
            "analysis": "Sensitivity analyses with investigator assessment"
        },
        "performance_bias": {
            "mitigation": "Standardized supportive care",
            "documentation": "Document concomitant medications by arm"
        }
    }
}

# =============================================================================
# DEMOGRAPHICS AND BASELINE CHARACTERISTICS
# =============================================================================
DEMOGRAPHICS_BASELINE = {
    "description": "Demographics and baseline characteristics specifications",

    "demographic_variables": {
        "age": {
            "statistics": ["N", "Mean", "SD", "Median", "Min", "Max"],
            "categories": ["<65 vs ≥65", "<75 vs ≥75"],
            "source": "CRF demographic page"
        },
        "sex": {
            "categories": ["Male", "Female"],
            "statistics": ["N", "%"]
        },
        "race": {
            "categories": ["White", "Black or African American", "Asian", "American Indian/Alaska Native",
                          "Native Hawaiian/Pacific Islander", "Multiple", "Other", "Not reported"],
            "statistics": ["N", "%"]
        },
        "ethnicity": {
            "categories": ["Hispanic or Latino", "Not Hispanic or Latino", "Not reported"],
            "statistics": ["N", "%"]
        },
        "region": {
            "categories": ["North America", "Europe", "Asia-Pacific", "Rest of World"],
            "statistics": ["N", "%"]
        },
        "weight": {
            "statistics": ["N", "Mean", "SD", "Median", "Min", "Max"],
            "units": "kg"
        },
        "height": {
            "statistics": ["N", "Mean", "SD", "Median", "Min", "Max"],
            "units": "cm"
        },
        "bsa": {
            "statistics": ["N", "Mean", "SD", "Median", "Min", "Max"],
            "units": "m²",
            "formula": "Mosteller or DuBois"
        },
        "bmi": {
            "statistics": ["N", "Mean", "SD", "Median", "Min", "Max"],
            "units": "kg/m²"
        }
    },

    "baseline_disease": {
        "ecog_ps": {
            "categories": ["0", "1", "2"],
            "statistics": ["N", "%"],
            "source": "ECOG Performance Status scale"
        },
        "karnofsky": {
            "categories": ["100", "90", "80", "70", "60", "50"],
            "statistics": ["N", "%"],
            "applicable": "Alternative to ECOG"
        },
        "disease_stage": {
            "description": "Per appropriate staging system",
            "statistics": ["N", "%"]
        },
        "time_since_diagnosis": {
            "statistics": ["N", "Mean", "SD", "Median", "Min", "Max"],
            "units": "months"
        },
        "measurable_disease": {
            "categories": ["Yes", "No"],
            "statistics": ["N", "%"]
        },
        "metastatic_sites": {
            "categories": ["Per disease-specific sites"],
            "statistics": ["N", "%"]
        },
        "target_lesions": {
            "statistics": ["N", "Mean", "SD", "Median", "Min", "Max"],
            "description": "Number of target lesions at baseline"
        },
        "sum_of_diameters": {
            "statistics": ["N", "Mean", "SD", "Median", "Min", "Max"],
            "units": "mm",
            "description": "Sum of longest diameters of target lesions"
        }
    }
}

# =============================================================================
# PRIOR THERAPY ANALYSIS
# =============================================================================
PRIOR_THERAPY_ANALYSIS = {
    "description": "Prior anti-cancer therapy analysis specifications",

    "summary_tables": {
        "number_of_prior_lines": {
            "definition": "Number of prior systemic therapy regimens",
            "categories": ["1", "2", "3", "≥4"],
            "statistics": ["N", "%", "Median", "Range"]
        },
        "type_of_prior_therapy": {
            "categories": [
                "Chemotherapy",
                "Immunotherapy",
                "Targeted therapy",
                "Hormonal therapy",
                "Radiation therapy",
                "Surgery",
                "Stem cell transplant"
            ],
            "statistics": ["N", "%"]
        },
        "specific_prior_agents": {
            "description": "By WHO Drug Dictionary coded term",
            "statistics": ["N", "%"],
            "threshold": "≥5% of subjects"
        }
    },

    "hematologic_specific": {
        "prior_anti_cd20": {
            "categories": ["Rituximab", "Obinutuzumab", "Other anti-CD20"],
            "statistics": ["N", "%"]
        },
        "prior_alkylating": {
            "categories": ["Bendamustine", "Cyclophosphamide", "Other"],
            "statistics": ["N", "%"]
        },
        "prior_asct": {
            "definition": "Prior autologous stem cell transplant",
            "statistics": ["N", "%"]
        },
        "prior_allo_sct": {
            "definition": "Prior allogeneic stem cell transplant",
            "statistics": ["N", "%"]
        },
        "refractory_status": {
            "categories": ["Primary refractory", "Refractory to last therapy", "Relapsed"],
            "definitions": {
                "primary_refractory": "No response (SD/PD) to first-line therapy",
                "refractory_to_last": "PD as best response or PD within 6 months of last therapy",
                "relapsed": "Response to last therapy followed by progression"
            }
        },
        "double_refractory": {
            "definition": "Refractory to both anti-CD20 and alkylating agent",
            "applicable": "Lymphoma"
        }
    },

    "solid_tumor_specific": {
        "prior_surgery": {
            "categories": ["Complete resection", "Partial resection", "Biopsy only", "None"],
            "statistics": ["N", "%"]
        },
        "prior_radiation": {
            "categories": ["Yes", "No"],
            "details": ["Site", "Total dose (Gy)", "Fractions"],
            "statistics": ["N", "%"]
        },
        "prior_targeted_therapy": {
            "description": "By specific mechanism",
            "examples": ["Prior EGFR TKI", "Prior ALK inhibitor", "Prior PARP inhibitor"],
            "statistics": ["N", "%"]
        }
    },

    "response_to_prior_therapy": {
        "best_response_to_last": {
            "categories": ["CR", "PR", "SD", "PD", "Not evaluable"],
            "statistics": ["N", "%"]
        },
        "duration_of_prior_response": {
            "statistics": ["N", "Median", "Range"],
            "units": "months"
        }
    }
}

# =============================================================================
# CONCOMITANT MEDICATIONS ANALYSIS
# =============================================================================
CONCOMITANT_MEDICATIONS = {
    "description": "Concomitant and prohibited medications analysis",

    "coding": {
        "dictionary": "WHO Drug Dictionary",
        "classification": "ATC (Anatomical Therapeutic Chemical) classification",
        "levels": ["ATC Level 2", "ATC Level 3", "Preferred Term"]
    },

    "summary_tables": {
        "prior_medications": {
            "definition": "Medications taken before first dose of study treatment",
            "period": "Within 30 days prior to first dose (or per protocol)",
            "display": "By ATC Level 2 and Preferred Term",
            "threshold": "≥5% of subjects"
        },
        "concomitant_medications": {
            "definition": "Medications taken during study treatment",
            "period": "From first dose to 30 days after last dose",
            "display": "By ATC Level 2 and Preferred Term",
            "threshold": "≥5% of subjects"
        },
        "post_treatment_medications": {
            "definition": "Medications started after end of study treatment",
            "period": "After 30 days from last dose",
            "display": "By ATC Level 2"
        }
    },

    "special_categories": {
        "supportive_care": {
            "growth_factors": ["G-CSF", "GM-CSF", "EPO"],
            "transfusions": ["RBC", "Platelet", "Plasma"],
            "antiemetics": ["5-HT3 antagonists", "NK1 antagonists", "Corticosteroids"],
            "antimicrobials": ["Prophylactic", "Therapeutic"]
        },
        "cart_supportive_care": {
            "tocilizumab": {
                "statistics": ["N (%)", "Number of doses", "Time to first dose"],
                "indication": "CRS management"
            },
            "corticosteroids": {
                "statistics": ["N (%)", "Duration", "Peak dose"],
                "indication": "CRS or ICANS management"
            },
            "vasopressors": {
                "statistics": ["N (%)", "Duration"],
                "indication": "Hypotension management"
            },
            "anti_seizure": {
                "statistics": ["N (%)"],
                "indication": "ICANS seizure prophylaxis/treatment"
            }
        }
    },

    "prohibited_medications": {
        "definition": "Protocol-specified prohibited medications",
        "handling": "List any use as protocol deviation",
        "display": "By subject with dates and reason"
    }
}

# =============================================================================
# MEDICAL HISTORY ANALYSIS
# =============================================================================
MEDICAL_HISTORY = {
    "description": "Medical history and concurrent conditions analysis",

    "coding": {
        "dictionary": "MedDRA",
        "level": "System Organ Class (SOC) and Preferred Term (PT)",
        "version": "Specify MedDRA version used"
    },

    "summary_tables": {
        "by_soc": {
            "display": "N (%) by SOC",
            "sorting": "Alphabetical or by frequency"
        },
        "by_pt": {
            "display": "N (%) by PT within SOC",
            "threshold": "≥5% of subjects"
        }
    },

    "relevant_conditions": {
        "cardiovascular": ["Hypertension", "CAD", "Heart failure", "Arrhythmia"],
        "diabetes": ["Type 1", "Type 2", "Pre-diabetes"],
        "renal": ["CKD stage", "eGFR category"],
        "hepatic": ["Hepatitis", "Cirrhosis", "Elevated LFTs"],
        "autoimmune": ["Relevant for immunotherapy trials"]
    }
}

# =============================================================================
# DEATH AND SURVIVAL ANALYSIS
# =============================================================================
DEATH_ANALYSIS = {
    "description": "Death, cause of death, and survival analysis specifications",

    "death_summary": {
        "overall_deaths": {
            "statistics": ["N (%)", "Rate per 100 patient-years"],
            "timing": ["On treatment", "Within 30 days", "Within 100 days", "Any time"]
        },
        "primary_cause_of_death": {
            "categories": [
                "Disease progression",
                "Adverse event",
                "Other medical condition",
                "Unknown"
            ],
            "statistics": ["N", "%"]
        },
        "deaths_due_to_ae": {
            "display": "List by PT with relationship to treatment",
            "adjudication": "Per investigator or adjudication committee"
        }
    },

    "survival_analysis": {
        "overall_survival": {
            "definition": "Time from first dose (or randomization) to death from any cause",
            "censoring": "Censored at last known alive date for subjects without event",
            "analysis": "Kaplan-Meier estimate, median with 95% CI"
        },
        "survival_rates": {
            "timepoints": ["6-month", "12-month", "24-month", "36-month"],
            "statistics": ["Rate", "95% CI"]
        }
    },

    "cause_of_death_adjudication": {
        "committee": "Independent endpoint adjudication committee (if applicable)",
        "categories": [
            "Disease under study",
            "Study treatment-related",
            "Related to study procedure",
            "Related to other medical condition",
            "Unknown/undetermined"
        ]
    }
}

# =============================================================================
# TUMOR RESPONSE ASSESSMENT
# =============================================================================
TUMOR_RESPONSE_ASSESSMENT = {
    "description": "Tumor response assessment methodology",

    "assessment_schedule": {
        "frequency": "Per protocol-specified schedule",
        "typical": "Every 6-12 weeks during treatment",
        "window": "±7 days from scheduled assessment"
    },

    "imaging_modality": {
        "primary": "CT scan (with contrast unless contraindicated)",
        "alternative": "MRI for specific sites",
        "pet_ct": "For lymphoma (Lugano criteria)",
        "bone_scan": "For bone metastases"
    },

    "recist_11": {
        "reference": "Eisenhauer EA et al. Eur J Cancer 2009;45:228-247",
        "applicable": "Solid tumors",
        "target_lesions": {
            "maximum": "5 total, 2 per organ",
            "minimum_size": "≥10mm (≥15mm for lymph nodes)",
            "measurement": "Longest diameter (short axis for lymph nodes)"
        },
        "non_target_lesions": {
            "definition": "All other lesions including unmeasurable",
            "assessment": "Present/Absent/Unequivocal progression"
        },
        "response_categories": {
            "CR": "Disappearance of all target lesions, LN <10mm",
            "PR": "≥30% decrease in sum of diameters",
            "PD": "≥20% increase with ≥5mm absolute increase, or new lesion",
            "SD": "Neither PR nor PD criteria met"
        }
    },

    "lugano_2014": {
        "reference": "Cheson BD et al. J Clin Oncol 2014;32:3059-3068",
        "applicable": "Lymphoma",
        "pet_scoring": {
            "5PS_scale": {
                "1": "No uptake",
                "2": "Uptake ≤ mediastinum",
                "3": "Uptake > mediastinum but ≤ liver",
                "4": "Uptake moderately > liver",
                "5": "Uptake markedly > liver or new lesions"
            },
            "response_threshold": "Score 1-3 = metabolic CR (for FDG-avid histologies)"
        }
    },

    "iwcll_2018": {
        "reference": "Hallek M et al. Blood 2018;131:2745-2760",
        "applicable": "CLL/SLL",
        "response_categories": ["CR", "CRi", "nPR", "PR", "PD", "SD"]
    },

    "imwg": {
        "reference": "Kumar S et al. Lancet Oncol 2016;17:e328-e346",
        "applicable": "Multiple myeloma",
        "response_categories": ["sCR", "CR", "VGPR", "PR", "MR", "SD", "PD"]
    },

    "irc_assessment": {
        "definition": "Independent Review Committee (blinded central review)",
        "use": "Primary efficacy endpoint in randomized studies",
        "concordance": "Compare IRC vs Investigator assessment"
    }
}

# =============================================================================
# TREATMENT COMPLIANCE AND ADHERENCE
# =============================================================================
TREATMENT_COMPLIANCE = {
    "description": "Treatment compliance and adherence specifications",

    "dose_compliance": {
        "definition": "Actual dose received / Planned dose × 100%",
        "statistics": ["Mean", "SD", "Median", "Range"],
        "categories": ["<80%", "80-100%", ">100%"]
    },

    "treatment_duration": {
        "statistics": ["N", "Mean", "SD", "Median", "Range"],
        "units": ["Days", "Weeks", "Cycles"]
    },

    "dose_modifications": {
        "reductions": {
            "definition": "Reduction from starting/planned dose",
            "statistics": ["N (%)", "Reason distribution"]
        },
        "delays": {
            "definition": "Delay beyond scheduled administration",
            "statistics": ["N (%)", "Median delay duration"]
        },
        "interruptions": {
            "definition": "Temporary discontinuation",
            "statistics": ["N (%)", "Median interruption duration"]
        }
    },

    "reasons_for_discontinuation": {
        "categories": [
            "Disease progression",
            "Adverse event",
            "Withdrawal of consent",
            "Death",
            "Lost to follow-up",
            "Physician decision",
            "Protocol deviation",
            "Other"
        ],
        "statistics": ["N", "%"]
    }
}

# =============================================================================
# CONCORDANCE ANALYSIS (IRC vs Investigator)
# =============================================================================
CONCORDANCE_ANALYSIS = {
    "description": "Response concordance between assessors",

    "overall_concordance": {
        "definition": "Agreement between IRC and Investigator on best overall response",
        "statistics": ["% agreement", "Kappa statistic with 95% CI"]
    },

    "response_concordance_matrix": {
        "display": "Cross-tabulation of IRC vs Investigator response",
        "categories": ["CR", "PR", "SD", "PD", "NE"]
    },

    "discordance_analysis": {
        "types": [
            "IRC responder, Inv non-responder",
            "IRC non-responder, Inv responder"
        ],
        "impact": "Sensitivity analysis using each assessment"
    },

    "timing_concordance": {
        "time_to_response": "Compare IRC vs Investigator TTR",
        "time_to_progression": "Compare IRC vs Investigator TTP"
    }
}

# =============================================================================
# IMMUNOGENICITY ANALYSIS
# =============================================================================
IMMUNOGENICITY_ANALYSIS = {
    "description": "Anti-drug antibody and immunogenicity analysis",

    "ada_testing": {
        "screening": {
            "method": "Validated immunoassay",
            "cutpoint": "Statistically determined from drug-naive samples"
        },
        "confirmatory": {
            "method": "Drug competition assay",
            "threshold": "Inhibition % for positive confirmation"
        },
        "titer": {
            "method": "Serial dilution",
            "reporting": "Titer value or range"
        },
        "neutralizing": {
            "method": "Cell-based or ligand-binding neutralization assay",
            "reporting": "Positive/Negative or titer"
        }
    },

    "analysis_populations": {
        "ada_evaluable": "Subjects with baseline and ≥1 post-baseline ADA sample",
        "treatment_emergent": "Negative at baseline, positive post-baseline OR "
                            "positive at baseline with ≥4-fold increase in titer"
    },

    "ada_summaries": {
        "incidence": {
            "statistics": ["N (%)", "By timepoint"],
            "categories": ["Treatment-emergent", "Treatment-boosted", "Transient", "Persistent"]
        },
        "time_to_onset": {
            "statistics": ["Median", "Range"]
        },
        "neutralizing_abs": {
            "statistics": ["N (%) of ADA-positive with NAb"]
        }
    },

    "impact_analysis": {
        "pk_impact": "Compare PK parameters in ADA+ vs ADA-",
        "efficacy_impact": "Compare efficacy in ADA+ vs ADA-",
        "safety_impact": "Compare AE incidence in ADA+ vs ADA-"
    }
}

# =============================================================================
# DATA CUTOFF SPECIFICATIONS
# =============================================================================
DATA_CUTOFF_SPECS = {
    "description": "Data cutoff date specifications",

    "cutoff_types": {
        "clinical_cutoff": {
            "definition": "Date through which clinical data are included",
            "timing": "Pre-specified or event-driven"
        },
        "database_lock": {
            "definition": "Date when database is locked for analysis",
            "activities": ["Query resolution", "Derivations complete", "Unblinding (if applicable)"]
        }
    },

    "event_driven_cutoff": {
        "primary_analysis": {
            "trigger": "Target number of events reached",
            "example": "When 200 PFS events have occurred"
        },
        "final_analysis": {
            "trigger": "Target events or minimum follow-up",
            "example": "When 350 OS events OR minimum 24 months follow-up"
        }
    },

    "data_maturity": {
        "calculation": "Events observed / Target events × 100%",
        "reporting": "Report data maturity at each analysis"
    }
}

# =============================================================================
# FOLLOW-UP ANALYSIS SPECIFICATIONS
# =============================================================================
FOLLOW_UP_ANALYSIS_SPECS = {
    "description": "Planned descriptive analyses at specified timepoints after primary analysis",

    "purpose": {
        "primary": "Provide updated efficacy and safety data with longer follow-up",
        "regulatory": "Support regulatory submissions with mature data",
        "note": "All follow-up analyses are DESCRIPTIVE only - no formal hypothesis testing"
    },

    "standard_timepoints": {
        "18_month": {
            "timing": "When all subjects have minimum 18 months follow-up from first dose/infusion",
            "typical_endpoints": ["Updated DOR", "Updated PFS", "Updated OS", "Long-term safety"],
            "analyses": [
                "Kaplan-Meier estimates with updated follow-up",
                "Landmark survival rates (12-month, 18-month)",
                "Updated response duration for responders",
                "Long-term AE summary (onset >6 months)"
            ]
        },
        "24_month": {
            "timing": "When all subjects have minimum 24 months follow-up from first dose/infusion",
            "typical_endpoints": ["Updated DOR", "Updated PFS", "Updated OS", "2-year landmark rates"],
            "analyses": [
                "Kaplan-Meier estimates with 24-month minimum follow-up",
                "Landmark survival rates (12-month, 24-month)",
                "Median follow-up time (reverse Kaplan-Meier)",
                "Long-term safety including delayed AEs"
            ]
        },
        "36_month": {
            "timing": "When all subjects have minimum 36 months follow-up",
            "typical_endpoints": ["Long-term OS", "Long-term DOR", "3-year landmark rates"],
            "analyses": [
                "3-year landmark rates for OS, PFS, DOR",
                "Long-term safety summary",
                "Plateau analysis for response durability"
            ]
        }
    },

    "cart_specific_follow_up": {
        "description": "CAR-T trials require extended follow-up per FDA guidance",
        "minimum_follow_up": "15 years recommended for gene therapy products",
        "key_analyses": [
            "Long-term B-cell recovery",
            "Persistent CAR-T cell detection",
            "Secondary malignancy monitoring",
            "Long-term hypogammaglobulinemia",
            "Delayed neurotoxicity assessment"
        ],
        "timepoints": ["Year 1", "Year 2", "Year 3", "Year 5", "Year 10", "Year 15"]
    },

    "analysis_content": {
        "efficacy_updates": {
            "tte_endpoints": [
                "Updated Kaplan-Meier curves",
                "Updated median (if not reached at primary)",
                "Landmark rates at specified timepoints",
                "Number of events / Number at risk"
            ],
            "response_updates": [
                "Updated DOR for responders",
                "Conversion rates (PR to CR)",
                "Loss of response summary"
            ]
        },
        "safety_updates": {
            "long_term_aes": "AEs with onset >6 months after treatment",
            "delayed_toxicities": "Focus on treatment-specific delayed effects",
            "deaths": "Updated death summary with causes",
            "subsequent_therapy": "Summary of subsequent anti-cancer therapies"
        }
    },

    "reporting_format": {
        "tables": [
            "Table X.1: Summary of Efficacy at [X] Months Follow-up",
            "Table X.2: Kaplan-Meier Estimates of DOR at [X] Months",
            "Table X.3: Kaplan-Meier Estimates of OS at [X] Months",
            "Table X.4: Long-term Safety Summary"
        ],
        "figures": [
            "Figure X.1: Updated Kaplan-Meier Plot of DOR",
            "Figure X.2: Updated Kaplan-Meier Plot of OS",
            "Figure X.3: Updated Swimmer Plot (responders)"
        ]
    },

    "statistical_notes": {
        "no_hypothesis_testing": "Follow-up analyses are descriptive; no p-values or formal comparisons",
        "confidence_intervals": "95% CI for all point estimates",
        "follow_up_time": "Report median follow-up using reverse Kaplan-Meier method {Schemper 1996}"
    }
}

# =============================================================================
# ORGAN FUNCTION REQUIREMENTS
# =============================================================================
ORGAN_FUNCTION_SPECS = {
    "description": "Organ function eligibility and analysis specifications",

    "hepatic_function": {
        "parameters": {
            "AST": {"ULN_multiple": [1.5, 3, 5], "units": "U/L"},
            "ALT": {"ULN_multiple": [1.5, 3, 5], "units": "U/L"},
            "total_bilirubin": {"ULN_multiple": [1.5, 2, 3], "units": "mg/dL or μmol/L"},
            "albumin": {"threshold": [3.0, 2.5], "units": "g/dL"}
        },
        "child_pugh": {
            "classes": ["A (5-6)", "B (7-9)", "C (10-15)"],
            "applicable": "Hepatic impairment studies"
        }
    },

    "renal_function": {
        "parameters": {
            "creatinine_clearance": {
                "calculation": "Cockcroft-Gault formula",
                "thresholds": [90, 60, 30, 15],
                "units": "mL/min"
            },
            "eGFR": {
                "calculation": "CKD-EPI equation",
                "thresholds": [90, 60, 45, 30, 15],
                "units": "mL/min/1.73m²"
            },
            "serum_creatinine": {
                "ULN_multiple": [1.5, 2],
                "units": "mg/dL"
            }
        },
        "ckd_stage": {
            "categories": ["G1 (≥90)", "G2 (60-89)", "G3a (45-59)", "G3b (30-44)", "G4 (15-29)", "G5 (<15)"]
        }
    },

    "hematologic_function": {
        "parameters": {
            "ANC": {"threshold": [1000, 1500], "units": "/mm³"},
            "platelet": {"threshold": [75000, 100000], "units": "/mm³"},
            "hemoglobin": {"threshold": [8, 9, 10], "units": "g/dL"}
        }
    },

    "cardiac_function": {
        "parameters": {
            "LVEF": {"threshold": [50, 45, 40], "units": "%", "method": "ECHO or MUGA"},
            "QTcF": {"threshold": [450, 470, 500], "units": "msec"}
        }
    }
}

# =============================================================================
# ANALYSIS TIMING AND WINDOWS
# =============================================================================
ANALYSIS_TIMING = {
    "description": "Analysis timing and visit window specifications",

    "visit_windows": {
        "screening": {"window": "-28 to -1 days before first dose"},
        "baseline": {"window": "≤7 days before first dose"},
        "cycle_visits": {"window": "±3 days from scheduled"},
        "end_of_treatment": {"window": "Within 30 days of last dose"},
        "follow_up": {"window": "±14 days from scheduled"}
    },

    "analysis_windows": {
        "efficacy_baseline": "Last assessment ≤7 days before first dose",
        "efficacy_post_baseline": "First assessment ≥14 days after first dose",
        "safety_baseline": "Last non-missing value before first dose",
        "safety_on_treatment": "First dose through 30 days after last dose"
    },

    "scheduled_assessment_windows": {
        "week_4": {"target": 28, "window": [22, 35]},
        "week_8": {"target": 56, "window": [50, 63]},
        "week_12": {"target": 84, "window": [78, 91]},
        "week_24": {"target": 168, "window": [154, 182]},
        "week_48": {"target": 336, "window": [322, 350]}
    }
}

# =============================================================================
# STRATIFICATION BALANCE
# =============================================================================
STRATIFICATION_BALANCE = {
    "description": "Stratification factor balance assessment",

    "balance_assessment": {
        "method": "Compare distribution of strata across arms",
        "display": "N (%) by stratification factor and arm",
        "imbalance_threshold": "Difference >10-15% considered notable"
    },

    "stratified_vs_unstratified": {
        "primary": "Use randomization strata for primary analysis",
        "sensitivity": "Unstratified analysis as sensitivity",
        "covariate_adjustment": "May adjust for imbalanced factors"
    }
}

# =============================================================================
# MASTER FUNCTION: Get all elements for a study type
# =============================================================================
def get_comprehensive_sap_elements(study_type: str = "oncology") -> dict:
    """
    Return all comprehensive SAP elements for a given study type.

    Args:
        study_type: Type of study ("oncology", "cart", "solid_tumor", "hematologic")

    Returns:
        Dictionary containing all applicable SAP element specifications
    """
    # Core elements for ALL oncology studies
    base_elements = {
        # Study Setup
        "study_definitions": STUDY_DEFINITIONS,
        "enrollment_summaries": ENROLLMENT_SUMMARIES,
        "demographics_baseline": DEMOGRAPHICS_BASELINE,
        "prior_therapy_analysis": PRIOR_THERAPY_ANALYSIS,
        "medical_history": MEDICAL_HISTORY,
        "concomitant_medications": CONCOMITANT_MEDICATIONS,
        # Efficacy
        "tumor_response_assessment": TUMOR_RESPONSE_ASSESSMENT,
        "estimand_framework": ESTIMAND_FRAMEWORK,
        "sensitivity_analyses": SENSITIVITY_ANALYSES,
        "concordance_analysis": CONCORDANCE_ANALYSIS,
        # Safety
        "exposure_analysis": EXPOSURE_ANALYSIS,
        "ae_period_analysis": AE_PERIOD_ANALYSIS,
        "death_analysis": DEATH_ANALYSIS,
        "subsequent_therapy": SUBSEQUENT_THERAPY,
        "treatment_compliance": TREATMENT_COMPLIANCE,
        # Analysis Specifications
        "protocol_deviations": PROTOCOL_DEVIATIONS,
        "multiplicity_adjustments": MULTIPLICITY_ADJUSTMENTS,
        "interim_analysis": INTERIM_ANALYSIS,
        "qol_pro_analysis": QOL_PRO_ANALYSIS,
        "healthcare_utilization": HEALTHCARE_UTILIZATION,
        "subgroup_analysis_specs": SUBGROUP_ANALYSIS_SPECS,
        "data_handling_rules": DATA_HANDLING_RULES,
        "blinding_considerations": BLINDING_CONSIDERATIONS,
        "data_cutoff_specs": DATA_CUTOFF_SPECS,
        "analysis_timing": ANALYSIS_TIMING,
        "follow_up_analysis": FOLLOW_UP_ANALYSIS_SPECS,
        "stratification_balance": STRATIFICATION_BALANCE,
        "organ_function_specs": ORGAN_FUNCTION_SPECS,
        # Special Topics
        "covid19_variations": COVID19_VARIATIONS,
        "biomarker_subgroups": BIOMARKER_SUBGROUPS,
        "phase2_designs": PHASE2_DESIGNS,
        "randomization_specs": RANDOMIZATION_SPECS,
        "pk_pd_analysis": PK_PD_ANALYSIS,
        "immunogenicity_analysis": IMMUNOGENICITY_ANALYSIS,
    }

    # Add CAR-T specific elements
    if study_type in ["cart", "cell_therapy"]:
        base_elements["cart_manufacturing_metrics"] = CART_MANUFACTURING_METRICS

    # Add MRD for hematologic malignancies
    if study_type in ["hematologic", "cart"]:
        base_elements["mrd_assessment"] = MRD_ASSESSMENT

    return base_elements


# =============================================================================
# Utility: Get specific element category
# =============================================================================
def get_element_category(category: str) -> dict:
    """Get a specific category of SAP elements."""
    categories = {
        # Core definitions
        "definitions": STUDY_DEFINITIONS,
        "demographics": DEMOGRAPHICS_BASELINE,
        "prior_therapy": PRIOR_THERAPY_ANALYSIS,
        "medical_history": MEDICAL_HISTORY,
        "concomitant_meds": CONCOMITANT_MEDICATIONS,
        # Efficacy
        "tumor_response": TUMOR_RESPONSE_ASSESSMENT,
        "concordance": CONCORDANCE_ANALYSIS,
        # Safety
        "exposure": EXPOSURE_ANALYSIS,
        "ae_periods": AE_PERIOD_ANALYSIS,
        "death": DEATH_ANALYSIS,
        "subsequent_therapy": SUBSEQUENT_THERAPY,
        "compliance": TREATMENT_COMPLIANCE,
        "organ_function": ORGAN_FUNCTION_SPECS,
        # CAR-T specific
        "cart_manufacturing": CART_MANUFACTURING_METRICS,
        "mrd": MRD_ASSESSMENT,
        # Analysis
        "protocol_deviations": PROTOCOL_DEVIATIONS,
        "sensitivity": SENSITIVITY_ANALYSES,
        "multiplicity": MULTIPLICITY_ADJUSTMENTS,
        "interim": INTERIM_ANALYSIS,
        "qol": QOL_PRO_ANALYSIS,
        "healthcare": HEALTHCARE_UTILIZATION,
        "estimand": ESTIMAND_FRAMEWORK,
        "subgroups": SUBGROUP_ANALYSIS_SPECS,
        "data_handling": DATA_HANDLING_RULES,
        "blinding": BLINDING_CONSIDERATIONS,
        "data_cutoff": DATA_CUTOFF_SPECS,
        "analysis_timing": ANALYSIS_TIMING,
        "follow_up": FOLLOW_UP_ANALYSIS_SPECS,
        "stratification": STRATIFICATION_BALANCE,
        # Special
        "biomarkers": BIOMARKER_SUBGROUPS,
        "phase2": PHASE2_DESIGNS,
        "randomization": RANDOMIZATION_SPECS,
        "covid19": COVID19_VARIATIONS,
        "pkpd": PK_PD_ANALYSIS,
        "immunogenicity": IMMUNOGENICITY_ANALYSIS,
        "enrollment": ENROLLMENT_SUMMARIES,
    }
    return categories.get(category, {})
