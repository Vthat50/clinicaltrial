"""
Disease-Specific Response Criteria v1.0
========================================

Comprehensive response criteria for tumor-specific oncology indications:

1. RANO (Response Assessment in Neuro-Oncology) - Brain tumors
2. Lugano Classification - Lymphoma
3. PCWG3 (Prostate Cancer Working Group 3) - Prostate cancer
4. irRECIST (Immune-related RECIST) - Immunotherapy trials
5. iRECIST (Immune RECIST) - Immunotherapy trials
6. Cheson 2007/2014 - Lymphoma
7. IMWG (International Myeloma Working Group) - Multiple Myeloma
8. GCIG (Gynecologic Cancer InterGroup) - CA-125 response

Each includes complete response categories, measurement rules, and
time-point assessments.
"""

from typing import Dict, List, Optional
import json
from pathlib import Path


# =============================================================================
# RANO CRITERIA - BRAIN TUMORS
# =============================================================================

RANO_CRITERIA = {
    "name": "RANO (Response Assessment in Neuro-Oncology)",
    "version": "2010",
    "indication": "High-Grade Gliomas (GBM, Anaplastic Astrocytoma)",
    "reference": "Wen et al. J Clin Oncol 2010",

    "imaging_requirements": {
        "modality": "Contrast-enhanced MRI",
        "sequences": ["T1 pre-contrast", "T1 post-contrast (Gadolinium)", "T2/FLAIR"],
        "frequency": "Every 8 weeks or per protocol",
        "slice_thickness": "5mm or less"
    },

    "measurable_disease": {
        "definition": "Contrast-enhancing lesion ≥10mm in two perpendicular diameters",
        "measurement": "Bi-dimensional (product of longest perpendicular diameters)",
        "minimum_lesions": "At least one measurable lesion",
        "maximum_lesions": "Up to 5 target lesions"
    },

    "response_categories": {
        "CR": {
            "name": "Complete Response",
            "criteria": [
                "Complete disappearance of all enhancing measurable disease",
                "Sustained for at least 4 weeks",
                "No new lesions",
                "Stable or improved non-enhancing (T2/FLAIR) lesions",
                "Off corticosteroids (or on physiologic replacement only)",
                "Clinically stable or improved"
            ]
        },
        "PR": {
            "name": "Partial Response",
            "criteria": [
                "≥50% decrease in sum of products of perpendicular diameters of all measurable enhancing lesions",
                "Sustained for at least 4 weeks",
                "No new lesions",
                "Stable or improved non-enhancing (T2/FLAIR) lesions",
                "Stable or reduced corticosteroid dose",
                "Clinically stable or improved"
            ]
        },
        "SD": {
            "name": "Stable Disease",
            "criteria": [
                "Does not qualify for CR, PR, or progression",
                "Stable non-enhancing (T2/FLAIR) lesions",
                "Clinically stable"
            ]
        },
        "PD": {
            "name": "Progressive Disease",
            "criteria": [
                "≥25% increase in sum of products of perpendicular diameters of enhancing lesions",
                "OR any new measurable enhancing lesion",
                "OR clear clinical deterioration not attributable to other causes",
                "OR significant increase in T2/FLAIR non-enhancing lesion",
                "Criteria met on stable or increased corticosteroid dose"
            ]
        }
    },

    "pseudoprogression": {
        "definition": "Apparent radiologic worsening within 12 weeks of radiation completion that stabilizes/improves without treatment change",
        "handling": "Continue treatment; confirm progression on subsequent scan ≥4 weeks later",
        "risk_factors": ["MGMT methylation", "Combined chemoradiation"]
    },

    "pseudoresponse": {
        "definition": "Rapid decrease in enhancement after antiangiogenic therapy (e.g., bevacizumab)",
        "handling": "Monitor T2/FLAIR changes; evaluate non-enhancing tumor progression"
    },

    "special_considerations": {
        "corticosteroid_use": "Must document dose; affects response classification",
        "clinical_status": "Neurological examination required at each assessment",
        "bevacizumab_trials": "RANO criteria with emphasis on T2/FLAIR progression"
    }
}


