#!/usr/bin/env python3
"""
LLM-based Extractor for Complex Protocol Fields
=================================================

Uses LLM to extract fields that:
1. Are not available in ClinicalTrials.gov API
2. Require semantic understanding (not just pattern matching)

Fields extracted:
- Statistical methodology (primary analysis method)
- Missing data handling approach
- Multiplicity adjustment strategy
- Sensitivity analysis plans
- Derivation rules
- Analysis windows

Usage:
    extractor = LLMExtractor()
    facts = extractor.extract(stats_section_text)
"""

import json
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

# Import tiered LLM client
try:
    from .tiered_llm import get_tiered_client, TieredLLMClient
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("[LLMExtractor] WARNING: TieredLLMClient not available")


@dataclass
class LLMExtractedFacts:
    """Facts extracted via LLM"""
    # Statistical Methods
    primary_analysis_method: str = ""  # ANCOVA, MMRM, logistic regression, etc.
    analysis_model: str = ""  # Full model specification
    covariates: List[str] = field(default_factory=list)

    # Missing Data
    missing_data_method: str = ""  # LOCF, MMRM, MI, etc.
    missing_data_assumptions: str = ""  # MAR, MNAR, etc.

    # Multiplicity
    multiplicity_adjustment: str = ""  # Bonferroni, Hochberg, Gatekeeping, etc.
    alpha_allocation: str = ""
    testing_hierarchy: List[str] = field(default_factory=list)

    # Sensitivity Analyses
    sensitivity_analyses: List[str] = field(default_factory=list)

    # Analysis Windows
    visit_windows: Dict[str, str] = field(default_factory=dict)
    baseline_definition: str = ""

    # Derivations
    endpoint_derivation: str = ""  # How primary endpoint is derived
    responder_definition: str = ""

    # Subgroups
    planned_subgroups: List[str] = field(default_factory=list)

    # Confidence
    extraction_confidence: float = 0.0
    llm_source: str = ""  # Which tier was used
    extraction_success: bool = False
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "primary_analysis_method": self.primary_analysis_method,
            "analysis_model": self.analysis_model,
            "covariates": self.covariates,
            "missing_data_method": self.missing_data_method,
            "missing_data_assumptions": self.missing_data_assumptions,
            "multiplicity_adjustment": self.multiplicity_adjustment,
            "alpha_allocation": self.alpha_allocation,
            "testing_hierarchy": self.testing_hierarchy,
            "sensitivity_analyses": self.sensitivity_analyses,
            "visit_windows": self.visit_windows,
            "baseline_definition": self.baseline_definition,
            "endpoint_derivation": self.endpoint_derivation,
            "responder_definition": self.responder_definition,
            "planned_subgroups": self.planned_subgroups,
            "extraction_confidence": self.extraction_confidence,
            "llm_source": self.llm_source,
        }


