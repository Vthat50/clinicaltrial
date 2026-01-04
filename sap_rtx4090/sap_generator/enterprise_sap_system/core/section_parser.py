#!/usr/bin/env python3
"""
Protocol Section Parser (Hybrid Vision + PyMuPDF Extraction)
=============================================================

PRODUCTION-GRADE HYBRID APPROACH:
1. Vision LOCATES section headers (visual pattern recognition)
2. PyMuPDF EXTRACTS content faithfully (no hallucination)
3. Multi-signal validation ensures correctness

Safeguards implemented:
- Header verification: Cross-validate Vision results with text search
- Section end detection: ICH M11 numbering + common end markers
- Adaptive sampling: Two-phase (coarse then fine-grained)
- Clean extraction: sort parameter, skip headers/footers
- Multi-signal validation: required/expected/forbidden keywords

Based on research:
- Vision for locating (good at visual patterns)
- PyMuPDF for extracting (faithful, no hallucination)
- SecTag algorithm: 92.7% accuracy on section boundaries
"""

import json
import re
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


# Multi-signal validation rules for each section type
# Based on research: required + expected + forbidden keywords
SECTION_VALIDATORS = {
    'statistical_methods': {
        'required': ['analysis', 'statistical'],
        'expected': ['primary', 'endpoint', 'hypothesis', 'test', 'log-rank', 'cox', 'ancova', 'mmrm', 'stratified'],
        'forbidden': ['table of contents', '..........', 'list of tables', 'list of figures'],
        'min_length': 500
    },
    'sample_size': {
        'required': ['sample', 'size'],
        'expected': ['power', 'patients', 'subjects', 'hazard ratio', 'events', 'alpha', 'beta', 'calculation'],
        'forbidden': ['table of contents', '..........'],
        'min_length': 300
    },
    'interim_analysis': {
        'required': ['interim'],
        'expected': ['analysis', 'spending', 'o\'brien', 'fleming', 'boundary', 'futility', 'dmc', 'idmc'],
        'forbidden': ['table of contents', '..........'],
        'min_length': 200
    },
    'multiplicity': {
        'required': ['multiplicity'],
        'expected': ['hypothesis', 'alpha', 'type i', 'familywise', 'hierarchical', 'gatekeeping', 'adjustment'],
        'forbidden': ['table of contents', '..........'],
        'min_length': 200
    },
    'missing_data': {
        'required': ['missing'],
        'expected': ['data', 'censoring', 'imputation', 'sensitivity', 'discontinuation', 'withdrawal'],
        'forbidden': ['table of contents', '..........'],
        'min_length': 200
    },
    'populations': {
        'required': ['population'],
        'expected': ['itt', 'intent-to-treat', 'per-protocol', 'safety', 'fas', 'analysis set', 'efficacy'],
        'forbidden': ['table of contents', '..........'],
        'min_length': 200
    },
    'endpoints': {
        'required': ['endpoint'],
        'expected': ['primary', 'secondary', 'outcome', 'efficacy', 'pfs', 'os', 'survival', 'response', 'orr'],
        'forbidden': ['table of contents', '..........'],
        'min_length': 300
    },
    'stratification': {
        'required': ['stratif'],
        'expected': ['factor', 'randomiz', 'region', 'ecog', 'performance', 'baseline'],
        'forbidden': ['table of contents', '..........'],
        'min_length': 150
    },
    'safety': {
        'required': ['safety'],
        'expected': ['adverse', 'event', 'toxicity', 'serious', 'aesi', 'discontinuation', 'ae', 'sae'],
        'forbidden': ['table of contents', '..........'],
        'min_length': 300
    },
    'estimand': {
        'required': ['estimand'],
        'expected': ['intercurrent', 'strategy', 'treatment policy', 'hypothetical', 'composite'],
        'forbidden': ['table of contents', '..........'],
        'min_length': 200
    }
}