# =============================================================================
# LUGANO CLASSIFICATION - LYMPHOMA
# =============================================================================

LUGANO_CRITERIA = {
    "name": "Lugano Classification",
    "version": "2014",
    "indication": "Hodgkin and Non-Hodgkin Lymphoma",
    "reference": "Cheson et al. J Clin Oncol 2014",

    "imaging_requirements": {
        "fdg_avid_lymphomas": {
            "modality": "PET-CT (FDG-PET)",
            "timing": "Interim (after 2-4 cycles) and End of Treatment",
            "uptake_time": "60 minutes post FDG injection",
            "reconstruction": "Ordered subsets expectation maximization (OSEM)"
        },
        "non_fdg_avid_lymphomas": {
            "modality": "CT alone",
            "contrast": "IV contrast-enhanced",
            "slice_thickness": "5mm"
        }
    },

    "measurable_disease": {
        "nodal_disease": {
            "definition": "Node/nodal mass >15mm in longest diameter (LDi)",
            "measurement": "CT: Long axis for nodal, short axis for extranodal",
            "up_to_six_target_nodes": True
        },
        "extranodal_disease": {
            "definition": "Lesion >10mm in longest diameter",
            "sites": ["Liver", "Spleen", "Bone", "Lung", "Skin", "GI tract", "CNS"]
        },
        "splenic_involvement": {
            "definition": "Splenomegaly >13cm in craniocaudal length OR focal lesions"
        }
    },

    "deauville_5_point_scale": {
        "description": "5-Point Scale (5-PS) for PET interpretation",
        "scores": {
            "1": "No uptake above background",
            "2": "Uptake ≤ mediastinum",
            "3": "Uptake > mediastinum but ≤ liver",
            "4": "Uptake moderately higher than liver",
            "5": "Uptake markedly higher than liver and/or new lesions"
        },
        "response_threshold": {
            "interim": "Score 1-3 considered negative (adequate response)",
            "end_of_treatment": "Score 1-3 considered CMR"
        }
    },

    "response_categories": {
        "CMR": {
            "name": "Complete Metabolic Response (FDG-avid) / Complete Response (non-FDG-avid)",
            "pet_criteria": "Deauville score 1, 2, or 3 (no metabolically active disease)",
            "ct_criteria": [
                "Target nodes/masses regressed to ≤1.5cm in LDi",
                "No extranodal sites of disease",
                "Bone marrow: No FDG-avid disease in marrow"
            ]
        },
        "PMR": {
            "name": "Partial Metabolic Response / Partial Response",
            "pet_criteria": "Deauville score 4 or 5 with reduced uptake from baseline",
            "ct_criteria": [
                "≥50% decrease in SPD of up to 6 measurable nodes",
                "No increase in non-measured lesions",
                "No new lesions"
            ]
        },
        "NMR": {
            "name": "No Metabolic Response / Stable Disease",
            "pet_criteria": "Deauville score 4 or 5 with no significant change from baseline",
            "ct_criteria": [
                "<50% decrease in SPD of target lesions",
                "No new lesions"
            ]
        },
        "PMD": {
            "name": "Progressive Metabolic Disease / Progressive Disease",
            "pet_criteria": [
                "Deauville score 4 or 5 with increased uptake from baseline",
                "OR new FDG-avid lesions"
            ],
            "ct_criteria": [
                "Individual node/lesion increase ≥50% in PPD from nadir",
                "OR increase in LDi or SDi by ≥0.5cm for lesions ≤2cm",
                "OR increase by ≥1.0cm for lesions >2cm",
                "OR new or recurrent splenomegaly",
                "OR new or recurrent lesion"
            ]
        }
    },

    "bone_marrow_assessment": {
        "fdg_avid": "PET-CT may replace bone marrow biopsy if diffusely positive",
        "non_fdg_avid": "Bone marrow biopsy required if clinically indicated"
    },

    "special_considerations": {
        "interim_pet": "Used for early response assessment; may guide therapy modification",
        "residual_mass": "Common in lymphoma; PET determines metabolic activity",
        "thymic_rebound": "May mimic residual disease on PET in young patients"
    }
}


