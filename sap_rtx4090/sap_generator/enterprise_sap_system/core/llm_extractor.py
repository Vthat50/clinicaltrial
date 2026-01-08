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
class InterimAnalysisDetails:
    """Detailed interim analysis parameters"""
    num_interim_analyses: int = 0  # e.g., 3 IAs + 1 FA = 4 total
    interim_timing: List[Dict[str, Any]] = field(default_factory=list)  # [{ia: 1, months: 27, events: 354, endpoint: "PFS"}, ...]
    alpha_spending_function: str = ""  # e.g., "Lan-DeMets O'Brien-Fleming"
    alpha_pfs: str = ""  # e.g., "0.005 one-sided"
    alpha_os: str = ""  # e.g., "0.02 one-sided"
    efficacy_boundaries: List[Dict[str, Any]] = field(default_factory=list)  # [{ia: 1, z_score: 4.33, p_value: 0.003, hr: 0.65}, ...]
    futility_boundaries: List[Dict[str, Any]] = field(default_factory=list)
    final_analysis_timing: Dict[str, Any] = field(default_factory=dict)  # {months: 48, events: 359}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_interim_analyses": self.num_interim_analyses,
            "interim_timing": self.interim_timing,
            "alpha_spending_function": self.alpha_spending_function,
            "alpha_pfs": self.alpha_pfs,
            "alpha_os": self.alpha_os,
            "efficacy_boundaries": self.efficacy_boundaries,
            "futility_boundaries": self.futility_boundaries,
            "final_analysis_timing": self.final_analysis_timing,
        }


@dataclass
class PowerCalculationDetails:
    """Detailed power calculation parameters"""
    pfs_power: str = ""  # e.g., "90% for HR 0.7"
    os_superiority_power: str = ""  # e.g., "90% for HR 0.7"
    os_ni_power: str = ""  # e.g., "82% for HR 0.8"
    control_median_pfs: str = ""  # e.g., "8.8 months"
    control_median_os: str = ""  # e.g., "23 months"
    assumed_hr: str = ""  # e.g., "0.7"
    dropout_rate: str = ""  # e.g., "10%"
    accrual_period: str = ""  # e.g., "24 months"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pfs_power": self.pfs_power,
            "os_superiority_power": self.os_superiority_power,
            "os_ni_power": self.os_ni_power,
            "control_median_pfs": self.control_median_pfs,
            "control_median_os": self.control_median_os,
            "assumed_hr": self.assumed_hr,
            "dropout_rate": self.dropout_rate,
            "accrual_period": self.accrual_period,
        }


@dataclass
class ExploratoryEndpointsDetails:
    """Detailed exploratory endpoints"""
    dor: str = ""  # Duration of Response
    dcr: str = ""  # Disease Control Rate
    cbr: str = ""  # Clinical Benefit Rate
    pfs2: str = ""  # Time to 2nd progression
    irecist_endpoints: List[str] = field(default_factory=list)
    biomarker_endpoints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dor": self.dor,
            "dcr": self.dcr,
            "cbr": self.cbr,
            "pfs2": self.pfs2,
            "irecist_endpoints": self.irecist_endpoints,
            "biomarker_endpoints": self.biomarker_endpoints,
        }


@dataclass
class PRODetails:
    """Patient-Reported Outcomes specific thresholds"""
    primary_timepoint: str = ""  # e.g., "Week 18"
    completion_threshold: str = ""  # e.g., "≥60%"
    compliance_threshold: str = ""  # e.g., "≥80%"
    improvement_definition: str = ""  # e.g., "≥10-point increase"
    stability_definition: str = ""  # e.g., "<10-point worsening"
    instruments: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_timepoint": self.primary_timepoint,
            "completion_threshold": self.completion_threshold,
            "compliance_threshold": self.compliance_threshold,
            "improvement_definition": self.improvement_definition,
            "stability_definition": self.stability_definition,
            "instruments": self.instruments,
        }


@dataclass
class RegionalExtensionDetails:
    """Regional extension specifics (e.g., China)"""
    china_sample_size: str = ""  # e.g., "131 (92 pMMR + 39 dMMR)"
    china_pfs_events: str = ""  # e.g., "71 events"
    china_os_events: str = ""  # e.g., "54 events"
    consistency_criterion: str = ""  # e.g., "≥50% risk reduction preserved"
    other_regional: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "china_sample_size": self.china_sample_size,
            "china_pfs_events": self.china_pfs_events,
            "china_os_events": self.china_os_events,
            "consistency_criterion": self.consistency_criterion,
            "other_regional": self.other_regional,
        }


