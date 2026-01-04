#!/usr/bin/env python3
"""
Extraction Schema for Oncology SAP Generation
==============================================

COMPREHENSIVE SCHEMA based on:
- Gamble et al. 2017 (JAMA): 55-item SAP checklist
- ICH E9 / E9(R1): Statistical principles and estimand framework
- FDA Oncology Guidance: Endpoint definitions
- CDISC ADaM: Data structure standards

CRITICAL FIELDS ADDED (2025-01 refactor):
- treatment_setting: neoadjuvant, adjuvant, first-line, etc.
- disease_type, tumor_type, histology: specific disease details
- stratification_factor_levels: actual values, not just names
- estimand fields (ICH E9 R1): 5 required attributes
- alpha_per_hypothesis: explicit alpha allocation per endpoint
- interim_by_endpoint: per-endpoint IA structure

All method choices come from EXTRACTION, not inference.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class TreatmentSetting(Enum):
    """Treatment setting classification."""
    FIRST_LINE = "first-line"
    SECOND_LINE = "second-line"
    THIRD_LINE_PLUS = "third-line or later"
    NEOADJUVANT = "neoadjuvant"
    ADJUVANT = "adjuvant"
    MAINTENANCE = "maintenance"
    SALVAGE = "salvage"
    UNKNOWN = "unknown"


class TrialDesignType(Enum):
    """Trial design types."""
    PARALLEL = "parallel"
    CROSSOVER = "crossover"
    FACTORIAL = "factorial"
    SINGLE_ARM = "single_arm"


class HypothesisFramework(Enum):
    """Hypothesis testing framework."""
    SUPERIORITY = "superiority"
    NON_INFERIORITY = "non_inferiority"
    EQUIVALENCE = "equivalence"


class OncologyEndpointType(Enum):
    """Standard FDA oncology endpoints."""
    OS = "Overall Survival"
    PFS = "Progression-Free Survival"
    ORR = "Objective Response Rate"
    DOR = "Duration of Response"
    DCR = "Disease Control Rate"
    TTP = "Time to Progression"
    DFS = "Disease-Free Survival"
    EFS = "Event-Free Survival"
    TTF = "Time to Treatment Failure"
    PCR = "Pathologic Complete Response"


class ICEStrategy(Enum):
    """Intercurrent event handling strategies (ICH E9 R1)."""
    TREATMENT_POLICY = "treatment_policy"
    COMPOSITE = "composite"
    HYPOTHETICAL = "hypothetical"
    PRINCIPAL_STRATUM = "principal_stratum"
    WHILE_ON_TREATMENT = "while_on_treatment"


# =============================================================================
# SECTION 1: ADMINISTRATIVE (Gamble Items 1-6)
# =============================================================================

@dataclass
class AdministrativeInfo:
    """Administrative information from Gamble et al. Section 1."""
    nct_id: str = ""                              # Trial registration number
    protocol_number: Optional[str] = None         # Protocol version reference
    protocol_title: Optional[str] = None          # Full protocol title
    sponsor: Optional[str] = None                 # Sponsor organization
    sap_version: Optional[str] = None             # SAP version if exists
    sap_date: Optional[str] = None                # SAP finalization date


# =============================================================================
# SECTION 2: STUDY DESIGN (Gamble Items 7-15 + FDA Oncology)
# =============================================================================

@dataclass
class StudyDesign:
    """Study design from Gamble et al. Section 3 + FDA Oncology Guidance."""
    # Item 9: Trial design (NO DEFAULTS - must be extracted)
    design_type: str = ""                         # parallel, crossover, factorial, single_arm
    phase: str = ""                               # 1, 2, 3, 4
    is_randomized: Optional[bool] = None          # None if not extracted
    is_blinded: Optional[bool] = None             # None if not extracted
    blinding_type: str = ""                       # double-blind, open-label, etc.

    # Treatment arms
    drug_name: str = ""
    drug_class: Optional[str] = None              # immunotherapy, chemotherapy, targeted
    comparator: str = ""
    comparator_type: str = ""                     # active, placebo, SOC

    # Item 10: Randomization (NO DEFAULTS)
    allocation_ratio: str = ""                    # MUST be extracted: "1:1", "2:1", etc.
    stratification_factors: List[str] = field(default_factory=list)

    # Item 11: Sample size
    sample_size: int = 0
    sample_size_per_arm: Optional[List[int]] = None
    sample_size_rationale: Optional[str] = None

    # Item 12: Framework (NO DEFAULTS)
    hypothesis_framework: str = ""                # superiority, non_inferiority, equivalence

    # ==========================================================================
    # NEW FIELDS (2025-01 refactor) - CRITICAL FOR ACCURACY
    # ==========================================================================

    # Treatment setting (was missing - caused neoadjuvant vs first-line errors)
    treatment_setting: str = ""                   # CRITICAL: first-line, neoadjuvant, adjuvant, etc.

    # Disease-specific fields (was missing - caused generic disease errors)
    disease_type: str = ""                        # e.g., "Non-small cell lung cancer (NSCLC)"
    tumor_type: str = ""                          # e.g., "Lung cancer"
    histology: str = ""                           # e.g., "Squamous", "Non-squamous", "Adenocarcinoma"
    disease_stage: str = ""                       # e.g., "Stage IIIB-IV", "Locally advanced or metastatic"
    biomarker_status: str = ""                    # e.g., "PD-L1 ≥50%", "EGFR mutation negative"

    # Stratification factor LEVELS (not just names)
    # e.g., {"PD-L1": ["<1%", "1-49%", "≥50%"], "ECOG": ["0", "1"]}
    stratification_factor_levels: Dict[str, List[str]] = field(default_factory=dict)


# =============================================================================
# SECTION 3: ESTIMAND FRAMEWORK (ICH E9 R1) - NEW SECTION
# =============================================================================

@dataclass
class Estimand:
    """
    ICH E9(R1) Estimand Framework - 5 required attributes.
    This section was entirely missing from the previous schema.
    """
    # Attribute 1: Population
    population: str = ""                          # e.g., "Adult patients with advanced NSCLC"

    # Attribute 2: Variable (endpoint)
    variable: str = ""                            # e.g., "Overall Survival"
    variable_definition: str = ""                 # e.g., "Time from randomization to death"

    # Attribute 3: Intercurrent events and strategies
    intercurrent_events: List[Dict[str, str]] = field(default_factory=list)
    # Each dict: {"event": "Treatment discontinuation", "strategy": "treatment_policy"}

    # Attribute 4: Population-level summary
    population_summary: str = ""                  # e.g., "Hazard ratio"

    # Pre-specified estimand for each endpoint
    primary_estimand: str = ""                    # Full estimand statement
    secondary_estimands: List[str] = field(default_factory=list)


# =============================================================================
# SECTION 4: ENDPOINTS (FDA Oncology Guidance + CDISC ADaM)
# =============================================================================

@dataclass
class Endpoint:
    """Endpoint definition from FDA Oncology Guidance + CDISC."""
    name: str = ""
    endpoint_type: str = ""                       # OS, PFS, ORR, DOR, etc.
    is_primary: bool = False
    definition: Optional[str] = None
    assessment_criteria: str = "RECIST 1.1"       # RECIST, irRECIST, mRECIST, Lugano
    assessment_method: str = "investigator"       # investigator, BICR, both
    assessment_schedule: Optional[str] = None
    timepoint: Optional[str] = None               # e.g., "Week 12", "Month 6"

    # For pathologic endpoints (neoadjuvant)
    pathologic_criteria: Optional[str] = None     # e.g., "Miller-Payne", "RCB"


@dataclass
class EndpointConfiguration:
    """Complete endpoint setup for the trial."""
    primary_endpoint: Optional[Endpoint] = None
    primary_endpoint_text: str = ""               # Simple text version
    secondary_endpoints: List[str] = field(default_factory=list)
    exploratory_endpoints: List[str] = field(default_factory=list)

    # Co-primary structure (was missing)
    is_co_primary: bool = False                   # Are there co-primary endpoints?
    co_primary_endpoints: List[str] = field(default_factory=list)
    co_primary_success_rule: str = ""             # e.g., "Both must be significant"


# =============================================================================
# SECTION 5: INTERIM ANALYSIS (ICH E9 + Lan-DeMets) - ENHANCED
# =============================================================================

@dataclass
class InterimAnalysisPerEndpoint:
    """Per-endpoint interim analysis structure (was missing)."""
    endpoint: str = ""                            # e.g., "PFS" or "OS"
    timing: str = ""                              # e.g., "60% information fraction"
    events_required: Optional[int] = None
    alpha_spent: Optional[float] = None
    boundary_type: str = ""                       # efficacy, futility, both


@dataclass
class InterimAnalysis:
    """
    Interim analysis specification from ICH E9 Section 4.5 + Gamble Items 13a-13c.
    ENHANCED with per-endpoint structure.
    """
    # Item 13a: Number and timing (NO DEFAULTS - must be extracted)
    has_interim_analysis: Optional[bool] = None   # None if not extracted
    num_interim_analyses: Optional[int] = None    # CRITICAL: must be extracted

    # Event counts - CRITICAL numerical fields
    interim_events: Optional[List[int]] = None    # Events at each interim look
    final_events: Optional[int] = None            # CRITICAL: 382 vs 639 bug

    # Information fractions
    information_fractions: Optional[List[float]] = None  # e.g., [0.5, 0.75, 1.0]

    # Item 13b: Alpha adjustment - CRITICAL numerical fields (NO DEFAULTS)
    alpha_spending_function: str = ""             # O'Brien-Fleming, Lan-DeMets, etc.
    overall_alpha: Optional[float] = None         # CRITICAL: must be extracted, NEVER default 0.05
    alpha_sidedness: str = ""                     # one-sided or two-sided - must be extracted
    alpha_at_interim: Optional[List[float]] = None  # CRITICAL: 0.020 vs 0.05 bug
    alpha_at_final: Optional[float] = None        # CRITICAL: 0.044 vs 0.05 bug

    # Item 13c: Stopping guidelines (NO DEFAULTS)
    efficacy_stopping: Optional[bool] = None      # None if not extracted
    futility_stopping: Optional[bool] = None      # None if not extracted
    futility_boundary_type: Optional[str] = None  # binding, non-binding
    stopping_boundaries: Optional[str] = None     # Description of boundaries

    # ==========================================================================
    # NEW: Per-endpoint IA structure (was missing - caused IA details errors)
    # ==========================================================================
    interim_by_endpoint: List[InterimAnalysisPerEndpoint] = field(default_factory=list)
    # e.g., [{"endpoint": "PFS", "timing": "60% IF", "alpha_spent": 0.005},
    #        {"endpoint": "OS", "timing": "70% IF", "alpha_spent": 0.015}]


# =============================================================================
# SECTION 6: STATISTICAL METHODS (Gamble Items 16-20, 27a-27f) - ENHANCED
# =============================================================================

@dataclass
class StatisticalMethods:
    """Statistical methods from Gamble Section 6 + FDA Oncology."""
    # Item 27a: Primary analysis
    primary_test: str = ""                        # e.g., "stratified log-rank"
    primary_test_details: Optional[str] = None    # e.g., "G(ρ=0, γ=1)" for F-H

    # Effect estimation
    hazard_ratio_method: str = "Cox regression"
    expected_hazard_ratio: Optional[float] = None
    confidence_interval_level: float = 0.95
    power: Optional[float] = None                 # e.g., 0.90 for 90%

    # Item 27b: Covariates
    stratification_in_analysis: List[str] = field(default_factory=list)

    # Item 27d: Alternative methods (non-PH)
    proportional_hazards_check: str = "Schoenfeld residuals"
    non_ph_alternatives: List[str] = field(default_factory=list)

    # Item 27e: Sensitivity analyses
    sensitivity_analyses: List[str] = field(default_factory=list)

    # Item 27f: Subgroup analyses
    subgroup_analyses: List[str] = field(default_factory=list)

    # ==========================================================================
    # NEW: Explicit hypothesis statements (was missing)
    # ==========================================================================
    null_hypothesis: str = ""                     # e.g., "HR = 1.0"
    alternative_hypothesis: str = ""              # e.g., "HR < 1.0 (superiority)"
    test_sidedness: str = "one-sided"             # one-sided or two-sided


# =============================================================================
# SECTION 7: MULTIPLICITY (Gamble Item 17 + FDA) - ENHANCED
# =============================================================================

@dataclass
class MultiplicityAdjustment:
    """Multiplicity adjustment from Gamble Item 17 + FDA FWER requirements."""
    has_multiplicity: Optional[bool] = None       # None if not extracted
    adjustment_method: Optional[str] = None       # Hierarchical, Hochberg, Holm, Graphical
    testing_sequence: List[str] = field(default_factory=list)
    alpha_allocation: Optional[str] = None        # Text description

    # ==========================================================================
    # NEW: Explicit alpha per hypothesis (was missing - caused alpha errors)
    # ==========================================================================
    alpha_per_hypothesis: Dict[str, float] = field(default_factory=dict)
    # e.g., {"PFS": 0.0125, "OS": 0.0125, "ORR": 0.025}

    # For graphical approach (Maurer & Bretz)
    graphical_weights: Optional[Dict[str, float]] = None
    graphical_transitions: Optional[Dict[str, Dict[str, float]]] = None

    # ==========================================================================
    # NEW: Structured hypothesis list (H1-H5 with descriptions and alpha)
    # ==========================================================================
    hypotheses_list: List[Dict[str, Any]] = field(default_factory=list)
    # e.g., [
    #   {"id": "H1", "description": "PFS superiority pMMR", "alpha": 0.005, "endpoint": "PFS", "population": "pMMR"},
    #   {"id": "H2", "description": "PFS superiority all-comers", "alpha": 0.0, "endpoint": "PFS", "population": "all"},
    #   {"id": "H3", "description": "OS non-inferiority pMMR", "alpha": 0.020, "endpoint": "OS", "population": "pMMR"},
    # ]


# =============================================================================
# SECTION 8: MISSING DATA & CENSORING (Gamble Item 28 + ICH E9(R1)) - ENHANCED
# =============================================================================

@dataclass
class MissingDataHandling:
    """Missing data handling from ICH E9(R1) Estimand Framework + Gamble Item 28."""
    # Intercurrent events (ICH E9(R1)) - NO DEFAULTS
    treatment_discontinuation_strategy: str = ""  # Must be extracted
    subsequent_therapy_handling: str = ""         # Must be extracted

    # Censoring rules (FDA PFS guidance)
    censoring_rules: List[str] = field(default_factory=list)

    # Missing tumor assessments
    missing_assessment_handling: str = ""         # Must be extracted

    # Sensitivity for missing data
    sensitivity_methods: List[str] = field(default_factory=list)

    # ==========================================================================
    # NEW: Missing data assumptions and methods - NO DEFAULTS
    # ==========================================================================
    missing_at_random_assumption: Optional[bool] = None   # None if not extracted
    tipping_point_analysis: Optional[bool] = None         # None if not extracted
    pattern_mixture_models: Optional[bool] = None         # None if not extracted
    multiple_imputation: Optional[bool] = None            # None if not extracted


# =============================================================================
# SECTION 9: ANALYSIS POPULATIONS (Gamble Item 20) - ENHANCED
# =============================================================================

@dataclass
class AnalysisPopulations:
    """Analysis populations from Gamble Item 20."""
    itt_definition: str = "All randomized subjects"
    per_protocol_definition: Optional[str] = None
    safety_population_definition: str = "All subjects who received at least one dose"

    # ==========================================================================
    # NEW: FAS and additional populations (was missing)
    # ==========================================================================
    fas_definition: str = ""                      # Full Analysis Set (often = ITT)

    # Oncology-specific
    efficacy_evaluable_definition: Optional[str] = None
    biomarker_evaluable_definition: Optional[str] = None
    pk_population_definition: Optional[str] = None  # For PK analysis


# =============================================================================
# SECTION 10: CROSSOVER / TREATMENT SWITCHING
# =============================================================================

@dataclass
class CrossoverHandling:
    """Treatment switching/crossover handling."""
    has_crossover: Optional[bool] = None          # None if not extracted
    crossover_description: Optional[str] = None
    crossover_adjustment_methods: List[str] = field(default_factory=list)  # RPSFT, IPCW


# =============================================================================
# SECTION 11: EXTRACTION CONFIDENCE (NEW SECTION)
# =============================================================================

@dataclass
class ExtractionConfidence:
    """
    Per-field confidence scores for extraction.
    Enables section-by-section extraction with quality tracking.
    """
    overall_confidence: float = 0.0               # 0-1 overall extraction quality

    # Per-section confidence
    section_confidence: Dict[str, float] = field(default_factory=dict)
    # e.g., {"study_design": 0.95, "interim_analysis": 0.80, "multiplicity": 0.60}

    # Fields that need review
    needs_review: List[str] = field(default_factory=list)
    # e.g., ["alpha_per_hypothesis", "interim_events"]

    # Fields not found in protocol
    not_found: List[str] = field(default_factory=list)

    # Extraction notes
    notes: List[str] = field(default_factory=list)


# =============================================================================
# MASTER SCHEMA - COMPLETE EXTRACTION
# =============================================================================

@dataclass
class ExtractedProtocolFacts:
    """
    Complete schema combining all authoritative sources.
    This is the SINGLE SOURCE OF TRUTH for generation.

    If a field is not extracted, it should be None (not defaulted).
    Generation should only use values that were actually extracted.

    CRITICAL: All fields defined here should be passed through the pipeline.
    """
    # Administrative
    admin: AdministrativeInfo = field(default_factory=AdministrativeInfo)

    # Design (ENHANCED with treatment_setting, disease details)
    design: StudyDesign = field(default_factory=StudyDesign)

    # Estimand (NEW - ICH E9 R1)
    estimand: Estimand = field(default_factory=Estimand)

    # Endpoints (ENHANCED with co-primary structure)
    endpoints: EndpointConfiguration = field(default_factory=EndpointConfiguration)

    # Interim Analysis (ENHANCED with per-endpoint structure)
    interim: InterimAnalysis = field(default_factory=InterimAnalysis)

    # Statistical Methods (ENHANCED with hypothesis statements)
    methods: StatisticalMethods = field(default_factory=StatisticalMethods)

    # Multiplicity (ENHANCED with alpha_per_hypothesis)
    multiplicity: MultiplicityAdjustment = field(default_factory=MultiplicityAdjustment)

    # Missing Data (ENHANCED with sensitivity methods)
    missing_data: MissingDataHandling = field(default_factory=MissingDataHandling)

    # Populations (ENHANCED with FAS)
    populations: AnalysisPopulations = field(default_factory=AnalysisPopulations)

    # Crossover
    crossover: CrossoverHandling = field(default_factory=CrossoverHandling)

    # Extraction Confidence (NEW)
    confidence: ExtractionConfidence = field(default_factory=ExtractionConfidence)

    def get_critical_numerical_fields(self) -> Dict[str, Any]:
        """
        Returns all numerical fields that MUST match the protocol exactly.
        """
        return {
            # Sample size
            'sample_size': self.design.sample_size,

            # Event counts - CRITICAL
            'final_events': self.interim.final_events,
            'interim_events': self.interim.interim_events,

            # Interim structure
            'num_interim_analyses': self.interim.num_interim_analyses,
            'information_fractions': self.interim.information_fractions,

            # Alpha values - CRITICAL
            'overall_alpha': self.interim.overall_alpha,
            'alpha_at_interim': self.interim.alpha_at_interim,
            'alpha_at_final': self.interim.alpha_at_final,
            'alpha_per_hypothesis': self.multiplicity.alpha_per_hypothesis,

            # Effect size
            'expected_hazard_ratio': self.methods.expected_hazard_ratio,
            'power': self.methods.power,
        }

    def validate_completeness(self) -> List[str]:
        """Check which critical fields are missing."""
        missing = []
        critical = self.get_critical_numerical_fields()
        for field_name, value in critical.items():
            if value is None or value == 0 or value == [] or value == {}:
                missing.append(field_name)
        return missing

    def to_flat_dict(self) -> Dict[str, Any]:
        """
        Convert to flat dictionary for prompt formatting.
        This is what gets passed to _format_facts().
        """
        return {
            # Administrative
            'nct_id': self.admin.nct_id,
            'protocol_number': self.admin.protocol_number,
            'sponsor': self.admin.sponsor,

            # Design - CORE
            'drug_name': self.design.drug_name,
            'comparator': self.design.comparator,
            'indication': self.design.drug_class,
            'phase': self.design.phase,
            'sample_size': self.design.sample_size,
            'allocation_ratio': self.design.allocation_ratio,
            'stratification_factors': self.design.stratification_factors,
            'design_type': self.design.design_type,

            # Design - NEW CRITICAL FIELDS
            'treatment_setting': self.design.treatment_setting,
            'disease_type': self.design.disease_type,
            'tumor_type': self.design.tumor_type,
            'histology': self.design.histology,
            'disease_stage': self.design.disease_stage,
            'biomarker_status': self.design.biomarker_status,
            'stratification_factor_levels': self.design.stratification_factor_levels,

            # Estimand (ICH E9 R1) - NEW
            'estimand_population': self.estimand.population,
            'estimand_variable': self.estimand.variable,
            'intercurrent_events': self.estimand.intercurrent_events,
            'primary_estimand': self.estimand.primary_estimand,

            # Endpoints
            'primary_endpoint': self.endpoints.primary_endpoint_text,
            'secondary_endpoints': self.endpoints.secondary_endpoints,
            'is_co_primary': self.endpoints.is_co_primary,
            'co_primary_endpoints': self.endpoints.co_primary_endpoints,

            # Interim Analysis - CRITICAL NUMERICAL FIELDS
            'has_interim_analysis': self.interim.has_interim_analysis,
            'num_interim_analyses': self.interim.num_interim_analyses,
            'interim_events': self.interim.interim_events,
            'final_events': self.interim.final_events,
            'information_fractions': self.interim.information_fractions,
            'alpha_spending_function': self.interim.alpha_spending_function,
            'overall_alpha': self.interim.overall_alpha,
            'alpha_sidedness': self.interim.alpha_sidedness,
            'alpha_at_interim': self.interim.alpha_at_interim,
            'alpha_at_final': self.interim.alpha_at_final,
            'stopping_boundaries': self.interim.stopping_boundaries,
            'interim_by_endpoint': [
                {'endpoint': ia.endpoint, 'timing': ia.timing, 'events': ia.events_required, 'alpha': ia.alpha_spent}
                for ia in self.interim.interim_by_endpoint
            ],

            # Methods
            'primary_test': self.methods.primary_test,
            'statistical_method': self.methods.primary_test,  # Alias
            'expected_hazard_ratio': self.methods.expected_hazard_ratio,
            'power': self.methods.power,
            'sensitivity_analyses': self.methods.sensitivity_analyses,
            'subgroup_analyses': self.methods.subgroup_analyses,
            'null_hypothesis': self.methods.null_hypothesis,
            'alternative_hypothesis': self.methods.alternative_hypothesis,

            # Multiplicity - ENHANCED
            'multiplicity_method': self.multiplicity.adjustment_method,
            'testing_sequence': self.multiplicity.testing_sequence,
            'alpha_per_hypothesis': self.multiplicity.alpha_per_hypothesis,
            'hypotheses_list': self.multiplicity.hypotheses_list,
            'graphical_weights': self.multiplicity.graphical_weights,
            'graphical_transitions': self.multiplicity.graphical_transitions,

            # Missing Data
            'treatment_discontinuation_strategy': self.missing_data.treatment_discontinuation_strategy,
            'censoring_rules': self.missing_data.censoring_rules,
            'tipping_point_analysis': self.missing_data.tipping_point_analysis,

            # Crossover
            'has_crossover': self.crossover.has_crossover,
            'crossover_adjustment_methods': self.crossover.crossover_adjustment_methods,

            # Populations
            'itt_definition': self.populations.itt_definition,
            'fas_definition': self.populations.fas_definition,
            'safety_definition': self.populations.safety_population_definition,

            # Confidence
            'extraction_confidence': self.confidence.overall_confidence,
            'needs_review': self.confidence.needs_review,
        }


# =============================================================================
# CONVERSION FUNCTIONS
# =============================================================================

def from_claude_extraction(extracted: Dict[str, Any]) -> ExtractedProtocolFacts:
    """
    Convert Claude LLM extraction output to structured schema.

    This function ensures all extracted fields are properly mapped
    to the schema, fixing the "fields not passed through" bug.
    """
    facts = ExtractedProtocolFacts()

    # Administrative
    facts.admin.nct_id = extracted.get('nct_id', '')
    facts.admin.protocol_title = extracted.get('protocol_title', '')
    facts.admin.sponsor = extracted.get('sponsor', '')

    # Design - CORE
    facts.design.drug_name = extracted.get('drug_name', '')
    facts.design.comparator = extracted.get('comparator', '')
    facts.design.phase = extracted.get('phase', '')
    facts.design.sample_size = extracted.get('sample_size', 0)
    facts.design.allocation_ratio = extracted.get('allocation_ratio') or extracted.get('randomization_ratio') or ''
    facts.design.stratification_factors = extracted.get('stratification_factors', [])
    facts.design.design_type = extracted.get('design_type', '')
    facts.design.is_randomized = extracted.get('is_randomized')  # None if not found

    # Design - NEW CRITICAL FIELDS
    facts.design.treatment_setting = extracted.get('treatment_setting', '')
    facts.design.disease_type = extracted.get('disease_type', '') or extracted.get('indication', '')
    facts.design.tumor_type = extracted.get('tumor_type', '')
    facts.design.histology = extracted.get('histology', '')
    facts.design.disease_stage = extracted.get('disease_stage', '')
    facts.design.biomarker_status = extracted.get('biomarker_status', '')
    facts.design.stratification_factor_levels = extracted.get('stratification_factor_levels', {})

    # Estimand (ICH E9 R1) - NEW
    facts.estimand.population = extracted.get('estimand_population', '')
    facts.estimand.variable = extracted.get('estimand_variable', '')
    facts.estimand.intercurrent_events = extracted.get('intercurrent_events', [])
    facts.estimand.primary_estimand = extracted.get('primary_estimand', '')

    # Endpoints
    facts.endpoints.primary_endpoint_text = extracted.get('primary_endpoint', '')
    facts.endpoints.secondary_endpoints = extracted.get('secondary_endpoints', [])
    facts.endpoints.is_co_primary = extracted.get('is_co_primary')  # None if not found
    facts.endpoints.co_primary_endpoints = extracted.get('co_primary_endpoints', [])

    # Interim Analysis - CRITICAL (NO DEFAULTS - must be extracted)
    facts.interim.has_interim_analysis = extracted.get('has_interim_analysis')  # None if not found
    facts.interim.num_interim_analyses = extracted.get('num_interim_analyses')  # None if not found
    facts.interim.interim_events = extracted.get('interim_events', [])
    facts.interim.final_events = extracted.get('final_events') or extracted.get('final_analysis_events')
    facts.interim.information_fractions = extracted.get('interim_information_fraction', [])
    facts.interim.alpha_spending_function = extracted.get('error_spending_function', '') or extracted.get('alpha_spending_function', '')
    facts.interim.overall_alpha = extracted.get('alpha_level') or extracted.get('overall_alpha')  # None if not found - NEVER default 0.05
    facts.interim.alpha_at_interim = extracted.get('interim_alpha_spent', []) or extracted.get('alpha_at_interim', [])
    facts.interim.alpha_at_final = extracted.get('alpha_at_final')
    facts.interim.stopping_boundaries = extracted.get('stopping_boundaries', '')

    # Per-endpoint IA - NEW
    interim_by_ep = extracted.get('interim_by_endpoint', [])
    for ia in interim_by_ep:
        facts.interim.interim_by_endpoint.append(InterimAnalysisPerEndpoint(
            endpoint=ia.get('endpoint', ''),
            timing=ia.get('timing', ''),
            events_required=ia.get('events'),
            alpha_spent=ia.get('alpha')
        ))

    # Methods
    facts.methods.primary_test = extracted.get('statistical_method', '') or extracted.get('primary_test', '')
    facts.methods.expected_hazard_ratio = extracted.get('hazard_ratio')
    facts.methods.power = extracted.get('power')
    facts.methods.sensitivity_analyses = extracted.get('sensitivity_methods', [])
    facts.methods.null_hypothesis = extracted.get('null_hypothesis', '')
    facts.methods.alternative_hypothesis = extracted.get('alternative_hypothesis', '')

    # Multiplicity - ENHANCED
    facts.multiplicity.adjustment_method = extracted.get('multiplicity_method', '')
    facts.multiplicity.testing_sequence = extracted.get('testing_sequence', [])
    facts.multiplicity.alpha_per_hypothesis = extracted.get('alpha_per_hypothesis', {})
    facts.multiplicity.hypotheses_list = extracted.get('hypotheses_list', [])
    facts.multiplicity.graphical_weights = extracted.get('graphical_weights', None)
    facts.multiplicity.graphical_transitions = extracted.get('graphical_transitions', None)

    # Missing Data
    facts.missing_data.tipping_point_analysis = extracted.get('tipping_point_analysis')  # None if not found
    facts.missing_data.censoring_rules = extracted.get('censoring_rules', [])

    # Crossover
    facts.crossover.has_crossover = extracted.get('crossover_permitted') or extracted.get('has_crossover')  # None if not found
    facts.crossover.crossover_adjustment_methods = extracted.get('crossover_adjustment_methods', [])

    # Populations
    facts.populations.fas_definition = extracted.get('fas_definition', '')

    # Confidence - NEW
    facts.confidence.overall_confidence = extracted.get('extraction_confidence', 0.0)
    facts.confidence.needs_review = extracted.get('needs_review', [])
    facts.confidence.section_confidence = extracted.get('section_confidence', {})

    return facts


# =============================================================================
# VALIDATION
# =============================================================================

def validate_extraction(facts: ExtractedProtocolFacts) -> Dict[str, Any]:
    """
    Validate extracted facts for completeness and consistency.

    Returns:
        Dict with 'valid' bool, 'missing' list, 'warnings' list
    """
    result = {
        'valid': True,
        'missing': [],
        'warnings': []
    }

    # Check critical numerical fields
    critical = facts.get_critical_numerical_fields()

    for field_name, value in critical.items():
        if value is None:
            result['missing'].append(field_name)
        elif isinstance(value, (int, float)) and value == 0:
            if field_name not in ['num_interim_analyses']:  # 0 interim is valid
                result['warnings'].append(f"{field_name} is 0 - verify this is correct")

    # Check critical text fields
    if not facts.design.treatment_setting:
        result['warnings'].append("treatment_setting not extracted - may cause setting errors")
    if not facts.design.disease_type:
        result['warnings'].append("disease_type not extracted - may cause generic disease errors")
    if not facts.methods.primary_test:
        result['missing'].append("statistical_method (primary_test)")

    # Validate interim analysis consistency
    if facts.interim.has_interim_analysis:
        if facts.interim.num_interim_analyses == 0:
            result['warnings'].append("has_interim_analysis=True but num_interim_analyses=0")
        if not facts.interim.interim_events:
            result['missing'].append("interim_events (required when has_interim_analysis=True)")
        if not facts.interim.alpha_at_interim:
            result['missing'].append("alpha_at_interim (required when has_interim_analysis=True)")

    # Check for default alpha being used
    if facts.interim.overall_alpha == 0.05:
        result['warnings'].append("alpha=0.05 may be default - verify from protocol")

    result['valid'] = len(result['missing']) == 0

    return result


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Enhanced Extraction Schema")
    print("=" * 60)

    # Create sample facts with new fields
    facts = ExtractedProtocolFacts()
    facts.admin.nct_id = "NCT02041533"
    facts.design.drug_name = "Nivolumab"
    facts.design.comparator = "Docetaxel"
    facts.design.sample_size = 504

    # NEW CRITICAL FIELDS
    facts.design.treatment_setting = "second-line"
    facts.design.disease_type = "Non-small cell lung cancer (NSCLC)"
    facts.design.histology = "Squamous"
    facts.design.stratification_factor_levels = {
        "PD-L1": ["<1%", "1-49%", "≥50%"],
        "ECOG": ["0", "1"]
    }

    # Interim
    facts.interim.has_interim_analysis = True
    facts.interim.num_interim_analyses = 1
    facts.interim.interim_events = [291]
    facts.interim.final_events = 382
    facts.interim.alpha_at_interim = [0.020]
    facts.interim.alpha_at_final = 0.044

    # Multiplicity with explicit alpha
    facts.multiplicity.alpha_per_hypothesis = {
        "OS": 0.025,
        "ORR": 0.025
    }

    # Get critical fields
    print("\nCritical Numerical Fields:")
    for field, value in facts.get_critical_numerical_fields().items():
        print(f"  {field}: {value}")

    # Validate
    print("\nValidation:")
    validation = validate_extraction(facts)
    print(f"  Valid: {validation['valid']}")
    print(f"  Missing: {validation['missing']}")
    print(f"  Warnings: {validation['warnings']}")

    # Convert to flat dict
    print("\nFlat Dict (for prompt):")
    flat = facts.to_flat_dict()
    print(f"  Total fields: {len(flat)}")
    for key in ['treatment_setting', 'disease_type', 'histology', 'alpha_per_hypothesis', 'stratification_factor_levels']:
        print(f"  {key}: {flat.get(key)}")
