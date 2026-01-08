#!/usr/bin/env python3
"""
Two-Pass Protocol Extraction System (V2 - Direct Generation)
=============================================================
Production-grade SAP generation that discovers then generates directly.

Pass 1: Discover all statistical elements in the protocol (CHECKLIST)
Pass 2: Generate SAP directly from full protocol text using checklist

NO INFORMATION LOSS - Full protocol text goes directly to SAP generation.

Architecture:
┌──────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Protocol │───▶│ LlamaParse  │───▶│   Pass 1    │───▶│   Direct    │
│   PDF    │    │  (full text)│    │  Discovery  │    │ Generation  │
└──────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                          │                   │
                                          ▼                   ▼
                                   ┌─────────────┐    ┌─────────────┐
                                   │  Checklist  │───▶│  Complete   │
                                   │  (40 items) │    │    SAP      │
                                   └─────────────┘    └─────────────┘

Key Change from V1:
- V1: Discovery → Extract each element → Flatten → Generate (LOSES INFO)
- V2: Discovery → Use as checklist → Generate from FULL text (NO LOSS)
"""

import os
import sys
import json
import time
import asyncio
import threading
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum

# LlamaParse for high-quality PDF extraction (handles tables, complex layouts)
try:
    from llama_cloud_services import LlamaParse
    LLAMAPARSE_AVAILABLE = True
    print("[TwoPassExtractor] LlamaParse available")
except ImportError:
    LLAMAPARSE_AVAILABLE = False
    print("[TwoPassExtractor] WARNING: LlamaParse not available - install with: pip install llama-cloud-services")

# Thread-local storage for event loops (avoid conflicts with uvloop)
_thread_local = threading.local()

def _get_or_create_event_loop():
    """Get or create a persistent event loop for this thread."""
    if not hasattr(_thread_local, 'loop') or _thread_local.loop.is_closed():
        _thread_local.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_thread_local.loop)
    return _thread_local.loop

def _run_async_in_thread(coro):
    """Run an async coroutine in a dedicated thread with a persistent event loop."""
    from concurrent.futures import ThreadPoolExecutor

    def run_in_persistent_loop():
        loop = _get_or_create_event_loop()
        try:
            return loop.run_until_complete(coro)
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                _thread_local.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(_thread_local.loop)
                return _thread_local.loop.run_until_complete(coro)
            raise

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_persistent_loop)
        return future.result(timeout=300)  # 5 minute timeout for large PDFs

# Use Anthropic (preferred) or OpenAI
if os.environ.get('ANTHROPIC_API_KEY'):
    from anthropic import Anthropic
    _USE_OPENAI = False
elif os.environ.get('OPENAI_API_KEY'):
    from openai import OpenAI
    _USE_OPENAI = True
else:
    from anthropic import Anthropic
    _USE_OPENAI = False

import re

# Deterministic verification (non-LLM)
from .deterministic_verifier import verify_sap_deterministic, AuditReport

# Audit logging for regulatory compliance
from .audit_logger import get_audit_logger


# =============================================================================
# POST-PROCESSORS - Deterministic fixes after SAP generation
# =============================================================================

def strip_duplicate_appendix(sap_text: str) -> str:
    """
    DETERMINISTIC: Remove only DUPLICATE appendix sections with placeholder text.

    KEEP Section 12 (APPENDICES) with TLF specifications.
    ONLY REMOVE: duplicate appendices that contain placeholder text like '[Primary endpoint as specified]'.

    Strategy:
    1. If "END OF STATISTICAL ANALYSIS PLAN" marker exists, keep everything up to it
    2. If there are MULTIPLE APPENDIX sections, keep the first (Section 12), remove duplicates
    3. If there's placeholder text after Section 12, remove that section only
    """
    print(f"[STRIP] ====== RUNNING strip_duplicate_appendix ======")
    print(f"[STRIP] Input length: {len(sap_text)} chars")

    # Placeholder patterns that indicate a bad appendix (should be removed)
    placeholder_patterns = [
        '[Primary endpoint as specified]',
        '[Primary endpoint]',
        '[ENDPOINT]',
        '[endpoint]',
        '[specify endpoint]',
        '[as specified]',
        '[TBD]',
    ]

    # Method 1: Cut at "END OF STATISTICAL ANALYSIS PLAN"
    end_markers = [
        'END OF STATISTICAL ANALYSIS PLAN',
        'End of Statistical Analysis Plan',
        'END OF SAP',
    ]
    for marker in end_markers:
        if marker in sap_text:
            idx = sap_text.find(marker)
            # Keep the marker and one line after, cut the rest
            end_idx = sap_text.find('\n\n', idx + len(marker))
            if end_idx > 0:
                sap_text = sap_text[:end_idx].strip()
                print(f"[STRIP] Cut SAP at '{marker}'")
                return sap_text

    # Method 2: Find Section 12 (APPENDICES) and check for duplicates
    # Look for "Section 12" or "## 12." patterns
    section_12_markers = ['Section 12', '## 12.', '# 12.', '12. APPENDICES', '12. Appendices']
    section_12_pos = -1
    for marker in section_12_markers:
        if marker in sap_text:
            section_12_pos = sap_text.find(marker)
            print(f"[STRIP] Found Section 12 at position {section_12_pos}")
            break

    # Check if there's a DUPLICATE appendix (APPENDIX appearing AFTER Section 12)
    if section_12_pos >= 0:
        # Look for 'APPENDIX:' (with colon) appearing after Section 12
        remaining_text = sap_text[section_12_pos + 100:]  # Skip Section 12 header

        # Find patterns that indicate a duplicate/bad appendix
        duplicate_markers = ['APPENDIX: TLF', 'APPENDIX:\n', '## APPENDIX', '# APPENDIX']
        for dup_marker in duplicate_markers:
            if dup_marker in remaining_text:
                dup_idx = remaining_text.find(dup_marker)
                absolute_idx = section_12_pos + 100 + dup_idx

                # Check if this duplicate section has placeholder text
                dup_section = sap_text[absolute_idx:absolute_idx + 2000]
                has_placeholders = any(p in dup_section for p in placeholder_patterns)

                if has_placeholders:
                    print(f"[STRIP] Found duplicate APPENDIX with placeholders at position {absolute_idx}")
                    sap_text = sap_text[:absolute_idx].strip()
                    print(f"[STRIP] Stripped duplicate, new length: {len(sap_text)}")
                    return sap_text
                else:
                    print(f"[STRIP] Found APPENDIX at {absolute_idx} but no placeholders, keeping it")

    # Method 3: If no Section 12, but there's an APPENDIX with placeholders, remove it
    if 'APPENDIX' in sap_text:
        idx = sap_text.find('APPENDIX')
        appendix_section = sap_text[idx:idx + 2000]
        has_placeholders = any(p in appendix_section for p in placeholder_patterns)

        if has_placeholders:
            print(f"[STRIP] APPENDIX at {idx} has placeholders, removing it")
            sap_text = sap_text[:idx].strip()
            print(f"[STRIP] Stripped, new length: {len(sap_text)}")
            return sap_text
        else:
            print(f"[STRIP] APPENDIX found but no placeholders, keeping it")

    print(f"[STRIP] No stripping needed, TLF tables preserved")
    return sap_text


def inject_tlf_tables(sap_text: str, discovered_elements: list) -> str:
    """
    DETERMINISTIC: Inject TLF table specifications into SAP.

    This GUARANTEES tables appear in the output regardless of what Claude generates.
    Called after stripping to ensure Section 12 has proper TLF content.
    """
    print(f"[TLF-INJECT] ====== INJECTING TLF TABLES ======")

    # Extract endpoints from discovered elements
    primary_endpoints = []
    secondary_endpoints = []

    for elem in discovered_elements:
        cat = (getattr(elem, 'category', '') or '').lower()
        name = (getattr(elem, 'name', '') or '').lower()
        desc = getattr(elem, 'description', '') or getattr(elem, 'name', '') or ''
        desc_lower = desc.lower()

        # Check if this is an endpoint element
        is_endpoint = 'endpoint' in cat or 'endpoint' in name or cat == 'endpoints'

        # Check for primary/secondary in category, name, OR description
        is_primary = 'primary' in cat or 'primary' in name or 'primary' in desc_lower
        is_secondary = 'secondary' in cat or 'secondary' in name or 'secondary' in desc_lower

        if is_endpoint or is_primary or is_secondary:
            if is_primary:
                primary_endpoints.append(desc[:150])
            elif is_secondary:
                secondary_endpoints.append(desc[:150])

    print(f"[TLF-INJECT] Found {len(primary_endpoints)} primary, {len(secondary_endpoints)} secondary endpoints")

    # Build TLF section content
    tlf_content = []
    tlf_content.append("\n\n## 12. APPENDICES\n")
    tlf_content.append("### 12.1 Statistical Model Specifications\n")
    tlf_content.append("See Section 6 for detailed statistical methodology.\n")
    tlf_content.append("\n### 12.2 Tables, Listings, and Figures Specifications\n")
    tlf_content.append("\nThe following TLF shells define the statistical outputs for this study:\n")

    # Demographics Table
    tlf_content.append("\n#### Table 14.1.1: Demographics and Baseline Characteristics\n")
    tlf_content.append("| Column | Width | Alignment | Source |\n")
    tlf_content.append("|--------|-------|-----------|--------|\n")
    tlf_content.append("| Characteristic | 2.5in | Left | ADSL |\n")
    tlf_content.append("| Treatment A (N=xxx) | 1.3in | Center | ADSL |\n")
    tlf_content.append("| Treatment B (N=xxx) | 1.3in | Center | ADSL |\n")
    tlf_content.append("| Total (N=xxx) | 1.3in | Center | ADSL |\n")
    tlf_content.append("\n**Population:** ITT Population\n")
    tlf_content.append("**Programming Notes:** Use PROC MEANS for continuous, PROC FREQ for categorical variables.\n")

    # Disposition Table
    tlf_content.append("\n#### Table 14.1.2: Subject Disposition\n")
    tlf_content.append("| Column | Width | Alignment | Source |\n")
    tlf_content.append("|--------|-------|-----------|--------|\n")
    tlf_content.append("| Disposition Category | 2.5in | Left | ADSL |\n")
    tlf_content.append("| Treatment A n (%) | 1.3in | Center | ADSL |\n")
    tlf_content.append("| Treatment B n (%) | 1.3in | Center | ADSL |\n")
    tlf_content.append("\n**Population:** All Randomized Subjects\n")

    # Primary Endpoint Tables
    for i, endpoint in enumerate(primary_endpoints[:3], start=1):
        tlf_content.append(f"\n#### Table 14.2.{i}: Primary Efficacy Analysis - {endpoint}\n")
        tlf_content.append("| Column | Width | Alignment | Source |\n")
        tlf_content.append("|--------|-------|-----------|--------|\n")
        tlf_content.append("| Statistic | 2.5in | Left | ADTTE/ADEFF |\n")
        tlf_content.append("| Treatment A | 1.5in | Center | ADTTE/ADEFF |\n")
        tlf_content.append("| Treatment B | 1.5in | Center | ADTTE/ADEFF |\n")
        tlf_content.append("\n**Population:** ITT Population\n")
        tlf_content.append("**Analysis:** Per primary analysis methodology in Section 6.\n")

    # Secondary Endpoint Tables
    for i, endpoint in enumerate(secondary_endpoints[:2], start=1):
        idx = len(primary_endpoints) + i
        tlf_content.append(f"\n#### Table 14.2.{idx}: Secondary Efficacy - {endpoint}\n")
        tlf_content.append("| Column | Width | Alignment | Source |\n")
        tlf_content.append("|--------|-------|-----------|--------|\n")
        tlf_content.append("| Parameter | 2.0in | Left | ADEFF |\n")
        tlf_content.append("| Treatment A | 1.5in | Center | ADEFF |\n")
        tlf_content.append("| Treatment B | 1.5in | Center | ADEFF |\n")
        tlf_content.append("\n**Population:** ITT Population\n")

    # Safety Tables
    tlf_content.append("\n#### Table 14.3.1: Overall Summary of Treatment-Emergent Adverse Events\n")
    tlf_content.append("| Column | Width | Alignment | Source |\n")
    tlf_content.append("|--------|-------|-----------|--------|\n")
    tlf_content.append("| AE Category | 2.5in | Left | ADAE |\n")
    tlf_content.append("| Treatment A n (%) | 1.2in | Center | ADAE |\n")
    tlf_content.append("| Treatment B n (%) | 1.2in | Center | ADAE |\n")
    tlf_content.append("| Total n (%) | 1.2in | Center | ADAE |\n")
    tlf_content.append("\n**Population:** Safety Population\n")
    tlf_content.append("**Filter:** SAFFL='Y' and TRTEMFL='Y'\n")

    tlf_content.append("\n#### Table 14.3.2: Serious Adverse Events\n")
    tlf_content.append("| Column | Width | Alignment | Source |\n")
    tlf_content.append("|--------|-------|-----------|--------|\n")
    tlf_content.append("| SOC / Preferred Term | 3.0in | Left | ADAE |\n")
    tlf_content.append("| Treatment A n (%) | 1.2in | Center | ADAE |\n")
    tlf_content.append("| Treatment B n (%) | 1.2in | Center | ADAE |\n")
    tlf_content.append("\n**Population:** Safety Population\n")
    tlf_content.append("**Filter:** SAFFL='Y' and AESER='Y'\n")

    # Figures
    tlf_content.append("\n### 12.3 Figure Specifications\n")

    for i, endpoint in enumerate(primary_endpoints[:2], start=1):
        tlf_content.append(f"\n#### Figure 14.2.{i}: Kaplan-Meier Plot - {endpoint}\n")
        tlf_content.append("**Population:** ITT Population\n")
        tlf_content.append("**X-axis:** Time (months)\n")
        tlf_content.append("**Y-axis:** Survival Probability (0.0 to 1.0)\n")
        tlf_content.append("**Elements:** KM curves by treatment, 95% CI bands, number at risk table\n")
        tlf_content.append("**Programming:** PROC LIFETEST with PLOTS=SURVIVAL(ATRISK CB)\n")

    tlf_content.append("\n#### Figure 14.2.3: Forest Plot - Subgroup Analyses\n")
    tlf_content.append("**Population:** ITT Population\n")
    tlf_content.append("**Elements:** HR with 95% CI by subgroup, vertical reference line at HR=1\n")
    tlf_content.append("**Subgroups:** Age (<65/≥65), Sex, ECOG PS, Geographic Region\n")

    tlf_content.append("\n\n---\nEND OF STATISTICAL ANALYSIS PLAN\n")

    # Check if SAP already has Section 12 with content
    has_section_12 = any(marker in sap_text for marker in ['## 12.', '# 12.', '12. APPENDICES'])
    has_table_14 = 'Table 14' in sap_text

    if has_section_12 and has_table_14:
        print(f"[TLF-INJECT] SAP already has Section 12 with tables, keeping existing")
        return sap_text

    # Remove any incomplete Section 12 before appending
    for marker in ['## 12.', '# 12.', '12. APPENDICES', '12. Appendices']:
        if marker in sap_text:
            idx = sap_text.find(marker)
            sap_text = sap_text[:idx].strip()
            print(f"[TLF-INJECT] Removed incomplete Section 12 at position {idx}")
            break

    # Append TLF content
    result = sap_text + ''.join(tlf_content)
    print(f"[TLF-INJECT] Injected TLF tables, new length: {len(result)} chars")

    return result


