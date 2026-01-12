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
    """Result from knowledge base retrieval with provenance and source traceability."""
    content: Any
    source_file: str
    source_key: str
    retrieved_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source_trials: List[str] = field(default_factory=list)
    regulatory_sources: List[str] = field(default_factory=list)
    source_note: str = ""

    def __post_init__(self):
        """Auto-populate source information from kb_source_mapping if not provided."""
        if not self.source_trials and not self.regulatory_sources:
            try:
                from kb_source_mapping import get_sources
                # Try to get sources for the source_key
                sources = get_sources(self.source_key)
                self.source_trials = sources.get("trials", [])
                self.regulatory_sources = sources.get("regulatory", [])
                self.source_note = sources.get("note", "")
            except ImportError:
                pass  # Source mapping not available

    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "provenance": {
                "source_file": self.source_file,
                "source_key": self.source_key,
                "retrieved_at": self.retrieved_at,
                "source_trials": self.source_trials,
                "regulatory_sources": self.regulatory_sources,
                "source_note": self.source_note
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

        # Load extended ADaM specifications (ADEX, ADVS, ADEG, ADPR, ADCM, ADMH)
        try:
            from .adam_specifications import (
                ADEX_SPECIFICATION,
                ADVS_SPECIFICATION,
                ADEG_SPECIFICATION,
                ADPR_SPECIFICATION,
                ADCM_SPECIFICATION,
                ADMH_SPECIFICATION
            )
            self.EXTENDED_ADAM_SPECS = {
                "adex": ADEX_SPECIFICATION,
                "advs": ADVS_SPECIFICATION,
                "adeg": ADEG_SPECIFICATION,
                "adpr": ADPR_SPECIFICATION,
                "adcm": ADCM_SPECIFICATION,
                "admh": ADMH_SPECIFICATION
            }
        except ImportError:
            try:
                from adam_specifications import (
                    ADEX_SPECIFICATION,
                    ADVS_SPECIFICATION,
                    ADEG_SPECIFICATION,
                    ADPR_SPECIFICATION,
                    ADCM_SPECIFICATION,
                    ADMH_SPECIFICATION
                )
                self.EXTENDED_ADAM_SPECS = {
                    "adex": ADEX_SPECIFICATION,
                    "advs": ADVS_SPECIFICATION,
                    "adeg": ADEG_SPECIFICATION,
                    "adpr": ADPR_SPECIFICATION,
                    "adcm": ADCM_SPECIFICATION,
                    "admh": ADMH_SPECIFICATION
                }
            except ImportError:
                self.EXTENDED_ADAM_SPECS = {}

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

        # v70: Include regulatory_source in provenance for better traceability
        regulatory_source = content.get("regulatory_source", "") if isinstance(content, dict) else ""
        source_key = f"STATISTICAL_METHODS['{method_name}']"
        if regulatory_source:
            source_key = f"{regulatory_source}"  # Use actual regulatory source

        return KBRetrievalResult(
            content=content,
            source_file="methodology_knowledge_base.py",
            source_key=source_key
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

        # v70: Include regulatory_source in provenance
        regulatory_source = content.get("regulatory_source", "") if isinstance(content, dict) else ""
        source_key = f"CENSORING_RULES['{endpoint_type}']"
        if regulatory_source:
            source_key = f"{regulatory_source}"

        return KBRetrievalResult(
            content=content,
            source_file="methodology_knowledge_base.py",
            source_key=source_key
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
                "IMPORTANT": "PROTOCOL-SPECIFIED GRADING TAKES PRECEDENCE over these defaults",
                "crs_grading_options": {
                    "ASTCT_2019": "ASTCT 2019 Consensus {Lee 2019} - newer standard",
                    "Lee_2014_modified": "Modified Lee et al. 2014 criteria - used by older axicabtagene/ZUMA studies",
                    "check_protocol": "Use EXACTLY what the protocol/IB specifies"
                },
                "neurologic_grading_options": {
                    "ICANS_ICE": "ICE Score (ASTCT 2019) - if protocol uses ICANS",
                    "separate_CTCAE": "Neurologic AEs graded per CTCAE separately from CRS - if protocol says 'not part of CRS'"
                },
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
            dataset_name: One of:
                - Core: "adsl", "adae", "adtte", "adrs", "adlb"
                - Extended: "adex", "advs", "adeg", "adpr", "adcm", "admh"
        """
        ds_lower = dataset_name.lower()

        # Check core specifications first
        content = self.ADAM_SPECIFICATIONS.get(ds_lower, {})
        source_file = "production_sap_specifications.py"

        # If not found, check extended specifications
        if not content and hasattr(self, 'EXTENDED_ADAM_SPECS'):
            content = self.EXTENDED_ADAM_SPECS.get(ds_lower, {})
            source_file = "adam_specifications.py"

        self._log_retrieval("get_adam_dataset_spec", dataset_name, source_file)

        return KBRetrievalResult(
            content=content,
            source_file=source_file,
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

    def get_safety_analysis_specs(self, analysis_type: str = "all") -> KBRetrievalResult:
        """
        Get safety analysis specifications from methodology KB.

        Args:
            analysis_type: One of:
                - "adverse_events": AE analysis methods (TEAE, SAE, related AEs)
                - "exposure": Drug exposure analysis (duration, dose intensity)
                - "laboratory": Lab shift analysis, toxicity grading
                - "vital_signs": VS change from baseline methods
                - "ecg": ECG analysis (QTc prolongation, outliers)
                - "all": All safety analysis specifications (default)

        Returns:
            Safety analysis specifications including:
            - AE incidence calculations
            - MedDRA coding conventions
            - Exposure-adjusted rates
            - Lab toxicity grading (CTCAE)
            - Shift tables methodology
        """
        if analysis_type == "all":
            content = self.SAFETY_ANALYSIS_SPECIFICATIONS
            source_key = "SAFETY_ANALYSIS_SPECIFICATIONS"
        else:
            content = self.SAFETY_ANALYSIS_SPECIFICATIONS.get(analysis_type, {})
            source_key = f"SAFETY_ANALYSIS_SPECIFICATIONS['{analysis_type}']"

        self._log_retrieval("get_safety_analysis_specs", analysis_type, "methodology_knowledge_base.py")

        return KBRetrievalResult(
            content=content,
            source_file="methodology_knowledge_base.py",
            source_key=source_key
        )

    def get_tfl_shells(self, shell_type: str = "all") -> KBRetrievalResult:
        """
        Get TFL shell templates from production SAP specifications.

        Args:
            shell_type: One of:
                - "disposition": Subject disposition shells
                - "demographics": Demographics and baseline shells
                - "efficacy": Efficacy analysis shells
                - "safety": Safety analysis shells
                - "pk": Pharmacokinetic shells
                - "all": All TFL shells (default)

        Returns:
            TFL shell templates with:
            - Table/Figure/Listing structure
            - Column headers and row labels
            - Statistical presentation formats
            - Footnote conventions
        """
        if shell_type == "all":
            content = self.TFL_SHELLS
            source_key = "TFL_SHELLS"
        else:
            content = self.TFL_SHELLS.get(shell_type, {})
            source_key = f"TFL_SHELLS['{shell_type}']"

        self._log_retrieval("get_tfl_shells", shell_type, "production_sap_specifications.py")

        return KBRetrievalResult(
            content=content,
            source_file="production_sap_specifications.py",
            source_key=source_key
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
    # TTE DERIVATION & APPENDIX TOOLS
    # =========================================================================

    def get_tte_derivation_tables(self, endpoint: str = "all") -> KBRetrievalResult:
        """
        Get time-to-event derivation circumstance tables.

        Returns detailed circumstance tables for DOR, DORR, PFS, OS showing
        when subjects are events vs censored. Essential for Appendix A.2.

        Args:
            endpoint: "DOR", "DORR", "PFS", "OS", or "all"

        Returns:
            Circumstance tables with columns: situation, event (0/1), date
        """
        self._log_retrieval("get_tte_derivation_tables", endpoint, "oncology_reference_data.py")

        tte_rules = self.CAR_T_MODULE.get("tte_derivation_rules", {})

        if endpoint.upper() == "ALL":
            content = tte_rules
        else:
            content = tte_rules.get(endpoint.upper(), {})
            if not content:
                content = {"error": f"Unknown endpoint: {endpoint}", "available": list(tte_rules.keys())}

        return KBRetrievalResult(
            content=content,
            source_file="oncology_reference_data.py",
            source_key=f"CAR_T_MODULE['tte_derivation_rules']['{endpoint}']"
        )

    def get_meddra_search_strategies(self, category: str = "all") -> KBRetrievalResult:
        """
        Get MedDRA search strategies (SMQ, MST, HLGT) for safety analyses.

        Returns SMQ/MST specifications for AE categories like cytopenias,
        infections, CRS, ICANS, cardiac events, TLS. Essential for Appendix A.3.

        Args:
            category: "CRS", "thrombocytopenia", "neutropenia", "anemia",
                     "infections", "GVHD", "immunogenicity", "tumor_lysis_syndrome",
                     "cardiac_events", or "all"

        Returns:
            MedDRA search specifications including SMQ names, scopes, HLGTs
        """
        self._log_retrieval("get_meddra_search_strategies", category, "oncology_reference_data.py")

        meddra = self.CAR_T_MODULE.get("meddra_search_strategies", {})

        if category.lower() == "all":
            content = meddra
        else:
            content = meddra.get(category.lower(), meddra.get(category, {}))
            if not content:
                content = {"error": f"Unknown category: {category}", "available": list(meddra.keys())}

        # Add standard cardiac SMQs if requested
        if category.lower() in ["all", "cardiac", "cardiac_events"]:
            cardiac_smqs = {
                "cardiac_failure": {
                    "search_type": "SMQ",
                    "smq_name": "Cardiac failure",
                    "scope": "narrow"
                },
                "cardiac_arrhythmias": {
                    "search_type": "SMQ",
                    "smq_name": "Cardiac arrhythmias",
                    "scope": "narrow + broad"
                }
            }
            if category.lower() == "all":
                content.update(cardiac_smqs)
            else:
                content = cardiac_smqs

        return KBRetrievalResult(
            content=content,
            source_file="oncology_reference_data.py",
            source_key=f"CAR_T_MODULE['meddra_search_strategies']"
        )

    def get_concordance_analysis(self) -> KBRetrievalResult:
        """
        Get concordance analysis methodology (IRC vs Investigator agreement).

        Returns specifications for kappa statistics, percent agreement,
        and discordance analysis. Essential for blinded review comparison.

        Returns:
            Concordance analysis methods including kappa coefficient calculation
        """
        self._log_retrieval("get_concordance_analysis", "all", "kb_tools.py")

        concordance_specs = {
            "description": "Concordance analysis between IRC and Investigator assessments",
            "metrics": {
                "overall_percent_agreement": {
                    "formula": "(Number of concordant assessments / Total assessments) × 100",
                    "interpretation": "Proportion of cases where IRC and Investigator agree"
                },
                "kappa_coefficient": {
                    "formula": "κ = (Po - Pe) / (1 - Pe)",
                    "where": {
                        "Po": "Observed agreement proportion",
                        "Pe": "Expected agreement by chance"
                    },
                    "interpretation": {
                        "0.81-1.00": "Almost perfect agreement",
                        "0.61-0.80": "Substantial agreement",
                        "0.41-0.60": "Moderate agreement",
                        "0.21-0.40": "Fair agreement",
                        "0.00-0.20": "Slight agreement",
                        "<0.00": "Poor agreement (worse than chance)"
                    },
                    "ci_method": "95% CI using asymptotic variance"
                }
            },
            "output_tables": {
                "cross_tabulation": "2x2 table of IRC vs Investigator response categories",
                "discordance_summary": "Summary of discordant cases by category (e.g., IRC=CR vs Inv=PR)",
                "by_endpoint": "Separate concordance for ORR, BOR, CR rate"
            },
            "reference": "Cohen J. A coefficient of agreement for nominal scales. Educ Psychol Meas. 1960;20:37-46"
        }

        return KBRetrievalResult(
            content=concordance_specs,
            source_file="kb_tools.py",
            source_key="concordance_analysis"
        )

    def get_required_references(self, study_type: str = "oncology") -> KBRetrievalResult:
        """
        Get required references for SAP based on study type.

        Returns standard citations for response criteria, statistical methods,
        grading scales, and regulatory guidance. Essential for References section.

        Args:
            study_type: "oncology", "cart", "lymphoma", "solid_tumor", "hematologic"

        Returns:
            List of required references with full citations
        """
        self._log_retrieval("get_required_references", study_type, "kb_tools.py")

        # Core references for all oncology trials
        core_refs = {
            "statistical_methods": [
                {
                    "citation": "Kaplan EL, Meier P. Nonparametric estimation from incomplete observations. J Am Stat Assoc. 1958;53:457-481.",
                    "use_for": "Time-to-event analysis, survival curves"
                },
                {
                    "citation": "Cox DR. Regression models and life-tables. J R Stat Soc Ser B. 1972;34:187-220.",
                    "use_for": "Hazard ratio estimation"
                },
                {
                    "citation": "Clopper CJ, Pearson ES. The use of confidence or fiducial limits illustrated in the case of the binomial. Biometrika. 1934;26:404-413.",
                    "use_for": "Exact confidence intervals for response rates"
                },
                {
                    "citation": "Schemper M, Smith TL. A note on quantifying follow-up in studies of failure time. Control Clin Trials. 1996;17:343-346.",
                    "use_for": "Reverse Kaplan-Meier for follow-up time"
                }
            ],
            "regulatory": [
                {
                    "citation": "ICH E9 Statistical Principles for Clinical Trials. 1998.",
                    "use_for": "General statistical methodology"
                },
                {
                    "citation": "ICH E9(R1) Addendum on Estimands and Sensitivity Analysis. 2019.",
                    "use_for": "Estimand framework"
                }
            ],
            "safety_grading": [
                {
                    "citation": "National Cancer Institute. Common Terminology Criteria for Adverse Events (CTCAE) v5.0. 2017.",
                    "use_for": "Adverse event grading"
                }
            ]
        }

        # Solid tumor specific
        solid_tumor_refs = {
            "response_criteria": [
                {
                    "citation": "Eisenhauer EA, et al. New response evaluation criteria in solid tumours: Revised RECIST guideline (version 1.1). Eur J Cancer. 2009;45:228-247.",
                    "use_for": "RECIST 1.1 tumor response assessment"
                }
            ]
        }

        # Lymphoma specific
        lymphoma_refs = {
            "response_criteria": [
                {
                    "citation": "Cheson BD, et al. Recommendations for initial evaluation, staging, and response assessment of Hodgkin and non-Hodgkin lymphoma: The Lugano Classification. J Clin Oncol. 2014;32:3059-3068.",
                    "use_for": "Lugano 2014 response criteria for lymphoma"
                }
            ]
        }

        # CAR-T specific
        cart_refs = {
            "crs_grading": [
                {
                    "citation": "Lee DW, et al. Current concepts in the diagnosis and management of cytokine release syndrome. Blood. 2014;124:188-195.",
                    "use_for": "Lee 2014 CRS grading criteria"
                },
                {
                    "citation": "Lee DW, et al. ASTCT Consensus Grading for Cytokine Release Syndrome and Neurologic Toxicity Associated with Immune Effector Cells. Biol Blood Marrow Transplant. 2019;25:625-638.",
                    "use_for": "ASTCT 2019 CRS grading consensus"
                }
            ],
            "neurotoxicity": [
                {
                    "citation": "Topp MS, et al. Safety and activity of blinatumomab for adult patients with relapsed or refractory B-precursor acute lymphoblastic leukaemia. Lancet Oncol. 2015;16:57-66.",
                    "use_for": "Neurologic toxicity assessment (Topp 2015)"
                }
            ]
        }

        # Multiple myeloma
        myeloma_refs = {
            "response_criteria": [
                {
                    "citation": "Kumar S, et al. International Myeloma Working Group consensus criteria for response and minimal residual disease assessment in multiple myeloma. Lancet Oncol. 2016;17:e328-e346.",
                    "use_for": "IMWG response criteria"
                }
            ]
        }

        # Assemble based on study type
        content = {"core": core_refs}

        if study_type.lower() in ["solid_tumor", "oncology"]:
            content["response_criteria"] = solid_tumor_refs["response_criteria"]
        elif study_type.lower() in ["lymphoma", "dlbcl", "nhl"]:
            content["response_criteria"] = lymphoma_refs["response_criteria"]
        elif study_type.lower() in ["cart", "car-t", "cell_therapy"]:
            content["response_criteria"] = lymphoma_refs["response_criteria"]
            content["crs_grading"] = cart_refs["crs_grading"]
            content["neurotoxicity"] = cart_refs["neurotoxicity"]
        elif study_type.lower() in ["myeloma", "multiple_myeloma", "mm"]:
            content["response_criteria"] = myeloma_refs["response_criteria"]
        elif study_type.lower() in ["hematologic", "leukemia"]:
            content["response_criteria"] = []  # Varies by specific disease

        return KBRetrievalResult(
            content=content,
            source_file="kb_tools.py",
            source_key=f"required_references[{study_type}]"
        )

    def get_date_imputation_rules(self) -> KBRetrievalResult:
        """
        Get date imputation algorithm specifications.

        Returns detailed rules for imputing partial dates for AE start/stop,
        death dates, concomitant medications. Essential for Appendix A.1.

        Returns:
            Date imputation matrix with scenarios and rules
        """
        self._log_retrieval("get_date_imputation_rules", "all", "oncology_reference_data.py")

        date_rules = self.CAR_T_MODULE.get("date_imputation_rules", {})

        return KBRetrievalResult(
            content=date_rules,
            source_file="oncology_reference_data.py",
            source_key="CAR_T_MODULE['date_imputation_rules']"
        )

    # =========================================================================
    # COMPREHENSIVE SAP ELEMENTS (v76)
    # =========================================================================

    def get_study_definitions(self, definition_type: str = "all") -> KBRetrievalResult:
        """
        Get standard study definitions required for every SAP.

        Returns definitions for Study Day 0/baseline, on-study period, end of study,
        TEAE, follow-up time calculations - essential for Section 5 (DEFINITIONS).

        Args:
            definition_type: "time", "safety", "events", or "all"

        Returns:
            Standard study definitions with variants for different trial types
        """
        from .comprehensive_sap_elements import STUDY_DEFINITIONS
        self._log_retrieval("get_study_definitions", definition_type, "comprehensive_sap_elements.py")

        if definition_type == "all":
            content = STUDY_DEFINITIONS
        elif definition_type == "time":
            content = STUDY_DEFINITIONS.get("time_definitions", {})
        elif definition_type == "safety":
            content = STUDY_DEFINITIONS.get("safety_definitions", {})
        elif definition_type == "events":
            content = STUDY_DEFINITIONS.get("event_derivations", {})
        elif definition_type == "followup":
            content = STUDY_DEFINITIONS.get("follow_up_definitions", {})
        else:
            content = STUDY_DEFINITIONS

        return KBRetrievalResult(
            content=content,
            source_file="comprehensive_sap_elements.py",
            source_key=f"STUDY_DEFINITIONS['{definition_type}']"
        )

    def get_exposure_specifications(self, exposure_type: str = "all") -> KBRetrievalResult:
        """
        Get drug exposure analysis specifications.

        Returns specifications for BSA-adjusted dosing, weight-based dosing,
        relative dose intensity, CAR-T specific exposure metrics.

        Args:
            exposure_type: "dose", "bsa", "weight", "cart", or "all"

        Returns:
            Exposure analysis specifications with formulas and statistics
        """
        from .comprehensive_sap_elements import EXPOSURE_ANALYSIS
        self._log_retrieval("get_exposure_specifications", exposure_type, "comprehensive_sap_elements.py")

        if exposure_type == "all":
            content = EXPOSURE_ANALYSIS
        elif exposure_type == "dose":
            content = EXPOSURE_ANALYSIS.get("dose_summaries", {})
        elif exposure_type == "bsa":
            content = EXPOSURE_ANALYSIS.get("bsa_adjusted_dosing", {})
        elif exposure_type == "weight":
            content = EXPOSURE_ANALYSIS.get("weight_adjusted_dosing", {})
        elif exposure_type == "cart":
            content = EXPOSURE_ANALYSIS.get("cart_specific_exposure", {})
        else:
            content = EXPOSURE_ANALYSIS

        return KBRetrievalResult(
            content=content,
            source_file="comprehensive_sap_elements.py",
            source_key=f"EXPOSURE_ANALYSIS['{exposure_type}']"
        )

    def get_cart_manufacturing_specs(self) -> KBRetrievalResult:
        """
        Get CAR-T manufacturing and logistics metrics specifications.

        Returns specifications for leukapheresis timing, vein-to-vein time,
        manufacturing success rates, bridging therapy summaries.

        Returns:
            CAR-T manufacturing metrics with statistics and definitions
        """
        from .comprehensive_sap_elements import CART_MANUFACTURING_METRICS
        self._log_retrieval("get_cart_manufacturing_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=CART_MANUFACTURING_METRICS,
            source_file="comprehensive_sap_elements.py",
            source_key="CART_MANUFACTURING_METRICS"
        )

    def get_subsequent_therapy_specs(self) -> KBRetrievalResult:
        """
        Get subsequent anti-cancer therapy tracking specifications.

        Returns specifications for subsequent therapy summaries,
        subsequent SCT (autologous/allogeneic), time to next therapy.

        Returns:
            Subsequent therapy tracking specifications
        """
        from .comprehensive_sap_elements import SUBSEQUENT_THERAPY
        self._log_retrieval("get_subsequent_therapy_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=SUBSEQUENT_THERAPY,
            source_file="comprehensive_sap_elements.py",
            source_key="SUBSEQUENT_THERAPY"
        )

    def get_enrollment_specifications(self) -> KBRetrievalResult:
        """
        Get enrollment summary specifications.

        Returns specifications for enrollment by country, site, region,
        and enrollment over time displays.

        Returns:
            Enrollment summary specifications
        """
        from .comprehensive_sap_elements import ENROLLMENT_SUMMARIES
        self._log_retrieval("get_enrollment_specifications", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=ENROLLMENT_SUMMARIES,
            source_file="comprehensive_sap_elements.py",
            source_key="ENROLLMENT_SUMMARIES"
        )

    def get_ae_period_specifications(self) -> KBRetrievalResult:
        """
        Get adverse event period analysis specifications.

        Returns CAR-T specific periods (Day 0-30, 31-92, 93+) and
        standard on-treatment/post-treatment periods for AE analysis.

        Returns:
            AE period analysis specifications with time windows
        """
        from .comprehensive_sap_elements import AE_PERIOD_ANALYSIS
        self._log_retrieval("get_ae_period_specifications", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=AE_PERIOD_ANALYSIS,
            source_file="comprehensive_sap_elements.py",
            source_key="AE_PERIOD_ANALYSIS"
        )

    def get_sensitivity_analysis_catalog(self, analysis_type: str = "all") -> KBRetrievalResult:
        """
        Get comprehensive catalog of standard sensitivity analyses.

        Returns TTE sensitivity analyses (censoring alternatives, population alternatives),
        response sensitivity analyses, and missing data sensitivity analyses.

        Args:
            analysis_type: "tte", "response", "missing_data", or "all"

        Returns:
            Sensitivity analysis catalog with methods and descriptions
        """
        from .comprehensive_sap_elements import SENSITIVITY_ANALYSES
        self._log_retrieval("get_sensitivity_analysis_catalog", analysis_type, "comprehensive_sap_elements.py")

        if analysis_type == "all":
            content = SENSITIVITY_ANALYSES
        elif analysis_type == "tte":
            content = SENSITIVITY_ANALYSES.get("tte_sensitivity", {})
        elif analysis_type == "response":
            content = SENSITIVITY_ANALYSES.get("response_sensitivity", {})
        elif analysis_type == "missing_data":
            content = SENSITIVITY_ANALYSES.get("missing_data_sensitivity", [])
        else:
            content = SENSITIVITY_ANALYSES

        return KBRetrievalResult(
            content=content,
            source_file="comprehensive_sap_elements.py",
            source_key=f"SENSITIVITY_ANALYSES['{analysis_type}']"
        )

    def get_multiplicity_methods(self, method_type: str = "all") -> KBRetrievalResult:
        """
        Get multiplicity adjustment methods specifications.

        Returns hierarchical testing procedures, alpha splitting methods
        (Bonferroni, Holm, Hochberg), graphical approaches, gatekeeping.

        Args:
            method_type: "hierarchical", "alpha_splitting", "gatekeeping",
                        "graphical", "group_sequential", or "all"

        Returns:
            Multiplicity adjustment specifications with procedures
        """
        from .comprehensive_sap_elements import MULTIPLICITY_ADJUSTMENTS
        self._log_retrieval("get_multiplicity_methods", method_type, "comprehensive_sap_elements.py")

        if method_type == "all":
            content = MULTIPLICITY_ADJUSTMENTS
        elif method_type in MULTIPLICITY_ADJUSTMENTS:
            content = MULTIPLICITY_ADJUSTMENTS.get(method_type, {})
        else:
            content = MULTIPLICITY_ADJUSTMENTS

        return KBRetrievalResult(
            content=content,
            source_file="comprehensive_sap_elements.py",
            source_key=f"MULTIPLICITY_ADJUSTMENTS['{method_type}']"
        )

    def get_interim_analysis_specs(self, spec_type: str = "all") -> KBRetrievalResult:
        """
        Get interim analysis and DSMB specifications.

        Returns timing specifications (event-driven, calendar-driven),
        futility assessment (binding/non-binding), DSMB charter elements.

        Args:
            spec_type: "timing", "futility", "dsmb", or "all"

        Returns:
            Interim analysis specifications
        """
        from .comprehensive_sap_elements import INTERIM_ANALYSIS
        self._log_retrieval("get_interim_analysis_specs", spec_type, "comprehensive_sap_elements.py")

        if spec_type == "all":
            content = INTERIM_ANALYSIS
        elif spec_type == "timing":
            content = INTERIM_ANALYSIS.get("timing", {})
        elif spec_type == "futility":
            content = INTERIM_ANALYSIS.get("futility", {})
        elif spec_type == "dsmb":
            content = {"dsmb_charter_elements": INTERIM_ANALYSIS.get("dsmb_charter_elements", [])}
        else:
            content = INTERIM_ANALYSIS

        return KBRetrievalResult(
            content=content,
            source_file="comprehensive_sap_elements.py",
            source_key=f"INTERIM_ANALYSIS['{spec_type}']"
        )

    def get_qol_analysis_specs(self, instrument: str = "all") -> KBRetrievalResult:
        """
        Get Quality of Life and PRO analysis specifications.

        Returns analysis methods for EORTC QLQ-C30, FACT-G, EQ-5D,
        disease-specific modules, time-to-deterioration analysis.

        Args:
            instrument: "EORTC", "FACT", "EQ5D", "methods", or "all"

        Returns:
            QoL/PRO analysis specifications with instruments and methods
        """
        from .comprehensive_sap_elements import QOL_PRO_ANALYSIS
        self._log_retrieval("get_qol_analysis_specs", instrument, "comprehensive_sap_elements.py")

        if instrument == "all":
            content = QOL_PRO_ANALYSIS
        elif instrument.upper() in ["EORTC", "FACT"]:
            content = QOL_PRO_ANALYSIS.get("common_instruments", {}).get("oncology_general", {})
        elif instrument.upper() == "EQ5D":
            content = QOL_PRO_ANALYSIS.get("common_instruments", {}).get("utility", {})
        elif instrument == "methods":
            content = QOL_PRO_ANALYSIS.get("analysis_methods", {})
        else:
            content = QOL_PRO_ANALYSIS

        return KBRetrievalResult(
            content=content,
            source_file="comprehensive_sap_elements.py",
            source_key=f"QOL_PRO_ANALYSIS['{instrument}']"
        )

    def get_estimand_specifications(self) -> KBRetrievalResult:
        """
        Get ICH E9(R1) estimand framework specifications.

        Returns estimand components (population, treatment, endpoint,
        intercurrent events, summary measure) and strategies for
        handling intercurrent events.

        Returns:
            Estimand framework specifications per ICH E9(R1)
        """
        from .comprehensive_sap_elements import ESTIMAND_FRAMEWORK
        self._log_retrieval("get_estimand_specifications", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=ESTIMAND_FRAMEWORK,
            source_file="comprehensive_sap_elements.py",
            source_key="ESTIMAND_FRAMEWORK"
        )

    def get_covid19_variations(self) -> KBRetrievalResult:
        """
        Get COVID-19 protocol variation specifications.

        Returns guidance for handling COVID-related assessment modifications,
        treatment delays, sensitivity analyses, and AE reporting.

        Returns:
            COVID-19 protocol variation specifications
        """
        from .comprehensive_sap_elements import COVID19_VARIATIONS
        self._log_retrieval("get_covid19_variations", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=COVID19_VARIATIONS,
            source_file="comprehensive_sap_elements.py",
            source_key="COVID19_VARIATIONS"
        )

    def get_subgroup_specifications(self) -> KBRetrievalResult:
        """
        Get subgroup analysis specifications.

        Returns pre-specified subgroups (demographic, disease-related),
        forest plot specifications, and interaction testing guidance.

        Returns:
            Subgroup analysis specifications
        """
        from .comprehensive_sap_elements import SUBGROUP_ANALYSIS_SPECS
        self._log_retrieval("get_subgroup_specifications", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=SUBGROUP_ANALYSIS_SPECS,
            source_file="comprehensive_sap_elements.py",
            source_key="SUBGROUP_ANALYSIS_SPECS"
        )

    def get_protocol_deviation_specs(self) -> KBRetrievalResult:
        """
        Get protocol deviation tracking specifications.

        Returns major/minor deviation categories and analysis specifications.

        Returns:
            Protocol deviation specifications
        """
        from .comprehensive_sap_elements import PROTOCOL_DEVIATIONS
        self._log_retrieval("get_protocol_deviation_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=PROTOCOL_DEVIATIONS,
            source_file="comprehensive_sap_elements.py",
            source_key="PROTOCOL_DEVIATIONS"
        )

    def get_healthcare_utilization_specs(self) -> KBRetrievalResult:
        """
        Get healthcare resource utilization specifications.

        Returns hospitalization, ED visits, outpatient visit tracking,
        and CAR-T specific utilization (CRS/ICANS hospitalization,
        tocilizumab use, corticosteroid use).

        Returns:
            Healthcare utilization analysis specifications
        """
        from .comprehensive_sap_elements import HEALTHCARE_UTILIZATION
        self._log_retrieval("get_healthcare_utilization_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=HEALTHCARE_UTILIZATION,
            source_file="comprehensive_sap_elements.py",
            source_key="HEALTHCARE_UTILIZATION"
        )

    def get_phase2_design_specs(self) -> KBRetrievalResult:
        """
        Get Phase 2 specific design specifications.

        Returns Simon two-stage design, Fleming's single-stage,
        Gehan two-stage, and Bayesian phase 2 design specifications.

        Returns:
            Phase 2 design specifications with parameters
        """
        from .comprehensive_sap_elements import PHASE2_DESIGNS
        self._log_retrieval("get_phase2_design_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=PHASE2_DESIGNS,
            source_file="comprehensive_sap_elements.py",
            source_key="PHASE2_DESIGNS"
        )

    def get_blinding_specifications(self) -> KBRetrievalResult:
        """
        Get blinding and unblinding specifications.

        Returns IRC assessment, endpoint adjudication, unblinding triggers,
        and open-label study considerations.

        Returns:
            Blinding specifications
        """
        from .comprehensive_sap_elements import BLINDING_CONSIDERATIONS
        self._log_retrieval("get_blinding_specifications", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=BLINDING_CONSIDERATIONS,
            source_file="comprehensive_sap_elements.py",
            source_key="BLINDING_CONSIDERATIONS"
        )

    def get_pkpd_analysis_specs(self, spec_type: str = "all") -> KBRetrievalResult:
        """
        Get PK/PD analysis specifications.

        Returns PK parameters (Cmax, AUC, etc.), exposure-response analysis,
        and CAR-T specific PK (transgene levels, expansion kinetics).

        Args:
            spec_type: "parameters", "exposure_response", "cart", or "all"

        Returns:
            PK/PD analysis specifications
        """
        from .comprehensive_sap_elements import PK_PD_ANALYSIS
        self._log_retrieval("get_pkpd_analysis_specs", spec_type, "comprehensive_sap_elements.py")

        if spec_type == "all":
            content = PK_PD_ANALYSIS
        elif spec_type == "parameters":
            content = PK_PD_ANALYSIS.get("pk_parameters", {})
        elif spec_type == "exposure_response":
            content = PK_PD_ANALYSIS.get("exposure_response", {})
        elif spec_type == "cart":
            content = PK_PD_ANALYSIS.get("cart_specific_pk", {})
        else:
            content = PK_PD_ANALYSIS

        return KBRetrievalResult(
            content=content,
            source_file="comprehensive_sap_elements.py",
            source_key=f"PK_PD_ANALYSIS['{spec_type}']"
        )

    def get_mrd_assessment_specs(self) -> KBRetrievalResult:
        """
        Get MRD (Minimal Residual Disease) assessment specifications.

        Returns MRD methods (flow cytometry, NGS, PCR), endpoints
        (MRD negativity rate, MRD in responders), and assessment timing.

        Returns:
            MRD assessment specifications for hematologic malignancies
        """
        from .comprehensive_sap_elements import MRD_ASSESSMENT
        self._log_retrieval("get_mrd_assessment_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=MRD_ASSESSMENT,
            source_file="comprehensive_sap_elements.py",
            source_key="MRD_ASSESSMENT"
        )

    def get_demographics_baseline_specs(self) -> KBRetrievalResult:
        """
        Get demographics and baseline characteristics specifications.

        Returns demographic variables (age, sex, race), baseline disease
        characteristics (ECOG, stage, target lesions), statistics to present.
        Also returns disease-specific baseline covariates for all oncology types.

        Returns:
            Demographics and baseline specs for SAP section
        """
        from .comprehensive_sap_elements import (
            DEMOGRAPHICS_BASELINE,
            BASELINE_COVARIATES_CORE,
            BASELINE_COVARIATES_SOLID_TUMOR,
            BASELINE_COVARIATES_BREAST,
            BASELINE_COVARIATES_LUNG,
            BASELINE_COVARIATES_GI,
            BASELINE_COVARIATES_PROSTATE,
            BASELINE_COVARIATES_OVARIAN,
            BASELINE_COVARIATES_LYMPHOMA,
            BASELINE_COVARIATES_MYELOMA,
            BASELINE_COVARIATES_LEUKEMIA,
            BASELINE_COVARIATES_CLL
        )
        self._log_retrieval("get_demographics_baseline_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content={
                "demographics_baseline": DEMOGRAPHICS_BASELINE,
                "baseline_covariates_core": BASELINE_COVARIATES_CORE,
                "disease_specific_covariates": {
                    "solid_tumor": BASELINE_COVARIATES_SOLID_TUMOR,
                    "breast": BASELINE_COVARIATES_BREAST,
                    "lung": BASELINE_COVARIATES_LUNG,
                    "gi": BASELINE_COVARIATES_GI,
                    "prostate": BASELINE_COVARIATES_PROSTATE,
                    "ovarian": BASELINE_COVARIATES_OVARIAN,
                    "lymphoma": BASELINE_COVARIATES_LYMPHOMA,
                    "myeloma": BASELINE_COVARIATES_MYELOMA,
                    "leukemia": BASELINE_COVARIATES_LEUKEMIA,
                    "cll": BASELINE_COVARIATES_CLL
                }
            },
            source_file="comprehensive_sap_elements.py",
            source_key="DEMOGRAPHICS_BASELINE + BASELINE_COVARIATES_*"
        )

    def get_baseline_covariates(self, disease_type: str = None) -> KBRetrievalResult:
        """
        Get baseline covariates for a specific disease type.

        Args:
            disease_type: One of 'breast', 'lung', 'gi', 'prostate', 'ovarian',
                         'lymphoma', 'myeloma', 'leukemia', 'cll', 'solid_tumor'
                         If None, returns all covariates for all disease types.

        Returns:
            Core baseline covariates + disease-specific covariates with source_trials
        """
        from .comprehensive_sap_elements import (
            BASELINE_COVARIATES_CORE,
            get_disease_specific_baseline_covariates,
            get_all_baseline_covariates
        )
        self._log_retrieval("get_baseline_covariates", disease_type or "all", "comprehensive_sap_elements.py")

        if disease_type:
            disease_specific = get_disease_specific_baseline_covariates(disease_type)
            return KBRetrievalResult(
                content={
                    "core": BASELINE_COVARIATES_CORE,
                    "disease_specific": disease_specific,
                    "disease_type": disease_type
                },
                source_file="comprehensive_sap_elements.py",
                source_key=f"BASELINE_COVARIATES_CORE + BASELINE_COVARIATES_{disease_type.upper()}"
            )
        else:
            return KBRetrievalResult(
                content=get_all_baseline_covariates(),
                source_file="comprehensive_sap_elements.py",
                source_key="BASELINE_COVARIATES_*"
            )

    def get_prior_therapy_specs(self) -> KBRetrievalResult:
        """
        Get prior anti-cancer therapy analysis specifications.

        Returns prior therapy summaries (number of lines, types),
        hematologic-specific (anti-CD20, alkylating, SCT, refractory status),
        solid tumor-specific (surgery, radiation, targeted therapy).

        Returns:
            Prior therapy analysis specifications
        """
        from .comprehensive_sap_elements import PRIOR_THERAPY_ANALYSIS
        self._log_retrieval("get_prior_therapy_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=PRIOR_THERAPY_ANALYSIS,
            source_file="comprehensive_sap_elements.py",
            source_key="PRIOR_THERAPY_ANALYSIS"
        )

    def get_concomitant_medication_specs(self) -> KBRetrievalResult:
        """
        Get concomitant medication analysis specifications.

        Returns coding (WHO Drug, ATC), summary tables, special categories
        (supportive care, CAR-T specific), prohibited medications handling.

        Returns:
            Concomitant medication analysis specifications
        """
        from .comprehensive_sap_elements import CONCOMITANT_MEDICATIONS
        self._log_retrieval("get_concomitant_medication_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=CONCOMITANT_MEDICATIONS,
            source_file="comprehensive_sap_elements.py",
            source_key="CONCOMITANT_MEDICATIONS"
        )

    def get_medical_history_specs(self) -> KBRetrievalResult:
        """
        Get medical history analysis specifications.

        Returns MedDRA coding, summary tables by SOC/PT, relevant conditions.

        Returns:
            Medical history analysis specifications
        """
        from .comprehensive_sap_elements import MEDICAL_HISTORY
        self._log_retrieval("get_medical_history_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=MEDICAL_HISTORY,
            source_file="comprehensive_sap_elements.py",
            source_key="MEDICAL_HISTORY"
        )

    def get_death_analysis_specs(self) -> KBRetrievalResult:
        """
        Get death and survival analysis specifications.

        Returns death summary, primary cause of death categories,
        survival analysis methods, cause of death adjudication.

        Returns:
            Death and survival analysis specifications
        """
        from .comprehensive_sap_elements import DEATH_ANALYSIS
        self._log_retrieval("get_death_analysis_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=DEATH_ANALYSIS,
            source_file="comprehensive_sap_elements.py",
            source_key="DEATH_ANALYSIS"
        )

    def get_tumor_response_specs(self) -> KBRetrievalResult:
        """
        Get tumor response assessment specifications.

        Returns RECIST 1.1, Lugano 2014, IWCLL 2018, IMWG criteria,
        IRC assessment, assessment schedule, imaging modality.

        Returns:
            Tumor response assessment specifications
        """
        from .comprehensive_sap_elements import TUMOR_RESPONSE_ASSESSMENT
        self._log_retrieval("get_tumor_response_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=TUMOR_RESPONSE_ASSESSMENT,
            source_file="comprehensive_sap_elements.py",
            source_key="TUMOR_RESPONSE_ASSESSMENT"
        )

    def get_treatment_compliance_specs(self) -> KBRetrievalResult:
        """
        Get treatment compliance and adherence specifications.

        Returns dose compliance, treatment duration, dose modifications,
        reasons for discontinuation categories.

        Returns:
            Treatment compliance specifications
        """
        from .comprehensive_sap_elements import TREATMENT_COMPLIANCE
        self._log_retrieval("get_treatment_compliance_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=TREATMENT_COMPLIANCE,
            source_file="comprehensive_sap_elements.py",
            source_key="TREATMENT_COMPLIANCE"
        )

    def get_concordance_specs(self) -> KBRetrievalResult:
        """
        Get IRC vs Investigator concordance analysis specifications.

        Returns overall concordance, response matrix, discordance analysis,
        timing concordance for TTR and TTP.

        Returns:
            Concordance analysis specifications
        """
        from .comprehensive_sap_elements import CONCORDANCE_ANALYSIS
        self._log_retrieval("get_concordance_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=CONCORDANCE_ANALYSIS,
            source_file="comprehensive_sap_elements.py",
            source_key="CONCORDANCE_ANALYSIS"
        )

    def get_immunogenicity_specs(self) -> KBRetrievalResult:
        """
        Get immunogenicity (ADA) analysis specifications.

        Returns ADA testing methodology, analysis populations,
        ADA summaries, impact analysis on PK/efficacy/safety.

        Returns:
            Immunogenicity analysis specifications
        """
        from .comprehensive_sap_elements import IMMUNOGENICITY_ANALYSIS
        self._log_retrieval("get_immunogenicity_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=IMMUNOGENICITY_ANALYSIS,
            source_file="comprehensive_sap_elements.py",
            source_key="IMMUNOGENICITY_ANALYSIS"
        )

    def get_organ_function_specs(self) -> KBRetrievalResult:
        """
        Get organ function requirements specifications.

        Returns hepatic (AST, ALT, bilirubin, Child-Pugh), renal (CrCl, eGFR),
        hematologic (ANC, platelet, Hgb), cardiac (LVEF, QTcF) specifications.

        Returns:
            Organ function specifications
        """
        from .comprehensive_sap_elements import ORGAN_FUNCTION_SPECS
        self._log_retrieval("get_organ_function_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=ORGAN_FUNCTION_SPECS,
            source_file="comprehensive_sap_elements.py",
            source_key="ORGAN_FUNCTION_SPECS"
        )

    def get_analysis_timing_specs(self) -> KBRetrievalResult:
        """
        Get analysis timing and visit window specifications.

        Returns visit windows, analysis windows, scheduled assessment windows.

        Returns:
            Analysis timing specifications
        """
        from .comprehensive_sap_elements import ANALYSIS_TIMING
        self._log_retrieval("get_analysis_timing_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=ANALYSIS_TIMING,
            source_file="comprehensive_sap_elements.py",
            source_key="ANALYSIS_TIMING"
        )

    def get_follow_up_analysis_specs(self, timepoint: str = "all") -> KBRetrievalResult:
        """
        Get follow-up analysis specifications for planned descriptive analyses.

        Returns specifications for 18-month, 24-month, 36-month follow-up analyses
        including endpoints, analysis content, and CAR-T specific long-term follow-up.
        Essential for Section 20 (FOLLOW-UP ANALYSIS).

        Args:
            timepoint: "18_month", "24_month", "36_month", "cart", or "all"

        Returns:
            Follow-up analysis specifications with timepoints, analyses, and reporting format
        """
        from .comprehensive_sap_elements import FOLLOW_UP_ANALYSIS_SPECS
        self._log_retrieval("get_follow_up_analysis_specs", timepoint, "comprehensive_sap_elements.py")

        if timepoint.lower() == "all":
            content = FOLLOW_UP_ANALYSIS_SPECS
        elif timepoint.lower() == "cart":
            content = FOLLOW_UP_ANALYSIS_SPECS.get("cart_specific_follow_up", {})
        elif timepoint.lower() in ["18_month", "24_month", "36_month"]:
            content = FOLLOW_UP_ANALYSIS_SPECS.get("standard_timepoints", {}).get(timepoint.lower(), {})
        else:
            content = FOLLOW_UP_ANALYSIS_SPECS

        return KBRetrievalResult(
            content=content,
            source_file="comprehensive_sap_elements.py",
            source_key=f"FOLLOW_UP_ANALYSIS_SPECS['{timepoint}']"
        )

    def get_stratification_balance_specs(self) -> KBRetrievalResult:
        """
        Get stratification factor balance specifications.

        Returns balance assessment method, stratified vs unstratified analysis.

        Returns:
            Stratification balance specifications
        """
        from .comprehensive_sap_elements import STRATIFICATION_BALANCE
        self._log_retrieval("get_stratification_balance_specs", "all", "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=STRATIFICATION_BALANCE,
            source_file="comprehensive_sap_elements.py",
            source_key="STRATIFICATION_BALANCE"
        )

    def get_comprehensive_sap_elements(self, study_type: str = "oncology") -> KBRetrievalResult:
        """
        Get ALL comprehensive SAP elements for a study type.

        Master function returning all SAP element specifications based on
        study type (oncology, cart, solid_tumor, hematologic).

        Args:
            study_type: "oncology", "cart", "solid_tumor", "hematologic"

        Returns:
            Complete dictionary of all applicable SAP specifications
        """
        from .comprehensive_sap_elements import get_comprehensive_sap_elements as get_elements
        self._log_retrieval("get_comprehensive_sap_elements", study_type, "comprehensive_sap_elements.py")

        return KBRetrievalResult(
            content=get_elements(study_type),
            source_file="comprehensive_sap_elements.py",
            source_key=f"get_comprehensive_sap_elements('{study_type}')"
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

        # v70: Format results with clear citation guidance
        formatted_results = []
        for trial in results:
            trial_id = trial.get("trial_id", "Unknown")
            trial_phase = trial.get("phase", "")
            trial_indication = trial.get("indication", "")
            # Create citation format: "TRIAL_ID (Phase X, Indication)"
            citation = f"{trial_id} ({trial_phase}, {trial_indication})" if trial_phase else trial_id
            formatted_results.append({
                **trial,
                "citation_format": f"[Precedent: {citation}]",
                "cite_as": citation
            })

        return KBRetrievalResult(
            content={
                "query": {
                    "phase": phase,
                    "indication": indication,
                    "endpoint_type": endpoint_type,
                    "design_type": design_type
                },
                "citation_instruction": "When using precedent data, cite as: [Precedent: TRIAL_NAME (Phase, Indication) - specific element]",
                "num_matches": len(results),
                "similar_trials": formatted_results
            },
            source_file="factual_kg_merged.json",
            source_key="TrialPrecedentKG.find_similar_trials"
        )

    # =========================================================================
    # REFERENCE SAP RETRIEVAL TOOLS (queries actual SAP text files)
    # =========================================================================

    def get_reference_sap_section(
        self,
        section_type: str,
        indication: Optional[str] = None,
        trial_name: Optional[str] = None
    ) -> KBRetrievalResult:
        """
        Retrieve actual SAP sections from 151 reference SAPs.

        This provides REAL SAP text with derivation tables, scoring algorithms,
        and multiplicity procedures - not just metadata.

        Args:
            section_type: Type of section to retrieve:
                - "recist_derivation" - RECIST Tables 2/3/4 (TL, NTL, Overall Response)
                - "pro_scoring" - PRO/QoL scoring algorithms, MID thresholds, MMRM
                - "multiplicity" - GSHf, alpha spending, graphical approaches
                - "censoring" - Censoring rules and derivation tables
                - "interim_analysis" - Interim analysis boundaries and procedures
                - "subgroups" - Subgroup analysis specifications
                - "sensitivity" - Sensitivity analysis methods
            indication: Optional filter by disease (e.g., "NSCLC", "breast", "lymphoma")
            trial_name: Optional specific trial (e.g., "PACIFIC", "KEYNOTE")

        Returns:
            Actual SAP text sections with source attribution
        """
        from pathlib import Path
        import re

        self._log_retrieval("get_reference_sap_section", f"{section_type}, {indication}, {trial_name}", "reference_saps/")
        print(f"[KB] get_reference_sap_section CALLED: section_type={section_type}, indication={indication}")

        # Path to reference SAPs
        ref_sap_dir = Path(__file__).parent / "reference_saps" / "extracted_text"
        print(f"[KB] Looking for reference SAPs in: {ref_sap_dir}")

        if not ref_sap_dir.exists():
            print(f"[KB] ERROR: Reference SAPs directory NOT FOUND at {ref_sap_dir}")
            return KBRetrievalResult(
                content={"error": "Reference SAPs directory not found"},
                source_file="reference_saps/extracted_text/",
                source_key="NOT_FOUND"
            )

        # Section patterns to search for
        section_patterns = {
            "recist_derivation": [
                # Look for actual table content, not TOC references
                r"Overall\s*Visit\s*Response[s]?\s*\n\s*Target\s*Lesion",
                r"Target\s*Lesion[s]?\s*\n\s*Non-?target\s*lesion",
                r"(CR|PR|SD|PD)\s+\n?\s*(CR|PR|SD|PD|Non[\s-]?PD|NE)\s+\n?\s*(Yes|No)\s+\n?\s*(CR|PR|SD|PD)",
                r"Table\s*[234]\s*\n\s*(Target|Overall|TL|NTL)[\s\S]{0,200}(CR|PR|SD|PD)",
                r"visit\s*response[\s\S]{0,100}(CR|PR|SD|PD)[\s\S]{0,100}(CR|PR|SD|PD)",
            ],
            "pro_scoring": [
                r"(EORTC|QLQ|FACT|EQ-?5D|SF-?36)[\s\S]{0,500}(scor|algorithm|MID|MCID)",
                r"(PRO|QoL|Quality of Life)[\s\S]{0,300}(analysis|scoring|threshold)",
                r"MMRM[\s\S]{0,500}(model|covariate|repeated)",
                r"(minimal|clinically)\s*(important|meaningful)\s*difference",
                r"compliance[\s\S]{0,200}(threshold|rate|%)",
            ],
            "multiplicity": [
                r"(GSHf|graphical|Hochberg|Bonferroni|Holm)[\s\S]{0,500}(alpha|procedure)",
                r"alpha\s*(spending|recycling|splitting|allocation)[\s\S]{0,500}",
                r"multiplicity[\s\S]{0,500}(adjustment|procedure|method)",
                r"(gatekeeping|hierarchical|fallback)[\s\S]{0,300}(procedure|testing)",
                r"(Type\s*I|familywise)\s*error[\s\S]{0,300}(control|rate|alpha)",
                r"\d+\.?\d*\s*%[\s\S]{0,50}alpha",
            ],
            "censoring": [
                r"censoring[\s\S]{0,500}(rule|date|event)",
                r"(event|censor)[\s\S]{0,200}(date|indicator|flag)",
                r"(PFS|OS|DOR|TTR)[\s\S]{0,300}censoring",
                r"lost\s*to\s*follow[\s\S]{0,200}(censor|date)",
            ],
            "interim_analysis": [
                r"interim\s*analysis[\s\S]{0,500}(boundary|alpha|stopping)",
                r"(O'Brien|Lan-DeMets|Pocock|Haybittle)[\s\S]{0,300}(boundary|function)",
                r"(futility|efficacy)\s*(boundary|stopping|rule)",
                r"alpha\s*spending[\s\S]{0,300}(function|boundary)",
                r"information\s*fraction[\s\S]{0,200}(\d+%|\d+\.\d+)",
            ],
            "subgroups": [
                r"subgroup[\s\S]{0,500}(analysis|forest|plot)",
                r"(pre-?specified|exploratory)\s*subgroup",
                r"forest\s*plot[\s\S]{0,300}(hazard|ratio|CI)",
                r"(age|sex|race|region|histology|stage|ECOG|PD-?L1)[\s\S]{0,100}subgroup",
            ],
            "sensitivity": [
                r"sensitivity\s*analysis[\s\S]{0,500}",
                r"(tipping\s*point|pattern\s*mixture|MNAR|MAR)",
                r"(per-?protocol|as-?treated|ITT)[\s\S]{0,200}sensitivity",
                r"(robust|alternative)[\s\S]{0,100}analysis",
            ],
        }

        patterns = section_patterns.get(section_type, section_patterns.get("recist_derivation"))

        # Find matching SAP files
        sap_files = list(ref_sap_dir.glob("*.txt"))

        # Filter by indication/trial name if specified
        if trial_name:
            trial_upper = trial_name.upper()
            sap_files = [f for f in sap_files if trial_upper in f.stem.upper()]
        if indication:
            indication_lower = indication.lower()
            # Keep all files but score them later by indication match
            pass

        results = []
        for sap_file in sap_files[:30]:  # Limit to 30 files to avoid timeout
            try:
                content = sap_file.read_text(encoding='utf-8', errors='ignore')

                # Check indication match if specified
                if indication:
                    if indication.lower() not in content.lower():
                        continue

                # Search for matching sections
                for pattern in patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        # Extract context around match (500 chars before, 1500 after)
                        start = max(0, match.start() - 500)
                        end = min(len(content), match.end() + 1500)
                        section_text = content[start:end]

                        # Clean up the section
                        section_text = section_text.strip()

                        # Find natural boundaries (section headers)
                        section_start = section_text.rfind('\n', 0, 500)
                        if section_start > 0:
                            section_text = section_text[section_start:].strip()

                        results.append({
                            "source_sap": sap_file.stem,
                            "section_type": section_type,
                            "matched_pattern": pattern[:50] + "...",
                            "content": section_text[:2500],  # Limit per section
                            "citation": f"[Reference: {sap_file.stem}]"
                        })

                        if len(results) >= 5:  # Limit to 5 best matches
                            break
                    if len(results) >= 5:
                        break

            except Exception as e:
                continue

            if len(results) >= 5:
                break

        # If no results, return helpful message
        if not results:
            return KBRetrievalResult(
                content={
                    "message": f"No {section_type} sections found matching criteria",
                    "suggestion": "Try broader search or different section_type",
                    "available_types": list(section_patterns.keys())
                },
                source_file="reference_saps/extracted_text/",
                source_key=f"search_{section_type}"
            )

        return KBRetrievalResult(
            content={
                "section_type": section_type,
                "num_matches": len(results),
                "instruction": "Use these ACTUAL SAP sections as templates. Adapt to current protocol specifics.",
                "sections": results
            },
            source_file="reference_saps/extracted_text/",
            source_key=f"reference_sap_sections_{section_type}"
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
        - CRS grading options (use what PROTOCOL specifies):
          * ASTCT 2019 Consensus - newer standard
          * Modified Lee et al. 2014 - older axicabtagene/ZUMA studies
        - Neurologic event grading (use what PROTOCOL specifies):
          * ICANS/ICE score - if protocol mentions ICANS
          * Separate CTCAE grading - if protocol says "not part of CRS"
        - Cellular kinetics endpoints (Cmax, persistence, B-cell aplasia)
        - Safety monitoring requirements
        - Step-up dosing considerations

        IMPORTANT: Protocol-specified grading takes precedence over KB defaults.
        Check protocol/IB for CRS grading scale specification.

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
        },
        # =====================================================================
        # v68: PREVIOUSLY UNEXPOSED KB CONTENT
        # =====================================================================
        {
            "name": "get_safety_analysis_specs",
            "description": "Get safety analysis specifications: AE incidence calculations, MedDRA coding conventions, exposure-adjusted rates, CTCAE toxicity grading, shift tables methodology, lab/VS/ECG analysis methods.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "analysis_type": {
                        "type": "string",
                        "description": "Type of safety analysis: 'adverse_events', 'exposure', 'laboratory', 'vital_signs', 'ecg', or 'all' (default)",
                        "enum": ["adverse_events", "exposure", "laboratory", "vital_signs", "ecg", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_tfl_shells",
            "description": "Get TFL shell templates with complete structure: table/figure/listing layouts, column headers, row labels, statistical presentation formats, and footnote conventions. Separate from complete_tfl_inventory.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "shell_type": {
                        "type": "string",
                        "description": "Type of shells: 'disposition', 'demographics', 'efficacy', 'safety', 'pk', or 'all' (default)",
                        "enum": ["disposition", "demographics", "efficacy", "safety", "pk", "all"]
                    }
                },
                "required": []
            }
        },
        # =====================================================================
        # v75: TTE DERIVATION, MEDDRA, CONCORDANCE, REFERENCES
        # =====================================================================
        {
            "name": "get_tte_derivation_tables",
            "description": "Get time-to-event derivation circumstance tables for DOR, DORR, PFS, OS. Shows when subjects are events vs censored for each circumstance. ESSENTIAL for Appendix A.2.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "endpoint": {
                        "type": "string",
                        "description": "Endpoint type: 'DOR', 'DORR', 'PFS', 'OS', or 'all' (default)",
                        "enum": ["DOR", "DORR", "PFS", "OS", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_meddra_search_strategies",
            "description": "Get MedDRA search strategies (SMQ, MST, HLGT) for safety analyses. Includes SMQ specifications for cytopenias, infections, CRS, ICANS, cardiac events, TLS, GVHD. ESSENTIAL for Appendix A.3 (MedDRA Search Strategies).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "AE category: 'CRS', 'thrombocytopenia', 'neutropenia', 'anemia', 'infections', 'GVHD', 'immunogenicity', 'tumor_lysis_syndrome', 'cardiac_events', or 'all' (default)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_concordance_analysis",
            "description": "Get concordance analysis methodology for IRC vs Investigator agreement. Includes kappa statistics, percent agreement, and discordance analysis methods. Use for blinded review comparison sections.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_required_references",
            "description": "Get required references for SAP based on study type. Includes standard citations for response criteria (RECIST, Lugano, IMWG), statistical methods (Kaplan-Meier, Cox), grading scales (CTCAE, CRS). ESSENTIAL for References section.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "study_type": {
                        "type": "string",
                        "description": "Study type: 'oncology', 'cart', 'lymphoma', 'solid_tumor', 'hematologic', 'myeloma'"
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_date_imputation_rules",
            "description": "Get date imputation algorithm specifications. Includes rules for imputing partial AE dates, death dates, concomitant medication dates. ESSENTIAL for Appendix A.1.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        # v76: Comprehensive SAP Elements
        {
            "name": "get_study_definitions",
            "description": "Get standard study definitions required for every SAP (Section 5). Returns Study Day 0/baseline definitions, on-study period, end of study, TEAE definition, follow-up time calculations. ESSENTIAL for DEFINITIONS section.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "definition_type": {
                        "type": "string",
                        "description": "Type of definition",
                        "enum": ["time", "safety", "events", "followup", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_exposure_specifications",
            "description": "Get drug exposure analysis specifications. Returns BSA-adjusted dosing, weight-based dosing, relative dose intensity, CAR-T cell dose specifications. Use for exposure/drug administration sections.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "exposure_type": {
                        "type": "string",
                        "description": "Type of exposure specification",
                        "enum": ["dose", "bsa", "weight", "cart", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_cart_manufacturing_specs",
            "description": "Get CAR-T manufacturing and logistics metrics. Returns leukapheresis timing, vein-to-vein time, manufacturing success rates, bridging therapy specifications. Use for CAR-T specific sections.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_subsequent_therapy_specs",
            "description": "Get subsequent anti-cancer therapy tracking specifications. Returns subsequent therapy summaries, subsequent SCT (autologous/allogeneic), time to next therapy. Use for post-treatment sections.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_enrollment_specifications",
            "description": "Get enrollment summary specifications. Returns enrollment by country, site, region, and enrollment over time displays. Use for Subject Disposition section.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_ae_period_specifications",
            "description": "Get AE period analysis specifications. Returns CAR-T specific periods (Day 0-30, 31-92, 93+) and standard on-treatment/post-treatment periods. Use for safety analysis sections.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_sensitivity_analysis_catalog",
            "description": "Get comprehensive catalog of standard sensitivity analyses. Returns TTE sensitivity (censoring, population, model alternatives), response sensitivity, missing data sensitivity. Use for Sensitivity Analyses section.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "analysis_type": {
                        "type": "string",
                        "description": "Type of sensitivity analysis",
                        "enum": ["tte", "response", "missing_data", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_multiplicity_methods",
            "description": "Get multiplicity adjustment methods. Returns hierarchical testing, alpha splitting (Bonferroni, Holm, Hochberg), graphical approaches, gatekeeping procedures. Use for Multiple Comparisons section.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "method_type": {
                        "type": "string",
                        "description": "Type of multiplicity method",
                        "enum": ["hierarchical_testing", "alpha_splitting", "gatekeeping", "graphical_approaches", "group_sequential", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_interim_analysis_specs",
            "description": "Get interim analysis and DSMB specifications. Returns timing specifications (event-driven, calendar-driven), futility assessment (binding/non-binding), DSMB charter elements. Use for Interim Analysis section.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "spec_type": {
                        "type": "string",
                        "description": "Type of interim analysis spec",
                        "enum": ["timing", "futility", "dsmb", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_qol_analysis_specs",
            "description": "Get Quality of Life and PRO analysis specifications. Returns EORTC QLQ-C30, FACT-G, EQ-5D specifications, time-to-deterioration analysis, responder analysis methods. Use for PRO/QoL sections.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "instrument": {
                        "type": "string",
                        "description": "QoL instrument",
                        "enum": ["EORTC", "FACT", "EQ5D", "methods", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_estimand_specifications",
            "description": "Get ICH E9(R1) estimand framework specifications. Returns estimand components (population, treatment, endpoint, intercurrent events, summary measure) and strategies for handling intercurrent events.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_covid19_variations",
            "description": "Get COVID-19 protocol variation specifications. Returns guidance for COVID-related assessment modifications, treatment delays, sensitivity analyses, AE reporting. Use if study had COVID-era enrollment.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_subgroup_specifications",
            "description": "Get subgroup analysis specifications. Returns pre-specified subgroups (demographic, disease-related), forest plot specifications, interaction testing guidance. Use for Subgroup Analyses section.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_protocol_deviation_specs",
            "description": "Get protocol deviation tracking specifications. Returns major/minor deviation categories and analysis specifications. Use for Protocol Deviations section.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_healthcare_utilization_specs",
            "description": "Get healthcare resource utilization specifications. Returns hospitalization, ED visits, CAR-T specific utilization (CRS/ICANS hospitalization, tocilizumab use). Use for HRU sections.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_phase2_design_specs",
            "description": "Get Phase 2 specific design specifications. Returns Simon two-stage design, Fleming's single-stage, Gehan two-stage, Bayesian phase 2 designs. Use for Phase 2 study SAPs.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_blinding_specifications",
            "description": "Get blinding and unblinding specifications. Returns IRC assessment, endpoint adjudication, unblinding triggers, open-label considerations. Use for Blinding section.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_pkpd_analysis_specs",
            "description": "Get PK/PD analysis specifications. Returns PK parameters (Cmax, AUC), exposure-response analysis, CAR-T specific PK (transgene levels, expansion kinetics). Use for PK/PD sections.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "spec_type": {
                        "type": "string",
                        "description": "Type of PK/PD spec",
                        "enum": ["parameters", "exposure_response", "cart", "all"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_mrd_assessment_specs",
            "description": "Get MRD (Minimal Residual Disease) assessment specifications. Returns MRD methods (flow cytometry, NGS, PCR), endpoints, assessment timing. Use for hematologic malignancy SAPs.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_comprehensive_sap_elements",
            "description": "Get ALL comprehensive SAP elements for a study type. Master function returning complete SAP specifications based on study type. Use when you need comprehensive coverage.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "study_type": {
                        "type": "string",
                        "description": "Type of study",
                        "enum": ["oncology", "cart", "solid_tumor", "hematologic"]
                    }
                },
                "required": []
            }
        },
        # v77: Additional comprehensive SAP element tools
        {
            "name": "get_demographics_baseline_specs",
            "description": "Get demographics and baseline characteristics specs. Returns demographic variables (age, sex, race), disease characteristics (ECOG, stage), statistics, plus ALL disease-specific baseline covariates (breast, lung, GI, prostate, ovarian, lymphoma, myeloma, leukemia, CLL). Use for Demographics/Baseline section.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "get_baseline_covariates",
            "description": "Get disease-specific baseline covariates with source trial documentation. Returns core covariates (demographics, labs, performance status) plus disease-specific covariates for: breast (ER/PR/HER2, Ki-67, prior CDK4/6i), lung (histology, smoking, EGFR/ALK/ROS1/KRAS, PD-L1), GI (Lauren, sidedness, MSI), prostate (Gleason, PSA, mHSPC/mCRPC), ovarian (platinum status, BRCA/HRD), lymphoma (IPI/FLIPI, prior lenalidomide, bone marrow), myeloma (ISS/R-ISS, cytogenetics), leukemia (ELN risk, FLT3/NPM1), CLL (IGHV, del17p). Each covariate includes source_trials showing which reference SAPs it came from.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "disease_type": {
                        "type": "string",
                        "description": "Disease type for specific covariates",
                        "enum": ["breast", "lung", "nsclc", "gi", "gastric", "colorectal", "crc", "hcc", "prostate", "ovarian", "lymphoma", "dlbcl", "follicular", "mcl", "myeloma", "mm", "leukemia", "aml", "all", "cll", "solid_tumor"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_prior_therapy_specs",
            "description": "Get prior anti-cancer therapy analysis specs. Returns prior therapy summaries, hematologic-specific (anti-CD20, SCT, refractory status), solid tumor-specific. Use for Prior Therapy section.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "get_concomitant_medication_specs",
            "description": "Get concomitant medication analysis specs. Returns coding (WHO Drug, ATC), special categories (supportive care, CAR-T specific). Use for Concomitant Medications section.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "get_medical_history_specs",
            "description": "Get medical history analysis specs. Returns MedDRA coding, summary tables by SOC/PT. Use for Medical History section.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "get_death_analysis_specs",
            "description": "Get death and survival analysis specs. Returns death summary, cause of death categories, survival analysis, adjudication. Use for Death/Survival section.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "get_tumor_response_specs",
            "description": "Get tumor response assessment specs. Returns RECIST 1.1, Lugano 2014, IWCLL 2018, IMWG criteria, IRC assessment. Use for Response Assessment section.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "get_treatment_compliance_specs",
            "description": "Get treatment compliance specs. Returns dose compliance, treatment duration, dose modifications, discontinuation reasons. Use for Exposure/Compliance section.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "get_concordance_specs",
            "description": "Get IRC vs Investigator concordance analysis specs. Returns concordance matrix, discordance analysis. Use when study has IRC assessment.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "get_immunogenicity_specs",
            "description": "Get immunogenicity (ADA) analysis specs. Returns ADA testing, populations, summaries, impact analysis. Use for biologic/antibody studies.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "get_organ_function_specs",
            "description": "Get organ function specs. Returns hepatic, renal, hematologic, cardiac function parameters and thresholds. Use for eligibility/subgroup sections.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "get_analysis_timing_specs",
            "description": "Get analysis timing and visit window specs. Returns visit windows, analysis windows, scheduled assessment windows. Use for Programming Specs section.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "get_follow_up_analysis_specs",
            "description": "Get follow-up analysis specifications for planned descriptive analyses at 18-month, 24-month, 36-month timepoints. Returns timepoints, analysis content, CAR-T long-term follow-up. ESSENTIAL for Section 20 (FOLLOW-UP ANALYSIS).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "timepoint": {
                        "type": "string",
                        "description": "Follow-up timepoint",
                        "enum": ["all", "18_month", "24_month", "36_month", "cart"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_stratification_balance_specs",
            "description": "Get stratification factor balance specs. Returns balance assessment method, stratified vs unstratified analysis. Use for randomized studies.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "get_figure_template",
            "description": "Get specific figure template by type (kaplan_meier, forest_plot, waterfall, swimmer, spider). Use for Figures section.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "figure_type": {
                        "type": "string",
                        "description": "Type of figure",
                        "enum": ["kaplan_meier", "forest_plot", "waterfall", "swimmer", "spider"]
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_study_design_specs",
            "description": "Get study design specifications (randomized, single-arm, crossover, adaptive, basket, umbrella). Use for Study Design section.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "design_type": {
                        "type": "string",
                        "description": "Type of study design"
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_programming_specifications",
            "description": "Get programming specifications (analysis windows, baseline definitions, derived variables). Use for Programming Specifications section.",
            "input_schema": {"type": "object", "properties": {}, "required": []}
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
        # v68: Previously unexposed KB content
        "get_safety_analysis_specs": lambda: kb.get_safety_analysis_specs(tool_input.get("analysis_type", "all")),
        "get_tfl_shells": lambda: kb.get_tfl_shells(tool_input.get("shell_type", "all")),
        "get_programming_specifications": lambda: kb.get_programming_specifications(),
        # v75: TTE derivation, MedDRA, concordance, references
        "get_tte_derivation_tables": lambda: kb.get_tte_derivation_tables(tool_input.get("endpoint", "all")),
        "get_meddra_search_strategies": lambda: kb.get_meddra_search_strategies(tool_input.get("category", "all")),
        "get_concordance_analysis": lambda: kb.get_concordance_analysis(),
        "get_required_references": lambda: kb.get_required_references(tool_input.get("study_type", "oncology")),
        "get_date_imputation_rules": lambda: kb.get_date_imputation_rules(),
        # v76: Comprehensive SAP Elements
        "get_study_definitions": lambda: kb.get_study_definitions(tool_input.get("definition_type", "all")),
        "get_exposure_specifications": lambda: kb.get_exposure_specifications(tool_input.get("exposure_type", "all")),
        "get_cart_manufacturing_specs": lambda: kb.get_cart_manufacturing_specs(),
        "get_subsequent_therapy_specs": lambda: kb.get_subsequent_therapy_specs(),
        "get_enrollment_specifications": lambda: kb.get_enrollment_specifications(),
        "get_ae_period_specifications": lambda: kb.get_ae_period_specifications(),
        "get_sensitivity_analysis_catalog": lambda: kb.get_sensitivity_analysis_catalog(tool_input.get("analysis_type", "all")),
        "get_multiplicity_methods": lambda: kb.get_multiplicity_methods(tool_input.get("method_type", "all")),
        "get_interim_analysis_specs": lambda: kb.get_interim_analysis_specs(tool_input.get("spec_type", "all")),
        "get_qol_analysis_specs": lambda: kb.get_qol_analysis_specs(tool_input.get("instrument", "all")),
        "get_estimand_specifications": lambda: kb.get_estimand_specifications(),
        "get_covid19_variations": lambda: kb.get_covid19_variations(),
        "get_subgroup_specifications": lambda: kb.get_subgroup_specifications(),
        "get_protocol_deviation_specs": lambda: kb.get_protocol_deviation_specs(),
        "get_healthcare_utilization_specs": lambda: kb.get_healthcare_utilization_specs(),
        "get_phase2_design_specs": lambda: kb.get_phase2_design_specs(),
        "get_blinding_specifications": lambda: kb.get_blinding_specifications(),
        "get_pkpd_analysis_specs": lambda: kb.get_pkpd_analysis_specs(tool_input.get("spec_type", "all")),
        "get_mrd_assessment_specs": lambda: kb.get_mrd_assessment_specs(),
        "get_comprehensive_sap_elements": lambda: kb.get_comprehensive_sap_elements(tool_input.get("study_type", "oncology")),
        # v77: Additional comprehensive SAP elements
        "get_demographics_baseline_specs": lambda: kb.get_demographics_baseline_specs(),
        "get_baseline_covariates": lambda: kb.get_baseline_covariates(tool_input.get("disease_type")),
        "get_prior_therapy_specs": lambda: kb.get_prior_therapy_specs(),
        "get_concomitant_medication_specs": lambda: kb.get_concomitant_medication_specs(),
        "get_medical_history_specs": lambda: kb.get_medical_history_specs(),
        "get_death_analysis_specs": lambda: kb.get_death_analysis_specs(),
        "get_tumor_response_specs": lambda: kb.get_tumor_response_specs(),
        "get_treatment_compliance_specs": lambda: kb.get_treatment_compliance_specs(),
        "get_concordance_specs": lambda: kb.get_concordance_specs(),
        "get_immunogenicity_specs": lambda: kb.get_immunogenicity_specs(),
        "get_organ_function_specs": lambda: kb.get_organ_function_specs(),
        "get_analysis_timing_specs": lambda: kb.get_analysis_timing_specs(),
        "get_follow_up_analysis_specs": lambda: kb.get_follow_up_analysis_specs(tool_input.get("timepoint", "all")),
        "get_stratification_balance_specs": lambda: kb.get_stratification_balance_specs(),
        "get_figure_template": lambda: kb.get_figure_template(tool_input.get("figure_type", "kaplan_meier")),
        "get_study_design_specs": lambda: kb.get_study_design_specs(tool_input.get("design_type")),
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
