"""
Knowledge Base Tools for SAP Generation
========================================

Provides explicit tool-based access to knowledge base content.
Claude calls these tools when it needs specific standards/templates.

This approach ensures:
1. Clear provenance - every piece of knowledge has a source
2. No contamination - protocol facts stay separate from KB templates
3. Explicit retrieval - Claude asks for what it needs
4. Auditable - log of all knowledge retrieved

Usage:
    from kb_tools import KnowledgeBaseTools

    kb = KnowledgeBaseTools()
    result = kb.get_statistical_method("cox_proportional_hazards")
    result = kb.get_table_template("14.1.1")
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


# =============================================================================
# TRIAL PRECEDENT KNOWLEDGE GRAPH
# =============================================================================

class TrialPrecedentKG:
    """
    Queries the factual knowledge graph (354 trials) for similar trial precedents.

    This provides real-world examples of how similar trials handled:
    - Censoring rules for specific endpoints
    - Multiplicity adjustments for co-primary endpoints
    - Interim analysis designs
    - Statistical methods for specific indications
    """

    def __init__(self):
        self.nodes: Dict[str, Dict] = {}
        self.edges: List[Dict] = []
        self.trials: Dict[str, Dict] = {}  # trial_id -> full trial data with connections
        self._loaded = False

    def _load_kg(self):
        """Load the factual knowledge graph."""
        if self._loaded:
            return

        kg_path = Path(__file__).parent / "output" / "factual_kg_merged.json"
        if not kg_path.exists():
            print(f"[TrialPrecedentKG] Warning: {kg_path} not found")
            self._loaded = True
            return

        with open(kg_path) as f:
            data = json.load(f)

        # Index nodes by ID
        for node in data.get("nodes", []):
            self.nodes[node["id"]] = node

        self.edges = data.get("edges", [])

        # Build trial index with all connections
        self._build_trial_index()
        self._loaded = True
        print(f"[TrialPrecedentKG] Loaded {len(self.trials)} trials with precedent data")

    def _build_trial_index(self):
        """Build an index of trials with their connected components."""
        # Find all trial nodes
        for node_id, node in self.nodes.items():
            if node.get("type") == "trial":
                attrs = node.get("attributes", {})
                # Only include trials with rich metadata (from PDF extraction)
                if attrs.get("phase") or attrs.get("indication"):
                    trial_data = {
                        "trial_id": attrs.get("trial_id", node_id),
                        "phase": attrs.get("phase", ""),
                        "indication": attrs.get("indication", ""),
                        "design": attrs.get("design", ""),
                        "source_file": attrs.get("source_file", ""),
                        "endpoints": [],
                        "censoring_rules": [],
                        "methods": [],
                        "multiplicity": [],
                        "interim_analyses": [],
                        "populations": []
                    }
                    self.trials[node_id] = trial_data

        # Connect components to trials via edges
        for edge in self.edges:
            source = edge.get("source")
            target = edge.get("target")
            edge_type = edge.get("type", "").lower()

            # Check if source is a trial we're tracking
            if source in self.trials:
                target_node = self.nodes.get(target, {})
                target_type = target_node.get("type", "")
                target_attrs = target_node.get("attributes", {})

                if target_type == "endpoint" or edge_type == "has_endpoint":
                    self.trials[source]["endpoints"].append(target_attrs)
                elif target_type == "censoring_rule" or edge_type == "has_censoring_rule":
                    self.trials[source]["censoring_rules"].append(target_attrs)
                elif target_type == "method" or edge_type == "uses_method":
                    self.trials[source]["methods"].append(target_attrs)
                elif target_type == "multiplicity" or edge_type == "has_multiplicity":
                    self.trials[source]["multiplicity"].append(target_attrs)
                elif target_type == "interim_analysis" or edge_type == "has_interim_analysis":
                    self.trials[source]["interim_analyses"].append(target_attrs)
                elif target_type == "population" or edge_type == "has_population":
                    self.trials[source]["populations"].append(target_attrs)

    def find_similar_trials(
        self,
        phase: Optional[str] = None,
        indication: Optional[str] = None,
        endpoint_type: Optional[str] = None,
        design_type: Optional[str] = None,
        max_results: int = 5
    ) -> List[Dict]:
        """
        Find similar trials based on matching criteria.

        Args:
            phase: Trial phase (e.g., "III", "Phase 3", "2/3")
            indication: Disease/indication keywords (e.g., "NSCLC", "breast cancer", "AML")
            endpoint_type: Primary endpoint type (e.g., "PFS", "OS", "ORR", "DFS")
            design_type: Study design (e.g., "randomized", "single-arm", "open-label")
            max_results: Maximum number of results to return

        Returns:
            List of matching trials with their full precedent data
        """
        self._load_kg()

        if not self.trials:
            return []

        # Normalize search terms
        phase_pattern = self._normalize_phase(phase) if phase else None
        indication_terms = self._extract_keywords(indication) if indication else []
        endpoint_terms = self._extract_keywords(endpoint_type) if endpoint_type else []
        design_terms = self._extract_keywords(design_type) if design_type else []

        scored_trials = []

        for trial_id, trial in self.trials.items():
            score = 0

            # Phase matching (exact or partial)
            if phase_pattern:
                trial_phase = self._normalize_phase(trial.get("phase", ""))
                if trial_phase and phase_pattern in trial_phase:
                    score += 30

            # Indication matching (keyword overlap)
            if indication_terms:
                trial_indication = trial.get("indication", "").lower()
                matches = sum(1 for term in indication_terms if term in trial_indication)
                score += matches * 25

            # Endpoint type matching
            if endpoint_terms:
                for ep in trial.get("endpoints", []):
                    ep_name = ep.get("name", "").lower()
                    ep_type = ep.get("endpoint_type", "").lower()
                    for term in endpoint_terms:
                        if term in ep_name or term in ep_type:
                            score += 20
                            break

            # Design type matching
            if design_terms:
                trial_design = trial.get("design", "").lower()
                matches = sum(1 for term in design_terms if term in trial_design)
                score += matches * 15

            # Bonus for trials with rich data
            if trial.get("censoring_rules"):
                score += 5
            if trial.get("multiplicity"):
                score += 5
            if trial.get("interim_analyses"):
                score += 3

            if score > 0:
                scored_trials.append((score, trial_id, trial))

        # Sort by score and return top results
        scored_trials.sort(key=lambda x: -x[0])

        results = []
        for score, trial_id, trial in scored_trials[:max_results]:
            results.append({
                "trial_id": trial.get("trial_id", trial_id),
                "phase": trial.get("phase"),
                "indication": trial.get("indication"),
                "design": trial.get("design"),
                "source_sap": trial.get("source_file"),
                "relevance_score": score,
                "precedent_data": {
                    "endpoints": trial.get("endpoints", [])[:5],  # Limit for context
                    "censoring_rules": trial.get("censoring_rules", []),
                    "methods": trial.get("methods", [])[:5],
                    "multiplicity": trial.get("multiplicity", []),
                    "interim_analyses": trial.get("interim_analyses", [])
                }
            })

        return results

    def _normalize_phase(self, phase: str) -> str:
        """Normalize phase string for matching."""
        if not phase:
            return ""
        phase = phase.lower().replace("phase", "").strip()
        # Convert roman numerals
        phase = phase.replace("iii", "3").replace("ii", "2").replace("i", "1")
        return phase

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract searchable keywords from text."""
        if not text:
            return []
        # Common medical abbreviations and terms
        text = text.lower()
        # Split on non-alphanumeric
        words = re.split(r'[^a-z0-9]+', text)
        # Filter short words but keep abbreviations
        return [w for w in words if len(w) >= 2]


