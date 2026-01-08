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

class KnowledgeGraph:
    """Static knowledge graph for statistical method selection based on endpoint type."""

    ENDPOINT_METHODS = {
        'time-to-event': {
            'primary': ['Kaplan-Meier', 'Log-rank test', 'Cox proportional hazards'],
            'secondary': ['Restricted mean survival time', 'Landmark analysis'],
            'sensitivity': ['Fleming-Harrington weighted log-rank', 'Peto-Peto test'],
            'adam_datasets': ['ADTTE'],
            'key_variables': ['AVAL', 'CNSR', 'STARTDT', 'ADT', 'EVNTDESC'],
        },
        'binary': {
            'primary': ['Cochran-Mantel-Haenszel test', 'Logistic regression', 'Chi-square test'],
            'secondary': ['Exact methods', 'Confidence intervals for proportions'],
            'sensitivity': ['Multiple imputation', 'Tipping point analysis'],
            'adam_datasets': ['ADEFF', 'ADRS'],
            'key_variables': ['AVALC', 'AVAL', 'CRIT1FL', 'ANL01FL'],
        },
        'continuous': {
            'primary': ['MMRM', 'ANCOVA', 'Mixed-effects model'],
            'secondary': ['t-test', 'Wilcoxon rank-sum'],
            'sensitivity': ['Pattern mixture models', 'Last observation carried forward'],
            'adam_datasets': ['ADEFF', 'ADLB'],
            'key_variables': ['AVAL', 'BASE', 'CHG', 'PCHG', 'ABLFL'],
        },
    }

    TA_CONSIDERATIONS = {
        'oncology': {
            'endpoints': ['OS', 'PFS', 'ORR', 'DOR', 'DCR', 'TTR'],
            'criteria': ['RECIST 1.1', 'iRECIST', 'RANO'],
            'populations': ['ITT', 'Evaluable', 'Per-protocol', 'PD-L1 subgroups'],
            'special': ['Independent central review', 'Confirmation of response', 'Censoring rules'],
        },
        'ibd': {
            'endpoints': ['Clinical remission', 'Clinical response', 'Endoscopic improvement', 'Mucosal healing'],
            'criteria': ['Modified Mayo score', 'CDAI', 'SES-CD', 'IBDQ'],
            'populations': ['FAS', 'Per-protocol', 'Bio-naive', 'Bio-experienced'],
            'special': ['Endoscopic subscore', 'Histologic remission', 'Corticosteroid-free remission'],
        },
        'rheumatology': {
            'endpoints': ['ACR20/50/70', 'DAS28', 'HAQ-DI', 'SDAI/CDAI'],
            'criteria': ['ACR criteria', 'EULAR response'],
            'populations': ['MTX-IR', 'TNF-IR', 'Bio-naive'],
            'special': ['Structural damage', 'Radiographic progression'],
        },
    }

    def get_recommended_methods(self, endpoint_type: str, therapeutic_area: str = None) -> Dict:
        """Get recommended statistical methods based on endpoint type."""
        endpoint_type = endpoint_type.lower().replace('-', '_').replace(' ', '_')
        endpoint_type = endpoint_type.replace('time_to_event', 'time-to-event')

        if endpoint_type not in self.ENDPOINT_METHODS:
            endpoint_type = 'binary'

        methods = self.ENDPOINT_METHODS[endpoint_type].copy()

        ta = (therapeutic_area or '').lower()
        if ta in self.TA_CONSIDERATIONS:
            methods['ta_specific'] = self.TA_CONSIDERATIONS[ta]

        return methods

    def get_adam_requirements(self, endpoint_type: str) -> Dict:
        """Get ADaM dataset requirements."""
        endpoint_type = endpoint_type.lower().replace('-', '_').replace(' ', '_')

        if endpoint_type not in self.ENDPOINT_METHODS:
            endpoint_type = 'binary'

        return {
            'datasets': self.ENDPOINT_METHODS[endpoint_type].get('adam_datasets', ['ADEFF']),
            'key_variables': self.ENDPOINT_METHODS[endpoint_type].get('key_variables', []),
        }

    def format_for_prompt(self, endpoint_type: str, therapeutic_area: str = None) -> str:
        """Format knowledge graph info for inclusion in prompt."""
        methods = self.get_recommended_methods(endpoint_type, therapeutic_area)
        adam = self.get_adam_requirements(endpoint_type)

        parts = [
            "## RECOMMENDED STATISTICAL METHODS (from Knowledge Graph)",
            f"Endpoint Type: {endpoint_type}",
            f"Primary Methods: {', '.join(methods.get('primary', []))}",
            f"Secondary Methods: {', '.join(methods.get('secondary', []))}",
            f"Sensitivity Methods: {', '.join(methods.get('sensitivity', []))}",
            f"ADaM Datasets: {', '.join(adam.get('datasets', []))}",
            f"Key Variables: {', '.join(adam.get('key_variables', []))}",
        ]

        if 'ta_specific' in methods:
            ta_info = methods['ta_specific']
            parts.append(f"\n## THERAPEUTIC AREA CONSIDERATIONS ({therapeutic_area})")
            parts.append(f"Standard Endpoints: {', '.join(ta_info.get('endpoints', []))}")
            parts.append(f"Response Criteria: {', '.join(ta_info.get('criteria', []))}")
            parts.append(f"Analysis Populations: {', '.join(ta_info.get('populations', []))}")
            parts.append(f"Special Considerations: {', '.join(ta_info.get('special', []))}")

        return "\n".join(parts)


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


