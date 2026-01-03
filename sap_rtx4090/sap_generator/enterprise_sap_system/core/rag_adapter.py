#!/usr/bin/env python3
"""
RAG Adapter for Hybrid Reasoning Engine
========================================

Adapts the existing RAG infrastructure to work with the hybrid reasoning engine.
Provides a unified interface for retrieving examples for any section type.

CRITICAL: All retrieved content is SANITIZED to prevent contamination:
- Numbers stripped → [N]
- Study names stripped → [STUDY]
- Drug names stripped → [DRUG]
- Indication terms stripped → [INDICATION]
- Metadata stripped (Chunk ID, Source, etc.)
"""

import re
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

    CRITICAL: All content is SANITIZED before returning to prevent contamination.
    """

    # Patterns for sanitizing RAG chunks - strip ALL contaminating content
    SANITIZE_PATTERNS = [
        # Metadata leakage
        (re.compile(r'Chunk\s*ID[:\s]*\d+', re.IGNORECASE), ''),
        (re.compile(r'Source[:\s]*[^\n]+', re.IGNORECASE), ''),
        (re.compile(r'Relevance[:\s]*[\d.]+', re.IGNORECASE), ''),
        (re.compile(r'Score[:\s]*[\d.]+', re.IGNORECASE), ''),
        (re.compile(r'Confidence[:\s]*[\d.]+', re.IGNORECASE), ''),
        # NCT IDs
        (re.compile(r'NCT\d{8}', re.IGNORECASE), '[NCT_ID]'),
        # Study names
        (re.compile(r'CheckMate[\s-]*\d+', re.IGNORECASE), '[STUDY]'),
        (re.compile(r'KEYNOTE[\s-]*\d+', re.IGNORECASE), '[STUDY]'),
        (re.compile(r'JAVELIN[\s\w]*\d*', re.IGNORECASE), '[STUDY]'),
        (re.compile(r'IMpower[\s-]*\d+', re.IGNORECASE), '[STUDY]'),
        (re.compile(r'OAK\s+study', re.IGNORECASE), '[STUDY]'),
        (re.compile(r'POPLAR\s+study', re.IGNORECASE), '[STUDY]'),
        (re.compile(r'GA\d{5}', re.IGNORECASE), '[STUDY_ID]'),
        (re.compile(r'BMS-\d+', re.IGNORECASE), '[STUDY_ID]'),
        (re.compile(r'MK-\d+', re.IGNORECASE), '[STUDY_ID]'),
        # Drug names
        (re.compile(r'\betrolizumab\b', re.IGNORECASE), '[DRUG]'),
        (re.compile(r'\bavelumab\b', re.IGNORECASE), '[DRUG]'),
        (re.compile(r'\bipilimumab\b', re.IGNORECASE), '[DRUG]'),
        (re.compile(r'\batezolizumab\b', re.IGNORECASE), '[DRUG]'),
        (re.compile(r'\bdurvalumab\b', re.IGNORECASE), '[DRUG]'),
        (re.compile(r'\bpembrolizumab\b', re.IGNORECASE), '[DRUG]'),
        (re.compile(r'\bnivolumab\b', re.IGNORECASE), '[DRUG]'),
        (re.compile(r'\bdocetaxel\b', re.IGNORECASE), '[COMPARATOR]'),
        # Indication terms
        (re.compile(r'\bmRCC\b', re.IGNORECASE), '[INDICATION]'),
        (re.compile(r'\bRCC\b'), '[INDICATION]'),  # Case sensitive to avoid "occurrence"
        (re.compile(r'\brenal cell carcinoma\b', re.IGNORECASE), '[INDICATION]'),
        (re.compile(r'\bhepatocellular\b', re.IGNORECASE), '[INDICATION]'),
        (re.compile(r'\bHCC\b'), '[INDICATION]'),
        (re.compile(r'\bmelanoma\b', re.IGNORECASE), '[INDICATION]'),
        (re.compile(r'\burothelial\b', re.IGNORECASE), '[INDICATION]'),
        (re.compile(r'\bNSCLC\b'), '[INDICATION]'),
        (re.compile(r'\bnon-small cell lung\b', re.IGNORECASE), '[INDICATION]'),
        # Numbers - MUST strip to prevent contamination
        (re.compile(r'\b(\d+)\s*(patients?|subjects?|participants?)\b', re.IGNORECASE), '[N] \\2'),
        (re.compile(r'\b(\d+)\s*(events?|deaths?)\b', re.IGNORECASE), '[N_EVENTS] \\2'),
        (re.compile(r'(\d+:\d+(?::\d+)?)\s*(ratio|randomiz)', re.IGNORECASE), '[RATIO] \\2'),
        (re.compile(r'(?:α|alpha)\s*[=<≤]\s*(\d+\.?\d*)', re.IGNORECASE), 'α=[ALPHA]'),
        (re.compile(r'p\s*[<≤]\s*(\d+\.?\d*)', re.IGNORECASE), 'p<[P_VALUE]'),
        (re.compile(r'(\d+\.?\d*)\s*%', re.IGNORECASE), '[N]%'),
        (re.compile(r'HR\s*[=:]\s*(\d+\.?\d*)', re.IGNORECASE), 'HR=[HR]'),
        (re.compile(r'(\d+)\s*(weeks?|months?|years?)', re.IGNORECASE), '[DURATION] \\2'),
        # Catch-all for remaining numbers
        (re.compile(r'\b\d{2,}\b'), '[N]'),
        (re.compile(r'\b\d+:\d+(?::\d+)?\b'), '[RATIO]'),
    ]

    # Wrong indication patterns to filter out
    WRONG_INDICATION_PATTERNS = {
        'NSCLC': [r'\bmRCC\b', r'\brenal cell\b', r'\bkidney cancer\b',
                  r'\bhepatocellular\b', r'\blive cancer\b', r'\bmelanoma\b',
                  r'\burothelial\b', r'\bbladder cancer\b'],
        'RCC': [r'\bNSCLC\b', r'\bnon-small cell lung\b', r'\blung cancer\b',
                r'\bhepatocellular\b', r'\blive cancer\b', r'\bmelanoma\b'],
        'HCC': [r'\bNSCLC\b', r'\blung cancer\b', r'\bmRCC\b', r'\brenal\b',
                r'\bmelanoma\b', r'\burothelial\b'],
        'MELANOMA': [r'\bNSCLC\b', r'\blung\b', r'\bmRCC\b', r'\brenal\b',
                     r'\bhepatocellular\b', r'\blive\b'],
    }

    # Section type to RAG query mapping
    SECTION_QUERIES = {
        'endpoints': {
            'section_type': 'endpoints',
            'query_template': '{therapeutic_area} {primary_endpoint} endpoint definition',
        },
        'methods': {
            'section_type': 'methods',
            'query_template': '{therapeutic_area} {endpoint_type} statistical analysis log-rank Cox hazard',
        },
        'stratification': {
            'section_type': 'study_design',
            'query_template': '{therapeutic_area} stratification randomization factors',
        },
        'windows': {
            'section_type': 'methods',
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
        # NEW: Methodology-specific sections from real SAPs
        'interim_analysis': {
            'section_type': 'interim_analysis',
            'query_template': 'interim analysis alpha spending Lan-DeMets O\'Brien-Fleming stopping boundary events',
        },
        'primary_analysis': {
            'section_type': 'primary_analysis',
            'query_template': 'primary endpoint analysis log-rank Cox hazard ratio stratified',
        },
        'sample_size': {
            'section_type': 'sample_size',
            'query_template': 'sample size power calculation hazard ratio events dropout accrual',
        },
        'multiplicity': {
            'section_type': 'multiplicity',
            'query_template': 'multiplicity hierarchical testing gatekeeping alpha control type I error',
        },
        'sensitivity_analysis': {
            'section_type': 'sensitivity_analysis',
            'query_template': 'sensitivity analysis robustness ITT per protocol missing data',
        },
        'missing_data': {
            'section_type': 'missing_data',
            'query_template': 'missing data imputation treatment policy multiple imputation',
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

            # Get current indication for filtering
            current_indication = str(protocol_data.get('indication') or '').upper()
            if not current_indication and protocol_data.get('therapeutic_area'):
                # Try to infer from therapeutic area
                ta = str(protocol_data['therapeutic_area']).upper()
                if 'LUNG' in ta:
                    current_indication = 'NSCLC'
                elif 'RENAL' in ta or 'KIDNEY' in ta:
                    current_indication = 'RCC'

            # Convert to simple dict format expected by hybrid engine
            # CRITICAL: Filter and SANITIZE all content
            filtered_results = []
            for r in results:
                if r.relevance_score < 0.3:
                    continue

                # FILTER: Skip chunks with wrong indication
                if current_indication and self._has_wrong_indication(r.content, current_indication):
                    print(f"[RAG Adapter] Filtered out chunk with wrong indication (target: {current_indication})")
                    continue

                # SANITIZE: Strip all contaminating content
                sanitized_content = self._sanitize_content(r.content)

                filtered_results.append({
                    'content': sanitized_content,  # SANITIZED content only
                    'nct_id': '[NCT_ID]',  # Anonymize NCT ID
                    'score': r.relevance_score,
                    'section_type': r.section_type,
                    'metadata': {},  # Strip all metadata
                    '_original_nct': r.nct_id  # Keep for debugging only
                })

            # WARN if no results found (helps debug RAG issues)
            if not filtered_results:
                print(f"[RAG Adapter] ⚠️ No examples found for {section_type} (query: '{query[:50]}...')")
            else:
                print(f"[RAG Adapter] Found {len(filtered_results)} SANITIZED examples for {section_type}")

            return filtered_results

        except Exception as e:
            print(f"[RAG Adapter] ❌ Error retrieving for {section_type}: {e}")
            return []

    def _sanitize_content(self, content: str) -> str:
        """
        CRITICAL: Sanitize RAG content to prevent contamination.

        Strips ALL:
        - Numbers (sample sizes, event counts, etc.)
        - Study names (CheckMate, KEYNOTE, JAVELIN, etc.)
        - Drug names (nivolumab, avelumab, etc.)
        - Indication terms (mRCC, NSCLC, etc.)
        - Metadata (Chunk ID, Source, Score, etc.)

        Returns structure-only content safe for LLM prompting.
        """
        sanitized = content

        # Apply all sanitization patterns
        for pattern, replacement in self.SANITIZE_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)

        # Clean up multiple placeholders and whitespace
        sanitized = re.sub(r'\[N\]\s*\[N\]', '[N]', sanitized)
        sanitized = re.sub(r'\s+', ' ', sanitized)
        sanitized = sanitized.strip()

        return sanitized

    def _has_wrong_indication(self, content: str, current_indication: str) -> bool:
        """
        Check if content contains wrong indication terms.

        Prevents RCC content from being used for NSCLC queries, etc.
        """
        patterns_to_check = self.WRONG_INDICATION_PATTERNS.get(current_indication, [])

        for pattern in patterns_to_check:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False

    def _build_filters(self, protocol_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build filters for RAG query"""
        filters = {}

        if protocol_data.get('therapeutic_area'):
            filters['therapeutic_area'] = protocol_data['therapeutic_area']

        if protocol_data.get('phase'):
            filters['phase'] = protocol_data['phase']

        # Add indication filter if available
        if protocol_data.get('indication'):
            filters['indication'] = protocol_data['indication']

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
