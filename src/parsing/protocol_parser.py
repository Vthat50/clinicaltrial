"""Parse protocol text into structured sections using Claude LLM."""
import os
import re
import json
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console

from .section_mappings import SectionType, COMPILED_PATTERNS

console = Console()


@dataclass
class ParsedSection:
    """A parsed section from the protocol."""
    section_type: SectionType
    title: str
    content: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    subsections: list["ParsedSection"] = field(default_factory=list)


@dataclass
class StructuredProtocolData:
    """Structured data extracted by Claude."""
    primary_objectives: list[str] = field(default_factory=list)
    secondary_objectives: list[str] = field(default_factory=list)
    primary_endpoints: list[dict] = field(default_factory=list)  # {name, definition, timing}
    secondary_endpoints: list[dict] = field(default_factory=list)
    study_design: dict = field(default_factory=dict)  # {type, randomization, blinding, arms}
    sample_size: dict = field(default_factory=dict)  # {total, per_arm, power, alpha, assumptions}
    statistical_methods: dict = field(default_factory=dict)  # {primary, secondary, missing_data}
    analysis_populations: dict = field(default_factory=dict)  # {itt, pp, safety}
    efficacy_analyses: dict = field(default_factory=dict)  # {primary, secondary, hypotheses}
    safety_analyses: dict = field(default_factory=dict)  # {ae_analysis, lab_analysis, coding}

    def to_dict(self) -> dict:
        return {
            "primary_objectives": self.primary_objectives,
            "secondary_objectives": self.secondary_objectives,
            "primary_endpoints": self.primary_endpoints,
            "secondary_endpoints": self.secondary_endpoints,
            "study_design": self.study_design,
            "sample_size": self.sample_size,
            "statistical_methods": self.statistical_methods,
            "analysis_populations": self.analysis_populations,
            "efficacy_analyses": self.efficacy_analyses,
            "safety_analyses": self.safety_analyses,
        }


@dataclass
class ParsedProtocol:
    """Complete parsed protocol structure."""
    nct_id: str
    title: Optional[str] = None
    sponsor: Optional[str] = None
    phase: Optional[str] = None
    sections: list[ParsedSection] = field(default_factory=list)
    structured_data: Optional[StructuredProtocolData] = None

    def get_section(self, section_type: SectionType) -> Optional[ParsedSection]:
        """Get a section by type."""
        for section in self.sections:
            if section.section_type == section_type:
                return section
        return None

    def get_sections(self, section_type: SectionType) -> list[ParsedSection]:
        """Get all sections of a type."""
        return [s for s in self.sections if s.section_type == section_type]

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        result = {
            "nct_id": self.nct_id,
            "title": self.title,
            "sponsor": self.sponsor,
            "phase": self.phase,
            "sections": [
                {
                    "type": s.section_type.value,
                    "title": s.title,
                    "content": s.content[:500] + "..." if len(s.content) > 500 else s.content,
                    "page_start": s.page_start,
                    "page_end": s.page_end,
                }
                for s in self.sections
            ],
        }
        if self.structured_data:
            result["structured_data"] = self.structured_data.to_dict()
        return result


