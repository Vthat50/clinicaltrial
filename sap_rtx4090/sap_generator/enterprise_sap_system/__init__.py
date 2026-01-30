"""
Enterprise SAP Generation System
=================================

A production-grade system for generating Statistical Analysis Plans (SAPs)
from clinical trial protocols using advanced GenAI techniques.

Features:
- TIER 1: Protocol Ingestion & Structured Parsing with Clinical NLP
- TIER 2: Knowledge-Augmented Generation with GraphRAG
- TIER 3: Multi-Agent SAP Generation Workflow
- TIER 4: Few-Shot Learning with Real Protocol-SAP Pairs
- TIER 5: CDISC ADaM Standards Integration
- TIER 6: TransCelerate-Aligned SAP Document Generation

Usage:
    from enterprise_sap_system import create_orchestrator

    orchestrator = create_orchestrator()
    result = orchestrator.generate_sap(protocol_text)

    if result.success:
        print(result.sap_document.full_document)
"""

__version__ = "2.0.0"
__author__ = "Enterprise SAP Generation System"

# Core components
from .core import (
    get_config, update_config, CONFIG,
    ParsedProtocol, Estimand, InterCurrentEvent, TreatmentArm,
    SampleSizeCalc, AnalysisPopulation, StatisticalMethod,
    StudyPhase, EndpointType, ICEStrategy, PopulationType,
    DesignType, BlindingType, SAPExamplePair, QualityReport, GeneratedSAP,
    ProtocolParser, create_parser
)

# Knowledge Graph
from .knowledge_graph import (
    BiostatisticsKnowledgeGraph,
    BiostatisticsGraphRAG,
    create_graph_rag
)

# Agents
from .agents import (
    SAPGenerationOrchestrator,
    GenerationResult,
    create_orchestrator,
    EstimandArchitectAgent,
    MethodsSelectorAgent,
    SAPWriterAgent,
    QualityReviewerAgent
)

# Few-Shot Learning
from .few_shot import (
    SAPPairDatabase,
    FewShotExampleSelector,
    create_sap_database,
    create_few_shot_selector
)

# CDISC
from .cdisc import (
    CDISCMapper,
    CDISCMapping,
    create_cdisc_mapper
)

# Templates
from .templates import (
    SAPTemplateManager,
    create_template_manager
)

__all__ = [
    # Version
    '__version__',

    # Core
    'get_config', 'update_config', 'CONFIG',
    'ParsedProtocol', 'Estimand', 'InterCurrentEvent',
    'TreatmentArm', 'SampleSizeCalc', 'AnalysisPopulation',
    'StatisticalMethod', 'StudyPhase', 'EndpointType',
    'ICEStrategy', 'PopulationType', 'DesignType', 'BlindingType',
    'SAPExamplePair', 'QualityReport', 'GeneratedSAP',
    'ProtocolParser', 'create_parser',

    # Knowledge Graph
    'BiostatisticsKnowledgeGraph', 'BiostatisticsGraphRAG', 'create_graph_rag',

    # Agents
    'SAPGenerationOrchestrator', 'GenerationResult', 'create_orchestrator',
    'EstimandArchitectAgent', 'MethodsSelectorAgent',
    'SAPWriterAgent', 'QualityReviewerAgent',

    # Few-Shot
    'SAPPairDatabase', 'FewShotExampleSelector',
    'create_sap_database', 'create_few_shot_selector',

    # CDISC
    'CDISCMapper', 'CDISCMapping', 'create_cdisc_mapper',

    # Templates
    'SAPTemplateManager', 'create_template_manager',
]
