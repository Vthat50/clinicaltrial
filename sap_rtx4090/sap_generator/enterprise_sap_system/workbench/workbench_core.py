"""
SAP Workbench Core
==================

Section-by-section SAP generation workbench.
Keeps existing one-shot generation untouched.

Author: SAP Generation System
"""

import json
import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid

try:
    import anthropic
except ImportError:
    print("Installing anthropic...")
    os.system("pip install anthropic")
    import anthropic

# Supabase for persistent storage
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("Warning: supabase-py not installed. Run: pip install supabase")

# Import KG extraction and KB tools
try:
    from enterprise_sap_system.knowledge_graph.kg_enhanced_pipeline import EnhancedKGPipeline
    from enterprise_sap_system.knowledge_graph.kb_tools import (
        KnowledgeBaseTools,
        get_claude_tool_definitions,
        execute_tool
    )
    from enterprise_sap_system.knowledge_graph.sap_structure_config import (
        MASTER_SAP_SECTIONS,
        detect_sap_conditions
    )
    from enterprise_sap_system.knowledge_graph.llm_parser import LLMParser
    KG_AVAILABLE = True
except ImportError:
    try:
        from ..knowledge_graph.kg_enhanced_pipeline import EnhancedKGPipeline
        from ..knowledge_graph.kb_tools import (
            KnowledgeBaseTools,
            get_claude_tool_definitions,
            execute_tool
        )
        from ..knowledge_graph.sap_structure_config import (
            MASTER_SAP_SECTIONS,
            detect_sap_conditions
        )
        from ..knowledge_graph.llm_parser import LLMParser
        KG_AVAILABLE = True
    except ImportError:
        KG_AVAILABLE = False
        MASTER_SAP_SECTIONS = []
        LLMParser = None
        print("Warning: KG pipeline not available, using basic extraction")

# v93: Import SDTM generator for SAP → SDTM mapping
try:
    from enterprise_sap_system.specs.sdtm_specs import (
        SDTMSpecGenerator,
        SDTMSpecification,
        create_sdtm_spec_generator
    )
    SDTM_AVAILABLE = True
except ImportError:
    try:
        from ..specs.sdtm_specs import (
            SDTMSpecGenerator,
            SDTMSpecification,
            create_sdtm_spec_generator
        )
        SDTM_AVAILABLE = True
    except ImportError:
        SDTM_AVAILABLE = False
        SDTMSpecGenerator = None
        SDTMSpecification = None
        print("Warning: SDTM generator not available")


class SectionStatus(Enum):
    """Status of each SAP section."""
    NOT_STARTED = "not_started"
    GENERATING = "generating"
    DRAFT = "draft"
    EDITED = "edited"
    APPROVED = "approved"


@dataclass
class ProtocolMetadata:
    """Structured metadata extracted from protocol using 55-category KG extraction."""
    study_id: str = ""
    study_title: str = ""
    phase: str = ""
    therapeutic_area: str = ""
    indication: str = ""

    # Extracted elements (basic - for backward compat)
    objectives: List[Dict] = field(default_factory=list)
    endpoints: List[Dict] = field(default_factory=list)
    populations: List[Dict] = field(default_factory=list)
    treatment_arms: List[Dict] = field(default_factory=list)
    stratification_factors: List[str] = field(default_factory=list)
    sample_size: Optional[int] = None
    statistical_methods: List[Dict] = field(default_factory=list)
    visit_schedule: List[Dict] = field(default_factory=list)

    # FULL 55-category KG extraction (new)
    full_extraction: Dict = field(default_factory=dict)

    # Disease-specific info (from KG extraction)
    disease_setting: str = ""  # adjuvant/neoadjuvant/metastatic
    performance_status_scale: str = ""  # ECOG/ASA/Karnofsky
    response_criteria: str = ""  # RECIST/irRECIST/Lugano/etc
    geographic_countries: List[str] = field(default_factory=list)
    baseline_variables: List[Dict] = field(default_factory=list)

    # Prohibition rules (for generation)
    prohibition_rules: List[str] = field(default_factory=list)

    # Source tracking
    extraction_timestamp: str = ""
    protocol_hash: str = ""
    extraction_method: str = "basic"  # "basic" or "kg_55_category"


@dataclass
class SAPSection:
    """A single SAP section with provenance."""
    id: str
    name: str
    display_name: str
    status: SectionStatus = SectionStatus.NOT_STARTED
    content: str = ""

    # Provenance - track all sources
    protocol_excerpts_used: List[str] = field(default_factory=list)  # Protocol sections referenced
    metadata_used: List[str] = field(default_factory=list)  # Extraction fields used
    kb_tools_used: List[Dict] = field(default_factory=list)  # KB tools called with source info
    generated_at: str = ""
    edited_at: str = ""
    user_comments: str = ""

    # Version tracking
    version: int = 1
    history: List[Dict] = field(default_factory=list)


@dataclass
class StudyWorkspace:
    """A complete study workspace."""
    id: str
    name: str
    created_at: str
    updated_at: str

    # Protocol
    protocol_content: str = ""
    protocol_filename: str = ""
    protocol_hash: str = ""

    # User inputs
    phase: str = ""
    therapeutic_area: str = ""
    indication: str = ""

    # Extracted metadata
    metadata: Optional[ProtocolMetadata] = None

    # SAP sections
    sections: Dict[str, SAPSection] = field(default_factory=dict)

    # Change tracking
    protocol_versions: List[Dict] = field(default_factory=list)

    # Protocol conditions for dynamic section filtering (v90)
    protocol_conditions: Dict[str, bool] = field(default_factory=dict)

    # v93: SDTM specification generated from SAP
    sdtm_spec: Optional[Dict] = None
    sdtm_generated_at: Optional[str] = None


# =============================================================================
# USE MASTER_SAP_SECTIONS FROM sap_structure_config.py (Single Source of Truth)
# =============================================================================
# No more duplicate SAP_SECTIONS list - use MASTER_SAP_SECTIONS directly
# This ensures workbench always stays in sync with the authoritative structure


def detect_conditions_from_text(protocol_text: str) -> Dict[str, bool]:
    """
    Quick condition detection from raw protocol text (keyword-based).

    Used when full extraction isn't available yet (e.g., at workspace creation).
    Returns dict of condition_name -> bool for section filtering.
    """
    text_lower = protocol_text.lower()
    conditions = {}

    # Study Design
    conditions["is_randomized"] = any(x in text_lower for x in ["randomized", "randomised", "randomization"])
    conditions["is_single_arm"] = "single-arm" in text_lower or "single arm" in text_lower
    conditions["is_blinded"] = any(x in text_lower for x in ["double-blind", "double blind", "blinded"])
    conditions["is_adaptive"] = "adaptive" in text_lower

    # Endpoints
    conditions["has_tte_endpoints"] = any(x in text_lower for x in ["survival", "progression-free", "pfs", "efs", "dfs", "event-free", "time to"])
    conditions["has_pfs_endpoint"] = "pfs" in text_lower or "progression-free survival" in text_lower
    conditions["has_os_endpoint"] = "overall survival" in text_lower or " os " in text_lower
    conditions["has_dor_endpoint"] = any(x in text_lower for x in ["duration of response", "dor", "duration of remission"])
    conditions["has_response_endpoint"] = any(x in text_lower for x in ["objective response", "orr", "response rate", "complete response", "partial response"])
    conditions["has_exploratory_endpoints"] = "exploratory" in text_lower and "endpoint" in text_lower
    conditions["has_biomarker_endpoints"] = any(x in text_lower for x in ["biomarker", "pd-l1", "tmb", "msi", "ctdna", "mrd"])

    # PRO/QoL
    conditions["has_pro_endpoints"] = any(x in text_lower for x in [
        "quality of life", "qol", "patient-reported", "eortc", "qlq-c30", "qlq-lc13",
        "eq-5d", "fact-", "facit", "sf-36", "euroqol", "health-related quality"
    ])

    # PK
    conditions["has_pk_endpoints"] = any(x in text_lower for x in ["pharmacokinetic", " pk ", "auc", "cmax", "tmax", "half-life"])

    # Therapy Types
    conditions["is_cart"] = any(x in text_lower for x in ["car-t", "car t", "chimeric antigen receptor", "axicabtagene", "tisagenlecleucel", "liso-cel"])
    conditions["is_cart_with_retreatment"] = conditions["is_cart"] and "retreatment" in text_lower
    conditions["is_bispecific"] = "bispecific" in text_lower or "bite" in text_lower
    conditions["is_adc"] = "antibody-drug conjugate" in text_lower or " adc " in text_lower
    conditions["is_immunotherapy"] = any(x in text_lower for x in ["checkpoint", "pd-1", "pd-l1", "ctla-4", "immunotherapy", "anti-pd", "pembrolizumab", "nivolumab", "durvalumab", "atezolizumab"])
    conditions["is_biologic"] = any(x in text_lower for x in ["antibody", "monoclonal", "biologic"])

    # Disease Types
    conditions["is_lymphoma"] = any(x in text_lower for x in ["lymphoma", "dlbcl", "follicular", "mantle cell", "hodgkin"])
    conditions["is_hematologic"] = any(x in text_lower for x in ["lymphoma", "leukemia", "myeloma", "hematologic", "aml", "all", "cll"])
    conditions["is_solid_tumor"] = not conditions["is_hematologic"] and any(x in text_lower for x in ["tumor", "tumour", "carcinoma", "adenocarcinoma", "nsclc", "breast", "lung", "colon", "melanoma"])

    # Study Features
    conditions["has_interim_analysis"] = "interim analysis" in text_lower or "interim analyses" in text_lower
    conditions["has_multiple_arms"] = any(x in text_lower for x in ["treatment arm", "control arm", "placebo arm", "arm a", "arm b"])
    conditions["has_stratification"] = "stratif" in text_lower  # catches stratification, stratified
    conditions["has_subgroups"] = "subgroup" in text_lower

    # Phase
    conditions["is_phase1"] = any(x in text_lower for x in ["phase 1", "phase i", "dose escalation", "dose-escalation", "dlt", "mtd"])

    # Special Features
    conditions["has_sensitivity_analyses"] = "sensitivity analysis" in text_lower or "sensitivity analyses" in text_lower
    conditions["has_missing_data"] = any(x in text_lower for x in ["missing data", "imputation", "missing values"])

    return conditions