# =============================================================================
# PCWG3 CRITERIA - PROSTATE CANCER
# =============================================================================

PCWG3_CRITERIA = {
    "name": "PCWG3 (Prostate Cancer Working Group 3)",
    "version": "2016",
    "indication": "Metastatic Castration-Resistant Prostate Cancer (mCRPC)",
    "reference": "Scher et al. J Clin Oncol 2016",

    "psa_endpoints": {
        "psa_response": {
            "definition": "≥50% decline from baseline confirmed ≥3 weeks later",
            "confirmation": "Second PSA value ≥3 weeks after first qualifying decline",
            "minimum_baseline": "PSA ≥2 ng/mL at baseline"
        },
        "psa_progression": {
            "definition": [
                "≥25% increase AND",
                "≥2 ng/mL absolute increase from nadir",
                "Confirmed by second value ≥3 weeks later"
            ],
            "timing_from_baseline": "Cannot occur before Week 12",
            "flare_provision": "PSA flare in first 12 weeks should not trigger discontinuation"
        },
        "waterfall_timepoint": "Maximum PSA decline at any time point"
    },

    "soft_tissue_assessment": {
        "method": "RECIST 1.1",
        "measurable_disease": {
            "lymph_nodes": "Short axis ≥15mm (extra-pelvic) or ≥10mm (pelvic)",
            "visceral_lesions": "Standard RECIST 1.1 (≥10mm)"
        },
        "response_categories": {
            "CR": "Complete disappearance of all measurable soft tissue disease",
            "PR": "≥30% decrease in sum of diameters",
            "SD": "Neither PR nor PD criteria met",
            "PD": "≥20% increase in sum of diameters AND ≥5mm absolute increase OR new lesion"
        }
    },

    "bone_assessment": {
        "modality": "Technetium-99m bone scan",
        "frequency": "Every 8-12 weeks",
        "progression_definition": [
            "≥2 new bone lesions on first scan post-baseline",
            "MUST be confirmed on second scan ≥6 weeks later showing ≥2 additional new lesions (total ≥4 new)",
            "OR clear unequivocal progression"
        ],
        "flare": {
            "definition": "Apparent new lesions in first 12 weeks due to treatment effect",
            "handling": "Require confirmation on subsequent scan"
        },
        "response": "Bone lesions are not considered to respond (only stable or progressing)"
    },

    "overall_response": {
        "soft_tissue_and_bone": {
            "CR": "Soft tissue CR AND no new bone lesions",
            "PR": "Soft tissue PR AND no new bone lesions",
            "SD": "Soft tissue SD AND no new bone lesions",
            "PD": "Any soft tissue PD OR confirmed bone progression"
        }
    },

    "special_endpoints": {
        "rPFS": {
            "name": "Radiographic Progression-Free Survival",
            "definition": "Time to first radiographic progression (soft tissue or bone) or death"
        },
        "symptomatic_skeletal_event": {
            "definition": [
                "Radiation to bone",
                "Pathologic fracture",
                "Spinal cord compression",
                "Surgery to bone"
            ]
        },
        "ctc_count": {
            "method": "CellSearch system",
            "favorable": "<5 CTC per 7.5mL blood",
            "unfavorable": "≥5 CTC per 7.5mL blood",
            "conversion": "Change from unfavorable to favorable at Week 12"
        }
    }
}


# =============================================================================
# irRECIST - IMMUNE-RELATED RECIST
# =============================================================================

