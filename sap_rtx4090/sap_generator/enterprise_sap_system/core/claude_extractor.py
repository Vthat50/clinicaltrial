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

    # Interim Analysis - COMPREHENSIVE for SAP documents
    has_interim_analysis: bool = False
    num_interim_analyses: int = 0
    interim_analysis_method: str = ""  # "Lan-DeMets", "O'Brien-Fleming", "Pocock", "Haybittle-Peto"
    error_spending_function: str = ""  # e.g., "Lan-DeMets with rho=1", "O'Brien-Fleming-like"
    alpha_spending_params: str = ""  # e.g., "rho=1", "gamma=-4"
    interim_events: List[int] = field(default_factory=list)  # Events at each interim
    interim_alpha_spent: List[float] = field(default_factory=list)  # Alpha spent at each interim (e.g., [0.0001, 0.05])
    interim_information_fraction: List[float] = field(default_factory=list)  # Info fraction at each interim
    final_events: int = 0  # Events at final analysis
    stopping_boundaries: str = ""  # e.g., "One-sided p<0.0001 at interim, p<0.0499 at final"

    # Hierarchical Testing Procedure - CRITICAL for multi-objective studies
    has_hierarchical_testing: bool = False
    hierarchical_testing_order: List[str] = field(default_factory=list)  # Order of tests
    # e.g., ["consistency_check", "primary_efficacy", "secondary_ORR", "secondary_PFS"]
    hierarchical_testing_description: str = ""  # Full description of procedure

    # Consistency/Non-Inferiority/Bridging Objectives - ENHANCED
    has_consistency_objective: bool = False  # True if comparing to prior studies
    consistency_type: str = ""  # "consistency", "non-inferiority", "bridging", "regional"
    consistency_margin: str = ""  # e.g., "HR upper bound < 1.29", "lower bound of 95% CI > 0.5"
    consistency_reference_studies: List[str] = field(default_factory=list)  # e.g., ["CheckMate 057", "CheckMate 017"]
    consistency_reference_effect: str = ""  # e.g., "pooled HR of 0.68"
    consistency_test_description: str = ""  # Full description of how consistency is tested
    consistency_is_primary: bool = False  # True if consistency is a PRIMARY objective (not secondary)

    # Regulatory-Specific Endpoints - ENHANCED
    regulatory_endpoints: List[Dict[str, str]] = field(default_factory=list)
    # e.g., [{"endpoint": "TTF", "region": "China", "purpose": "NDA filing", "definition": "..."}]
    is_bridging_study: bool = False  # True if this is a regional bridging study
    target_regions: List[str] = field(default_factory=list)  # e.g., ["China", "Japan"]

    # REGULATORY INTERIM ANALYSIS - For regional filings (e.g., TTF interim for China NDA)
    has_regulatory_interim: bool = False
    regulatory_interim_endpoint: str = ""  # e.g., "TTF"
    regulatory_interim_region: str = ""  # e.g., "China"
    regulatory_interim_purpose: str = ""  # e.g., "support early filing in China"
    regulatory_interim_timing: str = ""  # e.g., "~380 subjects with 8 months follow-up"
    regulatory_interim_alpha: float = 0.025  # Often one-sided
    regulatory_interim_method: str = ""  # e.g., "One-sided weighted log-rank"
    regulatory_interim_analyses: List[str] = field(default_factory=list)  # What's analyzed at this interim

    # PRO/QoL Endpoints - Patient-Reported Outcomes (NEW)
    pro_endpoints: List[Dict[str, str]] = field(default_factory=list)
    # e.g., [{"instrument": "LCSS", "subscale": "ASBI", "timepoints": ["Week 12", "Week 24"], "responder_definition": ">=10 point increase"}]
    has_pro_endpoint: bool = False
    pro_instruments: List[str] = field(default_factory=list)  # e.g., ["LCSS", "EQ-5D", "EORTC QLQ-C30"]

    # Non-Proportional Hazards Model (for immunotherapy delayed effect)
    has_nph_model: bool = False  # True if protocol assumes delayed treatment effect
    nph_model_type: str = ""  # "piecewise_exponential", "cure_model", "mixture"
    delayed_effect_months: float = 0.0  # e.g., 4.0 for 4-month delay in NSQ PD-L1+
    piecewise_hazards: List[Dict[str, Any]] = field(default_factory=list)
    # e.g., [{"subgroup": "NSQ PD-L1+", "period1_months": 4, "period1_hr": 1.0, "period2_hr": 0.5}]
    subgroup_specific_assumptions: List[Dict[str, Any]] = field(default_factory=list)
    # e.g., [{"subgroup": "Squamous", "control_median_os": 10, "experimental_median_os": 16.7, "hr": 0.6}]

    # Crossover Impact Modeling
    has_crossover_modeling: bool = False
    crossover_rates_modeled: List[float] = field(default_factory=list)  # e.g., [0, 0.05, 0.10, 0.15, 0.20]
    crossover_impact_on_hr: str = ""  # Description of impact

    # Subgroup Analyses Specification
    subgroup_analyses: List[str] = field(default_factory=list)  # Full list of subgroups to analyze
    # e.g., ["Age (<65, 65-<75, ≥75)", "Chinese vs Non-Chinese", "PD-L1 status", ...]

    # Document Type Detection
    document_type: str = ""  # "protocol", "sap", "csr", "unknown"

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