def get_workbench_sections(conditions: Dict[str, bool] = None) -> List[tuple]:
    """
    Get SAP sections for workbench from MASTER_SAP_SECTIONS.

    Args:
        conditions: Dict of condition_name -> bool for filtering conditional sections

    Returns:
        List of (section_number, section_title) tuples
    """
    if not MASTER_SAP_SECTIONS:
        # Fallback if import failed
        return [
            ("1", "Title Page"),
            ("2", "Introduction"),
            ("3", "Study Design"),
            ("4", "Sample Size"),
            ("5", "Analysis Populations"),
            ("6", "Endpoints"),
            ("7", "Statistical Methods"),
            ("12", "Safety Analysis"),
            ("16", "Definitions"),
            ("18", "TFL Shells"),
            ("22", "References"),
        ]

    conditions = conditions or {}
    sections = []

    def add_section(sec):
        """Recursively add section and subsections."""
        # Check if section should be included based on condition
        if sec.condition and not conditions.get(sec.condition, False):
            # For conditional sections, still include if condition not evaluated
            # This allows manual generation
            if sec.condition not in conditions:
                pass  # Include anyway
            else:
                return  # Skip - condition explicitly False

        sections.append((sec.number, sec.title))

        # Add subsections
        for sub in sec.subsections:
            add_section(sub)

    for sec in MASTER_SAP_SECTIONS:
        add_section(sec)

    return sections


def get_section_kb_tools(section_number: str) -> List[str]:
    """
    Get KB tools for a section from MASTER_SAP_SECTIONS.

    Args:
        section_number: The section number (e.g., "12", "5A", "A.2")

    Returns:
        List of KB tool names to call for this section
    """
    if not MASTER_SAP_SECTIONS:
        return []

    def find_section(sections, number):
        for sec in sections:
            if sec.number == number:
                return sec
            # Search subsections
            found = find_section(sec.subsections, number)
            if found:
                return found
        return None

    section = find_section(MASTER_SAP_SECTIONS, section_number)
    if section:
        return section.kb_tools
    return []


def get_section_by_number(section_number: str):
    """Get a SAPSection object by its number."""
    if not MASTER_SAP_SECTIONS:
        return None

    def find_section(sections, number):
        for sec in sections:
            if sec.number == number:
                return sec
            found = find_section(sec.subsections, number)
            if found:
                return found
        return None

    return find_section(MASTER_SAP_SECTIONS, section_number)


