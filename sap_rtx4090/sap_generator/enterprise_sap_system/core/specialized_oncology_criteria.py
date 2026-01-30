#!/usr/bin/env python3
"""
Specialized Oncology Response Criteria v1.0
===========================================
Implements missing criteria for ActionNeeded categories:
- lung_NSCLC: KRAS G12C, MET, ROS1, RET, NTRK biomarkers
- colorectal_CRC: BRAF V600E, sidedness, ctDNA MRD
- breast_HER2_pCR: RCB scoring
- prostate_PCWG: PCWG3 bone criteria
- pediatric: INRG, IRS staging
- mesothelioma: mRECIST measurement rules

Based on current clinical trial guidelines and FDA/EMA guidance documents.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ResponseCategory(Enum):
    """Standard response categories"""
    CR = "Complete Response"
    PR = "Partial Response"
    SD = "Stable Disease"
    PD = "Progressive Disease"
    NE = "Not Evaluable"
    # Immunotherapy-specific
    iCR = "Immune Complete Response"
    iPR = "Immune Partial Response"
    iSD = "Immune Stable Disease"
    iUPD = "Immune Unconfirmed Progressive Disease"
    iCPD = "Immune Confirmed Progressive Disease"


@dataclass
class BiomarkerResult:
    """Result of biomarker detection"""
    biomarker: str
    status: str  # positive, negative, unknown
    value: Optional[str] = None
    method: Optional[str] = None
    actionable: bool = False
    targeted_therapy: Optional[List[str]] = None


@dataclass
class ResponseAssessment:
    """Response assessment result"""
    category: ResponseCategory
    criteria_used: str
    measurements: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    confidence: float = 1.0


# =============================================================================
# LUNG NSCLC BIOMARKERS (KRAS G12C, MET, ROS1, RET, NTRK)
# =============================================================================

class LungNSCLCBiomarkers:
    """
    Extended NSCLC biomarker detection for actionable mutations.
    Adds: KRAS G12C, MET exon 14, ROS1, RET, NTRK fusions
    """

    BIOMARKER_PATTERNS = {
        # KRAS G12C - New FDA-approved target (sotorasib, adagrasib)
        "KRAS_G12C": {
            "patterns": [
                r"kras\s*g12c", r"kras\s+p\.g12c", r"kras\s+gly12cys",
                r"kras\s+codon\s*12\s*c", r"krasg12c"
            ],
            "therapies": ["sotorasib", "adagrasib"],
            "test_methods": ["NGS", "PCR", "Sanger sequencing"],
            "prevalence": "~13% of NSCLC adenocarcinoma"
        },
        # MET exon 14 skipping
        "MET_EX14": {
            "patterns": [
                r"met\s*exon\s*14\s*(?:skipping|skip|deletion|splice)",
                r"metex14", r"met\s+ex14", r"met\s*\u0394ex14",
                r"met\s+splice\s+site\s+mutation"
            ],
            "therapies": ["capmatinib", "tepotinib", "crizotinib"],
            "test_methods": ["NGS", "RNA-based NGS"],
            "prevalence": "~3-4% of NSCLC"
        },
        # ROS1 fusion
        "ROS1": {
            "patterns": [
                r"ros1\s*(?:fusion|rearrangement|positive|\+)",
                r"ros1-[a-z0-9]+\s*fusion", r"cd74-ros1", r"ezr-ros1",
                r"sdc4-ros1", r"slc34a2-ros1"
            ],
            "therapies": ["crizotinib", "entrectinib", "lorlatinib", "repotrectinib"],
            "test_methods": ["FISH", "NGS", "IHC"],
            "prevalence": "~1-2% of NSCLC"
        },
        # RET fusion/mutation
        "RET": {
            "patterns": [
                r"ret\s*(?:fusion|rearrangement|positive|\+)",
                r"ret-[a-z0-9]+\s*fusion", r"kif5b-ret", r"ccdc6-ret",
                r"ncoa4-ret", r"ret\s+mutation"
            ],
            "therapies": ["selpercatinib", "pralsetinib"],
            "test_methods": ["NGS", "FISH"],
            "prevalence": "~1-2% of NSCLC"
        },
        # NTRK fusion
        "NTRK": {
            "patterns": [
                r"ntrk\s*(?:1|2|3)?\s*(?:fusion|rearrangement|positive|\+)",
                r"ntrk[123]?\s*fusion", r"trk\s*(?:fusion|positive)",
                r"tpm3-ntrk1", r"lmna-ntrk1", r"etv6-ntrk3"
            ],
            "therapies": ["larotrectinib", "entrectinib"],
            "test_methods": ["NGS", "IHC", "FISH"],
            "prevalence": "~0.2-0.3% of NSCLC"
        },
        # Existing biomarkers (for completeness)
        "EGFR": {
            "patterns": [
                r"egfr\s*(?:mutation|positive|\+|mutant)",
                r"egfr\s*(?:exon\s*)?(?:19|21|20)",
                r"egfr\s*l858r", r"egfr\s*t790m", r"egfr\s*c797s"
            ],
            "therapies": ["osimertinib", "erlotinib", "gefitinib", "afatinib"],
            "test_methods": ["NGS", "PCR", "Cobas"],
            "prevalence": "~15-20% of NSCLC (higher in Asian populations)"
        },
        "ALK": {
            "patterns": [
                r"alk\s*(?:fusion|rearrangement|positive|\+)",
                r"alk-[a-z0-9]+\s*fusion", r"eml4-alk"
            ],
            "therapies": ["alectinib", "brigatinib", "lorlatinib", "crizotinib"],
            "test_methods": ["FISH", "NGS", "IHC"],
            "prevalence": "~3-7% of NSCLC"
        },
        # BRAF V600E in NSCLC
        "BRAF_V600E": {
            "patterns": [
                r"braf\s*v600e", r"braf\s*p\.v600e", r"braf\s*val600glu"
            ],
            "therapies": ["dabrafenib + trametinib"],
            "test_methods": ["NGS", "PCR"],
            "prevalence": "~2-4% of NSCLC"
        }
    }

    @classmethod
    def detect_biomarkers(cls, text: str) -> List[BiomarkerResult]:
        """Detect all actionable NSCLC biomarkers from text"""
        results = []
        text_lower = text.lower()

        for biomarker, config in cls.BIOMARKER_PATTERNS.items():
            for pattern in config["patterns"]:
                if re.search(pattern, text_lower):
                    # Determine status
                    status = cls._determine_status(text_lower, pattern)
                    results.append(BiomarkerResult(
                        biomarker=biomarker,
                        status=status,
                        actionable=True,
                        targeted_therapy=config["therapies"],
                        method=cls._detect_test_method(text_lower, config["test_methods"])
                    ))
                    break

        return results

    @classmethod
    def _determine_status(cls, text: str, pattern: str) -> str:
        """Determine if biomarker is positive or negative based on context"""
        match = re.search(pattern, text)
        if not match:
            return "unknown"

        # Check surrounding context
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 50)
        context = text[start:end]

        negative_indicators = ["negative", "wild-type", "wt", "absent", "not detected", "no mutation"]
        positive_indicators = ["positive", "mutant", "detected", "present", "mutation identified"]

        for neg in negative_indicators:
            if neg in context:
                return "negative"
        for pos in positive_indicators:
            if pos in context:
                return "positive"

        return "positive"  # Default to positive if mentioned

    @classmethod
    def _detect_test_method(cls, text: str, valid_methods: List[str]) -> Optional[str]:
        """Detect which testing method was used"""
        for method in valid_methods:
            if method.lower() in text:
                return method
        return None

    @classmethod
    def get_stratification_factors(cls) -> List[str]:
        """Return biomarker stratification factors for SAP"""
        return [
            "EGFR mutation status (positive vs negative)",
            "ALK rearrangement status (positive vs negative)",
            "KRAS G12C mutation status (positive vs negative)",
            "PD-L1 expression (TPS <1%, 1-49%, >=50%)",
            "ROS1/RET/NTRK fusion status (if tested)",
            "MET exon 14 skipping status (if tested)"
        ]


# =============================================================================
# COLORECTAL CANCER (BRAF V600E, Sidedness, ctDNA MRD)
# =============================================================================

class ColorectalCRCCriteria:
    """
    Colorectal cancer specific criteria including:
    - BRAF V600E mutation rules
    - Tumor sidedness stratification
    - ctDNA MRD endpoint definitions
    """

    # BRAF V600E specific rules
    BRAF_V600E_RULES = {
        "patterns": [
            r"braf\s*v600e", r"braf\s*p\.v600e", r"braf\s*val600glu",
            r"braf\s*mutant", r"brafv600e"
        ],
        "therapy_options": {
            "first_line": ["FOLFOXIRI + bevacizumab", "encorafenib + cetuximab"],
            "second_line": ["encorafenib + binimetinib + cetuximab"],
        },
        "prognostic_impact": "Poor prognosis - median OS typically shorter",
        "prevalence": "~8-12% of mCRC"
    }

    # Tumor sidedness definitions
    SIDEDNESS_DEFINITIONS = {
        "right_sided": {
            "anatomic_sites": ["cecum", "ascending colon", "hepatic flexure",
                             "transverse colon (proximal 2/3)"],
            "molecular_features": ["Higher MSI-H rate", "BRAF mutations more common",
                                  "CpG island methylator phenotype (CIMP)"],
            "prognosis": "Generally worse prognosis",
            "treatment_implications": "May benefit less from anti-EGFR therapy"
        },
        "left_sided": {
            "anatomic_sites": ["splenic flexure", "descending colon", "sigmoid colon",
                             "rectosigmoid junction", "rectum"],
            "molecular_features": ["Higher chromosomal instability", "EGFR overexpression"],
            "prognosis": "Generally better prognosis",
            "treatment_implications": "May benefit more from anti-EGFR therapy (if RAS wt)"
        }
    }

    # ctDNA MRD definitions
    CTDNA_MRD_DEFINITIONS = {
        "detection_methods": ["tumor-informed assays", "tumor-agnostic assays"],
        "timing": {
            "post_surgery": "2-8 weeks post-resection",
            "during_adjuvant": "During and after adjuvant chemotherapy",
            "surveillance": "Every 3-6 months for up to 3 years"
        },
        "endpoint_definitions": {
            "MRD_positive": "Detectable ctDNA above assay threshold",
            "MRD_negative": "No detectable ctDNA",
            "MRD_clearance": "Conversion from positive to negative",
            "MRD_recurrence": "Conversion from negative to positive"
        },
        "analysis_endpoints": {
            "ctDNA_DFS": "DFS by ctDNA status at landmark timepoint",
            "ctDNA_lead_time": "Time from ctDNA detection to radiographic recurrence",
            "ctDNA_dynamics": "Change in ctDNA levels over time"
        }
    }

    @classmethod
    def detect_braf_status(cls, text: str) -> BiomarkerResult:
        """Detect BRAF V600E mutation status"""
        text_lower = text.lower()

        for pattern in cls.BRAF_V600E_RULES["patterns"]:
            if re.search(pattern, text_lower):
                # Check for negative context
                if any(neg in text_lower for neg in ["wild-type", "wt", "negative", "not detected"]):
                    return BiomarkerResult(
                        biomarker="BRAF_V600E",
                        status="negative",
                        actionable=False
                    )
                return BiomarkerResult(
                    biomarker="BRAF_V600E",
                    status="positive",
                    actionable=True,
                    targeted_therapy=["encorafenib + cetuximab", "encorafenib + binimetinib + cetuximab"]
                )

        return BiomarkerResult(biomarker="BRAF_V600E", status="not_tested", actionable=False)

    @classmethod
    def determine_tumor_sidedness(cls, text: str) -> str:
        """Determine tumor sidedness from text"""
        text_lower = text.lower()

        # Check for explicit sidedness mention
        if any(term in text_lower for term in ["right-sided", "right sided", "right colon"]):
            return "right_sided"
        if any(term in text_lower for term in ["left-sided", "left sided", "left colon"]):
            return "left_sided"

        # Check anatomic sites
        right_sites = cls.SIDEDNESS_DEFINITIONS["right_sided"]["anatomic_sites"]
        left_sites = cls.SIDEDNESS_DEFINITIONS["left_sided"]["anatomic_sites"]

        for site in right_sites:
            if site.lower() in text_lower:
                return "right_sided"
        for site in left_sites:
            if site.lower() in text_lower:
                return "left_sided"

        return "unknown"

    @classmethod
    def get_ctdna_mrd_endpoints(cls) -> Dict[str, str]:
        """Return ctDNA MRD endpoint definitions for SAP"""
        return {
            "ctDNA_positivity_rate": "Proportion of patients with detectable ctDNA at specified timepoint",
            "ctDNA_DFS": "Disease-free survival stratified by ctDNA status",
            "ctDNA_lead_time": "Median time from ctDNA detection to clinical/radiographic recurrence",
            "ctDNA_clearance_rate": "Proportion achieving ctDNA clearance after adjuvant therapy",
            "ctDNA_dynamics": "Change in ctDNA variant allele frequency (VAF) over time"
        }

    @classmethod
    def get_stratification_factors(cls) -> List[str]:
        """Return CRC stratification factors for SAP"""
        return [
            "Tumor sidedness (right vs left)",
            "RAS mutation status (KRAS/NRAS wild-type vs mutant)",
            "BRAF V600E mutation status",
            "MSI-H/dMMR status",
            "Prior adjuvant chemotherapy (yes vs no)",
            "Number of metastatic sites (1 vs >1)",
            "ctDNA status at baseline (if available)"
        ]


# =============================================================================
# BREAST CANCER - RESIDUAL CANCER BURDEN (RCB)
# =============================================================================

class BreastRCBCriteria:
    """
    Residual Cancer Burden (RCB) scoring system for neoadjuvant breast cancer.
    Based on MD Anderson RCB Calculator methodology.
    """

    RCB_CLASSES = {
        "RCB-0": {
            "definition": "Pathological complete response (pCR) - ypT0/is ypN0",
            "criteria": "No residual invasive disease in breast or lymph nodes",
            "prognosis": "Excellent - 5-year EFS typically >90%"
        },
        "RCB-I": {
            "definition": "Minimal residual disease",
            "criteria": "RCB index <1.36",
            "prognosis": "Good - similar to pCR in many studies"
        },
        "RCB-II": {
            "definition": "Moderate residual disease",
            "criteria": "RCB index 1.36 to <3.28",
            "prognosis": "Intermediate"
        },
        "RCB-III": {
            "definition": "Extensive residual disease",
            "criteria": "RCB index >=3.28",
            "prognosis": "Poor - higher risk of recurrence"
        }
    }

    # RCB calculation components
    RCB_COMPONENTS = {
        "primary_tumor_bed": {
            "d1": "Largest dimension of residual tumor bed (mm)",
            "d2": "Second largest dimension of residual tumor bed (mm)",
            "cancer_cellularity": "Percentage of tumor bed area with cancer (%)",
            "in_situ_component": "Percentage of cancer that is in situ (%)"
        },
        "lymph_nodes": {
            "N_positive": "Number of positive lymph nodes",
            "d_met": "Diameter of largest metastasis (mm)"
        }
    }

    @classmethod
    def calculate_rcb_index(cls, d1: float, d2: float, cellularity: float,
                           in_situ_pct: float, n_positive: int, d_met: float) -> Tuple[float, str]:
        """
        Calculate RCB index and class.

        Formula: RCB = 1.4 * (f_inv * d_prim)^0.17 + [4 * (1-0.75^LN) * d_met]^0.17

        Where:
        - f_inv = cellularity * (1 - in_situ_pct/100)
        - d_prim = sqrt(d1 * d2)
        - LN = number of positive nodes
        """
        import math

        # Handle pCR case
        if cellularity == 0 and n_positive == 0:
            return 0.0, "RCB-0"

        # Calculate primary tumor component
        f_inv = (cellularity / 100) * (1 - in_situ_pct / 100)
        d_prim = math.sqrt(d1 * d2) if d1 > 0 and d2 > 0 else 0

        if d_prim > 0 and f_inv > 0:
            primary_component = 1.4 * math.pow(f_inv * d_prim, 0.17)
        else:
            primary_component = 0

        # Calculate lymph node component
        if n_positive > 0 and d_met > 0:
            ln_component = math.pow(4 * (1 - math.pow(0.75, n_positive)) * d_met, 0.17)
        else:
            ln_component = 0

        # Total RCB index
        rcb_index = primary_component + ln_component

        # Classify
        if rcb_index == 0:
            rcb_class = "RCB-0"
        elif rcb_index < 1.36:
            rcb_class = "RCB-I"
        elif rcb_index < 3.28:
            rcb_class = "RCB-II"
        else:
            rcb_class = "RCB-III"

        return round(rcb_index, 3), rcb_class

    @classmethod
    def get_rcb_endpoints(cls) -> Dict[str, str]:
        """Return RCB-related endpoint definitions for SAP"""
        return {
            "pCR_rate": "Proportion achieving ypT0/is ypN0 (RCB-0)",
            "RCB_0_I_rate": "Proportion achieving RCB-0 or RCB-I (minimal residual disease)",
            "RCB_distribution": "Distribution across RCB classes (0, I, II, III)",
            "EFS_by_RCB": "Event-free survival stratified by RCB class",
            "RCB_as_continuous": "RCB index as continuous variable for correlation analyses"
        }

    @classmethod
    def get_pcr_definitions(cls) -> Dict[str, str]:
        """Return pCR definitions commonly used"""
        return {
            "ypT0_ypN0": "No invasive or in situ residual disease in breast or nodes (strict)",
            "ypT0_is_ypN0": "No invasive residual disease; in situ allowed (FDA preferred)",
            "ypT0_any_N": "No residual invasive disease in breast regardless of nodal status"
        }


# =============================================================================
# PROSTATE CANCER - PCWG3 CRITERIA
# =============================================================================

class ProstatePCWG3Criteria:
    """
    PCWG3 (Prostate Cancer Working Group 3) criteria for mCRPC.
    Includes bone-specific progression rules and composite endpoints.
    """

    # PSA response definitions
    PSA_RESPONSE_RULES = {
        "PSA50": {
            "definition": ">=50% decline from baseline",
            "confirmation": "Confirmed by second value >=4 weeks later",
            "timing": "After >=12 weeks of therapy"
        },
        "PSA30": {
            "definition": ">=30% decline from baseline",
            "confirmation": "Confirmed by second value >=4 weeks later"
        },
        "PSA_progression": {
            "definition": ">=25% increase AND absolute increase >=2 ng/mL from nadir",
            "confirmation": "Confirmed by second value >=3 weeks later",
            "additional": "If no decline, progression requires 25% increase from baseline at >=12 weeks"
        }
    }

    # Bone-specific progression (PCWG3)
    BONE_PROGRESSION_RULES = {
        "first_scan": {
            "rule": ">=2 new lesions on first post-baseline scan",
            "action": "Requires confirmation on next scan >=6 weeks later"
        },
        "confirmation_scan": {
            "rule": ">=2 additional new lesions (total >=4 new lesions)",
            "date": "Date of progression = first scan date showing >=2 new lesions"
        },
        "subsequent_scans": {
            "rule": ">=2 new lesions compared to prior scan = progression",
            "note": "No confirmation required after first progression"
        },
        "important_notes": [
            "Bone lesions NEVER constitute CR - best response is PR or SD",
            "Flare phenomenon must be considered in first 12 weeks",
            "Each new lesion should be confirmed as metastatic if possible"
        ]
    }

    # Soft tissue response (RECIST 1.1 for measurable disease)
    SOFT_TISSUE_RULES = {
        "measurable": "Per RECIST 1.1 for lymph nodes and visceral metastases",
        "lymph_nodes": "Short axis >=15mm for target lesions",
        "bone_not_measurable": "Bone lesions are NOT measurable (non-target only)"
    }

    # Composite endpoints
    COMPOSITE_ENDPOINTS = {
        "rPFS": {
            "name": "Radiographic progression-free survival",
            "components": [
                "Bone progression per PCWG3",
                "Soft tissue progression per RECIST 1.1",
                "Death from any cause"
            ],
            "analysis": "Time from randomization to first event"
        },
        "MFS": {
            "name": "Metastasis-free survival",
            "definition": "Time from randomization to metastasis or death",
            "use": "nmCRPC trials (no detectable metastases at baseline)"
        },
        "time_to_PSA_progression": {
            "name": "Time to PSA progression",
            "definition": "Per PCWG3 PSA progression criteria"
        },
        "time_to_symptomatic_skeletal_event": {
            "name": "Time to symptomatic skeletal event (SSE)",
            "components": [
                "Pathological fracture",
                "Spinal cord compression",
                "Radiation to bone",
                "Surgery to bone"
            ]
        }
    }

    @classmethod
    def assess_psa_response(cls, baseline: float, current: float, nadir: float) -> Dict[str, any]:
        """Assess PSA response status"""
        pct_change_from_baseline = ((current - baseline) / baseline) * 100
        pct_change_from_nadir = ((current - nadir) / nadir) * 100 if nadir > 0 else 0

        result = {
            "baseline": baseline,
            "current": current,
            "nadir": nadir,
            "pct_change_from_baseline": round(pct_change_from_baseline, 1),
            "pct_change_from_nadir": round(pct_change_from_nadir, 1),
            "PSA50_response": pct_change_from_baseline <= -50,
            "PSA30_response": pct_change_from_baseline <= -30,
            "PSA_progression": (pct_change_from_nadir >= 25 and (current - nadir) >= 2)
        }
        return result

    @classmethod
    def get_rpfs_definition(cls) -> str:
        """Return rPFS definition for SAP"""
        return """
