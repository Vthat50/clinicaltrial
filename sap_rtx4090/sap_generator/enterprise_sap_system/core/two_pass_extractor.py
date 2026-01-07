#!/usr/bin/env python3
"""
Two-Pass Protocol Extraction System
====================================
Production-grade extraction that discovers then extracts.

Pass 1: Discover all statistical elements in the protocol
Pass 2: Extract detailed information for each discovered element

Architecture:
┌──────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Protocol │───▶│ LlamaParse  │───▶│   Pass 1    │───▶│   Pass 2    │
│   PDF    │    │  (sections) │    │  Discovery  │    │  Extraction │
└──────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                          │                   │
                                          ▼                   ▼
                                   ┌─────────────┐    ┌─────────────┐
                                   │  Element    │    │  Validated  │
                                   │  Registry   │    │   Schema    │
                                   └─────────────┘    └─────────────┘
"""

import os
import sys
import json
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum

# Use Anthropic (preferred) or OpenAI
# Force Anthropic if key available since it handles larger contexts better
if os.environ.get('ANTHROPIC_API_KEY'):
    from anthropic import Anthropic
    _USE_OPENAI = False
elif os.environ.get('OPENAI_API_KEY'):
    from openai import OpenAI
    _USE_OPENAI = True
else:
    from anthropic import Anthropic
    _USE_OPENAI = False


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
    section_hint: str  # Which section it was found in
    priority: int = 1  # 1=critical, 2=important, 3=supplementary


@dataclass
class ExtractedElement:
    """Detailed extraction from Pass 2."""
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

        # Group extracted data by category
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

        # Flatten into facts
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
# PASS 1: DISCOVERY
# =============================================================================

DISCOVERY_PROMPT = """You are a biostatistician analyzing a clinical trial protocol.

TASK: Identify ALL statistical and methodological elements present in this protocol.
Do NOT extract values yet - just LIST what elements exist.

Return a JSON array of discovered elements. For each element include:
- "name": Specific name (e.g., "Primary endpoint: PFS", "pMMR population analysis")
- "category": One of [study_design, endpoints, populations, sample_size, hypotheses,
               statistical_methods, interim_analysis, multiplicity, missing_data,
               sensitivity_analyses, subgroups, safety, patient_reported_outcomes, other]
- "description": Brief description of what this element covers
- "section_hint": Which protocol section contains this (e.g., "Section 9.4", "Statistical Methods")
- "priority": 1=critical for SAP, 2=important, 3=supplementary

BE THOROUGH. Look for:
- Multiple populations (e.g., pMMR, dMMR, all-comers) - list EACH separately
- Multiple endpoints - list EACH with its analysis method
- Multiple hypotheses (H1, H2, H3...) - list EACH
- Alpha allocation/spending strategies
- Each PRO instrument separately (EORTC QLQ-C30, EQ-5D, etc.)
- Each sensitivity analysis
- Each subgroup analysis
- Censoring rules for each time-to-event endpoint
- Treatment arms with doses
- Comparator details
- Any China/regional extensions

PROTOCOL TEXT:
{protocol_text}

Return ONLY valid JSON array, no markdown:"""


def run_discovery(protocol_text: str, model: str = None) -> List[DiscoveredElement]:
    """Pass 1: Discover all elements in the protocol."""

    # Truncate if needed
    max_chars = 180000
    text = protocol_text[:max_chars] if len(protocol_text) > max_chars else protocol_text

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

    # Parse JSON
    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        response_text = response_text.strip()

        # Try to repair truncated JSON arrays
        try:
            elements_raw = json.loads(response_text)
        except json.JSONDecodeError:
            # Attempt to repair truncated JSON
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
    text = text.strip()

    # Must start with [
    if not text.startswith('['):
        return None

    # Find the last complete object
    # Look for the last complete "}" followed by optional whitespace
    import re

    # Find all positions of complete objects ending with }
    # We look for }, followed by possible whitespace, then either , or ] or end
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
        # Truncate at last complete object and close the array
        repaired = text[:last_complete + 1] + "]"
        # Remove any trailing comma before the ]
        repaired = re.sub(r',\s*\]$', ']', repaired)
        try:
            json.loads(repaired)
            print(f"  [JSON repair] Recovered {repaired.count('{')} objects from truncated response")
            return repaired
        except:
            pass

    return None


# =============================================================================
# PASS 2: EXTRACTION
# =============================================================================

