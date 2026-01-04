#!/usr/bin/env python3
"""
Protocol Section Parser (Vision-based Content Extraction)
==========================================================

PRODUCTION-GRADE APPROACH:
1. Extract FULL TEXT from PDF (not page-by-page)
2. Use Vision to identify section headers VISUALLY (font size, formatting)
3. Vision returns the EXACT TEXT of headers (not page numbers)
4. Search full text for header text, extract until next header
5. Validate content semantically

NO REGEX. NO PAGE NUMBERS. Content-based extraction only.

Based on research:
- ColPali/VLMs: Process pages as images, understand structure visually
- Nutrient AI: "ML models recognize sections by context, not position"
- Key insight: Page numbers are unreliable, use header text instead
"""

import json
import base64
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# PyMuPDF for PDF processing
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
    print(f"[SectionParser] PyMuPDF available: version {fitz.version}")
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


# Vision prompt to identify section headers VISUALLY
# Returns the EXACT TEXT of headers, NOT page numbers
VISION_HEADER_DETECTION_PROMPT = '''Analyze this clinical trial protocol page VISUALLY.

Your task: Identify any SECTION HEADERS on this page by their visual formatting:
- Headers are typically LARGER FONT or BOLD
- They often have section numbers like "9", "9.1", "9.2.1"
- They start a new topic/section

For each header you see, extract the EXACT TEXT as it appears.

IMPORTANT: I need the EXACT HEADER TEXT, not page numbers.

RESPOND IN JSON:
{
    "has_section_headers": true/false,
    "section_headers": [
        {
            "exact_header_text": "9 STATISTICAL CONSIDERATIONS",
            "section_type": "STATISTICAL_METHODS",
            "is_main_section": true,
            "first_sentence_after": "The primary analysis will..."
        },
        {
            "exact_header_text": "9.1 Sample Size and Power Calculation",
            "section_type": "SAMPLE_SIZE",
            "is_main_section": false,
            "first_sentence_after": "A total of 500 patients..."
        }
    ],
    "is_toc_page": true/false,
    "is_appendix": true/false
}

Section types:
- STATISTICAL_METHODS (Section 9 or 10 typically)
- SAMPLE_SIZE
- POPULATIONS
- INTERIM_ANALYSIS
- MULTIPLICITY
- MISSING_DATA
- ENDPOINTS
- STRATIFICATION
- SAFETY
- ESTIMAND

CRITICAL: Extract the EXACT header text including section numbers, spacing, and capitalization.
'''

# Prompt to extract specific section content from a page
VISION_SECTION_CONTENT_PROMPT = '''Read this page from a clinical trial protocol.

I need you to extract the FULL TEXT CONTENT related to: {section_type}

If this page contains content for {section_type}, extract:
1. The section header (if visible)
2. ALL the paragraph text that follows
3. Any tables, lists, or figures descriptions

RESPOND IN JSON:
{{
    "found_section": true/false,
    "section_header": "<exact header text if visible>",
    "content": "<all the text content from this section>",
    "continues_on_next_page": true/false,
    "section_appears_complete": true/false
}}

Extract the ACTUAL TEXT, not a summary. Include numbers, methods, and all details.
'''


