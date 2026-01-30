"""Extract SAP-relevant data from protocol with LLM fallback."""
import os
import re
from typing import Optional
from dataclasses import dataclass

from rich.console import Console

from src.parsing.section_mappings import SectionType
from src.parsing.protocol_parser import ParsedProtocol
from .templates import LLM_EXTRACTION_PROMPTS

console = Console()


@dataclass
class ExtractedData:
    """Extracted data for SAP generation."""
    section_key: str
    content: str
    source: str  # "regex" or "llm"
    confidence: float  # 0-1


class SAPDataExtractor:
    """Extract SAP-relevant data from parsed protocols."""

    def __init__(self, use_llm_fallback: bool = True):
        self.use_llm_fallback = use_llm_fallback
        self.anthropic_client = None

        if use_llm_fallback:
            self._init_anthropic()

    def _init_anthropic(self):
        """Initialize Anthropic client if API key available."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=api_key)
                console.print("[green]Anthropic client initialized for LLM fallback[/green]")
            except ImportError:
                console.print("[yellow]anthropic package not installed, LLM fallback disabled[/yellow]")
        else:
            console.print("[yellow]ANTHROPIC_API_KEY not set, LLM fallback disabled[/yellow]")

    def extract_for_sap(self, protocol: ParsedProtocol) -> dict[str, ExtractedData]:
        """Extract all data needed for SAP generation.

        Args:
            protocol: Parsed protocol

        Returns:
            Dictionary mapping section keys to extracted data
        """
        extractions = {}

        # Map of SAP sections to protocol section types
        section_mapping = {
            "introduction": [SectionType.STUDY_IDENTIFICATION],
            "objectives": [SectionType.OBJECTIVES],
            "endpoints": [SectionType.ENDPOINTS],
            "study_design": [SectionType.STUDY_DESIGN, SectionType.TREATMENTS],
            "sample_size": [SectionType.SAMPLE_SIZE],
            "statistical_methods": [SectionType.STATISTICAL_METHODS],
            "analysis_populations": [SectionType.ANALYSIS_POPULATIONS, SectionType.POPULATION],
            "safety": [SectionType.SAFETY, SectionType.SCHEDULE_OF_ASSESSMENTS],
        }

        for sap_key, protocol_types in section_mapping.items():
            # First try regex-based extraction from parsed sections
            content = self._extract_from_sections(protocol, protocol_types)

            if content and len(content) > 100:
                extractions[sap_key] = ExtractedData(
                    section_key=sap_key,
                    content=content,
                    source="regex",
                    confidence=0.8,
                )
            elif self.use_llm_fallback and self.anthropic_client:
                # Fall back to LLM extraction
                console.print(f"[yellow]Using LLM fallback for {sap_key}[/yellow]")
                llm_content = self._extract_with_llm(protocol, sap_key)
                if llm_content:
                    extractions[sap_key] = ExtractedData(
                        section_key=sap_key,
                        content=llm_content,
                        source="llm",
                        confidence=0.9,
                    )
            else:
                # No content found
                extractions[sap_key] = ExtractedData(
                    section_key=sap_key,
                    content=self._get_placeholder(sap_key),
                    source="placeholder",
                    confidence=0.0,
                )

        return extractions

    def _extract_from_sections(
        self, protocol: ParsedProtocol, section_types: list[SectionType]
    ) -> str:
        """Extract content from parsed protocol sections."""
        contents = []

        for section_type in section_types:
            sections = protocol.get_sections(section_type)
            for section in sections:
                if section.content:
                    contents.append(section.content)

        return "\n\n".join(contents)

    def _extract_with_llm(self, protocol: ParsedProtocol, section_key: str) -> Optional[str]:
        """Use Claude to extract information when regex fails."""
        if not self.anthropic_client:
            return None

        prompt_template = LLM_EXTRACTION_PROMPTS.get(section_key)
        if not prompt_template:
            return None

        # Get relevant text (first 50k chars to stay within limits)
        full_text = "\n\n".join(s.content for s in protocol.sections if s.content)
        text_chunk = full_text[:50000]

        prompt = prompt_template.format(text=text_chunk)

        try:
            message = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text
        except Exception as e:
            console.print(f"[red]LLM extraction failed for {section_key}: {e}[/red]")
            return None

    def _get_placeholder(self, section_key: str) -> str:
        """Get placeholder text for missing sections."""
        placeholders = {
            "introduction": "[Study identification information not found in protocol]",
            "objectives": "[Study objectives not found in protocol]",
            "endpoints": "[Study endpoints not found in protocol]",
            "study_design": "[Study design details not found in protocol]",
            "sample_size": "[Sample size justification not found in protocol]",
            "statistical_methods": "[Statistical methods not found in protocol]",
            "analysis_populations": "[Analysis population definitions not found in protocol]",
            "safety": "[Safety analysis information not found in protocol]",
        }
        return placeholders.get(section_key, "[Section content not available]")

    def extract_metadata(self, protocol: ParsedProtocol) -> dict:
        """Extract study metadata."""
        return {
            "nct_id": protocol.nct_id,
            "title": protocol.title or "Unknown Study",
            "phase": protocol.phase or "Unknown",
            "sponsor": protocol.sponsor or "Unknown",
        }


# Regex patterns for specific extractions (used before LLM fallback)
EXTRACTION_PATTERNS = {
    "primary_objective": [
        r"(?i)primary\s+objective[s]?[:\s]+([^\.]+\.)",
        r"(?i)the\s+primary\s+objective[s]?\s+(?:is|are)[:\s]+([^\.]+\.)",
    ],
    "secondary_objective": [
        r"(?i)secondary\s+objective[s]?[:\s]+([^\.]+\.)",
        r"(?i)the\s+secondary\s+objective[s]?\s+(?:is|are)[:\s]+([^\.]+\.)",
    ],
    "primary_endpoint": [
        r"(?i)primary\s+endpoint[s]?[:\s]+([^\.]+\.)",
        r"(?i)primary\s+efficacy\s+endpoint[s]?[:\s]+([^\.]+\.)",
    ],
    "sample_size_value": [
        r"(?i)(?:approximately|total\s+of|enroll)\s+(\d+)\s+(?:patients?|subjects?|participants?)",
        r"(?i)sample\s+size[:\s]+(\d+)",
        r"(?i)(\d+)\s+patients?\s+(?:will\s+be\s+)?(?:enrolled|randomized)",
    ],
    "power": [
        r"(?i)(\d+)[%\s]*power",
        r"(?i)power\s+(?:of\s+)?(\d+)[%]?",
    ],
    "alpha": [
        r"(?i)(?:alpha|significance\s+level)[:\s]+(?:of\s+)?(\d*\.?\d+)",
        r"(?i)(\d*\.?\d+)\s+(?:two-sided\s+)?(?:significance|alpha)",
    ],
}


def extract_specific_value(text: str, pattern_key: str) -> Optional[str]:
    """Extract a specific value using predefined patterns."""
    patterns = EXTRACTION_PATTERNS.get(pattern_key, [])
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None