Radiographic Progression-Free Survival (rPFS):
Time from randomization to radiographic progression or death from any cause.

Radiographic progression is defined as ANY of:
1. BONE: >=2 new lesions on bone scan with confirmation per PCWG3
2. SOFT TISSUE: Progressive disease per RECIST 1.1 in lymph nodes/visceral sites
3. DEATH: Death from any cause

Censoring rules:
- Patients without progression/death: censored at last adequate tumor assessment
- Patients starting new anticancer therapy: censored at last assessment before new therapy
- Patients with no baseline assessment: censored at randomization (Day 1)
"""

    @classmethod
    def get_stratification_factors(cls) -> List[str]:
        """Return prostate cancer stratification factors"""
        return [
            "Prior docetaxel for mCRPC (yes vs no)",
            "Presence of visceral metastases (yes vs no)",
            "ECOG performance status (0 vs 1)",
            "Prior abiraterone or enzalutamide (yes vs no)",
            "PSA doubling time (<6 months vs >=6 months)"
        ]


# =============================================================================
# PEDIATRIC ONCOLOGY - INRG (Neuroblastoma) and IRS (Rhabdomyosarcoma)
# =============================================================================

class PediatricOncologyCriteria:
    """
    Pediatric oncology staging and response criteria:
    - INRG (International Neuroblastoma Risk Group) staging
    - IRS (Intergroup Rhabdomyosarcoma Study) staging/grouping
    - COG response criteria
    """

    # INRG Staging System for Neuroblastoma
    INRG_STAGING = {
        "L1": {
            "definition": "Localized tumor not involving vital structures",
            "idrf": "No image-defined risk factors (IDRFs)",
            "treatment": "Surgery alone may be sufficient"
        },
        "L2": {
            "definition": "Localized tumor with one or more IDRFs",
            "idrf": "One or more IDRFs present",
            "treatment": "Chemotherapy often needed before surgery"
        },
        "M": {
            "definition": "Metastatic disease",
            "sites": "Distant metastases (excluding MS)",
            "treatment": "Intensive multimodal therapy"
        },
        "MS": {
            "definition": "Metastatic special - infants <18 months",
            "sites": "Skin, liver, and/or bone marrow involvement only",
            "prognosis": "Often favorable despite metastases"
        }
    }

    # Image-Defined Risk Factors (IDRFs)
    INRG_IDRFs = [
        "Encasement of major vessels (aorta, vena cava, etc.)",
        "Extension into spinal canal",
        "Infiltration of adjacent organs",
        "Crossing midline with encasement of vessels",
        "Tumor in multiple body compartments"
    ]

    # INRG Risk Classification
    INRG_RISK_GROUPS = {
        "Very Low Risk": {
            "criteria": ["L1 with favorable biology", "MS with favorable biology"],
            "5yr_EFS": ">90%"
        },
        "Low Risk": {
            "criteria": ["L2 with favorable biology, MYCN non-amplified"],
            "5yr_EFS": "~85-90%"
        },
        "Intermediate Risk": {
            "criteria": ["L2 with unfavorable features", "M in infants"],
            "5yr_EFS": "~70-85%"
        },
        "High Risk": {
            "criteria": ["M in >18 months", "MYCN amplified any stage"],
            "5yr_EFS": "~40-50% with current therapy"
        }
    }

    # IRS/COG Grouping for Rhabdomyosarcoma
    IRS_CLINICAL_GROUPS = {
        "Group I": {
            "definition": "Localized, completely resected",
            "subgroups": {
                "IA": "Confined to site of origin",
                "IB": "Infiltration beyond site of origin"
            }
        },
        "Group II": {
            "definition": "Microscopic residual disease or regional nodes",
            "subgroups": {
                "IIA": "Gross resection with microscopic residual",
                "IIB": "Regional disease with nodes completely resected",
                "IIC": "Nodes with microscopic residual"
            }
        },
        "Group III": {
            "definition": "Gross residual disease after biopsy only",
            "subgroups": {
                "IIIA": "Biopsy only",
                "IIIB": "Gross residual after major resection (>50%)"
            }
        },
        "Group IV": {
            "definition": "Distant metastases at diagnosis"
        }
    }

    # COG Risk Stratification for RMS
    RMS_RISK_GROUPS = {
        "Low Risk": {
            "criteria": ["Group I/II embryonal, favorable site",
                        "Group I orbital embryonal"],
            "therapy": "VAC chemotherapy, reduced intensity"
        },
        "Intermediate Risk": {
            "criteria": ["Group III embryonal", "Group I-III alveolar non-metastatic"],
            "therapy": "VAC or VAC/VI chemotherapy with radiation"
        },
        "High Risk": {
            "criteria": ["Group IV (metastatic)", "Alveolar histology with unfavorable features"],
            "therapy": "Intensive chemotherapy, radiation, consider novel agents"
        }
    }

    # MIBG Response Criteria for Neuroblastoma
    MIBG_RESPONSE = {
        "Curie_score": {
            "description": "Semi-quantitative scoring of MIBG uptake",
            "range": "0-45 (9 body segments x 0-3 intensity)",
            "CR": "Score = 0 (no MIBG-avid disease)",
            "PR": "Score reduction >=50% from baseline"
        },
        "SIOPEN_score": {
            "description": "Alternative scoring system",
            "range": "0-72",
            "application": "More granular assessment"
        }
    }

    @classmethod
    def classify_neuroblastoma_risk(cls, stage: str, mycn: str, age_months: int,
                                    histology: str, ploidy: str = None) -> str:
        """Classify neuroblastoma risk group"""
        mycn_amp = mycn.lower() in ["amplified", "amp", "positive"]

        # MYCN amplification always high risk
        if mycn_amp:
            return "High Risk"

        # Stage-based classification
        if stage == "L1":
            return "Very Low Risk"
        elif stage == "L2":
            # Would need more biology info in real implementation
            return "Low Risk" if histology.lower() == "favorable" else "Intermediate Risk"
        elif stage == "MS":
            return "Very Low Risk" if age_months < 18 else "Intermediate Risk"
        elif stage == "M":
            return "Intermediate Risk" if age_months < 18 else "High Risk"

        return "Unknown"

    @classmethod
    def get_pediatric_endpoints(cls) -> Dict[str, str]:
        """Return pediatric oncology endpoint definitions"""
        return {
            "EFS": "Event-free survival: time to relapse, progression, secondary malignancy, or death",
            "OS": "Overall survival: time to death from any cause",
            "ORR": "Objective response rate per disease-specific criteria",
            "MIBG_response": "MIBG response per Curie or SIOPEN scoring (neuroblastoma)",
            "pCR": "Pathological complete response at delayed primary surgery"
        }


# =============================================================================
# MESOTHELIOMA - Modified RECIST
# =============================================================================

class MesotheliomaCriteria:
    """
    Modified RECIST criteria for pleural mesothelioma.
    Uses unidimensional measurement perpendicular to chest wall.
    """

    # Modified RECIST for Mesothelioma
    MEASUREMENT_RULES = {
        "target_lesions": {
            "measurement_method": "Unidimensional measurement perpendicular to chest wall or mediastinum",
            "number": "Up to 6 pleural sites (max 2 per level)",
            "minimum_size": ">=10mm on CT",
            "levels": ["Upper zone", "Middle zone", "Lower zone"] * 2,  # bilateral
            "exclusion": "Do not include fissural thickness"
        },
        "measurement_technique": {
            "plane": "Axial CT images",
            "direction": "Perpendicular to chest wall/mediastinum",
            "consistency": "Same anatomic level and position at each assessment"
        }
    }

    # Response definitions
    RESPONSE_CRITERIA = {
        "CR": {
            "definition": "Disappearance of all target and non-target lesions",
            "pleural_effusion": "Must be absent or non-malignant"
        },
        "PR": {
            "definition": ">=30% decrease in sum of unidimensional measurements",
            "confirmation": "Confirmed at least 4 weeks later"
        },
        "SD": {
            "definition": "Neither PR nor PD criteria met"
        },
        "PD": {
            "definition": ">=20% increase in sum of measurements AND absolute increase >=5mm",
            "new_lesions": "OR appearance of new lesions",
            "note": "Increase must be from nadir"
        }
    }

    # Special considerations
    SPECIAL_CONSIDERATIONS = {
        "pleural_effusion": {
            "rule": "Not measured as target lesion",
            "progression": "New or increasing effusion alone does not constitute PD unless cytologically confirmed",
            "response": "Decrease in effusion can support response assessment"
        },
        "chest_wall_invasion": {
            "rule": "Document presence but don't include in measurements"
        },
        "lymph_nodes": {
            "rule": "Measure short axis per standard RECIST 1.1",
            "target": ">=15mm short axis for target lesion"
        }
    }

    @classmethod
    def calculate_response(cls, baseline_sum: float, current_sum: float,
                          nadir_sum: float) -> ResponseAssessment:
        """Calculate response per modified RECIST for mesothelioma"""
        # Check for CR
        if current_sum == 0:
            return ResponseAssessment(
                category=ResponseCategory.CR,
                criteria_used="Modified RECIST for Mesothelioma",
                measurements={"sum": current_sum}
            )

        # Calculate changes
        change_from_baseline = ((current_sum - baseline_sum) / baseline_sum) * 100
        change_from_nadir = ((current_sum - nadir_sum) / nadir_sum) * 100 if nadir_sum > 0 else 0

        # Check for PD
        if change_from_nadir >= 20 and (current_sum - nadir_sum) >= 5:
            return ResponseAssessment(
                category=ResponseCategory.PD,
                criteria_used="Modified RECIST for Mesothelioma",
                measurements={
                    "sum": current_sum,
                    "change_from_nadir_pct": round(change_from_nadir, 1)
                }
            )

        # Check for PR
        if change_from_baseline <= -30:
            return ResponseAssessment(
                category=ResponseCategory.PR,
                criteria_used="Modified RECIST for Mesothelioma",
                measurements={
                    "sum": current_sum,
                    "change_from_baseline_pct": round(change_from_baseline, 1)
                },
                notes=["Requires confirmation at >=4 weeks"]
            )

        # SD
        return ResponseAssessment(
            category=ResponseCategory.SD,
            criteria_used="Modified RECIST for Mesothelioma",
            measurements={
                "sum": current_sum,
                "change_from_baseline_pct": round(change_from_baseline, 1)
            }
        )

    @classmethod
    def get_measurement_guidance(cls) -> str:
        """Return measurement guidance for SAP"""
        return """
