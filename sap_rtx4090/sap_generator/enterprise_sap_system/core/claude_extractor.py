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
    is_pilot_study: bool = False  # True for feasibility/pilot studies (no hypothesis testing)

    # Sample
    sample_size: int = 0
    sample_size_justification: str = ""  # Captures if formal power calc vs pragmatic

    # Arms
    num_arms: int = 0
    arms: List[Dict[str, str]] = field(default_factory=list)
    randomization_ratio: str = ""

    # Drug
    drug_name: str = ""
    comparator: str = ""

    # Endpoints - NOW SUPPORTS MULTIPLE CO-PRIMARY ENDPOINTS
    primary_endpoints: List[Dict[str, str]] = field(default_factory=list)
    # Each dict: {"definition": "...", "type": "safety|efficacy|tumor_response", "timepoint": "..."}
    primary_endpoint: str = ""  # DEPRECATED - kept for backwards compatibility
    primary_timepoint: str = ""  # DEPRECATED - kept for backwards compatibility
    secondary_endpoints: List[str] = field(default_factory=list)

    # Oncology Response Criteria (NEW)
    response_criteria: str = ""  # "RECIST 1.1", "mRECIST", "Lugano", "IMWG", "iRECIST", etc.
    pathologic_response_criteria: str = ""  # "Junker", "Miller-Payne", "TRG", etc.
    response_assessor: str = ""  # "investigator", "IRRC", "BICR"

    # Statistical - ENHANCED for complex trial designs
    statistical_method: str = ""  # Primary method (e.g., "log-rank", "MMRM")
    statistical_method_details: str = ""  # Full details (e.g., "Fleming-Harrington weighted log-rank G(rho=0, gamma=1)")
    alpha_level: float = 0.05
    power: float = 0.0
    hypothesis_testing_planned: bool = True  # False for pilot/feasibility studies

    # Interim Analysis (NEW)
    has_interim_analysis: bool = False
    num_interim_analyses: int = 0
    interim_analysis_method: str = ""  # "Lan-DeMets", "O'Brien-Fleming", "Pocock", etc.
    error_spending_function: str = ""  # e.g., "alpha-spending with rho=1"
    interim_events: List[int] = field(default_factory=list)  # Events at each interim
    final_events: int = 0  # Events at final analysis

    # Consistency/Non-Inferiority Objectives (NEW)
    has_consistency_objective: bool = False  # True if comparing to prior studies
    consistency_margin: str = ""  # e.g., "HR upper bound < 1.29"
    consistency_reference_studies: List[str] = field(default_factory=list)  # e.g., ["CheckMate 057", "CheckMate 017"]

    # Regulatory-Specific Endpoints (NEW)
    regulatory_endpoints: List[Dict[str, str]] = field(default_factory=list)
    # e.g., [{"endpoint": "TTF", "region": "China", "purpose": "NDA filing"}]

    # Analysis Populations - Protocol-Specific Definitions (NEW)
    itt_definition: str = ""  # Protocol's exact ITT definition
    pp_definition: str = ""   # Protocol's exact PP definition
    safety_definition: str = ""  # Protocol's exact Safety population definition
    fas_definition: str = ""  # Protocol's exact FAS definition (if different from ITT)

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
  "nct_id": "NCT ID of THIS study only (NOT reference studies). Look for the NCT ID associated with the protocol title, study ID, or CA209-xxx number. If multiple NCT IDs appear, identify which one belongs to THIS protocol.",
  "protocol_title": "Full title of the study",
  "sponsor": "Sponsor company/organization",
  "phase": "Phase 1, Phase 2, Phase 3, Phase 4, or Phase 1/2, etc.",
  "design_type": "randomized, single-arm, crossover, parallel-group, etc.",
  "is_randomized": true or false,
  "is_blinded": true or false,
  "blinding_type": "double-blind, single-blind, open-label, or empty",
  "is_pilot_study": true or false (true if explicitly described as pilot, feasibility, exploratory, hypothesis-generating, or if no formal power calculation),
  "sample_size": number (total planned enrollment),
  "sample_size_justification": "formal_power_calculation OR pragmatic OR feasibility (indicate which type)",
  "num_arms": number of treatment arms,
  "arms": [
    {{"name": "Arm A", "treatment": "Drug X 100mg", "n": 50}},
    {{"name": "Arm B", "treatment": "Placebo", "n": 50}}
  ],
  "randomization_ratio": "1:1, 2:1, etc. or empty if not randomized",
  "drug_name": "Primary study drug/investigational product name",
  "comparator": "Comparator drug or placebo if applicable",

  "primary_endpoints": [
    {{
      "definition": "Full definition of the primary endpoint",
      "type": "safety OR efficacy OR tumor_response OR feasibility OR pk",
      "timepoint": "When measured (e.g., Week 12, at surgery)",
      "criteria": "Assessment criteria if applicable (e.g., RECIST 1.1, NCI-CTCAE v4.03)"
    }}
  ],
  "secondary_endpoints": ["List of secondary endpoints"],

  "response_criteria": "For oncology: RECIST 1.1, mRECIST, iRECIST, Lugano, IMWG, ELN, etc. Empty if not oncology.",
  "pathologic_response_criteria": "Pathologic grading system if mentioned (Junker, Miller-Payne, TRG, pCR definition, etc.)",
  "response_assessor": "Who assesses response: investigator, IRRC, BICR, central review",

  "statistical_method": "Primary statistical analysis method (e.g., log-rank, MMRM, Cox regression)",
  "statistical_method_details": "Full method specification including weights/parameters (e.g., 'Fleming-Harrington weighted log-rank G(rho=0, gamma=1)', 'stratified log-rank')",
  "alpha_level": 0.05 (significance level as decimal),
  "power": 0.80 (statistical power as decimal if mentioned, 0 if no formal power calculation),
  "hypothesis_testing_planned": true or false (false if pilot/feasibility study with only descriptive statistics),

  "has_interim_analysis": true or false,
  "num_interim_analyses": number of planned interim analyses (0 if none),
  "interim_analysis_method": "Lan-DeMets, O'Brien-Fleming, Pocock, Haybittle-Peto, or other",
  "error_spending_function": "Alpha spending function details if specified (e.g., 'rho=1', 'gamma=-4')",
  "interim_events": [number of events at each interim analysis],
  "final_events": number of events at final analysis,

  "has_consistency_objective": true or false (true if study must show consistency with prior studies),
  "consistency_margin": "HR upper bound or margin for consistency (e.g., 'HR < 1.29', 'delta = 0.1')",
  "consistency_reference_studies": ["Names of reference studies for consistency check (e.g., 'CheckMate 057', 'CheckMate 017')"],

  "regulatory_endpoints": [
    {{"endpoint": "TTF or other regulatory-specific endpoint", "region": "China, Japan, EU, etc.", "purpose": "NDA filing, bridging study, etc."}}
  ],

  "itt_definition": "Protocol's exact definition of Intent-to-Treat or Full Analysis Set population",
  "pp_definition": "Protocol's exact definition of Per-Protocol population",
  "safety_definition": "Protocol's exact definition of Safety population",

  "therapeutic_area": "oncology, immunology, cardiology, etc.",
  "indication": "Specific disease/condition being studied",
  "stratification_factors": ["List of stratification factors if randomized"],
  "confidence": 0.0 to 1.0 (your confidence in the extraction accuracy)
}}

