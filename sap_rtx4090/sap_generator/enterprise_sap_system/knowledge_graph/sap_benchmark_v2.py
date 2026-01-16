"""
SAP Benchmark System v2.0
=========================
Comprehensive evaluation of generated SAP sections against reference SAPs.

Based on:
- ICH E9 / E9(R1) Guidelines
- Gamble et al. JAMA 2017 (55-item checklist)
- FDA Oncology Endpoints Guidance

Author: SAP Generation System
"""

import json
import time
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import anthropic

# =============================================================================
# SCORING DIMENSIONS (Universal across all sections)
# =============================================================================

SCORING_DIMENSIONS = {
    "accuracy": {
        "weight": 0.25,
        "description": "Correct statistical methods and values for trial type",
        "rubric": {
            1: "Fundamentally wrong methods",
            2: "Major methodological errors",
            3: "Multiple incorrect approaches",
            4: "Some methods inappropriate",
            5: "Methods acceptable but suboptimal",
            6: "Methods mostly correct, minor issues",
            7: "Correct methods, small gaps",
            8: "Correct methods throughout",
            9: "Methods match reference exactly",
            10: "Perfect accuracy, regulatory-ready"
        }
    },
    "completeness": {
        "weight": 0.30,
        "description": "All required elements present",
        "rubric": {
            1: "<20% elements present",
            2: "20-30% elements",
            3: "30-40% elements",
            4: "40-50% elements",
            5: "50-60% elements",
            6: "60-70% elements",
            7: "70-80% elements",
            8: "80-90% elements",
            9: "90-95% elements",
            10: ">95% elements present"
        }
    },
    "specificity": {
        "weight": 0.20,
        "description": "Protocol-specific values vs generic templates",
        "rubric": {
            1: "100% generic boilerplate",
            2: "Mostly generic, few specific values",
            3: "More generic than specific",
            4: "Half generic, half specific",
            5: "Slightly more specific than generic",
            6: "Mostly specific, some generic",
            7: "Largely protocol-specific",
            8: "Almost all protocol-specific",
            9: "All values from protocol",
            10: "Perfect specificity with protocol citations"
        }
    },
    "conciseness": {
        "weight": 0.15,
        "description": "Appropriate length matching reference scope",
        "rubric": {
            1: ">5x reference length (severe over-elaboration)",
            2: "4-5x reference length",
            3: "3-4x reference length",
            4: "2-3x reference length",
            5: "1.5-2x reference length",
            6: "1.25-1.5x reference length",
            7: "0.75-1.25x reference (ideal range)",
            8: "Within 15% of reference",
            9: "Within 10% of reference",
            10: "Perfect length match"
        }
    },
    "quality": {
        "weight": 0.10,
        "description": "Professional writing, FDA submission ready",
        "rubric": {
            1: "Unintelligible or severely flawed",
            2: "Major structural/grammar issues",
            3: "Poorly organized",
            4: "Readable but informal",
            5: "Acceptable quality",
            6: "Good professional quality",
            7: "Very professional",
            8: "Excellent, near submission-ready",
            9: "Submission-ready quality",
            10: "Exemplary regulatory document"
        }
    }
}

# =============================================================================
# SECTION WEIGHTS (Regulatory importance)
# =============================================================================

SECTION_WEIGHTS = {
    "1_title_page": 0.02,
    "2_objectives_endpoints_estimands": 0.14,
    "3_study_design": 0.14,
    "4_statistical_analyses": 0.20,
    "6_efficacy": 0.25,
    "7_safety": 0.12,
    "11_appendices": 0.13
}

# =============================================================================
# SECTION CONFIGURATIONS WITH REQUIRED ELEMENTS
# =============================================================================

