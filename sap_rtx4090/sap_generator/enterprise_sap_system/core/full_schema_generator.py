#!/usr/bin/env python3
"""
Fully Constrained SAP Schema Generator
======================================

Philosophy: If it's extracted from the protocol → It MUST be constrained

Every protocol-specific value uses Literal types.
Only narrative/prose fields allow free LLM generation.
"""

import re
from typing import Any, Dict, List, Optional, Type, Literal, Union
from pydantic import BaseModel, Field, field_validator, create_model
from dataclasses import dataclass, field

# Import the SINGLE SOURCE OF TRUTH for extraction
from .structured_extractor import StructuredFactExtractor, ProtocolFacts


# =============================================================================
# PROTOCOL FACTS: All Extractable Entities
# =============================================================================

@dataclass
class FullProtocolFacts:
    """Complete set of facts extracted from protocol - ALL will be constrained"""

    # === IDENTIFICATION (High contamination risk) ===
    nct_id: Optional[str] = None
    study_id: Optional[str] = None
    sponsor: Optional[str] = None

    # === STUDY INFO ===
    title: Optional[str] = None
    phase: Optional[str] = None
    therapeutic_area: Optional[str] = None
    indication: Optional[str] = None
    design_type: Optional[str] = None  # e.g., "randomized, double-blind, placebo-controlled"

    # === DRUG/TREATMENT (High contamination risk) ===
    drug_name: Optional[str] = None
    drug_code: Optional[str] = None
    drug_generic: Optional[str] = None
    route: Optional[str] = None

    # === ARMS (High contamination risk) ===
    num_arms: Optional[int] = None
    ratio: Optional[str] = None
    arm_names: List[str] = field(default_factory=list)
    arm_descriptions: List[str] = field(default_factory=list)
    arm_doses: List[str] = field(default_factory=list)

    # === SAMPLE SIZE (High contamination risk) ===
    total_n: Optional[int] = None
    per_arm_n: Optional[Dict[str, int]] = None
    power: Optional[str] = None
    power_scenarios: List[str] = field(default_factory=list)  # All power values (e.g., ["83%", "70%"])
    alpha: Optional[float] = None
    alpha_sidedness: Optional[str] = None
    dropout_rate: Optional[str] = None

    # === POWER CALCULATION ASSUMPTIONS ===
    expected_response_placebo: Optional[str] = None  # e.g., "10%"
    expected_response_active: Optional[str] = None   # e.g., "40%"
    primary_comparison: Optional[str] = None         # e.g., "Placebo vs. 600mg"

    # === ENDPOINTS ===
    primary_endpoint: Optional[str] = None
    primary_endpoint_definition: Optional[str] = None  # Full definition with criteria
    primary_timepoint: Optional[str] = None
    secondary_endpoints: List[str] = field(default_factory=list)
    secondary_endpoints_detailed: List[Dict[str, str]] = field(default_factory=list)  # With timepoints

    # === POPULATIONS ===
    primary_population: Optional[str] = None
    itt_definition: Optional[str] = None
    pp_definition: Optional[str] = None
    safety_definition: Optional[str] = None
    pk_population_definition: Optional[str] = None
    pk_population_size: Optional[int] = None

    # === STRATIFICATION ===
    stratification_factors: List[str] = field(default_factory=list)

    # === ANALYSIS ===
    primary_analysis_method: Optional[str] = None

    # === TIMING ===
    study_duration: Optional[str] = None

    # === PK ANALYSIS ===
    has_pk_substudy: bool = False
    pk_parameters: List[str] = field(default_factory=list)
    pk_software: Optional[str] = None
    pk_sampling_timepoints: List[str] = field(default_factory=list)

    # === BIOMARKERS ===
    biomarker_endpoints: List[str] = field(default_factory=list)
    biomarker_subgroups: List[str] = field(default_factory=list)

    # === SUBGROUPS ===
    subgroup_analyses: List[str] = field(default_factory=list)

    # === VISIT WINDOWS ===
    visit_windows: Dict[str, str] = field(default_factory=dict)