Modified RECIST for Pleural Mesothelioma - Measurement Guidance:

1. TARGET LESION SELECTION:
   - Select up to 6 pleural sites (maximum 2 per level: upper/middle/lower, bilateral)
   - Each measurement must be >=10mm
   - Do NOT include fissural thickening

2. MEASUREMENT TECHNIQUE:
   - Measure PERPENDICULAR to chest wall or mediastinum
   - Use same anatomic level and window settings at each assessment
   - Measure on axial CT images

3. SUM OF MEASUREMENTS:
   - Sum all target lesion measurements (unidimensional)
   - Track baseline sum, nadir sum, and current sum

4. RESPONSE ASSESSMENT:
   - CR: Complete disappearance of all tumor
   - PR: >=30% decrease from baseline (confirm at 4+ weeks)
   - PD: >=20% increase from nadir AND >=5mm absolute increase
   - SD: Neither PR nor PD

5. SPECIAL NOTES:
   - Pleural effusion: Not a target lesion; new/increasing effusion alone =/= PD
   - Lymph nodes: Measure short axis per RECIST 1.1
"""


# =============================================================================
# MAIN REGISTRY AND FACTORY
# =============================================================================

class SpecializedCriteriaRegistry:
    """Registry for all specialized oncology criteria modules"""

    CRITERIA_MODULES = {
        "lung_NSCLC": LungNSCLCBiomarkers,
        "colorectal_CRC": ColorectalCRCCriteria,
        "breast_HER2_pCR": BreastRCBCriteria,
        "prostate_PCWG": ProstatePCWG3Criteria,
        "pediatric": PediatricOncologyCriteria,
        "mesothelioma": MesotheliomaCriteria
    }

    @classmethod
    def get_criteria_module(cls, category: str):
        """Get the criteria module for a specific category"""
        return cls.CRITERIA_MODULES.get(category)

    @classmethod
    def get_all_categories(cls) -> List[str]:
        """Get list of all implemented categories"""
        return list(cls.CRITERIA_MODULES.keys())

    @classmethod
    def get_stratification_factors(cls, category: str) -> List[str]:
        """Get stratification factors for a category"""
        module = cls.get_criteria_module(category)
        if module and hasattr(module, 'get_stratification_factors'):
            return module.get_stratification_factors()
        return []

    @classmethod
    def detect_applicable_criteria(cls, protocol_text: str) -> List[str]:
        """Detect which specialized criteria apply to a protocol"""
        text_lower = protocol_text.lower()
        applicable = []

        detection_keywords = {
            "lung_NSCLC": ["nsclc", "non-small cell lung", "lung adenocarcinoma", "lung cancer"],
            "colorectal_CRC": ["colorectal", "colon cancer", "rectal cancer", "crc"],
            "breast_HER2_pCR": ["breast cancer", "neoadjuvant", "her2", "pcr", "residual"],
            "prostate_PCWG": ["prostate cancer", "mcrpc", "castration-resistant", "psa"],
            "pediatric": ["neuroblastoma", "rhabdomyosarcoma", "pediatric", "childhood cancer"],
            "mesothelioma": ["mesothelioma", "pleural", "asbestos"]
        }

        for category, keywords in detection_keywords.items():
            if any(kw in text_lower for kw in keywords):
                applicable.append(category)

        return applicable


# Export all classes
__all__ = [
    'ResponseCategory',
    'BiomarkerResult',
    'ResponseAssessment',
    'LungNSCLCBiomarkers',
    'ColorectalCRCCriteria',
    'BreastRCBCriteria',
    'ProstatePCWG3Criteria',
    'PediatricOncologyCriteria',
    'MesotheliomaCriteria',
    'SpecializedCriteriaRegistry'
]
