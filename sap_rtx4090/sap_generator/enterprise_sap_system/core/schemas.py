#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Data Schemas
=================================================
Structured data types for protocol parsing and SAP generation.
Based on ICH E9(R1) Estimand Framework and CDISC Standards.

This module provides:
1. Legacy dataclass-based schemas (ParsedProtocol, Estimand, etc.)
2. New Pydantic-based unified schema (ProtocolData) with all 55+ fields
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import json
from datetime import datetime

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object  # type: ignore
    def Field(*args, **kwargs):  # type: ignore
        return kwargs.get('default', None)


# ============================================================
# ENUMS
# ============================================================

class StudyPhase(Enum):
    """Clinical trial phases"""
    PHASE_1 = "1"
    PHASE_1A = "1a"
    PHASE_1B = "1b"
    PHASE_1_2 = "1/2"
    PHASE_2 = "2"
    PHASE_2A = "2a"
    PHASE_2B = "2b"
    PHASE_2_3 = "2/3"
    PHASE_3 = "3"
    PHASE_3A = "3a"
    PHASE_3B = "3b"
    PHASE_4 = "4"
    UNKNOWN = "unknown"


class EndpointType(Enum):
    """Primary endpoint types"""
    SAFETY = "SAFETY"
    ORR = "ORR"      # Objective Response Rate
    PFS = "PFS"      # Progression-Free Survival
    OS = "OS"        # Overall Survival
    DFS = "DFS"      # Disease-Free Survival
    EFS = "EFS"      # Event-Free Survival
    PK = "PK"        # Pharmacokinetic
    EFFICACY = "EFFICACY"  # General efficacy (IBD remission, ACR20, PASI, etc.)
    OTHER = "OTHER"


class ICEStrategy(Enum):
    """Intercurrent Event Strategies per ICH E9(R1)"""
    TREATMENT_POLICY = "treatment_policy"
    COMPOSITE = "composite"
    HYPOTHETICAL = "hypothetical"
    PRINCIPAL_STRATUM = "principal_stratum"
    WHILE_ON_TREATMENT = "while_on_treatment"


class PopulationType(Enum):
    """Analysis population types"""
    ITT = "ITT"           # Intent-to-Treat
    MITT = "mITT"         # Modified Intent-to-Treat
    PP = "PP"             # Per-Protocol
    SAFETY = "Safety"
    PK = "PK"
    EVALUABLE = "Evaluable"


class DesignType(Enum):
    """Study design types"""
    PARALLEL = "parallel"
    CROSSOVER = "crossover"
    SINGLE_ARM = "single_arm"
    ADAPTIVE = "adaptive"
    FACTORIAL = "factorial"
    PLATFORM = "platform"


class BlindingType(Enum):
    """Blinding types"""
    OPEN_LABEL = "open_label"
    SINGLE_BLIND = "single_blind"
    DOUBLE_BLIND = "double_blind"
    TRIPLE_BLIND = "triple_blind"


# ============================================================
# CORE DATA STRUCTURES
# ============================================================

@dataclass
class InterCurrentEvent:
    """ICH E9(R1) Intercurrent Event Definition"""
    event: str                    # Description of the event
    strategy: ICEStrategy         # How to handle in analysis
    rationale: str               # Justification for strategy choice
    examples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "event": self.event,
            "strategy": self.strategy.value,
            "rationale": self.rationale,
            "examples": self.examples
        }


@dataclass
class Estimand:
    """
    ICH E9(R1) Estimand Framework
    All 5 attributes are required for regulatory compliance.
    """
    objective: str               # What clinical question
    population: str              # Target population
    treatment: str               # Treatment condition
    variable: str                # Endpoint variable
    variable_type: EndpointType  # Endpoint classification
    intercurrent_events: List[InterCurrentEvent]
    summary_measure: str         # Population-level statistic
    analysis_method: str         # Statistical method to use
    is_primary: bool = False
    confidence: float = 1.0

    def to_dict(self) -> Dict:
        return {
            "objective": self.objective,
            "population": self.population,
            "treatment": self.treatment,
            "variable": self.variable,
            "variable_type": self.variable_type.value,
            "intercurrent_events": [ice.to_dict() for ice in self.intercurrent_events],
            "summary_measure": self.summary_measure,
            "analysis_method": self.analysis_method,
            "is_primary": self.is_primary,
            "confidence": self.confidence
        }

    def validate(self) -> List[str]:
        """Validate estimand completeness per ICH E9(R1)"""
        issues = []
        if not self.population:
            issues.append("Missing: Population specification")
        if not self.treatment:
            issues.append("Missing: Treatment specification")
        if not self.variable:
            issues.append("Missing: Variable (endpoint) specification")
        if not self.intercurrent_events:
            issues.append("Missing: Intercurrent event strategies")
        if not self.summary_measure:
            issues.append("Missing: Summary measure")
        return issues