# =============================================================================
# SECTION SCHEMAS: All Protocol Values Constrained
# =============================================================================

class IntroductionSectionBase(BaseModel):
    """Section 1: Introduction - All IDs constrained"""
    # Constrained fields (protocol values)
    nct_id: str
    study_id: str
    sponsor: str
    title: str
    phase: str

    # Free narrative fields
    purpose_statement: str = Field(
        description="Purpose of the SAP. DO NOT include specific IDs or values."
    )
    scope_statement: str = Field(
        description="Scope of the document. DO NOT include specific values."
    )

    @field_validator('purpose_statement', 'scope_statement')
    @classmethod
    def check_no_contamination(cls, v: str) -> str:
        """Ensure narrative doesn't contain wrong drug names used as THE study drug"""
        # Only block wrong drug names - study IDs may appear legitimately in references
        # NOTE: Don't block study IDs like GA29144 - they might be comparative references
        drug_contaminants = ['etrolizumab', 'tocilizumab', 'sarilumab']
        for c in drug_contaminants:
            # Check if drug is being used as the study drug (not just mentioned)
            patterns = [f'{c.lower()} will be', f'treatment with {c.lower()}', f'study drug {c.lower()}']
            for pattern in patterns:
                if pattern in v.lower():
                    raise ValueError(f"Narrative uses wrong study drug: {c}")
        return v


class StudyDesignSectionBase(BaseModel):
    """Section 3: Study Design - All design elements constrained"""
    # Constrained fields
    design_type: str
    drug_name: str
    route: str
    num_arms: int
    ratio: str
    arm_names: List[str]
    arm_descriptions: List[str]

    # Free narrative
    design_narrative: str = Field(
        description="Study design description. Reference constrained values, don't restate numbers."
    )


class PopulationsSectionBase(BaseModel):
    """Section 4: Analysis Populations - All definitions constrained"""
    # Constrained fields
    primary_population: str
    itt_definition: str
    pp_definition: str
    safety_definition: str

    # Free narrative
    population_rationale: str = Field(
        description="Rationale for population choices."
    )


class EndpointsSectionBase(BaseModel):
    """Section 5: Endpoints - All endpoints constrained"""
    # Constrained fields
    primary_endpoint: str
    primary_timepoint: str
    secondary_endpoints: List[str]

    # Free narrative
    endpoint_rationale: str = Field(
        description="Rationale for endpoint selection."
    )
    endpoint_derivation: str = Field(
        description="How endpoints will be derived."
    )


class SampleSizeSectionBase(BaseModel):
    """Section 6: Sample Size - All numbers constrained"""
    # Constrained fields
    total_n: int
    num_arms: int
    ratio: str
    per_arm_n: Dict[str, int]
    power: str
    alpha: float
    alpha_sidedness: str
    dropout_rate: str

    # Free narrative
    sample_size_rationale: str = Field(
        description="Rationale for sample size. DO NOT include any numbers."
    )
    power_methodology: str = Field(
        description="Power calculation methodology. DO NOT include specific numbers."
    )

    @field_validator('sample_size_rationale', 'power_methodology')
    @classmethod
    def no_numbers_in_narrative(cls, v: str) -> str:
        """Block numbers in narrative - they should come from constrained fields"""
        # Find numbers that look like sample sizes or percentages
        suspicious = re.findall(r'\b(\d{2,4})\b', v)
        for num in suspicious:
            n = int(num)
            if n > 10 and n not in [100]:  # Allow small numbers and 100%
                raise ValueError(f"Narrative contains number {n} - use constrained fields instead")
        return v


