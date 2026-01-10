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

# Import KG extraction and KB tools
try:
    from enterprise_sap_system.knowledge_graph.kg_enhanced_pipeline import EnhancedKGPipeline
    from enterprise_sap_system.knowledge_graph.kb_tools import (
        KnowledgeBaseTools,
        get_claude_tool_definitions,
        execute_tool
    )
    KG_AVAILABLE = True
except ImportError:
    try:
        from ..knowledge_graph.kg_enhanced_pipeline import EnhancedKGPipeline
        from ..knowledge_graph.kb_tools import (
            KnowledgeBaseTools,
            get_claude_tool_definitions,
            execute_tool
        )
        KG_AVAILABLE = True
    except ImportError:
        KG_AVAILABLE = False
        print("Warning: KG pipeline not available, using basic extraction")


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

    # Provenance
    protocol_excerpts_used: List[str] = field(default_factory=list)
    metadata_used: List[str] = field(default_factory=list)
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


# Standard SAP sections
SAP_SECTIONS = [
    ("study_info", "Study Information"),
    ("objectives", "Study Objectives"),
    ("endpoints", "Study Endpoints"),
    ("estimands", "Estimands"),
    ("populations", "Analysis Populations"),
    ("statistical_methods", "Statistical Methods"),
    ("sample_size", "Sample Size"),
    ("primary_analysis", "Primary Efficacy Analysis"),
    ("secondary_analysis", "Secondary Efficacy Analysis"),
    ("safety_analysis", "Safety Analysis"),
    ("missing_data", "Missing Data Handling"),
    ("interim_analysis", "Interim Analysis"),
    ("multiplicity", "Multiplicity Adjustment"),
    ("table_shells", "Table/Figure Shells"),
]


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

    def __init__(self, api_key: str, storage_dir: str = None, use_kg: bool = True):
        self.api_key = api_key
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"

        # Storage for workspaces
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = Path(__file__).parent / "workspaces"
        self.storage_dir.mkdir(exist_ok=True)

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

        print(f"   Storage: {self.storage_dir}")

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
        """Create a new study workspace."""

        workspace_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        protocol_hash = hashlib.md5(protocol_content.encode()).hexdigest()

        # Initialize sections
        sections = {}
        for section_id, display_name in SAP_SECTIONS:
            sections[section_id] = SAPSection(
                id=section_id,
                name=section_id,
                display_name=display_name,
                status=SectionStatus.NOT_STARTED
            )

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

        # Try loading from disk
        return self._load_workspace(workspace_id)

    def list_workspaces(self) -> List[Dict]:
        """List all workspaces."""
        workspaces = []
        for ws_file in self.storage_dir.glob("*.json"):
            try:
                with open(ws_file) as f:
                    data = json.load(f)
                workspaces.append({
                    "id": data["id"],
                    "name": data["name"],
                    "created_at": data["created_at"],
                    "phase": data.get("phase", ""),
                    "therapeutic_area": data.get("therapeutic_area", "")
                })
            except Exception:
                pass
        return workspaces

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

            # Build prohibition rules
            prohibition_rules = self._build_prohibition_rules(full_extraction)

            # Extract key fields from full extraction
            trial_id = full_extraction.get("trial_identification", {})
            disease = full_extraction.get("disease_classification", {})
            ps = full_extraction.get("performance_status", {})
            rc = full_extraction.get("response_criteria_details", {})
            geo = full_extraction.get("geographic", {})

            # Get countries
            countries = []
            for c in geo.get("countries", []):
                if c.get("country"):
                    countries.append(c.get("country"))

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

            # Convert populations
            populations = []
            pops = full_extraction.get("populations", {})
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

            # Get stratification factors
            strat_factors = []
            rand = full_extraction.get("randomization", {})
            for sf in rand.get("stratification_factors", []):
                if sf.get("factor_name"):
                    strat_factors.append(sf.get("factor_name"))

            # Get sample size
            ss = full_extraction.get("sample_size", {})
            sample_size_val = ss.get("total_n", {}).get("value") if ss else None
            if sample_size_val:
                try:
                    sample_size_val = int(sample_size_val)
                except:
                    sample_size_val = None

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
        for section_id, display_name in SAP_SECTIONS:
            section = workspace.sections.get(section_id)
            if section:
                outline.append({
                    "id": section_id,
                    "name": display_name,
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

        # Get section-specific prompt
        prompt = self._build_section_prompt(workspace, section_id)
        print(f"[WORKBENCH] Prompt length: {len(prompt):,} chars")

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()

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

            workspace.updated_at = datetime.now().isoformat()
            self._save_workspace(workspace)

            return section

        except Exception as e:
            section.status = SectionStatus.NOT_STARTED
            raise e

    def _build_section_prompt(self, workspace: StudyWorkspace, section_id: str) -> str:
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

        prompt = f"""Generate the "{workspace.sections[section_id].display_name}" section of a Statistical Analysis Plan.

## CRITICAL RULES:
1. Follow the protocol EXACTLY - do not add generic content
2. Use ONLY variables and categories from the extraction
3. Respect ALL prohibition rules below
{prohibition_section}

{metadata_context}

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
        """Export complete SAP."""

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

        # Add each section
        for section_id, display_name in SAP_SECTIONS:
            section = workspace.sections.get(section_id)
            if section and section.content:
                lines.append(f"## {display_name}")
                lines.append("")
                lines.append(section.content)
                lines.append("")
                lines.append("---")
                lines.append("")

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
                    "history_count": len(section.history)
                }

        return report

    # =========================================================================
    # STORAGE
    # =========================================================================

    def _save_workspace(self, workspace: StudyWorkspace):
        """Save workspace to disk."""
        filepath = self.storage_dir / f"{workspace.id}.json"

        # Convert to dict
        data = {
            "id": workspace.id,
            "name": workspace.name,
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at,
            "protocol_content": workspace.protocol_content,
            "protocol_filename": workspace.protocol_filename,
            "protocol_hash": workspace.protocol_hash,
            "phase": workspace.phase,
            "therapeutic_area": workspace.therapeutic_area,
            "indication": workspace.indication,
            "metadata": asdict(workspace.metadata) if workspace.metadata else None,
            "sections": {
                k: {
                    "id": v.id,
                    "name": v.name,
                    "display_name": v.display_name,
                    "status": v.status.value,
                    "content": v.content,
                    "protocol_excerpts_used": v.protocol_excerpts_used,
                    "metadata_used": v.metadata_used,
                    "generated_at": v.generated_at,
                    "edited_at": v.edited_at,
                    "user_comments": v.user_comments,
                    "version": v.version,
                    "history": v.history
                }
                for k, v in workspace.sections.items()
            },
            "protocol_versions": workspace.protocol_versions
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_workspace(self, workspace_id: str) -> Optional[StudyWorkspace]:
        """Load workspace from disk."""
        filepath = self.storage_dir / f"{workspace_id}.json"

        if not filepath.exists():
            return None

        with open(filepath) as f:
            data = json.load(f)

        # Reconstruct metadata
        metadata = None
        if data.get("metadata"):
            m = data["metadata"]
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
                extraction_timestamp=m.get("extraction_timestamp", ""),
                protocol_hash=m.get("protocol_hash", "")
            )

        # Reconstruct sections
        sections = {}
        for k, v in data.get("sections", {}).items():
            sections[k] = SAPSection(
                id=v["id"],
                name=v["name"],
                display_name=v["display_name"],
                status=SectionStatus(v["status"]),
                content=v.get("content", ""),
                protocol_excerpts_used=v.get("protocol_excerpts_used", []),
                metadata_used=v.get("metadata_used", []),
                generated_at=v.get("generated_at", ""),
                edited_at=v.get("edited_at", ""),
                user_comments=v.get("user_comments", ""),
                version=v.get("version", 1),
                history=v.get("history", [])
            )

        workspace = StudyWorkspace(
            id=data["id"],
            name=data["name"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            protocol_content=data.get("protocol_content", ""),
            protocol_filename=data.get("protocol_filename", ""),
            protocol_hash=data.get("protocol_hash", ""),
            phase=data.get("phase", ""),
            therapeutic_area=data.get("therapeutic_area", ""),
            indication=data.get("indication", ""),
            metadata=metadata,
            sections=sections,
            protocol_versions=data.get("protocol_versions", [])
        )

        self.workspaces[workspace_id] = workspace
        return workspace


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
