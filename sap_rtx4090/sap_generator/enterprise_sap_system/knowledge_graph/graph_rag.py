#!/usr/bin/env python3
"""
Enterprise SAP Generation System - GraphRAG Module
====================================================
TIER 2: Knowledge-Augmented Generation with Biostatistics Knowledge Graph

Features:
- Biostatistics knowledge graph construction
- Multi-hop graph traversal for context retrieval
- Entity linking and path ranking
- Integration with regulatory guidelines (ICH, FDA, CDISC)
"""

import json
import re
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import numpy as np

try:
    import networkx as nx
except ImportError:
    nx = None
    print("WARNING: networkx not installed. Install with: pip install networkx")

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None
    print("WARNING: sentence-transformers not installed. Install with: pip install sentence-transformers")

# Use relative imports for consistent module resolution
try:
    from ..core.config import get_config
    from ..core.schemas import ParsedProtocol, EndpointType
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from core.config import get_config
    from core.schemas import ParsedProtocol, EndpointType


@dataclass
class KnowledgeEntity:
    """Entity in the biostatistics knowledge graph"""
    id: str
    name: str
    entity_type: str
    description: str
    source: str = ""
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeRelationship:
    """Relationship between entities in the knowledge graph"""
    source_id: str
    target_id: str
    relation_type: str
    evidence: str = ""
    confidence: float = 1.0
    source_document: str = ""


@dataclass
class RetrievedPath:
    """A path in the knowledge graph retrieved for context"""
    entities: List[str]
    relationships: List[str]
    evidence: str
    relevance_score: float
    source_document: str = ""