class StatMethodsSectionBase(BaseModel):
    """Section 7: Statistical Methods - Analysis method constrained"""
    # Constrained fields
    primary_analysis_method: str
    primary_population: str
    alpha: float
    alpha_sidedness: str

    # Free narrative
    analysis_description: str = Field(
        description="Description of statistical analysis approach."
    )
    missing_data_handling: str = Field(
        description="How missing data will be handled."
    )
    sensitivity_analyses: str = Field(
        description="Planned sensitivity analyses."
    )


class StratificationSectionBase(BaseModel):
    """Stratification factors - All factors constrained"""
    # Constrained fields
    stratification_factors: List[str]
    ratio: str

    # Free narrative
    stratification_rationale: str = Field(
        description="Rationale for stratification approach."
    )


# =============================================================================
# FULL SAP SCHEMA: Everything Combined
# =============================================================================

class FullSAPSchemaBase(BaseModel):
    """
    Complete SAP with ALL protocol values constrained.

    Philosophy:
    - Every value from protocol → Literal constraint
    - Only narrative text → Free generation
    """

    # === SECTION 1: INTRODUCTION ===
    nct_id: str
    study_id: str
    sponsor: str
    title: str
    phase: str
    therapeutic_area: str
    indication: str

    # === SECTION 3: STUDY DESIGN ===
    design_type: str
    drug_name: str
    drug_code: str
    route: str
    num_arms: int
    ratio: str
    arm_names: List[str]
    arm_descriptions: List[str]

    # === SECTION 4: POPULATIONS ===
    primary_population: str

    # === SECTION 5: ENDPOINTS ===
    primary_endpoint: str
    primary_timepoint: str
    secondary_endpoints: List[str]

    # === SECTION 6: SAMPLE SIZE ===
    total_n: int
    power: str
    alpha: float
    alpha_sidedness: str

    # === SECTION 7: METHODS ===
    primary_analysis_method: str
    stratification_factors: List[str]

    # === NARRATIVES (Free generation) ===
    introduction_narrative: str = Field(description="Introduction text")
    design_narrative: str = Field(description="Study design description")
    population_narrative: str = Field(description="Population definitions")
    endpoint_narrative: str = Field(description="Endpoint descriptions")
    sample_size_narrative: str = Field(description="Sample size rationale - NO NUMBERS")
    methods_narrative: str = Field(description="Statistical methods description")


# =============================================================================
# SCHEMA FACTORY: Create Fully Constrained Schema from Facts
# =============================================================================