irRECIST_CRITERIA = {
    "name": "irRECIST (Immune-related RECIST)",
    "version": "2017",
    "indication": "Immunotherapy clinical trials",
    "reference": "Nishino et al. Clin Cancer Res 2017",

    "rationale": "Modified RECIST to accommodate atypical response patterns in immunotherapy",

    "key_differences_from_recist": [
        "New lesions do not automatically indicate PD",
        "Tumor burden includes new lesion measurements",
        "Confirmation of progression required",
        "Allows treatment beyond initial progression"
    ],

    "response_categories": {
        "irCR": {
            "name": "Immune-related Complete Response",
            "criteria": "Complete disappearance of all measurable and new lesions, confirmed ≥4 weeks"
        },
        "irPR": {
            "name": "Immune-related Partial Response",
            "criteria": "≥30% decrease in total tumor burden (including new measurable lesions), confirmed ≥4 weeks"
        },
        "irSD": {
            "name": "Immune-related Stable Disease",
            "criteria": "Does not meet irCR, irPR, or irPD"
        },
        "irPD": {
            "name": "Immune-related Progressive Disease",
            "criteria": [
                "≥20% increase in total tumor burden (sum of all target + new measurable lesions)",
                "AND ≥5mm absolute increase",
                "Must be confirmed ≥4 weeks later"
            ]
        }
    },

    "new_lesions": {
        "handling": "Measure and add to total tumor burden",
        "threshold": "New lesion ≥10mm (or ≥15mm for lymph nodes) becomes measurable",
        "documentation": "Record new lesions separately for analysis"
    },

    "confirmation_requirement": {
        "irPD": "Must confirm progression ≥4 weeks after initial assessment",
        "rationale": "Distinguish pseudoprogression from true progression"
    },

    "pseudoprogression": {
        "definition": "Initial apparent increase in tumor burden followed by response",
        "frequency": "~10% of patients with immunotherapy",
        "management": "Continue treatment if clinically stable; re-assess in 4-8 weeks"
    }
}


# =============================================================================
# iRECIST - IMMUNE RECIST (OFFICIAL RECIST WORKING GROUP)
# =============================================================================

iRECIST_CRITERIA = {
    "name": "iRECIST",
    "version": "2017",
    "indication": "Immunotherapy clinical trials (RECIST Working Group consensus)",
    "reference": "Seymour et al. Lancet Oncol 2017",

    "description": "Modification of RECIST 1.1 by the official RECIST Working Group for immunotherapy",

    "response_categories": {
        "iCR": {
            "name": "Immune Complete Response",
            "criteria": "Disappearance of all target lesions, any pathological lymph nodes <10mm"
        },
        "iPR": {
            "name": "Immune Partial Response",
            "criteria": "≥30% decrease in sum of diameters of target lesions"
        },
        "iSD": {
            "name": "Immune Stable Disease",
            "criteria": "Neither sufficient shrinkage for iPR nor sufficient increase for iPD"
        },
        "iUPD": {
            "name": "Immune Unconfirmed Progressive Disease",
            "criteria": [
                "≥20% increase in sum of diameters AND ≥5mm absolute increase",
                "OR appearance of new lesions",
                "Requires confirmation 4-8 weeks later"
            ]
        },
        "iCPD": {
            "name": "Immune Confirmed Progressive Disease",
            "criteria": [
                "Confirmation of iUPD on next assessment",
                "Further increase in tumor burden OR additional new lesions"
            ]
        }
    },

    "unconfirmed_progression_handling": {
        "options": [
            "Continue treatment and reassess in 4-8 weeks",
            "Discontinue treatment if clinical deterioration"
        ],
        "clinical_stability": "Patient must be clinically stable to continue beyond iUPD"
    },

    "new_lesions_irecist": {
        "first_occurrence": "Triggers iUPD, not automatic iCPD",
        "measurement": "Must be measurable (≥10mm, ≥15mm for lymph nodes)",
        "confirmation": "Additional new lesions on next scan confirm iCPD"
    },

    "best_overall_response": {
        "hierarchy": ["iCR", "iPR", "iSD", "iUPD", "iCPD"],
        "non_cr_non_pd": "iSD or better achieved before iUPD can be BOR if iUPD not confirmed"
    }
}


# =============================================================================
# IMWG CRITERIA - MULTIPLE MYELOMA
# =============================================================================

