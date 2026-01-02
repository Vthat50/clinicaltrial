#!/usr/bin/env python3
"""
Knowledge Graph for SAP Methodology
====================================

Builds a graph of relationships between:
- Trials (NCT IDs)
- Drug classes (checkpoint inhibitor, TKI, chemotherapy)
- Indications (NSCLC, melanoma, RCC)
- Statistical methods (log-rank, Fleming-Harrington, RPSFT)
- Conditions (delayed effect, crossover, interim analysis)

The graph enables queries like:
- "What methods do checkpoint inhibitor trials use?"
- "What trials with NSCLC used Fleming-Harrington?"
- "Given this protocol, what similar trials exist and what methods did they use?"
"""

import re
import json
import pickle
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    print("Warning: networkx not installed. Run: pip install networkx")


# Entity extraction patterns
PATTERNS = {
    # Drug classes
    "checkpoint_inhibitor": [
        r"nivolumab", r"pembrolizumab", r"atezolizumab", r"durvalumab",
        r"avelumab", r"ipilimumab", r"tremelimumab", r"cemiplimab",
        r"checkpoint inhibitor", r"anti-PD-1", r"anti-PD-L1", r"anti-CTLA-4",
        r"PD-1 inhibitor", r"PD-L1 inhibitor", r"immunotherapy"
    ],
    "tki": [
        r"sunitinib", r"sorafenib", r"axitinib", r"cabozantinib", r"lenvatinib",
        r"pazopanib", r"regorafenib", r"vandetanib", r"gefitinib", r"erlotinib",
        r"osimertinib", r"crizotinib", r"alectinib", r"brigatinib", r"lorlatinib",
        r"tyrosine kinase inhibitor", r"TKI", r"VEGFR", r"EGFR inhibitor"
    ],
    "chemotherapy": [
        r"docetaxel", r"paclitaxel", r"carboplatin", r"cisplatin", r"oxaliplatin",
        r"gemcitabine", r"pemetrexed", r"capecitabine", r"fluorouracil", r"5-FU",
        r"doxorubicin", r"cyclophosphamide", r"etoposide", r"irinotecan",
        r"chemotherapy", r"cytotoxic"
    ],
    "her2_targeted": [
        r"trastuzumab", r"pertuzumab", r"T-DM1", r"trastuzumab deruxtecan",
        r"DS-8201", r"HER2", r"anti-HER2"
    ],
    "cdk_inhibitor": [
        r"palbociclib", r"ribociclib", r"abemaciclib", r"CDK4/6", r"CDK inhibitor"
    ],

    # Indications
    "nsclc": [r"NSCLC", r"non-small cell lung", r"non-small-cell lung"],
    "sclc": [r"SCLC", r"small cell lung", r"small-cell lung"],
    "melanoma": [r"melanoma", r"cutaneous melanoma"],
    "rcc": [r"RCC", r"renal cell carcinoma", r"kidney cancer"],
    "uc": [r"urothelial", r"bladder cancer", r"UC "],
    "hnscc": [r"HNSCC", r"head and neck", r"squamous cell carcinoma of head"],
    "hcc": [r"HCC", r"hepatocellular", r"liver cancer"],
    "crc": [r"CRC", r"colorectal", r"colon cancer"],
    "breast": [r"breast cancer", r"TNBC", r"HR\+", r"HER2\+"],
    "gastric": [r"gastric", r"stomach cancer", r"GEJ", r"gastroesophageal"],
    "esophageal": [r"esophageal", r"oesophageal"],
    "ovarian": [r"ovarian", r"epithelial ovarian"],
    "prostate": [r"prostate", r"CRPC", r"mCRPC", r"nmCRPC"],

    # Statistical methods
    "log_rank": [r"log-rank", r"logrank", r"log rank test"],
    "fleming_harrington": [
        r"Fleming-Harrington", r"Fleming Harrington", r"FH\s*\(", r"G\s*\(\s*\d",
        r"weighted log-rank", r"weighted logrank"
    ],
    "cox_regression": [r"Cox proportional", r"Cox regression", r"Cox model", r"hazard ratio"],
    "kaplan_meier": [r"Kaplan-Meier", r"Kaplan Meier", r"KM estimate", r"KM curve"],
    "rmst": [r"RMST", r"restricted mean survival", r"restricted mean"],
    "maxcombo": [r"MaxCombo", r"max-combo", r"combination test"],
    "lan_demets": [r"Lan-DeMets", r"Lan DeMets", r"alpha spending", r"spending function"],
    "obrien_fleming": [r"O'Brien-Fleming", r"OBrien-Fleming", r"O'Brien Fleming"],
    "rpsft": [r"RPSFT", r"rank preserving", r"structural failure time"],
    "ipcw": [r"IPCW", r"inverse probability", r"censoring weight"],
    "iptw": [r"IPTW", r"inverse probability of treatment"],
    "hierarchical_testing": [
        r"hierarchical test", r"gatekeeping", r"fixed sequence",
        r"sequential testing", r"testing hierarchy"
    ],
    "multiplicity": [
        r"multiplicity", r"multiple endpoint", r"multiple comparison",
        r"Bonferroni", r"Hochberg", r"Holm"
    ],

    # Conditions/characteristics
    "delayed_effect": [
        r"delayed effect", r"delayed treatment effect", r"non-proportional hazard",
        r"nonproportional hazard", r"NPH", r"crossing curves"
    ],
    "crossover": [
        r"crossover", r"cross-over", r"treatment switching", r"switch to",
        r"crossed over"
    ],
    "interim_analysis": [
        r"interim analysis", r"interim look", r"group sequential",
        r"data monitoring committee", r"DMC", r"DSMB"
    ],
    "bridging_study": [
        r"bridging study", r"bridging trial", r"ethnic factor",
        r"multi-regional", r"MRCT", r"consistency"
    ],
    "china_regulatory": [
        r"NMPA", r"China", r"Chinese", r"CDE", r"China NDA"
    ],
    "japan_regulatory": [
        r"PMDA", r"Japan", r"Japanese"
    ],
}


