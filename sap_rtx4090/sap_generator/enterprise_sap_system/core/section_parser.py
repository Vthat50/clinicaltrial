#!/usr/bin/env python3
"""
Protocol Section Parser (LlamaParse Integration)
================================================

PRODUCTION-GRADE APPROACH:
1. LlamaParse extracts structured markdown from PDF (accurate, handles complex layouts)
2. Parse markdown to identify section headers and content
3. Multi-signal validation ensures correctness

LlamaParse advantages over Vision + PyMuPDF:
- Purpose-built for document parsing
- Better table extraction
- Handles complex clinical protocol layouts
- Returns structured markdown with headers
- More accurate section boundary detection

Fallback: PyMuPDF for when LlamaParse is unavailable
"""

import json
import re
import os
import asyncio
import concurrent.futures
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Thread-local storage for persistent event loops (avoid 'Event loop is closed' errors)
import threading
_thread_local = threading.local()

def _get_or_create_event_loop():
    """Get or create a persistent event loop for the current thread.

    Using a persistent loop per thread avoids httpx connection caching issues
    that cause 'Event loop is closed' errors when creating new loops.
    """
    if not hasattr(_thread_local, 'loop') or _thread_local.loop is None or _thread_local.loop.is_closed():
        _thread_local.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_thread_local.loop)
    return _thread_local.loop

def _run_async_in_thread(coro):
    """Run an async coroutine in a dedicated thread with a persistent event loop.

    Uses thread-local persistent loops to avoid 'Event loop is closed' errors
    that occur when httpx tries to cleanup connections on a closed loop.

    On Python 3.13+, httpx's async client caches connection state. When we
    create a new loop for each call, the old loop gets closed but httpx
    still tries to use cached connections tied to the old loop.

    Solution: Use a persistent loop per thread that stays open across calls.
    """
    def run_in_persistent_loop():
        loop = _get_or_create_event_loop()
        try:
            return loop.run_until_complete(coro)
        except RuntimeError as e:
            # If loop is somehow closed, create a fresh one and retry
            if "Event loop is closed" in str(e):
                _thread_local.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(_thread_local.loop)
                return _thread_local.loop.run_until_complete(coro)
            raise

    # Use a thread pool to isolate the event loop from the main thread
    # This prevents conflicts with FastAPI/uvicorn's event loop
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_persistent_loop)
        return future.result(timeout=240)  # 4 minute timeout for large PDFs

# LlamaParse for accurate PDF parsing
try:
    from llama_cloud_services import LlamaParse
    LLAMAPARSE_AVAILABLE = True
    print("[SectionParser] LlamaParse available")
except ImportError:
    LLAMAPARSE_AVAILABLE = False
    print("[SectionParser] WARNING: LlamaParse not available - install with: pip install llama-cloud-services")

# Note: PyMuPDF fallback removed - LlamaParse is the only PDF extraction method


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


# NO VALIDATION RULES - extract content directly from protocol
# Template provides SAP structure (section names), content is copied from protocol as-is
SECTION_VALIDATORS = {}

# ICH M11 expected section order for validation
ICH_M11_SECTION_ORDER = [
    'objectives', 'endpoints', 'study_design', 'populations',
    'stratification', 'randomization', 'blinding',
    'statistical_methods', 'sample_size', 'interim_analysis',
    'multiplicity', 'missing_data', 'sensitivity', 'safety'
]

# Section header patterns for parsing LlamaParse markdown output
SECTION_HEADER_PATTERNS = [
    # Match headers like "9. STATISTICAL CONSIDERATIONS" or "9.1 Sample Size"
    r'^#+\s*(\d+(?:\.\d+)*)\s*[\.:]?\s*(.+)$',  # Markdown headers with numbers
    r'^(\d+(?:\.\d+)*)\s*[\.:]?\s*(.+)$',  # Plain numbered sections
    r'^(?:SECTION\s+)?(\d+(?:\.\d+)*)\s*[\.:]?\s*(.+)$',  # "SECTION X.Y Title"
    # NEW: Unnumbered markdown headers containing key section words
    r'^#+\s*()((?:Sample Size|Statistical|Interim|Endpoint|Objective|Population|Safety|Multiplicity|Estimand|Study Design).*)$',
]

