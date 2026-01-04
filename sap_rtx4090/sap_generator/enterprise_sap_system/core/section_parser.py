#!/usr/bin/env python3
"""
Protocol Section Parser (Claude API-based)
============================================

Uses Claude API to intelligently parse clinical protocol documents into logical sections.
This replaces the regex-based approach for more accurate section detection.

Includes Claude Vision fallback for PDF structure analysis when text parsing fails.

Usage:
    parser = ProtocolSectionParser(llm_client=client)
    sections = parser.parse(protocol_text)
    stats_section = sections.get("statistical_methods", "")

    # With PDF for vision fallback:
    sections = parser.parse(protocol_text, pdf_path="/path/to/protocol.pdf")
"""

import json
import re
import base64
import io
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path

# Optional: PyMuPDF for PDF to image conversion
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


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


# Section identification prompt for Claude
SECTION_IDENTIFICATION_PROMPT = '''You are analyzing a clinical trial protocol document. Your task is to identify the boundaries of different sections.

IMPORTANT: Clinical protocols follow ICH E6/E9 structure. Common sections include:
- OBJECTIVES (study objectives, primary/secondary objectives)
- ENDPOINTS (efficacy endpoints, primary/secondary endpoints, outcome measures)
- STUDY_DESIGN (trial design, randomization, blinding)
- STATISTICAL_METHODS (statistical analysis, statistical considerations)
- SAMPLE_SIZE (sample size calculation, power calculation)
- POPULATIONS (analysis populations, ITT, per-protocol, safety population)
- INTERIM_ANALYSIS (interim analyses, DMC, stopping rules)
- MULTIPLICITY (multiple comparisons, alpha adjustment, type I error control)
- MISSING_DATA (missing data handling, imputation, censoring)
- SAFETY (adverse events, safety analysis)
- ESTIMAND (ICH E9 R1 estimand framework, intercurrent events)
- STRATIFICATION (stratification factors, randomization stratification)

For each section you identify, provide:
1. The section name (use the canonical names above)
2. The approximate starting line or position
3. A brief quote from the section header

RESPOND IN JSON FORMAT:
{
    "sections_found": [
        {"name": "OBJECTIVES", "header_text": "2.1 Study Objectives", "start_indicator": "The primary objective..."},
        {"name": "ENDPOINTS", "header_text": "2.2 Endpoints", "start_indicator": "The primary endpoint is..."},
        ...
    ],
    "is_toc_heavy": true/false,
    "notes": "Any observations about document structure"
}

PROTOCOL TEXT (sampled from beginning, middle, and end):
'''

# Vision-based section identification prompt
VISION_SECTION_PROMPT = '''Analyze this clinical trial protocol page image.

Identify any section headers you can see. Look for:
- Table of Contents entries (list with page numbers, dots/leaders)
- Actual section headers (bold text, numbered sections like "9. STATISTICAL METHODS")
- Chapter/section breaks

For each section header visible, tell me:
1. The section name and number (e.g., "9.1 Sample Size")
2. Whether this is a TOC entry or actual content header
3. The page appears to be: TOC page, content page, or appendix

RESPOND IN JSON:
{
    "page_type": "toc" | "content" | "appendix" | "title",
    "sections_visible": [
        {"header": "9. Statistical Methods", "is_toc_entry": false, "section_type": "STATISTICAL_METHODS"},
        ...
    ],
    "notes": "Any observations"
}
'''


