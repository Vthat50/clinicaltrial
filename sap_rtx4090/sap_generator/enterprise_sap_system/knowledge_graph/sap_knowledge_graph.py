"""
SAP Knowledge Graph Builder
============================

Creates a comprehensive knowledge graph mapping:
- Local sap_data folder (354 SAP examples)
- Enterprise modules (Phases 5-8)
- Response criteria, safety analyses, statistical methods
- Coverage analysis and relationships

Outputs:
1. JSON knowledge graph
2. GraphML for visualization
3. Coverage report
4. Module-to-data mapping
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class DataSource:
    """A source of SAP data (PDF, text file, etc.)"""
    source_id: str
    source_type: str  # "specialized_pdf", "general_sap", "ground_truth"
    file_path: str
    category: str  # "response_criteria", "safety", "statistical_methods", etc.
    subcategory: str = ""
    nct_id: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class EnterpriseModule:
    """An enterprise module created"""
    module_id: str
    module_name: str
    file_path: str
    phase: str  # "Phase 5", "Phase 6", "Phase 8"
    category: str
    coverage_status: str  # "full", "partial", "none"
    data_sources: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)


@dataclass
class KnowledgeNode:
    """A node in the knowledge graph"""
    node_id: str
    node_type: str  # "module", "data_source", "category", "concept"
    label: str
    properties: Dict = field(default_factory=dict)


@dataclass
class KnowledgeEdge:
    """An edge in the knowledge graph"""
    source_id: str
    target_id: str
    relationship: str  # "covers", "requires", "implements", "contains"
    weight: float = 1.0
    properties: Dict = field(default_factory=dict)


class SAPKnowledgeGraph:
    """
    Comprehensive knowledge graph of SAP data and modules.
    """

    def __init__(self, sap_data_path: Path = None):
        """
        Initialize knowledge graph builder.

        Args:
            sap_data_path: Path to sap_data folder
        """
        if sap_data_path is None:
            sap_data_path = Path("/mnt/c/Users/vijay/Desktop/sap_data")

        self.sap_data_path = sap_data_path
        self.specialized_criteria_path = sap_data_path / "specialized_criteria"
        self.oncology_saps_path = sap_data_path / "oncology_trials" / "saps"
        self.ground_truth_path = sap_data_path / "ground_truth"

        # Graph components
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.edges: List[KnowledgeEdge] = []
        self.data_sources: Dict[str, DataSource] = {}
        self.modules: Dict[str, EnterpriseModule] = {}

        # Statistics
        self.stats = {
            "total_pdfs": 0,
            "total_ground_truth": 0,
            "total_modules": 0,
            "coverage_full": 0,
            "coverage_partial": 0,
            "coverage_none": 0
        }

    def build_graph(self):
        """Build the complete knowledge graph"""
        logger.info("Building SAP knowledge graph...")

        # 1. Scan local data sources
        self._scan_specialized_criteria()
        self._scan_oncology_saps()
        self._scan_ground_truth()

        # 2. Define enterprise modules
        self._define_enterprise_modules()

        # 3. Create category nodes
        self._create_category_nodes()

        # 4. Map modules to data sources
        self._map_modules_to_data()

        # 5. Create relationships
        self._create_relationships()

        # 6. Calculate statistics
        self._calculate_statistics()

        logger.info(f"Knowledge graph built: {len(self.nodes)} nodes, {len(self.edges)} edges")

    def _scan_specialized_criteria(self):
        """Scan specialized_criteria folder"""
        if not self.specialized_criteria_path.exists():
            logger.warning(f"Specialized criteria path not found: {self.specialized_criteria_path}")
            return

        # Mapping of folder names to categories
        category_mapping = {
            "brain_RANO": ("response_criteria", "RANO"),
            "lymphoma_Lugano": ("response_criteria", "Cheson/Lugano"),
            "melanoma_irRECIST": ("response_criteria", "irRC"),
            "iRECIST": ("response_criteria", "iRECIST"),
            "RECIST_full": ("response_criteria", "RECIST 1.1"),
            "HCC_mRECIST": ("response_criteria", "mRECIST"),
            "leukemia_IWG": ("response_criteria", "IWG"),
            "myeloma": ("response_criteria", "Myeloma"),
            "ovarian_GCIG": ("response_criteria", "GCIG"),
            "prostate_PCWG": ("response_criteria", "PCWG"),
            "OS_PFS_censoring": ("statistical_methods", "Survival Analysis"),
            "DOR_TTR": ("statistical_methods", "Binary Endpoints"),
            "GIST": ("tumor_specific", "GIST"),
            "RCC_kidney": ("tumor_specific", "Renal Cell Carcinoma"),
            "breast_HER2_pCR": ("tumor_specific", "Breast Cancer"),
            "colorectal_CRC": ("tumor_specific", "Colorectal Cancer"),
            "head_neck_HNSCC": ("tumor_specific", "Head and Neck Cancer"),
            "lung_NSCLC": ("tumor_specific", "Lung Cancer"),
            "pancreatic_PDAC": ("tumor_specific", "Pancreatic Cancer"),
            "NET_carcinoid": ("tumor_specific", "Neuroendocrine Tumors"),
            "mesothelioma": ("tumor_specific", "Mesothelioma"),
            "sarcoma": ("tumor_specific", "Sarcoma"),
            "thymoma": ("tumor_specific", "Thymoma"),
            "pediatric": ("tumor_specific", "Pediatric")
        }

        for folder in self.specialized_criteria_path.iterdir():
            if not folder.is_dir():
                continue

            folder_name = folder.name
            category, subcategory = category_mapping.get(folder_name, ("other", folder_name))

            # Count PDFs
            pdfs = list(folder.glob("*.pdf"))
            for pdf in pdfs:
                # Extract NCT ID from filename
                nct_id = "UNKNOWN"
                if "NCT" in pdf.name:
                    import re
                    match = re.search(r'NCT\d{8}', pdf.name)
                    if match:
                        nct_id = match.group(0)

                source_id = f"specialized_{folder_name}_{pdf.stem}"
                self.data_sources[source_id] = DataSource(
                    source_id=source_id,
                    source_type="specialized_pdf",
                    file_path=str(pdf),
                    category=category,
                    subcategory=subcategory,
                    nct_id=nct_id,
                    metadata={"folder": folder_name, "pdf_count": len(pdfs)}
                )

                # Create node
                self.nodes[source_id] = KnowledgeNode(
                    node_id=source_id,
                    node_type="data_source",
                    label=f"{subcategory}: {nct_id}",
                    properties={
                        "type": "specialized_pdf",
                        "category": category,
                        "subcategory": subcategory,
                        "nct_id": nct_id
                    }
                )

            self.stats["total_pdfs"] += len(pdfs)

    def _scan_oncology_saps(self):
        """Scan general oncology SAPs"""
        if not self.oncology_saps_path.exists():
            return

        pdfs = list(self.oncology_saps_path.glob("*.pdf"))
        for pdf in pdfs:
            # Extract NCT ID
            nct_id = "UNKNOWN"
            if "NCT" in pdf.name:
                import re
                match = re.search(r'NCT\d{8}', pdf.name)
                if match:
                    nct_id = match.group(0)

            source_id = f"oncology_sap_{pdf.stem}"
            self.data_sources[source_id] = DataSource(
                source_id=source_id,
                source_type="general_sap",
                file_path=str(pdf),
                category="comprehensive",
                subcategory="oncology",
                nct_id=nct_id
            )

            self.nodes[source_id] = KnowledgeNode(
                node_id=source_id,
                node_type="data_source",
                label=f"General SAP: {nct_id}",
                properties={
                    "type": "general_sap",
                    "category": "comprehensive",
                    "nct_id": nct_id
                }
            )

        self.stats["total_pdfs"] += len(pdfs)

    def _scan_ground_truth(self):
        """Scan ground truth SAP text files"""
        if not self.ground_truth_path.exists():
            return

        sap_files = list(self.ground_truth_path.glob("*_sap.txt"))
        for sap_file in sap_files:
            # Extract NCT ID
            nct_id = sap_file.stem.replace("_sap", "")

            source_id = f"ground_truth_{nct_id}"
            self.data_sources[source_id] = DataSource(
                source_id=source_id,
                source_type="ground_truth",
                file_path=str(sap_file),
                category="comprehensive",
                subcategory="ground_truth",
                nct_id=nct_id
            )

            self.nodes[source_id] = KnowledgeNode(
                node_id=source_id,
                node_type="data_source",
                label=f"Ground Truth: {nct_id}",
                properties={
                    "type": "ground_truth",
                    "category": "comprehensive",
                    "nct_id": nct_id
                }
            )

        self.stats["total_ground_truth"] = len(sap_files)

    def _define_enterprise_modules(self):
        """Define all enterprise modules created"""
        modules_definition = [
            # Phase 6: Response Criteria
            {
                "module_id": "irrc",
                "module_name": "Immune-Related Response Criteria (irRC)",
                "file_path": "response_criteria/irrc.py",
                "phase": "Phase 6",
                "category": "response_criteria",
                "capabilities": ["Bidimensional measurements", "Pseudoprogression handling", "New lesion integration"]
            },
            {
                "module_id": "rano",
                "module_name": "Response Assessment in Neuro-Oncology (RANO)",
                "file_path": "response_criteria/rano.py",
                "phase": "Phase 6",
                "category": "response_criteria",
                "capabilities": ["Brain tumor assessment", "T1+Gad and T2/FLAIR", "Corticosteroid tracking", "Pseudoprogression"]
            },
            {
                "module_id": "cheson",
                "module_name": "Cheson/Lugano Criteria for Lymphoma",
                "file_path": "response_criteria/cheson.py",
                "phase": "Phase 6",
                "category": "response_criteria",
                "capabilities": ["PET integration", "Deauville 5-point scale", "Bone marrow assessment", "B symptoms"]
            },
            {
                "module_id": "iwg_leukemia",
                "module_name": "IWG Criteria for Acute Leukemia (AML/ALL)",
                "file_path": "response_criteria/iwg_leukemia.py",
                "phase": "Phase 6",
                "category": "response_criteria",
                "capabilities": ["Bone marrow blast assessment", "CR/CRi/MLFS categories", "MRD integration", "Relapse detection"]
            },
            {
                "module_id": "mrecist",
                "module_name": "Modified RECIST (mRECIST) for HCC",
                "file_path": "response_criteria/mrecist.py",
                "phase": "Phase 6",
                "category": "response_criteria",
                "capabilities": ["Viable tumor measurement", "Arterial enhancement", "Post-TACE/ablation response", "HCC-specific imaging"]
            },

            # Phase 5: Safety Analysis
            {
                "module_id": "adverse_events",
                "module_name": "Adverse Event Analysis",
                "file_path": "safety/adverse_event_analysis.py",
                "phase": "Phase 5",
                "category": "safety_analysis",
                "capabilities": ["TEAE analysis", "SAE analysis", "CTCAE grading", "AESI tracking", "DLT analysis"]
            },
            {
                "module_id": "laboratory",
                "module_name": "Laboratory Safety Analysis",
                "file_path": "safety/laboratory_analysis.py",
                "phase": "Phase 5",
                "category": "safety_analysis",
                "capabilities": ["Shift tables", "CTCAE lab grading", "Hy's Law analysis", "PCSA detection"]
            },
            {
                "module_id": "safety_integration",
                "module_name": "Comprehensive Safety Integration",
                "file_path": "safety/safety_integration.py",
                "phase": "Phase 7",
                "category": "safety_analysis",
                "capabilities": ["Vital signs", "ECG QTc analysis", "Exposure analysis", "Integrated safety assessment"]
            },

            # Phase 8: Statistical Methods (14 modules)
            {
                "module_id": "survival_analysis",
                "module_name": "Survival Analysis",
                "file_path": "statistical_methods/survival_analysis.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["Kaplan-Meier", "Log-rank test", "Cox proportional hazards", "RMST"]
            },
            {
                "module_id": "subgroup_analysis",
                "module_name": "Subgroup Analysis",
                "file_path": "statistical_methods/subgroup_analysis.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["Forest plots", "Interaction testing", "Consistency assessment"]
            },
            {
                "module_id": "missing_data",
                "module_name": "Missing Data Analysis",
                "file_path": "statistical_methods/missing_data.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["Multiple imputation", "MAR/MNAR handling", "Tipping point analysis"]
            },
            {
                "module_id": "multiplicity",
                "module_name": "Multiplicity Adjustment",
                "file_path": "statistical_methods/multiplicity.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["Bonferroni", "Holm", "Fixed-sequence", "Graphical approaches"]
            },
            {
                "module_id": "interim_analysis",
                "module_name": "Interim Analysis",
                "file_path": "statistical_methods/interim_analysis.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["Group sequential", "Alpha spending", "Conditional power", "DMC reporting"]
            },
            {
                "module_id": "binary_endpoints",
                "module_name": "Binary Endpoints Analysis",
                "file_path": "statistical_methods/binary_endpoints.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["ORR analysis", "CMH test", "Exact CI", "Responder analysis"]
            },
            {
                "module_id": "estimands",
                "module_name": "Estimands Framework (ICH E9(R1))",
                "file_path": "statistical_methods/estimands.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["5 ICE strategies", "Treatment policy", "Composite", "Hypothetical"]
            },
            {
                "module_id": "sample_size",
                "module_name": "Sample Size Calculation",
                "file_path": "statistical_methods/sample_size.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["Schoenfeld formula", "Power analysis", "Non-inferiority", "Event calculations"]
            },
            {
                "module_id": "covariate_adjustment",
                "module_name": "Covariate Adjustment",
                "file_path": "statistical_methods/covariate_adjustment.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["ANCOVA", "Stratified analysis", "Propensity scores"]
            },
            {
                "module_id": "repeated_measures",
                "module_name": "Repeated Measures Analysis",
                "file_path": "statistical_methods/repeated_measures.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["MMRM", "GEE", "Unstructured covariance", "Kenward-Roger DF"]
            },
            {
                "module_id": "nonparametric",
                "module_name": "Non-parametric Methods",
                "file_path": "statistical_methods/nonparametric.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["Wilcoxon", "Kruskal-Wallis", "Van Elteren", "Bootstrap CI"]
            },
            {
                "module_id": "dose_response",
                "module_name": "Dose-Response Analysis (MCP-Mod)",
                "file_path": "statistical_methods/dose_response.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["MCP-Mod", "Candidate models", "Optimal contrasts", "Target dose"]
            },
            {
                "module_id": "bayesian",
                "module_name": "Bayesian Methods",
                "file_path": "statistical_methods/bayesian.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["MCMC", "Posterior probability", "Predictive probability", "Adaptive designs"]
            },
            {
                "module_id": "pro_qol",
                "module_name": "Patient-Reported Outcomes / QoL",
                "file_path": "statistical_methods/pro_qol.py",
                "phase": "Phase 8",
                "category": "statistical_methods",
                "capabilities": ["EORTC QLQ-C30", "TTD analysis", "MID", "Responder analysis"]
            },
        ]

        for module_def in modules_definition:
            module = EnterpriseModule(
                module_id=module_def["module_id"],
                module_name=module_def["module_name"],
                file_path=module_def["file_path"],
                phase=module_def["phase"],
                category=module_def["category"],
                coverage_status="unknown",  # Will be determined later
                capabilities=module_def["capabilities"]
            )

            self.modules[module.module_id] = module

            # Create node
            self.nodes[module.module_id] = KnowledgeNode(
                node_id=module.module_id,
                node_type="module",
                label=module.module_name,
                properties={
                    "phase": module.phase,
                    "category": module.category,
                    "file_path": module.file_path,
                    "capabilities": module.capabilities
                }
            )

        self.stats["total_modules"] = len(self.modules)

    def _create_category_nodes(self):
        """Create high-level category nodes"""
        categories = [
            ("response_criteria", "Response Criteria", "Assessment of tumor response"),
            ("safety_analysis", "Safety Analysis", "Adverse events, labs, vitals, ECG"),
            ("statistical_methods", "Statistical Methods", "Analysis techniques and methods"),
            ("tumor_specific", "Tumor-Specific", "Disease-specific considerations"),
            ("comprehensive", "Comprehensive SAPs", "Complete SAP documents")
        ]

        for cat_id, label, description in categories:
            self.nodes[f"cat_{cat_id}"] = KnowledgeNode(
                node_id=f"cat_{cat_id}",
                node_type="category",
                label=label,
                properties={"description": description}
            )

    def _map_modules_to_data(self):
        """Map enterprise modules to data sources based on coverage"""
        # Define mapping rules
        mappings = {
            # Response Criteria
            "irrc": ["melanoma_irRECIST"],
            "rano": ["brain_RANO"],
            "cheson": ["lymphoma_Lugano"],
            "iwg_leukemia": ["leukemia_IWG", "comprehensive"],
            "mrecist": ["HCC_mRECIST", "comprehensive"],

            # Safety Analysis (covered by all SAPs)
            "adverse_events": ["comprehensive"],
            "laboratory": ["comprehensive"],
            "safety_integration": ["comprehensive"],

            # Statistical Methods
            "survival_analysis": ["OS_PFS_censoring", "comprehensive"],
            "binary_endpoints": ["DOR_TTR", "comprehensive"],
            "sample_size": ["comprehensive"],
            "subgroup_analysis": ["comprehensive"],
            "missing_data": ["comprehensive"],
            "multiplicity": ["comprehensive"],
            "interim_analysis": ["comprehensive"],
            "estimands": ["comprehensive"],  # Partial - newer SAPs
            "covariate_adjustment": ["comprehensive"],
            "repeated_measures": ["comprehensive"],
            "nonparametric": ["comprehensive"],
            "dose_response": ["GIST", "sarcoma"],  # Partial
            "bayesian": ["comprehensive"],  # Partial
            "pro_qol": ["comprehensive"],
        }

        for module_id, data_categories in mappings.items():
            if module_id not in self.modules:
                continue

            module = self.modules[module_id]
            matched_sources = []

            for category in data_categories:
                # Find matching data sources
                for source_id, source in self.data_sources.items():
                    if category == "comprehensive":
                        # All comprehensive SAPs match
                        if source.source_type in ["general_sap", "ground_truth"]:
                            matched_sources.append(source_id)
                    else:
                        # Match by subcategory folder name
                        if category in source.metadata.get("folder", ""):
                            matched_sources.append(source_id)

            module.data_sources = list(set(matched_sources))

            # Determine coverage status
            if len(matched_sources) >= 5:
                module.coverage_status = "full"
                self.stats["coverage_full"] += 1
            elif len(matched_sources) > 0:
                module.coverage_status = "partial"
                self.stats["coverage_partial"] += 1
            else:
                module.coverage_status = "none"
                self.stats["coverage_none"] += 1

            # Update node properties
            self.nodes[module_id].properties["coverage"] = module.coverage_status
            self.nodes[module_id].properties["data_sources_count"] = len(matched_sources)

    def _create_relationships(self):
        """Create edges between nodes"""
        # 1. Module -> Data Source (covers)
        for module_id, module in self.modules.items():
            for source_id in module.data_sources:
                self.edges.append(KnowledgeEdge(
                    source_id=module_id,
                    target_id=source_id,
                    relationship="covered_by",
                    weight=1.0
                ))

        # 2. Module -> Category (belongs_to)
        for module_id, module in self.modules.items():
            cat_id = f"cat_{module.category}"
            if cat_id in self.nodes:
                self.edges.append(KnowledgeEdge(
                    source_id=module_id,
                    target_id=cat_id,
                    relationship="belongs_to",
                    weight=1.0
                ))

        # 3. Data Source -> Category (belongs_to)
        for source_id, source in self.data_sources.items():
            cat_id = f"cat_{source.category}"
            if cat_id in self.nodes:
                self.edges.append(KnowledgeEdge(
                    source_id=source_id,
                    target_id=cat_id,
                    relationship="belongs_to",
                    weight=1.0
                ))

    def _calculate_statistics(self):
        """Calculate final statistics"""
        # Already populated during scanning
        pass

    def export_json(self, output_path: Path):
        """Export knowledge graph as JSON"""
        graph_data = {
            "metadata": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "total_modules": self.stats["total_modules"],
                "total_pdfs": self.stats["total_pdfs"],
                "total_ground_truth": self.stats["total_ground_truth"],
                "coverage_full": self.stats["coverage_full"],
                "coverage_partial": self.stats["coverage_partial"],
                "coverage_none": self.stats["coverage_none"]
            },
            "nodes": [
                {
                    "id": node.node_id,
                    "type": node.node_type,
                    "label": node.label,
                    "properties": node.properties
                }
                for node in self.nodes.values()
            ],
            "edges": [
                {
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "relationship": edge.relationship,
                    "weight": edge.weight,
                    "properties": edge.properties
                }
                for edge in self.edges
            ],
            "modules": [
                {
                    "module_id": mod.module_id,
                    "module_name": mod.module_name,
                    "phase": mod.phase,
                    "category": mod.category,
                    "coverage": mod.coverage_status,
                    "data_sources_count": len(mod.data_sources),
                    "capabilities": mod.capabilities
                }
                for mod in self.modules.values()
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(graph_data, f, indent=2)

        logger.info(f"Knowledge graph exported to {output_path}")

    def export_graphml(self, output_path: Path):
        """Export as GraphML for visualization in tools like Gephi, yEd"""
        try:
            import xml.etree.ElementTree as ET

            graphml = ET.Element("graphml", xmlns="http://graphml.graphdrawing.org/xmlns")

            # Define keys
            keys = [
                ("type", "node", "string"),
                ("label", "node", "string"),
                ("category", "node", "string"),
                ("coverage", "node", "string"),
                ("relationship", "edge", "string")
            ]

            for key_id, key_for, key_type in keys:
                ET.SubElement(graphml, "key", {
                    "id": key_id,
                    "for": key_for,
                    "attr.name": key_id,
                    "attr.type": key_type
                })

            # Create graph
            graph = ET.SubElement(graphml, "graph", {
                "id": "SAP_Knowledge_Graph",
                "edgedefault": "directed"
            })

            # Add nodes
            for node in self.nodes.values():
                node_elem = ET.SubElement(graph, "node", {"id": node.node_id})

                data_type = ET.SubElement(node_elem, "data", {"key": "type"})
                data_type.text = node.node_type

                data_label = ET.SubElement(node_elem, "data", {"key": "label"})
                data_label.text = node.label

                if "category" in node.properties:
                    data_cat = ET.SubElement(node_elem, "data", {"key": "category"})
                    data_cat.text = node.properties["category"]

                if "coverage" in node.properties:
                    data_cov = ET.SubElement(node_elem, "data", {"key": "coverage"})
                    data_cov.text = node.properties["coverage"]

            # Add edges
            for i, edge in enumerate(self.edges):
                edge_elem = ET.SubElement(graph, "edge", {
                    "id": f"e{i}",
                    "source": edge.source_id,
                    "target": edge.target_id
                })

                data_rel = ET.SubElement(edge_elem, "data", {"key": "relationship"})
                data_rel.text = edge.relationship

            # Write to file
            tree = ET.ElementTree(graphml)
            tree.write(output_path, encoding="utf-8", xml_declaration=True)

            logger.info(f"GraphML exported to {output_path}")

        except Exception as e:
            logger.error(f"Failed to export GraphML: {e}")

    def generate_coverage_report(self, output_path: Path):
        """Generate detailed coverage report"""
        report_lines = [
            "=" * 80,
            "SAP KNOWLEDGE GRAPH - COVERAGE REPORT",
            "=" * 80,
            "",
            "SUMMARY STATISTICS",
            "-" * 80,
            f"Total Data Sources: {self.stats['total_pdfs'] + self.stats['total_ground_truth']}",
            f"  - Specialized PDFs: {self.stats['total_pdfs']}",
            f"  - Ground Truth SAPs: {self.stats['total_ground_truth']}",
            "",
            f"Total Enterprise Modules: {self.stats['total_modules']}",
            f"  - Full Coverage: {self.stats['coverage_full']}",
            f"  - Partial Coverage: {self.stats['coverage_partial']}",
            f"  - No Coverage: {self.stats['coverage_none']}",
            "",
            "=" * 80,
            "MODULE COVERAGE DETAILS",
            "=" * 80,
            ""
        ]

        # Group by phase
        phases = {}
        for module in self.modules.values():
            if module.phase not in phases:
                phases[module.phase] = []
            phases[module.phase].append(module)

        for phase in sorted(phases.keys()):
            report_lines.append(f"\n{phase}")
            report_lines.append("-" * 80)

            for module in sorted(phases[phase], key=lambda m: m.module_name):
                status_icon = {
                    "full": "✅",
                    "partial": "⚠️",
                    "none": "❌"
                }.get(module.coverage_status, "?")

                report_lines.append(f"{status_icon} {module.module_name}")
                report_lines.append(f"   Coverage: {module.coverage_status.upper()}")
                report_lines.append(f"   Data Sources: {len(module.data_sources)}")
                report_lines.append(f"   Capabilities: {', '.join(module.capabilities[:3])}...")
                report_lines.append("")

        # Data source breakdown
        report_lines.extend([
            "",
            "=" * 80,
            "DATA SOURCE BREAKDOWN",
            "=" * 80,
            ""
        ])

        # Count by category
        category_counts = defaultdict(int)
        for source in self.data_sources.values():
            category_counts[source.category] += 1

        for category, count in sorted(category_counts.items()):
            report_lines.append(f"{category.replace('_', ' ').title()}: {count} sources")

        report_text = "\n".join(report_lines)

        with open(output_path, 'w') as f:
            f.write(report_text)

        logger.info(f"Coverage report generated: {output_path}")
        return report_text


def main():
    """Main function to build and export knowledge graph"""
    # Initialize
    kg = SAPKnowledgeGraph()

    # Build graph
    kg.build_graph()

    # Export in multiple formats
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    kg.export_json(output_dir / "sap_knowledge_graph.json")
    kg.export_graphml(output_dir / "sap_knowledge_graph.graphml")
    report = kg.generate_coverage_report(output_dir / "coverage_report.txt")

    print(report)

    print(f"\n{'='*80}")
    print("Knowledge graph built successfully!")
    print(f"{'='*80}")
    print(f"Total nodes: {len(kg.nodes)}")
    print(f"Total edges: {len(kg.edges)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
