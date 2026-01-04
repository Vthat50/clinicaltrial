#!/usr/bin/env python3
"""
Protocol Section Parser (Claude Vision-based)
==============================================

Uses Claude Vision to intelligently parse clinical protocol PDFs into logical sections.
Vision is the PRIMARY method - it understands document structure visually.

NO REGEX for TOC detection. Claude handles everything semantically.

Usage:
    parser = ProtocolSectionParser(llm_client=client)
    sections = parser.parse(protocol_text, pdf_path="/path/to/protocol.pdf")
    stats_section = sections.get("statistical_methods", "")
"""

import json
import base64
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

# PyMuPDF for PDF to image conversion
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("[SectionParser] WARNING: PyMuPDF not available - install with: pip install pymupdf")


@dataclass
class ParsedSection:
    """A parsed section from the protocol"""
    name: str
    title: str
    content: str
    start_page: int = 0
    end_page: int = 0
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


# Vision prompt to analyze document structure
VISION_STRUCTURE_PROMPT = '''Analyze this clinical trial protocol page.

Tell me:
1. Is this a Table of Contents page, or actual content?
2. If content: What section is this? (e.g., "9.1 Sample Size", "Statistical Methods")
3. What's the page number shown on this page (if visible)?

RESPOND IN JSON:
{
    "is_toc_page": true/false,
    "is_content_page": true/false,
    "page_number_shown": <number or null>,
    "sections_on_page": [
        {"section_number": "9.1", "section_title": "Sample Size", "section_type": "SAMPLE_SIZE"},
        ...
    ],
    "notes": "any observations"
}

Section types to use:
- OBJECTIVES
- ENDPOINTS
- STUDY_DESIGN
- STATISTICAL_METHODS
- SAMPLE_SIZE
- POPULATIONS
- INTERIM_ANALYSIS
- MULTIPLICITY
- MISSING_DATA
- SAFETY
- ESTIMAND
- STRATIFICATION
'''

# Prompt to find specific section locations
VISION_FIND_SECTIONS_PROMPT = '''I need to find where these sections START in a clinical trial protocol PDF.

Look at these sample pages from the document and tell me:
1. Which pages contain the TABLE OF CONTENTS?
2. Which pages contain the ACTUAL CONTENT for each section?

I'm looking for these sections:
- Statistical Methods / Statistical Considerations
- Sample Size / Power Calculation
- Analysis Populations
- Interim Analysis
- Multiplicity Adjustments
- Missing Data Handling
- Primary Endpoint Analysis
- Secondary Endpoint Analysis
- Safety Analysis

RESPOND IN JSON:
{
    "toc_pages": [2, 3, 4],
    "section_locations": [
        {"section_type": "STATISTICAL_METHODS", "content_starts_page": 125, "section_title": "9. Statistical Methods"},
        {"section_type": "SAMPLE_SIZE", "content_starts_page": 130, "section_title": "9.1 Sample Size"},
        ...
    ],
    "total_pages_analyzed": 10,
    "notes": "observations about document structure"
}
'''


