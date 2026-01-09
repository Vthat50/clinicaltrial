"""
RAG Integration Layer
=====================

Connects enterprise SAP modules to the ChromaDB RAG system for dynamic content retrieval.

Instead of hardcoded methodology text, this layer:
1. Queries ChromaDB for similar SAP sections from real trials
2. Retrieves tumor-specific response criteria from specialized_criteria PDFs
3. Pulls safety analysis patterns from validated SAPs
4. Provides context-aware content generation

Integration Points:
- Response criteria modules (RECIST, iRECIST, irRC, RANO, Cheson)
- Safety analysis modules (AE, Laboratory, Vital Signs, ECG)
- Statistical methods modules (all 14 modules)
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# ChromaDB imports (optional - gracefully degrade if not available)
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    logger.warning("ChromaDB not available - RAG features will be disabled")
    CHROMADB_AVAILABLE = False


@dataclass
class RAGConfig:
    """Configuration for RAG system integration"""
    # Path to sap_data directory
    sap_data_path: Path = Path(r"C:\Users\vijay\Desktop\sap_data")

    # ChromaDB paths
    chroma_db_path: Path = None
    chroma_unified_path: Path = None

    # Collection names
    collection_structure: str = "sap_structure"
    collection_content: str = "sap_content"
    collection_tlf: str = "sap_tlf"
    collection_criteria: str = "response_criteria"
    collection_safety: str = "safety_analysis"

    # Specialized criteria paths
    specialized_criteria_path: Path = None

    # RAG behavior
    use_rag: bool = True
    fallback_to_hardcoded: bool = True
    max_retrieved_examples: int = 3
    similarity_threshold: float = 0.7

    def __post_init__(self):
        """Initialize derived paths"""
        if self.chroma_db_path is None:
            self.chroma_db_path = self.sap_data_path / "chroma_db"

        if self.chroma_unified_path is None:
            self.chroma_unified_path = self.sap_data_path / "chroma_unified"

        if self.specialized_criteria_path is None:
            self.specialized_criteria_path = self.sap_data_path / "specialized_criteria"


@dataclass
class RetrievedExample:
    """A retrieved example from RAG system"""
    content: str
    nct_id: str
    trial_name: str
    section_name: str
    similarity_score: float
    metadata: Dict


class RAGIntegrationService:
    """
    Service for integrating enterprise modules with ChromaDB RAG system.

    Provides methods to:
    - Query for similar SAP sections
    - Retrieve tumor-specific criteria examples
    - Pull safety analysis patterns
    - Generate context-aware methodology text
    """

    def __init__(self, config: RAGConfig = None):
        """
        Initialize RAG integration service.

        Args:
            config: RAG configuration (uses defaults if not provided)
        """
        self.config = config or RAGConfig()
        self.client = None
        self.collections = {}

        # Initialize ChromaDB if available
        if CHROMADB_AVAILABLE and self.config.use_rag:
            self._initialize_chromadb()
        else:
            logger.warning("RAG system not available - using hardcoded fallbacks")

    def _initialize_chromadb(self):
        """Initialize ChromaDB client and collections"""
        try:
            # Try unified database first (preferred)
            if self.config.chroma_unified_path.exists():
                self.client = chromadb.PersistentClient(
                    path=str(self.config.chroma_unified_path)
                )
                logger.info(f"Connected to ChromaDB at {self.config.chroma_unified_path}")
            elif self.config.chroma_db_path.exists():
                self.client = chromadb.PersistentClient(
                    path=str(self.config.chroma_db_path)
                )
                logger.info(f"Connected to ChromaDB at {self.config.chroma_db_path}")
            else:
                logger.warning("ChromaDB database not found - RAG features disabled")
                self.config.use_rag = False
                return

            # Get or create collections
            self._load_collections()

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.config.use_rag = False

    def _load_collections(self):
        """Load all collections"""
        collection_names = [
            self.config.collection_structure,
            self.config.collection_content,
            self.config.collection_tlf,
        ]

        for name in collection_names:
            try:
                self.collections[name] = self.client.get_collection(name=name)
                logger.info(f"Loaded collection: {name}")
            except Exception as e:
                logger.warning(f"Collection {name} not found: {e}")

    def query_sap_sections(
        self,
        query: str,
        section_type: str = None,
        phase: str = None,
        endpoint_type: str = None,
        n_results: int = 3
    ) -> List[RetrievedExample]:
        """
        Query SAP content collection for similar sections.

        Args:
            query: Search query
            section_type: Filter by section (e.g., "sample_size", "statistical_methods")
            phase: Filter by trial phase (e.g., "Phase 3")
            endpoint_type: Filter by endpoint (e.g., "Time-to-Event")
            n_results: Number of results to retrieve

        Returns:
            List of retrieved examples with similarity scores
        """
        if not self.config.use_rag or self.config.collection_content not in self.collections:
            return []

        try:
            collection = self.collections[self.config.collection_content]

            # Build where filter
            where_filter = {}
            if section_type:
                where_filter["section_name"] = section_type
            if phase:
                where_filter["phase"] = phase
            if endpoint_type:
                where_filter["endpoint_type"] = endpoint_type

            # Query
            results = collection.query(
                query_texts=[query],
                n_results=min(n_results, self.config.max_retrieved_examples),
                where=where_filter if where_filter else None
            )

            # Parse results
            examples = []
            if results and results['documents'] and len(results['documents']) > 0:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                    distance = results['distances'][0][i] if results['distances'] else 1.0
                    similarity = 1.0 - distance  # Convert distance to similarity

                    if similarity >= self.config.similarity_threshold:
                        examples.append(RetrievedExample(
                            content=doc,
                            nct_id=metadata.get('nct_id', 'UNKNOWN'),
                            trial_name=metadata.get('trial_name', 'Unknown'),
                            section_name=metadata.get('section_name', 'Unknown'),
                            similarity_score=similarity,
                            metadata=metadata
                        ))

            logger.info(f"Retrieved {len(examples)} examples for query: {query[:50]}...")
            return examples

        except Exception as e:
            logger.error(f"Error querying SAP sections: {e}")
            return []

    def get_response_criteria_examples(
        self,
        criteria_type: str,
        indication: str = None
    ) -> List[RetrievedExample]:
        """
        Retrieve examples of specific response criteria from real SAPs.

        Args:
            criteria_type: Type of criteria (e.g., "RANO", "Cheson", "irRC")
            indication: Tumor type/indication filter

        Returns:
            List of relevant examples
        """
        # Build query based on criteria type
        queries = {
            "RANO": "RANO response assessment neuro-oncology brain tumor glioblastoma",
            "Cheson": "Cheson Lugano lymphoma response PET Deauville",
            "irRC": "immune-related response criteria irRC pseudoprogression",
            "iRECIST": "iRECIST immunotherapy response unconfirmed progressive disease",
            "RECIST": "RECIST 1.1 response assessment target lesions"
        }

        query = queries.get(criteria_type, criteria_type)

        # Add indication to query if provided
        if indication:
            query = f"{query} {indication}"

        return self.query_sap_sections(
            query=query,
            section_type="efficacy_analysis",
            n_results=self.config.max_retrieved_examples
        )

    def get_safety_analysis_examples(
        self,
        analysis_type: str,
        phase: str = None
    ) -> List[RetrievedExample]:
        """
        Retrieve safety analysis examples from real SAPs.

        Args:
            analysis_type: Type of analysis (e.g., "adverse_events", "laboratory", "ECG")
            phase: Trial phase filter

        Returns:
            List of relevant examples
        """
        queries = {
            "adverse_events": "adverse event analysis TEAE SAE Grade 3 CTCAE",
            "laboratory": "laboratory analysis shift tables Hy's Law liver function",
            "vital_signs": "vital signs blood pressure heart rate",
            "ECG": "ECG QTc prolongation Fridericia cardiac safety",
            "exposure": "drug exposure dose intensity modifications"
        }

        query = queries.get(analysis_type, analysis_type)

        return self.query_sap_sections(
            query=query,
            section_type="safety_analysis",
            phase=phase,
            n_results=self.config.max_retrieved_examples
        )

    def get_statistical_method_examples(
        self,
        method_type: str,
        endpoint_type: str = None
    ) -> List[RetrievedExample]:
        """
        Retrieve statistical method examples from real SAPs.

        Args:
            method_type: Method type (e.g., "survival", "missing_data", "multiplicity")
            endpoint_type: Endpoint type filter

        Returns:
            List of relevant examples
        """
        queries = {
            "survival": "Kaplan-Meier survival analysis log-rank Cox proportional hazards",
            "missing_data": "missing data multiple imputation MAR sensitivity analysis",
            "multiplicity": "multiplicity adjustment Bonferroni Holm alpha spending",
            "interim": "interim analysis group sequential O'Brien-Fleming alpha spending",
            "subgroup": "subgroup analysis forest plot interaction test",
            "estimands": "estimand ICH E9(R1) intercurrent events treatment policy",
            "sample_size": "sample size calculation power analysis Schoenfeld events",
            "bayesian": "Bayesian analysis posterior probability predictive",
            "PRO": "patient-reported outcomes EORTC QLQ-C30 time to deterioration"
        }

        query = queries.get(method_type, method_type)

        return self.query_sap_sections(
            query=query,
            section_type="statistical_methods",
            endpoint_type=endpoint_type,
            n_results=self.config.max_retrieved_examples
        )

    def enhance_methodology_text(
        self,
        base_text: str,
        context: Dict
    ) -> str:
        """
        Enhance hardcoded methodology text with RAG-retrieved examples.

        Args:
            base_text: Hardcoded methodology text
            context: Context dict with keys like 'criteria_type', 'indication', 'phase'

        Returns:
            Enhanced text with real-world examples
        """
        if not self.config.use_rag:
            return base_text

        # Determine what to query based on context
        examples = []

        if 'criteria_type' in context:
            examples = self.get_response_criteria_examples(
                criteria_type=context['criteria_type'],
                indication=context.get('indication')
            )
        elif 'safety_type' in context:
            examples = self.get_safety_analysis_examples(
                analysis_type=context['safety_type'],
                phase=context.get('phase')
            )
        elif 'method_type' in context:
            examples = self.get_statistical_method_examples(
                method_type=context['method_type'],
                endpoint_type=context.get('endpoint_type')
            )

        if not examples:
            return base_text

        # Add examples section
        enhanced_text = base_text + "\n\n"
        enhanced_text += "### Examples from Real Trials\n\n"

        for i, example in enumerate(examples, 1):
            enhanced_text += f"**Example {i}: {example.trial_name} ({example.nct_id})**\n\n"
            enhanced_text += f"{example.content[:500]}...\n\n"

        return enhanced_text

    def get_specialized_criteria_pdfs(
        self,
        criteria_type: str
    ) -> List[Path]:
        """
        Get paths to specialized criteria PDFs.

        Args:
            criteria_type: Criteria type (e.g., "RANO", "Lugano")

        Returns:
            List of PDF paths
        """
        mapping = {
            "RANO": "brain_RANO",
            "Cheson": "lymphoma_Lugano",
            "Lugano": "lymphoma_Lugano",
            "irRC": "melanoma_irRECIST",
            "iRECIST": "iRECIST",
            "RECIST": "RECIST_full",
            "mRECIST": "HCC_mRECIST"
        }

        folder_name = mapping.get(criteria_type)
        if not folder_name:
            return []

        folder_path = self.config.specialized_criteria_path / folder_name
        if not folder_path.exists():
            return []

        return list(folder_path.glob("*.pdf"))

    def validate_rag_availability(self) -> Dict[str, bool]:
        """
        Check availability of RAG system components.

        Returns:
            Dict with availability status of each component
        """
        status = {
            "chromadb_installed": CHROMADB_AVAILABLE,
            "sap_data_exists": self.config.sap_data_path.exists(),
            "chroma_db_exists": self.config.chroma_unified_path.exists(),
            "specialized_criteria_exists": self.config.specialized_criteria_path.exists(),
            "collections_loaded": len(self.collections) > 0,
            "rag_enabled": self.config.use_rag
        }

        return status


# Singleton instance
_rag_service: Optional[RAGIntegrationService] = None


def get_rag_service(config: RAGConfig = None) -> RAGIntegrationService:
    """
    Get RAG integration service instance.

    Args:
        config: Optional RAG configuration

    Returns:
        RAGIntegrationService instance
    """
    global _rag_service

    if _rag_service is None:
        _rag_service = RAGIntegrationService(config=config)

    return _rag_service


def enable_rag_for_module(
    module_name: str,
    query_context: Dict
) -> Tuple[bool, List[RetrievedExample]]:
    """
    Helper function to enable RAG for any module.

    Usage in module:
        rag_enabled, examples = enable_rag_for_module(
            "RANO",
            {"criteria_type": "RANO", "indication": "glioblastoma"}
        )

        if rag_enabled:
            # Use examples to enhance methodology
            pass
        else:
            # Fall back to hardcoded text
            pass

    Args:
        module_name: Name of calling module
        query_context: Context for RAG query

    Returns:
        Tuple of (RAG enabled boolean, list of examples)
    """
    try:
        rag_service = get_rag_service()

        if not rag_service.config.use_rag:
            return False, []

        # Query based on context
        if 'criteria_type' in query_context:
            examples = rag_service.get_response_criteria_examples(
                criteria_type=query_context['criteria_type'],
                indication=query_context.get('indication')
            )
        elif 'safety_type' in query_context:
            examples = rag_service.get_safety_analysis_examples(
                analysis_type=query_context['safety_type'],
                phase=query_context.get('phase')
            )
        elif 'method_type' in query_context:
            examples = rag_service.get_statistical_method_examples(
                method_type=query_context['method_type'],
                endpoint_type=query_context.get('endpoint_type')
            )
        else:
            # Generic query
            examples = rag_service.query_sap_sections(
                query=query_context.get('query', module_name)
            )

        return True, examples

    except Exception as e:
        logger.error(f"RAG query failed for {module_name}: {e}")
        return False, []
