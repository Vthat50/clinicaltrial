#!/usr/bin/env python3
"""
Unified Protocol Fact Extractor
================================

Combines three extraction layers for maximum accuracy:

1. ClinicalTrials.gov API (Primary - 100% accurate for available fields)
2. Section Parser (Targeted extraction from correct protocol sections)
3. LLM Extraction (For fields requiring semantic understanding)

This replaces the regex-based StructuredFactExtractor for new extractions.

Usage:
    extractor = UnifiedExtractor()
    facts = extractor.extract(protocol_text)
"""

import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from .api_extractor import ClinicalTrialsAPIExtractor, APIExtractedFacts
from .section_parser import ProtocolSectionParser, ParsedProtocol
from .llm_extractor import LLMExtractor, LLMExtractedFacts

# Keep StructuredFactExtractor as fallback for fields not covered
try:
    from .structured_extractor import StructuredFactExtractor, ProtocolFacts
    REGEX_FALLBACK_AVAILABLE = True
except ImportError:
    REGEX_FALLBACK_AVAILABLE = False


@dataclass
class UnifiedFacts:
    """Combined facts from all extraction layers"""
    # Identifiers
    nct_id: str = ""
    protocol_title: str = ""
    sponsor: str = ""

    # Design (from API)
    phase: str = ""
    design_type: str = ""
    is_randomized: bool = False
    is_blinded: bool = False
    is_single_arm: bool = False

    # Sample (from API)
    sample_size: int = 0
    num_arms: int = 0
    arms: List[Dict[str, Any]] = field(default_factory=list)

    # Drug (from API)
    drug_name: str = ""
    therapeutic_area: str = ""
    conditions: List[str] = field(default_factory=list)

    # Endpoints (from API)
    primary_endpoint: str = ""
    primary_timepoint: str = ""
    secondary_endpoints: List[str] = field(default_factory=list)

    # Statistical Methods (from LLM)
    primary_analysis_method: str = ""
    analysis_model: str = ""
    covariates: List[str] = field(default_factory=list)
    missing_data_method: str = ""
    multiplicity_adjustment: str = ""
    sensitivity_analyses: List[str] = field(default_factory=list)

    # Derivations (from LLM)
    baseline_definition: str = ""
    endpoint_derivation: str = ""
    responder_definition: str = ""
    visit_windows: Dict[str, str] = field(default_factory=dict)

    # Subgroups (from LLM)
    planned_subgroups: List[str] = field(default_factory=list)
    stratification_factors: List[str] = field(default_factory=list)

    # Source tracking
    api_success: bool = False
    llm_success: bool = False
    section_parse_success: bool = False
    sources_used: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for pipeline compatibility"""
        return {
            "nct_id": self.nct_id,
            "protocol_title": self.protocol_title,
            "sponsor": self.sponsor,
            "phase": self.phase,
            "design_type": self.design_type,
            "is_randomized": self.is_randomized,
            "is_blinded": self.is_blinded,
            "is_single_arm": self.is_single_arm,
            "sample_size": self.sample_size,
            "num_arms": self.num_arms,
            "arms": self.arms,
            "drug_name": self.drug_name,
            "therapeutic_area": self.therapeutic_area,
            "conditions": self.conditions,
            "primary_endpoint": self.primary_endpoint,
            "primary_timepoint": self.primary_timepoint,
            "secondary_endpoints": self.secondary_endpoints,
            "primary_analysis_method": self.primary_analysis_method,
            "analysis_model": self.analysis_model,
            "covariates": self.covariates,
            "missing_data_method": self.missing_data_method,
            "multiplicity_adjustment": self.multiplicity_adjustment,
            "sensitivity_analyses": self.sensitivity_analyses,
            "baseline_definition": self.baseline_definition,
            "endpoint_derivation": self.endpoint_derivation,
            "responder_definition": self.responder_definition,
            "visit_windows": self.visit_windows,
            "planned_subgroups": self.planned_subgroups,
            "stratification_factors": self.stratification_factors,
            "sources_used": self.sources_used,
        }


class UnifiedExtractor:
    """
    Three-layer extraction for maximum accuracy.

    Layer 1: ClinicalTrials.gov API (structured, 100% accurate)
    Layer 2: Section Parser + LLM (targeted, semantic)
    Layer 3: Regex fallback (legacy, for missing fields)
    """

    def __init__(
        self,
        use_api: bool = True,
        use_llm: bool = True,
        use_regex_fallback: bool = True,
        verbose: bool = True
    ):
        self.use_api = use_api
        self.use_llm = use_llm
        self.use_regex_fallback = use_regex_fallback
        self.verbose = verbose

        # Initialize extractors
        self.api_extractor = ClinicalTrialsAPIExtractor() if use_api else None
        self.section_parser = ProtocolSectionParser()
        self.llm_extractor = LLMExtractor() if use_llm else None
        self.regex_extractor = StructuredFactExtractor() if use_regex_fallback and REGEX_FALLBACK_AVAILABLE else None

        if verbose:
            print("[UnifiedExtractor] Initialized")
            print(f"  API: {'enabled' if use_api else 'disabled'}")
            print(f"  LLM: {'enabled' if use_llm else 'disabled'}")
            print(f"  Regex fallback: {'enabled' if use_regex_fallback and REGEX_FALLBACK_AVAILABLE else 'disabled'}")

    def extract(self, protocol_text: str, nct_id: Optional[str] = None) -> UnifiedFacts:
        """
        Extract facts using all available layers.

        Args:
            protocol_text: Full protocol text
            nct_id: Optional NCT ID (will extract from text if not provided)

        Returns:
            UnifiedFacts with data from all sources
        """
        facts = UnifiedFacts()

        # LAYER 1: API Extraction (if NCT ID available)
        if self.use_api and self.api_extractor:
            facts = self._extract_from_api(protocol_text, nct_id, facts)

        # LAYER 2: Section Parser + LLM
        if self.use_llm and self.llm_extractor:
            facts = self._extract_with_llm(protocol_text, facts)

        # LAYER 3: Regex fallback for missing fields
        if self.use_regex_fallback and self.regex_extractor:
            facts = self._fill_from_regex(protocol_text, facts)

        return facts

    def _extract_from_api(
        self,
        protocol_text: str,
        nct_id: Optional[str],
        facts: UnifiedFacts
    ) -> UnifiedFacts:
        """Layer 1: Extract from ClinicalTrials.gov API"""
        if self.verbose:
            print("[Layer 1] Fetching from ClinicalTrials.gov API...")

        # Get NCT ID
        if not nct_id:
            nct_id = self.api_extractor.extract_nct_id(protocol_text)

        if not nct_id:
            facts.warnings.append("No NCT ID found - API extraction skipped")
            if self.verbose:
                print("  ⚠️ No NCT ID found in text")
            return facts

        # Fetch from API
        api_facts = self.api_extractor.fetch(nct_id)

        if not api_facts.api_success:
            facts.warnings.append(f"API extraction failed: {api_facts.api_error}")
            if self.verbose:
                print(f"  ⚠️ API error: {api_facts.api_error}")
            return facts

        # Copy API facts
        facts.nct_id = api_facts.nct_id
        facts.protocol_title = api_facts.official_title or api_facts.brief_title
        facts.sponsor = api_facts.sponsor
        facts.phase = api_facts.phase
        facts.design_type = api_facts._get_design_type()
        facts.is_randomized = api_facts.is_randomized
        facts.is_blinded = api_facts.is_blinded
        facts.is_single_arm = api_facts.is_single_arm
        facts.sample_size = api_facts.sample_size
        facts.num_arms = api_facts.num_arms
        facts.arms = api_facts.arms
        facts.drug_name = api_facts.drug_name
        facts.therapeutic_area = api_facts.therapeutic_area
        facts.conditions = api_facts.conditions

        # Endpoints
        if api_facts.primary_endpoints:
            facts.primary_endpoint = api_facts.primary_endpoints[0].get("measure", "")
            facts.primary_timepoint = api_facts.primary_endpoints[0].get("timeFrame", "")

        facts.secondary_endpoints = [
            ep.get("measure", "") for ep in api_facts.secondary_endpoints
        ]

        facts.api_success = True
        facts.sources_used.append("clinicaltrials.gov_api")

        if self.verbose:
            print(f"  ✓ API success: {facts.nct_id}")
            print(f"    Primary endpoint: {facts.primary_endpoint[:60]}...")

        return facts

    def _extract_with_llm(self, protocol_text: str, facts: UnifiedFacts) -> UnifiedFacts:
        """Layer 2: Parse sections and extract with LLM"""
        if self.verbose:
            print("[Layer 2] Parsing sections and extracting with LLM...")

        # Parse protocol into sections
        parsed = self.section_parser.parse(protocol_text)
        facts.section_parse_success = parsed.parse_success

        if self.verbose:
            print(f"  Found {parsed.section_count} sections")

        # Get statistical methods section for LLM extraction
        stats_text = self.section_parser.get_stats_sections(parsed)

        if not stats_text:
            # Fall back to searching for statistical content in full text
            stats_text = self._find_stats_content(protocol_text)

        if not stats_text:
            facts.warnings.append("No statistical methods section found")
            if self.verbose:
                print("  ⚠️ No statistical methods section found")
            return facts

        # Extract with LLM
        llm_facts = self.llm_extractor.extract(stats_text)

        if not llm_facts.extraction_success:
            facts.warnings.append(f"LLM extraction failed: {llm_facts.error}")
            if self.verbose:
                print(f"  ⚠️ LLM error: {llm_facts.error}")
            return facts

        # Copy LLM-extracted facts
        facts.primary_analysis_method = llm_facts.primary_analysis_method
        facts.analysis_model = llm_facts.analysis_model
        facts.covariates = llm_facts.covariates
        facts.missing_data_method = llm_facts.missing_data_method
        facts.multiplicity_adjustment = llm_facts.multiplicity_adjustment
        facts.sensitivity_analyses = llm_facts.sensitivity_analyses
        facts.baseline_definition = llm_facts.baseline_definition
        facts.endpoint_derivation = llm_facts.endpoint_derivation
        facts.responder_definition = llm_facts.responder_definition
        facts.visit_windows = llm_facts.visit_windows
        facts.planned_subgroups = llm_facts.planned_subgroups

        facts.llm_success = True
        facts.sources_used.append(f"llm_{llm_facts.llm_source}")

        if self.verbose:
            print(f"  ✓ LLM success via {llm_facts.llm_source}")
            print(f"    Analysis method: {facts.primary_analysis_method}")
            print(f"    Missing data: {facts.missing_data_method}")

        return facts

    def _fill_from_regex(self, protocol_text: str, facts: UnifiedFacts) -> UnifiedFacts:
        """Layer 3: Fill missing fields from regex extraction"""
        if self.verbose:
            print("[Layer 3] Filling gaps with regex extraction...")

        regex_facts = self.regex_extractor.extract(protocol_text)

        filled = []

        # Only fill if API didn't provide
        if not facts.primary_endpoint and regex_facts.primary_endpoint:
            facts.primary_endpoint = regex_facts.primary_endpoint.definition
            filled.append("primary_endpoint")

        if not facts.drug_name and regex_facts.drug_name:
            facts.drug_name = regex_facts.drug_name
            filled.append("drug_name")

        if not facts.sample_size and regex_facts.sample_size:
            facts.sample_size = regex_facts.sample_size.total_n
            filled.append("sample_size")

        if not facts.phase and regex_facts.phase:
            facts.phase = regex_facts.phase.value
            filled.append("phase")

        if not facts.stratification_factors and regex_facts.stratification_factors:
            facts.stratification_factors = regex_facts.stratification_factors
            filled.append("stratification_factors")

        if filled:
            facts.sources_used.append("regex_fallback")
            if self.verbose:
                print(f"  ✓ Filled from regex: {', '.join(filled)}")
        else:
            if self.verbose:
                print("  No gaps to fill")

        return facts

    def _find_stats_content(self, text: str) -> str:
        """Find statistical content if section parsing fails"""
        # Look for statistical keywords and extract surrounding context
        patterns = [
            r'(?:statistical\s+(?:analysis|method|consideration))[^\n]*(?:\n[^\n]+){0,20}',
            r'(?:primary\s+(?:analysis|efficacy\s+analysis))[^\n]*(?:\n[^\n]+){0,15}',
            r'(?:sample\s+size)[^\n]*(?:\n[^\n]+){0,10}',
        ]

        content_parts = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            content_parts.extend(matches)

        return "\n\n".join(content_parts[:3])  # Limit to avoid too much text


# Convenience function
def extract_unified(protocol_text: str, nct_id: Optional[str] = None) -> UnifiedFacts:
    """Quick unified extraction"""
    return UnifiedExtractor().extract(protocol_text, nct_id)