def replace_placeholders(sap_text: str, discovered_elements: list) -> str:
    """
    Replace remaining placeholders using discovered elements.

    NO REGEX - uses simple string replacement for reliability.
    """
    if not discovered_elements:
        print("[PostProcess] No discovered elements - skipping placeholder replacement")
        return sap_text

    replacements_made = 0

    # Build lookup from discovered elements
    primary_endpoint = None
    endpoints = []

    for elem in discovered_elements:
        category = getattr(elem, 'category', '') or ''
        name = getattr(elem, 'name', '') or ''
        description = getattr(elem, 'description', '') or ''

        # Look for primary endpoint - check category, name, AND description
        cat_lower = category.lower()
        name_lower = name.lower()
        desc_lower = description.lower()

        # Check if this is an endpoint element
        is_endpoint = 'endpoint' in cat_lower or 'endpoint' in name_lower or cat_lower == 'endpoints'

        # Check if it's PRIMARY - look in category, name, OR description
        is_primary = 'primary' in cat_lower or 'primary' in name_lower or 'primary' in desc_lower

        if is_endpoint or is_primary:
            # Try to get a usable endpoint name
            # Priority: description, then name
            endpoint_text = description if description else name
            if endpoint_text:
                # Set as primary endpoint if marked as primary
                if is_primary and not primary_endpoint:
                    primary_endpoint = endpoint_text
                    print(f"[PostProcess] Found primary endpoint: {endpoint_text[:80]}")
                endpoints.append(endpoint_text)

    print(f"[PostProcess] Found {len(endpoints)} endpoints, primary: {primary_endpoint[:50] if primary_endpoint else 'None'}")

    # Simple string replacements - NO REGEX
    placeholder_replacements = [
        '[Primary endpoint as specified]',
        '[Primary endpoint]',
        '[ENDPOINT]',
        '[endpoint]',
        '[specify endpoint]',
        '[primary endpoint as specified]',
    ]

    if primary_endpoint:
        for placeholder in placeholder_replacements:
            if placeholder in sap_text:
                sap_text = sap_text.replace(placeholder, primary_endpoint)
                replacements_made += 1
                print(f"[PostProcess] Replaced '{placeholder}' with '{primary_endpoint[:50]}'")

    # Remove generic placeholders entirely
    remove_placeholders = [
        '[specify timepoints]',
        '[specify timepoint]',
        '[specify visits]',
        '[specify visit]',
        '[as specified]',
        '[TBD]',
        '[To be specified]',
        '[to be specified]',
    ]

    for placeholder in remove_placeholders:
        if placeholder in sap_text:
            sap_text = sap_text.replace(placeholder, '')
            replacements_made += 1

    if replacements_made > 0:
        print(f"[PostProcess] Replaced {replacements_made} placeholders total")

    return sap_text


# =============================================================================
# TLF SHELL RETRIEVER - Uses ChromaDB 3-collection architecture
# =============================================================================

class TLFShellRetriever:
    """Retrieve TLF shells from ChromaDB for APPENDICES section."""

    def __init__(self):
        self.rag_index = None
        self._initialize_rag()

    def _initialize_rag(self):
        """Initialize RAG index for TLF retrieval."""
        try:
            from .sap_rag import SAPRAGIndex
            # Use the same DB path as the main RAG system
            db_path = Path(__file__).parent.parent.parent / "chroma_db" / "sap_rag_3col"
            if db_path.exists():
                self.rag_index = SAPRAGIndex(db_path=str(db_path))
                stats = self.rag_index.get_stats()
                print(f"  [OK] TLF Retriever: {stats.get('tlf_count', 0)} TLF shells available")
            else:
                print(f"  [!] TLF Retriever: ChromaDB not found at {db_path}")
        except Exception as e:
            print(f"  [!] TLF Retriever initialization failed: {e}")

    def get_tlf_shells(self, therapeutic_area: str = None) -> str:
        """
        Retrieve TLF shells from ChromaDB and format for appendix.

        Returns formatted TLF shell text to append directly to SAP.
        """
        if not self.rag_index:
            return self._get_default_tlf_text()

        tlf_parts = []
        tlf_parts.append("## APPENDIX: TLF SHELL SPECIFICATIONS\n")
        tlf_parts.append("The following TLF shell specifications provide detailed programming requirements for statistical outputs.\n")

        # Query TLF shells by category
        categories = ["demographics", "efficacy", "safety", "figures"]
        total_shells = 0

        for category in categories:
            try:
                # Query TLF collection
                tlfs = self.rag_index.query_tlf(
                    query=category,
                    category=category,
                    n_results=3
                )

                if tlfs:
                    tlf_parts.append(f"\n### {category.title()} TLF Shells\n")
                    for tlf in tlfs:
                        content = tlf.get('content', '')
                        metadata = tlf.get('metadata', {})
                        tlf_type = metadata.get('tlf_type', 'Table')
                        tlf_number = metadata.get('tlf_number', 'TBD')
                        tlf_title = metadata.get('tlf_title', '')

                        tlf_parts.append(f"\n**{tlf_type} {tlf_number}**: {tlf_title}\n")
                        # Include the full shell specification
                        if content:
                            # Clean up and include content
                            content_clean = content.strip()[:2000]  # Limit length
                            tlf_parts.append(f"```\n{content_clean}\n```\n")
                        total_shells += 1

            except Exception as e:
                print(f"  [!] Error querying {category} TLFs: {e}")
                continue

        if total_shells == 0:
            return self._get_default_tlf_text()

        print(f"  [TLF] Retrieved {total_shells} TLF shells from ChromaDB")
        return "\n".join(tlf_parts)

    def _get_default_tlf_text(self) -> str:
        """Return empty - Claude generates TLF specs in Section 12.2."""
        # NO DEFAULTS - Claude generates protocol-specific TLF specs
        return ""


# =============================================================================
# RAG RETRIEVER - Similar SAP sections for few-shot examples
# =============================================================================