@dataclass
class CensoringRules:
    """Censoring rules for time-to-event endpoints"""
    dor_censoring: List[str] = field(default_factory=list)  # Duration of Response censoring rules
    pfs_censoring: List[str] = field(default_factory=list)
    pfs2_censoring: List[str] = field(default_factory=list)  # PFS2 events and censoring
    os_censoring: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dor_censoring": self.dor_censoring,
            "pfs_censoring": self.pfs_censoring,
            "pfs2_censoring": self.pfs2_censoring,
            "os_censoring": self.os_censoring,
        }


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

    # === NEW: Detailed extraction for missing elements ===
    interim_analysis: InterimAnalysisDetails = field(default_factory=InterimAnalysisDetails)
    power_calculations: PowerCalculationDetails = field(default_factory=PowerCalculationDetails)
    exploratory_endpoints: ExploratoryEndpointsDetails = field(default_factory=ExploratoryEndpointsDetails)
    pro_details: PRODetails = field(default_factory=PRODetails)
    regional_extensions: RegionalExtensionDetails = field(default_factory=RegionalExtensionDetails)
    censoring_rules: CensoringRules = field(default_factory=CensoringRules)

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
            # NEW: Detailed extraction fields
            "interim_analysis": self.interim_analysis.to_dict(),
            "power_calculations": self.power_calculations.to_dict(),
            "exploratory_endpoints": self.exploratory_endpoints.to_dict(),
            "pro_details": self.pro_details.to_dict(),
            "regional_extensions": self.regional_extensions.to_dict(),
            "censoring_rules": self.censoring_rules.to_dict(),
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

    # === NEW: Specialized prompts for missing elements ===

    INTERIM_ANALYSIS_PROMPT = """Extract ALL interim analysis details from this clinical trial protocol.

CRITICAL: Extract EXACT numeric values, not descriptions.

Return ONLY valid JSON:
{
    "num_interim_analyses": 3,  // EXACT count of interim analyses (not including final)
    "interim_timing": [
        {"ia": 1, "months": 27, "events": 354, "endpoint": "PFS", "population": "pMMR"},
        {"ia": 2, "months": 36, "events": 472, "endpoint": "PFS", "population": "pMMR"},
        {"ia": 3, "months": 42, "events": 316, "endpoint": "OS", "population": "pMMR"}
    ],
    "final_analysis_timing": {"months": 48, "events": 359, "endpoint": "OS"},
    "alpha_spending_function": "Lan-DeMets O'Brien-Fleming",
    "alpha_pfs": "0.005 one-sided",
    "alpha_os": "0.02 one-sided",
    "efficacy_boundaries": [
        {"ia": 1, "z_score": 4.33, "p_value": 0.003, "hr_boundary": 0.65, "info_fraction": 0.50},
        {"ia": 2, "z_score": 2.96, "p_value": 0.0015, "hr_boundary": 0.72, "info_fraction": 0.75}
    ],
    "futility_boundaries": [
        {"ia": 1, "conditional_power_threshold": 0.20, "hr_threshold": 0.95}
    ],
    "confidence": 0.0 to 1.0
}

Protocol text:
{text}

Return ONLY the JSON, no other text."""

    POWER_CALCULATION_PROMPT = """Extract ALL power calculation and sample size assumptions from this protocol.

Return ONLY valid JSON:
{
    "pfs_power": "90% for HR 0.7",
    "os_superiority_power": "90% for HR 0.7",
    "os_ni_power": "82% for HR 0.8",
    "control_median_pfs": "8.8 months",
    "control_median_os": "23 months",
    "treatment_median_pfs": "12.6 months",
    "treatment_median_os": "32.9 months",
    "assumed_hr": "0.7",
    "ni_margin": "1.1",
    "dropout_rate": "10%",
    "accrual_period": "24 months",
    "total_events_pfs": 472,
    "total_events_os": 359,
    "total_sample_size": 500,
    "confidence": 0.0 to 1.0
}

Protocol text:
{text}

Return ONLY the JSON, no other text."""

    EXPLORATORY_ENDPOINTS_PROMPT = """Extract ALL exploratory endpoints from this protocol.

Return ONLY valid JSON:
{
    "dor": "Duration of Response by BICR using RECIST 1.1",
    "dcr": "Disease Control Rate (CR + PR + SD ≥6 weeks)",
    "cbr": "Clinical Benefit Rate",
    "pfs2": "Time from randomization to second disease progression or death",
    "ttd": "Time to deterioration",
    "irecist_endpoints": ["iPFS", "iORR", "iDOR"],
    "biomarker_endpoints": ["PD-L1 status", "TMB", "MSI status"],
    "pharmacokinetic_endpoints": ["Cmax", "AUC", "Trough"],
    "confidence": 0.0 to 1.0
}

Protocol text:
{text}

Return ONLY the JSON, no other text."""

    PRO_DETAILS_PROMPT = """Extract Patient-Reported Outcomes (PRO) analysis details from this protocol.

Return ONLY valid JSON:
{
    "primary_timepoint": "Week 18",
    "completion_threshold": "≥60%",
    "compliance_threshold": "≥80%",
    "improvement_definition": "≥10-point increase from baseline",
    "stability_definition": "<10-point worsening from baseline",
    "instruments": ["EORTC QLQ-C30", "EQ-5D-5L", "FACT-G"],
    "mcid": {"QLQ-C30": "10 points", "EQ-5D-5L": "0.08"},
    "analysis_method": "MMRM with treatment, visit, treatment*visit, baseline as covariates",
    "missing_data_approach": "Pattern mixture model sensitivity analysis",
    "confidence": 0.0 to 1.0
}

Protocol text:
{text}

Return ONLY the JSON, no other text."""

    REGIONAL_EXTENSION_PROMPT = """Extract regional extension details (China, Japan, etc.) from this protocol.

Return ONLY valid JSON:
{
    "china_extension": {
        "sample_size": "131 (92 pMMR + 39 dMMR)",
        "pfs_events": "71 events",
        "os_events": "54 events",
        "consistency_criterion": "≥50% risk reduction preserved",
        "primary_endpoint": "PFS by BICR"
    },
    "japan_extension": {
        "sample_size": "",
        "pmda_requirements": ""
    },
    "other_regional": {},
    "confidence": 0.0 to 1.0
}

Protocol text:
{text}

Return ONLY the JSON, no other text."""

    CENSORING_RULES_PROMPT = """Extract ALL censoring rules for time-to-event endpoints from this protocol.

Return ONLY valid JSON:
{
    "pfs_censoring": [
        {"scenario": "No progression, no death", "censoring": "Date of last adequate tumor assessment"},
        {"scenario": "New anticancer therapy before progression", "censoring": "Last assessment before new therapy"},
        {"scenario": "Death without prior progression", "event_type": "Event at date of death"},
        {"scenario": "Two or more missed assessments", "censoring": "Last adequate assessment before gap"}
    ],
    "os_censoring": [
        {"scenario": "Alive at data cutoff", "censoring": "Last known alive date"},
        {"scenario": "Lost to follow-up", "censoring": "Last contact date"}
    ],
    "dor_censoring": [
        {"scenario": "Ongoing response", "censoring": "Date of last adequate assessment"},
        {"scenario": "Death before progression", "event_type": "Event at date of death"}
    ],
    "pfs2_censoring": [
        {"scenario": "No second progression", "censoring": "Date of last follow-up for progression"}
    ],
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

    def extract(self, text: str, include_windows: bool = True,
                include_interim: bool = True, include_power: bool = True,
                include_exploratory: bool = True, include_pro: bool = True,
                include_regional: bool = True, include_censoring: bool = True) -> LLMExtractedFacts:
        """
        Extract statistical methodology from text.

        Args:
            text: Protocol section text (ideally statistical methods section)
            include_windows: Also extract visit windows
            include_interim: Extract interim analysis details (NEW)
            include_power: Extract power calculation details (NEW)
            include_exploratory: Extract exploratory endpoints (NEW)
            include_pro: Extract PRO details (NEW)
            include_regional: Extract regional extension details (NEW)
            include_censoring: Extract censoring rules (NEW)

        Returns:
            LLMExtractedFacts with all extracted details
        """
        facts = LLMExtractedFacts()

        if not self.llm:
            facts.error = "LLM client not available"
            return facts

        if not text or len(text) < 50:
            facts.error = "Text too short for extraction"
            return facts

        # Use larger context for full protocol extraction
        max_chars = 50000  # Increased for modern LLMs with large context
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...[truncated]"

        try:
            # Extract main methodology
            facts = self._extract_methodology(text, facts)

            # Extract visit windows if requested
            if include_windows:
                facts = self._extract_windows(text, facts)

            # === NEW: Extract detailed elements ===
            if include_interim and self._has_interim_indicators(text):
                facts = self._extract_interim_analysis(text, facts)

            if include_power:
                facts = self._extract_power_calculations(text, facts)

            if include_exploratory:
                facts = self._extract_exploratory_endpoints(text, facts)

            if include_pro and self._has_pro_indicators(text):
                facts = self._extract_pro_details(text, facts)

            if include_regional and self._has_regional_indicators(text):
                facts = self._extract_regional_extensions(text, facts)

            if include_censoring and self._has_tte_indicators(text):
                facts = self._extract_censoring_rules(text, facts)

            facts.extraction_success = True

        except Exception as e:
            facts.error = f"Extraction failed: {str(e)}"

        return facts

    def _has_interim_indicators(self, text: str) -> bool:
        """Check if text contains interim analysis indicators"""
        indicators = ['interim analysis', 'interim analyses', 'alpha spending',
                      'stopping boundary', 'information fraction', 'DSMB', 'DMC']
        text_lower = text.lower()
        return any(ind in text_lower for ind in indicators)

    def _has_pro_indicators(self, text: str) -> bool:
        """Check if text contains PRO indicators"""
        indicators = ['patient-reported', 'quality of life', 'qol', 'eortc',
                      'eq-5d', 'fact-', 'pro analysis', 'patient reported']
        text_lower = text.lower()
        return any(ind in text_lower for ind in indicators)

    def _has_regional_indicators(self, text: str) -> bool:
        """Check if text contains regional extension indicators"""
        indicators = ['china extension', 'china cohort', 'japan extension',
                      'pmda', 'nmpa', 'regional analysis', 'local regulatory']
        text_lower = text.lower()
        return any(ind in text_lower for ind in indicators)

    def _has_tte_indicators(self, text: str) -> bool:
        """Check if text contains time-to-event indicators"""
        indicators = ['survival', 'pfs', 'efs', 'dfs', 'os', 'time to event',
                      'kaplan-meier', 'cox', 'censoring', 'hazard']
        text_lower = text.lower()
        return any(ind in text_lower for ind in indicators)

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

    # === NEW: Extraction methods for missing elements ===

    def _extract_interim_analysis(self, text: str, facts: LLMExtractedFacts) -> LLMExtractedFacts:
        """Extract detailed interim analysis parameters"""
        prompt = self.INTERIM_ANALYSIS_PROMPT.format(text=text)

        result, source = self.llm.chat_json(
            prompt=prompt,
            system_prompt="You are extracting interim analysis details from a clinical trial protocol. Extract EXACT numeric values.",
            temperature=0.1
        )

        if result:
            facts.interim_analysis = InterimAnalysisDetails(
                num_interim_analyses=result.get("num_interim_analyses", 0),
                interim_timing=result.get("interim_timing", []),
                alpha_spending_function=result.get("alpha_spending_function", ""),
                alpha_pfs=result.get("alpha_pfs", ""),
                alpha_os=result.get("alpha_os", ""),
                efficacy_boundaries=result.get("efficacy_boundaries", []),
                futility_boundaries=result.get("futility_boundaries", []),
                final_analysis_timing=result.get("final_analysis_timing", {})
            )
            print(f"  [LLMExtractor] Extracted interim analysis: {facts.interim_analysis.num_interim_analyses} IAs")

        return facts

    def _extract_power_calculations(self, text: str, facts: LLMExtractedFacts) -> LLMExtractedFacts:
        """Extract power calculation details"""
        prompt = self.POWER_CALCULATION_PROMPT.format(text=text)

        result, _ = self.llm.chat_json(
            prompt=prompt,
            system_prompt="You are extracting sample size and power calculation details. Extract EXACT values.",
            temperature=0.1
        )

        if result:
            facts.power_calculations = PowerCalculationDetails(
                pfs_power=result.get("pfs_power", ""),
                os_superiority_power=result.get("os_superiority_power", ""),
                os_ni_power=result.get("os_ni_power", ""),
                control_median_pfs=result.get("control_median_pfs", ""),
                control_median_os=result.get("control_median_os", ""),
                assumed_hr=result.get("assumed_hr", ""),
                dropout_rate=result.get("dropout_rate", ""),
                accrual_period=result.get("accrual_period", "")
            )
            print(f"  [LLMExtractor] Extracted power calculations: PFS power={facts.power_calculations.pfs_power}")

        return facts

    def _extract_exploratory_endpoints(self, text: str, facts: LLMExtractedFacts) -> LLMExtractedFacts:
        """Extract exploratory endpoints"""
        prompt = self.EXPLORATORY_ENDPOINTS_PROMPT.format(text=text)

        result, _ = self.llm.chat_json(
            prompt=prompt,
            temperature=0.1
        )

        if result:
            facts.exploratory_endpoints = ExploratoryEndpointsDetails(
                dor=result.get("dor", ""),
                dcr=result.get("dcr", ""),
                cbr=result.get("cbr", ""),
                pfs2=result.get("pfs2", ""),
                irecist_endpoints=result.get("irecist_endpoints", []),
                biomarker_endpoints=result.get("biomarker_endpoints", [])
            )
            print(f"  [LLMExtractor] Extracted exploratory endpoints: DOR={bool(facts.exploratory_endpoints.dor)}, PFS2={bool(facts.exploratory_endpoints.pfs2)}")

        return facts

    def _extract_pro_details(self, text: str, facts: LLMExtractedFacts) -> LLMExtractedFacts:
        """Extract PRO analysis details"""
        prompt = self.PRO_DETAILS_PROMPT.format(text=text)

        result, _ = self.llm.chat_json(
            prompt=prompt,
            temperature=0.1
        )

        if result:
            facts.pro_details = PRODetails(
                primary_timepoint=result.get("primary_timepoint", ""),
                completion_threshold=result.get("completion_threshold", ""),
                compliance_threshold=result.get("compliance_threshold", ""),
                improvement_definition=result.get("improvement_definition", ""),
                stability_definition=result.get("stability_definition", ""),
                instruments=result.get("instruments", [])
            )
            print(f"  [LLMExtractor] Extracted PRO details: timepoint={facts.pro_details.primary_timepoint}, instruments={len(facts.pro_details.instruments)}")

        return facts

    def _extract_regional_extensions(self, text: str, facts: LLMExtractedFacts) -> LLMExtractedFacts:
        """Extract regional extension details"""
        prompt = self.REGIONAL_EXTENSION_PROMPT.format(text=text)

        result, _ = self.llm.chat_json(
            prompt=prompt,
            temperature=0.1
        )

        if result:
            china = result.get("china_extension", {})
            facts.regional_extensions = RegionalExtensionDetails(
                china_sample_size=china.get("sample_size", ""),
                china_pfs_events=china.get("pfs_events", ""),
                china_os_events=china.get("os_events", ""),
                consistency_criterion=china.get("consistency_criterion", ""),
                other_regional=result.get("other_regional", {})
            )
            print(f"  [LLMExtractor] Extracted regional extensions: China N={facts.regional_extensions.china_sample_size}")

        return facts

    def _extract_censoring_rules(self, text: str, facts: LLMExtractedFacts) -> LLMExtractedFacts:
        """Extract censoring rules for TTE endpoints"""
        prompt = self.CENSORING_RULES_PROMPT.format(text=text)

        result, _ = self.llm.chat_json(
            prompt=prompt,
            temperature=0.1
        )

        if result:
            facts.censoring_rules = CensoringRules(
                dor_censoring=result.get("dor_censoring", []),
                pfs_censoring=result.get("pfs_censoring", []),
                pfs2_censoring=result.get("pfs2_censoring", []),
                os_censoring=result.get("os_censoring", [])
            )
            print(f"  [LLMExtractor] Extracted censoring rules: PFS={len(facts.censoring_rules.pfs_censoring)}, DOR={len(facts.censoring_rules.dor_censoring)}")

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
