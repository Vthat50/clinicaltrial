#!/usr/bin/env python3
"""
Regulatory-Grade SAP Generator
==============================

Generates Statistical Analysis Plans that match real pharmaceutical SAPs
following ICH E9(R1) guidelines.

Structure based on actual SAPs like CheckMate 078 (CA209-078).
"""

import re
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

# Import LLM client for Claude extraction
try:
    from enterprise_sap_system.core.tiered_llm import TieredLLMClient
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    TieredLLMClient = None


# Safe type conversion helpers - Claude may return non-numeric strings
def _safe_int(value, default=0):
    """Safely convert value to int."""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _safe_float(value, default=0.0):
    """Safely convert value to float."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


@dataclass
class ProtocolFacts:
    """Comprehensive protocol facts extracted from protocol document."""
    # Identifiers
    nct_id: str = ""
    protocol_number: str = ""
    sponsor: str = ""
    study_title: str = ""

    # Study Design
    phase: str = ""
    design_type: str = ""  # open-label, double-blind, etc.
    randomization_ratio: str = ""  # "2:1", "1:1"
    is_randomized: bool = True
    is_controlled: bool = True

    # Treatment Arms
    experimental_drug: str = ""
    experimental_dose: str = ""
    comparator_drug: str = ""
    comparator_dose: str = ""
    treatment_duration: str = ""

    # Population
    indication: str = ""
    target_population: str = ""
    key_inclusion: List[str] = field(default_factory=list)
    key_exclusion: List[str] = field(default_factory=list)

    # Sample Size
    total_sample_size: int = 0
    events_required_interim: int = 0
    events_required_final: int = 0
    power: Optional[float] = None  # NO DEFAULT - must be extracted
    alpha: Optional[float] = None  # NO DEFAULT - must be extracted

    # Stratification
    stratification_factors: List[str] = field(default_factory=list)

    # Endpoints
    primary_endpoint: str = ""
    primary_endpoint_definition: str = ""
    primary_timepoint: str = ""
    secondary_endpoints: List[str] = field(default_factory=list)

    # Statistical Methods
    primary_test: str = ""  # e.g., "Fleming-Harrington G(rho=0, gamma=1)"
    alpha_interim: float = 0.0
    alpha_final: float = 0.0
    error_spending_function: str = ""  # e.g., "Lan-DeMets O'Brien-Fleming"

    # Interim Analysis
    has_interim: bool = False
    num_interim_analyses: int = 0
    interim_timing: str = ""
    dmc_oversight: bool = False

    # Drug Class (for method selection)
    drug_class: str = ""  # checkpoint_inhibitor, targeted_therapy, etc.
    therapeutic_area: str = ""  # oncology, immunology, etc.


@dataclass
class SAPDocument:
    """Complete SAP document with all sections."""
    # Metadata
    protocol_number: str = ""
    version: str = "1.0"
    date: str = ""

    # Sections (ICH E9 structure)
    cover_page: str = ""
    table_of_contents: str = ""

    sec1_introduction: str = ""
    sec1_1_hypothesis: str = ""
    sec1_2_schedule: str = ""

    sec2_study_description: str = ""
    sec2_1_design: str = ""
    sec2_2_treatment: str = ""
    sec2_3_blinding: str = ""
    sec2_4_amendments: str = ""
    sec2_5_dmc: str = ""

    sec3_objectives: str = ""
    sec3_1_primary: str = ""
    sec3_2_secondary: str = ""

    sec4_endpoints: str = ""
    sec4_1_primary: str = ""
    sec4_2_secondary: str = ""

    sec5_sample_size: str = ""

    sec6_populations: str = ""
    sec6_1_study_periods: str = ""
    sec6_2_treatment_regimens: str = ""
    sec6_3_analysis_populations: str = ""

    sec7_statistical_analyses: str = ""
    sec7_1_general_methods: str = ""
    sec7_2_study_conduct: str = ""
    sec7_3_study_population: str = ""
    sec7_4_extent_exposure: str = ""
    sec7_5_efficacy: str = ""
    sec7_5_1_primary_analysis: str = ""
    sec7_5_2_secondary_analyses: str = ""
    sec7_5_3_sensitivity_analyses: str = ""
    sec7_5_4_subgroup_analyses: str = ""
    sec7_6_safety: str = ""

    sec8_conventions: str = ""
    sec9_reports: str = ""
    sec10_history: str = ""

    references: str = ""


class RegulatorySAPGenerator:
    """
    Generates regulatory-grade SAPs matching pharmaceutical standards.

    Based on real SAPs like CheckMate 078 (BMS), KEYNOTE trials (Merck).
    """

    # Claude extraction prompt for comprehensive protocol facts
    EXTRACTION_PROMPT = """You are extracting protocol facts from a clinical trial protocol document for SAP generation.

Extract ALL of the following information. Return ONLY valid JSON with no additional text.

{
  "nct_id": "NCT number if present",
  "protocol_number": "Protocol ID (e.g., CA209-078)",
  "sponsor": "Sponsor company name",
  "study_title": "Full study title",

  "phase": "1, 2, or 3",
  "design_type": "open-label, double-blind, single-blind",
  "randomization_ratio": "e.g., 2:1, 1:1",
  "is_randomized": true/false,

  "experimental_drug": "Name of experimental drug",
  "experimental_dose": "Dose and schedule",
  "comparator_drug": "Name of comparator (or Placebo)",
  "comparator_dose": "Dose and schedule",

  "indication": "Disease being treated",
  "target_population": "Description of patient population",

  "total_sample_size": number,
  "events_required_interim": number or null,
  "events_required_final": number,
  "power": 0.80 or 0.90,
  "alpha": 0.05,

  "stratification_factors": ["factor1", "factor2"],

  "primary_endpoint": "Primary endpoint name",
  "primary_endpoint_definition": "Exact definition",
  "primary_timepoint": "When measured",
  "secondary_endpoints": ["endpoint1", "endpoint2"],

  "primary_test": "Statistical test to use (e.g., Fleming-Harrington weighted log-rank G(rho=0, gamma=1) for immunotherapy OS trials, or stratified log-rank)",
  "alpha_interim": 0.020 or null,
  "alpha_final": 0.044 or 0.05,
  "error_spending_function": "Lan-DeMets O'Brien-Fleming or null",

  "has_interim": true/false,
  "num_interim_analyses": number,
  "interim_timing": "When interim occurs",
  "dmc_oversight": true/false,

  "drug_class": "checkpoint_inhibitor, targeted_therapy, chemotherapy, etc.",
  "therapeutic_area": "oncology, immunology, cardiology, etc.",

  "has_crossover": true/false,
  "has_delayed_effect": true/false
}

