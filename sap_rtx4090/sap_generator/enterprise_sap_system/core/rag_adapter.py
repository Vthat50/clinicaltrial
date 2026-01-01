#!/usr/bin/env python3
"""
RAG Adapter for Hybrid Reasoning Engine
========================================

Adapts the existing RAG infrastructure to work with the hybrid reasoning engine.
Provides a unified interface for retrieving examples for any section type.
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Try to import RAG components
try:
    from ..rag.vector_store import SAPVectorStore, create_vector_store, RetrievalResult
    from ..rag.rag_agents import SAPRetriever, RAGContext
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("[RAG Adapter] Warning: RAG components not available")


class HybridRAGAdapter:
    """
    Adapter that provides RAG retrieval for the hybrid reasoning engine.

    Maps section types to appropriate RAG queries and returns
    examples in a format the hybrid generators can use.
    """

    # Section type to RAG query mapping
    SECTION_QUERIES = {
        'endpoints': {
            'section_type': 'endpoints',
            'query_template': '{therapeutic_area} {primary_endpoint} endpoint definition',
        },
        'methods': {
            'section_type': 'methods',
            'query_template': '{therapeutic_area} {endpoint_type} statistical analysis method',
        },
        'stratification': {
            'section_type': 'study_design',  # Stratification is in study design sections
            'query_template': '{therapeutic_area} stratification randomization factors',
        },
        'windows': {
            'section_type': 'methods',  # Windows often in methods sections
            'query_template': '{therapeutic_area} analysis visit windows',
        },
        'populations': {
            'section_type': 'populations',
            'query_template': '{therapeutic_area} analysis populations ITT FAS',
        },
        'safety': {
            'section_type': 'safety',
            'query_template': '{therapeutic_area} adverse events TEAE safety analysis',
        },
    }

    def __init__(self, vector_store_dir: Path = None):
        """
        Initialize RAG adapter.

        Args:
            vector_store_dir: Directory for vector store (optional)
        """
        self._vector_store: Optional[SAPVectorStore] = None
        self._retriever: Optional[SAPRetriever] = None
        self._initialized = False
        self.vector_store_dir = vector_store_dir

    def _ensure_initialized(self) -> bool:
        """Lazy initialization of RAG components"""
        if self._initialized:
            return RAG_AVAILABLE and self._vector_store is not None

        if not RAG_AVAILABLE:
            self._initialized = True
            return False

        try:
            self._vector_store = create_vector_store(self.vector_store_dir)
            self._retriever = SAPRetriever(self._vector_store)
            self._initialized = True
            print("[RAG Adapter] Initialized successfully")
            return True
        except Exception as e:
            print(f"[RAG Adapter] Warning: Could not initialize: {e}")
            self._initialized = True
            return False

    def retrieve_for_section(
        self,
        section_type: str,
        protocol_data: Dict[str, Any],
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant examples for a section type.

        Args:
            section_type: Type of section (endpoints, methods, etc.)
            protocol_data: Protocol facts dictionary
            n_results: Number of results to retrieve

        Returns:
            List of example dictionaries with 'content', 'nct_id', 'score'
        """
        if not self._ensure_initialized():
            return []

        try:
            # Get query configuration for this section
            config = self.SECTION_QUERIES.get(section_type, {
                'section_type': section_type,
                'query_template': '{therapeutic_area} {section_type}',
            })

            # Build query from template - exclude keys we set explicitly
            explicit_keys = {'therapeutic_area', 'primary_endpoint', 'endpoint_type', 'section_type'}
            extra_kwargs = {
                k: v for k, v in protocol_data.items()
                if isinstance(v, str) and k not in explicit_keys
            }
            query = config['query_template'].format(
                therapeutic_area=protocol_data.get('therapeutic_area', ''),
                primary_endpoint=protocol_data.get('primary_endpoint', ''),
                endpoint_type=protocol_data.get('endpoint_type', 'efficacy'),
                section_type=section_type,
                **extra_kwargs
            ).strip()

            # Add explicit query if provided
            if protocol_data.get('query'):
                query = f"{protocol_data['query']} {query}"

            # Query vector store
            results = self._vector_store.query(
                section_type=config['section_type'],
                query_text=query,
                n_results=n_results,
                filters=self._build_filters(protocol_data)
            )

            # Convert to simple dict format expected by hybrid engine
            filtered_results = [
                {
                    'content': r.content,
                    'nct_id': r.nct_id,
                    'score': r.relevance_score,
                    'section_type': r.section_type,
                    'metadata': r.metadata
                }
                for r in results
                if r.relevance_score >= 0.3  # Minimum relevance threshold
            ]

            # WARN if no results found (helps debug RAG issues)
            if not filtered_results:
                print(f"[RAG Adapter] ⚠️ No examples found for {section_type} (query: '{query[:50]}...')")
            else:
                print(f"[RAG Adapter] Found {len(filtered_results)} examples for {section_type}")

            return filtered_results

        except Exception as e:
            print(f"[RAG Adapter] ❌ Error retrieving for {section_type}: {e}")
            return []

    def _build_filters(self, protocol_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build filters for RAG query"""
        filters = {}

        if protocol_data.get('therapeutic_area'):
            filters['therapeutic_area'] = protocol_data['therapeutic_area']

        if protocol_data.get('phase'):
            filters['phase'] = protocol_data['phase']

        return filters if filters else None

    def get_full_context(
        self,
        protocol_data: Dict[str, Any],
        section_types: List[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get RAG context for multiple sections at once.

        Args:
            protocol_data: Protocol facts
            section_types: List of section types (defaults to all)

        Returns:
            Dictionary of section_type -> list of examples
        """
        if section_types is None:
            section_types = list(self.SECTION_QUERIES.keys())

        results = {}
        for section_type in section_types:
            results[section_type] = self.retrieve_for_section(
                section_type=section_type,
                protocol_data=protocol_data,
                n_results=3
            )

        return results

    @property
    def is_available(self) -> bool:
        """Check if RAG is available"""
        return self._ensure_initialized()


class MockRAGAdapter:
    """
    Mock RAG adapter for testing when RAG is not available.
    Returns empty results for all queries.
    """

    def __init__(self):
        print("[RAG Adapter] ⚠️ WARNING: RAG not available - using MockRAGAdapter (empty results)")

    def retrieve_for_section(
        self,
        section_type: str,
        protocol_data: Dict[str, Any],
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """Return empty results"""
        print(f"[RAG Adapter] ⚠️ MockRAGAdapter returning empty for {section_type}")
        return []

    def get_full_context(
        self,
        protocol_data: Dict[str, Any],
        section_types: List[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Return empty context"""
        return {}

    @property
    def is_available(self) -> bool:
        return False


def create_rag_adapter(vector_store_dir: Path = None) -> HybridRAGAdapter:
    """
    Factory function to create RAG adapter.

    Returns HybridRAGAdapter if RAG is available, MockRAGAdapter otherwise.
    """
    if RAG_AVAILABLE:
        return HybridRAGAdapter(vector_store_dir)
    else:
        return MockRAGAdapter()