CLAUDE_EXTRACTION_PROMPT = """Extract the following from this clinical trial protocol and return as JSON:

{{
  "title": "Full protocol title",
  "sponsor": "Sponsor name",
  "phase": "Study phase (e.g., Phase 3)",
  "primary_objectives": ["List of primary objectives"],
  "secondary_objectives": ["List of secondary objectives"],
  "primary_endpoints": [
    {{"name": "Endpoint name", "definition": "How it's measured", "timing": "When assessed"}}
  ],
  "secondary_endpoints": [
    {{"name": "Endpoint name", "definition": "How it's measured", "timing": "When assessed"}}
  ],
  "study_design": {{
    "type": "e.g., randomized, double-blind, placebo-controlled",
    "randomization_ratio": "e.g., 1:1 or 2:1",
    "blinding": "double-blind/single-blind/open-label",
    "arms": ["List of treatment arms with descriptions"],
    "duration": "Study duration"
  }},
  "sample_size": {{
    "total": number,
    "per_arm": {{"arm1": number, "arm2": number}},
    "power": "e.g., 80% or 90%",
    "alpha": "e.g., 0.05 two-sided",
    "effect_size": "Expected treatment effect",
    "assumptions": ["Key assumptions for sample size"]
  }},
  "statistical_methods": {{
    "primary_analysis": "Method for primary endpoint",
    "secondary_analyses": ["Methods for secondary endpoints"],
    "missing_data": "How missing data will be handled",
    "multiplicity": "Adjustment for multiple comparisons",
    "sensitivity_analyses": ["Planned sensitivity analyses"],
    "interim_analyses": "Interim analysis plan if any"
  }},
  "analysis_populations": {{
    "itt": "Intent-to-treat definition",
    "modified_itt": "Modified ITT definition if applicable",
    "per_protocol": "Per-protocol definition",
    "safety": "Safety population definition"
  }},
  "efficacy_analyses": {{
    "primary_efficacy": "Detailed description of primary efficacy analysis including statistical test, null hypothesis (H0), point estimate, and confidence interval approach",
    "secondary_efficacy": ["List of secondary efficacy analyses with methods"],
    "null_hypothesis": "Formal statement of the null hypothesis (e.g., H0: treatment effect = 0)",
    "treatment_effect_estimate": "How point estimate and treatment effect will be calculated",
    "subgroup_analyses": ["Planned subgroup analyses for efficacy"]
  }},
  "safety_analyses": {{
    "adverse_event_analysis": "How AEs will be summarized and analyzed (e.g., by system organ class, severity, relationship)",
    "ae_coding_dictionary": "Coding dictionary used (e.g., MedDRA version)",
    "serious_ae_handling": "How SAEs will be reported and analyzed",
    "laboratory_analyses": "How lab parameters will be analyzed and presented",
    "vital_signs": "How vital signs will be summarized",
    "exposure_summary": "How treatment exposure will be summarized"
  }}
}}

Return ONLY valid JSON, no other text.

Protocol text:
{text}"""