IMWG_CRITERIA = {
    "name": "IMWG (International Myeloma Working Group)",
    "version": "2016",
    "indication": "Multiple Myeloma",
    "reference": "Kumar et al. Lancet Oncol 2016",

    "measurable_disease": {
        "serum_m_protein": "≥1 g/dL",
        "urine_m_protein": "≥200 mg/24 hours",
        "serum_free_light_chain": "Involved FLC ≥10 mg/dL with abnormal ratio",
        "bone_marrow_plasmacytosis": "≥30% if no other measurable disease"
    },

    "response_categories": {
        "sCR": {
            "name": "Stringent Complete Response",
            "criteria": [
                "CR criteria plus",
                "Normal FLC ratio",
                "Absence of clonal plasma cells by immunohistochemistry or flow cytometry"
            ]
        },
        "CR": {
            "name": "Complete Response",
            "criteria": [
                "Negative immunofixation on serum and urine",
                "<5% plasma cells in bone marrow",
                "Disappearance of soft tissue plasmacytomas"
            ]
        },
        "VGPR": {
            "name": "Very Good Partial Response",
            "criteria": [
                "Serum and urine M-protein detectable by immunofixation but not electrophoresis",
                "OR ≥90% reduction in serum M-protein",
                "Plus urine M-protein <100 mg/24 hours"
            ]
        },
        "PR": {
            "name": "Partial Response",
            "criteria": [
                "≥50% reduction in serum M-protein",
                "AND ≥90% reduction in 24-hour urine M-protein (or <200 mg/24 hours)",
                "If measurable soft tissue plasmacytoma: ≥50% reduction",
                "If only measurable by FLC: ≥50% decrease in difference between involved and uninvolved FLC"
            ]
        },
        "MR": {
            "name": "Minimal Response",
            "criteria": [
                "≥25% but <50% reduction in serum M-protein",
                "AND 50-89% reduction in 24-hour urine M-protein"
            ]
        },
        "SD": {
            "name": "Stable Disease",
            "criteria": "Not meeting criteria for sCR, CR, VGPR, PR, MR, or PD"
        },
        "PD": {
            "name": "Progressive Disease",
            "criteria": [
                "≥25% increase from lowest confirmed response in serum M-protein (absolute increase ≥0.5 g/dL)",
                "OR urine M-protein (absolute increase ≥200 mg/24 hours)",
                "OR difference between involved and uninvolved FLC (absolute increase ≥10 mg/dL)",
                "OR bone marrow plasma cell percentage (absolute increase ≥10%)",
                "OR definite new bone lesion or soft tissue plasmacytoma",
                "OR definite increase in existing plasmacytoma or bone lesion"
            ]
        }
    },

    "mrd_assessment": {
        "description": "Minimal Residual Disease Assessment",
        "methods": [
            {"name": "Next-Generation Sequencing (NGS)", "sensitivity": "10^-6"},
            {"name": "Next-Generation Flow (NGF)", "sensitivity": "10^-5 to 10^-6"},
            {"name": "PET-CT", "purpose": "Evaluate extramedullary disease"}
        ],
        "mrd_negative": "No clonal plasma cells detected at specified sensitivity"
    }
}


# =============================================================================
# GCIG CA-125 CRITERIA - OVARIAN CANCER
# =============================================================================

GCIG_CA125_CRITERIA = {
    "name": "GCIG CA-125 Response Criteria",
    "version": "2011",
    "indication": "Ovarian, Fallopian Tube, and Primary Peritoneal Cancer",
    "reference": "Rustin et al. Int J Gynecol Cancer 2011",

    "ca125_response": {
        "definition": "≥50% reduction in CA-125 from pretreatment sample",
        "requirements": [
            "Pretreatment sample ≥2× upper limit of normal",
            "Confirmed by repeat sample ≥28 days later",
            "No clinical evidence of progression"
        ]
    },

    "ca125_progression": {
        "from_nadir": {
            "criteria": [
                "CA-125 ≥2× nadir value",
                "OR CA-125 ≥2× ULN if never normalized"
            ],
            "confirmation": "Second sample confirming elevation"
        },
        "from_baseline": {
            "criteria": "Serial rise in CA-125 (≥2 samples) during treatment",
            "date_of_progression": "Date of first sample showing rise"
        }
    },

    "combined_response": {
        "description": "Combined CA-125 and RECIST Response",
        "cr": "CA-125 normalization AND RECIST CR",
        "pr": "CA-125 response OR RECIST PR (without other PD)",
        "sd": "Neither response nor progression by either criterion",
        "pd": "CA-125 progression OR RECIST PD"
    },

    "special_considerations": {
        "maintenance_therapy": "Rising CA-125 alone may prompt switch to next-line therapy",
        "parp_inhibitors": "CA-125 fluctuations common; correlate with imaging"
    }
}