EXTRACTION_PROMPT = """You are extracting detailed information about a specific element from a clinical trial protocol.

ELEMENT TO EXTRACT: {element_name}
CATEGORY: {category}
DESCRIPTION: {description}
LIKELY LOCATION: {section_hint}

Extract ALL relevant details for this element. Return a JSON object with:
- "element_name": "{element_name}"
- "extracted_data": {{...all relevant fields and values...}}
- "source_text": "Exact quote from protocol (max 200 chars)"
- "confidence": 0.0-1.0 confidence score
- "notes": ["any caveats or uncertainties"]

For extracted_data, include whatever fields are relevant. Examples:

For an ENDPOINT:
{{"definition": "...", "analysis_method": "...", "estimand": "...", "censoring_rules": [...], "timing": "..."}}

For SAMPLE SIZE:
{{"total": N, "per_arm": {{"arm1": N, "arm2": N}}, "assumptions": {{...}}, "power": X, "alpha": Y}}

For a POPULATION:
{{"name": "...", "definition": "...", "n_expected": N, "primary_for": ["endpoint1"]}}

For HYPOTHESES:
{{"null": "H0: ...", "alternative": "H1: ...", "type": "superiority/non-inferiority", "margin": X, "alpha_allocated": Y}}

For PRO:
{{"instrument": "...", "domains": [...], "timing": [...], "analysis_method": "...", "MID": "..."}}

For SENSITIVITY ANALYSIS:
{{"name": "...", "purpose": "...", "method": "...", "applies_to": "..."}}

Be precise. Extract exact numbers, percentages, and definitions from the protocol.

PROTOCOL TEXT:
{protocol_text}

Return ONLY valid JSON, no markdown:"""