class SAPWorkbench:
    """
    SAP Workbench for section-by-section generation.

    Workflow:
    1. Create workspace (upload protocol + metadata)
    2. Extract structured metadata
    3. Generate sections one at a time
    4. Edit/approve sections
    5. Track changes if protocol updates
    6. Export final SAP
    """

    def __init__(
        self,
        api_key: str,
        supabase_url: str = None,
        supabase_key: str = None,
        use_kg: bool = True
    ):
        self.api_key = api_key
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"

        # Supabase storage (required for persistence)
        self.supabase: Optional[Client] = None
        if supabase_url and supabase_key and SUPABASE_AVAILABLE:
            try:
                self.supabase = create_client(supabase_url, supabase_key)
                print(f"✅ Supabase storage initialized")
            except Exception as e:
                print(f"❌ Supabase init failed: {e}")
                raise RuntimeError(f"Supabase connection failed: {e}")
        else:
            if not SUPABASE_AVAILABLE:
                raise RuntimeError("supabase-py not installed. Run: pip install supabase")
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required for workspace storage")

        # In-memory cache
        self.workspaces: Dict[str, StudyWorkspace] = {}

        # KG Pipeline for 55-category extraction
        self.use_kg = use_kg and KG_AVAILABLE
        self.kg_pipeline = None
        self.kb_tools = None

        if self.use_kg:
            try:
                self.kg_pipeline = EnhancedKGPipeline(api_key)
                self.kb_tools = KnowledgeBaseTools()
                print(f"✅ SAP Workbench initialized with KG Pipeline (55-category extraction)")
            except Exception as e:
                print(f"Warning: KG Pipeline init failed: {e}")
                self.use_kg = False

        if not self.use_kg:
            print(f"✅ SAP Workbench initialized (basic extraction)")

        print(f"   Storage: Supabase (workspaces table)")

    # =========================================================================
    # KB TOOLS INTEGRATION
    # =========================================================================

    def _get_kb_content_for_section(self, section_id: str, metadata: Optional[Any] = None) -> tuple:
        """
        Get KB content for a section by calling the appropriate KB tools.

        Uses MASTER_SAP_SECTIONS from sap_structure_config.py as single source of truth.

        Returns:
            tuple: (kb_content_string, list_of_kb_tools_used)
        """
        if not self.kb_tools:
            return "", []

        # Get KB tools from MASTER_SAP_SECTIONS (single source of truth)
        kb_tool_names = get_section_kb_tools(section_id)

        # Also check parent section (e.g., "12" for "12.8")
        if not kb_tool_names and "." in section_id:
            parent = section_id.split(".")[0]
            kb_tool_names = get_section_kb_tools(parent)

        if not kb_tool_names:
            return "", []

        # Detect conditions from metadata to determine which tools to call
        conditions = {}
        if metadata and hasattr(metadata, 'full_extraction') and metadata.full_extraction:
            try:
                conditions = detect_sap_conditions(metadata.full_extraction)
            except Exception:
                conditions = {}

        # Also detect from metadata fields directly
        if metadata:
            # Check for CAR-T
            product_name = (metadata.indication or "").lower()
            therapeutic_area = (metadata.therapeutic_area or "").lower()
            if any(x in product_name + therapeutic_area for x in ["car-t", "cart", "cell therapy", "axicabtagene"]):
                conditions["is_cart"] = True
                conditions["is_cart_with_retreatment"] = True

            # Check for single-arm
            if metadata.full_extraction:
                design = metadata.full_extraction.get("study_design", {})
                design_type = (design.get("design_type", {}).get("value") or "").lower()
                if "single" in design_type:
                    conditions["is_single_arm"] = True

        kb_content_parts = []
        kb_tools_used = []  # Track which tools were called

        for tool_name in kb_tool_names:
            try:
                # Skip CAR-T tools if not a CAR-T study
                if tool_name in ["get_cart_specifications", "get_cart_tables", "get_cart_manufacturing_specs"]:
                    if not conditions.get("is_cart"):
                        continue

                # Skip single-arm tools if not single-arm
                if tool_name == "get_single_arm_tables":
                    if not conditions.get("is_single_arm"):
                        continue

                # Call the KB tool
                tool_method = getattr(self.kb_tools, tool_name, None)
                if tool_method:
                    result = tool_method()
                    if result and result.content:
                        content_str = json.dumps(result.content, indent=2, default=str)
                        # Limit content size to avoid prompt explosion
                        if len(content_str) > 8000:
                            content_str = content_str[:8000] + "\n... [truncated]"
                        kb_content_parts.append(f"### {tool_name}\n{content_str}")

                        # Track provenance
                        kb_tools_used.append({
                            "tool_name": tool_name,
                            "source_file": getattr(result, 'source_file', 'methodology_knowledge_base.py'),
                            "source_key": getattr(result, 'source_key', tool_name.upper()),
                            "description": f"KB: {tool_name.replace('get_', '').replace('_', ' ').title()}"
                        })
            except Exception as e:
                print(f"[KB] Warning: Failed to call {tool_name}: {e}")
                continue

        if not kb_content_parts:
            return "", []

        return "\n\n".join(kb_content_parts), kb_tools_used

    # =========================================================================
    # WORKSPACE MANAGEMENT
    # =========================================================================

    def create_workspace(
        self,
        protocol_content: str,
        protocol_filename: str,
        phase: str = "",
        therapeutic_area: str = "",
        indication: str = ""
    ) -> StudyWorkspace:
        """Create a new study workspace with dynamic section filtering based on protocol."""

        workspace_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        protocol_hash = hashlib.md5(protocol_content.encode()).hexdigest()

        # v90: Detect protocol conditions for dynamic section filtering
        protocol_conditions = detect_conditions_from_text(protocol_content)

        # Log detected conditions for debugging
        active_conditions = [k for k, v in protocol_conditions.items() if v]
        print(f"[Workbench] Detected {len(active_conditions)} conditions: {', '.join(active_conditions[:10])}")

        # Initialize sections from MASTER_SAP_SECTIONS with condition filtering
        sections = {}
        for section_number, section_title in get_workbench_sections(protocol_conditions):
            sections[section_number] = SAPSection(
                id=section_number,
                name=section_number,
                display_name=section_title,
                status=SectionStatus.NOT_STARTED
            )

        print(f"[Workbench] Initialized {len(sections)} relevant sections (filtered from MASTER_SAP_SECTIONS)")

        workspace = StudyWorkspace(
            id=workspace_id,
            name=protocol_filename.replace('.txt', '').replace('.pdf', ''),
            created_at=now,
            updated_at=now,
            protocol_content=protocol_content,
            protocol_filename=protocol_filename,
            protocol_hash=protocol_hash,
            phase=phase,
            therapeutic_area=therapeutic_area,
            indication=indication,
            sections=sections,
            protocol_conditions=protocol_conditions,
            protocol_versions=[{
                "version": 1,
                "hash": protocol_hash,
                "uploaded_at": now,
                "filename": protocol_filename
            }]
        )

        self.workspaces[workspace_id] = workspace
        self._save_workspace(workspace)

        return workspace

    def get_workspace(self, workspace_id: str) -> Optional[StudyWorkspace]:
        """Get a workspace by ID."""
        if workspace_id in self.workspaces:
            return self.workspaces[workspace_id]

        # Try loading from Supabase
        return self._load_workspace(workspace_id)

    def list_workspaces(self) -> List[Dict]:
        """List all workspaces from Supabase."""
        try:
            result = self.supabase.table("workspaces").select(
                "id, created_at, updated_at, protocol_filename, metadata"
            ).order("updated_at", desc=True).execute()

            workspaces = []
            for row in result.data:
                metadata = row.get("metadata") or {}
                workspaces.append({
                    "id": row["id"],
                    "name": metadata.get("study_title", row.get("protocol_filename", "Untitled")),
                    "created_at": row["created_at"],
                    "phase": metadata.get("phase", ""),
                    "therapeutic_area": metadata.get("therapeutic_area", "")
                })
            return workspaces
        except Exception as e:
            print(f"Error listing workspaces: {e}")
            return []

    # =========================================================================
    # METADATA EXTRACTION
    # =========================================================================

    def extract_metadata(self, workspace_id: str) -> ProtocolMetadata:
        """Extract structured metadata using 55-category KG extraction when available."""

        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        # Use KG extraction if available
        if self.use_kg and self.kg_pipeline:
            return self._extract_metadata_kg(workspace)
        else:
            return self._extract_metadata_basic(workspace)

    def _extract_metadata_kg(self, workspace: StudyWorkspace) -> ProtocolMetadata:
        """Extract using 55-category KG pipeline."""
        import tempfile

        try:
            # Write protocol to temp file for KG pipeline
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(workspace.protocol_content)
                temp_path = f.name

            # Run KG extraction (this uses the 55-category prompt)
            # Access the _extract_entities method directly
            doc_id = f"doc:{workspace.id}"
            extracted_list = self.kg_pipeline._extract_entities(
                workspace.protocol_content, doc_id
            )

            # Get the full extraction object
            full_extraction = getattr(self.kg_pipeline, '_last_full_extraction', {}) or {}

            # === DETAILED EXTRACTION LOGGING ===
            print("\n" + "="*70)
            print("FULL EXTRACTION DEBUG - All Fields (with values)")
            print("="*70)

            # Helper to extract display value from nested structures
            def get_display_value(item, keys_to_try):
                for k in keys_to_try:
                    if isinstance(item, dict):
                        val = item.get(k)
                        if isinstance(val, dict):
                            val = val.get("value", val)
                        if val:
                            return str(val)[:60]
                return str(item)[:60] if item else "[empty]"

            for key, value in full_extraction.items():
                val_type = type(value).__name__
                if isinstance(value, list):
                    print(f"  {key}: [{val_type}] {len(value)} items")
                    for i, item in enumerate(value[:3]):  # Show first 3
                        if isinstance(item, dict):
                            # Show actual values for common keys
                            display = get_display_value(item, ["name", "factor", "factor_name", "endpoint", "variable_name", "country", "region", "category"])
                            print(f"    [{i}]: {display}")
                        else:
                            print(f"    [{i}]: {str(item)[:60]}")
                    if len(value) > 3:
                        print(f"    ... and {len(value) - 3} more")
                elif isinstance(value, dict):
                    # Show nested values for important fields
                    if key in ["sample_size", "trial_identification", "study_phase", "geographic", "randomization"]:
                        print(f"  {key}: [{val_type}]")
                        for k, v in list(value.items())[:5]:
                            if isinstance(v, dict) and "value" in v:
                                print(f"    {k}: {v.get('value', '[no value]')}")
                            elif isinstance(v, list):
                                print(f"    {k}: {len(v)} items")
                            else:
                                print(f"    {k}: {str(v)[:50]}")
                    else:
                        print(f"  {key}: [{val_type}] keys={list(value.keys())[:5]}")
                elif value is None:
                    print(f"  {key}: [None]")
                else:
                    print(f"  {key}: [{val_type}] {str(value)[:60]}")
            print("="*70 + "\n")

            # Build prohibition rules
            prohibition_rules = self._build_prohibition_rules(full_extraction)

            # Extract key fields from full extraction
            trial_id = full_extraction.get("trial_identification", {})
            disease = full_extraction.get("disease_classification", {})
            ps = full_extraction.get("performance_status", {})
            rc = full_extraction.get("response_criteria_details", {})
            geo = full_extraction.get("geographic", {})

            # Get countries and regions
            countries = []
            geo_data = geo if isinstance(geo, dict) else {}
            # Try countries list first
            for c in geo_data.get("countries", []):
                if isinstance(c, dict) and c.get("country"):
                    countries.append(c.get("country"))
                elif isinstance(c, str) and c:
                    countries.append(c)
            # Also include regions if no countries found
            if not countries:
                for r in geo_data.get("regions", []):
                    if isinstance(r, dict) and r.get("region"):
                        countries.append(r.get("region"))
                    elif isinstance(r, str) and r:
                        countries.append(r)

            # Convert endpoints
            endpoints = []
            for ep in full_extraction.get("primary_endpoints", []):
                if ep.get("name"):
                    endpoints.append({
                        "name": ep.get("name"),
                        "type": "primary",
                        "definition": ep.get("definition", ""),
                        "timeframe": ep.get("assessment_schedule", ""),
                        "response_criteria": ep.get("response_criteria", "")
                    })
            for ep in full_extraction.get("secondary_endpoints", []):
                if ep.get("name"):
                    endpoints.append({
                        "name": ep.get("name"),
                        "type": "secondary",
                        "definition": ep.get("definition", "")
                    })

            # Convert populations (handles both list and dict formats)
            populations = []
            pops = full_extraction.get("populations", [])
            if isinstance(pops, list):
                # New dynamic list format
                for pop in pops:
                    if pop.get("name"):
                        populations.append({
                            "name": pop.get("name", ""),
                            "abbreviation": pop.get("abbreviation", pop.get("name", "")).upper(),
                            "definition": pop.get("definition", "")
                        })
            elif isinstance(pops, dict):
                # Legacy dict format (backward compatibility)
                for pop_key in ["itt_definition", "mitt_definition", "pp_definition", "safety_definition"]:
                    pop = pops.get(pop_key, {})
                    if pop and pop.get("value"):
                        populations.append({
                            "name": pop_key.replace("_definition", "").upper(),
                            "abbreviation": pop_key.replace("_definition", "").upper(),
                            "definition": pop.get("value")
                        })

            # Convert treatment arms
            treatment_arms = []
            for arm in full_extraction.get("treatment_arms", []):
                if arm.get("arm_name"):
                    treatment_arms.append({
                        "name": arm.get("arm_name"),
                        "description": f"{arm.get('drug_name', '')} {arm.get('dose', '')} {arm.get('schedule', '')}".strip()
                    })

            # Get stratification factors (handles both "factor_name" and "factor" keys)
            strat_factors = []
            rand = full_extraction.get("randomization", {})
            rand_strat = rand.get("stratification_factors", []) if isinstance(rand, dict) else []
            for sf in rand_strat:
                # Try factor_name first (Stage 2 schema), then factor (Stage 1 schema)
                factor = sf.get("factor_name") or sf.get("factor")
                if factor:
                    strat_factors.append(factor)

            # Fallback: check subgroups with is_stratification_factor=True
            if not strat_factors:
                for sg in full_extraction.get("subgroups", []):
                    if sg.get("is_stratification_factor") and sg.get("factor"):
                        strat_factors.append(sg.get("factor"))

            # Fallback: check top-level stratification_factors (Stage 1 output)
            if not strat_factors:
                for sf in full_extraction.get("stratification_factors", []):
                    factor = sf.get("factor_name") or sf.get("factor")
                    if factor:
                        strat_factors.append(factor)

            # Get sample size (handles list, dict with total_n, or dict with n)
            ss = full_extraction.get("sample_size", {})
            sample_size_val = None
            if isinstance(ss, list) and ss:
                # List format: use first entry's n value
                sample_size_val = ss[0].get("n") if ss[0] else None
            elif isinstance(ss, dict):
                # Dict format: try total_n.value first, then n directly
                if ss.get("total_n"):
                    sample_size_val = ss.get("total_n", {}).get("value")
                elif ss.get("n"):
                    sample_size_val = ss.get("n")
            if sample_size_val:
                try:
                    sample_size_val = int(sample_size_val)
                except:
                    sample_size_val = None

            # === LOG CONVERTED VALUES ===
            print("\n" + "-"*70)
            print("CONVERTED METADATA VALUES")
            print("-"*70)
            print(f"  endpoints: {len(endpoints)} items")
            print(f"  populations: {len(populations)} items -> {[p.get('name') for p in populations]}")
            print(f"  treatment_arms: {len(treatment_arms)} items")
            print(f"  strat_factors: {strat_factors}")
            print(f"  sample_size: {sample_size_val} (raw type: {type(ss).__name__})")
            print(f"  countries: {countries}")
            print(f"  prohibition_rules: {prohibition_rules}")
            print("-"*70 + "\n")

            metadata = ProtocolMetadata(
                study_id=trial_id.get("nct_id", {}).get("value", "") or trial_id.get("protocol_number", {}).get("value", ""),
                study_title=trial_id.get("study_title", {}).get("value", ""),
                phase=full_extraction.get("study_phase", {}).get("phase", {}).get("value", workspace.phase),
                therapeutic_area=workspace.therapeutic_area,
                indication=disease.get("tumor_type", {}).get("value", workspace.indication),
                objectives=[],  # Populated separately if needed
                endpoints=endpoints,
                populations=populations,
                treatment_arms=treatment_arms,
                stratification_factors=strat_factors,
                sample_size=sample_size_val,
                statistical_methods=[],
                visit_schedule=[],
                full_extraction=full_extraction,
                disease_setting=disease.get("disease_setting", {}).get("value", ""),
                performance_status_scale=ps.get("scale", {}).get("value", ""),
                response_criteria=rc.get("criteria_name", ""),
                geographic_countries=countries,
                baseline_variables=full_extraction.get("baseline_variables", []),
                prohibition_rules=prohibition_rules,
                extraction_timestamp=datetime.now().isoformat(),
                protocol_hash=workspace.protocol_hash,
                extraction_method="kg_55_category"
            )

            workspace.metadata = metadata
            workspace.updated_at = datetime.now().isoformat()

            # v91: Update protocol_conditions from extraction (same as generate_sap_with_tools)
            # This replaces the initial text-based detection with accurate extraction-based detection
            workspace.protocol_conditions = detect_sap_conditions(full_extraction)
            active_conditions = [k for k, v in workspace.protocol_conditions.items() if v]
            print(f"[Workbench] Updated conditions from extraction: {', '.join(active_conditions[:10])}")

            self._save_workspace(workspace)

            # Cleanup temp file
            import os
            os.unlink(temp_path)

            return metadata

        except Exception as e:
            print(f"KG extraction failed: {e}, falling back to basic")
            import traceback
            traceback.print_exc()
            return self._extract_metadata_basic(workspace)

    def _build_prohibition_rules(self, full_extraction: Dict) -> List[str]:
        """Build prohibition rules based on protocol extraction."""
        rules = []

        if not full_extraction:
            return rules

        # 1. Race/Ethnicity check
        baseline_vars = full_extraction.get("baseline_variables", [])
        var_names = [v.get("variable_name", "").lower() for v in baseline_vars if v.get("variable_name")]
        has_race = any("race" in v or "ethnicity" in v for v in var_names)

        geo = full_extraction.get("geographic", {})
        countries = [c.get("country", "").lower() for c in geo.get("countries", []) if c.get("country")]

        is_nordic = all(c in ["sweden", "norway", "denmark", "finland", "iceland"] for c in countries) if countries else False

        if not has_race:
            rules.append("DO NOT include Race or Ethnicity variables")
        if is_nordic:
            rules.append("DO NOT include North America, Asia, or Rest of World subgroups (Nordic study)")

        # 2. Performance status
        ps = full_extraction.get("performance_status", {})
        ps_scale = ps.get("scale", {}).get("value", "").upper() if ps else ""
        if ps_scale == "ASA":
            rules.append("DO NOT use ECOG - use ASA Score (1-5) for surgical patients")
        elif ps_scale == "KARNOFSKY":
            rules.append("DO NOT use ECOG - use Karnofsky Performance Status")

        # 3. Disease setting
        disease = full_extraction.get("disease_classification", {})
        setting = disease.get("disease_setting", {}).get("value", "").lower() if disease else ""
        if setting == "adjuvant":
            rules.append("DO NOT include CR/PR/SD/PD response tables (adjuvant = no measurable tumor)")
            rules.append("Use Hazard Ratio (not Odds Ratio) for time-to-event endpoints")

        # 4. Dose modifications
        dose_mods = full_extraction.get("dose_modifications", {})
        if not dose_mods.get("dose_reduction_rules"):
            rules.append("DO NOT include dose modification rows (fixed-dose study)")

        return rules

    def _extract_metadata_basic(self, workspace: StudyWorkspace) -> ProtocolMetadata:
        """Fallback basic extraction without KG."""

        prompt = f"""Extract structured metadata from this clinical trial protocol.

Return a JSON object with these fields:

{{
  "study_id": "NCT number or protocol ID",
  "study_title": "Full study title",
  "phase": "Phase 1/2/3/4",
  "therapeutic_area": "oncology/cardiology/etc",
  "indication": "Specific disease/condition",
  "objectives": [{{"type": "primary", "text": "..."}}],
  "endpoints": [{{"name": "", "type": "primary/secondary", "definition": ""}}],
  "populations": [{{"name": "", "abbreviation": "", "definition": ""}}],
  "treatment_arms": [{{"name": "", "description": ""}}],
  "stratification_factors": ["Factor 1"],
  "sample_size": 500,
  "statistical_methods": [{{"endpoint": "", "method": ""}}],
  "visit_schedule": [{{"visit": "", "timing": ""}}]
}}

PROTOCOL:
{workspace.protocol_content[:20000]}

Return ONLY valid JSON."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # v92: Use LLMParser for robust JSON parsing
            if LLMParser:
                parser = LLMParser(client=self.client, model=self.model)
                result = parser.parse(
                    response_text,
                    retry_with_llm=True,
                    context="Basic metadata extraction from protocol"
                )
                if not result.success:
                    raise ValueError(f"Parse failed: {result.error}")
                data = result.data
                if result.repairs_applied:
                    print(f"[Workbench] LLMParser applied repairs: {', '.join(result.repairs_applied)}")
            else:
                # Fallback if LLMParser not available
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                data = json.loads(response_text)

            metadata = ProtocolMetadata(
                study_id=data.get("study_id", ""),
                study_title=data.get("study_title", ""),
                phase=data.get("phase", workspace.phase),
                therapeutic_area=data.get("therapeutic_area", workspace.therapeutic_area),
                indication=data.get("indication", workspace.indication),
                objectives=data.get("objectives", []),
                endpoints=data.get("endpoints", []),
                populations=data.get("populations", []),
                treatment_arms=data.get("treatment_arms", []),
                stratification_factors=data.get("stratification_factors", []),
                sample_size=data.get("sample_size"),
                statistical_methods=data.get("statistical_methods", []),
                visit_schedule=data.get("visit_schedule", []),
                extraction_timestamp=datetime.now().isoformat(),
                protocol_hash=workspace.protocol_hash,
                extraction_method="basic"
            )

            workspace.metadata = metadata
            workspace.updated_at = datetime.now().isoformat()
            self._save_workspace(workspace)

            return metadata

        except Exception as e:
            print(f"Error extracting metadata: {e}")
            raise

    # =========================================================================
    # SECTION GENERATION
    # =========================================================================

    def get_outline(self, workspace_id: str) -> List[Dict]:
        """Get SAP outline with section statuses."""
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        outline = []
        # v90: Use stored protocol conditions for dynamic section filtering
        for section_number, section_title in get_workbench_sections(workspace.protocol_conditions):
            section = workspace.sections.get(section_number)
            if section:
                outline.append({
                    "id": section_number,
                    "name": section_title,
                    "status": section.status.value,
                    "has_content": bool(section.content),
                    "version": section.version,
                    "edited_at": section.edited_at
                })
        return outline

    def generate_section(
        self,
        workspace_id: str,
        section_id: str,
        regenerate: bool = False
    ) -> SAPSection:
        """Generate a single SAP section."""

        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        if section_id not in workspace.sections:
            raise ValueError(f"Unknown section: {section_id}")

        section = workspace.sections[section_id]

        # Don't regenerate approved sections unless forced
        if section.status == SectionStatus.APPROVED and not regenerate:
            return section

        # DEBUG: Log protocol content quality
        protocol_preview = workspace.protocol_content[:500] if workspace.protocol_content else "EMPTY"
        print(f"[WORKBENCH] Generating section: {section_id}")
        print(f"[WORKBENCH] Protocol content length: {len(workspace.protocol_content):,} chars")
        print(f"[WORKBENCH] Protocol preview: {protocol_preview[:200]}...")

        # Check if protocol looks like binary/garbled data
        if workspace.protocol_content and workspace.protocol_content.startswith('%PDF'):
            print(f"[WORKBENCH] WARNING: Protocol content starts with %PDF - this is RAW PDF bytes, not extracted text!")
            print(f"[WORKBENCH] This workspace was created BEFORE the PDF parsing fix. Please create a NEW workspace.")

        # Update status
        section.status = SectionStatus.GENERATING

        # Get KB content and track which tools were used for provenance
        kb_content, kb_tools_used = self._get_kb_content_for_section(section_id, workspace.metadata)
        if kb_content:
            print(f"[WORKBENCH] KB content added for section {section_id}: {len(kb_content):,} chars from {len(kb_tools_used)} tools")

        # Get section-specific prompt
        prompt = self._build_section_prompt(workspace, section_id, kb_content)
        print(f"[WORKBENCH] Prompt length: {len(prompt):,} chars")

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()

            # v99.6: Validate and auto-fix critical elements
            validation = self._validate_section(section_id, content)
            if not validation["passed"]:
                print(f"[WORKBENCH] Section {section_id} missing: {validation['missing']}")
                print(f"[WORKBENCH] Auto-fixing...")
                content = self._regenerate_section_fix(
                    section_id,
                    content,
                    validation["missing"],
                    workspace.protocol_content
                )
                # Verify fix worked
                recheck = self._validate_section(section_id, content)
                if recheck["passed"]:
                    print(f"[WORKBENCH] ✅ Section {section_id} fixed successfully")
                else:
                    print(f"[WORKBENCH] ⚠️ Section {section_id} still missing: {recheck['missing']}")

            # Save history if editing
            if section.content:
                section.history.append({
                    "version": section.version,
                    "content": section.content,
                    "saved_at": section.generated_at
                })
                section.version += 1

            section.content = content
            section.status = SectionStatus.DRAFT
            section.generated_at = datetime.now().isoformat()

            # Track provenance
            section.protocol_excerpts_used = self._get_relevant_excerpts(
                workspace.protocol_content, section_id
            )
            section.metadata_used = self._get_metadata_used(workspace.metadata, section_id)
            section.kb_tools_used = kb_tools_used  # Track KB sources

            workspace.updated_at = datetime.now().isoformat()
            self._save_workspace(workspace)

            return section

        except Exception as e:
            section.status = SectionStatus.NOT_STARTED
            raise e

    def _build_section_prompt(self, workspace: StudyWorkspace, section_id: str, kb_content: str = "") -> str:
        """Build prompt for generating a specific section with prohibition rules."""

        metadata = workspace.metadata

        # Build prohibition rules section
        prohibition_section = ""
        if metadata and metadata.prohibition_rules:
            prohibition_section = f"""