@dataclass
class KBRetrievalResult:
    """Result from knowledge base retrieval with provenance."""
    content: Any
    source_file: str
    source_key: str
    retrieved_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "provenance": {
                "source_file": self.source_file,
                "source_key": self.source_key,
                "retrieved_at": self.retrieved_at
            }
        }


class KnowledgeBaseTools:
    """
    Tool-based access to knowledge base content.
    Each method is a tool Claude can call explicitly.
    """

    def __init__(self):
        self._load_knowledge_bases()
        self.retrieval_log: List[Dict] = []  # Audit trail
        # Initialize trial precedent KG for similar trial lookup
        self.trial_kg = TrialPrecedentKG()

    def _load_knowledge_bases(self):
        """Load all knowledge base modules."""
        kb_dir = Path(__file__).parent

        # Import knowledge base modules
        try:
            from .methodology_knowledge_base import (
                STATISTICAL_METHODS,
                MISSING_DATA_HANDLING,
                SENSITIVITY_ANALYSES,
                STRATIFICATION_SPECIFICATIONS,
                SUBGROUP_ANALYSIS_SPECIFICATIONS,
                MULTIPLICITY_ADJUSTMENT,
                TIME_TO_EVENT_ANALYSIS,
                SAFETY_ANALYSIS_SPECIFICATIONS
            )
            self.STATISTICAL_METHODS = STATISTICAL_METHODS
            self.MISSING_DATA_HANDLING = MISSING_DATA_HANDLING
            self.SENSITIVITY_ANALYSES = SENSITIVITY_ANALYSES
            self.STRATIFICATION_SPECIFICATIONS = STRATIFICATION_SPECIFICATIONS
            self.SUBGROUP_ANALYSES = SUBGROUP_ANALYSIS_SPECIFICATIONS
            self.MULTIPLICITY_ADJUSTMENTS = MULTIPLICITY_ADJUSTMENT
            self.TIME_TO_EVENT_ANALYSIS = TIME_TO_EVENT_ANALYSIS
            self.SAFETY_ANALYSIS_SPECIFICATIONS = SAFETY_ANALYSIS_SPECIFICATIONS
        except ImportError:
            from methodology_knowledge_base import (
                STATISTICAL_METHODS,
                MISSING_DATA_HANDLING,
                SENSITIVITY_ANALYSES,
                STRATIFICATION_SPECIFICATIONS,
                SUBGROUP_ANALYSIS_SPECIFICATIONS,
                MULTIPLICITY_ADJUSTMENT,
                TIME_TO_EVENT_ANALYSIS,
                SAFETY_ANALYSIS_SPECIFICATIONS
            )
            self.STATISTICAL_METHODS = STATISTICAL_METHODS
            self.MISSING_DATA_HANDLING = MISSING_DATA_HANDLING
            self.SENSITIVITY_ANALYSES = SENSITIVITY_ANALYSES
            self.STRATIFICATION_SPECIFICATIONS = STRATIFICATION_SPECIFICATIONS
            self.SUBGROUP_ANALYSES = SUBGROUP_ANALYSIS_SPECIFICATIONS
            self.MULTIPLICITY_ADJUSTMENTS = MULTIPLICITY_ADJUSTMENT
            self.TIME_TO_EVENT_ANALYSIS = TIME_TO_EVENT_ANALYSIS
            self.SAFETY_ANALYSIS_SPECIFICATIONS = SAFETY_ANALYSIS_SPECIFICATIONS

        try:
            from .complete_tfl_inventory import (
                DISPOSITION_TABLES,
                EFFICACY_TABLES,
                SAFETY_TABLES,
                FIGURES,
                LISTINGS
            )
            self.DISPOSITION_TABLES = DISPOSITION_TABLES
            self.EFFICACY_TABLES = EFFICACY_TABLES
            self.SAFETY_TABLES = SAFETY_TABLES
            self.PHARMACOKINETIC_TABLES = {}  # Not in current KB
            self.BIOMARKER_TABLES = {}  # Not in current KB
            self.FIGURES = FIGURES
            self.LISTINGS = LISTINGS
        except ImportError:
            from complete_tfl_inventory import (
                DISPOSITION_TABLES,
                EFFICACY_TABLES,
                SAFETY_TABLES,
                FIGURES,
                LISTINGS
            )
            self.DISPOSITION_TABLES = DISPOSITION_TABLES
            self.EFFICACY_TABLES = EFFICACY_TABLES
            self.SAFETY_TABLES = SAFETY_TABLES
            self.PHARMACOKINETIC_TABLES = {}  # Not in current KB
            self.BIOMARKER_TABLES = {}  # Not in current KB
            self.FIGURES = FIGURES
            self.LISTINGS = LISTINGS

        try:
            from .production_sap_specifications import (
                TFL_SHELLS,
                ADAM_SPECIFICATIONS,
                ESTIMANDS_FRAMEWORK,
                PROGRAMMING_SPECIFICATIONS,
                STUDY_DESIGN,
                RECIST_SPECIFICATIONS,
                SAFETY_SPECIFICATIONS,
                DATA_HANDLING
            )
            self.TFL_SHELLS = TFL_SHELLS
            self.ADAM_SPECIFICATIONS = ADAM_SPECIFICATIONS
            self.ESTIMANDS_FRAMEWORK = ESTIMANDS_FRAMEWORK
            self.PROGRAMMING_SPECIFICATIONS = PROGRAMMING_SPECIFICATIONS
            self.STUDY_DESIGN = STUDY_DESIGN
            self.RECIST_SPECIFICATIONS = RECIST_SPECIFICATIONS
            self.SAFETY_SPECIFICATIONS = SAFETY_SPECIFICATIONS
            self.DATA_HANDLING = DATA_HANDLING
        except ImportError:
            from production_sap_specifications import (
                TFL_SHELLS,
                ADAM_SPECIFICATIONS,
                ESTIMANDS_FRAMEWORK,
                PROGRAMMING_SPECIFICATIONS,
                STUDY_DESIGN,
                RECIST_SPECIFICATIONS,
                SAFETY_SPECIFICATIONS,
                DATA_HANDLING
            )
            self.TFL_SHELLS = TFL_SHELLS
            self.ADAM_SPECIFICATIONS = ADAM_SPECIFICATIONS
            self.ESTIMANDS_FRAMEWORK = ESTIMANDS_FRAMEWORK
            self.PROGRAMMING_SPECIFICATIONS = PROGRAMMING_SPECIFICATIONS
            self.STUDY_DESIGN = STUDY_DESIGN
            self.RECIST_SPECIFICATIONS = RECIST_SPECIFICATIONS
            self.SAFETY_SPECIFICATIONS = SAFETY_SPECIFICATIONS
            self.DATA_HANDLING = DATA_HANDLING

    def _log_retrieval(self, tool_name: str, key: str, source: str):
        """Log each retrieval for audit trail."""
        self.retrieval_log.append({
            "tool": tool_name,
            "key": key,
            "source": source,
            "timestamp": datetime.now().isoformat()
        })

    # =========================================================================
    # STATISTICAL METHODS TOOLS
    # =========================================================================

    def get_statistical_method(self, method_name: str) -> KBRetrievalResult:
        """
        Get specification for a statistical method.

        Args:
            method_name: One of:
                - "cox_proportional_hazards"
                - "kaplan_meier"
                - "log_rank_test"
                - "stratified_log_rank"
                - "rmst" (restricted mean survival time)
                - "clopper_pearson"
                - "cmh_test"
                - "logistic_regression"
                - "mmrm"
                - "ancova"

        Returns:
            KBRetrievalResult with method specification and provenance
        """
        content = self.STATISTICAL_METHODS.get(method_name, {})
        self._log_retrieval("get_statistical_method", method_name, "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=content,
            source_file="methodology_knowledge_base.py",
            source_key=f"STATISTICAL_METHODS['{method_name}']"
        )

    def get_missing_data_method(self, method_name: str) -> KBRetrievalResult:
        """
        Get specification for missing data handling method.

        Args:
            method_name: One of:
                - "multiple_imputation"
                - "mmrm"
                - "locf"
                - "bocf"
                - "tipping_point"
                - "pattern_mixture"
        """
        content = self.MISSING_DATA_HANDLING.get(method_name, {})
        self._log_retrieval("get_missing_data_method", method_name, "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=content,
            source_file="methodology_knowledge_base.py",
            source_key=f"MISSING_DATA_HANDLING['{method_name}']"
        )

    def get_sensitivity_analysis(self, endpoint_type: str) -> KBRetrievalResult:
        """
        Get sensitivity analyses for an endpoint type.

        Args:
            endpoint_type: One of "pfs_sensitivity", "os_sensitivity", "orr_sensitivity"
        """
        content = self.SENSITIVITY_ANALYSES.get(endpoint_type, {})
        self._log_retrieval("get_sensitivity_analysis", endpoint_type, "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=content,
            source_file="methodology_knowledge_base.py",
            source_key=f"SENSITIVITY_ANALYSES['{endpoint_type}']"
        )

    def get_stratification_specs(self) -> KBRetrievalResult:
        """Get all stratification specifications."""
        self._log_retrieval("get_stratification_specs", "all", "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=self.STRATIFICATION_SPECIFICATIONS,
            source_file="methodology_knowledge_base.py",
            source_key="STRATIFICATION_SPECIFICATIONS"
        )

    def get_multiplicity_adjustment(self, method_name: str) -> KBRetrievalResult:
        """
        Get multiplicity adjustment method specification.

        Args:
            method_name: One of:
                - "fixed_sequence"
                - "hochberg"
                - "holm"
                - "graphical_approach"
                - "alpha_splitting"
        """
        content = self.MULTIPLICITY_ADJUSTMENTS.get(method_name, {})
        self._log_retrieval("get_multiplicity_adjustment", method_name, "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=content,
            source_file="methodology_knowledge_base.py",
            source_key=f"MULTIPLICITY_ADJUSTMENTS['{method_name}']"
        )

    def get_subgroup_analysis_specs(self) -> KBRetrievalResult:
        """Get subgroup analysis specifications."""
        self._log_retrieval("get_subgroup_analysis_specs", "all", "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=self.SUBGROUP_ANALYSES,
            source_file="methodology_knowledge_base.py",
            source_key="SUBGROUP_ANALYSES"
        )

    # =========================================================================
    # TABLE/FIGURE/LISTING TOOLS
    # =========================================================================

    def get_table_template(self, table_id: str) -> KBRetrievalResult:
        """
        Get table shell template by ID.

        Args:
            table_id: Table number like "14.1.1", "14.2.1", "14.3.1"
        """
        # Search across all table categories
        content = None
        source_key = None

        for category_name, category in [
            ("DISPOSITION_TABLES", self.DISPOSITION_TABLES),
            ("EFFICACY_TABLES", self.EFFICACY_TABLES),
            ("SAFETY_TABLES", self.SAFETY_TABLES),
            ("PHARMACOKINETIC_TABLES", self.PHARMACOKINETIC_TABLES),
            ("BIOMARKER_TABLES", self.BIOMARKER_TABLES)
        ]:
            if table_id in category:
                content = category[table_id]
                source_key = f"{category_name}['{table_id}']"
                break

        # Also check TFL_SHELLS
        if content is None:
            for shell_category in self.TFL_SHELLS.values():
                if isinstance(shell_category, dict) and table_id in shell_category:
                    content = shell_category[table_id]
                    source_key = f"TFL_SHELLS[...]['{table_id}']"
                    break

        self._log_retrieval("get_table_template", table_id, "complete_tfl_inventory.py")

        return KBRetrievalResult(
            content=content or {},
            source_file="complete_tfl_inventory.py",
            source_key=source_key or f"NOT_FOUND['{table_id}']"
        )

    def get_disposition_tables(self) -> KBRetrievalResult:
        """Get all disposition table templates (CONSORT flowchart, demographics, etc.)."""
        self._log_retrieval("get_disposition_tables", "all", "complete_tfl_inventory.py")

        return KBRetrievalResult(
            content=self.DISPOSITION_TABLES,
            source_file="complete_tfl_inventory.py",
            source_key="DISPOSITION_TABLES"
        )

    def get_efficacy_tables(self) -> KBRetrievalResult:
        """Get all efficacy table templates (PFS, OS, ORR, etc.)."""
        self._log_retrieval("get_efficacy_tables", "all", "complete_tfl_inventory.py")

        return KBRetrievalResult(
            content=self.EFFICACY_TABLES,
            source_file="complete_tfl_inventory.py",
            source_key="EFFICACY_TABLES"
        )

    def get_safety_tables(self) -> KBRetrievalResult:
        """Get all safety table templates (AE summaries, lab shifts, etc.)."""
        self._log_retrieval("get_safety_tables", "all", "complete_tfl_inventory.py")

        return KBRetrievalResult(
            content=self.SAFETY_TABLES,
            source_file="complete_tfl_inventory.py",
            source_key="SAFETY_TABLES"
        )

    def get_figure_template(self, figure_id: str) -> KBRetrievalResult:
        """Get figure template by ID (e.g., "14.4.1" for KM plot)."""
        content = self.FIGURES.get(figure_id, {})
        self._log_retrieval("get_figure_template", figure_id, "complete_tfl_inventory.py")

        return KBRetrievalResult(
            content=content,
            source_file="complete_tfl_inventory.py",
            source_key=f"FIGURES['{figure_id}']"
        )

    def get_all_figures(self) -> KBRetrievalResult:
        """Get all figure templates."""
        self._log_retrieval("get_all_figures", "all", "complete_tfl_inventory.py")

        return KBRetrievalResult(
            content=self.FIGURES,
            source_file="complete_tfl_inventory.py",
            source_key="FIGURES"
        )

    # =========================================================================
    # ADAM & DATA SPECIFICATION TOOLS
    # =========================================================================

    def get_adam_dataset_spec(self, dataset_name: str) -> KBRetrievalResult:
        """
        Get ADaM dataset specification.

        Args:
            dataset_name: One of "adsl", "adae", "adtte", "adrs", "adlb"
        """
        content = self.ADAM_SPECIFICATIONS.get(dataset_name.lower(), {})
        self._log_retrieval("get_adam_dataset_spec", dataset_name, "production_sap_specifications.py")

        return KBRetrievalResult(
            content=content,
            source_file="production_sap_specifications.py",
            source_key=f"ADAM_SPECIFICATIONS['{dataset_name}']"
        )

    def get_data_handling_rules(self) -> KBRetrievalResult:
        """Get data handling conventions (treatment assignment, missing data, etc.)."""
        self._log_retrieval("get_data_handling_rules", "all", "production_sap_specifications.py")

        return KBRetrievalResult(
            content=self.DATA_HANDLING,
            source_file="production_sap_specifications.py",
            source_key="DATA_HANDLING"
        )

    def get_programming_specifications(self) -> KBRetrievalResult:
        """Get programming specifications (visit windowing, baseline definition, etc.)."""
        self._log_retrieval("get_programming_specifications", "all", "production_sap_specifications.py")

        return KBRetrievalResult(
            content=self.PROGRAMMING_SPECIFICATIONS,
            source_file="production_sap_specifications.py",
            source_key="PROGRAMMING_SPECIFICATIONS"
        )

    # =========================================================================
    # ESTIMANDS & REGULATORY TOOLS
    # =========================================================================

    def get_estimand_framework(self) -> KBRetrievalResult:
        """Get ICH E9(R1) estimands framework specification."""
        self._log_retrieval("get_estimand_framework", "all", "production_sap_specifications.py")

        return KBRetrievalResult(
            content=self.ESTIMANDS_FRAMEWORK,
            source_file="production_sap_specifications.py",
            source_key="ESTIMANDS_FRAMEWORK"
        )

    def get_recist_specifications(self) -> KBRetrievalResult:
        """Get RECIST 1.1 response criteria specifications."""
        self._log_retrieval("get_recist_specifications", "all", "production_sap_specifications.py")

        return KBRetrievalResult(
            content=self.RECIST_SPECIFICATIONS,
            source_file="production_sap_specifications.py",
            source_key="RECIST_SPECIFICATIONS"
        )

    def get_safety_specifications(self) -> KBRetrievalResult:
        """Get safety analysis specifications (TEAE definition, lab analysis, etc.)."""
        self._log_retrieval("get_safety_specifications", "all", "production_sap_specifications.py")

        return KBRetrievalResult(
            content=self.SAFETY_SPECIFICATIONS,
            source_file="production_sap_specifications.py",
            source_key="SAFETY_SPECIFICATIONS"
        )

    def get_study_design_specs(self) -> KBRetrievalResult:
        """Get study design specifications (sample size, alpha allocation, interim analysis)."""
        self._log_retrieval("get_study_design_specs", "all", "production_sap_specifications.py")

        return KBRetrievalResult(
            content=self.STUDY_DESIGN,
            source_file="production_sap_specifications.py",
            source_key="STUDY_DESIGN"
        )

    # =========================================================================
    # TRIAL PRECEDENT TOOLS (queries factual_kg_merged.json)
    # =========================================================================

    def get_similar_trials(
        self,
        phase: Optional[str] = None,
        indication: Optional[str] = None,
        endpoint_type: Optional[str] = None,
        design_type: Optional[str] = None
    ) -> KBRetrievalResult:
        """
        Find similar trials from the knowledge graph to use as precedent.

        This queries 354 real trial SAPs to find examples of how similar trials
        handled censoring rules, multiplicity, interim analyses, and endpoints.

        Args:
            phase: Trial phase (e.g., "III", "Phase 3", "2/3")
            indication: Disease/indication (e.g., "NSCLC", "breast cancer", "AML", "lymphoma")
            endpoint_type: Primary endpoint (e.g., "PFS", "OS", "ORR", "DFS", "EFS")
            design_type: Study design (e.g., "randomized", "single-arm", "open-label")

        Returns:
            Similar trials with their precedent data including:
            - Endpoint definitions used
            - Censoring rules applied
            - Statistical methods selected
            - Multiplicity adjustments
            - Interim analysis designs
        """
        search_key = f"phase={phase}, indication={indication}, endpoint={endpoint_type}, design={design_type}"
        self._log_retrieval("get_similar_trials", search_key, "factual_kg_merged.json")

        results = self.trial_kg.find_similar_trials(
            phase=phase,
            indication=indication,
            endpoint_type=endpoint_type,
            design_type=design_type,
            max_results=5
        )

        return KBRetrievalResult(
            content={
                "query": {
                    "phase": phase,
                    "indication": indication,
                    "endpoint_type": endpoint_type,
                    "design_type": design_type
                },
                "num_matches": len(results),
                "similar_trials": results
            },
            source_file="factual_kg_merged.json",
            source_key="TrialPrecedentKG.find_similar_trials"
        )

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_retrieval_log(self) -> List[Dict]:
        """Get the audit log of all retrievals."""
        return self.retrieval_log

    def list_available_tools(self) -> List[Dict]:
        """List all available tools with descriptions."""
        return [
            {"name": "get_statistical_method", "description": "Get statistical method specification (Cox, KM, log-rank, etc.)"},
            {"name": "get_missing_data_method", "description": "Get missing data handling specification (MI, MMRM, etc.)"},
            {"name": "get_sensitivity_analysis", "description": "Get sensitivity analyses for endpoint type"},
            {"name": "get_stratification_specs", "description": "Get stratification specifications"},
            {"name": "get_multiplicity_adjustment", "description": "Get multiplicity adjustment method"},
            {"name": "get_subgroup_analysis_specs", "description": "Get subgroup analysis specifications"},
            {"name": "get_table_template", "description": "Get specific table shell by ID"},
            {"name": "get_disposition_tables", "description": "Get all disposition tables (CONSORT, demographics)"},
            {"name": "get_efficacy_tables", "description": "Get all efficacy tables (PFS, OS, ORR)"},
            {"name": "get_safety_tables", "description": "Get all safety tables (AE, labs)"},
            {"name": "get_figure_template", "description": "Get specific figure template by ID"},
            {"name": "get_all_figures", "description": "Get all figure templates"},
            {"name": "get_adam_dataset_spec", "description": "Get ADaM dataset specification"},
            {"name": "get_data_handling_rules", "description": "Get data handling conventions"},
            {"name": "get_programming_specifications", "description": "Get programming specifications"},
            {"name": "get_estimand_framework", "description": "Get ICH E9(R1) estimands framework"},
            {"name": "get_recist_specifications", "description": "Get RECIST 1.1 specifications"},
            {"name": "get_safety_specifications", "description": "Get safety analysis specifications"},
            {"name": "get_study_design_specs", "description": "Get study design specifications"},
            {"name": "get_similar_trials", "description": "Find similar trials from 354-trial KG for precedent (censoring, multiplicity, methods)"},
        ]


