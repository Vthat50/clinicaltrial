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
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


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
