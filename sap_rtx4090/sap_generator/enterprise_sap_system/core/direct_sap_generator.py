#!/usr/bin/env python3
"""
Direct SAP Generator
====================

ARCHITECTURE:
Protocol PDF → LlamaParse → Classify ALL content → SAP Template

1. Extract ALL content from protocol (don't lose anything)
2. Split into paragraphs
3. Classify each paragraph into SAP sections by keywords
4. Assemble SAP with classified content
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path

from .section_parser import ProtocolSectionParser
from .section_classifier import (
    classify_with_recovery,
    get_section_content,
    SAP_SECTION_ORDER,
)


@dataclass
class SAPGenerationResult:
    """Result from generating SAP."""
    sap_text: str
    sections_generated: List[str]
    sections_skipped: List[str]
    protocol_sections_used: Dict[str, List[str]]  # SAP section → protocol sections used
    warnings: List[str] = field(default_factory=list)


class DirectSAPGenerator:
    """
    Generate SAP directly from protocol sections.

    Flow:
    1. LlamaParse extracts protocol sections
    2. Rule-based mapping finds relevant protocol sections for each SAP section
    3. DIRECT COPY - protocol section text injected into SAP template (NO LLM)
    """

    def __init__(self):
        """Initialize generator."""
        self.section_parser = ProtocolSectionParser()

    def generate_sap(
        self,
        pdf_path: str,
        sections: Optional[List[str]] = None,
    ) -> SAPGenerationResult:
        """
        Generate SAP from protocol PDF by classifying ALL content.

        Args:
            pdf_path: Path to protocol PDF
            sections: Optional list of SAP sections to generate (default: all)

        Returns:
            SAPGenerationResult with generated SAP text
        """
        print(f"\n{'='*60}")
        print("DIRECT SAP GENERATOR - CLASSIFY ALL CONTENT")
        print(f"{'='*60}")
        print(f"Protocol: {pdf_path}")

        # Step 1: Extract ALL content from protocol using LlamaParse
        print("\n[Step 1] Extracting ALL content with LlamaParse...")
        parsed_protocol = self.section_parser.parse("", pdf_path=pdf_path)
        full_text = parsed_protocol.raw_text or ""
        print(f"  Total text: {len(full_text)} chars")

        # Step 2: Classify ALL paragraphs into SAP sections (with recovery)
        print("\n[Step 2] Classifying content into SAP sections...")
        classified = classify_with_recovery(full_text)

        # Count paragraphs per section
        for section_name, items in classified.items():
            if items:
                print(f"  {section_name}: {len(items)} paragraphs")

        # Step 3: Build SAP sections from classified content
        print("\n[Step 3] Building SAP sections...")
        sap_sections = sections or SAP_SECTION_ORDER
        generated_sections = {}
        sections_skipped = []
        section_stats = {}
        warnings = []

        for sap_section in sap_sections:
            content = get_section_content(classified, sap_section)

            if content:
                generated_sections[sap_section] = content
                para_count = len(classified.get(sap_section, []))
                section_stats[sap_section] = para_count
                print(f"  {sap_section}: {len(content)} chars ({para_count} paragraphs)")
            else:
                sections_skipped.append(sap_section)
                print(f"  {sap_section}: NO CONTENT MATCHED")

        # Report unclassified content
        unclassified = classified.get("unclassified", [])
        if unclassified:
            print(f"\n  [Unclassified: {len(unclassified)} paragraphs]")

        # Step 4: Assemble final SAP
        print("\n[Step 4] Assembling SAP document...")
        sap_text = self._assemble_sap(generated_sections)

        return SAPGenerationResult(
            sap_text=sap_text,
            sections_generated=list(generated_sections.keys()),
            sections_skipped=sections_skipped,
            protocol_sections_used=section_stats,
            warnings=warnings,
        )

    def _assemble_sap(self, sections: Dict[str, str]) -> str:
        """Assemble all sections into final SAP document."""
        sap_parts = [
            "# STATISTICAL ANALYSIS PLAN",
            "",
            "---",
            "",
        ]

        section_titles = {
            "introduction": "1. INTRODUCTION",
            "objectives": "2. STUDY OBJECTIVES",
            "endpoints": "3. STUDY ENDPOINTS",
            "study_design": "4. STUDY DESIGN",
            "sample_size": "5. SAMPLE SIZE DETERMINATION",
            "analysis_populations": "6. ANALYSIS POPULATIONS",
            "statistical_methods": "7. STATISTICAL METHODS",
            "efficacy_analysis": "8. EFFICACY ANALYSIS",
            "safety_analysis": "9. SAFETY ANALYSIS",
            "pharmacokinetics": "10. PHARMACOKINETIC ANALYSIS",
            "interim_analysis": "11. INTERIM ANALYSIS",
            "multiplicity": "12. MULTIPLICITY ADJUSTMENT",
            "missing_data": "13. HANDLING OF MISSING DATA",
            "sensitivity_analysis": "14. SENSITIVITY ANALYSES",
            "subgroup_analysis": "15. SUBGROUP ANALYSES",
        }

        for section_key in SAP_SECTION_ORDER:
            if section_key in sections:
                title = section_titles.get(section_key, section_key.upper())
                content = sections[section_key]
                sap_parts.append(f"## {title}")
                sap_parts.append("")
                sap_parts.append(content)
                sap_parts.append("")
                sap_parts.append("---")
                sap_parts.append("")

        return "\n".join(sap_parts)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_direct_generator() -> DirectSAPGenerator:
    """Create a DirectSAPGenerator instance (no LLM needed)."""
    return DirectSAPGenerator()


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("Direct SAP Generator - Test")
    print("=" * 50)

    generator = DirectSAPGenerator()
    print(f"SAP sections: {SAP_SECTION_ORDER}")
    print(f"Mapping entries: {len(PROTOCOL_TO_SAP_MAPPING)}")