@dataclass
class TreatmentArm:
    """
    Treatment arm definition (legacy dataclass).

    DEPRECATED: Use TreatmentArmModel (Pydantic) instead.
    This class is kept for backwards compatibility only.
    The canonical definition is TreatmentArmModel defined later in this file.
    """
    name: str
    description: str = ""  # Made optional with default for compatibility
    dose: Optional[str] = None
    schedule: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None  # Added for compatibility
    n_patients: Optional[int] = None  # Added for compatibility
    is_control: bool = False
    is_placebo: bool = False  # Added for compatibility
    is_active_comparator: bool = False

    def __post_init__(self):
        # Auto-populate description if not provided
        if not self.description:
            self.description = self.name


@dataclass
class SampleSizeCalc:
    """Sample size calculation details"""
    total_n: int
    per_arm_n: Dict[str, int]
    power: float
    alpha: float
    effect_size: Optional[float] = None
    assumptions: Dict[str, Any] = field(default_factory=dict)
    method: str = ""
    formula: str = ""
    source: str = ""


@dataclass
class AnalysisPopulation:
    """Analysis population definition"""
    name: str
    type: PopulationType
    definition: str
    inclusion_criteria: List[str] = field(default_factory=list)
    exclusion_criteria: List[str] = field(default_factory=list)
    primary_for: List[str] = field(default_factory=list)  # Which analyses use this


@dataclass
class StatisticalMethod:
    """Statistical method specification"""
    name: str
    description: str
    application: str           # What it's used for
    assumptions: List[str]
    implementation: str        # SAS/R code reference
    references: List[str] = field(default_factory=list)
    sensitivity_analyses: List[str] = field(default_factory=list)


@dataclass
class ParsedProtocol:
    """
    Fully parsed clinical trial protocol
    Contains all extracted and structured information.
    """
    # Identifiers
    nct_id: str
    protocol_number: str = ""
    sponsor: str = ""
    study_title: str = ""

    # Classification
    therapeutic_area: str = ""
    indication: str = ""
    phase: StudyPhase = StudyPhase.UNKNOWN

    # ICH E9(R1) Estimands
    primary_estimand: Optional[Estimand] = None
    secondary_estimands: List[Estimand] = field(default_factory=list)
    exploratory_estimands: List[Estimand] = field(default_factory=list)

    # Study Design
    design_type: DesignType = DesignType.PARALLEL
    randomization_ratio: str = ""
    stratification_factors: List[str] = field(default_factory=list)
    blinding: BlindingType = BlindingType.OPEN_LABEL

    # Populations
    populations: List[AnalysisPopulation] = field(default_factory=list)

    # Sample Size
    sample_size: Optional[SampleSizeCalc] = None

    # Treatment Arms
    arms: List[TreatmentArm] = field(default_factory=list)

    # Methods (extracted or inferred)
    statistical_methods: List[StatisticalMethod] = field(default_factory=list)

    # Metadata
    extraction_confidence: Dict[str, float] = field(default_factory=dict)
    extraction_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    raw_text_length: int = 0
    _raw_text: str = ""  # Store for downstream faithfulness checks

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "nct_id": self.nct_id,
            "protocol_number": self.protocol_number,
            "sponsor": self.sponsor,
            "study_title": self.study_title,
            "therapeutic_area": self.therapeutic_area,
            "indication": self.indication,
            "phase": self.phase.value if isinstance(self.phase, StudyPhase) else self.phase,
            "primary_estimand": self.primary_estimand.to_dict() if self.primary_estimand else None,
            "secondary_estimands": [e.to_dict() for e in self.secondary_estimands],
            "design_type": self.design_type.value if isinstance(self.design_type, DesignType) else self.design_type,
            "randomization_ratio": self.randomization_ratio,
            "stratification_factors": self.stratification_factors,
            "blinding": self.blinding.value if isinstance(self.blinding, BlindingType) else self.blinding,
            "populations": [{"name": p.name, "type": p.type.value, "definition": p.definition} for p in self.populations],
            "sample_size": {
                "total_n": self.sample_size.total_n,
                "power": self.sample_size.power,
                "alpha": self.sample_size.alpha,
                "assumptions": self.sample_size.assumptions
            } if self.sample_size else None,
            "arms": [{"name": a.name, "description": a.description} for a in self.arms],
            "extraction_confidence": self.extraction_confidence,
            "extraction_timestamp": self.extraction_timestamp
        }

    def to_text(self) -> str:
        """Convert to text representation for embedding"""
        parts = [
            f"NCT ID: {self.nct_id}",
            f"Title: {self.study_title}",
            f"Phase: {self.phase.value if isinstance(self.phase, StudyPhase) else self.phase}",
            f"Therapeutic Area: {self.therapeutic_area}",
            f"Indication: {self.indication}",
            f"Design: {self.design_type.value if isinstance(self.design_type, DesignType) else self.design_type}",
        ]
        if self.primary_estimand:
            parts.append(f"Primary Endpoint: {self.primary_estimand.variable}")
            parts.append(f"Endpoint Type: {self.primary_estimand.variable_type.value}")
        return " | ".join(parts)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class SAPExamplePair:
    """
    Protocol-SAP pair for few-shot learning
    """
    # Identifiers
    nct_id: str
    sponsor: str = ""
    year: int = 0

    # Protocol Content
    protocol_text: str = ""
    protocol_parsed: Optional[ParsedProtocol] = None

    # SAP Content
    sap_text: str = ""
    sap_sections: Dict[str, str] = field(default_factory=dict)

    # Metadata for matching
    therapeutic_area: str = ""
    phase: str = ""
    primary_endpoint_type: str = ""
    design: str = ""

    # Quality metrics
    regulatory_outcome: str = "unknown"
    source_quality: float = 0.8

    # Embeddings (to be computed)
    protocol_embedding: Optional[List[float]] = None
    sap_embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict:
        return {
            "nct_id": self.nct_id,
            "sponsor": self.sponsor,
            "year": self.year,
            "therapeutic_area": self.therapeutic_area,
            "phase": self.phase,
            "primary_endpoint_type": self.primary_endpoint_type,
            "design": self.design,
            "regulatory_outcome": self.regulatory_outcome,
            "source_quality": self.source_quality
        }


