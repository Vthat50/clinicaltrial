#!/usr/bin/env python3
"""
Golden Set Evaluation Framework
===============================

Tests SAP generation against curated protocol → expected output pairs.
This is the ground truth for measuring factual accuracy.

Unlike tool-calling evals (which test behavior), golden set evals test correctness:
- Does the output contain the RIGHT content?
- Does it NOT contain WRONG content (hallucinations, wrong disease)?
- Is it complete?

Usage:
    python golden_set_eval.py --list                    # List all cases
    python golden_set_eval.py --run all                 # Run all cases
    python golden_set_eval.py --run lung_phase3_pfs    # Run specific case
    python golden_set_eval.py --run all --export results.json
    python golden_set_eval.py --category oncology       # Filter by category

Author: SAP Generation System
"""

import json
import os
import sys
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field, asdict
from enum import Enum

# =============================================================================
# DATA STRUCTURES
# =============================================================================

class Severity(Enum):
    """Severity of a check failure."""
    CRITICAL = "critical"  # Fails the test
    HIGH = "high"          # Major issue
    MEDIUM = "medium"      # Should fix
    LOW = "low"            # Nice to have


@dataclass
class ContentCheck:
    """A single content check (required or forbidden)."""
    pattern: str                    # Regex or literal string to search
    description: str                # Human-readable description
    severity: Severity = Severity.HIGH
    is_regex: bool = False          # If True, treat pattern as regex
    case_sensitive: bool = False

    def matches(self, text: str) -> bool:
        """Check if pattern matches in text."""
        if self.is_regex:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            return bool(re.search(self.pattern, text, flags))
        else:
            if self.case_sensitive:
                return self.pattern in text
            return self.pattern.lower() in text.lower()


@dataclass
class SectionExpectation:
    """Expected content for a specific SAP section."""
    section_id: str                                  # e.g., "7" for Efficacy
    section_name: str                                # e.g., "Efficacy Analysis"
    required_content: List[ContentCheck] = field(default_factory=list)
    forbidden_content: List[ContentCheck] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    min_length: int = 100                            # Minimum expected length


@dataclass
class GoldenSetCase:
    """A complete golden set test case."""
    case_id: str
    description: str
    category: str                                    # e.g., "oncology", "hematology"

    # Protocol input
    protocol: Dict[str, Any]

    # Expected outputs by section
    section_expectations: List[SectionExpectation]

    # Global checks (apply to entire SAP)
    global_required: List[ContentCheck] = field(default_factory=list)
    global_forbidden: List[ContentCheck] = field(default_factory=list)

    # Metadata
    difficulty: str = "standard"                     # "simple", "standard", "complex"
    tags: List[str] = field(default_factory=list)


@dataclass
class CheckResult:
    """Result of a single check."""
    check_type: str         # "required" or "forbidden"
    pattern: str
    description: str
    passed: bool
    severity: Severity
    section: str = "global"


@dataclass
class SectionResult:
    """Result for a single section."""
    section_id: str
    section_name: str
    passed: bool
    score: float            # 0-100
    checks_passed: int
    checks_failed: int
    required_found: List[str]
    required_missing: List[str]
    forbidden_found: List[str]
    tools_called: List[str]
    tools_expected: List[str]
    tools_missing: List[str]
    content_length: int
    details: List[CheckResult]


