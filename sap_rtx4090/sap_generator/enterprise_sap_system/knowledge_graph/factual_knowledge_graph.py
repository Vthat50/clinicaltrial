"""
Factual Knowledge Graph v1.0
============================

A PROPER knowledge graph that stores FACTS with PROVENANCE, not inferences.

Node Types:
- Trial: NCT ID, phase, indication
- Document: filename, type (SAP/Protocol/SOP)
- Endpoint: name, type (primary/secondary/exploratory)
- Method: statistical method name
- Table: TFL identifier, title
- Quote: exact text extraction

Edge Types (FACTUAL ONLY - NO INFERENCE):
- has_endpoint: Trial → Endpoint
- analyzed_with: Endpoint → Method
- extracted_from: Any → Document
- quoted_as: Any → Quote
- similar_to: Trial → Trial (computed similarity, no decision)
- uses_template: Trial → Table

⚠️ NO EDGES LIKE:
- should_use (inference)
- implies (inference)
- requires (inference)
- recommends (inference)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
import json
import hashlib
from pathlib import Path
from datetime import datetime


# =============================================================================
# NODE TYPES
# =============================================================================

class NodeType(Enum):
    TRIAL = "trial"
    DOCUMENT = "document"
    ENDPOINT = "endpoint"
    METHOD = "method"
    TABLE = "table"
    QUOTE = "quote"
    POPULATION = "population"
    STRATUM = "stratum"


@dataclass
class Node:
    """Base node with unique ID and type."""
    id: str
    node_type: NodeType
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.node_type.value,
            "attributes": self.attributes
        }


@dataclass
class TrialNode(Node):
    """Trial node - represents a clinical trial."""
    def __init__(self, nct_id: str, phase: str = "", indication: str = "", title: str = ""):
        super().__init__(
            id=nct_id,
            node_type=NodeType.TRIAL,
            attributes={
                "nct_id": nct_id,
                "phase": phase,
                "indication": indication,
                "title": title
            }
        )


@dataclass
class DocumentNode(Node):
    """Document node - represents a source document (SAP, Protocol, SOP)."""
    def __init__(self, filename: str, doc_type: str, trial_id: str = ""):
        doc_id = f"doc:{hashlib.md5(filename.encode()).hexdigest()[:8]}"
        super().__init__(
            id=doc_id,
            node_type=NodeType.DOCUMENT,
            attributes={
                "filename": filename,
                "doc_type": doc_type,  # "SAP", "Protocol", "SOP", "CSR"
                "trial_id": trial_id
            }
        )


@dataclass
class EndpointNode(Node):
    """Endpoint node - represents a trial endpoint."""
    def __init__(self, name: str, endpoint_type: str, definition: str = ""):
        endpoint_id = f"endpoint:{hashlib.md5(f'{name}:{endpoint_type}'.encode()).hexdigest()[:8]}"
        super().__init__(
            id=endpoint_id,
            node_type=NodeType.ENDPOINT,
            attributes={
                "name": name,
                "endpoint_type": endpoint_type,  # "primary", "secondary", "exploratory"
                "definition": definition
            }
        )


@dataclass
class MethodNode(Node):
    """Method node - represents a statistical method."""
    def __init__(self, name: str, description: str = ""):
        method_id = f"method:{name.lower().replace(' ', '_')}"
        super().__init__(
            id=method_id,
            node_type=NodeType.METHOD,
            attributes={
                "name": name,
                "description": description
            }
        )


@dataclass
class TableNode(Node):
    """Table/Figure/Listing node."""
    def __init__(self, table_id: str, title: str, table_type: str = "table"):
        super().__init__(
            id=f"tfl:{table_id}",
            node_type=NodeType.TABLE,
            attributes={
                "table_id": table_id,
                "title": title,
                "table_type": table_type  # "table", "figure", "listing"
            }
        )


@dataclass
class QuoteNode(Node):
    """Quote node - exact text extracted from document."""
    def __init__(self, text: str, page: str = "", section: str = ""):
        quote_id = f"quote:{hashlib.md5(text[:100].encode()).hexdigest()[:8]}"
        super().__init__(
            id=quote_id,
            node_type=NodeType.QUOTE,
            attributes={
                "text": text,
                "page": page,
                "section": section
            }
        )


@dataclass
class PopulationNode(Node):
    """Analysis population node."""
    def __init__(self, name: str, definition: str = ""):
        pop_id = f"pop:{name.lower().replace(' ', '_')}"
        super().__init__(
            id=pop_id,
            node_type=NodeType.POPULATION,
            attributes={
                "name": name,
                "definition": definition
            }
        )


@dataclass
class StratumNode(Node):
    """Stratification factor node."""
    def __init__(self, factor_name: str, categories: List[str] = None):
        strat_id = f"strat:{factor_name.lower().replace(' ', '_')}"
        super().__init__(
            id=strat_id,
            node_type=NodeType.STRATUM,
            attributes={
                "factor_name": factor_name,
                "categories": categories or []
            }
        )


# =============================================================================
# EDGE TYPES (FACTUAL ONLY - NO INFERENCE)
# =============================================================================

class EdgeType(Enum):
    """
    ALLOWED edge types (factual relationships):
    - These capture WHAT WAS DONE, not WHAT SHOULD BE DONE
    """
    # Trial relationships
    HAS_ENDPOINT = "has_endpoint"           # Trial → Endpoint (fact: this trial has this endpoint)
    HAS_POPULATION = "has_population"       # Trial → Population
    STRATIFIED_BY = "stratified_by"         # Trial → Stratum

    # Method relationships
    ANALYZED_WITH = "analyzed_with"         # Endpoint → Method (fact: this endpoint was analyzed with this method)

    # Provenance relationships
    EXTRACTED_FROM = "extracted_from"       # Any → Document (provenance)
    QUOTED_AS = "quoted_as"                 # Any → Quote (exact source text)

    # Similarity (computed, no decision)
    SIMILAR_TO = "similar_to"               # Trial → Trial (based on attributes)

    # TFL relationships
    USES_TEMPLATE = "uses_template"         # Trial → Table (fact: this trial used this table)
    PRODUCES_OUTPUT = "produces_output"     # Method → Table


@dataclass
class Edge:
    """Factual edge connecting two nodes."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.edge_type.value,
            "attributes": self.attributes
        }