IMPORTANT RULES:
1. Extract ONLY what is explicitly stated in the document
2. If a field is not found, use empty string "" or 0 or empty array []
3. CRITICAL for nct_id: Many protocols mention REFERENCE studies (prior trials, supporting data). You MUST identify the NCT ID for THIS specific study:
   - Look for NCT ID near: protocol title, sponsor ID (e.g., CA209-xxx), "this study", "current trial"
   - IGNORE NCT IDs mentioned with: "prior study", "reference", "CheckMate 057", "similar to", "consistent with"
   - IGNORE NCT IDs listed together (e.g., "NCT01234567 and NCT02345678") - those are usually references
   - If you see "CA209-078" or similar sponsor protocol number, find the NCT ID associated with THAT number
4. For primary_endpoints, extract ALL co-primary endpoints - many studies have 2-3 (e.g., safety + efficacy + tumor response)
5. For each primary endpoint, classify its TYPE: safety (AE rates), efficacy (clinical benefit), tumor_response (RECIST/pathologic), feasibility (compliance), pk (pharmacokinetic)
6. For drug_name, identify the investigational product, not standard of care
7. Set is_pilot_study=true if: no formal power calculation, described as pilot/feasibility/exploratory, or sample size justified by pragmatic/feasibility rationale
8. Set hypothesis_testing_planned=false for pilot studies - they use descriptive statistics only
9. For oncology studies, extract response_criteria (RECIST version) and pathologic_response_criteria if tumor assessment is an endpoint
10. STATISTICAL METHOD: Extract FULL specification including:
    - Weighted tests: "Fleming-Harrington G(rho=X, gamma=Y)", "Gehan-Wilcoxon"
    - Stratification: "stratified log-rank by X, Y, Z"
    - Parameters: any rho, gamma, or other weighting parameters
11. INTERIM ANALYSIS: Look for Lan-DeMets, O'Brien-Fleming, alpha-spending functions. Extract:
    - Number of interim analyses
    - Events/deaths at each analysis
    - Error spending function parameters (rho, gamma values)