def run_discovery(protocol_text: str, model: str = None) -> List[DiscoveredElement]:
    """Pass 1: Discover all elements in the protocol."""

    # NO TRUNCATION - send full protocol to preserve all statistical details
    # Modern models (Claude-sonnet-4, GPT-4o) have 128k-200k context
    text = protocol_text
    print(f"  [Discovery] Processing full protocol: {len(text):,} characters")

    prompt = DISCOVERY_PROMPT.format(protocol_text=text)

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
                priority=e.get("priority", 2)
            ))

        return elements

    except json.JSONDecodeError as e:
        print(f"WARNING: Could not parse discovery response: {e}")
        print(f"Response was: {response_text[:500]}...")
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

NEVER write "[To be specified]" or "will be detailed in..." - FIND THE EXACT VALUE.

I discovered these {num_elements} elements in the protocol.
EVERY SINGLE ONE must appear in your SAP with EXACT values from the protocol:

{checklist}

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
Do not skip anything."""


def generate_sap_direct(protocol_text: str, discovered_elements: List[DiscoveredElement],
                        sap_template: str = None, model: str = None,
                        rag_examples: str = None, knowledge_graph: str = None,
                        verbose: bool = True) -> str:
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

    prompt = SAP_GENERATION_PROMPT.format(
        num_elements=len(discovered_elements),
        checklist=checklist,
        knowledge_graph=knowledge_graph or "(No knowledge graph available)",
        rag_examples=rag_examples or "(No RAG examples available)",
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

        # Initialize RAG and Knowledge Graph
        print("[TwoPassExtractor] Initializing with RAG + Knowledge Graph...")
        self.rag_retriever = RAGRetriever()
        self.knowledge_graph = KnowledgeGraph()
        print(f"  [OK] RAG: {len(self.rag_retriever.sections_db)} sections indexed")
        print(f"  [OK] Knowledge Graph: {len(self.knowledge_graph.ENDPOINT_METHODS)} endpoint types")

    def discover(self, protocol_text: str, verbose: bool = True) -> List[DiscoveredElement]:
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
        elements = run_discovery(protocol_text, self.model)
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
                     verbose: bool = True) -> Dict[str, Any]:
        """
        Pass 2: Generate SAP directly from full protocol text.

        Args:
            protocol_text: Full protocol text
            discovered_elements: Elements from Pass 1 (or run discovery if None)
            sap_template: Custom SAP template (optional)
            validate: Run validation after generation
            verbose: Print progress

        Returns:
            Dict with 'sap_text', 'validation', and 'metadata'
        """

        # Run discovery if not provided
        if discovered_elements is None:
            discovered_elements = self.discover(protocol_text, verbose=verbose)

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

        # Get Knowledge Graph recommendations based on endpoint type
        kg_info = self.knowledge_graph.format_for_prompt(
            endpoint_type=endpoint_type,
            therapeutic_area=therapeutic_area
        )
        if verbose:
            print(f"  Knowledge Graph: Methods for {endpoint_type} endpoints")

        # Generate SAP with RAG + KG
        sap_text = generate_sap_direct(
            protocol_text=protocol_text,
            discovered_elements=discovered_elements,
            sap_template=sap_template,
            model=self.model,
            rag_examples=rag_examples,
            knowledge_graph=kg_info,
            verbose=verbose
        )

        self._last_sap = sap_text

        result = {
            "sap_text": sap_text,
            "discovered_count": len(discovered_elements),
            "sap_length": len(sap_text),
            "therapeutic_area": therapeutic_area,
            "endpoint_type": endpoint_type,
            "rag_examples_used": len(rag_examples) > 0,
            "knowledge_graph_used": True
        }

        # Validate if requested
        if validate:
            validation = validate_sap(
                sap_text=sap_text,
                discovered_elements=discovered_elements,
                model=self.model,
                verbose=verbose
            )
            result["validation"] = validation

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

                    # Get markdown output (preserves tables and formatting)
                    markdown_docs = result.get_markdown_documents(split_by_page=False)

                    if markdown_docs:
                        protocol_text = "\n\n".join(doc.text for doc in markdown_docs)
                        print(f"[TwoPassExtractor] LlamaParse extracted {len(protocol_text):,} characters")
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
        protocol_text = ""
        for page in doc:
            protocol_text += page.get_text()
        doc.close()

        print(f"[TwoPassExtractor] PyMuPDF extracted {len(protocol_text):,} characters")
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
        """Extract text from PDF using LlamaParse (preferred) or PyMuPDF (fallback)."""
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
                    markdown_docs = result.get_markdown_documents(split_by_page=False)

                    if markdown_docs:
                        return "\n\n".join(doc.text for doc in markdown_docs)
                except Exception as e:
                    print(f"[TwoPassExtractor] LlamaParse error: {e}")

        # Fallback to PyMuPDF
        try:
            import fitz
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
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