@dataclass
class QualityReport:
    """Quality assessment report for generated SAP"""
    overall_score: float
    ich_e9r1_compliance: float
    estimand_completeness: float
    cdisc_alignment: float
    statistical_soundness: float
    consistency_score: float
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    section_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class GeneratedSAP:
    """Complete generated SAP document with metadata"""
    # Content
    sections: Dict[str, str]
    full_document: str

    # Source information
    protocol_id: str
    parsed_protocol: ParsedProtocol
    estimands: List[Estimand]

    # Quality
    quality_report: QualityReport

    # Metadata
    generation_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    model_used: str = ""
    few_shot_examples_used: List[str] = field(default_factory=list)
    rag_context_used: bool = False

    def to_dict(self) -> Dict:
        return {
            "protocol_id": self.protocol_id,
            "sections": self.sections,
            "quality_report": {
                "overall_score": self.quality_report.overall_score,
                "ich_e9r1_compliance": self.quality_report.ich_e9r1_compliance,
                "issues": self.quality_report.issues
            },
            "generation_timestamp": self.generation_timestamp,
            "model_used": self.model_used
        }


# ============================================================
# UNIFIED PYDANTIC SCHEMAS (Replaces structured_extractor.py)
# ============================================================
# These are the canonical definitions used throughout the pipeline.
# All 55+ fields for comprehensive protocol extraction.

import re

class RouteOfAdministration(str, Enum):
    """Route of drug administration"""
    IV = "intravenous"
    SC = "subcutaneous"
    IM = "intramuscular"
    ORAL = "oral"
    TOPICAL = "topical"
    INHALED = "inhaled"
    OTHER = "other"


class TrialDesignType(str, Enum):
    """Trial design type - determines template selection and statistical approach"""
    SINGLE_ARM = "single_arm"
    RANDOMIZED_CONTROLLED = "randomized_controlled"
    RANDOMIZED_OPEN_LABEL = "randomized_open_label"
    NON_RANDOMIZED_COMPARATIVE = "non_randomized_comparative"
    UNKNOWN = "unknown"