# =============================================================================
# CLAUDE TOOL DEFINITIONS
# =============================================================================

def get_claude_tool_definitions() -> List[Dict]:
    """
    Get tool definitions in Claude API format.
    These are passed to Claude so it knows what tools are available.
    """
    return [
        {
            "name": "get_statistical_method",
            "description": "Get the standard specification for a statistical method including formula, assumptions, and implementation details. Use this when you need to include a statistical method in the SAP.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "method_name": {
                        "type": "string",
                        "description": "The statistical method name",
                        "enum": [
                            "cox_proportional_hazards",
                            "kaplan_meier",
                            "log_rank_test",
                            "stratified_log_rank",
                            "rmst",
                            "clopper_pearson",
                            "cmh_test",
                            "logistic_regression",
                            "mmrm",
                            "ancova"
                        ]
                    }
                },
                "required": ["method_name"]
            }
        },
        {
            "name": "get_missing_data_method",
            "description": "Get the standard specification for a missing data handling method. Use this when writing the Missing Data section of the SAP.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "method_name": {
                        "type": "string",
                        "description": "The missing data method name",
                        "enum": [
                            "multiple_imputation",
                            "mmrm",
                            "locf",
                            "bocf",
                            "tipping_point",
                            "pattern_mixture"
                        ]
                    }
                },
                "required": ["method_name"]
            }
        },
        {
            "name": "get_sensitivity_analysis",
            "description": "Get standard sensitivity analyses for a specific endpoint type. Use this when writing sensitivity analysis sections.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "endpoint_type": {
                        "type": "string",
                        "description": "The endpoint type",
                        "enum": ["pfs_sensitivity", "os_sensitivity", "orr_sensitivity"]
                    }
                },
                "required": ["endpoint_type"]
            }
        },
        {
            "name": "get_table_template",
            "description": "Get the standard table shell template for a specific table ID. Use this when creating the TFL shells section.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "table_id": {
                        "type": "string",
                        "description": "The table ID (e.g., '14.1.1' for Subject Disposition, '14.2.1' for PFS Summary)"
                    }
                },
                "required": ["table_id"]
            }
        },
        {
            "name": "get_disposition_tables",
            "description": "Get all standard disposition table templates including CONSORT flowchart, demographics, and baseline characteristics. Use this for Section 14.1 tables.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_efficacy_tables",
            "description": "Get all standard efficacy table templates including PFS, OS, ORR, DOR tables. Use this for Section 14.2 tables.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_safety_tables",
            "description": "Get all standard safety table templates including AE summaries, lab shifts, vital signs. Use this for Section 14.3 tables.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_all_figures",
            "description": "Get all standard figure templates including Kaplan-Meier plots, forest plots, waterfall plots.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_estimand_framework",
            "description": "Get the ICH E9(R1) estimands framework specification including intercurrent event strategies. Use this for the Estimands section.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_adam_dataset_spec",
            "description": "Get the ADaM dataset specification for a specific dataset. Use this when referencing analysis datasets.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "dataset_name": {
                        "type": "string",
                        "description": "The ADaM dataset name",
                        "enum": ["adsl", "adae", "adtte", "adrs", "adlb"]
                    }
                },
                "required": ["dataset_name"]
            }
        },
        {
            "name": "get_recist_specifications",
            "description": "Get RECIST 1.1 response criteria specifications. Use this when writing tumor response assessment sections.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_safety_specifications",
            "description": "Get safety analysis specifications including TEAE definitions, laboratory analysis methods, and vital signs analysis.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_multiplicity_adjustment",
            "description": "Get multiplicity adjustment method specification. Use this when writing about multiple testing procedures.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "method_name": {
                        "type": "string",
                        "description": "The multiplicity method name",
                        "enum": ["fixed_sequence", "hochberg", "holm", "graphical_approach", "alpha_splitting"]
                    }
                },
                "required": ["method_name"]
            }
        },
        {
            "name": "get_stratification_specs",
            "description": "Get stratification factor specifications including common factors and how they are used in analysis.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_subgroup_analysis_specs",
            "description": "Get subgroup analysis specifications including standard subgroups and forest plot specifications.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_data_handling_rules",
            "description": "Get data handling conventions including treatment assignment rules, visit windowing, and censoring rules.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_similar_trials",
            "description": "Find similar trials from the 354-trial knowledge graph for precedent. Returns real examples of censoring rules, multiplicity adjustments, interim analysis designs, and statistical methods used in similar trials. Use this to see what approaches were accepted in similar regulatory submissions.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "string",
                        "description": "Trial phase (e.g., 'III', 'Phase 3', '2/3', '1b/2')"
                    },
                    "indication": {
                        "type": "string",
                        "description": "Disease/indication keywords (e.g., 'NSCLC', 'breast cancer', 'AML', 'lymphoma', 'melanoma')"
                    },
                    "endpoint_type": {
                        "type": "string",
                        "description": "Primary endpoint type (e.g., 'PFS', 'OS', 'ORR', 'DFS', 'EFS', 'CR rate')"
                    },
                    "design_type": {
                        "type": "string",
                        "description": "Study design (e.g., 'randomized', 'single-arm', 'open-label', 'double-blind')"
                    }
                },
                "required": []
            }
        }
    ]