## PROHIBITED CONTENT (DO NOT INCLUDE):
{chr(10).join('- ' + rule for rule in metadata.prohibition_rules)}
"""

        # Build disease-specific context
        disease_context = ""
        if metadata:
            if metadata.disease_setting:
                disease_context += f"Disease Setting: {metadata.disease_setting.upper()}\n"
            if metadata.performance_status_scale:
                disease_context += f"Performance Status Scale: {metadata.performance_status_scale}\n"
            if metadata.response_criteria:
                disease_context += f"Response Criteria: {metadata.response_criteria}\n"
            if metadata.geographic_countries:
                disease_context += f"Countries: {', '.join(metadata.geographic_countries)}\n"

        # Build metadata context
        metadata_context = ""
        if metadata:
            metadata_context = f"""
## EXTRACTED METADATA (55-CATEGORY EXTRACTION)

Study: {metadata.study_id} - {metadata.study_title}
Phase: {metadata.phase}
Therapeutic Area: {metadata.therapeutic_area}
Indication: {metadata.indication}
{disease_context}

Endpoints:
{json.dumps(metadata.endpoints, indent=2)}

Populations:
{json.dumps(metadata.populations, indent=2)}

Treatment Arms:
{json.dumps(metadata.treatment_arms, indent=2)}