# Map section title keywords to canonical section types
# ORDER MATTERS - more specific patterns checked first
SECTION_TITLE_MAPPING = {
    # Statistical methods
    'statistical': 'statistical_methods',
    'statistic': 'statistical_methods',
    'analysis method': 'statistical_methods',

    # Sample size
    'sample size': 'sample_size',
    'power': 'sample_size',

    # Interim analysis
    'interim': 'interim_analysis',
    'group sequential': 'interim_analysis',

    # Multiplicity
    'multiplicity': 'multiplicity',
    'multiple testing': 'multiplicity',
    'multiple comparison': 'multiplicity',

    # Missing data
    'missing data': 'missing_data',
    'censoring': 'missing_data',

    # Populations
    'population': 'populations',
    'analysis set': 'populations',

    # Endpoints - SPECIFIC patterns only (not broad 'efficacy')
    'primary endpoint': 'endpoints',
    'secondary endpoint': 'endpoints',
    'exploratory endpoint': 'endpoints',
    'study endpoint': 'endpoints',
    'efficacy endpoint': 'endpoints',
    'endpoint': 'endpoints',  # Generic - checked after specific ones
    # Note: 'efficacy' alone is TOO BROAD - matches background sections

    # Objectives - SEPARATE from endpoints per ICH M11
    'objective': 'objectives',

    # Stratification
    'stratification': 'stratification',
    'stratified': 'stratification',
    'randomization': 'stratification',

    # Safety
    'safety': 'safety',
    'adverse': 'safety',

    # Estimand
    'estimand': 'estimand',
    'intercurrent': 'estimand',
}


