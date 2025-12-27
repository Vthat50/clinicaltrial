#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Data Schemas
=================================================
Structured data types for protocol parsing and SAP generation.
Based on ICH E9(R1) Estimand Framework and CDISC Standards.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import json
from datetime import datetime


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
    """Treatment arm definition"""
    name: str
    description: str
    dose: Optional[str] = None
    schedule: Optional[str] = None
    route: Optional[str] = None
    is_control: bool = False
    is_active_comparator: bool = False


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
