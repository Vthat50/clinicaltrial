"""
Interactive Tool-Source Visualization
=====================================
Generates an interactive HTML graph showing all KB tools and their sources.
Click on any node to see details.
"""

from pyvis.network import Network
import json

# =============================================================================
# COMPLETE TOOL TO SOURCE MAPPING
# =============================================================================

TOOL_SOURCE_MAPPING = {
    # -------------------------------------------------------------------------
    # TOOLS WITH EXPLICIT SOURCE MAPPING (from kb_source_mapping.py)
    # -------------------------------------------------------------------------
    "get_censoring_rules": {
        "category": "Methodology",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "ALEX (NCT02838420)",
                "BEACON CRC (ARRAY-818-302)",
                "CheckMate-214 (CA209214)",
                "CheckMate-649 (CA209649)",
                "DESTINY-Breast03 (DS8201-A-U302)",
                "KEYNOTE-024 (MK-3475-024)",
                "IMpower133 (NCT02763579)",
                "CASSIOPEIA (NCT02541383)",
                "ClarIDHy (AG120-C-005)",
                "POLO (D081FC00001)",
                "PRIMA (PR-30-5017-C)",
                "TOPAZ-1 (D933AC00001)",
                "ENGOT-OV44/FIRST (3000-03-005)",
                "EAA171/OPTIMUM",
                "ELARA (CCTL019E2202)"
            ],
            "regulatory": [
                "ICH E9(R1): Estimands and Sensitivity Analysis",
                "FDA: Clinical Trial Endpoints for Cancer Drugs"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-trial-endpoints-approval-cancer-drugs-and-biologics"
        }
    },

    "get_time_to_event_analysis": {
        "category": "Methodology",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "ALEX (NCT02838420)",
                "BEACON CRC (ARRAY-818-302)",
                "BMT CTN 0901",
                "CASSIOPEIA (NCT02541383)",
                "CheckMate-214 (CA209214)",
                "CheckMate-649 (CA209649)",
                "DESTINY-Breast03 (DS8201-A-U302)",
                "IMpower133 (NCT02763579)",
                "KEYNOTE-024 (MK-3475-024)",
                "PACIFIC (D4191C00001)",
                "POLO (D081FC00001)",
                "PROfound (D081DC00007)",
                "VISION (NCT03511664)"
            ],
            "regulatory": [],
            "public_url": "https://www.cdisc.org/standards/foundational/adam/adamig-v1-3"
        }
    },

    "get_statistical_method": {
        "category": "Methodology",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "ALEX (NCT02838420)",
                "BEACON CRC (ARRAY-818-302)",
                "CASSIOPEIA (NCT02541383)",
                "ClarIDHy (AG120-C-005)",
                "ENGOT-OV44/FIRST (3000-03-005)",
                "IMpower133 (NCT02763579)",
                "InnovaTV 301 (SGNTV-003)",
                "KATHERINE (NCT01772472)",
                "MONALEESA-3 (CLEE011F2301)"
            ],
            "regulatory": [
                "ICH E9: Statistical Principles for Clinical Trials",
                "ICH E9(R1): Estimands and Sensitivity Analysis"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_stratification_specs": {
        "category": "Methodology",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "ALEX (NCT02838420)",
                "BEACON CRC (ARRAY-818-302)",
                "CASSIOPEIA (NCT02541383)",
                "CheckMate-214 (CA209214)",
                "DESTINY-Breast03 (DS8201-A-U302)",
                "IMpower133 (NCT02763579)",
                "KEYNOTE-024 (MK-3475-024)",
                "MONALEESA-3 (CLEE011F2301)"
            ],
            "regulatory": [],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_missing_data_method": {
        "category": "Methodology",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "BEACON CRC (ARRAY-818-302)",
                "CASSIOPEIA (NCT02541383)",
                "ClarIDHy (AG120-C-005)",
                "ENGOT-OV44/FIRST (3000-03-005)",
                "IMpower133 (NCT02763579)"
            ],
            "regulatory": [
                "ICH E9(R1): Estimands and Sensitivity Analysis",
                "EMA: Missing Data in Confirmatory Clinical Trials"
            ],
            "public_url": "https://www.ema.europa.eu/en/missing-data-confirmatory-clinical-trials-scientific-guideline"
        }
    },

    "get_sensitivity_analysis": {
        "category": "Methodology",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "BEACON CRC (ARRAY-818-302)",
                "CASSIOPEIA (NCT02541383)",
                "ClarIDHy (AG120-C-005)",
                "ENGOT-OV44/FIRST (3000-03-005)",
                "IMpower133 (NCT02763579)",
                "KEYNOTE-024 (MK-3475-024)"
            ],
            "regulatory": [
                "ICH E9(R1): Estimands and Sensitivity Analysis"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_multiplicity_adjustment": {
        "category": "Methodology",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "CASSIOPEIA (NCT02541383)",
                "ClarIDHy (AG120-C-005)",
                "ENGOT-OV44/FIRST (3000-03-005)",
                "IMpower133 (NCT02763579)",
                "InnovaTV 301 (SGNTV-003)",
                "KEYNOTE-024 (MK-3475-024)",
                "MONALEESA-3 (CLEE011F2301)"
            ],
            "regulatory": [
                "EMA: Multiplicity Issues Guideline",
                "FDA: Multiple Endpoints in Clinical Trials"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/multiple-endpoints-clinical-trials-guidance-industry"
        }
    },

    "get_subgroup_analysis_specs": {
        "category": "Methodology",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "ALEX (NCT02838420)",
                "BEACON CRC (ARRAY-818-302)",
                "CASSIOPEIA (NCT02541383)",
                "CheckMate-214 (CA209214)",
                "DESTINY-Breast03 (DS8201-A-U302)",
                "IMpower133 (NCT02763579)"
            ],
            "regulatory": [],
            "public_url": ""
        }
    },

    "get_interim_analysis": {
        "category": "Methodology",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "ALEX (NCT02838420)",
                "BEACON CRC (ARRAY-818-302)",
                "CASSIOPEIA (NCT02541383)",
                "ClarIDHy (AG120-C-005)",
                "DESTINY-Breast03 (DS8201-A-U302)",
                "MONALEESA-3 (CLEE011F2301)"
            ],
            "regulatory": [
                "FDA: Adaptive Designs for Clinical Trials"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/adaptive-design-clinical-trials-drugs-and-biologics-guidance-industry"
        }
    },

    "get_confidence_interval_methods": {
        "category": "Methodology",
        "sources": {
            "trials": [
                "ZUMA-3 (KTE-X19)",
                "ELIANA (CTL019B2202)",
                "ELARA (CCTL019E2202)",
                "EMPOWER-CSCC1 (R2810-ONC-1540)",
                "NCI Anti-CD19 CAR (09-C-0082)"
            ],
            "regulatory": [],
            "public_url": ""
        }
    },

    "get_healthcare_utilization_specs": {
        "category": "Safety",
        "sources": {
            "trials": [
                "ZUMA-3 (KTE-X19)",
                "ELIANA (CTL019B2202)"
            ],
            "regulatory": [],
            "public_url": ""
        }
    },

    # Response Criteria
    "get_recist_specifications": {
        "category": "Response Criteria",
        "sources": {
            "trials": [
                "ALEX (NCT02838420)",
                "BEACON CRC (ARRAY-818-302)",
                "CheckMate-214 (CA209214)",
                "CheckMate-649 (CA209649)",
                "ClarIDHy (AG120-C-005)",
                "DESTINY-Breast03 (DS8201-A-U302)",
                "IMpower133 (NCT02763579)",
                "KEYNOTE-024 (MK-3475-024)",
                "PACIFIC (D4191C00001)",
                "POLO (D081FC00001)",
                "TOPAZ-1 (D933AC00001)"
            ],
            "regulatory": [
                "Eisenhauer et al. Eur J Cancer 2009 (RECIST 1.1)"
            ],
            "public_url": "https://pubmed.ncbi.nlm.nih.gov/19097774/"
        }
    },

    "get_response_criteria": {
        "category": "Response Criteria",
        "sources": {
            "trials": [
                "ELARA (CCTL019E2202) - Lugano",
                "L-MIND (MOR208C203) - Lugano",
                "SHINE (PCI-32765MCL3002) - Lugano",
                "CASSIOPEIA (NCT02541383) - IMWG",
                "PROfound (D081DC00007) - PCWG3",
                "VISION (NCT03511664) - PCWG3",
                "CheckMate-214 (CA209214) - irRECIST"
            ],
            "regulatory": [
                "Cheson et al. JCO 2014 (Lugano)",
                "Kumar et al. Lancet Oncol 2016 (IMWG)",
                "Scher et al. JCO 2016 (PCWG3)",
                "iRECIST Lancet Oncology 2017"
            ],
            "public_url": "https://pubmed.ncbi.nlm.nih.gov/25113753/"
        }
    },

    "get_all_response_criteria": {
        "category": "Response Criteria",
        "sources": {
            "trials": [],
            "regulatory": [
                "RECIST 1.1 (Eisenhauer 2009)",
                "Lugano (Cheson 2014)",
                "IMWG (Kumar 2016)",
                "PCWG3 (Scher 2016)",
                "irRECIST/iRECIST (2017)",
                "GCIG CA-125 (Rustin 2011)"
            ],
            "public_url": "https://pubmed.ncbi.nlm.nih.gov/19097774/"
        }
    },

    # Therapy-Specific
    "get_cart_specifications": {
        "category": "Therapy-Specific",
        "sources": {
            "trials": [
                "ZUMA-1 (Axicabtagene)",
                "ZUMA-3 (KTE-X19)",
                "ELIANA (CTL019B2202)",
                "ELARA (CCTL019E2202)",
                "NCI Anti-CD19 CAR (09-C-0082)"
            ],
            "regulatory": [],
            "public_url": "https://www.accessdata.fda.gov/drugsatfda_docs/nda/2017/125643Orig1s000TOC.cfm"
        }
    },

    "get_bispecific_specifications": {
        "category": "Therapy-Specific",
        "sources": {
            "trials": [
                "CD19-CD22 BiCART",
                "FDA Elranatamab Review",
                "FDA Teclistamab Review"
            ],
            "regulatory": [],
            "public_url": "https://www.accessdata.fda.gov/scripts/cder/daf/"
        }
    },

    "get_adc_specifications": {
        "category": "Therapy-Specific",
        "sources": {
            "trials": [
                "DESTINY-Breast03 (DS8201-A-U302)",
                "EV-301 (Enfortumab Vedotin)",
                "InnovaTV 301 (SGNTV-003)",
                "KATHERINE (NCT01772472)"
            ],
            "regulatory": [],
            "public_url": "https://www.accessdata.fda.gov/scripts/cder/daf/"
        }
    },

    # TFL
    "get_disposition_tables": {
        "category": "TFL",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "CASSIOPEIA (NCT02541383)",
                "KEYNOTE-024 (MK-3475-024)"
            ],
            "regulatory": [],
            "public_url": "https://phuse.global/"
        }
    },

    "get_efficacy_tables": {
        "category": "TFL",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "BEACON CRC (ARRAY-818-302)",
                "CheckMate-214 (CA209214)",
                "DESTINY-Breast03 (DS8201-A-U302)",
                "IMpower133 (NCT02763579)",
                "KEYNOTE-024 (MK-3475-024)"
            ],
            "regulatory": [],
            "public_url": "https://phuse.global/"
        }
    },

    "get_safety_tables": {
        "category": "TFL",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "CASSIOPEIA (NCT02541383)",
                "DESTINY-Breast03 (DS8201-A-U302)",
                "IMpower133 (NCT02763579)",
                "ZUMA-3 (KTE-X19)"
            ],
            "regulatory": [
                "CTCAE v5.0"
            ],
            "public_url": "https://ctep.cancer.gov/protocoldevelopment/electronic_applications/ctc.htm"
        }
    },

    "get_all_figures": {
        "category": "TFL",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "CheckMate-214 (CA209214)",
                "CheckMate-649 (CA209649)",
                "DESTINY-Breast03 (DS8201-A-U302)",
                "IMpower133 (NCT02763579)",
                "KEYNOTE-024 (MK-3475-024)",
                "ZUMA-3 (KTE-X19)",
                "ELIANA (CTL019B2202)",
                "ELARA (CCTL019E2202)"
            ],
            "regulatory": [],
            "public_url": "https://phuse.global/"
        }
    },

    # Baseline Covariates
    "get_baseline_covariates": {
        "category": "Baseline",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "ALEX (NCT02838420)",
                "BEACON CRC (ARRAY-818-302)",
                "CASSIOPEIA (NCT02541383)",
                "CheckMate-214 (CA209214)",
                "DESTINY-Breast03 (DS8201-A-U302)",
                "ELARA (CCTL019E2202)",
                "IMpower133 (NCT02763579)",
                "KEYNOTE-024 (MK-3475-024)",
                "L-MIND (MOR208C203)",
                "MONALEESA-3 (CLEE011F2301)",
                "PACIFIC (D4191C00001)",
                "PALOMA-3 (A5481023)",
                "PROfound (D081DC00007)",
                "VIALE-A (M15-656)",
                "VISION (NCT03511664)",
                "ZUMA-3 (KTE-X19)"
            ],
            "regulatory": [],
            "public_url": ""
        }
    },

    "get_demographics_baseline_specs": {
        "category": "Baseline",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "CheckMate-214 (CA209214)",
                "KEYNOTE-024 (MK-3475-024)"
            ],
            "regulatory": [
                "CDISC SDTM DM Domain"
            ],
            "public_url": "https://www.cdisc.org/standards/foundational/sdtm"
        }
    },

    # Estimands & ADaM
    "get_estimand_framework": {
        "category": "Estimands",
        "sources": {
            "trials": [
                "ADAURA (D5164C00001)",
                "CASSIOPEIA (NCT02541383)",
                "ENGOT-OV44/FIRST (3000-03-005)"
            ],
            "regulatory": [
                "ICH E9(R1): Estimands and Sensitivity Analysis"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_adam_dataset_spec": {
        "category": "ADaM",
        "sources": {
            "trials": [
                "KEYNOTE-024 (MK-3475-024)",
                "CheckMate-214 (CA209214)"
            ],
            "regulatory": [
                "CDISC ADaM Implementation Guide"
            ],
            "public_url": "https://www.cdisc.org/standards/foundational/adam"
        }
    },

    "get_mrd_assessment_specs": {
        "category": "Hematology",
        "sources": {
            "trials": [
                "CASSIOPEIA (NCT02541383)",
                "EAA171/OPTIMUM",
                "CLL-MRD (J2N-MC-JZNJ)"
            ],
            "regulatory": [
                "FDA: MRD in Hematologic Malignancies"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents"
        }
    },

    # -------------------------------------------------------------------------
    # TOOLS WITHOUT EXPLICIT MAPPING - PUBLIC SOURCES
    # -------------------------------------------------------------------------
    "get_population_definitions": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "ICH E9: Statistical Principles for Clinical Trials"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_derived_variables": {
        "category": "ADaM",
        "sources": {
            "trials": [],
            "regulatory": [
                "CDISC ADaM Implementation Guide"
            ],
            "public_url": "https://www.cdisc.org/standards/foundational/adam"
        }
    },

    "get_pro_qol_analysis": {
        "category": "PRO/QoL",
        "sources": {
            "trials": [],
            "regulatory": [
                "EORTC QLQ-C30 Scoring Manual",
                "EQ-5D User Guide"
            ],
            "public_url": "https://www.eortc.org/app/uploads/sites/2/2018/02/SCmanual.pdf"
        }
    },

    "get_qol_analysis_specs": {
        "category": "PRO/QoL",
        "sources": {
            "trials": [],
            "regulatory": [
                "EORTC QLQ-C30 Scoring Manual",
                "FDA PRO Guidance"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/patient-reported-outcome-measures-use-medical-product-development-support-labeling-claims"
        }
    },

    "get_analysis_windows": {
        "category": "ADaM",
        "sources": {
            "trials": [],
            "regulatory": [
                "CDISC ADaM Implementation Guide"
            ],
            "public_url": "https://www.cdisc.org/standards/foundational/adam"
        }
    },

    "get_data_cutoff_specs": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA Clinical Review Documents"
            ],
            "public_url": "https://www.accessdata.fda.gov/scripts/cder/daf/"
        }
    },

    "get_cml_criteria": {
        "category": "Response Criteria",
        "sources": {
            "trials": [],
            "regulatory": [
                "ELN CML Guidelines (Baccarani Blood 2013)"
            ],
            "public_url": "https://pubmed.ncbi.nlm.nih.gov/23843494/"
        }
    },

    "get_iwcll_criteria": {
        "category": "Response Criteria",
        "sources": {
            "trials": [],
            "regulatory": [
                "iwCLL Guidelines (Hallek Blood 2018)"
            ],
            "public_url": "https://pubmed.ncbi.nlm.nih.gov/29540348/"
        }
    },

    "get_organ_function_scores": {
        "category": "Clinical Scales",
        "sources": {
            "trials": [],
            "regulatory": [
                "Child-Pugh Score",
                "MELD Score",
                "CKD-EPI"
            ],
            "public_url": "https://www.mdcalc.com/"
        }
    },

    "get_listings": {
        "category": "TFL",
        "sources": {
            "trials": [],
            "regulatory": [
                "CDISC Standards",
                "PHUSE Templates"
            ],
            "public_url": "https://phuse.global/"
        }
    },

    "get_table_template": {
        "category": "TFL",
        "sources": {
            "trials": [],
            "regulatory": [
                "PHUSE TFL Templates",
                "FDA Review Documents"
            ],
            "public_url": "https://phuse.global/"
        }
    },

    "get_figure_template": {
        "category": "TFL",
        "sources": {
            "trials": [],
            "regulatory": [
                "PHUSE Templates"
            ],
            "public_url": "https://phuse.global/"
        }
    },

    "get_single_arm_tables": {
        "category": "TFL",
        "sources": {
            "trials": [
                "ZUMA-1 (Axicabtagene)",
                "ELIANA (CTL019B2202)"
            ],
            "regulatory": [
                "FDA Single-Arm Guidance"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents"
        }
    },

    "get_lymphoma_tables": {
        "category": "TFL",
        "sources": {
            "trials": [
                "ELARA (CCTL019E2202)",
                "L-MIND (MOR208C203)"
            ],
            "regulatory": [],
            "public_url": ""
        }
    },

    "get_cart_tables": {
        "category": "TFL",
        "sources": {
            "trials": [
                "ZUMA-1 (Axicabtagene)",
                "ZUMA-3 (KTE-X19)",
                "ELIANA (CTL019B2202)"
            ],
            "regulatory": [],
            "public_url": "https://www.accessdata.fda.gov/drugsatfda_docs/nda/2017/125643Orig1s000TOC.cfm"
        }
    },

    "get_oncology_tfl_templates": {
        "category": "TFL",
        "sources": {
            "trials": [],
            "regulatory": [
                "PHUSE Oncology TFL Templates"
            ],
            "public_url": "https://phuse.global/"
        }
    },

    "get_tfl_shells": {
        "category": "TFL",
        "sources": {
            "trials": [],
            "regulatory": [
                "PHUSE Standard Analyses",
                "FDA Review Documents"
            ],
            "public_url": "https://phuse.global/"
        }
    },

    "get_tte_derivation_tables": {
        "category": "ADaM",
        "sources": {
            "trials": [],
            "regulatory": [
                "CDISC ADTTE Implementation Guide"
            ],
            "public_url": "https://www.cdisc.org/standards/foundational/adam/adamig-v1-3"
        }
    },

    "get_concordance_analysis": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "Cohen's Kappa (Statistics literature)",
                "Lin's Concordance Correlation"
            ],
            "public_url": ""
        }
    },

    "get_concordance_specs": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "Statistics textbooks"
            ],
            "public_url": ""
        }
    },

    "get_required_references": {
        "category": "References",
        "sources": {
            "trials": [],
            "regulatory": [
                "Standard SAP citations"
            ],
            "public_url": ""
        }
    },

    "get_date_imputation_rules": {
        "category": "ADaM",
        "sources": {
            "trials": [],
            "regulatory": [
                "CDISC SDTM/ADaM Implementation Guide"
            ],
            "public_url": "https://www.cdisc.org/standards"
        }
    },

    "get_study_definitions": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "ICH E9: Statistical Principles"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_exposure_specifications": {
        "category": "ADaM",
        "sources": {
            "trials": [],
            "regulatory": [
                "CDISC ADEX Specification"
            ],
            "public_url": "https://www.cdisc.org/standards/foundational/adam"
        }
    },

    "get_subsequent_therapy_specs": {
        "category": "Efficacy",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA Oncology Endpoint Guidance"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents"
        }
    },

    "get_enrollment_specifications": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "ICH E6: Good Clinical Practice"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_ae_period_specifications": {
        "category": "Safety",
        "sources": {
            "trials": [],
            "regulatory": [
                "CDISC ADAE",
                "ICH E2A: Safety Reporting"
            ],
            "public_url": "https://www.cdisc.org/standards/foundational/adam"
        }
    },

    "get_covid19_variations": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA COVID-19 Clinical Trial Guidance",
                "EMA COVID-19 Guidance"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/fda-guidance-conduct-clinical-trials-medical-products-during-covid-19-public-health-emergency"
        }
    },

    "get_protocol_deviation_specs": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "ICH E3: Clinical Study Reports"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_phase2_design_specs": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "Simon Two-Stage Design (Simon 1989)",
                "Fleming One-Stage Design"
            ],
            "public_url": "https://pubmed.ncbi.nlm.nih.gov/2702835/"
        }
    },

    "get_blinding_specifications": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "ICH E9: Statistical Principles"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_pkpd_analysis_specs": {
        "category": "PK/PD",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA Population PK Guidance"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/population-pharmacokinetics"
        }
    },

    "get_prior_therapy_specs": {
        "category": "Baseline",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA Clinical Review Documents"
            ],
            "public_url": "https://www.accessdata.fda.gov/scripts/cder/daf/"
        }
    },

    "get_concomitant_medication_specs": {
        "category": "Safety",
        "sources": {
            "trials": [],
            "regulatory": [
                "WHO ATC Classification"
            ],
            "public_url": "https://www.whocc.no/atc_ddd_index/"
        }
    },

    "get_medical_history_specs": {
        "category": "Safety",
        "sources": {
            "trials": [],
            "regulatory": [
                "MedDRA Coding"
            ],
            "public_url": "https://www.meddra.org/"
        }
    },

    "get_death_analysis_specs": {
        "category": "Safety",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA Oncology Endpoint Guidance"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents"
        }
    },

    "get_tumor_response_specs": {
        "category": "Response Criteria",
        "sources": {
            "trials": [],
            "regulatory": [
                "RECIST 1.1 (Eisenhauer 2009)"
            ],
            "public_url": "https://pubmed.ncbi.nlm.nih.gov/19097774/"
        }
    },

    "get_treatment_compliance_specs": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "ICH E9: Statistical Principles"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_immunogenicity_specs": {
        "category": "Safety",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA Immunogenicity Guidance"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/immunogenicity-testing-therapeutic-protein-products-developing-and-validating-assays-anti-drug"
        }
    },

    "get_organ_function_specs": {
        "category": "Safety",
        "sources": {
            "trials": [],
            "regulatory": [
                "CTCAE v5.0",
                "NCI Organ Function Criteria"
            ],
            "public_url": "https://ctep.cancer.gov/protocoldevelopment/electronic_applications/ctc.htm"
        }
    },

    "get_analysis_timing_specs": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA Clinical Review Documents"
            ],
            "public_url": "https://www.accessdata.fda.gov/scripts/cder/daf/"
        }
    },

    "get_follow_up_analysis_specs": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA Clinical Review Documents"
            ],
            "public_url": "https://www.accessdata.fda.gov/scripts/cder/daf/"
        }
    },

    "get_stratification_balance_specs": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "ICH E9: Statistical Principles"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_comprehensive_sap_elements": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "Gamble et al. JAMA 2017 (SAP Guidelines)"
            ],
            "public_url": "https://pubmed.ncbi.nlm.nih.gov/28873131/"
        }
    },

    "get_similar_trials": {
        "category": "Knowledge Graph",
        "sources": {
            "trials": [
                "354 trials from ClinicalTrials.gov"
            ],
            "regulatory": [],
            "public_url": "https://clinicaltrials.gov/api/gui"
        }
    },

    "get_reference_sap_section": {
        "category": "Reference",
        "sources": {
            "trials": [
                "Proprietary SAP access required"
            ],
            "regulatory": [],
            "public_url": ""
        }
    },

    "get_study_type_template": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA Disease-Specific Guidance"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents"
        }
    },

    "get_biomarker_endpoints": {
        "category": "Biomarkers",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA Biomarker Qualification Program"
            ],
            "public_url": "https://www.fda.gov/drugs/biomarker-qualification-program"
        }
    },

    "get_performance_status_scales": {
        "category": "Clinical Scales",
        "sources": {
            "trials": [],
            "regulatory": [
                "ECOG (Oken et al. 1982)",
                "Karnofsky (Karnofsky 1949)"
            ],
            "public_url": "https://pubmed.ncbi.nlm.nih.gov/7165009/"
        }
    },

    "get_prognostic_scores": {
        "category": "Clinical Scales",
        "sources": {
            "trials": [],
            "regulatory": [
                "IPI (Shipp et al. NEJM 1993)",
                "FLIPI (Solal-Céligny et al. Blood 2004)",
                "ISS (Greipp et al. JCO 2005)",
                "IMDC (Heng et al. JCO 2009)"
            ],
            "public_url": "https://pubmed.ncbi.nlm.nih.gov/8411477/"
        }
    },

    "get_meddra_search_strategies": {
        "category": "Safety",
        "sources": {
            "trials": [],
            "regulatory": [
                "MedDRA SMQ/CMQ Documentation"
            ],
            "public_url": "https://www.meddra.org/"
        }
    },

    "get_safety_analysis_specs": {
        "category": "Safety",
        "sources": {
            "trials": [],
            "regulatory": [
                "ICH E2A: Safety Reporting",
                "CTCAE v5.0"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_safety_specifications": {
        "category": "Safety",
        "sources": {
            "trials": [],
            "regulatory": [
                "ICH E2A",
                "CTCAE v5.0"
            ],
            "public_url": "https://ctep.cancer.gov/protocoldevelopment/electronic_applications/ctc.htm"
        }
    },

    "get_study_design_specs": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "ICH E9: Statistical Principles"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_programming_specifications": {
        "category": "ADaM",
        "sources": {
            "trials": [],
            "regulatory": [
                "CDISC ADaM Implementation Guide"
            ],
            "public_url": "https://www.cdisc.org/standards/foundational/adam"
        }
    },

    "get_data_handling_rules": {
        "category": "ADaM",
        "sources": {
            "trials": [],
            "regulatory": [
                "CDISC Standards"
            ],
            "public_url": "https://www.cdisc.org/standards"
        }
    },

    "get_estimand_specifications": {
        "category": "Estimands",
        "sources": {
            "trials": [],
            "regulatory": [
                "ICH E9(R1): Estimands and Sensitivity Analysis"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_subgroup_specifications": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA Subgroup Analysis Guidance"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents"
        }
    },

    "get_multiplicity_methods": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA Multiple Endpoints Guidance",
                "Bretz et al. Graphical Approaches"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/multiple-endpoints-clinical-trials-guidance-industry"
        }
    },

    "get_interim_analysis_specs": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "FDA Adaptive Designs Guidance",
                "Lan-DeMets Alpha Spending"
            ],
            "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/adaptive-design-clinical-trials-drugs-and-biologics-guidance-industry"
        }
    },

    "get_sensitivity_analysis_catalog": {
        "category": "Methodology",
        "sources": {
            "trials": [],
            "regulatory": [
                "ICH E9(R1): Estimands"
            ],
            "public_url": "https://www.ich.org/page/efficacy-guidelines"
        }
    },

    "get_cart_manufacturing_specs": {
        "category": "Therapy-Specific",
        "sources": {
            "trials": [
                "ZUMA-1 (Axicabtagene)",
                "ELIANA (CTL019B2202)"
            ],
            "regulatory": [],
            "public_url": "https://www.accessdata.fda.gov/drugsatfda_docs/nda/2017/125643Orig1s000TOC.cfm"
        }
    }
}