Stratification Factors:
{json.dumps(metadata.stratification_factors, indent=2)}

Sample Size: {metadata.sample_size}
"""
            # Add full extraction if available (for table_shells and detailed sections)
            if metadata.full_extraction and section_id in ["table_shells", "primary_analysis", "safety_analysis"]:
                # Add relevant parts of full extraction
                fe = metadata.full_extraction
                if section_id == "table_shells" and fe.get("baseline_variables"):
                    metadata_context += f"\nBaseline Variables (use ONLY these):\n{json.dumps(fe.get('baseline_variables', []), indent=2)}\n"
                if section_id == "safety_analysis" and fe.get("safety_endpoints"):
                    metadata_context += f"\nSafety Endpoints:\n{json.dumps(fe.get('safety_endpoints', {}), indent=2)}\n"

        # Get previously generated sections for context
        prev_sections = ""
        for sec_id, section in workspace.sections.items():
            if section.content and sec_id != section_id:
                prev_sections += f"\n### {section.display_name}\n{section.content[:800]}...\n"

        # Section-specific instructions
        section_instructions = self._get_section_instructions(section_id)

        # Build KB section from passed content
        kb_section = ""
        if kb_content:
            kb_section = f"""
## KNOWLEDGE BASE REFERENCE (USE THIS CONTENT)
The following is from the validated knowledge base. Use these specifications
when writing this section. For CAR-T studies, use the CRS grading scale
and population definitions provided. For single-arm studies, use the
appropriate table shells.

{kb_content}
"""

        prompt = f"""Generate the "{workspace.sections[section_id].display_name}" section of a Statistical Analysis Plan.

## CRITICAL RULES:
1. Follow the protocol EXACTLY - do not add generic content
2. Use ONLY variables and categories from the extraction
3. Respect ALL prohibition rules below
4. USE the Knowledge Base content provided below for standard specifications
{prohibition_section}

{metadata_context}
{kb_section}

## PREVIOUSLY GENERATED SECTIONS (for context)
{prev_sections if prev_sections else "(None yet)"}

## PROTOCOL CONTENT
{workspace.protocol_content[:12000]}

## SECTION-SPECIFIC INSTRUCTIONS
{section_instructions}

## OUTPUT FORMAT
Generate ONLY the content for this section.
Use proper markdown formatting.
Be specific to this protocol - no generic templates.
Mark anything not in the protocol as [TO BE CONFIRMED].
For CAR-T studies: Include CRS grading scale (Lee 2014 or ASTCT as per protocol).
For all studies: Include proper definitions section with Study Day, Baseline, TEAE.

Generate the {workspace.sections[section_id].display_name} section now:"""

        return prompt

    def _get_section_instructions(self, section_id: str) -> str:
        """Get specific instructions for each section type."""

        instructions = {
            "study_info": """
Include:
- Study title and ID
- Sponsor
- Phase
- Study design (randomization, blinding, etc.)
- Study duration
""",
            "objectives": """
Include:
- Primary objective(s)
- Secondary objective(s)
- Exploratory objectives (if any)
Format as numbered list with clear hierarchy.
""",
            "endpoints": """
Include for each endpoint:
- Name
- Type (primary/secondary/exploratory)
- Definition
- Timeframe
- Assessment method
""",
            "estimands": """
For each primary/key secondary endpoint, define:
- Population
- Variable (endpoint)
- Intercurrent events and handling strategies
- Population-level summary
""",
            "populations": """
Define each analysis population:
- Name and abbreviation
- Definition (inclusion criteria)
- Primary use (which analyses)

For CAR-T studies (use Knowledge Base content):
- Include Safety Re-treatment Analysis Set if protocol allows retreatment
- Include Inferential Analysis Set (subjects meeting pivotal cohort criteria)
- Include mITT (subjects who received CAR-T infusion)
""",
            "statistical_methods": """
Include:
- Hypothesis testing approach
- Significance level
- Confidence intervals
- Software to be used
""",
            "sample_size": """
Include:
- Target sample size
- Assumptions (effect size, variability, rates)
- Power calculation details
- Dropout/attrition assumptions
""",
            "primary_analysis": """
Include:
- Analysis population
- Statistical model/test
- Primary estimand
- Sensitivity analyses
- Handling of missing data
""",
            "secondary_analysis": """
For each secondary endpoint:
- Analysis method
- Population
- Multiplicity adjustment (if any)
""",
            "safety_analysis": """
Include:
- Safety population definition
- AE coding (MedDRA version)
- AE summary tables (TEAE, SAE, etc.)
- Laboratory parameters
- Vital signs

For CAR-T studies (CRITICAL - use Knowledge Base content):
- CRS grading scale: Use EXACTLY what protocol specifies (Lee 2014 Modified OR ASTCT 2019)
  * If protocol says "Lee 2014" or "modified Lee": Use "Modified Lee et al. 2014 criteria where neurologic AEs are NOT reported as part of CRS"
  * If protocol says "ASTCT": Use "ASTCT 2019 Consensus"
- ICANS/Neurologic events: Grade separately per protocol specification
- Include Safety Re-treatment Analysis Set if retreatment is allowed
- Include CRS/ICANS tables from the KB content provided
""",
            "missing_data": """
Include:
- Primary missing data mechanism assumption
- Primary analysis approach
- Sensitivity analyses
""",
            "interim_analysis": """
Include (if applicable):
- Timing of interim analysis
- Stopping rules
- Alpha spending function
- DMC charter reference
""",
            "multiplicity": """
Include:
- Testing hierarchy
- Adjustment method
- Graphical approach (if used)
""",
            "table_shells": """
Generate table shells for:
- Demographics and baseline characteristics
- Primary endpoint results
- Key secondary endpoints
- Safety summary

Use the actual treatment arms from the protocol.
Use appropriate summary statistics (n(%) for categorical, median/IQR for continuous).
For SINGLE-ARM studies: Do NOT use "By treatment arm" columns. Use single column for all treated subjects.
For CAR-T studies: Include CRS/ICANS tables from KB content.
""",
            "definitions": """
CRITICAL: This section must include ALL standard definitions from the Knowledge Base.

Include:
- Study Day 0 definition (Day of first dose or CAR-T infusion)
- Baseline definition (Last value prior to first dose)
- On-study period definition
- End of study definition
- TEAE definition (Treatment-Emergent Adverse Event)
- Treatment-related AE definition
- SAE definition
- Follow-up time definitions (actual vs potential, reverse K-M)
- Enrollment definition (date of consent, randomization, or leukapheresis for CAR-T)

For CAR-T studies, include CAR-T specific definitions:
- Day 0 = Day of CAR-T infusion
- Baseline for efficacy = Prior to conditioning chemotherapy
- Baseline for safety = Prior to CAR-T infusion
""",
            "references": """
Include citations for all statistical methods and criteria used:

Required references (from Knowledge Base):
- Kaplan-Meier survival analysis
- Response criteria (Cheson 2014 for lymphoma, RECIST 1.1 for solid tumors)
- CRS grading scale (Lee 2014 or ASTCT 2019 as specified in protocol)
- Follow-up time calculation (Schemper 1996 reverse K-M)
- Any disease-specific criteria (Topp 2015 for ICANS if applicable)