class RAGRetriever:
    """Retrieve similar SAP sections from indexed SAPs for few-shot examples."""

    def __init__(self):
        self.sections_db = {}
        self.indexed = False
        self._load_sections()

    def _load_sections(self):
        """Load SAP sections from data directory."""
        data_dir = Path(__file__).parent.parent.parent / "data"
        all_pairs_dir = data_dir / "all_pairs"
        ground_truth_dir = data_dir / "ground_truth"

        total_sections = 0

        for sap_dir in [ground_truth_dir, all_pairs_dir]:
            if not sap_dir.exists():
                continue

            for sap_file in sap_dir.glob("*_sap.txt"):
                nct_id = sap_file.stem.replace("_sap", "")
                try:
                    sap_text = sap_file.read_text(encoding='utf-8', errors='ignore')
                    sections = self._parse_sections(sap_text)
                    ta = self._detect_ta(sap_text)

                    for section_name, content in sections.items():
                        if content and len(content) > 50:
                            key = f"{nct_id}_{section_name}"
                            self.sections_db[key] = {
                                'nct_id': nct_id,
                                'section': section_name,
                                'content': content,
                                'therapeutic_area': ta,
                                'length': len(content)
                            }
                            total_sections += 1
                except Exception as e:
                    continue

        self.indexed = total_sections > 0
        print(f"[RAG] Loaded {total_sections} sections from {len(set(s['nct_id'] for s in self.sections_db.values()))} SAPs")

    def _parse_sections(self, sap_text: str) -> Dict[str, str]:
        """Parse SAP text into sections."""
        sections = {}
        current_section = "introduction"
        current_content = []

        section_patterns = {
            'introduction': r'^#+\s*(?:1[\.\s]*)?introduction',
            'objectives': r'^#+\s*(?:2[\.\s]*)?(?:study\s+)?objectives',
            'endpoints': r'^#+\s*(?:3[\.\s]*)?(?:study\s+)?endpoints?',
            'design': r'^#+\s*(?:4[\.\s]*)?study\s+design',
            'populations': r'^#+\s*(?:5[\.\s]*)?(?:analysis\s+)?populations?',
            'methods': r'^#+\s*(?:6[\.\s]*)?statistical\s+(?:analysis\s+)?methods?',
            'interim': r'^#+\s*(?:7[\.\s]*)?interim\s+analysis',
            'sample_size': r'^#+\s*(?:8[\.\s]*)?sample\s+size',
            'missing_data': r'^#+\s*(?:9[\.\s]*)?(?:handling\s+of\s+)?missing\s+data',
        }

        for line in sap_text.split('\n'):
            line_lower = line.lower().strip()
            for section_name, pattern in section_patterns.items():
                if re.match(pattern, line_lower):
                    if current_content:
                        sections[current_section] = '\n'.join(current_content)
                    current_section = section_name
                    current_content = []
                    break
            else:
                current_content.append(line)

        if current_content:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _detect_ta(self, text: str) -> str:
        """Detect therapeutic area from text."""
        text_lower = text.lower()
        if 'colitis' in text_lower or 'crohn' in text_lower:
            return 'ibd'
        elif 'cancer' in text_lower or 'tumor' in text_lower or 'carcinoma' in text_lower:
            return 'oncology'
        elif 'arthritis' in text_lower or 'rheumatoid' in text_lower:
            return 'rheumatology'
        return 'general'

    def retrieve(self, therapeutic_area: str = None, section_type: str = None, k: int = 3) -> List[Dict]:
        """Retrieve similar sections based on therapeutic area."""
        if not self.indexed:
            return []

        ta = (therapeutic_area or '').lower()
        results = []

        for key, section_data in self.sections_db.items():
            if section_data['therapeutic_area'] == ta:
                score = 1.0
            elif section_data['therapeutic_area'] == 'general':
                score = 0.5
            else:
                score = 0.2

            if section_type and section_data['section'] != section_type:
                continue

            if section_data['length'] > 500:
                score += 0.2

            results.append({
                'nct_id': section_data['nct_id'],
                'section': section_data['section'],
                'content': section_data['content'],
                'score': score
            })

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:k]

    def get_sanitized_examples(self, therapeutic_area: str = None, k: int = 3) -> str:
        """Get sanitized examples with protocol-specific values replaced."""
        examples = self.retrieve(therapeutic_area, k=k)

        if not examples:
            return ""

        sanitized_parts = []
        for ex in examples:
            content = ex['content']

            # Replace specific values with placeholders to prevent contamination
            content = re.sub(r'NCT\d{8}', '{PROTOCOL_ID}', content)
            content = re.sub(r'\b\d{2,4}\s*(?:patients|subjects|participants)', '{N} patients', content, flags=re.IGNORECASE)
            content = re.sub(r'\b\d+:\d+(?::\d+)?\s*(?:randomization|ratio)', '{RATIO}', content, flags=re.IGNORECASE)

            sanitized_parts.append(f"### Example from {ex['nct_id']}:\n{content[:2000]}")

        return "\n\n".join(sanitized_parts)


# =============================================================================
# KNOWLEDGE GRAPH - Statistical method selection
# =============================================================================

# NOTE: Hardcoded KnowledgeGraph was removed.
# The 130-rule JSON knowledge graph at knowledge_graph/sap_knowledge_graph.json
# can be connected in the future for context-based method recommendations.


# =============================================================================
# CONFIGURATION
# =============================================================================

class ElementCategory(Enum):
    """Categories of statistical elements."""
    STUDY_DESIGN = "study_design"
    ENDPOINTS = "endpoints"
    POPULATIONS = "populations"
    SAMPLE_SIZE = "sample_size"
    HYPOTHESES = "hypotheses"
    STATISTICAL_METHODS = "statistical_methods"
    INTERIM_ANALYSIS = "interim_analysis"
    MULTIPLICITY = "multiplicity"
    MISSING_DATA = "missing_data"
    SENSITIVITY = "sensitivity_analyses"
    SUBGROUPS = "subgroups"
    SAFETY = "safety"
    PRO = "patient_reported_outcomes"
    OTHER = "other"


@dataclass
class DiscoveredElement:
    """An element discovered in Pass 1."""
    name: str
    category: str
    description: str
    section_hint: str
    priority: int = 1
    # Source traceability for audit trail
    source_page: Optional[int] = None  # Page number where element was found
    source_context: Optional[str] = None  # Surrounding text for verification


@dataclass
class ExtractedElement:
    """Detailed extraction from Pass 2 (legacy, kept for compatibility)."""
    element_name: str
    category: str
    extracted_data: Dict[str, Any]
    source_text: str
    confidence: float
    notes: List[str] = field(default_factory=list)


@dataclass
class TwoPassExtractionResult:
    """Complete extraction result."""
    protocol_id: str
    discovered_elements: List[DiscoveredElement]
    extracted_data: Dict[str, ExtractedElement]
    metadata: Dict[str, Any]
    validation_flags: List[str] = field(default_factory=list)

    def to_facts_dict(self) -> Dict[str, Any]:
        """Convert to a flat dictionary suitable for SAP generation."""
        facts = {
            "_discovery_count": len(self.discovered_elements),
            "_extraction_count": len(self.extracted_data),
            "_categories": list(set(e.category for e in self.discovered_elements))
        }

        by_category = {}
        for name, elem in self.extracted_data.items():
            cat = elem.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append({
                "name": name,
                "data": elem.extracted_data,
                "confidence": elem.confidence
            })

        for cat, items in by_category.items():
            facts[cat] = items

        return facts

    def get_section_data(self, section_type: str) -> List[Dict]:
        """Get extracted data relevant to a SAP section."""
        section_category_map = {
            "introduction": ["study_design"],
            "objectives_endpoints": ["endpoints", "hypotheses"],
            "study_design": ["study_design", "populations"],
            "sample_size": ["sample_size"],
            "analysis_populations": ["populations"],
            "statistical_methods": ["statistical_methods", "multiplicity"],
            "efficacy_analysis": ["endpoints", "statistical_methods", "sensitivity_analyses"],
            "safety_analysis": ["safety"],
            "missing_data": ["missing_data"],
            "sensitivity_analysis": ["sensitivity_analyses"],
            "interim_analysis": ["interim_analysis"],
            "multiplicity": ["multiplicity", "hypotheses"],
            "subgroup_analysis": ["subgroups"],
            "pro_analysis": ["patient_reported_outcomes"],
        }

        relevant_categories = section_category_map.get(section_type, [])
        relevant_data = []

        for name, elem in self.extracted_data.items():
            if elem.category in relevant_categories:
                relevant_data.append({
                    "element": name,
                    "category": elem.category,
                    "data": elem.extracted_data,
                    "confidence": elem.confidence,
                    "source": elem.source_text
                })

        return relevant_data


# =============================================================================
# PASS 1: DISCOVERY (Enhanced for completeness)
# =============================================================================

DISCOVERY_PROMPT = """You are a biostatistician analyzing a clinical trial protocol.

TASK: Identify ALL statistical and methodological elements present in this protocol.
EXTRACT THE EXACT VALUES - not just element names!

Return a JSON array of discovered elements. For each element include:
- "name": Specific name WITH EXACT VALUES (e.g., "Primary endpoint: PFS in pMMR population, HR=0.7")
- "category": One of [study_design, endpoints, populations, sample_size, hypotheses,
               statistical_methods, interim_analysis, multiplicity, missing_data,
               sensitivity_analyses, subgroups, safety, patient_reported_outcomes, other]
- "description": INCLUDE ALL NUMERIC VALUES found (alpha, power, margins, boundaries, event counts)
- "section_hint": Which protocol section contains this
- "priority": 1=critical for SAP, 2=important, 3=supplementary
- "source_page": Page number where this element was found (look for page markers like "Page X" or "---" separators)
- "source_context": 50-100 character excerpt of surrounding text (for verification)

══════════════════════════════════════════════════════════════════════════════
CRITICAL: EXTRACT EXACT STUDY IDENTIFIERS
══════════════════════════════════════════════════════════════════════════════
- Study number/Protocol number (e.g., "MK-7902-001-05" or "NCT04865289") - EXACT as written
- Sponsor protocol ID - EXACT as written
- ClinicalTrials.gov identifier - EXACT as written

BE EXHAUSTIVE. You MUST find and list WITH EXACT VALUES:

STUDY DESIGN (category: study_design):
- Blinding type (open-label, single-blind, double-blind) - REQUIRED
- Randomization ratio and method
- Study phase
- Treatment arms with specific doses
- Comparator/control details
- Stratification factors

ENDPOINTS (category: endpoints):
- Primary endpoint(s) - if CO-PRIMARY, list EACH separately
- Secondary endpoints - list EACH separately
- Exploratory endpoints
- For each: definition, assessment timing, measurement method

POPULATIONS (category: populations):
- Each analysis population (ITT, FAS, PP, Safety)
- If multiple patient subsets (e.g., pMMR, dMMR, all-comers), list EACH
- Which population is PRIMARY for which endpoint

HYPOTHESES (category: hypotheses):
- List EVERY hypothesis: H1, H2, H3, H4, H5...
- For each: type (superiority/non-inferiority/equivalence)
- For NI hypotheses: the non-inferiority MARGIN (e.g., "NI margin = 1.1") - EXACT NUMBER REQUIRED
- Alpha allocated to each hypothesis (e.g., "α = 0.005 one-sided") - EXACT NUMBER REQUIRED

SAMPLE SIZE (category: sample_size):
- Total sample size - EXACT NUMBER
- Per-arm sample size - EXACT NUMBER
- Power calculation (e.g., "90% power") - EXACT PERCENTAGE
- Effect size / hazard ratio assumed (e.g., "HR = 0.7") - EXACT NUMBER
- Number of events required - EXACT NUMBER

STATISTICAL METHODS (category: statistical_methods):
- Primary analysis method for each endpoint
- Sensitivity analyses - list EACH
- Handling of covariates
- Model specifications

INTERIM ANALYSIS (category: interim_analysis):
- EXACT COUNT of interim analyses (e.g., "3 IAs + 1 FA")
- Timing of EACH: months, % information fraction, # events (e.g., "IA1: ~27 months, ~354 PFS events")
- Stopping boundaries at EACH: Z-scores, p-values, HR boundaries (e.g., "Z=2.96, p=0.0015, HR≤0.72")
- Alpha spending function (e.g., "Lan-DeMets O'Brien-Fleming")
- What is tested at each interim (which hypotheses)

MULTIPLICITY (category: multiplicity):
- Overall alpha (e.g., "α = 0.025 one-sided" or "α = 0.05 two-sided") - EXACT
- Alpha split across hypotheses - EXACT allocation to each (e.g., "H1: α=0.005, H2: α=0.02")
- Testing sequence/hierarchy with weights
- Gatekeeping strategy if applicable
- Graphical approach weights for alpha reallocation

MISSING DATA (category: missing_data):
- Primary approach for missing data
- Sensitivity analyses for missing data

SAFETY (category: safety):
- Safety analysis population
- Key safety endpoints
- Analysis methods for safety

PRO/QoL (category: patient_reported_outcomes):
- Each PRO instrument (EORTC QLQ-C30, EQ-5D-5L, etc.) - list EACH
- Timing of assessments
- Analysis approach

REGIONAL EXTENSIONS (category: other):
- China extension - priority 2
- Japan PMDA requirements - priority 2
- Any regional differences - priority 2

PROTOCOL TEXT:
{protocol_text}

Return ONLY valid JSON array, no markdown. Include AT LEAST 30 elements for a typical protocol:"""