SECTION_CONFIGS = {
    # =========================================================================
    # SECTION 1: TITLE PAGE
    # =========================================================================
    "1_title_page": {
        "id": "1_title_page",
        "name": "Title Page",
        "display_name": "1. Title Page",
        "weight": 0.02,
        "reference_length_chars": 400,
        "required_elements": [
            {
                "id": "protocol_number",
                "name": "Protocol Number",
                "critical": True,
                "description": "Exact protocol identification number",
                "validation": "Must match protocol exactly",
                "keywords": ["protocol", "study number", "protocol no", "study id"]
            },
            {
                "id": "protocol_title",
                "name": "Protocol Title",
                "critical": True,
                "description": "Full official study title",
                "validation": "Must match protocol title page",
                "keywords": ["title", "study title", "protocol title"]
            },
            {
                "id": "sap_version",
                "name": "SAP Version",
                "critical": True,
                "description": "Version number and date",
                "validation": "Format: Version X.X, DD-MMM-YYYY",
                "keywords": ["version", "sap version", "document version"]
            },
            {
                "id": "sponsor_name",
                "name": "Sponsor Name",
                "critical": False,
                "description": "Sponsoring company or institution",
                "validation": "Official legal name",
                "keywords": ["sponsor", "company", "institution"]
            },
            {
                "id": "author_statistician",
                "name": "Author/Statistician",
                "critical": False,
                "description": "Lead statistician name and credentials",
                "validation": "Name with degree/title",
                "keywords": ["author", "statistician", "prepared by", "biostatistician"]
            },
            {
                "id": "signature_lines",
                "name": "Signature Lines",
                "critical": False,
                "description": "Approval signature blocks",
                "validation": "Statistician + Medical Monitor minimum",
                "keywords": ["signature", "approval", "approved by", "sign"]
            },
            {
                "id": "amendment_history",
                "name": "Amendment History",
                "critical": False,
                "conditional": True,
                "condition": "sap_version > 1.0",
                "description": "Table of SAP versions and changes",
                "keywords": ["amendment", "revision history", "change history", "version history"]
            },
            {
                "id": "confidentiality_statement",
                "name": "Confidentiality Statement",
                "critical": False,
                "description": "Standard confidentiality language",
                "keywords": ["confidential", "proprietary", "not for distribution"]
            }
        ]
    },

    # =========================================================================
    # SECTION 2: OBJECTIVES, ENDPOINTS, AND ESTIMANDS
    # =========================================================================
    "2_objectives_endpoints_estimands": {
        "id": "2_objectives_endpoints_estimands",
        "name": "Objectives, Endpoints, and Estimands",
        "display_name": "2. Objectives, Endpoints, and Estimands",
        "weight": 0.14,
        "reference_length_chars": 4000,
        "required_elements": [
            # 2.1 Primary Objective
            {
                "id": "primary_objective_statement",
                "name": "Primary Objective Statement",
                "critical": True,
                "description": "Clear statement of what study aims to demonstrate",
                "validation": "Must include: action verb + treatment + comparator + population",
                "keywords": ["primary objective", "main objective", "primary aim"]
            },
            {
                "id": "primary_treatment_comparison",
                "name": "Treatment Comparison in Objective",
                "critical": True,
                "description": "What is being compared",
                "validation": "Intervention vs control clearly stated",
                "keywords": ["compare", "versus", "vs", "compared to"]
            },
            # 2.1.1 Primary Endpoint(s)
            {
                "id": "primary_endpoint_name",
                "name": "Primary Endpoint Name",
                "critical": True,
                "description": "Exact name of primary endpoint",
                "validation": "Standard terminology (PFS, OS, ORR, pCR, etc.)",
                "keywords": ["primary endpoint", "primary efficacy endpoint", "pfs", "os", "orr"]
            },
            {
                "id": "primary_endpoint_definition",
                "name": "Primary Endpoint Definition",
                "critical": True,
                "description": "Complete definition of endpoint",
                "validation": "Time from X to Y, or proportion with Z",
                "keywords": ["defined as", "time from", "proportion", "rate of"]
            },
            {
                "id": "assessment_method",
                "name": "Assessment Method",
                "critical": True,
                "description": "How endpoint is measured",
                "validation": "RECIST 1.1, iRECIST, Lugano, BICR, investigator, etc.",
                "keywords": ["recist", "lugano", "bicr", "investigator", "central review", "assessment"]
            },
            {
                "id": "assessment_schedule",
                "name": "Assessment Schedule",
                "critical": True,
                "description": "When assessments occur",
                "validation": "Frequency and duration specified",
                "keywords": ["every", "weeks", "schedule", "frequency", "assessed"]
            },
            {
                "id": "confirmation_requirement",
                "name": "Response Confirmation Requirement",
                "critical": False,
                "conditional": True,
                "condition": "has_response_endpoint",
                "description": "If response needs confirmation",
                "validation": "Confirmation timing specified",
                "keywords": ["confirmed", "confirmation", "≥4 weeks", "repeat assessment"]
            },
            # Estimand Framework
            {
                "id": "estimand_population",
                "name": "Estimand: Population Component",
                "critical": True,
                "description": "ICH E9(R1) estimand population component",
                "validation": "Which patients included",
                "keywords": ["population", "itt", "fas", "all randomized"]
            },
            {
                "id": "estimand_variable",
                "name": "Estimand: Variable Component",
                "critical": True,
                "description": "ICH E9(R1) estimand variable component",
                "validation": "The endpoint being measured",
                "keywords": ["variable", "endpoint", "outcome"]
            },
            {
                "id": "estimand_ice",
                "name": "Estimand: Intercurrent Events",
                "critical": True,
                "description": "ICH E9(R1) intercurrent event handling",
                "validation": "Each ICE listed with strategy",
                "keywords": ["intercurrent", "ice", "treatment policy", "composite", "hypothetical"]
            },
            {
                "id": "estimand_summary",
                "name": "Estimand: Population-level Summary",
                "critical": True,
                "description": "ICH E9(R1) summary measure",
                "validation": "HR, difference in proportions, odds ratio, etc.",
                "keywords": ["hazard ratio", "difference", "odds ratio", "summary measure"]
            },
            # 2.2 Secondary Objectives/Endpoints
            {
                "id": "secondary_objectives_list",
                "name": "Secondary Objectives Listed",
                "critical": True,
                "description": "All secondary objectives stated",
                "validation": "Each objective numbered/bulleted",
                "keywords": ["secondary objective", "secondary aim"]
            },
            {
                "id": "secondary_endpoints_list",
                "name": "Secondary Endpoints Listed",
                "critical": True,
                "description": "All secondary endpoints with definitions",
                "validation": "Each endpoint named and defined",
                "keywords": ["secondary endpoint", "os", "orr", "dor", "dcr"]
            },
            {
                "id": "secondary_endpoint_definitions",
                "name": "Secondary Endpoint Definitions",
                "critical": True,
                "description": "Each secondary endpoint fully defined",
                "validation": "Definition, assessment method for each",
                "keywords": ["defined as", "calculated as", "measured"]
            },
            # 2.3 Exploratory
            {
                "id": "exploratory_objectives_list",
                "name": "Exploratory Objectives Listed",
                "critical": False,
                "description": "Exploratory/tertiary objectives",
                "validation": "Objectives listed",
                "keywords": ["exploratory objective", "tertiary", "additional objective"]
            },
            {
                "id": "exploratory_endpoints_list",
                "name": "Exploratory Endpoints Listed",
                "critical": False,
                "description": "Exploratory endpoints defined",
                "validation": "Each endpoint named",
                "keywords": ["exploratory endpoint", "biomarker", "correlative"]
            },
            {
                "id": "no_inferential_testing_note",
                "name": "No Inferential Testing Statement",
                "critical": True,
                "description": "Disclaimer that exploratory analyses not for inference",
                "validation": "Statement present",
                "keywords": ["not for inferential", "descriptive", "exploratory", "no formal testing"]
            }
        ]
    },

    # =========================================================================
    # SECTION 3: STUDY DESIGN
    # =========================================================================
    "3_study_design": {
        "id": "3_study_design",
        "name": "Study Design",
        "display_name": "3. Study Design",
        "weight": 0.14,
        "reference_length_chars": 3500,
        "required_elements": [
            # 3.3 Analysis Populations
            {
                "id": "itt_fas_definition",
                "name": "ITT/FAS Definition",
                "critical": True,
                "description": "Intent-to-Treat or Full Analysis Set",
                "validation": "All randomized OR all enrolled - specify which",
                "keywords": ["itt", "intent-to-treat", "fas", "full analysis set", "all randomized"]
            },
            {
                "id": "itt_inclusion_criteria",
                "name": "ITT Inclusion Criteria",
                "critical": True,
                "description": "Exact criteria for ITT inclusion",
                "validation": "Clear rule (randomized, regardless of treatment)",
                "keywords": ["regardless of", "all patients who", "inclusion"]
            },
            {
                "id": "safety_population_definition",
                "name": "Safety Population Definition",
                "critical": True,
                "description": "Safety analysis set",
                "validation": "Received at least one dose",
                "keywords": ["safety population", "safety set", "received", "at least one dose"]
            },
            {
                "id": "safety_analysis_assignment",
                "name": "Safety Analysis Assignment",
                "critical": True,
                "description": "How patients assigned in safety analysis",
                "validation": "As-treated vs as-randomized",
                "keywords": ["as-treated", "actual treatment received", "as randomized"]
            },
            {
                "id": "pp_definition",
                "name": "Per-Protocol Definition",
                "critical": True,
                "description": "Per-protocol population",
                "validation": "No major protocol deviations",
                "keywords": ["per-protocol", "pp", "without major", "protocol deviation"]
            },
            {
                "id": "pp_exclusion_criteria",
                "name": "PP Exclusion Criteria",
                "critical": True,
                "description": "What excludes from per-protocol",
                "validation": "List of major deviation types",
                "keywords": ["excluded", "exclusion", "major deviation", "not eligible"]
            },
            {
                "id": "evaluable_population",
                "name": "Evaluable/Response-Evaluable Population",
                "critical": False,
                "conditional": True,
                "condition": "has_response_endpoint",
                "description": "Response-evaluable set",
                "validation": "Baseline + ≥1 post-baseline assessment",
                "keywords": ["evaluable", "response-evaluable", "baseline and", "post-baseline"]
            },
            {
                "id": "pk_population",
                "name": "PK Population",
                "critical": False,
                "conditional": True,
                "condition": "has_pk_endpoints",
                "description": "Pharmacokinetic analysis set",
                "validation": "≥1 evaluable PK sample",
                "keywords": ["pk population", "pharmacokinetic", "pk concentration"]
            },
            {
                "id": "primary_efficacy_population",
                "name": "Primary Efficacy Analysis Population",
                "critical": True,
                "description": "Which population for primary analysis",
                "validation": "Explicitly stated",
                "keywords": ["primary efficacy", "primary analysis", "will be performed on"]
            },
            {
                "id": "population_use_mapping",
                "name": "Population Use Mapping",
                "critical": True,
                "description": "Which analyses use which population",
                "validation": "Table or list mapping population to analysis type",
                "keywords": ["efficacy analysis", "safety analysis", "sensitivity", "population"]
            },
            # 3.4 Timing of Analysis
            {
                "id": "primary_analysis_timing",
                "name": "Primary Analysis Timing",
                "critical": True,
                "description": "When primary analysis occurs",
                "validation": "Event-driven, calendar-driven, or enrollment-driven",
                "keywords": ["primary analysis", "when", "after", "events", "conducted"]
            },
            {
                "id": "analysis_trigger",
                "name": "Analysis Trigger",
                "critical": True,
                "description": "What triggers the analysis",
                "validation": "Specific trigger clearly stated",
                "keywords": ["event-driven", "calendar", "enrollment", "triggered", "when"]
            },
            {
                "id": "events_required",
                "name": "Number of Events Required",
                "critical": True,
                "conditional": True,
                "condition": "has_tte_endpoint",
                "description": "Target events for time-to-event analysis",
                "validation": "Exact number from sample size",
                "keywords": ["events", "approximately", "target", "required"]
            },
            {
                "id": "interim_analysis_timing",
                "name": "Interim Analysis Timing",
                "critical": True,
                "conditional": True,
                "condition": "has_interim_analysis",
                "description": "When interim analyses occur",
                "validation": "Information fraction or calendar time",
                "keywords": ["interim analysis", "interim", "information fraction"]
            },
            {
                "id": "final_analysis_timing",
                "name": "Final Analysis Timing",
                "critical": True,
                "description": "When final analysis occurs",
                "validation": "Trigger specified",
                "keywords": ["final analysis", "final", "primary analysis"]
            },
            {
                "id": "data_cutoff_definition",
                "name": "Data Cutoff Definition",
                "critical": True,
                "description": "How data cutoff date determined",
                "validation": "Clear rule for cutoff",
                "keywords": ["data cutoff", "cutoff date", "data cut", "clinical cutoff"]
            },
            # 3.7 Statistical Hypotheses
            {
                "id": "null_hypothesis",
                "name": "Null Hypothesis (H₀)",
                "critical": True,
                "description": "Null hypothesis explicitly stated",
                "validation": "H₀ with mathematical notation",
                "keywords": ["null hypothesis", "h0", "h₀", "hr = 1", "no difference"]
            },
            {
                "id": "alternative_hypothesis",
                "name": "Alternative Hypothesis (H₁)",
                "critical": True,
                "description": "Alternative hypothesis explicitly stated",
                "validation": "H₁ with mathematical notation",
                "keywords": ["alternative hypothesis", "h1", "h₁", "hr <", "superior"]
            },
            {
                "id": "alpha_level",
                "name": "Alpha Level",
                "critical": True,
                "description": "Type I error rate",
                "validation": "Numeric value (0.05, 0.025, 0.01)",
                "keywords": ["alpha", "α", "significance level", "type i error", "0.05", "0.025"]
            },
            {
                "id": "sidedness",
                "name": "One-sided vs Two-sided",
                "critical": True,
                "description": "Directionality of test",
                "validation": "Explicitly stated",
                "keywords": ["one-sided", "two-sided", "1-sided", "2-sided"]
            },
            {
                "id": "success_criteria",
                "name": "Success Criteria",
                "critical": True,
                "description": "What constitutes positive result",
                "validation": "Clear statement of success",
                "keywords": ["success", "positive", "considered successful", "if p-value"]
            }
        ]
    },

    # =========================================================================
    # SECTION 4: STATISTICAL ANALYSES
    # =========================================================================
    "4_statistical_analyses": {
        "id": "4_statistical_analyses",
        "name": "Statistical Analyses",
        "display_name": "4. Statistical Analyses",
        "weight": 0.20,
        "reference_length_chars": 5000,
        "required_elements": [
            # 4.1 General Methodology
            {
                "id": "software_specified",
                "name": "Statistical Software",
                "critical": False,
                "description": "Software and version",
                "validation": "SAS, R, or other with version",
                "keywords": ["sas", "r version", "software", "statistical software"]
            },
            {
                "id": "rounding_conventions",
                "name": "Rounding Conventions",
                "critical": True,
                "description": "Decimal places for statistics",
                "validation": "Rules for means, %, p-values",
                "keywords": ["decimal", "rounding", "significant figures", "places"]
            },
            {
                "id": "pvalue_reporting",
                "name": "P-value Reporting",
                "critical": True,
                "description": "P-value format and threshold",
                "validation": "Format specified",
                "keywords": ["p-value", "p value", "<0.0001", "decimal places"]
            },
            {
                "id": "ci_level",
                "name": "Confidence Interval Level",
                "critical": True,
                "description": "Default CI level",
                "validation": "95%, 90%, etc.",
                "keywords": ["confidence interval", "95%", "ci", "confidence level"]
            },
            {
                "id": "two_sided_default",
                "name": "Two-sided Default",
                "critical": True,
                "description": "Default sidedness convention",
                "validation": "Statement of default",
                "keywords": ["two-sided", "unless otherwise", "default"]
            },
            {
                "id": "descriptive_statistics",
                "name": "Descriptive Statistics Conventions",
                "critical": True,
                "description": "How summaries presented",
                "validation": "Continuous: N, mean, SD, median, min-max; Categorical: n(%)",
                "keywords": ["mean", "median", "standard deviation", "n (%)", "descriptive"]
            },
            # 4.2 Key Definitions
            {
                "id": "study_day_definition",
                "name": "Study Day Definition",
                "critical": True,
                "description": "How study day calculated",
                "validation": "Day 1 definition (randomization or first dose)",
                "keywords": ["study day", "day 1", "day one", "calculated as"]
            },
            {
                "id": "baseline_definition",
                "name": "Baseline Definition",
                "critical": True,
                "description": "What constitutes baseline",
                "validation": "Last value before X",
                "keywords": ["baseline", "last value", "prior to", "before first dose"]
            },
            {
                "id": "baseline_efficacy_vs_safety",
                "name": "Baseline: Efficacy vs Safety Distinction",
                "critical": True,
                "description": "Different baselines if applicable",
                "validation": "Distinction made if different",
                "keywords": ["efficacy baseline", "safety baseline", "randomization", "first dose"]
            },
            {
                "id": "on_treatment_period",
                "name": "On-Treatment Period",
                "critical": True,
                "description": "Treatment period definition",
                "validation": "Start and end defined",
                "keywords": ["on-treatment", "treatment period", "first dose", "last dose", "+ 30 days"]
            },
            {
                "id": "teae_definition",
                "name": "TEAE Definition",
                "critical": True,
                "description": "Treatment-emergent AE criteria",
                "validation": "New or worsened after first dose",
                "keywords": ["teae", "treatment-emergent", "onset", "worsened", "after first dose"]
            },
            {
                "id": "follow_up_time_definition",
                "name": "Follow-up Time Definition",
                "critical": True,
                "description": "How follow-up calculated",
                "validation": "Formula provided",
                "keywords": ["follow-up time", "follow up", "duration", "months", "calculated"]
            },
            # 4.3 Multiplicity Adjustment
            {
                "id": "adjustment_method",
                "name": "Multiplicity Adjustment Method",
                "critical": True,
                "description": "Statistical method for multiplicity",
                "validation": "Hochberg, Holm, Bonferroni, graphical, hierarchical, or none",
                "keywords": ["hochberg", "holm", "bonferroni", "graphical", "hierarchical", "multiplicity"]
            },
            {
                "id": "testing_hierarchy",
                "name": "Testing Hierarchy",
                "critical": True,
                "description": "Order of hypothesis testing",
                "validation": "Explicit order stated",
                "keywords": ["hierarchy", "order", "first", "then", "tested only if"]
            },
            {
                "id": "alpha_allocation",
                "name": "Alpha Allocation",
                "critical": True,
                "description": "How alpha split across hypotheses",
                "validation": "Fractions sum to total alpha",
                "keywords": ["alpha allocation", "α =", "split", "allocated"]
            },
            {
                "id": "recycling_rules",
                "name": "Alpha Recycling Rules",
                "critical": True,
                "conditional": True,
                "condition": "method == 'graphical'",
                "description": "How alpha recycles on rejection",
                "validation": "Transition weights specified",
                "keywords": ["recycling", "transfer", "transition", "if rejected"]
            },
            # 4.4 Covariates and Subgroups
            {
                "id": "stratification_factors",
                "name": "Stratification Factors",
                "critical": True,
                "description": "Randomization stratification factors",
                "validation": "All factors listed with categories",
                "keywords": ["stratification", "stratified by", "strata", "randomization factor"]
            },
            {
                "id": "covariates_in_model",
                "name": "Covariates in Statistical Model",
                "critical": True,
                "description": "Covariates for adjusted analyses",
                "validation": "List with rationale",
                "keywords": ["covariate", "adjusted for", "model", "stratified"]
            },
            {
                "id": "prespecified_subgroups",
                "name": "Pre-specified Subgroups",
                "critical": True,
                "description": "All subgroups for analysis",
                "validation": "Complete list",
                "keywords": ["subgroup", "pre-specified", "prespecified", "age", "sex", "ecog"]
            },
            {
                "id": "subgroup_categories",
                "name": "Subgroup Categories/Cutpoints",
                "critical": True,
                "description": "Categories for each subgroup",
                "validation": "All cutpoints specified",
                "keywords": ["<65", "≥65", "cutpoint", "categories", "vs"]
            },
            {
                "id": "interaction_tests",
                "name": "Interaction Tests",
                "critical": True,
                "description": "Treatment × subgroup interaction",
                "validation": "Method specified",
                "keywords": ["interaction", "treatment-by-subgroup", "heterogeneity"]
            },
            {
                "id": "forest_plot_specification",
                "name": "Forest Plot Specification",
                "critical": True,
                "conditional": True,
                "condition": "is_randomized",
                "description": "Forest plot details",
                "validation": "HR + 95% CI display specified",
                "keywords": ["forest plot", "hr", "95% ci", "subgroup"]
            },
            {
                "id": "subgroup_exploratory_disclaimer",
                "name": "Subgroup Exploratory Disclaimer",
                "critical": True,
                "description": "Statement that subgroups are exploratory",
                "validation": "Disclaimer present",
                "keywords": ["exploratory", "not adjusted for multiplicity", "hypothesis-generating"]
            },
            # 4.5 Visit Windows
            {
                "id": "window_definitions",
                "name": "Visit Window Definitions",
                "critical": True,
                "description": "Windows for each scheduled visit",
                "validation": "Target day ± window for each visit",
                "keywords": ["window", "±", "target day", "visit"]
            },
            {
                "id": "target_day",
                "name": "Target Day for Each Visit",
                "critical": True,
                "description": "Nominal day for visits",
                "validation": "Numeric day specified",
                "keywords": ["target day", "day", "nominal"]
            },
            {
                "id": "window_range",
                "name": "Window Range",
                "critical": True,
                "description": "Acceptable range around target",
                "validation": "± days or absolute range",
                "keywords": ["±", "days", "range", "window"]
            },
            {
                "id": "multiple_assessments_rule",
                "name": "Multiple Assessments Rule",
                "critical": True,
                "description": "Which value if >1 in window",
                "validation": "Rule specified (closest, first, last, worst)",
                "keywords": ["multiple", "closest", "first", "last", "if more than one"]
            },
            {
                "id": "unscheduled_visit_handling",
                "name": "Unscheduled Visit Handling",
                "critical": True,
                "description": "How unscheduled visits assigned",
                "validation": "Assignment rule",
                "keywords": ["unscheduled", "assigned", "nearest"]
            },
            # 4.6 Intercurrent Events
            {
                "id": "ice_types_listed",
                "name": "ICE Types Listed",
                "critical": True,
                "description": "All intercurrent events identified",
                "validation": "Complete list",
                "keywords": ["intercurrent event", "ice", "death", "discontinuation", "new therapy"]
            },
            {
                "id": "strategy_per_ice",
                "name": "Strategy per ICE",
                "critical": True,
                "description": "ICH E9(R1) strategy for each ICE",
                "validation": "Treatment policy, composite, hypothetical, principal stratum",
                "keywords": ["treatment policy", "composite", "hypothetical", "principal stratum", "strategy"]
            },
            {
                "id": "strategy_rationale",
                "name": "Strategy Rationale",
                "critical": True,
                "description": "Why each strategy chosen",
                "validation": "Justification provided",
                "keywords": ["rationale", "because", "reflects", "real-world"]
            },
            {
                "id": "estimand_alignment",
                "name": "ICE-Estimand Alignment",
                "critical": True,
                "description": "Link to Section 2 estimand",
                "validation": "Reference to estimand",
                "keywords": ["estimand", "consistent with", "section 2", "aligned"]
            },
            # 4.7 Missing Data
            {
                "id": "primary_missing_approach",
                "name": "Primary Missing Data Approach",
                "critical": True,
                "description": "Main method for missing data",
                "validation": "Method clearly stated",
                "keywords": ["missing data", "available data", "censored", "imputation"]
            },
            {
                "id": "date_imputation_rules",
                "name": "Date Imputation Rules",
                "critical": True,
                "description": "Partial date handling",
                "validation": "Day, month, year rules",
                "keywords": ["partial date", "imputation", "missing day", "missing month"]
            },
            {
                "id": "missing_day_rule",
                "name": "Missing Day Rule",
                "critical": True,
                "description": "How missing day imputed",
                "validation": "1st or 15th typically",
                "keywords": ["missing day", "1st", "15th", "impute"]
            },
            {
                "id": "missing_month_rule",
                "name": "Missing Month Rule",
                "critical": True,
                "description": "How missing month imputed",
                "validation": "January, June, July, etc.",
                "keywords": ["missing month", "january", "june", "impute"]
            },
            {
                "id": "missing_baseline_handling",
                "name": "Missing Baseline Handling",
                "critical": True,
                "description": "What if baseline missing",
                "validation": "Excluded or imputed rule",
                "keywords": ["missing baseline", "excluded", "not included"]
            },
            {
                "id": "missing_covariate_handling",
                "name": "Missing Covariate Handling",
                "critical": True,
                "description": "Missing stratification/covariate data",
                "validation": "Rule specified",
                "keywords": ["missing covariate", "missing stratification", "irt", "crf"]
            },
            # 4.8 Duplicate and Unscheduled
            {
                "id": "duplicate_record_rule",
                "name": "Duplicate Record Rule",
                "critical": True,
                "description": "Which value kept if duplicate",
                "validation": "Rule specified",
                "keywords": ["duplicate", "if duplicate", "same timepoint"]
            },
            {
                "id": "unscheduled_assessment_rule",
                "name": "Unscheduled Assessment Rule",
                "critical": True,
                "description": "How unscheduled data handled",
                "validation": "Included/excluded, assignment",
                "keywords": ["unscheduled", "included", "excluded", "assigned"]
            },
            {
                "id": "reassessment_rule",
                "name": "Re-assessment Rule",
                "critical": True,
                "description": "Repeat measurements handling",
                "validation": "Which value used",
                "keywords": ["repeat", "reassessment", "replicate", "average"]
            }
        ]
    },

    # =========================================================================
    # SECTION 6: EFFICACY
    # =========================================================================
    "6_efficacy": {
        "id": "6_efficacy",
        "name": "Efficacy",
        "display_name": "6. Efficacy",
        "weight": 0.25,
        "reference_length_chars": 6000,
        "required_elements": [
            # 6.1.1.1.1 Primary Estimand
            {
                "id": "estimand_restated",
                "name": "Estimand Restated",
                "critical": True,
                "description": "Estimand from Section 2 restated",
                "validation": "All 4 components present",
                "keywords": ["estimand", "population", "variable", "intercurrent", "summary"]
            },
            # 6.1.1.1.2 Endpoint Definition
            {
                "id": "endpoint_derivation",
                "name": "Endpoint Derivation Formula",
                "critical": True,
                "description": "How endpoint calculated from data",
                "validation": "Formula or algorithm",
                "keywords": ["calculated as", "derived", "formula", "= ("]
            },
            {
                "id": "tte_start_date",
                "name": "Time-to-Event Start Date",
                "critical": True,
                "description": "Origin for TTE",
                "validation": "Randomization, dosing, etc.",
                "keywords": ["start date", "time from", "date of randomization", "origin"]
            },
            {
                "id": "event_date_definition",
                "name": "Event Date Definition",
                "critical": True,
                "description": "What constitutes event date",
                "validation": "Date of progression, death, etc.",
                "keywords": ["event date", "date of", "progression", "death"]
            },
            {
                "id": "response_criteria_version",
                "name": "Response Criteria with Version",
                "critical": True,
                "description": "RECIST, Lugano, etc. with version",
                "validation": "Criteria + version number",
                "keywords": ["recist 1.1", "lugano", "version", "criteria"]
            },
            {
                "id": "assessment_type",
                "name": "Assessment Type (BICR/Investigator)",
                "critical": True,
                "description": "BICR, investigator, or both",
                "validation": "Specified",
                "keywords": ["bicr", "investigator", "central review", "blinded"]
            },
            {
                "id": "censoring_rules_reference",
                "name": "Censoring Rules Reference",
                "critical": True,
                "conditional": True,
                "condition": "has_tte_endpoint",
                "description": "Reference to censoring section or table",
                "validation": "Reference or table included",
                "keywords": ["censoring", "censored", "section", "table"]
            },
            # 6.1.1.1.3 Primary Analysis
            {
                "id": "statistical_method",
                "name": "Primary Statistical Method",
                "critical": True,
                "description": "Primary statistical test/model",
                "validation": "Method named",
                "keywords": ["log-rank", "cox", "fisher", "cmh", "chi-square", "statistical method"]
            },
            {
                "id": "model_specification",
                "name": "Model Specification",
                "critical": True,
                "description": "Full model details",
                "validation": "Covariates, strata listed",
                "keywords": ["cox model", "stratified by", "adjusted for", "covariates"]
            },
            {
                "id": "stratification_in_analysis",
                "name": "Stratification in Analysis",
                "critical": True,
                "description": "How stratification handled",
                "validation": "IRT strata vs CRF strata",
                "keywords": ["stratified", "irt", "crf", "randomization strata"]
            },
            {
                "id": "point_estimate",
                "name": "Point Estimate",
                "critical": True,
                "description": "Primary effect measure",
                "validation": "HR, OR, difference specified",
                "keywords": ["hazard ratio", "hr", "odds ratio", "difference", "point estimate"]
            },
            {
                "id": "ci_method_efficacy",
                "name": "CI Method for Efficacy",
                "critical": True,
                "description": "Confidence interval method",
                "validation": "Method and level",
                "keywords": ["95% ci", "confidence interval", "clopper-pearson"]
            },
            {
                "id": "pvalue_test",
                "name": "P-value Test",
                "critical": True,
                "description": "Test for p-value",
                "validation": "Test specified",
                "keywords": ["p-value", "log-rank", "two-sided", "test"]
            },
            {
                "id": "analysis_population_efficacy",
                "name": "Analysis Population for Primary",
                "critical": True,
                "description": "Population for primary analysis",
                "validation": "ITT, mITT, FAS specified",
                "keywords": ["itt", "fas", "population", "performed on"]
            },
            {
                "id": "km_methods",
                "name": "Kaplan-Meier Methods",
                "critical": True,
                "conditional": True,
                "condition": "has_tte_endpoint",
                "description": "KM estimation details",
                "validation": "Product-limit method",
                "keywords": ["kaplan-meier", "km", "product-limit", "survival curve"]
            },
            {
                "id": "median_ci_method",
                "name": "Median CI Method",
                "critical": True,
                "conditional": True,
                "condition": "has_tte_endpoint",
                "description": "CI method for median",
                "validation": "Brookmeyer-Crowley or similar",
                "keywords": ["median", "brookmeyer", "ci for median"]
            },
            {
                "id": "landmark_rates",
                "name": "Landmark Survival Rates",
                "critical": False,
                "description": "Survival rates at timepoints",
                "validation": "Timepoints specified",
                "keywords": ["6-month", "12-month", "landmark", "rate at"]
            },
            # 6.1.1.1.4 Secondary Analyses
            {
                "id": "secondary_analyses_list",
                "name": "Secondary Analyses Listed",
                "critical": True,
                "description": "All secondary analyses of primary endpoint",
                "validation": "Each analysis named",
                "keywords": ["secondary analysis", "additional", "supportive"]
            },
            {
                "id": "secondary_analysis_methods",
                "name": "Methods for Secondary Analyses",
                "critical": True,
                "description": "How each conducted",
                "validation": "Method specified for each",
                "keywords": ["unstratified", "investigator", "method"]
            },
            # 6.1.1.1.5 Sensitivity Analyses
            {
                "id": "sensitivity_list",
                "name": "Sensitivity Analyses Listed",
                "critical": True,
                "description": "All pre-specified sensitivity analyses",
                "validation": "Each named with purpose",
                "keywords": ["sensitivity analysis", "sensitivity", "robustness"]
            },
            {
                "id": "assumption_tested",
                "name": "Assumption Tested per Sensitivity",
                "critical": True,
                "description": "What each sensitivity tests",
                "validation": "Explicit assumption stated",
                "keywords": ["assumption", "robustness to", "tests"]
            },
            {
                "id": "sensitivity_methods",
                "name": "Methods for Sensitivity Analyses",
                "critical": True,
                "description": "How each conducted",
                "validation": "Method specified",
                "keywords": ["method", "using", "per-protocol", "unstratified"]
            },
            {
                "id": "prespecified_statement",
                "name": "Pre-specified Statement",
                "critical": True,
                "description": "Statement that these are pre-specified",
                "validation": "Not post-hoc",
                "keywords": ["pre-specified", "prespecified", "planned", "a priori"]
            },
            {
                "id": "per_protocol_sensitivity",
                "name": "Per-Protocol Sensitivity",
                "critical": True,
                "description": "PP analysis as sensitivity",
                "validation": "Present",
                "keywords": ["per-protocol", "pp population", "sensitivity"]
            },
            {
                "id": "unstratified_sensitivity",
                "name": "Unstratified Sensitivity",
                "critical": True,
                "conditional": True,
                "condition": "primary_is_stratified",
                "description": "Unstratified if primary stratified",
                "validation": "Present if applicable",
                "keywords": ["unstratified", "without stratification"]
            },
            # 6.1.1.1.6 Subgroup Analyses
            {
                "id": "subgroups_efficacy_listed",
                "name": "All Subgroups Listed for Efficacy",
                "critical": True,
                "description": "Complete subgroup list from 4.4",
                "validation": "All subgroups with categories",
                "keywords": ["subgroup", "age", "sex", "ecog", "pd-l1"]
            },
            {
                "id": "subgroup_analysis_method",
                "name": "Subgroup Analysis Method",
                "critical": True,
                "description": "Method for subgroup analyses",
                "validation": "Same as primary or different",
                "keywords": ["within each subgroup", "cox model", "unstratified"]
            },
            {
                "id": "forest_plot_efficacy",
                "name": "Forest Plot Specification",
                "critical": True,
                "description": "Forest plot details",
                "validation": "HR + CI + interaction p",
                "keywords": ["forest plot", "hr", "95% ci", "interaction"]
            },
            {
                "id": "interaction_pvalue",
                "name": "Interaction P-value Method",
                "critical": True,
                "description": "Treatment × subgroup interaction",
                "validation": "How calculated",
                "keywords": ["interaction", "p-value", "treatment-by-subgroup"]
            },
            {
                "id": "subgroup_exploratory_statement",
                "name": "Subgroup Exploratory Statement",
                "critical": True,
                "description": "Subgroups are exploratory disclaimer",
                "validation": "Present",
                "keywords": ["exploratory", "no multiplicity", "hypothesis-generating"]
            }
        ]
    },

    # =========================================================================
    # SECTION 7: SAFETY ANALYSES
    # =========================================================================
    "7_safety": {
        "id": "7_safety",
        "name": "Safety Analyses",
        "display_name": "7. Safety Analyses",
        "weight": 0.12,
        "reference_length_chars": 3500,
        "required_elements": [
            {
                "id": "safety_population_reference",
                "name": "Safety Population Reference",
                "critical": True,
                "description": "Reference to safety population definition",
                "validation": "Links to Section 3.3",
                "keywords": ["safety population", "section 3", "received"]
            },
            {
                "id": "teae_definition_reference",
                "name": "TEAE Definition Reference",
                "critical": True,
                "description": "Reference to TEAE definition",
                "validation": "Links to Section 4.2 or stated here",
                "keywords": ["teae", "treatment-emergent", "section 4", "defined"]
            },
            {
                "id": "meddra_version",
                "name": "MedDRA Version",
                "critical": True,
                "description": "Medical Dictionary version",
                "validation": "Version number specified",
                "keywords": ["meddra", "version", "coded using"]
            },
            {
                "id": "ctcae_version",
                "name": "CTCAE Version",
                "critical": True,
                "description": "CTCAE grading version",
                "validation": "Version number specified",
                "keywords": ["ctcae", "nci ctcae", "version", "graded"]
            },
            {
                "id": "ae_summary_approach",
                "name": "AE Summary Approach",
                "critical": True,
                "description": "How AEs summarized",
                "validation": "By SOC/PT, by severity, etc.",
                "keywords": ["soc", "pt", "preferred term", "system organ class", "summarized"]
            },
            {
                "id": "ae_incidence_calculation",
                "name": "AE Incidence Calculation",
                "critical": True,
                "description": "Subject-level vs event-level",
                "validation": "Counting method specified",
                "keywords": ["incidence", "patient", "subject", "counted once"]
            },
            {
                "id": "severity_grading",
                "name": "Severity Grading Method",
                "critical": True,
                "description": "How severity determined",
                "validation": "CTCAE grades or Mild/Moderate/Severe",
                "keywords": ["grade", "severity", "mild", "moderate", "severe", "ctcae"]
            },
            {
                "id": "sae_handling",
                "name": "SAE Handling",
                "critical": True,
                "description": "Serious AE analysis",
                "validation": "Separate summary specified",
                "keywords": ["sae", "serious adverse event", "separate", "summarized"]
            },
            {
                "id": "deaths_analysis",
                "name": "Deaths Analysis",
                "critical": True,
                "description": "Death summary approach",
                "validation": "Cause, timing specified",
                "keywords": ["death", "cause of death", "on-treatment", "follow-up"]
            },
            {
                "id": "discontinuation_due_to_ae",
                "name": "Discontinuation Due to AE",
                "critical": True,
                "description": "Treatment discontinuation for AEs",
                "validation": "Summary approach",
                "keywords": ["discontinuation", "discontinued due to", "leading to"]
            },
            {
                "id": "aesi_handling",
                "name": "AESI Handling",
                "critical": False,
                "conditional": True,
                "condition": "has_aesi",
                "description": "Adverse Events of Special Interest",
                "validation": "AESI defined and summarized separately",
                "keywords": ["aesi", "special interest", "immune-related", "irae"]
            },
            # 7.1.3 Laboratory
            {
                "id": "lab_parameters_listed",
                "name": "Laboratory Parameters Listed",
                "critical": True,
                "description": "Categories of labs analyzed",
                "validation": "Hematology, chemistry, urinalysis",
                "keywords": ["hematology", "chemistry", "laboratory", "hemoglobin", "alt", "ast"]
            },
            {
                "id": "lab_summary_statistics",
                "name": "Lab Summary Statistics",
                "critical": True,
                "description": "How labs summarized",
                "validation": "By visit, change from baseline",
                "keywords": ["by visit", "change from baseline", "actual value", "shift"]
            },
            {
                "id": "shift_table_spec",
                "name": "Shift Table Specification",
                "critical": True,
                "description": "Baseline to post-baseline shift",
                "validation": "Shift categories defined",
                "keywords": ["shift table", "baseline to", "worst post-baseline", "grade"]
            },
            {
                "id": "ctcae_grading_labs",
                "name": "CTCAE Grading for Labs",
                "critical": True,
                "description": "CTCAE grades for lab abnormalities",
                "validation": "Grade criteria referenced",
                "keywords": ["ctcae grade", "laboratory", "graded per", "abnormality"]
            },
            {
                "id": "normal_range_handling",
                "name": "Normal Range Handling",
                "critical": True,
                "description": "Central vs local lab ranges",
                "validation": "Specified",
                "keywords": ["normal range", "central lab", "local lab", "reference range"]
            }
        ]
    },

    # =========================================================================
    # SECTION 11: APPENDICES
    # =========================================================================
    "11_appendices": {
        "id": "11_appendices",
        "name": "Appendices",
        "display_name": "11. Appendices",
        "weight": 0.13,
        "reference_length_chars": 4000,
        "required_elements": [
            # 11.1 Schedule of Assessments
            {
                "id": "soa_table_present",
                "name": "SOA Table Present",
                "critical": True,
                "description": "Full schedule table",
                "validation": "Table with visits × assessments",
                "keywords": ["schedule of assessment", "soa", "visit", "screening"]
            },
            {
                "id": "all_visits_listed",
                "name": "All Visits Listed",
                "critical": True,
                "description": "Complete visit schedule",
                "validation": "Screening through follow-up",
                "keywords": ["screening", "day 1", "week", "eot", "follow-up"]
            },
            {
                "id": "all_assessments_mapped",
                "name": "All Assessments Mapped",
                "critical": True,
                "description": "Which assessment at which visit",
                "validation": "X marks or checkmarks",
                "keywords": ["x", "assessment", "tumor", "laboratory", "ecg"]
            },
            {
                "id": "soa_windows_shown",
                "name": "Visit Windows Shown in SOA",
                "critical": True,
                "description": "± days for each visit",
                "validation": "Windows in table or footnote",
                "keywords": ["±", "window", "days"]
            },
            # 11.2 Lab Normal Ranges
            {
                "id": "reference_ranges_table",
                "name": "Reference Ranges Table",
                "critical": True,
                "description": "Normal ranges by parameter",
                "validation": "Table with parameter | units | range",
                "keywords": ["normal range", "reference range", "parameter", "units"]
            },
            {
                "id": "units_specified",
                "name": "Units Specified",
                "critical": True,
                "description": "SI or conventional units",
                "validation": "Units column present",
                "keywords": ["units", "g/dl", "mg/dl", "mmol/l"]
            },
            {
                "id": "lab_source_noted",
                "name": "Lab Source Noted",
                "critical": True,
                "description": "Central lab or standard reference",
                "validation": "Source specified",
                "keywords": ["central lab", "source", "reference"]
            },
            # 11.3 Questionnaire Scoring (conditional)
            {
                "id": "pro_instruments_named",
                "name": "PRO Instruments Named",
                "critical": True,
                "conditional": True,
                "condition": "has_pro_endpoints",
                "description": "All PRO instruments used",
                "validation": "Full names with abbreviations",
                "keywords": ["eortc", "qlq", "eq-5d", "fact", "pro"]
            },
            {
                "id": "scoring_algorithm",
                "name": "Scoring Algorithm",
                "critical": True,
                "conditional": True,
                "condition": "has_pro_endpoints",
                "description": "How scores calculated",
                "validation": "Algorithm or reference to manual",
                "keywords": ["scoring", "algorithm", "calculated", "manual"]
            },
            {
                "id": "missing_item_rules_pro",
                "name": "Missing Item Rules for PRO",
                "critical": True,
                "conditional": True,
                "condition": "has_pro_endpoints",
                "description": "How missing items handled",
                "validation": "Half-rule, prorating, etc.",
                "keywords": ["missing item", "half-rule", "50%", "imputed"]
            },
            {
                "id": "mid_thresholds",
                "name": "MID Thresholds",
                "critical": False,
                "conditional": True,
                "condition": "has_pro_endpoints",
                "description": "Minimally important difference",
                "validation": "Threshold values",
                "keywords": ["mid", "minimally important", "clinically meaningful"]
            },
            # 11.5 TFL Index
            {
                "id": "table_index",
                "name": "Table Index",
                "critical": True,
                "description": "All tables numbered and titled",
                "validation": "Complete table list",
                "keywords": ["table", "index", "14.", "list of tables"]
            },
            {
                "id": "listing_index",
                "name": "Listing Index",
                "critical": True,
                "description": "All listings numbered and titled",
                "validation": "Complete listing list",
                "keywords": ["listing", "index", "16.", "list of listings"]
            },
            {
                "id": "figure_index",
                "name": "Figure Index",
                "critical": True,
                "description": "All figures numbered and titled",
                "validation": "Complete figure list",
                "keywords": ["figure", "index", "kaplan-meier", "forest plot"]
            },
            {
                "id": "numbering_convention",
                "name": "Numbering Convention",
                "critical": True,
                "description": "TFL numbering system",
                "validation": "Convention explained",
                "keywords": ["numbering", "convention", "14.", "16."]
            },
            {
                "id": "population_per_output",
                "name": "Population per Output",
                "critical": True,
                "description": "Which population for each TFL",
                "validation": "Population indicated",
                "keywords": ["population", "itt", "safety", "per output"]
            }
        ]
    }
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ElementScore:
    """Score for a single required element."""
    element_id: str
    element_name: str
    present: bool
    quality: int  # 1-10
    note: str = ""
    is_critical: bool = False


@dataclass
class DimensionScores:
    """Scores for each dimension."""
    accuracy: float
    completeness: float
    specificity: float
    conciseness: float
    quality: float


@dataclass
class SectionResult:
    """Complete result for a section evaluation."""
    section_id: str
    section_name: str
    element_scores: List[ElementScore]
    dimension_scores: DimensionScores
    section_score: float
    critical_elements_met: bool
    elements_present: str  # "X/Y"
    critical_present: str  # "X/Y"
    gaps: List[str]
    over_elaboration: List[str]
    strengths: List[str]
    summary: str
    generated_length: int
    reference_length: int


@dataclass
class BenchmarkResult:
    """Complete benchmark result."""
    trial_id: str
    indication: str
    phase: str
    timestamp: str
    overall_score: float
    section_results: Dict[str, SectionResult]
    weakest_sections: List[str]
    strongest_sections: List[str]
    critical_failures: List[str]
    top_gaps: List[str]
    top_over_elaborations: List[str]


# =============================================================================
# BENCHMARK ENGINE
# =============================================================================

class SAPBenchmark:
    """
    SAP Benchmark System for evaluating generated SAP sections.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        """Initialize benchmark with Anthropic client."""
        self.client = anthropic.Anthropic()
        self.model = model
        self.section_configs = SECTION_CONFIGS
        self.scoring_dimensions = SCORING_DIMENSIONS
        self.section_weights = SECTION_WEIGHTS

    def evaluate_section(
        self,
        section_id: str,
        generated_content: str,
        reference_content: str,
        trial_info: Dict[str, str] = None
    ) -> SectionResult:
        """
        Evaluate a single SAP section.

        Args:
            section_id: Section identifier (e.g., "2_objectives_endpoints_estimands")
            generated_content: Generated SAP section content
            reference_content: Reference SAP section content
            trial_info: Optional dict with trial_id, indication, phase

        Returns:
            SectionResult with detailed evaluation
        """
        if section_id not in self.section_configs:
            raise ValueError(f"Unknown section: {section_id}")

        config = self.section_configs[section_id]
        trial_info = trial_info or {"trial_id": "Unknown", "indication": "Unknown", "phase": "Unknown"}

        # Build elements checklist for prompt
        elements_checklist = self._build_elements_checklist(config)

        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(
            section_name=config["display_name"],
            generated_content=generated_content,
            reference_content=reference_content,
            elements_checklist=elements_checklist,
            trial_info=trial_info
        )

        # Call LLM for evaluation
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text
            evaluation = self._parse_evaluation_response(result_text, config)

        except Exception as e:
            print(f"Error evaluating section {section_id}: {e}")
            evaluation = self._create_error_evaluation(config, str(e))

        # Calculate section score
        section_score = self._calculate_section_score(evaluation, config)

        # Build result
        return SectionResult(
            section_id=section_id,
            section_name=config["display_name"],
            element_scores=evaluation["element_scores"],
            dimension_scores=evaluation["dimension_scores"],
            section_score=section_score,
            critical_elements_met=evaluation["critical_met"],
            elements_present=evaluation["elements_present"],
            critical_present=evaluation["critical_present"],
            gaps=evaluation["gaps"],
            over_elaboration=evaluation["over_elaboration"],
            strengths=evaluation["strengths"],
            summary=evaluation["summary"],
            generated_length=len(generated_content),
            reference_length=len(reference_content) if reference_content else config["reference_length_chars"]
        )

    def evaluate_full_sap(
        self,
        generated_sections: Dict[str, str],
        reference_sections: Dict[str, str],
        trial_info: Dict[str, str]
    ) -> BenchmarkResult:
        """
        Evaluate all SAP sections.

        Args:
            generated_sections: Dict mapping section_id to generated content
            reference_sections: Dict mapping section_id to reference content
            trial_info: Dict with trial_id, indication, phase

        Returns:
            BenchmarkResult with complete evaluation
        """
        section_results = {}

        for section_id in self.section_configs.keys():
            generated = generated_sections.get(section_id, "")
            reference = reference_sections.get(section_id, "")

            if not generated:
                print(f"Skipping {section_id} - no generated content")
                continue

            print(f"Evaluating {section_id}...")
            result = self.evaluate_section(
                section_id=section_id,
                generated_content=generated,
                reference_content=reference,
                trial_info=trial_info
            )
            section_results[section_id] = result

        # Calculate overall score
        overall = self._calculate_overall_score(section_results)

        # Aggregate gaps and over-elaborations
        all_gaps = []
        all_over = []
        for result in section_results.values():
            all_gaps.extend([(result.section_name, g) for g in result.gaps])
            all_over.extend([(result.section_name, o) for o in result.over_elaboration])

        return BenchmarkResult(
            trial_id=trial_info.get("trial_id", "Unknown"),
            indication=trial_info.get("indication", "Unknown"),
            phase=trial_info.get("phase", "Unknown"),
            timestamp=datetime.now().isoformat(),
            overall_score=overall["overall_score"],
            section_results=section_results,
            weakest_sections=overall["weakest_sections"],
            strongest_sections=overall["strongest_sections"],
            critical_failures=overall["critical_failures"],
            top_gaps=[f"{s}: {g}" for s, g in all_gaps[:10]],
            top_over_elaborations=[f"{s}: {o}" for s, o in all_over[:5]]
        )

    def _build_elements_checklist(self, config: Dict) -> str:
        """Build checklist string from config elements."""
        lines = []
        for elem in config["required_elements"]:
            critical = "[CRITICAL]" if elem.get("critical") else ""
            conditional = f"[IF {elem.get('condition')}]" if elem.get("conditional") else ""
            lines.append(f"- {elem['name']} {critical}{conditional}: {elem['description']}")
        return "\n".join(lines)

    def _build_evaluation_prompt(
        self,
        section_name: str,
        generated_content: str,
        reference_content: str,
        elements_checklist: str,
        trial_info: Dict[str, str]
    ) -> str:
        """Build the LLM evaluation prompt."""

        # Truncate content if too long
        gen_truncated = generated_content[:8000] if len(generated_content) > 8000 else generated_content
        ref_truncated = reference_content[:8000] if reference_content and len(reference_content) > 8000 else reference_content

        prompt = f"""You are an expert SAP reviewer evaluating a generated Statistical Analysis Plan section.

SECTION: {section_name}
TRIAL: {trial_info.get('trial_id', 'Unknown')} ({trial_info.get('indication', 'Unknown')}, {trial_info.get('phase', 'Unknown')})

=== GENERATED CONTENT ===
{gen_truncated}

=== REFERENCE SAP (Real Pharma) ===
{ref_truncated if ref_truncated else "(No reference available)"}

=== REQUIRED ELEMENTS FOR THIS SECTION ===
{elements_checklist}

=== EVALUATION INSTRUCTIONS ===

1. ELEMENT CHECK
For each required element listed above, determine:
- PRESENT: Is this element clearly present in the generated content? (true/false)
- QUALITY (1-10): If present, how well is it executed? (1=poor, 10=excellent)
- NOTE: Brief observation (max 20 words)

2. DIMENSION SCORES (1-10 each)
- ACCURACY: Are statistical methods correct for this trial type?
- COMPLETENESS: What percentage of required elements are present?
- SPECIFICITY: Is content protocol-specific (not generic boilerplate)?
- CONCISENESS: Is length appropriate? (Reference length: {len(reference_content) if reference_content else 'unknown'} chars, Generated: {len(generated_content)} chars)
- QUALITY: Is this FDA submission ready?

3. GAPS (max 5)
List the most important missing or inadequate elements

4. OVER-ELABORATION (max 3)
List content that significantly exceeds reference scope or adds unnecessary detail

5. STRENGTHS (max 3)
List well-executed elements

6. SUMMARY
One sentence overall assessment

=== RETURN JSON ONLY ===
Return ONLY valid JSON in this exact format (no other text):
{{
  "elements": {{
    "element_id": {{"present": true, "quality": 8, "note": "brief note"}}
  }},
  "scores": {{
    "accuracy": 7,
    "completeness": 6,
    "specificity": 8,
    "conciseness": 5,
    "quality": 7
  }},
  "gaps": ["gap 1", "gap 2"],
  "over_elaboration": ["item 1"],
  "strengths": ["strength 1"],
  "summary": "One sentence summary"
}}"""

        return prompt

    def _parse_evaluation_response(self, response_text: str, config: Dict) -> Dict:
        """Parse LLM response into structured evaluation."""

        # Extract JSON from response
        try:
            # Find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"Response was: {response_text[:500]}...")
            return self._create_error_evaluation(config, f"JSON parse error: {e}")

        # Build element scores
        element_scores = []
        required_elements = config["required_elements"]
        elements_data = data.get("elements", {})

        for elem in required_elements:
            elem_id = elem["id"]
            elem_data = elements_data.get(elem_id, {})

            # Also try matching by name if ID not found
            if not elem_data:
                for key, val in elements_data.items():
                    if elem["name"].lower() in key.lower() or key.lower() in elem["name"].lower():
                        elem_data = val
                        break

            element_scores.append(ElementScore(
                element_id=elem_id,
                element_name=elem["name"],
                present=elem_data.get("present", False),
                quality=elem_data.get("quality", 0) if elem_data.get("present") else 0,
                note=elem_data.get("note", ""),
                is_critical=elem.get("critical", False)
            ))

        # Build dimension scores
        scores = data.get("scores", {})
        dimension_scores = DimensionScores(
            accuracy=scores.get("accuracy", 5),
            completeness=scores.get("completeness", 5),
            specificity=scores.get("specificity", 5),
            conciseness=scores.get("conciseness", 5),
            quality=scores.get("quality", 5)
        )

        # Count elements
        total_elements = len(required_elements)
        present_elements = sum(1 for e in element_scores if e.present)
        critical_elements = [e for e in element_scores if e.is_critical]
        critical_present = sum(1 for e in critical_elements if e.present)

        # Identify strengths (high quality elements)
        strengths = data.get("strengths", [])
        if not strengths:
            strengths = [e.element_name for e in element_scores if e.quality >= 8][:3]

        return {
            "element_scores": element_scores,
            "dimension_scores": dimension_scores,
            "critical_met": critical_present == len(critical_elements),
            "elements_present": f"{present_elements}/{total_elements}",
            "critical_present": f"{critical_present}/{len(critical_elements)}",
            "gaps": data.get("gaps", [])[:5],
            "over_elaboration": data.get("over_elaboration", [])[:3],
            "strengths": strengths[:3],
            "summary": data.get("summary", "Evaluation completed")
        }

    def _create_error_evaluation(self, config: Dict, error_msg: str) -> Dict:
        """Create default evaluation when error occurs."""
        element_scores = [
            ElementScore(
                element_id=elem["id"],
                element_name=elem["name"],
                present=False,
                quality=0,
                note="Evaluation error",
                is_critical=elem.get("critical", False)
            )
            for elem in config["required_elements"]
        ]

        return {
            "element_scores": element_scores,
            "dimension_scores": DimensionScores(5, 5, 5, 5, 5),
            "critical_met": False,
            "elements_present": "0/0",
            "critical_present": "0/0",
            "gaps": [f"Evaluation error: {error_msg}"],
            "over_elaboration": [],
            "strengths": [],
            "summary": f"Evaluation failed: {error_msg}"
        }

    def _calculate_section_score(self, evaluation: Dict, config: Dict) -> float:
        """Calculate overall section score from evaluation."""

        # Element-based score
        element_scores = evaluation["element_scores"]
        total_elements = len(element_scores)
        present_elements = sum(1 for e in element_scores if e.present)

        element_completeness = (present_elements / total_elements) * 10 if total_elements > 0 else 0

        present_qualities = [e.quality for e in element_scores if e.present and e.quality > 0]
        element_quality = sum(present_qualities) / len(present_qualities) if present_qualities else 0

        element_score = (element_completeness * 0.6) + (element_quality * 0.4)

        # Dimension-based score
        dim = evaluation["dimension_scores"]
        dimension_score = (
            dim.accuracy * SCORING_DIMENSIONS["accuracy"]["weight"] +
            dim.completeness * SCORING_DIMENSIONS["completeness"]["weight"] +
            dim.specificity * SCORING_DIMENSIONS["specificity"]["weight"] +
            dim.conciseness * SCORING_DIMENSIONS["conciseness"]["weight"] +
            dim.quality * SCORING_DIMENSIONS["quality"]["weight"]
        )

        # Combined score
        section_score = (element_score * 0.5) + (dimension_score * 0.5)

        return round(section_score, 1)

    def _calculate_overall_score(self, section_results: Dict[str, SectionResult]) -> Dict:
        """Calculate weighted overall score from section results."""

        weighted_sum = 0
        total_weight = 0

        for section_id, result in section_results.items():
            weight = self.section_weights.get(section_id, 0.1)
            weighted_sum += result.section_score * weight
            total_weight += weight

        overall_score = weighted_sum / total_weight if total_weight > 0 else 0

        # Sort sections by score
        sorted_sections = sorted(
            section_results.items(),
            key=lambda x: x[1].section_score
        )

        return {
            "overall_score": round(overall_score, 1),
            "weakest_sections": [s[0] for s in sorted_sections[:2]],
            "strongest_sections": [s[0] for s in sorted_sections[-2:]],
            "critical_failures": [
                s[0] for s in sorted_sections
                if not s[1].critical_elements_met
            ]
        }

    def generate_report(self, result: BenchmarkResult) -> str:
        """Generate formatted benchmark report."""

        lines = [
            "=" * 80,
            "SAP BENCHMARK REPORT",
            "=" * 80,
            f"Trial: {result.trial_id}",
            f"Indication: {result.indication}",
            f"Phase: {result.phase}",
            f"Generated: {result.timestamp}",
            "",
            "=" * 80,
            f"OVERALL SCORE: {result.overall_score}/10",
            "=" * 80,
            "",
            "SECTION SCORES:",
            "┌─────────────────────────────────────┬────────┬────────┬────────┬────────┬────────┬─────────┐",
            "│ Section                             │ Accur. │ Compl. │ Specif.│ Conc.  │ Qual.  │ SCORE   │",
            "├─────────────────────────────────────┼────────┼────────┼────────┼────────┼────────┼─────────┤"
        ]

        for section_id, section_result in result.section_results.items():
            dim = section_result.dimension_scores
            name = section_result.section_name[:35].ljust(35)
            lines.append(
                f"│ {name} │ {dim.accuracy:6.1f} │ {dim.completeness:6.1f} │ "
                f"{dim.specificity:6.1f} │ {dim.conciseness:6.1f} │ {dim.quality:6.1f} │ {section_result.section_score:7.1f} │"
            )

        lines.append("└─────────────────────────────────────┴────────┴────────┴────────┴────────┴────────┴─────────┘")
        lines.append("")

        # Critical gaps
        lines.append("=" * 80)
        lines.append("CRITICAL GAPS (Priority Fixes)")
        lines.append("=" * 80)
        for i, gap in enumerate(result.top_gaps[:10], 1):
            lines.append(f"{i}. {gap}")

        # Over-elaboration
        lines.append("")
        lines.append("=" * 80)
        lines.append("OVER-ELABORATION ISSUES")
        lines.append("=" * 80)
        for i, over in enumerate(result.top_over_elaborations[:5], 1):
            lines.append(f"{i}. {over}")

        # Element summary
        lines.append("")
        lines.append("=" * 80)
        lines.append("ELEMENT SUMMARY BY SECTION")
        lines.append("=" * 80)
        for section_id, section_result in result.section_results.items():
            lines.append(
                f"{section_result.section_name}: {section_result.elements_present} elements "
                f"({section_result.critical_present} critical)"
            )

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)


# =============================================================================
# SECTION MAPPING UTILITIES
# =============================================================================

def map_generated_to_benchmark_sections(
    workbench_sections: Dict[str, str]
) -> Dict[str, str]:
    """
    Map workbench section IDs to benchmark section IDs.

    Args:
        workbench_sections: Dict from workbench (e.g., {"2": content, "3": content})

    Returns:
        Dict with benchmark section IDs
    """
    # Mapping from workbench section numbers to benchmark IDs
    SECTION_MAPPING = {
        "1": "1_title_page",
        "2": "2_objectives_endpoints_estimands",
        "3": "3_study_design",
        "4": "4_statistical_analyses",
        "5": "3_study_design",  # Analysis populations -> Study Design
        "6": "2_objectives_endpoints_estimands",  # Endpoints -> Section 2
        "7": "4_statistical_analyses",  # Statistical Methods -> Section 4
        "8": "6_efficacy",  # Censoring -> Efficacy
        "9": "4_statistical_analyses",  # Missing Data -> Section 4
        "10": "6_efficacy",  # Sensitivity -> Efficacy
        "11": "6_efficacy",  # Subgroups -> Efficacy
        "12": "7_safety",  # Safety
        "13": "4_statistical_analyses",  # Interim -> Section 4
        "14": "11_appendices",  # TFL Shells -> Appendices
        "16": "4_statistical_analyses",  # Definitions -> Section 4
        "18": "11_appendices",  # TFL Index -> Appendices
        "A": "11_appendices",  # Appendices
    }

    # Combine sections that map to the same benchmark section
    result = {}
    for wb_id, content in workbench_sections.items():
        bench_id = SECTION_MAPPING.get(wb_id)
        if bench_id:
            if bench_id in result:
                result[bench_id] += "\n\n" + content
            else:
                result[bench_id] = content

    return result


def extract_reference_sections(
    reference_sap_text: str,
    client: anthropic.Anthropic = None
) -> Dict[str, str]:
    """
    Extract benchmark sections from reference SAP text.

    Args:
        reference_sap_text: Full reference SAP text
        client: Optional Anthropic client for LLM-based extraction

    Returns:
        Dict mapping benchmark section IDs to content
    """
    if client is None:
        client = anthropic.Anthropic()

    sections = {}

    # Section extraction keywords
    SECTION_KEYWORDS = {
        "1_title_page": ["title page", "statistical analysis plan", "protocol number"],
        "2_objectives_endpoints_estimands": ["objective", "endpoint", "estimand", "primary objective"],
        "3_study_design": ["study design", "analysis population", "timing of analysis", "hypothesis"],
        "4_statistical_analyses": ["general methodology", "multiplicity", "missing data", "visit window"],
        "6_efficacy": ["efficacy", "primary analysis", "sensitivity analysis", "subgroup"],
        "7_safety": ["safety", "adverse event", "laboratory", "ctcae"],
        "11_appendices": ["appendix", "schedule of assessment", "tfl", "table index"]
    }

    for section_id, keywords in SECTION_KEYWORDS.items():
        prompt = f"""Extract the section about {', '.join(keywords)} from this SAP document.

SAP DOCUMENT:
{reference_sap_text[:50000]}

Return ONLY the relevant section content (2000-6000 characters).
If section not found, return "SECTION_NOT_FOUND".
Do not add any commentary."""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()
            if "SECTION_NOT_FOUND" not in content and len(content) > 100:
                sections[section_id] = content

        except Exception as e:
            print(f"Error extracting {section_id}: {e}")

    return sections


# =============================================================================
# CLI INTERFACE
# =============================================================================

def run_benchmark_cli():
    """Command-line interface for running benchmarks."""
    import argparse

    parser = argparse.ArgumentParser(description="SAP Benchmark System v2.0")
    parser.add_argument("--generated", type=str, help="Path to generated SAP JSON/markdown")
    parser.add_argument("--reference", type=str, help="Path to reference SAP text")
    parser.add_argument("--trial-id", type=str, default="Unknown")
    parser.add_argument("--indication", type=str, default="Unknown")
    parser.add_argument("--phase", type=str, default="Unknown")
    parser.add_argument("--output", type=str, help="Output path for report")
    parser.add_argument("--section", type=str, help="Evaluate single section only")

    args = parser.parse_args()

    # Initialize benchmark
    benchmark = SAPBenchmark()

    trial_info = {
        "trial_id": args.trial_id,
        "indication": args.indication,
        "phase": args.phase
    }

    if args.section:
        # Single section evaluation
        with open(args.generated, 'r') as f:
            generated = f.read()

        reference = ""
        if args.reference:
            with open(args.reference, 'r') as f:
                reference = f.read()

        result = benchmark.evaluate_section(
            section_id=args.section,
            generated_content=generated,
            reference_content=reference,
            trial_info=trial_info
        )

        print(f"\nSection: {result.section_name}")
        print(f"Score: {result.section_score}/10")
        print(f"Elements: {result.elements_present} ({result.critical_present} critical)")
        print(f"Gaps: {', '.join(result.gaps)}")
        print(f"Summary: {result.summary}")

    else:
        # Full SAP evaluation
        print("Full SAP evaluation requires generated sections dict")
        print("Use --section for single section evaluation")


if __name__ == "__main__":
    run_benchmark_cli()