class ProtocolParser:
    """Parse protocol text into structured sections using Claude LLM."""

    def __init__(self, use_claude: bool = True):
        self.console = Console()
        self.use_claude = use_claude
        self.anthropic_client = None

        if use_claude:
            self._init_anthropic()

    def _init_anthropic(self):
        """Initialize Anthropic client."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=api_key)
                self.console.print("[green]Claude parser initialized[/green]")
            except ImportError:
                self.console.print("[yellow]anthropic package not installed[/yellow]")
                self.use_claude = False
        else:
            self.console.print("[yellow]ANTHROPIC_API_KEY not set, using regex fallback[/yellow]")
            self.use_claude = False

    def parse(self, text: str, nct_id: str) -> ParsedProtocol:
        """Parse protocol text into structured sections.

        Args:
            text: Full protocol text
            nct_id: NCT identifier

        Returns:
            ParsedProtocol with extracted sections and structured data
        """
        protocol = ParsedProtocol(nct_id=nct_id)

        # Try Claude extraction first
        if self.use_claude and self.anthropic_client:
            self.console.print(f"[blue]Parsing {nct_id} with Claude...[/blue]")
            structured = self._parse_with_claude(text)
            if structured:
                protocol.structured_data = structured
                protocol.title = structured.study_design.get("title") or self._extract_title(text)
                protocol.sponsor = self._extract_sponsor(text)
                protocol.phase = structured.study_design.get("phase") or self._extract_phase(text)

                # Convert structured data to sections for compatibility
                protocol.sections = self._structured_to_sections(structured)
                self.console.print(f"[green]Claude extracted {len(protocol.sections)} sections[/green]")
                return protocol

        # Fallback to regex-based parsing
        self.console.print(f"[yellow]Falling back to regex parsing for {nct_id}[/yellow]")
        return self._parse_with_regex(text, nct_id)

    def _parse_with_claude(self, text: str) -> Optional[StructuredProtocolData]:
        """Extract structured data using Claude."""
        # Truncate text if too long (keep first 50k chars for context)
        text_chunk = text[:50000] if len(text) > 50000 else text

        prompt = CLAUDE_EXTRACTION_PROMPT.format(text=text_chunk)

        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            json_text = response.content[0].text.strip()

            # Handle potential markdown code blocks
            if json_text.startswith("```"):
                json_text = re.sub(r'^```(?:json)?\n?', '', json_text)
                json_text = re.sub(r'\n?```$', '', json_text)

            data = json.loads(json_text)

            return StructuredProtocolData(
                primary_objectives=data.get("primary_objectives", []),
                secondary_objectives=data.get("secondary_objectives", []),
                primary_endpoints=data.get("primary_endpoints", []),
                secondary_endpoints=data.get("secondary_endpoints", []),
                study_design=data.get("study_design", {}),
                sample_size=data.get("sample_size", {}),
                statistical_methods=data.get("statistical_methods", {}),
                analysis_populations=data.get("analysis_populations", {}),
                efficacy_analyses=data.get("efficacy_analyses", {}),
                safety_analyses=data.get("safety_analyses", {}),
            )

        except json.JSONDecodeError as e:
            self.console.print(f"[red]Failed to parse Claude response as JSON: {e}[/red]")
            return None
        except Exception as e:
            self.console.print(f"[red]Claude extraction failed: {e}[/red]")
            return None

    def _structured_to_sections(self, data: StructuredProtocolData) -> list[ParsedSection]:
        """Convert structured data back to sections for compatibility."""
        sections = []

        # Objectives section
        if data.primary_objectives or data.secondary_objectives:
            content = "Primary Objectives:\n"
            for obj in data.primary_objectives:
                content += f"• {obj}\n"
            content += "\nSecondary Objectives:\n"
            for obj in data.secondary_objectives:
                content += f"• {obj}\n"
            sections.append(ParsedSection(
                section_type=SectionType.OBJECTIVES,
                title="Study Objectives",
                content=content,
            ))

        # Endpoints section
        if data.primary_endpoints or data.secondary_endpoints:
            content = "Primary Endpoints:\n"
            for ep in data.primary_endpoints:
                content += f"• {ep.get('name', 'N/A')}: {ep.get('definition', 'N/A')}\n"
                if ep.get('timing'):
                    content += f"  Timing: {ep['timing']}\n"
            content += "\nSecondary Endpoints:\n"
            for ep in data.secondary_endpoints:
                content += f"• {ep.get('name', 'N/A')}: {ep.get('definition', 'N/A')}\n"
            sections.append(ParsedSection(
                section_type=SectionType.ENDPOINTS,
                title="Study Endpoints",
                content=content,
            ))

        # Study design section
        if data.study_design:
            sd = data.study_design
            content = f"Design: {sd.get('type', 'N/A')}\n"
            content += f"Randomization: {sd.get('randomization_ratio', 'N/A')}\n"
            content += f"Blinding: {sd.get('blinding', 'N/A')}\n"
            if sd.get('arms'):
                content += "Treatment Arms:\n"
                for arm in sd['arms']:
                    content += f"• {arm}\n"
            if sd.get('duration'):
                content += f"Duration: {sd['duration']}\n"
            sections.append(ParsedSection(
                section_type=SectionType.STUDY_DESIGN,
                title="Study Design",
                content=content,
            ))

        # Sample size section
        if data.sample_size:
            ss = data.sample_size
            content = f"Total Sample Size: {ss.get('total', 'N/A')}\n"
            content += f"Power: {ss.get('power', 'N/A')}\n"
            content += f"Alpha: {ss.get('alpha', 'N/A')}\n"
            content += f"Expected Effect: {ss.get('effect_size', 'N/A')}\n"
            if ss.get('assumptions'):
                content += "Assumptions:\n"
                for assumption in ss['assumptions']:
                    content += f"• {assumption}\n"
            sections.append(ParsedSection(
                section_type=SectionType.SAMPLE_SIZE,
                title="Sample Size",
                content=content,
            ))

        # Statistical methods section
        if data.statistical_methods:
            sm = data.statistical_methods
            content = f"Primary Analysis: {sm.get('primary_analysis', 'N/A')}\n"
            if sm.get('secondary_analyses'):
                content += "Secondary Analyses:\n"
                for analysis in sm['secondary_analyses']:
                    content += f"• {analysis}\n"
            content += f"\nMissing Data: {sm.get('missing_data', 'N/A')}\n"
            content += f"Multiplicity: {sm.get('multiplicity', 'N/A')}\n"
            if sm.get('interim_analyses'):
                content += f"Interim Analysis: {sm['interim_analyses']}\n"
            sections.append(ParsedSection(
                section_type=SectionType.STATISTICAL_METHODS,
                title="Statistical Methods",
                content=content,
            ))

        # Analysis populations section
        if data.analysis_populations:
            ap = data.analysis_populations
            content = f"Intent-to-Treat (ITT): {ap.get('itt', 'N/A')}\n"
            if ap.get('modified_itt'):
                content += f"Modified ITT: {ap['modified_itt']}\n"
            content += f"Per-Protocol: {ap.get('per_protocol', 'N/A')}\n"
            content += f"Safety Population: {ap.get('safety', 'N/A')}\n"
            sections.append(ParsedSection(
                section_type=SectionType.ANALYSIS_POPULATIONS,
                title="Analysis Populations",
                content=content,
            ))

        # Efficacy analyses section
        if data.efficacy_analyses:
            ea = data.efficacy_analyses
            content = "Primary Efficacy Analysis:\n"
            content += f"{ea.get('primary_efficacy', 'N/A')}\n\n"
            if ea.get('null_hypothesis'):
                content += f"Null Hypothesis (H0): {ea['null_hypothesis']}\n\n"
            if ea.get('treatment_effect_estimate'):
                content += f"Point Estimate: {ea['treatment_effect_estimate']}\n\n"
            if ea.get('secondary_efficacy'):
                content += "Secondary Efficacy Analyses:\n"
                for analysis in ea['secondary_efficacy']:
                    content += f"• {analysis}\n"
            if ea.get('subgroup_analyses'):
                content += "\nSubgroup Analyses:\n"
                for subgroup in ea['subgroup_analyses']:
                    content += f"• {subgroup}\n"
            sections.append(ParsedSection(
                section_type=SectionType.EFFICACY_ANALYSES,
                title="Efficacy Analyses",
                content=content,
            ))

        # Safety analyses section
        if data.safety_analyses:
            sa = data.safety_analyses
            content = "Adverse Event Analysis:\n"
            content += f"{sa.get('adverse_event_analysis', 'N/A')}\n\n"
            if sa.get('ae_coding_dictionary'):
                content += f"AE Coding Dictionary: {sa['ae_coding_dictionary']}\n\n"
            if sa.get('serious_ae_handling'):
                content += f"Serious AE Handling: {sa['serious_ae_handling']}\n\n"
            if sa.get('laboratory_analyses'):
                content += f"Laboratory Analyses: {sa['laboratory_analyses']}\n\n"
            if sa.get('vital_signs'):
                content += f"Vital Signs: {sa['vital_signs']}\n\n"
            if sa.get('exposure_summary'):
                content += f"Treatment Exposure: {sa['exposure_summary']}\n"
            sections.append(ParsedSection(
                section_type=SectionType.SAFETY_ANALYSES,
                title="Safety Analyses",
                content=content,
            ))

        return sections

    def _parse_with_regex(self, text: str, nct_id: str) -> ParsedProtocol:
        """Fallback regex-based parsing."""
        protocol = ParsedProtocol(nct_id=nct_id)

        # Extract metadata
        protocol.title = self._extract_title(text)
        protocol.sponsor = self._extract_sponsor(text)
        protocol.phase = self._extract_phase(text)

        # Find section boundaries
        section_boundaries = self._find_section_boundaries(text)

        # Extract each section
        for i, (section_type, title, start_pos) in enumerate(section_boundaries):
            end_pos = (
                section_boundaries[i + 1][2]
                if i + 1 < len(section_boundaries)
                else len(text)
            )

            content = text[start_pos:end_pos].strip()
            content = self._remove_title_from_content(content, title)

            protocol.sections.append(ParsedSection(
                section_type=section_type,
                title=title,
                content=content,
            ))

        self.console.print(f"[green]Regex parsed {len(protocol.sections)} sections from {nct_id}[/green]")
        return protocol

    def _find_section_boundaries(self, text: str) -> list[tuple[SectionType, str, int]]:
        """Find all section boundaries in the text."""
        boundaries = []
        lines = text.split('\n')
        current_pos = 0

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                current_pos += len(line) + 1
                continue

            for section_type, pattern, _ in COMPILED_PATTERNS:
                if pattern.match(line_stripped):
                    boundaries.append((section_type, line_stripped, current_pos))
                    break

            current_pos += len(line) + 1

        boundaries.sort(key=lambda x: x[2])
        return self._deduplicate_boundaries(boundaries)

    def _deduplicate_boundaries(
        self, boundaries: list[tuple[SectionType, str, int]]
    ) -> list[tuple[SectionType, str, int]]:
        """Remove duplicate adjacent sections of the same type."""
        if not boundaries:
            return []

        deduped = [boundaries[0]]
        for boundary in boundaries[1:]:
            if boundary[0] != deduped[-1][0]:
                deduped.append(boundary)
        return deduped

    def _extract_title(self, text: str) -> Optional[str]:
        """Extract protocol title from text."""
        patterns = [
            r"(?i)protocol\s+title[:\s]+([^\n]+)",
            r"(?i)study\s+title[:\s]+([^\n]+)",
            r"(?i)title[:\s]+([^\n]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:5000])
            if match:
                title = match.group(1).strip()
                if len(title) > 10:
                    return title
        return None

    def _extract_sponsor(self, text: str) -> Optional[str]:
        """Extract sponsor from text."""
        patterns = [
            r"(?i)sponsor[:\s]+([^\n]+)",
            r"(?i)sponsored\s+by[:\s]+([^\n]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:5000])
            if match:
                return match.group(1).strip()
        return None

    def _extract_phase(self, text: str) -> Optional[str]:
        """Extract trial phase from text."""
        patterns = [
            r"(?i)(phase\s+[IViv123]+(?:/[IViv123]+)?)",
            r"(?i)phase[:\s]+([IViv123]+(?:/[IViv123]+)?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:5000])
            if match:
                return match.group(1).strip()
        return None

    def _remove_title_from_content(self, content: str, title: str) -> str:
        """Remove the section title from the beginning of content."""
        if content.startswith(title):
            content = content[len(title):].strip()
        return content


if __name__ == "__main__":
    from src.config import PROCESSED_DIR

    parser = ProtocolParser(use_claude=True)
    for txt_file in PROCESSED_DIR.glob("*_Protocol.txt"):
        nct_id = txt_file.stem.replace("_Protocol", "")
        console.print(f"[blue]Parsing {nct_id}...[/blue]")

        with open(txt_file, 'r', encoding='utf-8') as f:
            text = f.read()

        protocol = parser.parse(text, nct_id)
        console.print(f"  Title: {protocol.title}")
        console.print(f"  Phase: {protocol.phase}")
        console.print(f"  Sections: {[s.section_type.value for s in protocol.sections]}")

        if protocol.structured_data:
            console.print(f"  Primary Objectives: {len(protocol.structured_data.primary_objectives)}")
            console.print(f"  Endpoints: {len(protocol.structured_data.primary_endpoints)}")