12. CONSISTENCY OBJECTIVES: If the study must demonstrate "consistency" with prior trials:
    - Set has_consistency_objective=true
    - Extract the consistency margin (e.g., "HR upper bound < 1.29")
    - List the reference studies (e.g., "CheckMate 057", "CheckMate 017")
13. REGULATORY ENDPOINTS: Look for endpoints required for specific regions (China NDA, Japan PMDA):
    - TTF (Time to Treatment Failure) for China
    - Any bridging study endpoints
14. Return ONLY the JSON object, no explanations

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
        result.is_pilot_study = bool(response.get("is_pilot_study", False))

        # Sample
        result.sample_size = int(response.get("sample_size", 0) or 0)
        result.sample_size_justification = response.get("sample_size_justification", "") or ""

        # Arms
        result.num_arms = int(response.get("num_arms", 0) or 0)
        result.arms = response.get("arms", []) or []
        result.randomization_ratio = response.get("randomization_ratio", "") or ""

        # Drug
        result.drug_name = response.get("drug_name", "") or ""
        result.comparator = response.get("comparator", "") or ""

        # Endpoints - NEW: Support multiple co-primary endpoints
        result.primary_endpoints = response.get("primary_endpoints", []) or []
        result.secondary_endpoints = response.get("secondary_endpoints", []) or []

        # Backwards compatibility: populate deprecated single-value fields
        if result.primary_endpoints:
            first_endpoint = result.primary_endpoints[0]
            result.primary_endpoint = first_endpoint.get("definition", "") if isinstance(first_endpoint, dict) else str(first_endpoint)
            result.primary_timepoint = first_endpoint.get("timepoint", "") if isinstance(first_endpoint, dict) else ""
        else:
            # Fallback to old format if LLM returns old format
            result.primary_endpoint = response.get("primary_endpoint", "") or ""
            result.primary_timepoint = response.get("primary_timepoint", "") or ""
            # Convert old format to new format
            if result.primary_endpoint:
                result.primary_endpoints = [{
                    "definition": result.primary_endpoint,
                    "type": "efficacy",  # Default, will be inferred
                    "timepoint": result.primary_timepoint,
                    "criteria": ""
                }]

        # Oncology Response Criteria (NEW)
        result.response_criteria = response.get("response_criteria", "") or ""
        result.pathologic_response_criteria = response.get("pathologic_response_criteria", "") or ""
        result.response_assessor = response.get("response_assessor", "") or ""

        # Statistical - ENHANCED
        result.statistical_method = response.get("statistical_method", "") or ""
        result.statistical_method_details = response.get("statistical_method_details", "") or ""
        result.alpha_level = float(response.get("alpha_level", 0.05) or 0.05)
        result.power = float(response.get("power", 0) or 0)
        result.hypothesis_testing_planned = bool(response.get("hypothesis_testing_planned", True))

        # Interim Analysis (NEW)
        result.has_interim_analysis = bool(response.get("has_interim_analysis", False))
        result.num_interim_analyses = int(response.get("num_interim_analyses", 0) or 0)
        result.interim_analysis_method = response.get("interim_analysis_method", "") or ""
        result.error_spending_function = response.get("error_spending_function", "") or ""
        result.interim_events = response.get("interim_events", []) or []
        result.final_events = int(response.get("final_events", 0) or 0)

        # Consistency Objectives (NEW)
        result.has_consistency_objective = bool(response.get("has_consistency_objective", False))
        result.consistency_margin = response.get("consistency_margin", "") or ""
        result.consistency_reference_studies = response.get("consistency_reference_studies", []) or []

        # Regulatory Endpoints (NEW)
        result.regulatory_endpoints = response.get("regulatory_endpoints", []) or []

        # Population Definitions (NEW)
        result.itt_definition = response.get("itt_definition", "") or ""
        result.pp_definition = response.get("pp_definition", "") or ""
        result.safety_definition = response.get("safety_definition", "") or ""
        result.fas_definition = response.get("fas_definition", "") or ""

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

        # Infer pilot study from various indicators
        if not result.is_pilot_study:
            pilot_indicators = [
                "pilot" in result.design_type.lower(),
                "feasibility" in result.design_type.lower(),
                "exploratory" in result.design_type.lower(),
                result.sample_size_justification.lower() in ["pragmatic", "feasibility"],
                result.power == 0 and result.sample_size < 50,  # Small study with no power calc
                "phase 1" in result.phase.lower() and not result.is_randomized,
            ]
            result.is_pilot_study = any(pilot_indicators)

        # If pilot study, hypothesis testing should be false
        if result.is_pilot_study:
            result.hypothesis_testing_planned = False

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
