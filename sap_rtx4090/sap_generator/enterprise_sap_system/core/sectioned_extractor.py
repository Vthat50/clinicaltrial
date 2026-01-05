#!/usr/bin/env python3
"""
Section-by-Section Protocol Extractor
======================================

CRITICAL DESIGN PRINCIPLE:
- Extract by section, not all at once
- Each section has explicit confidence scores
- Fields not found in protocol are flagged [NEEDS REVIEW]
- NO inference from drug class, keywords, or rules

Sections (based on Gamble et al. 2017 JAMA checklist):
1. Administrative (Items 1-6)
2. Study Design (Items 7-15)
3. Endpoints (Items 16-19)
4. Interim Analysis (Items 13a-13c)
5. Statistical Methods (Items 27a-27f)
6. Multiplicity (Item 17)
7. Missing Data (Item 28)
8. Populations (Item 20)
9. Estimand (ICH E9 R1)
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from .extraction_schema import (
    ExtractedProtocolFacts,
    from_claude_extraction,
    ExtractionConfidence
)
from .section_parser import ProtocolSectionParser, ParsedProtocol


@dataclass
class SectionExtractionResult:
    """Result from extracting a single section."""
    section_name: str
    extracted_fields: Dict[str, Any]
    confidence: float  # 0-1
    fields_found: List[str]
    fields_not_found: List[str]
    needs_review: List[str]
    notes: List[str] = field(default_factory=list)


class SectionedProtocolExtractor:
    """
    Extracts protocol facts section-by-section with confidence scoring.

    This replaces the single-pass extraction with a more robust approach:
    1. Each section is extracted separately
    2. Each field has a confidence score
    3. Fields not found are explicitly flagged
    4. No inference from drug class or keywords
    """

    # Cache for section locations (computed once per document)
    # Maps text_hash -> {section_name: position_fraction}
    _section_locations_cache: Dict[str, Dict[str, float]] = {}

    # Section definitions with required and optional fields
    SECTIONS = {
        'study_design': {
            'required': ['treatment_setting', 'disease_type', 'phase', 'drug_name', 'comparator',
                        'is_single_arm', 'is_pilot_study', 'num_arms'],
            'optional': ['histology', 'disease_stage', 'biomarker_status', 'allocation_ratio', 'blinding_type',
                        'hypothesis_testing_planned', 'sample_size_justification_type', 'study_category'],
            'critical': ['treatment_setting', 'disease_type', 'is_single_arm', 'is_pilot_study']
        },
        'stratification': {
            'required': ['stratification_factors'],
            'optional': ['stratification_factor_levels', 'num_strata', 'stratification_method', 'block_size'],
            'critical': ['stratification_factors']
        },
        'sample_size': {
            'required': ['sample_size', 'power'],
            'optional': ['sample_size_per_arm', 'sample_size_rationale', 'hazard_ratio',
                        'sample_size_justification_type', 'is_pragmatic_sample',
                        'sample_size_by_population', 'regional_cohorts', 'allocation_ratio'],
            'critical': ['sample_size']
        },
        'endpoints': {
            'required': ['primary_endpoint'],
            'optional': ['secondary_endpoints', 'is_co_primary', 'co_primary_endpoints', 'assessment_criteria'],
            'critical': ['primary_endpoint']
        },
        'statistical_methods': {
            'required': ['statistical_method'],
            'optional': ['null_hypothesis', 'alternative_hypothesis', 'test_sidedness', 'hazard_ratio_method'],
            'critical': ['statistical_method']
        },
        'interim_analysis': {
            'required': ['has_interim_analysis', 'num_interim_analyses'],
            'optional': ['interim_events', 'final_events', 'information_fractions',
                        'alpha_spending_function', 'alpha_at_interim', 'alpha_at_final',
                        'stopping_boundaries', 'interim_by_endpoint', 'overall_alpha',
                        'alpha_sidedness', 'event_triggers', 'interim_timing_months', 'spending_parameters'],
            'critical': ['num_interim_analyses', 'final_events']
        },
        'multiplicity': {
            'required': ['has_multiplicity'],
            'optional': ['adjustment_method', 'testing_sequence', 'alpha_per_hypothesis', 'hypotheses_list',
                        'alpha_propagation', 'ni_margin', 'ni_endpoint', 'ni_then_superiority',
                        'efficacy_boundaries', 'total_alpha'],
            'critical': ['hypotheses_list', 'alpha_per_hypothesis']
        },
        'missing_data': {
            'required': ['censoring_rules'],
            'optional': ['treatment_discontinuation_strategy', 'tipping_point_analysis',
                        'subsequent_therapy_handling'],
            'critical': []
        },
        'populations': {
            'required': ['itt_definition'],
            'optional': ['fas_definition', 'per_protocol_definition', 'safety_population_definition'],
            'critical': []
        },
        'estimand': {
            'required': [],
            'optional': ['estimand_population', 'estimand_variable', 'intercurrent_events',
                        'primary_estimand'],
            'critical': []  # Per ICH E9 R1 - should be in modern protocols
        },
        'crossover': {
            'required': ['has_crossover'],
            'optional': ['crossover_description', 'crossover_adjustment_methods'],
            'critical': []
        },
        # =========================================================================
        # NEW SECTIONS (2025-01) - Based on comprehensive regulatory sources
        # =========================================================================
        'safety_analysis': {
            'required': ['teae_definition', 'ae_collection_period'],
            'optional': ['ae_coding_dictionary', 'ae_grading_scale', 'sae_definition',
                        'sae_reporting_period', 'aesi_list', 'irae_categories',
                        'dose_reduction_rules', 'dose_discontinuation_rules'],
            'critical': ['teae_definition']  # TEAE definition is critical for safety analysis
        },
        'pharmacokinetics': {
            'required': ['pk_population_definition'],
            'optional': ['pk_parameters', 'pk_sampling_timepoints', 'pk_analysis_method',
                        'population_pk_model', 'pk_software', 'exposure_response_analysis',
                        'pk_covariates'],
            'critical': []
        },
        'biomarkers': {
            'required': [],
            'optional': ['predictive_biomarkers', 'prognostic_biomarkers', 'pdl1_assay',
                        'pdl1_cutoffs', 'pdl1_scoring_method', 'tmb_assay', 'tmb_cutoff',
                        'msi_testing_method', 'mmr_proteins_tested', 'genomic_platform',
                        'ctdna_analysis', 'companion_diagnostic_required', 'companion_diagnostic_name'],
            'critical': ['pdl1_assay', 'pdl1_cutoffs']  # Critical for IO trials
        },
        'laboratory': {
            'required': [],
            'optional': ['hematology_parameters', 'chemistry_parameters', 'urinalysis_parameters',
                        'shift_table_analysis', 'lab_ctcae_grading', 'clinically_notable_criteria',
                        'hys_law_analysis'],
            'critical': []
        },
        'exposure': {
            'required': [],
            'optional': ['exposure_metrics', 'dose_delay_definition', 'dose_reduction_definition',
                        'rdi_calculation_method', 'rdi_categories'],
            'critical': []
        },
        'concomitant_medications': {
            'required': [],
            'optional': ['medication_coding', 'prohibited_medications', 'medications_of_interest',
                        'prior_lines_of_therapy', 'prior_immunotherapy'],
            'critical': []
        },
        'immunogenicity': {
            'required': [],
            'optional': ['ada_testing_performed', 'ada_assay_type', 'ada_sampling_timepoints',
                        'nab_testing_performed', 'nab_assay_type', 'ada_incidence_analysis',
                        'ada_impact_on_efficacy', 'ada_impact_on_safety', 'ada_impact_on_pk'],
            'critical': []  # Critical for biologics
        },
        'conventions': {
            'required': [],
            'optional': ['baseline_definition', 'baseline_window', 'partial_date_imputation_rules',
                        'visit_windows', 'on_treatment_definition', 'post_treatment_definition',
                        'rounding_convention'],
            'critical': ['baseline_definition']
        },
        'protocol_deviations': {
            'required': [],
            'optional': ['important_deviation_categories', 'deviation_impact_on_populations'],
            'critical': []
        },
        'pro': {
            'required': [],
            'optional': ['pro_instruments', 'instrument_scoring_rules', 'pro_primary_endpoint',
                        'pro_secondary_endpoints', 'time_to_deterioration', 'ttd_threshold',
                        'pro_responder_definition', 'pro_missing_data_handling',
                        'pro_compliance_threshold', 'pro_collection_schedule', 'pro_electronic_capture'],
            'critical': []
        },
        'dmc': {
            'required': ['has_dmc'],
            'optional': ['dmc_charter_exists', 'dmc_review_frequency', 'dmc_unblinded',
                        'safety_stopping_rules', 'safety_boundary_type', 'futility_review_planned',
                        'futility_boundary', 'dmc_recommendation_options', 'sponsor_blinded',
                        'independent_statistician'],
            'critical': ['has_dmc']
        },
        'special_designs': {
            'required': [],
            'optional': ['is_master_protocol', 'master_protocol_type', 'is_basket_trial',
                        'basket_tumor_types', 'basket_shared_biomarker', 'is_umbrella_trial',
                        'umbrella_biomarker_arms', 'is_platform_trial', 'shared_control_arm',
                        'is_adaptive', 'adaptive_features', 'adaptation_timing', 'adaptation_rules',
                        'is_seamless', 'seamless_phases', 'phase2_to_phase3_criteria'],
            'critical': []
        },
        'tumor_assessment': {
            'required': ['response_criteria'],
            'optional': ['response_criteria_version', 'assessment_schedule', 'baseline_imaging_window',
                        'target_lesion_selection', 'max_target_lesions', 'min_lesion_size',
                        'assessment_method', 'bicr_primary', 'discrepancy_resolution',
                        'confirmation_required', 'confirmation_window', 'pseudoprogression_handling',
                        'new_lesion_confirmation', 'progression_date_definition'],
            'critical': ['response_criteria', 'assessment_method']
        },
        # =========================================================================
        # NEW SECTIONS (2025-01) - Bridging, Structured Analyses, Regulatory
        # =========================================================================
        'bridging_study': {
            'required': [],
            'optional': ['is_bridging_study', 'is_mrct', 'bridging_region', 'reference_studies',
                        'consistency_testing_required', 'consistency_hr_threshold_interim',
                        'consistency_hr_threshold_final', 'hierarchical_testing_steps',
                        'ethnic_sensitivity_assessment', 'intrinsic_factors', 'extrinsic_factors'],
            'critical': ['is_bridging_study', 'consistency_hr_threshold_interim']  # Critical for bridging
        },
        'filing_endpoints': {
            'required': [],
            'optional': ['has_early_filing_endpoint', 'filing_endpoint_name', 'filing_endpoint_definition',
                        'filing_regulatory_authority', 'filing_target_subjects', 'filing_minimum_followup_months',
                        'filing_statistical_test', 'filing_alpha', 'filing_alpha_penalty', 'filing_hypothesis'],
            'critical': ['filing_endpoint_name', 'filing_target_subjects']  # Critical for early filing
        },
        'secondary_analyses': {
            'required': [],
            'optional': ['endpoint_testing_hierarchy', 'orr_analysis', 'pfs_analysis', 'dor_analysis',
                        'ttr_analysis', 'dcr_analysis'],
            'critical': ['endpoint_testing_hierarchy']
        },
        'subgroup_specs': {
            'required': [],
            'optional': ['forest_plot_planned', 'forest_plot_variables', 'forest_plot_method',
                        'multivariate_cox_planned', 'multivariate_cox_covariates', 'covariate_selection_method',
                        'landmark_analysis_planned', 'landmark_timepoints', 'landmark_method',
                        'waterfall_plot_planned', 'swimmer_plot_planned', 'spider_plot_planned'],
            'critical': ['forest_plot_variables']
        },
        'baseline_chars': {
            'required': [],
            'optional': ['baseline_demographic_variables', 'baseline_regional_variables',
                        'baseline_disease_variables', 'baseline_molecular_variables',
                        'baseline_prior_therapy_variables', 'baseline_performance_status_variables',
                        'continuous_summary_stats', 'categorical_summary_stats'],
            'critical': ['baseline_demographic_variables', 'baseline_disease_variables']
        },
        'date_imputation': {
            'required': [],
            'optional': ['death_date_imputation', 'progression_date_imputation', 'ae_start_date_imputation',
                        'ae_end_date_imputation', 'treatment_start_imputation', 'duration_calculation_formula',
                        'days_per_month', 'days_per_year'],
            'critical': ['death_date_imputation', 'duration_calculation_formula']
        },
        'exposure_formulas': {
            'required': [],
            'optional': ['rdi_formula_experimental', 'rdi_formula_control', 'planned_dose_experimental',
                        'planned_dose_control', 'dose_delay_threshold_days', 'dose_reduction_levels',
                        'rdi_categories', 'cycle_length_experimental_days', 'cycle_length_control_days'],
            'critical': ['rdi_formula_experimental', 'planned_dose_experimental']
        },
        'study_conduct': {
            'required': [],
            'optional': ['deviation_categories', 'programmable_deviations', 'non_programmable_deviations',
                        'accrual_summary_by', 'stratification_discrepancy_analysis',
                        'as_randomized_vs_as_treated', 'drug_accountability_analysis', 'consent_tracking'],
            'critical': ['deviation_categories']
        },
        'cdisc_versioning': {
            'required': [],
            'optional': ['sdtm_ig_version', 'adam_ig_version', 'define_xml_version', 'ct_version',
                        'ct_freeze_date', 'ct_freeze_milestone', 'ct_packages_used', 'recoding_milestone',
                        'submission_type', 'regulatory_authority', 'electronic_submission_format'],
            'critical': ['sdtm_ig_version', 'adam_ig_version', 'ct_version']
        },
        'coding_standards': {
            'required': [],
            'optional': ['meddra_version', 'meddra_freeze_date', 'meddra_freeze_milestone',
                        'ae_coding_level', 'whodrug_version', 'whodrug_format', 'whodrug_freeze_date',
                        'atc_classification_level', 'recoding_triggers', 'dual_coding_required'],
            'critical': ['meddra_version', 'whodrug_version']
        },
        'control_rationale': {
            'required': [],
            'optional': ['control_type', 'control_justification', 'active_control_drug', 'active_control_dose',
                        'active_control_rationale', 'historical_effect_estimate', 'ni_margin_justification',
                        'ni_margin_preserves', 'historical_trials_referenced', 'rescue_medication_permitted'],
            'critical': ['control_type', 'active_control_rationale']
        },
        'genomic_sampling': {
            'required': [],
            'optional': ['sample_types_collected', 'genomic_collection_timepoints', 'sample_mandatory_vs_optional',
                        'sample_processing_requirements', 'genomic_consent_type', 'prespecified_genomic_analyses',
                        'exploratory_genomic_analyses', 'ngs_platform', 'gene_panel', 'ctdna_assay',
                        'genomic_data_format', 'bioinformatics_pipeline'],
            'critical': ['sample_types_collected', 'prespecified_genomic_analyses']
        }
    }

    # Section-specific prompts
    SECTION_PROMPTS = {
        'study_design': '''Extract STUDY DESIGN information from this protocol section.

CRITICAL: Extract EXACTLY what the protocol says. DO NOT infer from drug name or therapeutic area.

=== CRITICAL: DETECT STUDY TYPE (use contextual understanding) ===

is_single_arm: Is there only ONE treatment group with NO comparator/control arm?
  - TRUE if: only one treatment described, no randomization between groups, no control arm
  - FALSE if: patients are randomized between treatment vs control/comparator
  - Look at the STUDY DESIGN section, not just keywords

is_pilot_study: Is this an exploratory/feasibility study rather than confirmatory?
  - TRUE if: primary goal is safety/feasibility assessment, small sample without power calculation,
    explicitly called pilot/feasibility, or "no formal hypothesis testing"
  - FALSE if: designed to test a hypothesis with statistical power, Phase 3, registration-enabling
  - Consider the OBJECTIVES and SAMPLE SIZE JUSTIFICATION

num_arms: How many distinct treatment groups are patients assigned to?
  - Count: 1 for single-arm, 2 for two-arm randomized, 3+ for multi-arm

hypothesis_testing_planned: Will formal statistical hypothesis tests be performed?
  - FALSE if: "descriptive statistics only", "no statistical tests", exploratory endpoints only
  - TRUE if: p-values, type I error control, power calculations mentioned

study_category: Classify the study type for downstream analysis:
  - "confirmatory_superiority": Phase 3, hypothesis testing, superiority claim
  - "confirmatory_non_inferiority": Phase 3, NI design, registration-enabling
  - "exploratory_single_arm": Phase 2, single-arm, often ORR primary
  - "exploratory_randomized": Phase 2, randomized but not registration-enabling
  - "dose_finding": Phase 1/1b, MTD/RP2D identification
  - "basket_trial": Multiple tumor types, shared biomarker
  - "umbrella_trial": One tumor type, multiple biomarker arms
  - "platform_trial": Shared control, arms added/dropped adaptively
  - "adaptive_design": Pre-planned adaptations (sample size, enrichment)

Required fields (must find or mark [NOT FOUND]):
- treatment_setting: EXACTLY one of: "first-line", "second-line", "third-line or later",
  "neoadjuvant", "adjuvant", "maintenance".

  CRITICAL - Check the PROTOCOL TITLE first! It often contains the treatment line:
  - "First-Line Treatment" or "1L" = first-line
  - "Second-Line" or "2L" or "Previously Treated" = second-line

  Also look for these phrases:
  FIRST-LINE indicators (any of these = first-line):
  - "first-line treatment" / "1st line" / "1L"
  - "previously untreated" / "treatment-naive" / "treatment-naïve"
  - "no prior systemic therapy" / "have not received prior"
  - "front-line" / "initial treatment"

  SECOND-LINE indicators (any of these = second-line):
  - "second-line" / "2nd line" / "2L"
  - "after failure of" / "following progression"
  - "previously treated" / "prior therapy required"
  - "relapsed" / "refractory"
- disease_type: The specific disease, e.g., "Non-small cell lung cancer (NSCLC)",
  "HER2-positive breast cancer", "Advanced melanoma". Be specific, not generic.
- phase: "Phase 1", "Phase 2", "Phase 3", etc.
- drug_name: The experimental drug name
- comparator: The control arm treatment (use "None - single arm" if single-arm study)

Optional fields:
- histology: e.g., "Squamous", "Non-squamous", "Adenocarcinoma"
- disease_stage: e.g., "Stage IIIB-IV", "Locally advanced or metastatic"
- biomarker_status: e.g., "PD-L1 ≥50%", "EGFR mutation negative"
- allocation_ratio: e.g., "1:1", "2:1" (null if single-arm)
- blinding_type: e.g., "Open-label", "Double-blind"

RESPOND IN JSON:
{{
    "is_single_arm": <true/false>,
    "is_pilot_study": <true/false>,
    "num_arms": <number>,
    "hypothesis_testing_planned": <true/false>,
    "study_category": "<category from list above>",
    "treatment_setting": "<exact setting or [NOT FOUND]>",
    "disease_type": "<specific disease or [NOT FOUND]>",
    "phase": "<phase>",
    "drug_name": "<drug>",
    "comparator": "<comparator or 'None - single arm'>",
    "histology": "<histology or null>",
    "disease_stage": "<stage or null>",
    "biomarker_status": "<status or null>",
    "allocation_ratio": "<ratio or null>",
    "blinding_type": "<blinding>",
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'stratification': '''Extract STRATIFICATION information from this protocol section.

SEARCH AGGRESSIVELY for these patterns:
- "stratified by" or "stratification factors" or "stratification variables"
- "randomization stratified" or "stratified randomization"
- Look for lists after "stratified by:" such as:
  - Geographic region (e.g., "East Asia vs Rest of World")
  - Performance status (e.g., "ECOG 0 vs 1")
  - PD-L1 status (e.g., "<1% vs ≥1%", "TPS <50% vs ≥50%")
  - Histology (e.g., "squamous vs non-squamous")
  - Prior therapy (e.g., "yes vs no")
  - Sex (e.g., "male vs female")
  - Smoking status (e.g., "never vs ever")
  - Disease stage, metastases, brain metastases

=== CRITICAL: COUNT TOTAL STRATA ===
Total strata = product of all factor levels.
Example: 3 factors with 2, 2, 3 levels = 2 × 2 × 3 = 12 strata
Look for phrases like "9 strata", "12 stratification cells", "randomization strata"

=== EXTRACT FACTOR COMBINATIONS ===
Some protocols explicitly list stratification combinations in tables:
| Stratum | Region | ECOG | Prior Chemo |
|---------|--------|------|-------------|
| 1 | East Asia | 0 | Yes |
| 2 | East Asia | 0 | No |
...

Required fields:
- stratification_factors: List ALL factors mentioned, even if in different parts of protocol
- num_strata: Total number of stratification cells (product of levels)

Critical field (MUST extract with full detail):
- stratification_factor_levels: For EACH factor, extract EXACT levels/categories
  Example: {{"Region": ["East Asia", "Rest of World"], "ECOG PS": ["0", "1"], "PD-L1": ["<1%", "1-49%", "≥50%"]}}

Optional fields:
- stratification_method: "IVRS", "IWRS", "block randomization", "dynamic allocation"
- block_size: If mentioned (e.g., "block size 4" or "variable block sizes")

RESPOND IN JSON:
{{
    "stratification_factors": ["<factor1>", "<factor2>", "<factor3>", ...],
    "stratification_factor_levels": {{"<factor>": ["<level1>", "<level2>"], ...}},
    "num_strata": <total number of strata combinations>,
    "stratification_method": "<method>" or null,
    "block_size": "<size or 'variable'>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'sample_size': '''Extract SAMPLE SIZE information from this protocol section.

SEARCH AGGRESSIVELY for these patterns:
- "N = ###" or "n = ###" or "### patients" or "### subjects" or "### participants"
- "sample size of ###" or "enroll ###" or "randomize ###" or "total of ###"
- "approximately ###" or "~###" or "about ###" patients
- "### per arm" or "### in each arm" or "1:1" (implies equal arms)
- "power of ##%" or "##% power" or "power = 0.##"
- "HR of 0.##" or "hazard ratio 0.##" or "HR = 0.##"
- Look for tables with sample size calculations

=== CRITICAL: NEVER RETURN 0 FOR SAMPLE SIZE ===
If you cannot find a sample size, return null, NOT 0.
A sample size of 0 is NEVER valid for a clinical trial.

=== LOOK FOR SAMPLE SIZE BY POPULATION ===
Some trials have different sample sizes for subgroups. COMMON PATTERNS:
- Biomarker-defined: "XXX PD-L1 positive" + "YYY PD-L1 negative" = total
- Molecular subtype: "XXX biomarker-positive" + "YYY biomarker-negative" = total
- Cohorts: "XXX in Cohort A" + "YYY in Cohort B" = total
- Histology: "XXX squamous" + "YYY non-squamous" = total
- Add up subgroup sizes if total is not explicitly stated

=== OPTIONAL: REGIONAL EXTENSION COHORTS ===
Some global trials have regional extensions with SEPARATE enrollment. Look for ANY of:
- "[Country] extension" / "[Country] cohort" / "[Region] sub-study"
- "after global enrollment" / "following primary enrollment"
- "regional filing" / "local regulatory" / "NMPA/PMDA submission"
- "consistency evaluation" / "treatment effect preservation"

If regional extensions exist, extract them. If NOT present, return null.
Regional cohorts may NOT be included in the main sample size.

=== DETECT SAMPLE SIZE JUSTIFICATION TYPE ===
Different study designs have different justification approaches:

1. POWER CALCULATION (Phase 3, confirmatory):
   - "90% power" / "80% power" / "power of XX%"
   - "detect HR of 0.XX" / "detect difference of XX"
   - "type I error" / "alpha = 0.025"

2. PHASE 2 DESIGNS (single-arm, exploratory):
   - "Simon two-stage" / "Simon's optimal" / "minimax design"
   - "Fleming single-stage" / "Fleming-A'Hern"
   - "null hypothesis: response rate ≤ XX%"
   - "acceptable response rate XX%" / "unacceptable response rate XX%"

3. BAYESIAN APPROACHES:
   - "posterior probability" / "Bayesian design"
   - "credible interval" / "predictive probability"

4. PRECISION-BASED:
   - "confidence interval width" / "precision of estimate"
   - "standard error" / "half-width"

5. PRAGMATIC/FEASIBILITY:
   - "pragmatic" / "feasibility" / "no formal calculation"
   - "expected enrollment" / "practical considerations"
   - N ≤ 50 without formal justification

6. DOSE-FINDING (Phase 1):
   - "3+3 design" / "rolling six" / "CRM" / "BOIN"
   - "MTD" / "RP2D" / "DLT"

Set is_pragmatic_sample=true if NO formal calculation exists.

Required fields:
- sample_size: Total number of patients (MUST be > 0 or null)
  - Add up subgroup sizes if needed
  - Look for "approximately" or "~" numbers
  - NEVER return 0 - use null if truly not found
- power: Statistical power as decimal 0.0-1.0 (convert 80% to 0.80, 90% to 0.90). NULL if not applicable.

Optional fields:
- sample_size_per_arm: Number per treatment arm [arm1_n, arm2_n]
- sample_size_by_population: Breakdown by biomarker/subgroup
  Example: {{"biomarker_positive": 500, "biomarker_negative": 200, "total": 700}}
- regional_cohorts: Regional extension cohorts if any (null if none)
  Example: {{"<region>_extension": <n>}} or null
- sample_size_rationale: Text describing the calculation basis
- sample_size_justification_type: One of: "power_calculation", "simon_two_stage", "fleming_single_stage",
  "bayesian", "precision", "pragmatic", "feasibility", "dose_finding", "binomial"
- hazard_ratio: Expected/assumed hazard ratio (usually 0.6-0.8 for oncology)
- allocation_ratio: Randomization ratio like "1:1" or "2:1" (null if single-arm)
- is_pragmatic_sample: true if not based on formal calculation

RESPOND IN JSON:
{{
    "sample_size": <number > 0 or null - NEVER 0>,
    "power": <0.0-1.0 or null>,
    "sample_size_per_arm": [<arm1_n>, <arm2_n>] or null,
    "sample_size_by_population": {{"<pop1>": <n1>, "<pop2>": <n2>}} or null,
    "regional_cohorts": {{"<region>": <n>}} or null,
    "sample_size_rationale": "<text>" or null,
    "sample_size_justification_type": "<type>" or null,
    "is_pragmatic_sample": <true/false>,
    "hazard_ratio": <number> or null,
    "allocation_ratio": "<ratio>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'endpoints': '''Extract ENDPOINT information from this protocol section.

SEMANTIC SEARCH - Look for these CONCEPTS:
- "primary endpoint" / "primary outcome" / "primary efficacy" / "primary objective"
- "PFS" / "progression-free survival" / "time to progression"
- "OS" / "overall survival" / "time to death"
- "ORR" / "objective response rate" / "tumor response" / "response rate"
- "DOR" / "duration of response" / "DoR"
- "DCR" / "disease control rate"
- "TTR" / "time to response"
- "secondary endpoint" / "secondary outcome" / "key secondary"
- "co-primary" / "dual primary" / "two primary endpoints"
- "RECIST" / "irRECIST" / "iRECIST" / "mRECIST" / "BICR" / "blinded independent"
- "defined as" / "measured as" / "time from randomization"

Required fields:
- primary_endpoint: The PRIMARY endpoint with its FULL definition
  Example: "Progression-free survival (PFS), defined as time from randomization to first documented disease progression per RECIST 1.1 or death"

Optional fields:
- secondary_endpoints: List ALL secondary endpoints mentioned
- is_co_primary: true if there are CO-PRIMARY endpoints (both must succeed)
- co_primary_endpoints: List the co-primary endpoints if is_co_primary is true
- assessment_criteria: Response assessment criteria

RESPOND IN JSON:
{{
    "primary_endpoint": "<endpoint name AND full definition>",
    "secondary_endpoints": ["<endpoint1 with definition>", "<endpoint2>", ...],
    "is_co_primary": <true/false>,
    "co_primary_endpoints": ["<co-primary1>", "<co-primary2>"] or [],
    "assessment_criteria": "<criteria>",
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'statistical_methods': '''Extract STATISTICAL METHODS information from this protocol section.

SEMANTIC SEARCH - Look for these CONCEPTS:
- "log-rank" / "logrank" / "log rank" / "Mantel-Cox"
- "stratified log-rank" / "stratified analysis" / "adjusted for stratification"
- "Fleming-Harrington" / "weighted log-rank" / "G(rho,gamma)" / "ρ=" / "γ="
- "Cox" / "proportional hazards" / "Cox regression" / "hazard ratio"
- "Kaplan-Meier" / "survival curves" / "survival analysis"
- "one-sided" / "two-sided" / "α=0.025" / "α=0.05"
- "null hypothesis" / "H0:" / "alternative hypothesis" / "H1:" / "Ha:"
- "superiority" / "non-inferiority" / "equivalence"
- "Fisher exact" / "chi-square" / "χ²" / "Cochran-Mantel-Haenszel" / "CMH"
- "confidence interval" / "CI" / "95% CI" / "hazard ratio with 95% CI"

CRITICAL: Extract the EXACT method specified. DO NOT infer based on drug class.

Required field:
- statistical_method: The primary statistical test with full specification
  Example: "Stratified log-rank test, stratified by ECOG PS and region"
  Example: "Fleming-Harrington weighted log-rank test with ρ=0, γ=1"

Optional fields:
- null_hypothesis: e.g., "HR = 1.0" or "HR ≥ 1.0"
- alternative_hypothesis: e.g., "HR < 1.0" or "HR ≠ 1.0"
- test_sidedness: "one-sided" or "two-sided"
- hazard_ratio_method: How HR is estimated (e.g., "unstratified Cox model")

If the statistical method is NOT explicitly stated, return:
"statistical_method": "[STATISTICAL METHOD NOT FOUND IN PROTOCOL - NEEDS REVIEW]"

RESPOND IN JSON:
{{
    "statistical_method": "<exact method from protocol or [STATISTICAL METHOD NOT FOUND IN PROTOCOL - NEEDS REVIEW]>",
    "null_hypothesis": "<H0>" or null,
    "alternative_hypothesis": "<H1>" or null,
    "test_sidedness": "<sidedness>",
    "hazard_ratio_method": "<HR estimation method>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'interim_analysis': '''Extract INTERIM ANALYSIS information from this protocol section.

SEMANTIC SEARCH - Look for these CONCEPTS (not just exact phrases):
- "interim analysis" / "interim look" / "planned looks" / "group sequential"
- "### events" / "### deaths" / "### PFS events" / "### OS events" / "target events"
- "information fraction" / "information time" / "% of events" / "% information"
- "alpha spending" / "spending function" / "O'Brien-Fleming" / "Lan-DeMets" / "Pocock"
- "stopping boundary" / "efficacy boundary" / "futility boundary" / "early stopping"
- "one-sided alpha" / "two-sided alpha" / "α=" / "alpha="
- "first interim at ###" / "second interim at ###" / "final at ###"

=== CRITICAL: COUNT INTERIM ANALYSES CAREFULLY ===
Look for tables or lists that show MULTIPLE interim analyses. Common patterns:
- "IA1", "IA2", "IA3", "FA" (= 3 interim analyses + final)
- "Interim 1", "Interim 2", "Interim 3", "Final" (= 3 interims)
- "First interim", "Second interim", "Third interim" (= 3 interims)
- Tables with columns for each analysis timepoint

EXAMPLE TABLE FORMAT (markdown):
| Analysis | Timing | PFS Events | OS Events | Alpha |
|----------|--------|------------|-----------|-------|
| IA1      | 27 mo  | 354        | -         | 0.001 |
| IA2      | 36 mo  | 472        | -         | 0.005 |
| IA3      | 42 mo  | -          | 316       | 0.01  |
| FA       | 48 mo  | -          | 359       | 0.009 |

This table shows 3 interim analyses (IA1, IA2, IA3) plus final (FA).
Count each IA row as one interim analysis. FA is the final, not an interim.

=== CRITICAL: EXTRACT EVENT-DRIVEN TIMING ===
Interim analyses are often triggered by EVENT COUNTS, not calendar time:
- "~354 PFS events" or "approximately 354 progression events"
- "~269 OS events" or "when 269 deaths have occurred"
- "whichever occurs first" (time OR events)
- "at 50% information" / "at 70% of target events"

Look for CONDITIONAL triggers:
- "IA1 at ~354 PFS events OR 27 months, whichever occurs first"
- "when approximately 50% of final OS events have occurred"

=== ALPHA SPENDING FUNCTION DETAILS ===
Extract the EXACT spending function with parameters:
- "Lan-DeMets O'Brien-Fleming" (most common)
- "Lan-DeMets Pocock"
- "O'Brien-Fleming" (discrete boundaries)
- "Hwang-Shih-DeCani" with gamma parameter
- "Kim-DeMets" with rho parameter

Also extract:
- Overall alpha (e.g., 0.025 one-sided)
- Whether alpha is split between endpoints

Required fields:
- has_interim_analysis: true if ANY interim analysis is mentioned
- num_interim_analyses: Count DISTINCT interim looks (NOT including final analysis)
  - If you see IA1, IA2, IA3, FA → num_interim_analyses = 3
  - If you see IA1, FA → num_interim_analyses = 1
  - If you see "two interim analyses and a final" → num_interim_analyses = 2

CRITICAL fields - extract ALL numbers you find:
- interim_events: Events at each interim [e.g., [354, 472, 316] for 3 interims]
- final_events: Events at final analysis [e.g., 359]
- information_fractions: [e.g., [0.35, 0.70, 0.88, 1.0] for 3 interims + final]
- alpha_spending_function: The spending function name (e.g., "Lan-DeMets O'Brien-Fleming")
- alpha_at_interim: Alpha spent at each interim [e.g., [0.001, 0.005, 0.01]]
- alpha_at_final: Remaining alpha [e.g., 0.009]
- stopping_boundaries: HR thresholds or Z-values for stopping
- interim_timing_months: Timing in months [e.g., [27, 36, 42] for 3 interims]
- interim_by_endpoint: SEPARATE structure per endpoint (PFS vs OS often differ!)

RESPOND IN JSON:
{{
    "has_interim_analysis": <true/false>,
    "num_interim_analyses": <number - COUNT CAREFULLY>,
    "interim_events": [<events1>, <events2>, <events3>] or null,
    "final_events": <number> or null,
    "information_fractions": [<frac1>, <frac2>, ..., 1.0] or null,
    "alpha_spending_function": "<exact function name with parameters>" or null,
    "overall_alpha": <e.g., 0.025>,
    "alpha_sidedness": "one-sided" or "two-sided",
    "alpha_at_interim": [<alpha1>, <alpha2>, ...] or null,
    "alpha_at_final": <number> or null,
    "stopping_boundaries": "<description>" or null,
    "interim_timing_months": [<months1>, <months2>, ...] or null,
    "event_triggers": [
        {{"analysis": "IA1", "pfs_events": <n>, "os_events": <n>, "condition": "<e.g., whichever first>"}},
        {{"analysis": "IA2", "pfs_events": <n>, "os_events": <n>, "condition": "<>"}},
        {{"analysis": "FA", "pfs_events": <n>, "os_events": <n>}}
    ] or null,
    "interim_by_endpoint": [
        {{"endpoint": "PFS", "timing": "<when>", "events": <n>, "alpha": <a>}},
        {{"endpoint": "OS", "timing": "<when>", "events": <n>, "alpha": <a>}}
    ] or [],
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'multiplicity': '''Extract MULTIPLICITY information from this protocol section.

=== FIRST: DOES THIS PROTOCOL HAVE MULTIPLICITY? ===

NOT all trials have multiplicity. Set has_multiplicity=false if:
- Single primary endpoint with NO key secondaries under alpha control
- Phase 2 single-arm with "descriptive statistics only"
- "No formal hypothesis testing planned"
- Exploratory/pilot study with no p-value thresholds
- No mention of alpha adjustment, FWER, or multiple testing

Set has_multiplicity=true if ANY of these apply:
- Multiple primary endpoints (co-primary)
- Key secondary endpoints tested with alpha control
- Graphical/hierarchical/gatekeeping approach mentioned
- Non-inferiority + superiority sequential testing
- Explicit alpha allocation across hypotheses

If has_multiplicity=false, return minimal response with empty arrays.

=== IF MULTIPLICITY EXISTS, SEARCH FOR: ===

SEMANTIC SEARCH - Look for these CONCEPTS:
- "multiplicity" / "multiple testing" / "multiple endpoints" / "multiple hypotheses"
- "H1" / "H2" / "H3" / "H4" / "H5" / "hypothesis 1" / "hypothesis 2"
- "hierarchical testing" / "gatekeeping" / "fixed sequence" / "sequential testing"
- "graphical approach" / "Maurer-Bretz" / "Maurer and Bretz" / "weighted Bonferroni"
- "Hochberg" / "Holm" / "Bonferroni" / "Simes"
- "alpha allocation" / "α=" / "one-sided 0.0###" / "two-sided 0.0###"
- "type I error" / "FWER" / "familywise error rate"
- "primary hypothesis" / "secondary hypothesis" / "key secondary"
- "tested at α=" / "tested at alpha" / "significance level"
- "non-inferiority margin" / "NI margin" / "superiority" / "non-inferiority"
- Diagrams or tables showing hypothesis structure

=== CRITICAL: EXTRACT FULL HYPOTHESIS STRUCTURE ===

Protocols may have 2-6+ hypotheses. Common structures include:

EXAMPLE 1 - Two endpoints, two populations (4 hypotheses):
| Hypothesis | Description | Initial Alpha |
|------------|-------------|---------------|
| H1 | PFS in biomarker-positive | 0.01 |
| H2 | PFS in all-comers | 0 |
| H3 | OS in biomarker-positive | 0.015 |
| H4 | OS in all-comers | 0 |

EXAMPLE 2 - Hierarchical with key secondary (3 hypotheses):
| Hypothesis | Description | Alpha |
|------------|-------------|-------|
| H1 | OS superiority | 0.025 |
| H2 | PFS superiority | 0 (from H1) |
| H3 | ORR superiority | 0 (from H2) |

EXAMPLE 3 - Non-inferiority then superiority (2 hypotheses):
| Hypothesis | Description | Alpha |
|------------|-------------|-------|
| H1 | OS non-inferiority (margin=1.1) | 0.025 |
| H2 | OS superiority | 0 (from H1) |

For graphical approaches, also look for:
- "alpha propagation" or "alpha recycling" or "transition weights"
- "if H1 is rejected, alpha flows to H2" style descriptions
- Diagrams showing arrows between hypotheses with weights

=== CRITICAL: NON-INFERIORITY PARAMETERS ===
If ANY non-inferiority testing is mentioned, extract:
- ni_margin: The HR threshold (e.g., 1.1, 1.2, 1.3)
- ni_endpoint: Which endpoint (usually OS)
- ni_justification: Why this margin was chosen
- ni_then_superiority: true if NI → superiority sequential testing

Common NI margin patterns:
- "upper bound of the 95% CI for HR < 1.1"
- "non-inferiority margin of 1.1"
- "HR ≤ 1.1 establishes non-inferiority"

=== EFFICACY BOUNDARY TABLES ===
Look for tables with stopping boundaries at each analysis:
| Analysis | Information | Z-score | p-value | HR Boundary |
|----------|-------------|---------|---------|-------------|
| IA1      | 35%         | 3.71    | 0.0001  | 0.52        |
| IA2      | 70%         | 2.51    | 0.006   | 0.73        |
| FA       | 100%        | 1.99    | 0.023   | 0.82        |

Extract ALL boundary values if available.

Required field:
- has_multiplicity: true if ANY alpha adjustment or multiple hypothesis testing is mentioned

CRITICAL fields - extract the FULL hypothesis structure:
- hypotheses_list: List EACH hypothesis with full definition
  Example (biomarker-defined): [
    "H1: PFS superiority in biomarker-positive population",
    "H2: PFS superiority in ITT population",
    "H3: OS superiority in biomarker-positive population",
    "H4: OS superiority in ITT population"
  ]
  Example (with non-inferiority): [
    "H1: OS non-inferiority (margin=1.1)",
    "H2: OS superiority"
  ]
- alpha_per_hypothesis: Alpha for EACH hypothesis (can be 0 for initially untested)
  Example: {{"H1": 0.01, "H2": 0, "H3": 0.015, "H4": 0}}
- adjustment_method: The specific method (e.g., "Graphical approach of Maurer and Bretz")
- testing_sequence: Order of testing
- alpha_propagation: How alpha flows between hypotheses when rejected
  Example: "If H1 rejected, alpha flows to H2; if H3 rejected, alpha flows to H4"
- ni_margin: Non-inferiority margin if any (e.g., 1.1 for OS HR)
- ni_endpoint: Which endpoint has NI testing (e.g., "OS")
- ni_then_superiority: true if sequential NI → superiority testing
- total_alpha: Overall type I error (e.g., 0.025 one-sided)

RESPOND IN JSON:
{{
    "has_multiplicity": <true/false>,
    "adjustment_method": "<method>" or null,
    "hypotheses_list": ["H1: <full definition>", "H2: <full definition>", ...] or [],
    "testing_sequence": ["H1", "H2", ...] or [],
    "alpha_per_hypothesis": {{"H1": <alpha>, "H2": <alpha>, ...}} or {{}},
    "alpha_propagation": "<detailed description of how alpha flows>" or null,
    "ni_margin": <number> or null,
    "ni_endpoint": "<endpoint>" or null,
    "ni_then_superiority": <true/false>,
    "efficacy_boundaries": [
        {{"analysis": "IA1", "information_fraction": <0.XX>, "z_score": <X.XX>, "p_value": <0.XXX>, "hr_boundary": <0.XX>}},
        {{"analysis": "FA", "information_fraction": 1.0, "z_score": <X.XX>, "p_value": <0.XXX>, "hr_boundary": <0.XX>}}
    ] or null,
    "total_alpha": <number> or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'missing_data': '''Extract MISSING DATA and CENSORING information from this protocol section.

=== CRITICAL: LOOK FOR CENSORING RULES TABLES ===

Censoring rules are often in tables like this (markdown format):
| Situation | PFS Censoring Rule | OS Censoring Rule |
|-----------|-------------------|-------------------|
| No progression, alive | Last adequate tumor assessment | Censored at last known alive |
| Started new anticancer therapy | Date of new therapy start | Not censored |
| Missed ≥2 tumor assessments | Last adequate assessment before miss | Not censored |
| Lost to follow-up | Last adequate assessment | Last known alive date |

Or as numbered lists:
1. Subjects without documented progression will be censored at last adequate tumor assessment
2. Subjects who start new anticancer therapy will be censored at date of new therapy
3. Subjects lost to follow-up will be censored at last contact date

EXTRACT EACH CENSORING SCENARIO with its rule.

Fields to extract:
- censoring_rules: List EACH censoring scenario and how it's handled
  Example: [
    "No progression, alive: Censored at last adequate tumor assessment",
    "Started new anticancer therapy before progression: Censored at date of new therapy",
    "Missed 2+ consecutive assessments: Censored at last adequate assessment",
    "Lost to follow-up: Censored at last known alive date",
    "Death: Event for OS, censored at death date for PFS"
  ]
- treatment_discontinuation_strategy: How treatment discontinuation is handled
- tipping_point_analysis: true/false
- subsequent_therapy_handling: How subsequent therapies affect censoring
- missing_assessment_handling: What happens when tumor assessments are missed

RESPOND IN JSON:
{{
    "censoring_rules": ["<scenario1>: <rule1>", "<scenario2>: <rule2>", ...],
    "treatment_discontinuation_strategy": "<strategy>" or null,
    "tipping_point_analysis": <true/false>,
    "subsequent_therapy_handling": "<handling>" or null,
    "missing_assessment_handling": "<handling>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'populations': '''Extract ANALYSIS POPULATIONS from this protocol section.

Fields:
- itt_definition: Intent-to-treat population definition
- fas_definition: Full Analysis Set definition (often same as ITT)
- per_protocol_definition: Per-protocol population definition
- safety_population_definition: Safety population definition

RESPOND IN JSON:
{{
    "itt_definition": "<definition>",
    "fas_definition": "<definition>" or null,
    "per_protocol_definition": "<definition>" or null,
    "safety_population_definition": "<definition>",
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'estimand': '''Extract ESTIMAND information from this protocol section (ICH E9 R1).

The estimand framework has 5 attributes:
1. Population: Target patient population
2. Variable: Endpoint being measured
3. Intercurrent events: Events occurring post-randomization that affect interpretation
4. Strategy: How each intercurrent event is handled
5. Population-level summary: Statistical measure (e.g., hazard ratio)

RESPOND IN JSON:
{{
    "estimand_population": "<population description>" or null,
    "estimand_variable": "<endpoint>" or null,
    "intercurrent_events": [
        {{"event": "<event1>", "strategy": "<strategy1>"}},
        {{"event": "<event2>", "strategy": "<strategy2>"}}
    ] or [],
    "primary_estimand": "<full estimand statement>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'crossover': '''Extract CROSSOVER/TREATMENT SWITCHING information from this protocol section.

Fields:
- has_crossover: true/false - is crossover permitted?
- crossover_description: When/how crossover is allowed
- crossover_adjustment_methods: Statistical methods for adjusting crossover bias
  (e.g., "RPSFT", "IPCW", "Two-stage")

RESPOND IN JSON:
{{
    "has_crossover": <true/false>,
    "crossover_description": "<description>" or null,
    "crossover_adjustment_methods": ["<method1>", "<method2>"] or [],
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        # =========================================================================
        # NEW SECTION PROMPTS (2025-01)
        # =========================================================================

        'safety_analysis': '''Extract SAFETY ANALYSIS information from this protocol section.

SEARCH for these patterns (ICH E2A, E6, FDA Safety Guidance):
- "treatment-emergent" / "TEAE" / "adverse event" / "adverse experience"
- "MedDRA" / "WHO-ART" / "coding dictionary"
- "CTCAE" / "NCI-CTCAE" / "Common Terminology Criteria"
- "serious adverse event" / "SAE" / "Grade 3-4" / "Grade 5"
- "adverse events of special interest" / "AESI" / "events of interest"
- "immune-related" / "irAE" / "immune-mediated"
- "dose modification" / "dose reduction" / "dose delay" / "dose discontinuation"
- "30 days" / "90 days" / "follow-up period" for AE collection

Required fields:
- teae_definition: How treatment-emergent AEs are defined
- ae_collection_period: When AEs are collected (start to end)

Optional fields:
- ae_coding_dictionary: e.g., "MedDRA version 25.0"
- ae_grading_scale: e.g., "NCI-CTCAE v5.0"
- sae_definition: SAE criteria
- sae_reporting_period: SAE reporting window
- aesi_list: List of AEs of special interest
- irae_categories: List of immune-related AE categories
- dose_reduction_rules: Rules for dose reduction
- dose_discontinuation_rules: Rules for stopping treatment

RESPOND IN JSON:
{{
    "teae_definition": "<definition or [NOT FOUND]>",
    "ae_collection_period": "<period or [NOT FOUND]>",
    "ae_coding_dictionary": "<dictionary>" or null,
    "ae_grading_scale": "<scale>" or null,
    "sae_definition": "<definition>" or null,
    "sae_reporting_period": "<period>" or null,
    "aesi_list": ["<aesi1>", "<aesi2>", ...] or [],
    "irae_categories": ["<category1>", "<category2>", ...] or [],
    "dose_reduction_rules": ["<rule1>", "<rule2>", ...] or [],
    "dose_discontinuation_rules": ["<rule1>", "<rule2>", ...] or [],
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'pharmacokinetics': '''Extract PHARMACOKINETIC (PK) ANALYSIS information from this protocol section.

SEARCH for these patterns (FDA Population PK Guidance):
- "pharmacokinetic" / "PK" / "pharmacokinetics"
- "Cmax" / "Tmax" / "AUC" / "t1/2" / "half-life" / "clearance"
- "population PK" / "PopPK" / "NONMEM" / "Phoenix"
- "exposure" / "exposure-response" / "E-R"
- "PK population" / "PK evaluable" / "rich sampling" / "sparse sampling"
- "BLQ" / "below limit of quantification"

Required field:
- pk_population_definition: Who is included in PK analysis

Optional fields:
- pk_parameters: List of PK parameters (Cmax, AUC, etc.)
- pk_sampling_timepoints: When PK samples are collected
- pk_analysis_method: "Non-compartmental" or "Population PK"
- population_pk_model: Model type if PopPK
- pk_software: Software used (NONMEM, Phoenix, etc.)
- exposure_response_analysis: true/false
- pk_covariates: Covariates in PK analysis

RESPOND IN JSON:
{{
    "pk_population_definition": "<definition or [NOT FOUND]>",
    "pk_parameters": ["<param1>", "<param2>", ...] or [],
    "pk_sampling_timepoints": ["<time1>", "<time2>", ...] or [],
    "pk_analysis_method": "<method>" or null,
    "population_pk_model": "<model>" or null,
    "pk_software": "<software>" or null,
    "exposure_response_analysis": <true/false> or null,
    "pk_covariates": ["<cov1>", "<cov2>", ...] or [],
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'biomarkers': '''Extract BIOMARKER ANALYSIS information from this protocol section.

SEARCH for these patterns (FDA Biomarker/CDx Guidance):
- "biomarker" / "predictive" / "prognostic" / "pharmacodynamic"
- "PD-L1" / "22C3" / "SP263" / "28-8" / "TPS" / "CPS" / "IC"
- "TMB" / "tumor mutational burden" / "mutations per megabase"
- "MSI" / "microsatellite instability" / "MSI-H" / "MSS"
- "MMR" / "mismatch repair" / "MLH1" / "MSH2" / "MSH6" / "PMS2"
- "ctDNA" / "circulating tumor DNA" / "liquid biopsy"
- "companion diagnostic" / "CDx" / "FoundationOne" / "MSK-IMPACT"
- "EGFR" / "ALK" / "ROS1" / "BRAF" / "KRAS" / "NTRK"

Optional fields (extract all that apply):
- predictive_biomarkers: Biomarkers that predict treatment response
- prognostic_biomarkers: Biomarkers that predict outcome regardless of treatment
- pdl1_assay: Specific PD-L1 assay used
- pdl1_cutoffs: PD-L1 cutoff values (e.g., <1%, 1-49%, ≥50%)
- pdl1_scoring_method: TPS, CPS, or IC scoring
- tmb_assay: TMB assay used
- tmb_cutoff: TMB threshold (e.g., ≥10 mut/Mb)
- msi_testing_method: MSI testing method (IHC, PCR, NGS)
- mmr_proteins_tested: MMR proteins tested
- genomic_platform: Genomic testing platform
- ctdna_analysis: true/false if ctDNA analysis planned
- companion_diagnostic_required: true/false
- companion_diagnostic_name: Name of CDx

RESPOND IN JSON:
{{
    "predictive_biomarkers": ["<biomarker1>", "<biomarker2>", ...] or [],
    "prognostic_biomarkers": ["<biomarker1>", "<biomarker2>", ...] or [],
    "pdl1_assay": "<assay>" or null,
    "pdl1_cutoffs": ["<cutoff1>", "<cutoff2>", ...] or [],
    "pdl1_scoring_method": "<method>" or null,
    "tmb_assay": "<assay>" or null,
    "tmb_cutoff": "<cutoff>" or null,
    "msi_testing_method": "<method>" or null,
    "mmr_proteins_tested": ["<protein1>", "<protein2>", ...] or [],
    "genomic_platform": "<platform>" or null,
    "ctdna_analysis": <true/false> or null,
    "companion_diagnostic_required": <true/false> or null,
    "companion_diagnostic_name": "<name>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'laboratory': '''Extract LABORATORY ANALYSIS information from this protocol section.

SEARCH for these patterns (ICH E3, CTCAE):
- "laboratory" / "lab" / "hematology" / "chemistry" / "urinalysis"
- "hemoglobin" / "WBC" / "ANC" / "platelets" / "neutrophils"
- "ALT" / "AST" / "bilirubin" / "creatinine" / "GFR"
- "shift table" / "baseline to worst" / "worst post-baseline"
- "ULN" / "LLN" / "upper limit of normal" / "lower limit"
- "Hy's law" / "hepatotoxicity" / "DILI"
- "clinically notable" / "clinically significant"

Optional fields:
- hematology_parameters: List of hematology labs
- chemistry_parameters: List of chemistry labs
- urinalysis_parameters: List of urinalysis tests
- shift_table_analysis: true/false if shift tables planned
- lab_ctcae_grading: true/false if labs graded by CTCAE
- clinically_notable_criteria: Criteria for notable abnormalities
- hys_law_analysis: true/false if Hy's law analysis planned

RESPOND IN JSON:
{{
    "hematology_parameters": ["<param1>", "<param2>", ...] or [],
    "chemistry_parameters": ["<param1>", "<param2>", ...] or [],
    "urinalysis_parameters": ["<param1>", "<param2>", ...] or [],
    "shift_table_analysis": <true/false> or null,
    "lab_ctcae_grading": <true/false> or null,
    "clinically_notable_criteria": {{"<param>": "<criteria>", ...}} or {{}},
    "hys_law_analysis": <true/false> or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'exposure': '''Extract STUDY DRUG EXPOSURE information from this protocol section.

SEARCH for these patterns:
- "exposure" / "drug exposure" / "treatment exposure"
- "duration of treatment" / "time on treatment" / "cycles"
- "cumulative dose" / "total dose" / "dose intensity"
- "relative dose intensity" / "RDI" / "dose intensity"
- "dose delay" / "dose reduction" / "dose interruption"

Optional fields:
- exposure_metrics: List of exposure metrics reported
- dose_delay_definition: How dose delay is defined
- dose_reduction_definition: How dose reduction is defined
- rdi_calculation_method: How RDI is calculated
- rdi_categories: Categories for RDI analysis

RESPOND IN JSON:
{{
    "exposure_metrics": ["<metric1>", "<metric2>", ...] or [],
    "dose_delay_definition": "<definition>" or null,
    "dose_reduction_definition": "<definition>" or null,
    "rdi_calculation_method": "<method>" or null,
    "rdi_categories": ["<category1>", "<category2>", ...] or [],
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'concomitant_medications': '''Extract CONCOMITANT MEDICATIONS information from this protocol section.

SEARCH for these patterns:
- "concomitant" / "prior therapy" / "prior treatment" / "prior medication"
- "prohibited" / "forbidden" / "not permitted" / "excluded"
- "WHO Drug Dictionary" / "ATC" / "medication coding"
- "immunosuppressant" / "steroid" / "corticosteroid"
- "lines of therapy" / "prior lines" / "treatment history"

Optional fields:
- medication_coding: Coding dictionary used
- prohibited_medications: List of prohibited medications
- medications_of_interest: Medications to be analyzed separately
- prior_lines_of_therapy: true/false if prior lines collected
- prior_immunotherapy: true/false if prior IO collected

RESPOND IN JSON:
{{
    "medication_coding": "<coding>" or null,
    "prohibited_medications": ["<med1>", "<med2>", ...] or [],
    "medications_of_interest": ["<med1>", "<med2>", ...] or [],
    "prior_lines_of_therapy": <true/false> or null,
    "prior_immunotherapy": <true/false> or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'immunogenicity': '''Extract IMMUNOGENICITY information from this protocol section.

SEARCH for these patterns (FDA Immunogenicity Guidance):
- "immunogenicity" / "anti-drug antibody" / "ADA" / "antibody"
- "neutralizing antibody" / "NAb" / "neutralizing"
- "screening" / "confirmatory" / "titer"
- "treatment-emergent ADA" / "treatment-boosted"
- "impact on efficacy" / "impact on safety" / "impact on PK"

Optional fields (extract all that apply):
- ada_testing_performed: true/false
- ada_assay_type: Type of ADA assay
- ada_sampling_timepoints: When ADA samples collected
- nab_testing_performed: true/false
- nab_assay_type: Type of NAb assay
- ada_incidence_analysis: true/false if incidence analyzed
- ada_impact_on_efficacy: true/false
- ada_impact_on_safety: true/false
- ada_impact_on_pk: true/false

RESPOND IN JSON:
{{
    "ada_testing_performed": <true/false> or null,
    "ada_assay_type": "<type>" or null,
    "ada_sampling_timepoints": ["<time1>", "<time2>", ...] or [],
    "nab_testing_performed": <true/false> or null,
    "nab_assay_type": "<type>" or null,
    "ada_incidence_analysis": <true/false> or null,
    "ada_impact_on_efficacy": <true/false> or null,
    "ada_impact_on_safety": <true/false> or null,
    "ada_impact_on_pk": <true/false> or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'conventions': '''Extract ANALYSIS CONVENTIONS information from this protocol section.

SEARCH for these patterns (CDISC ADaM, ICH E9):
- "baseline" / "baseline definition" / "baseline value"
- "last observation" / "LOCF" / "last value"
- "date imputation" / "partial date" / "missing date"
- "visit window" / "analysis window" / "target day"
- "on-treatment" / "on treatment" / "treatment period"
- "post-treatment" / "follow-up" / "off-treatment"
- "rounding" / "decimal places"

Optional fields:
- baseline_definition: How baseline is defined
- baseline_window: Window for baseline measurements
- partial_date_imputation_rules: Rules for imputing partial dates
- visit_windows: Visit window definitions
- on_treatment_definition: Definition of on-treatment period
- post_treatment_definition: Definition of post-treatment
- rounding_convention: Rounding rules

RESPOND IN JSON:
{{
    "baseline_definition": "<definition>" or null,
    "baseline_window": "<window>" or null,
    "partial_date_imputation_rules": {{"<date_type>": "<rule>", ...}} or {{}},
    "visit_windows": {{"<visit>": "<window>", ...}} or {{}},
    "on_treatment_definition": "<definition>" or null,
    "post_treatment_definition": "<definition>" or null,
    "rounding_convention": "<convention>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'protocol_deviations': '''Extract PROTOCOL DEVIATION information from this protocol section.

SEARCH for these patterns (ICH E6, E9):
- "protocol deviation" / "protocol violation" / "deviation"
- "important deviation" / "major deviation" / "minor deviation"
- "eligibility violation" / "inclusion/exclusion" / "wrong treatment"
- "prohibited medication" / "prohibited therapy"
- "impact on" / "exclusion from"

Optional fields:
- important_deviation_categories: Categories of important deviations
- deviation_impact_on_populations: How deviations affect populations

RESPOND IN JSON:
{{
    "important_deviation_categories": ["<category1>", "<category2>", ...] or [],
    "deviation_impact_on_populations": "<description>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'pro': '''Extract PATIENT-REPORTED OUTCOMES (PRO) information from this protocol section.

SEARCH for these patterns (FDA PRO Guidance):
- "patient-reported" / "PRO" / "quality of life" / "QoL" / "HRQoL"
- "EORTC" / "QLQ-C30" / "QLQ-LC13" / "QLQ-BR23"
- "EQ-5D" / "EQ-5D-5L" / "EuroQol"
- "FACT" / "FACT-G" / "FACIT"
- "symptom" / "symptom burden" / "symptom severity"
- "time to deterioration" / "TTD" / "deterioration"
- "responder" / "responder analysis" / "MID" / "minimally important difference"
- "compliance" / "completion rate" / "missing PRO"
- "ePRO" / "electronic PRO"

Optional fields (extract all that apply):
- pro_instruments: List of PRO instruments used
- instrument_scoring_rules: Scoring rules for instruments
- pro_primary_endpoint: PRO as primary endpoint (if applicable)
- pro_secondary_endpoints: PRO secondary endpoints
- time_to_deterioration: true/false if TTD analysis planned
- ttd_threshold: Threshold for deterioration
- pro_responder_definition: Definition of PRO responder
- pro_missing_data_handling: How missing PRO data is handled
- pro_compliance_threshold: Required compliance rate
- pro_collection_schedule: When PROs are collected
- pro_electronic_capture: true/false if ePRO used

RESPOND IN JSON:
{{
    "pro_instruments": ["<instrument1>", "<instrument2>", ...] or [],
    "instrument_scoring_rules": {{"<instrument>": "<scoring>", ...}} or {{}},
    "pro_primary_endpoint": "<endpoint>" or null,
    "pro_secondary_endpoints": ["<endpoint1>", "<endpoint2>", ...] or [],
    "time_to_deterioration": <true/false> or null,
    "ttd_threshold": "<threshold>" or null,
    "pro_responder_definition": "<definition>" or null,
    "pro_missing_data_handling": "<handling>" or null,
    "pro_compliance_threshold": <number> or null,
    "pro_collection_schedule": ["<time1>", "<time2>", ...] or [],
    "pro_electronic_capture": <true/false> or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'dmc': '''Extract DATA MONITORING COMMITTEE (DMC) information from this protocol section.

SEARCH for these patterns (FDA DMC Guidance):
- "data monitoring committee" / "DMC" / "DSMB" / "data safety"
- "independent" / "unblinded" / "charter"
- "safety review" / "interim review" / "periodic review"
- "stopping rule" / "stopping boundary" / "safety stopping"
- "futility" / "conditional power" / "predictive probability"
- "recommendation" / "continue" / "stop" / "modify"

Required field:
- has_dmc: true/false - is there a DMC?

Optional fields:
- dmc_charter_exists: true/false
- dmc_review_frequency: How often DMC reviews
- dmc_unblinded: true/false if DMC sees unblinded data
- safety_stopping_rules: List of safety stopping rules
- safety_boundary_type: Type of safety boundary
- futility_review_planned: true/false
- futility_boundary: Futility stopping criterion
- dmc_recommendation_options: What DMC can recommend
- sponsor_blinded: true/false if sponsor is blinded
- independent_statistician: true/false if independent stats support

RESPOND IN JSON:
{{
    "has_dmc": <true/false or null if unknown>,
    "dmc_charter_exists": <true/false> or null,
    "dmc_review_frequency": "<frequency>" or null,
    "dmc_unblinded": <true/false> or null,
    "safety_stopping_rules": ["<rule1>", "<rule2>", ...] or [],
    "safety_boundary_type": "<type>" or null,
    "futility_review_planned": <true/false> or null,
    "futility_boundary": "<boundary>" or null,
    "dmc_recommendation_options": ["<option1>", "<option2>", ...] or [],
    "sponsor_blinded": <true/false> or null,
    "independent_statistician": <true/false> or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'special_designs': '''Extract SPECIAL TRIAL DESIGN information from this protocol section.

SEARCH for these patterns (FDA Adaptive/Master Protocol Guidance):
- "master protocol" / "basket" / "umbrella" / "platform"
- "adaptive" / "adaptive design" / "sample size re-estimation"
- "enrichment" / "adaptive enrichment" / "biomarker-guided"
- "seamless" / "phase 2/3" / "phase II/III"
- "shared control" / "common control" / "borrowing"
- "response-adaptive" / "adaptive randomization"

Optional fields (most trials will have none of these):
- is_master_protocol: true/false
- master_protocol_type: basket, umbrella, or platform
- is_basket_trial: true/false
- basket_tumor_types: List of tumor types in basket
- basket_shared_biomarker: Common biomarker
- is_umbrella_trial: true/false
- umbrella_biomarker_arms: Biomarker-defined arms
- is_platform_trial: true/false
- shared_control_arm: true/false
- is_adaptive: true/false
- adaptive_features: List of adaptive features
- adaptation_timing: When adaptations occur
- adaptation_rules: Rules for adaptation
- is_seamless: true/false
- seamless_phases: Which phases combined
- phase2_to_phase3_criteria: Go/no-go criteria

RESPOND IN JSON:
{{
    "is_master_protocol": <true/false> or null,
    "master_protocol_type": "<type>" or null,
    "is_basket_trial": <true/false> or null,
    "basket_tumor_types": ["<type1>", "<type2>", ...] or [],
    "basket_shared_biomarker": "<biomarker>" or null,
    "is_umbrella_trial": <true/false> or null,
    "umbrella_biomarker_arms": []{{"biomarker": "<bm>", "treatment": "<tx>"}}, ...] or [],
    "is_platform_trial": <true/false> or null,
    "shared_control_arm": <true/false> or null,
    "is_adaptive": <true/false> or null,
    "adaptive_features": ["<feature1>", "<feature2>", ...] or [],
    "adaptation_timing": ["<timing1>", "<timing2>", ...] or [],
    "adaptation_rules": "<rules>" or null,
    "is_seamless": <true/false> or null,
    "seamless_phases": "<phases>" or null,
    "phase2_to_phase3_criteria": "<criteria>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'tumor_assessment': '''Extract TUMOR ASSESSMENT information from this protocol section.

SEARCH for these patterns (RECIST, iRECIST, FDA Oncology):
- "RECIST" / "RECIST 1.1" / "response criteria" / "response evaluation"
- "iRECIST" / "irRECIST" / "immune-related" / "immune-modified"
- "Lugano" / "lymphoma" / "Cheson"
- "RANO" / "brain tumor" / "CNS"
- "tumor assessment" / "imaging" / "radiologic" / "scan"
- "target lesion" / "non-target" / "measurable" / "evaluable"
- "BICR" / "blinded independent" / "central review" / "investigator"
- "CR" / "PR" / "SD" / "PD" / "complete response" / "partial response"
- "confirmation" / "confirmed response" / "unconfirmed"
- "pseudoprogression" / "iUPD" / "iCPD"

Required field:
- response_criteria: Which criteria used (RECIST 1.1, iRECIST, etc.)

Optional fields:
- response_criteria_version: Version number
- assessment_schedule: When assessments occur
- baseline_imaging_window: Window for baseline scans
- target_lesion_selection: Rules for selecting target lesions
- max_target_lesions: Maximum number of target lesions
- min_lesion_size: Minimum measurable lesion size
- assessment_method: investigator, BICR, or both
- bicr_primary: true/false if BICR is primary
- discrepancy_resolution: How discrepancies handled
- confirmation_required: true/false if confirmation needed
- confirmation_window: Time window for confirmation
- pseudoprogression_handling: How pseudoprogression handled
- new_lesion_confirmation: true/false if new lesions need confirmation
- progression_date_definition: How progression date determined

RESPOND IN JSON:
{{
    "response_criteria": "<criteria or [NOT FOUND]>",
    "response_criteria_version": "<version>" or null,
    "assessment_schedule": "<schedule>" or null,
    "baseline_imaging_window": "<window>" or null,
    "target_lesion_selection": "<rules>" or null,
    "max_target_lesions": <number> or null,
    "min_lesion_size": "<size>" or null,
    "assessment_method": "<method>" or null,
    "bicr_primary": <true/false> or null,
    "discrepancy_resolution": "<resolution>" or null,
    "confirmation_required": <true/false> or null,
    "confirmation_window": "<window>" or null,
    "pseudoprogression_handling": "<handling>" or null,
    "new_lesion_confirmation": <true/false> or null,
    "progression_date_definition": "<definition>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        # =========================================================================
        # NEW SECTION PROMPTS (2025-01) - Bridging, Structured Analyses, Regulatory
        # =========================================================================

        'bridging_study': '''Extract BRIDGING STUDY and MULTI-REGIONAL CLINICAL TRIAL (MRCT) information.

Source: ICH E5 (Ethnic Factors), ICH E17 (MRCT)

Look for:
- Is this a bridging study or MRCT (multi-regional)?
- Reference studies being bridged to
- Consistency testing thresholds (e.g., HR < 0.850 at interim, < 0.835 at final)
- Hierarchical testing steps for bridging
- Ethnic sensitivity assessments

Return JSON:
{{
    "is_bridging_study": <true/false> or null,
    "is_mrct": <true/false> or null,
    "bridging_region": "<region>" or null,
    "reference_studies": ["<study1>", "<study2>", ...] or [],
    "consistency_testing_required": <true/false> or null,
    "consistency_hr_threshold_interim": <number> or null,
    "consistency_hr_threshold_final": <number> or null,
    "hierarchical_testing_steps": ["<step1>", "<step2>", ...] or [],
    "ethnic_sensitivity_assessment": "<assessment>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'filing_endpoints': '''Extract REGULATORY FILING ENDPOINT information (e.g., TTF for China filing).

Source: NMPA guidance, PMDA guidance, regional filing strategies

Look for:
- Early filing endpoints (TTF, ORR for accelerated approval)
- Filing-specific sample sizes and follow-up requirements
- Statistical tests for filing endpoints (e.g., weighted log-rank)
- Alpha spending for filing endpoints

Return JSON:
{{
    "has_early_filing_endpoint": <true/false> or null,
    "filing_endpoint_name": "<endpoint>" or null,
    "filing_endpoint_definition": "<definition>" or null,
    "filing_regulatory_authority": "<authority>" or null,
    "filing_target_subjects": <number> or null,
    "filing_minimum_followup_months": <number> or null,
    "filing_statistical_test": "<test>" or null,
    "filing_alpha": <number> or null,
    "filing_alpha_penalty": <true/false> or null,
    "filing_hypothesis": "<hypothesis>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'secondary_analyses': '''Extract STRUCTURED SECONDARY ENDPOINT ANALYSIS information.

Source: ICH E9, FDA Guidance

Look for:
- Testing hierarchy for secondary endpoints
- ORR analysis method (e.g., CMH test, Clopper-Pearson CI)
- PFS analysis method and censoring
- DOR analysis method
- Analysis timepoints

Return JSON:
{{
    "endpoint_testing_hierarchy": ["<endpoint1>", "<endpoint2>", ...] or [],
    "orr_analysis": {{
        "analysis_method": "<method>" or null,
        "ci_method": "<ci>" or null,
        "hypothesis_test": "<test>" or null,
        "timepoints": ["<t1>", "<t2>", ...] or []
    }} or null,
    "pfs_analysis": {{
        "analysis_method": "<method>" or null,
        "censoring_reference": "<ref>" or null
    }} or null,
    "dor_analysis": {{
        "analysis_method": "<method>" or null
    }} or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'subgroup_specs': '''Extract SUBGROUP ANALYSIS SPECIFICATIONS.

Source: ICH E9, FDA Subgroup Analysis Guidance

Look for:
- Forest plot variables (age, gender, race, disease characteristics)
- Multivariate Cox covariates
- Landmark analysis timepoints
- Visualization plans (waterfall, swimmer, spider plots)

Return JSON:
{{
    "forest_plot_planned": <true/false> or null,
    "forest_plot_variables": ["<var1>", "<var2>", ...] or [],
    "forest_plot_method": "<method>" or null,
    "multivariate_cox_planned": <true/false> or null,
    "multivariate_cox_covariates": ["<cov1>", "<cov2>", ...] or [],
    "covariate_selection_method": "<method>" or null,
    "landmark_analysis_planned": <true/false> or null,
    "landmark_timepoints": ["<t1>", "<t2>", ...] or [],
    "landmark_method": "<method>" or null,
    "waterfall_plot_planned": <true/false> or null,
    "swimmer_plot_planned": <true/false> or null,
    "spider_plot_planned": <true/false> or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'baseline_chars': '''Extract BASELINE CHARACTERISTICS (Table 1) specifications.

Source: ICH E3, CDISC SDTM

Look for:
- Demographic variables to summarize
- Disease characteristics
- Molecular/biomarker variables
- Prior therapy variables
- Summary statistics to use

Return JSON:
{{
    "baseline_demographic_variables": ["<var1>", "<var2>", ...] or [],
    "baseline_regional_variables": ["<var1>", "<var2>", ...] or [],
    "baseline_disease_variables": ["<var1>", "<var2>", ...] or [],
    "baseline_molecular_variables": ["<var1>", "<var2>", ...] or [],
    "baseline_prior_therapy_variables": ["<var1>", "<var2>", ...] or [],
    "baseline_performance_status_variables": ["<var1>", "<var2>", ...] or [],
    "continuous_summary_stats": ["<stat1>", "<stat2>", ...] or [],
    "categorical_summary_stats": ["<stat1>", "<stat2>", ...] or [],
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'date_imputation': '''Extract DATE IMPUTATION RULES and calculation conventions.

Source: CDISC ADaM, ICH E9

Look for:
- Death date imputation rules
- Progression date imputation rules
- AE date imputation rules
- Duration calculation formulas
- Days per month/year conventions

Return JSON:
{{
    "death_date_imputation": "<rule>" or null,
    "progression_date_imputation": "<rule>" or null,
    "ae_start_date_imputation": "<rule>" or null,
    "ae_end_date_imputation": "<rule>" or null,
    "treatment_start_imputation": "<rule>" or null,
    "duration_calculation_formula": "<formula>" or null,
    "days_per_month": <number> or null,
    "days_per_year": <number> or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'exposure_formulas': '''Extract EXPOSURE and RDI (Relative Dose Intensity) FORMULAS.

Source: ICH E3, company standards

Look for:
- RDI formula for experimental arm (include the actual formula)
- RDI formula for control arm
- Planned doses per arm
- Dose delay threshold
- Dose reduction levels
- Cycle lengths

Return JSON:
{{
    "rdi_formula_experimental": "<formula>" or null,
    "rdi_formula_control": "<formula>" or null,
    "planned_dose_experimental": "<dose>" or null,
    "planned_dose_control": "<dose>" or null,
    "dose_delay_threshold_days": <number> or null,
    "dose_reduction_levels": ["<level1>", "<level2>", ...] or [],
    "rdi_categories": ["<cat1>", "<cat2>", ...] or [],
    "cycle_length_experimental_days": <number> or null,
    "cycle_length_control_days": <number> or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'study_conduct': '''Extract STUDY CONDUCT ANALYSES information.

Source: ICH E6, ICH E3

Look for:
- Protocol deviation categories
- Programmable vs non-programmable deviations
- Accrual summaries (by country, site, time)
- Stratification discrepancy analysis plans
- Treatment assignment discrepancies

Return JSON:
{{
    "deviation_categories": ["<cat1>", "<cat2>", ...] or [],
    "programmable_deviations": ["<dev1>", "<dev2>", ...] or [],
    "non_programmable_deviations": ["<dev1>", "<dev2>", ...] or [],
    "accrual_summary_by": ["<dim1>", "<dim2>", ...] or [],
    "stratification_discrepancy_analysis": <true/false> or null,
    "as_randomized_vs_as_treated": <true/false> or null,
    "drug_accountability_analysis": <true/false> or null,
    "consent_tracking": <true/false> or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'cdisc_versioning': '''Extract CDISC VERSIONING and DEFINE-XML information.

Source: FDA Study Data Technical Conformance Guide, CDISC Define-XML v2.1

Look for:
- SDTM-IG version
- ADaM-IG version
- Define-XML version
- Controlled Terminology version and freeze date
- Submission type and format

Return JSON:
{{
    "sdtm_ig_version": "<version>" or null,
    "adam_ig_version": "<version>" or null,
    "define_xml_version": "<version>" or null,
    "ct_version": "<version>" or null,
    "ct_freeze_date": "<date>" or null,
    "ct_freeze_milestone": "<milestone>" or null,
    "ct_packages_used": ["<pkg1>", "<pkg2>", ...] or [],
    "recoding_milestone": "<milestone>" or null,
    "submission_type": "<type>" or null,
    "regulatory_authority": "<authority>" or null,
    "electronic_submission_format": "<format>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'coding_standards': '''Extract MEDICAL CODING STANDARDS information (MedDRA, WHODrug).

Source: MedDRA (ICH), WHODrug (Uppsala Monitoring Centre)

Look for:
- MedDRA version and freeze date
- MedDRA coding level (LLT, PT, SOC)
- WHODrug version and format
- ATC classification level
- Recoding triggers and conventions

Return JSON:
{{
    "meddra_version": "<version>" or null,
    "meddra_freeze_date": "<date>" or null,
    "meddra_freeze_milestone": "<milestone>" or null,
    "ae_coding_level": "<level>" or null,
    "whodrug_version": "<version>" or null,
    "whodrug_format": "<format>" or null,
    "whodrug_freeze_date": "<date>" or null,
    "atc_classification_level": "<level>" or null,
    "recoding_triggers": ["<trigger1>", "<trigger2>", ...] or [],
    "dual_coding_required": <true/false> or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'control_rationale': '''Extract CONTROL GROUP RATIONALE (ICH E10).

Source: ICH E10 (Choice of Control Group)

Look for:
- Control type (active, placebo, dose-response)
- Active control justification
- Historical effect estimates
- Non-inferiority margin justification
- Assay sensitivity evidence

Return JSON:
{{
    "control_type": "<type>" or null,
    "control_justification": "<justification>" or null,
    "active_control_drug": "<drug>" or null,
    "active_control_dose": "<dose>" or null,
    "active_control_rationale": "<rationale>" or null,
    "historical_effect_estimate": "<estimate>" or null,
    "ni_margin_justification": "<justification>" or null,
    "ni_margin_preserves": "<percentage>" or null,
    "historical_trials_referenced": ["<trial1>", "<trial2>", ...] or [],
    "rescue_medication_permitted": <true/false> or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'genomic_sampling': '''Extract GENOMIC SAMPLING (ICH E18) information.

Source: ICH E18 (Genomic Sampling)

Look for:
- Sample types collected (tumor tissue, ctDNA, PBMCs)
- Collection timepoints
- Mandatory vs optional samples
- Pre-specified genomic analyses
- Exploratory genomic analyses
- NGS platforms and assays

Return JSON:
{{
    "sample_types_collected": ["<type1>", "<type2>", ...] or [],
    "genomic_collection_timepoints": ["<t1>", "<t2>", ...] or [],
    "sample_mandatory_vs_optional": {{"<sample>": "<mandatory/optional>", ...}} or {{}},
    "sample_processing_requirements": "<requirements>" or null,
    "genomic_consent_type": "<type>" or null,
    "prespecified_genomic_analyses": ["<analysis1>", "<analysis2>", ...] or [],
    "exploratory_genomic_analyses": ["<analysis1>", "<analysis2>", ...] or [],
    "ngs_platform": "<platform>" or null,
    "gene_panel": "<panel>" or null,
    "ctdna_assay": "<assay>" or null,
    "genomic_data_format": "<format>" or null,
    "bioinformatics_pipeline": "<pipeline>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}'''
    }

    # Map our section names to ProtocolSectionParser section names
    SECTION_MAPPING = {
        'study_design': ['study_design', 'objectives', 'randomization', 'blinding'],
        'stratification': ['stratification', 'randomization', 'study_design', 'statistical_methods'],
        'sample_size': ['sample_size', 'statistical_methods'],
        'endpoints': ['endpoints', 'objectives', 'efficacy'],
        'statistical_methods': ['statistical_methods', 'sample_size', 'efficacy'],
        'interim_analysis': ['interim_analysis', 'statistical_methods'],
        'multiplicity': ['multiplicity', 'statistical_methods'],
        'missing_data': ['missing_data', 'statistical_methods', 'sensitivity'],
        'populations': ['populations', 'safety', 'efficacy'],
        'estimand': ['estimand', 'endpoints', 'statistical_methods'],
        'crossover': ['statistical_methods', 'sensitivity'],
        # NEW SECTION MAPPINGS (2025-01)
        'safety_analysis': ['safety', 'adverse_events', 'safety_analysis'],
        'pharmacokinetics': ['pharmacokinetics', 'pk', 'pharmacology'],
        'biomarkers': ['biomarkers', 'correlative', 'translational', 'pd-l1'],
        'laboratory': ['laboratory', 'lab', 'safety'],
        'exposure': ['exposure', 'drug_exposure', 'study_drug'],
        'concomitant_medications': ['concomitant', 'medications', 'prior_therapy'],
        'immunogenicity': ['immunogenicity', 'ada', 'antibody'],
        'conventions': ['conventions', 'definitions', 'general_considerations'],
        'protocol_deviations': ['deviations', 'protocol_deviations', 'populations'],
        'pro': ['pro', 'patient_reported', 'quality_of_life', 'qol'],
        'dmc': ['dmc', 'dsmb', 'data_monitoring', 'interim_analysis'],
        'special_designs': ['study_design', 'design', 'adaptive'],
        'tumor_assessment': ['tumor_assessment', 'imaging', 'response', 'efficacy'],
        # NEW SECTION MAPPINGS (2025-01) - Bridging, Structured Analyses, Regulatory
        'bridging_study': ['study_design', 'objectives', 'statistical_methods', 'mrct'],
        'filing_endpoints': ['endpoints', 'statistical_methods', 'filing', 'regulatory'],
        'secondary_analyses': ['efficacy', 'endpoints', 'statistical_methods'],
        'subgroup_specs': ['subgroup', 'statistical_methods', 'efficacy'],
        'baseline_chars': ['demographics', 'baseline', 'populations'],
        'date_imputation': ['conventions', 'definitions', 'statistical_methods'],
        'exposure_formulas': ['exposure', 'drug_exposure', 'study_drug', 'safety'],
        'study_conduct': ['deviations', 'populations', 'conduct'],
        'cdisc_versioning': ['cdisc', 'standards', 'conventions'],
        'coding_standards': ['adverse_events', 'safety', 'concomitant', 'coding'],
        'control_rationale': ['study_design', 'objectives', 'rationale'],
        'genomic_sampling': ['biomarkers', 'correlative', 'samples', 'genomic'],
    }

    def __init__(self, llm_client=None):
        """
        Initialize sectioned extractor.

        Args:
            llm_client: LLM client with chat() method
        """
        self.llm = llm_client
        # Pass LLM client to section parser for Claude Vision-based section detection
        self.section_parser = ProtocolSectionParser(llm_client=llm_client)
        self._parsed_protocol: Optional[ParsedProtocol] = None
        self._current_pdf_path: Optional[str] = None
        # Track which PDF was parsed to enable proper caching
        self._cached_pdf_path: Optional[str] = None
        self._cached_text_hash: Optional[str] = None
        # Flag to prevent re-parsing during parallel extraction
        self._in_parallel_extraction: bool = False

    def _get_relevant_text(self, section_name: str, protocol_text: str, max_chars: int = 60000) -> str:
        """
        Get relevant text for a section by:
        1. Parsing protocol into sections
        2. Returning combined text from relevant sections
        3. Using MULTI-REGION SAMPLING when section parsing fails

        CRITICAL: When falling back to full document, sample from multiple regions
        because statistical content is typically at 50-80% through the document,
        NOT in the first 25K characters.
        """
        # Parse protocol if not already done
        # CRITICAL FIX: NEVER re-parse during parallel extraction!
        # The pre-parse in extract_all() handles this.
        if self._in_parallel_extraction:
            # During parallel extraction, we MUST use the pre-parsed result
            # Re-parsing from multiple threads causes asyncio event loop conflicts
            if self._parsed_protocol is None:
                print(f"[SectionedExtractor] ERROR: In parallel extraction but no pre-parsed result!")
                # Fall through to use protocol_text directly
            # Skip verbose logging in parallel mode to reduce noise
        else:
            # NOT in parallel mode - can safely parse if needed
            needs_parsing = False
            text_hash = str(hash(protocol_text[:1000])) if protocol_text else None

            if self._parsed_protocol is None:
                needs_parsing = True
            elif self._current_pdf_path:
                # PDF mode: only reparse if PDF path changed
                needs_parsing = (self._cached_pdf_path != self._current_pdf_path)
            else:
                # Text mode: reparse if text content changed (use hash for efficiency)
                needs_parsing = (self._cached_text_hash != text_hash)

            if needs_parsing:
                print(f"[SectionedExtractor] Parsing document (PDF: {self._current_pdf_path})")
                # Use Vision-based parsing if PDF path is available
                self._parsed_protocol = self.section_parser.parse(
                    protocol_text,
                    pdf_path=self._current_pdf_path
                )
                # Cache the keys
                self._cached_pdf_path = self._current_pdf_path
                self._cached_text_hash = text_hash
                print(f"[SectionedExtractor] Parsed protocol into {len(self._parsed_protocol.sections)} sections")
                print(f"[SectionedExtractor] Available sections: {list(self._parsed_protocol.sections.keys())}")
            else:
                print(f"[SectionedExtractor] Using CACHED parse result ({len(self._parsed_protocol.sections)} sections)")

        # NO FALLBACKS: Use dynamic section location ONLY
        raw_text = ""
        if self._parsed_protocol and "full_text" in self._parsed_protocol.sections:
            raw_text = self._parsed_protocol.get("full_text", "")
        else:
            raw_text = protocol_text

        if not raw_text:
            print(f"[SectionedExtractor] ERROR: No text available for {section_name}")
            return ""

        # ALWAYS use multi-region sampling with dynamic location
        # This finds the ACTUAL section position, not wrong fallback content
        sampled_text = self._multi_region_sample(raw_text, section_name)
        combined_text = [sampled_text] if sampled_text else []

        result = "\n\n".join(combined_text) if combined_text else ""
        print(f"[SectionedExtractor] Final text for {section_name}: {len(result)} chars")
        return result[:max_chars]

    def _locate_sections_in_document(self, text: str) -> Dict[str, float]:
        """
        PASS 1: Use Claude to FIND where sections are located in the document.

        Instead of assuming fixed percentages, we scan the document and ask Claude
        to identify section headings and their approximate locations.

        Returns dict mapping section_name -> fraction (0.0-1.0) where section starts
        """
        # Check cache first (key by text hash)
        text_hash = str(hash(text[:1000] + text[-1000:]))  # Use start+end as hash key
        if text_hash in self._section_locations_cache:
            print(f"[SectionedExtractor] Using cached section locations")
            return self._section_locations_cache[text_hash]

        print(f"[SectionedExtractor] PASS 1: Locating sections in {len(text)} char document...")

        text_len = len(text)

        # Sample more heavily from CONTENT AREAS (40-85%) where statistical sections are
        # Reduce sampling of TOC area (0-15%) to avoid confusion
        # INCREASED from 900 to 1500 to better capture tables
        sample_size = 1500
        scan_samples = []

        # Strategic sampling positions:
        # Clinical protocols have statistical sections at 60-95%, NOT 45-70%!
        # Structure varies by protocol - sample more densely
        # - 0-5%: Title, TOC, Synopsis
        # - 5-25%: Background, Objectives, Eligibility
        # - 25-50%: Interventions, Dose modifications, Study Design
        # - 50-75%: Assessments, Adverse Events, Endpoints
        # - 60-95%: STATISTICAL METHODS (Section 9/10/11) <-- KEY AREA!
        # - 95-100%: References, Appendices
        sample_positions = [
            0.02,   # Very beginning (title - check for "first-line" etc)
            0.08,   # Synopsis area (often has sample size summary)
            0.15,   # End of TOC / start of intro
            0.25,   # Study design area
            0.35,   # Endpoints/objectives
            0.45,   # Mid-document (some protocols have stats earlier)
            0.55,   # Assessment schedules
            # DENSE SAMPLING of statistical content area
            0.60,   # Start of statistical section
            0.65,   # Sample size calculations
            0.70,   # Analysis populations
            0.75,   # Primary analysis methods
            0.78,   # Interim analysis
            0.80,   # Interim analysis details
            0.82,   # Multiplicity adjustments
            0.85,   # Missing data handling
            0.88,   # Censoring rules
            0.90,   # Sensitivity analyses
            0.93,   # Late statistical content
            0.96,   # Very late content (some SAPs have stats here)
        ]

        for pos_frac in sample_positions:
            pos = int(pos_frac * text_len)
            end_pos = min(pos + sample_size, text_len)
            snippet = text[pos:end_pos]
            pct = int(pos_frac * 100)
            scan_samples.append(f"=== POSITION {pct}% ===\n{snippet}")

        scan_text = "\n\n".join(scan_samples)

        prompt = f'''Scan this clinical trial protocol (sampled at different positions) and identify WHERE the ACTUAL CONTENT for key sections is located.

CRITICAL DISTINCTION - You must distinguish between:
1. **TABLE OF CONTENTS (TOC)** entries - These are LISTS of section names with page numbers. Example:
   "9. Statistical Methods............85"
   "9.1 Sample Size...................87"
   These are typically at 0-15% of the document. IGNORE THESE.

2. **ACTUAL SECTION CONTENT** - These are the real sections with paragraphs of text. Example:
   "9. STATISTICAL METHODS
   The primary analysis will be performed using a stratified log-rank test..."
   These typically start at 40-80% of the document.

HOW TO TELL THE DIFFERENCE:
- TOC entries have: section number + title + dots/spaces + page number
- Actual content has: section header followed by PARAGRAPHS of descriptive text

For each section, report where the ACTUAL CONTENT starts (NOT the TOC entry).

Look for these sections:
- STATISTICAL METHODS / STATISTICAL ANALYSIS (section 9, 10, or 11 typically)
- SAMPLE SIZE / POWER CALCULATION
- INTERIM ANALYSIS / GROUP SEQUENTIAL
- MULTIPLICITY / MULTIPLE TESTING / ALPHA SPENDING
- MISSING DATA / CENSORING
- STRATIFICATION / STRATIFIED RANDOMIZATION
- ENDPOINTS / PRIMARY ENDPOINT / OBJECTIVES
- STUDY POPULATIONS / ITT / FAS / PER-PROTOCOL

RESPOND IN JSON:
{{
    "sections_found": [
        {{"name": "statistical_methods", "position_percent": 65, "heading_found": "9. STATISTICAL ANALYSIS", "is_actual_content": true}},
        {{"name": "sample_size", "position_percent": 68, "heading_found": "9.1 Sample Size", "is_actual_content": true}},
        ...
    ]
}}

IMPORTANT RULES:
1. SKIP anything that looks like a Table of Contents (has page numbers after section names)
2. Only report sections where you see ACTUAL PARAGRAPH TEXT following the heading
3. Positions below 30% are almost always TOC - be suspicious of these
4. If you only see TOC entries and no actual content, report an empty list

DOCUMENT SAMPLES:
{scan_text}
'''

        try:
            if not self.llm:
                print(f"[SectionedExtractor] No LLM client available for section location")
                return {}

            if hasattr(self.llm, 'chat'):
                response = self.llm.chat(prompt, max_tokens=2000)
                # Extract actual content from response object
                if isinstance(response, str):
                    response_text = response
                elif hasattr(response, 'content'):
                    # LLMResponse object with content attribute
                    response_text = response.content
                elif hasattr(response, 'text'):
                    response_text = response.text
                else:
                    response_text = str(response)
            elif hasattr(self.llm, 'messages'):
                response = self.llm.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = response.content[0].text
            else:
                return {}

            # Parse response - with debug output
            print(f"[SectionedExtractor] Raw response (first 500 chars): {response_text[:500]}")

            json_text = response_text

            # Try to extract from markdown code block
            if '```json' in json_text:
                json_text = json_text.split('```json')[1].split('```')[0].strip()
            elif '```' in json_text:
                parts = json_text.split('```')
                for part in parts[1::2]:  # Odd indices are code blocks
                    if '{' in part:
                        json_text = part.strip()
                        break

            # Find the JSON object
            start = json_text.find('{')
            end = json_text.rfind('}') + 1

            if start < 0 or end <= start:
                print(f"[SectionedExtractor] No valid JSON object found in response")
                return {}

            json_str = json_text[start:end]

            # Decode literal escape sequences if present (e.g., "\\n" -> "\n")
            # This handles cases where the LLM response has escaped newlines
            if '\\n' in json_str or '\\t' in json_str:
                try:
                    # Try to decode as unicode escape sequence
                    json_str = json_str.encode('utf-8').decode('unicode_escape')
                except (UnicodeDecodeError, UnicodeEncodeError):
                    # If that fails, just replace common escapes manually
                    json_str = json_str.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')

            # Fix common JSON issues

            # 1. Fix unquoted keys: {sections_found: -> {"sections_found":
            json_str = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)', r'\1"\2"\3', json_str)

            # 2. Fix single-quoted keys: {'key': -> {"key":
            json_str = re.sub(r"'([^']+)'(\s*:)", r'"\1"\2', json_str)

            # 3. Fix single-quoted string values: : 'value' -> : "value"
            json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)

            # 4. Remove trailing commas before ] or }
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

            # 5. Fix Python-style None/True/False
            json_str = json_str.replace(': None', ': null')
            json_str = json_str.replace(': True', ': true')
            json_str = json_str.replace(': False', ': false')

            print(f"[SectionedExtractor] Cleaned JSON: {json_str[:300]}...")

            data = json.loads(json_str)

            # Normalize LLM-returned names to our expected section names
            NAME_ALIASES = {
                # Sample size variations
                'sample_size': 'sample_size',
                'sample_size_calculation': 'sample_size',
                'sample_size_justification': 'sample_size',
                'power_calculation': 'sample_size',
                'power': 'sample_size',
                'sample_size_determination': 'sample_size',
                # Statistical methods variations
                'statistical_methods': 'statistical_methods',
                'statistical_analysis': 'statistical_methods',
                'statistical': 'statistical_methods',
                'analysis_methods': 'statistical_methods',
                'primary_analysis': 'statistical_methods',
                # Endpoints variations
                'endpoints': 'endpoints',
                'primary_endpoint': 'endpoints',
                'primary_endpoints': 'endpoints',
                'objectives': 'endpoints',
                'efficacy_endpoints': 'endpoints',
                # Interim analysis variations
                'interim_analysis': 'interim_analysis',
                'interim_analyses': 'interim_analysis',
                'interim': 'interim_analysis',
                'group_sequential': 'interim_analysis',
                # Multiplicity variations
                'multiplicity': 'multiplicity',
                'multiple_testing': 'multiplicity',
                'alpha_spending': 'multiplicity',
                'multiplicity_adjustment': 'multiplicity',
                # Missing data variations
                'missing_data': 'missing_data',
                'censoring': 'missing_data',
                'missing_data_handling': 'missing_data',
                'sensitivity_analysis': 'missing_data',
                # Populations variations
                'populations': 'populations',
                'study_populations': 'populations',
                'analysis_populations': 'populations',
                'itt': 'populations',
                'fas': 'populations',
                'per_protocol': 'populations',
                # Stratification variations
                'stratification': 'stratification',
                'stratified_randomization': 'stratification',
                'randomization': 'stratification',
                # Study design variations
                'study_design': 'study_design',
                'study_overview': 'study_design',
                'design': 'study_design',
                # Estimand variations
                'estimand': 'estimand',
                'estimand_framework': 'estimand',
                # Safety variations
                'safety': 'safety_analysis',
                'safety_analysis': 'safety_analysis',
                'adverse_events': 'safety_analysis',
            }

            locations = {}
            for s in data.get('sections_found', []):
                raw_name = s.get('name', '').lower().replace(' ', '_')
                # Normalize the name
                name = NAME_ALIASES.get(raw_name, raw_name)
                pos = s.get('position_percent', 50) / 100.0
                heading = s.get('heading_found', '')
                is_actual = s.get('is_actual_content', True)

                # CRITICAL: Filter out TOC entries (positions below 30% are almost always TOC)
                if pos < 0.30:
                    print(f"[SectionedExtractor] SKIPPING '{raw_name}' at {int(pos*100)}% - likely TOC entry: {heading}")
                    continue

                # Also skip if explicitly marked as not actual content
                if not is_actual:
                    print(f"[SectionedExtractor] SKIPPING '{raw_name}' - not marked as actual content: {heading}")
                    continue

                # If name was normalized, log it
                if name != raw_name:
                    print(f"[SectionedExtractor] Normalized '{raw_name}' -> '{name}'")

                locations[name] = pos
                print(f"[SectionedExtractor] Found '{name}' at {int(pos*100)}%: {heading}")

            # Cache the results
            self._section_locations_cache[text_hash] = locations
            return locations

        except json.JSONDecodeError as e:
            print(f"[SectionedExtractor] JSON parse error: {e}")
            if 'json_str' in locals():
                # Show the problematic part of the JSON
                error_pos = e.pos if hasattr(e, 'pos') else 0
                context_start = max(0, error_pos - 20)
                context_end = min(len(json_str), error_pos + 20)
                print(f"[SectionedExtractor] Context around error: ...{json_str[context_start:context_end]}...")
        except Exception as e:
            print(f"[SectionedExtractor] Section location error: {e}")
            import traceback
            traceback.print_exc()

        return {}

    def _multi_region_sample(self, text: str, section_name: str) -> str:
        """
        Sample from multiple regions of the document based on section type.

        TWO-PASS APPROACH:
        1. First, try to locate the section dynamically using Claude
        2. If found, sample around that location
        3. Fall back to default regions if not found
        """
        text_len = len(text)

        # Try to get dynamically-located position first
        located = self._locate_sections_in_document(text)

        if section_name in located:
            # Use dynamically-discovered location!
            center_pos = located[section_name]
            print(f"[SectionedExtractor] Using dynamic location for '{section_name}': {int(center_pos*100)}%")

            # Sample a 20% window around the discovered location
            regions = [
                (max(0.0, center_pos - 0.10), min(1.0, center_pos + 0.05)),  # Just before and into section
                (max(0.0, center_pos), min(1.0, center_pos + 0.10)),          # Section start to middle
                (max(0.0, center_pos + 0.05), min(1.0, center_pos + 0.15)),   # Middle to end
            ]
        else:
            # NO FALLBACK - if section location failed, raise error
            raise ValueError(f"[SectionedExtractor] FATAL: Section '{section_name}' not located in document. Section location must succeed - no fallbacks allowed.")

        # Calculate sample size per region (aim for ~20K total for better coverage)
        sample_per_region = 20000 // len(regions)

        samples = []
        for i, (start_frac, end_frac) in enumerate(regions):
            start_pos = int(text_len * start_frac)
            end_pos = int(text_len * end_frac)
            region_len = end_pos - start_pos

            # Sample from CENTER of region, not just beginning
            # This ensures we capture content even if it's in the middle/end of region
            if region_len > sample_per_region:
                # Take from center of region for better coverage
                center_start = start_pos + (region_len - sample_per_region) // 2
                sample = text[center_start:center_start + sample_per_region]
            else:
                # Region is smaller than sample size, take all
                sample = text[start_pos:end_pos]

            region_label = f"REGION {i+1} ({int(start_frac*100)}-{int(end_frac*100)}% of document)"
            samples.append(f"=== {region_label} ===\n{sample}")

        return "\n\n".join(samples)

    def extract_section(
        self,
        section_name: str,
        protocol_text: str,
        max_tokens: int = 1500
    ) -> SectionExtractionResult:
        """
        Extract a single section from the protocol.

        Uses intelligent section parsing to find relevant text instead of
        simple truncation.

        Args:
            section_name: Name of section to extract
            protocol_text: Full protocol text (extractor will find relevant parts)
            max_tokens: Max tokens for LLM response

        Returns:
            SectionExtractionResult with extracted fields and confidence
        """
        if section_name not in self.SECTION_PROMPTS:
            raise ValueError(f"Unknown section: {section_name}")

        prompt = self.SECTION_PROMPTS[section_name]

        # Get RELEVANT text for this section (not just truncation!)
        relevant_text = self._get_relevant_text(section_name, protocol_text, max_chars=25000)

        # Diagnostic: Show first 500 chars of relevant text
        print(f"[Extractor] {section_name}: {len(relevant_text)} chars of relevant text")
        print(f"[Extractor] {section_name} preview: {relevant_text[:500]}...")

        # Build full prompt with section-relevant text
        full_prompt = f"""You are extracting structured information from a clinical trial protocol.