class BiostatisticsKnowledgeGraph:
    """
    Knowledge graph for biostatistics domain.
    Contains entities and relationships for:
    - Endpoint types
    - Statistical methods
    - Regulatory guidelines
    - CDISC standards
    """

    def __init__(self):
        if nx is None:
            raise ImportError("networkx is required for knowledge graph functionality")

        self.graph = nx.DiGraph()
        self.entity_index: Dict[str, KnowledgeEntity] = {}
        self._build_initial_knowledge()

    def _build_initial_knowledge(self):
        """Build the initial knowledge graph with biostatistics domain knowledge"""

        # ========================================
        # ENDPOINT TYPES
        # ========================================
        endpoint_entities = [
            KnowledgeEntity(
                id="OS", name="Overall Survival",
                entity_type="EndpointType",
                description="Time from randomization to death from any cause. Gold standard endpoint in oncology.",
                source="ICH E9"
            ),
            KnowledgeEntity(
                id="PFS", name="Progression-Free Survival",
                entity_type="EndpointType",
                description="Time from randomization to objective tumor progression or death. Commonly used surrogate endpoint.",
                source="FDA Oncology Guidance"
            ),
            KnowledgeEntity(
                id="ORR", name="Objective Response Rate",
                entity_type="EndpointType",
                description="Proportion of patients with complete or partial response per RECIST criteria.",
                source="RECIST 1.1"
            ),
            KnowledgeEntity(
                id="DFS", name="Disease-Free Survival",
                entity_type="EndpointType",
                description="Time from randomization to disease recurrence or death. Used in adjuvant settings.",
                source="FDA Guidance"
            ),
            KnowledgeEntity(
                id="EFS", name="Event-Free Survival",
                entity_type="EndpointType",
                description="Time from randomization to any protocol-defined event. Composite endpoint.",
                source="Clinical Practice"
            ),
            KnowledgeEntity(
                id="SAFETY", name="Safety Endpoint",
                entity_type="EndpointType",
                description="Assessment of adverse events, DLTs, MTD. Primary in Phase 1 studies.",
                source="ICH E6"
            ),
            KnowledgeEntity(
                id="PK", name="Pharmacokinetic Endpoint",
                entity_type="EndpointType",
                description="Drug concentration-time profiles including AUC, Cmax, Tmax, half-life.",
                source="FDA BA/BE Guidance"
            ),
        ]

        # ========================================
        # STATISTICAL METHODS
        # ========================================
        method_entities = [
            KnowledgeEntity(
                id="KAPLAN_MEIER", name="Kaplan-Meier Method",
                entity_type="StatisticalMethod",
                description="Non-parametric estimator of survival function. Handles censored data. Standard for TTE endpoints.",
                source="Kaplan & Meier, JASA 1958"
            ),
            KnowledgeEntity(
                id="COX_PH", name="Cox Proportional Hazards Model",
                entity_type="StatisticalMethod",
                description="Semi-parametric regression for hazard ratios. Allows covariate adjustment. Assumes proportional hazards.",
                source="Cox, JRSSB 1972"
            ),
            KnowledgeEntity(
                id="LOG_RANK", name="Log-Rank Test",
                entity_type="StatisticalMethod",
                description="Non-parametric test for comparing survival curves. Optimal under proportional hazards.",
                source="Mantel, Cancer Chemotherapy Reports 1966"
            ),
            KnowledgeEntity(
                id="CMH", name="Cochran-Mantel-Haenszel Test",
                entity_type="StatisticalMethod",
                description="Stratified analysis of 2x2 tables. Controls for confounding factors.",
                source="Cochran 1954; Mantel & Haenszel 1959"
            ),
            KnowledgeEntity(
                id="CLOPPER_PEARSON", name="Clopper-Pearson Exact CI",
                entity_type="StatisticalMethod",
                description="Exact binomial confidence interval. Conservative coverage. Standard for response rates.",
                source="Clopper & Pearson, Biometrika 1934"
            ),
            KnowledgeEntity(
                id="MMRM", name="Mixed Model Repeated Measures",
                entity_type="StatisticalMethod",
                description="Likelihood-based analysis of longitudinal data. Handles missing data under MAR assumption.",
                source="Mallinckrodt et al., 2008"
            ),
            KnowledgeEntity(
                id="NCA", name="Non-Compartmental Analysis",
                entity_type="StatisticalMethod",
                description="Model-independent PK analysis. Calculates AUC, Cmax from concentration-time data.",
                source="FDA BE Guidance"
            ),
            KnowledgeEntity(
                id="ANOVA", name="Analysis of Variance",
                entity_type="StatisticalMethod",
                description="Comparison of means across groups. Linear model framework.",
                source="Fisher, 1925"
            ),
        ]

        # ========================================
        # EFFECT MEASURES
        # ========================================
        measure_entities = [
            KnowledgeEntity(
                id="HR", name="Hazard Ratio",
                entity_type="EffectMeasure",
                description="Ratio of hazard rates between treatment groups. HR<1 favors treatment. Derived from Cox model.",
                source="Cox Model"
            ),
            KnowledgeEntity(
                id="OR", name="Odds Ratio",
                entity_type="EffectMeasure",
                description="Ratio of odds of event between groups. Used for rare events and case-control studies.",
                source="Epidemiology"
            ),
            KnowledgeEntity(
                id="RR", name="Risk Ratio",
                entity_type="EffectMeasure",
                description="Ratio of event probabilities. More interpretable than OR for common events.",
                source="Epidemiology"
            ),
            KnowledgeEntity(
                id="RD", name="Risk Difference",
                entity_type="EffectMeasure",
                description="Absolute difference in event probabilities. Useful for NNT calculation.",
                source="Epidemiology"
            ),
            KnowledgeEntity(
                id="GMR", name="Geometric Mean Ratio",
                entity_type="EffectMeasure",
                description="Ratio of geometric means. Standard for PK parameters (AUC, Cmax).",
                source="FDA BE Guidance"
            ),
        ]

        # ========================================
        # ANALYSIS POPULATIONS
        # ========================================
        population_entities = [
            KnowledgeEntity(
                id="ITT", name="Intent-to-Treat Population",
                entity_type="AnalysisPopulation",
                description="All randomized patients analyzed as randomized. Preserves randomization. Primary for efficacy.",
                source="ICH E9"
            ),
            KnowledgeEntity(
                id="mITT", name="Modified Intent-to-Treat",
                entity_type="AnalysisPopulation",
                description="ITT with additional requirements (e.g., received treatment, baseline assessment).",
                source="ICH E9"
            ),
            KnowledgeEntity(
                id="PP", name="Per-Protocol Population",
                entity_type="AnalysisPopulation",
                description="Patients without major protocol deviations. Supportive analysis. May overestimate effect.",
                source="ICH E9"
            ),
            KnowledgeEntity(
                id="SAFETY_POP", name="Safety Population",
                entity_type="AnalysisPopulation",
                description="All patients who received at least one dose. Analyzed as treated. Primary for safety.",
                source="ICH E9"
            ),
        ]

        # ========================================
        # REGULATORY GUIDELINES
        # ========================================
        guideline_entities = [
            KnowledgeEntity(
                id="ICH_E9", name="ICH E9 Statistical Principles",
                entity_type="ICHGuideline",
                description="Fundamental principles for clinical trial statistics. Covers design, analysis, reporting.",
                source="ICH"
            ),
            KnowledgeEntity(
                id="ICH_E9R1", name="ICH E9(R1) Estimands Addendum",
                entity_type="ICHGuideline",
                description="Framework for estimands and sensitivity analysis. Defines 5 estimand attributes and ICE strategies.",
                source="ICH 2019"
            ),
            KnowledgeEntity(
                id="ICH_E6", name="ICH E6 GCP",
                entity_type="ICHGuideline",
                description="Good Clinical Practice guidelines. SAP timing and documentation requirements.",
                source="ICH"
            ),
            KnowledgeEntity(
                id="FDA_ONCOLOGY", name="FDA Oncology Endpoints Guidance",
                entity_type="RegulatoryGuidance",
                description="Guidance on endpoints for oncology trials. OS, PFS, ORR considerations.",
                source="FDA 2018"
            ),
        ]

        # ========================================
        # CDISC STANDARDS
        # ========================================
        cdisc_entities = [
            KnowledgeEntity(
                id="ADSL", name="Subject-Level Analysis Dataset",
                entity_type="CDISCDataset",
                description="One record per subject. Contains demographics, treatment, population flags.",
                source="CDISC ADaM IG"
            ),
            KnowledgeEntity(
                id="ADTTE", name="Time-to-Event Analysis Dataset",
                entity_type="CDISCDataset",
                description="Analysis dataset for OS, PFS, DFS. Contains AVAL (time), CNSR (censor), PARAMCD.",
                source="CDISC ADaM IG"
            ),
            KnowledgeEntity(
                id="ADRS", name="Response Analysis Dataset",
                entity_type="CDISCDataset",
                description="Tumor response data. AVALC for response category, AVAL for numeric response indicator.",
                source="CDISC ADaM IG"
            ),
            KnowledgeEntity(
                id="ADAE", name="Adverse Event Analysis Dataset",
                entity_type="CDISCDataset",
                description="Analysis dataset for AEs. Contains AEDECOD (MedDRA PT), AESEV, AEREL.",
                source="CDISC ADaM IG"
            ),
            KnowledgeEntity(
                id="ADPC", name="PK Concentration Dataset",
                entity_type="CDISCDataset",
                description="Analysis dataset for PK concentrations. AVAL for concentration, PCTPT for timepoint.",
                source="CDISC ADaM IG"
            ),
            KnowledgeEntity(
                id="ADPP", name="PK Parameters Dataset",
                entity_type="CDISCDataset",
                description="Analysis dataset for derived PK parameters. PARAMCD for parameter (AUC, CMAX).",
                source="CDISC ADaM IG"
            ),
        ]

        # ========================================
        # ICE STRATEGIES
        # ========================================
        ice_entities = [
            KnowledgeEntity(
                id="ICE_TREATMENT_POLICY", name="Treatment Policy Strategy",
                entity_type="ICEStrategy",
                description="Analyze outcome regardless of ICE occurrence. Reflects real-world treatment effect.",
                source="ICH E9(R1)"
            ),
            KnowledgeEntity(
                id="ICE_COMPOSITE", name="Composite Strategy",
                entity_type="ICEStrategy",
                description="ICE is incorporated into endpoint definition (e.g., death in PFS).",
                source="ICH E9(R1)"
            ),
            KnowledgeEntity(
                id="ICE_HYPOTHETICAL", name="Hypothetical Strategy",
                entity_type="ICEStrategy",
                description="Estimate effect if ICE had not occurred. Requires causal assumptions.",
                source="ICH E9(R1)"
            ),
            KnowledgeEntity(
                id="ICE_PRINCIPAL_STRATUM", name="Principal Stratum Strategy",
                entity_type="ICEStrategy",
                description="Effect in subgroup where ICE would not occur regardless of treatment.",
                source="ICH E9(R1)"
            ),
            KnowledgeEntity(
                id="ICE_WHILE_ON_TREATMENT", name="While on Treatment Strategy",
                entity_type="ICEStrategy",
                description="Outcome assessed only during active treatment period.",
                source="ICH E9(R1)"
            ),
        ]

        # Add all entities to graph
        all_entities = (
            endpoint_entities + method_entities + measure_entities +
            population_entities + guideline_entities + cdisc_entities + ice_entities
        )

        for entity in all_entities:
            self.graph.add_node(
                entity.id,
                name=entity.name,
                type=entity.entity_type,
                description=entity.description,
                source=entity.source
            )
            self.entity_index[entity.id] = entity

        # ========================================
        # RELATIONSHIPS
        # ========================================
        relationships = [
            # Endpoint -> Method relationships
            ("OS", "KAPLAN_MEIER", "analyzed_by", "OS is analyzed using Kaplan-Meier curves"),
            ("OS", "COX_PH", "requires", "OS uses Cox model for HR estimation"),
            ("OS", "LOG_RANK", "tested_by", "OS uses log-rank test for group comparison"),
            ("OS", "HR", "measure_is", "Primary effect measure for OS is hazard ratio"),
            ("OS", "ADTTE", "maps_to_adam", "OS maps to ADTTE dataset with PARAMCD=OS"),

            ("PFS", "KAPLAN_MEIER", "analyzed_by", "PFS is analyzed using Kaplan-Meier curves"),
            ("PFS", "COX_PH", "requires", "PFS uses Cox model for HR estimation"),
            ("PFS", "LOG_RANK", "tested_by", "PFS uses log-rank test for group comparison"),
            ("PFS", "HR", "measure_is", "Primary effect measure for PFS is hazard ratio"),
            ("PFS", "ADTTE", "maps_to_adam", "PFS maps to ADTTE dataset with PARAMCD=PFS"),

            ("DFS", "KAPLAN_MEIER", "analyzed_by", "DFS analyzed using Kaplan-Meier method"),
            ("DFS", "COX_PH", "requires", "DFS uses Cox model"),
            ("DFS", "ADTTE", "maps_to_adam", "DFS maps to ADTTE dataset"),

            ("ORR", "CLOPPER_PEARSON", "analyzed_by", "ORR uses exact binomial CI"),
            ("ORR", "CMH", "tested_by", "ORR uses CMH test for stratified comparison"),
            ("ORR", "RD", "measure_is", "ORR uses risk difference as effect measure"),
            ("ORR", "ADRS", "maps_to_adam", "ORR maps to ADRS dataset with PARAMCD=BOR"),

            ("SAFETY", "ADAE", "maps_to_adam", "Safety endpoints map to ADAE dataset"),
            ("SAFETY", "ITT", "requires_population", "Safety often analyzed in Safety Population"),

            ("PK", "NCA", "analyzed_by", "PK uses non-compartmental analysis"),
            ("PK", "GMR", "measure_is", "PK uses geometric mean ratio for comparison"),
            ("PK", "ADPC", "maps_to_adam", "PK concentrations map to ADPC"),
            ("PK", "ADPP", "maps_to_adam", "PK parameters map to ADPP"),

            # Population relationships
            ("ITT", "ICH_E9", "defined_in", "ITT population defined in ICH E9"),
            ("PP", "ICH_E9", "defined_in", "Per-protocol population defined in ICH E9"),
            ("SAFETY_POP", "ICH_E9", "defined_in", "Safety population defined in ICH E9"),

            # Method -> Guideline relationships
            ("COX_PH", "ICH_E9", "guideline_for", "Cox model recommended per ICH E9"),
            ("KAPLAN_MEIER", "ICH_E9", "guideline_for", "KM method standard per ICH E9"),

            # ICE Strategy relationships
            ("ICE_TREATMENT_POLICY", "ICH_E9R1", "defined_in", "Treatment policy strategy from ICH E9(R1)"),
            ("ICE_COMPOSITE", "ICH_E9R1", "defined_in", "Composite strategy from ICH E9(R1)"),
            ("ICE_HYPOTHETICAL", "ICH_E9R1", "defined_in", "Hypothetical strategy from ICH E9(R1)"),
            ("ICE_PRINCIPAL_STRATUM", "ICH_E9R1", "defined_in", "Principal stratum from ICH E9(R1)"),
            ("ICE_WHILE_ON_TREATMENT", "ICH_E9R1", "defined_in", "While on treatment from ICH E9(R1)"),

            # CDISC relationships
            ("ADTTE", "ADSL", "derived_from", "ADTTE merges with ADSL for demographics"),
            ("ADRS", "ADSL", "derived_from", "ADRS merges with ADSL"),
            ("ADAE", "ADSL", "derived_from", "ADAE merges with ADSL"),
        ]

        for source, target, rel_type, evidence in relationships:
            if source in self.graph and target in self.graph:
                self.graph.add_edge(
                    source, target,
                    type=rel_type,
                    evidence=evidence
                )

    def add_entity(self, entity: KnowledgeEntity):
        """Add a new entity to the knowledge graph"""
        self.graph.add_node(
            entity.id,
            name=entity.name,
            type=entity.entity_type,
            description=entity.description,
            source=entity.source,
            confidence=entity.confidence
        )
        self.entity_index[entity.id] = entity

    def add_relationship(self, relationship: KnowledgeRelationship):
        """Add a new relationship to the knowledge graph"""
        self.graph.add_edge(
            relationship.source_id,
            relationship.target_id,
            type=relationship.relation_type,
            evidence=relationship.evidence,
            confidence=relationship.confidence,
            source=relationship.source_document
        )

    def get_entity(self, entity_id: str) -> Optional[KnowledgeEntity]:
        """Get entity by ID"""
        return self.entity_index.get(entity_id)

    def get_neighbors(self, entity_id: str, max_hops: int = 2) -> Set[str]:
        """Get all nodes within max_hops of an entity"""
        if entity_id not in self.graph:
            return set()
        return set(nx.ego_graph(self.graph, entity_id, radius=max_hops).nodes())

    def get_paths_between(
        self,
        source_id: str,
        target_id: str,
        max_length: int = 3
    ) -> List[List[str]]:
        """Get all paths between two entities"""
        if source_id not in self.graph or target_id not in self.graph:
            return []

        try:
            paths = list(nx.all_simple_paths(
                self.graph, source_id, target_id, cutoff=max_length
            ))
            return paths
        except nx.NetworkXNoPath:
            return []

    def get_subgraph_for_endpoint(self, endpoint_type: str) -> nx.DiGraph:
        """Get relevant subgraph for an endpoint type"""
        if endpoint_type not in self.graph:
            return nx.DiGraph()

        # Get 2-hop neighborhood
        neighbors = self.get_neighbors(endpoint_type, max_hops=2)
        return self.graph.subgraph(neighbors).copy()

    def to_dict(self) -> Dict:
        """Export knowledge graph to dictionary"""
        return {
            "nodes": [
                {
                    "id": node,
                    **self.graph.nodes[node]
                }
                for node in self.graph.nodes()
            ],
            "edges": [
                {
                    "source": u,
                    "target": v,
                    **self.graph.edges[u, v]
                }
                for u, v in self.graph.edges()
            ]
        }