Format as numbered list with full citations.
"""
        }

        return instructions.get(section_id, "Generate appropriate content based on the protocol.")

    def _get_relevant_excerpts(self, protocol: str, section_id: str) -> List[str]:
        """Get protocol excerpts relevant to this section."""
        # Simplified - in practice would use semantic search
        excerpts = []

        keywords = {
            "objectives": ["objective", "aim", "purpose"],
            "endpoints": ["endpoint", "outcome", "primary", "secondary"],
            "populations": ["population", "analysis set", "ITT", "safety"],
            "sample_size": ["sample size", "power", "enrollment"],
            "safety_analysis": ["adverse", "safety", "AE", "SAE"],
        }

        section_keywords = keywords.get(section_id, [])

        # Find paragraphs containing keywords
        paragraphs = protocol.split('\n\n')
        for para in paragraphs:
            para_lower = para.lower()
            if any(kw in para_lower for kw in section_keywords):
                excerpts.append(para[:500])
                if len(excerpts) >= 3:
                    break

        return excerpts

    def _get_metadata_used(self, metadata: Optional[ProtocolMetadata], section_id: str) -> List[str]:
        """Get which metadata fields were used for this section."""
        if not metadata:
            return []

        field_map = {
            "study_info": ["study_id", "study_title", "phase"],
            "objectives": ["objectives"],
            "endpoints": ["endpoints"],
            "populations": ["populations"],
            "sample_size": ["sample_size"],
            "primary_analysis": ["endpoints", "statistical_methods"],
            "safety_analysis": ["populations"],
            "table_shells": ["treatment_arms", "endpoints"],
        }

        return field_map.get(section_id, [])

    # =========================================================================
    # SECTION EDITING
    # =========================================================================

    def update_section(
        self,
        workspace_id: str,
        section_id: str,
        content: str,
        comments: str = ""
    ) -> SAPSection:
        """Update a section with user edits."""

        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        section = workspace.sections.get(section_id)
        if not section:
            raise ValueError(f"Unknown section: {section_id}")

        # Save history
        if section.content:
            section.history.append({
                "version": section.version,
                "content": section.content,
                "saved_at": section.edited_at or section.generated_at
            })
            section.version += 1

        section.content = content
        section.status = SectionStatus.EDITED
        section.edited_at = datetime.now().isoformat()
        section.user_comments = comments

        workspace.updated_at = datetime.now().isoformat()
        self._save_workspace(workspace)

        return section

    def approve_section(self, workspace_id: str, section_id: str) -> SAPSection:
        """Mark a section as approved."""

        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        section = workspace.sections.get(section_id)
        if not section:
            raise ValueError(f"Unknown section: {section_id}")

        section.status = SectionStatus.APPROVED
        workspace.updated_at = datetime.now().isoformat()
        self._save_workspace(workspace)

        return section

    # =========================================================================
    # CHANGE MANAGEMENT
    # =========================================================================

    def update_protocol(
        self,
        workspace_id: str,
        new_protocol_content: str,
        new_filename: str
    ) -> Dict:
        """Update protocol and identify impacted sections."""

        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        old_hash = workspace.protocol_hash
        new_hash = hashlib.md5(new_protocol_content.encode()).hexdigest()

        if old_hash == new_hash:
            return {"changed": False, "impacted_sections": []}

        # Compare protocols
        impacted = self._compare_protocols(
            workspace.protocol_content,
            new_protocol_content,
            workspace.metadata
        )

        # Update workspace
        workspace.protocol_content = new_protocol_content
        workspace.protocol_filename = new_filename
        workspace.protocol_hash = new_hash
        workspace.protocol_versions.append({
            "version": len(workspace.protocol_versions) + 1,
            "hash": new_hash,
            "uploaded_at": datetime.now().isoformat(),
            "filename": new_filename
        })

        # Mark impacted sections for review
        for section_id in impacted:
            if section_id in workspace.sections:
                section = workspace.sections[section_id]
                if section.status == SectionStatus.APPROVED:
                    section.status = SectionStatus.EDITED  # Needs re-review

        workspace.updated_at = datetime.now().isoformat()
        self._save_workspace(workspace)

        return {
            "changed": True,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "impacted_sections": impacted
        }

    def _compare_protocols(
        self,
        old_protocol: str,
        new_protocol: str,
        metadata: Optional[ProtocolMetadata]
    ) -> List[str]:
        """Compare protocols and identify impacted sections."""

        impacted = []

        # Simple keyword-based comparison
        checks = {
            "objectives": ["objective", "aim", "purpose"],
            "endpoints": ["endpoint", "outcome", "primary endpoint", "secondary endpoint"],
            "populations": ["population", "analysis set", "ITT"],
            "sample_size": ["sample size", "power", "enrollment", "subjects"],
            "statistical_methods": ["statistical", "analysis method", "cox", "kaplan"],
            "safety_analysis": ["adverse event", "safety", "AE", "SAE"],
            "primary_analysis": ["primary analysis", "primary endpoint"],
        }

        old_lower = old_protocol.lower()
        new_lower = new_protocol.lower()

        for section_id, keywords in checks.items():
            for kw in keywords:
                # Find context around keyword in both versions
                old_idx = old_lower.find(kw)
                new_idx = new_lower.find(kw)

                if old_idx >= 0 and new_idx >= 0:
                    old_context = old_lower[max(0, old_idx-100):old_idx+200]
                    new_context = new_lower[max(0, new_idx-100):new_idx+200]

                    if old_context != new_context:
                        if section_id not in impacted:
                            impacted.append(section_id)
                        break

        return impacted

    # =========================================================================
    # EXPORT
    # =========================================================================

    def export_sap(self, workspace_id: str, format: str = "markdown") -> str:
        """Export complete SAP with full provenance/sources for each section."""

        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        lines = [
            "# STATISTICAL ANALYSIS PLAN",
            "",
            f"**Study:** {workspace.metadata.study_title if workspace.metadata else workspace.name}",
            f"**Protocol:** {workspace.protocol_filename}",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d')}",
            "",
            "---",
            ""
        ]

        # Add each section from MASTER_SAP_SECTIONS (v90: use stored conditions)
        for section_number, section_title in get_workbench_sections(workspace.protocol_conditions):
            section = workspace.sections.get(section_number)
            if section and section.content:
                lines.append(f"## {section_number}. {section_title}")
                lines.append("")
                lines.append(section.content)
                lines.append("")

                # Add provenance/sources section
                sources = []

                # Protocol sources
                if section.protocol_excerpts_used:
                    sources.append("**Protocol Sources:**")
                    for i, excerpt in enumerate(section.protocol_excerpts_used[:3], 1):
                        # Truncate long excerpts
                        excerpt_preview = excerpt[:150].replace('\n', ' ') + "..." if len(excerpt) > 150 else excerpt.replace('\n', ' ')
                        sources.append(f"  - Protocol excerpt {i}: \"{excerpt_preview}\"")

                # Metadata extraction sources
                if section.metadata_used:
                    sources.append("**Extracted Metadata Used:**")
                    for field in section.metadata_used:
                        sources.append(f"  - {field}")

                # Knowledge Base sources
                if section.kb_tools_used:
                    sources.append("**Knowledge Base Sources:**")
                    for kb_tool in section.kb_tools_used:
                        tool_name = kb_tool.get("tool_name", "unknown")
                        source_file = kb_tool.get("source_file", "methodology_knowledge_base.py")
                        source_key = kb_tool.get("source_key", "")
                        description = kb_tool.get("description", tool_name)
                        sources.append(f"  - {description}")
                        sources.append(f"    - File: `{source_file}`")
                        sources.append(f"    - Key: `{source_key}`")

                # Add generation timestamp
                if section.generated_at:
                    sources.append(f"**Generated:** {section.generated_at}")

                if sources:
                    lines.append("")
                    lines.append("<details>")
                    lines.append("<summary>📚 Section Sources & Provenance</summary>")
                    lines.append("")
                    lines.extend(sources)
                    lines.append("")
                    lines.append("</details>")

                lines.append("")
                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    # =========================================================================
    # v93: SDTM SPECIFICATION GENERATION
    # =========================================================================

    def generate_sdtm_spec(self, workspace_id: str) -> Dict:
        """
        Generate SDTM specification from the completed SAP.

        Uses Claude + LLMParser for accurate SAP parsing and SDTM domain mapping.

        Args:
            workspace_id: The workspace ID

        Returns:
            Dictionary with SDTM specification including domains and traceability
        """
        if not SDTM_AVAILABLE:
            raise ValueError("SDTM generator not available")

        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        # Get the full SAP content
        sap_content = self.export_sap(workspace_id, format="markdown")
        if not sap_content or len(sap_content) < 100:
            raise ValueError("SAP content is empty or too short. Generate SAP sections first.")

        print(f"[Workbench] Generating SDTM spec from SAP ({len(sap_content):,} chars)")

        # Create SDTM generator with same client
        generator = create_sdtm_spec_generator(client=self.client, model=self.model)

        # Get protocol facts from extraction if available
        protocol_facts = {}
        if workspace.metadata and workspace.metadata.full_extraction:
            protocol_facts = workspace.metadata.full_extraction
        else:
            # Parse from SAP text
            parsed = generator.parser.parse(sap_content)
            protocol_facts = parsed

        # Generate SDTM specification
        spec = generator.generate(protocol_facts)

        # Convert to dictionary for storage
        sdtm_dict = {
            "study_id": spec.study_id,
            "study_name": spec.study_name,
            "generated_at": datetime.now().isoformat(),
            "domains": [
                {
                    "code": d.code,
                    "name": d.name,
                    "label": d.label,
                    "domain_class": d.domain_class.value,
                    "structure": d.structure,
                    "description": d.description,
                    "purpose": d.purpose,
                    "variables": [
                        {
                            "name": v.name,
                            "label": v.label,
                            "type": v.type,
                            "length": v.length,
                            "core": v.core.value,
                            "codelist": v.codelist,
                            "description": v.description,
                            "source": v.source
                        }
                        for v in d.variables
                    ],
                    "notes": d.notes
                }
                for d in spec.domains
            ],
            "traceability": [
                {
                    "sap_section": t.sap_section,
                    "sap_text": t.sap_text[:200],  # Truncate for storage
                    "sdtm_element": t.sdtm_element,
                    "rationale": t.rationale
                }
                for t in spec.traceability
            ],
            "validation_notes": spec.validation_notes
        }

        # Store in workspace
        workspace.sdtm_spec = sdtm_dict
        workspace.sdtm_generated_at = datetime.now().isoformat()
        workspace.updated_at = datetime.now().isoformat()
        self._save_workspace(workspace)

        print(f"[Workbench] Generated SDTM spec with {len(sdtm_dict['domains'])} domains")

        return sdtm_dict

    def export_sdtm(self, workspace_id: str, format: str = "markdown") -> str:
        """
        Export SDTM specification as markdown or JSON.

        Args:
            workspace_id: The workspace ID
            format: "markdown" or "json"

        Returns:
            Formatted SDTM specification
        """
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        if not workspace.sdtm_spec:
            raise ValueError("No SDTM specification generated. Call generate_sdtm_spec first.")

        spec = workspace.sdtm_spec

        if format == "json":
            return json.dumps(spec, indent=2)

        # Markdown format
        lines = [
            "# SDTM Specification",
            "",
            f"**Study:** {spec.get('study_id', 'Unknown')}",
            f"**Generated:** {spec.get('generated_at', '')}",
            "",
            "---",
            "",
            "## Domains Required",
            ""
        ]

        for domain in spec.get('domains', []):
            lines.append(f"### {domain['code']} - {domain['name']}")
            lines.append("")
            lines.append(f"**Class:** {domain['domain_class']}")
            lines.append(f"**Structure:** {domain['structure']}")
            lines.append(f"**Purpose:** {domain.get('purpose', '')}")
            lines.append("")

            if domain.get('notes'):
                lines.append("**Notes:**")
                for note in domain['notes']:
                    lines.append(f"- {note}")
                lines.append("")

            lines.append("**Variables:**")
            lines.append("")
            lines.append("| Variable | Label | Type | Core |")
            lines.append("|----------|-------|------|------|")

            for var in domain.get('variables', [])[:20]:  # Limit to first 20
                lines.append(
                    f"| {var['name']} | {var['label'][:40]} | {var['type']} | {var['core']} |"
                )

            lines.append("")
            lines.append("---")
            lines.append("")

        # Traceability section
        lines.append("## SAP to SDTM Traceability")
        lines.append("")
        lines.append("| SAP Section | SDTM Element | Rationale |")
        lines.append("|-------------|--------------|-----------|")

        for trace in spec.get('traceability', [])[:30]:  # Limit
            lines.append(
                f"| {trace['sap_section']} | {trace['sdtm_element']} | {trace['rationale'][:50]} |"
            )

        return "\n".join(lines)

    def get_provenance_report(self, workspace_id: str) -> Dict:
        """Get full provenance report."""

        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        report = {
            "workspace_id": workspace_id,
            "protocol_hash": workspace.protocol_hash,
            "protocol_versions": workspace.protocol_versions,
            "sections": {}
        }

        for section_id, section in workspace.sections.items():
            if section.content:
                report["sections"][section_id] = {
                    "status": section.status.value,
                    "version": section.version,
                    "generated_at": section.generated_at,
                    "edited_at": section.edited_at,
                    "protocol_excerpts_used": section.protocol_excerpts_used,
                    "metadata_used": section.metadata_used,
                    "kb_tools_used": section.kb_tools_used,
                    "history_count": len(section.history)
                }

        return report

    # =========================================================================
    # STORAGE
    # =========================================================================

    def _save_workspace(self, workspace: StudyWorkspace):
        """Save workspace to Supabase."""
        # Convert sections to serializable dict
        sections_data = {
            k: {
                "id": v.id,
                "name": v.name,
                "display_name": v.display_name,
                "status": v.status.value,
                "content": v.content,
                "protocol_excerpts_used": v.protocol_excerpts_used,
                "metadata_used": v.metadata_used,
                "kb_tools_used": v.kb_tools_used,
                "generated_at": v.generated_at,
                "edited_at": v.edited_at,
                "user_comments": v.user_comments,
                "version": v.version,
                "history": v.history
            }
            for k, v in workspace.sections.items()
        }

        # Convert metadata to dict (includes full_extraction)
        metadata_dict = asdict(workspace.metadata) if workspace.metadata else {}
        # Add workspace-level fields to metadata for backwards compat
        metadata_dict["phase"] = workspace.phase
        metadata_dict["therapeutic_area"] = workspace.therapeutic_area
        metadata_dict["indication"] = workspace.indication
        metadata_dict["name"] = workspace.name
        metadata_dict["protocol_versions"] = workspace.protocol_versions

        # Upsert to Supabase
        data = {
            "id": workspace.id,
            "created_at": workspace.created_at,
            "updated_at": datetime.now().isoformat(),
            "protocol_content": workspace.protocol_content,
            "protocol_filename": workspace.protocol_filename,
            "protocol_hash": workspace.protocol_hash,
            "metadata": metadata_dict,
            "sections": sections_data,
            "protocol_conditions": workspace.protocol_conditions
        }

        try:
            self.supabase.table("workspaces").upsert(data).execute()
        except Exception as e:
            print(f"Error saving workspace {workspace.id}: {e}")
            raise

    def _load_workspace(self, workspace_id: str) -> Optional[StudyWorkspace]:
        """Load workspace from Supabase."""
        try:
            result = self.supabase.table("workspaces").select("*").eq("id", workspace_id).execute()

            if not result.data:
                return None

            data = result.data[0]
        except Exception as e:
            print(f"Error loading workspace {workspace_id}: {e}")
            return None

        # Get metadata from JSONB column
        m = data.get("metadata") or {}

        # Reconstruct metadata (including full_extraction for reuse)
        metadata = None
        if m:
            metadata = ProtocolMetadata(
                study_id=m.get("study_id", ""),
                study_title=m.get("study_title", ""),
                phase=m.get("phase", ""),
                therapeutic_area=m.get("therapeutic_area", ""),
                indication=m.get("indication", ""),
                objectives=m.get("objectives", []),
                endpoints=m.get("endpoints", []),
                populations=m.get("populations", []),
                treatment_arms=m.get("treatment_arms", []),
                stratification_factors=m.get("stratification_factors", []),
                sample_size=m.get("sample_size"),
                statistical_methods=m.get("statistical_methods", []),
                visit_schedule=m.get("visit_schedule", []),
                # FULL 55-category extraction (critical for section generation)
                full_extraction=m.get("full_extraction", {}),
                # Disease-specific info
                disease_setting=m.get("disease_setting", ""),
                performance_status_scale=m.get("performance_status_scale", ""),
                response_criteria=m.get("response_criteria", ""),
                geographic_countries=m.get("geographic_countries", []),
                baseline_variables=m.get("baseline_variables", []),
                # Prohibition rules
                prohibition_rules=m.get("prohibition_rules", []),
                # Source tracking
                extraction_timestamp=m.get("extraction_timestamp", ""),
                protocol_hash=m.get("protocol_hash", ""),
                extraction_method=m.get("extraction_method", "basic")
            )

        # Reconstruct sections from JSONB column
        sections = {}
        sections_data = data.get("sections") or {}
        for k, v in sections_data.items():
            sections[k] = SAPSection(
                id=v["id"],
                name=v["name"],
                display_name=v["display_name"],
                status=SectionStatus(v["status"]),
                content=v.get("content", ""),
                protocol_excerpts_used=v.get("protocol_excerpts_used", []),
                metadata_used=v.get("metadata_used", []),
                kb_tools_used=v.get("kb_tools_used", []),
                generated_at=v.get("generated_at", ""),
                edited_at=v.get("edited_at", ""),
                user_comments=v.get("user_comments", ""),
                version=v.get("version", 1),
                history=v.get("history", [])
            )

        workspace = StudyWorkspace(
            id=data["id"],
            name=m.get("name", data.get("protocol_filename", "Untitled")),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            protocol_content=data.get("protocol_content", ""),
            protocol_filename=data.get("protocol_filename", ""),
            protocol_hash=data.get("protocol_hash", ""),
            phase=m.get("phase", ""),
            therapeutic_area=m.get("therapeutic_area", ""),
            indication=m.get("indication", ""),
            metadata=metadata,
            sections=sections,
            protocol_versions=m.get("protocol_versions", []),
            # Protocol conditions for section filtering
            protocol_conditions=data.get("protocol_conditions") or {}
        )

        self.workspaces[workspace_id] = workspace
        return workspace

    # =========================================================================
    # SECTION VALIDATION & AUTO-FIX (v99.6)
    # =========================================================================

    # Define which sections need validation and what to check
    SECTION_VALIDATION_RULES = {
        "5A.2": {
            "name": "Baseline Disease Characteristics",
            "checks": ["stage_substages"],
            "required_content": {
                "stage_substages": ["iiia", "iiib", "iiic"]  # At least one
            }
        },
        "11.1": {
            "name": "Pre-specified Subgroups",
            "checks": ["subgroups_adequate"],
            "min_subgroups": 6,
            "subgroup_keywords": ["age", "sex", "smoking", "ecog", "histology", "region", "pd-l1", "stage"]
        },
        "15.1": {
            "name": "PRO Instruments",
            "checks": ["pro_symptoms", "eq5d_domains", "lc13_symptoms"],
            "required_content": {
                "pro_symptoms": ["fatigue", "pain", "nausea"],
                "eq5d_domains": ["mobility", "self-care", "anxiety"],
                "lc13_symptoms": ["dyspnoea", "dyspnea", "coughing", "cough", "haemoptysis"]  # Any 2 of these for lung
            },
            "lc13_min_matches": 2  # Need at least 2 LC13 symptoms for lung cancer
        },
        "18.3": {
            "name": "Efficacy Tables",
            "checks": ["dcr_present"],
            "required_content": {
                "dcr_present": ["dcr", "disease control"]  # Either one
            }
        },
        "18.5": {
            "name": "Figures",
            "checks": ["waterfall_plot"],
            "required_content": {
                "waterfall_plot": ["waterfall"]
            }
        },
        "A.2": {
            "name": "Censoring Rules",
            "checks": ["censoring_tables"],
            "required_content": {
                "censoring_tables": ["cnsr", "censored"]
            },
            "required_scenarios": ["death", "progression", "lost to follow", "withdrew"]
        }
    }

    SECTION_REGENERATION_PROMPTS = {
        "stage_substages": """Add the following disease stage breakdown to this section:

**Disease Stage at Diagnosis:**
| Stage | n (%) |
|-------|-------|
| Stage IIIA | |
| Stage IIIB | |
| Stage IIIC | |
| Stage IVA | |
| Stage IVB | |

Note: Stage classification per AJCC 8th edition.""",

        "subgroups_adequate": """The subgroup section needs MORE subgroups. Add ALL of these:

Pre-specified Subgroups:
1. Age (<65 years vs ≥65 years)
2. Sex (Male vs Female)
3. Race (White vs Asian vs Other)
4. ECOG Performance Status (0 vs 1)
5. Smoking status (Current/Former vs Never)
6. Histology (Squamous vs Non-squamous)
7. Geographic region (North America vs Europe vs Asia vs Rest of World)
8. Disease stage (Stage III vs Stage IV)
9. PD-L1 expression (<1% vs 1-49% vs ≥50%)
10. Prior therapy (Yes vs No)
11. Response to prior CRT (CR/PR vs SD)
12. Number of metastatic sites (≤2 vs >2)
13. Brain metastases at baseline (Yes vs No)
14. Liver metastases at baseline (Yes vs No)

For each subgroup, primary endpoint will be analyzed using same methods as overall analysis.""",

        "pro_symptoms": """Add explicit symptom listings for each PRO instrument:

**EORTC QLQ-C30 Symptom Scales:**
- Fatigue (items 10, 12, 18)
- Nausea and vomiting (items 14, 15)
- Pain (items 9, 19)
- Dyspnoea (item 8)
- Insomnia (item 11)
- Appetite loss (item 13)
- Constipation (item 16)
- Diarrhoea (item 17)
- Financial difficulties (item 28)

**EORTC QLQ-LC13 Symptom Scales (for lung cancer):**
- Dyspnoea (items 3-5)
- Coughing (item 1)
- Haemoptysis (item 2)
- Sore mouth (item 6)
- Dysphagia (item 7)
- Peripheral neuropathy (item 8)
- Alopecia (item 9)
- Pain in chest (item 10)
- Pain in arm/shoulder (item 11)

**EQ-5D-5L Dimensions:**
- Mobility
- Self-Care
- Usual Activities
- Pain/Discomfort
- Anxiety/Depression""",

        "eq5d_domains": """Add the EQ-5D-5L dimensions explicitly:

**EQ-5D-5L Health State Assessment:**
The EQ-5D-5L descriptive system comprises five dimensions:
1. Mobility
2. Self-Care
3. Usual Activities
4. Pain/Discomfort
5. Anxiety/Depression

Each dimension has 5 levels: no problems, slight problems, moderate problems, severe problems, and extreme problems.""",

        "lc13_symptoms": """Add the EORTC QLQ-LC13 lung cancer-specific symptoms:

**EORTC QLQ-LC13 (Lung Cancer Module)**

The QLQ-LC13 is a 13-item lung cancer-specific questionnaire supplement assessing:

**Symptom Scales:**
- Dyspnoea (items 3, 4, 5) - shortness of breath at rest, walking, climbing stairs
- Coughing (item 1)
- Haemoptysis (item 2) - coughing up blood
- Sore mouth (item 6)
- Dysphagia (item 7) - difficulty swallowing
- Peripheral neuropathy (item 8) - tingling hands/feet
- Alopecia (item 9) - hair loss

**Pain Items:**
- Pain in chest (item 10)
- Pain in arm or shoulder (item 11)
- Pain in other parts (item 12)

**Single Item:**
- Use of pain medication (item 13)

**Scoring:** Linear transformation to 0-100 scale. Higher scores = worse symptoms.
**MID:** 10 points change considered clinically meaningful.""",

        "dcr_present": """Add DCR (Disease Control Rate) to the response table:

**Table 14.2.X: Best Overall Response (ITT Population)**

| Response Category | N | % | 95% CI |
|-------------------|---|---|--------|
| Complete Response (CR) | | | |
| Partial Response (PR) | | | |
| Stable Disease (SD) | | | |
| Progressive Disease (PD) | | | |
| Not Evaluable (NE) | | | |
| **Objective Response Rate (ORR = CR + PR)** | | | |
| **Disease Control Rate (DCR = CR + PR + SD)** | | | |

95% confidence intervals calculated using Clopper-Pearson exact method.""",

        "waterfall_plot": """Add waterfall plot specification:

**Figure 14.4.X: Waterfall Plot of Best Percentage Change from Baseline in Sum of Target Lesions**

**Purpose:** Display individual patient tumor responses showing best percentage change from baseline in sum of target lesion diameters.

**Specifications:**
- X-axis: Individual patients (sorted by best % change, largest reduction on left)
- Y-axis: Best percentage change from baseline (%)
- Reference lines: +20% (progression threshold per RECIST), -30% (response threshold)
- Bar colors: By best overall response (CR=dark blue, PR=light blue, SD=yellow, PD=red)
- Include dashed horizontal lines at +20% and -30%

**Population:** ITT population with measurable disease at baseline and at least one post-baseline tumor assessment.

**Data source:** ADRS dataset, PARAMCD='SUMDIAM', select minimum (best) percentage change per subject.""",

        "censoring_tables": """Add detailed censoring rules tables:

**Table A.2.1: PFS Event and Censoring Rules**

| Situation | Outcome | Date Used | CNSR |
|-----------|---------|-----------|------|
| Disease progression documented | Event | Date of progression | 0 |
| Death without prior progression | Event | Date of death | 0 |
| No progression, still on study | Censored | Date of last adequate assessment | 1 |
| Lost to follow-up | Censored | Date of last adequate assessment | 1 |
| Withdrew consent | Censored | Date of last adequate assessment | 1 |
| Started new anti-cancer therapy | Censored | Date prior to start of new therapy | 1 |
| Missed ≥2 assessments then progressed | Censored | Date of last assessment before gap | 1 |

**Table A.2.2: OS Event and Censoring Rules**

| Situation | Outcome | Date Used | CNSR |
|-----------|---------|-----------|------|
| Death from any cause | Event | Date of death | 0 |
| Alive at data cutoff | Censored | Date of last known alive | 1 |
| Lost to follow-up | Censored | Date of last contact | 1 |
| Withdrew consent | Censored | Date of withdrawal | 1 |"""
    }

    def _validate_section(self, section_id: str, content: str) -> Dict[str, Any]:
        """
        Validate a section for required elements.
        Returns dict with 'passed', 'missing', and 'checks' details.
        """
        # Normalize section_id (handle "Appendix A.2" -> "A.2")
        normalized_id = section_id.replace("Appendix ", "").strip()

        rules = self.SECTION_VALIDATION_RULES.get(normalized_id)
        if not rules:
            # No validation rules for this section
            return {"passed": True, "missing": [], "checks": {}}

        content_lower = content.lower()
        checks = {}
        missing = []

        for check_name in rules.get("checks", []):
            passed = False

            if check_name == "subgroups_adequate":
                # Count subgroup keywords
                keywords = rules.get("subgroup_keywords", [])
                count = sum(1 for kw in keywords if kw in content_lower)
                min_required = rules.get("min_subgroups", 6)
                passed = count >= min_required
                checks[check_name] = {"count": count, "required": min_required, "passed": passed}

            elif check_name == "lc13_symptoms":
                # Special case: LC13 needs at least N matches (for lung cancer)
                required_terms = rules["required_content"].get(check_name, [])
                min_matches = rules.get("lc13_min_matches", 2)
                match_count = sum(1 for term in required_terms if term in content_lower)
                passed = match_count >= min_matches
                checks[check_name] = {"terms": required_terms, "found": match_count, "required": min_matches, "passed": passed}

            elif check_name in rules.get("required_content", {}):
                # Check if ANY of the required terms are present
                required_terms = rules["required_content"][check_name]
                found = any(term in content_lower for term in required_terms)
                passed = found
                checks[check_name] = {"required_any": required_terms, "found": found, "passed": passed}

            if not passed:
                missing.append(check_name)

        # Special check for censoring tables - need scenarios too
        if normalized_id == "A.2" and "censoring_tables" not in missing:
            scenarios = rules.get("required_scenarios", [])
            scenario_count = sum(1 for s in scenarios if s in content_lower)
            if scenario_count < 3:  # Need at least 3 scenarios
                missing.append("censoring_tables")
                checks["censoring_scenarios"] = {"found": scenario_count, "required": 3, "passed": False}

        return {
            "passed": len(missing) == 0,
            "missing": missing,
            "checks": checks
        }

    def _regenerate_section_fix(self, section_id: str, original_content: str, missing_elements: List[str], protocol_content: str) -> str:
        """
        Regenerate/fix a section by adding missing elements.
        """
        if not missing_elements:
            return original_content

        # Build fix prompt
        fixes_to_add = []
        for element in missing_elements:
            if element in self.SECTION_REGENERATION_PROMPTS:
                fixes_to_add.append(self.SECTION_REGENERATION_PROMPTS[element])

        if not fixes_to_add:
            return original_content

        prompt = f"""You are fixing a SAP section that is missing required elements.

ORIGINAL SECTION CONTENT:
{original_content}

MISSING ELEMENTS TO ADD:
{chr(10).join(fixes_to_add)}

INSTRUCTIONS:
1. Keep ALL the original content
2. ADD the missing elements at appropriate locations
3. Maintain consistent formatting with the original
4. Output the COMPLETE fixed section

Output the fixed section now:"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            print(f"[WORKBENCH] Fix regeneration failed: {e}")
            return original_content


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set")
        exit(1)

    print("="*70)
    print("SAP WORKBENCH TEST")
    print("="*70)

    # Initialize
    workbench = SAPWorkbench(api_key)

    # Load test protocol
    protocol_path = Path(__file__).parent.parent.parent / "data/all_pairs/NCT01853878_protocol.txt"
    if not protocol_path.exists():
        print(f"❌ Test protocol not found: {protocol_path}")
        exit(1)

    protocol_content = protocol_path.read_text(encoding='utf-8', errors='ignore')

    # Create workspace
    print("\n1. Creating workspace...")
    workspace = workbench.create_workspace(
        protocol_content=protocol_content,
        protocol_filename="NCT01853878_protocol.txt",
        phase="Phase 2",
        therapeutic_area="oncology",
        indication="NSCLC"
    )
    print(f"   ✅ Created workspace: {workspace.id}")

    # Extract metadata
    print("\n2. Extracting metadata...")
    metadata = workbench.extract_metadata(workspace.id)
    print(f"   ✅ Study: {metadata.study_id}")
    print(f"   ✅ Endpoints: {len(metadata.endpoints)}")
    print(f"   ✅ Populations: {len(metadata.populations)}")

    # Get outline
    print("\n3. Getting SAP outline...")
    outline = workbench.get_outline(workspace.id)
    for item in outline[:5]:
        print(f"   • {item['name']}: {item['status']}")

    # Generate one section
    print("\n4. Generating 'Study Information' section...")
    section = workbench.generate_section(workspace.id, "study_info")
    print(f"   ✅ Status: {section.status.value}")
    print(f"   ✅ Content: {len(section.content)} chars")
    print(f"\n   Preview:\n{section.content[:500]}...")

    # Export
    print("\n5. Exporting SAP...")
    sap = workbench.export_sap(workspace.id)
    print(f"   ✅ Exported: {len(sap)} chars")

    print("\n" + "="*70)
    print("✅ WORKBENCH TEST COMPLETE")
    print("="*70)