RELEVANT PROTOCOL SECTIONS FOR {section_name.upper()}:
{relevant_text}

{prompt}

Remember: Extract ONLY what is explicitly stated. Mark fields as [NOT FOUND] if not present.
"""

        try:
            response = self.llm.chat(full_prompt, max_tokens=max_tokens)

            # Handle different response types
            if hasattr(response, 'content'):
                response_text = response.content
            elif isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)

            # Diagnostic: Show LLM response
            print(f"[Extractor] {section_name} LLM response: {response_text[:800]}...")

            # Parse JSON response
            result = self._parse_section_response(section_name, response_text)
            return result

        except Exception as e:
            print(f"[SectionedExtractor] Error extracting {section_name}: {e}")
            return SectionExtractionResult(
                section_name=section_name,
                extracted_fields={},
                confidence=0.0,
                fields_found=[],
                fields_not_found=self.SECTIONS[section_name].get('required', []),
                needs_review=self.SECTIONS[section_name].get('critical', []),
                notes=[f"Extraction failed: {str(e)}"]
            )

    def _validate_extracted_data(
        self,
        section_name: str,
        data: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validate extracted data and fix obvious errors.

        Returns:
            Tuple of (corrected_data, validation_notes)
        """
        notes = []

        # =========================================================
        # SAMPLE SIZE VALIDATION
        # =========================================================
        if section_name == 'sample_size':
            sample_size = data.get('sample_size')

            # Fix sample_size = 0 (NEVER valid)
            if sample_size == 0:
                print(f"[VALIDATION] ERROR: sample_size=0 is invalid, setting to null")
                data['sample_size'] = None
                notes.append("VALIDATION: sample_size=0 is invalid - set to null for review")

            # Flag suspiciously small sample sizes for Phase 3
            if sample_size and sample_size < 50:
                notes.append(f"VALIDATION WARNING: sample_size={sample_size} is unusually small")

            # Cross-validate regional cohorts against total sample size
            regional_cohorts = data.get('regional_cohorts')
            if regional_cohorts and isinstance(regional_cohorts, dict):
                cohort_sum = sum(v for v in regional_cohorts.values() if isinstance(v, (int, float)))
                if cohort_sum > 0:
                    notes.append(f"VALIDATION: Found regional cohorts totaling {cohort_sum} patients")
                    # Regional cohorts should be ADDITIONAL to main study, not exceed total
                    if sample_size and cohort_sum > sample_size:
                        notes.append(f"VALIDATION WARNING: regional cohorts ({cohort_sum}) exceed main sample_size ({sample_size}) - may be separate extension")

        # =========================================================
        # INTERIM ANALYSIS VALIDATION
        # =========================================================
        if section_name == 'interim_analysis':
            num_ia = data.get('num_interim_analyses')

            # Not all trials have interim analyses - this is valid
            if not num_ia or num_ia == 0:
                # Valid for Phase 2, single-arm, or trials without DMC
                notes.append("VALIDATION: No interim analyses planned - valid for many study designs")
            else:
                # Only validate IA details if interim analyses exist
                # Validate num_interim_analyses against interim_events array
                interim_events = data.get('interim_events', [])
                if interim_events and isinstance(interim_events, list):
                    expected_count = len(interim_events)
                    if num_ia != expected_count:
                        print(f"[VALIDATION] WARNING: num_interim_analyses={num_ia} but interim_events has {expected_count} entries")
                        notes.append(f"VALIDATION: num_interim_analyses mismatch - {num_ia} vs {expected_count} events")

                # Check alpha_at_interim consistency
                alpha_interim = data.get('alpha_at_interim', [])
                if alpha_interim and isinstance(alpha_interim, list):
                    if len(alpha_interim) != num_ia:
                        notes.append(f"VALIDATION: alpha_at_interim has {len(alpha_interim)} values but num_interim_analyses={num_ia}")

                # Check event_triggers - only warn, don't require (some IAs are calendar-based)
                event_triggers = data.get('event_triggers', [])
                if not event_triggers or len(event_triggers) == 0:
                    # This is informational, not an error - some trials use calendar time
                    pass  # Don't warn, event triggers are optional
                elif len(event_triggers) < num_ia:
                    notes.append(f"VALIDATION: {len(event_triggers)} event_triggers for {num_ia} interim analyses - some may be calendar-based")

                # Validate alpha spending function consistency
                alpha_spending_fn = data.get('alpha_spending_function')
                spending_params = data.get('spending_parameters', {})
                if alpha_spending_fn and 'NOT FOUND' not in str(alpha_spending_fn):
                    if not spending_params or spending_params == {}:
                        notes.append(f"VALIDATION: alpha_spending_function '{alpha_spending_fn}' found but no spending_parameters")

        # =========================================================
        # TREATMENT SETTING VALIDATION
        # =========================================================
        if section_name == 'study_design':
            treatment_setting = data.get('treatment_setting', '')

            # Check for common misclassifications in the notes
            raw_notes = data.get('notes', [])
            if isinstance(raw_notes, list):
                notes_text = ' '.join(str(n) for n in raw_notes).lower()

                # If notes mention "first-line" but setting says second-line, flag it
                if 'first-line' in notes_text or 'first line' in notes_text:
                    if treatment_setting and 'second' in treatment_setting.lower():
                        notes.append("VALIDATION WARNING: Notes mention 'first-line' but setting extracted as second-line")

        # =========================================================
        # MULTIPLICITY VALIDATION
        # =========================================================
        if section_name == 'multiplicity':
            has_multiplicity = data.get('has_multiplicity', False)

            # Skip detailed validation if no multiplicity (valid for many study types)
            if not has_multiplicity:
                # This is valid for Phase 2 single-arm, exploratory studies, etc.
                # Don't flag missing fields as errors
                notes.append("VALIDATION: No multiplicity adjustment needed for this study design")
            else:
                # Only validate multiplicity details if multiplicity exists
                hypotheses = data.get('hypotheses_list', [])
                alpha_per = data.get('alpha_per_hypothesis', {})

                # Check if number of hypotheses matches alpha allocations
                if hypotheses and alpha_per:
                    if len(hypotheses) != len(alpha_per):
                        notes.append(f"VALIDATION: {len(hypotheses)} hypotheses but {len(alpha_per)} alpha allocations")

                # Check that total alpha doesn't exceed 0.025 (one-sided) or 0.05 (two-sided)
                if alpha_per and isinstance(alpha_per, dict):
                    total_alpha = sum(v for v in alpha_per.values() if isinstance(v, (int, float)))
                    if total_alpha > 0.03:  # Allow small rounding errors
                        notes.append(f"VALIDATION WARNING: total initial alpha={total_alpha:.4f} exceeds expected 0.025")

            # Validate NI margin exists when NI testing is mentioned
            ni_endpoint = data.get('ni_endpoint')
            ni_margin = data.get('ni_margin')
            ni_then_superiority = data.get('ni_then_superiority')

            if ni_endpoint and 'NOT FOUND' not in str(ni_endpoint):
                if not ni_margin:
                    notes.append(f"VALIDATION WARNING: ni_endpoint='{ni_endpoint}' but no ni_margin extracted - critical for NI testing")
                elif ni_margin < 1.0:
                    # Could be risk difference margin (e.g., 0.10 for 10% difference) vs HR
                    if ni_margin > 0.5:
                        notes.append(f"VALIDATION INFO: ni_margin={ni_margin} - verify if this is HR or risk difference margin")
                    elif ni_margin > 0:
                        # Values like 0.05-0.15 are typical risk difference margins
                        notes.append(f"VALIDATION INFO: ni_margin={ni_margin} appears to be risk difference (not HR)")
                    else:
                        notes.append(f"VALIDATION WARNING: ni_margin={ni_margin} is unusually small or invalid")
                elif ni_margin > 2.0:
                    notes.append(f"VALIDATION WARNING: ni_margin={ni_margin} is unusually large for HR-based NI (expected 1.1-1.5)")

            if ni_then_superiority and not ni_margin:
                notes.append(f"VALIDATION WARNING: ni_then_superiority=True but no ni_margin extracted")

            # Validate efficacy boundaries structure
            efficacy_boundaries = data.get('efficacy_boundaries', [])
            if efficacy_boundaries and isinstance(efficacy_boundaries, list):
                for i, boundary in enumerate(efficacy_boundaries):
                    if isinstance(boundary, dict):
                        if 'information_fraction' not in boundary and 'z_score' not in boundary:
                            notes.append(f"VALIDATION: efficacy_boundaries[{i}] missing key fields (information_fraction, z_score)")
                        # Info fraction should be between 0 and 1
                        info_frac = boundary.get('information_fraction')
                        if info_frac and (info_frac < 0 or info_frac > 1):
                            notes.append(f"VALIDATION WARNING: efficacy_boundaries[{i}] has invalid information_fraction={info_frac}")

        # =========================================================
        # CENSORING RULES VALIDATION
        # =========================================================
        if section_name == 'missing_data':
            censoring = data.get('censoring_rules', [])

            # Censoring rules should be a list, not a string
            if isinstance(censoring, str):
                if censoring and '[NOT FOUND]' not in censoring:
                    data['censoring_rules'] = [censoring]
                    notes.append("VALIDATION: Converted censoring_rules from string to list")

        # =========================================================
        # STRATIFICATION VALIDATION
        # =========================================================
        if section_name == 'stratification':
            factors = data.get('stratification_factors', [])
            factor_levels = data.get('stratification_factor_levels', {})
            num_strata = data.get('num_strata')

            # Calculate expected strata from factor_levels dict
            # Structure: {"Region": ["East Asia", "ROW"], "ECOG": ["0", "1"], ...}
            if factor_levels and isinstance(factor_levels, dict) and len(factor_levels) > 0:
                expected_strata = 1
                for factor_name, levels in factor_levels.items():
                    if isinstance(levels, list) and len(levels) > 0:
                        expected_strata *= len(levels)

                if num_strata and num_strata != expected_strata:
                    notes.append(f"VALIDATION: num_strata={num_strata} vs calculated {expected_strata} from factor levels")

                if not num_strata:
                    # Auto-calculate num_strata if not extracted
                    data['num_strata'] = expected_strata
                    notes.append(f"VALIDATION: Calculated num_strata={expected_strata} from {len(factor_levels)} factors")

            # Validate stratification method presence
            strat_method = data.get('stratification_method')
            if factors and len(factors) > 0 and not strat_method:
                notes.append("VALIDATION: stratification_factors found but no stratification_method - check if IVRS/IWRS mentioned")

        return data, notes

    def _parse_section_response(
        self,
        section_name: str,
        response_text: str
    ) -> SectionExtractionResult:
        """Parse LLM response for a section."""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                raise ValueError("No JSON found in response")

            data = json.loads(json_match.group())

            # =========================================================
            # VALIDATION: Catch and fix obvious extraction errors
            # =========================================================
            data, validation_notes = self._validate_extracted_data(section_name, data)

            # Analyze what was found vs not found
            section_def = self.SECTIONS[section_name]
            required = section_def.get('required', [])
            critical = section_def.get('critical', [])

            fields_found = []
            fields_not_found = []
            needs_review = []

            for field in required + section_def.get('optional', []):
                value = data.get(field)

                if value is None or value == "" or value == [] or value == {}:
                    fields_not_found.append(field)
                    if field in critical:
                        needs_review.append(field)
                elif isinstance(value, str) and '[NOT FOUND]' in value:
                    fields_not_found.append(field)
                    if field in critical:
                        needs_review.append(field)
                elif isinstance(value, str) and '[NEEDS REVIEW]' in value:
                    needs_review.append(field)
                    fields_found.append(field)
                else:
                    fields_found.append(field)

            # Combine extraction notes with validation notes
            all_notes = data.get('notes', []) + validation_notes

            return SectionExtractionResult(
                section_name=section_name,
                extracted_fields=data,
                confidence=data.get('confidence', 0.5),
                fields_found=fields_found,
                fields_not_found=fields_not_found,
                needs_review=needs_review,
                notes=all_notes
            )

        except json.JSONDecodeError as e:
            return SectionExtractionResult(
                section_name=section_name,
                extracted_fields={},
                confidence=0.0,
                fields_found=[],
                fields_not_found=[],
                needs_review=[],
                notes=[f"JSON parse error: {str(e)}"]
            )

    def extract_all_sections(
        self,
        protocol_text: str,
        sections: Optional[List[str]] = None,
        pdf_path: Optional[str] = None,
        parallel: bool = True,
        max_workers: int = 10
    ) -> Tuple[ExtractedProtocolFacts, Dict[str, SectionExtractionResult]]:
        """
        Extract all sections from a protocol.

        Args:
            protocol_text: Full protocol text
            sections: Optional list of sections to extract (default: all)
            pdf_path: Path to PDF file for Vision-based section parsing
            parallel: If True, extract sections in parallel (MUCH faster)
            max_workers: Number of parallel workers (default 10)

        Returns:
            Tuple of (ExtractedProtocolFacts, dict of section results)
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Store PDF path for Vision-based parsing
        self._current_pdf_path = pdf_path
        if pdf_path:
            print(f"[SectionedExtractor] PDF path provided: {pdf_path}")

        # =====================================================================
        # CRITICAL FIX: Pre-parse PDF ONCE before parallel extraction
        # This prevents multiple LlamaParse calls (rate limiting + event loop issues)
        # ALSO: Must re-parse if PDF path changed from previous request!
        # =====================================================================
        needs_preparse = False
        if pdf_path:
            if self._parsed_protocol is None:
                needs_preparse = True
                print(f"[SectionedExtractor] PRE-PARSING: No cached parse result")
            elif self._cached_pdf_path != pdf_path:
                needs_preparse = True
                print(f"[SectionedExtractor] PRE-PARSING: PDF changed ({self._cached_pdf_path} -> {pdf_path})")

        if needs_preparse:
            print(f"[SectionedExtractor] PRE-PARSING PDF before parallel extraction...")
            self._parsed_protocol = self.section_parser.parse(
                protocol_text,
                pdf_path=pdf_path
            )
            self._cached_pdf_path = pdf_path
            self._cached_text_hash = str(hash(protocol_text[:1000])) if protocol_text else None
            print(f"[SectionedExtractor] Pre-parsed into {len(self._parsed_protocol.sections)} sections: {list(self._parsed_protocol.sections.keys())}")
        elif pdf_path:
            print(f"[SectionedExtractor] Using CACHED pre-parse result ({len(self._parsed_protocol.sections)} sections)")

        if sections is None:
            sections = list(self.SECTIONS.keys())

        section_results = {}
        combined_data = {}

        if parallel:
            # PARALLEL EXTRACTION - ~10x faster
            print(f"[SectionedExtractor] Parallel extraction: {len(sections)} sections with {max_workers} workers")

            def extract_one(section_name: str) -> Tuple[str, SectionExtractionResult]:
                """Extract one section (thread-safe)."""
                result = self.extract_section(section_name, protocol_text)
                return section_name, result

            # Set flag to prevent re-parsing in worker threads
            self._in_parallel_extraction = True
            try:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(extract_one, s): s for s in sections}

                    for future in as_completed(futures):
                        section_name = futures[future]
                        try:
                            name, result = future.result()
                            section_results[name] = result

                            # Merge extracted fields
                            for field, value in result.extracted_fields.items():
                                if field not in ['confidence', 'notes']:
                                    combined_data[field] = value

                            conf = result.confidence if result.confidence is not None else 0.0
                            print(f"[SectionedExtractor] ✓ {name} ({conf:.0%})")
                        except Exception as e:
                            print(f"[SectionedExtractor] ✗ {section_name}: {e}")
            finally:
                # Always clear the flag, even if extraction fails
                self._in_parallel_extraction = False
        else:
            # SEQUENTIAL EXTRACTION (fallback)
            for section_name in sections:
                print(f"[SectionedExtractor] Extracting: {section_name}")
                result = self.extract_section(section_name, protocol_text)
                section_results[section_name] = result

                # Merge extracted fields
                for field, value in result.extracted_fields.items():
                    if field not in ['confidence', 'notes']:
                        combined_data[field] = value

                conf = result.confidence if result.confidence is not None else 0.0
                print(f"  - Confidence: {conf:.0%}")
                print(f"  - Found: {len(result.fields_found)} fields")
                print(f"  - Not found: {len(result.fields_not_found)} fields")
                if result.needs_review:
                    print(f"  - NEEDS REVIEW: {result.needs_review}")

        # Convert to ExtractedProtocolFacts
        facts = from_claude_extraction(combined_data)

        # Calculate overall confidence (handle None values)
        if section_results:
            valid_confidences = [r.confidence for r in section_results.values() if r.confidence is not None]
            facts.confidence.overall_confidence = sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0.0

            facts.confidence.section_confidence = {
                name: r.confidence for name, r in section_results.items()
            }

            facts.confidence.needs_review = []
            facts.confidence.not_found = []
            for r in section_results.values():
                facts.confidence.needs_review.extend(r.needs_review)
                facts.confidence.not_found.extend(r.fields_not_found)

        return facts, section_results


def create_sectioned_extractor(llm_client=None) -> SectionedProtocolExtractor:
    """Factory function for sectioned extractor."""
    return SectionedProtocolExtractor(llm_client=llm_client)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Sectioned Protocol Extractor")
    print("=" * 60)

    # Test section prompts
    extractor = SectionedProtocolExtractor()

    print(f"\nSections defined: {len(extractor.SECTIONS)}")
    for section in extractor.SECTIONS:
        section_def = extractor.SECTIONS[section]
        print(f"  {section}:")
        print(f"    - Required: {len(section_def.get('required', []))} fields")
        print(f"    - Optional: {len(section_def.get('optional', []))} fields")
        print(f"    - Critical: {section_def.get('critical', [])}")