class BiostatisticsGraphRAG:
    """
    GraphRAG implementation for SAP generation.
    Combines knowledge graph traversal with semantic retrieval.
    """

    def __init__(self, embedding_model_name: str = None):
        self.config = get_config()
        self.knowledge_graph = BiostatisticsKnowledgeGraph()

        # Initialize embedding model
        self.embedding_model = None
        if SentenceTransformer is not None:
            model_name = embedding_model_name or self.config.model.embedding_model
            try:
                self.embedding_model = SentenceTransformer(model_name)
            except Exception as e:
                print(f"WARNING: Could not load embedding model: {e}")

        # Pre-compute entity embeddings
        self.entity_embeddings: Dict[str, np.ndarray] = {}
        self._compute_entity_embeddings()

    def _compute_entity_embeddings(self):
        """Pre-compute embeddings for all entities"""
        if self.embedding_model is None:
            return

        for entity_id, entity in self.knowledge_graph.entity_index.items():
            text = f"{entity.name}: {entity.description}"
            try:
                embedding = self.embedding_model.encode(text)
                self.entity_embeddings[entity_id] = embedding
            except Exception as e:
                print(f"Error embedding entity {entity_id}: {e}")

    def retrieve_context(
        self,
        parsed_protocol: ParsedProtocol,
        query: str = "",
        top_k: int = 20
    ) -> str:
        """
        Retrieve relevant context from knowledge graph for SAP generation.

        Args:
            parsed_protocol: Parsed protocol data
            query: Optional additional query
            top_k: Number of paths to retrieve

        Returns:
            Formatted context string for LLM
        """
        # 1. Identify relevant entities from protocol
        relevant_entities = self._identify_relevant_entities(parsed_protocol)

        # 2. If we have embeddings and a query, find similar entities
        if self.embedding_model is not None and query:
            similar_entities = self._find_similar_entities(query, k=5)
            relevant_entities.update(similar_entities)

        # 3. Traverse graph to get connected knowledge
        paths = []
        for entity_id in relevant_entities:
            entity_paths = self._get_entity_paths(entity_id)
            paths.extend(entity_paths)

        # 4. Rank and select top paths
        ranked_paths = self._rank_paths(paths, parsed_protocol)[:top_k]

        # 5. Format as context
        return self._format_context(ranked_paths, parsed_protocol)

    def _identify_relevant_entities(self, protocol: ParsedProtocol) -> Set[str]:
        """Identify relevant entities based on parsed protocol"""
        entities = set()

        # Add endpoint type
        if protocol.primary_estimand:
            endpoint_type = protocol.primary_estimand.variable_type
            if isinstance(endpoint_type, EndpointType):
                entities.add(endpoint_type.value)

        # Add phase-specific entities
        if "1" in str(protocol.phase.value):
            entities.add("SAFETY")
            entities.add("PK")

        # Add common entities
        entities.add("ITT")
        entities.add("ICH_E9R1")

        return entities

    def _find_similar_entities(self, query: str, k: int = 5) -> Set[str]:
        """Find entities similar to query using embeddings"""
        if not self.entity_embeddings:
            return set()

        query_embedding = self.embedding_model.encode(query)

        # Calculate similarities
        similarities = {}
        for entity_id, entity_embedding in self.entity_embeddings.items():
            similarity = np.dot(query_embedding, entity_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(entity_embedding)
            )
            similarities[entity_id] = similarity

        # Get top-k
        sorted_entities = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
        return set([e[0] for e in sorted_entities[:k]])

    def _get_entity_paths(self, entity_id: str) -> List[RetrievedPath]:
        """Get paths from an entity through the knowledge graph"""
        paths = []

        if entity_id not in self.knowledge_graph.graph:
            return paths

        # Get 2-hop subgraph
        subgraph = self.knowledge_graph.get_subgraph_for_endpoint(entity_id)

        # Extract meaningful paths
        for neighbor in subgraph.neighbors(entity_id):
            edge_data = subgraph.edges[entity_id, neighbor]
            entity_data = subgraph.nodes[entity_id]
            neighbor_data = subgraph.nodes[neighbor]

            path = RetrievedPath(
                entities=[entity_id, neighbor],
                relationships=[edge_data.get('type', 'related_to')],
                evidence=edge_data.get('evidence', ''),
                relevance_score=1.0,
                source_document=entity_data.get('source', '')
            )
            paths.append(path)

            # Add 2-hop paths
            for second_neighbor in subgraph.neighbors(neighbor):
                if second_neighbor != entity_id:
                    second_edge = subgraph.edges.get((neighbor, second_neighbor), {})
                    path_2hop = RetrievedPath(
                        entities=[entity_id, neighbor, second_neighbor],
                        relationships=[
                            edge_data.get('type', 'related_to'),
                            second_edge.get('type', 'related_to')
                        ],
                        evidence=f"{edge_data.get('evidence', '')}; {second_edge.get('evidence', '')}",
                        relevance_score=0.8,
                        source_document=entity_data.get('source', '')
                    )
                    paths.append(path_2hop)

        return paths

    def _rank_paths(
        self,
        paths: List[RetrievedPath],
        protocol: ParsedProtocol
    ) -> List[RetrievedPath]:
        """Rank paths by relevance to protocol"""
        # Simple scoring based on entity types and protocol characteristics
        for path in paths:
            score = path.relevance_score

            # Boost paths containing endpoint-relevant entities
            if protocol.primary_estimand:
                endpoint_type = protocol.primary_estimand.variable_type
                if isinstance(endpoint_type, EndpointType):
                    if endpoint_type.value in path.entities:
                        score *= 1.5

            # Boost paths with regulatory guidance
            if any('ICH' in str(e) or 'FDA' in str(e) for e in path.entities):
                score *= 1.2

            # Boost paths with CDISC mappings
            if any('AD' in str(e) for e in path.entities):
                score *= 1.1

            path.relevance_score = score

        return sorted(paths, key=lambda p: p.relevance_score, reverse=True)

    def _format_context(
        self,
        paths: List[RetrievedPath],
        protocol: ParsedProtocol
    ) -> str:
        """Format retrieved paths as context for LLM"""
        context_parts = [
            "## Relevant Biostatistics Knowledge\n",
            "The following knowledge from regulatory guidelines and standards is relevant:\n"
        ]

        # Group by relationship type
        grouped: Dict[str, List[RetrievedPath]] = defaultdict(list)
        for path in paths:
            if path.relationships:
                grouped[path.relationships[0]].append(path)

        for rel_type, rel_paths in grouped.items():
            context_parts.append(f"\n### {rel_type.replace('_', ' ').title()}:\n")
            for path in rel_paths[:5]:  # Limit per category
                # Get entity descriptions
                entity_descs = []
                for entity_id in path.entities:
                    entity = self.knowledge_graph.get_entity(entity_id)
                    if entity:
                        entity_descs.append(f"**{entity.name}**: {entity.description}")

                if entity_descs:
                    context_parts.append("- " + " → ".join(entity_descs[:2]))
                    if path.evidence:
                        context_parts.append(f"  - Evidence: {path.evidence}")
                    context_parts.append("")

        # Add endpoint-specific guidance
        if protocol.primary_estimand:
            endpoint_type = protocol.primary_estimand.variable_type
            if isinstance(endpoint_type, EndpointType):
                context_parts.append(f"\n### Specific Guidance for {endpoint_type.value} Endpoint:\n")
                entity = self.knowledge_graph.get_entity(endpoint_type.value)
                if entity:
                    context_parts.append(f"- {entity.description}")
                    context_parts.append(f"- Source: {entity.source}")

        return "\n".join(context_parts)

    def get_methods_for_endpoint(self, endpoint_type: EndpointType) -> List[str]:
        """Get recommended statistical methods for an endpoint type"""
        methods = []
        entity_id = endpoint_type.value

        if entity_id in self.knowledge_graph.graph:
            for neighbor in self.knowledge_graph.graph.neighbors(entity_id):
                edge_data = self.knowledge_graph.graph.edges[entity_id, neighbor]
                if edge_data.get('type') in ['analyzed_by', 'requires', 'tested_by']:
                    entity = self.knowledge_graph.get_entity(neighbor)
                    if entity and entity.entity_type == 'StatisticalMethod':
                        methods.append(entity.name)

        return methods

    def get_adam_mapping(self, endpoint_type: EndpointType) -> Dict[str, str]:
        """Get ADaM dataset mapping for an endpoint type"""
        mapping = {}
        entity_id = endpoint_type.value

        if entity_id in self.knowledge_graph.graph:
            for neighbor in self.knowledge_graph.graph.neighbors(entity_id):
                edge_data = self.knowledge_graph.graph.edges[entity_id, neighbor]
                if edge_data.get('type') == 'maps_to_adam':
                    entity = self.knowledge_graph.get_entity(neighbor)
                    if entity:
                        mapping['dataset'] = entity.id
                        mapping['description'] = entity.description
                        mapping['evidence'] = edge_data.get('evidence', '')

        return mapping


# Factory function
def create_graph_rag() -> BiostatisticsGraphRAG:
    """Create a GraphRAG instance"""
    return BiostatisticsGraphRAG()