EXTRACTION_PROMPT = '''You are extracting structured information from a clinical trial document (protocol or SAP).

FIRST: Identify the document type by looking for:
- "Statistical Analysis Plan" or "SAP" -> document_type = "sap"
- "Protocol" without SAP -> document_type = "protocol"
- SAP documents have detailed statistical methods sections with interim analysis, multiplicity, etc.

Extract the following fields and return ONLY valid JSON (no other text):

{{
  "document_type": "protocol OR sap OR csr OR unknown",
  "nct_id": "NCT ID of THIS study only (NOT reference studies). Look for NCT ID near protocol title, sponsor ID (CA209-xxx), or 'this study'.",
  "protocol_title": "Full title of the study",
  "sponsor": "Sponsor company/organization",
  "phase": "Phase 1, Phase 2, Phase 3, Phase 4, or Phase 1/2, etc.",
  "design_type": "randomized, single-arm, crossover, parallel-group, etc.",
  "is_randomized": true or false,
  "is_blinded": true or false,
  "blinding_type": "double-blind, single-blind, open-label, or empty",
  "is_pilot_study": true or false,
  "sample_size": number (total planned enrollment),
  "sample_size_justification": "formal_power_calculation OR pragmatic OR feasibility",
  "num_arms": number of treatment arms,
  "arms": [
    {{"name": "Arm A", "treatment": "Drug X 100mg", "n": 50}},
    {{"name": "Arm B", "treatment": "Comparator", "n": 50}}
  ],
  "randomization_ratio": "1:1, 2:1, etc.",
  "drug_name": "Primary investigational product name",
  "comparator": "Comparator drug (NOT placebo unless it really is placebo)",

  "primary_endpoints": [
    {{
      "definition": "Full definition of the primary endpoint",
      "type": "safety OR efficacy OR tumor_response OR feasibility OR pk",
      "timepoint": "When measured",
      "criteria": "Assessment criteria (RECIST 1.1, CTCAE, etc.)"
    }}
  ],
  "secondary_endpoints": ["List of secondary endpoints including TTF if present"],

  "response_criteria": "RECIST 1.1, mRECIST, iRECIST, Lugano, IMWG, etc.",
  "pathologic_response_criteria": "Junker, Miller-Payne, TRG, pCR definition, etc.",
  "response_assessor": "investigator, IRRC, BICR, central review",

  "statistical_method": "Primary method (log-rank, MMRM, Cox, etc.)",
  "statistical_method_details": "FULL specification: 'Fleming-Harrington G(rho=0, gamma=1)', 'stratified log-rank', weights, parameters",
  "alpha_level": 0.05,
  "power": 0.80 or 0 if not specified,
  "hypothesis_testing_planned": true or false,

  "has_interim_analysis": true or false,
  "num_interim_analyses": number (0 if none),
  "interim_analysis_method": "Lan-DeMets, O'Brien-Fleming, Pocock, Haybittle-Peto, or other",
  "error_spending_function": "Full details: 'Lan-DeMets with rho=1', 'O'Brien-Fleming-like'",
  "alpha_spending_params": "rho=X, gamma=Y, or specific function parameters",
  "interim_events": [events at each interim, e.g., 291],
  "interim_alpha_spent": [alpha spent at each interim, e.g., 0.0001],
  "interim_information_fraction": [info fraction at each interim, e.g., 0.76],
  "final_events": events at final analysis (e.g., 382),
  "stopping_boundaries": "Boundary description: 'p<0.0001 at interim, p<0.0499 at final'",

  "has_hierarchical_testing": true or false (true if tests must be done in specific order),
  "hierarchical_testing_order": ["order of tests, e.g., 'consistency', 'primary_OS', 'secondary_ORR'"],
  "hierarchical_testing_description": "Full description of hierarchical/gatekeeping procedure",

  "has_consistency_objective": true or false (true if must show consistency with prior studies),
  "consistency_type": "consistency, non-inferiority, bridging, regional",
  "consistency_margin": "HR upper bound < 1.29, or lower CI > 0.5, etc.",
  "consistency_reference_studies": ["CheckMate 057", "CheckMate 017", etc.],
  "consistency_reference_effect": "pooled HR of 0.68, or treatment effect from prior studies",
  "consistency_test_description": "How consistency is tested (upper bound of CI must be < X)",
  "consistency_is_primary": true or false (true if consistency is a PRIMARY objective, not just secondary),

  "regulatory_endpoints": [
    {{"endpoint": "TTF", "region": "China", "purpose": "NDA filing", "definition": "time from randomization to..."}}
  ],
  "is_bridging_study": true or false,
  "target_regions": ["China", "Japan", etc.],

  "has_regulatory_interim": true if there's a SEPARATE interim analysis for regional filing (e.g., TTF interim for China),
  "regulatory_interim_endpoint": "TTF or other endpoint for regional interim",
  "regulatory_interim_region": "China, Japan, etc.",
  "regulatory_interim_purpose": "support early filing in China",
  "regulatory_interim_timing": "when ~380 subjects have 8 months follow-up",
  "regulatory_interim_alpha": 0.025 (one-sided alpha for regional interim),
  "regulatory_interim_method": "One-sided weighted log-rank (Fleming-Harrington)",
  "regulatory_interim_analyses": ["TTF", "ORR (descriptive)", "Safety", "Chinese subjects subanalysis"],

  "has_pro_endpoint": true if patient-reported outcomes are measured,
  "pro_endpoints": [
    {{"instrument": "LCSS", "subscale": "ASBI", "timepoints": ["Week 12", "Week 24"], "responder_definition": ">=10 point increase from baseline"}}
  ],
  "pro_instruments": ["LCSS", "EQ-5D", "EORTC QLQ-C30", etc.],

  "has_nph_model": true if non-proportional hazards/delayed effect is assumed,
  "nph_model_type": "piecewise_exponential, cure_model, or mixture",
  "delayed_effect_months": months of delay before treatment effect (e.g., 4.0),
  "piecewise_hazards": [
    {{"subgroup": "NSQ PD-L1+", "period1_months": 4, "period1_hr": 1.0, "period2_hr": 0.5}}
  ],
  "subgroup_specific_assumptions": [
    {{"subgroup": "Squamous", "control_median_os": 10, "experimental_median_os": 16.7, "hr": 0.6, "model": "exponential"}},
    {{"subgroup": "NSQ PD-L1+", "control_median_os": 12, "experimental_median_os": 20, "hr": "NPH", "model": "piecewise", "delay_months": 4}}
  ],

  "has_crossover_modeling": true if crossover impact is modeled,
  "crossover_rates_modeled": [0, 0.05, 0.10, 0.15, 0.20],
  "crossover_impact_on_hr": "Expected HR at 20% crossover: 0.75 interim, 0.73 final",

  "subgroup_analyses": ["Age (<65, 65-<75, ≥75)", "Gender", "Race", "Chinese vs Non-Chinese", "ECOG PS", "Smoking status", "Histology", "PD-L1 status", "Disease stage", "Prior therapy", "CNS metastases"],

  "itt_definition": "Protocol's exact ITT/FAS definition",
  "pp_definition": "Protocol's exact Per-Protocol definition",
  "safety_definition": "Protocol's exact Safety population definition",

  "therapeutic_area": "oncology, immunology, cardiology, etc.",
  "indication": "Specific disease/condition",
  "stratification_factors": ["List of stratification factors"],
  "confidence": 0.0 to 1.0
}}

IMPORTANT RULES:
1. Extract ONLY what is explicitly stated in the document
2. If a field is not found, use empty string "" or 0 or empty array []

3. DOCUMENT TYPE: Identify if this is a SAP (Statistical Analysis Plan) or Protocol
   - SAPs have sections like "Statistical Methods", "Interim Analysis", "Multiplicity"
   - SAPs contain more statistical detail than protocols
   - Set document_type accordingly

4. NCT ID: Many documents mention REFERENCE studies. Extract ONLY the NCT ID for THIS study:
   - Look near: protocol title, sponsor ID (CA209-xxx), "this study"
   - IGNORE: NCT IDs with "prior study", "reference", "consistent with", "CheckMate 057/017"
   - IGNORE: Multiple NCT IDs listed together (those are references)

5. ENDPOINTS: Extract ALL co-primary endpoints. Many studies have 2-3 (safety + efficacy + tumor response)

6. STATISTICAL METHOD: Extract FULL specification:
   - "Fleming-Harrington G(rho=0, gamma=1)" not just "weighted log-rank"
   - "stratified log-rank by histology, PD-L1, ECOG" not just "stratified"
   - Include ALL parameters (rho, gamma, weights)

7. INTERIM ANALYSIS - CRITICAL FOR SAP DOCUMENTS:
   Look for these patterns and extract ALL details:
   - "Lan-DeMets alpha-spending function" -> interim_analysis_method = "Lan-DeMets"
   - "O'Brien-Fleming" or "OF-like" -> interim_analysis_method = "O'Brien-Fleming"
   - "rho = 1" or "gamma = -4" -> alpha_spending_params
   - "291 deaths at interim" -> interim_events = [291]
   - "382 deaths at final" -> final_events = 382
   - "0.01% alpha spent" or "0.0001" -> interim_alpha_spent = [0.0001]
   - "information fraction of 0.76" -> interim_information_fraction = [0.76]
   - "one-sided p < 0.0001" -> stopping_boundaries

8. HIERARCHICAL TESTING - CRITICAL FOR MULTI-OBJECTIVE STUDIES:
   Look for these patterns:
   - "hierarchical testing procedure" -> has_hierarchical_testing = true
   - "gatekeeping strategy" -> has_hierarchical_testing = true
   - "test A first, then B, then C" -> hierarchical_testing_order = ["A", "B", "C"]
   - "consistency must be shown before efficacy" -> order starts with "consistency"

9. CONSISTENCY OBJECTIVES - CRITICAL FOR REGIONAL/BRIDGING STUDIES:
   Look for these patterns:
   - "consistent with CheckMate 057/017" -> has_consistency_objective = true
   - "treatment effect consistent with prior studies" -> has_consistency_objective = true
   - "upper bound of 95% CI < 1.29" -> consistency_margin = "HR upper bound < 1.29"
   - "preserve X% of the effect" -> consistency_margin
   - If consistency is a PRIMARY objective (not secondary) -> consistency_is_primary = true
   - If this is a China/Japan bridging study -> is_bridging_study = true

10. REGULATORY ENDPOINTS:
    - TTF (Time to Treatment Failure) - common for China NDA
    - Look for "required for [region] filing"
    - Extract the full definition

11. REGULATORY INTERIM ANALYSIS - CRITICAL FOR REGIONAL FILINGS:
    Look for SEPARATE interim analyses for regional filing support:
    - "TTF interim analysis" or "TTF analysis for China"
    - "support early filing in China" or "support NDA filing"
    - Different alpha level (often one-sided 0.025)
    - Different timing than OS interim (e.g., "380 subjects with 8 months follow-up")
    - Chinese/non-Chinese subanalysis at this interim
    Set has_regulatory_interim=true and extract all details

12. PRO/PATIENT-REPORTED OUTCOMES - CRITICAL FOR QoL ENDPOINTS:
    Look for these instruments and extract them:
    - LCSS (Lung Cancer Symptom Scale) -> ASBI (Average Symptom Burden Index)
    - EORTC QLQ-C30, QLQ-LC13 (lung cancer module)
    - EQ-5D, SF-36, FACT-L
    - Symptom deterioration definitions (e.g., "≥10 point increase from baseline")
    - PRO assessment timepoints (Week 12, Week 24, etc.)
    Set has_pro_endpoint=true and extract all PRO details

13. NON-PROPORTIONAL HAZARDS - CRITICAL FOR IMMUNOTHERAPY:
    Look for evidence of delayed treatment effect modeling:
    - "piecewise exponential" or "delayed effect" or "lag phase"
    - Different HR assumptions for different time periods
    - Different survival assumptions by subgroup (e.g., SQ vs NSQ PD-L1+)
    - If Fleming-Harrington weighted log-rank is used, has_nph_model is likely true
    - Extract subgroup-specific assumptions: control mOS, experimental mOS, HR, model type
    Set has_nph_model=true if protocol assumes delayed treatment effect

14. CROSSOVER IMPACT MODELING:
    Look for sensitivity analyses modeling crossover from control to experimental arm:
    - "crossover rate of X%"
    - "adjusted for crossover"
    - Table showing HR impact at different crossover rates
    Set has_crossover_modeling=true and extract rates modeled

15. SUBGROUP ANALYSES:
    Extract the FULL list of planned subgroup analyses, especially:
    - Chinese vs Non-Chinese (for Asian bridging studies)
    - Regional subgroups
    - Biomarker subgroups (PD-L1 levels)
    - Age categories (often 3 levels: <65, 65-<75, ≥75)

16. CONSISTENCY AS PRIMARY OBJECTIVE:
    Set consistency_is_primary=true ONLY if:
    - Consistency check is listed as a PRIMARY objective (not secondary)
    - Consistency must be demonstrated BEFORE efficacy (gatekeeping)
    - The PRIMARY hypothesis is about consistency with prior studies
    - Look for: "The primary objective is to demonstrate consistency..."

17. For drug_name: Use investigational product, NOT standard of care/comparator

18. Return ONLY the JSON object, no explanations

DOCUMENT TEXT:
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

        # Interim Analysis - COMPREHENSIVE
        result.has_interim_analysis = bool(response.get("has_interim_analysis", False))
        result.num_interim_analyses = int(response.get("num_interim_analyses", 0) or 0)
        result.interim_analysis_method = response.get("interim_analysis_method", "") or ""
        result.error_spending_function = response.get("error_spending_function", "") or ""
        result.alpha_spending_params = response.get("alpha_spending_params", "") or ""
        result.interim_events = response.get("interim_events", []) or []
        result.interim_alpha_spent = response.get("interim_alpha_spent", []) or []
        result.interim_information_fraction = response.get("interim_information_fraction", []) or []
        result.final_events = int(response.get("final_events", 0) or 0)
        result.stopping_boundaries = response.get("stopping_boundaries", "") or ""

        # Hierarchical Testing (NEW)
        result.has_hierarchical_testing = bool(response.get("has_hierarchical_testing", False))
        result.hierarchical_testing_order = response.get("hierarchical_testing_order", []) or []
        result.hierarchical_testing_description = response.get("hierarchical_testing_description", "") or ""

        # Consistency Objectives - ENHANCED
        result.has_consistency_objective = bool(response.get("has_consistency_objective", False))
        result.consistency_type = response.get("consistency_type", "") or ""
        result.consistency_margin = response.get("consistency_margin", "") or ""
        result.consistency_reference_studies = response.get("consistency_reference_studies", []) or []
        result.consistency_reference_effect = response.get("consistency_reference_effect", "") or ""
        result.consistency_test_description = response.get("consistency_test_description", "") or ""
        result.consistency_is_primary = bool(response.get("consistency_is_primary", False))

        # Regulatory Endpoints - ENHANCED
        result.regulatory_endpoints = response.get("regulatory_endpoints", []) or []
        result.is_bridging_study = bool(response.get("is_bridging_study", False))
        result.target_regions = response.get("target_regions", []) or []

        # REGULATORY INTERIM ANALYSIS - For regional filings (e.g., TTF for China)
        result.has_regulatory_interim = bool(response.get("has_regulatory_interim", False))
        result.regulatory_interim_endpoint = response.get("regulatory_interim_endpoint", "") or ""
        result.regulatory_interim_region = response.get("regulatory_interim_region", "") or ""
        result.regulatory_interim_purpose = response.get("regulatory_interim_purpose", "") or ""
        result.regulatory_interim_timing = response.get("regulatory_interim_timing", "") or ""
        result.regulatory_interim_alpha = float(response.get("regulatory_interim_alpha", 0.025) or 0.025)
        result.regulatory_interim_method = response.get("regulatory_interim_method", "") or ""
        result.regulatory_interim_analyses = response.get("regulatory_interim_analyses", []) or []

        # PRO/QoL Endpoints - Patient-Reported Outcomes
        result.has_pro_endpoint = bool(response.get("has_pro_endpoint", False))
        result.pro_endpoints = response.get("pro_endpoints", []) or []
        result.pro_instruments = response.get("pro_instruments", []) or []

        # Non-Proportional Hazards Model (immunotherapy delayed effect)
        result.has_nph_model = bool(response.get("has_nph_model", False))
        result.nph_model_type = response.get("nph_model_type", "") or ""
        result.delayed_effect_months = float(response.get("delayed_effect_months", 0) or 0)
        result.piecewise_hazards = response.get("piecewise_hazards", []) or []
        result.subgroup_specific_assumptions = response.get("subgroup_specific_assumptions", []) or []

        # Crossover Impact Modeling
        result.has_crossover_modeling = bool(response.get("has_crossover_modeling", False))
        result.crossover_rates_modeled = response.get("crossover_rates_modeled", []) or []
        result.crossover_impact_on_hr = response.get("crossover_impact_on_hr", "") or ""

        # Subgroup Analyses
        result.subgroup_analyses = response.get("subgroup_analyses", []) or []

        # Document Type
        result.document_type = response.get("document_type", "") or ""

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
                "phase 1" in str(result.phase).lower() and not result.is_randomized,
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
