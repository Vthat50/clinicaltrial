#!/usr/bin/env python3
"""
Extraction Schema for Oncology SAP Generation
==============================================

Defines the COMPLETE set of fields that must be extracted and passed through
the pipeline. This is the SINGLE SOURCE OF TRUTH for all numerical values.

Sources:
- ICH E9 / E9(R1): Statistical principles and estimand framework
- Gamble et al. 2017 (JAMA): 55-item SAP checklist
- FDA Oncology Guidance: Endpoint definitions
- CDISC ADaM: Data structure standards
- Lan-DeMets: Alpha spending methodology

This schema addresses the "48 fields defined, 10 passed through" bug.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

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


class AlphaSpendingFunction(Enum):
    """Alpha spending functions for interim analysis."""
    OBRIEN_FLEMING = "O'Brien-Fleming"
    POCOCK = "Pocock"
    LAN_DEMETS_OF = "Lan-DeMets (O'Brien-Fleming type)"
    LAN_DEMETS_POCOCK = "Lan-DeMets (Pocock type)"
    HWANG_SHIH_DECANI = "Hwang-Shih-DeCani"
    CUSTOM = "Custom"


class PrimaryTestMethod(Enum):
    """Primary analysis methods for time-to-event."""
    LOG_RANK = "Log-rank test"
    STRATIFIED_LOG_RANK = "Stratified log-rank test"
    WEIGHTED_LOG_RANK = "Weighted log-rank test"
    FLEMING_HARRINGTON = "Fleming-Harrington weighted log-rank"
    MAXCOMBO = "MaxCombo test"
    RMST = "Restricted Mean Survival Time"
    COX_REGRESSION = "Cox proportional hazards"


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


# =============================================================================
# SECTION 2: STUDY DESIGN (Gamble Items 7-15 + FDA Oncology)
# =============================================================================

@dataclass
class StudyDesign:
    """Study design from Gamble et al. Section 3 + FDA Oncology Guidance."""
    # Item 9: Trial design
    design_type: str = "parallel"                 # parallel, crossover, factorial, single_arm
    phase: str = ""                               # 1, 2, 3, 4
    is_randomized: bool = True
    is_blinded: bool = False
    blinding_type: str = ""                       # double-blind, open-label, etc.

    # Treatment arms
    drug_name: str = ""
    drug_class: Optional[str] = None              # immunotherapy, chemotherapy, targeted
    comparator: str = ""
    comparator_type: str = "active"               # active, placebo, SOC

    # Item 10: Randomization
    allocation_ratio: str = "1:1"
    stratification_factors: List[str] = field(default_factory=list)

    # Item 11: Sample size
    sample_size: int = 0
    sample_size_per_arm: Optional[List[int]] = None
    sample_size_rationale: Optional[str] = None

    # Item 12: Framework
    hypothesis_framework: str = "superiority"     # superiority, non_inferiority, equivalence


# =============================================================================
# SECTION 3: ENDPOINTS (FDA Oncology Guidance + CDISC ADaM)
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


@dataclass
class EndpointConfiguration:
    """Complete endpoint setup for the trial."""
    primary_endpoint: Optional[Endpoint] = None
    primary_endpoint_text: str = ""               # Simple text version
    secondary_endpoints: List[str] = field(default_factory=list)
    exploratory_endpoints: List[str] = field(default_factory=list)


# =============================================================================
# SECTION 4: INTERIM ANALYSIS (ICH E9 + Lan-DeMets)
# CRITICAL: These fields caused the 639 vs 382 events bug
# =============================================================================

@dataclass
class InterimAnalysis:
    """
    Interim analysis specification from ICH E9 Section 4.5 + Gamble Items 13a-13c.

    CRITICAL NUMERICAL FIELDS - must be extracted and passed through exactly.
    These are the fields that were missing and caused RAG contamination bugs.
    """
    # Item 13a: Number and timing
    has_interim_analysis: bool = False
    num_interim_analyses: int = 0                 # CRITICAL: 1 vs 2 bug

    # Event counts - CRITICAL numerical fields
    interim_events: Optional[List[int]] = None    # Events at each interim look
    final_events: Optional[int] = None            # CRITICAL: 382 vs 639 bug

    # Information fractions
    information_fractions: Optional[List[float]] = None  # e.g., [0.5, 0.75, 1.0]

    # Item 13b: Alpha adjustment - CRITICAL numerical fields
    alpha_spending_function: str = ""             # O'Brien-Fleming, Lan-DeMets, etc.
    overall_alpha: float = 0.05                   # Total alpha (one or two-sided)
    alpha_sidedness: str = "one-sided"            # one-sided or two-sided
    alpha_at_interim: Optional[List[float]] = None  # CRITICAL: 0.020 vs 0.05 bug
    alpha_at_final: Optional[float] = None        # CRITICAL: 0.044 vs 0.05 bug

    # Item 13c: Stopping guidelines
    efficacy_stopping: bool = True
    futility_stopping: bool = False
    futility_boundary_type: Optional[str] = None  # binding, non-binding
    stopping_boundaries: Optional[str] = None     # Description of boundaries


# =============================================================================
# SECTION 5: STATISTICAL METHODS (Gamble Items 16-20, 27a-27f)
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


# =============================================================================
# SECTION 6: MULTIPLICITY (Gamble Item 17 + FDA)
# =============================================================================

@dataclass
class MultiplicityAdjustment:
    """Multiplicity adjustment from Gamble Item 17 + FDA FWER requirements."""
    has_multiplicity: bool = False
    adjustment_method: Optional[str] = None       # Hierarchical, Hochberg, Holm, etc.
    testing_sequence: List[str] = field(default_factory=list)
    alpha_allocation: Optional[str] = None


# =============================================================================
# SECTION 7: MISSING DATA & CENSORING (Gamble Item 28 + ICH E9(R1))
# =============================================================================

@dataclass
class MissingDataHandling:
    """Missing data handling from ICH E9(R1) Estimand Framework + Gamble Item 28."""
    # Intercurrent events (ICH E9(R1))
    treatment_discontinuation_strategy: str = "treatment_policy"
    subsequent_therapy_handling: str = "censor"

    # Censoring rules (FDA PFS guidance)
    censoring_rules: List[str] = field(default_factory=list)

    # Missing tumor assessments
    missing_assessment_handling: str = "censor_at_last_assessment"

    # Sensitivity for missing data
    sensitivity_methods: List[str] = field(default_factory=list)


# =============================================================================
# SECTION 8: ANALYSIS POPULATIONS (Gamble Item 20)
# =============================================================================

@dataclass
class AnalysisPopulations:
    """Analysis populations from Gamble Item 20."""
    itt_definition: str = "All randomized subjects"
    per_protocol_definition: Optional[str] = None
    safety_population_definition: str = "All subjects who received at least one dose"

    # Oncology-specific
    efficacy_evaluable_definition: Optional[str] = None
    biomarker_evaluable_definition: Optional[str] = None


# =============================================================================
# SECTION 9: CROSSOVER / TREATMENT SWITCHING
# =============================================================================

@dataclass
class CrossoverHandling:
    """Treatment switching/crossover handling."""
    has_crossover: bool = False
    crossover_description: Optional[str] = None
    crossover_adjustment_methods: List[str] = field(default_factory=list)  # RPSFT, IPCW


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

    CRITICAL: This schema ensures all 40+ fields are defined and can be
    passed through the pipeline - fixing the "48 defined, 10 passed" bug.
    """
    # Administrative
    admin: AdministrativeInfo = field(default_factory=AdministrativeInfo)

    # Design
    design: StudyDesign = field(default_factory=StudyDesign)

    # Endpoints (FDA Oncology)
    endpoints: EndpointConfiguration = field(default_factory=EndpointConfiguration)

    # Interim Analysis (ICH E9 + Lan-DeMets) - CRITICAL for numerical accuracy
    interim: InterimAnalysis = field(default_factory=InterimAnalysis)

    # Statistical Methods
    methods: StatisticalMethods = field(default_factory=StatisticalMethods)

    # Multiplicity
    multiplicity: MultiplicityAdjustment = field(default_factory=MultiplicityAdjustment)

    # Missing Data (ICH E9(R1))
    missing_data: MissingDataHandling = field(default_factory=MissingDataHandling)

    # Populations
    populations: AnalysisPopulations = field(default_factory=AnalysisPopulations)

    # Crossover
    crossover: CrossoverHandling = field(default_factory=CrossoverHandling)

    def get_critical_numerical_fields(self) -> Dict[str, Any]:
        """
        Returns all numerical fields that MUST match the protocol exactly.
        These are the fields that caused RAG contamination bugs.
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

            # Effect size
            'expected_hazard_ratio': self.methods.expected_hazard_ratio,
            'power': self.methods.power,
        }

    def validate_completeness(self) -> List[str]:
        """Check which critical fields are missing."""
        missing = []
        critical = self.get_critical_numerical_fields()
        for field_name, value in critical.items():
            if value is None or value == 0 or value == []:
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

            # Design
            'drug_name': self.design.drug_name,
            'comparator': self.design.comparator,
            'indication': self.design.drug_class,
            'phase': self.design.phase,
            'sample_size': self.design.sample_size,
            'allocation_ratio': self.design.allocation_ratio,
            'stratification_factors': self.design.stratification_factors,
            'design_type': self.design.design_type,

            # Endpoints
            'primary_endpoint': self.endpoints.primary_endpoint_text,
            'secondary_endpoints': self.endpoints.secondary_endpoints,

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

            # Methods
            'primary_test': self.methods.primary_test,
            'expected_hazard_ratio': self.methods.expected_hazard_ratio,
            'power': self.methods.power,
            'sensitivity_analyses': self.methods.sensitivity_analyses,
            'subgroup_analyses': self.methods.subgroup_analyses,

            # Multiplicity
            'multiplicity_method': self.multiplicity.adjustment_method,
            'testing_sequence': self.multiplicity.testing_sequence,

            # Crossover
            'has_crossover': self.crossover.has_crossover,
            'crossover_adjustment_methods': self.crossover.crossover_adjustment_methods,

            # Populations
            'itt_definition': self.populations.itt_definition,
            'safety_definition': self.populations.safety_population_definition,
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

    # Design
    facts.design.drug_name = extracted.get('drug_name', '')
    facts.design.comparator = extracted.get('comparator', '')
    facts.design.phase = extracted.get('phase', '')
    facts.design.sample_size = extracted.get('sample_size', 0)
    facts.design.allocation_ratio = extracted.get('randomization_ratio', '1:1')
    facts.design.stratification_factors = extracted.get('stratification_factors', [])
    facts.design.design_type = extracted.get('design_type', 'parallel')
    facts.design.is_randomized = extracted.get('is_randomized', True)

    # Endpoints
    facts.endpoints.primary_endpoint_text = extracted.get('primary_endpoint', '')
    facts.endpoints.secondary_endpoints = extracted.get('secondary_endpoints', [])

    # Interim Analysis - CRITICAL
    facts.interim.has_interim_analysis = extracted.get('has_interim_analysis', False)
    facts.interim.num_interim_analyses = extracted.get('num_interim_analyses', 0)
    facts.interim.interim_events = extracted.get('interim_events', [])
    facts.interim.final_events = extracted.get('final_events') or extracted.get('final_analysis_events')
    facts.interim.information_fractions = extracted.get('interim_information_fraction', [])
    facts.interim.alpha_spending_function = extracted.get('error_spending_function', '')
    facts.interim.overall_alpha = extracted.get('alpha_level', 0.05)
    facts.interim.alpha_at_interim = extracted.get('interim_alpha_spent', [])
    facts.interim.alpha_at_final = extracted.get('alpha_at_final')
    facts.interim.stopping_boundaries = extracted.get('stopping_boundaries', '')

    # Methods
    facts.methods.primary_test = extracted.get('statistical_method', '')
    facts.methods.expected_hazard_ratio = extracted.get('hazard_ratio')
    facts.methods.power = extracted.get('power')
    facts.methods.sensitivity_analyses = extracted.get('sensitivity_methods', [])

    # Crossover
    facts.crossover.has_crossover = extracted.get('crossover_permitted', False) or extracted.get('has_crossover', False)

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
    print("Testing Extraction Schema")
    print("=" * 60)

    # Create sample facts
    facts = ExtractedProtocolFacts()
    facts.admin.nct_id = "NCT02041533"
    facts.design.drug_name = "Nivolumab"
    facts.design.comparator = "Docetaxel"
    facts.design.sample_size = 504
    facts.interim.has_interim_analysis = True
    facts.interim.num_interim_analyses = 1
    facts.interim.interim_events = [291]
    facts.interim.final_events = 382
    facts.interim.alpha_at_interim = [0.020]
    facts.interim.alpha_at_final = 0.044

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
    for key, value in list(flat.items())[:10]:  # First 10
        print(f"  {key}: {value}")
    print(f"  ... and {len(flat) - 10} more fields")
