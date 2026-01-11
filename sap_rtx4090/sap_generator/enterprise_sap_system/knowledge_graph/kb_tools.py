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
                SAFETY_ANALYSIS_SPECIFICATIONS,
                CENSORING_RULES,
                INTERIM_ANALYSIS_SPECIFICATIONS,
                DERIVED_VARIABLE_SPECIFICATIONS,
                CONFIDENCE_INTERVAL_METHODS,
                PRO_QOL_ANALYSIS,
                ANALYSIS_WINDOWS,
                DATA_CUTOFF_SPECIFICATIONS
            )
            self.STATISTICAL_METHODS = STATISTICAL_METHODS
            self.MISSING_DATA_HANDLING = MISSING_DATA_HANDLING
            self.SENSITIVITY_ANALYSES = SENSITIVITY_ANALYSES
            self.STRATIFICATION_SPECIFICATIONS = STRATIFICATION_SPECIFICATIONS
            self.SUBGROUP_ANALYSES = SUBGROUP_ANALYSIS_SPECIFICATIONS
            self.MULTIPLICITY_ADJUSTMENTS = MULTIPLICITY_ADJUSTMENT
            self.TIME_TO_EVENT_ANALYSIS = TIME_TO_EVENT_ANALYSIS
            self.SAFETY_ANALYSIS_SPECIFICATIONS = SAFETY_ANALYSIS_SPECIFICATIONS
            self.CENSORING_RULES = CENSORING_RULES
            self.INTERIM_ANALYSIS = INTERIM_ANALYSIS_SPECIFICATIONS
            self.DERIVED_VARIABLES = DERIVED_VARIABLE_SPECIFICATIONS
            self.CONFIDENCE_INTERVALS = CONFIDENCE_INTERVAL_METHODS
            self.PRO_QOL = PRO_QOL_ANALYSIS
            self.ANALYSIS_WINDOWS = ANALYSIS_WINDOWS
            self.DATA_CUTOFF = DATA_CUTOFF_SPECIFICATIONS
        except ImportError:
            from methodology_knowledge_base import (
                STATISTICAL_METHODS,
                MISSING_DATA_HANDLING,
                SENSITIVITY_ANALYSES,
                STRATIFICATION_SPECIFICATIONS,
                SUBGROUP_ANALYSIS_SPECIFICATIONS,
                MULTIPLICITY_ADJUSTMENT,
                TIME_TO_EVENT_ANALYSIS,
                SAFETY_ANALYSIS_SPECIFICATIONS,
                CENSORING_RULES,
                INTERIM_ANALYSIS_SPECIFICATIONS,
                DERIVED_VARIABLE_SPECIFICATIONS,
                CONFIDENCE_INTERVAL_METHODS,
                PRO_QOL_ANALYSIS,
                ANALYSIS_WINDOWS,
                DATA_CUTOFF_SPECIFICATIONS
            )
            self.STATISTICAL_METHODS = STATISTICAL_METHODS
            self.MISSING_DATA_HANDLING = MISSING_DATA_HANDLING
            self.SENSITIVITY_ANALYSES = SENSITIVITY_ANALYSES
            self.STRATIFICATION_SPECIFICATIONS = STRATIFICATION_SPECIFICATIONS
            self.SUBGROUP_ANALYSES = SUBGROUP_ANALYSIS_SPECIFICATIONS
            self.MULTIPLICITY_ADJUSTMENTS = MULTIPLICITY_ADJUSTMENT
            self.TIME_TO_EVENT_ANALYSIS = TIME_TO_EVENT_ANALYSIS
            self.SAFETY_ANALYSIS_SPECIFICATIONS = SAFETY_ANALYSIS_SPECIFICATIONS
            self.CENSORING_RULES = CENSORING_RULES
            self.INTERIM_ANALYSIS = INTERIM_ANALYSIS_SPECIFICATIONS
            self.DERIVED_VARIABLES = DERIVED_VARIABLE_SPECIFICATIONS
            self.CONFIDENCE_INTERVALS = CONFIDENCE_INTERVAL_METHODS
            self.PRO_QOL = PRO_QOL_ANALYSIS
            self.ANALYSIS_WINDOWS = ANALYSIS_WINDOWS
            self.DATA_CUTOFF = DATA_CUTOFF_SPECIFICATIONS

        # Standard population definitions (not in external file - defined here)
        self.POPULATION_DEFINITIONS = {
            "itt": {
                "name": "Intent-to-Treat (ITT) Population",
                "definition": "All randomized subjects, analyzed according to randomized treatment assignment regardless of actual treatment received.",
                "use_for": ["Primary efficacy analysis", "Regulatory submission"],
                "source": "ICH E9"
            },
            "mitt": {
                "name": "Modified Intent-to-Treat (mITT) Population",
                "definition": "All randomized subjects who received at least one dose of study treatment and had at least one post-baseline efficacy assessment.",
                "use_for": ["Supportive efficacy analysis"],
                "exclusions": ["No study drug received", "No post-baseline assessment"]
            },
            "safety": {
                "name": "Safety Population",
                "definition": "All subjects who received at least one dose (or partial dose) of study treatment, analyzed according to treatment actually received.",
                "use_for": ["All safety analyses", "AE summaries", "Laboratory analyses"]
            },
            "per_protocol": {
                "name": "Per-Protocol (PP) Population",
                "definition": "All subjects in the ITT population who completed the study without major protocol deviations that could affect efficacy assessment.",
                "use_for": ["Supportive/sensitivity efficacy analysis"],
                "exclusions": ["Major protocol deviations", "Inadequate treatment exposure", "Wrong diagnosis"]
            },
            "evaluable": {
                "name": "Evaluable Population",
                "definition": "All subjects who received study treatment and had adequate baseline and post-baseline tumor assessments for response evaluation.",
                "use_for": ["Response rate analyses (ORR, CR, PR)"]
            },
            "pharmacokinetic": {
                "name": "Pharmacokinetic (PK) Population",
                "definition": "All subjects who received study treatment and had at least one evaluable PK sample.",
                "use_for": ["PK analyses", "Exposure-response analyses"]
            },
            "dlt_evaluable": {
                "name": "DLT-Evaluable Population",
                "definition": "All subjects who received the full planned dose during the DLT evaluation period or experienced a DLT.",
                "use_for": ["Phase 1 dose-escalation", "MTD determination"]
            }
        }

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
            # v67: Design-specific templates
            from .complete_tfl_inventory import (
                SINGLE_ARM_DISPOSITION_TABLES,
                LYMPHOMA_BASELINE_TABLES,
                LYMPHOMA_EFFICACY_TABLES,
                CAR_T_SAFETY_TABLES,
                CAR_T_RETREATMENT_TABLES
            )
            self.SINGLE_ARM_TABLES = SINGLE_ARM_DISPOSITION_TABLES
            self.LYMPHOMA_BASELINE_TABLES = LYMPHOMA_BASELINE_TABLES
            self.LYMPHOMA_EFFICACY_TABLES = LYMPHOMA_EFFICACY_TABLES
            self.CAR_T_SAFETY_TABLES = CAR_T_SAFETY_TABLES
            self.CAR_T_RETREATMENT_TABLES = CAR_T_RETREATMENT_TABLES
        except ImportError:
            from complete_tfl_inventory import (
                DISPOSITION_TABLES,
                EFFICACY_TABLES,
                SAFETY_TABLES,
                FIGURES,
                LISTINGS,
                SINGLE_ARM_DISPOSITION_TABLES,
                LYMPHOMA_BASELINE_TABLES,
                LYMPHOMA_EFFICACY_TABLES,
                CAR_T_SAFETY_TABLES,
                CAR_T_RETREATMENT_TABLES
            )
            self.DISPOSITION_TABLES = DISPOSITION_TABLES
            self.EFFICACY_TABLES = EFFICACY_TABLES
            self.SAFETY_TABLES = SAFETY_TABLES
            self.PHARMACOKINETIC_TABLES = {}  # Not in current KB
            self.BIOMARKER_TABLES = {}  # Not in current KB
            self.FIGURES = FIGURES
            self.LISTINGS = LISTINGS
            # v67: Design-specific templates
            self.SINGLE_ARM_TABLES = SINGLE_ARM_DISPOSITION_TABLES
            self.LYMPHOMA_BASELINE_TABLES = LYMPHOMA_BASELINE_TABLES
            self.LYMPHOMA_EFFICACY_TABLES = LYMPHOMA_EFFICACY_TABLES
            self.CAR_T_SAFETY_TABLES = CAR_T_SAFETY_TABLES
            self.CAR_T_RETREATMENT_TABLES = CAR_T_RETREATMENT_TABLES

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

        # Load disease-specific response criteria (Lugano, IMWG, irRECIST, etc.)
        try:
            from .disease_specific_criteria import (
                RANO_CRITERIA,
                LUGANO_CRITERIA,
                PCWG3_CRITERIA,
                irRECIST_CRITERIA,
                iRECIST_CRITERIA,
                IMWG_CRITERIA,
                GCIG_CA125_CRITERIA,
                RANO_BM_CRITERIA
            )
            self.DISEASE_CRITERIA = {
                "RANO": RANO_CRITERIA,
                "Lugano": LUGANO_CRITERIA,
                "PCWG3": PCWG3_CRITERIA,
                "irRECIST": irRECIST_CRITERIA,
                "iRECIST": iRECIST_CRITERIA,
                "IMWG": IMWG_CRITERIA,
                "GCIG_CA125": GCIG_CA125_CRITERIA,
                "RANO_BM": RANO_BM_CRITERIA
            }
        except ImportError:
            from disease_specific_criteria import (
                RANO_CRITERIA,
                LUGANO_CRITERIA,
                PCWG3_CRITERIA,
                irRECIST_CRITERIA,
                iRECIST_CRITERIA,
                IMWG_CRITERIA,
                GCIG_CA125_CRITERIA,
                RANO_BM_CRITERIA
            )
            self.DISEASE_CRITERIA = {
                "RANO": RANO_CRITERIA,
                "Lugano": LUGANO_CRITERIA,
                "PCWG3": PCWG3_CRITERIA,
                "irRECIST": irRECIST_CRITERIA,
                "iRECIST": iRECIST_CRITERIA,
                "IMWG": IMWG_CRITERIA,
                "GCIG_CA125": GCIG_CA125_CRITERIA,
                "RANO_BM": RANO_BM_CRITERIA
            }

        # Load oncology reference data (CAR-T, study type templates, biomarkers)
        try:
            from .oncology_reference_data import (
                CAR_T_MODULE,
                BISPECIFIC_ANTIBODY_MODULE,
                ADC_MODULE,
                ADJUVANT_TRIAL_TEMPLATE,
                NEOADJUVANT_TRIAL_TEMPLATE,
                BASKET_TRIAL_TEMPLATE,
                UMBRELLA_TRIAL_TEMPLATE,
                BIOMARKER_ENDPOINTS,
                PERFORMANCE_STATUS_SCALES,
                PROGNOSTIC_SCORES,
                EFFICACY_TFL_TEMPLATES,
                SAFETY_TFL_TEMPLATES,
                CML_CRITERIA,
                IWCLL_CRITERIA,
                ORGAN_FUNCTION_SCORES
            )
            self.CAR_T_MODULE = CAR_T_MODULE
            self.BISPECIFIC_MODULE = BISPECIFIC_ANTIBODY_MODULE
            self.ADC_MODULE = ADC_MODULE
            self.STUDY_TYPE_TEMPLATES = {
                "adjuvant": ADJUVANT_TRIAL_TEMPLATE,
                "neoadjuvant": NEOADJUVANT_TRIAL_TEMPLATE,
                "basket": BASKET_TRIAL_TEMPLATE,
                "umbrella": UMBRELLA_TRIAL_TEMPLATE
            }
            self.BIOMARKER_ENDPOINTS = BIOMARKER_ENDPOINTS
            self.PERFORMANCE_STATUS_SCALES = PERFORMANCE_STATUS_SCALES
            self.PROGNOSTIC_SCORES = PROGNOSTIC_SCORES
            self.CML_CRITERIA = CML_CRITERIA
            self.IWCLL_CRITERIA = IWCLL_CRITERIA
            self.ORGAN_FUNCTION_SCORES = ORGAN_FUNCTION_SCORES
            self.ONCOLOGY_TFL_TEMPLATES = {
                "efficacy": EFFICACY_TFL_TEMPLATES,
                "safety": SAFETY_TFL_TEMPLATES
            }
        except ImportError:
            from oncology_reference_data import (
                CAR_T_MODULE,
                BISPECIFIC_ANTIBODY_MODULE,
                ADC_MODULE,
                ADJUVANT_TRIAL_TEMPLATE,
                NEOADJUVANT_TRIAL_TEMPLATE,
                BASKET_TRIAL_TEMPLATE,
                UMBRELLA_TRIAL_TEMPLATE,
                BIOMARKER_ENDPOINTS,
                PERFORMANCE_STATUS_SCALES,
                PROGNOSTIC_SCORES,
                EFFICACY_TFL_TEMPLATES,
                SAFETY_TFL_TEMPLATES,
                CML_CRITERIA,
                IWCLL_CRITERIA,
                ORGAN_FUNCTION_SCORES
            )
            self.CAR_T_MODULE = CAR_T_MODULE
            self.BISPECIFIC_MODULE = BISPECIFIC_ANTIBODY_MODULE
            self.ADC_MODULE = ADC_MODULE
            self.STUDY_TYPE_TEMPLATES = {
                "adjuvant": ADJUVANT_TRIAL_TEMPLATE,
                "neoadjuvant": NEOADJUVANT_TRIAL_TEMPLATE,
                "basket": BASKET_TRIAL_TEMPLATE,
                "umbrella": UMBRELLA_TRIAL_TEMPLATE
            }
            self.BIOMARKER_ENDPOINTS = BIOMARKER_ENDPOINTS
            self.PERFORMANCE_STATUS_SCALES = PERFORMANCE_STATUS_SCALES
            self.PROGNOSTIC_SCORES = PROGNOSTIC_SCORES
            self.CML_CRITERIA = CML_CRITERIA
            self.IWCLL_CRITERIA = IWCLL_CRITERIA
            self.ORGAN_FUNCTION_SCORES = ORGAN_FUNCTION_SCORES
            self.ONCOLOGY_TFL_TEMPLATES = {
                "efficacy": EFFICACY_TFL_TEMPLATES,
                "safety": SAFETY_TFL_TEMPLATES
            }

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

    def get_censoring_rules(self, endpoint_type: str = "pfs") -> KBRetrievalResult:
        """
        Get censoring rules for time-to-event endpoints.

        Args:
            endpoint_type: One of:
                - "pfs" (progression-free survival)
                - "os" (overall survival)
                - "dfs" (disease-free survival)
                - "efs" (event-free survival)
                - "dor" (duration of response)
                - "ttf" (time to treatment failure)
                - "all" (returns all censoring rules)
        """
        if endpoint_type == "all":
            content = self.CENSORING_RULES
        else:
            content = self.CENSORING_RULES.get(f"{endpoint_type}_censoring",
                      self.CENSORING_RULES.get(endpoint_type, {}))

        self._log_retrieval("get_censoring_rules", endpoint_type, "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=content,
            source_file="methodology_knowledge_base.py",
            source_key=f"CENSORING_RULES['{endpoint_type}']"
        )

    def get_interim_analysis(self, analysis_type: str = "all") -> KBRetrievalResult:
        """
        Get interim analysis specifications.

        Args:
            analysis_type: One of:
                - "dmc_charter" (DMC composition and recommendations)
                - "efficacy_interim" (efficacy boundaries, alpha spending)
                - "os_interim_at_pfs_final" (OS interim at PFS final)
                - "sample_size_re_estimation" (blinded/unblinded re-estimation)
                - "alpha_spending" (spending functions: OBF, Lan-DeMets)
                - "all" (returns all specifications)
        """
        if analysis_type == "all":
            content = self.INTERIM_ANALYSIS
        else:
            content = self.INTERIM_ANALYSIS.get(analysis_type, {})

        self._log_retrieval("get_interim_analysis", analysis_type, "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=content,
            source_file="methodology_knowledge_base.py",
            source_key=f"INTERIM_ANALYSIS['{analysis_type}']"
        )

    def get_population_definitions(self, population_type: str = "all") -> KBRetrievalResult:
        """
        Get standard analysis population definitions.

        Args:
            population_type: One of:
                - "itt" (Intent-to-Treat)
                - "mitt" (Modified Intent-to-Treat)
                - "safety" (Safety Population)
                - "per_protocol" (Per-Protocol)
                - "evaluable" (Evaluable/Response-Evaluable)
                - "pharmacokinetic" (PK Population)
                - "dlt_evaluable" (DLT-Evaluable for Phase 1)
                - "all" (returns all population definitions)
        """
        if population_type == "all":
            content = self.POPULATION_DEFINITIONS
        else:
            content = self.POPULATION_DEFINITIONS.get(population_type, {})

        self._log_retrieval("get_population_definitions", population_type, "kb_tools.py")

        return KBRetrievalResult(
            content=content,
            source_file="kb_tools.py",
            source_key=f"POPULATION_DEFINITIONS['{population_type}']"
        )

    def get_derived_variables(self, variable_type: str = "all") -> KBRetrievalResult:
        """
        Get derived variable specifications for ADaM datasets.

        Args:
            variable_type: One of:
                - "baseline_flags" (baseline value derivation)
                - "treatment_flags" (on-treatment definitions)
                - "time_variables" (study day, relative day)
                - "all" (returns all specifications)
        """
        if variable_type == "all":
            content = self.DERIVED_VARIABLES
        else:
            content = self.DERIVED_VARIABLES.get(variable_type, {})

        self._log_retrieval("get_derived_variables", variable_type, "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=content,
            source_file="methodology_knowledge_base.py",
            source_key=f"DERIVED_VARIABLES['{variable_type}']"
        )

    def get_time_to_event_analysis(self) -> KBRetrievalResult:
        """Get time-to-event analysis specifications (Kaplan-Meier, Cox, competing risks)."""
        self._log_retrieval("get_time_to_event_analysis", "all", "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=self.TIME_TO_EVENT_ANALYSIS,
            source_file="methodology_knowledge_base.py",
            source_key="TIME_TO_EVENT_ANALYSIS"
        )

    def get_confidence_interval_methods(self, method_type: str = "all") -> KBRetrievalResult:
        """
        Get confidence interval calculation methods.

        Args:
            method_type: One of:
                - "clopper_pearson" (exact binomial CI)
                - "wilson" (Wilson score CI)
                - "brookmeyer_crowley" (median survival CI)
                - "greenwood" (KM survival CI)
                - "all" (returns all methods)
        """
        if method_type == "all":
            content = self.CONFIDENCE_INTERVALS
        else:
            content = self.CONFIDENCE_INTERVALS.get(method_type, {})

        self._log_retrieval("get_confidence_interval_methods", method_type, "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=content,
            source_file="methodology_knowledge_base.py",
            source_key=f"CONFIDENCE_INTERVALS['{method_type}']"
        )

    def get_pro_qol_analysis(self) -> KBRetrievalResult:
        """Get PRO/QoL (Patient-Reported Outcomes / Quality of Life) analysis specifications."""
        self._log_retrieval("get_pro_qol_analysis", "all", "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=self.PRO_QOL,
            source_file="methodology_knowledge_base.py",
            source_key="PRO_QOL_ANALYSIS"
        )

    def get_analysis_windows(self) -> KBRetrievalResult:
        """Get analysis window specifications (visit windows, on-treatment period definitions)."""
        self._log_retrieval("get_analysis_windows", "all", "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=self.ANALYSIS_WINDOWS,
            source_file="methodology_knowledge_base.py",
            source_key="ANALYSIS_WINDOWS"
        )

    def get_data_cutoff_specs(self) -> KBRetrievalResult:
        """Get data cutoff specifications (clinical cutoff date rules, database lock procedures)."""
        self._log_retrieval("get_data_cutoff_specs", "all", "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=self.DATA_CUTOFF,
            source_file="methodology_knowledge_base.py",
            source_key="DATA_CUTOFF_SPECIFICATIONS"
        )

    def get_cml_criteria(self) -> KBRetrievalResult:
        """Get CML (Chronic Myeloid Leukemia) response criteria per ELN recommendations."""
        self._log_retrieval("get_cml_criteria", "all", "oncology_reference_data.py")

        return KBRetrievalResult(
            content=self.CML_CRITERIA,
            source_file="oncology_reference_data.py",
            source_key="CML_CRITERIA"
        )

    def get_iwcll_criteria(self) -> KBRetrievalResult:
        """Get iwCLL (International Workshop on CLL) response criteria for CLL trials."""
        self._log_retrieval("get_iwcll_criteria", "all", "oncology_reference_data.py")

        return KBRetrievalResult(
            content=self.IWCLL_CRITERIA,
            source_file="oncology_reference_data.py",
            source_key="IWCLL_CRITERIA"
        )

    def get_organ_function_scores(self, score_type: str = "all") -> KBRetrievalResult:
        """
        Get organ function scoring systems.

        Args:
            score_type: One of:
                - "child_pugh" (hepatic function)
                - "meld" (hepatic function - Model for End-Stage Liver Disease)
                - "ckd_epi" (renal function - CKD-EPI eGFR)
                - "cockcroft_gault" (renal function - creatinine clearance)
                - "all" (returns all scoring systems)
        """
        if score_type == "all":
            content = self.ORGAN_FUNCTION_SCORES
        else:
            content = self.ORGAN_FUNCTION_SCORES.get(score_type, {})

        self._log_retrieval("get_organ_function_scores", score_type, "oncology_reference_data.py")

        return KBRetrievalResult(
            content=content,
            source_file="oncology_reference_data.py",
            source_key=f"ORGAN_FUNCTION_SCORES['{score_type}']"
        )

    def get_listings(self) -> KBRetrievalResult:
        """Get patient listing templates (subject-level data listings)."""
        self._log_retrieval("get_listings", "all", "complete_tfl_inventory.py")

        return KBRetrievalResult(
            content=self.LISTINGS,
            source_file="complete_tfl_inventory.py",
            source_key="LISTINGS"
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
    # v67: DESIGN-SPECIFIC TFL TOOLS
    # =========================================================================

    def get_single_arm_tables(self) -> KBRetrievalResult:
        """
        Get TFL templates for SINGLE-ARM studies.

        These templates have:
        - No randomization in CONSORT diagram
        - Single treatment column (no comparator)
        - Clopper-Pearson CI for response rates
        - No hazard ratios or treatment comparisons

        Call this for Phase 2 single-arm studies, CAR-T studies, etc.
        """
        self._log_retrieval("get_single_arm_tables", "all", "complete_tfl_inventory.py")

        return KBRetrievalResult(
            content=self.SINGLE_ARM_TABLES,
            source_file="complete_tfl_inventory.py",
            source_key="SINGLE_ARM_DISPOSITION_TABLES"
        )

    def get_lymphoma_tables(self) -> KBRetrievalResult:
        """
        Get TFL templates for LYMPHOMA studies (NHL, HL, CLL, etc.).

        These templates have:
        - Ann Arbor staging (I, II, III, IV) - NOT M1a/M1b/M1c
        - Lugano Classification response (NOT RECIST)
        - FLIPI/IPI prognostic scores
        - Deauville score for PET response
        - NO BRAF mutation, NO solid tumor staging

        Call this for any hematologic/lymphoma trial.
        """
        self._log_retrieval("get_lymphoma_tables", "all", "complete_tfl_inventory.py")

        content = {
            "baseline_tables": self.LYMPHOMA_BASELINE_TABLES,
            "efficacy_tables": self.LYMPHOMA_EFFICACY_TABLES,
            "notes": {
                "staging": "Use Ann Arbor staging (I, II, III, IV with A/B modifiers)",
                "response_criteria": "Use Lugano Classification {Cheson 2014}",
                "not_applicable": ["M1a/M1b/M1c staging", "BRAF mutation", "TNM staging", "RECIST 1.1"]
            }
        }

        return KBRetrievalResult(
            content=content,
            source_file="complete_tfl_inventory.py",
            source_key="LYMPHOMA_BASELINE_TABLES + LYMPHOMA_EFFICACY_TABLES"
        )

    def get_cart_tables(self) -> KBRetrievalResult:
        """
        Get TFL templates for CAR-T CELL THERAPY studies.

        These templates include:
        - CRS (Cytokine Release Syndrome) summary tables with ASTCT grading
        - ICANS (neurotoxicity) summary tables with ICE score
        - CAR-T cellular kinetics (Cmax, AUC, persistence)
        - Prolonged cytopenias, infections, hypogammaglobulinemia
        - Retreatment response and DORR (if applicable)
        - NO dose modification tables (single infusion)

        Call this for any CAR-T or cell therapy trial.
        """
        self._log_retrieval("get_cart_tables", "all", "complete_tfl_inventory.py")

        content = {
            "safety_tables": self.CAR_T_SAFETY_TABLES,
            "retreatment_tables": self.CAR_T_RETREATMENT_TABLES,
            "notes": {
                "crs_grading": "ASTCT 2019 Consensus {Lee 2019}",
                "icans_grading": "ICE Score (ASTCT 2019)",
                "not_applicable": ["Dose modification tables", "Dose reduction tables"]
            }
        }

        return KBRetrievalResult(
            content=content,
            source_file="complete_tfl_inventory.py",
            source_key="CAR_T_SAFETY_TABLES + CAR_T_RETREATMENT_TABLES"
        )

    def get_oncology_tfl_templates(self, template_type: str = "all") -> KBRetrievalResult:
        """
        Get oncology-specific TFL templates for efficacy and safety.

        Args:
            template_type: One of "efficacy", "safety", or "all" (default)

        Contains:
            - EFFICACY_TFL_TEMPLATES: OS tables, exploratory endpoints, endpoint specifications
            - SAFETY_TFL_TEMPLATES: AE by visit, AE leading to modification
        """
        if template_type == "efficacy":
            content = self.ONCOLOGY_TFL_TEMPLATES.get("efficacy", {})
            source_key = "EFFICACY_TFL_TEMPLATES"
        elif template_type == "safety":
            content = self.ONCOLOGY_TFL_TEMPLATES.get("safety", {})
            source_key = "SAFETY_TFL_TEMPLATES"
        else:
            content = self.ONCOLOGY_TFL_TEMPLATES
            source_key = "EFFICACY_TFL_TEMPLATES + SAFETY_TFL_TEMPLATES"

        self._log_retrieval("get_oncology_tfl_templates", template_type, "oncology_reference_data.py")

        return KBRetrievalResult(
            content=content,
            source_file="oncology_reference_data.py",
            source_key=source_key
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
    # DISEASE-SPECIFIC RESPONSE CRITERIA TOOLS
    # =========================================================================

    def get_response_criteria(self, criteria_name: str) -> KBRetrievalResult:
        """
        Get disease-specific response criteria.

        Args:
            criteria_name: One of:
                - "RECIST" (solid tumors - already in production_sap_specifications)
                - "Lugano" (Hodgkin and Non-Hodgkin Lymphoma)
                - "IMWG" (Multiple Myeloma)
                - "irRECIST" (Immunotherapy - modified RECIST)
                - "iRECIST" (Immunotherapy - RECIST Working Group official)
                - "RANO" (Brain tumors / High-grade glioma)
                - "RANO_BM" (Brain metastases)
                - "PCWG3" (Prostate cancer)
                - "GCIG_CA125" (Ovarian cancer CA-125 response)

        Returns:
            Complete response criteria with categories, measurement rules, timepoints
        """
        # Handle RECIST from production specs
        if criteria_name.upper() == "RECIST":
            self._log_retrieval("get_response_criteria", criteria_name, "production_sap_specifications.py")
            return KBRetrievalResult(
                content=self.RECIST_SPECIFICATIONS,
                source_file="production_sap_specifications.py",
                source_key="RECIST_SPECIFICATIONS"
            )

        # Handle disease-specific criteria
        criteria = self.DISEASE_CRITERIA.get(criteria_name)
        if criteria:
            self._log_retrieval("get_response_criteria", criteria_name, "disease_specific_criteria.py")
            return KBRetrievalResult(
                content=criteria,
                source_file="disease_specific_criteria.py",
                source_key=f"{criteria_name}_CRITERIA"
            )

        # Return available options if not found
        available = list(self.DISEASE_CRITERIA.keys()) + ["RECIST"]
        return KBRetrievalResult(
            content={"error": f"Unknown criteria: {criteria_name}", "available": available},
            source_file="disease_specific_criteria.py",
            source_key="error"
        )

    def get_all_response_criteria(self) -> KBRetrievalResult:
        """Get list of all available response criteria with brief descriptions."""
        criteria_list = [
            {"name": "RECIST", "indication": "Solid tumors", "source": "production_sap_specifications.py"},
            {"name": "Lugano", "indication": "Hodgkin and Non-Hodgkin Lymphoma", "source": "disease_specific_criteria.py"},
            {"name": "IMWG", "indication": "Multiple Myeloma", "source": "disease_specific_criteria.py"},
            {"name": "irRECIST", "indication": "Immunotherapy (modified RECIST)", "source": "disease_specific_criteria.py"},
            {"name": "iRECIST", "indication": "Immunotherapy (RECIST WG official)", "source": "disease_specific_criteria.py"},
            {"name": "RANO", "indication": "Brain tumors / High-grade glioma", "source": "disease_specific_criteria.py"},
            {"name": "RANO_BM", "indication": "Brain metastases", "source": "disease_specific_criteria.py"},
            {"name": "PCWG3", "indication": "Prostate cancer", "source": "disease_specific_criteria.py"},
            {"name": "GCIG_CA125", "indication": "Ovarian cancer (CA-125)", "source": "disease_specific_criteria.py"}
        ]
        self._log_retrieval("get_all_response_criteria", "all", "disease_specific_criteria.py")
        return KBRetrievalResult(
            content=criteria_list,
            source_file="disease_specific_criteria.py",
            source_key="ALL_CRITERIA"
        )

    # =========================================================================
    # CAR-T / CELL THERAPY TOOLS
    # =========================================================================

    def get_cart_specifications(self) -> KBRetrievalResult:
        """
        Get CAR-T cell therapy specifications including:
        - CRS grading (ASTCT 2019 Consensus, grades 1-4)
        - ICANS grading (ICE score for >=12 years, CAPD for <12 years)
        - Cellular kinetics endpoints (Cmax, persistence, B-cell aplasia)
        - Safety monitoring requirements
        - Step-up dosing considerations

        Use for any CAR-T, TCR-T, or adoptive cell therapy trial.
        """
        self._log_retrieval("get_cart_specifications", "CAR_T_MODULE", "oncology_reference_data.py")
        return KBRetrievalResult(
            content=self.CAR_T_MODULE,
            source_file="oncology_reference_data.py",
            source_key="CAR_T_MODULE"
        )

    def get_bispecific_specifications(self) -> KBRetrievalResult:
        """
        Get bispecific antibody specifications including:
        - CRS monitoring (similar to CAR-T but generally lower risk)
        - Step-up dosing requirements
        - Common endpoints (ORR by IRC, DOR, PFS)
        """
        self._log_retrieval("get_bispecific_specifications", "BISPECIFIC_MODULE", "oncology_reference_data.py")
        return KBRetrievalResult(
            content=self.BISPECIFIC_MODULE,
            source_file="oncology_reference_data.py",
            source_key="BISPECIFIC_ANTIBODY_MODULE"
        )

    def get_adc_specifications(self) -> KBRetrievalResult:
        """
        Get ADC (Antibody-Drug Conjugate) specifications including:
        - Ocular toxicity monitoring
        - Neuropathy assessments
        - Common efficacy endpoints
        """
        self._log_retrieval("get_adc_specifications", "ADC_MODULE", "oncology_reference_data.py")
        return KBRetrievalResult(
            content=self.ADC_MODULE,
            source_file="oncology_reference_data.py",
            source_key="ADC_MODULE"
        )

    # =========================================================================
    # STUDY TYPE TEMPLATE TOOLS
    # =========================================================================

    def get_study_type_template(self, study_type: str) -> KBRetrievalResult:
        """
        Get study type-specific template.

        Args:
            study_type: One of:
                - "adjuvant" (post-surgical, DFS/RFS endpoints)
                - "neoadjuvant" (pre-surgical, pCR endpoints)
                - "basket" (multiple tumor types, single biomarker)
                - "umbrella" (single tumor type, multiple biomarkers)

        Returns:
            Template with appropriate endpoints, populations, and analysis methods
        """
        template = self.STUDY_TYPE_TEMPLATES.get(study_type.lower())
        if template:
            self._log_retrieval("get_study_type_template", study_type, "oncology_reference_data.py")
            return KBRetrievalResult(
                content=template,
                source_file="oncology_reference_data.py",
                source_key=f"{study_type.upper()}_TRIAL_TEMPLATE"
            )

        available = list(self.STUDY_TYPE_TEMPLATES.keys())
        return KBRetrievalResult(
            content={"error": f"Unknown study type: {study_type}", "available": available},
            source_file="oncology_reference_data.py",
            source_key="error"
        )

    # =========================================================================
    # BIOMARKER AND PROGNOSTIC TOOLS
    # =========================================================================

    def get_biomarker_endpoints(self) -> KBRetrievalResult:
        """
        Get biomarker endpoint specifications including:
        - PD-L1 expression cutoffs and assays
        - TMB (tumor mutational burden) thresholds
        - MSI/dMMR definitions
        - ctDNA endpoints
        """
        self._log_retrieval("get_biomarker_endpoints", "BIOMARKER_ENDPOINTS", "oncology_reference_data.py")
        return KBRetrievalResult(
            content=self.BIOMARKER_ENDPOINTS,
            source_file="oncology_reference_data.py",
            source_key="BIOMARKER_ENDPOINTS"
        )

    def get_performance_status_scales(self) -> KBRetrievalResult:
        """
        Get performance status scales including:
        - ECOG (0-5)
        - Karnofsky (0-100)
        - Lansky (pediatric)
        """
        self._log_retrieval("get_performance_status_scales", "PERFORMANCE_STATUS_SCALES", "oncology_reference_data.py")
        return KBRetrievalResult(
            content=self.PERFORMANCE_STATUS_SCALES,
            source_file="oncology_reference_data.py",
            source_key="PERFORMANCE_STATUS_SCALES"
        )

    def get_prognostic_scores(self) -> KBRetrievalResult:
        """
        Get prognostic scoring systems including:
        - IPI (International Prognostic Index) for NHL
        - ISS/R-ISS for myeloma
        - IMDC for RCC
        - FLIPI for follicular lymphoma
        """
        self._log_retrieval("get_prognostic_scores", "PROGNOSTIC_SCORES", "oncology_reference_data.py")
        return KBRetrievalResult(
            content=self.PROGNOSTIC_SCORES,
            source_file="oncology_reference_data.py",
            source_key="PROGNOSTIC_SCORES"
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
            # Statistical Methods
            {"name": "get_statistical_method", "description": "Get statistical method specification (Cox, KM, log-rank, etc.)"},
            {"name": "get_missing_data_method", "description": "Get missing data handling specification (MI, MMRM, etc.)"},
            {"name": "get_sensitivity_analysis", "description": "Get sensitivity analyses for endpoint type"},
            {"name": "get_stratification_specs", "description": "Get stratification specifications"},
            {"name": "get_multiplicity_adjustment", "description": "Get multiplicity adjustment method"},
            {"name": "get_subgroup_analysis_specs", "description": "Get subgroup analysis specifications"},
            # TFL Templates
            {"name": "get_table_template", "description": "Get specific table shell by ID"},
            {"name": "get_disposition_tables", "description": "Get all disposition tables (CONSORT, demographics)"},
            {"name": "get_efficacy_tables", "description": "Get all efficacy tables (PFS, OS, ORR)"},
            {"name": "get_safety_tables", "description": "Get all safety tables (AE, labs)"},
            {"name": "get_figure_template", "description": "Get specific figure template by ID"},
            {"name": "get_all_figures", "description": "Get all figure templates"},
            # Specifications
            {"name": "get_adam_dataset_spec", "description": "Get ADaM dataset specification"},
            {"name": "get_data_handling_rules", "description": "Get data handling conventions"},
            {"name": "get_programming_specifications", "description": "Get programming specifications"},
            {"name": "get_estimand_framework", "description": "Get ICH E9(R1) estimands framework"},
            {"name": "get_recist_specifications", "description": "Get RECIST 1.1 specifications"},
            {"name": "get_safety_specifications", "description": "Get safety analysis specifications"},
            {"name": "get_study_design_specs", "description": "Get study design specifications"},
            # Trial Precedent
            {"name": "get_similar_trials", "description": "Find similar trials from 354-trial KG for precedent (censoring, multiplicity, methods)"},
            # Disease-Specific Response Criteria (NEW)
            {"name": "get_response_criteria", "description": "Get disease-specific response criteria (Lugano, IMWG, irRECIST, iRECIST, RANO, PCWG3, GCIG)"},
            {"name": "get_all_response_criteria", "description": "List all available response criteria systems"},
            # CAR-T / Cell Therapy (NEW)
            {"name": "get_cart_specifications", "description": "Get CAR-T specs (CRS grading, ICANS, cellular kinetics)"},
            {"name": "get_bispecific_specifications", "description": "Get bispecific antibody specs (CRS, step-up dosing)"},
            {"name": "get_adc_specifications", "description": "Get ADC specs (ocular toxicity, neuropathy)"},
            # Study Type Templates (NEW)
            {"name": "get_study_type_template", "description": "Get study type template (adjuvant, neoadjuvant, basket, umbrella)"},
            # Biomarkers and Prognostic (NEW)
            {"name": "get_biomarker_endpoints", "description": "Get biomarker endpoints (PD-L1, TMB, MSI, ctDNA)"},
            {"name": "get_performance_status_scales", "description": "Get performance status scales (ECOG, Karnofsky, Lansky)"},
            {"name": "get_prognostic_scores", "description": "Get prognostic scores (IPI, ISS, IMDC, FLIPI)"},
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
            "name": "get_censoring_rules",
            "description": "Get censoring rules for time-to-event endpoints (PFS, OS, DFS, DOR). Specifies when patients are censored vs counted as events. ESSENTIAL for Section 8 (Censoring Rules).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "endpoint_type": {
                        "type": "string",
                        "description": "The time-to-event endpoint type",
                        "enum": ["pfs", "os", "dfs", "efs", "dor", "ttf", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_interim_analysis",
            "description": "Get interim analysis specifications including DMC charter, alpha spending functions (O'Brien-Fleming, Lan-DeMets), efficacy/futility boundaries. ESSENTIAL for Section 11 (Interim Analysis).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "analysis_type": {
                        "type": "string",
                        "description": "The type of interim analysis specification",
                        "enum": ["dmc_charter", "efficacy_interim", "os_interim_at_pfs_final", "sample_size_re_estimation", "alpha_spending", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_population_definitions",
            "description": "Get standard analysis population definitions (ITT, mITT, Safety, Per-Protocol, Evaluable, PK, DLT-Evaluable). ESSENTIAL for Section 4 (Analysis Populations).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "population_type": {
                        "type": "string",
                        "description": "The population type",
                        "enum": ["itt", "mitt", "safety", "per_protocol", "evaluable", "pharmacokinetic", "dlt_evaluable", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_derived_variables",
            "description": "Get derived variable specifications for ADaM datasets (baseline flags, treatment flags, time variables).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "variable_type": {
                        "type": "string",
                        "description": "The variable type",
                        "enum": ["baseline_flags", "treatment_flags", "time_variables", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_time_to_event_analysis",
            "description": "Get time-to-event analysis specifications (Kaplan-Meier, Cox PH, competing risks, landmark analysis).",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_confidence_interval_methods",
            "description": "Get confidence interval calculation methods (Clopper-Pearson, Wilson, Brookmeyer-Crowley, Greenwood).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "method_type": {
                        "type": "string",
                        "description": "The CI method type",
                        "enum": ["clopper_pearson", "wilson", "brookmeyer_crowley", "greenwood", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_pro_qol_analysis",
            "description": "Get PRO/QoL (Patient-Reported Outcomes / Quality of Life) analysis specifications.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_analysis_windows",
            "description": "Get analysis window specifications (visit windows, on-treatment period definitions, baseline windows).",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_data_cutoff_specs",
            "description": "Get data cutoff specifications (clinical cutoff date rules, database lock procedures, interim data cuts).",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_cml_criteria",
            "description": "Get CML (Chronic Myeloid Leukemia) response criteria per ELN 2020 recommendations.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_iwcll_criteria",
            "description": "Get iwCLL (International Workshop on CLL) response criteria for chronic lymphocytic leukemia trials.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_organ_function_scores",
            "description": "Get organ function scoring systems (Child-Pugh, MELD, CKD-EPI eGFR, Cockcroft-Gault).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "score_type": {
                        "type": "string",
                        "description": "The organ function score type",
                        "enum": ["child_pugh", "meld", "ckd_epi", "cockcroft_gault", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_listings",
            "description": "Get patient listing templates (subject-level data listings for appendices).",
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
        },
        # =====================================================================
        # DISEASE-SPECIFIC RESPONSE CRITERIA (NEW)
        # =====================================================================
        {
            "name": "get_response_criteria",
            "description": "Get disease-specific response criteria. Use this for non-RECIST tumor types like lymphoma (Lugano), myeloma (IMWG), prostate (PCWG3), brain tumors (RANO), immunotherapy (irRECIST/iRECIST), or ovarian (GCIG CA-125).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "criteria_name": {
                        "type": "string",
                        "description": "The response criteria system",
                        "enum": ["RECIST", "Lugano", "IMWG", "irRECIST", "iRECIST", "RANO", "RANO_BM", "PCWG3", "GCIG_CA125"]
                    }
                },
                "required": ["criteria_name"]
            }
        },
        {
            "name": "get_all_response_criteria",
            "description": "List all available response criteria systems with their indications. Use this to see what options are available.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        # =====================================================================
        # CAR-T / CELL THERAPY (NEW)
        # =====================================================================
        {
            "name": "get_cart_specifications",
            "description": "Get CAR-T cell therapy specifications including ASTCT CRS grading (grades 1-4), ICANS grading (ICE score), cellular kinetics endpoints (Cmax, persistence, B-cell aplasia), and safety monitoring. Use for any CAR-T, TCR-T, or adoptive cell therapy trial.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_bispecific_specifications",
            "description": "Get bispecific antibody specifications including CRS monitoring, step-up dosing, and common endpoints. Use for bispecific T-cell engagers (BiTEs) like blinatumomab.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_adc_specifications",
            "description": "Get ADC (Antibody-Drug Conjugate) specifications including ocular toxicity monitoring, neuropathy assessments, and common efficacy endpoints.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        # =====================================================================
        # STUDY TYPE TEMPLATES (NEW)
        # =====================================================================
        {
            "name": "get_study_type_template",
            "description": "Get study type-specific template with appropriate endpoints, populations, and methods. Use this for adjuvant (DFS/RFS), neoadjuvant (pCR), basket, or umbrella trials.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "study_type": {
                        "type": "string",
                        "description": "The study type",
                        "enum": ["adjuvant", "neoadjuvant", "basket", "umbrella"]
                    }
                },
                "required": ["study_type"]
            }
        },
        # =====================================================================
        # BIOMARKER AND PROGNOSTIC (NEW)
        # =====================================================================
        {
            "name": "get_biomarker_endpoints",
            "description": "Get biomarker endpoint specifications including PD-L1 expression cutoffs, TMB thresholds, MSI/dMMR definitions, and ctDNA endpoints.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_performance_status_scales",
            "description": "Get performance status scales including ECOG (0-5), Karnofsky (0-100), and Lansky (pediatric).",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_prognostic_scores",
            "description": "Get prognostic scoring systems including IPI (NHL), ISS/R-ISS (myeloma), IMDC (RCC), and FLIPI (follicular lymphoma).",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        # =====================================================================
        # v67: DESIGN-SPECIFIC TFL TEMPLATES (NEW)
        # =====================================================================
        {
            "name": "get_single_arm_tables",
            "description": "Get TFL templates for SINGLE-ARM studies. These have NO randomization, NO comparator columns, and use Clopper-Pearson CI. Use for Phase 2 single-arm or CAR-T trials.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_lymphoma_tables",
            "description": "Get TFL templates for LYMPHOMA studies (NHL, HL, CLL). These use Ann Arbor staging (I-IV), Lugano response criteria, FLIPI/IPI scores, and Deauville PET scoring. NO BRAF, NO TNM staging, NO RECIST.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_cart_tables",
            "description": "Get TFL templates specifically for CAR-T studies. Includes CRS summary (ASTCT grading), ICANS summary (ICE score), cellular kinetics tables, prolonged cytopenias, infections, B-cell aplasia, and retreatment/DORR tables. NO dose modification tables.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_oncology_tfl_templates",
            "description": "Get oncology-specific TFL templates for efficacy and safety. Includes OS tables at 5 years, exploratory endpoint specifications, endpoint variable specifications (PFS/OS/ORR/DOR definitions with events and censoring), AE by visit tables, and AE leading to dose modification.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "template_type": {
                        "type": "string",
                        "description": "Type of templates: 'efficacy', 'safety', or 'all' (default)",
                        "enum": ["efficacy", "safety", "all"]
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
        # Statistical Methods
        "get_statistical_method": lambda: kb.get_statistical_method(tool_input.get("method_name", "")),
        "get_missing_data_method": lambda: kb.get_missing_data_method(tool_input.get("method_name", "")),
        "get_sensitivity_analysis": lambda: kb.get_sensitivity_analysis(tool_input.get("endpoint_type", "")),
        "get_multiplicity_adjustment": lambda: kb.get_multiplicity_adjustment(tool_input.get("method_name", "")),
        "get_stratification_specs": lambda: kb.get_stratification_specs(),
        "get_subgroup_analysis_specs": lambda: kb.get_subgroup_analysis_specs(),
        "get_censoring_rules": lambda: kb.get_censoring_rules(tool_input.get("endpoint_type", "all")),
        "get_interim_analysis": lambda: kb.get_interim_analysis(tool_input.get("analysis_type", "all")),
        "get_population_definitions": lambda: kb.get_population_definitions(tool_input.get("population_type", "all")),
        # TFL Templates
        "get_table_template": lambda: kb.get_table_template(tool_input.get("table_id", "")),
        "get_disposition_tables": lambda: kb.get_disposition_tables(),
        "get_efficacy_tables": lambda: kb.get_efficacy_tables(),
        "get_safety_tables": lambda: kb.get_safety_tables(),
        "get_all_figures": lambda: kb.get_all_figures(),
        # Specifications
        "get_estimand_framework": lambda: kb.get_estimand_framework(),
        "get_adam_dataset_spec": lambda: kb.get_adam_dataset_spec(tool_input.get("dataset_name", "")),
        "get_recist_specifications": lambda: kb.get_recist_specifications(),
        "get_safety_specifications": lambda: kb.get_safety_specifications(),
        "get_data_handling_rules": lambda: kb.get_data_handling_rules(),
        # Trial Precedent
        "get_similar_trials": lambda: kb.get_similar_trials(
            phase=tool_input.get("phase"),
            indication=tool_input.get("indication"),
            endpoint_type=tool_input.get("endpoint_type"),
            design_type=tool_input.get("design_type")
        ),
        # Disease-Specific Response Criteria (NEW)
        "get_response_criteria": lambda: kb.get_response_criteria(tool_input.get("criteria_name", "")),
        "get_all_response_criteria": lambda: kb.get_all_response_criteria(),
        # CAR-T / Cell Therapy (NEW)
        "get_cart_specifications": lambda: kb.get_cart_specifications(),
        "get_bispecific_specifications": lambda: kb.get_bispecific_specifications(),
        "get_adc_specifications": lambda: kb.get_adc_specifications(),
        # Study Type Templates (NEW)
        "get_study_type_template": lambda: kb.get_study_type_template(tool_input.get("study_type", "")),
        # Biomarker and Prognostic (NEW)
        "get_biomarker_endpoints": lambda: kb.get_biomarker_endpoints(),
        "get_performance_status_scales": lambda: kb.get_performance_status_scales(),
        "get_prognostic_scores": lambda: kb.get_prognostic_scores(),
        # Complete KB Coverage (v64)
        "get_derived_variables": lambda: kb.get_derived_variables(tool_input.get("variable_type", "all")),
        "get_time_to_event_analysis": lambda: kb.get_time_to_event_analysis(tool_input.get("analysis_type", "all")),
        "get_confidence_interval_methods": lambda: kb.get_confidence_interval_methods(tool_input.get("ci_type", "all")),
        "get_pro_qol_analysis": lambda: kb.get_pro_qol_analysis(tool_input.get("instrument", "all")),
        "get_analysis_windows": lambda: kb.get_analysis_windows(tool_input.get("window_type", "all")),
        "get_data_cutoff_specs": lambda: kb.get_data_cutoff_specs(),
        "get_cml_criteria": lambda: kb.get_cml_criteria(),
        "get_iwcll_criteria": lambda: kb.get_iwcll_criteria(),
        "get_organ_function_scores": lambda: kb.get_organ_function_scores(tool_input.get("score_type", "all")),
        "get_listings": lambda: kb.get_listings(tool_input.get("listing_type", "all")),
        # v67: Design-specific TFL templates
        "get_single_arm_tables": lambda: kb.get_single_arm_tables(),
        "get_lymphoma_tables": lambda: kb.get_lymphoma_tables(),
        "get_cart_tables": lambda: kb.get_cart_tables(),
        "get_oncology_tfl_templates": lambda: kb.get_oncology_tfl_templates(tool_input.get("template_type", "all")),
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
