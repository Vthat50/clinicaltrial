#!/usr/bin/env python3
"""
LLM-Based Section Generator for SAP
====================================

This module ACTUALLY uses LLM to generate SAP sections.
No templates. No hardcoded content. Real LLM synthesis.

For each section:
1. Retrieve relevant examples from RAG
2. Build a prompt with facts + examples
3. Call LLM to generate section content
4. Validate and return

This replaces the fake "RAG" generators that were just templates.
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# Import the tiered LLM client
from .tiered_llm import get_tiered_client, TieredLLMClient, LLMResponse


@dataclass
class GeneratedSection:
    """Result from LLM section generation"""
    content: str
    section_name: str
    llm_source: str  # claude, openai, groq
    rag_examples_used: List[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


class LLMSectionGenerator:
    """
    Generates SAP sections using actual LLM calls.

    Uses RAG examples as few-shot examples for the LLM,
    NOT for regex pattern matching.
    """

    def __init__(self, rag_adapter=None):
        """
        Initialize with optional RAG adapter for retrieving examples.

        Args:
            rag_adapter: HybridRAGAdapter instance for retrieving similar SAP sections
        """
        self.rag_adapter = rag_adapter
        self.llm_client: TieredLLMClient = get_tiered_client()

    def _retrieve_examples(
        self,
        section_type: str,
        facts: Dict[str, Any],
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """Retrieve RAG examples for a section type."""
        if not self.rag_adapter:
            print(f"[LLM Generator] No RAG adapter - generating {section_type} without examples")
            return []

        try:
            examples = self.rag_adapter.retrieve_for_section(
                section_type=section_type,
                protocol_data=facts,
                n_results=n_results
            )
            if examples:
                print(f"[LLM Generator] Retrieved {len(examples)} examples for {section_type}")
            return examples
        except Exception as e:
            print(f"[LLM Generator] Error retrieving examples: {e}")
            return []

    def _format_examples_for_prompt(self, examples: List[Dict[str, Any]], max_chars: int = 4000) -> str:
        """Format RAG examples for inclusion in LLM prompt."""
        if not examples:
            return "No similar examples available."

        formatted = []
        total_chars = 0

        for i, ex in enumerate(examples, 1):
            content = ex.get('content', '')
            nct_id = ex.get('nct_id', 'Unknown')

            # Truncate if needed
            if len(content) > 1500:
                content = content[:1500] + "..."

            if total_chars + len(content) > max_chars:
                break

            formatted.append(f"=== Example {i} (from {nct_id}) ===\n{content}")
            total_chars += len(content)

        return "\n\n".join(formatted)

    # =========================================================================
    # STUDY TYPE DETECTION - NO DEFAULTS, CHECK MULTIPLE SIGNALS
    # =========================================================================

    def _detect_single_arm(self, facts: Dict[str, Any]) -> bool:
        """
        Detect if this is a single-arm study from multiple signals.
        NO DEFAULT - must be explicitly determined.
        """
        # Direct extraction (most reliable)
        if facts.get('is_single_arm') is True:
            return True
        if facts.get('is_single_arm') is False:
            return False

        # Check num_arms
        num_arms = facts.get('num_arms')
        if num_arms == 1:
            return True
        if num_arms and num_arms > 1:
            return False

        # Check for signals of single-arm
        comparator = str(facts.get('comparator', '')).lower()
        if comparator in ['none', 'none - single arm', 'n/a', 'na', '']:
            return True
        if 'single' in comparator and 'arm' in comparator:
            return True

        # Check allocation (non-randomized = often single-arm)
        allocation = str(facts.get('allocation_type', '')).lower()
        if 'non_randomized' in allocation or 'non-randomized' in allocation:
            return True

        # Check design type
        design = str(facts.get('design_type', '')).lower()
        if 'single-arm' in design or 'single arm' in design or 'one arm' in design:
            return True

        # Default: assume randomized (safer for regulatory)
        return False

    def _detect_pilot_study(self, facts: Dict[str, Any]) -> bool:
        """
        Detect if this is a pilot/feasibility study from multiple signals.
        NO DEFAULT - must be explicitly determined.
        """
        # Direct extraction (most reliable)
        if facts.get('is_pilot_study') is True:
            return True
        if facts.get('is_pilot_study') is False:
            return False

        # Check sample size justification type
        justification = str(facts.get('sample_size_justification_type', '')).lower()
        if justification in ['pragmatic', 'feasibility', 'exploratory']:
            return True

        # Check is_pragmatic_sample flag
        if facts.get('is_pragmatic_sample') is True:
            return True

        # Check sample size rationale text
        rationale = str(facts.get('sample_size_rationale', '')).lower()
        if any(x in rationale for x in ['pilot', 'feasibility', 'exploratory', 'pragmatic', 'no formal']):
            return True

        # Check phase (Phase 1, early Phase 2 often exploratory)
        phase = str(facts.get('phase', '')).lower()
        if 'phase 1' in phase or 'phase1' in phase:
            return True

        # Check small sample size without power (N <= 50)
        sample_size = facts.get('sample_size')
        if isinstance(sample_size, (int, float)) and sample_size <= 50:
            power = facts.get('power')
            if power is None or power == '[NOT FOUND]':
                return True

        # Check design type
        design = str(facts.get('design_type', '')).lower()
        if any(x in design for x in ['pilot', 'feasibility', 'exploratory']):
            return True

        # Default: assume confirmatory (safer for regulatory)
        return False

    def _detect_hypothesis_testing(self, facts: Dict[str, Any]) -> bool:
        """
        Detect if formal hypothesis testing is planned from multiple signals.
        NO DEFAULT - must be explicitly determined.
        """
        # Direct extraction (most reliable)
        if facts.get('hypothesis_testing_planned') is False:
            return False
        if facts.get('hypothesis_testing_planned') is True:
            return True

        # If pilot study, likely no hypothesis testing
        if self._detect_pilot_study(facts):
            return False

        # Check statistical method mentions
        method = str(facts.get('statistical_method', '')).lower()
        if 'descriptive' in method and 'only' in method:
            return False
        if 'no statistical test' in method or 'no formal test' in method:
            return False

        # Check sample size rationale
        rationale = str(facts.get('sample_size_rationale', '')).lower()
        if 'no hypothesis' in rationale or 'descriptive' in rationale:
            return False

        # Check for presence of hypothesis/power (implies testing planned)
        if facts.get('power') and facts.get('alpha_level'):
            return True

        # Default: assume hypothesis testing (safer for regulatory)
        return True

    def _detect_interim_analysis(self, facts: Dict[str, Any]) -> bool:
        """
        Detect if interim analysis is planned from multiple signals.
        NO DEFAULT - must be explicitly determined from protocol.
        """
        # Direct extraction (most reliable)
        if facts.get('has_interim_analysis') is True:
            return True
        if facts.get('has_interim_analysis') is False:
            return False

        # Check for interim-related fields populated
        if facts.get('num_interim_analyses') and facts.get('num_interim_analyses') > 0:
            return True
        if facts.get('interim_events') and len(facts.get('interim_events', [])) > 0:
            return True
        if facts.get('alpha_spending_function'):
            return True
        if facts.get('interim_analysis_method'):
            return True
        if facts.get('interim_information_fraction'):
            return True

        # Check for mentions in protocol text fields
        stat_method = str(facts.get('statistical_method_details', '')).lower()
        if 'interim' in stat_method or 'group sequential' in stat_method:
            return True

        # Default: no interim analysis (don't assume it's planned)
        return False

    def _detect_hierarchical_testing(self, facts: Dict[str, Any]) -> bool:
        """
        Detect if hierarchical/sequential testing is planned.
        NO DEFAULT - must be explicitly determined from protocol.
        """
        # Direct extraction (most reliable)
        if facts.get('has_hierarchical_testing') is True:
            return True
        if facts.get('has_hierarchical_testing') is False:
            return False

        # Check for hierarchical testing fields
        if facts.get('hierarchical_testing_order') and len(facts.get('hierarchical_testing_order', [])) > 0:
            return True
        if facts.get('hierarchical_testing_description'):
            return True
        if facts.get('testing_sequence') and len(facts.get('testing_sequence', [])) > 1:
            return True

        # Check multiplicity method
        mult_method = str(facts.get('multiplicity_method', '')).lower()
        if any(x in mult_method for x in ['hierarchical', 'sequential', 'fixed-sequence', 'gatekeeping']):
            return True

        # Check endpoint testing hierarchy
        if facts.get('endpoint_testing_hierarchy') and len(facts.get('endpoint_testing_hierarchy', [])) > 1:
            return True

        # Default: no hierarchical testing
        return False

    def _detect_consistency_objective(self, facts: Dict[str, Any]) -> bool:
        """
        Detect if consistency analysis is part of objectives (bridging studies).
        NO DEFAULT - must be explicitly determined from protocol.
        """
        # Direct extraction (most reliable)
        if facts.get('has_consistency_objective') is True:
            return True
        if facts.get('has_consistency_objective') is False:
            return False

        # Check for bridging/MRCT study
        if facts.get('is_bridging_study') is True or facts.get('is_mrct') is True:
            return True

        # Check for consistency-related fields
        if facts.get('consistency_type'):
            return True
        if facts.get('consistency_margin'):
            return True
        if facts.get('consistency_reference_studies') and len(facts.get('consistency_reference_studies', [])) > 0:
            return True
        if facts.get('consistency_test_description'):
            return True

        # Default: no consistency objective
        return False

    def _detect_consistency_is_primary(self, facts: Dict[str, Any]) -> bool:
        """
        Detect if consistency is a PRIMARY objective (vs secondary).
        NO DEFAULT - must be explicitly determined from protocol.
        """
        # Direct extraction (most reliable)
        if facts.get('consistency_is_primary') is True:
            return True
        if facts.get('consistency_is_primary') is False:
            return False

        # Check if bridging study with two-step testing (consistency first)
        if facts.get('is_bridging_study') is True:
            hierarchy = facts.get('hierarchical_testing_description', '').lower()
            if 'consistency' in hierarchy and ('first' in hierarchy or 'primary' in hierarchy):
                return True

        # Default: if consistency exists, check if it's mentioned as primary
        if self._detect_consistency_objective(facts):
            primary_obj = str(facts.get('primary_objective', '')).lower()
            if 'consistency' in primary_obj:
                return True

        return False

    def _detect_regulatory_interim(self, facts: Dict[str, Any]) -> bool:
        """
        Detect if regulatory interim analysis is planned (e.g., TTF for China).
        NO DEFAULT - must be explicitly determined from protocol.
        """
        # Direct extraction (most reliable)
        if facts.get('has_regulatory_interim') is True:
            return True
        if facts.get('has_regulatory_interim') is False:
            return False

        # Check for regulatory interim fields
        if facts.get('regulatory_interim_endpoint'):
            return True
        if facts.get('regulatory_interim_region'):
            return True
        if facts.get('regulatory_interim_timing'):
            return True

        # Check for TTF-specific fields (common in China filings)
        if facts.get('ttf_endpoint') or facts.get('ttf_analysis'):
            return True

        # Check for China-specific filing support
        regions = facts.get('regional_regulatory_requirements', [])
        if isinstance(regions, list) and any('china' in str(r).lower() for r in regions):
            return True

        # Default: no regulatory interim
        return False

    def _detect_pro_endpoint(self, facts: Dict[str, Any]) -> bool:
        """
        Detect if PRO (Patient-Reported Outcomes) endpoints exist.
        NO DEFAULT - must be explicitly determined from protocol.
        """
        # Direct extraction (most reliable)
        if facts.get('has_pro_endpoint') is True:
            return True
        if facts.get('has_pro_endpoint') is False:
            return False

        # Check for PRO-related fields
        if facts.get('pro_endpoints') and len(facts.get('pro_endpoints', [])) > 0:
            return True
        if facts.get('pro_instruments') and len(facts.get('pro_instruments', [])) > 0:
            return True
        if facts.get('qol_endpoints') and len(facts.get('qol_endpoints', [])) > 0:
            return True

        # Check secondary endpoints for PRO/QOL mentions
        secondary = facts.get('secondary_endpoints', [])
        if isinstance(secondary, list):
            for ep in secondary:
                ep_str = str(ep).lower()
                if any(x in ep_str for x in ['pro', 'qol', 'quality of life', 'patient reported',
                                               'eortc', 'eq-5d', 'fact-', 'sf-36', 'facit']):
                    return True

        # Check primary endpoint
        primary = str(facts.get('primary_endpoint', '')).lower()
        if any(x in primary for x in ['pro', 'qol', 'quality of life', 'patient reported']):
            return True

        # Default: no PRO endpoints
        return False

    def _format_facts_for_prompt(self, facts: Dict[str, Any]) -> str:
        """
        Format protocol facts for LLM prompt.

        UPDATED 2025-01: Now uses ALL 229 fields from extraction schema.
        Organized by category for readability.
        """
        # Human-readable labels for all schema fields
        # Organized by category to match extraction_schema.py sections
        field_labels = {
            # === CORE DESIGN ===
            'nct_id': 'NCT ID',
            'protocol_number': 'Protocol Number',
            'sponsor': 'Sponsor',
            'drug_name': 'Study Drug',
            'comparator': 'Comparator',
            'phase': 'Phase',
            'design_type': 'Study Design',
            'sample_size': 'Sample Size',
            'allocation_ratio': 'Randomization Ratio',
            'stratification_factors': 'Stratification Factors',
            'treatment_setting': 'Treatment Setting',
            'disease_type': 'Disease Type',
            'tumor_type': 'Tumor Type',
            'histology': 'Histology',
            'disease_stage': 'Disease Stage',
            'biomarker_status': 'Biomarker Status',
            'stratification_factor_levels': 'Stratification Factor Levels',

            # === ENDPOINTS ===
            'primary_endpoint': 'Primary Endpoint',
            'secondary_endpoints': 'Secondary Endpoints',
            'is_co_primary': 'Co-Primary Endpoints',
            'co_primary_endpoints': 'Co-Primary Endpoint List',
            'endpoint_testing_hierarchy': 'Endpoint Testing Hierarchy',

            # === ESTIMAND (ICH E9 R1) ===
            'estimand_population': 'Estimand Population',
            'estimand_variable': 'Estimand Variable',
            'intercurrent_events': 'Intercurrent Events',
            'primary_estimand': 'Primary Estimand',

            # === INTERIM ANALYSIS ===
            'has_interim_analysis': 'Interim Analysis Planned',
            'num_interim_analyses': 'Number of Interim Analyses',
            'interim_events': 'Events at Interim Analyses',
            'final_events': 'Events at Final Analysis',
            'information_fractions': 'Information Fractions',
            'alpha_spending_function': 'Alpha Spending Function',
            'overall_alpha': 'Overall Alpha',
            'alpha_sidedness': 'Alpha Sidedness',
            'alpha_at_interim': 'Alpha at Interim',
            'alpha_at_final': 'Alpha at Final',
            'stopping_boundaries': 'Stopping Boundaries',
            'interim_by_endpoint': 'Interim by Endpoint',

            # === STATISTICAL METHODS ===
            'primary_test': 'Primary Statistical Test',
            'statistical_method': 'Statistical Method',
            'expected_hazard_ratio': 'Expected Hazard Ratio',
            'power': 'Statistical Power',
            'sensitivity_analyses': 'Sensitivity Analyses',
            'subgroup_analyses': 'Subgroup Analyses',
            'null_hypothesis': 'Null Hypothesis',
            'alternative_hypothesis': 'Alternative Hypothesis',

            # === MULTIPLICITY ===
            'multiplicity_method': 'Multiplicity Adjustment Method',
            'testing_sequence': 'Testing Sequence',
            'alpha_per_hypothesis': 'Alpha per Hypothesis',
            'hypotheses_list': 'Hypotheses List',
            'graphical_weights': 'Graphical Weights',
            'graphical_transitions': 'Graphical Transitions',

            # === MISSING DATA ===
            'treatment_discontinuation_strategy': 'Treatment Discontinuation Strategy',
            'censoring_rules': 'Censoring Rules',
            'tipping_point_analysis': 'Tipping Point Analysis',

            # === CROSSOVER ===
            'has_crossover': 'Crossover Permitted',
            'crossover_adjustment_methods': 'Crossover Adjustment Methods',

            # === POPULATIONS ===
            'itt_definition': 'ITT Definition',
            'fas_definition': 'FAS Definition',
            'safety_definition': 'Safety Population Definition',

            # === BRIDGING STUDY (ICH E5, E17) ===
            'is_bridging_study': 'BRIDGING STUDY',
            'is_mrct': 'Multi-Regional Clinical Trial (MRCT)',
            'bridging_region': 'Bridging Region',
            'reference_studies': 'Reference Studies (Global Trials)',
            'consistency_testing_required': 'Consistency Testing Required',
            'consistency_hr_threshold_interim': 'Consistency HR Threshold (Interim)',
            'consistency_hr_threshold_final': 'Consistency HR Threshold (Final)',
            'hierarchical_testing_steps': 'Hierarchical Testing Steps',
            'ethnic_sensitivity_assessment': 'Ethnic Sensitivity Assessment',

            # === REGULATORY FILING ENDPOINTS (TTF, etc.) ===
            'has_early_filing_endpoint': 'Early Filing Endpoint Planned',
            'filing_endpoint_name': 'Filing Endpoint Name (e.g., TTF)',
            'filing_endpoint_definition': 'Filing Endpoint Definition',
            'filing_regulatory_authority': 'Filing Regulatory Authority',
            'filing_target_subjects': 'Filing Target Subjects',
            'filing_minimum_followup_months': 'Filing Minimum Follow-up (months)',
            'filing_statistical_test': 'Filing Statistical Test',
            'filing_alpha': 'Filing Alpha',

            # === SECONDARY ENDPOINT ANALYSES ===
            'orr_analysis_method': 'ORR Analysis Method',
            'orr_ci_method': 'ORR CI Method',
            'pfs_analysis_method': 'PFS Analysis Method',
            'dor_analysis_method': 'DOR Analysis Method',

            # === SUBGROUP SPECIFICATIONS ===
            'forest_plot_planned': 'Forest Plot Planned',
            'forest_plot_variables': 'Forest Plot Variables',
            'multivariate_cox_planned': 'Multivariate Cox Planned',
            'multivariate_cox_covariates': 'Multivariate Cox Covariates',
            'landmark_analysis_planned': 'Landmark Analysis Planned',
            'landmark_timepoints': 'Landmark Timepoints',
            'waterfall_plot_planned': 'Waterfall Plot Planned',
            'swimmer_plot_planned': 'Swimmer Plot Planned',

            # === BASELINE CHARACTERISTICS ===
            'baseline_demographic_variables': 'Baseline Demographic Variables',
            'baseline_disease_variables': 'Baseline Disease Variables',
            'baseline_molecular_variables': 'Baseline Molecular Variables',
            'baseline_prior_therapy_variables': 'Baseline Prior Therapy Variables',
            'baseline_performance_status_variables': 'Baseline Performance Status Variables',

            # === DATE IMPUTATION RULES ===
            'death_date_imputation': 'Death Date Imputation Rule',
            'progression_date_imputation': 'Progression Date Imputation Rule',
            'ae_start_date_imputation': 'AE Start Date Imputation Rule',
            'duration_calculation_formula': 'Duration Calculation Formula',
            'days_per_month': 'Days per Month',
            'days_per_year': 'Days per Year',

            # === EXPOSURE FORMULAS (RDI) ===
            'rdi_formula_experimental': 'RDI Formula (Experimental)',
            'rdi_formula_control': 'RDI Formula (Control)',
            'planned_dose_experimental': 'Planned Dose (Experimental)',
            'planned_dose_control': 'Planned Dose (Control)',
            'dose_delay_threshold_days': 'Dose Delay Threshold (days)',
            'dose_reduction_levels': 'Dose Reduction Levels',
            'cycle_length_experimental_days': 'Cycle Length Experimental (days)',
            'cycle_length_control_days': 'Cycle Length Control (days)',

            # === STUDY CONDUCT ===
            'deviation_categories': 'Protocol Deviation Categories',
            'programmable_deviations': 'Programmable Deviations',
            'accrual_summary_by': 'Accrual Summary By',
            'stratification_discrepancy_analysis': 'Stratification Discrepancy Analysis',

            # === CDISC VERSIONING ===
            'sdtm_ig_version': 'SDTM-IG Version',
            'adam_ig_version': 'ADaM-IG Version',
            'define_xml_version': 'Define-XML Version',
            'ct_version': 'Controlled Terminology Version',
            'ct_freeze_date': 'CT Freeze Date',
            'ct_freeze_milestone': 'CT Freeze Milestone',
            'submission_type': 'Submission Type',
            'electronic_submission_format': 'Electronic Submission Format',

            # === MEDICAL CODING STANDARDS ===
            'meddra_version': 'MedDRA Version',
            'meddra_freeze_date': 'MedDRA Freeze Date',
            'meddra_freeze_milestone': 'MedDRA Freeze Milestone',
            'ae_coding_level': 'AE Coding Level',
            'whodrug_version': 'WHODrug Version',
            'whodrug_format': 'WHODrug Format',
            'whodrug_freeze_date': 'WHODrug Freeze Date',
            'atc_classification_level': 'ATC Classification Level',

            # === CONTROL GROUP RATIONALE (ICH E10) ===
            'control_type': 'Control Type',
            'control_justification': 'Control Justification',
            'active_control_drug': 'Active Control Drug',
            'active_control_dose': 'Active Control Dose',
            'ni_margin_justification': 'NI Margin Justification',
            'historical_trials_referenced': 'Historical Trials Referenced',

            # === GENOMIC SAMPLING (ICH E18) ===
            'sample_types_collected': 'Sample Types Collected',
            'genomic_collection_timepoints': 'Genomic Collection Timepoints',
            'prespecified_genomic_analyses': 'Pre-specified Genomic Analyses',
            'exploratory_genomic_analyses': 'Exploratory Genomic Analyses',
            'ngs_platform': 'NGS Platform',
            'gene_panel': 'Gene Panel',
            'ctdna_assay': 'ctDNA Assay',

            # === SAFETY ===
            'ae_coding_dictionary': 'AE Coding Dictionary',
            'ae_grading_scale': 'AE Grading Scale',
            'ae_collection_period': 'AE Collection Period',
            'teae_definition': 'TEAE Definition',
            'sae_definition': 'SAE Definition',
            'aesi_list': 'AESI List',
            'irae_categories': 'irAE Categories',
            'dose_reduction_rules': 'Dose Reduction Rules',
            'dose_discontinuation_rules': 'Dose Discontinuation Rules',

            # === TUMOR ASSESSMENT ===
            'response_criteria': 'Response Criteria',
            'assessment_schedule': 'Assessment Schedule',
            'assessment_method': 'Assessment Method',
            'bicr_primary': 'BICR Primary',
            'confirmation_required': 'Confirmation Required',
            'confirmation_window': 'Confirmation Window',
            'pseudoprogression_handling': 'Pseudoprogression Handling',
            'progression_date_definition': 'Progression Date Definition',

            # === PRO ===
            'pro_instruments': 'PRO Instruments',
            'pro_primary_endpoint': 'PRO Primary Endpoint',
            'pro_secondary_endpoints': 'PRO Secondary Endpoints',
            'time_to_deterioration': 'Time to Deterioration',
            'ttd_threshold': 'TTD Threshold',
            'pro_missing_data_handling': 'PRO Missing Data Handling',

            # === DMC ===
            'has_dmc': 'Has DMC',
            'dmc_review_frequency': 'DMC Review Frequency',
            'dmc_unblinded': 'DMC Unblinded',
            'safety_stopping_rules': 'Safety Stopping Rules',
            'futility_review_planned': 'Futility Review Planned',
            'futility_boundary': 'Futility Boundary',
        }

        lines = []

        # Process ALL facts, using labels where available
        for key, value in facts.items():
            # Skip empty values
            if value is None or value == '' or value == [] or value == {}:
                continue

            # Skip confidence/internal fields
            if key in ('extraction_confidence', 'needs_review', 'confidence'):
                continue

            # Get human-readable label or generate from key
            label = field_labels.get(key, key.replace('_', ' ').title())

            # Format the value
            if isinstance(value, list) and value and isinstance(value[0], dict):
                formatted_items = []
                for i, item in enumerate(value, 1):
                    if isinstance(item, dict):
                        defn = item.get('definition', item.get('name', str(item)))
                        formatted_items.append(f"  {i}. {defn}")
                    else:
                        formatted_items.append(f"  {i}. {item}")
                value = '\n' + '\n'.join(formatted_items)
            elif isinstance(value, dict):
                # Format dicts nicely
                dict_items = [f"    {k}: {v}" for k, v in value.items() if v]
                if dict_items:
                    value = '\n' + '\n'.join(dict_items)
                else:
                    continue
            elif isinstance(value, list):
                if len(value) > 0:
                    value = ', '.join(str(v) for v in value)
                else:
                    continue
            elif isinstance(value, bool):
                value = 'Yes' if value else 'No'

            lines.append(f"- {label}: {value}")

        return "\n".join(lines) if lines else "No protocol facts available."

    def generate_introduction(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Introduction section using LLM."""
        examples = self._retrieve_examples('introduction', facts, n_results=2)

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write a professional Introduction section for an SAP. Include:
1. Study identification (NCT ID, protocol number, title)
2. Purpose of the SAP
3. Scope of analyses covered
4. Regulatory alignment (mention ICH E9, ICH E9(R1))
5. Roles and responsibilities overview