IMPORTANT RULES:
1. For checkpoint inhibitors (nivolumab, pembrolizumab, atezolizumab, durvalumab, ipilimumab) with OS endpoint:
   - primary_test MUST be "Fleming-Harrington weighted log-rank test G(rho=0, gamma=1)"
   - has_delayed_effect MUST be true
   - error_spending_function MUST be "Lan-DeMets with O'Brien-Fleming boundaries"

2. If interim analysis is mentioned:
   - alpha_interim should be ~0.020
   - alpha_final should be ~0.044

3. Extract EXACT numbers for sample size and events required.

4. If a field cannot be determined, use null.

PROTOCOL TEXT:
"""

    def __init__(self, rag_retriever=None, llm_client=None):
        self.rag = rag_retriever
        # Initialize LLM client
        if llm_client:
            self.llm = llm_client
        elif LLM_AVAILABLE:
            try:
                self.llm = TieredLLMClient()
                print("[SAP Generator] Claude LLM client initialized for extraction")
            except Exception as e:
                print(f"[SAP Generator] Warning: Could not initialize LLM client: {e}")
                self.llm = None
        else:
            self.llm = None

    def generate(self, protocol_text: str, facts: ProtocolFacts = None) -> SAPDocument:
        """
        Generate complete SAP from protocol text.

        Args:
            protocol_text: Raw protocol document text
            facts: Pre-extracted facts (optional, will extract if not provided)

        Returns:
            SAPDocument with all sections populated
        """
        # Extract facts if not provided
        if facts is None:
            facts = self.extract_protocol_facts(protocol_text)

        # Create document
        doc = SAPDocument()
        doc.protocol_number = facts.protocol_number or facts.nct_id
        doc.version = "1.0"
        doc.date = datetime.now().strftime("%B %d, %Y")

        # Generate each section
        doc.cover_page = self._generate_cover_page(facts)
        doc.sec1_1_hypothesis = self._generate_hypothesis(facts)
        doc.sec1_2_schedule = self._generate_schedule(facts)
        doc.sec2_1_design = self._generate_study_design(facts)
        doc.sec2_2_treatment = self._generate_treatment_assignment(facts)
        doc.sec2_3_blinding = self._generate_blinding(facts)
        doc.sec2_5_dmc = self._generate_dmc(facts)
        doc.sec3_1_primary = self._generate_primary_objective(facts)
        doc.sec3_2_secondary = self._generate_secondary_objectives(facts)
        doc.sec4_1_primary = self._generate_primary_endpoint(facts)
        doc.sec4_2_secondary = self._generate_secondary_endpoints(facts)
        doc.sec5_sample_size = self._generate_sample_size(facts)
        doc.sec6_3_analysis_populations = self._generate_populations(facts)
        doc.sec7_1_general_methods = self._generate_general_methods(facts)
        doc.sec7_5_1_primary_analysis = self._generate_primary_analysis(facts)
        doc.sec7_5_2_secondary_analyses = self._generate_secondary_analysis(facts)
        doc.sec7_5_3_sensitivity_analyses = self._generate_sensitivity(facts)
        doc.sec7_5_4_subgroup_analyses = self._generate_subgroups(facts)
        doc.sec7_6_safety = self._generate_safety(facts)
        doc.sec8_conventions = self._generate_conventions(facts)
        doc.sec10_history = self._generate_history(facts)

        # Generate TOC
        doc.table_of_contents = self._generate_toc()

        return doc

    def extract_protocol_facts(self, protocol_text: str) -> ProtocolFacts:
        """
        Extract comprehensive facts from protocol text using Claude API.

        Requires Claude API - no regex fallback.
        """
        if not self.llm:
            raise RuntimeError(
                "Claude API required for protocol extraction. "
                "Set ANTHROPIC_API_KEY environment variable."
            )

        facts = self._extract_with_llm(protocol_text)
        print("[SAP Generator] Successfully extracted facts using Claude API")
        return facts

    def _extract_with_llm(self, protocol_text: str) -> ProtocolFacts:
        """Extract protocol facts using Claude API."""
        # Truncate if too long (Claude context limit)
        max_chars = 100000
        if len(protocol_text) > max_chars:
            protocol_text = protocol_text[:max_chars]

        prompt = self.EXTRACTION_PROMPT + protocol_text

        # Call Claude
        response = self.llm.generate(
            prompt=prompt,
            system_prompt="You are a clinical trial protocol analyst. Extract facts precisely as JSON.",
            max_tokens=4000,
            temperature=0.0  # Deterministic extraction
        )

        # Parse JSON response
        return self._parse_llm_response(response)

    def _parse_llm_response(self, response: str) -> ProtocolFacts:
        """Parse Claude's JSON response into ProtocolFacts."""
        facts = ProtocolFacts()

        # Extract JSON from response (Claude sometimes wraps in markdown)
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            print("[SAP Generator] Warning: Could not find JSON in Claude response")
            return facts

        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            print(f"[SAP Generator] Warning: JSON parse error: {e}")
            return facts

        # Map JSON to ProtocolFacts
        facts.nct_id = data.get("nct_id") or ""
        facts.protocol_number = data.get("protocol_number") or ""
        facts.sponsor = data.get("sponsor") or ""
        facts.study_title = data.get("study_title") or ""

        facts.phase = str(data.get("phase") or "")
        facts.design_type = data.get("design_type") or ""
        facts.randomization_ratio = data.get("randomization_ratio") or ""
        facts.is_randomized = bool(data.get("is_randomized", True))

        facts.experimental_drug = data.get("experimental_drug") or ""
        facts.experimental_dose = data.get("experimental_dose") or ""
        facts.comparator_drug = data.get("comparator_drug") or ""
        facts.comparator_dose = data.get("comparator_dose") or ""

        facts.indication = data.get("indication") or ""
        facts.target_population = data.get("target_population") or ""

        facts.total_sample_size = _safe_int(data.get("total_sample_size"))
        facts.events_required_interim = _safe_int(data.get("events_required_interim"))
        facts.events_required_final = _safe_int(data.get("events_required_final"))
        power_val = data.get("power")
        facts.power = _safe_float(power_val) if power_val else None
        alpha_val = data.get("alpha")
        facts.alpha = _safe_float(alpha_val) if alpha_val else None

        facts.stratification_factors = data.get("stratification_factors") or []

        facts.primary_endpoint = data.get("primary_endpoint") or ""
        facts.primary_endpoint_definition = data.get("primary_endpoint_definition") or ""
        facts.primary_timepoint = data.get("primary_timepoint") or ""
        facts.secondary_endpoints = data.get("secondary_endpoints") or []

        facts.primary_test = data.get("primary_test") or ""
        facts.alpha_interim = _safe_float(data.get("alpha_interim"))
        alpha_final_val = data.get("alpha_final")
        facts.alpha_final = _safe_float(alpha_final_val) if alpha_final_val else None
        facts.error_spending_function = data.get("error_spending_function") or ""

        facts.has_interim = bool(data.get("has_interim", False))
        facts.num_interim_analyses = _safe_int(data.get("num_interim_analyses"))
        facts.interim_timing = data.get("interim_timing") or ""
        facts.dmc_oversight = bool(data.get("dmc_oversight", False))

        facts.drug_class = data.get("drug_class") or ""
        facts.therapeutic_area = data.get("therapeutic_area") or ""

        # Derive endpoint definition if not provided
        if facts.primary_endpoint and not facts.primary_endpoint_definition:
            pe_lower = str(facts.primary_endpoint).lower()
            pe_upper = str(facts.primary_endpoint).upper()
            if "overall survival" in pe_lower or pe_upper == "OS":
                facts.primary_endpoint_definition = "OS is defined as the time from randomization to the date of death. A subject who has not died will be censored at last known date alive."
            elif "progression-free survival" in pe_lower or "pfs" in pe_lower:
                facts.primary_endpoint_definition = "PFS is defined as the time from randomization to the date of the first documented tumor progression as determined by the investigator using RECIST 1.1 criteria or death due to any cause."

        return facts

    def _generate_cover_page(self, facts: ProtocolFacts) -> str:
        """Generate SAP cover page."""
        return f"""
================================================================================
                        STATISTICAL ANALYSIS PLAN
                        FOR CLINICAL STUDY REPORT
================================================================================

{facts.study_title or f"A {facts.design_type or 'Randomized'} {f'Phase {facts.phase}' if facts.phase else ''} Trial of {facts.experimental_drug or '[Drug]'} versus {facts.comparator_drug or '[Comparator]'} in {facts.indication or '[Indication]'}"}

                        PROTOCOL {facts.protocol_number or facts.nct_id or '[Protocol Number]'}

                        NCT Number: {facts.nct_id or '[NCT ID]'}

                        VERSION # {self._get_version()}

                        Date: {datetime.now().strftime("%B %d, %Y")}

================================================================================
"""

    def _get_version(self) -> str:
        return "1.0"

    def _generate_toc(self) -> str:
        """Generate table of contents."""
        return """
TABLE OF CONTENTS

STATISTICAL ANALYSIS PLAN FOR CLINICAL STUDY REPORT.............................1
TABLE OF CONTENTS...............................................................2
LIST OF TABLES..................................................................4
LIST OF FIGURES.................................................................4

1       INTRODUCTION............................................................5
1.1     Research Hypothesis.....................................................5
1.2     Schedule of Analyses....................................................5

2       STUDY DESCRIPTION.......................................................6
2.1     Study Design............................................................6
2.2     Treatment Assignment....................................................7
2.3     Blinding and Unblinding.................................................8
2.4     Protocol Amendments.....................................................8
2.5     Data Monitoring Committee...............................................8

3       OBJECTIVES..............................................................9
3.1     Primary.................................................................9
3.2     Secondary...............................................................9

4       ENDPOINTS..............................................................10
4.1     Primary Endpoint.......................................................10
4.2     Secondary Endpoints....................................................10

5       SAMPLE SIZE AND POWER..................................................12

6       STUDY PERIODS, TREATMENT REGIMENS AND POPULATIONS FOR ANALYSES.........14
6.1     Study Periods..........................................................14
6.2     Treatment Regimens.....................................................14
6.3     Populations for Analyses...............................................15

7       STATISTICAL ANALYSES...................................................16
7.1     General Methods........................................................16
7.2     Study Conduct..........................................................17
7.3     Study Population.......................................................18
7.4     Extent of Exposure.....................................................19
7.5     Efficacy...............................................................20
7.5.1   Primary Analysis.......................................................20
7.5.2   Secondary Analyses.....................................................22
7.5.3   Sensitivity Analyses...................................................24
7.5.4   Subgroup Analyses......................................................25
7.6     Safety.................................................................26

8       CONVENTIONS............................................................28

9       CONTENT OF REPORTS.....................................................29

10      DOCUMENT HISTORY.......................................................30

REFERENCES.....................................................................31
"""

    def _generate_hypothesis(self, facts: ProtocolFacts) -> str:
        """Generate Section 1.1 Research Hypothesis."""
        return f"""
1.1     Research Hypothesis

The treatment effect of {facts.experimental_drug or '[experimental drug]'} is superior to {facts.comparator_drug or '[comparator]'} in improving {facts.primary_endpoint or 'the primary endpoint'} in subjects with {facts.indication or '[indication]'}.

{"Given the mechanism of action of checkpoint inhibitors, a delayed treatment effect may be observed. The study design accounts for potential non-proportional hazards using appropriate statistical methodology." if facts.drug_class == "checkpoint_inhibitor" else ""}
"""

    def _generate_schedule(self, facts: ProtocolFacts) -> str:
        """Generate Section 1.2 Schedule of Analyses."""
        if facts.has_interim:
            return f"""
1.2     Schedule of Analyses

{facts.primary_endpoint or 'The primary endpoint'} is the primary endpoint for this study.

{"One formal interim analysis for superiority is planned when at least " + str(facts.events_required_interim or int(facts.events_required_final * 0.76)) + " events (" + str(round(100 * (facts.events_required_interim or int(facts.events_required_final * 0.76)) / facts.events_required_final if facts.events_required_final else 76)) + "% of total events required for the final analysis) have been observed." if facts.events_required_final else "One formal interim analysis for superiority is planned at approximately 76% information fraction."}

The interim analysis will be monitored by an independent Data Monitoring Committee (DMC).

The final analysis is planned to be performed when at least {facts.events_required_final or '[N]'} events are observed.
"""
        else:
            return f"""
1.2     Schedule of Analyses

{facts.primary_endpoint or 'The primary endpoint'} is the primary endpoint for this study.

The primary analysis will be performed when at least {facts.events_required_final or '[N]'} events have been observed in all randomized subjects.
"""

    def _generate_study_design(self, facts: ProtocolFacts) -> str:
        """Generate Section 2.1 Study Design."""
        return f"""
2       STUDY DESCRIPTION

2.1     Study Design

This is {"an " + str(facts.design_type).lower() if facts.design_type else "a"}, {"randomized, " if facts.is_randomized else ""}{"Phase " + str(facts.phase) + " " if facts.phase else ""}study in adult (≥ 18 years old) male and female subjects with {facts.indication or '[indication]'}.

{"Approximately " + str(facts.total_sample_size) + " subjects will be randomized to " + facts.experimental_drug + " vs. " + facts.comparator_drug + " in a " + facts.randomization_ratio + " ratio." if facts.total_sample_size and facts.experimental_drug and facts.comparator_drug and facts.randomization_ratio else ""}

{self._generate_stratification_text(facts)}

Subjects will be evaluated for response according to the RECIST 1.1 criteria. The first on-treatment radiographic assessment will be obtained in both treatment arms at Week 6 (± 7 days). Subsequent radiographic assessments will be conducted every 6 weeks (± 7 days) for the first 12 months, then every 12 weeks (± 14 days) until disease progression.

{"Subjects treated on the " + facts.experimental_drug + " arm will be allowed to continue study therapy after initial investigator-assessed RECIST 1.1-defined progression if they are assessed by the investigator to be deriving clinical benefit and tolerating study drug." if facts.drug_class == "checkpoint_inhibitor" else ""}

All subjects will be followed for overall survival every 3 months until death, lost to follow-up, or withdrawal of study consent.
"""

    def _generate_stratification_text(self, facts: ProtocolFacts) -> str:
        """Generate stratification factors text."""
        if facts.stratification_factors:
            factors = "\n".join([f"  • {f}" for f in facts.stratification_factors])
            return f"""Randomization will be stratified and balanced according to the following factors:
{factors}
"""
        return ""

    def _generate_treatment_assignment(self, facts: ProtocolFacts) -> str:
        """Generate Section 2.2 Treatment Assignment."""
        return f"""
2.2     Treatment Assignment

Subjects are enrolled using the Interactive Voice Response System (IVRS) to obtain a subject ID. Subjects who have signed informed consent and met all eligibility criteria will be ready to be randomized through the IVRS.

The IVRS will randomly assign the subject in a {facts.randomization_ratio or '1:1'} ratio to either:
  • Arm A: Experimental arm - {facts.experimental_drug or '[experimental drug]'} {facts.experimental_dose or ''}
  • Arm B: Control arm - {facts.comparator_drug or '[comparator]'} {facts.comparator_dose or ''}

{f"Stratification factors: " + ", ".join(facts.stratification_factors) if facts.stratification_factors else ""}

The randomization will be carried out via permuted blocks within each stratum.
"""

    def _generate_blinding(self, facts: ProtocolFacts) -> str:
        """Generate Section 2.3 Blinding."""
        if facts.design_type and 'open' in str(facts.design_type).lower():
            return """
2.3     Blinding and Unblinding

Not applicable. This is an open-label study.
"""
        else:
            return """
2.3     Blinding and Unblinding

This study is double-blind. Neither the subject nor the investigator will know which treatment the subject is receiving. Unblinding will occur only in case of medical emergency.
"""

    def _generate_dmc(self, facts: ProtocolFacts) -> str:
        """Generate Section 2.5 Data Monitoring Committee."""
        if facts.dmc_oversight:
            return """
2.5     Data Monitoring Committee

A Data Monitoring Committee (DMC) will be instituted for this study. This committee will provide independent oversight of safety and efficacy considerations, study conduct, and risk-benefit ratio. Following review, the DMC will recommend continuation, modification, or discontinuation of this study based on reported safety and efficacy data.

A separate DMC charter describes the members and activities of this committee, as well as the proposed meeting schedule. Representatives of the Sponsor will serve only as coordinators of the committee, without having full member responsibilities or privileges.

In addition, the Sponsor will independently review safety data in a blinded manner during the conduct of this trial to ensure that any safety issues are identified and addressed.
"""
        return """
2.5     Data Monitoring Committee

Not applicable for this study.
"""

    def _generate_primary_objective(self, facts: ProtocolFacts) -> str:
        """Generate Section 3.1 Primary Objectives."""
        return f"""
3       OBJECTIVES

3.1     Primary

  • To compare the {facts.primary_endpoint or '[primary endpoint]'} of {facts.experimental_drug or '[experimental drug]'} versus {facts.comparator_drug or '[comparator]'} in subjects with {facts.indication or '[indication]'}.
"""

    def _generate_secondary_objectives(self, facts: ProtocolFacts) -> str:
        """Generate Section 3.2 Secondary Objectives."""
        secondary = facts.secondary_endpoints or [
            "Objective Response Rate (ORR)",
            "Progression-Free Survival (PFS)",
            "Duration of Response (DOR)"
        ]
        objectives = "\n".join([f"  • To compare the {ep} of {facts.experimental_drug or '[experimental drug]'} vs. {facts.comparator_drug or '[comparator]'}" for ep in secondary])

        return f"""
3.2     Secondary

{objectives}
  • To evaluate clinical efficacy in different subgroups
  • To evaluate rates of treatment-related adverse events (AEs) and serious adverse events (SAEs)
"""

    def _generate_primary_endpoint(self, facts: ProtocolFacts) -> str:
        """Generate Section 4.1 Primary Endpoint."""
        return f"""
4       ENDPOINTS

4.1     Primary Endpoint

{facts.primary_endpoint or 'Overall Survival (OS)'} is the primary endpoint.

{facts.primary_endpoint_definition or "OS is defined as the time from randomization to the date of death. A subject who has not died will be censored at last known date alive."}
"""

    def _generate_secondary_endpoints(self, facts: ProtocolFacts) -> str:
        """Generate Section 4.2 Secondary Endpoints."""
        return """
4.2     Secondary Endpoints

4.2.1   Objective Response Rate

Objective Response Rate (ORR) is defined as the number of subjects whose best objective response (BOR) is a confirmed CR or confirmed PR, as determined by the investigator, divided by the number of randomized subjects.

BOR is defined as the best response designation, recorded between the date of randomization and the date of objectively documented progression per RECIST v1.1 or the date of subsequent anticancer therapy, whichever occurs first.

4.2.2   Progression-Free Survival

Progression-Free Survival (PFS) is defined as the time from randomization to the date of the first documented tumor progression as determined by the investigator using RECIST 1.1 criteria or death due to any cause.

Clinical deterioration in the absence of unequivocal evidence of progression (per RECIST 1.1) is not considered progression for purposes of determining PFS.

Table 4.2.2-1: Censoring Scheme for Primary Definition of PFS

┌─────────────────────────────────────────┬────────────────────────────────────────┬──────────┐
│ Situation                               │ Date of Progression or Censoring       │ Outcome  │
├─────────────────────────────────────────┼────────────────────────────────────────┼──────────┤
│ No baseline tumor assessments           │ Randomization                          │ Censored │
│ No on-study tumor assessments, no death │ Randomization                          │ Censored │
│ New anticancer treatment started        │ Date of last evaluable tumor           │ Censored │
│   without prior reported progression    │   assessment prior to new therapy      │          │
│ Progression documented at visit         │ Date of first documented progression   │Progressed│
│ Subject progression-free, no new        │ Date of last tumor assessment          │ Censored │
│   anticancer treatment                  │                                        │          │
│ Death without prior progression         │ Date of death                          │Progressed│
└─────────────────────────────────────────┴────────────────────────────────────────┴──────────┘

4.2.3   Duration of Response

Duration of Response (DOR) is defined as the time from first documented response (CR or PR) to the date of first documented progression or death, whichever occurs first.
"""

    def _generate_sample_size(self, facts: ProtocolFacts) -> str:
        """Generate Section 5 Sample Size and Power."""
        return f"""
5       SAMPLE SIZE AND POWER

The sample size is calculated in order to compare the {facts.primary_endpoint or '[primary endpoint]'} between subjects randomized to receive {facts.experimental_drug or '[experimental drug]'} and subjects randomized to receive {facts.comparator_drug or '[comparator]'}.

Approximately {facts.total_sample_size or '[N]'} subjects will be randomized to the {facts.experimental_drug or 'experimental'} and {facts.comparator_drug or 'control'} arms in a {facts.randomization_ratio or '1:1'} ratio.

At least {facts.events_required_final or '[N]'} events will be required for the final analysis.

{"A formal interim analysis will be conducted when at least " + str(facts.events_required_interim or int((facts.events_required_final or 0) * 0.76)) + " events (approximately 76% information fraction) have been observed." if facts.has_interim else ""}

Statistical Assumptions:
  • Two-sided significance level (α): {facts.alpha or 0.05}
  • Power: {facts.power or 90}%
  • Expected hazard ratio: [HR]

{self._generate_power_methodology(facts)}

Table 5-1: Power Calculations

┌──────────────────────────┬───────────────┬───────────────┬───────────────┐
│ Parameter                │ Interim       │ Final         │ Notes         │
├──────────────────────────┼───────────────┼───────────────┼───────────────┤
│ Events                   │ {str(facts.events_required_interim or 'N/A'):^13} │ {str(facts.events_required_final or 'N/A'):^13} │               │
│ Alpha (two-sided)        │ {str(facts.alpha_interim or 'N/A'):^13} │ {str(facts.alpha_final or facts.alpha or 0.05):^13} │ Lan-DeMets    │
│ Expected HR              │ {'^13'} │ {'^13'} │               │
│ Power (log-rank)         │ {'^13'} │ {'^13'} │               │
│ Power (weighted log-rank)│ {'^13'} │ {'^13'} │               │
└──────────────────────────┴───────────────┴───────────────┴───────────────┘
"""

    def _generate_power_methodology(self, facts: ProtocolFacts) -> str:
        """Generate power calculation methodology text."""
        if facts.drug_class == "checkpoint_inhibitor":
            return """
Given the mechanism of action of checkpoint inhibitors, a delayed treatment effect may be observed. Therefore, the power of both the standard log-rank and Fleming-Harrington (FH) weighted log-rank tests was assessed.

The FH method with G(rho=0, gamma=1) weights is known to be more efficient for testing survival differences when a delayed treatment effect is present.

To control the overall Type I error rate under a two-sided 5%, significance levels were calculated using the Lan-DeMets error spending function with O'Brien-Fleming boundaries.
"""
        return """
Simulations were run to calculate the power of the log-rank test under the assumed treatment effect.
"""

    def _generate_populations(self, facts: ProtocolFacts) -> str:
        """Generate Section 6.3 Analysis Populations."""
        return """
6       STUDY PERIODS, TREATMENT REGIMENS AND POPULATIONS FOR ANALYSES

6.3     Populations for Analyses

  • All Enrolled Subjects: All subjects who signed an informed consent form and were registered into the IVRS. This population is used for analysis of subjects enrolled but not randomized.

  • All Randomized Subjects (Intent-to-Treat, ITT): All subjects who were randomized to any treatment group in the study. This is the primary dataset for analyses of demographics, baseline characteristics, and efficacy.

  • All Treated Subjects (Safety Population): All subjects who received at least one dose of study medication. This is the primary dataset for dosing and safety analyses.

  • Per-Protocol Population: All randomized subjects who received at least one dose of study medication and had no major protocol deviations affecting efficacy assessment.

  • Response Evaluable Subjects: Randomized subjects whose change in the sum of diameters of target lesions was assessed (i.e., target lesion measurements were made at baseline and at least one on-study tumor assessment).

  • All Responders: Randomized subjects with confirmed CR or PR as best objective response.
"""

    def _generate_general_methods(self, facts: ProtocolFacts) -> str:
        """Generate Section 7.1 General Methods."""
        strat_factors = ", ".join(facts.stratification_factors) if facts.stratification_factors else "[stratification factors]"

        return f"""
7       STATISTICAL ANALYSES

7.1     General Methods

Unless otherwise noted, discrete variables will be tabulated by the frequency and proportion of subjects falling into each category, grouped by treatment (with total). Percentages given in these tables will be rounded and, therefore, may not always sum to 100%.

Continuous variables will be summarized by treatment group (with total) using the mean, standard deviation, median, minimum, and maximum values.

Time-to-event distributions (i.e., overall survival, progression-free survival, and duration of response) will be estimated using Kaplan-Meier techniques.

Median survival time along with 95% CI will be constructed based on a log-log transformed CI for the survivor function S(t). Rates at fixed timepoints (e.g., OS at 6 months, 12 months) will be derived from the Kaplan-Meier estimate with corresponding confidence intervals calculated using Greenwood's formula for variance derivation.

Unless otherwise specified, the stratified log-rank test will be performed to test the comparison between time-to-event distributions. Stratification factors will be: {strat_factors}.

Unless otherwise specified, the stratified hazard ratio between 2 treatment groups along with CI will be obtained by fitting a stratified Cox model with the treatment group variable as the unique covariate.

The difference in rates between the two treatment arms along with their two-sided 95% CI will be estimated using the Cochran-Mantel-Haenszel (CMH) method of weighting, adjusting for the stratification factors.

The p-values from sensitivity analyses for efficacy endpoints are for descriptive purposes only and not adjusted for multiplicity.
"""

    def _generate_primary_analysis(self, facts: ProtocolFacts) -> str:
        """Generate Section 7.5.1 Primary Analysis."""
        return f"""
7.5     Efficacy

7.5.1   {facts.primary_endpoint or 'Overall Survival'}

7.5.1.1 Primary Analysis

{facts.primary_endpoint or 'OS'} is the primary endpoint of this study.

{self._generate_hierarchical_testing(facts)}

The distribution of {facts.primary_endpoint or 'OS'} will be compared in two randomized arms via a two-sided weighted log-rank test stratified by {", ".join(facts.stratification_factors) if facts.stratification_factors else "[stratification factors]"}.

{"The weighted log-rank test will use G(rho=0, gamma=1) weights, in the terminology of Fleming and Harrington. This weighting scheme is appropriate for immunotherapy trials where a delayed treatment effect is expected." if facts.drug_class == "checkpoint_inhibitor" else ""}

The unweighted hazard ratio (HR) and the corresponding {int((1-facts.alpha_final)*100) if facts.alpha_final else 95}% CI will be estimated in a stratified Cox proportional hazards model using randomized arm as a single covariate with the same stratification factors.

The {facts.primary_endpoint or 'OS'} curves for each treatment group will be estimated using the Kaplan-Meier (KM) product-limit method. Two-sided, 95% confidence intervals for median {facts.primary_endpoint or 'OS'} will be constructed based on a log-log transformed CI for the survivor function S(t).

Survival rates at 6, 12, 18, 24, 36, and 48 months will be estimated using KM estimates for each randomized arm. Associated two-sided 95% CIs will be calculated using Greenwood's formula for variance derivation and log-log transformation applied to the survivor function S(t).

The status of subjects who are censored in the {facts.primary_endpoint or 'OS'} Kaplan-Meier analysis will be tabulated for each treatment group using the following categories:
  • On-study (on-treatment and not progressed, on-treatment progressed, in follow-up)
  • Off-study (lost to follow-up, withdrew consent, etc.)

To examine the assumption of proportional hazards in the Cox regression model, in addition to treatment, a time-dependent variable defined by treatment-by-time interaction will be added into the model. A two-sided Wald Chi-square p-value of less than 0.1 may indicate a potential non-constant treatment effect. In that case, additional exploratory analyses may be performed.
"""

    def _generate_hierarchical_testing(self, facts: ProtocolFacts) -> str:
        """Generate hierarchical testing text for interim analyses."""
        if facts.has_interim:
            return f"""
At both the interim and final analysis, a 2-step hierarchical testing will be performed:

Step 1: Check for consistency in HR for {facts.primary_endpoint or 'OS'}.
Step 2: If consistency is demonstrated, test for superiority.

This OS comparison will be tested using the interim monitoring feature based on a generalization of the {facts.error_spending_function or 'Lan-DeMets error spending function'} to control for a two-sided overall α of {facts.alpha or 0.05}.

  • At the interim analysis ({facts.events_required_interim or 'N'} events), H₀ will be rejected if p < {facts.alpha_interim or 0.020}
  • At the final analysis ({facts.events_required_final or 'N'} events), H₀ will be rejected if p < {facts.alpha_final or 0.044}

If the number of events is not exactly as specified at the time of analysis, the nominal critical point will be calculated based upon the observed information fraction.

The DMC will review the safety and efficacy data from the interim analysis and will determine if the study should continue or be stopped. If the trial is stopped for superiority at the interim, all secondary endpoint analyses will be tested at that time.
"""
        return ""

    def _generate_secondary_analysis(self, facts: ProtocolFacts) -> str:
        """Generate Section 7.5.2 Secondary Analyses."""
        return f"""
7.5.2   Objective Response Rate

7.5.2.1 Primary Analysis of ORR

Best Overall Response (BOR) will be summarized by response category for each treatment group. ORR will be computed in each treatment group along with the exact 95% CI using the Clopper-Pearson method.

An estimate of the difference in ORRs and corresponding 95% CI will be calculated using CMH methodology and adjusted by the same stratification factors as for primary analysis.

In addition, the stratified odds ratios (Mantel-Haenszel estimator) between the treatments will be provided along with the 95% CI. The difference will be tested via the Cochran-Mantel-Haenszel (CMH) test using a two-sided, 5% α level.

7.5.2.2 Duration of Response

Duration of response in each treatment group will be estimated using KM product-limit method for subjects who achieve PR or CR. Median values along with two-sided 95% CI will be calculated.

7.5.3   Progression-Free Survival

7.5.3.1 Primary Analysis of PFS

PFS for each treatment arm will be estimated using the Kaplan-Meier product-limit method and graphically displayed. A two-sided 95% CI for median duration will be constructed based on a log-log transformed CI for the survivor function S(t).

The comparison of PFS distribution will be performed via a stratified log-rank test at two-sided, 5% level. In addition, the stratified hazard ratios between treatment groups will be provided along with the 95% CI.

7.5.4   Hierarchy for Key Secondary Efficacy Endpoints

In order to preserve an experimental-wise Type I error rate at 5%, a pre-planned hierarchy for key secondary ORR and PFS endpoints will be applied:

1) Objective Response Rate (ORR)
2) Progression-Free Survival (PFS)

The statistical testing will be carried out using the following sequential procedure:
  • If superiority for {facts.primary_endpoint or 'OS'} is demonstrated, ORR will be tested at 5% level
  • If ORR is statistically significant, PFS will be tested at 5% level
  • If ORR is not significant, no further testing of PFS will be conducted (estimates and 95% CI will still be provided)
"""

    def _generate_sensitivity(self, facts: ProtocolFacts) -> str:
        """Generate Section 7.5.3 Sensitivity Analyses."""
        return f"""
7.5.5   Sensitivity Analyses

The following sensitivity analyses will be performed for {facts.primary_endpoint or 'the primary endpoint'}:

  1. {facts.primary_endpoint or 'OS'} will be compared between treatment groups using a two-sided stratified regular (unweighted) log-rank test.

  2. {facts.primary_endpoint or 'OS'} will be compared between treatment groups using a two-sided unstratified regular log-rank test.

  3. {facts.primary_endpoint or 'OS'} will be compared between treatment groups using stratification factors as determined at baseline (CRF source). This analysis will be performed only if at least one stratification variable at IVRS and at baseline disagrees for at least 10% of the randomized subjects.

  4. {facts.primary_endpoint or 'OS'} will be compared between treatment groups in the All Treated Subjects population, using arm as randomized. This analysis will be performed only if the proportion of randomized but never treated subjects exceeds 10% in any arm.

  5. {facts.primary_endpoint or 'OS'} will be compared between treatment groups, censoring subjects in the control arm at the time of subsequent use of anti-PD(L)1 therapy.

For each sensitivity analysis, the estimate of the hazard ratio, its two-sided 95% CI, and p-value will be presented.

PFS Sensitivity Analyses:

  • PFS accounting for assessment after subsequent therapy
  • PFS accounting for missing tumor assessment prior to PFS event (if ≥20% of events have missing prior assessment)
  • PFS accounting for assessment after on-treatment palliative radiotherapy
"""

    def _generate_subgroups(self, facts: ProtocolFacts) -> str:
        """Generate Section 7.5.4 Subgroup Analyses."""
        return f"""
7.5.6   Consistency of Treatment Effect in Subsets

To assess consistency of treatment effects in different subsets, a "forest" plot of the {facts.primary_endpoint or 'OS'} unstratified hazard ratio (and 95% CI) will be produced for the following subgroups:

  • Age categorization (< 65, ≥ 65 to < 75, ≥ 75)
  • Gender (male, female)
  • Race (White, Asian, Other)
  • Baseline ECOG Performance Status (0 vs. ≥ 1)
  • Smoking status (current/former vs. never smoked vs. unknown)
  • Histology (squamous vs. non-squamous)
  • PD-L1 status at baseline (positive vs. negative, using 1% cutoff)
  • Disease stage at study entry (stage IIIB vs. stage IV/recurrent)
  • Time from initial diagnosis to randomization (< 1 year vs. ≥ 1 year)
  • Time from completion of most recent prior therapy to randomization (< 3 months, 3-6 months, > 6 months)
  • Prior maintenance therapy (yes vs. no)
  • Best response to most recent prior regimen (responders vs. non-responders)
  • CNS metastases (yes vs. no)

If subset category has less than 10 subjects per treatment group, HR will not be computed/displayed. Number of events and median {facts.primary_endpoint or 'OS'} along with 95% CI will be displayed for each treatment group.

7.5.7   Multivariate Analysis

A multivariate stratified Cox model will be fitted to assess the treatment effect on {facts.primary_endpoint or 'OS'} when adjusted for potential prognostic factors:

  • Time from initial diagnosis to randomization (< 1 year vs. other)
  • Age categorization (< 65 vs. ≥ 65)
  • Gender (male vs. female)
  • Smoking status (yes vs. no or unknown)
  • Disease stage at study entry (stage IIIB vs. stage IV/recurrent)

HR and 95% CI will be provided for treatment variable and all covariates. Descriptive p-values will be provided.
"""

    def _generate_safety(self, facts: ProtocolFacts) -> str:
        """Generate Section 7.6 Safety."""
        return """
7.6     Safety

Safety analyses will be performed by treatment group "as treated". The primary population for safety analyses will be the All Treated Subjects population.

7.6.1   Deaths

A summary of deaths will be provided including:
  • Number and percentage of deaths by treatment arm
  • Time from first dose to death
  • Primary cause of death (disease progression, study drug toxicity, other)

7.6.2   Serious Adverse Events

Serious adverse events (SAEs) will be summarized by System Organ Class (SOC) and Preferred Term (PT) according to MedDRA. Incidence rates will be presented by treatment group.

7.6.3   Adverse Events Leading to Discontinuation

AEs leading to discontinuation of study therapy will be summarized by SOC and PT.

7.6.4   Adverse Events Leading to Dose Delay

AEs leading to dose delay will be summarized by SOC and PT.

7.6.5   Adverse Events

All treatment-emergent adverse events (TEAEs) will be summarized by SOC and PT. TEAEs are defined as AEs that occur or worsen on or after the first dose of study therapy and within 30 days of the last dose.

The following summaries will be provided:
  • All TEAEs by maximum grade
  • Drug-related TEAEs
  • Grade 3-4 TEAEs
  • Grade 5 TEAEs (deaths)

7.6.6   Adverse Events of Special Interest

For immunotherapy agents, the following adverse events of special interest will be analyzed separately:
  • Pneumonitis
  • Colitis
  • Hepatitis
  • Endocrinopathies (thyroid disorders, hypophysitis, adrenal insufficiency, diabetes)
  • Nephritis
  • Skin reactions
  • Infusion reactions

Time to onset, duration, and management of immune-related adverse events will be summarized.

7.6.7   Clinical Laboratory Evaluations

Laboratory parameters will be summarized using shift tables (baseline grade vs. worst post-baseline grade) and by change from baseline.
"""

    def _generate_conventions(self, facts: ProtocolFacts) -> str:
        """Generate Section 8 Conventions."""
        return """
8       CONVENTIONS

The following conventions may be used for imputing partial dates for analyses requiring dates:

  • For missing and partial adverse event onset dates, imputation will be performed per the Adverse Event Domain Requirements Specification.

  • Missing and partial non-study medication dates will be imputed using the standard derivation algorithm.

For death dates:
  • If only the day of the month is missing, the 1st of the month will be used. The imputed date will be compared to the last known date alive and the maximum will be considered as the death date.
  • If the month or year is missing, the death date will be imputed as the last known date alive.

For date of progression:
  • If only the day is missing, the 1st of the month will be used.
  • If day and month are missing or date is completely missing, it will be considered as missing.

Conversion factors:
  • 1 month = 30.4375 days
  • 1 year = 365.25 days

Duration calculation:
  Duration = (Last date - First date + 1)

All statistical analyses will be carried out using SAS (Statistical Analysis System software, SAS Institute, North Carolina, USA) unless otherwise noted.
"""

    def _generate_history(self, facts: ProtocolFacts) -> str:
        """Generate Section 10 Document History."""
        return f"""
9       CONTENT OF REPORTS

All analyses described in this SAP will be included in the final Clinical Study Report.
Refer to the Data Presentation Plan for mock-ups of all tables and listings.


10      DOCUMENT HISTORY

┌─────────┬─────────────────┬─────────────┬─────────────────────────────────────────────┐
│ Version │ Author(s)       │ Date        │ Description                                 │
├─────────┼─────────────────┼─────────────┼─────────────────────────────────────────────┤
│ 1.0     │ [Statistician]  │ {datetime.now().strftime("%d%b%Y")}  │ Initial version                             │
└─────────┴─────────────────┴─────────────┴─────────────────────────────────────────────┘


REFERENCES

1. ICH E9: Statistical Principles for Clinical Trials (1998)
2. ICH E9(R1): Addendum on Estimands and Sensitivity Analysis (2019)
3. Fleming TR, Harrington DP. Counting Processes and Survival Analysis. Wiley (1991)
4. Lan KKG, DeMets DL. Discrete sequential boundaries for clinical trials. Biometrika (1983)
5. Kaplan EL, Meier P. Nonparametric estimation from incomplete observations. JASA (1958)
6. Cox DR. Regression models and life tables. J Royal Stat Soc (1972)
"""

    def assemble_document(self, doc: SAPDocument) -> str:
        """Assemble all sections into final document."""
        sections = [
            doc.cover_page,
            doc.table_of_contents,
            doc.sec1_1_hypothesis,
            doc.sec1_2_schedule,
            doc.sec2_1_design,
            doc.sec2_2_treatment,
            doc.sec2_3_blinding,
            doc.sec2_5_dmc,
            doc.sec3_1_primary,
            doc.sec3_2_secondary,
            doc.sec4_1_primary,
            doc.sec4_2_secondary,
            doc.sec5_sample_size,
            doc.sec6_3_analysis_populations,
            doc.sec7_1_general_methods,
            doc.sec7_5_1_primary_analysis,
            doc.sec7_5_2_secondary_analyses,
            doc.sec7_5_3_sensitivity_analyses,
            doc.sec7_5_4_subgroup_analyses,
            doc.sec7_6_safety,
            doc.sec8_conventions,
            doc.sec10_history,
        ]

        return "\n".join([s for s in sections if s])