# =============================================================================
# RANO-BM CRITERIA - BRAIN METASTASES
# =============================================================================

RANO_BM_CRITERIA = {
    "name": "RANO-BM (Response Assessment in Neuro-Oncology - Brain Metastases)",
    "version": "2015",
    "indication": "Brain Metastases from Solid Tumors",
    "reference": "Lin et al. Lancet Oncol 2015",

    "imaging": {
        "modality": "Contrast-enhanced MRI",
        "frequency": "Every 6-12 weeks",
        "measurement": "Bi-dimensional (longest diameter × perpendicular)",
        "minimum_size": "≥10mm in longest diameter"
    },

    "response_categories": {
        "CR": {
            "name": "Complete Response",
            "criteria": [
                "Complete disappearance of all CNS target lesions",
                "No new CNS lesions",
                "No corticosteroids (or physiologic replacement)",
                "Clinical stability or improvement"
            ]
        },
        "PR": {
            "name": "Partial Response",
            "criteria": [
                "≥30% decrease in sum of longest diameters of CNS target lesions",
                "No new CNS lesions",
                "Stable or decreased corticosteroids",
                "Clinical stability or improvement"
            ]
        },
        "SD": {
            "name": "Stable Disease",
            "criteria": "Does not qualify for CR, PR, or PD"
        },
        "PD": {
            "name": "Progressive Disease",
            "criteria": [
                "≥20% increase in sum of longest diameters of CNS target lesions AND ≥5mm absolute increase",
                "OR unequivocal progression in non-target lesions",
                "OR any new CNS lesion"
            ]
        }
    },

    "local_vs_distant": {
        "local_failure": "Progression at previously treated site (e.g., SRS field)",
        "distant_failure": "New brain metastasis outside treated area"
    }
}


# =============================================================================
# EXPORT FUNCTION
# =============================================================================

def export_disease_criteria(output_path: Path) -> Dict:
    """Export all disease-specific criteria as JSON."""
    criteria = {
        "metadata": {
            "version": "1.0",
            "description": "Disease-Specific Response Criteria for Oncology SAPs",
            "criteria_count": 8
        },
        "RANO": RANO_CRITERIA,
        "Lugano": LUGANO_CRITERIA,
        "PCWG3": PCWG3_CRITERIA,
        "irRECIST": irRECIST_CRITERIA,
        "iRECIST": iRECIST_CRITERIA,
        "IMWG": IMWG_CRITERIA,
        "GCIG_CA125": GCIG_CA125_CRITERIA,
        "RANO_BM": RANO_BM_CRITERIA
    }

    with open(output_path, 'w') as f:
        json.dump(criteria, f, indent=2, default=str)

    print(f"Disease-specific criteria exported to {output_path}")
    return criteria


if __name__ == "__main__":
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    criteria = export_disease_criteria(output_dir / "disease_specific_criteria.json")

    print("\n" + "=" * 80)
    print("DISEASE-SPECIFIC RESPONSE CRITERIA v1.0")
    print("=" * 80)

    for name, spec in [
        ("RANO", "Brain Tumors / High-Grade Glioma"),
        ("Lugano", "Hodgkin and Non-Hodgkin Lymphoma"),
        ("PCWG3", "Prostate Cancer (mCRPC)"),
        ("irRECIST", "Immunotherapy (modified RECIST)"),
        ("iRECIST", "Immunotherapy (RECIST Working Group)"),
        ("IMWG", "Multiple Myeloma"),
        ("GCIG CA-125", "Ovarian Cancer"),
        ("RANO-BM", "Brain Metastases")
    ]:
        print(f"  {name}: {spec}")

    print(f"\n{'=' * 80}")
    print("Total: 8 disease-specific response criteria systems")
    print("=" * 80)