Use the protocol facts provided. Write in formal scientific language.
Do NOT use placeholder text like [X] or [INSERT]. Use actual values from the facts.
If a value is missing, make a reasonable assumption or omit that detail."""

        user_prompt = f"""Write the Introduction section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

Write the Introduction section now. Start with "## 1. INTRODUCTION" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000
        )

        return GeneratedSection(
            content=response.content if response.success else "[LLM GENERATION FAILED - REQUIRES MANUAL REVIEW]",
            section_name="introduction",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_objectives(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Objectives/Estimands section using LLM."""
        examples = self._retrieve_examples('endpoints', facts, n_results=3)

        # Check for pilot study and co-primary endpoints
        # NO DEFAULTS - detect from multiple signals
        is_pilot_study = self._detect_pilot_study(facts)
        hypothesis_testing_planned = self._detect_hypothesis_testing(facts)
        primary_endpoints = facts.get('primary_endpoints', [])
        has_multiple_primary = len(primary_endpoints) > 1

        # Check for consistency as PRIMARY objective - NO DEFAULTS
        consistency_is_primary = self._detect_consistency_is_primary(facts)
        has_consistency = self._detect_consistency_objective(facts)

        # Build co-primary context
        coprimary_context = ""
        if has_multiple_primary:
            coprimary_context = f"""

CO-PRIMARY ENDPOINTS ({len(primary_endpoints)}):
This study has MULTIPLE co-primary endpoints. Create a separate PRIMARY OBJECTIVE for EACH endpoint.
Each co-primary endpoint requires its own estimand definition."""

        # Build consistency context - CRITICAL for regional studies
        consistency_context = ""
        if consistency_is_primary:
            ref_studies = facts.get('consistency_reference_studies', [])
            ref_effect = facts.get('consistency_reference_effect', '')
            margin = facts.get('consistency_margin', '')
            consistency_context = f"""

CRITICAL - CONSISTENCY IS A PRIMARY OBJECTIVE:
The PRIMARY objective of this study is to demonstrate consistency with prior studies.
Reference studies: {', '.join(ref_studies) if ref_studies else 'Global studies'}
Reference effect: {ref_effect if ref_effect else 'See protocol'}
Consistency margin: {margin if margin else 'Protocol-defined threshold'}

The hierarchy is:
1. FIRST PRIMARY: Demonstrate consistency with reference studies
2. SECOND PRIMARY: Demonstrate superiority of experimental vs comparator (only tested if consistency met)

Write the consistency objective as PRIMARY OBJECTIVE #1, not secondary."""
        elif has_consistency:
            consistency_context = """

Note: This study has a consistency objective (secondary). Include it after primary objectives."""

        if is_pilot_study or not hypothesis_testing_planned:
            system_prompt = f"""You are a biostatistician writing a Statistical Analysis Plan (SAP) for a PILOT/FEASIBILITY STUDY.

Write the Objectives section for a pilot study. Note:
- Pilot studies have EXPLORATORY objectives, not confirmatory
- The primary objective is typically to evaluate FEASIBILITY, SAFETY, or PRELIMINARY EFFICACY
- NO hypothesis testing is planned - objectives are descriptive

For pilot studies, objectives should focus on:
1. Feasibility of recruitment, treatment delivery, outcome assessment
2. Safety profile characterization
3. Preliminary efficacy signals (descriptive only)
4. Informing design of future confirmatory trials

Do NOT include formal estimands with hypothesis testing for pilot studies.
Instead, describe what will be ESTIMATED and DESCRIBED (not tested).
{coprimary_context}"""

            user_prompt = f"""Write the Objectives section for this PILOT/FEASIBILITY SAP.

CRITICAL: This is a pilot study. Objectives are EXPLORATORY and DESCRIPTIVE.
NO formal hypothesis testing will be performed.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

IMPORTANT:
- Frame objectives as exploratory/descriptive (e.g., "To evaluate...", "To describe...", "To assess feasibility of...")
- Do NOT include formal estimands with treatment effect summary measures
- Focus on feasibility, safety characterization, and preliminary efficacy estimates

Write the section now. Start with "## 2. OBJECTIVES" as the header."""

        else:
            # Standard confirmatory trial
            system_prompt = f"""You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Objectives and Estimands section following ICH E9(R1) guidelines.

For each objective, define the estimand with these 5 attributes:
1. Treatment: What treatments are being compared
2. Population: Target population for the analysis
3. Variable: The endpoint/outcome being measured
4. Intercurrent events: How to handle discontinuation, rescue therapy, death
5. Summary measure: How treatment effect is quantified (HR, OR, mean difference, etc.)

Use the actual comparator from the protocol - do NOT default to "placebo" unless it's actually a placebo-controlled study.
Write in formal scientific language with proper statistical terminology.
{coprimary_context}
{consistency_context}"""

            user_prompt = f"""Write the Objectives and Estimands section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

IMPORTANT:
- Use the actual comparator drug name, not "placebo" unless it IS a placebo study
- Follow ICH E9(R1) estimand framework exactly
- Include primary AND secondary objectives
- If there are CO-PRIMARY ENDPOINTS, create a separate objective and estimand for EACH
- If CONSISTENCY IS A PRIMARY OBJECTIVE, list it as PRIMARY OBJECTIVE #1 before the efficacy objective

Write the section now. Start with "## 2. OBJECTIVES AND ESTIMANDS" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2500
        )

        return GeneratedSection(
            content=response.content if response.success else "[LLM GENERATION FAILED - REQUIRES MANUAL REVIEW]",
            section_name="objectives",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_study_design(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Study Design section using LLM."""
        examples = self._retrieve_examples('study_design', facts, n_results=2)

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Study Design section including:
1. Study design type (randomized, open-label, double-blind, etc.)
2. Treatment arms and descriptions
3. Randomization scheme and ratio
4. Stratification factors
5. Blinding procedures (if applicable)
6. Study schema or flowchart description

Use the actual values from the protocol. Be specific about treatment arms."""

        user_prompt = f"""Write the Study Design section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

Write the section now. Start with "## 3. STUDY DESIGN" as the header.
Include a table showing treatment arms if multiple arms exist."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000
        )

        return GeneratedSection(
            content=response.content if response.success else "[LLM GENERATION FAILED - REQUIRES MANUAL REVIEW]",
            section_name="study_design",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_sample_size(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Sample Size section using LLM."""
        examples = self._retrieve_examples('methods', facts, n_results=3)

        # Check if this is a pilot/feasibility study - NO DEFAULTS
        is_pilot_study = self._detect_pilot_study(facts)
        hypothesis_testing_planned = self._detect_hypothesis_testing(facts)
        sample_size_justification = str(facts.get('sample_size_justification') or '').lower()

        # Determine if formal power calculation was done
        is_pragmatic = sample_size_justification in ['pragmatic', 'feasibility'] or \
                       'pragmatic' in sample_size_justification or \
                       'feasibility' in sample_size_justification

        if is_pilot_study or not hypothesis_testing_planned or is_pragmatic:
            system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP) for a PILOT/FEASIBILITY STUDY.

CRITICAL: This is a pilot study. NO FORMAL SAMPLE SIZE CALCULATION has been performed.

Write the Sample Size section including:
1. Statement that NO formal sample size estimation has been performed
2. Target sample size (pragmatically determined)
3. Rationale for the chosen sample size (feasibility, resource constraints, exploratory nature)
4. Statement that this is NOT powered for hypothesis testing
5. Note that this study is for feasibility/exploratory purposes

DO NOT include:
- Power calculations
- Effect size assumptions for testing
- Type I/II error specifications
- Dropout rate adjustments for power

Use phrases like:
- "No formal sample size estimation has been performed"
- "Target sample size of N=X is based on feasibility considerations"
- "This study is not powered for formal hypothesis testing"
- "Sample size was pragmatically determined" """

            user_prompt = f"""Write the Sample Size section for this PILOT/FEASIBILITY SAP.

CRITICAL: This is a pilot/feasibility study. NO FORMAL SAMPLE SIZE CALCULATION was performed.
Sample size was determined pragmatically for feasibility purposes.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

IMPORTANT:
- State that NO formal sample size estimation has been performed
- Explain that target sample size is based on feasibility/pragmatic considerations
- Do NOT include power calculations or effect size assumptions

Write the section now. Start with "## 6. SAMPLE SIZE" as the header (NOT "Sample Size and Power")."""

        else:
            # Standard confirmatory trial with power calculation
            system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Sample Size and Power section including:
1. Total sample size and per-arm breakdown
2. Primary endpoint for power calculation
3. Key assumptions (effect size, control rate, standard deviation)
4. Type I error (alpha) and power (1-beta)
5. Dropout/attrition rate adjustment
6. Justification and references for assumptions

Use actual values from the protocol. Show the calculation logic.
If sample size is provided, explain the justification.
If not provided, note that it should be calculated based on the primary endpoint."""

            user_prompt = f"""Write the Sample Size and Power section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs (showing how power calculations are justified):
{self._format_examples_for_prompt(examples)}

Write the section now. Start with "## 6. SAMPLE SIZE AND POWER" as the header.
Include an assumptions table."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000
        )

        return GeneratedSection(
            content=response.content if response.success else "[LLM GENERATION FAILED - REQUIRES MANUAL REVIEW]",
            section_name="sample_size",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_missing_data(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Missing Data section using LLM."""
        examples = self._retrieve_examples('methods', facts, n_results=2)

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Missing Data section including:
1. Missing data assumptions (MCAR, MAR, MNAR)
2. Primary analysis approach for handling missing data
3. Imputation methods if applicable (MI, LOCF, BOCF, MMRM)
4. Sensitivity analyses (tipping point, worst-case, best-case)
5. Missing data reporting requirements

Base the approach on the therapeutic area and endpoint type.
For efficacy trials: typically use MI or MMRM
For safety: typically use as-observed data"""

        user_prompt = f"""Write the Missing Data section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

Write the section now. Start with "## 9. MISSING DATA" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1500
        )

        return GeneratedSection(
            content=response.content if response.success else "[LLM GENERATION FAILED - REQUIRES MANUAL REVIEW]",
            section_name="missing_data",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_methods(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Statistical Methods section using LLM with RAG examples."""
        examples = self._retrieve_examples('methods', facts, n_results=3)

        # Check if this is a pilot/feasibility study - NO DEFAULTS
        is_pilot_study = self._detect_pilot_study(facts)
        hypothesis_testing_planned = self._detect_hypothesis_testing(facts)

        # Determine endpoint type for method selection
        primary_endpoint = str(facts.get('primary_endpoint', '')).lower()
        if any(x in primary_endpoint for x in ['survival', 'pfs', 'os', 'time to', 'tte']):
            endpoint_type = "time-to-event"
        elif any(x in primary_endpoint for x in ['response', 'rate', 'proportion', 'remission']):
            endpoint_type = "binary"
        else:
            endpoint_type = "continuous"

        # Different prompts for pilot vs confirmatory studies
        if is_pilot_study or not hypothesis_testing_planned:
            system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP) for a PILOT/FEASIBILITY STUDY.

CRITICAL: This is a pilot study with a small sample size. NO FORMAL HYPOTHESIS TESTING will be performed.

Write the Statistical Methods section including:
1. General statistical principles (descriptive statistics ONLY)
2. Statement that NO statistical hypothesis tests are performed due to small sample size
3. Descriptive analyses for all endpoints
4. For binary endpoints: proportions with 95% Wilson confidence intervals
5. For continuous endpoints: means, medians, standard deviations, ranges
6. For time-to-event endpoints: Kaplan-Meier estimates (descriptive only, no log-rank)
7. Subgroup analyses will be descriptive only

DO NOT include:
- p-values or hypothesis tests
- Power calculations or effect size estimations for future trials
- Multiplicity adjustments (not needed without hypothesis testing)
- Statistical comparisons between groups

Use phrases like:
- "No statistical tests are performed due to the small sample size"
- "All analyses will be descriptive"
- "Confidence intervals according to Wilson method for proportions"
- "Kaplan-Meier estimates for descriptive purposes only" """

            user_prompt = f"""Write the Statistical Methods section for this PILOT/FEASIBILITY SAP.

CRITICAL: This study has a SMALL SAMPLE SIZE ({facts.get('sample_size', 'N/A')} patients) and is designed as a PILOT/FEASIBILITY study.
NO FORMAL HYPOTHESIS TESTING is planned. All analyses are DESCRIPTIVE ONLY.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

ENDPOINT TYPE DETECTED: {endpoint_type}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

IMPORTANT:
- State explicitly that NO STATISTICAL TESTS are performed due to small sample size
- Use Wilson confidence intervals for proportions/event rates
- Kaplan-Meier for time-to-event but NO log-rank tests
- All analyses are descriptive (means, medians, proportions with CIs)

Write the section now. Start with "## 7. STATISTICAL METHODS" as the header."""

        else:
            # Standard confirmatory trial prompt
            # Check for protocol-specific statistical details - NO DEFAULTS
            stat_method = facts.get('statistical_method', '')
            stat_method_details = facts.get('statistical_method_details', '')
            has_interim = self._detect_interim_analysis(facts)
            interim_method = facts.get('interim_analysis_method', '')
            error_spending = facts.get('error_spending_function', '')
            alpha_spending_params = facts.get('alpha_spending_params', '')
            interim_events = facts.get('interim_events', [])
            interim_alpha_spent = facts.get('interim_alpha_spent', [])
            interim_info_fraction = facts.get('interim_information_fraction', [])
            final_events = facts.get('final_events')  # NO DEFAULT - use actual value or None
            stopping_boundaries = facts.get('stopping_boundaries', '')
            has_hierarchical = self._detect_hierarchical_testing(facts)
            hierarchical_order = facts.get('hierarchical_testing_order', [])
            hierarchical_desc = facts.get('hierarchical_testing_description', '')
            has_consistency = self._detect_consistency_objective(facts)
            consistency_type = facts.get('consistency_type', '')
            consistency_margin = facts.get('consistency_margin', '')
            consistency_refs = facts.get('consistency_reference_studies', [])
            consistency_ref_effect = facts.get('consistency_reference_effect', '')
            consistency_test_desc = facts.get('consistency_test_description', '')
            consistency_is_primary = self._detect_consistency_is_primary(facts)

            # Build interim analysis context - COMPREHENSIVE
            interim_context = ""
            if has_interim:
                interim_context = f"""
INTERIM ANALYSIS DESIGN - CRITICAL SECTION:
- Method: {interim_method}
- Error Spending Function: {error_spending}
- Alpha Spending Parameters: {alpha_spending_params}
- Number of Interim Analyses: {facts.get('num_interim_analyses', 1)}
- Events at Interim: {interim_events}
- Alpha Spent at Interim: {interim_alpha_spent}
- Information Fraction at Interim: {interim_info_fraction}
- Events at Final: {final_events}
- Stopping Boundaries: {stopping_boundaries}

YOU MUST include a detailed interim analysis subsection with:
1. The exact alpha-spending function and parameters
2. The number of events/deaths triggering each analysis
3. The alpha allocated at each look (e.g., 0.0001 at interim, 0.0499 at final)
4. The stopping boundaries (p-value thresholds)
5. Decision rules for stopping early"""

            # Build hierarchical testing context
            hierarchical_context = ""
            if has_hierarchical:
                hierarchical_context = f"""
HIERARCHICAL TESTING PROCEDURE - CRITICAL:
This study uses a hierarchical (gatekeeping) testing procedure.
- Testing Order: {' -> '.join(hierarchical_order) if hierarchical_order else 'Not specified'}
- Description: {hierarchical_desc}

YOU MUST describe:
1. The exact order in which hypotheses are tested
2. The rule for proceeding to the next test (only if previous passes)
3. How alpha is preserved across tests"""

            # Build consistency objective context - ENHANCED
            consistency_context = ""
            if has_consistency:
                primary_text = "PRIMARY" if consistency_is_primary else "SECONDARY"
                consistency_context = f"""
CONSISTENCY OBJECTIVE - THIS IS A {primary_text} OBJECTIVE:
This study has a CONSISTENCY OBJECTIVE with prior studies.
- Type: {consistency_type}
- Consistency Margin: {consistency_margin}
- Reference Studies: {', '.join(consistency_refs) if consistency_refs else 'Prior studies'}
- Reference Effect Size: {consistency_ref_effect}
- Test Description: {consistency_test_desc}

{'THIS IS A PRIMARY OBJECTIVE. Consistency must be demonstrated BEFORE the main efficacy hypothesis can be tested.' if consistency_is_primary else ''}

YOU MUST include:
1. A clear statement of the consistency hypothesis
2. How consistency is tested (e.g., upper bound of 95% CI < margin)
3. The consistency margin and its justification
4. The hierarchical relationship with other objectives"""

            system_prompt = f"""You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Statistical Methods section including:
1. General statistical principles (significance level, confidence intervals)
2. Primary endpoint analysis method (appropriate for endpoint type)
3. Secondary endpoint analyses
4. Sensitivity analyses
5. Subgroup analyses
6. Multiplicity adjustment strategy

Choose methods appropriate for the endpoint type:
- Time-to-event: Kaplan-Meier, log-rank test, Cox regression
- Binary: CMH test, logistic regression, Fisher's exact
- Continuous: ANCOVA, MMRM, t-test

IMPORTANT - USE PROTOCOL-SPECIFIED METHODS:
- If the protocol specifies a weighted log-rank test (e.g., Fleming-Harrington), USE THAT EXACT METHOD
- If rho/gamma parameters are given (e.g., G(rho=0, gamma=1)), include them
- If interim analysis uses Lan-DeMets or O'Brien-Fleming, describe the error spending function
- If there is a consistency objective, describe the hierarchical testing procedure

Use the actual comparator drug name, not "placebo" unless it IS placebo.
Write specific model specifications with covariates.
{interim_context}
{hierarchical_context}
{consistency_context}"""

            # Build statistical method instruction
            stat_method_instruction = ""
            if stat_method_details:
                stat_method_instruction = f"""
PROTOCOL-SPECIFIED STATISTICAL METHOD: {stat_method_details}
You MUST use this exact method as specified in the protocol."""
            elif stat_method:
                stat_method_instruction = f"""
PROTOCOL-SPECIFIED STATISTICAL METHOD: {stat_method}"""

            user_prompt = f"""Write the Statistical Methods section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

ENDPOINT TYPE DETECTED: {endpoint_type}
{stat_method_instruction}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

IMPORTANT:
- Use the actual comparator (not "placebo" unless it really is)
- Be specific about model covariates and stratification
- Use the EXACT statistical method specified in the protocol (if provided)
- If interim analysis is planned, include full alpha-spending details
- If consistency objective exists, describe hierarchical testing

Write the section now. Start with "## 7. STATISTICAL METHODS" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=3000
        )

        return GeneratedSection(
            content=response.content if response.success else "[LLM GENERATION FAILED - REQUIRES MANUAL REVIEW]",
            section_name="methods",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_endpoints(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Endpoints section using LLM with RAG examples."""
        examples = self._retrieve_examples('endpoints', facts, n_results=3)

        # Check for co-primary endpoints
        primary_endpoints = facts.get('primary_endpoints', [])
        has_multiple_primary = len(primary_endpoints) > 1

        # Check for oncology response criteria
        response_criteria = facts.get('response_criteria', '')
        pathologic_response_criteria = facts.get('pathologic_response_criteria', '')
        response_assessor = facts.get('response_assessor', '')

        # Build context about response criteria
        response_context = ""
        if response_criteria or pathologic_response_criteria:
            response_context = "\n\nONCOLOGY RESPONSE CRITERIA:\n"
            if response_criteria:
                response_context += f"- Tumor Response Criteria: {response_criteria}\n"
            if pathologic_response_criteria:
                response_context += f"- Pathologic Response Criteria: {pathologic_response_criteria}\n"
            if response_assessor:
                response_context += f"- Response Assessor: {response_assessor}\n"

        # Build context about co-primary endpoints
        coprimary_context = ""
        if has_multiple_primary:
            coprimary_context = f"""

CO-PRIMARY ENDPOINTS DETECTED ({len(primary_endpoints)} endpoints):
This study has MULTIPLE co-primary endpoints. List ALL of them separately in the SAP.
Each co-primary endpoint should have its own subsection with definition, type, and assessment criteria."""

        system_prompt = f"""You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Endpoints section including:
1. Primary endpoint(s) - definition and assessment timepoint for EACH
2. For studies with CO-PRIMARY ENDPOINTS: list each separately with its own definition
3. Secondary endpoints with definitions
4. Exploratory endpoints
5. Endpoint derivation rules
6. For tumor response endpoints: specify EXACT criteria version (e.g., RECIST 1.1, not just "RECIST")
7. For pathologic response: specify grading system (e.g., Junker, Miller-Payne, TRG)
8. For safety endpoints: specify CTCAE version (e.g., NCI-CTCAE v4.03 or v5.0)
9. For time-to-event endpoints: censoring rules

Be specific about how each endpoint is measured and derived.
Use the EXACT assessment criteria version from the protocol (e.g., "NCI-CTCAE v4.03" not just "CTCAE").
{coprimary_context}
{response_context}"""

        user_prompt = f"""Write the Endpoints section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

IMPORTANT:
- If there are multiple co-primary endpoints, list ALL of them as separate subsections
- Use the EXACT version of assessment criteria from the protocol
- For oncology: specify exact RECIST version (1.1, mRECIST, iRECIST, etc.)
- For AE grading: use exact CTCAE version (v4.03 or v5.0)
- For pathologic response: specify exact grading system

Write the section now. Start with "## 5. ENDPOINTS" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2500
        )

        return GeneratedSection(
            content=response.content if response.success else "[LLM GENERATION FAILED - REQUIRES MANUAL REVIEW]",
            section_name="endpoints",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_stratification(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Stratification section using LLM with RAG examples."""
        examples = self._retrieve_examples('stratification', facts, n_results=2)

        # Check if single-arm study - NO DEFAULTS, detect from multiple signals
        is_single_arm = self._detect_single_arm(facts)

        if is_single_arm:
            return GeneratedSection(
                content="""## STRATIFICATION

### Stratification Factors

This is a single-arm study without randomization. Therefore, no stratification factors are applicable for randomization.

For analysis purposes, subgroup analyses may be performed by:
- Baseline disease characteristics
- Prior treatment history
- Geographic region
- Demographic factors

These subgroups will be used for descriptive analyses only.""",
                section_name="stratification",
                llm_source="rules",
                rag_examples_used=[],
                success=True
            )

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Stratification section including:
1. List of stratification factors used for randomization
2. Levels within each factor
3. How stratification will be incorporated in analysis
4. Handling of pooling for small strata

Use the actual stratification factors from the protocol."""

        user_prompt = f"""Write the Stratification section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

Write the section now. Start with "## STRATIFICATION" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1500
        )

        return GeneratedSection(
            content=response.content if response.success else "[LLM GENERATION FAILED - REQUIRES MANUAL REVIEW]",
            section_name="stratification",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_regulatory_interim(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Regulatory Interim Analysis section (e.g., TTF for China)."""
        if not self._detect_regulatory_interim(facts):
            return GeneratedSection(
                content="",
                section_name="regulatory_interim",
                llm_source="none",
                success=True,
                error=None
            )

        examples = self._retrieve_examples('methods', facts, n_results=2)

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write a Regulatory Interim Analysis section for regional filing support (e.g., TTF interim for China NDA).

This section should include:
1. Purpose of the regulatory interim analysis
2. Timing of the analysis
3. Statistical methods (often different from primary analysis)
4. Analyses to be performed (TTF, ORR, safety, subgroup analyses)
5. Decision rules (if any)
6. Relationship to primary analysis alpha spending (often independent/no penalty)

Use formal scientific language appropriate for regulatory submission."""

        user_prompt = f"""Write the Regulatory Interim Analysis section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

REGULATORY INTERIM DETAILS:
- Endpoint: {facts.get('regulatory_interim_endpoint', 'TTF')}
- Region: {facts.get('regulatory_interim_region', 'China')}
- Purpose: {facts.get('regulatory_interim_purpose', 'Support early filing')}
- Timing: {facts.get('regulatory_interim_timing', 'Per protocol')}
- Alpha: {facts.get('regulatory_interim_alpha', 0.025)}
- Method: {facts.get('regulatory_interim_method', 'Weighted log-rank')}
- Analyses: {facts.get('regulatory_interim_analyses', [])}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

Write the section now. Start with "## 7.X REGULATORY INTERIM ANALYSIS" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1500
        )

        return GeneratedSection(
            content=response.content if response.success else "[LLM GENERATION FAILED - REQUIRES MANUAL REVIEW]",
            section_name="regulatory_interim",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_pro_endpoints(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Patient-Reported Outcomes section."""
        if not self._detect_pro_endpoint(facts):
            return GeneratedSection(
                content="",
                section_name="pro_endpoints",
                llm_source="none",
                success=True,
                error=None
            )

        examples = self._retrieve_examples('endpoints', facts, n_results=2)

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write a Patient-Reported Outcomes (PRO) section for quality of life and symptom endpoints.

This section should include:
1. PRO instruments used (LCSS, EORTC QLQ-C30, EQ-5D, etc.)
2. Subscales and domains assessed
3. Assessment schedule/timepoints
4. Responder definition (e.g., ≥10 point change from baseline)
5. Analysis methods for PRO data
6. Handling of missing PRO data

Use formal scientific language appropriate for regulatory submission."""

        pro_endpoints = facts.get('pro_endpoints', [])
        instruments = facts.get('pro_instruments', [])

        user_prompt = f"""Write the Patient-Reported Outcomes section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

PRO DETAILS:
- Instruments: {', '.join(instruments) if instruments else 'As specified in protocol'}
- PRO Endpoints: {pro_endpoints}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

Write the section now. Start with "## 5.X PATIENT-REPORTED OUTCOMES" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1500
        )

        return GeneratedSection(
            content=response.content if response.success else "[LLM GENERATION FAILED - REQUIRES MANUAL REVIEW]",
            section_name="pro_endpoints",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_subgroup_analyses(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Subgroup Analyses section."""
        examples = self._retrieve_examples('methods', facts, n_results=2)

        subgroups = facts.get('subgroup_analyses', [])

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write a comprehensive Subgroup Analyses section.

This section should include:
1. Complete list of planned subgroups
2. Methodology (forest plot, interaction tests)
3. Interpretation guidance (exploratory nature)
4. Multiplicity considerations

Use formal scientific language appropriate for regulatory submission."""

        user_prompt = f"""Write the Subgroup Analyses section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

PLANNED SUBGROUPS:
{chr(10).join([f'- {s}' for s in subgroups]) if subgroups else 'Per protocol specification'}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

Write the section now. Start with "## 7.X SUBGROUP ANALYSES" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1500
        )

        return GeneratedSection(
            content=response.content if response.success else "[LLM GENERATION FAILED - REQUIRES MANUAL REVIEW]",
            section_name="subgroup_analyses",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )


# Convenience function
def create_llm_generator(rag_adapter=None) -> LLMSectionGenerator:
    """Factory function to create LLM section generator."""
    return LLMSectionGenerator(rag_adapter=rag_adapter)