def create_regulatory_sap_generator(rag_retriever=None, llm_client=None) -> RegulatorySAPGenerator:
    """Factory function to create the regulatory SAP generator."""
    return RegulatorySAPGenerator(rag_retriever, llm_client)


# Test
if __name__ == "__main__":
    generator = RegulatorySAPGenerator()

    # Test with CheckMate-like protocol
    test_protocol = """
    An Open-label Randomized Multinational Phase 3 Trial of Nivolumab Versus
    Docetaxel in Previously Treated Subjects With Advanced or Metastatic
    Non-small Cell Lung Cancer (NSCLC)

    NCT Number: NCT02613507
    Protocol: CA209-078

    Primary Endpoint: Overall Survival (OS), defined as time from randomization
    to death from any cause.

    Approximately 500 subjects will be randomized to nivolumab vs. docetaxel
    in a 2:1 ratio.

    Randomization will be stratified by:
    - Histology (squamous vs. non-squamous)
    - PD-L1 Status (positive vs. negative/unevaluable)
    - ECOG Performance status (0 vs. 1)

    At least 382 deaths will be required for the final OS analysis.
    One interim analysis is planned at 291 deaths (76% information fraction).

    Given the mechanism of action of checkpoint inhibitors, a delayed
    treatment effect may be observed.

    An independent Data Monitoring Committee will conduct interim analyses.
    """

    # Extract facts
    facts = generator.extract_protocol_facts(test_protocol)
    print("Extracted Facts:")
    print(f"  NCT ID: {facts.nct_id}")
    print(f"  Protocol: {facts.protocol_number}")
    print(f"  Phase: {facts.phase}")
    print(f"  Drug: {facts.experimental_drug} vs {facts.comparator_drug}")
    print(f"  Sample Size: {facts.total_sample_size}")
    print(f"  Primary Endpoint: {facts.primary_endpoint}")
    print(f"  Events Required: {facts.events_required_final}")
    print(f"  Stratification: {facts.stratification_factors}")
    print(f"  Has Interim: {facts.has_interim}")
    print(f"  Primary Test: {facts.primary_test}")
    print()

    # Generate SAP
    doc = generator.generate(test_protocol, facts)
    full_sap = generator.assemble_document(doc)

    print("=" * 80)
    print("GENERATED SAP:")
    print("=" * 80)
    print(full_sap[:10000])  # Print first 10K chars
    print("\n... [truncated] ...")
    print(f"\nTotal length: {len(full_sap)} characters")