def run_extraction(protocol_text: str, element: DiscoveredElement, model: str = None) -> ExtractedElement:
    """Pass 2: Extract details for a specific element."""

    # Truncate if needed
    max_chars = 150000
    text = protocol_text[:max_chars] if len(protocol_text) > max_chars else protocol_text

    prompt = EXTRACTION_PROMPT.format(
        element_name=element.name,
        category=element.category,
        description=element.description,
        section_hint=element.section_hint,
        protocol_text=text
    )

    if _USE_OPENAI:
        client = OpenAI()
        response = client.chat.completions.create(
            model=model or "gpt-4o",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.choices[0].message.content
    else:
        client = Anthropic()
        response = client.messages.create(
            model=model or "claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.content[0].text

    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        data = json.loads(response_text.strip())

        return ExtractedElement(
            element_name=element.name,
            category=element.category,
            extracted_data=data.get("extracted_data", {}),
            source_text=data.get("source_text", ""),
            confidence=data.get("confidence", 0.5),
            notes=data.get("notes", [])
        )

    except json.JSONDecodeError as e:
        return ExtractedElement(
            element_name=element.name,
            category=element.category,
            extracted_data={"raw_response": response_text[:1000]},
            source_text="",
            confidence=0.0,
            notes=[f"Parse error: {str(e)}"]
        )


# =============================================================================
# MAIN PIPELINE
# =============================================================================

class TwoPassExtractor:
    """
    Two-Pass Protocol Extraction System.

    Pass 1: Discover all statistical elements
    Pass 2: Extract detailed data for each element
    """

    def __init__(self, model: str = None):
        self.model = model

    def extract(self, protocol_text: str, protocol_id: str = "unknown",
                max_elements: int = 50, priority_threshold: int = 3,
                verbose: bool = True) -> TwoPassExtractionResult:
        """
        Full two-pass extraction pipeline.

        Args:
            protocol_text: Full protocol text
            protocol_id: Identifier for the protocol
            max_elements: Maximum elements to extract in Pass 2
            priority_threshold: Only extract elements with priority <= this value
            verbose: Print progress

        Returns:
            TwoPassExtractionResult with all discovered and extracted elements
        """

        if verbose:
            print(f"\n{'='*70}")
            print("TWO-PASS PROTOCOL EXTRACTION")
            print(f"{'='*70}")
            print(f"Protocol: {protocol_id}")
            print(f"Text length: {len(protocol_text):,} characters")

        # PASS 1: Discovery
        if verbose:
            print(f"\n{'-'*70}")
            print("PASS 1: DISCOVERY")
            print(f"{'-'*70}")

        start_time = time.time()
        discovered = run_discovery(protocol_text, self.model)
        discovery_time = time.time() - start_time

        if verbose:
            print(f"\nDiscovered {len(discovered)} elements in {discovery_time:.1f}s")

            # Group by category
            by_category = {}
            for elem in discovered:
                cat = elem.category
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(elem)

            print("\nElements by category:")
            for cat, elems in sorted(by_category.items()):
                print(f"  {cat}: {len(elems)}")
                for e in elems[:3]:
                    print(f"    - {e.name} (P{e.priority})")
                if len(elems) > 3:
                    print(f"    ... and {len(elems)-3} more")

        # PASS 2: Extraction
        if verbose:
            print(f"\n{'-'*70}")
            print("PASS 2: EXTRACTION")
            print(f"{'-'*70}")

        # Filter by priority and limit
        to_extract = [e for e in discovered if e.priority <= priority_threshold]
        to_extract = sorted(to_extract, key=lambda x: x.priority)[:max_elements]

        if verbose:
            print(f"\nExtracting {len(to_extract)} elements (priority <= {priority_threshold}, max {max_elements})")

        extracted = {}
        extraction_times = []

        for i, element in enumerate(to_extract):
            if verbose:
                print(f"\n  [{i+1}/{len(to_extract)}] {element.name}...", end=" ", flush=True)

            start_time = time.time()
            result = run_extraction(protocol_text, element, self.model)
            elapsed = time.time() - start_time
            extraction_times.append(elapsed)

            extracted[element.name] = result

            if verbose:
                if result.confidence >= 0.8:
                    print(f"✓ ({elapsed:.1f}s, conf={result.confidence:.2f})")
                elif result.confidence >= 0.5:
                    print(f"⚠ ({elapsed:.1f}s, conf={result.confidence:.2f})")
                else:
                    print(f"✗ ({elapsed:.1f}s, conf={result.confidence:.2f})")

        avg_time = sum(extraction_times) / len(extraction_times) if extraction_times else 0

        if verbose:
            print(f"\nAverage extraction time: {avg_time:.1f}s per element")

        # Validation
        validation_flags = []

        # Check for critical elements
        categories_found = set(e.category for e in discovered)
        critical_categories = {"endpoints", "sample_size", "statistical_methods", "populations"}
        missing = critical_categories - categories_found
        if missing:
            validation_flags.append(f"Missing critical categories: {missing}")

        # Check confidence levels
        low_confidence = [name for name, e in extracted.items() if e.confidence < 0.5]
        if low_confidence:
            validation_flags.append(f"Low confidence extractions: {low_confidence}")

        # Build result
        result = TwoPassExtractionResult(
            protocol_id=protocol_id,
            discovered_elements=discovered,
            extracted_data=extracted,
            metadata={
                "total_discovered": len(discovered),
                "total_extracted": len(extracted),
                "discovery_time_s": discovery_time,
                "avg_extraction_time_s": avg_time,
                "categories_found": list(categories_found)
            },
            validation_flags=validation_flags
        )

        if verbose and validation_flags:
            print(f"\n⚠ Validation flags:")
            for flag in validation_flags:
                print(f"  - {flag}")

        return result

    def extract_from_pdf(self, pdf_path: str, **kwargs) -> TwoPassExtractionResult:
        """Extract from a PDF file."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("Install PyMuPDF: pip install PyMuPDF")

        doc = fitz.open(pdf_path)
        protocol_text = ""
        for page in doc:
            protocol_text += page.get_text()
        doc.close()

        protocol_id = Path(pdf_path).stem
        return self.extract(protocol_text, protocol_id=protocol_id, **kwargs)


def result_to_dict(result: TwoPassExtractionResult) -> dict:
    """Convert result to serializable dict."""
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
        sys.exit(1)

    protocol_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else f"{Path(protocol_path).stem}_extracted.json"

    if not Path(protocol_path).exists():
        print(f"ERROR: File not found: {protocol_path}")
        sys.exit(1)

    try:
        extractor = TwoPassExtractor()
        result = extractor.extract_from_pdf(protocol_path)

        # Summary
        print(f"\n{'='*70}")
        print("EXTRACTION COMPLETE")
        print(f"{'='*70}")

        print(f"\nDiscovered: {result.metadata['total_discovered']} elements")
        print(f"Extracted:  {result.metadata['total_extracted']} elements")

        # Save
        output = result_to_dict(result)
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\nSaved to: {output_path}")

        # Print sample of extracted data
        print(f"\n{'-'*70}")
        print("SAMPLE EXTRACTED DATA")
        print(f"{'-'*70}")

        for name, elem in list(result.extracted_data.items())[:5]:
            print(f"\n{name}:")
            print(f"  Category: {elem.category}")
            print(f"  Confidence: {elem.confidence:.2f}")
            data_str = json.dumps(elem.extracted_data, indent=4)
            if len(data_str) > 500:
                data_str = data_str[:500] + "..."
            print(f"  Data: {data_str}")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