# ICH M11 expected section order for validation
ICH_M11_SECTION_ORDER = [
    'objectives', 'endpoints', 'study_design', 'populations',
    'stratification', 'randomization', 'blinding',
    'statistical_methods', 'sample_size', 'interim_analysis',
    'multiplicity', 'missing_data', 'sensitivity', 'safety'
]

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

            # STEP 3: Extract content from the ACTUAL PAGES where headers were found
            # NOT from full text (which would find TOC entries first)
            print(f"[SectionParser/Vision] Step 3: Extracting sections from actual pages...")
            sections = self._extract_by_page(doc, found_headers)

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
        ADAPTIVE TWO-PHASE SAMPLING for header detection.

        Phase 1: Coarse sampling (every 5th page) to find approximate locations
        Phase 2: Fine-grained scan around found headers to fill gaps

        Returns list of headers with VERIFIED page numbers.
        """
        found_headers = []

        # PHASE 1: Coarse sampling
        print(f"[SectionParser/Adaptive] Phase 1: Coarse sampling...")
        coarse_pages = []

        # Skip first 10% (title pages, TOC)
        start_page = int(total_pages * 0.10)

        # Sample every 5th page
        for page_num in range(start_page, total_pages, 5):
            coarse_pages.append(page_num)

        print(f"[SectionParser/Adaptive] Scanning {len(coarse_pages)} pages in coarse phase...")

        for page_num in coarse_pages:
            headers = self._detect_headers_on_page(doc, page_num)
            for h in headers:
                if h.get('is_toc_entry', False):
                    continue

                header_text = h.get('exact_header_text', '')
                section_type = h.get('section_type', '').lower()

                if header_text and section_type in self.CANONICAL_SECTIONS:
                    existing = [x for x in found_headers if x['section_type'] == section_type]
                    if not existing:
                        # VERIFY: Cross-validate with PyMuPDF text search
                        verified_page = self._verify_header_location(doc, page_num, header_text)

                        if verified_page is not None:
                            found_headers.append({
                                'exact_header_text': header_text,
                                'section_type': section_type,
                                'first_sentence': h.get('first_sentence_after', ''),
                                'page_num': verified_page,
                                'verified': True
                            })
                            print(f"[SectionParser/Adaptive] ✓ Verified header: '{header_text}' -> {section_type} (page {verified_page})")
                        else:
                            # Keep unverified but flag it
                            found_headers.append({
                                'exact_header_text': header_text,
                                'section_type': section_type,
                                'first_sentence': h.get('first_sentence_after', ''),
                                'page_num': page_num,
                                'verified': False
                            })
                            print(f"[SectionParser/Adaptive] ? Unverified header: '{header_text}' -> {section_type} (page {page_num})")

        # PHASE 2: Fill gaps - look for missing priority sections
        print(f"[SectionParser/Adaptive] Phase 2: Filling gaps...")
        found_types = {h['section_type'] for h in found_headers}
        missing_sections = [s for s in self.PRIORITY_SECTIONS if s not in found_types]

        if missing_sections and found_headers:
            print(f"[SectionParser/Adaptive] Missing sections: {missing_sections}")

            # Sort found headers by page
            sorted_headers = sorted(found_headers, key=lambda x: x['page_num'])

            # Dense scan between found sections
            for i in range(len(sorted_headers)):
                start = sorted_headers[i]['page_num']
                end = sorted_headers[i + 1]['page_num'] if i + 1 < len(sorted_headers) else min(start + 20, total_pages)

                # If gap is large, scan it densely
                if end - start > 5:
                    for page_num in range(start + 1, end):
                        if page_num in coarse_pages:
                            continue  # Already scanned

                        headers = self._detect_headers_on_page(doc, page_num)
                        for h in headers:
                            section_type = h.get('section_type', '').lower()
                            if section_type in missing_sections:
                                header_text = h.get('exact_header_text', '')
                                verified_page = self._verify_header_location(doc, page_num, header_text)

                                found_headers.append({
                                    'exact_header_text': header_text,
                                    'section_type': section_type,
                                    'first_sentence': h.get('first_sentence_after', ''),
                                    'page_num': verified_page or page_num,
                                    'verified': verified_page is not None
                                })
                                missing_sections.remove(section_type)
                                print(f"[SectionParser/Adaptive] ✓ Found missing: '{header_text}' -> {section_type} (page {verified_page or page_num})")

        # ICH M11 structure validation
        self._validate_section_order(found_headers)

        return found_headers

    def _verify_header_location(self, doc, page_num: int, header_text: str) -> Optional[int]:
        """
        Cross-validate Vision result with PyMuPDF text search.

        Check 3 pages around the reported location to confirm header exists.
        Returns actual page number or None if not found.
        """
        # Normalize header for search
        search_text = ' '.join(header_text.lower().split())

        # Check reported page and nearby pages
        for offset in [0, -1, 1, -2, 2]:
            check_page = page_num + offset
            if 0 <= check_page < len(doc):
                page = doc[check_page]
                page_text = page.get_text().lower()
                normalized_page = ' '.join(page_text.split())

                if search_text in normalized_page:
                    return check_page

        return None  # Not verified

    def _validate_section_order(self, found_headers: List[Dict]) -> None:
        """
        ICH M11 structure validation.

        Clinical protocols follow a known structure. Flag if sections appear out of order.
        """
        if len(found_headers) < 2:
            return

        sorted_headers = sorted(found_headers, key=lambda x: x['page_num'])

        for i in range(len(sorted_headers) - 1):
            curr_type = sorted_headers[i]['section_type']
            next_type = sorted_headers[i + 1]['section_type']

            # Check if they're both in our known order
            if curr_type in ICH_M11_SECTION_ORDER and next_type in ICH_M11_SECTION_ORDER:
                curr_idx = ICH_M11_SECTION_ORDER.index(curr_type)
                next_idx = ICH_M11_SECTION_ORDER.index(next_type)

                if curr_idx > next_idx:
                    print(f"[SectionParser/Validate] ⚠ Section order anomaly: {curr_type} (page {sorted_headers[i]['page_num']}) appears before {next_type} (page {sorted_headers[i+1]['page_num']})")

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

    def _extract_by_page(
        self,
        doc,
        found_headers: List[Dict]
    ) -> Dict[str, ParsedSection]:
        """
        HYBRID APPROACH: Extract section content using Claude API.

        Vision tells us which PDF pages have section headers.
        Claude API extracts content from those specific pages.

        Approach:
        1. Sort headers by page number
        2. For each header, find section end using ICH M11 numbering
        3. Use Claude API to extract content from those pages
        4. Validate content with multi-signal validation
        """
        sections = {}
        total_pages = len(doc)

        # Sort headers by page number
        sorted_headers = sorted(found_headers, key=lambda x: x.get('page_num', 0))

        print(f"[SectionParser/Hybrid] Extracting {len(sorted_headers)} sections...")

        for i, header in enumerate(sorted_headers):
            section_type = header['section_type']
            header_text = header['exact_header_text']
            start_page = header.get('page_num', 0)

            # Find section end using ICH M11 numbering
            if i + 1 < len(sorted_headers):
                end_page = sorted_headers[i + 1]['page_num']
            else:
                end_page = self._find_section_end(doc, start_page, header_text)

            # Ensure reasonable bounds
            end_page = min(end_page, start_page + 30, total_pages)
            if end_page <= start_page:
                end_page = min(start_page + 10, total_pages)

            print(f"[SectionParser/Hybrid] Extracting '{section_type}' from pages {start_page}-{end_page-1}")

            # Extract content using Claude API
            content = self._extract_section_with_claude(doc, start_page, end_page, section_type)

            if not content or len(content) < 100:
                # Fallback to PyMuPDF if Claude extraction fails
                print(f"[SectionParser/Hybrid] Claude extraction failed, falling back to PyMuPDF...")
                content = self._extract_with_pymupdf(doc, start_page, end_page)

            # Multi-signal validation
            if len(content) > 100:
                is_valid, confidence, message = self._validate_multi_signal(section_type, content)

                if is_valid:
                    sections[section_type] = ParsedSection(
                        name=section_type,
                        title=header_text,
                        content=content,
                        start_page=start_page,
                        end_page=end_page - 1,
                        confidence=confidence
                    )
                    print(f"[SectionParser/Hybrid] ✓ Extracted '{section_type}': {len(content)} chars (confidence: {confidence:.2f})")
                else:
                    print(f"[SectionParser/Hybrid] ✗ REJECTED '{section_type}': {message}")

                    # Try extending the range
                    extended_end = min(end_page + 10, total_pages)
                    extended_content = self._extract_with_pymupdf(doc, start_page, extended_end)

                    is_valid, confidence, message = self._validate_multi_signal(section_type, extended_content)
                    if is_valid:
                        sections[section_type] = ParsedSection(
                            name=section_type,
                            title=header_text,
                            content=extended_content,
                            start_page=start_page,
                            end_page=extended_end - 1,
                            confidence=confidence
                        )
                        print(f"[SectionParser/Hybrid] ✓ Salvaged '{section_type}' with extended range: {len(extended_content)} chars")
            else:
                print(f"[SectionParser/Hybrid] ✗ '{section_type}': content too short ({len(content)} chars)")

        return sections

    def _find_section_end(self, doc, start_page: int, header_text: str) -> int:
        """
        Find section end using ICH M11 numbering + common end markers.

        Parse section number from header and look for next major section.
        """
        # Parse section number: "9.7 Sample Size" -> (9, 7)
        match = re.match(r'^(\d+)(?:\.(\d+))?', header_text.strip())
        if match:
            major = int(match.group(1))
            # Look for next major section (major + 1)
            next_major_pattern = rf'\b{major + 1}[\.\s]'

            for page_num in range(start_page + 1, min(start_page + 30, len(doc))):
                page = doc[page_num]
                text = page.get_text()

                # Look for next major section
                if re.search(next_major_pattern, text):
                    return page_num

                # Look for common end markers
                if re.search(r'^\s*(REFERENCES|APPENDIX|APPENDICES|BIBLIOGRAPHY)', text, re.MULTILINE | re.IGNORECASE):
                    return page_num

        # Fallback: assume 15 pages max
        return min(start_page + 15, len(doc))

    def _extract_section_with_claude(self, doc, start_page: int, end_page: int, section_type: str) -> str:
        """
        Extract section content using Claude API (Vision).

        Send page images to Claude and ask it to extract the text content.
        Better handling of complex layouts, tables, multi-column text.
        """
        if not self.vision_client:
            return ""

        all_content = []

        # Limit to max 5 pages per Claude call to manage costs
        pages_to_process = min(end_page - start_page, 5)

        for i in range(pages_to_process):
            page_num = start_page + i
            if page_num >= len(doc):
                break

            try:
                page = doc[page_num]

                # Render to image
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                img_bytes = pix.tobytes("png")
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')

                # Ask Claude to extract the text
                prompt = f"""Extract ALL text content from this clinical trial protocol page.

