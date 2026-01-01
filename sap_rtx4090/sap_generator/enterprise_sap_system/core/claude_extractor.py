#!/usr/bin/env python3
"""
Claude-Based Protocol Extractor
================================

Uses Claude API to extract structured data from clinical trial protocols.
Based on research showing 99.5% accuracy for LLM clinical extraction.

Reference: AutoCriteria (JAMIA 2024) - GPT-4 achieves 89.42% F1 with zero-shot prompting.
Reference: PMC Study (2025) - Claude 3 Opus achieves 99.5% accuracy on clinical extraction.

This replaces regex-based extraction entirely.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import json
import re

# Import tiered LLM client
try:
    from .tiered_llm import get_tiered_client, TieredLLMClient
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


@dataclass
class ExtractedProtocol:
    """Structured data extracted from protocol via LLM"""
    # Identifiers
    nct_id: str = ""
    protocol_title: str = ""
    sponsor: str = ""

    # Design
    phase: str = ""
    design_type: str = ""  # "randomized", "single-arm", etc.
    is_randomized: bool = False
    is_blinded: bool = False
    blinding_type: str = ""  # "double-blind", "open-label", etc.

    # Sample
    sample_size: int = 0

    # Arms
    num_arms: int = 0
    arms: List[Dict[str, str]] = field(default_factory=list)
    randomization_ratio: str = ""

    # Drug
    drug_name: str = ""
    comparator: str = ""

    # Endpoints
    primary_endpoint: str = ""
    primary_timepoint: str = ""
    secondary_endpoints: List[str] = field(default_factory=list)

    # Statistical
    statistical_method: str = ""
    alpha_level: float = 0.05
    power: float = 0.0

    # Other
    therapeutic_area: str = ""
    indication: str = ""
    stratification_factors: List[str] = field(default_factory=list)

    # Metadata
    extraction_success: bool = False
    extraction_source: str = ""  # "claude", "openai", "groq"
    extraction_confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)


EXTRACTION_PROMPT = '''You are extracting structured information from a clinical trial protocol document.

Extract the following fields and return ONLY valid JSON (no other text):

{{
  "nct_id": "NCT number if present (e.g., NCT01234567)",
  "protocol_title": "Full title of the study",
  "sponsor": "Sponsor company/organization",
  "phase": "Phase 1, Phase 2, Phase 3, Phase 4, or Phase 1/2, etc.",
  "design_type": "randomized, single-arm, crossover, parallel-group, etc.",
  "is_randomized": true or false,
  "is_blinded": true or false,
  "blinding_type": "double-blind, single-blind, open-label, or empty",
  "sample_size": number (total planned enrollment),
  "num_arms": number of treatment arms,
  "arms": [
    {{"name": "Arm A", "treatment": "Drug X 100mg", "n": 50}},
    {{"name": "Arm B", "treatment": "Placebo", "n": 50}}
  ],
  "randomization_ratio": "1:1, 2:1, etc. or empty if not randomized",
  "drug_name": "Primary study drug/investigational product name",
  "comparator": "Comparator drug or placebo if applicable",
  "primary_endpoint": "Exact definition of the primary endpoint",
  "primary_timepoint": "When primary endpoint is measured (e.g., Week 12)",
  "secondary_endpoints": ["List of secondary endpoints"],
  "statistical_method": "Primary statistical analysis method (e.g., ANCOVA, MMRM, logistic regression)",
  "alpha_level": 0.05 (significance level as decimal),
  "power": 0.80 (statistical power as decimal if mentioned),
  "therapeutic_area": "oncology, immunology, cardiology, etc.",
  "indication": "Specific disease/condition being studied",
  "stratification_factors": ["List of stratification factors if randomized"],
  "confidence": 0.0 to 1.0 (your confidence in the extraction accuracy)
}}

IMPORTANT RULES:
1. Extract ONLY what is explicitly stated in the document
2. If a field is not found, use empty string "" or 0 or empty array []
3. For primary_endpoint, extract the COMPLETE definition, not just a fragment
4. For drug_name, identify the investigational product, not standard of care
5. Return ONLY the JSON object, no explanations

PROTOCOL TEXT:
{protocol_text}
'''


class ClaudeProtocolExtractor:
    """
    Extract structured protocol data using Claude/LLM.

    This is the PRIMARY extraction method - no regex fallback.
    """

    def __init__(self, llm_client: Optional[TieredLLMClient] = None):
        if llm_client:
            self.llm = llm_client
        elif LLM_AVAILABLE:
            self.llm = get_tiered_client()
        else:
            self.llm = None
            print("[ClaudeExtractor] WARNING: No LLM client available")

    def extract(self, protocol_text: str) -> ExtractedProtocol:
        """
        Extract structured data from protocol text using LLM.

        Args:
            protocol_text: Full protocol document text

        Returns:
            ExtractedProtocol with all fields populated
        """
        result = ExtractedProtocol()

        if not self.llm:
            result.warnings.append("LLM client not available")
            return result

        if not protocol_text or len(protocol_text) < 100:
            result.warnings.append("Protocol text too short")
            return result

        # Truncate if too long (keep first and last parts for context)
        max_chars = 50000  # Claude can handle ~100k tokens
        if len(protocol_text) > max_chars:
            # Keep beginning (usually has key info) and end (usually has stats)
            half = max_chars // 2
            protocol_text = protocol_text[:half] + "\n\n[...truncated...]\n\n" + protocol_text[-half:]
            result.warnings.append("Protocol truncated due to length")

        # Build prompt
        prompt = EXTRACTION_PROMPT.format(protocol_text=protocol_text)

        # Call LLM
        try:
            response, source = self.llm.chat_json(
                prompt=prompt,
                system_prompt="You are a clinical trial protocol analyst. Extract structured information accurately. Return only valid JSON.",
                temperature=0.1
            )

            if response:
                result = self._parse_response(response, result)
                result.extraction_success = True
                result.extraction_source = source
                print(f"[ClaudeExtractor] ✓ Extraction successful via {source}")
            else:
                result.warnings.append("LLM returned empty response")

        except Exception as e:
            result.warnings.append(f"Extraction failed: {str(e)}")

        return result

    def _parse_response(self, response: Dict[str, Any], result: ExtractedProtocol) -> ExtractedProtocol:
        """Parse LLM JSON response into ExtractedProtocol"""

        # Identifiers
        result.nct_id = response.get("nct_id", "") or ""
        result.protocol_title = response.get("protocol_title", "") or ""
        result.sponsor = response.get("sponsor", "") or ""

        # Design
        result.phase = response.get("phase", "") or ""
        result.design_type = response.get("design_type", "") or ""
        result.is_randomized = bool(response.get("is_randomized", False))
        result.is_blinded = bool(response.get("is_blinded", False))
        result.blinding_type = response.get("blinding_type", "") or ""

        # Sample
        result.sample_size = int(response.get("sample_size", 0) or 0)

        # Arms
        result.num_arms = int(response.get("num_arms", 0) or 0)
        result.arms = response.get("arms", []) or []
        result.randomization_ratio = response.get("randomization_ratio", "") or ""

        # Drug
        result.drug_name = response.get("drug_name", "") or ""
        result.comparator = response.get("comparator", "") or ""

        # Endpoints
        result.primary_endpoint = response.get("primary_endpoint", "") or ""
        result.primary_timepoint = response.get("primary_timepoint", "") or ""
        result.secondary_endpoints = response.get("secondary_endpoints", []) or []

        # Statistical
        result.statistical_method = response.get("statistical_method", "") or ""
        result.alpha_level = float(response.get("alpha_level", 0.05) or 0.05)
        result.power = float(response.get("power", 0) or 0)

        # Other
        result.therapeutic_area = response.get("therapeutic_area", "") or ""
        result.indication = response.get("indication", "") or ""
        result.stratification_factors = response.get("stratification_factors", []) or []

        # Confidence
        result.extraction_confidence = float(response.get("confidence", 0.8) or 0.8)

        # Infer num_arms from arms list if not set
        if not result.num_arms and result.arms:
            result.num_arms = len(result.arms)

        # Infer single-arm from design_type
        if "single" in result.design_type.lower():
            result.num_arms = 1
            result.is_randomized = False

        return result

    def extract_section(self, text: str, section_name: str) -> str:
        """Extract a specific section using LLM"""
        if not self.llm:
            return ""

        prompt = f"""Extract the {section_name} section from this clinical trial document.
Return ONLY the content of that section, nothing else.

Document:
{text[:20000]}
"""

        response = self.llm.chat(prompt=prompt, temperature=0.1)
        return response.content if response.success else ""


def extract_protocol(protocol_text: str) -> ExtractedProtocol:
    """Convenience function for quick extraction"""
    return ClaudeProtocolExtractor().extract(protocol_text)