class ProtocolSectionParser:
    """
    Parse clinical protocol into logical sections using Claude API.

    This approach is more accurate than regex because:
    1. Claude understands document structure semantically
    2. Can distinguish TOC entries from actual content
    3. Handles varied formatting across sponsors
    """

    # Canonical section names for mapping
    CANONICAL_SECTIONS = [
        "objectives", "endpoints", "study_design", "statistical_methods",
        "sample_size", "populations", "interim_analysis", "multiplicity",
        "missing_data", "safety", "efficacy", "estimand", "stratification",
        "randomization", "blinding", "pharmacokinetics", "immunogenicity",
        "subgroups", "sensitivity"
    ]

    def __init__(self, llm_client=None, min_section_length: int = 50, vision_client=None):
        """
        Initialize parser.

        Args:
            llm_client: Claude API client with chat() method
            min_section_length: Minimum section length to include
            vision_client: Optional separate client for vision (uses llm_client if not provided)
        """
        self.llm_client = llm_client
        self.vision_client = vision_client or llm_client
        self.min_section_length = min_section_length

    def parse(self, text: str, pdf_path: Optional[str] = None) -> ParsedProtocol:
        """
        Parse protocol text into sections using Claude API.

        Args:
            text: Full protocol text
            pdf_path: Optional path to PDF for vision-based fallback

        Returns:
            ParsedProtocol with identified sections
        """
        result = ParsedProtocol(raw_text=text)

        if not text or len(text) < 100:
            return result

        # If no LLM client, use the full document approach
        if self.llm_client is None:
            print("[SectionParser] No LLM client - returning full document")
            result.sections["full_text"] = ParsedSection(
                name="full_text",
                title="Full Document",
                content=text,
                start_pos=0,
                end_pos=len(text),
                confidence=1.0
            )
            result.parse_success = True
            result.section_count = 1
            return result

        try:
            # Use Claude to identify sections from text
            sections = self._identify_sections_with_claude(text)

            if sections:
                result.sections = sections
                result.parse_success = True
                result.section_count = len(sections)
                print(f"[SectionParser] Claude identified {len(sections)} sections: {list(sections.keys())}")
            else:
                # Try vision fallback if PDF is available
                if pdf_path and PYMUPDF_AVAILABLE and self.vision_client:
                    print("[SectionParser] Text parsing failed - trying Claude Vision fallback...")
                    sections = self._identify_sections_with_vision(text, pdf_path)

                    if sections:
                        result.sections = sections
                        result.parse_success = True
                        result.section_count = len(sections)
                        print(f"[SectionParser] Vision identified {len(sections)} sections: {list(sections.keys())}")
                        return result

                # Fallback to full document if both methods fail
                print("[SectionParser] Section parsing failed - using full document")
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

        except Exception as e:
            print(f"[SectionParser] Error using Claude API: {e}")
            # Fallback to full document
            result.sections["full_text"] = ParsedSection(
                name="full_text",
                title="Full Document",
                content=text,
                start_pos=0,
                end_pos=len(text),
                confidence=0.3
            )
            result.parse_success = True
            result.section_count = 1

        return result

    def _identify_sections_with_claude(self, text: str) -> Dict[str, ParsedSection]:
        """Use Claude API to identify section boundaries."""

        # Sample from MULTIPLE parts of the document, not just the beginning
        # Clinical protocols often have long introductions before statistical content
        text_len = len(text)

        # Build a representative sample:
        # - First 8000 chars (title, synopsis, objectives)
        # - Middle section where statistical methods usually are (around 40-60% of doc)
        # - Sample from 70-85% where interim/multiplicity often appears
        samples = []

        # Beginning (synopsis, objectives, design)
        samples.append(("BEGINNING", text[:8000]))

        # Middle (statistical methods, sample size typically here)
        if text_len > 20000:
            mid_start = int(text_len * 0.35)
            samples.append(("MIDDLE", text[mid_start:mid_start + 8000]))

        # Later section (interim analysis, multiplicity, missing data)
        if text_len > 40000:
            late_start = int(text_len * 0.6)
            samples.append(("LATE", text[late_start:late_start + 8000]))

        # Combine samples with markers
        preview_text = "\n\n--- DOCUMENT SECTION: BEGINNING ---\n" + samples[0][1]
        for label, content in samples[1:]:
            preview_text += f"\n\n--- DOCUMENT SECTION: {label} ---\n" + content

        prompt = SECTION_IDENTIFICATION_PROMPT + preview_text[:25000]  # Cap at 25k total

        try:
            response = self.llm_client.chat(prompt, max_tokens=2000)

            # Handle different response types
            if hasattr(response, 'content'):
                response_text = response.content
            elif isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)

            # Parse JSON response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                print("[SectionParser] No JSON in Claude response")
                return {}

            data = json.loads(json_match.group())
            sections_found = data.get("sections_found", [])

            if not sections_found:
                print("[SectionParser] Claude found no sections")
                return {}

            # Now extract actual section content based on identified headers
            return self._extract_sections_from_markers(text, sections_found)

        except json.JSONDecodeError as e:
            print(f"[SectionParser] JSON parse error: {e}")
            return {}
        except Exception as e:
            print(f"[SectionParser] Claude API error: {e}")
            return {}

    def _is_toc_line(self, text: str, pos: int) -> bool:
        """Check if the line at position is a TOC entry (has dots + page number)."""
        # Find line boundaries
        line_start = text.rfind('\n', 0, pos) + 1
        line_end = text.find('\n', pos)
        if line_end == -1:
            line_end = len(text)

        line = text[line_start:line_end]

        # Pattern 1: Multiple consecutive dots followed by digits
        # e.g., "Section Title.....123" or "Section Title ..... 123"
        if re.search(r'\.{3,}\s*\d+', line):
            return True

        # Pattern 2: Lots of dots in line (leader dots) + ends with number
        # e.g., "Section Title . . . . . . 42"
        if line.count('.') > 10 and re.search(r'\d{1,3}\s*$', line):
            return True

        # Pattern 3: Spaced dots pattern (individual dots separated by spaces)
        # e.g., ". . . . . . . 42" or "Section . . . 42"
        if re.search(r'(\.\s+){5,}\d+', line):
            return True

        # Pattern 4: Line ends with just spaces and a page number (no content after header)
        # e.g., "9.8 Multiplicity                    42"
        # Check: header at start, then mostly spaces, then number at end
        if re.match(r'^[\d.]+\s+\S+.*\s{10,}\d{1,3}\s*$', line):
            return True

        # Pattern 5: Very short line that's just section number + title + page
        # These are typically TOC lines
        if len(line.strip()) < 80 and re.search(r'\s+\d{1,3}\s*$', line):
            # Check if it's mostly whitespace between title and number
            parts = re.split(r'\s{5,}', line)
            if len(parts) >= 2:
                return True

        return False

    def _find_flexible_section_match(self, text: str, header_text: str, section_name: str) -> int:
        """
        Try flexible matching when exact match fails.

        Handles formatting differences like:
        - "9.8 Multiplicity" vs "9.8  MULTIPLICITY"
        - "9.8 Multiplicity" vs "9.8. Multiplicity"
        - "Section 9.8 Multiplicity" vs "9.8 Multiplicity"
        """
        # Extract section number (e.g., "9.8" from "9.8 Multiplicity")
        section_num_match = re.search(r'^(\d+\.?\d*)', header_text.strip())
        if not section_num_match:
            return -1

        section_num = section_num_match.group(1)

        # Build flexible pattern: section number + any whitespace + word(s)
        # Match "9.8", "9.8.", "9.8:" followed by whitespace and text
        pattern = rf'{re.escape(section_num)}[.:\s]+\s*\w+'

        # Find all matches
        matches = list(re.finditer(pattern, text, re.IGNORECASE))

        if not matches:
            return -1

        # Check from last to first, skip TOC entries
        for match in reversed(matches):
            pos = match.start()

            if not self._is_toc_line(text, pos):
                preview = text[pos:min(pos+100, len(text))].replace('\n', ' ')
                print(f"[SectionParser] Flexible match for '{section_num}' at {pos}: '{preview}...'")
                return pos

        print(f"[SectionParser] Flexible search for '{section_num}': all {len(matches)} matches were TOC")
        return -1

    def _find_non_toc_occurrence(self, text: str, text_lower: str, search_term: str) -> int:
        """Find the last occurrence of search_term that is NOT in a TOC line."""
        search_lower = search_term.lower()
        pos = len(text)
        occurrence_count = 0
        toc_count = 0

        # Search backwards through all occurrences
        while True:
            pos = text_lower.rfind(search_lower, 0, pos)
            if pos == -1:
                if occurrence_count > 0:
                    print(f"[SectionParser] '{search_term[:30]}': {occurrence_count} occurrences, {toc_count} were TOC")
                return -1  # Not found at all

            occurrence_count += 1

            # Check if this occurrence is in a TOC line
            if not self._is_toc_line(text, pos):
                # Preview content after this position
                preview_end = min(pos + 200, len(text))
                preview = text[pos:preview_end].replace('\n', ' ')[:100]
                print(f"[SectionParser] Found non-TOC '{search_term[:20]}' at {pos}: '{preview}...'")
                return pos  # Found a non-TOC occurrence

            # This was a TOC line, keep searching backwards
            toc_count += 1

            if pos == 0:
                print(f"[SectionParser] '{search_term[:30]}': ALL {occurrence_count} occurrences were TOC lines!")
                return -1  # Reached beginning, all occurrences were TOC

        return -1

    def _extract_sections_from_markers(
        self,
        text: str,
        sections_found: List[dict]
    ) -> Dict[str, ParsedSection]:
        """Extract section content based on Claude-identified markers."""

        sections = {}
        text_lower = text.lower()

        # Find positions of each section header
        section_positions = []

        for section_info in sections_found:
            name = section_info.get("name", "").lower()
            header_text = section_info.get("header_text", "")
            start_indicator = section_info.get("start_indicator", "")

            # Skip if not a canonical section
            if name not in self.CANONICAL_SECTIONS:
                # Try to map to canonical name
                name = self._map_to_canonical(name)
                if not name:
                    continue

            # Find the section in the text - skip TOC entries
            pos = -1

            # Try header text first - find LAST non-TOC occurrence
            if header_text:
                pos = self._find_non_toc_occurrence(text, text_lower, header_text)

                # If not found, try flexible matching (handles "9.8 Title" vs "9.8  TITLE")
                if pos == -1:
                    pos = self._find_flexible_section_match(text, header_text, name)

            # Try start indicator if header not found
            if pos == -1 and start_indicator:
                indicator_text = start_indicator[:50]  # First 50 chars
                pos = self._find_non_toc_occurrence(text, text_lower, indicator_text)

            if pos != -1:
                section_positions.append((name, header_text, pos))
            else:
                print(f"[SectionParser] Section '{name}' only found in TOC, no actual content")

        # Sort by position
        section_positions.sort(key=lambda x: x[2])

        # Extract content between sections
        for i, (name, header, start_pos) in enumerate(section_positions):
            # Find end position (start of next section or end of document)
            if i < len(section_positions) - 1:
                end_pos = section_positions[i + 1][2]
            else:
                end_pos = len(text)

            # Extract content
            content = text[start_pos:end_pos].strip()

            # Skip if too short
            if len(content) < self.min_section_length:
                continue

            # Skip if this looks like a TOC entry (lots of dots, very short)
            if content.count('.') > 50 and len(content) < 500:
                continue

            sections[name] = ParsedSection(
                name=name,
                title=header,
                content=content,
                start_pos=start_pos,
                end_pos=end_pos,
                confidence=0.85
            )

        return sections

    def _map_to_canonical(self, name: str) -> Optional[str]:
        """Map a section name to canonical form."""
        name_lower = name.lower().strip()

        mappings = {
            "objective": "objectives",
            "primary objective": "objectives",
            "secondary objective": "objectives",
            "endpoint": "endpoints",
            "primary endpoint": "endpoints",
            "secondary endpoint": "endpoints",
            "outcome measure": "endpoints",
            "design": "study_design",
            "trial design": "study_design",
            "statistical": "statistical_methods",
            "statistical analysis": "statistical_methods",
            "statistical consideration": "statistical_methods",
            "sample size": "sample_size",
            "power": "sample_size",
            "population": "populations",
            "analysis population": "populations",
            "interim": "interim_analysis",
            "interim analyses": "interim_analysis",
            "multiple comparison": "multiplicity",
            "multiplicity adjustment": "multiplicity",
            "missing": "missing_data",
            "censoring": "missing_data",
            "safety analysis": "safety",
            "adverse event": "safety",
            "efficacy analysis": "efficacy",
            "stratification factor": "stratification",
        }

        for key, canonical in mappings.items():
            if key in name_lower:
                return canonical

        # Direct match
        if name_lower in self.CANONICAL_SECTIONS:
            return name_lower

        return None

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

    def _identify_sections_with_vision(
        self,
        text: str,
        pdf_path: str
    ) -> Dict[str, ParsedSection]:
        """
        Use Claude Vision to analyze PDF pages and identify document structure.

        This is a fallback when text-based parsing fails.
        """
        if not PYMUPDF_AVAILABLE:
            print("[SectionParser] PyMuPDF not available for vision fallback")
            return {}

        try:
            # Open PDF and sample key pages
            doc = fitz.open(pdf_path)
            total_pages = len(doc)

            # Sample strategic pages:
            # - TOC pages (usually pages 2-5)
            # - Middle pages where statistical methods likely are
            # - Later pages for interim/multiplicity
            pages_to_analyze = []

            # TOC region (pages 2-5)
            for i in range(1, min(5, total_pages)):
                pages_to_analyze.append(i)

            # Middle region (40-50% through document)
            mid_page = int(total_pages * 0.45)
            pages_to_analyze.extend([mid_page, mid_page + 1])

            # Later region (60-70%)
            late_page = int(total_pages * 0.65)
            pages_to_analyze.extend([late_page, late_page + 1])

            # Remove duplicates and invalid indices
            pages_to_analyze = sorted(set(p for p in pages_to_analyze if 0 <= p < total_pages))

            print(f"[SectionParser/Vision] Analyzing pages: {pages_to_analyze}")

            all_sections_found = []

            for page_num in pages_to_analyze[:6]:  # Limit to 6 pages max
                # Render page to image
                page = doc[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))  # 1.5x zoom for readability

                # Convert to base64
                img_bytes = pix.tobytes("png")
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')

                # Send to Claude Vision
                sections = self._analyze_page_with_vision(img_base64, page_num)
                all_sections_found.extend(sections)

            doc.close()

            if not all_sections_found:
                return {}

            # Deduplicate and filter to content headers (not TOC entries)
            content_headers = [
                s for s in all_sections_found
                if not s.get("is_toc_entry", True)
            ]

            if not content_headers:
                # If all were TOC entries, use them but note lower confidence
                print("[SectionParser/Vision] Only TOC entries found - extracting from text")
                content_headers = all_sections_found

            # Convert to sections based on text search
            return self._extract_sections_from_markers(text, [
                {
                    "name": s.get("section_type", "").upper(),
                    "header_text": s.get("header", ""),
                    "start_indicator": s.get("header", "")[:30]
                }
                for s in content_headers
            ])

        except Exception as e:
            print(f"[SectionParser/Vision] Error: {e}")
            return {}

    def _analyze_page_with_vision(
        self,
        img_base64: str,
        page_num: int
    ) -> List[dict]:
        """Send a single page image to Claude Vision for analysis."""
        try:
            # Build multimodal message
            # Note: This assumes the vision_client supports Claude's vision API format
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": VISION_SECTION_PROMPT
                        }
                    ]
                }
            ]

            # Call vision API
            # Try different client interfaces
            if hasattr(self.vision_client, 'messages'):
                # Anthropic SDK style
                response = self.vision_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    messages=messages
                )
                response_text = response.content[0].text
            elif hasattr(self.vision_client, 'chat_with_images'):
                # Custom interface
                response_text = self.vision_client.chat_with_images(
                    VISION_SECTION_PROMPT,
                    images=[img_base64]
                )
            else:
                print(f"[SectionParser/Vision] Vision client doesn't support image input")
                return []

            # Parse JSON response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                return []

            data = json.loads(json_match.group())
            sections = data.get("sections_visible", [])

            print(f"[SectionParser/Vision] Page {page_num}: {data.get('page_type', 'unknown')} - {len(sections)} sections")
            return sections

        except Exception as e:
            print(f"[SectionParser/Vision] Error analyzing page {page_num}: {e}")
            return []


# Convenience function
def parse_protocol(text: str, llm_client=None) -> ParsedProtocol:
    """Quick protocol parsing"""
    return ProtocolSectionParser(llm_client=llm_client).parse(text)