# =============================================================================
# FACTUAL KNOWLEDGE GRAPH
# =============================================================================

class FactualKnowledgeGraph:
    """
    Knowledge graph that stores FACTS with PROVENANCE.

    This graph:
    ✅ Stores what was done in actual trials
    ✅ Maintains provenance (source document, page, quote)
    ✅ Allows similarity queries without making decisions

    This graph does NOT:
    ❌ Make inference decisions
    ❌ Have "should_use", "implies", "requires" edges
    ❌ Recommend methods based on rules
    """

    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.metadata = {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "type": "factual_knowledge_graph"
        }

    def add_node(self, node: Node) -> str:
        """Add a node to the graph."""
        self.nodes[node.id] = node
        return node.id

    def add_edge(self, edge: Edge) -> None:
        """Add a factual edge to the graph."""
        # Validate edge type is allowed (factual only)
        if edge.edge_type not in EdgeType:
            raise ValueError(f"Invalid edge type: {edge.edge_type}")
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_edges_from(self, source_id: str, edge_type: EdgeType = None) -> List[Edge]:
        """Get all edges from a source node."""
        edges = [e for e in self.edges if e.source_id == source_id]
        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        return edges

    def get_edges_to(self, target_id: str, edge_type: EdgeType = None) -> List[Edge]:
        """Get all edges to a target node."""
        edges = [e for e in self.edges if e.target_id == target_id]
        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        return edges

    def query_by_trial(self, trial_id: str) -> Dict:
        """Get all facts about a trial."""
        result = {
            "trial": self.get_node(trial_id),
            "endpoints": [],
            "methods": [],
            "populations": [],
            "stratification": [],
            "tables": [],
            "sources": []
        }

        for edge in self.get_edges_from(trial_id):
            target = self.get_node(edge.target_id)
            if target:
                if edge.edge_type == EdgeType.HAS_ENDPOINT:
                    result["endpoints"].append(target.to_dict())
                elif edge.edge_type == EdgeType.HAS_POPULATION:
                    result["populations"].append(target.to_dict())
                elif edge.edge_type == EdgeType.STRATIFIED_BY:
                    result["stratification"].append(target.to_dict())
                elif edge.edge_type == EdgeType.USES_TEMPLATE:
                    result["tables"].append(target.to_dict())
                elif edge.edge_type == EdgeType.EXTRACTED_FROM:
                    result["sources"].append(target.to_dict())

        return result

    def query_similar_trials(self, trial_id: str) -> List[Dict]:
        """Get similar trials (factual similarity, no inference)."""
        similar = []
        for edge in self.get_edges_from(trial_id, EdgeType.SIMILAR_TO):
            target = self.get_node(edge.target_id)
            if target:
                similar.append({
                    "trial": target.to_dict(),
                    "similarity_score": edge.attributes.get("similarity_score", 0)
                })
        return similar

    def query_method_usage(self, method_name: str) -> List[Dict]:
        """Get all trials that used a specific method (factual query)."""
        method_id = f"method:{method_name.lower().replace(' ', '_')}"
        results = []

        for edge in self.get_edges_to(method_id, EdgeType.ANALYZED_WITH):
            endpoint = self.get_node(edge.source_id)
            if endpoint:
                # Find trials with this endpoint
                for trial_edge in self.get_edges_to(endpoint.id, EdgeType.HAS_ENDPOINT):
                    trial = self.get_node(trial_edge.source_id)
                    if trial:
                        results.append({
                            "trial": trial.to_dict(),
                            "endpoint": endpoint.to_dict(),
                            "provenance": edge.attributes.get("provenance", {})
                        })

        return results

    def to_dict(self) -> Dict:
        """Export graph to dictionary."""
        return {
            "metadata": self.metadata,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
            "statistics": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "node_types": self._count_by_type("node"),
                "edge_types": self._count_by_type("edge")
            }
        }

    def _count_by_type(self, kind: str) -> Dict[str, int]:
        """Count nodes or edges by type."""
        if kind == "node":
            counts = {}
            for node in self.nodes.values():
                t = node.node_type.value
                counts[t] = counts.get(t, 0) + 1
            return counts
        else:
            counts = {}
            for edge in self.edges:
                t = edge.edge_type.value
                counts[t] = counts.get(t, 0) + 1
            return counts

    def export_json(self, output_path: Path) -> None:
        """Export graph to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        print(f"Graph exported to {output_path}")


# =============================================================================
# FACT EXTRACTOR - Extracts facts from SAP documents
# =============================================================================

class FactExtractor:
    """
    Extracts FACTS from SAP documents and adds them to the knowledge graph.

    This extractor:
    ✅ Extracts what was done (facts)
    ✅ Preserves exact quotes and provenance
    ✅ Links to source documents

    This extractor does NOT:
    ❌ Make inference rules
    ❌ Create "should_use" relationships
    """

    def __init__(self, graph: FactualKnowledgeGraph):
        self.graph = graph

    def extract_from_sap(self, sap_content: str, nct_id: str, filename: str) -> Dict:
        """
        Extract facts from a SAP document.
        Returns extraction statistics.
        """
        stats = {
            "endpoints_extracted": 0,
            "methods_extracted": 0,
            "populations_extracted": 0,
            "tables_extracted": 0,
            "quotes_extracted": 0
        }

        # Create trial node
        trial = TrialNode(nct_id=nct_id)
        self.graph.add_node(trial)

        # Create document node
        doc = DocumentNode(filename=filename, doc_type="SAP", trial_id=nct_id)
        self.graph.add_node(doc)

        # Link trial to document
        self.graph.add_edge(Edge(
            source_id=trial.id,
            target_id=doc.id,
            edge_type=EdgeType.EXTRACTED_FROM
        ))

        # Extract facts from content
        # Note: In production, this would use NLP/regex patterns
        # Here we show the STRUCTURE of factual extraction

        # Example: Extract primary endpoint
        if "primary endpoint" in sap_content.lower():
            stats["endpoints_extracted"] += self._extract_endpoints(sap_content, trial.id, doc.id)

        # Example: Extract statistical methods
        if "log-rank" in sap_content.lower() or "cox" in sap_content.lower():
            stats["methods_extracted"] += self._extract_methods(sap_content, trial.id, doc.id)

        # Example: Extract populations
        if "intent-to-treat" in sap_content.lower() or "safety population" in sap_content.lower():
            stats["populations_extracted"] += self._extract_populations(sap_content, trial.id, doc.id)

        # Example: Extract stratification
        if "stratif" in sap_content.lower():
            self._extract_stratification(sap_content, trial.id, doc.id)

        return stats

    def _extract_endpoints(self, content: str, trial_id: str, doc_id: str) -> int:
        """Extract endpoint facts."""
        count = 0

        # Look for PFS
        if "progression-free survival" in content.lower() or "pfs" in content.lower():
            endpoint = EndpointNode(
                name="Progression-Free Survival",
                endpoint_type="primary",
                definition="Time from randomization to progression or death"
            )
            self.graph.add_node(endpoint)

            # FACTUAL edge: this trial has this endpoint
            self.graph.add_edge(Edge(
                source_id=trial_id,
                target_id=endpoint.id,
                edge_type=EdgeType.HAS_ENDPOINT,
                attributes={"provenance": doc_id}
            ))
            count += 1

        # Look for OS
        if "overall survival" in content.lower():
            endpoint = EndpointNode(
                name="Overall Survival",
                endpoint_type="secondary" if "secondary" in content.lower() else "co-primary",
                definition="Time from randomization to death"
            )
            self.graph.add_node(endpoint)

            self.graph.add_edge(Edge(
                source_id=trial_id,
                target_id=endpoint.id,
                edge_type=EdgeType.HAS_ENDPOINT,
                attributes={"provenance": doc_id}
            ))
            count += 1

        # Look for ORR
        if "objective response" in content.lower() or "orr" in content.lower():
            endpoint = EndpointNode(
                name="Objective Response Rate",
                endpoint_type="secondary",
                definition="Proportion of subjects with CR or PR"
            )
            self.graph.add_node(endpoint)

            self.graph.add_edge(Edge(
                source_id=trial_id,
                target_id=endpoint.id,
                edge_type=EdgeType.HAS_ENDPOINT,
                attributes={"provenance": doc_id}
            ))
            count += 1

        return count

    def _extract_methods(self, content: str, trial_id: str, doc_id: str) -> int:
        """Extract statistical method facts."""
        count = 0

        # Find endpoints first
        endpoint_edges = self.graph.get_edges_from(trial_id, EdgeType.HAS_ENDPOINT)

        # Log-rank test
        if "log-rank" in content.lower() or "logrank" in content.lower():
            method = MethodNode(
                name="Stratified Log-Rank Test",
                description="Hypothesis test for time-to-event endpoints"
            )
            self.graph.add_node(method)

            # Link to PFS endpoint if exists
            for edge in endpoint_edges:
                endpoint = self.graph.get_node(edge.target_id)
                if endpoint and "survival" in endpoint.attributes.get("name", "").lower():
                    # FACTUAL: this endpoint was analyzed with this method
                    self.graph.add_edge(Edge(
                        source_id=endpoint.id,
                        target_id=method.id,
                        edge_type=EdgeType.ANALYZED_WITH,
                        attributes={"provenance": doc_id}
                    ))
                    count += 1

        # Cox model
        if "cox" in content.lower():
            method = MethodNode(
                name="Cox Proportional Hazards Model",
                description="Regression model for time-to-event endpoints"
            )
            self.graph.add_node(method)

            for edge in endpoint_edges:
                endpoint = self.graph.get_node(edge.target_id)
                if endpoint and "survival" in endpoint.attributes.get("name", "").lower():
                    self.graph.add_edge(Edge(
                        source_id=endpoint.id,
                        target_id=method.id,
                        edge_type=EdgeType.ANALYZED_WITH,
                        attributes={"provenance": doc_id}
                    ))
                    count += 1

        # Kaplan-Meier
        if "kaplan-meier" in content.lower() or "kaplan meier" in content.lower():
            method = MethodNode(
                name="Kaplan-Meier Estimation",
                description="Non-parametric survival function estimation"
            )
            self.graph.add_node(method)

            for edge in endpoint_edges:
                endpoint = self.graph.get_node(edge.target_id)
                if endpoint and "survival" in endpoint.attributes.get("name", "").lower():
                    self.graph.add_edge(Edge(
                        source_id=endpoint.id,
                        target_id=method.id,
                        edge_type=EdgeType.ANALYZED_WITH,
                        attributes={"provenance": doc_id}
                    ))
                    count += 1

        return count

    def _extract_populations(self, content: str, trial_id: str, doc_id: str) -> int:
        """Extract analysis population facts."""
        count = 0

        if "intent-to-treat" in content.lower() or "itt" in content.lower():
            pop = PopulationNode(
                name="Intent-to-Treat",
                definition="All randomized subjects"
            )
            self.graph.add_node(pop)

            self.graph.add_edge(Edge(
                source_id=trial_id,
                target_id=pop.id,
                edge_type=EdgeType.HAS_POPULATION,
                attributes={"provenance": doc_id}
            ))
            count += 1

        if "safety population" in content.lower():
            pop = PopulationNode(
                name="Safety Population",
                definition="All subjects who received at least one dose"
            )
            self.graph.add_node(pop)

            self.graph.add_edge(Edge(
                source_id=trial_id,
                target_id=pop.id,
                edge_type=EdgeType.HAS_POPULATION,
                attributes={"provenance": doc_id}
            ))
            count += 1

        if "per-protocol" in content.lower() or "per protocol" in content.lower():
            pop = PopulationNode(
                name="Per-Protocol Population",
                definition="Subjects without major protocol deviations"
            )
            self.graph.add_node(pop)

            self.graph.add_edge(Edge(
                source_id=trial_id,
                target_id=pop.id,
                edge_type=EdgeType.HAS_POPULATION,
                attributes={"provenance": doc_id}
            ))
            count += 1

        return count

    def _extract_stratification(self, content: str, trial_id: str, doc_id: str) -> int:
        """Extract stratification factor facts."""
        count = 0

        # Common stratification factors
        factors = [
            ("ECOG Performance Status", ["0", "1"]),
            ("Geographic Region", ["North America", "Europe", "Rest of World"]),
            ("Prior Lines of Therapy", ["0-1", ">=2"]),
            ("PD-L1 Expression", ["<1%", ">=1%"])
        ]

        for factor_name, categories in factors:
            if factor_name.lower() in content.lower() or factor_name.replace(" ", "").lower() in content.lower():
                strat = StratumNode(factor_name=factor_name, categories=categories)
                self.graph.add_node(strat)

                self.graph.add_edge(Edge(
                    source_id=trial_id,
                    target_id=strat.id,
                    edge_type=EdgeType.STRATIFIED_BY,
                    attributes={"provenance": doc_id}
                ))
                count += 1

        return count

    def add_quote_provenance(self, node_id: str, quote_text: str, page: str, section: str, doc_id: str) -> str:
        """Add exact quote provenance to any node."""
        quote = QuoteNode(text=quote_text, page=page, section=section)
        self.graph.add_node(quote)

        # Link the quote to the node
        self.graph.add_edge(Edge(
            source_id=node_id,
            target_id=quote.id,
            edge_type=EdgeType.QUOTED_AS,
            attributes={"document": doc_id}
        ))

        return quote.id


# =============================================================================
# MAIN: Build graph from ground truth SAPs
# =============================================================================

def build_factual_graph_from_saps(sap_directory: Path) -> FactualKnowledgeGraph:
    """
    Build a factual knowledge graph from SAP files.
    """
    graph = FactualKnowledgeGraph()
    extractor = FactExtractor(graph)

    # Find SAP files
    sap_files = list(sap_directory.glob("*.txt"))

    total_stats = {
        "files_processed": 0,
        "endpoints_extracted": 0,
        "methods_extracted": 0,
        "populations_extracted": 0
    }

    for sap_file in sap_files:
        # Extract NCT ID from filename
        filename = sap_file.name
        nct_id = filename.split("_")[0] if "_" in filename else filename.replace(".txt", "")

        try:
            content = sap_file.read_text(encoding='utf-8', errors='ignore')

            stats = extractor.extract_from_sap(content, nct_id, filename)

            total_stats["files_processed"] += 1
            total_stats["endpoints_extracted"] += stats["endpoints_extracted"]
            total_stats["methods_extracted"] += stats["methods_extracted"]
            total_stats["populations_extracted"] += stats["populations_extracted"]

        except Exception as e:
            print(f"Error processing {filename}: {e}")

    print(f"\nExtraction complete:")
    print(f"  Files processed: {total_stats['files_processed']}")
    print(f"  Endpoints extracted: {total_stats['endpoints_extracted']}")
    print(f"  Methods extracted: {total_stats['methods_extracted']}")
    print(f"  Populations extracted: {total_stats['populations_extracted']}")

    return graph


if __name__ == "__main__":
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # Try to find SAP files
    possible_paths = [
        Path(__file__).parent.parent.parent / "data" / "all_pairs",  # sap_generator/data/all_pairs
        Path(__file__).parent.parent.parent.parent / "ground_truth",
        Path(__file__).parent.parent.parent / "ground_truth",
        Path(__file__).parent.parent / "ground_truth",
    ]

    sap_dir = None
    for path in possible_paths:
        if path.exists():
            sap_dir = path
            break

    if sap_dir:
        print(f"Building factual knowledge graph from SAPs in: {sap_dir}")
        graph = build_factual_graph_from_saps(sap_dir)
    else:
        print("No ground_truth directory found. Creating example graph...")
        graph = FactualKnowledgeGraph()

        # Create example factual data
        trial = TrialNode(
            nct_id="NCT02743221",
            phase="Phase 3",
            indication="NSCLC",
            title="Example Immunotherapy Trial"
        )
        graph.add_node(trial)

        # Add endpoint (fact)
        endpoint = EndpointNode(
            name="Progression-Free Survival",
            endpoint_type="primary",
            definition="Time from randomization to first documented progression per RECIST v1.1 or death"
        )
        graph.add_node(endpoint)

        # FACTUAL edge: this trial has this endpoint
        graph.add_edge(Edge(
            source_id=trial.id,
            target_id=endpoint.id,
            edge_type=EdgeType.HAS_ENDPOINT
        ))

        # Add method (fact)
        method = MethodNode(
            name="Stratified Log-Rank Test",
            description="Hypothesis test for time-to-event comparison"
        )
        graph.add_node(method)

        # FACTUAL edge: this endpoint was analyzed with this method
        graph.add_edge(Edge(
            source_id=endpoint.id,
            target_id=method.id,
            edge_type=EdgeType.ANALYZED_WITH
        ))

    # Export
    graph.export_json(output_dir / "factual_knowledge_graph.json")

    print("\n" + "=" * 80)
    print("FACTUAL KNOWLEDGE GRAPH")
    print("=" * 80)
    print(f"Nodes: {len(graph.nodes)}")
    print(f"Edges: {len(graph.edges)}")
    print("\nNode types:")
    for node_type, count in graph._count_by_type("node").items():
        print(f"  {node_type}: {count}")
    print("\nEdge types (FACTUAL ONLY):")
    for edge_type, count in graph._count_by_type("edge").items():
        print(f"  {edge_type}: {count}")
    print("=" * 80)
    print("\n✅ NO INFERENCE EDGES (should_use, implies, requires, recommends)")
    print("=" * 80)
