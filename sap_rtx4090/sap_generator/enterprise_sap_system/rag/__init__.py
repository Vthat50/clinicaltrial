"""
RAG System for SAP Generation
=============================
Retrieval-Augmented Generation using 350+ real SAP examples.

Components:
- SAPSectionParser: Parses SAP PDFs into structured sections
- SAPVectorStore: Chroma-based vector database for semantic search
- RAG Agents: Specialized agents for endpoint, method, and stratification tasks
- RAGOrchestrator: Coordinates all agents for complete SAP generation
"""

from .sap_section_parser import (
    SAPSectionParser,
    ParsedSection,
    SAPMetadata,
    SectionType,
    EndpointType,
    TherapeuticArea,
    create_sap_parser
)

from .vector_store import (
    SAPVectorStore,
    RetrievalResult,
    create_vector_store
)

from .rag_agents import (
    RAGContext,
    SAPRetriever,
    EndpointExtractionAgent,
    MethodSelectionAgent,
    StratificationParserAgent,
    RAGOrchestrator,
    create_rag_orchestrator
)

from .pipeline_integration import (
    RAGPipelineIntegration
)

__all__ = [
    # Parser
    'SAPSectionParser',
    'ParsedSection',
    'SAPMetadata',
    'SectionType',
    'EndpointType',
    'TherapeuticArea',
    'create_sap_parser',
    # Vector Store
    'SAPVectorStore',
    'RetrievalResult',
    'create_vector_store',
    # Agents
    'RAGContext',
    'SAPRetriever',
    'EndpointExtractionAgent',
    'MethodSelectionAgent',
    'StratificationParserAgent',
    'RAGOrchestrator',
    'create_rag_orchestrator',
    # Integration
    'RAGPipelineIntegration',
]