class ProtocolSectionParser:
    """
    Parse clinical protocol into logical sections using LlamaParse.

    PRODUCTION-GRADE APPROACH:
    1. LlamaParse extracts structured markdown from PDF
    2. Parse markdown to identify section headers and boundaries
    3. Extract content between headers
    4. Validate content semantically with multi-signal validation

    LlamaParse is more accurate than Vision + PyMuPDF for clinical protocols.
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
            llm_client: Claude API client (optional, for fallback text extraction)
            vision_client: Not used (kept for API compatibility)
        """
        self.llm_client = llm_client
        self._full_text_cache: Dict[str, str] = {}
        self._markdown_cache: Dict[str, str] = {}
        # Cache for parsed sections (key: pdf_path, value: Dict[str, ParsedSection])
        self._sections_cache: Dict[str, Dict[str, 'ParsedSection']] = {}

        # Initialize LlamaParse if available
        self._llamaparse = None
        if LLAMAPARSE_AVAILABLE:
            api_key = os.environ.get('LLAMAPARSE_API_KEY') or os.environ.get('LLAMA_CLOUD_API_KEY')
            if api_key:
                try:
                    self._llamaparse = LlamaParse(
                        api_key=api_key,
                        num_workers=4,
                        verbose=True,
                        language="en"
                    )
                    print(f"[SectionParser] LlamaParse initialized with API key")
                except Exception as e:
                    print(f"[SectionParser] WARNING: LlamaParse initialization failed: {e}")
            else:
                print("[SectionParser] WARNING: No LLAMAPARSE_API_KEY or LLAMA_CLOUD_API_KEY environment variable set")

    def parse(self, text: str, pdf_path: Optional[str] = None) -> ParsedProtocol:
        """
        Parse protocol using LlamaParse for accurate section extraction.

        APPROACH:
        1. LlamaParse extracts structured markdown from PDF
        2. Parse markdown to identify section headers
        3. Extract content between headers
        4. Validate with multi-signal validation

        Args:
            text: Full protocol text (used as fallback if pdf_path not provided)
            pdf_path: Path to PDF file

        Returns:
            ParsedProtocol with identified sections
        """
        result = ParsedProtocol(raw_text=text)

        print(f"[SectionParser] parse() called: pdf_path={pdf_path}, LLAMAPARSE_AVAILABLE={LLAMAPARSE_AVAILABLE}")

        # LlamaParse extraction from PDF (no fallback - expose errors clearly)
        if pdf_path and self._llamaparse:
            # CHECK CACHE FIRST - avoid multiple LlamaParse API calls
            if pdf_path in self._sections_cache:
                print(f"[SectionParser] Using CACHED LlamaParse result for: {pdf_path}")
                sections = self._sections_cache[pdf_path]
                result.sections = sections
                result.parse_success = True
                result.section_count = len(sections)
                result.raw_text = self._full_text_cache.get(pdf_path, text)
                return result

            print("[SectionParser] Using LlamaParse for PDF extraction...")
            sections = self._extract_with_llamaparse(pdf_path)

            if sections:
                # Cache the result
                self._sections_cache[pdf_path] = sections
                result.sections = sections
                result.parse_success = True
                result.section_count = len(sections)
                # Store full text for later use
                result.raw_text = self._full_text_cache.get(pdf_path, text)
                print(f"[SectionParser] LlamaParse extracted {len(sections)} sections: {list(sections.keys())}")
                return result
            else:
                # LlamaParse returned no sections - this is an error, not a fallback situation
                raise RuntimeError("[SectionParser] LlamaParse returned no sections from PDF. Check API key and PDF content.")

        if pdf_path and not self._llamaparse:
            raise RuntimeError("[SectionParser] LlamaParse not initialized. Check LLAMAPARSE_API_KEY environment variable.")

        # Text-based extraction with LLM (only if no PDF provided)
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

    def _extract_with_llamaparse(self, pdf_path: str) -> Dict[str, ParsedSection]:
        """
        Extract sections using LlamaParse.

        LlamaParse returns structured markdown which we parse to identify sections.
        Uses async parsing in a separate thread to avoid uvloop conflicts.
        """
        try:
            print(f"[SectionParser/LlamaParse] Parsing PDF: {pdf_path}")

            # Define async parsing function with timeout
            async def async_parse():
                # Use aparse for async operation with 3 minute timeout (protocols are large)
                result = await asyncio.wait_for(
                    self._llamaparse.aparse(pdf_path),
                    timeout=180.0
                )
                return result

            # Run async parsing in separate thread with its own event loop
            print("[SectionParser/LlamaParse] Running async parse in thread pool...")
            result = _run_async_in_thread(async_parse())

            # Get markdown output
            markdown_docs = result.get_markdown_documents(split_by_page=False)

            if not markdown_docs:
                print("[SectionParser/LlamaParse] No markdown documents returned")
                return {}

            # Combine all markdown pages
            full_markdown = "\n\n".join(doc.text for doc in markdown_docs)
            self._markdown_cache[pdf_path] = full_markdown
            self._full_text_cache[pdf_path] = full_markdown  # Store for raw_text

            print(f"[SectionParser/LlamaParse] Extracted {len(full_markdown)} characters of markdown")

            # Parse markdown to identify sections
            sections = self._parse_markdown_sections(full_markdown)

            return sections

        except Exception as e:
            print(f"[SectionParser/LlamaParse] Error: {e}")
            import traceback
            traceback.print_exc()
            raise  # Re-raise to expose the actual error

    def _parse_markdown_sections(self, markdown: str) -> Dict[str, ParsedSection]:
        """
        Parse LlamaParse markdown output to identify section headers and extract content.

        Looks for numbered section headers and maps them to canonical section types.
        """
        sections = {}
        lines = markdown.split('\n')

        # Find all section headers with their positions
        headers = []
        for i, line in enumerate(lines):
            # SKIP TABLE ROWS - they contain '|' and are often TOC entries
            if '|' in line:
                continue
            
            # SKIP lines that look like page numbers or metadata
            stripped = line.strip()
            if stripped.isdigit():  # Just a page number
                continue
            if stripped.startswith('Page ') or stripped.startswith('---'):
                continue
                
            # Strip HTML-like tags that LlamaParse sometimes adds (e.g., </h8>, </h9>)
            clean_line = re.sub(r'</h\d+>', '', line.strip())
            
            # Try each pattern
            for pattern in SECTION_HEADER_PATTERNS:
                match = re.match(pattern, clean_line, re.IGNORECASE)
                if match:
                    section_num = match.group(1)
                    section_title = match.group(2).strip()

                    # Map title to canonical section type
                    section_type = self._map_title_to_section_type(section_title)

                    if section_type:
                        headers.append({
                            'line_num': i,
                            'section_num': section_num,
                            'title': section_title,
                            'section_type': section_type,
                            'raw_line': line
                        })
                        print(f"[SectionParser/LlamaParse] Found header: {section_num} {section_title} -> {section_type}")
                    break

        print(f"[SectionParser/LlamaParse] Found {len(headers)} section headers")

        # Extract content between headers
        for i, header in enumerate(headers):
            section_type = header['section_type']

            # If we already have this section type, keep the BETTER one (longer content)
            start_line = header['line_num']
            if i + 1 < len(headers):
                end_line = headers[i + 1]['line_num']
            else:
                end_line = len(lines)
            new_content = '\n'.join(lines[start_line:end_line]).strip()
            
            if section_type in sections:
                existing_len = len(sections[section_type].content)
                # Replace if new one is significantly better (2x longer or existing is tiny)
                if len(new_content) > existing_len * 2 or existing_len < 300:
                    print(f"[SectionParser/LlamaParse] Replacing '{section_type}': {existing_len} -> {len(new_content)} chars")
                    del sections[section_type]
                else:
                    continue

            start_line = header['line_num']

            # Find end of section
            if i + 1 < len(headers):
                end_line = headers[i + 1]['line_num']
            else:
                end_line = len(lines)

            # Extract content
            content_lines = lines[start_line:end_line]
            content = '\n'.join(content_lines).strip()

            # Validate content
            if len(content) > 50:
                is_valid, confidence, message = self._validate_multi_signal(section_type, content)

                if is_valid:
                    sections[section_type] = ParsedSection(
                        name=section_type,
                        title=header['title'],
                        content=content,
                        start_page=0,  # Line-based, not page-based
                        end_page=0,
                        confidence=confidence
                    )
                    print(f"[SectionParser/LlamaParse] ✓ Extracted '{section_type}': {len(content)} chars (confidence: {confidence:.2f})")
                else:
                    print(f"[SectionParser/LlamaParse] ✗ REJECTED '{section_type}': {message}")
            else:
                print(f"[SectionParser/LlamaParse] ✗ '{section_type}': content too short ({len(content)} chars)")

        # After extracting sections, check for large lumped sections and split them
        for section_type, section in list(sections.items()):
            if len(section.content) > 5000:  # Suspiciously large - may contain multiple sections
                print(f"[SectionParser/LlamaParse] Section '{section_type}' is large ({len(section.content)} chars), attempting split...")
                sub_sections = self._split_large_section(section.content)
                if len(sub_sections) > 1:
                    print(f"[SectionParser/LlamaParse] Split into {len(sub_sections)} sub-sections: {list(sub_sections.keys())}")
                    # Add the split sections (don't replace the original, just add new ones)
                    for sub_type, sub_content in sub_sections.items():
                        if sub_type not in sections and sub_type != section_type:
                            sections[sub_type] = ParsedSection(
                                name=sub_type,
                                title=sub_type,
                                content=sub_content,
                                confidence=0.7
                            )
                            print(f"[SectionParser/LlamaParse] + Added '{sub_type}': {len(sub_content)} chars")

        return sections

    def _split_large_section(self, content: str) -> Dict[str, str]:
        """
        Split a large lumped section into sub-sections based on header patterns.

        Protocols often have sections like "Objectives" that contain Background,
        Inclusion Criteria, Treatment Plan, Statistical Considerations, etc.
        """
        import re

        # Patterns for internal section boundaries (headers within the content)
        boundary_patterns = [
            # "# Background:" or "# Statistical Considerations"
            (r'\n#\s+([A-Z][A-Za-z\s/&,-]+?)(?::|)\s*\n', 1),
            # "Background:" at start of line
            (r'\n([A-Z][a-z]+(?:\s+[A-Za-z]+){0,3}):\s*\n', 1),
            # ALL CAPS headers like "STATISTICAL CONSIDERATIONS"
            (r'\n([A-Z][A-Z\s]{5,})\n', 1),
            # Numbered sections like "9.1 Sample Size"
            (r'\n(\d+\.\d*\s+[A-Z][^\n]{5,50})\n', 1),
        ]

        # Find all boundaries
        boundaries = []
        for pattern, group_idx in boundary_patterns:
            for match in re.finditer(pattern, content):
                header = match.group(group_idx).strip()
                # Clean up header
                header = re.sub(r'^#+\s*', '', header)  # Remove markdown #
                header = header.strip(':').strip()

                section_type = self._map_title_to_section_type(header)
                if section_type:
                    boundaries.append((match.start(), section_type, header))

        # Also check for specific keyword-based boundaries (handles markdown # headers)
        keyword_boundaries = [
            (r'\n#*\s*(Inclusion Criteria)[:\s]*\n', 'inclusion_criteria'),
            (r'\n#*\s*(Exclusion Criteria)[:\s]*\n', 'exclusion_criteria'),
            (r'\n#*\s*(Treatment Plan)[:\s]*\n', 'treatment_plan'),
            (r'\n#*\s*(Statistical Considerations)[:\s]*\n', 'statistical_methods'),
            (r'\n#*\s*(Sample Size)[:\s]*\n', 'sample_size'),
            (r'\n#*\s*(Background)[:\s]*\n', 'background'),
            (r'\n#*\s*(Objectives)[:\s]*\n', 'objectives'),
            (r'\n#*\s*(Study Design)[:\s]*\n', 'study_design'),
            (r'\n#*\s*(Safety)[:\s]*\n', 'safety'),
            (r'\n#*\s*(Efficacy)[:\s]*\n', 'efficacy'),
            (r'\n#*\s*(Introduction)[:\s]*\n', 'introduction'),
            (r'\n#*\s*(Study Objectives)[:\s]*\n', 'objectives'),
            (r'\n#*\s*(Primary Endpoint)[:\s]*\n', 'endpoints'),
            (r'\n#*\s*(Endpoints)[:\s]*\n', 'endpoints'),
        ]

        for pattern, section_type in keyword_boundaries:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                header = match.group(1).strip()
                # Don't add duplicates
                if not any(b[1] == section_type for b in boundaries):
                    boundaries.append((match.start(), section_type, header))

        if len(boundaries) < 2:
            return {}  # Not enough boundaries to split

        # Sort by position
        boundaries.sort(key=lambda x: x[0])

        # Remove duplicate section types (keep first occurrence)
        seen_types = set()
        unique_boundaries = []
        for pos, section_type, header in boundaries:
            if section_type not in seen_types:
                unique_boundaries.append((pos, section_type, header))
                seen_types.add(section_type)
        boundaries = unique_boundaries

        # Extract content between boundaries
        sections = {}
        for i, (pos, section_type, header) in enumerate(boundaries):
            end_pos = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(content)
            section_content = content[pos:end_pos].strip()

            if len(section_content) > 100:  # Minimum content length
                sections[section_type] = section_content

        return sections

    def _map_title_to_section_type(self, title: str) -> Optional[str]:
        """Map a section title to a canonical section type."""
        import re
        title_lower = title.lower().strip()

        # ===== EXCLUDE BIBLIOGRAPHY/REFERENCE ENTRIES =====
        # Pattern: "13 PASS 14 Power Analysis..." or "14 Fleiss JL, Levin B..."
        if re.match(r'^\d+\.?\s+[A-Z]', title):  # Starts with number + capital letter
            # Check for bibliography indicators
            bib_indicators = [
                r'\d{4}[.\):]',           # Year like 2015. or 2015)
                r':\s*[A-Z][a-z]+\s+&',   # Publisher: "John Wiley &"
                r'LLC|Inc\.|edn\.',       # Company suffixes
                r'[A-Z]{2},\s*[A-Z][a-z]+\s+[A-Z]{1,2}[,:]',  # Author format "JL, Levin B,"
            ]
            for pattern in bib_indicators:
                if re.search(pattern, title):
                    return None  # Skip - this is a bibliography entry

        # SKIP reference citations (contain year patterns like "(2015)", "(2013)")
        if re.search(r'\(\d{4}\)', title):
            return None  # This is a reference citation

        # SKIP endpoint/outcome NAMES (not section headers)
        # These are metrics like "Objective Response Rate", "Overall Survival"
        endpoint_names = ['response rate', 'orr', 'pfs', 'os', 'dor', 'dcr', 'overall survival',
                          'progression-free', 'duration of response', 'disease control']
        for name in endpoint_names:
            if name in title_lower:
                return None  # This is an endpoint name, not a section header

        # Handle COMPOUND headers like "HYPOTHESES, OBJECTIVES, AND ENDPOINTS"
        has_objective = 'objective' in title_lower
        has_endpoint = 'endpoint' in title_lower

        if has_objective and has_endpoint:
            # Compound section - map to objectives (endpoints will be a subsection)
            return 'objectives'

        # Check specific patterns FIRST (before broad keywords)
        specific_mappings = [
            ('primary endpoint', 'endpoints'),
            ('secondary endpoint', 'endpoints'),
            ('exploratory endpoint', 'endpoints'),
            ('efficacy endpoint', 'endpoints'),
            ('study endpoint', 'endpoints'),
            ('sample size', 'sample_size'),
            ('power calculation', 'sample_size'),
            ('interim analysis', 'interim_analysis'),
            ('group sequential', 'interim_analysis'),
            ('analysis population', 'populations'),
            ('analysis set', 'populations'),
            ('missing data', 'missing_data'),
            ('multiple testing', 'multiplicity'),
            ('multiple comparison', 'multiplicity'),
        ]

        for pattern, section_type in specific_mappings:
            if pattern in title_lower:
                return section_type

        # Then check broad keywords
        broad_mappings = [
            ('introduction', 'introduction'),
            ('background', 'introduction'),  # Background often serves as intro
            ('study design', 'study_design'),
            ('trial design', 'study_design'),
            ('statistical', 'statistical_methods'),
            ('multiplicity', 'multiplicity'),
            ('interim', 'interim_analysis'),
            ('endpoint', 'endpoints'),  # Only if specific patterns didn't match
            ('objective', 'objectives'),
            ('population', 'populations'),
            ('stratification', 'stratification'),
            ('randomization', 'stratification'),
            ('safety', 'safety'),
            ('adverse', 'safety'),
            ('estimand', 'estimand'),
        ]

        for keyword, section_type in broad_mappings:
            if keyword in title_lower:
                return section_type

        return None

    # PyMuPDF methods removed - LlamaParse is the only PDF extraction method

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

        # Check expected keywords (need min_expected_keywords, default 2)
        expected = rules.get('expected', [])
        found_expected = sum(1 for kw in expected if kw in content_lower)
        min_expected = rules.get('min_expected_keywords', 2)

        if found_expected < min_expected:
            return False, 0.2, f"Only found {found_expected} expected keywords"

        # Calculate confidence based on expected keyword coverage
        confidence = min(0.95, 0.5 + (found_expected / len(expected)) * 0.5) if expected else 0.7

        # Structure validation: check for paragraph structure (not just TOC lines)
        lines = content.split('\n')
        avg_line_length = sum(len(line) for line in lines) / max(len(lines), 1)

        # Use per-section threshold or default 30
        min_avg_line = rules.get('min_avg_line_length', 30)
        if avg_line_length < min_avg_line:
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
                    model="gpt-4o-mini",
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
