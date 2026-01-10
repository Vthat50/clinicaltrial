#!/usr/bin/env python3
"""
Hybrid Retriever for SAP Generation
====================================

Combines:
1. Vector Search (semantic similarity from ChromaDB)
2. Graph Search (relationship traversal from Knowledge Graph)
3. Hybrid Reranking (boost results from similar trials)

This is Agent 2 in the Agentic HybridRAG architecture.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Tuple
from collections import defaultdict

from enterprise_sap_system.rag.vector_store import SAPVectorStore, RetrievalResult, create_vector_store

# Knowledge graph removed - using vector-only retrieval
# Graph-based features disabled until new knowledge graph is integrated


@dataclass
class HybridResult:
    """Result from hybrid retrieval combining vector and graph signals."""
    chunk_id: str
    content: str
    nct_id: str
    section_type: str
    metadata: Dict[str, Any]

    # Scoring components
    vector_score: float = 0.0      # Semantic similarity (0-1)
    graph_score: float = 0.0       # Graph relationship score (0-1)
    combined_score: float = 0.0    # Weighted combination

    # Extracted information
    methods_found: Set[str] = field(default_factory=set)
    drug_classes_found: Set[str] = field(default_factory=set)
    conditions_found: Set[str] = field(default_factory=set)

    def __hash__(self):
        return hash(self.chunk_id)


@dataclass
class ProtocolCharacteristics:
    """Structured representation of protocol characteristics for retrieval."""
    drug_classes: List[str] = field(default_factory=list)
    indication: str = ""
    phase: str = ""
    endpoint_type: str = ""  # OS, PFS, ORR, etc.
    design_type: str = ""    # randomized, open-label, crossover
    conditions: List[str] = field(default_factory=list)  # delayed_effect, interim_analysis, etc.
    regions: List[str] = field(default_factory=list)  # china_regulatory, japan_regulatory

    def to_query(self) -> str:
        """Convert characteristics to a search query string."""
        parts = []

        if self.phase:
            parts.append(f"Phase {self.phase}")

        if self.drug_classes:
            parts.extend(self.drug_classes)

        if self.indication:
            parts.append(self.indication)

        if self.endpoint_type:
            parts.append(f"{self.endpoint_type} endpoint")

        if self.design_type:
            parts.append(self.design_type)

        if self.conditions:
            parts.extend(self.conditions)

        return " ".join(parts)


class HybridRetriever:
    """
    Hybrid retrieval combining vector search and knowledge graph traversal.

    Usage:
        retriever = HybridRetriever()

        # From protocol text
        results = retriever.retrieve_for_protocol(protocol_text)

        # From structured characteristics
        chars = ProtocolCharacteristics(
            drug_classes=["checkpoint_inhibitor"],
            indication="NSCLC",
            endpoint_type="OS"
        )
        results = retriever.retrieve(chars)
    """

    def __init__(
        self,
        vector_store: Optional[SAPVectorStore] = None,
        knowledge_graph: Optional[Any] = None,  # SAPKnowledgeGraph removed
        vector_weight: float = 0.4,
        graph_weight: float = 0.6,
    ):
        """
        Initialize hybrid retriever.

        Args:
            vector_store: ChromaDB vector store
            knowledge_graph: SAP knowledge graph
            vector_weight: Weight for vector similarity (0-1)
            graph_weight: Weight for graph relationships (0-1)
        """
        self.vector_store = vector_store or create_vector_store()
        self.knowledge_graph = knowledge_graph  # Knowledge graph disabled

        self.vector_weight = vector_weight
        self.graph_weight = graph_weight

    def extract_characteristics(self, protocol_text: str) -> ProtocolCharacteristics:
        """Extract protocol characteristics from text."""
        chars = ProtocolCharacteristics()
        text_lower = protocol_text.lower()

        # Extract drug classes
        if any(term in text_lower for term in ["nivolumab", "pembrolizumab", "atezolizumab",
                                                "durvalumab", "ipilimumab", "checkpoint",
                                                "anti-pd-1", "anti-pd-l1", "immunotherapy"]):
            chars.drug_classes.append("checkpoint_inhibitor")

        if any(term in text_lower for term in ["sunitinib", "sorafenib", "axitinib",
                                                "cabozantinib", "lenvatinib", "tki",
                                                "tyrosine kinase"]):
            chars.drug_classes.append("tki")

        if any(term in text_lower for term in ["docetaxel", "paclitaxel", "carboplatin",
                                                "cisplatin", "chemotherapy"]):
            chars.drug_classes.append("chemotherapy")

        # Extract indication
        indication_map = {
            "nsclc": ["nsclc", "non-small cell lung", "non-small-cell lung"],
            "sclc": ["sclc", "small cell lung"],
            "melanoma": ["melanoma"],
            "rcc": ["rcc", "renal cell", "kidney cancer"],
            "hcc": ["hcc", "hepatocellular", "liver cancer"],
            "crc": ["crc", "colorectal", "colon cancer"],
            "breast": ["breast cancer", "tnbc"],
            "gastric": ["gastric", "stomach"],
            "hnscc": ["hnscc", "head and neck"],
            "urothelial": ["urothelial", "bladder"],
        }

        for indication, patterns in indication_map.items():
            if any(p in text_lower for p in patterns):
                chars.indication = indication
                break

        # Extract phase
        phase_match = re.search(r"phase\s*([123]|i{1,3})", text_lower)
        if phase_match:
            phase = phase_match.group(1)
            chars.phase = {"i": "1", "ii": "2", "iii": "3"}.get(phase.lower(), phase)

        # Extract endpoint type
        if "overall survival" in text_lower or " os " in text_lower:
            chars.endpoint_type = "OS"
        elif "progression-free survival" in text_lower or "pfs" in text_lower:
            chars.endpoint_type = "PFS"
        elif "overall response rate" in text_lower or "orr" in text_lower:
            chars.endpoint_type = "ORR"

        # Extract conditions
        if any(term in text_lower for term in ["delayed effect", "non-proportional",
                                                "nonproportional", "delayed treatment"]):
            chars.conditions.append("delayed_effect")

        if any(term in text_lower for term in ["crossover", "cross-over",
                                                "treatment switching", "switched"]):
            chars.conditions.append("crossover")

        if any(term in text_lower for term in ["interim analysis", "interim look",
                                                "group sequential", "dmc", "dsmb"]):
            chars.conditions.append("interim_analysis")

        if any(term in text_lower for term in ["bridging", "multi-regional", "mrct",
                                                "ethnic factor", "consistency"]):
            chars.conditions.append("bridging_study")

        # Extract regions
        if any(term in text_lower for term in ["china", "nmpa", "chinese"]):
            chars.regions.append("china_regulatory")
        if any(term in text_lower for term in ["japan", "pmda", "japanese"]):
            chars.regions.append("japan_regulatory")

        return chars

    def _get_graph_similar_trials(
        self,
        chars: ProtocolCharacteristics
    ) -> Dict[str, float]:
        """Get trials similar to characteristics from knowledge graph."""
        trial_scores = defaultdict(float)

        # Get similar trials by drug class
        for drug_class in chars.drug_classes:
            similar = self.knowledge_graph.get_similar_trials(
                drug_class=drug_class,
                indication=chars.indication,
                limit=50
            )
            for nct_id, trial, score in similar:
                trial_scores[nct_id] += score * 2.0  # Drug class weighted heavily

        # Get trials with similar conditions
        for condition in chars.conditions:
            similar = self.knowledge_graph.get_similar_trials(
                condition=condition,
                limit=30
            )
            for nct_id, trial, score in similar:
                trial_scores[nct_id] += score * 1.5

        # Normalize scores
        if trial_scores:
            max_score = max(trial_scores.values())
            trial_scores = {k: v / max_score for k, v in trial_scores.items()}

        return dict(trial_scores)

    def _extract_methods_from_content(self, content: str) -> Set[str]:
        """Extract statistical methods mentioned in content."""
        methods = set()
        content_lower = content.lower()

        method_patterns = {
            "log_rank": [r"log-rank", r"logrank", r"log rank"],
            "fleming_harrington": [r"fleming-harrington", r"fleming harrington", r"fh\s*\(", r"g\s*\(\s*\d"],
            "cox_regression": [r"cox proportional", r"cox regression", r"cox model"],
            "kaplan_meier": [r"kaplan-meier", r"kaplan meier", r"km estimate"],
            "rmst": [r"rmst", r"restricted mean survival"],
            "maxcombo": [r"maxcombo", r"max-combo", r"combination test"],
            "lan_demets": [r"lan-demets", r"lan demets", r"alpha spending"],
            "obrien_fleming": [r"o'brien-fleming", r"obrien-fleming"],
            "rpsft": [r"rpsft", r"rank preserving"],
            "ipcw": [r"ipcw", r"inverse probability.*censoring"],
            "hierarchical_testing": [r"hierarchical test", r"gatekeeping", r"fixed sequence"],
        }

        for method, patterns in method_patterns.items():
            if any(re.search(p, content_lower) for p in patterns):
                methods.add(method)

        return methods

    def retrieve(
        self,
        characteristics: ProtocolCharacteristics,
        section_types: List[str] = None,
        n_results: int = 20,
    ) -> List[HybridResult]:
        """
        Retrieve relevant chunks using hybrid vector + graph search.

        Args:
            characteristics: Protocol characteristics
            section_types: Specific section types to search
            n_results: Number of results to return

        Returns:
            List of HybridResult with combined scoring
        """
        # Default section types for methodology - PRIORITIZED ORDER
        # primary_analysis and statistical_methods are most important for method extraction
        if section_types is None:
            section_types = [
                "primary_analysis",      # Highest priority - contains actual methodology
                "statistical_methods",   # High priority - detailed method descriptions
                "sensitivity_analysis",  # Important for crossover/RPSFT/IPCW
                "interim_analysis",      # Important for alpha spending
                "multiplicity",          # Important for hierarchical testing
                "time_to_event",         # May contain methodology details
            ]

        # Build query from characteristics - emphasize methodology terms
        base_query = characteristics.to_query()

        # Add methodology-specific terms to improve retrieval
        methodology_terms = "primary analysis statistical method log-rank Cox proportional hazards"

        if "checkpoint_inhibitor" in (characteristics.drug_classes or []):
            methodology_terms += " immunotherapy delayed effect Fleming-Harrington weighted"

        if "crossover" in (characteristics.conditions or []):
            methodology_terms += " RPSFT IPCW crossover treatment switching"

        if "interim_analysis" in (characteristics.conditions or []):
            methodology_terms += " interim analysis Lan-DeMets alpha spending O'Brien-Fleming"

        query = f"{base_query} {methodology_terms}".strip()

        if not query:
            query = "statistical analysis plan primary endpoint analysis methods"

        # Get graph-based trial similarities
        graph_trial_scores = self._get_graph_similar_trials(characteristics)

        # Collect results from vector search across section types
        all_results: Dict[str, HybridResult] = {}

        for section_type in section_types:
            try:
                vector_results = self.vector_store.query(
                    section_type=section_type,
                    query_text=query,
                    n_results=n_results // len(section_types) + 5
                )

                for vr in vector_results:
                    chunk_id = vr.nct_id

                    # Extract NCT ID from chunk_id
                    nct_match = re.search(r"NCT\d{8}", chunk_id)
                    nct_id = nct_match.group() if nct_match else ""

                    # Calculate graph score based on trial similarity
                    graph_score = graph_trial_scores.get(nct_id, 0.0)

                    # Boost if trial has similar drug class or condition
                    if nct_id in self.knowledge_graph.trials:
                        trial = self.knowledge_graph.trials[nct_id]

                        # Boost for matching drug class
                        if characteristics.drug_classes:
                            matching_classes = set(characteristics.drug_classes) & trial.drug_classes
                            if matching_classes:
                                graph_score += 0.3 * len(matching_classes)

                        # Boost for matching conditions
                        if characteristics.conditions:
                            matching_conditions = set(characteristics.conditions) & trial.conditions
                            if matching_conditions:
                                graph_score += 0.2 * len(matching_conditions)

                    # Normalize graph score
                    graph_score = min(graph_score, 1.0)

                    # Calculate combined score
                    vector_score = vr.relevance_score
                    combined_score = (
                        self.vector_weight * vector_score +
                        self.graph_weight * graph_score
                    )

                    # Extract methods from content
                    methods_found = self._extract_methods_from_content(vr.content)

                    # Create or update result
                    if chunk_id not in all_results:
                        all_results[chunk_id] = HybridResult(
                            chunk_id=chunk_id,
                            content=vr.content,
                            nct_id=nct_id,
                            section_type=section_type,
                            metadata=vr.metadata,
                            vector_score=vector_score,
                            graph_score=graph_score,
                            combined_score=combined_score,
                            methods_found=methods_found,
                        )
                    else:
                        # Update if better score
                        if combined_score > all_results[chunk_id].combined_score:
                            all_results[chunk_id].combined_score = combined_score
                            all_results[chunk_id].vector_score = vector_score
                            all_results[chunk_id].graph_score = graph_score
                        all_results[chunk_id].methods_found.update(methods_found)

            except Exception as e:
                print(f"Error querying {section_type}: {e}")
                continue

        # Sort by combined score
        sorted_results = sorted(
            all_results.values(),
            key=lambda x: x.combined_score,
            reverse=True
        )

        return sorted_results[:n_results]

    def retrieve_for_protocol(
        self,
        protocol_text: str,
        section_types: List[str] = None,
        n_results: int = 20,
    ) -> List[HybridResult]:
        """
        Retrieve relevant chunks for a protocol text.

        Args:
            protocol_text: Raw protocol text
            section_types: Specific section types to search
            n_results: Number of results to return

        Returns:
            List of HybridResult
        """
        # Extract characteristics from protocol
        chars = self.extract_characteristics(protocol_text)

        # Retrieve using characteristics
        return self.retrieve(chars, section_types, n_results)

    def get_method_recommendations(
        self,
        characteristics: ProtocolCharacteristics,
    ) -> Dict[str, float]:
        """
        Get method recommendations based on similar trials in the knowledge graph.

        This replaces hardcoded rules with data-driven recommendations.
        """
        return self.knowledge_graph.recommend_methods(
            drug_classes=characteristics.drug_classes,
            indication=characteristics.indication,
            conditions=characteristics.conditions
        )

    def retrieve_with_method_context(
        self,
        characteristics: ProtocolCharacteristics,
        n_results: int = 20,
    ) -> Tuple[List[HybridResult], Dict[str, float]]:
        """
        Retrieve chunks AND method recommendations together.

        Returns:
            Tuple of (chunks, method_recommendations)
        """
        # Get chunks
        chunks = self.retrieve(characteristics, n_results=n_results)

        # Get method recommendations from graph
        method_recs = self.get_method_recommendations(characteristics)

        # Also collect methods actually found in retrieved chunks
        chunk_methods = defaultdict(int)
        for chunk in chunks:
            for method in chunk.methods_found:
                chunk_methods[method] += 1

        # Combine graph recommendations with chunk evidence
        combined_recs = {}
        all_methods = set(method_recs.keys()) | set(chunk_methods.keys())

        for method in all_methods:
            graph_score = method_recs.get(method, 0.0)
            chunk_count = chunk_methods.get(method, 0)
            chunk_score = min(chunk_count / max(len(chunks), 1), 1.0)

            # Combined score: graph recommendation + evidence from chunks
            combined_recs[method] = 0.6 * graph_score + 0.4 * chunk_score

        # Sort by combined score
        combined_recs = dict(sorted(combined_recs.items(), key=lambda x: -x[1]))

        return chunks, combined_recs


def create_hybrid_retriever(
    vector_store: Optional[SAPVectorStore] = None,
    knowledge_graph: Optional[SAPKnowledgeGraph] = None,
) -> HybridRetriever:
    """Factory function to create a hybrid retriever."""
    return HybridRetriever(
        vector_store=vector_store,
        knowledge_graph=knowledge_graph
    )


if __name__ == "__main__":
    print("=" * 70)
    print("HYBRID RETRIEVER TEST")
    print("=" * 70)

    # Create retriever
    retriever = create_hybrid_retriever()

    # Test case 1: Checkpoint inhibitor + NSCLC + OS
    print("\n--- Test 1: Checkpoint Inhibitor + NSCLC + OS ---")
    chars1 = ProtocolCharacteristics(
        drug_classes=["checkpoint_inhibitor"],
        indication="nsclc",
        phase="3",
        endpoint_type="OS",
        conditions=["interim_analysis"]
    )

    results1, methods1 = retriever.retrieve_with_method_context(chars1, n_results=10)

    print(f"\nRetrieved {len(results1)} chunks")
    print("\nTop 5 chunks:")
    for r in results1[:5]:
        print(f"  {r.nct_id} | V:{r.vector_score:.2f} G:{r.graph_score:.2f} C:{r.combined_score:.2f}")
        print(f"    Section: {r.section_type}")
        print(f"    Methods: {r.methods_found or 'none detected'}")

    print("\nMethod Recommendations (data-driven):")
    for method, score in list(methods1.items())[:10]:
        print(f"  {method}: {score:.1%}")

    # Test case 2: Immunotherapy with delayed effect
    print("\n--- Test 2: Immunotherapy with Delayed Effect ---")
    chars2 = ProtocolCharacteristics(
        drug_classes=["checkpoint_inhibitor"],
        indication="melanoma",
        endpoint_type="OS",
        conditions=["delayed_effect", "crossover"]
    )

    results2, methods2 = retriever.retrieve_with_method_context(chars2, n_results=10)

    print(f"\nRetrieved {len(results2)} chunks")
    print("\nMethod Recommendations (data-driven):")
    for method, score in list(methods2.items())[:10]:
        print(f"  {method}: {score:.1%}")

    # Test case 3: From raw protocol text
    print("\n--- Test 3: From Protocol Text ---")
    test_protocol = """
    A Phase 3, Randomized, Open-Label Study of Nivolumab versus Docetaxel
    in Patients with Advanced Non-Small Cell Lung Cancer (NSCLC)

    Primary Endpoint: Overall Survival (OS)

    An interim analysis will be conducted when approximately 50% of events
    have occurred. The study includes provisions for crossover to nivolumab
    upon disease progression.

    Given the mechanism of action of checkpoint inhibitors, a delayed
    treatment effect may be observed.
    """

    results3 = retriever.retrieve_for_protocol(test_protocol, n_results=10)

    print(f"\nExtracted characteristics:")
    chars3 = retriever.extract_characteristics(test_protocol)
    print(f"  Drug classes: {chars3.drug_classes}")
    print(f"  Indication: {chars3.indication}")
    print(f"  Endpoint: {chars3.endpoint_type}")
    print(f"  Conditions: {chars3.conditions}")

    print(f"\nRetrieved {len(results3)} chunks")
    print("\nTop methods found in chunks:")
    all_methods = defaultdict(int)
    for r in results3:
        for m in r.methods_found:
            all_methods[m] += 1
    for method, count in sorted(all_methods.items(), key=lambda x: -x[1])[:10]:
        print(f"  {method}: {count} chunks")
