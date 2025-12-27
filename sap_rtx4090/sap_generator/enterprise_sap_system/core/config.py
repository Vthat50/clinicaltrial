#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Configuration Module
========================================================
Centralized configuration for all system components.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class ModelConfig:
    """LLM Model Configuration"""
    primary_model: str = "llama-3.3-70b-versatile"  # Main generation (via Groq)
    review_model: str = "llama-3.3-70b-versatile"   # Quality review
    fast_model: str = "llama-3.1-8b-instant"        # Parsing, classification
    embedding_model: str = "BAAI/bge-large-en-v1.5" # Vector embeddings

    # API Configuration
    groq_api_key: Optional[str] = field(default_factory=lambda: os.getenv("GROQ_API_KEY"))
    anthropic_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))

    # Generation parameters
    temperature: float = 0.3
    max_tokens: int = 8192
    top_p: float = 0.9


@dataclass
class PathConfig:
    """File Path Configuration"""
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def all_pairs_dir(self) -> Path:
        return self.data_dir / "all_pairs"

    @property
    def knowledge_base_dir(self) -> Path:
        return self.base_dir / "enterprise_sap_system" / "data" / "knowledge_base"

    @property
    def embeddings_dir(self) -> Path:
        return self.base_dir / "enterprise_sap_system" / "data" / "embeddings"

    @property
    def processed_pairs_dir(self) -> Path:
        return self.base_dir / "enterprise_sap_system" / "data" / "processed_pairs"

    @property
    def output_dir(self) -> Path:
        return self.base_dir / "output"


@dataclass
class GraphRAGConfig:
    """Knowledge Graph RAG Configuration"""
    # Graph parameters
    max_hops: int = 2
    top_k_entities: int = 10
    top_k_paths: int = 20
    similarity_threshold: float = 0.7

    # Entity types for the biostatistics knowledge graph
    entity_types: List[str] = field(default_factory=lambda: [
        "EndpointType", "StatisticalMethod", "AnalysisPopulation",
        "StudyPhase", "TherapeuticArea", "IntercurrentEvent",
        "ICHGuideline", "RegulatoryBody", "CDISCStandard", "EffectMeasure"
    ])

    # Relationship types
    relationship_types: List[str] = field(default_factory=lambda: [
        "analyzed_by", "requires", "measure_is", "defined_in",
        "primary_is", "intercurrent", "maps_to_adam", "guideline_for"
    ])


@dataclass
class AgentConfig:
    """Multi-Agent System Configuration"""
    max_iterations: int = 5
    agent_timeout: int = 120  # seconds
    parallel_agents: bool = True

    # Agent names and roles
    agents: Dict[str, str] = field(default_factory=lambda: {
        "protocol_parser": "Parse protocol and extract structured data",
        "estimand_architect": "Design ICH E9(R1) compliant estimands",
        "methods_selector": "Select appropriate statistical methods",
        "knowledge_retrieval": "Retrieve relevant context from knowledge base",
        "sap_writer": "Generate SAP document sections",
        "sample_size_calculator": "Perform sample size calculations",
        "cdisc_mapper": "Map endpoints to CDISC ADaM standards",
        "quality_reviewer": "Review and validate generated SAP"
    })


@dataclass
class FewShotConfig:
    """Few-Shot Learning Configuration"""
    n_examples: int = 3
    diversity_weight: float = 0.3
    min_similarity: float = 0.5

    # Matching constraints
    match_endpoint_type: bool = True
    match_therapeutic_area: bool = True
    match_phase: bool = True


@dataclass
class CDISCConfig:
    """CDISC Standards Configuration"""
    adam_version: str = "1.1"
    sdtm_version: str = "1.8"

    # Standard ADaM datasets
    adam_datasets: List[str] = field(default_factory=lambda: [
        "ADSL", "ADAE", "ADTTE", "ADRS", "ADLB", "ADVS", "ADEX", "ADPC", "ADPP"
    ])


@dataclass
class SAPConfig:
    """SAP Generation Configuration"""
    template_version: str = "TransCelerate 2024"

    # Required sections
    sections: List[str] = field(default_factory=lambda: [
        "1_introduction",
        "2_objectives_estimands",
        "3_study_design",
        "4_analysis_populations",
        "5_statistical_methods",
        "6_sample_size",
        "7_data_handling",
        "8_cdisc_alignment",
        "9_tlf_specifications"
    ])


@dataclass
class SystemConfig:
    """Master Configuration"""
    model: ModelConfig = field(default_factory=ModelConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    graph_rag: GraphRAGConfig = field(default_factory=GraphRAGConfig)
    agents: AgentConfig = field(default_factory=AgentConfig)
    few_shot: FewShotConfig = field(default_factory=FewShotConfig)
    cdisc: CDISCConfig = field(default_factory=CDISCConfig)
    sap: SAPConfig = field(default_factory=SAPConfig)

    # System-wide settings
    verbose: bool = True
    debug: bool = False
    log_level: str = "INFO"


# Global configuration instance
CONFIG = SystemConfig()


def get_config() -> SystemConfig:
    """Get the global configuration instance"""
    return CONFIG


def update_config(**kwargs) -> SystemConfig:
    """Update configuration with new values"""
    global CONFIG
    for key, value in kwargs.items():
        if hasattr(CONFIG, key):
            setattr(CONFIG, key, value)
    return CONFIG