def run_discovery(protocol_text: str, model: str = None, protocol_id: str = "unknown") -> List[DiscoveredElement]:
    """Pass 1: Discover all elements in the protocol."""

    # NO TRUNCATION - send full protocol to preserve all statistical details
    # Modern models (Claude-sonnet-4, GPT-4o) have 128k-200k context
    text = protocol_text
    print(f"  [Discovery] Processing full protocol: {len(text):,} characters")

    prompt = DISCOVERY_PROMPT.format(protocol_text=text)

    # Audit log: prompt
    logger = get_audit_logger()
    used_model = model or ("gpt-4o" if _USE_OPENAI else "claude-sonnet-4-20250514")
    logger.log_prompt(protocol_id, "discovery", prompt, model=used_model)

    start_time = time.time()

    if _USE_OPENAI:
        client = OpenAI()
        response = client.chat.completions.create(
            model=model or "gpt-4o",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.choices[0].message.content
    else:
        client = Anthropic()
        response = client.messages.create(
            model=model or "claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.content[0].text

    duration = time.time() - start_time

    # Audit log: response
    logger.log_response(protocol_id, "discovery", response_text, model=used_model, duration_s=duration)

    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        response_text = response_text.strip()

        try:
            elements_raw = json.loads(response_text)
        except json.JSONDecodeError:
            repaired = _repair_truncated_json(response_text)
            if repaired:
                elements_raw = json.loads(repaired)
            else:
                raise

        elements = []
        for e in elements_raw:
            elements.append(DiscoveredElement(
                name=e.get("name", "Unknown"),
                category=e.get("category", "other"),
                description=e.get("description", ""),
                section_hint=e.get("section_hint", ""),
                priority=e.get("priority", 2),
                # Source traceability
                source_page=e.get("source_page"),
                source_context=e.get("source_context", "")[:200] if e.get("source_context") else None
            ))

        # Audit log: extraction results
        logger.log_extraction(
            protocol_id,
            elements=[{"name": e.name, "category": e.category, "source_page": e.source_page} for e in elements],
            source="discovery_pass",
            metadata={"duration_s": duration}
        )

        return elements

    except json.JSONDecodeError as e:
        print(f"WARNING: Could not parse discovery response: {e}")
        print(f"Response was: {response_text[:500]}...")
        logger.log_error(protocol_id, "json_parse_error", str(e), metadata={"response_preview": response_text[:500]})
        return []


def _repair_truncated_json(text: str) -> Optional[str]:
    """Attempt to repair truncated JSON array."""
    import re

    text = text.strip()

    if not text.startswith('['):
        return None

    last_complete = -1
    depth = 0
    in_string = False
    escape_next = False

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                last_complete = i

    if last_complete > 0:
        repaired = text[:last_complete + 1] + "]"
        repaired = re.sub(r',\s*\]$', ']', repaired)
        try:
            json.loads(repaired)
            print(f"  [JSON repair] Recovered {repaired.count('{')} objects from truncated response")
            return repaired
        except:
            pass

    return None


# =============================================================================
# SAP TEMPLATE (Default)
# =============================================================================

DEFAULT_SAP_TEMPLATE = """
STATISTICAL ANALYSIS PLAN

1. INTRODUCTION
   1.1 Study Overview
   1.2 Study Objectives
   1.3 Study Design Summary

2. STUDY OBJECTIVES AND ENDPOINTS
   2.1 Primary Objective(s) and Endpoint(s)
   2.2 Secondary Objectives and Endpoints
   2.3 Exploratory Objectives and Endpoints

3. STUDY DESIGN
   3.1 Overall Design
   3.2 Blinding
   3.3 Randomization and Stratification
   3.4 Treatment Arms
   3.5 Sample Size Determination

4. ANALYSIS POPULATIONS
   4.1 Intent-to-Treat (ITT) / Full Analysis Set (FAS)
   4.2 Per-Protocol Population
   4.3 Safety Population
   4.4 Other Populations (if applicable)

5. STATISTICAL HYPOTHESES AND TESTING STRATEGY
   5.1 Primary Hypotheses
   5.2 Secondary Hypotheses
   5.3 Testing Hierarchy / Multiplicity Adjustment
   5.4 Alpha Allocation

6. STATISTICAL METHODS FOR EFFICACY
   6.1 Primary Efficacy Analysis
   6.2 Secondary Efficacy Analyses
   6.3 Sensitivity Analyses
   6.4 Subgroup Analyses

7. INTERIM ANALYSES
   7.1 Overview of Interim Analyses
   7.2 Alpha Spending
   7.3 Stopping Boundaries
   7.4 Decision Rules

8. SAFETY ANALYSES
   8.1 Safety Population
   8.2 Adverse Events
   8.3 Laboratory Parameters
   8.4 Other Safety Endpoints

9. MISSING DATA
   9.1 Missing Data Handling
   9.2 Sensitivity Analyses for Missing Data

10. PATIENT-REPORTED OUTCOMES (if applicable)
    10.1 PRO Instruments
    10.2 Analysis Methods

11. REGIONAL CONSIDERATIONS (if applicable)
    11.1 China Extension
    11.2 Other Regional Requirements

12. APPENDICES
    12.1 Statistical Models
    12.2 Tables, Figures, and Listings Specifications
"""


# =============================================================================
# DIRECT SAP GENERATION (No information loss)
# =============================================================================

SAP_GENERATION_PROMPT = """You are an expert biostatistician writing a Statistical Analysis Plan (SAP) for a clinical trial.

READ the protocol below completely. WRITE a comprehensive, production-quality SAP.

══════════════════════════════════════════════════════════════════════════════
⚠️ CRITICAL: USE EXACT NUMBERS FROM THE PROTOCOL - NO PLACEHOLDERS
══════════════════════════════════════════════════════════════════════════════

NEVER write "[To be specified]", "CCI", or "will be detailed in..." - USE THE EXACT VALUES PROVIDED.

I discovered these {num_elements} elements in the protocol.
EVERY SINGLE ONE must appear in your SAP with EXACT values from the protocol:

{checklist}

══════════════════════════════════════════════════════════════════════════════
⭐ PRE-CALCULATED BOUNDARY PARAMETERS (USE THESE EXACT VALUES)
══════════════════════════════════════════════════════════════════════════════

{boundary_info}

IMPORTANT: The boundary parameters above have been extracted and calculated.
Include these EXACT values in Section 7 (Interim Analyses). Do NOT write "CCI" or placeholders.

══════════════════════════════════════════════════════════════════════════════
KNOWLEDGE GRAPH - RECOMMENDED STATISTICAL METHODS
══════════════════════════════════════════════════════════════════════════════

{knowledge_graph}

══════════════════════════════════════════════════════════════════════════════
RAG EXAMPLES - SIMILAR SAP SECTIONS (Use format/style, NOT specific values)
══════════════════════════════════════════════════════════════════════════════

{rag_examples}

══════════════════════════════════════════════════════════════════════════════
MANDATORY REQUIREMENTS - WITH EXACT NUMBERS
══════════════════════════════════════════════════════════════════════════════

1. STUDY IDENTIFIERS:
   - Protocol number EXACTLY as written (e.g., "MK-7902-001-05")
   - NCT number EXACTLY as written
   - DO NOT modify or guess these numbers

2. BLINDING: State explicitly whether open-label, single-blind, or double-blind

3. ENDPOINTS:
   - If there are CO-PRIMARY endpoints, document BOTH with their relationship
   - List ALL secondary endpoints

4. HYPOTHESES - WITH EXACT ALPHA VALUES:
   - List EVERY hypothesis (H1, H2, H3, H4, H5...)
   - For EACH hypothesis state: type (superiority/NI), EXACT alpha allocated (e.g., "α = 0.005 one-sided")
   - For NON-INFERIORITY hypotheses: state the NI MARGIN as EXACT NUMBER (e.g., "NI margin = 1.1")

5. INTERIM ANALYSES - WITH EXACT TIMING AND BOUNDARIES:
   - State the TOTAL COUNT (e.g., "3 interim analyses plus 1 final analysis")
   - For EACH interim state:
     * EXACT timing (months and/or event count, e.g., "IA1: ~27 months, ~354 PFS events")
     * EXACT stopping boundaries (Z-scores, p-values, HR boundaries)
   - Alpha spending function name (e.g., "Lan-DeMets O'Brien-Fleming")

6. ALPHA ALLOCATION - EXACT NUMBERS:
   - Overall alpha level with sidedness (e.g., "α = 0.025 one-sided")
   - EXACT alpha allocation to each hypothesis (e.g., "H1: α=0.005, H3: α=0.02")

7. SAMPLE SIZE - EXACT NUMBERS:
   - Total N and per-arm N
   - Power percentage (e.g., "90% power")
   - Effect size/HR assumed (e.g., "HR = 0.7")
   - Number of events required

8. CENSORING RULES:
   - Describe each censoring scenario
   - Include sensitivity analysis approaches for missing data

9. POPULATIONS:
   - If multiple populations (pMMR, dMMR, all-comers), document EACH
   - Which population is primary for which endpoint

10. REGIONAL EXTENSIONS:
    - If there's a China extension, include Section 11.1 with sample size
    - If there are other regional requirements, document them

11. APPENDICES (Section 12):
    Section 12.2 must list specific tables and figures for THIS protocol.
    Use the ACTUAL endpoint names from the checklist above.

    {tlf_specifications}

══════════════════════════════════════════════════════════════════════════════
SAP TEMPLATE TO FOLLOW
══════════════════════════════════════════════════════════════════════════════

{sap_template}

══════════════════════════════════════════════════════════════════════════════
PROTOCOL TEXT
══════════════════════════════════════════════════════════════════════════════

{protocol_text}

══════════════════════════════════════════════════════════════════════════════
NOW WRITE THE COMPLETE SAP
══════════════════════════════════════════════════════════════════════════════

Write a professional, comprehensive SAP. Include ALL elements from the checklist.
Use exact values from the protocol. Use the Knowledge Graph methods where appropriate.
Follow the style/format from RAG examples but NOT their specific values.
Do not skip anything.

Section 12 is the final section. Use actual endpoint names from the protocol."""


def _generate_tlf_specs(discovered_elements: List[DiscoveredElement]) -> str:
    """Generate TLF specifications from discovered endpoints.

    Extracts actual endpoint names and creates specific table/figure specs.
    This prevents Claude from using placeholder text from training data.
    """
    # Extract endpoints from discovered elements
    primary_endpoints = []
    secondary_endpoints = []
    populations = []

    for elem in discovered_elements:
        cat = (elem.category or '').lower()
        name = (elem.name or '').lower()
        desc = elem.description or elem.name or ''
        desc_lower = desc.lower()

        # Check if this is an endpoint element
        is_endpoint = 'endpoint' in cat or 'endpoint' in name or cat == 'endpoints'

        # Check for primary/secondary in category, name, OR description
        is_primary = 'primary' in cat or 'primary' in name or 'primary' in desc_lower
        is_secondary = 'secondary' in cat or 'secondary' in name or 'secondary' in desc_lower

        if is_endpoint or is_primary or is_secondary:
            if is_primary:
                primary_endpoints.append(desc)
            elif is_secondary:
                secondary_endpoints.append(desc)
        elif 'population' in cat or 'population' in name:
            populations.append(desc)

    # Build TLF specs with actual names
    specs = []
    specs.append("Generate these SPECIFIC tables and figures:")
    specs.append("")
    specs.append("Tables:")
    specs.append("- Table 14.1.1: Demographics and Baseline Characteristics")
    specs.append("- Table 14.1.2: Subject Disposition")

    # Add primary endpoint tables with actual names
    for i, endpoint in enumerate(primary_endpoints[:3], start=1):
        short_name = endpoint[:100] if len(endpoint) > 100 else endpoint
        specs.append(f"- Table 14.2.{i}: {short_name}")

    # Add secondary endpoint tables
    for i, endpoint in enumerate(secondary_endpoints[:3], start=1):
        short_name = endpoint[:100] if len(endpoint) > 100 else endpoint
        specs.append(f"- Table 14.2.{len(primary_endpoints) + i}: {short_name}")

    specs.append("- Table 14.3.1: Treatment-Emergent Adverse Events Summary")
    specs.append("- Table 14.3.2: Serious Adverse Events")
    specs.append("")
    specs.append("Figures:")

    # Add figures for primary endpoints
    for i, endpoint in enumerate(primary_endpoints[:2], start=1):
        short_name = endpoint[:80] if len(endpoint) > 80 else endpoint
        specs.append(f"- Figure 14.2.{i}: Kaplan-Meier Plot - {short_name}")

    specs.append("- Figure 14.2.3: Forest Plot for Subgroup Analyses")

    return "\n".join(specs)


def generate_sap_direct(protocol_text: str, discovered_elements: List[DiscoveredElement],
                        sap_template: str = None, model: str = None,
                        rag_examples: str = None, knowledge_graph: str = None,
                        boundary_info: str = None,
                        verbose: bool = True, protocol_id: str = "unknown") -> str:
    """
    Generate SAP directly from full protocol text.

    Uses discovered elements as a checklist to ensure completeness.
    NO information is lost because we don't extract to intermediate fields.

    Args:
        protocol_text: Full protocol text from LlamaParse
        discovered_elements: Elements found in Pass 1 (used as checklist)
        sap_template: Template structure for SAP (optional)
        model: LLM model to use
        rag_examples: Sanitized examples from similar SAPs
        knowledge_graph: Recommended methods from knowledge graph
        boundary_info: Pre-calculated boundary parameters and tables
        verbose: Print progress

    Returns:
        Complete SAP text
    """

    if verbose:
        print(f"\n{'-'*70}")
        print("GENERATING SAP FROM FULL PROTOCOL TEXT")
        print(f"  + RAG Examples: {'Yes' if rag_examples else 'No'}")
        print(f"  + Knowledge Graph: {'Yes' if knowledge_graph else 'No'}")
        print(f"{'-'*70}")

    # Build checklist from discovered elements, grouped by category
    by_category = {}
    for elem in discovered_elements:
        cat = elem.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(elem)

    checklist_parts = []
    for cat in sorted(by_category.keys()):
        checklist_parts.append(f"\n[{cat.upper()}]")
        for elem in by_category[cat]:
            priority_marker = "★" if elem.priority == 1 else "•"
            checklist_parts.append(f"  {priority_marker} {elem.name}")
            if elem.description:
                checklist_parts.append(f"    → {elem.description}")

    checklist = "\n".join(checklist_parts)

    template = sap_template or DEFAULT_SAP_TEMPLATE

    # Generate TLF specifications from discovered endpoints
    tlf_specs = _generate_tlf_specs(discovered_elements)

    prompt = SAP_GENERATION_PROMPT.format(
        num_elements=len(discovered_elements),
        checklist=checklist,
        boundary_info=boundary_info or "(Boundary parameters not available - extract from protocol)",
        knowledge_graph=knowledge_graph or "(No knowledge graph available)",
        rag_examples=rag_examples or "(No RAG examples available)",
        tlf_specifications=tlf_specs,
        sap_template=template,
        protocol_text=protocol_text
    )

    # NO TRUNCATION - send full protocol to preserve all statistical details
    # Modern models have large context windows (Claude: 200k, GPT-4o: 128k)
    # If protocol is too large, let the API error rather than lose critical data

    if verbose:
        print(f"  Checklist: {len(discovered_elements)} elements across {len(by_category)} categories")
        print(f"  Prompt size: {len(prompt):,} characters")
        print(f"  Generating SAP...")

    # Audit log: SAP generation prompt
    logger = get_audit_logger()
    used_model = model or ("gpt-4o" if _USE_OPENAI else "claude-sonnet-4-20250514")
    logger.log_prompt(protocol_id, "sap_generation", prompt, model=used_model,
                      metadata={"checklist_count": len(discovered_elements)})

    start_time = time.time()

    if _USE_OPENAI:
        client = OpenAI()
        response = client.chat.completions.create(
            model=model or "gpt-4o",
            max_tokens=16000,
            temperature=0.1,  # Lower temperature for consistency
            messages=[{"role": "user", "content": prompt}]
        )
        sap_text = response.choices[0].message.content
    else:
        client = Anthropic()
        response = client.messages.create(
            model=model or "claude-sonnet-4-20250514",
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}]
        )
        sap_text = response.content[0].text

    elapsed = time.time() - start_time

    # Audit log: SAP generation response
    logger.log_response(protocol_id, "sap_generation", sap_text, model=used_model, duration_s=elapsed)

    if verbose:
        print(f"  Generated: {len(sap_text):,} characters in {elapsed:.1f}s")

    return sap_text