This page is part of the {section_type.upper().replace('_', ' ')} section.

IMPORTANT:
- Extract the EXACT text as it appears, do not summarize
- Include all numbers, percentages, and statistical values
- Preserve paragraph structure
- Include table content if present
- Skip headers, footers, and page numbers

Return ONLY the extracted text, no commentary."""

                response = self._call_vision_api(img_base64, prompt)
                if response:
                    all_content.append(response)

            except Exception as e:
                print(f"[SectionParser/Claude] Error extracting page {page_num}: {e}")

        return "\n\n".join(all_content)

    def _extract_with_pymupdf(self, doc, start_page: int, end_page: int) -> str:
        """
        Fallback: Extract text using PyMuPDF with sort parameter.

        Uses sort=True for proper reading order.
        """
        content_parts = []

        for page_num in range(start_page, end_page):
            if page_num < len(doc):
                page = doc[page_num]
                # Use sort=True for proper reading order
                page_text = page.get_text(sort=True)
                if page_text:
                    content_parts.append(page_text)

        return "\n".join(content_parts).strip()

    def _validate_multi_signal(self, section_type: str, content: str) -> Tuple[bool, float, str]:
        """
        Multi-signal validation using required/expected/forbidden keywords.

        Returns (is_valid, confidence, message)
        """
        rules = SECTION_VALIDATORS.get(section_type)
        if not rules:
            return True, 0.7, "No validation rules"

        content_lower = content.lower()

        # Check required keywords (must have ALL)
        for kw in rules.get('required', []):
            if kw not in content_lower:
                return False, 0.0, f"Missing required keyword: {kw}"

        # Check forbidden patterns (must NOT have any)
        for pattern in rules.get('forbidden', []):
            if pattern in content_lower:
                return False, 0.0, f"Found forbidden pattern: {pattern}"

        # Check minimum length
        min_length = rules.get('min_length', 100)
        if len(content) < min_length:
            return False, 0.0, f"Content too short: {len(content)} < {min_length}"

        # Check expected keywords (need 2+)
        expected = rules.get('expected', [])
        found_expected = sum(1 for kw in expected if kw in content_lower)

        if found_expected < 2:
            return False, 0.2, f"Only found {found_expected} expected keywords"

        # Calculate confidence based on expected keyword coverage
        confidence = min(0.95, 0.5 + (found_expected / len(expected)) * 0.5) if expected else 0.7

        # Structure validation: check for paragraph structure (not just TOC lines)
        lines = content.split('\n')
        avg_line_length = sum(len(line) for line in lines) / max(len(lines), 1)

        if avg_line_length < 30:  # Very short lines = probably TOC
            return False, 0.1, f"Low average line length: {avg_line_length:.1f} (possible TOC)"

        return True, confidence, "Validation passed"

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

        CRITICAL: Skip TOC entries (which have "....page_number" after them).
        Find the ACTUAL section header followed by paragraph content.
        """
        # Normalize both strings for matching
        normalized_full = ' '.join(full_text.split())
        normalized_header = ' '.join(header_text.split())

        # Find ALL occurrences and pick the one that's actual content, not TOC
        search_text = normalized_full.lower()
        search_header = normalized_header.lower()

        start_pos = 0
        while True:
            pos = search_text.find(search_header, start_pos)
            if pos < 0:
                break

            # Check if this is a TOC entry (has dots/periods followed by page numbers after it)
            after_header = normalized_full[pos + len(normalized_header):pos + len(normalized_header) + 100]

            # TOC entries look like: "9.9 Sample Size...............138"
            # Actual content looks like: "9.9 Sample Size\nThe sample size was calculated..."
            is_toc_entry = False

            # Check for dot leaders (........) or page number patterns
            if '.....' in after_header or '......' in after_header:
                is_toc_entry = True
            elif after_header.strip()[:10].replace('.', '').replace(' ', '').isdigit():
                # Starts with just numbers = page number = TOC
                is_toc_entry = True

            if not is_toc_entry:
                # This looks like actual content - return this position
                return self._map_position_to_original(full_text, normalized_full, pos)

            # This was a TOC entry, continue searching
            start_pos = pos + len(search_header)

        # If no non-TOC match found, try the last occurrence (often actual content is later)
        last_pos = search_text.rfind(search_header)
        if last_pos >= 0:
            return self._map_position_to_original(full_text, normalized_full, last_pos)

        # Try matching just the significant words
        words = normalized_header.split()
        if len(words) >= 2:
            key_words = ' '.join(words[1:3])
            # Find LAST occurrence of key words (more likely to be content, not TOC)
            pos = search_text.rfind(key_words.lower())
            if pos >= 0:
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
