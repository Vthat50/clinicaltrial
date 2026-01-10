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


class SectionStatus(Enum):
    """Status of each SAP section."""
    NOT_STARTED = "not_started"
    GENERATING = "generating"
    DRAFT = "draft"
    EDITED = "edited"
    APPROVED = "approved"


@dataclass
class ProtocolMetadata:
    """Structured metadata extracted from protocol."""
    study_id: str = ""
    study_title: str = ""
    phase: str = ""
    therapeutic_area: str = ""
    indication: str = ""

    # Extracted elements
    objectives: List[Dict] = field(default_factory=list)  # [{type: "primary", text: "..."}]
    endpoints: List[Dict] = field(default_factory=list)   # [{name, type, definition, timeframe}]
    populations: List[Dict] = field(default_factory=list) # [{name, abbreviation, definition}]
    treatment_arms: List[Dict] = field(default_factory=list)  # [{name, description}]
    stratification_factors: List[str] = field(default_factory=list)
    sample_size: Optional[int] = None
    statistical_methods: List[Dict] = field(default_factory=list)
    visit_schedule: List[Dict] = field(default_factory=list)

    # Source tracking
    extraction_timestamp: str = ""
    protocol_hash: str = ""


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

    def __init__(self, api_key: str, storage_dir: str = None):
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

        print(f"✅ SAP Workbench initialized")
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
        """Extract structured metadata from protocol."""

        workspace = self.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        prompt = f"""Extract structured metadata from this clinical trial protocol.

Return a JSON object with these fields:

{{
  "study_id": "NCT number or protocol ID",
  "study_title": "Full study title",
  "phase": "Phase 1/2/3/4",
  "therapeutic_area": "oncology/cardiology/etc",
  "indication": "Specific disease/condition",

  "objectives": [
    {{"type": "primary", "text": "Primary objective text"}},
    {{"type": "secondary", "text": "Secondary objective text"}}
  ],

  "endpoints": [
    {{
      "name": "Overall Survival",
      "type": "primary",
      "definition": "Time from randomization to death",
      "timeframe": "Up to 5 years",
      "analysis_method": "Cox regression"
    }}
  ],

  "populations": [
    {{
      "name": "Intent-to-Treat",
      "abbreviation": "ITT",
      "definition": "All randomized subjects"
    }}
  ],

  "treatment_arms": [
    {{
      "name": "Treatment A",
      "description": "Drug X 100mg daily"
    }}
  ],

  "stratification_factors": ["Factor 1", "Factor 2"],

  "sample_size": 500,

  "statistical_methods": [
    {{
      "endpoint": "Primary",
      "method": "Cox proportional hazards",
      "measure": "Hazard Ratio"
    }}
  ],

  "visit_schedule": [
    {{"visit": "Screening", "timing": "Day -28 to -1"}},
    {{"visit": "Baseline", "timing": "Day 1"}}
  ]
}}

PROTOCOL:
{workspace.protocol_content[:20000]}

Return ONLY valid JSON, no other text."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # Clean JSON
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
                protocol_hash=workspace.protocol_hash
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

        # Update status
        section.status = SectionStatus.GENERATING

        # Get section-specific prompt
        prompt = self._build_section_prompt(workspace, section_id)

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
        """Build prompt for generating a specific section."""

        metadata = workspace.metadata
        metadata_context = ""
        if metadata:
            metadata_context = f"""
## EXTRACTED METADATA

Study: {metadata.study_id} - {metadata.study_title}
Phase: {metadata.phase}
Therapeutic Area: {metadata.therapeutic_area}
Indication: {metadata.indication}

Objectives:
{json.dumps(metadata.objectives, indent=2)}

Endpoints:
{json.dumps(metadata.endpoints, indent=2)}

Populations:
{json.dumps(metadata.populations, indent=2)}

Treatment Arms:
{json.dumps(metadata.treatment_arms, indent=2)}

Sample Size: {metadata.sample_size}

Statistical Methods:
{json.dumps(metadata.statistical_methods, indent=2)}
"""

        # Get previously generated sections for context
        prev_sections = ""
        for sec_id, section in workspace.sections.items():
            if section.content and sec_id != section_id:
                prev_sections += f"\n### {section.display_name}\n{section.content[:1000]}...\n"

        # Section-specific instructions
        section_instructions = self._get_section_instructions(section_id)

        prompt = f"""Generate the "{workspace.sections[section_id].display_name}" section of a Statistical Analysis Plan.

## CRITICAL: Follow the protocol exactly. Do not add generic content.

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
