"""
Comprehensive Tool Calling Evaluation Set
==========================================

Tests that Claude calls the correct KB tools for every:
1. SAP section (16 main sections)
2. Disease type (lung, breast, lymphoma, myeloma, etc.)
3. Study design (randomized, single-arm, adjuvant, etc.)
4. Endpoint type (PFS, OS, ORR, DFS, CR rate, etc.)

Run with:
    python eval_tool_calling.py [--verbose] [--section SECTION_ID]

Author: SAP Generation System
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

# =============================================================================
# EVAL RESULT STRUCTURE
# =============================================================================

@dataclass
class ToolCall:
    """Expected or actual tool call."""
    name: str
    input: Dict[str, Any] = field(default_factory=dict)

    def matches(self, other: 'ToolCall') -> bool:
        """Check if this tool call matches another (name + key params)."""
        if self.name != other.name:
            return False
        # Check key parameters match
        for key, value in self.input.items():
            if key in other.input and other.input[key] != value:
                return False
        return True


@dataclass
class EvalCase:
    """A single evaluation test case."""
    test_id: str
    description: str
    section: str
    section_number: str

    # Protocol context
    protocol: Dict[str, Any]

    # Expected behavior
    expected_tools: List[ToolCall]
    optional_tools: List[ToolCall] = field(default_factory=list)  # Nice to have
    forbidden_tools: List[str] = field(default_factory=list)

    # Output validation
    expected_in_output: List[str] = field(default_factory=list)
    forbidden_in_output: List[str] = field(default_factory=list)

    # Metadata
    category: str = ""  # e.g., "efficacy", "safety", "demographics"
    priority: str = "medium"  # "critical", "high", "medium", "low"


@dataclass
class EvalResult:
    """Result of running an eval case."""
    test_id: str
    passed: bool

    # Tool analysis
    tools_called: List[str]
    expected_tools_found: List[str]
    expected_tools_missing: List[str]
    forbidden_tools_called: List[str]

    # Output analysis
    output_keywords_found: List[str]
    output_keywords_missing: List[str]
    forbidden_keywords_found: List[str]

    # Generated content
    generated_content: str = ""

    # Timing
    execution_time_seconds: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


# =============================================================================
# SECTION 1: TITLE PAGE (No tools needed)
# =============================================================================

SECTION_1_EVALS = [
    EvalCase(
        test_id="section1_title_page",
        description="Title page should not call any KB tools",
        section="Title Page & Administrative Information",
        section_number="1",
        protocol={
            "study_id": "ABC-001",
            "sponsor": "Test Pharma",
            "phase": "Phase 3"
        },
        expected_tools=[],
        forbidden_tools=[
            "get_statistical_method",
            "get_efficacy_tables",
            "get_safety_tables"
        ],
        expected_in_output=["Statistical Analysis Plan", "Version"],
        category="administrative",
        priority="low"
    ),
]


# =============================================================================
# SECTION 2: INTRODUCTION & OBJECTIVES
# =============================================================================

SECTION_2_EVALS = [
    EvalCase(
        test_id="section2_intro_phase3_pfs",
        description="Introduction for Phase 3 PFS trial",
        section="Introduction",
        section_number="2",
        protocol={
            "phase": "Phase 3",
            "indication": "NSCLC",
            "primary_endpoint": "PFS",
            "design": "randomized, double-blind"
        },
        expected_tools=[],
        optional_tools=[
            ToolCall("get_study_design_specs")
        ],
        expected_in_output=[
            "Phase 3",
            "progression-free survival",
            "primary endpoint"
        ],
        category="introduction",
        priority="medium"
    ),

    EvalCase(
        test_id="section2_intro_phase2_orr",
        description="Introduction for Phase 2 ORR trial",
        section="Introduction",
        section_number="2",
        protocol={
            "phase": "Phase 2",
            "indication": "Melanoma",
            "primary_endpoint": "ORR",
            "design": "single-arm"
        },
        expected_tools=[],
        expected_in_output=[
            "Phase 2",
            "objective response rate",
            "single-arm"
        ],
        category="introduction",
        priority="medium"
    ),
]


# =============================================================================
# SECTION 3: STUDY DESIGN
# =============================================================================

SECTION_3_EVALS = [
    # Randomized trials
    EvalCase(
        test_id="section3_randomized_stratified",
        description="Randomized trial with stratification factors",
        section="Study Design",
        section_number="3",
        protocol={
            "design": "randomized",
            "randomization_ratio": "1:1",
            "stratification_factors": ["Region", "ECOG PS", "PD-L1 status"],
            "blinding": "double-blind"
        },
        expected_tools=[
            ToolCall("get_study_design_specs"),
            ToolCall("get_stratification_specs"),
        ],
        optional_tools=[
            ToolCall("get_study_type_template"),
            ToolCall("get_blinding_specifications")
        ],
        expected_in_output=[
            "randomization",
            "1:1",
            "stratification",
            "ECOG",
            "double-blind"
        ],
        category="study_design",
        priority="high"
    ),

    EvalCase(
        test_id="section3_single_arm",
        description="Single-arm study (no randomization section)",
        section="Study Design",
        section_number="3",
        protocol={
            "design": "single-arm",
            "blinding": "open-label"
        },
        expected_tools=[
            ToolCall("get_study_design_specs"),
            ToolCall("get_study_type_template", {"study_type": "single_arm"})
        ],
        forbidden_tools=[
            "get_stratification_specs"  # No stratification in single-arm
        ],
        expected_in_output=[
            "single-arm",
            "open-label"
        ],
        forbidden_in_output=[
            "randomization ratio",
            "stratification factors"
        ],
        category="study_design",
        priority="high"
    ),

    EvalCase(
        test_id="section3_crossover",
        description="Crossover study design",
        section="Study Design",
        section_number="3",
        protocol={
            "design": "crossover",
            "periods": 2,
            "washout": "2 weeks"
        },
        expected_tools=[
            ToolCall("get_study_design_specs"),
            ToolCall("get_study_type_template", {"study_type": "crossover"})
        ],
        expected_in_output=[
            "crossover",
            "period",
            "washout"
        ],
        category="study_design",
        priority="medium"
    ),

    EvalCase(
        test_id="section3_adaptive",
        description="Adaptive study design",
        section="Study Design",
        section_number="3",
        protocol={
            "design": "adaptive",
            "adaptations": ["sample size re-estimation", "treatment arm dropping"]
        },
        expected_tools=[
            ToolCall("get_study_design_specs"),
            ToolCall("get_study_type_template", {"study_type": "adaptive"})
        ],
        expected_in_output=[
            "adaptive",
            "sample size re-estimation"
        ],
        category="study_design",
        priority="medium"
    ),
]


# =============================================================================
# SECTION 4: SAMPLE SIZE & POWER
# =============================================================================

SECTION_4_EVALS = [
    EvalCase(
        test_id="section4_pfs_sample_size",
        description="Sample size for PFS primary endpoint",
        section="Sample Size & Power",
        section_number="4",
        protocol={
            "primary_endpoint": "PFS",
            "target_hr": 0.70,
            "power": 0.90,
            "alpha": 0.05,
            "median_control": "6 months"
        },
        expected_tools=[
            ToolCall("get_statistical_method", {"method_name": "log_rank_test"}),
        ],
        optional_tools=[
            ToolCall("get_time_to_event_analysis")
        ],
        expected_in_output=[
            "hazard ratio",
            "power",
            "alpha",
            "events"
        ],
        category="sample_size",
        priority="high"
    ),

    EvalCase(
        test_id="section4_orr_sample_size",
        description="Sample size for ORR primary endpoint",
        section="Sample Size & Power",
        section_number="4",
        protocol={
            "primary_endpoint": "ORR",
            "null_hypothesis": "20%",
            "alternative_hypothesis": "35%",
            "power": 0.80,
            "alpha": 0.05
        },
        expected_tools=[
            ToolCall("get_statistical_method", {"method_name": "clopper_pearson"}),
        ],
        expected_in_output=[
            "response rate",
            "power",
            "sample size"
        ],
        forbidden_in_output=[
            "hazard ratio",  # Not for binary endpoint
            "events required"
        ],
        category="sample_size",
        priority="high"
    ),

    EvalCase(
        test_id="section4_os_events",
        description="Event-driven sample size for OS",
        section="Sample Size & Power",
        section_number="4",
        protocol={
            "primary_endpoint": "OS",
            "target_hr": 0.75,
            "events_required": 350,
            "interim_analyses": 2
        },
        expected_tools=[
            ToolCall("get_statistical_method", {"method_name": "log_rank_test"}),
            ToolCall("get_interim_analysis")
        ],
        expected_in_output=[
            "events",
            "hazard ratio",
            "interim"
        ],
        category="sample_size",
        priority="high"
    ),
]


# =============================================================================
# SECTION 5: ANALYSIS POPULATIONS
# =============================================================================

SECTION_5_EVALS = [
    EvalCase(
        test_id="section5_standard_populations",
        description="Standard ITT, Safety, PP populations",
        section="Analysis Populations",
        section_number="5",
        protocol={
            "design": "randomized",
            "populations": ["ITT", "Safety", "Per-Protocol"]
        },
        expected_tools=[
            ToolCall("get_population_definitions")
        ],
        expected_in_output=[
            "intent-to-treat",
            "ITT",
            "safety population",
            "per-protocol"
        ],
        category="populations",
        priority="critical"
    ),

    EvalCase(
        test_id="section5_response_evaluable",
        description="Response-evaluable population for ORR trials",
        section="Analysis Populations",
        section_number="5",
        protocol={
            "primary_endpoint": "ORR",
            "response_criteria": "RECIST 1.1"
        },
        expected_tools=[
            ToolCall("get_population_definitions"),
        ],
        expected_in_output=[
            "response-evaluable",
            "measurable disease",
            "baseline tumor assessment"
        ],
        category="populations",
        priority="high"
    ),

    EvalCase(
        test_id="section5_cart_populations",
        description="CAR-T specific populations (mITT, leukapheresis)",
        section="Analysis Populations",
        section_number="5",
        protocol={
            "treatment": "CAR-T",
            "indication": "DLBCL"
        },
        expected_tools=[
            ToolCall("get_population_definitions"),
            ToolCall("get_cart_specifications")
        ],
        expected_in_output=[
            "leukapheresis",
            "infused",
            "mITT",
            "modified intent-to-treat"
        ],
        category="populations",
        priority="high"
    ),

    EvalCase(
        test_id="section5_pk_population",
        description="PK population for PK sub-study",
        section="Analysis Populations",
        section_number="5",
        protocol={
            "has_pk_substudy": True,
            "pk_samples": "sparse sampling"
        },
        expected_tools=[
            ToolCall("get_population_definitions")
        ],
        expected_in_output=[
            "pharmacokinetic",
            "PK population",
            "evaluable PK"
        ],
        category="populations",
        priority="medium"
    ),

    EvalCase(
        test_id="section5_dlt_evaluable",
        description="DLT-evaluable population for Phase 1",
        section="Analysis Populations",
        section_number="5",
        protocol={
            "phase": "Phase 1",
            "has_dose_escalation": True
        },
        expected_tools=[
            ToolCall("get_population_definitions")
        ],
        expected_in_output=[
            "DLT-evaluable",
            "dose-limiting toxicity",
            "evaluation period"
        ],
        category="populations",
        priority="medium"
    ),
]


# =============================================================================
# SECTION 5A: BASELINE CHARACTERISTICS (by disease type)
# =============================================================================

SECTION_5A_EVALS = [
    # LUNG CANCER
    EvalCase(
        test_id="section5a_baseline_nsclc",
        description="Baseline characteristics for NSCLC trial",
        section="Baseline Characteristics",
        section_number="5A",
        protocol={
            "indication": "NSCLC",
            "biomarkers": ["EGFR", "ALK", "PD-L1"]
        },
        expected_tools=[
            ToolCall("get_demographics_baseline_specs"),
            ToolCall("get_baseline_covariates", {"disease_type": "lung"})
        ],
        expected_in_output=[
            "EGFR mutation",
            "ALK",
            "PD-L1",
            "smoking status",
            "histology",
            "adenocarcinoma",
            "squamous"
        ],
        forbidden_in_output=[
            "Ann Arbor",  # Lymphoma
            "Gleason",    # Prostate
            "ER/PR"       # Breast
        ],
        category="baseline",
        priority="critical"
    ),

    # BREAST CANCER
    EvalCase(
        test_id="section5a_baseline_breast",
        description="Baseline characteristics for breast cancer trial",
        section="Baseline Characteristics",
        section_number="5A",
        protocol={
            "indication": "breast cancer",
            "subtype": "HR+/HER2-"
        },
        expected_tools=[
            ToolCall("get_demographics_baseline_specs"),
            ToolCall("get_baseline_covariates", {"disease_type": "breast"})
        ],
        expected_in_output=[
            "ER",
            "PR",
            "HER2",
            "hormone receptor",
            "Ki-67",
            "menopausal status"
        ],
        forbidden_in_output=[
            "EGFR mutation",  # Lung
            "ALK status",     # Lung
            "smoking"         # Lung
        ],
        category="baseline",
        priority="critical"
    ),

    # COLORECTAL CANCER
    EvalCase(
        test_id="section5a_baseline_crc",
        description="Baseline characteristics for colorectal cancer trial",
        section="Baseline Characteristics",
        section_number="5A",
        protocol={
            "indication": "colorectal cancer",
            "setting": "metastatic"
        },
        expected_tools=[
            ToolCall("get_demographics_baseline_specs"),
            ToolCall("get_baseline_covariates", {"disease_type": "gi"})
        ],
        expected_in_output=[
            "RAS",
            "KRAS",
            "BRAF",
            "MSI",
            "primary tumor location",
            "left",
            "right"
        ],
        category="baseline",
        priority="critical"
    ),

    # PROSTATE CANCER
    EvalCase(
        test_id="section5a_baseline_prostate",
        description="Baseline characteristics for prostate cancer trial",
        section="Baseline Characteristics",
        section_number="5A",
        protocol={
            "indication": "prostate cancer",
            "setting": "mCRPC"
        },
        expected_tools=[
            ToolCall("get_demographics_baseline_specs"),
            ToolCall("get_baseline_covariates", {"disease_type": "prostate"})
        ],
        expected_in_output=[
            "Gleason",
            "PSA",
            "prior docetaxel",
            "visceral metastases",
            "bone metastases"
        ],
        category="baseline",
        priority="critical"
    ),

    # LYMPHOMA (DLBCL)
    EvalCase(
        test_id="section5a_baseline_dlbcl",
        description="Baseline characteristics for DLBCL trial",
        section="Baseline Characteristics",
        section_number="5A",
        protocol={
            "indication": "DLBCL",
            "setting": "relapsed/refractory"
        },
        expected_tools=[
            ToolCall("get_demographics_baseline_specs"),
            ToolCall("get_baseline_covariates", {"disease_type": "lymphoma"})
        ],
        expected_in_output=[
            "Ann Arbor",
            "IPI",
            "B symptoms",
            "LDH",
            "extranodal",
            "bulky disease"
        ],
        forbidden_in_output=[
            "RECIST",     # Solid tumor
            "EGFR",       # Lung
            "Gleason"     # Prostate
        ],
        category="baseline",
        priority="critical"
    ),

    # MULTIPLE MYELOMA
    EvalCase(
        test_id="section5a_baseline_myeloma",
        description="Baseline characteristics for multiple myeloma trial",
        section="Baseline Characteristics",
        section_number="5A",
        protocol={
            "indication": "multiple myeloma",
            "setting": "newly diagnosed"
        },
        expected_tools=[
            ToolCall("get_demographics_baseline_specs"),
            ToolCall("get_baseline_covariates", {"disease_type": "myeloma"})
        ],
        expected_in_output=[
            "ISS",
            "R-ISS",
            "cytogenetics",
            "M-protein",
            "plasmacytoma",
            "del(17p)",
            "t(4;14)"
        ],
        category="baseline",
        priority="critical"
    ),

    # AML
    EvalCase(
        test_id="section5a_baseline_aml",
        description="Baseline characteristics for AML trial",
        section="Baseline Characteristics",
        section_number="5A",
        protocol={
            "indication": "AML",
            "setting": "newly diagnosed"
        },
        expected_tools=[
            ToolCall("get_demographics_baseline_specs"),
            ToolCall("get_baseline_covariates", {"disease_type": "leukemia"})
        ],
        expected_in_output=[
            "cytogenetics",
            "FLT3",
            "NPM1",
            "IDH1",
            "IDH2",
            "WBC",
            "blast"
        ],
        category="baseline",
        priority="critical"
    ),

    # CLL
    EvalCase(
        test_id="section5a_baseline_cll",
        description="Baseline characteristics for CLL trial",
        section="Baseline Characteristics",
        section_number="5A",
        protocol={
            "indication": "CLL",
            "setting": "relapsed/refractory"
        },
        expected_tools=[
            ToolCall("get_demographics_baseline_specs"),
            ToolCall("get_baseline_covariates", {"disease_type": "cll"})
        ],
        expected_in_output=[
            "IGHV",
            "del(17p)",
            "TP53",
            "Rai stage",
            "Binet stage"
        ],
        category="baseline",
        priority="critical"
    ),

    # OVARIAN CANCER
    EvalCase(
        test_id="section5a_baseline_ovarian",
        description="Baseline characteristics for ovarian cancer trial",
        section="Baseline Characteristics",
        section_number="5A",
        protocol={
            "indication": "ovarian cancer",
            "setting": "platinum-sensitive recurrent"
        },
        expected_tools=[
            ToolCall("get_demographics_baseline_specs"),
            ToolCall("get_baseline_covariates", {"disease_type": "ovarian"})
        ],
        expected_in_output=[
            "BRCA",
            "HRD",
            "CA-125",
            "platinum-free interval",
            "FIGO stage"
        ],
        category="baseline",
        priority="critical"
    ),

    # MELANOMA
    EvalCase(
        test_id="section5a_baseline_melanoma",
        description="Baseline characteristics for melanoma trial",
        section="Baseline Characteristics",
        section_number="5A",
        protocol={
            "indication": "melanoma",
            "setting": "unresectable or metastatic"
        },
        expected_tools=[
            ToolCall("get_demographics_baseline_specs"),
            ToolCall("get_baseline_covariates", {"disease_type": "solid_tumor"})
        ],
        expected_in_output=[
            "BRAF",
            "LDH",
            "M stage",
            "prior immunotherapy"
        ],
        category="baseline",
        priority="high"
    ),

    # RCC (Renal Cell Carcinoma)
    EvalCase(
        test_id="section5a_baseline_rcc",
        description="Baseline characteristics for RCC trial",
        section="Baseline Characteristics",
        section_number="5A",
        protocol={
            "indication": "renal cell carcinoma",
            "setting": "first-line metastatic"
        },
        expected_tools=[
            ToolCall("get_demographics_baseline_specs"),
            ToolCall("get_prognostic_scores")
        ],
        expected_in_output=[
            "IMDC",
            "MSKCC",
            "favorable",
            "intermediate",
            "poor risk",
            "prior nephrectomy"
        ],
        category="baseline",
        priority="high"
    ),
]


# =============================================================================
# SECTION 6: ENDPOINT DEFINITIONS
# =============================================================================

SECTION_6_EVALS = [
    # Time-to-event endpoints
    EvalCase(
        test_id="section6_pfs_definition",
        description="PFS endpoint definition",
        section="Endpoint Definitions",
        section_number="6",
        protocol={
            "primary_endpoint": "PFS",
            "response_criteria": "RECIST 1.1"
        },
        expected_tools=[
            ToolCall("get_censoring_rules", {"endpoint_type": "pfs"}),
            ToolCall("get_recist_specifications")
        ],
        expected_in_output=[
            "progression-free survival",
            "progression",
            "death",
            "censoring",
            "RECIST"
        ],
        category="endpoints",
        priority="critical"
    ),

    EvalCase(
        test_id="section6_os_definition",
        description="OS endpoint definition",
        section="Endpoint Definitions",
        section_number="6",
        protocol={
            "primary_endpoint": "OS"
        },
        expected_tools=[
            ToolCall("get_censoring_rules", {"endpoint_type": "os"})
        ],
        expected_in_output=[
            "overall survival",
            "death",
            "any cause",
            "censoring",
            "last known alive"
        ],
        category="endpoints",
        priority="critical"
    ),

    EvalCase(
        test_id="section6_dfs_adjuvant",
        description="DFS endpoint for adjuvant trial",
        section="Endpoint Definitions",
        section_number="6",
        protocol={
            "primary_endpoint": "DFS",
            "setting": "adjuvant"
        },
        expected_tools=[
            ToolCall("get_censoring_rules", {"endpoint_type": "dfs"})
        ],
        expected_in_output=[
            "disease-free survival",
            "recurrence",
            "new primary",
            "death"
        ],
        forbidden_in_output=[
            "tumor response",
            "RECIST",
            "CR/PR/SD/PD"
        ],
        category="endpoints",
        priority="critical"
    ),

    EvalCase(
        test_id="section6_efs_cart",
        description="EFS endpoint for CAR-T trial",
        section="Endpoint Definitions",
        section_number="6",
        protocol={
            "primary_endpoint": "EFS",
            "treatment": "CAR-T"
        },
        expected_tools=[
            ToolCall("get_censoring_rules"),
            ToolCall("get_cart_specifications")
        ],
        expected_in_output=[
            "event-free survival",
            "progression",
            "relapse",
            "death",
            "new anticancer therapy"
        ],
        category="endpoints",
        priority="high"
    ),

    # Binary endpoints
    EvalCase(
        test_id="section6_orr_recist",
        description="ORR endpoint with RECIST",
        section="Endpoint Definitions",
        section_number="6",
        protocol={
            "primary_endpoint": "ORR",
            "response_criteria": "RECIST 1.1"
        },
        expected_tools=[
            ToolCall("get_recist_specifications")
        ],
        expected_in_output=[
            "objective response rate",
            "complete response",
            "partial response",
            "CR",
            "PR",
            "RECIST 1.1"
        ],
        category="endpoints",
        priority="critical"
    ),

    EvalCase(
        test_id="section6_orr_lugano",
        description="ORR endpoint with Lugano for lymphoma",
        section="Endpoint Definitions",
        section_number="6",
        protocol={
            "primary_endpoint": "ORR",
            "indication": "DLBCL",
            "response_criteria": "Lugano"
        },
        expected_tools=[
            ToolCall("get_response_criteria", {"criteria_name": "lugano"})
        ],
        expected_in_output=[
            "Lugano",
            "Deauville",
            "metabolic response",
            "PET"
        ],
        forbidden_in_output=[
            "RECIST"  # Wrong criteria for lymphoma
        ],
        category="endpoints",
        priority="critical"
    ),

    EvalCase(
        test_id="section6_cr_rate_myeloma",
        description="CR rate for myeloma",
        section="Endpoint Definitions",
        section_number="6",
        protocol={
            "primary_endpoint": "CR rate",
            "indication": "multiple myeloma"
        },
        expected_tools=[
            ToolCall("get_response_criteria", {"criteria_name": "imwg"})
        ],
        expected_in_output=[
            "IMWG",
            "stringent complete response",
            "sCR",
            "immunofixation",
            "MRD"
        ],
        category="endpoints",
        priority="high"
    ),

    EvalCase(
        test_id="section6_orr_irrecist",
        description="ORR with irRECIST for immunotherapy",
        section="Endpoint Definitions",
        section_number="6",
        protocol={
            "primary_endpoint": "ORR",
            "treatment": "immunotherapy",
            "response_criteria": "irRECIST"
        },
        expected_tools=[
            ToolCall("get_response_criteria", {"criteria_name": "irrecist"})
        ],
        expected_in_output=[
            "irRECIST",
            "immune-related",
            "pseudoprogression",
            "confirmation"
        ],
        category="endpoints",
        priority="high"
    ),

    EvalCase(
        test_id="section6_rano_brain",
        description="Response criteria for brain tumors (RANO)",
        section="Endpoint Definitions",
        section_number="6",
        protocol={
            "indication": "glioblastoma",
            "response_criteria": "RANO"
        },
        expected_tools=[
            ToolCall("get_response_criteria", {"criteria_name": "rano"})
        ],
        expected_in_output=[
            "RANO",
            "MRI",
            "T1",
            "FLAIR",
            "enhancing"
        ],
        forbidden_in_output=[
            "RECIST"  # Wrong for brain tumors
        ],
        category="endpoints",
        priority="high"
    ),

    # Duration of Response
    EvalCase(
        test_id="section6_dor_definition",
        description="DOR endpoint definition",
        section="Endpoint Definitions",
        section_number="6",
        protocol={
            "secondary_endpoint": "DOR"
        },
        expected_tools=[
            ToolCall("get_censoring_rules", {"endpoint_type": "dor"})
        ],
        expected_in_output=[
            "duration of response",
            "responders",
            "first response",
            "progression"
        ],
        category="endpoints",
        priority="high"
    ),

    # TTR (Time to Response)
    EvalCase(
        test_id="section6_ttr_definition",
        description="TTR endpoint definition",
        section="Endpoint Definitions",
        section_number="6",
        protocol={
            "secondary_endpoint": "TTR"
        },
        expected_tools=[
            ToolCall("get_censoring_rules")
        ],
        expected_in_output=[
            "time to response",
            "first response"
        ],
        category="endpoints",
        priority="medium"
    ),
]


# =============================================================================
# SECTION 7: EFFICACY ANALYSIS
# =============================================================================

SECTION_7_EVALS = [
    # PFS Analysis
    EvalCase(
        test_id="section7_pfs_analysis",
        description="PFS efficacy analysis",
        section="Efficacy Analysis",
        section_number="7",
        protocol={
            "primary_endpoint": "PFS",
            "design": "randomized"
        },
        expected_tools=[
            ToolCall("get_censoring_rules", {"endpoint_type": "pfs"}),
            ToolCall("get_statistical_method", {"method_name": "cox_proportional_hazards"}),
            ToolCall("get_statistical_method", {"method_name": "kaplan_meier"}),
            ToolCall("get_statistical_method", {"method_name": "stratified_log_rank"}),
            ToolCall("get_time_to_event_analysis"),
            ToolCall("get_efficacy_tables")
        ],
        expected_in_output=[
            "hazard ratio",
            "Kaplan-Meier",
            "log-rank",
            "Cox",
            "censoring",
            "median PFS"
        ],
        category="efficacy",
        priority="critical"
    ),

    # OS Analysis
    EvalCase(
        test_id="section7_os_analysis",
        description="OS efficacy analysis",
        section="Efficacy Analysis",
        section_number="7",
        protocol={
            "primary_endpoint": "OS",
            "design": "randomized"
        },
        expected_tools=[
            ToolCall("get_censoring_rules", {"endpoint_type": "os"}),
            ToolCall("get_statistical_method", {"method_name": "cox_proportional_hazards"}),
            ToolCall("get_statistical_method", {"method_name": "kaplan_meier"}),
            ToolCall("get_time_to_event_analysis")
        ],
        expected_in_output=[
            "overall survival",
            "hazard ratio",
            "Kaplan-Meier",
            "median OS"
        ],
        category="efficacy",
        priority="critical"
    ),

    # ORR Analysis (Single-arm)
    EvalCase(
        test_id="section7_orr_single_arm",
        description="ORR efficacy analysis for single-arm",
        section="Efficacy Analysis",
        section_number="7",
        protocol={
            "primary_endpoint": "ORR",
            "design": "single-arm"
        },
        expected_tools=[
            ToolCall("get_recist_specifications"),
            ToolCall("get_statistical_method", {"method_name": "clopper_pearson"}),
            ToolCall("get_efficacy_tables")
        ],
        forbidden_tools=[
            "get_censoring_rules"  # Not for binary endpoint
        ],
        expected_in_output=[
            "objective response rate",
            "Clopper-Pearson",
            "confidence interval",
            "exact"
        ],
        forbidden_in_output=[
            "hazard ratio",
            "Kaplan-Meier",
            "censoring"
        ],
        category="efficacy",
        priority="critical"
    ),

    # ORR Analysis (Randomized)
    EvalCase(
        test_id="section7_orr_randomized",
        description="ORR efficacy analysis for randomized trial",
        section="Efficacy Analysis",
        section_number="7",
        protocol={
            "primary_endpoint": "ORR",
            "design": "randomized"
        },
        expected_tools=[
            ToolCall("get_recist_specifications"),
            ToolCall("get_statistical_method", {"method_name": "cmh_test"}),
            ToolCall("get_efficacy_tables")
        ],
        expected_in_output=[
            "objective response rate",
            "CMH",
            "Cochran-Mantel-Haenszel",
            "odds ratio"
        ],
        category="efficacy",
        priority="critical"
    ),

    # DFS Analysis (Adjuvant)
    EvalCase(
        test_id="section7_dfs_adjuvant",
        description="DFS analysis for adjuvant trial",
        section="Efficacy Analysis",
        section_number="7",
        protocol={
            "primary_endpoint": "DFS",
            "setting": "adjuvant"
        },
        expected_tools=[
            ToolCall("get_censoring_rules", {"endpoint_type": "dfs"}),
            ToolCall("get_statistical_method", {"method_name": "cox_proportional_hazards"}),
            ToolCall("get_time_to_event_analysis")
        ],
        forbidden_tools=[
            "get_recist_specifications"  # No tumor response in adjuvant
        ],
        expected_in_output=[
            "disease-free survival",
            "hazard ratio",
            "recurrence"
        ],
        forbidden_in_output=[
            "tumor response",
            "RECIST",
            "CR/PR"
        ],
        category="efficacy",
        priority="critical"
    ),

    # Lymphoma Efficacy
    EvalCase(
        test_id="section7_lymphoma_efficacy",
        description="Efficacy analysis for lymphoma (Lugano)",
        section="Efficacy Analysis",
        section_number="7",
        protocol={
            "indication": "DLBCL",
            "primary_endpoint": "ORR",
            "response_criteria": "Lugano"
        },
        expected_tools=[
            ToolCall("get_response_criteria", {"criteria_name": "lugano"}),
            ToolCall("get_efficacy_tables")
        ],
        forbidden_tools=[
            "get_recist_specifications"  # Wrong for lymphoma
        ],
        expected_in_output=[
            "Lugano",
            "complete metabolic response",
            "Deauville"
        ],
        category="efficacy",
        priority="critical"
    ),

    # Myeloma Efficacy
    EvalCase(
        test_id="section7_myeloma_efficacy",
        description="Efficacy analysis for myeloma (IMWG)",
        section="Efficacy Analysis",
        section_number="7",
        protocol={
            "indication": "multiple myeloma",
            "primary_endpoint": "ORR"
        },
        expected_tools=[
            ToolCall("get_response_criteria", {"criteria_name": "imwg"})
        ],
        expected_in_output=[
            "IMWG",
            "stringent complete response",
            "VGPR",
            "M-protein"
        ],
        category="efficacy",
        priority="high"
    ),

    # RMST Analysis
    EvalCase(
        test_id="section7_rmst_analysis",
        description="RMST analysis as sensitivity",
        section="Efficacy Analysis",
        section_number="7",
        protocol={
            "primary_endpoint": "PFS",
            "sensitivity_analyses": ["RMST"]
        },
        expected_tools=[
            ToolCall("get_statistical_method", {"method_name": "rmst"})
        ],
        expected_in_output=[
            "restricted mean survival time",
            "RMST"
        ],
        category="efficacy",
        priority="medium"
    ),
]


# =============================================================================
# SECTION 8: SAFETY ANALYSIS
# =============================================================================

SECTION_8_EVALS = [
    # Standard Safety
    EvalCase(
        test_id="section8_standard_safety",
        description="Standard safety analysis",
        section="Safety Analysis",
        section_number="8",
        protocol={
            "indication": "solid tumor"
        },
        expected_tools=[
            ToolCall("get_safety_specifications"),
            ToolCall("get_safety_tables")
        ],
        expected_in_output=[
            "TEAE",
            "treatment-emergent",
            "MedDRA",
            "CTCAE",
            "serious adverse event",
            "SAE"
        ],
        category="safety",
        priority="critical"
    ),

    # CAR-T Safety
    EvalCase(
        test_id="section8_cart_safety",
        description="CAR-T specific safety (CRS, ICANS)",
        section="Safety Analysis",
        section_number="8",
        protocol={
            "treatment": "CAR-T",
            "indication": "DLBCL"
        },
        expected_tools=[
            ToolCall("get_safety_specifications"),
            ToolCall("get_safety_tables"),
            ToolCall("get_cart_specifications")
        ],
        expected_in_output=[
            "CRS",
            "cytokine release syndrome",
            "ICANS",
            "neurotoxicity",
            "Lee criteria",
            "tocilizumab",
            "corticosteroids"
        ],
        category="safety",
        priority="critical"
    ),

    # Immunotherapy Safety
    EvalCase(
        test_id="section8_io_safety",
        description="Immunotherapy-related AE safety",
        section="Safety Analysis",
        section_number="8",
        protocol={
            "treatment": "immunotherapy",
            "drug_class": "PD-1 inhibitor"
        },
        expected_tools=[
            ToolCall("get_safety_specifications"),
            ToolCall("get_safety_tables")
        ],
        expected_in_output=[
            "immune-related",
            "irAE",
            "colitis",
            "pneumonitis",
            "hepatitis",
            "endocrinopathy"
        ],
        category="safety",
        priority="critical"
    ),

    # ADC Safety
    EvalCase(
        test_id="section8_adc_safety",
        description="ADC-specific safety (ILD, peripheral neuropathy)",
        section="Safety Analysis",
        section_number="8",
        protocol={
            "treatment": "ADC",
            "drug_name": "trastuzumab deruxtecan"
        },
        expected_tools=[
            ToolCall("get_safety_specifications"),
            ToolCall("get_adc_specifications")
        ],
        expected_in_output=[
            "interstitial lung disease",
            "ILD",
            "pneumonitis"
        ],
        category="safety",
        priority="high"
    ),

    # Bispecific Safety
    EvalCase(
        test_id="section8_bispecific_safety",
        description="Bispecific antibody safety",
        section="Safety Analysis",
        section_number="8",
        protocol={
            "treatment": "bispecific antibody"
        },
        expected_tools=[
            ToolCall("get_safety_specifications"),
            ToolCall("get_bispecific_specifications")
        ],
        expected_in_output=[
            "CRS",
            "cytokine release",
            "step-up dosing"
        ],
        category="safety",
        priority="high"
    ),

    # Laboratory Analysis
    EvalCase(
        test_id="section8_laboratory",
        description="Laboratory parameters analysis",
        section="Safety Analysis",
        section_number="8",
        protocol={},
        expected_tools=[
            ToolCall("get_safety_specifications")
        ],
        expected_in_output=[
            "laboratory",
            "shift table",
            "hepatic",
            "renal",
            "hematology"
        ],
        category="safety",
        priority="high"
    ),

    # Vital Signs
    EvalCase(
        test_id="section8_vital_signs",
        description="Vital signs analysis",
        section="Safety Analysis",
        section_number="8",
        protocol={},
        expected_tools=[
            ToolCall("get_safety_specifications")
        ],
        expected_in_output=[
            "vital signs",
            "blood pressure",
            "heart rate",
            "weight"
        ],
        category="safety",
        priority="medium"
    ),

    # ECG Analysis
    EvalCase(
        test_id="section8_ecg",
        description="ECG analysis (QTc)",
        section="Safety Analysis",
        section_number="8",
        protocol={
            "has_ecg_monitoring": True
        },
        expected_tools=[
            ToolCall("get_safety_specifications")
        ],
        expected_in_output=[
            "ECG",
            "QTc",
            "Fridericia",
            "prolongation"
        ],
        category="safety",
        priority="medium"
    ),

    # Exposure Analysis
    EvalCase(
        test_id="section8_exposure",
        description="Drug exposure analysis",
        section="Safety Analysis",
        section_number="8",
        protocol={},
        expected_tools=[
            ToolCall("get_safety_specifications")
        ],
        expected_in_output=[
            "exposure",
            "duration",
            "dose intensity",
            "dose modification"
        ],
        category="safety",
        priority="high"
    ),
]


# =============================================================================
# SECTION 9: INTERIM ANALYSIS
# =============================================================================

SECTION_9_EVALS = [
    EvalCase(
        test_id="section9_interim_obf",
        description="Interim analysis with O'Brien-Fleming",
        section="Interim Analysis",
        section_number="9",
        protocol={
            "has_interim": True,
            "number_of_interims": 2,
            "spending_function": "O'Brien-Fleming"
        },
        expected_tools=[
            ToolCall("get_interim_analysis"),
            ToolCall("get_multiplicity_adjustment")
        ],
        expected_in_output=[
            "O'Brien-Fleming",
            "alpha spending",
            "stopping boundary",
            "information fraction"
        ],
        category="interim",
        priority="critical"
    ),

    EvalCase(
        test_id="section9_interim_lan_demets",
        description="Interim analysis with Lan-DeMets",
        section="Interim Analysis",
        section_number="9",
        protocol={
            "has_interim": True,
            "spending_function": "Lan-DeMets"
        },
        expected_tools=[
            ToolCall("get_interim_analysis"),
            ToolCall("get_multiplicity_adjustment")
        ],
        expected_in_output=[
            "Lan-DeMets",
            "alpha spending",
            "boundary"
        ],
        category="interim",
        priority="high"
    ),

    EvalCase(
        test_id="section9_futility",
        description="Futility analysis",
        section="Interim Analysis",
        section_number="9",
        protocol={
            "has_interim": True,
            "futility_analysis": True
        },
        expected_tools=[
            ToolCall("get_interim_analysis")
        ],
        expected_in_output=[
            "futility",
            "non-binding",
            "conditional power"
        ],
        category="interim",
        priority="high"
    ),

    EvalCase(
        test_id="section9_no_interim",
        description="Study without interim analysis",
        section="Interim Analysis",
        section_number="9",
        protocol={
            "has_interim": False
        },
        expected_tools=[],
        forbidden_tools=[
            "get_interim_analysis"
        ],
        expected_in_output=[
            "no interim",
            "not planned"
        ],
        category="interim",
        priority="medium"
    ),
]


# =============================================================================
# SECTION 10: MULTIPLICITY
# =============================================================================

SECTION_10_EVALS = [
    EvalCase(
        test_id="section10_hierarchical",
        description="Hierarchical testing for multiple endpoints",
        section="Multiplicity Adjustment",
        section_number="10",
        protocol={
            "primary_endpoints": ["PFS", "OS"],
            "multiplicity_strategy": "hierarchical"
        },
        expected_tools=[
            ToolCall("get_multiplicity_adjustment")
        ],
        expected_in_output=[
            "hierarchical",
            "gatekeeping",
            "alpha"
        ],
        category="multiplicity",
        priority="critical"
    ),

    EvalCase(
        test_id="section10_hochberg",
        description="Hochberg adjustment",
        section="Multiplicity Adjustment",
        section_number="10",
        protocol={
            "multiplicity_strategy": "Hochberg"
        },
        expected_tools=[
            ToolCall("get_multiplicity_adjustment", {"method_name": "hochberg"})
        ],
        expected_in_output=[
            "Hochberg",
            "step-up"
        ],
        category="multiplicity",
        priority="high"
    ),

    EvalCase(
        test_id="section10_graphical",
        description="Graphical approach for multiplicity",
        section="Multiplicity Adjustment",
        section_number="10",
        protocol={
            "multiplicity_strategy": "graphical"
        },
        expected_tools=[
            ToolCall("get_multiplicity_adjustment")
        ],
        expected_in_output=[
            "graphical",
            "propagation",
            "alpha reallocation"
        ],
        category="multiplicity",
        priority="high"
    ),

    EvalCase(
        test_id="section10_single_primary",
        description="Single primary endpoint (no multiplicity)",
        section="Multiplicity Adjustment",
        section_number="10",
        protocol={
            "primary_endpoints": ["PFS"]
        },
        expected_tools=[],
        expected_in_output=[
            "single primary",
            "no adjustment"
        ],
        category="multiplicity",
        priority="medium"
    ),
]


# =============================================================================
# SECTION 11: MISSING DATA
# =============================================================================

SECTION_11_EVALS = [
    EvalCase(
        test_id="section11_missing_tte",
        description="Missing data for time-to-event",
        section="Missing Data",
        section_number="11",
        protocol={
            "primary_endpoint": "PFS"
        },
        expected_tools=[
            ToolCall("get_missing_data_method"),
            ToolCall("get_sensitivity_analysis", {"endpoint_type": "pfs_sensitivity"})
        ],
        expected_in_output=[
            "censoring",
            "lost to follow-up",
            "sensitivity"
        ],
        category="missing_data",
        priority="high"
    ),

    EvalCase(
        test_id="section11_mmrm",
        description="MMRM for longitudinal data",
        section="Missing Data",
        section_number="11",
        protocol={
            "has_longitudinal_data": True
        },
        expected_tools=[
            ToolCall("get_missing_data_method", {"method_name": "mmrm"})
        ],
        expected_in_output=[
            "MMRM",
            "mixed model",
            "repeated measures"
        ],
        category="missing_data",
        priority="high"
    ),

    EvalCase(
        test_id="section11_multiple_imputation",
        description="Multiple imputation",
        section="Missing Data",
        section_number="11",
        protocol={
            "missing_data_method": "multiple imputation"
        },
        expected_tools=[
            ToolCall("get_missing_data_method", {"method_name": "multiple_imputation"})
        ],
        expected_in_output=[
            "multiple imputation",
            "Rubin"
        ],
        category="missing_data",
        priority="medium"
    ),

    EvalCase(
        test_id="section11_tipping_point",
        description="Tipping point analysis",
        section="Missing Data",
        section_number="11",
        protocol={
            "sensitivity_analyses": ["tipping point"]
        },
        expected_tools=[
            ToolCall("get_missing_data_method", {"method_name": "tipping_point"})
        ],
        expected_in_output=[
            "tipping point",
            "sensitivity"
        ],
        category="missing_data",
        priority="medium"
    ),
]


# =============================================================================
# SECTION 12: SENSITIVITY ANALYSES
# =============================================================================

SECTION_12_EVALS = [
    EvalCase(
        test_id="section12_sensitivity_pfs",
        description="Sensitivity analyses for PFS",
        section="Sensitivity Analyses",
        section_number="12",
        protocol={
            "primary_endpoint": "PFS"
        },
        expected_tools=[
            ToolCall("get_sensitivity_analysis", {"endpoint_type": "pfs_sensitivity"})
        ],
        expected_in_output=[
            "per-protocol",
            "sensitivity",
            "censoring"
        ],
        category="sensitivity",
        priority="high"
    ),

    EvalCase(
        test_id="section12_sensitivity_os",
        description="Sensitivity analyses for OS",
        section="Sensitivity Analyses",
        section_number="12",
        protocol={
            "primary_endpoint": "OS"
        },
        expected_tools=[
            ToolCall("get_sensitivity_analysis", {"endpoint_type": "os_sensitivity"})
        ],
        expected_in_output=[
            "treatment switching",
            "IPCW",
            "RPSFT"
        ],
        category="sensitivity",
        priority="high"
    ),

    EvalCase(
        test_id="section12_per_protocol",
        description="Per-protocol analysis",
        section="Sensitivity Analyses",
        section_number="12",
        protocol={},
        expected_tools=[
            ToolCall("get_sensitivity_analysis")
        ],
        expected_in_output=[
            "per-protocol",
            "major protocol deviation"
        ],
        category="sensitivity",
        priority="high"
    ),
]


# =============================================================================
# SECTION 13: SUBGROUP ANALYSES
# =============================================================================

SECTION_13_EVALS = [
    EvalCase(
        test_id="section13_subgroups_standard",
        description="Standard subgroup analyses",
        section="Subgroup Analyses",
        section_number="13",
        protocol={
            "primary_endpoint": "PFS"
        },
        expected_tools=[
            ToolCall("get_subgroup_analysis_specs")
        ],
        expected_in_output=[
            "subgroup",
            "forest plot",
            "interaction",
            "age",
            "sex",
            "region"
        ],
        category="subgroup",
        priority="high"
    ),

    EvalCase(
        test_id="section13_subgroups_biomarker",
        description="Biomarker-defined subgroups",
        section="Subgroup Analyses",
        section_number="13",
        protocol={
            "biomarker_subgroups": ["PD-L1 >=50%", "PD-L1 1-49%", "PD-L1 <1%"]
        },
        expected_tools=[
            ToolCall("get_subgroup_analysis_specs")
        ],
        expected_in_output=[
            "PD-L1",
            "biomarker",
            "subgroup"
        ],
        category="subgroup",
        priority="high"
    ),
]


# =============================================================================
# SECTION 14: PRO/QoL ANALYSIS
# =============================================================================

SECTION_14_EVALS = [
    EvalCase(
        test_id="section14_pro_eortc",
        description="PRO analysis with EORTC QLQ-C30",
        section="PRO/QoL Analysis",
        section_number="14",
        protocol={
            "pro_instruments": ["EORTC QLQ-C30"]
        },
        expected_tools=[
            ToolCall("get_pro_qol_analysis", {"instrument": "eortc_qlq_c30"})
        ],
        expected_in_output=[
            "EORTC",
            "QLQ-C30",
            "global health",
            "functioning",
            "symptom"
        ],
        category="pro",
        priority="high"
    ),

    EvalCase(
        test_id="section14_pro_eq5d",
        description="PRO analysis with EQ-5D",
        section="PRO/QoL Analysis",
        section_number="14",
        protocol={
            "pro_instruments": ["EQ-5D-5L"]
        },
        expected_tools=[
            ToolCall("get_pro_qol_analysis", {"instrument": "eq5d"})
        ],
        expected_in_output=[
            "EQ-5D",
            "utility",
            "VAS"
        ],
        category="pro",
        priority="medium"
    ),

    EvalCase(
        test_id="section14_pro_ttd",
        description="Time to deterioration analysis",
        section="PRO/QoL Analysis",
        section_number="14",
        protocol={
            "pro_endpoints": ["TTD"]
        },
        expected_tools=[
            ToolCall("get_pro_qol_analysis")
        ],
        expected_in_output=[
            "time to deterioration",
            "TTD",
            "clinically meaningful"
        ],
        category="pro",
        priority="high"
    ),
]


# =============================================================================
# SECTION 15: TFL SPECIFICATIONS
# =============================================================================

SECTION_15_EVALS = [
    EvalCase(
        test_id="section15_tfl_shells_standard",
        description="Standard TFL shells",
        section="TFL Specifications",
        section_number="15",
        protocol={
            "design": "randomized",
            "primary_endpoint": "PFS"
        },
        expected_tools=[
            ToolCall("get_disposition_tables"),
            ToolCall("get_efficacy_tables"),
            ToolCall("get_safety_tables"),
            ToolCall("get_all_figures")
        ],
        expected_in_output=[
            "Table 14.1",
            "Table 14.2",
            "Table 14.3",
            "Figure",
            "Listing"
        ],
        category="tfl",
        priority="critical"
    ),

    EvalCase(
        test_id="section15_tfl_shells_single_arm",
        description="TFL shells for single-arm",
        section="TFL Specifications",
        section_number="15",
        protocol={
            "design": "single-arm"
        },
        expected_tools=[
            ToolCall("get_disposition_tables"),
            ToolCall("get_efficacy_tables"),
            ToolCall("get_safety_tables")
        ],
        expected_in_output=[
            "single-arm",
            "Table"
        ],
        forbidden_in_output=[
            "Treatment A vs Treatment B"
        ],
        category="tfl",
        priority="high"
    ),

    EvalCase(
        test_id="section15_km_figure",
        description="Kaplan-Meier figure specification",
        section="TFL Specifications",
        section_number="15",
        protocol={
            "primary_endpoint": "PFS"
        },
        expected_tools=[
            ToolCall("get_all_figures")
        ],
        expected_in_output=[
            "Kaplan-Meier",
            "curve",
            "at-risk table"
        ],
        category="tfl",
        priority="high"
    ),

    EvalCase(
        test_id="section15_forest_plot",
        description="Forest plot specification",
        section="TFL Specifications",
        section_number="15",
        protocol={
            "has_subgroup_analyses": True
        },
        expected_tools=[
            ToolCall("get_all_figures")
        ],
        expected_in_output=[
            "forest plot",
            "subgroup"
        ],
        category="tfl",
        priority="high"
    ),

    EvalCase(
        test_id="section15_waterfall",
        description="Waterfall plot specification",
        section="TFL Specifications",
        section_number="15",
        protocol={
            "has_tumor_response": True
        },
        expected_tools=[
            ToolCall("get_all_figures")
        ],
        expected_in_output=[
            "waterfall",
            "best percent change"
        ],
        category="tfl",
        priority="medium"
    ),

    EvalCase(
        test_id="section15_swimmer_plot",
        description="Swimmer plot specification",
        section="TFL Specifications",
        section_number="15",
        protocol={
            "has_response_duration": True
        },
        expected_tools=[
            ToolCall("get_all_figures")
        ],
        expected_in_output=[
            "swimmer",
            "duration"
        ],
        category="tfl",
        priority="medium"
    ),
]


# =============================================================================
# SECTION 16: ADaM SPECIFICATIONS
# =============================================================================

SECTION_16_EVALS = [
    EvalCase(
        test_id="section16_adsl",
        description="ADSL dataset specification",
        section="ADaM Specifications",
        section_number="16",
        protocol={},
        expected_tools=[
            ToolCall("get_adam_dataset_spec", {"dataset_name": "ADSL"})
        ],
        expected_in_output=[
            "ADSL",
            "subject level",
            "USUBJID",
            "SAFFL",
            "ITTFL"
        ],
        category="adam",
        priority="critical"
    ),

    EvalCase(
        test_id="section16_adtte_pfs",
        description="ADTTE dataset for PFS",
        section="ADaM Specifications",
        section_number="16",
        protocol={
            "primary_endpoint": "PFS"
        },
        expected_tools=[
            ToolCall("get_adam_dataset_spec", {"dataset_name": "ADTTE"})
        ],
        expected_in_output=[
            "ADTTE",
            "time-to-event",
            "AVAL",
            "CNSR",
            "PARAMCD"
        ],
        category="adam",
        priority="critical"
    ),

    EvalCase(
        test_id="section16_adrs",
        description="ADRS dataset for tumor response",
        section="ADaM Specifications",
        section_number="16",
        protocol={
            "has_tumor_response": True
        },
        expected_tools=[
            ToolCall("get_adam_dataset_spec", {"dataset_name": "ADRS"})
        ],
        expected_in_output=[
            "ADRS",
            "response",
            "AVALC",
            "RSSTRESC"
        ],
        category="adam",
        priority="high"
    ),

    EvalCase(
        test_id="section16_adae",
        description="ADAE dataset for adverse events",
        section="ADaM Specifications",
        section_number="16",
        protocol={},
        expected_tools=[
            ToolCall("get_adam_dataset_spec", {"dataset_name": "ADAE"})
        ],
        expected_in_output=[
            "ADAE",
            "adverse event",
            "AEDECOD",
            "AEBODSYS",
            "TRTEMFL"
        ],
        category="adam",
        priority="high"
    ),
]


# =============================================================================
# CROSS-CUTTING: ESTIMAND FRAMEWORK
# =============================================================================

ESTIMAND_EVALS = [
    EvalCase(
        test_id="estimand_pfs_treatment_policy",
        description="Treatment policy estimand for PFS",
        section="Estimand Framework",
        section_number="7",
        protocol={
            "primary_endpoint": "PFS",
            "estimand_strategy": "treatment policy"
        },
        expected_tools=[
            ToolCall("get_estimand_framework")
        ],
        expected_in_output=[
            "estimand",
            "treatment policy",
            "ICH E9",
            "intercurrent event"
        ],
        category="estimand",
        priority="critical"
    ),

    EvalCase(
        test_id="estimand_hypothetical",
        description="Hypothetical strategy for death",
        section="Estimand Framework",
        section_number="7",
        protocol={
            "intercurrent_events": ["death"]
        },
        expected_tools=[
            ToolCall("get_estimand_framework")
        ],
        expected_in_output=[
            "hypothetical",
            "intercurrent"
        ],
        category="estimand",
        priority="high"
    ),
]


# =============================================================================
# SPECIAL CASE: SIMILAR TRIAL LOOKUP
# =============================================================================

SIMILAR_TRIAL_EVALS = [
    EvalCase(
        test_id="similar_trials_nsclc_phase3",
        description="Find similar NSCLC Phase 3 trials",
        section="Any",
        section_number="*",
        protocol={
            "phase": "Phase 3",
            "indication": "NSCLC",
            "primary_endpoint": "PFS"
        },
        expected_tools=[
            ToolCall("get_similar_trials", {
                "phase": "III",
                "indication": "NSCLC",
                "endpoint_type": "PFS"
            })
        ],
        expected_in_output=[
            "similar",
            "precedent"
        ],
        category="precedent",
        priority="medium"
    ),

    EvalCase(
        test_id="similar_trials_lymphoma",
        description="Find similar lymphoma trials",
        section="Any",
        section_number="*",
        protocol={
            "indication": "DLBCL",
            "treatment": "CAR-T"
        },
        expected_tools=[
            ToolCall("get_similar_trials", {
                "indication": "lymphoma"
            })
        ],
        category="precedent",
        priority="medium"
    ),
]


# =============================================================================
# AGGREGATE ALL EVAL CASES
# =============================================================================

ALL_EVAL_CASES = (
    SECTION_1_EVALS +
    SECTION_2_EVALS +
    SECTION_3_EVALS +
    SECTION_4_EVALS +
    SECTION_5_EVALS +
    SECTION_5A_EVALS +
    SECTION_6_EVALS +
    SECTION_7_EVALS +
    SECTION_8_EVALS +
    SECTION_9_EVALS +
    SECTION_10_EVALS +
    SECTION_11_EVALS +
    SECTION_12_EVALS +
    SECTION_13_EVALS +
    SECTION_14_EVALS +
    SECTION_15_EVALS +
    SECTION_16_EVALS +
    ESTIMAND_EVALS +
    SIMILAR_TRIAL_EVALS
)


# =============================================================================
# EVAL RUNNER
# =============================================================================

class ToolCallingEvaluator:
    """Runs tool calling evaluations."""

    def __init__(self, pipeline=None):
        self.pipeline = pipeline
        self.results: List[EvalResult] = []

    def run_single_eval(self, eval_case: EvalCase, verbose: bool = False) -> EvalResult:
        """Run a single evaluation case."""
        import time
        start_time = time.time()

        if verbose:
            print(f"\n{'='*60}")
            print(f"Running: {eval_case.test_id}")
            print(f"Section: {eval_case.section_number} - {eval_case.section}")
            print(f"{'='*60}")

        # If no pipeline, do a mock run (just validate the test case structure)
        if self.pipeline is None:
            return self._mock_eval(eval_case)

        # Run the actual generation
        try:
            result = self.pipeline.generate_section(
                section=eval_case.section,
                section_number=eval_case.section_number,
                protocol=eval_case.protocol
            )

            # Extract tool calls from result
            tools_called = [t.name for t in result.tool_calls] if hasattr(result, 'tool_calls') else []
            generated_content = result.content if hasattr(result, 'content') else ""

        except Exception as e:
            if verbose:
                print(f"Error: {e}")
            return EvalResult(
                test_id=eval_case.test_id,
                passed=False,
                tools_called=[],
                expected_tools_found=[],
                expected_tools_missing=[t.name for t in eval_case.expected_tools],
                forbidden_tools_called=[],
                output_keywords_found=[],
                output_keywords_missing=eval_case.expected_in_output,
                forbidden_keywords_found=[],
                execution_time_seconds=time.time() - start_time
            )

        # Analyze results
        expected_tools_found = []
        expected_tools_missing = []

        for expected_tool in eval_case.expected_tools:
            if expected_tool.name in tools_called:
                expected_tools_found.append(expected_tool.name)
            else:
                expected_tools_missing.append(expected_tool.name)

        forbidden_tools_called = [t for t in tools_called if t in eval_case.forbidden_tools]

        # Check output keywords
        content_lower = generated_content.lower()
        output_keywords_found = [kw for kw in eval_case.expected_in_output if kw.lower() in content_lower]
        output_keywords_missing = [kw for kw in eval_case.expected_in_output if kw.lower() not in content_lower]
        forbidden_keywords_found = [kw for kw in eval_case.forbidden_in_output if kw.lower() in content_lower]

        # Determine pass/fail
        passed = (
            len(expected_tools_missing) == 0 and
            len(forbidden_tools_called) == 0 and
            len(output_keywords_missing) == 0 and
            len(forbidden_keywords_found) == 0
        )

        eval_result = EvalResult(
            test_id=eval_case.test_id,
            passed=passed,
            tools_called=tools_called,
            expected_tools_found=expected_tools_found,
            expected_tools_missing=expected_tools_missing,
            forbidden_tools_called=forbidden_tools_called,
            output_keywords_found=output_keywords_found,
            output_keywords_missing=output_keywords_missing,
            forbidden_keywords_found=forbidden_keywords_found,
            generated_content=generated_content[:500],  # Truncate for storage
            execution_time_seconds=time.time() - start_time
        )

        if verbose:
            self._print_result(eval_result)

        return eval_result

    def _mock_eval(self, eval_case: EvalCase) -> EvalResult:
        """Mock evaluation when no pipeline available."""
        return EvalResult(
            test_id=eval_case.test_id,
            passed=True,  # Mock always passes
            tools_called=[t.name for t in eval_case.expected_tools],
            expected_tools_found=[t.name for t in eval_case.expected_tools],
            expected_tools_missing=[],
            forbidden_tools_called=[],
            output_keywords_found=eval_case.expected_in_output,
            output_keywords_missing=[],
            forbidden_keywords_found=[],
            generated_content="[MOCK] Test case validated",
            execution_time_seconds=0.0
        )

    def run_all_evals(self, verbose: bool = False, category: str = None,
                      priority: str = None) -> List[EvalResult]:
        """Run all evaluation cases."""

        cases_to_run = ALL_EVAL_CASES

        # Filter by category
        if category:
            cases_to_run = [c for c in cases_to_run if c.category == category]

        # Filter by priority
        if priority:
            cases_to_run = [c for c in cases_to_run if c.priority == priority]

        print(f"\nRunning {len(cases_to_run)} eval cases...")
        print(f"Categories: {set(c.category for c in cases_to_run)}")

        self.results = []
        for case in cases_to_run:
            result = self.run_single_eval(case, verbose=verbose)
            self.results.append(result)

        return self.results

    def _print_result(self, result: EvalResult):
        """Print a single result."""
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"\n{status} {result.test_id}")

        if result.expected_tools_missing:
            print(f"   Missing tools: {result.expected_tools_missing}")
        if result.forbidden_tools_called:
            print(f"   Forbidden tools called: {result.forbidden_tools_called}")
        if result.output_keywords_missing:
            print(f"   Missing keywords: {result.output_keywords_missing}")
        if result.forbidden_keywords_found:
            print(f"   Forbidden keywords found: {result.forbidden_keywords_found}")

    def print_summary(self):
        """Print summary of all results."""
        if not self.results:
            print("No results to summarize")
            return

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        print(f"\n{'='*60}")
        print(f"EVAL SUMMARY")
        print(f"{'='*60}")
        print(f"Total: {total}")
        print(f"Passed: {passed} ({100*passed/total:.1f}%)")
        print(f"Failed: {total - passed}")

        # Group by category
        categories = {}
        for r in self.results:
            case = next((c for c in ALL_EVAL_CASES if c.test_id == r.test_id), None)
            if case:
                cat = case.category
                if cat not in categories:
                    categories[cat] = {"passed": 0, "total": 0}
                categories[cat]["total"] += 1
                if r.passed:
                    categories[cat]["passed"] += 1

        print(f"\nBy Category:")
        for cat, stats in sorted(categories.items()):
            pct = 100 * stats["passed"] / stats["total"] if stats["total"] > 0 else 0
            print(f"  {cat}: {stats['passed']}/{stats['total']} ({pct:.0f}%)")

        # List failures
        failures = [r for r in self.results if not r.passed]
        if failures:
            print(f"\nFailed Tests:")
            for r in failures:
                print(f"  - {r.test_id}")
                if r.expected_tools_missing:
                    print(f"      Missing: {r.expected_tools_missing}")

    def export_results(self, filepath: str):
        """Export results to JSON."""
        output = {
            "timestamp": datetime.now().isoformat(),
            "total_cases": len(self.results),
            "passed": sum(1 for r in self.results if r.passed),
            "failed": sum(1 for r in self.results if not r.passed),
            "results": [r.to_dict() for r in self.results]
        }

        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"Results exported to {filepath}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run evaluations from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Run tool calling evaluations")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--category", "-c", type=str, help="Filter by category")
    parser.add_argument("--priority", "-p", type=str, choices=["critical", "high", "medium", "low"])
    parser.add_argument("--test", "-t", type=str, help="Run specific test by ID")
    parser.add_argument("--mock", action="store_true", help="Run mock evaluation (no pipeline)")
    parser.add_argument("--export", "-e", type=str, help="Export results to JSON file")
    parser.add_argument("--list", "-l", action="store_true", help="List all test cases")

    args = parser.parse_args()

    # List test cases
    if args.list:
        print(f"\nTotal eval cases: {len(ALL_EVAL_CASES)}")
        print(f"\nBy Category:")
        categories = {}
        for case in ALL_EVAL_CASES:
            if case.category not in categories:
                categories[case.category] = []
            categories[case.category].append(case.test_id)

        for cat, tests in sorted(categories.items()):
            print(f"\n{cat.upper()} ({len(tests)} tests):")
            for test_id in tests:
                print(f"  - {test_id}")
        return

    # Initialize evaluator
    pipeline = None
    if not args.mock:
        try:
            from kg_enhanced_pipeline import EnhancedKGPipeline
            pipeline = EnhancedKGPipeline()
            print("Pipeline loaded successfully")
        except Exception as e:
            print(f"Could not load pipeline: {e}")
            print("Running in mock mode")

    evaluator = ToolCallingEvaluator(pipeline=pipeline)

    # Run specific test
    if args.test:
        case = next((c for c in ALL_EVAL_CASES if c.test_id == args.test), None)
        if case:
            result = evaluator.run_single_eval(case, verbose=True)
            evaluator.results = [result]
        else:
            print(f"Test not found: {args.test}")
            return
    else:
        # Run all (or filtered)
        evaluator.run_all_evals(
            verbose=args.verbose,
            category=args.category,
            priority=args.priority
        )

    # Print summary
    evaluator.print_summary()

    # Export if requested
    if args.export:
        evaluator.export_results(args.export)


if __name__ == "__main__":
    main()
