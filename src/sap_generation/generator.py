"""Generate abbreviated SAP from extracted protocol data."""
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from rich.console import Console

from src.parsing.protocol_parser import ParsedProtocol
from .extractor import SAPDataExtractor, ExtractedData
from .templates import SAP_TEMPLATE, SAP_SECTIONS, SECTION_TEMPLATE

console = Console()


@dataclass
class GeneratedSAP:
    """Generated SAP document."""
    nct_id: str
    title: str
    content: str
    sections: dict[str, str]
    extraction_stats: dict


class SAPGenerator:
    """Generate abbreviated SAP from protocol."""

    def __init__(self, use_llm: bool = True):
        self.extractor = SAPDataExtractor(use_llm_fallback=use_llm)

    def generate(self, protocol: ParsedProtocol) -> GeneratedSAP:
        """Generate abbreviated SAP from parsed protocol.

        Args:
            protocol: Parsed protocol

        Returns:
            GeneratedSAP with full content and sections
        """
        # Extract metadata
        metadata = self.extractor.extract_metadata(protocol)

        # Extract all section data
        extractions = self.extractor.extract_for_sap(protocol)

        # Build sections
        sections = {}
        section_contents = []

        for section_def in SAP_SECTIONS:
            section_content = self._build_section(section_def, extractions)
            sections[section_def.key] = section_content
            section_contents.append(
                SECTION_TEMPLATE.format(
                    title=section_def.title,
                    content=section_content
                )
            )

        # Combine into full SAP
        full_content = SAP_TEMPLATE.format(
            study_title=metadata["title"],
            nct_id=metadata["nct_id"],
            date=datetime.now().strftime("%Y-%m-%d"),
            sections="\n---\n".join(section_contents),
        )

        # Calculate extraction statistics
        stats = self._calculate_stats(extractions)

        console.print(f"[green]Generated SAP for {protocol.nct_id}[/green]")
        console.print(f"  Sections: {len(sections)}")
        console.print(f"  Regex extractions: {stats['regex_count']}")
        console.print(f"  LLM extractions: {stats['llm_count']}")
        console.print(f"  Placeholders: {stats['placeholder_count']}")

        return GeneratedSAP(
            nct_id=protocol.nct_id,
            title=metadata["title"],
            content=full_content,
            sections=sections,
            extraction_stats=stats,
        )

    def _build_section(
        self,
        section_def,
        extractions: dict[str, ExtractedData]
    ) -> str:
        """Build a single SAP section from extractions."""
        # Get relevant extractions for this section
        relevant_keys = self._get_relevant_keys(section_def.key)
        contents = []

        for key in relevant_keys:
            if key in extractions:
                contents.append(extractions[key].content)

        if not contents:
            return f"[{section_def.title} - Content not available]"

        combined = "\n\n".join(contents)

        # Format based on section type
        return self._format_section_content(section_def.key, combined)

    def _get_relevant_keys(self, section_key: str) -> list[str]:
        """Get extraction keys relevant to a SAP section."""
        mapping = {
            "introduction": ["introduction"],
            "objectives_endpoints": ["objectives", "endpoints"],
            "study_design": ["study_design"],
            "analysis_populations": ["analysis_populations"],
            "sample_size": ["sample_size"],
            "statistical_methods": ["statistical_methods"],
            "efficacy_analyses": ["endpoints", "statistical_methods"],
            "safety_analyses": ["safety"],
        }
        return mapping.get(section_key, [section_key])

    def _format_section_content(self, section_key: str, content: str) -> str:
        """Apply section-specific formatting."""
        # Clean up content
        content = content.strip()

        # Add section-specific formatting
        if section_key == "objectives_endpoints":
            content = self._format_objectives_endpoints(content)
        elif section_key == "sample_size":
            content = self._format_sample_size(content)
        elif section_key == "statistical_methods":
            content = self._format_statistical_methods(content)

        return content

    def _format_objectives_endpoints(self, content: str) -> str:
        """Format objectives and endpoints section."""
        # Try to structure as subsections
        formatted = content

        # Add subsection headers if not present
        if "primary objective" in content.lower() and "### " not in content:
            formatted = formatted.replace(
                "Primary Objective",
                "### Primary Objective"
            ).replace(
                "Primary objective",
                "### Primary Objective"
            )

        if "secondary objective" in content.lower():
            formatted = formatted.replace(
                "Secondary Objective",
                "### Secondary Objectives"
            ).replace(
                "Secondary objective",
                "### Secondary Objectives"
            )

        return formatted

    def _format_sample_size(self, content: str) -> str:
        """Format sample size section."""
        return f"""### Sample Size Justification

{content}

### Key Assumptions

*(Extracted from protocol)*
"""

    def _format_statistical_methods(self, content: str) -> str:
        """Format statistical methods section."""
        return f"""### Primary Analysis

{content}

### Missing Data Handling

*(As specified in protocol)*

### Sensitivity Analyses

*(As pre-specified)*
"""

    def _calculate_stats(self, extractions: dict[str, ExtractedData]) -> dict:
        """Calculate extraction statistics."""
        regex_count = sum(1 for e in extractions.values() if e.source == "regex")
        llm_count = sum(1 for e in extractions.values() if e.source == "llm")
        placeholder_count = sum(1 for e in extractions.values() if e.source == "placeholder")
        avg_confidence = (
            sum(e.confidence for e in extractions.values()) / len(extractions)
            if extractions else 0
        )

        return {
            "regex_count": regex_count,
            "llm_count": llm_count,
            "placeholder_count": placeholder_count,
            "total_sections": len(extractions),
            "avg_confidence": round(avg_confidence, 2),
        }

    def save_sap(self, sap: GeneratedSAP, output_path: str) -> bool:
        """Save generated SAP to file."""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(sap.content)
            console.print(f"[green]SAP saved to {output_path}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]Failed to save SAP: {e}[/red]")
            return False