if PYDANTIC_AVAILABLE:
    class TreatmentArmModel(BaseModel):
        """
        Treatment arm definition (Pydantic model).
        This is the canonical definition used throughout the pipeline.
        """
        name: str
        description: Optional[str] = None
        dose: Optional[str] = None
        schedule: Optional[str] = None
        route: Optional[str] = None
        frequency: Optional[str] = None
        n_patients: Optional[int] = None
        is_placebo: bool = False
        is_control: bool = False
        is_active_comparator: bool = False

        def __init__(self, **data):
            if 'description' not in data or data.get('description') is None:
                data['description'] = data.get('name', '')
            super().__init__(**data)

        class Config:
            extra = 'allow'

    class EndpointDefinition(BaseModel):
        """Definition of a clinical endpoint"""
        name: str
        definition: str
        timepoint: Optional[str] = None
        scoring_system: Optional[str] = None
        components: List[str] = Field(default_factory=list)

        class Config:
            extra = 'allow'

    class AlphaSpecification(BaseModel):
        """Alpha/significance level specification"""
        primary_alpha: float = 0.05
        sidedness: str = "two-sided"
        additional_levels: List[float] = Field(default_factory=list)
        multiplicity_adjustment: Optional[str] = None

        class Config:
            extra = 'allow'

    class SampleSizeSpec(BaseModel):
        """Sample size specification"""
        total_n: int = 0
        per_arm: Dict[str, int] = Field(default_factory=dict)
        power: Optional[float] = None
        effect_size: Optional[str] = None
        dropout_rate: Optional[float] = None

        class Config:
            extra = 'allow'

    class PKSubstudy(BaseModel):
        """PK substudy specification"""
        has_pk_substudy: bool = False
        pk_population_size: Optional[int] = None
        pk_sampling_timepoints: List[str] = Field(default_factory=list)
        pk_parameters: List[str] = Field(default_factory=list)
        pk_analysis_software: Optional[str] = None

        class Config:
            extra = 'allow'

    class ImmunogenicityAssessment(BaseModel):
        """Immunogenicity/ADA specification"""
        has_immunogenicity: bool = False
        ada_sampling_timepoints: List[str] = Field(default_factory=list)
        antibody_type: Optional[str] = None
        assay_method: Optional[str] = None

        class Config:
            extra = 'allow'

    class SubgroupAnalysisSpec(BaseModel):
        """Subgroup analysis specification"""
        factor: str
        categories: List[str] = Field(default_factory=list)
        rationale: Optional[str] = None

        class Config:
            extra = 'allow'

    class InterimAnalysisSpec(BaseModel):
        """Interim analysis specification"""
        has_interim: bool = False
        interim_timepoints: List[str] = Field(default_factory=list)
        monitoring_committee: Optional[str] = None
        stopping_rules: List[str] = Field(default_factory=list)

        class Config:
            extra = 'allow'

    class ProtocolFacts(BaseModel):
        """
        Complete structured facts extracted from protocol.
        This is the SINGLE SOURCE OF TRUTH for SAP generation.
        Contains all 55+ fields for comprehensive extraction.
        """
        # ===== IDENTIFIERS (4 fields) =====
        nct_id: Optional[str] = None
        study_id: Optional[str] = None
        protocol_title: Optional[str] = None
        sponsor: Optional[str] = None

        # ===== STUDY DESIGN (6 fields) =====
        phase: str = "Unknown"
        therapeutic_area: Optional[str] = None
        indication: Optional[str] = None
        design_type: Optional[str] = None
        is_blinded: bool = False
        blinding_type: Optional[str] = None

        # ===== DRUG/TREATMENT (3 fields) =====
        drug_name: Optional[str] = None
        drug_names_all: List[str] = Field(default_factory=list)
        route_of_administration: str = "other"

        # ===== ARMS AND RANDOMIZATION (4 fields) =====
        num_arms: int = 0
        arms: List[Dict[str, Any]] = Field(default_factory=list)
        randomization_ratio: Optional[str] = None
        stratification_factors: List[str] = Field(default_factory=list)

        # ===== SAMPLE SIZE (1 complex field) =====
        sample_size: Dict[str, Any] = Field(default_factory=lambda: {"total_n": 0})

        # ===== ENDPOINTS (2 complex fields) =====
        primary_endpoint: Optional[Dict[str, Any]] = None
        secondary_endpoints: List[Dict[str, Any]] = Field(default_factory=list)

        # ===== STATISTICAL (4 fields) =====
        alpha: Dict[str, Any] = Field(default_factory=lambda: {"primary_alpha": 0.05, "sidedness": "two-sided"})
        primary_analysis_method: Optional[str] = None
        primary_analysis_population: Optional[str] = None
        power: Optional[float] = None

        # ===== POPULATIONS (5 fields) =====
        itt_definition: Optional[str] = None
        fas_definition: Optional[str] = None
        pp_definition: Optional[str] = None
        safety_population_definition: Optional[str] = None
        pk_population_definition: Optional[str] = None

        # ===== TIMEPOINTS (3 fields) =====
        primary_timepoint: Optional[str] = None
        study_duration: Optional[str] = None
        treatment_duration: Optional[str] = None

        # ===== PK ANALYSIS (1 complex field) =====
        pk_substudy: Dict[str, Any] = Field(default_factory=lambda: {"has_pk_substudy": False})

        # ===== IMMUNOGENICITY (1 complex field) =====
        immunogenicity: Dict[str, Any] = Field(default_factory=lambda: {"has_immunogenicity": False})

        # ===== SUBGROUP ANALYSES (1 complex field) =====
        subgroup_analyses: List[Dict[str, Any]] = Field(default_factory=list)

        # ===== INTERIM ANALYSIS (8 fields) =====
        interim_analysis: Dict[str, Any] = Field(default_factory=lambda: {"has_interim": False})
        has_interim_analysis: bool = False
        num_interim_analyses: int = 0
        interim_analysis_method: Optional[str] = None
        error_spending_function: Optional[str] = None
        interim_events: List[int] = Field(default_factory=list)
        interim_alpha_spent: List[float] = Field(default_factory=list)
        final_events: int = 0

        # ===== ONCOLOGY-SPECIFIC (4 fields) =====
        response_criteria: Optional[str] = None
        pathologic_response_criteria: Optional[str] = None
        response_assessor: Optional[str] = None
        has_nph_model: bool = False

        # ===== REGULATORY (5 fields) =====
        regulatory_endpoints: List[Dict[str, Any]] = Field(default_factory=list)
        is_bridging_study: bool = False
        target_regions: List[str] = Field(default_factory=list)
        has_regulatory_interim: bool = False
        has_consistency_objective: bool = False

        # ===== METADATA (4 fields) =====
        document_type: Optional[str] = None
        extraction_success: bool = False
        extraction_source: Optional[str] = None
        extraction_confidence: float = 0.0
        warnings: List[str] = Field(default_factory=list)

        class Config:
            extra = 'allow'

        def to_dict(self) -> Dict[str, Any]:
            """Convert to dictionary for serialization"""
            return self.model_dump() if hasattr(self, 'model_dump') else self.dict()

        def get(self, key: str, default: Any = None) -> Any:
            """Dict-like access for compatibility"""
            return getattr(self, key, default)

    # Aliases for backwards compatibility
    SubgroupAnalysis = SubgroupAnalysisSpec
    InterimAnalysis = InterimAnalysisSpec

