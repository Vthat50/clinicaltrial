#!/usr/bin/env python3
"""
Protocol Section Parser
========================

Parses clinical protocol documents into logical sections based on ICH E9 structure.
This enables targeted extraction from the correct section rather than searching
the entire document.

Usage:
    parser = ProtocolSectionParser()
    sections = parser.parse(protocol_text)
    stats_section = sections.get("statistical_methods", "")
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ParsedSection:
    """A parsed section from the protocol"""
    name: str
    title: str  # Original section title found
    content: str
    start_pos: int
    end_pos: int
    confidence: float = 1.0


@dataclass
class ParsedProtocol:
    """Complete parsed protocol with all sections"""
    sections: Dict[str, ParsedSection] = field(default_factory=dict)
    raw_text: str = ""
    parse_success: bool = False
    section_count: int = 0

    def get(self, section_name: str, default: str = "") -> str:
        """Get section content by name"""
        section = self.sections.get(section_name)
        return section.content if section else default

    def get_section(self, section_name: str) -> Optional[ParsedSection]:
        """Get full section object"""
        return self.sections.get(section_name)

    def get_combined(self, *section_names: str) -> str:
        """Get combined content from multiple sections"""
        parts = []
        for name in section_names:
            content = self.get(name)
            if content:
                parts.append(content)
        return "\n\n".join(parts)


class ProtocolSectionParser:
    """
    Parse clinical protocol into logical sections.

    Clinical protocols follow ICH E6/E9 guidelines and typically have:
    - Objectives (primary, secondary)
    - Study Design
    - Endpoints/Outcome Measures
    - Statistical Methods
    - Sample Size
    - Analysis Populations
    """

    # Section patterns - ordered by priority
    # Format: (canonical_name, [list of regex patterns])
    SECTION_PATTERNS = {
        "objectives": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(STUDY\s+OBJECTIVES?|OBJECTIVES?|PRIMARY\s+AND\s+SECONDARY\s+OBJECTIVES?)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(TRIAL\s+OBJECTIVES?)",
        ],
        "endpoints": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(ENDPOINTS?|OUTCOME\s+MEASURES?|EFFICACY\s+ENDPOINTS?)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(PRIMARY\s+AND\s+SECONDARY\s+ENDPOINTS?)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(EFFICACY\s+ASSESSMENTS?)",
        ],
        "study_design": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(STUDY\s+DESIGN|TRIAL\s+DESIGN|OVERALL\s+DESIGN)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(DESIGN\s+AND\s+METHODOLOGY)",
        ],
        "statistical_methods": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(STATISTICAL\s+(?:METHODS?|ANALYSIS|CONSIDERATIONS?))",
            r"(?:^|\n)\s*\d*\.?\d*\s*(STATISTICAL\s+AND\s+ANALYTICAL\s+PLANS?)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(ANALYSIS\s+METHODS?)",
        ],
        "sample_size": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(SAMPLE\s+SIZE|DETERMINATION\s+OF\s+SAMPLE\s+SIZE)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(POWER\s+AND\s+SAMPLE\s+SIZE)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(SAMPLE\s+SIZE\s+(?:CALCULATION|JUSTIFICATION))",
        ],
        "populations": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(ANALYSIS\s+POPULATIONS?|STUDY\s+POPULATIONS?)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(POPULATIONS?\s+FOR\s+ANALYSIS)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(ITT|INTENT.TO.TREAT|PER.PROTOCOL)\s+POPULATION",
        ],
        "safety": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(SAFETY\s+(?:ANALYSIS|ASSESSMENTS?|EVALUATIONS?))",
            r"(?:^|\n)\s*\d*\.?\d*\s*(ADVERSE\s+EVENTS?)",
        ],
        "efficacy": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(EFFICACY\s+(?:ANALYSIS|ASSESSMENTS?|EVALUATIONS?))",
            r"(?:^|\n)\s*\d*\.?\d*\s*(PRIMARY\s+EFFICACY\s+ANALYSIS)",
        ],
        "missing_data": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(MISSING\s+DATA|HANDLING\s+OF\s+MISSING)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(IMPUTATION|DATA\s+IMPUTATION)",
        ],
        "multiplicity": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(MULTIPLICITY|MULTIPLE\s+COMPARISONS?|ADJUSTMENT\s+FOR\s+MULTIPLICITY)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(ALPHA\s+(?:SPENDING|ALLOCATION|ADJUSTMENT))",
        ],
        "interim_analysis": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(INTERIM\s+ANALYSIS|INTERIM\s+ANALYSES)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(PLANNED\s+INTERIM)",
        ],
        "subgroups": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(SUBGROUP\s+ANALYSIS|SUBGROUP\s+ANALYSES)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(EXPLORATORY\s+ANALYSES)",
        ],
        "sensitivity": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(SENSITIVITY\s+ANALYSIS|SENSITIVITY\s+ANALYSES)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(SUPPORTIVE\s+ANALYSES)",
        ],
        "pharmacokinetics": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(PHARMACOKINETIC|PK\s+ANALYSIS|PHARMACOKINETICS)",
        ],
        "immunogenicity": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(IMMUNOGENICITY|ANTI.DRUG\s+ANTIBOD)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(ADA\s+ANALYSIS)",
        ],
        "randomization": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(RANDOMIZATION|TREATMENT\s+ASSIGNMENT)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(STRATIFICATION)",
        ],
        "blinding": [
            r"(?:^|\n)\s*\d*\.?\d*\s*(BLINDING|MASKING)",
            r"(?:^|\n)\s*\d*\.?\d*\s*(UNBLINDING|BREAKING\s+THE\s+BLIND)",
        ],
    }

    # Patterns that indicate end of a section (start of next major section)
    END_PATTERNS = [
        r"(?:^|\n)\s*\d+\.\s+[A-Z][A-Z\s]+(?:\n|$)",  # "1. SECTION TITLE"
        r"(?:^|\n)\s*\d+\.\d+\s+[A-Z][A-Z\s]+(?:\n|$)",  # "1.1 SECTION TITLE"
        r"(?:^|\n)\s*[A-Z][A-Z\s]{10,}(?:\n|$)",  # "ALL CAPS HEADER"
    ]

    def __init__(self, min_section_length: int = 50):
        self.min_section_length = min_section_length

    def parse(self, text: str) -> ParsedProtocol:
        """
        Parse protocol text into sections.

        Args:
            text: Full protocol text

        Returns:
            ParsedProtocol with identified sections
        """
        result = ParsedProtocol(raw_text=text)

        if not text or len(text) < 100:
            return result

        # Find all section matches
        section_matches: List[Tuple[str, str, int, int]] = []

        for section_name, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                    section_matches.append((
                        section_name,
                        match.group(1),  # Original title
                        match.start(),
                        match.end()
                    ))

        if not section_matches:
            # No sections found - return entire text as "full_text"
            result.sections["full_text"] = ParsedSection(
                name="full_text",
                title="Full Document",
                content=text,
                start_pos=0,
                end_pos=len(text),
                confidence=0.5
            )
            result.parse_success = True
            result.section_count = 1
            return result

        # Sort by position
        section_matches.sort(key=lambda x: x[2])

        # Remove duplicates - prefer LATER matches (actual content over TOC entries)
        # TOC entries typically appear first but have minimal content
        section_best_matches = {}
        for match in section_matches:
            section_name = match[0]
            start_pos = match[2]

            # Calculate content length to next section or end
            next_section_pos = len(text)
            for other in section_matches:
                if other[2] > start_pos:
                    next_section_pos = min(next_section_pos, other[2])

            content_length = next_section_pos - match[3]  # header_end to next section

            # Skip if this looks like a TOC entry (very short content)
            if content_length < 200:
                continue

            # Prefer the match with most content (actual section over TOC)
            if section_name not in section_best_matches:
                section_best_matches[section_name] = (match, content_length)
            elif content_length > section_best_matches[section_name][1]:
                section_best_matches[section_name] = (match, content_length)

        unique_matches = [m[0] for m in section_best_matches.values()]
        unique_matches.sort(key=lambda x: x[2])  # Sort by position

        # Diagnostic: show what sections were found with actual content
        if section_best_matches:
            print(f"[SectionParser] Found {len(section_best_matches)} sections with actual content:")
            for name, (match, content_len) in sorted(section_best_matches.items(), key=lambda x: x[1][0][2]):
                print(f"  - {name}: {content_len} chars")
        else:
            print(f"[SectionParser] No sections with >200 chars content found (likely TOC-only matches)")

        # Extract content between sections
        for i, (section_name, title, start, header_end) in enumerate(unique_matches):
            # Find end of this section (start of next section or end of document)
            if i < len(unique_matches) - 1:
                end = unique_matches[i + 1][2]
            else:
                end = len(text)

            content = text[header_end:end].strip()

            # Only include if content is substantial
            if len(content) >= self.min_section_length:
                result.sections[section_name] = ParsedSection(
                    name=section_name,
                    title=title.strip(),
                    content=content,
                    start_pos=start,
                    end_pos=end,
                    confidence=0.9
                )

        result.parse_success = True
        result.section_count = len(result.sections)
        return result

    def get_stats_sections(self, parsed: ParsedProtocol) -> str:
        """Get combined statistical methodology sections"""
        return parsed.get_combined(
            "statistical_methods",
            "sample_size",
            "missing_data",
            "multiplicity",
            "interim_analysis",
            "sensitivity"
        )

    def get_efficacy_sections(self, parsed: ParsedProtocol) -> str:
        """Get combined efficacy-related sections"""
        return parsed.get_combined(
            "objectives",
            "endpoints",
            "efficacy",
            "populations"
        )

    def get_safety_sections(self, parsed: ParsedProtocol) -> str:
        """Get combined safety-related sections"""
        return parsed.get_combined(
            "safety",
            "populations"
        )


# Convenience function
def parse_protocol(text: str) -> ParsedProtocol:
    """Quick protocol parsing"""
    return ProtocolSectionParser().parse(text)