@dataclass
class GoldenSetResult:
    """Complete result for a golden set case."""
    case_id: str
    description: str
    passed: bool
    overall_score: float    # 0-100

    # Timing
    execution_time_seconds: float

    # Section results
    section_results: List[SectionResult]

    # Global checks
    global_checks: List[CheckResult]

    # Summary stats
    total_required_checks: int
    required_checks_passed: int
    total_forbidden_checks: int
    forbidden_checks_passed: int  # Passed = pattern NOT found

    # Critical failures
    critical_failures: List[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export."""
        d = asdict(self)
        # Convert enums
        for section in d.get('section_results', []):
            for detail in section.get('details', []):
                if isinstance(detail.get('severity'), Severity):
                    detail['severity'] = detail['severity'].value
        for check in d.get('global_checks', []):
            if isinstance(check.get('severity'), Severity):
                check['severity'] = check['severity'].value
        return d


# =============================================================================
# GOLDEN SET TEST CASES
# =============================================================================

GOLDEN_SET_CASES: List[GoldenSetCase] = [

    # =========================================================================
    # CASE 1: Lung Cancer Phase 3 PFS Trial (Classic solid tumor)
    # =========================================================================
    GoldenSetCase(
        case_id="lung_phase3_pfs",
        description="Phase 3 randomized NSCLC trial with PFS primary endpoint",
        category="oncology",
        difficulty="standard",
        tags=["solid_tumor", "phase3", "randomized", "time_to_event", "pfs"],
        protocol={
            "study_id": "LUNG-001",
            "phase": "Phase 3",
            "indication": "NSCLC",
            "indication_detail": "Advanced non-small cell lung cancer",
            "line_of_therapy": "first-line",
            "design": "randomized",
            "randomization_ratio": "1:1",
            "blinding": "double-blind",
            "control": "standard of care",
            "primary_endpoint": "PFS",
            "secondary_endpoints": ["OS", "ORR", "DOR", "TTR"],
            "response_criteria": "RECIST 1.1",
            "stratification_factors": ["ECOG PS (0 vs 1)", "PD-L1 status", "Region"],
            "biomarkers": ["EGFR", "ALK", "PD-L1", "KRAS"],
            "sample_size": 500,
            "events_required": 350,
            "has_interim": True,
            "interim_analyses": 2,
        },
        section_expectations=[
            SectionExpectation(
                section_id="5",
                section_name="Analysis Populations",
                required_content=[
                    ContentCheck("intent-to-treat", "ITT population defined", Severity.CRITICAL),
                    ContentCheck("ITT", "ITT abbreviation used", Severity.HIGH),
                    ContentCheck("safety population", "Safety population defined", Severity.CRITICAL),
                    ContentCheck("per-protocol", "Per-protocol population defined", Severity.HIGH),
                ],
                forbidden_content=[
                    ContentCheck("leukapheresis", "CAR-T term in solid tumor", Severity.CRITICAL),
                    ContentCheck("mITT", "CAR-T modified ITT in non-CAR-T", Severity.HIGH),
                ],
                required_tools=["get_population_definitions"],
            ),
            SectionExpectation(
                section_id="5A",
                section_name="Baseline Characteristics",
                required_content=[
                    ContentCheck("EGFR", "EGFR mutation status", Severity.CRITICAL),
                    ContentCheck("ALK", "ALK status", Severity.CRITICAL),
                    ContentCheck("PD-L1", "PD-L1 expression", Severity.CRITICAL),
                    ContentCheck("smoking", "Smoking history", Severity.HIGH),
                    ContentCheck("histology", "Histology type", Severity.HIGH),
                    ContentCheck("ECOG", "Performance status", Severity.HIGH),
                ],
                forbidden_content=[
                    ContentCheck("Ann Arbor", "Lymphoma staging in lung cancer", Severity.CRITICAL),
                    ContentCheck("IPI", "Lymphoma prognostic index", Severity.CRITICAL),
                    ContentCheck("Gleason", "Prostate scoring in lung", Severity.CRITICAL),
                    ContentCheck("ER/PR", "Breast cancer markers in lung", Severity.CRITICAL),
                    ContentCheck("HER2", "Breast cancer marker in lung", Severity.HIGH),
                ],
                required_tools=["get_baseline_covariates", "get_demographics_baseline_specs"],
            ),
            SectionExpectation(
                section_id="6",
                section_name="Endpoint Definitions",
                required_content=[
                    ContentCheck("progression-free survival", "PFS defined", Severity.CRITICAL),
                    ContentCheck("RECIST", "Response criteria specified", Severity.CRITICAL),
                    ContentCheck("censoring", "Censoring rules defined", Severity.CRITICAL),
                    ContentCheck("progression", "Progression event defined", Severity.HIGH),
                    ContentCheck("death", "Death as event", Severity.HIGH),
                ],
                forbidden_content=[
                    ContentCheck("Lugano", "Lymphoma criteria in solid tumor", Severity.CRITICAL),
                    ContentCheck("IMWG", "Myeloma criteria in lung", Severity.CRITICAL),
                    ContentCheck("Deauville", "Lymphoma PET criteria", Severity.CRITICAL),
                ],
                required_tools=["get_censoring_rules", "get_recist_specifications"],
            ),
            SectionExpectation(
                section_id="7",
                section_name="Efficacy Analysis",
                required_content=[
                    ContentCheck("Kaplan-Meier", "KM method", Severity.CRITICAL),
                    ContentCheck("log-rank", "Log-rank test", Severity.CRITICAL),
                    ContentCheck("Cox", "Cox regression", Severity.CRITICAL),
                    ContentCheck("hazard ratio", "HR reported", Severity.CRITICAL),
                    ContentCheck("stratified", "Stratified analysis", Severity.HIGH),
                    ContentCheck("confidence interval", "CI reported", Severity.HIGH),
                ],
                forbidden_content=[
                    ContentCheck("Clopper-Pearson", "Binary CI for TTE endpoint", Severity.MEDIUM),
                ],
                required_tools=[
                    "get_statistical_method",
                    "get_time_to_event_analysis",
                    "get_efficacy_tables"
                ],
            ),
            SectionExpectation(
                section_id="8",
                section_name="Safety Analysis",
                required_content=[
                    ContentCheck("TEAE", "Treatment-emergent AE", Severity.CRITICAL),
                    ContentCheck("MedDRA", "MedDRA coding", Severity.HIGH),
                    ContentCheck("CTCAE", "CTCAE grading", Severity.HIGH),
                    ContentCheck("SAE", "Serious AE", Severity.HIGH),
                ],
                forbidden_content=[
                    ContentCheck("CRS", "CAR-T CRS in chemo trial", Severity.CRITICAL),
                    ContentCheck("cytokine release syndrome", "CAR-T term", Severity.CRITICAL),
                    ContentCheck("ICANS", "CAR-T neurotoxicity", Severity.CRITICAL),
                ],
                required_tools=["get_safety_specifications", "get_safety_tables"],
            ),
            SectionExpectation(
                section_id="9",
                section_name="Interim Analysis",
                required_content=[
                    ContentCheck("interim", "Interim analysis mentioned", Severity.CRITICAL),
                    ContentCheck("alpha spending", "Alpha spending function", Severity.HIGH),
                    ContentCheck("O'Brien-Fleming", "Spending function type", Severity.MEDIUM),
                    ContentCheck("stopping", "Stopping boundary", Severity.HIGH),
                ],
                required_tools=["get_interim_analysis", "get_multiplicity_adjustment"],
            ),
        ],
        global_required=[
            ContentCheck("Statistical Analysis Plan", "SAP title", Severity.HIGH),
            ContentCheck("Phase 3", "Correct phase", Severity.HIGH),
            ContentCheck("NSCLC", "Correct indication", Severity.HIGH),
        ],
        global_forbidden=[
            ContentCheck("Phase 1", "Wrong phase", Severity.CRITICAL),
            ContentCheck("Phase 2", "Wrong phase", Severity.HIGH),
            ContentCheck("lymphoma", "Wrong disease", Severity.CRITICAL),
            ContentCheck("myeloma", "Wrong disease", Severity.CRITICAL),
            ContentCheck("leukemia", "Wrong disease", Severity.CRITICAL),
        ],
    ),

    # =========================================================================
    # CASE 2: DLBCL CAR-T Trial (Hematology with special safety)
    # =========================================================================
    GoldenSetCase(
        case_id="dlbcl_cart_orr",
        description="CAR-T therapy trial in relapsed/refractory DLBCL",
        category="hematology",
        difficulty="complex",
        tags=["hematology", "cart", "single_arm", "binary_endpoint", "special_safety"],
        protocol={
            "study_id": "CART-001",
            "phase": "Phase 2",
            "indication": "DLBCL",
            "indication_detail": "Relapsed/refractory diffuse large B-cell lymphoma",
            "line_of_therapy": "third-line or later",
            "design": "single-arm",
            "treatment": "CAR-T",
            "treatment_name": "CD19-directed CAR-T",
            "primary_endpoint": "ORR",
            "secondary_endpoints": ["CR rate", "DOR", "PFS", "OS"],
            "response_criteria": "Lugano 2014",
            "sample_size": 100,
            "has_interim": False,
        },
        section_expectations=[
            SectionExpectation(
                section_id="5",
                section_name="Analysis Populations",
                required_content=[
                    ContentCheck("leukapheresis", "Leukapheresis population", Severity.CRITICAL),
                    ContentCheck("infused", "Infused population", Severity.CRITICAL),
                    ContentCheck("mITT", "Modified ITT for CAR-T", Severity.HIGH),
                    ContentCheck("modified intent-to-treat", "mITT defined", Severity.HIGH),
                ],
                forbidden_content=[],
                required_tools=["get_population_definitions", "get_cart_specifications"],
            ),
            SectionExpectation(
                section_id="5A",
                section_name="Baseline Characteristics",
                required_content=[
                    ContentCheck("Ann Arbor", "Lymphoma staging", Severity.CRITICAL),
                    ContentCheck("IPI", "IPI score", Severity.HIGH),
                    ContentCheck("LDH", "LDH level", Severity.HIGH),
                    ContentCheck("extranodal", "Extranodal involvement", Severity.MEDIUM),
                    ContentCheck("bulky", "Bulky disease", Severity.MEDIUM),
                    ContentCheck("prior lines", "Prior therapy lines", Severity.HIGH),
                ],
                forbidden_content=[
                    ContentCheck("EGFR", "Lung cancer marker in lymphoma", Severity.CRITICAL),
                    ContentCheck("ALK", "Lung cancer marker in lymphoma", Severity.CRITICAL),
                    ContentCheck("RECIST", "Solid tumor criteria in lymphoma", Severity.CRITICAL),
                    ContentCheck("Gleason", "Prostate marker in lymphoma", Severity.CRITICAL),
                ],
                required_tools=["get_baseline_covariates"],
            ),
            SectionExpectation(
                section_id="6",
                section_name="Endpoint Definitions",
                required_content=[
                    ContentCheck("Lugano", "Lugano criteria", Severity.CRITICAL),
                    ContentCheck("Deauville", "Deauville score", Severity.HIGH),
                    ContentCheck("metabolic", "Metabolic response", Severity.HIGH),
                    ContentCheck("PET", "PET assessment", Severity.HIGH),
                    ContentCheck("complete response", "CR definition", Severity.HIGH),
                    ContentCheck("partial response", "PR definition", Severity.HIGH),
                ],
                forbidden_content=[
                    ContentCheck("RECIST", "Solid tumor criteria", Severity.CRITICAL),
                    ContentCheck("IMWG", "Myeloma criteria", Severity.CRITICAL),
                ],
                required_tools=["get_response_criteria"],
            ),
            SectionExpectation(
                section_id="7",
                section_name="Efficacy Analysis",
                required_content=[
                    ContentCheck("objective response rate", "ORR defined", Severity.CRITICAL),
                    ContentCheck("Clopper-Pearson", "Exact CI method", Severity.HIGH),
                    ContentCheck("confidence interval", "CI reported", Severity.HIGH),
                    ContentCheck("exact", "Exact method", Severity.MEDIUM),
                ],
                forbidden_content=[
                    ContentCheck("hazard ratio", "TTE stat for binary endpoint", Severity.HIGH),
                    ContentCheck("log-rank", "TTE test for binary", Severity.HIGH),
                ],
                required_tools=["get_statistical_method", "get_efficacy_tables"],
            ),
            SectionExpectation(
                section_id="8",
                section_name="Safety Analysis",
                required_content=[
                    ContentCheck("CRS", "Cytokine release syndrome", Severity.CRITICAL),
                    ContentCheck("cytokine release syndrome", "CRS full name", Severity.HIGH),
                    ContentCheck("ICANS", "Neurotoxicity", Severity.CRITICAL),
                    ContentCheck("neurotoxicity", "Neuro AE", Severity.HIGH),
                    ContentCheck("Lee criteria", "CRS grading", Severity.HIGH),
                    ContentCheck("tocilizumab", "CRS treatment", Severity.MEDIUM),
                    ContentCheck("corticosteroid", "CRS/ICANS treatment", Severity.MEDIUM),
                ],
                forbidden_content=[],
                required_tools=["get_safety_specifications", "get_cart_specifications"],
            ),
        ],
        global_required=[
            ContentCheck("CAR-T", "CAR-T therapy mentioned", Severity.HIGH),
            ContentCheck("DLBCL", "Correct indication", Severity.HIGH),
        ],
        global_forbidden=[
            ContentCheck("NSCLC", "Wrong disease", Severity.CRITICAL),
            ContentCheck("breast cancer", "Wrong disease", Severity.CRITICAL),
            ContentCheck("solid tumor", "Wrong tumor type", Severity.HIGH),
        ],
    ),

    # =========================================================================
    # CASE 3: Breast Cancer Adjuvant DFS Trial
    # =========================================================================
    GoldenSetCase(
        case_id="breast_adjuvant_dfs",
        description="Adjuvant breast cancer trial with DFS primary endpoint",
        category="oncology",
        difficulty="standard",
        tags=["solid_tumor", "adjuvant", "time_to_event", "dfs", "breast"],
        protocol={
            "study_id": "BREAST-001",
            "phase": "Phase 3",
            "indication": "breast cancer",
            "indication_detail": "Early-stage HR+/HER2- breast cancer",
            "setting": "adjuvant",
            "design": "randomized",
            "randomization_ratio": "1:1",
            "primary_endpoint": "DFS",
            "secondary_endpoints": ["OS", "DRFS", "safety"],
            "biomarkers": ["ER", "PR", "HER2", "Ki-67"],
            "stratification_factors": ["Nodal status", "Prior chemotherapy", "Menopausal status"],
            "sample_size": 4000,
            "events_required": 500,
            "has_interim": True,
        },
        section_expectations=[
            SectionExpectation(
                section_id="5A",
                section_name="Baseline Characteristics",
                required_content=[
                    ContentCheck("ER", "Estrogen receptor", Severity.CRITICAL),
                    ContentCheck("PR", "Progesterone receptor", Severity.CRITICAL),
                    ContentCheck("HER2", "HER2 status", Severity.CRITICAL),
                    ContentCheck("Ki-67", "Ki-67 proliferation", Severity.HIGH),
                    ContentCheck("menopausal", "Menopausal status", Severity.HIGH),
                    ContentCheck("nodal", "Nodal status", Severity.HIGH),
                ],
                forbidden_content=[
                    ContentCheck("EGFR", "Lung marker in breast", Severity.CRITICAL),
                    ContentCheck("ALK", "Lung marker in breast", Severity.CRITICAL),
                    ContentCheck("Ann Arbor", "Lymphoma staging", Severity.CRITICAL),
                    ContentCheck("smoking", "Lung risk factor in breast", Severity.HIGH),
                ],
                required_tools=["get_baseline_covariates"],
            ),
            SectionExpectation(
                section_id="6",
                section_name="Endpoint Definitions",
                required_content=[
                    ContentCheck("disease-free survival", "DFS defined", Severity.CRITICAL),
                    ContentCheck("DFS", "DFS abbreviation", Severity.HIGH),
                    ContentCheck("recurrence", "Recurrence event", Severity.CRITICAL),
                    ContentCheck("death", "Death as event", Severity.HIGH),
                    ContentCheck("new primary", "Second primary as event", Severity.MEDIUM),
                ],
                forbidden_content=[
                    ContentCheck("tumor response", "Response in adjuvant", Severity.HIGH),
                    ContentCheck("RECIST", "Response criteria in adjuvant", Severity.HIGH),
                    ContentCheck("ORR", "Response rate in adjuvant", Severity.HIGH),
                    ContentCheck("CR/PR", "Response categories in adjuvant", Severity.MEDIUM),
                ],
                required_tools=["get_censoring_rules"],
            ),
            SectionExpectation(
                section_id="7",
                section_name="Efficacy Analysis",
                required_content=[
                    ContentCheck("Kaplan-Meier", "KM method", Severity.CRITICAL),
                    ContentCheck("Cox", "Cox regression", Severity.CRITICAL),
                    ContentCheck("hazard ratio", "HR", Severity.CRITICAL),
                    ContentCheck("log-rank", "Log-rank test", Severity.HIGH),
                ],
                forbidden_content=[
                    ContentCheck("objective response", "Response in adjuvant", Severity.HIGH),
                    ContentCheck("RECIST", "Response criteria", Severity.HIGH),
                ],
                required_tools=["get_statistical_method", "get_time_to_event_analysis"],
            ),
        ],
        global_required=[
            ContentCheck("adjuvant", "Adjuvant setting", Severity.HIGH),
            ContentCheck("breast", "Correct indication", Severity.HIGH),
        ],
        global_forbidden=[
            ContentCheck("metastatic", "Wrong setting", Severity.HIGH),
            ContentCheck("advanced", "Wrong setting", Severity.MEDIUM),
            ContentCheck("lymphoma", "Wrong disease", Severity.CRITICAL),
        ],
    ),

    # =========================================================================
    # CASE 4: Multiple Myeloma Phase 2 (IMWG Criteria)
    # =========================================================================
    GoldenSetCase(
        case_id="myeloma_phase2_cr",
        description="Multiple myeloma trial with stringent CR as primary endpoint",
        category="hematology",
        difficulty="standard",
        tags=["hematology", "myeloma", "binary_endpoint", "imwg"],
        protocol={
            "study_id": "MM-001",
            "phase": "Phase 2",
            "indication": "multiple myeloma",
            "indication_detail": "Relapsed/refractory multiple myeloma",
            "design": "single-arm",
            "primary_endpoint": "sCR rate",
            "secondary_endpoints": ["ORR", "VGPR rate", "PFS", "DOR", "MRD negativity"],
            "response_criteria": "IMWG",
            "sample_size": 80,
        },
        section_expectations=[
            SectionExpectation(
                section_id="5A",
                section_name="Baseline Characteristics",
                required_content=[
                    ContentCheck("ISS", "ISS staging", Severity.CRITICAL),
                    ContentCheck("R-ISS", "Revised ISS", Severity.HIGH),
                    ContentCheck("cytogenetics", "Cytogenetic risk", Severity.CRITICAL),
                    ContentCheck("del(17p)", "High-risk cytogenetics", Severity.HIGH),
                    ContentCheck("t(4;14)", "High-risk translocation", Severity.HIGH),
                    ContentCheck("M-protein", "M-protein level", Severity.HIGH),
                ],
                forbidden_content=[
                    ContentCheck("Ann Arbor", "Lymphoma staging", Severity.CRITICAL),
                    ContentCheck("EGFR", "Solid tumor marker", Severity.CRITICAL),
                    ContentCheck("RECIST", "Solid tumor criteria", Severity.CRITICAL),
                ],
                required_tools=["get_baseline_covariates"],
            ),
            SectionExpectation(
                section_id="6",
                section_name="Endpoint Definitions",
                required_content=[
                    ContentCheck("IMWG", "IMWG criteria", Severity.CRITICAL),
                    ContentCheck("stringent complete response", "sCR definition", Severity.CRITICAL),
                    ContentCheck("sCR", "sCR abbreviation", Severity.HIGH),
                    ContentCheck("VGPR", "VGPR category", Severity.HIGH),
                    ContentCheck("immunofixation", "Response assessment", Severity.HIGH),
                    ContentCheck("MRD", "Minimal residual disease", Severity.MEDIUM),
                ],
                forbidden_content=[
                    ContentCheck("RECIST", "Solid tumor criteria", Severity.CRITICAL),
                    ContentCheck("Lugano", "Lymphoma criteria", Severity.CRITICAL),
                ],
                required_tools=["get_response_criteria"],
            ),
            SectionExpectation(
                section_id="7",
                section_name="Efficacy Analysis",
                required_content=[
                    ContentCheck("Clopper-Pearson", "Exact CI", Severity.HIGH),
                    ContentCheck("confidence interval", "CI", Severity.HIGH),
                    ContentCheck("response rate", "Rate analysis", Severity.HIGH),
                ],
                required_tools=["get_statistical_method"],
            ),
        ],
        global_required=[
            ContentCheck("myeloma", "Correct disease", Severity.HIGH),
            ContentCheck("IMWG", "Correct criteria", Severity.HIGH),
        ],
        global_forbidden=[
            ContentCheck("NSCLC", "Wrong disease", Severity.CRITICAL),
            ContentCheck("lymphoma", "Wrong disease", Severity.HIGH),
            ContentCheck("RECIST", "Wrong criteria", Severity.CRITICAL),
        ],
    ),

    # =========================================================================
    # CASE 5: Phase 1 Dose Escalation
    # =========================================================================
    GoldenSetCase(
        case_id="phase1_dose_escalation",
        description="Phase 1 dose escalation study with DLT as primary endpoint",
        category="early_phase",
        difficulty="standard",
        tags=["phase1", "dose_escalation", "dlt", "safety_focused"],
        protocol={
            "study_id": "PHASE1-001",
            "phase": "Phase 1",
            "indication": "solid tumors",
            "indication_detail": "Advanced solid tumors",
            "design": "dose escalation",
            "dose_escalation_method": "3+3",
            "primary_endpoint": "DLT",
            "primary_objective": "MTD determination",
            "secondary_endpoints": ["ORR", "PK", "safety"],
            "dlt_evaluation_period": "28 days",
            "sample_size": 30,
            "has_expansion_cohort": True,
        },
        section_expectations=[
            SectionExpectation(
                section_id="5",
                section_name="Analysis Populations",
                required_content=[
                    ContentCheck("DLT-evaluable", "DLT evaluable population", Severity.CRITICAL),
                    ContentCheck("dose-limiting toxicity", "DLT defined", Severity.CRITICAL),
                    ContentCheck("safety population", "Safety population", Severity.HIGH),
                ],
                required_tools=["get_population_definitions"],
            ),
            SectionExpectation(
                section_id="6",
                section_name="Endpoint Definitions",
                required_content=[
                    ContentCheck("dose-limiting toxicity", "DLT defined", Severity.CRITICAL),
                    ContentCheck("DLT", "DLT abbreviation", Severity.HIGH),
                    ContentCheck("MTD", "MTD defined", Severity.CRITICAL),
                    ContentCheck("maximum tolerated dose", "MTD full name", Severity.HIGH),
                    ContentCheck("evaluation period", "DLT window", Severity.HIGH),
                ],
                required_tools=[],
            ),
            SectionExpectation(
                section_id="7",
                section_name="Efficacy Analysis",
                required_content=[
                    ContentCheck("descriptive", "Descriptive stats", Severity.HIGH),
                ],
                forbidden_content=[
                    ContentCheck("primary analysis", "No primary efficacy in Ph1", Severity.MEDIUM),
                    ContentCheck("hypothesis test", "No hypothesis in Ph1", Severity.MEDIUM),
                ],
                required_tools=[],
            ),
            SectionExpectation(
                section_id="8",
                section_name="Safety Analysis",
                required_content=[
                    ContentCheck("DLT", "DLT analysis", Severity.CRITICAL),
                    ContentCheck("dose level", "By dose analysis", Severity.HIGH),
                    ContentCheck("CTCAE", "CTCAE grading", Severity.HIGH),
                ],
                required_tools=["get_safety_specifications"],
            ),
        ],
        global_required=[
            ContentCheck("Phase 1", "Correct phase", Severity.CRITICAL),
            ContentCheck("dose escalation", "Correct design", Severity.HIGH),
        ],
        global_forbidden=[
            ContentCheck("Phase 3", "Wrong phase", Severity.CRITICAL),
            ContentCheck("randomized", "Wrong design for Ph1", Severity.HIGH),
            ContentCheck("hazard ratio", "Efficacy stat in Ph1 dose finding", Severity.MEDIUM),
        ],
    ),

    # =========================================================================
    # CASE 6: RCC with Immunotherapy (IO-specific safety)
    # =========================================================================
    GoldenSetCase(
        case_id="rcc_immunotherapy_pfs",
        description="RCC trial with immunotherapy and IO-specific safety analysis",
        category="oncology",
        difficulty="standard",
        tags=["solid_tumor", "immunotherapy", "io_safety", "rcc"],
        protocol={
            "study_id": "RCC-IO-001",
            "phase": "Phase 3",
            "indication": "renal cell carcinoma",
            "indication_detail": "Advanced clear cell RCC",
            "line_of_therapy": "first-line",
            "design": "randomized",
            "treatment": "immunotherapy",
            "treatment_class": "PD-1 inhibitor + TKI",
            "primary_endpoint": "PFS",
            "secondary_endpoints": ["OS", "ORR", "DOR"],
            "response_criteria": "RECIST 1.1",
            "stratification_factors": ["IMDC risk", "Region"],
            "sample_size": 800,
        },
        section_expectations=[
            SectionExpectation(
                section_id="5A",
                section_name="Baseline Characteristics",
                required_content=[
                    ContentCheck("IMDC", "IMDC risk score", Severity.CRITICAL),
                    ContentCheck("favorable", "Favorable risk", Severity.HIGH),
                    ContentCheck("intermediate", "Intermediate risk", Severity.HIGH),
                    ContentCheck("poor", "Poor risk", Severity.HIGH),
                    ContentCheck("nephrectomy", "Prior nephrectomy", Severity.HIGH),
                    ContentCheck("clear cell", "Histology", Severity.MEDIUM),
                ],
                forbidden_content=[
                    ContentCheck("EGFR mutation", "Lung-specific", Severity.HIGH),
                    ContentCheck("ALK", "Lung-specific", Severity.HIGH),
                ],
                required_tools=["get_baseline_covariates", "get_prognostic_scores"],
            ),
            SectionExpectation(
                section_id="8",
                section_name="Safety Analysis",
                required_content=[
                    ContentCheck("immune-related", "irAE analysis", Severity.CRITICAL),
                    ContentCheck("irAE", "irAE abbreviation", Severity.HIGH),
                    ContentCheck("colitis", "IO-specific AE", Severity.HIGH),
                    ContentCheck("pneumonitis", "IO-specific AE", Severity.HIGH),
                    ContentCheck("hepatitis", "IO-specific AE", Severity.MEDIUM),
                    ContentCheck("endocrinop", "Endocrine AE", Severity.MEDIUM),
                ],
                forbidden_content=[
                    ContentCheck("CRS", "CAR-T term", Severity.CRITICAL),
                    ContentCheck("ICANS", "CAR-T term", Severity.CRITICAL),
                ],
                required_tools=["get_safety_specifications"],
            ),
        ],
        global_required=[
            ContentCheck("renal", "Correct indication", Severity.HIGH),
            ContentCheck("immunotherapy", "Correct treatment", Severity.HIGH),
        ],
        global_forbidden=[
            ContentCheck("breast", "Wrong disease", Severity.CRITICAL),
            ContentCheck("lymphoma", "Wrong disease", Severity.CRITICAL),
        ],
    ),

    # =========================================================================
    # CASE 7: CLL with Targeted Therapy
    # =========================================================================
    GoldenSetCase(
        case_id="cll_targeted_pfs",
        description="CLL trial with BTK inhibitor",
        category="hematology",
        difficulty="standard",
        tags=["hematology", "cll", "targeted_therapy", "time_to_event"],
        protocol={
            "study_id": "CLL-001",
            "phase": "Phase 3",
            "indication": "CLL",
            "indication_detail": "Relapsed/refractory chronic lymphocytic leukemia",
            "design": "randomized",
            "treatment": "BTK inhibitor",
            "primary_endpoint": "PFS",
            "secondary_endpoints": ["OS", "ORR", "MRD"],
            "response_criteria": "iwCLL 2018",
            "sample_size": 300,
        },
        section_expectations=[
            SectionExpectation(
                section_id="5A",
                section_name="Baseline Characteristics",
                required_content=[
                    ContentCheck("IGHV", "IGHV mutation status", Severity.CRITICAL),
                    ContentCheck("del(17p)", "High-risk deletion", Severity.CRITICAL),
                    ContentCheck("TP53", "TP53 mutation", Severity.HIGH),
                    ContentCheck("Rai", "Rai staging", Severity.HIGH),
                    ContentCheck("Binet", "Binet staging", Severity.MEDIUM),
                ],
                forbidden_content=[
                    ContentCheck("Ann Arbor", "Wrong staging system", Severity.CRITICAL),
                    ContentCheck("ISS", "Myeloma staging", Severity.CRITICAL),
                    ContentCheck("EGFR", "Solid tumor marker", Severity.CRITICAL),
                ],
                required_tools=["get_baseline_covariates"],
            ),
            SectionExpectation(
                section_id="6",
                section_name="Endpoint Definitions",
                required_content=[
                    ContentCheck("iwCLL", "iwCLL criteria", Severity.HIGH),
                    ContentCheck("progression-free survival", "PFS defined", Severity.CRITICAL),
                ],
                forbidden_content=[
                    ContentCheck("RECIST", "Solid tumor criteria", Severity.CRITICAL),
                    ContentCheck("IMWG", "Myeloma criteria", Severity.HIGH),
                ],
                required_tools=["get_censoring_rules"],
            ),
        ],
        global_required=[
            ContentCheck("CLL", "Correct disease", Severity.CRITICAL),
        ],
        global_forbidden=[
            ContentCheck("NSCLC", "Wrong disease", Severity.CRITICAL),
            ContentCheck("solid tumor", "Wrong tumor type", Severity.HIGH),
        ],
    ),

    # =========================================================================
    # CASE 8: ADC Trial (Special safety: ILD)
    # =========================================================================
    GoldenSetCase(
        case_id="adc_her2_orr",
        description="HER2-directed ADC trial with ILD monitoring",
        category="oncology",
        difficulty="complex",
        tags=["solid_tumor", "adc", "special_safety", "binary_endpoint"],
        protocol={
            "study_id": "ADC-001",
            "phase": "Phase 2",
            "indication": "breast cancer",
            "indication_detail": "HER2-positive metastatic breast cancer",
            "design": "single-arm",
            "treatment": "ADC",
            "treatment_name": "HER2-directed ADC",
            "primary_endpoint": "ORR",
            "secondary_endpoints": ["DOR", "PFS", "OS"],
            "response_criteria": "RECIST 1.1",
            "sample_size": 150,
            "special_safety": ["ILD", "ocular toxicity"],
        },
        section_expectations=[
            SectionExpectation(
                section_id="8",
                section_name="Safety Analysis",
                required_content=[
                    ContentCheck("interstitial lung disease", "ILD monitoring", Severity.CRITICAL),
                    ContentCheck("ILD", "ILD abbreviation", Severity.CRITICAL),
                    ContentCheck("pneumonitis", "Lung toxicity", Severity.HIGH),
                ],
                forbidden_content=[
                    ContentCheck("CRS", "CAR-T term", Severity.HIGH),
                    ContentCheck("ICANS", "CAR-T term", Severity.HIGH),
                ],
                required_tools=["get_safety_specifications", "get_adc_specifications"],
            ),
        ],
        global_required=[
            ContentCheck("ADC", "Correct treatment type", Severity.HIGH),
            ContentCheck("HER2", "Correct target", Severity.HIGH),
        ],
        global_forbidden=[
            ContentCheck("CAR-T", "Wrong treatment", Severity.CRITICAL),
        ],
    ),
]


# =============================================================================
# EVALUATOR CLASS
# =============================================================================

class GoldenSetEvaluator:
    """Evaluates generated SAP sections against golden set expectations."""

    def __init__(self, workbench=None, verbose: bool = False):
        """
        Initialize evaluator.

        Args:
            workbench: Optional WorkbenchCore instance for generation
            verbose: Print detailed output
        """
        self.workbench = workbench
        self.verbose = verbose
        self.results: List[GoldenSetResult] = []

    def evaluate_content(
        self,
        content: str,
        required_checks: List[ContentCheck],
        forbidden_checks: List[ContentCheck],
        section: str = "global"
    ) -> tuple[List[CheckResult], List[str], List[str], List[str]]:
        """
        Evaluate content against required and forbidden checks.

        Returns:
            Tuple of (all_results, required_found, required_missing, forbidden_found)
        """
        results = []
        required_found = []
        required_missing = []
        forbidden_found = []

        # Check required content
        for check in required_checks:
            found = check.matches(content)
            results.append(CheckResult(
                check_type="required",
                pattern=check.pattern,
                description=check.description,
                passed=found,
                severity=check.severity,
                section=section
            ))
            if found:
                required_found.append(check.pattern)
            else:
                required_missing.append(check.pattern)

        # Check forbidden content
        for check in forbidden_checks:
            found = check.matches(content)
            results.append(CheckResult(
                check_type="forbidden",
                pattern=check.pattern,
                description=check.description,
                passed=not found,  # Pass if NOT found
                severity=check.severity,
                section=section
            ))
            if found:
                forbidden_found.append(check.pattern)

        return results, required_found, required_missing, forbidden_found

    def evaluate_section(
        self,
        content: str,
        expectation: SectionExpectation,
        tools_called: List[str] = None
    ) -> SectionResult:
        """Evaluate a single section against expectations."""
        tools_called = tools_called or []

        # Run content checks
        check_results, required_found, required_missing, forbidden_found = self.evaluate_content(
            content,
            expectation.required_content,
            expectation.forbidden_content,
            section=expectation.section_id
        )

        # Check tools
        tools_expected = expectation.required_tools
        tools_missing = [t for t in tools_expected if t not in tools_called]

        # Calculate score
        total_checks = len(expectation.required_content) + len(expectation.forbidden_content)
        passed_checks = sum(1 for r in check_results if r.passed)

        # Tool penalty
        tool_score = 1.0 if not tools_expected else (
            len([t for t in tools_expected if t in tools_called]) / len(tools_expected)
        )

        # Length penalty
        length_ok = len(content) >= expectation.min_length

        # Final score
        if total_checks > 0:
            content_score = (passed_checks / total_checks) * 100
        else:
            content_score = 100.0

        score = content_score * 0.7 + tool_score * 100 * 0.2 + (100 if length_ok else 50) * 0.1

        # Determine pass/fail
        critical_failures = [
            r for r in check_results
            if not r.passed and r.severity == Severity.CRITICAL
        ]
        passed = len(critical_failures) == 0 and len(forbidden_found) == 0

        return SectionResult(
            section_id=expectation.section_id,
            section_name=expectation.section_name,
            passed=passed,
            score=round(score, 1),
            checks_passed=passed_checks,
            checks_failed=total_checks - passed_checks,
            required_found=required_found,
            required_missing=required_missing,
            forbidden_found=forbidden_found,
            tools_called=tools_called,
            tools_expected=tools_expected,
            tools_missing=tools_missing,
            content_length=len(content),
            details=check_results
        )

    def run_case(
        self,
        case: GoldenSetCase,
        generated_sections: Dict[str, str] = None,
        tools_by_section: Dict[str, List[str]] = None
    ) -> GoldenSetResult:
        """
        Run evaluation for a single golden set case.

        Args:
            case: The golden set test case
            generated_sections: Dict mapping section_id to generated content
            tools_by_section: Dict mapping section_id to tools called
        """
        start_time = time.time()

        generated_sections = generated_sections or {}
        tools_by_section = tools_by_section or {}

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"Running: {case.case_id}")
            print(f"Description: {case.description}")
            print(f"{'='*60}")

        # Evaluate each section
        section_results = []
        for expectation in case.section_expectations:
            content = generated_sections.get(expectation.section_id, "")
            tools = tools_by_section.get(expectation.section_id, [])

            if not content and self.workbench:
                # Generate section if workbench available
                try:
                    result = self.workbench.generate_section(
                        workspace_id="eval",
                        section_id=expectation.section_id,
                        protocol_metadata=case.protocol,
                        use_tools=True
                    )
                    content = result.get("content", "")
                    tools = result.get("tools_called", [])
                except Exception as e:
                    if self.verbose:
                        print(f"  Generation error for section {expectation.section_id}: {e}")
                    content = ""
                    tools = []

            section_result = self.evaluate_section(content, expectation, tools)
            section_results.append(section_result)

            if self.verbose:
                status = "PASS" if section_result.passed else "FAIL"
                print(f"  Section {expectation.section_id} ({expectation.section_name}): {status} ({section_result.score:.0f}%)")
                if section_result.required_missing:
                    print(f"    Missing: {section_result.required_missing[:3]}")
                if section_result.forbidden_found:
                    print(f"    Forbidden found: {section_result.forbidden_found}")

        # Global checks (combine all content)
        all_content = " ".join(generated_sections.values())
        global_results, global_found, global_missing, global_forbidden = self.evaluate_content(
            all_content,
            case.global_required,
            case.global_forbidden,
            section="global"
        )

        # Calculate overall metrics
        total_required = sum(len(e.required_content) for e in case.section_expectations) + len(case.global_required)
        required_passed = sum(s.checks_passed for s in section_results) + len(global_found)

        total_forbidden = sum(len(e.forbidden_content) for e in case.section_expectations) + len(case.global_forbidden)
        forbidden_passed = total_forbidden - len(global_forbidden) - sum(len(s.forbidden_found) for s in section_results)

        # Critical failures
        critical_failures = []
        for sr in section_results:
            for detail in sr.details:
                if not detail.passed and detail.severity == Severity.CRITICAL:
                    critical_failures.append(f"{sr.section_id}: {detail.description}")
        for gr in global_results:
            if not gr.passed and gr.severity == Severity.CRITICAL:
                critical_failures.append(f"Global: {gr.description}")

        # Overall score
        section_avg = sum(s.score for s in section_results) / len(section_results) if section_results else 0
        global_score = (len(global_found) / len(case.global_required) * 100) if case.global_required else 100

        # Penalties for forbidden content
        forbidden_penalty = len(global_forbidden) * 10 + sum(len(s.forbidden_found) * 10 for s in section_results)

        overall_score = max(0, section_avg * 0.8 + global_score * 0.2 - forbidden_penalty)

        # Overall pass/fail
        passed = len(critical_failures) == 0 and all(s.passed for s in section_results)

        result = GoldenSetResult(
            case_id=case.case_id,
            description=case.description,
            passed=passed,
            overall_score=round(overall_score, 1),
            execution_time_seconds=round(time.time() - start_time, 2),
            section_results=section_results,
            global_checks=global_results,
            total_required_checks=total_required,
            required_checks_passed=required_passed,
            total_forbidden_checks=total_forbidden,
            forbidden_checks_passed=forbidden_passed,
            critical_failures=critical_failures
        )

        self.results.append(result)
        return result

    def run_all(
        self,
        category: str = None,
        tags: List[str] = None,
        generated_data: Dict[str, Dict[str, str]] = None
    ) -> List[GoldenSetResult]:
        """
        Run all golden set cases (optionally filtered).

        Args:
            category: Filter by category
            tags: Filter by tags (any match)
            generated_data: Dict mapping case_id to {section_id: content}
        """
        cases = GOLDEN_SET_CASES

        if category:
            cases = [c for c in cases if c.category == category]

        if tags:
            cases = [c for c in cases if any(t in c.tags for t in tags)]

        print(f"\nRunning {len(cases)} golden set cases...")

        self.results = []
        for case in cases:
            sections = (generated_data or {}).get(case.case_id, {})
            self.run_case(case, generated_sections=sections)

        return self.results

    def print_summary(self):
        """Print summary of all results."""
        if not self.results:
            print("No results to summarize")
            return

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        avg_score = sum(r.overall_score for r in self.results) / total

        print(f"\n{'='*60}")
        print("GOLDEN SET EVALUATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total Cases: {total}")
        print(f"Passed: {passed} ({100*passed/total:.0f}%)")
        print(f"Failed: {total - passed}")
        print(f"Average Score: {avg_score:.1f}/100")

        # By category
        categories = {}
        for r in self.results:
            case = next((c for c in GOLDEN_SET_CASES if c.case_id == r.case_id), None)
            if case:
                cat = case.category
                if cat not in categories:
                    categories[cat] = {"passed": 0, "total": 0, "scores": []}
                categories[cat]["total"] += 1
                categories[cat]["scores"].append(r.overall_score)
                if r.passed:
                    categories[cat]["passed"] += 1

        print(f"\nBy Category:")
        for cat, stats in sorted(categories.items()):
            avg = sum(stats["scores"]) / len(stats["scores"])
            print(f"  {cat}: {stats['passed']}/{stats['total']} passed, avg score {avg:.0f}")

        # Critical failures
        all_critical = []
        for r in self.results:
            for cf in r.critical_failures:
                all_critical.append(f"{r.case_id}: {cf}")

        if all_critical:
            print(f"\nCritical Failures ({len(all_critical)}):")
            for cf in all_critical[:10]:
                print(f"  - {cf}")
            if len(all_critical) > 10:
                print(f"  ... and {len(all_critical) - 10} more")

        # Failed cases
        failed = [r for r in self.results if not r.passed]
        if failed:
            print(f"\nFailed Cases:")
            for r in failed:
                print(f"  - {r.case_id}: {r.overall_score:.0f}/100")

    def export_results(self, filepath: str):
        """Export results to JSON."""
        output = {
            "timestamp": datetime.now().isoformat(),
            "total_cases": len(self.results),
            "passed": sum(1 for r in self.results if r.passed),
            "failed": sum(1 for r in self.results if not r.passed),
            "average_score": sum(r.overall_score for r in self.results) / len(self.results) if self.results else 0,
            "results": [r.to_dict() for r in self.results]
        }

        # Fix enum serialization
        def fix_enums(obj):
            if isinstance(obj, dict):
                return {k: fix_enums(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [fix_enums(item) for item in obj]
            elif isinstance(obj, Severity):
                return obj.value
            return obj

        output = fix_enums(output)

        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"Results exported to {filepath}")


# =============================================================================
# MOCK DATA GENERATOR (for testing without actual generation)
# =============================================================================

def generate_mock_sections(case: GoldenSetCase) -> Dict[str, str]:
    """
    Generate mock section content that should pass the golden set.
    Useful for testing the eval framework itself.
    """
    mock_sections = {}

    for expectation in case.section_expectations:
        # Build content that includes all required patterns
        content_parts = [f"Section {expectation.section_id}: {expectation.section_name}\n"]

        for check in expectation.required_content:
            content_parts.append(f"This section covers {check.pattern} as required. ")

        # Add some filler
        content_parts.append("\n" * 5)
        content_parts.append("Additional analysis details and methodology are described below. " * 10)

        mock_sections[expectation.section_id] = "".join(content_parts)

    return mock_sections


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Golden Set Evaluation Framework")
    parser.add_argument("--list", "-l", action="store_true", help="List all test cases")
    parser.add_argument("--run", "-r", type=str, help="Run case(s): 'all' or specific case_id")
    parser.add_argument("--category", "-c", type=str, help="Filter by category")
    parser.add_argument("--tag", "-t", type=str, help="Filter by tag")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--export", "-e", type=str, help="Export results to JSON file")
    parser.add_argument("--mock", "-m", action="store_true", help="Use mock data (for testing eval framework)")

    args = parser.parse_args()

    # List cases
    if args.list:
        print(f"\nGolden Set Test Cases ({len(GOLDEN_SET_CASES)} total)\n")
        print(f"{'ID':<25} {'Category':<15} {'Difficulty':<12} Description")
        print("-" * 80)
        for case in GOLDEN_SET_CASES:
            print(f"{case.case_id:<25} {case.category:<15} {case.difficulty:<12} {case.description[:40]}")

        print(f"\nCategories: {set(c.category for c in GOLDEN_SET_CASES)}")
        print(f"Tags: {set(t for c in GOLDEN_SET_CASES for t in c.tags)}")
        return

    # Run evaluation
    if args.run:
        evaluator = GoldenSetEvaluator(verbose=args.verbose)

        if args.run == "all":
            # Generate mock data if requested
            generated_data = {}
            if args.mock:
                for case in GOLDEN_SET_CASES:
                    generated_data[case.case_id] = generate_mock_sections(case)

            tags = [args.tag] if args.tag else None
            evaluator.run_all(
                category=args.category,
                tags=tags,
                generated_data=generated_data if args.mock else None
            )
        else:
            # Run specific case
            case = next((c for c in GOLDEN_SET_CASES if c.case_id == args.run), None)
            if not case:
                print(f"Case not found: {args.run}")
                print("Use --list to see available cases")
                return

            sections = generate_mock_sections(case) if args.mock else {}
            evaluator.run_case(case, generated_sections=sections)

        evaluator.print_summary()

        if args.export:
            evaluator.export_results(args.export)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