class LLMExtractor:
    """
    Extract complex statistical methodology using LLM.

    This handles fields that require semantic understanding:
    - What statistical method is being used?
    - How is missing data handled?
    - What's the multiplicity strategy?
    """

    EXTRACTION_PROMPT = """You are extracting statistical methodology information from a clinical trial protocol section.

Extract the following fields from the text. If a field is not mentioned, leave it empty.

Return ONLY valid JSON with these fields:
{
    "primary_analysis_method": "The main statistical method for primary endpoint (e.g., ANCOVA, MMRM, logistic regression, Cochran-Mantel-Haenszel, Fisher's exact test)",
    "analysis_model": "Full model specification if provided (e.g., 'ANCOVA with treatment, region, and baseline as covariates')",
    "covariates": ["list", "of", "covariates"],
    "missing_data_method": "How missing data is handled (e.g., LOCF, MMRM, multiple imputation, observed cases)",
    "missing_data_assumptions": "Assumption about missing data mechanism (e.g., MAR, MCAR, MNAR)",
    "multiplicity_adjustment": "Method for multiple comparisons (e.g., Bonferroni, Hochberg, Holm, gatekeeping, graphical approach)",
    "alpha_allocation": "How alpha is split between endpoints/comparisons",
    "testing_hierarchy": ["ordered", "list", "of", "hypotheses"],
    "sensitivity_analyses": ["list", "of", "planned", "sensitivity", "analyses"],
    "baseline_definition": "How baseline is defined (e.g., last observation before first dose)",
    "endpoint_derivation": "How the primary endpoint value is calculated/derived",
    "responder_definition": "Definition of a responder if applicable",
    "planned_subgroups": ["list", "of", "planned", "subgroup", "analyses"],
    "confidence": 0.0 to 1.0 based on how clear the information was
}

Protocol text:
{text}

Return ONLY the JSON, no other text."""

    VISIT_WINDOW_PROMPT = """Extract analysis visit windows from this clinical trial protocol section.

Return ONLY valid JSON:
{
    "windows": {
        "Baseline": "Day -7 to Day 1",
        "Week 4": "Day 22 to Day 36",
        ...
    },
    "window_selection_rule": "How to handle multiple assessments in a window (e.g., closest to target, worst case)",
    "confidence": 0.0 to 1.0
}

Protocol text:
{text}

Return ONLY the JSON, no other text."""

    def __init__(self, llm_client: Optional[TieredLLMClient] = None):
        """Initialize with optional LLM client"""
        if llm_client:
            self.llm = llm_client
        elif LLM_AVAILABLE:
            self.llm = get_tiered_client()
        else:
            self.llm = None

    def extract(self, text: str, include_windows: bool = True) -> LLMExtractedFacts:
        """
        Extract statistical methodology from text.

        Args:
            text: Protocol section text (ideally statistical methods section)
            include_windows: Also extract visit windows

        Returns:
            LLMExtractedFacts
        """
        facts = LLMExtractedFacts()

        if not self.llm:
            facts.error = "LLM client not available"
            return facts

        if not text or len(text) < 50:
            facts.error = "Text too short for extraction"
            return facts

        # Truncate if too long (LLM context limits)
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...[truncated]"

        try:
            # Extract main methodology
            facts = self._extract_methodology(text, facts)

            # Extract visit windows if requested
            if include_windows:
                facts = self._extract_windows(text, facts)

            facts.extraction_success = True

        except Exception as e:
            facts.error = f"Extraction failed: {str(e)}"

        return facts

    def _extract_methodology(self, text: str, facts: LLMExtractedFacts) -> LLMExtractedFacts:
        """Extract statistical methodology"""
        prompt = self.EXTRACTION_PROMPT.format(text=text)

        result, source = self.llm.chat_json(
            prompt=prompt,
            system_prompt="You are a clinical trial statistician extracting methodology from protocols. Return only valid JSON.",
            temperature=0.1
        )

        if result:
            facts.llm_source = source
            facts.primary_analysis_method = result.get("primary_analysis_method", "")
            facts.analysis_model = result.get("analysis_model", "")
            facts.covariates = result.get("covariates", [])
            facts.missing_data_method = result.get("missing_data_method", "")
            facts.missing_data_assumptions = result.get("missing_data_assumptions", "")
            facts.multiplicity_adjustment = result.get("multiplicity_adjustment", "")
            facts.alpha_allocation = result.get("alpha_allocation", "")
            facts.testing_hierarchy = result.get("testing_hierarchy", [])
            facts.sensitivity_analyses = result.get("sensitivity_analyses", [])
            facts.baseline_definition = result.get("baseline_definition", "")
            facts.endpoint_derivation = result.get("endpoint_derivation", "")
            facts.responder_definition = result.get("responder_definition", "")
            facts.planned_subgroups = result.get("planned_subgroups", [])
            facts.extraction_confidence = result.get("confidence", 0.7)

        return facts

    def _extract_windows(self, text: str, facts: LLMExtractedFacts) -> LLMExtractedFacts:
        """Extract visit windows"""
        # Only extract if text mentions windows
        if not re.search(r'window|visit|day\s*\d+|week\s*\d+', text, re.IGNORECASE):
            return facts

        prompt = self.VISIT_WINDOW_PROMPT.format(text=text)

        result, _ = self.llm.chat_json(
            prompt=prompt,
            temperature=0.1
        )

        if result:
            facts.visit_windows = result.get("windows", {})

        return facts

    def extract_field(self, text: str, field_name: str, field_description: str) -> Optional[str]:
        """
        Extract a single specific field from text.

        Args:
            text: Source text
            field_name: Name of the field
            field_description: Description of what to extract

        Returns:
            Extracted value or None
        """
        if not self.llm:
            return None

        prompt = f"""Extract the {field_name} from this clinical trial text.

{field_description}

Return JSON: {{"value": "extracted value", "confidence": 0.0-1.0, "source_quote": "relevant quote from text"}}

Text:
{text[:4000]}

Return ONLY the JSON."""

        result, _ = self.llm.chat_json(prompt=prompt, temperature=0.1)

        if result and result.get("confidence", 0) > 0.5:
            return result.get("value")

        return None


# Convenience functions
def extract_with_llm(text: str) -> LLMExtractedFacts:
    """Quick LLM extraction"""
    return LLMExtractor().extract(text)


def extract_field(text: str, field_name: str, description: str) -> Optional[str]:
    """Extract single field with LLM"""
    return LLMExtractor().extract_field(text, field_name, description)