else:
    # Fallback for when Pydantic is not available
    @dataclass
    class TreatmentArmModel:
        name: str
        description: str = ""
        dose: Optional[str] = None
        schedule: Optional[str] = None
        route: Optional[str] = None
        frequency: Optional[str] = None
        n_patients: Optional[int] = None
        is_placebo: bool = False
        is_control: bool = False
        is_active_comparator: bool = False

    @dataclass
    class EndpointDefinition:
        name: str
        definition: str
        timepoint: Optional[str] = None
        scoring_system: Optional[str] = None
        components: List[str] = field(default_factory=list)

    @dataclass
    class AlphaSpecification:
        primary_alpha: float = 0.05
        sidedness: str = "two-sided"
        additional_levels: List[float] = field(default_factory=list)
        multiplicity_adjustment: Optional[str] = None

    @dataclass
    class SampleSizeSpec:
        total_n: int = 0
        per_arm: Dict[str, int] = field(default_factory=dict)
        power: Optional[float] = None
        effect_size: Optional[str] = None
        dropout_rate: Optional[float] = None

    @dataclass
    class PKSubstudy:
        has_pk_substudy: bool = False
        pk_population_size: Optional[int] = None
        pk_sampling_timepoints: List[str] = field(default_factory=list)
        pk_parameters: List[str] = field(default_factory=list)
        pk_analysis_software: Optional[str] = None

    @dataclass
    class ImmunogenicityAssessment:
        has_immunogenicity: bool = False
        ada_sampling_timepoints: List[str] = field(default_factory=list)
        antibody_type: Optional[str] = None
        assay_method: Optional[str] = None

    @dataclass
    class SubgroupAnalysisSpec:
        factor: str
        categories: List[str] = field(default_factory=list)
        rationale: Optional[str] = None

    @dataclass
    class InterimAnalysisSpec:
        has_interim: bool = False
        interim_timepoints: List[str] = field(default_factory=list)
        monitoring_committee: Optional[str] = None
        stopping_rules: List[str] = field(default_factory=list)

    @dataclass
    class ProtocolFacts:
        nct_id: Optional[str] = None
        study_id: Optional[str] = None
        protocol_title: Optional[str] = None
        sponsor: Optional[str] = None
        phase: str = "Unknown"
        therapeutic_area: Optional[str] = None
        indication: Optional[str] = None
        design_type: Optional[str] = None
        is_blinded: bool = False
        blinding_type: Optional[str] = None
        drug_name: Optional[str] = None
        drug_names_all: List[str] = field(default_factory=list)
        route_of_administration: str = "other"
        num_arms: int = 0
        arms: List[Dict[str, Any]] = field(default_factory=list)
        randomization_ratio: Optional[str] = None
        stratification_factors: List[str] = field(default_factory=list)
        sample_size: Dict[str, Any] = field(default_factory=lambda: {"total_n": 0})
        primary_endpoint: Optional[Dict[str, Any]] = None
        secondary_endpoints: List[Dict[str, Any]] = field(default_factory=list)
        alpha: Dict[str, Any] = field(default_factory=lambda: {"primary_alpha": 0.05})
        primary_analysis_method: Optional[str] = None
        primary_analysis_population: Optional[str] = None
        power: Optional[float] = None
        itt_definition: Optional[str] = None
        fas_definition: Optional[str] = None
        pp_definition: Optional[str] = None
        safety_population_definition: Optional[str] = None
        pk_population_definition: Optional[str] = None
        primary_timepoint: Optional[str] = None
        study_duration: Optional[str] = None
        treatment_duration: Optional[str] = None
        pk_substudy: Dict[str, Any] = field(default_factory=lambda: {"has_pk_substudy": False})
        immunogenicity: Dict[str, Any] = field(default_factory=lambda: {"has_immunogenicity": False})
        subgroup_analyses: List[Dict[str, Any]] = field(default_factory=list)
        interim_analysis: Dict[str, Any] = field(default_factory=lambda: {"has_interim": False})
        has_interim_analysis: bool = False
        num_interim_analyses: int = 0
        interim_analysis_method: Optional[str] = None
        error_spending_function: Optional[str] = None
        interim_events: List[int] = field(default_factory=list)
        interim_alpha_spent: List[float] = field(default_factory=list)
        final_events: int = 0
        response_criteria: Optional[str] = None
        pathologic_response_criteria: Optional[str] = None
        response_assessor: Optional[str] = None
        has_nph_model: bool = False
        regulatory_endpoints: List[Dict[str, Any]] = field(default_factory=list)
        is_bridging_study: bool = False
        target_regions: List[str] = field(default_factory=list)
        has_regulatory_interim: bool = False
        has_consistency_objective: bool = False
        document_type: Optional[str] = None
        extraction_success: bool = False
        extraction_source: Optional[str] = None
        extraction_confidence: float = 0.0
        warnings: List[str] = field(default_factory=list)

        def to_dict(self) -> Dict[str, Any]:
            return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

        def get(self, key: str, default: Any = None) -> Any:
            return getattr(self, key, default)

    SubgroupAnalysis = SubgroupAnalysisSpec
    InterimAnalysis = InterimAnalysisSpec