class ProtocolSectionParser:
    """
    Parse clinical protocol into logical sections using Claude Vision.

    Vision is the PRIMARY method because:
    1. It visually distinguishes TOC from content pages
    2. It reads section headers regardless of text formatting
    3. It handles varied PDF structures across sponsors
    4. No brittle regex patterns needed
    """

    CANONICAL_SECTIONS = [
        "objectives", "endpoints", "study_design", "statistical_methods",
        "sample_size", "populations", "interim_analysis", "multiplicity",
        "missing_data", "safety", "efficacy", "estimand", "stratification",
        "randomization", "blinding", "subgroups", "sensitivity"
    ]

    def __init__(self, llm_client=None, vision_client=None):
        """
        Initialize parser.

        Args:
            llm_client: Claude API client (used for vision if vision_client not provided)
            vision_client: Anthropic client with vision support
        """
        self.llm_client = llm_client
        self.vision_client = vision_client or llm_client

    def parse(self, text: str, pdf_path: Optional[str] = None) -> ParsedProtocol:
        """
        Parse protocol using Claude Vision as PRIMARY method.

        Args:
            text: Full protocol text (for content extraction after Vision identifies pages)
            pdf_path: Path to PDF file (REQUIRED for Vision-based parsing)

        Returns:
            ParsedProtocol with identified sections
        """
        result = ParsedProtocol(raw_text=text)

        if not text or len(text) < 100:
            return result

        # Vision requires PDF path
        if pdf_path and PYMUPDF_AVAILABLE and self.vision_client:
            print("[SectionParser] Using Claude Vision to analyze PDF structure...")
            sections = self._parse_with_vision(text, pdf_path)

            if sections:
                result.sections = sections
                result.parse_success = True
                result.section_count = len(sections)
                print(f"[SectionParser] Vision identified {len(sections)} sections: {list(sections.keys())}")
                return result
            else:
                print("[SectionParser] Vision parsing returned no sections")

        # If no PDF or Vision failed, ask Claude to extract from text directly
        if self.llm_client:
            print("[SectionParser] Using Claude to extract sections from text...")
            sections = self._extract_with_claude_text(text)

            if sections:
                result.sections = sections
                result.parse_success = True
                result.section_count = len(sections)
                return result

        # Ultimate fallback: return full text
        print("[SectionParser] Returning full document as single section")
        result.sections["full_text"] = ParsedSection(
            name="full_text",
            title="Full Document",
            content=text,
            confidence=0.3
        )
        result.parse_success = True
        result.section_count = 1
        return result

    def _parse_with_vision(self, text: str, pdf_path: str) -> Dict[str, ParsedSection]:
        """
        Use Claude Vision to understand PDF structure and extract sections.

        Strategy:
        1. Analyze sample pages to understand document structure
        2. Identify TOC pages vs content pages
        3. Find where each section starts
        4. Extract text from those specific pages
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            print(f"[SectionParser/Vision] PDF has {total_pages} pages")

            # Step 1: Analyze document structure with sample pages
            structure = self._analyze_document_structure(doc, total_pages)

            if not structure:
                doc.close()
                return {}

            # Step 2: Extract text from identified content pages
            sections = self._extract_sections_from_pages(doc, text, structure)

            doc.close()
            return sections

        except Exception as e:
            print(f"[SectionParser/Vision] Error: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _analyze_document_structure(self, doc, total_pages: int) -> Dict[str, Any]:
        """
        Analyze PDF structure using Vision on strategic pages.

        Returns dict with:
        - toc_pages: list of TOC page numbers
        - section_locations: list of {section_type, content_starts_page, section_title}
        """
        # Sample pages strategically:
        # - Early pages (TOC usually pages 2-10)
        # - Middle pages (statistical methods often 40-60% through)
        # - Later pages (appendices, additional methods)

        pages_to_sample = []

        # Early pages for TOC
        for i in range(min(10, total_pages)):
            pages_to_sample.append(i)

        # Middle pages where statistical sections likely are
        mid_start = int(total_pages * 0.4)
        for i in range(mid_start, min(mid_start + 5, total_pages)):
            pages_to_sample.append(i)

        # Later middle (60-70%)
        late_mid = int(total_pages * 0.6)
        for i in range(late_mid, min(late_mid + 5, total_pages)):
            pages_to_sample.append(i)

        pages_to_sample = sorted(set(pages_to_sample))
        print(f"[SectionParser/Vision] Sampling pages: {pages_to_sample[:15]}...")

        # Analyze each page with Vision
        page_analyses = []

        for page_num in pages_to_sample[:15]:  # Max 15 pages
            analysis = self._analyze_single_page(doc, page_num)
            if analysis:
                analysis['pdf_page'] = page_num
                page_analyses.append(analysis)

        if not page_analyses:
            print("[SectionParser/Vision] No pages could be analyzed")
            return {}

        # Aggregate results
        toc_pages = []
        section_locations = {}

        for analysis in page_analyses:
            pdf_page = analysis.get('pdf_page', 0)

            if analysis.get('is_toc_page'):
                toc_pages.append(pdf_page)

            if analysis.get('is_content_page'):
                for section in analysis.get('sections_on_page', []):
                    section_type = section.get('section_type', '').lower()
                    if section_type and section_type in self.CANONICAL_SECTIONS:
                        # Only keep first occurrence (actual content, not repeated references)
                        if section_type not in section_locations:
                            section_locations[section_type] = {
                                'content_starts_page': pdf_page,
                                'section_title': section.get('section_title', ''),
                                'section_number': section.get('section_number', '')
                            }

        print(f"[SectionParser/Vision] Found TOC on pages: {toc_pages}")
        print(f"[SectionParser/Vision] Found sections: {list(section_locations.keys())}")

        return {
            'toc_pages': toc_pages,
            'section_locations': section_locations,
            'total_pages': len(doc)
        }

    def _analyze_single_page(self, doc, page_num: int) -> Optional[Dict]:
        """Analyze a single PDF page with Claude Vision."""
        try:
            page = doc[page_num]

            # Render to image (1.5x zoom for readability)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img_bytes = pix.tobytes("png")
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')

            # Call Claude Vision
            response = self._call_vision_api(img_base64, VISION_STRUCTURE_PROMPT)

            if not response:
                return None

            # Parse JSON from response
            try:
                # Find JSON in response
                response_text = response
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = response_text[start:end]
                    return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            return None

        except Exception as e:
            print(f"[SectionParser/Vision] Error on page {page_num}: {e}")
            return None

    def _call_vision_api(self, img_base64: str, prompt: str) -> Optional[str]:
        """Call Claude Vision API with an image."""
        try:
            # Build multimodal message
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
                            "text": prompt
                        }
                    ]
                }
            ]

            # Try Anthropic SDK interface
            if hasattr(self.vision_client, 'messages'):
                response = self.vision_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1500,
                    messages=messages
                )
                return response.content[0].text

            # Try chat_with_vision interface
            elif hasattr(self.vision_client, 'chat_with_vision'):
                return self.vision_client.chat_with_vision(prompt, img_base64)

            # Try generic interface that accepts messages
            elif hasattr(self.vision_client, 'create'):
                response = self.vision_client.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1500,
                    messages=messages
                )
                return response.content[0].text

            else:
                print("[SectionParser/Vision] No compatible vision API interface found")
                return None

        except Exception as e:
            print(f"[SectionParser/Vision] API error: {e}")
            return None

    def _extract_sections_from_pages(
        self,
        doc,
        full_text: str,
        structure: Dict[str, Any]
    ) -> Dict[str, ParsedSection]:
        """
        Extract section content from identified pages.

        Uses Vision-identified page numbers to extract text.
        """
        sections = {}
        section_locations = structure.get('section_locations', {})
        total_pages = structure.get('total_pages', len(doc))

        # Sort sections by page number to determine boundaries
        sorted_sections = sorted(
            section_locations.items(),
            key=lambda x: x[1].get('content_starts_page', 0)
        )

        for i, (section_type, info) in enumerate(sorted_sections):
            start_page = info.get('content_starts_page', 0)
            section_title = info.get('section_title', section_type)

            # End page is start of next section, or +10 pages, or end of doc
            if i + 1 < len(sorted_sections):
                end_page = sorted_sections[i + 1][1].get('content_starts_page', start_page + 10)
            else:
                end_page = min(start_page + 15, total_pages)

            # Extract text from these pages
            content_parts = []
            for page_num in range(start_page, min(end_page, total_pages)):
                try:
                    page = doc[page_num]
                    page_text = page.get_text()
                    if page_text:
                        content_parts.append(page_text)
                except Exception as e:
                    print(f"[SectionParser] Error extracting page {page_num}: {e}")

            content = "\n".join(content_parts).strip()

            if len(content) > 100:  # Minimum content length
                sections[section_type] = ParsedSection(
                    name=section_type,
                    title=section_title,
                    content=content,
                    start_page=start_page,
                    end_page=end_page,
                    confidence=0.9
                )
                print(f"[SectionParser] Extracted '{section_type}' from pages {start_page}-{end_page} ({len(content)} chars)")

        return sections

    def _extract_with_claude_text(self, text: str) -> Dict[str, ParsedSection]:
        """
        Extract sections from text using Claude.

        CRITICAL: Sample from MULTIPLE parts of the document!
        Statistical methods are typically at 60-80% through the protocol,
        not in the first 50K characters.
        """
        text_len = len(text)
        print(f"[SectionParser] Text length: {text_len} chars")

        # Sample from MULTIPLE parts of the document
        # Clinical protocols have statistical content at 50-80% through
        samples = []

        # Beginning (title, synopsis, objectives) - first 8K
        samples.append(("BEGINNING (Title, Synopsis)", text[:8000]))

        # Early middle (study design, endpoints) - 25-35%
        if text_len > 30000:
            early_mid = int(text_len * 0.25)
            samples.append(("STUDY DESIGN (~25%)", text[early_mid:early_mid + 8000]))

        # Middle (where statistical methods often START) - 50-60%
        if text_len > 50000:
            mid_start = int(text_len * 0.50)
            samples.append(("STATISTICAL METHODS START (~50%)", text[mid_start:mid_start + 10000]))

        # Late middle (sample size, populations) - 60-70%
        if text_len > 80000:
            late_mid = int(text_len * 0.60)
            samples.append(("SAMPLE SIZE/POPULATIONS (~60%)", text[late_mid:late_mid + 10000]))

        # Later (interim, multiplicity) - 70-80%
        if text_len > 100000:
            later = int(text_len * 0.70)
            samples.append(("INTERIM/MULTIPLICITY (~70%)", text[later:later + 10000]))

        # Near end (missing data, sensitivity) - 80-90%
        if text_len > 120000:
            near_end = int(text_len * 0.80)
            samples.append(("MISSING DATA/SENSITIVITY (~80%)", text[near_end:near_end + 8000]))

        # Combine samples with markers
        combined_text = ""
        for label, content in samples:
            combined_text += f"\n\n=== {label} ===\n{content}"

        print(f"[SectionParser] Sampled {len(samples)} regions, total {len(combined_text)} chars")

        prompt = f'''Analyze this clinical trial protocol text (sampled from multiple parts of the document) and extract the statistical methodology sections.

For each section you find, provide:
1. Section name (e.g., "sample_size", "multiplicity", "interim_analysis")
2. The FULL content of that section (not just a summary)

RESPOND IN JSON:
{{
    "sections": [
        {{"name": "sample_size", "title": "9.1 Sample Size", "content": "The sample size was calculated..."}},
        {{"name": "statistical_methods", "title": "9. Statistical Methods", "content": "The primary analysis will use..."}},
        ...
    ]
}}

IMPORTANT:
- Extract the ACTUAL content, not summaries
- Include all details, numbers, methods
- The text is sampled from different parts of the document
- Look for statistical content in all sections, not just the beginning

PROTOCOL TEXT (sampled from multiple regions):
{combined_text[:60000]}
'''

        try:
            if hasattr(self.llm_client, 'chat'):
                response = self.llm_client.chat(prompt, max_tokens=8000)
                response_text = response if isinstance(response, str) else str(response)
            elif hasattr(self.llm_client, 'messages'):
                response = self.llm_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=8000,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = response.content[0].text
            else:
                return {}

            # Parse JSON - robust extraction
            json_text = response_text

            # Try to extract from markdown code block first
            if '```json' in json_text:
                code_start = json_text.find('```json') + 7
                code_end = json_text.find('```', code_start)
                if code_end > code_start:
                    json_text = json_text[code_start:code_end].strip()
            elif '```' in json_text:
                code_start = json_text.find('```') + 3
                code_end = json_text.find('```', code_start)
                if code_end > code_start:
                    json_text = json_text[code_start:code_end].strip()

            # Find JSON object
            start = json_text.find('{')
            end = json_text.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = json_text[start:end]

                # Try parsing
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    # Try fixing common issues: single quotes, trailing commas
                    import re
                    fixed = json_str.replace("'", '"')
                    fixed = re.sub(r',\s*}', '}', fixed)
                    fixed = re.sub(r',\s*]', ']', fixed)
                    data = json.loads(fixed)

                sections = {}
                for s in data.get('sections', []):
                    name = s.get('name', '').lower()
                    if name in self.CANONICAL_SECTIONS:
                        sections[name] = ParsedSection(
                            name=name,
                            title=s.get('title', name),
                            content=s.get('content', ''),
                            confidence=0.7
                        )
                print(f"[SectionParser] Extracted {len(sections)} sections via Claude text")
                return sections

        except Exception as e:
            print(f"[SectionParser] Text extraction error: {e}")

        return {}

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


def parse_protocol(text: str, pdf_path: str = None, llm_client=None) -> ParsedProtocol:
    """Quick protocol parsing"""
    return ProtocolSectionParser(llm_client=llm_client).parse(text, pdf_path=pdf_path)