class ProtocolSectionParser:
    """
    Parse clinical protocol into logical sections using Vision-based content extraction.

    PRODUCTION-GRADE APPROACH:
    1. Extract FULL TEXT from PDF (not page-by-page)
    2. Vision scans pages to identify section headers VISUALLY
    3. Vision returns EXACT HEADER TEXT (not page numbers)
    4. Search full text for header, extract until next header
    5. Validate content semantically

    NO REGEX. NO PAGE NUMBERS. Content-based extraction only.
    """

    CANONICAL_SECTIONS = [
        "objectives", "endpoints", "study_design", "statistical_methods",
        "sample_size", "populations", "interim_analysis", "multiplicity",
        "missing_data", "safety", "efficacy", "estimand", "stratification",
        "randomization", "blinding", "subgroups", "sensitivity"
    ]

    # Priority sections to find (in order of importance)
    PRIORITY_SECTIONS = [
        "statistical_methods", "sample_size", "interim_analysis",
        "multiplicity", "endpoints", "populations", "missing_data",
        "stratification", "safety"
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
        self._full_text_cache: Dict[str, str] = {}

    def parse(self, text: str, pdf_path: Optional[str] = None) -> ParsedProtocol:
        """
        Parse protocol using Vision-based content extraction.

        APPROACH:
        1. Extract full PDF text
        2. Vision identifies section headers visually
        3. Extract content from header to next header (text search, not page numbers)

        Args:
            text: Full protocol text (can be empty if pdf_path provided)
            pdf_path: Path to PDF file

        Returns:
            ParsedProtocol with identified sections
        """
        result = ParsedProtocol(raw_text=text)

        print(f"[SectionParser] parse() called: pdf_path={pdf_path}, PYMUPDF_AVAILABLE={PYMUPDF_AVAILABLE}")

        # Vision-based extraction from PDF
        if pdf_path and PYMUPDF_AVAILABLE and self.vision_client:
            print("[SectionParser] Using Vision-based content extraction...")
            sections = self._extract_with_vision(pdf_path)

            if sections:
                result.sections = sections
                result.parse_success = True
                result.section_count = len(sections)
                # Store full text for later use
                result.raw_text = self._full_text_cache.get(pdf_path, text)
                print(f"[SectionParser] Extracted {len(sections)} sections: {list(sections.keys())}")
                return result
            else:
                print("[SectionParser] Vision extraction returned no sections, trying text fallback")

        # Fallback: text-based extraction
        if text and len(text) > 100 and self.llm_client:
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
            content=text or self._full_text_cache.get(pdf_path, ""),
            confidence=0.3
        )
        result.parse_success = True
        result.section_count = 1
        return result

    def _extract_with_vision(self, pdf_path: str) -> Dict[str, ParsedSection]:
        """
        PRODUCTION-GRADE EXTRACTION:
        1. Extract FULL TEXT from PDF
        2. Vision scans pages to identify section headers VISUALLY
        3. Search full text for header, extract until next header

        NO PAGE NUMBERS used for extraction - only header text.
        """
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            print(f"[SectionParser/Vision] PDF has {total_pages} pages")

            # STEP 1: Extract FULL TEXT from PDF
            print(f"[SectionParser/Vision] Step 1: Extracting full text...")
            full_text = self._extract_full_text(doc)
            self._full_text_cache[pdf_path] = full_text
            print(f"[SectionParser/Vision] Full text: {len(full_text)} characters")

            # STEP 2: Scan pages to find section headers (returns HEADER TEXT, not page numbers)
            print(f"[SectionParser/Vision] Step 2: Scanning for section headers...")
            found_headers = self._scan_for_headers(doc, total_pages)
            print(f"[SectionParser/Vision] Found {len(found_headers)} section headers")

            if not found_headers:
                doc.close()
                return {}

            # STEP 3: Extract content from header to next header (text search)
            print(f"[SectionParser/Vision] Step 3: Extracting sections by header text...")
            sections = self._extract_by_headers(full_text, found_headers)

            doc.close()
            return sections

        except Exception as e:
            print(f"[SectionParser/Vision] Error: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _extract_full_text(self, doc) -> str:
        """Extract complete text from PDF."""
        text_parts = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text:
                text_parts.append(text)
        return "\n".join(text_parts)

    def _scan_for_headers(self, doc, total_pages: int) -> List[Dict]:
        """
        Scan PDF pages to identify section headers VISUALLY.

        Returns list of headers with their EXACT TEXT:
        [
            {"exact_header_text": "9 STATISTICAL CONSIDERATIONS", "section_type": "statistical_methods"},
            {"exact_header_text": "9.1 Sample Size", "section_type": "sample_size"},
            ...
        ]

        Does NOT return page numbers - we use header text for extraction.
        """
        found_headers = []

        # Strategic scanning: focus on 60-95% where statistical sections are
        # Scan every 3rd page for efficiency
        scan_pages = []

        # Early pages (for study design, endpoints)
        scan_pages.extend([int(total_pages * 0.15), int(total_pages * 0.25)])

        # Statistical section region (60-95%)
        for frac in [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
            page = int(total_pages * frac)
            if page < total_pages and page not in scan_pages:
                scan_pages.append(page)

        print(f"[SectionParser/Vision] Scanning {len(scan_pages)} pages for headers...")

        for page_num in scan_pages:
            if page_num >= total_pages:
                continue

            headers = self._detect_headers_on_page(doc, page_num)
            for h in headers:
                # Skip TOC entries
                if h.get('is_toc_entry', False):
                    continue

                header_text = h.get('exact_header_text', '')
                section_type = h.get('section_type', '').lower()

                if header_text and section_type in self.CANONICAL_SECTIONS:
                    # Check if we already have this section
                    existing = [x for x in found_headers if x['section_type'] == section_type]
                    if not existing:
                        found_headers.append({
                            'exact_header_text': header_text,
                            'section_type': section_type,
                            'first_sentence': h.get('first_sentence_after', '')
                        })
                        print(f"[SectionParser/Vision] Found header: '{header_text}' -> {section_type}")

        return found_headers

    def _detect_headers_on_page(self, doc, page_num: int) -> List[Dict]:
        """Use Vision to detect section headers on a page."""
        try:
            page = doc[page_num]

            # Render to image (1.5x zoom for readability)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img_bytes = pix.tobytes("png")
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')

            # Call Claude Vision
            response = self._call_vision_api(img_base64, VISION_HEADER_DETECTION_PROMPT)

            if not response:
                return []

            # Parse JSON response
            data = self._parse_json_response(response)
            if data:
                # Skip TOC pages
                if data.get('is_toc_page', False):
                    return []

                return data.get('section_headers', [])

            return []

        except Exception as e:
            print(f"[SectionParser/Vision] Error detecting headers on page {page_num}: {e}")
            return []

    def _extract_by_headers(
        self,
        full_text: str,
        found_headers: List[Dict]
    ) -> Dict[str, ParsedSection]:
        """
        Extract section content using header text (NOT page numbers).

        Approach:
        1. For each header, find its position in full text
        2. Extract from that position until next header
        3. Validate content semantically
        """
        sections = {}

        # Sort headers by their position in text
        headers_with_pos = []
        for h in found_headers:
            header_text = h['exact_header_text']
            pos = self._find_header_in_text(full_text, header_text)
            if pos >= 0:
                headers_with_pos.append({
                    **h,
                    'position': pos
                })
                print(f"[SectionParser/Vision] Header '{header_text}' found at position {pos}")
            else:
                print(f"[SectionParser/Vision] WARNING: Header '{header_text}' not found in text!")

        # Sort by position
        headers_with_pos.sort(key=lambda x: x['position'])

        # Extract content between headers
        for i, h in enumerate(headers_with_pos):
            section_type = h['section_type']
            start_pos = h['position']

            # End position is start of next header, or +50000 chars, or end of text
            if i + 1 < len(headers_with_pos):
                end_pos = headers_with_pos[i + 1]['position']
            else:
                end_pos = min(start_pos + 50000, len(full_text))

            content = full_text[start_pos:end_pos].strip()

            # Semantic validation: verify content matches expected section type
            if len(content) > 100:
                confidence = self._validate_content_semantically(section_type, content)

                if confidence >= 0.5:  # Accept if reasonably valid
                    sections[section_type] = ParsedSection(
                        name=section_type,
                        title=h['exact_header_text'],
                        content=content,
                        confidence=confidence
                    )
                    print(f"[SectionParser/Vision] Extracted '{section_type}': {len(content)} chars (confidence: {confidence:.2f})")
                else:
                    print(f"[SectionParser/Vision] REJECTED '{section_type}': failed semantic validation (confidence: {confidence:.2f})")

        return sections

    def _validate_content_semantically(self, section_type: str, content: str) -> float:
        """
        Validate that extracted content matches expected section type.

        Uses keyword presence to estimate confidence. No regex - just substring checks.
        Returns confidence score 0.0-1.0
        """
        content_lower = content.lower()

        # Define expected keywords for each section type
        validation_keywords = {
            'statistical_methods': ['analysis', 'statistical', 'test', 'hypothesis', 'log-rank', 'cox', 'stratified'],
            'sample_size': ['sample size', 'patients', 'power', 'hazard ratio', 'events', 'enrolled', 'subjects'],
            'interim_analysis': ['interim', 'analysis', 'spending', 'o\'brien', 'fleming', 'boundary', 'futility'],
            'multiplicity': ['multiplicity', 'hypothesis', 'alpha', 'type i', 'familywise', 'hierarchical', 'gatekeeping'],
            'missing_data': ['missing', 'censoring', 'imputation', 'sensitivity', 'discontinuation'],
            'populations': ['population', 'itt', 'intent-to-treat', 'per-protocol', 'safety', 'fas', 'analysis set'],
            'endpoints': ['endpoint', 'primary', 'secondary', 'outcome', 'efficacy', 'pfs', 'survival', 'response'],
            'stratification': ['stratif', 'factor', 'randomiz', 'region', 'ecog', 'performance status'],
            'safety': ['safety', 'adverse', 'event', 'toxicity', 'serious', 'aesi', 'discontinuation'],
            'estimand': ['estimand', 'intercurrent', 'strategy', 'treatment policy', 'hypothetical']
        }

        keywords = validation_keywords.get(section_type, [])
        if not keywords:
            return 0.7  # Unknown section type, moderate confidence

        # Count matching keywords
        matches = sum(1 for kw in keywords if kw in content_lower)
        keyword_ratio = matches / len(keywords) if keywords else 0

        # Base confidence on keyword matches
        # At least 2 matches or 30% of keywords should match
        if matches >= 2 or keyword_ratio >= 0.3:
            confidence = min(0.9, 0.5 + (keyword_ratio * 0.5))
        else:
            confidence = keyword_ratio * 0.5

        return confidence

    def _find_header_in_text(self, full_text: str, header_text: str) -> int:
        """
        Find header text position in full text using semantic matching.
        Handles variations in whitespace, line breaks, etc.
        """
        # Normalize both strings for matching
        normalized_full = ' '.join(full_text.split())
        normalized_header = ' '.join(header_text.split())

        # Try exact match first
        pos = normalized_full.find(normalized_header)
        if pos >= 0:
            # Convert back to original text position (approximate)
            return self._map_position_to_original(full_text, normalized_full, pos)

        # Try case-insensitive match
        pos = normalized_full.lower().find(normalized_header.lower())
        if pos >= 0:
            return self._map_position_to_original(full_text, normalized_full, pos)

        # Try matching just the significant words (for headers with varied formatting)
        # E.g., "9 STATISTICAL CONSIDERATIONS" might appear as "9. Statistical Considerations"
        words = normalized_header.split()
        if len(words) >= 2:
            # Search for key words together
            key_words = ' '.join(words[1:3])  # Skip section number, get first 2 words
            pos = normalized_full.lower().find(key_words.lower())
            if pos >= 0:
                # Back up to find section number
                search_start = max(0, pos - 20)
                return self._map_position_to_original(full_text, normalized_full, search_start)

        return -1

    def _map_position_to_original(self, original: str, normalized: str, norm_pos: int) -> int:
        """Map position from normalized text back to original text."""
        # Simple approximation: count characters
        char_count = 0
        orig_pos = 0

        normalized_chars = normalized[:norm_pos]
        target_count = len(normalized_chars)

        for i, c in enumerate(original):
            if not c.isspace() or (i > 0 and not original[i-1].isspace()):
                char_count += 1
            if char_count >= target_count:
                return i

        return max(0, len(original) - 1000)  # Fallback to near end

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

    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """Parse JSON from Vision API response."""
        try:
            # Handle markdown code blocks
            if '```json' in response:
                start = response.find('```json') + 7
                end = response.find('```', start)
                if end > start:
                    response = response[start:end].strip()
            elif '```' in response:
                start = response.find('```') + 3
                end = response.find('```', start)
                if end > start:
                    response = response[start:end].strip()

            # Find JSON object
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)

            return None

        except json.JSONDecodeError as e:
            print(f"[SectionParser/Vision] JSON parse error: {e}")
            return None

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
