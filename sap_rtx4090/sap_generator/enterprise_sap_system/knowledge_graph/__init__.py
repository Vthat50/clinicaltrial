"""
Enterprise SAP Generation System - Knowledge Graph Module
"""

# graph_rag was archived - make imports optional
try:
    from .graph_rag import (
        BiostatisticsKnowledgeGraph,
        BiostatisticsGraphRAG,
        KnowledgeEntity,
        KnowledgeRelationship,
        RetrievedPath,
        create_graph_rag
    )
    GRAPH_RAG_AVAILABLE = True
except ImportError:
    # graph_rag not available (archived)
    GRAPH_RAG_AVAILABLE = False
    BiostatisticsKnowledgeGraph = None
    BiostatisticsGraphRAG = None
    KnowledgeEntity = None
    KnowledgeRelationship = None
    RetrievedPath = None
    create_graph_rag = None

__all__ = [
    'BiostatisticsKnowledgeGraph',
    'BiostatisticsGraphRAG',
    'KnowledgeEntity',
    'KnowledgeRelationship',
    'RetrievedPath',
    'create_graph_rag',
    'GRAPH_RAG_AVAILABLE'
]
