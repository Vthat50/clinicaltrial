#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Configuration Module
========================================================
Centralized configuration for all system components.

Production Features:
- Environment variable validation at startup
- Configuration validation
- Structured logging integration
"""

import os
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from pathlib import Path

# Import logging
try:
    from .logging_config import get_logger, ConfigurationError
except ImportError:
    import logging
    def get_logger(name):
        return logging.getLogger(name)
    class ConfigurationError(Exception):
        def __init__(self, message, config_key=None):
            self.config_key = config_key
            super().__init__(message)

logger = get_logger(__name__)


def validate_env_vars(required: List[str] = None, optional: List[str] = None) -> Dict[str, bool]:
    """
    Validate environment variables at startup.

    Args:
        required: List of required env vars (raises error if missing)
        optional: List of optional env vars (logs warning if missing)

    Returns:
        Dict mapping env var names to whether they're set

    Raises:
        ConfigurationError if required vars are missing
    """
    required = required or []
    optional = optional or []
    result = {}
    missing_required = []

    for var in required:
        value = os.getenv(var)
        result[var] = bool(value)
        if not value:
            missing_required.append(var)

    for var in optional:
        value = os.getenv(var)
        result[var] = bool(value)
        if not value:
            logger.warning(f"Optional env var not set: {var}")

    if missing_required:
        error_msg = f"Required environment variables not set: {', '.join(missing_required)}"
        logger.error(error_msg, missing_vars=missing_required)
        raise ConfigurationError(error_msg, config_key="env_vars")

    return result


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
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))

    def get_available_providers(self) -> List[str]:
        """Get list of LLM providers with configured API keys."""
        providers = []
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.openai_api_key:
            providers.append("openai")
        if self.groq_api_key:
            providers.append("groq")
        return providers

    def validate(self) -> bool:
        """Validate that at least one LLM provider is configured."""
        providers = self.get_available_providers()
        if not providers:
            logger.warning(
                "No LLM API keys configured",
                hint="Set at least one of: ANTHROPIC_API_KEY, OPENAI_API_KEY, GROQ_API_KEY"
            )
            return False
        logger.info("LLM providers available", providers=providers)
        return True

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


# Thread-safe global configuration
_config: Optional[SystemConfig] = None
_config_lock = threading.Lock()


def get_config() -> SystemConfig:
    """Get the global configuration instance (thread-safe)."""
    global _config

    if _config is not None:
        return _config

    with _config_lock:
        # Double-check locking pattern
        if _config is None:
            _config = SystemConfig()
            # Validate on first access
            _config.model.validate()
            logger.info(
                "Configuration initialized",
                llm_providers=_config.model.get_available_providers(),
                log_level=_config.log_level,
                debug=_config.debug
            )

    return _config


def update_config(**kwargs) -> SystemConfig:
    """Update configuration with new values (thread-safe)."""
    global _config

    with _config_lock:
        config = get_config()
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
                logger.debug(f"Config updated: {key}", new_value=str(value)[:50])
            else:
                logger.warning(f"Unknown config key: {key}")

    return config


def reset_config():
    """Reset configuration to defaults (for testing)."""
    global _config
    with _config_lock:
        _config = None


# Lazy-loaded backwards compatibility - access via get_config()
# Note: Direct CONFIG usage is deprecated, use get_config() instead
class _ConfigProxy:
    """Proxy for lazy CONFIG access."""
    def __getattr__(self, name):
        return getattr(get_config(), name)

CONFIG = _ConfigProxy()