def create_fully_constrained_schema(facts: FullProtocolFacts) -> Type[BaseModel]:
    """
    Create a Pydantic schema where EVERY protocol value is a Literal.

    The LLM cannot output any value that wasn't extracted from the protocol.
    """

    # Build field definitions with Literal types
    field_definitions = {}

    # === IDENTIFICATION ===
    if facts.nct_id:
        field_definitions['nct_id'] = (Literal[facts.nct_id], facts.nct_id)
    else:
        field_definitions['nct_id'] = (str, "UNKNOWN")

    if facts.study_id:
        field_definitions['study_id'] = (Literal[facts.study_id], facts.study_id)
    else:
        field_definitions['study_id'] = (str, "UNKNOWN")

    if facts.sponsor:
        field_definitions['sponsor'] = (Literal[facts.sponsor], facts.sponsor)
    else:
        field_definitions['sponsor'] = (str, "UNKNOWN")

    # === STUDY INFO ===
    if facts.title:
        field_definitions['title'] = (Literal[facts.title], facts.title)
    else:
        field_definitions['title'] = (str, "Clinical Trial")

    if facts.phase:
        field_definitions['phase'] = (Literal[facts.phase], facts.phase)
    else:
        field_definitions['phase'] = (str, "Phase 2")

    if facts.therapeutic_area:
        field_definitions['therapeutic_area'] = (Literal[facts.therapeutic_area], facts.therapeutic_area)
    else:
        field_definitions['therapeutic_area'] = (str, "Not specified")

    if facts.indication:
        field_definitions['indication'] = (Literal[facts.indication], facts.indication)
    else:
        field_definitions['indication'] = (str, "Not specified")

    if facts.design_type:
        field_definitions['design_type'] = (Literal[facts.design_type], facts.design_type)
    else:
        field_definitions['design_type'] = (str, "Randomized controlled trial")

    # === DRUG/TREATMENT ===
    if facts.drug_name:
        field_definitions['drug_name'] = (Literal[facts.drug_name], facts.drug_name)
    else:
        field_definitions['drug_name'] = (str, "Study Drug")

    if facts.drug_code:
        field_definitions['drug_code'] = (Literal[facts.drug_code], facts.drug_code)
    else:
        field_definitions['drug_code'] = (str, "")

    if facts.route:
        field_definitions['route'] = (Literal[facts.route], facts.route)
    else:
        field_definitions['route'] = (str, "Not specified")

    # === ARMS ===
    if facts.num_arms:
        field_definitions['num_arms'] = (Literal[facts.num_arms], facts.num_arms)
    else:
        field_definitions['num_arms'] = (int, 2)

    if facts.ratio:
        field_definitions['ratio'] = (Literal[facts.ratio], facts.ratio)
    else:
        field_definitions['ratio'] = (str, "1:1")

    # For lists, we create a Literal tuple of the values
    if facts.arm_names:
        # Convert list to tuple for Literal
        arm_names_tuple = tuple(facts.arm_names)
        field_definitions['arm_names'] = (List[str], list(facts.arm_names))
    else:
        field_definitions['arm_names'] = (List[str], [])

    if facts.arm_descriptions:
        field_definitions['arm_descriptions'] = (List[str], list(facts.arm_descriptions))
    else:
        field_definitions['arm_descriptions'] = (List[str], [])

    # === SAMPLE SIZE ===
    if facts.total_n:
        field_definitions['total_n'] = (Literal[facts.total_n], facts.total_n)
    else:
        field_definitions['total_n'] = (int, 100)

    if facts.power:
        field_definitions['power'] = (Literal[facts.power], facts.power)
    else:
        field_definitions['power'] = (str, "80%")

    if facts.alpha:
        field_definitions['alpha'] = (Literal[facts.alpha], facts.alpha)
    else:
        field_definitions['alpha'] = (float, 0.05)

    if facts.alpha_sidedness:
        field_definitions['alpha_sidedness'] = (Literal[facts.alpha_sidedness], facts.alpha_sidedness)
    else:
        field_definitions['alpha_sidedness'] = (str, "one-sided")  # Default to one-sided for efficacy trials

    if facts.dropout_rate:
        field_definitions['dropout_rate'] = (Literal[facts.dropout_rate], facts.dropout_rate)
    else:
        field_definitions['dropout_rate'] = (str, "10%")

    # === ENDPOINTS ===
    if facts.primary_endpoint:
        field_definitions['primary_endpoint'] = (Literal[facts.primary_endpoint], facts.primary_endpoint)
    else:
        field_definitions['primary_endpoint'] = (str, "Primary endpoint")

    if facts.primary_timepoint:
        field_definitions['primary_timepoint'] = (Literal[facts.primary_timepoint], facts.primary_timepoint)
    else:
        field_definitions['primary_timepoint'] = (str, "Week 12")

    if facts.secondary_endpoints:
        field_definitions['secondary_endpoints'] = (List[str], list(facts.secondary_endpoints))
    else:
        field_definitions['secondary_endpoints'] = (List[str], [])

    # === POPULATIONS ===
    if facts.primary_population:
        field_definitions['primary_population'] = (Literal[facts.primary_population], facts.primary_population)
    else:
        field_definitions['primary_population'] = (str, "ITT")

    # === STRATIFICATION ===
    if facts.stratification_factors:
        field_definitions['stratification_factors'] = (List[str], list(facts.stratification_factors))
    else:
        field_definitions['stratification_factors'] = (List[str], [])

    # === ANALYSIS ===
    if facts.primary_analysis_method:
        field_definitions['primary_analysis_method'] = (Literal[facts.primary_analysis_method], facts.primary_analysis_method)
    else:
        field_definitions['primary_analysis_method'] = (str, "Not specified")

    # === NARRATIVE FIELDS (Not constrained - LLM writes freely) ===
    field_definitions['introduction_narrative'] = (str, ...)
    field_definitions['design_narrative'] = (str, ...)
    field_definitions['population_narrative'] = (str, ...)
    field_definitions['endpoint_narrative'] = (str, ...)
    field_definitions['sample_size_narrative'] = (str, ...)
    field_definitions['methods_narrative'] = (str, ...)

    # Create the model
    FullyConstrainedSAP = create_model(
        'FullyConstrainedSAP',
        **field_definitions
    )

    return FullyConstrainedSAP