# Category colors
CATEGORY_COLORS = {
    "Methodology": "#4CAF50",      # Green
    "Response Criteria": "#2196F3", # Blue
    "Therapy-Specific": "#FF9800",  # Orange
    "TFL": "#9C27B0",              # Purple
    "Baseline": "#00BCD4",          # Cyan
    "Safety": "#F44336",            # Red
    "ADaM": "#795548",              # Brown
    "Estimands": "#607D8B",         # Blue Grey
    "PRO/QoL": "#E91E63",           # Pink
    "Clinical Scales": "#FFEB3B",   # Yellow
    "Hematology": "#3F51B5",        # Indigo
    "PK/PD": "#009688",             # Teal
    "References": "#9E9E9E",        # Grey
    "Knowledge Graph": "#673AB7",   # Deep Purple
    "Biomarkers": "#8BC34A",        # Light Green
    "Reference": "#FF5722",         # Deep Orange
    "Efficacy": "#03A9F4"           # Light Blue
}


def create_interactive_graph():
    """Create an interactive HTML visualization of tools and sources."""

    # Create network
    net = Network(
        height="900px",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="white",
        directed=False
    )

    # Physics settings for better layout
    net.barnes_hut(
        gravity=-3000,
        central_gravity=0.3,
        spring_length=200,
        spring_strength=0.01,
        damping=0.09
    )

    # Track added nodes to avoid duplicates
    added_sources = set()

    # Add tool nodes and their connections
    for tool_name, tool_data in TOOL_SOURCE_MAPPING.items():
        category = tool_data.get("category", "Other")
        color = CATEGORY_COLORS.get(category, "#666666")
        sources = tool_data.get("sources", {})
        public_url = sources.get("public_url", "")

        # Build tooltip for tool
        trials = sources.get("trials", [])
        regulatory = sources.get("regulatory", [])

        tooltip = f"<b>{tool_name}</b><br><br>"
        tooltip += f"<b>Category:</b> {category}<br><br>"

        if trials:
            tooltip += f"<b>Trial Sources ({len(trials)}):</b><br>"
            for t in trials[:5]:
                tooltip += f"• {t}<br>"
            if len(trials) > 5:
                tooltip += f"<i>... and {len(trials) - 5} more</i><br>"
            tooltip += "<br>"

        if regulatory:
            tooltip += f"<b>Regulatory Sources ({len(regulatory)}):</b><br>"
            for r in regulatory:
                tooltip += f"• {r}<br>"
            tooltip += "<br>"

        if public_url:
            tooltip += f"<b>Public URL:</b><br><a href='{public_url}' target='_blank'>{public_url[:50]}...</a>"

        # Add tool node
        net.add_node(
            tool_name,
            label=tool_name.replace("get_", "").replace("_", " ").title(),
            title=tooltip,
            color=color,
            size=25,
            shape="dot",
            font={"size": 10, "color": "white"}
        )

        # Add source nodes and edges
        for trial in trials:
            source_id = f"trial_{trial}"
            if source_id not in added_sources:
                net.add_node(
                    source_id,
                    label=trial.split("(")[0].strip()[:20],
                    title=f"<b>Trial:</b> {trial}",
                    color="#666666",
                    size=10,
                    shape="triangle",
                    font={"size": 8, "color": "#cccccc"}
                )
                added_sources.add(source_id)
            net.add_edge(tool_name, source_id, color="#444444", width=0.5)

        for reg in regulatory:
            source_id = f"reg_{reg}"
            if source_id not in added_sources:
                # Determine URL for regulatory source
                reg_url = ""
                if "ICH" in reg:
                    reg_url = "https://www.ich.org/page/efficacy-guidelines"
                elif "FDA" in reg:
                    reg_url = "https://www.fda.gov/regulatory-information/search-fda-guidance-documents"
                elif "CDISC" in reg:
                    reg_url = "https://www.cdisc.org/standards"
                elif "EMA" in reg:
                    reg_url = "https://www.ema.europa.eu/"
                elif "CTCAE" in reg:
                    reg_url = "https://ctep.cancer.gov/protocoldevelopment/electronic_applications/ctc.htm"

                tooltip = f"<b>Regulatory:</b> {reg}"
                if reg_url:
                    tooltip += f"<br><br><a href='{reg_url}' target='_blank'>View Source</a>"

                net.add_node(
                    source_id,
                    label=reg[:25] + "..." if len(reg) > 25 else reg,
                    title=tooltip,
                    color="#FFD700",
                    size=15,
                    shape="square",
                    font={"size": 8, "color": "#cccccc"}
                )
                added_sources.add(source_id)
            net.add_edge(tool_name, source_id, color="#FFD700", width=1)

    # Add legend
    legend_html = """
    <div style="position: fixed; top: 10px; right: 10px; background: rgba(0,0,0,0.8); padding: 15px; border-radius: 10px; font-family: Arial; font-size: 12px; color: white; z-index: 1000;">
        <b style="font-size: 14px;">Legend</b><br><br>
        <b>Node Shapes:</b><br>
        ● Tool (circle)<br>
        ▲ Trial Source (triangle)<br>
        ■ Regulatory Source (square)<br><br>
        <b>Categories:</b><br>
    """
    for cat, color in CATEGORY_COLORS.items():
        legend_html += f'<span style="color:{color}">●</span> {cat}<br>'
    legend_html += """
        <br><b>Tip:</b> Click nodes to see details!<br>
        Scroll to zoom, drag to pan.
    </div>
    """

    # Save to HTML
    output_path = "tool_source_graph.html"
    net.save_graph(output_path)

    # Inject legend into HTML
    with open(output_path, "r") as f:
        html_content = f.read()

    html_content = html_content.replace("</body>", legend_html + "</body>")

    # Add title
    title_html = """
    <div style="position: fixed; top: 10px; left: 10px; background: rgba(0,0,0,0.8); padding: 15px; border-radius: 10px; font-family: Arial; color: white; z-index: 1000;">
        <h2 style="margin: 0;">KB Tools & Sources Graph</h2>
        <p style="margin: 5px 0 0 0; font-size: 12px; color: #888;">Interactive visualization of all tools and their sources</p>
    </div>
    """
    html_content = html_content.replace("</body>", title_html + "</body>")

    with open(output_path, "w") as f:
        f.write(html_content)

    print(f"Graph saved to: {output_path}")
    print(f"Total tools: {len(TOOL_SOURCE_MAPPING)}")
    print(f"Total source nodes: {len(added_sources)}")

    return output_path


def export_json():
    """Export the mapping as JSON for other visualizations."""
    output_path = "tool_source_mapping.json"
    with open(output_path, "w") as f:
        json.dump(TOOL_SOURCE_MAPPING, f, indent=2)
    print(f"JSON exported to: {output_path}")
    return output_path


if __name__ == "__main__":
    print("=" * 60)
    print("Generating Interactive Tool-Source Visualization")
    print("=" * 60)

    try:
        graph_path = create_interactive_graph()
        json_path = export_json()

        print("\n" + "=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        print(f"1. Open {graph_path} in a browser to view the interactive graph")
        print(f"2. JSON data exported to {json_path}")
        print("\nIn the graph:")
        print("  - Click on any node to see details")
        print("  - Hover over nodes for tooltips with sources")
        print("  - Regulatory sources have clickable URLs")
        print("  - Scroll to zoom, drag to pan")
    except ImportError:
        print("\nERROR: pyvis not installed. Installing...")
        print("Run: pip install pyvis")
        print("\nAlternatively, run: python -m pip install pyvis")