def execute_tool(tool_name: str, tool_input: Dict, kb: KnowledgeBaseTools) -> KBRetrievalResult:
    """
    Execute a tool call and return the result.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Input parameters for the tool
        kb: KnowledgeBaseTools instance

    Returns:
        KBRetrievalResult with content and provenance
    """
    tool_map = {
        "get_statistical_method": lambda: kb.get_statistical_method(tool_input.get("method_name", "")),
        "get_missing_data_method": lambda: kb.get_missing_data_method(tool_input.get("method_name", "")),
        "get_sensitivity_analysis": lambda: kb.get_sensitivity_analysis(tool_input.get("endpoint_type", "")),
        "get_table_template": lambda: kb.get_table_template(tool_input.get("table_id", "")),
        "get_disposition_tables": lambda: kb.get_disposition_tables(),
        "get_efficacy_tables": lambda: kb.get_efficacy_tables(),
        "get_safety_tables": lambda: kb.get_safety_tables(),
        "get_all_figures": lambda: kb.get_all_figures(),
        "get_estimand_framework": lambda: kb.get_estimand_framework(),
        "get_adam_dataset_spec": lambda: kb.get_adam_dataset_spec(tool_input.get("dataset_name", "")),
        "get_recist_specifications": lambda: kb.get_recist_specifications(),
        "get_safety_specifications": lambda: kb.get_safety_specifications(),
        "get_multiplicity_adjustment": lambda: kb.get_multiplicity_adjustment(tool_input.get("method_name", "")),
        "get_stratification_specs": lambda: kb.get_stratification_specs(),
        "get_subgroup_analysis_specs": lambda: kb.get_subgroup_analysis_specs(),
        "get_data_handling_rules": lambda: kb.get_data_handling_rules(),
        "get_similar_trials": lambda: kb.get_similar_trials(
            phase=tool_input.get("phase"),
            indication=tool_input.get("indication"),
            endpoint_type=tool_input.get("endpoint_type"),
            design_type=tool_input.get("design_type")
        ),
    }

    if tool_name in tool_map:
        return tool_map[tool_name]()
    else:
        return KBRetrievalResult(
            content={"error": f"Unknown tool: {tool_name}"},
            source_file="kb_tools.py",
            source_key="ERROR"
        )


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("KNOWLEDGE BASE TOOLS TEST")
    print("=" * 70)

    kb = KnowledgeBaseTools()

    # Test statistical method retrieval
    print("\n1. Testing get_statistical_method('cox_proportional_hazards'):")
    result = kb.get_statistical_method("cox_proportional_hazards")
    print(f"   Source: {result.source_file} -> {result.source_key}")
    if result.content:
        print(f"   Content keys: {list(result.content.keys())[:5]}...")

    # Test table template retrieval
    print("\n2. Testing get_table_template('14.1.1'):")
    result = kb.get_table_template("14.1.1")
    print(f"   Source: {result.source_file} -> {result.source_key}")
    if result.content:
        print(f"   Title: {result.content.get('title', 'N/A')}")

    # Test missing data method
    print("\n3. Testing get_missing_data_method('multiple_imputation'):")
    result = kb.get_missing_data_method("multiple_imputation")
    print(f"   Source: {result.source_file} -> {result.source_key}")

    # List available tools
    print("\n4. Available tools for Claude:")
    tools = get_claude_tool_definitions()
    for tool in tools[:5]:
        print(f"   - {tool['name']}: {tool['description'][:60]}...")
    print(f"   ... and {len(tools) - 5} more tools")

    # Show retrieval log
    print("\n5. Retrieval log (audit trail):")
    for entry in kb.get_retrieval_log():
        print(f"   {entry['timestamp']}: {entry['tool']}({entry['key']})")

    print("\n" + "=" * 70)
    print("TOOLS READY FOR CLAUDE INTEGRATION")
    print("=" * 70)