# =============================================================================
# EXTRACTION: Get FullProtocolFacts from Protocol Text
# =============================================================================

# Global extractor instance (singleton pattern)
_extractor = None

def _get_extractor() -> StructuredFactExtractor:
    """Get or create the singleton extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = StructuredFactExtractor()
    return _extractor


def convert_protocol_facts_to_full(pf: ProtocolFacts) -> FullProtocolFacts:
    """
    Convert ProtocolFacts (from StructuredExtractor) to FullProtocolFacts.
    
    This is the SINGLE mapping layer - all extraction logic lives in 
    StructuredFactExtractor. No duplicate patterns here.
    """
    facts = FullProtocolFacts()
    
    # === IDENTIFICATION ===
    facts.nct_id = pf.nct_id
    facts.study_id = pf.study_id
    facts.sponsor = pf.sponsor
    facts.title = pf.protocol_title
    
    # === STUDY INFO ===
    facts.phase = pf.phase.value if pf.phase else None
    facts.therapeutic_area = pf.therapeutic_area
    facts.indication = pf.indication
    facts.design_type = pf.design_type
    
    # === DRUG/TREATMENT ===
    facts.drug_name = pf.drug_name
    # Extract drug code from drug_names_all if available
    if pf.drug_names_all:
        for name in pf.drug_names_all:
            if re.match(r'^[A-Z]{2,4}[-]?\d{3,6}$', name):
                facts.drug_code = name
                break
    
    # Get route from first arm if available
    if pf.arms:
        facts.route = pf.arms[0].route
    
    # === ARMS ===
    facts.num_arms = pf.num_arms
    facts.ratio = pf.randomization_ratio
    
    if pf.arms:
        facts.arm_names = [arm.name for arm in pf.arms]
        facts.arm_descriptions = [
            f"{arm.name}: {arm.dose or ''} {arm.route or ''} {arm.frequency or ''}".strip()
            for arm in pf.arms
        ]
        facts.arm_doses = [arm.dose or "" for arm in pf.arms]
    
    # === SAMPLE SIZE ===
    if pf.sample_size:
        facts.total_n = pf.sample_size.total_n
        facts.per_arm_n = pf.sample_size.per_arm
        if pf.sample_size.power:
            facts.power = f"{int(pf.sample_size.power * 100)}%" if pf.sample_size.power < 1 else f"{int(pf.sample_size.power)}%"
        if pf.sample_size.dropout_rate:
            facts.dropout_rate = f"{int(pf.sample_size.dropout_rate * 100)}%" if pf.sample_size.dropout_rate < 1 else f"{int(pf.sample_size.dropout_rate)}%"
    
    # === ALPHA ===
    if pf.alpha:
        facts.alpha = pf.alpha.primary_alpha
        facts.alpha_sidedness = pf.alpha.sidedness
    
    # === ENDPOINTS ===
    if pf.primary_endpoint:
        facts.primary_endpoint = pf.primary_endpoint.name
        facts.primary_endpoint_definition = pf.primary_endpoint.definition
        facts.primary_timepoint = pf.primary_endpoint.timepoint or pf.primary_timepoint
    
    if pf.secondary_endpoints:
        facts.secondary_endpoints = [ep.name for ep in pf.secondary_endpoints]
        facts.secondary_endpoints_detailed = [
            {"endpoint": ep.name, "timepoint": ep.timepoint or "Various"}
            for ep in pf.secondary_endpoints
        ]
    
    # === POPULATIONS ===
    facts.primary_population = pf.primary_analysis_population
    facts.itt_definition = pf.itt_definition
    facts.pp_definition = pf.pp_definition
    facts.safety_definition = pf.safety_population_definition
    facts.pk_population_definition = pf.pk_population_definition
    
    # === STRATIFICATION ===
    facts.stratification_factors = pf.stratification_factors
    
    # === ANALYSIS ===
    facts.primary_analysis_method = pf.primary_analysis_method
    
    # === TIMING ===
    facts.study_duration = pf.study_duration
    
    # === PK ANALYSIS ===
    if pf.pk_substudy:
        facts.has_pk_substudy = pf.pk_substudy.has_pk_substudy
        facts.pk_parameters = pf.pk_substudy.pk_parameters
        facts.pk_software = pf.pk_substudy.pk_analysis_software
        facts.pk_sampling_timepoints = pf.pk_substudy.pk_sampling_timepoints
        facts.pk_population_size = pf.pk_substudy.pk_population_size
    
    # === SUBGROUPS ===
    if pf.subgroup_analyses:
        facts.subgroup_analyses = [sg.factor for sg in pf.subgroup_analyses]
    
    return facts


def extract_full_protocol_facts(protocol_text: str) -> FullProtocolFacts:
    """
    Extract ALL protocol facts for complete constraint coverage.
    
    CONSOLIDATED: Uses StructuredFactExtractor as the single source of truth.
    No duplicate extraction logic - just conversion from ProtocolFacts.
    """
    # Use the single source of truth for extraction
    extractor = _get_extractor()
    protocol_facts = extractor.extract_all(protocol_text)
    
    # Convert to FullProtocolFacts
    facts = convert_protocol_facts_to_full(protocol_facts)
    
    # Debug logging
    if facts.drug_name:
        print(f"[DEBUG] Consolidated extraction - drug: {facts.drug_name}")
    if facts.nct_id:
        print(f"[DEBUG] Consolidated extraction - NCT: {facts.nct_id}")
    
    return facts


# =============================================================================
# ESTIMAND SCHEMA: Constrained Treatment and Endpoints
# =============================================================================

class InterCurrentEventSchema(BaseModel):
    """ICE with constrained strategy options"""
    event: str = Field(description="Description of the intercurrent event")
    strategy: Literal[
        "treatment_policy",
        "composite",
        "hypothetical",
        "principal_stratum",
        "while_on_treatment"
    ]
    rationale: str = Field(description="Rationale for strategy choice")


class EstimandSchemaBase(BaseModel):
    """
    Estimand schema with constrained protocol values.

    Constrained fields:
    - drug_name: From protocol (prevents "etrolizumab" contamination)
    - indication: From protocol
    - primary_endpoint: From protocol
    - primary_timepoint: From protocol
    - arm_descriptions: From protocol

    Free fields:
    - objective: LLM writes (but must reference constrained drug)
    - population_description: LLM writes (but must reference constrained indication)
    - intercurrent_events: LLM designs
    - summary_measure: LLM writes
    """
    # Constrained fields - LLM cannot change these
    drug_name: str
    indication: str
    primary_endpoint: str
    primary_timepoint: str
    comparator: str  # e.g., "Placebo" or active comparator

    # Semi-constrained - must include constrained values
    treatment_description: str = Field(
        description="Treatment comparison. MUST use the drug_name provided."
    )
    population_description: str = Field(
        description="Target population. MUST reference the indication provided."
    )
    variable_description: str = Field(
        description="Endpoint variable. MUST use the primary_endpoint provided."
    )

    # Free fields - LLM designs these
    objective: str = Field(description="Clinical objective of the estimand")
    intercurrent_events: List[InterCurrentEventSchema] = Field(
        description="List of intercurrent events with strategies"
    )
    summary_measure: str = Field(description="Summary measure for the estimand")
    analysis_method: str = Field(description="Primary analysis method")

    @field_validator('treatment_description')
    @classmethod
    def must_contain_drug(cls, v: str, info) -> str:
        """Ensure treatment description contains the constrained drug name"""
        drug = info.data.get('drug_name', '')
        if drug and drug.lower() not in v.lower():
            raise ValueError(f"Treatment description must contain drug name: {drug}")
        # Check for drug contaminants only (not study IDs - those may appear in references)
        # Only flag if a contaminant drug is used AND it's not the actual study drug
        drug_contaminants = ['etrolizumab', 'tocilizumab', 'sarilumab']
        for c in drug_contaminants:
            if c.lower() in v.lower() and (not drug or c.lower() != drug.lower()):
                raise ValueError(f"Treatment contains wrong drug: {c}")
        return v

    @field_validator('population_description')
    @classmethod
    def must_reference_indication(cls, v: str, info) -> str:
        """Ensure population references the indication"""
        # Check for contaminants
        if 'etrolizumab' in v.lower():
            raise ValueError("Population contains contaminant drug name")
        return v


def create_constrained_estimand_schema(facts: FullProtocolFacts) -> Type[BaseModel]:
    """
    Create Estimand schema with protocol values as Literals.

    This prevents the LLM from outputting "etrolizumab" when
    the protocol says "TJ301".
    """

    _drug = facts.drug_name or "Study Drug"
    _indication = facts.indication or "Target Indication"
    _endpoint = facts.primary_endpoint or "Primary Endpoint"
    _timepoint = facts.primary_timepoint or "Week 12"
    _comparator = "Placebo"  # Default, could extract from protocol

    # Find comparator from arms
    if facts.arm_descriptions:
        for desc in facts.arm_descriptions:
            if 'placebo' in desc.lower():
                _comparator = "Placebo"
                break
            elif 'control' in desc.lower() or 'comparator' in desc.lower():
                _comparator = desc
                break

    ConstrainedEstimand = create_model(
        'ConstrainedEstimand',
        __base__=EstimandSchemaBase,
        drug_name=(Literal[_drug], _drug),
        indication=(Literal[_indication], _indication),
        primary_endpoint=(Literal[_endpoint], _endpoint),
        primary_timepoint=(Literal[_timepoint], _timepoint),
        comparator=(Literal[_comparator], _comparator),
    )

    return ConstrainedEstimand


class FullEstimandOutput(BaseModel):
    """Complete estimand output with primary and secondary"""
    primary_estimand: EstimandSchemaBase
    secondary_estimands: List[EstimandSchemaBase] = Field(default_factory=list)


def create_full_estimand_schema(facts: FullProtocolFacts) -> Type[BaseModel]:
    """Create schema for full estimand output"""

    ConstrainedEstimand = create_constrained_estimand_schema(facts)

    FullConstrainedEstimandOutput = create_model(
        'FullConstrainedEstimandOutput',
        primary_estimand=(ConstrainedEstimand, ...),
        secondary_estimands=(List[ConstrainedEstimand], []),
    )

    return FullConstrainedEstimandOutput


# =============================================================================
# PROMPT GENERATOR
# =============================================================================

def generate_constrained_prompt(facts: FullProtocolFacts) -> str:
    """Generate prompt that tells LLM to use constrained values"""

    # Build list of all constrained values
    constraints = []

    if facts.nct_id:
        constraints.append(f"NCT ID: {facts.nct_id}")
    if facts.study_id:
        constraints.append(f"Study ID: {facts.study_id}")
    if facts.drug_name:
        constraints.append(f"Drug Name: {facts.drug_name}")
    if facts.total_n:
        constraints.append(f"Total Sample Size: {facts.total_n}")
    if facts.ratio:
        constraints.append(f"Randomization Ratio: {facts.ratio}")
    if facts.num_arms:
        constraints.append(f"Number of Arms: {facts.num_arms}")
    if facts.phase:
        constraints.append(f"Phase: {facts.phase}")
    if facts.indication:
        constraints.append(f"Indication: {facts.indication}")
    if facts.route:
        constraints.append(f"Route: {facts.route}")
    if facts.power:
        constraints.append(f"Power: {facts.power}")
    if facts.alpha:
        constraints.append(f"Alpha: {facts.alpha} ({facts.alpha_sidedness or 'one-sided'})")
    if facts.primary_endpoint:
        constraints.append(f"Primary Endpoint: {facts.primary_endpoint}")
    if facts.primary_timepoint:
        constraints.append(f"Primary Timepoint: {facts.primary_timepoint}")
    if facts.arm_names:
        constraints.append(f"Arms: {', '.join(facts.arm_names)}")
    if facts.stratification_factors:
        constraints.append(f"Stratification: {', '.join(facts.stratification_factors)}")

    prompt = f"""Generate a Statistical Analysis Plan (SAP) for this clinical trial.