@dataclass
class TrialNode:
    """Represents a clinical trial in the knowledge graph."""
    nct_id: str
    name: str = ""
    indication: str = ""
    sponsor: str = ""
    phase: str = ""
    drug_classes: Set[str] = field(default_factory=set)
    methods: Set[str] = field(default_factory=set)
    conditions: Set[str] = field(default_factory=set)
    chunk_ids: List[str] = field(default_factory=list)


@dataclass
class MethodNode:
    """Represents a statistical method in the knowledge graph."""
    name: str
    category: str  # primary_analysis, interim, sensitivity, multiplicity
    description: str = ""
    used_by_trials: Set[str] = field(default_factory=set)
    associated_conditions: Set[str] = field(default_factory=set)


class SAPKnowledgeGraph:
    """
    Knowledge Graph for SAP methodology relationships.

    Enables queries like:
    - get_methods_for_drug_class("checkpoint_inhibitor") → {"fleming_harrington": 0.7, "log_rank": 0.3}
    - get_similar_trials(indication="NSCLC", drug_class="checkpoint_inhibitor") → [NCT02066...]
    - get_method_rationale("fleming_harrington") → "Used for delayed treatment effects in immunotherapy"
    """

    def __init__(self, persist_path: Optional[Path] = None):
        if not NETWORKX_AVAILABLE:
            raise ImportError("networkx required. Install with: pip install networkx")

        self.graph = nx.MultiDiGraph()
        self.trials: Dict[str, TrialNode] = {}
        self.methods: Dict[str, MethodNode] = {}
        self.persist_path = persist_path or Path(__file__).parent.parent.parent / "data" / "knowledge_graph.pkl"

        # Statistics for method recommendations
        self.drug_class_method_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.indication_method_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.condition_method_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def extract_entities(self, text: str) -> Dict[str, Set[str]]:
        """Extract entities from text using pattern matching."""
        entities = defaultdict(set)
        text_lower = text.lower()

        for entity_type, patterns in PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    # Categorize the entity
                    if entity_type in ["checkpoint_inhibitor", "tki", "chemotherapy", "her2_targeted", "cdk_inhibitor"]:
                        entities["drug_class"].add(entity_type)
                    elif entity_type in ["nsclc", "sclc", "melanoma", "rcc", "uc", "hnscc", "hcc", "crc", "breast", "gastric", "esophageal", "ovarian", "prostate"]:
                        entities["indication"].add(entity_type)
                    elif entity_type in ["log_rank", "fleming_harrington", "cox_regression", "kaplan_meier", "rmst", "maxcombo", "lan_demets", "obrien_fleming", "rpsft", "ipcw", "iptw", "hierarchical_testing", "multiplicity"]:
                        entities["method"].add(entity_type)
                    elif entity_type in ["delayed_effect", "crossover", "interim_analysis", "bridging_study", "china_regulatory", "japan_regulatory"]:
                        entities["condition"].add(entity_type)

        return dict(entities)

    def add_trial_from_chunk(self, chunk_id: str, content: str, metadata: Dict[str, Any]):
        """Add or update trial information from a chunk."""
        # Extract NCT ID
        nct_match = re.search(r"NCT\d{8}", chunk_id) or re.search(r"NCT\d{8}", content)
        if not nct_match:
            return

        nct_id = nct_match.group()

        # Get or create trial node
        if nct_id not in self.trials:
            self.trials[nct_id] = TrialNode(nct_id=nct_id)

        trial = self.trials[nct_id]

        # Update from metadata
        if metadata.get("indication"):
            trial.indication = metadata["indication"]
        if metadata.get("sponsor"):
            trial.sponsor = metadata["sponsor"]
        if metadata.get("source"):
            # Extract trial name from source like "NCT02684006 - JAVELIN Renal 101"
            source = metadata["source"]
            if " - " in source:
                trial.name = source.split(" - ", 1)[1]

        # Extract entities from content
        entities = self.extract_entities(content)

        trial.drug_classes.update(entities.get("drug_class", set()))
        trial.methods.update(entities.get("method", set()))
        trial.conditions.update(entities.get("condition", set()))
        trial.chunk_ids.append(chunk_id)

        # Add special methods from metadata
        special_methods = metadata.get("special_methods", "")
        if special_methods and special_methods != "None":
            for method in special_methods.split(", "):
                method_key = method.lower().replace(" ", "_").replace("-", "_")
                trial.methods.add(method_key)

    def build_from_vector_store(self, vector_store):
        """Build knowledge graph from all chunks in the vector store."""
        print("Building Knowledge Graph from Vector Store...")

        total_chunks = 0

        for collection_name, collection in vector_store.collections.items():
            if collection is None:
                continue

            try:
                # Get all documents from collection
                result = collection.get(include=["documents", "metadatas"])

                if not result["ids"]:
                    continue

                print(f"  Processing {collection_name}: {len(result['ids'])} chunks")

                for chunk_id, content, metadata in zip(
                    result["ids"],
                    result["documents"],
                    result["metadatas"]
                ):
                    self.add_trial_from_chunk(chunk_id, content, metadata or {})
                    total_chunks += 1

            except Exception as e:
                print(f"  Error processing {collection_name}: {e}")

        print(f"\nProcessed {total_chunks} chunks")
        print(f"Found {len(self.trials)} unique trials")

        # Build the graph structure
        self._build_graph()

        # Compute statistics
        self._compute_statistics()

        return self

    def _build_graph(self):
        """Build NetworkX graph from trial data."""
        # Add trial nodes
        for nct_id, trial in self.trials.items():
            self.graph.add_node(
                nct_id,
                node_type="trial",
                name=trial.name,
                indication=trial.indication,
                sponsor=trial.sponsor
            )

            # Add edges to drug classes
            for drug_class in trial.drug_classes:
                self.graph.add_node(drug_class, node_type="drug_class")
                self.graph.add_edge(nct_id, drug_class, relation="uses_drug_class")

            # Add edges to methods
            for method in trial.methods:
                self.graph.add_node(method, node_type="method")
                self.graph.add_edge(nct_id, method, relation="uses_method")

            # Add edges to conditions
            for condition in trial.conditions:
                self.graph.add_node(condition, node_type="condition")
                self.graph.add_edge(nct_id, condition, relation="has_condition")

            # Add indication edge
            if trial.indication:
                ind_key = trial.indication.lower().replace(" ", "_")
                self.graph.add_node(ind_key, node_type="indication")
                self.graph.add_edge(nct_id, ind_key, relation="treats")

    def _compute_statistics(self):
        """Compute co-occurrence statistics for recommendations."""
        for nct_id, trial in self.trials.items():
            for drug_class in trial.drug_classes:
                for method in trial.methods:
                    self.drug_class_method_counts[drug_class][method] += 1

            for condition in trial.conditions:
                for method in trial.methods:
                    self.condition_method_counts[condition][method] += 1

            if trial.indication:
                ind_key = trial.indication.lower().replace(" ", "_")
                for method in trial.methods:
                    self.indication_method_counts[ind_key][method] += 1

    def get_methods_for_drug_class(self, drug_class: str) -> Dict[str, float]:
        """Get method recommendations for a drug class with confidence scores."""
        counts = self.drug_class_method_counts.get(drug_class, {})
        if not counts:
            return {}

        total = sum(counts.values())
        return {method: count / total for method, count in sorted(counts.items(), key=lambda x: -x[1])}

    def get_methods_for_condition(self, condition: str) -> Dict[str, float]:
        """Get method recommendations for a condition with confidence scores."""
        counts = self.condition_method_counts.get(condition, {})
        if not counts:
            return {}

        total = sum(counts.values())
        return {method: count / total for method, count in sorted(counts.items(), key=lambda x: -x[1])}

    def get_methods_for_indication(self, indication: str) -> Dict[str, float]:
        """Get method recommendations for an indication with confidence scores."""
        ind_key = indication.lower().replace(" ", "_")
        counts = self.indication_method_counts.get(ind_key, {})
        if not counts:
            return {}

        total = sum(counts.values())
        return {method: count / total for method, count in sorted(counts.items(), key=lambda x: -x[1])}

    def get_similar_trials(
        self,
        drug_class: Optional[str] = None,
        indication: Optional[str] = None,
        condition: Optional[str] = None,
        limit: int = 10
    ) -> List[Tuple[str, TrialNode, float]]:
        """Find trials similar to the given characteristics."""
        scores = defaultdict(float)

        for nct_id, trial in self.trials.items():
            score = 0.0

            if drug_class and drug_class in trial.drug_classes:
                score += 1.0

            if indication:
                ind_key = indication.lower().replace(" ", "_")
                if ind_key in trial.indication.lower():
                    score += 1.0

            if condition and condition in trial.conditions:
                score += 0.5

            if score > 0:
                scores[nct_id] = score

        # Sort by score
        sorted_trials = sorted(scores.items(), key=lambda x: -x[1])[:limit]

        return [(nct_id, self.trials[nct_id], score) for nct_id, score in sorted_trials]

    def recommend_methods(
        self,
        drug_classes: List[str] = None,
        indication: str = None,
        conditions: List[str] = None
    ) -> Dict[str, float]:
        """
        Recommend statistical methods based on trial characteristics.

        This is the key function that replaces hardcoded rules.
        It learns from the existing SAP corpus what methods are used
        for similar trials.
        """
        method_scores = defaultdict(float)
        weights_used = 0

        # Weight by drug class (highest weight - most predictive)
        if drug_classes:
            for drug_class in drug_classes:
                class_methods = self.get_methods_for_drug_class(drug_class)
                for method, score in class_methods.items():
                    method_scores[method] += score * 2.0  # Weight = 2.0
                if class_methods:
                    weights_used += 2.0

        # Weight by condition (medium weight)
        if conditions:
            for condition in conditions:
                cond_methods = self.get_methods_for_condition(condition)
                for method, score in cond_methods.items():
                    method_scores[method] += score * 1.5  # Weight = 1.5
                if cond_methods:
                    weights_used += 1.5

        # Weight by indication (lower weight - less predictive)
        if indication:
            ind_methods = self.get_methods_for_indication(indication)
            for method, score in ind_methods.items():
                method_scores[method] += score * 1.0  # Weight = 1.0
            if ind_methods:
                weights_used += 1.0

        # Normalize
        if weights_used > 0:
            method_scores = {k: v / weights_used for k, v in method_scores.items()}

        return dict(sorted(method_scores.items(), key=lambda x: -x[1]))

    def save(self, path: Optional[Path] = None):
        """Save knowledge graph to disk."""
        path = path or self.persist_path
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "trials": self.trials,
            "methods": self.methods,
            "drug_class_method_counts": dict(self.drug_class_method_counts),
            "indication_method_counts": dict(self.indication_method_counts),
            "condition_method_counts": dict(self.condition_method_counts),
        }

        with open(path, "wb") as f:
            pickle.dump(data, f)

        print(f"Saved knowledge graph to {path}")

    def load(self, path: Optional[Path] = None) -> "SAPKnowledgeGraph":
        """Load knowledge graph from disk."""
        path = path or self.persist_path

        if not path.exists():
            raise FileNotFoundError(f"Knowledge graph not found at {path}")

        with open(path, "rb") as f:
            data = pickle.load(f)

        self.trials = data["trials"]
        self.methods = data.get("methods", {})
        self.drug_class_method_counts = defaultdict(lambda: defaultdict(int), data["drug_class_method_counts"])
        self.indication_method_counts = defaultdict(lambda: defaultdict(int), data["indication_method_counts"])
        self.condition_method_counts = defaultdict(lambda: defaultdict(int), data["condition_method_counts"])

        # Rebuild graph
        self._build_graph()

        print(f"Loaded knowledge graph from {path}")
        print(f"  Trials: {len(self.trials)}")

        return self

    def print_statistics(self):
        """Print knowledge graph statistics."""
        print("\n" + "=" * 60)
        print("KNOWLEDGE GRAPH STATISTICS")
        print("=" * 60)

        print(f"\nTrials: {len(self.trials)}")

        # Drug class distribution
        drug_class_counts = defaultdict(int)
        for trial in self.trials.values():
            for dc in trial.drug_classes:
                drug_class_counts[dc] += 1

        print("\nDrug Classes:")
        for dc, count in sorted(drug_class_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {dc}: {count} trials")

        # Method distribution
        method_counts = defaultdict(int)
        for trial in self.trials.values():
            for m in trial.methods:
                method_counts[m] += 1

        print("\nMethods:")
        for m, count in sorted(method_counts.items(), key=lambda x: -x[1])[:15]:
            print(f"  {m}: {count} trials")

        # Condition distribution
        condition_counts = defaultdict(int)
        for trial in self.trials.values():
            for c in trial.conditions:
                condition_counts[c] += 1

        print("\nConditions:")
        for c, count in sorted(condition_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {c}: {count} trials")

        # Key relationships
        print("\n" + "-" * 40)
        print("KEY RELATIONSHIPS (learned from data):")
        print("-" * 40)

        print("\nCheckpoint Inhibitor → Methods:")
        for method, score in list(self.get_methods_for_drug_class("checkpoint_inhibitor").items())[:5]:
            print(f"  {method}: {score:.1%}")

        print("\nDelayed Effect → Methods:")
        for method, score in list(self.get_methods_for_condition("delayed_effect").items())[:5]:
            print(f"  {method}: {score:.1%}")

        print("\nInterim Analysis → Methods:")
        for method, score in list(self.get_methods_for_condition("interim_analysis").items())[:5]:
            print(f"  {method}: {score:.1%}")


def create_knowledge_graph(vector_store=None, rebuild: bool = False) -> SAPKnowledgeGraph:
    """
    Factory function to create or load a knowledge graph.

    Args:
        vector_store: Optional vector store to build from
        rebuild: If True, rebuild even if cached version exists

    Returns:
        SAPKnowledgeGraph instance
    """
    kg = SAPKnowledgeGraph()

    if not rebuild and kg.persist_path.exists():
        try:
            return kg.load()
        except Exception as e:
            print(f"Error loading cached KG: {e}")

    if vector_store is None:
        from enterprise_sap_system.rag.vector_store import create_vector_store
        vector_store = create_vector_store()

    kg.build_from_vector_store(vector_store)
    kg.save()

    return kg


if __name__ == "__main__":
    # Build and test the knowledge graph
    kg = create_knowledge_graph(rebuild=True)
    kg.print_statistics()

    # Test recommendations
    print("\n" + "=" * 60)
    print("TEST: Method recommendations for checkpoint inhibitor + NSCLC")
    print("=" * 60)

    recommendations = kg.recommend_methods(
        drug_classes=["checkpoint_inhibitor"],
        indication="NSCLC",
        conditions=["interim_analysis"]
    )

    print("\nRecommended methods:")
    for method, score in list(recommendations.items())[:10]:
        print(f"  {method}: {score:.1%}")