# ============================================================
# STRUCTURED FACT EXTRACTOR (Replaces structured_extractor.py)
# ============================================================

class StructuredFactExtractor:
    """
    Extracts protocol facts using regex/rules - NO LLM.
    This ensures deterministic, fast, auditable extraction.
    """

    def extract_all(self, protocol_text: str) -> ProtocolFacts:
        """Extract all facts from protocol."""
        facts = ProtocolFacts()

        # Identifiers
        facts.nct_id = self._extract_nct_id(protocol_text)
        facts.study_id = self._extract_study_id(protocol_text)
        facts.protocol_title = self._extract_title(protocol_text)
        facts.sponsor = self._extract_sponsor(protocol_text)

        # Study Design
        facts.phase = self._extract_phase(protocol_text)
        facts.therapeutic_area = self._extract_therapeutic_area(protocol_text)
        facts.indication = self._extract_indication(protocol_text)
        facts.design_type = self._extract_design_type(protocol_text)
        facts.is_blinded, facts.blinding_type = self._extract_blinding(protocol_text)

        # Drug/Treatment
        facts.drug_name, facts.drug_names_all = self._extract_drug_names(protocol_text)
        facts.route_of_administration = self._extract_route(protocol_text)

        # Arms and Randomization
        facts.arms = self._extract_arms(protocol_text)
        facts.num_arms = len(facts.arms) if facts.arms else self._extract_num_arms(protocol_text)
        facts.randomization_ratio = self._extract_randomization_ratio(protocol_text)
        facts.stratification_factors = self._extract_stratification_factors(protocol_text)

        # Ensure consistency for single-arm
        if facts.design_type and 'single-arm' in facts.design_type.lower():
            facts.num_arms = 1
            facts.arms = facts.arms[:1] if facts.arms else []

        # Sample Size
        sample_spec = self._extract_sample_size(protocol_text, facts.num_arms)
        facts.sample_size = {"total_n": sample_spec.get('total_n', 0), "per_arm": sample_spec.get('per_arm', {}), "power": sample_spec.get('power')}

        # Endpoints
        facts.primary_endpoint = self._extract_primary_endpoint(protocol_text)
        facts.secondary_endpoints = self._extract_secondary_endpoints(protocol_text)

        # Statistical
        alpha_spec = self._extract_alpha(protocol_text)
        facts.alpha = {"primary_alpha": alpha_spec.get('primary_alpha', 0.05), "sidedness": alpha_spec.get('sidedness', 'two-sided')}
        facts.primary_analysis_method = self._extract_primary_analysis_method(protocol_text)
        facts.primary_analysis_population = self._extract_analysis_population(protocol_text)

        # Populations
        facts.itt_definition = self._extract_population_definition(protocol_text, "ITT")
        facts.fas_definition = self._extract_population_definition(protocol_text, "FAS")
        facts.pp_definition = self._extract_population_definition(protocol_text, "PP")
        facts.safety_population_definition = self._extract_population_definition(protocol_text, "safety")
        facts.pk_population_definition = self._extract_population_definition(protocol_text, "PK")

        # Timepoints
        facts.primary_timepoint = self._extract_primary_timepoint(protocol_text)
        facts.study_duration = self._extract_study_duration(protocol_text)

        # Interim analysis
        interim = self._extract_interim_analysis(protocol_text)
        facts.interim_analysis = interim
        facts.has_interim_analysis = interim.get('has_interim', False)

        facts.extraction_success = True
        facts.extraction_source = "regex"

        return facts

    def _extract_nct_id(self, text: str) -> Optional[str]:
        patterns = [r'NCT\d{8}', r'NCT[-\s]?\d{8}']
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                digits = re.sub(r'[^\d]', '', match.group(0))
                if len(digits) == 8:
                    return f"NCT{digits}"
        return None

    def _extract_study_id(self, text: str) -> Optional[str]:
        patterns = [r'\b([A-Z]{2,5}\d{3,4}[A-Z]{0,3}\d{0,3})\b']
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                study_id = match.group(1)
                if not re.match(r'^(NCT|EUR|IND|NDA|BLA|ICH|FDA|EMA)\d', study_id):
                    return study_id
        return None

    def _extract_title(self, text: str) -> Optional[str]:
        patterns = [r'(?:protocol\s+)?title[:\s]+([^\n]+)']
        for pattern in patterns:
            match = re.search(pattern, text[:3000], re.IGNORECASE | re.MULTILINE)
            if match:
                title = match.group(1).strip()
                if 20 < len(title) < 500:
                    return title
        return None

    def _extract_sponsor(self, text: str) -> Optional[str]:
        known_sponsors = ['Bristol-Myers Squibb', 'Pfizer', 'Merck', 'Novartis', 'Roche',
                         'AstraZeneca', 'Eli Lilly', 'Sanofi', 'GlaxoSmithKline', 'AbbVie',
                         'Amgen', 'Gilead', 'Biogen', 'Regeneron', 'Takeda', 'Bayer']
        text_lower = text.lower()
        for sponsor in known_sponsors:
            if sponsor.lower() in text_lower:
                return sponsor
        return None

    def _extract_phase(self, text: str) -> str:
        text_lower = text.lower()
        if re.search(r'phase\s*1/2', text_lower):
            return "Phase 1/2"
        elif re.search(r'phase\s*2/3', text_lower):
            return "Phase 2/3"
        elif re.search(r'phase\s*(?:4|iv)', text_lower):
            return "Phase 4"
        elif re.search(r'phase\s*(?:3|iii)', text_lower):
            return "Phase 3"
        elif re.search(r'phase\s*(?:2|ii)', text_lower):
            return "Phase 2"
        elif re.search(r'phase\s*(?:1|i)', text_lower):
            return "Phase 1"
        return "Unknown"

    def _extract_therapeutic_area(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        ta_patterns = {
            'Oncology': r'cancer|tumor|carcinoma|lymphoma|leukemia|melanoma|metastatic',
            'IBD': r'ulcerative\s+colitis|crohn|inflammatory\s+bowel',
            'Cardiology': r'heart\s+failure|cardiac|cardiovascular',
            'Neurology': r'alzheimer|parkinson|multiple\s+sclerosis',
            'Rheumatology': r'rheumatoid|arthritis|lupus',
        }
        for ta, pattern in ta_patterns.items():
            if re.search(pattern, text_lower):
                return ta
        return None

    def _extract_indication(self, text: str) -> Optional[str]:
        patterns = [r'(?:patients?\s+with|treatment\s+of)\s+([a-zA-Z\s\'-]+(?:disease|cancer|colitis))']
        for pattern in patterns:
            match = re.search(pattern, text[:10000], re.IGNORECASE)
            if match:
                indication = match.group(1).strip()
                if 5 < len(indication) < 100:
                    return indication
        return None

    def _extract_design_type(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        design_parts = []
        if any(x in text_lower for x in ['single-arm', 'single arm', 'one-arm']):
            design_parts.append('single-arm')
        elif 'randomized' in text_lower:
            design_parts.append('randomized')
        if 'double-blind' in text_lower:
            design_parts.append('double-blind')
        elif 'open-label' in text_lower:
            design_parts.append('open-label')
        if 'placebo-controlled' in text_lower:
            design_parts.append('placebo-controlled')
        return ', '.join(design_parts) if design_parts else None

    def _extract_blinding(self, text: str):
        text_lower = text.lower()
        if 'double-blind' in text_lower:
            return True, 'double-blind'
        elif 'open-label' in text_lower:
            return False, 'open-label'
        return False, None

    def _extract_drug_names(self, text: str):
        drug_names = set()
        inn_patterns = [r'\b([A-Za-z]{4,}(?:mab|nib|lib|mod|vir|pril|statin))\b']
        for pattern in inn_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            drug_names.update(m.lower() for m in matches)
        drug_list = list(drug_names)
        return (drug_list[0] if drug_list else None), drug_list

    def _extract_route(self, text: str) -> str:
        text_lower = text.lower()
        if re.search(r'\biv\b|intravenous', text_lower):
            return "intravenous"
        elif re.search(r'\bsc\b|subcutaneous', text_lower):
            return "subcutaneous"
        elif re.search(r'\boral|orally|tablet', text_lower):
            return "oral"
        return "other"

    def _extract_arms(self, text: str) -> List[Dict[str, Any]]:
        arms = []
        arm_patterns = [r'(?:arm|group)\s*([A-D1-4])[:\s]+([^\n]{5,100})']
        seen = set()
        for pattern in arm_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                arm_id = match[0].upper()
                if arm_id not in seen:
                    seen.add(arm_id)
                    arms.append({"name": match[1].strip(), "is_placebo": 'placebo' in match[1].lower()})
        return arms

    def _extract_num_arms(self, text: str) -> int:
        text_lower = text.lower()
        if any(x in text_lower for x in ['single-arm', 'single arm']):
            return 1
        ratio_match = re.search(r'(\d+:\d+(?::\d+)*)', text)
        if ratio_match:
            return len(ratio_match.group(1).split(':'))
        return 0

    def _extract_randomization_ratio(self, text: str) -> Optional[str]:
        match = re.search(r'(\d+:\d+(?::\d+)*)', text)
        return match.group(1) if match else None

    def _extract_stratification_factors(self, text: str) -> List[str]:
        factors = []
        match = re.search(r'stratif(?:y|ied|ication)\s+(?:by|factors?)[:\s]+([^\n.]+)', text, re.IGNORECASE)
        if match:
            parts = re.split(r'[,;]', match.group(1))
            factors = [p.strip() for p in parts if 3 < len(p.strip()) < 100]
        return factors

    def _extract_sample_size(self, text: str, num_arms: int) -> Dict[str, Any]:
        spec = {"total_n": 0, "per_arm": {}, "power": None}
        patterns = [r'(\d+)\s*(?:patients?|subjects?)\s+(?:will\s+be\s+)?(?:enrolled|randomized)']
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                n = int(match.group(1))
                if 10 <= n <= 100000:
                    spec["total_n"] = n
                    break
        power_match = re.search(r'(\d{2})\s*%?\s*power', text, re.IGNORECASE)
        if power_match:
            spec["power"] = float(power_match.group(1)) / 100
        return spec

    def _extract_primary_endpoint(self, text: str) -> Optional[Dict[str, Any]]:
        patterns = [r'(?:primary\s+(?:efficacy\s+)?endpoint)[:\s]+([^.]+\.)', r'(?:primary\s+endpoint)[:\s]+([^\n]+)']
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                endpoint_text = match.group(1).strip()
                if len(endpoint_text) > 10:
                    return {"name": "Primary Endpoint", "definition": endpoint_text[:500]}
        return None

    def _extract_secondary_endpoints(self, text: str) -> List[Dict[str, Any]]:
        endpoints = []
        patterns = [r'(?:secondary\s+endpoint)[:\s]+([^.]+\.)']
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:5]:
                if len(match.strip()) > 10:
                    endpoints.append({"name": "Secondary Endpoint", "definition": match.strip()[:300]})
        return endpoints

    def _extract_alpha(self, text: str) -> Dict[str, Any]:
        spec = {"primary_alpha": 0.05, "sidedness": "two-sided"}
        if re.search(r'one[- ]sided', text, re.IGNORECASE):
            spec["sidedness"] = "one-sided"
        alpha_match = re.search(r'alpha[:\s=]+(\d+\.?\d*)', text, re.IGNORECASE)
        if alpha_match:
            alpha_val = float(alpha_match.group(1))
            if alpha_val > 1:
                alpha_val = alpha_val / 100
            if 0.001 <= alpha_val <= 0.5:
                spec["primary_alpha"] = alpha_val
        return spec

    def _extract_primary_analysis_method(self, text: str) -> Optional[str]:
        method_patterns = [
            (r'log[- ]rank\s+test', 'Log-Rank Test'),
            (r'cox\s+(?:proportional\s+)?hazard', 'Cox Proportional Hazards'),
            (r'kaplan[- ]meier', 'Kaplan-Meier'),
            (r'MMRM|mixed[- ]model', 'MMRM'),
            (r'ANCOVA', 'ANCOVA'),
        ]
        for pattern, method_name in method_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return method_name
        return None

    def _extract_analysis_population(self, text: str) -> Optional[str]:
        patterns = [r'(?:primary\s+analysis)[^.]*(?:on|using)\s+(?:the\s+)?(ITT|FAS|PP|mITT)']
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return None

    def _extract_population_definition(self, text: str, pop_type: str) -> Optional[str]:
        patterns = {
            'ITT': r'(?:ITT|intent[- ]to[- ]treat)[^.]*(?:defined\s+as)[:\s]+([^.]+)',
            'FAS': r'(?:FAS|full\s+analysis\s+set)[^.]*(?:defined\s+as)[:\s]+([^.]+)',
            'PP': r'(?:PP|per[- ]protocol)[^.]*(?:defined\s+as)[:\s]+([^.]+)',
            'safety': r'(?:safety\s+population)[^.]*(?:defined\s+as)[:\s]+([^.]+)',
            'PK': r'(?:PK|pharmacokinetic)[^.]*(?:defined\s+as)[:\s]+([^.]+)',
        }
        pattern = patterns.get(pop_type)
        if pattern:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:300]
        return None

    def _extract_primary_timepoint(self, text: str) -> Optional[str]:
        match = re.search(r'(?:primary\s+(?:endpoint|analysis))[^.]*(?:at|by)\s+(week\s+\d+|month\s+\d+)', text, re.IGNORECASE)
        return match.group(1) if match else None

    def _extract_study_duration(self, text: str) -> Optional[str]:
        match = re.search(r'(?:study|treatment)\s+duration[:\s]+(\d+\s+(?:weeks?|months?))', text, re.IGNORECASE)
        return match.group(1) if match else None

    def _extract_interim_analysis(self, text: str) -> Dict[str, Any]:
        interim = {"has_interim": False, "monitoring_committee": None, "stopping_rules": []}
        if re.search(r'interim\s+analysis|DMC|DSMB', text, re.IGNORECASE):
            interim["has_interim"] = True
            if re.search(r'DMC|data\s+monitoring\s+committee', text, re.IGNORECASE):
                interim["monitoring_committee"] = "Data Monitoring Committee (DMC)"
        return interim

    def to_prompt_context(self, facts: ProtocolFacts) -> str:
        """Convert facts to prompt context string for LLM."""
        lines = ["## MANDATORY PROTOCOL FACTS", ""]
        if facts.nct_id:
            lines.append(f"- NCT ID: {facts.nct_id}")
        if facts.drug_name:
            lines.append(f"- Drug: {facts.drug_name}")
        if facts.phase:
            lines.append(f"- Phase: {facts.phase}")
        sample_n = facts.sample_size.get('total_n', 0) if isinstance(facts.sample_size, dict) else getattr(facts.sample_size, 'total_n', 0)
        if sample_n:
            lines.append(f"- Sample Size: {sample_n}")
        return "\n".join(lines)


# Convenience function
def extract_protocol_facts(protocol_text: str) -> ProtocolFacts:
    """Extract all facts from protocol text"""
    extractor = StructuredFactExtractor()
    return extractor.extract_all(protocol_text)