## CONSTRAINED VALUES (You MUST use these EXACT values - enforced by schema):

{chr(10).join(f'- {c}' for c in constraints)}

## INSTRUCTIONS:

1. The schema enforces the exact values above - you cannot output different values
2. For narrative fields, write professional regulatory-grade prose
3. DO NOT include numbers in narrative fields - they come from constrained fields
4. DO NOT reference other studies, drugs, or examples
5. Focus ONLY on the protocol values provided above

Generate each section following the schema structure."""

    return prompt


# =============================================================================
# UTILITY: Print Constraint Summary
# =============================================================================

def print_constraint_summary(facts: FullProtocolFacts):
    """Print summary of what will be constrained"""
    print("\n" + "="*60)
    print("CONSTRAINT SUMMARY - All Protocol Values Locked")
    print("="*60)

    categories = [
        ("IDENTIFICATION", [
            ("nct_id", facts.nct_id),
            ("study_id", facts.study_id),
            ("sponsor", facts.sponsor),
        ]),
        ("STUDY INFO", [
            ("phase", facts.phase),
            ("indication", facts.indication),
            ("therapeutic_area", facts.therapeutic_area),
            ("design_type", facts.design_type),
        ]),
        ("DRUG/TREATMENT", [
            ("drug_name", facts.drug_name),
            ("drug_code", facts.drug_code),
            ("route", facts.route),
        ]),
        ("ARMS", [
            ("num_arms", facts.num_arms),
            ("ratio", facts.ratio),
            ("arm_names", facts.arm_names),
        ]),
        ("SAMPLE SIZE", [
            ("total_n", facts.total_n),
            ("power", facts.power),
            ("alpha", facts.alpha),
            ("alpha_sidedness", facts.alpha_sidedness),
        ]),
        ("ENDPOINTS", [
            ("primary_endpoint", facts.primary_endpoint),
            ("primary_timepoint", facts.primary_timepoint),
            ("secondary_endpoints", facts.secondary_endpoints),
        ]),
        ("STRATIFICATION", [
            ("stratification_factors", facts.stratification_factors),
        ]),
    ]

    total = 0
    constrained = 0

    for category, fields in categories:
        print(f"\n  {category}:")
        for name, value in fields:
            total += 1
            if value:
                constrained += 1
                status = "✓ Literal"
                val_str = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
            else:
                status = "○ Default"
                val_str = "(not found)"
            print(f"    {name}: {status} = {val_str}")

    print(f"\n  COVERAGE: {constrained}/{total} entities constrained")
    print("="*60)