# =============================================================================
# VALIDATION (Post-generation check)
# =============================================================================

VALIDATION_PROMPT = """Review this generated SAP against the checklist of required elements.

CHECKLIST (elements that MUST be in the SAP):
{checklist}

GENERATED SAP:
{sap_text}

For each checklist item, determine if it's:
- ✓ PRESENT: Element is clearly addressed in the SAP
- ✗ MISSING: Element is not found in the SAP
- ⚠ PARTIAL: Element is mentioned but incomplete

Return JSON:
{{
    "present": ["element1", "element2", ...],
    "missing": ["element3", ...],
    "partial": ["element4", ...],
    "overall_score": 0.0-1.0,
    "critical_gaps": ["description of any critical missing items"]
}}

Return ONLY valid JSON:"""


def validate_sap(sap_text: str, discovered_elements: List[DiscoveredElement],
                 model: str = None, verbose: bool = True) -> Dict[str, Any]:
    """
    Validate generated SAP against discovered elements.

    Returns validation report with coverage score and gaps.
    """

    if verbose:
        print(f"\n{'-'*70}")
        print("VALIDATING SAP COMPLETENESS")
        print(f"{'-'*70}")

    # Build simple checklist
    checklist = "\n".join([
        f"- [{e.category}] {e.name}"
        for e in discovered_elements
    ])

    prompt = VALIDATION_PROMPT.format(
        checklist=checklist,
        sap_text=sap_text[:50000]  # Limit SAP text for validation
    )

    if _USE_OPENAI:
        client = OpenAI()
        response = client.chat.completions.create(
            model=model or "gpt-4o",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.choices[0].message.content
    else:
        client = Anthropic()
        response = client.messages.create(
            model=model or "claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.content[0].text

    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        validation = json.loads(response_text.strip())

        if verbose:
            score = validation.get('overall_score', 0)
            present = len(validation.get('present', []))
            missing = len(validation.get('missing', []))
            partial = len(validation.get('partial', []))

            print(f"\n  Coverage Score: {score:.1%}")
            print(f"  Present: {present} | Partial: {partial} | Missing: {missing}")

            if validation.get('critical_gaps'):
                print(f"\n  Critical Gaps:")
                for gap in validation['critical_gaps']:
                    print(f"    ⚠ {gap}")

        return validation

    except json.JSONDecodeError:
        if verbose:
            print("  WARNING: Could not parse validation response")
        return {
            "present": [],
            "missing": [],
            "partial": [],
            "overall_score": 0.0,
            "critical_gaps": ["Validation parsing failed"],
            "raw_response": response_text[:500]
        }


# =============================================================================
# MAIN CLASS
# =============================================================================

class TwoPassExtractor:
    """
    Two-Pass Protocol Extraction System (V2) with RAG + Knowledge Graph.

    Pass 1: Discover all statistical elements (checklist)
    Pass 2: Generate SAP directly from full protocol text
            + RAG examples for style/format
            + Knowledge Graph for statistical methods

    This approach ensures NO information is lost between parsing and generation.
    """

    def __init__(self, model: str = None):
        self.model = model
        self._last_discovered = None
        self._last_sap = None

        # Initialize RAG and TLF Shells
        print("[TwoPassExtractor] Initializing with RAG + TLF Shells + Boundary Calculator...")
        self.rag_retriever = RAGRetriever()
        self.tlf_retriever = TLFShellRetriever()

        # Initialize boundary calculator for Phase 2/3 trials
        self.boundary_calculator = None
        try:
            from .boundary_calculator import SAPCalculationEngine
            self.boundary_calculator = SAPCalculationEngine()
            self.boundary_calculator.initialize()
            # Check which engine is primary
            phase3_engine = self.boundary_calculator.phase3_primary.name
            if "R-" in phase3_engine:
                print(f"  [OK] Boundary Calculator: {phase3_engine} (cross-validated)")
            else:
                print(f"  [~] Boundary Calculator: {phase3_engine} (scipy fallback)")
        except Exception as e:
            print(f"  [!] Boundary Calculator: Not available ({e})")

        print(f"  [OK] RAG: {len(self.rag_retriever.sections_db)} sections indexed")

    def discover(self, protocol_text: str, verbose: bool = True, protocol_id: str = "unknown") -> List[DiscoveredElement]:
        """
        Pass 1: Discover all elements in the protocol.

        Returns list of discovered elements to use as checklist.
        """
        if verbose:
            print(f"\n{'='*70}")
            print("PASS 1: ELEMENT DISCOVERY")
            print(f"{'='*70}")
            print(f"Protocol length: {len(protocol_text):,} characters")

        start_time = time.time()
        elements = run_discovery(protocol_text, self.model, protocol_id=protocol_id)
        elapsed = time.time() - start_time

        if verbose:
            print(f"\nDiscovered {len(elements)} elements in {elapsed:.1f}s")

            # Summary by category
            by_cat = {}
            for e in elements:
                by_cat[e.category] = by_cat.get(e.category, 0) + 1

            print("\nBy category:")
            for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
                print(f"  {cat}: {count}")

        self._last_discovered = elements
        return elements

    def generate_sap(self, protocol_text: str, discovered_elements: List[DiscoveredElement] = None,
                     sap_template: str = None, validate: bool = True,
                     verbose: bool = True, protocol_id: str = "unknown") -> Dict[str, Any]:
        """
        Pass 2: Generate SAP directly from full protocol text.

        Args:
            protocol_text: Full protocol text
            discovered_elements: Elements from Pass 1 (or run discovery if None)
            sap_template: Custom SAP template (optional)
            validate: Run validation after generation
            verbose: Print progress
            protocol_id: Protocol identifier for audit trail

        Returns:
            Dict with 'sap_text', 'validation', 'verification', and 'metadata'
        """

        # Run discovery if not provided
        if discovered_elements is None:
            discovered_elements = self.discover(protocol_text, verbose=verbose, protocol_id=protocol_id)

        if verbose:
            print(f"\n{'='*70}")
            print("PASS 2: DIRECT SAP GENERATION + RAG + KNOWLEDGE GRAPH")
            print(f"{'='*70}")

        # Detect therapeutic area and endpoint type from discovered elements
        therapeutic_area = self._detect_therapeutic_area(discovered_elements, protocol_text)
        endpoint_type = self._detect_endpoint_type(discovered_elements, protocol_text)

        if verbose:
            print(f"  Therapeutic Area: {therapeutic_area}")
            print(f"  Endpoint Type: {endpoint_type}")

        # Get RAG examples based on therapeutic area
        rag_examples = self.rag_retriever.get_sanitized_examples(
            therapeutic_area=therapeutic_area,
            k=3
        )
        if verbose:
            print(f"  RAG Examples: {len(rag_examples)} chars from similar SAPs")

        # CRITICAL: Extract and calculate boundary parameters FIRST
        # So we can pass them to the LLM for inclusion in Section 7
        boundary_info = self._prepare_boundary_info(discovered_elements, protocol_text, verbose)

        # Generate SAP with RAG + Pre-calculated Boundaries
        # NOTE: Knowledge graph removed - JSON version can be connected later
        sap_text = generate_sap_direct(
            protocol_text=protocol_text,
            discovered_elements=discovered_elements,
            sap_template=sap_template,
            model=self.model,
            rag_examples=rag_examples,
            knowledge_graph=None,
            boundary_info=boundary_info,
            verbose=verbose,
            protocol_id=protocol_id
        )

        # =====================================================================
        # POST-PROCESSING: Deterministic fixes after SAP generation
        # =====================================================================
        # 1. Strip duplicate APPENDIX section with placeholders
        sap_text = strip_duplicate_appendix(sap_text)

        # 2. Replace any remaining placeholders using discovered elements
        sap_text = replace_placeholders(sap_text, discovered_elements)

        # 3. INJECT TLF TABLES - Guarantees tables appear regardless of what Claude generates
        sap_text = inject_tlf_tables(sap_text, discovered_elements)

        if verbose:
            print(f"[PostProcess] SAP post-processing complete (with TLF injection)")

        # =====================================================================
        # DETERMINISTIC VERIFICATION (Non-LLM)
        # =====================================================================
        # Verify SAP against protocol and calculations WITHOUT using LLM
        if verbose:
            print(f"\n{'-'*70}")
            print("DETERMINISTIC VERIFICATION (Non-LLM)")
            print(f"{'-'*70}")

        try:
            audit_report, audit_text = verify_sap_deterministic(
                sap_text=sap_text,
                protocol_text=protocol_text,
                discovered_elements=discovered_elements,
                r_boundaries=getattr(self, '_last_r_boundaries', None),
                protocol_id=protocol_id
            )

            if verbose:
                print(f"  Checks: {audit_report.total_checks}")
                print(f"  Passed: {audit_report.passed_checks}")
                print(f"  Failed: {audit_report.failed_checks}")
                print(f"  Warnings: {audit_report.warning_checks}")
                if audit_report.requires_human_review:
                    print(f"  ⚠️  REQUIRES HUMAN REVIEW")

            # Audit log: verification results
            logger = get_audit_logger()
            logger.log_verification(
                protocol_id=protocol_id,
                verification_type="deterministic",
                passed=audit_report.passed_checks,
                failed=audit_report.failed_checks,
                warnings=audit_report.warning_checks,
                details=[{"check": c.check_name, "status": c.status.value, "source": c.source_location}
                         for c in (audit_report.extraction_checks + audit_report.calculation_checks +
                                   audit_report.consistency_checks + audit_report.completeness_checks)[:50]],
                metadata={"requires_human_review": audit_report.requires_human_review}
            )
        except Exception as e:
            if verbose:
                print(f"  [!] Verification error: {e}")
            audit_report = None
            audit_text = f"Verification failed: {e}"
            # Log error
            logger = get_audit_logger()
            logger.log_error(protocol_id, "verification_error", str(e))

        self._last_sap = sap_text

        result = {
            "sap_text": sap_text,
            "discovered_count": len(discovered_elements),
            "sap_length": len(sap_text),
            "therapeutic_area": therapeutic_area,
            "endpoint_type": endpoint_type,
            "rag_examples_used": len(rag_examples) > 0,
            "knowledge_graph_used": False,  # Hardcoded KG removed, JSON version can be connected later
            "tlf_in_sap": True,  # Claude generates TLF specs in Section 12 APPENDICES
            "boundary_info_provided": bool(boundary_info and "not available" not in boundary_info.lower()),
            # Deterministic verification results
            "verification": {
                "passed": audit_report.passed_checks if audit_report else 0,
                "failed": audit_report.failed_checks if audit_report else 0,
                "warnings": audit_report.warning_checks if audit_report else 0,
                "requires_human_review": audit_report.requires_human_review if audit_report else True,
                "critical_failures": audit_report.critical_failures if audit_report else [],
                "audit_report": audit_text
            }
        }

        # Validate if requested (legacy LLM-based validation)
        if validate:
            validation = validate_sap(
                sap_text=sap_text,
                discovered_elements=discovered_elements,
                model=self.model,
                verbose=verbose
            )
            result["validation"] = validation

        # Audit log: final SAP generated
        logger = get_audit_logger()
        logger.log_sap_generated(
            protocol_id=protocol_id,
            sap_text=sap_text,
            validation_score=result.get("validation", {}).get("overall_score"),
            verification_summary=result.get("verification"),
            metadata={
                "therapeutic_area": therapeutic_area,
                "endpoint_type": endpoint_type,
                "discovered_count": len(discovered_elements)
            }
        )

        return result

    def _detect_therapeutic_area(self, discovered_elements: List[DiscoveredElement], protocol_text: str) -> str:
        """Detect therapeutic area from discovered elements or protocol text."""
        # Check discovered elements first
        for elem in discovered_elements:
            name_lower = elem.name.lower()
            desc_lower = (elem.description or "").lower()
            combined = name_lower + " " + desc_lower

            if any(term in combined for term in ['cancer', 'tumor', 'carcinoma', 'melanoma', 'lymphoma', 'leukemia', 'oncology']):
                return 'oncology'
            if any(term in combined for term in ['colitis', 'crohn', 'inflammatory bowel', 'ibd', 'ulcerative']):
                return 'ibd'
            if any(term in combined for term in ['arthritis', 'rheumatoid', 'lupus', 'psoriatic']):
                return 'rheumatology'

        # Fallback to protocol text
        text_lower = protocol_text.lower()
        if any(term in text_lower for term in ['cancer', 'tumor', 'carcinoma', 'melanoma', 'lymphoma', 'oncology']):
            return 'oncology'
        if any(term in text_lower for term in ['colitis', 'crohn', 'inflammatory bowel', 'ibd']):
            return 'ibd'
        if any(term in text_lower for term in ['arthritis', 'rheumatoid', 'lupus']):
            return 'rheumatology'

        return 'general'

    def _detect_endpoint_type(self, discovered_elements: List[DiscoveredElement], protocol_text: str) -> str:
        """Detect endpoint type from discovered elements or protocol text."""
        # Check discovered elements first
        for elem in discovered_elements:
            if elem.category == 'endpoints':
                name_lower = elem.name.lower()
                desc_lower = (elem.description or "").lower()
                combined = name_lower + " " + desc_lower

                if any(term in combined for term in ['survival', 'pfs', 'os', 'time-to-event', 'tte', 'progression-free', 'overall survival', 'kaplan-meier']):
                    return 'time-to-event'
                if any(term in combined for term in ['continuous', 'change from baseline', 'mmrm', 'score', 'index']):
                    return 'continuous'
                if any(term in combined for term in ['response rate', 'orr', 'remission', 'binary', 'proportion', 'responder']):
                    return 'binary'

        # Fallback to protocol text
        text_lower = protocol_text.lower()
        if any(term in text_lower for term in ['progression-free survival', 'overall survival', 'time to event', 'kaplan-meier', 'pfs', ' os ']):
            return 'time-to-event'
        if any(term in text_lower for term in ['change from baseline', 'mmrm', 'continuous endpoint']):
            return 'continuous'

        return 'binary'

    def _prepare_boundary_info(self, discovered_elements: List[DiscoveredElement],
                                protocol_text: str, verbose: bool = True) -> str:
        """
        Extract boundary parameters and format them for the LLM prompt.

        This runs BEFORE SAP generation so the LLM can include exact values.
        """
        if verbose:
            print(f"\n{'-'*70}")
            print("EXTRACTING BOUNDARY PARAMETERS (PRE-GENERATION)")
            print(f"{'-'*70}")

        # Extract parameters using LlamaExtract/Claude
        inputs = self._extract_boundary_inputs(discovered_elements, protocol_text)

        if verbose:
            print(f"  Phase: {inputs.get('phase', 'unknown')}")
            print(f"  Alpha (PFS): {inputs.get('alpha', 'not found')}")
            print(f"  Alpha (OS): {inputs.get('os_alpha', 'not found')}")
            print(f"  PFS Events: {inputs.get('events', [])}")
            print(f"  OS Events: {inputs.get('os_events', [])}")
            print(f"  HR: {inputs.get('hr', 'not found')}")
            print(f"  NI Margin: {inputs.get('ni_margin', 'not found')}")
            print(f"  Power (beta): {inputs.get('beta', 0.10)}")
            print(f"  Spending Function: {inputs.get('spending_function', 'OF')}")

        # Format boundary info for LLM prompt
        info_parts = []

        # Trial phase
        phase = inputs.get('phase', '')
        if phase:
            info_parts.append(f"Trial Phase: {phase.replace('phase', 'Phase ')}")

        # Alpha allocation
        alpha = inputs.get('alpha')
        os_alpha = inputs.get('os_alpha')
        if alpha:
            info_parts.append(f"PFS Alpha: α = {alpha} (one-sided)")
        if os_alpha:
            info_parts.append(f"OS Alpha: α = {os_alpha} (one-sided)")

        # Power
        beta = inputs.get('beta')
        if beta is not None:
            power = (1 - beta) * 100
            info_parts.append(f"Power: {power:.0f}%")

        # Hazard ratio
        hr = inputs.get('hr')
        if hr:
            info_parts.append(f"Assumed Hazard Ratio: HR = {hr}")

        # NI margin
        ni_margin = inputs.get('ni_margin')
        if ni_margin and ni_margin > 1.0:
            info_parts.append(f"Non-Inferiority Margin: {ni_margin}")

        # Median survival
        median = inputs.get('median_control')
        if median:
            info_parts.append(f"Control Median Survival: {median} months")

        # Spending function
        sf = inputs.get('spending_function') or 'OF'
        sf_name = "Lan-DeMets O'Brien-Fleming" if sf == "OF" else "Lan-DeMets Pocock" if sf == "Pocock" else sf
        if sf:
            info_parts.append(f"Alpha Spending Function: {sf_name}")

        # Number of analyses
        n_analyses = inputs.get('n_analyses')
        events = inputs.get('events') or []
        os_events = inputs.get('os_events') or []

        if n_analyses:
            n_interim = n_analyses - 1
            info_parts.append(f"Number of Analyses: {n_interim} interim + 1 final = {n_analyses} total")
        elif events:
            info_parts.append(f"Number of PFS Analyses: {len(events)} (based on event counts)")

        # PFS event schedule
        if events:
            info_parts.append(f"\nPFS Event Schedule:")
            for i, ev in enumerate(events):
                if i < len(events) - 1:
                    info_parts.append(f"  IA{i+1}: {ev} PFS events")
                else:
                    info_parts.append(f"  Final: {ev} PFS events")

        # OS event schedule
        if os_events:
            info_parts.append(f"\nOS Event Schedule:")
            for i, ev in enumerate(os_events):
                if i < len(os_events) - 1:
                    info_parts.append(f"  IA{i+1}: {ev} OS events")
                else:
                    info_parts.append(f"  Final: {ev} OS events")

        # Calculate and add boundary tables if we have enough info
        if self.boundary_calculator and phase == 'phase3' and alpha and events:
            try:
                boundary_tables = self.boundary_calculator.generate_interim_analysis_section(
                    pfs_events=events,
                    pfs_alpha=alpha,
                    os_events=os_events,
                    os_alpha=os_alpha,
                    hr_alternative=hr or 0.7,
                    ni_margin=ni_margin if ni_margin and ni_margin > 1.0 else None,
                    spending_function=sf
                )
                if boundary_tables:
                    info_parts.append(f"\n{boundary_tables}")
                    if verbose:
                        print(f"  [OK] Generated boundary tables")
            except Exception as e:
                if verbose:
                    print(f"  [!] Boundary calculation failed: {e}")

        # Phase 2 specific
        if phase == 'phase2':
            p0 = inputs.get('p0')
            p1 = inputs.get('p1')
            if p0:
                info_parts.append(f"Null Response Rate (p0): {p0}")
            if p1:
                info_parts.append(f"Alternative Response Rate (p1): {p1}")

        if not info_parts:
            return "(No boundary parameters could be extracted from protocol)"

        return "\n".join(info_parts)

    def _extract_boundary_inputs(self, discovered_elements: List[DiscoveredElement], protocol_text: str) -> Dict[str, Any]:
        """
        Extract inputs for boundary calculations using Claude (primary) with LlamaExtract fallback.

        Claude has strong clinical trial knowledge for understanding:
        - Phase (Phase 2 or Phase 3)
        - Alpha levels (PFS and OS)
        - Number of interim analyses
        - Event counts (PFS and OS)
        - HR assumptions, NI margins, spending functions
        """
        print(f"  [Extraction] Sending full protocol to Claude ({len(protocol_text)} chars)")

        # Primary: Use Claude for extraction (better clinical terminology understanding)
        extraction_prompt = f"""Extract statistical parameters for interim analysis boundary calculations from this clinical trial protocol.

IMPORTANT: Extract EXACT numerical values from the protocol. Return null for any values not explicitly stated.

FULL PROTOCOL TEXT:
{protocol_text}

Return a JSON object with these fields (use null if not found):
{{
    "phase": "phase2" or "phase3" or "phase1" or null,
    "alpha": <one-sided alpha for primary endpoint, e.g. 0.025>,
    "beta": <type II error rate, e.g. 0.10 for 90% power>,
    "n_analyses": <total number of analyses including final, e.g. 3 for 2 interim + 1 final>,
    "pfs_events": [<list of PFS event counts at each analysis>],
    "os_events": [<list of OS event counts at each analysis if separate OS analysis>],
    "os_alpha": <alpha allocated to OS if different from PFS>,
    "hr": <assumed hazard ratio under alternative hypothesis, e.g. 0.70>,
    "ni_margin": <non-inferiority margin if NI trial, e.g. 1.1>,
    "median_control": <median survival in control arm in months>,
    "p0": <null response rate for Phase 2, e.g. 0.10>,
    "p1": <alternative response rate for Phase 2, e.g. 0.25>,
    "spending_function": "OF" or "Pocock" or null
}}

Notes:
- For two-sided alpha (e.g., 0.05), divide by 2 for one-sided (0.025)
- PFS events should be a list like [100, 200, 300] for interim 1, interim 2, final
- If only final analysis events given, use a single-element list like [500]
- HR should be <1 for superiority trials (e.g., 0.70 means 30% reduction)

Return ONLY valid JSON, no explanation."""

        try:
            if _USE_OPENAI:
                client = OpenAI()
                response = client.chat.completions.create(
                    model=self.model or "gpt-4o",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": extraction_prompt}]
                )
                response_text = response.choices[0].message.content
            else:
                client = Anthropic()
                response = client.messages.create(
                    model=self.model or "claude-sonnet-4-20250514",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": extraction_prompt}]
                )
                response_text = response.content[0].text

            # Parse JSON response
            response_text = response_text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            extracted = json.loads(response_text)

            phase = extracted.get('phase')

            inputs = {
                'phase': phase,
                'alpha': extracted.get('alpha'),
                'beta': extracted.get('beta') or 0.10,
                'n_analyses': extracted.get('n_analyses'),
                'events': extracted.get('pfs_events') or [],
                'info_fractions': [],
                'hr': extracted.get('hr'),
                'ni_margin': extracted.get('ni_margin'),
                'median_control': extracted.get('median_control'),
                'p0': extracted.get('p0'),
                'p1': extracted.get('p1'),
                'os_events': extracted.get('os_events') or [],
                'os_alpha': extracted.get('os_alpha'),
                'china_events': None,
                'spending_function': extracted.get('spending_function') or 'OF',
            }

            print(f"  [Claude] Successfully extracted boundary parameters")
            return inputs

        except Exception as e:
            print(f"  [!] Claude extraction failed: {e}, trying LlamaExtract fallback")

        # Fallback: Use LlamaExtract with Pydantic schema
        try:
            from llama_cloud_services import LlamaExtract
            from pydantic import BaseModel, Field
            from typing import Optional, List as TypingList
            import tempfile

            class BoundaryParameters(BaseModel):
                """Schema for clinical trial boundary calculation parameters."""
                phase: Optional[str] = Field(None, description="Trial phase: 'phase1', 'phase2', or 'phase3'")
                alpha: Optional[float] = Field(None, description="One-sided alpha/significance level for PFS")
                beta: Optional[float] = Field(None, description="Type II error rate (1 - power)")
                n_analyses: Optional[int] = Field(None, description="Total number of analyses including final")
                pfs_events: Optional[TypingList[int]] = Field(None, description="List of PFS event counts at each analysis")
                os_events: Optional[TypingList[int]] = Field(None, description="List of OS event counts at each analysis")
                os_alpha: Optional[float] = Field(None, description="Alpha allocated to OS endpoint")
                hr: Optional[float] = Field(None, description="Assumed hazard ratio under alternative hypothesis")
                ni_margin: Optional[float] = Field(None, description="Non-inferiority margin if NI trial")
                median_control: Optional[float] = Field(None, description="Median survival in control arm in months")
                p0: Optional[float] = Field(None, description="Null response rate for Phase 2")
                p1: Optional[float] = Field(None, description="Alternative response rate for Phase 2")
                spending_function: Optional[str] = Field(None, description="Alpha spending function: 'OF' or 'Pocock'")

            extractor = LlamaExtract()

            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(protocol_text[:100000])
                temp_path = f.name

            try:
                results = extractor.extract(
                    files=[temp_path],
                    schema=BoundaryParameters.model_json_schema(),
                )

                if results and len(results) > 0:
                    extracted = results[0].data if hasattr(results[0], 'data') else results[0]

                    phase = extracted.get('phase')

                    inputs = {
                        'phase': phase,
                        'alpha': extracted.get('alpha'),
                        'beta': extracted.get('beta') or 0.10,
                        'n_analyses': extracted.get('n_analyses'),
                        'events': extracted.get('pfs_events') or [],
                        'info_fractions': [],
                        'hr': extracted.get('hr'),
                        'ni_margin': extracted.get('ni_margin'),
                        'median_control': extracted.get('median_control'),
                        'p0': extracted.get('p0'),
                        'p1': extracted.get('p1'),
                        'os_events': extracted.get('os_events') or [],
                        'os_alpha': extracted.get('os_alpha'),
                        'china_events': None,
                        'spending_function': extracted.get('spending_function') or 'OF',
                    }

                    print(f"  [LlamaExtract] Successfully extracted boundary parameters (fallback)")
                    return inputs

            finally:
                import os as os_module
                if os_module.path.exists(temp_path):
                    os_module.unlink(temp_path)

        except Exception as fallback_e:
            print(f"  [!] LlamaExtract fallback also failed: {fallback_e}")

        # Last resort: return empty values - extraction failed
        phase = 'phase3' if 'phase 3' in protocol_text.lower() or 'phase iii' in protocol_text.lower() else 'phase2' if 'phase 2' in protocol_text.lower() else None

        print(f"  [!] Extraction failed - returning empty values for {phase or 'unknown'} trial")

        return {
            'phase': phase,
            'alpha': None,
            'beta': None,
            'n_analyses': None,
            'events': [],
            'info_fractions': [],
            'hr': None,
            'ni_margin': None,
            'median_control': None,
            'p0': None,
            'p1': None,
            'os_events': [],
            'os_alpha': None,
            'china_events': None,
            'spending_function': None,
        }

    def _generate_boundary_tables(self, discovered_elements: List[DiscoveredElement],
                                   protocol_text: str, verbose: bool = True) -> str:
        """
        Generate boundary tables from protocol inputs using the SAP Calculation Engine.

        Supports:
        - Phase 2: Simon's two-stage designs (optimal, minimax)
        - Phase 3: Group sequential boundaries with Lan-DeMets O'Brien-Fleming
        - China extension power calculations
        - Multiplicity adjustments (graphical approach)

        Returns formatted markdown for inclusion in SAP.
        """
        if not self.boundary_calculator:
            if verbose:
                print("  [!] Boundary calculator not available - skipping boundary tables")
            return ""

        # Extract inputs from protocol
        inputs = self._extract_boundary_inputs(discovered_elements, protocol_text)

        if verbose:
            print(f"\n{'-'*70}")
            print("CALCULATING BOUNDARY TABLES")
            print(f"{'-'*70}")
            print(f"  Phase: {inputs.get('phase', 'unknown')}")
            print(f"  Alpha: {inputs.get('alpha', 'not found')}")
            print(f"  Events: {inputs.get('events', [])}")
            print(f"  HR: {inputs.get('hr', 'not found')}")
            print(f"  NI Margin: {inputs.get('ni_margin', 'not found')}")
            print(f"  Engine: {self.boundary_calculator.phase3_primary.name}")

        phase = inputs.get('phase', '')

        # Phase 2 calculations
        if phase == 'phase2':
            p0 = inputs.get('p0')
            p1 = inputs.get('p1')

            if p0 and p1:
                try:
                    optimal = self.boundary_calculator.calculate_simon_design(
                        p0=p0, p1=p1, design_type="optimal"
                    )
                    minimax = self.boundary_calculator.calculate_simon_design(
                        p0=p0, p1=p1, design_type="minimax"
                    )

                    if verbose:
                        print(f"  [OK] Generated Phase 2 designs (n={optimal.n} optimal, n={minimax.n} minimax)")

                    return "\n\n".join([
                        "## Phase 2 Design Parameters",
                        "",
                        "### Optimal Design (Minimizes Expected N under H0)",
                        optimal.to_markdown(),
                        "",
                        "### Minimax Design (Minimizes Maximum N)",
                        minimax.to_markdown()
                    ])
                except Exception as e:
                    if verbose:
                        print(f"  [!] Phase 2 calculation failed: {e}")
                    return ""
            else:
                if verbose:
                    print("  [~] Phase 2 requires p0 and p1 - skipping")
                return ""

        # Phase 3 calculations
        elif phase == 'phase3':
            if not inputs['alpha'] or not inputs['events']:
                if verbose:
                    print("  [~] Insufficient inputs for Phase 3 boundary calculations")
                return ""

            try:
                # Use generate_interim_analysis_section for complete output
                hr_alternative = inputs.get('hr') or 0.7
                ni_margin = inputs.get('ni_margin')

                # Check if we have separate PFS and OS events
                pfs_events = inputs.get('events') or []
                pfs_alpha = inputs.get('alpha') or 0.025

                # Generate the complete interim analysis section
                formatted = self.boundary_calculator.generate_interim_analysis_section(
                    pfs_events=pfs_events,
                    pfs_alpha=pfs_alpha,
                    os_events=inputs.get('os_events'),
                    os_alpha=inputs.get('os_alpha'),
                    hr_alternative=hr_alternative,
                    ni_margin=ni_margin if ni_margin and ni_margin > 1.0 else None,
                    spending_function="OF"
                )

                if verbose:
                    print(f"  [OK] Generated Phase 3 boundary tables ({len(pfs_events)} analyses)")

                # Add China extension if applicable
                china_events = inputs.get('china_events')
                if china_events:
                    from .boundary_calculator import ChinaExtensionCalculator
                    china_section = ChinaExtensionCalculator.to_markdown(
                        pfs_events=china_events.get('pfs', 71),
                        os_events=china_events.get('os', 54),
                        hr_assumed=hr_alternative
                    )
                    formatted += "\n\n---\n\n" + china_section
                    if verbose:
                        print("  [OK] Added China extension power calculations")

                return formatted

            except Exception as e:
                if verbose:
                    print(f"  [!] Phase 3 boundary calculation failed: {e}")
                return ""

        else:
            if verbose:
                print(f"  [~] Phase '{phase}' not supported for boundary calculations")
            return ""

    def process_protocol(self, protocol_text: str, protocol_id: str = "unknown",
                        sap_template: str = None, validate: bool = True,
                        verbose: bool = True) -> Dict[str, Any]:
        """
        Full pipeline: Discover → Generate → Validate.

        This is the main entry point for production use.
        """

        if verbose:
            print(f"\n{'='*70}")
            print(f"PROCESSING PROTOCOL: {protocol_id}")
            print(f"{'='*70}")

        start_time = time.time()

        # Pass 1: Discovery
        discovered = self.discover(protocol_text, verbose=verbose)

        # Pass 2: Generation
        result = self.generate_sap(
            protocol_text=protocol_text,
            discovered_elements=discovered,
            sap_template=sap_template,
            validate=validate,
            verbose=verbose
        )

        total_time = time.time() - start_time

        result["protocol_id"] = protocol_id
        result["total_time_s"] = total_time
        result["discovered_elements"] = [asdict(e) for e in discovered]

        if verbose:
            print(f"\n{'='*70}")
            print("PROCESSING COMPLETE")
            print(f"{'='*70}")
            print(f"  Total time: {total_time:.1f}s")
            print(f"  Elements discovered: {len(discovered)}")
            print(f"  SAP length: {len(result['sap_text']):,} chars")
            if result.get('validation'):
                print(f"  Validation score: {result['validation'].get('overall_score', 0):.1%}")

        return result

    def process_pdf(self, pdf_path: str, **kwargs) -> Dict[str, Any]:
        """
        Process a PDF file using LlamaParse for high-quality extraction.

        LlamaParse handles:
        - Complex tables (boundary tables, alpha allocation)
        - Multi-column layouts
        - Headers/footers
        - Preserves formatting that contains critical statistical values
        """
        protocol_id = kwargs.pop('protocol_id', Path(pdf_path).stem)

        # Use LlamaParse for accurate PDF extraction
        if LLAMAPARSE_AVAILABLE:
            api_key = os.environ.get('LLAMAPARSE_API_KEY') or os.environ.get('LLAMA_CLOUD_API_KEY')
            if api_key:
                print(f"[TwoPassExtractor] Using LlamaParse for PDF extraction: {pdf_path}")
                try:
                    llamaparse = LlamaParse(
                        api_key=api_key,
                        result_type="markdown",
                        verbose=True
                    )

                    # Async parse in separate thread (avoid uvloop conflicts)
                    async def async_parse():
                        return await asyncio.wait_for(
                            llamaparse.aparse(pdf_path),
                            timeout=180.0  # 3 minute timeout
                        )

                    print("[TwoPassExtractor] Running LlamaParse async extraction...")
                    result = _run_async_in_thread(async_parse())

                    # Get markdown output WITH page markers for source traceability
                    # split_by_page=True returns separate documents per page
                    markdown_docs = result.get_markdown_documents(split_by_page=True)

                    if markdown_docs:
                        # Add page markers to enable source traceability
                        protocol_parts = []
                        for i, doc in enumerate(markdown_docs, start=1):
                            protocol_parts.append(f"\n\n--- PAGE {i} ---\n\n{doc.text}")
                        protocol_text = "\n".join(protocol_parts)
                        print(f"[TwoPassExtractor] LlamaParse extracted {len(protocol_text):,} characters ({len(markdown_docs)} pages)")
                        return self.process_protocol(protocol_text, protocol_id=protocol_id, **kwargs)
                    else:
                        print("[TwoPassExtractor] WARNING: LlamaParse returned no content, falling back to PyMuPDF")

                except Exception as e:
                    print(f"[TwoPassExtractor] LlamaParse error: {e}, falling back to PyMuPDF")
            else:
                print("[TwoPassExtractor] WARNING: LLAMAPARSE_API_KEY not set, falling back to PyMuPDF")
        else:
            print("[TwoPassExtractor] WARNING: LlamaParse not available, using PyMuPDF (lower quality)")

        # Fallback to PyMuPDF (less accurate for tables)
        try:
            import fitz
        except ImportError:
            raise ImportError("Install PyMuPDF: pip install PyMuPDF")

        print(f"[TwoPassExtractor] Using PyMuPDF fallback for: {pdf_path}")
        doc = fitz.open(pdf_path)
        # Add page markers for source traceability
        protocol_parts = []
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text()
            protocol_parts.append(f"\n\n--- PAGE {page_num} ---\n\n{page_text}")
        doc.close()
        protocol_text = "\n".join(protocol_parts)

        print(f"[TwoPassExtractor] PyMuPDF extracted {len(protocol_text):,} characters ({len(protocol_parts)} pages)")
        return self.process_protocol(protocol_text, protocol_id=protocol_id, **kwargs)

    # =========================================================================
    # LEGACY METHODS (for backward compatibility)
    # =========================================================================

    def extract(self, protocol_text: str, protocol_id: str = "unknown",
                max_elements: int = 50, priority_threshold: int = 3,
                verbose: bool = True) -> TwoPassExtractionResult:
        """
        Legacy extraction method (backward compatible).

        NOTE: For new code, use process_protocol() instead.
        This method still does element-by-element extraction which can lose info.
        """

        if verbose:
            print("\n[NOTE: Using legacy extract() method. Consider using process_protocol() instead.]\n")

        # Discovery
        discovered = self.discover(protocol_text, verbose=verbose)

        # For legacy compatibility, we still need to return TwoPassExtractionResult
        # but we skip the detailed extraction since it loses information

        result = TwoPassExtractionResult(
            protocol_id=protocol_id,
            discovered_elements=discovered,
            extracted_data={},  # Empty - use generate_sap() instead
            metadata={
                "total_discovered": len(discovered),
                "total_extracted": 0,
                "note": "Use generate_sap() for actual SAP generation"
            },
            validation_flags=["Legacy method used - no detailed extraction performed"]
        )

        return result

    def extract_from_pdf(self, pdf_path: str, **kwargs) -> TwoPassExtractionResult:
        """Legacy method for PDF extraction - uses LlamaParse."""
        protocol_text = self._extract_pdf_text(pdf_path)
        protocol_id = Path(pdf_path).stem
        return self.extract(protocol_text, protocol_id=protocol_id, **kwargs)

    def _extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text from PDF using LlamaParse (preferred) or PyMuPDF (fallback).

        Includes page markers (--- PAGE X ---) for source traceability.
        """
        # Try LlamaParse first
        if LLAMAPARSE_AVAILABLE:
            api_key = os.environ.get('LLAMAPARSE_API_KEY') or os.environ.get('LLAMA_CLOUD_API_KEY')
            if api_key:
                try:
                    llamaparse = LlamaParse(
                        api_key=api_key,
                        result_type="markdown",
                        verbose=True
                    )

                    async def async_parse():
                        return await asyncio.wait_for(
                            llamaparse.aparse(pdf_path),
                            timeout=180.0
                        )

                    result = _run_async_in_thread(async_parse())
                    markdown_docs = result.get_markdown_documents(split_by_page=True)

                    if markdown_docs:
                        # Add page markers for source traceability
                        parts = []
                        for i, doc in enumerate(markdown_docs, start=1):
                            parts.append(f"\n\n--- PAGE {i} ---\n\n{doc.text}")
                        return "\n".join(parts)
                except Exception as e:
                    print(f"[TwoPassExtractor] LlamaParse error: {e}")

        # Fallback to PyMuPDF
        try:
            import fitz
            doc = fitz.open(pdf_path)
            parts = []
            for page_num, page in enumerate(doc, start=1):
                parts.append(f"\n\n--- PAGE {page_num} ---\n\n{page.get_text()}")
            doc.close()
            return "\n".join(parts)
        except ImportError:
            raise ImportError("Install PyMuPDF: pip install PyMuPDF")


def result_to_dict(result: TwoPassExtractionResult) -> dict:
    """Convert legacy result to serializable dict."""
    return {
        "protocol_id": result.protocol_id,
        "discovered_elements": [asdict(e) for e in result.discovered_elements],
        "extracted_data": {
            name: {
                "element_name": e.element_name,
                "category": e.category,
                "extracted_data": e.extracted_data,
                "source_text": e.source_text,
                "confidence": e.confidence,
                "notes": e.notes
            }
            for name, e in result.extracted_data.items()
        },
        "metadata": result.metadata,
        "validation_flags": result.validation_flags
    }


# =============================================================================
# CLI
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python two_pass_extractor.py <protocol.pdf> [output.json]")
        print("\nThis will:")
        print("  1. Discover all statistical elements in the protocol")
        print("  2. Generate a complete SAP directly from the full text")
        print("  3. Validate the SAP against discovered elements")
        sys.exit(1)

    protocol_path = sys.argv[1]
    output_base = sys.argv[2] if len(sys.argv) > 2 else Path(protocol_path).stem

    if not Path(protocol_path).exists():
        print(f"ERROR: File not found: {protocol_path}")
        sys.exit(1)

    try:
        extractor = TwoPassExtractor()
        result = extractor.process_pdf(protocol_path, validate=True)

        # Save SAP
        sap_output = f"{output_base}_SAP.txt"
        with open(sap_output, 'w') as f:
            f.write(result['sap_text'])
        print(f"\nSAP saved to: {sap_output}")

        # Save full result as JSON
        json_output = f"{output_base}_result.json"

        # Remove sap_text from JSON (it's in the .txt file)
        json_result = {k: v for k, v in result.items() if k != 'sap_text'}
        json_result['sap_file'] = sap_output

        with open(json_output, 'w') as f:
            json.dump(json_result, f, indent=2)
        print(f"Result saved to: {json_output}")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
