#!/usr/bin/env python3
"""
Section-by-Section Protocol Extractor
======================================

CRITICAL DESIGN PRINCIPLE:
- Extract by section, not all at once
- Each section has explicit confidence scores
- Fields not found in protocol are flagged [NEEDS REVIEW]
- NO inference from drug class, keywords, or rules

Sections (based on Gamble et al. 2017 JAMA checklist):
1. Administrative (Items 1-6)
2. Study Design (Items 7-15)
3. Endpoints (Items 16-19)
4. Interim Analysis (Items 13a-13c)
5. Statistical Methods (Items 27a-27f)
6. Multiplicity (Item 17)
7. Missing Data (Item 28)
8. Populations (Item 20)
9. Estimand (ICH E9 R1)
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from .extraction_schema import (
    ExtractedProtocolFacts,
    from_claude_extraction,
    ExtractionConfidence
)
from .section_parser import ProtocolSectionParser, ParsedProtocol


@dataclass
class SectionExtractionResult:
    """Result from extracting a single section."""
    section_name: str
    extracted_fields: Dict[str, Any]
    confidence: float  # 0-1
    fields_found: List[str]
    fields_not_found: List[str]
    needs_review: List[str]
    notes: List[str] = field(default_factory=list)


class SectionedProtocolExtractor:
    """
    Extracts protocol facts section-by-section with confidence scoring.

    This replaces the single-pass extraction with a more robust approach:
    1. Each section is extracted separately
    2. Each field has a confidence score
    3. Fields not found are explicitly flagged
    4. No inference from drug class or keywords
    """

    # Section definitions with required and optional fields
    SECTIONS = {
        'study_design': {
            'required': ['treatment_setting', 'disease_type', 'phase', 'drug_name', 'comparator'],
            'optional': ['histology', 'disease_stage', 'biomarker_status', 'allocation_ratio', 'blinding_type'],
            'critical': ['treatment_setting', 'disease_type']  # These MUST be extracted
        },
        'stratification': {
            'required': ['stratification_factors'],
            'optional': ['stratification_factor_levels'],
            'critical': ['stratification_factors']
        },
        'sample_size': {
            'required': ['sample_size', 'power'],
            'optional': ['sample_size_per_arm', 'sample_size_rationale', 'hazard_ratio'],
            'critical': ['sample_size']
        },
        'endpoints': {
            'required': ['primary_endpoint'],
            'optional': ['secondary_endpoints', 'is_co_primary', 'co_primary_endpoints', 'assessment_criteria'],
            'critical': ['primary_endpoint']
        },
        'statistical_methods': {
            'required': ['statistical_method'],
            'optional': ['null_hypothesis', 'alternative_hypothesis', 'test_sidedness', 'hazard_ratio_method'],
            'critical': ['statistical_method']  # MUST come from protocol, not inferred
        },
        'interim_analysis': {
            'required': ['has_interim_analysis', 'num_interim_analyses'],
            'optional': ['interim_events', 'final_events', 'information_fractions',
                        'alpha_spending_function', 'alpha_at_interim', 'alpha_at_final',
                        'stopping_boundaries', 'interim_by_endpoint'],
            'critical': ['num_interim_analyses', 'final_events']
        },
        'multiplicity': {
            'required': ['has_multiplicity'],
            'optional': ['adjustment_method', 'testing_sequence', 'alpha_per_hypothesis', 'hypotheses_list', 'alpha_propagation'],
            'critical': ['hypotheses_list', 'alpha_per_hypothesis']
        },
        'missing_data': {
            'required': ['censoring_rules'],
            'optional': ['treatment_discontinuation_strategy', 'tipping_point_analysis',
                        'subsequent_therapy_handling'],
            'critical': []
        },
        'populations': {
            'required': ['itt_definition'],
            'optional': ['fas_definition', 'per_protocol_definition', 'safety_population_definition'],
            'critical': []
        },
        'estimand': {
            'required': [],
            'optional': ['estimand_population', 'estimand_variable', 'intercurrent_events',
                        'primary_estimand'],
            'critical': []  # Per ICH E9 R1 - should be in modern protocols
        },
        'crossover': {
            'required': ['has_crossover'],
            'optional': ['crossover_description', 'crossover_adjustment_methods'],
            'critical': []
        }
    }

    # Section-specific prompts
    SECTION_PROMPTS = {
        'study_design': '''Extract STUDY DESIGN information from this protocol section.

CRITICAL: Extract EXACTLY what the protocol says. DO NOT infer from drug name or therapeutic area.

Required fields (must find or mark [NOT FOUND]):
- treatment_setting: EXACTLY one of: "first-line", "second-line", "third-line or later",
  "neoadjuvant", "adjuvant", "maintenance". Look for phrases like "first-line treatment",
  "previously untreated", "treatment-naive" (= first-line), "after failure of", "following progression" (= second-line+)
- disease_type: The specific disease, e.g., "Non-small cell lung cancer (NSCLC)",
  "HER2-positive breast cancer", "Advanced melanoma". Be specific, not generic.
- phase: "Phase 1", "Phase 2", "Phase 3", etc.
- drug_name: The experimental drug name
- comparator: The control arm treatment

Optional fields:
- histology: e.g., "Squamous", "Non-squamous", "Adenocarcinoma"
- disease_stage: e.g., "Stage IIIB-IV", "Locally advanced or metastatic"
- biomarker_status: e.g., "PD-L1 ≥50%", "EGFR mutation negative"
- allocation_ratio: e.g., "1:1", "2:1"
- blinding_type: e.g., "Open-label", "Double-blind"

RESPOND IN JSON:
{{
    "treatment_setting": "<exact setting or [NOT FOUND]>",
    "disease_type": "<specific disease or [NOT FOUND]>",
    "phase": "<phase>",
    "drug_name": "<drug>",
    "comparator": "<comparator>",
    "histology": "<histology or null>",
    "disease_stage": "<stage or null>",
    "biomarker_status": "<status or null>",
    "allocation_ratio": "<ratio>",
    "blinding_type": "<blinding>",
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'stratification': '''Extract STRATIFICATION information from this protocol section.

SEARCH AGGRESSIVELY for these patterns:
- "stratified by" or "stratification factors" or "stratification variables"
- "randomization stratified" or "stratified randomization"
- Look for lists after "stratified by:" such as:
  - Geographic region (e.g., "East Asia vs Rest of World")
  - Performance status (e.g., "ECOG 0 vs 1")
  - PD-L1 status (e.g., "<1% vs ≥1%", "TPS <50% vs ≥50%")
  - Histology (e.g., "squamous vs non-squamous")
  - Prior therapy (e.g., "yes vs no")
  - Sex (e.g., "male vs female")
  - Smoking status (e.g., "never vs ever")
  - Disease stage, metastases, brain metastases

Required fields:
- stratification_factors: List ALL factors mentioned, even if in different parts of protocol

Critical field (MUST extract with full detail):
- stratification_factor_levels: For EACH factor, extract EXACT levels/categories
  Example: {{"Region": ["East Asia", "Rest of World"], "ECOG PS": ["0", "1"], "PD-L1": ["<1%", "1-49%", "≥50%"]}}

RESPOND IN JSON:
{{
    "stratification_factors": ["<factor1>", "<factor2>", "<factor3>", ...],
    "stratification_factor_levels": {{"<factor>": ["<level1>", "<level2>"], ...}},
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'sample_size': '''Extract SAMPLE SIZE information from this protocol section.

SEARCH AGGRESSIVELY for these patterns:
- "N = ###" or "n = ###" or "### patients" or "### subjects" or "### participants"
- "sample size of ###" or "enroll ###" or "randomize ###" or "total of ###"
- "### per arm" or "### in each arm" or "1:1" (implies equal arms)
- "power of ##%" or "##% power" or "power = 0.##"
- "HR of 0.##" or "hazard ratio 0.##" or "HR = 0.##"
- Look for tables with sample size calculations

Required fields:
- sample_size: Total number of patients (look for N=, total, enrolled)
- power: Statistical power as decimal 0.0-1.0 (convert 80% to 0.80, 90% to 0.90)

Optional fields:
- sample_size_per_arm: Number per treatment arm [arm1_n, arm2_n]
- sample_size_rationale: Text describing the calculation basis
- hazard_ratio: Expected/assumed hazard ratio (usually 0.6-0.8 for oncology)
- allocation_ratio: Randomization ratio like "1:1" or "2:1"

RESPOND IN JSON:
{{
    "sample_size": <number or null if truly not found>,
    "power": <0.0-1.0 or null>,
    "sample_size_per_arm": [<arm1_n>, <arm2_n>] or null,
    "sample_size_rationale": "<text>" or null,
    "hazard_ratio": <number> or null,
    "allocation_ratio": "<ratio>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'endpoints': '''Extract ENDPOINT information from this protocol section.

SEMANTIC SEARCH - Look for these CONCEPTS:
- "primary endpoint" / "primary outcome" / "primary efficacy" / "primary objective"
- "PFS" / "progression-free survival" / "time to progression"
- "OS" / "overall survival" / "time to death"
- "ORR" / "objective response rate" / "tumor response" / "response rate"
- "DOR" / "duration of response" / "DoR"
- "DCR" / "disease control rate"
- "TTR" / "time to response"
- "secondary endpoint" / "secondary outcome" / "key secondary"
- "co-primary" / "dual primary" / "two primary endpoints"
- "RECIST" / "irRECIST" / "iRECIST" / "mRECIST" / "BICR" / "blinded independent"
- "defined as" / "measured as" / "time from randomization"

Required fields:
- primary_endpoint: The PRIMARY endpoint with its FULL definition
  Example: "Progression-free survival (PFS), defined as time from randomization to first documented disease progression per RECIST 1.1 or death"

Optional fields:
- secondary_endpoints: List ALL secondary endpoints mentioned
- is_co_primary: true if there are CO-PRIMARY endpoints (both must succeed)
- co_primary_endpoints: List the co-primary endpoints if is_co_primary is true
- assessment_criteria: Response assessment criteria

RESPOND IN JSON:
{{
    "primary_endpoint": "<endpoint name AND full definition>",
    "secondary_endpoints": ["<endpoint1 with definition>", "<endpoint2>", ...],
    "is_co_primary": <true/false>,
    "co_primary_endpoints": ["<co-primary1>", "<co-primary2>"] or [],
    "assessment_criteria": "<criteria>",
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'statistical_methods': '''Extract STATISTICAL METHODS information from this protocol section.

SEMANTIC SEARCH - Look for these CONCEPTS:
- "log-rank" / "logrank" / "log rank" / "Mantel-Cox"
- "stratified log-rank" / "stratified analysis" / "adjusted for stratification"
- "Fleming-Harrington" / "weighted log-rank" / "G(rho,gamma)" / "ρ=" / "γ="
- "Cox" / "proportional hazards" / "Cox regression" / "hazard ratio"
- "Kaplan-Meier" / "survival curves" / "survival analysis"
- "one-sided" / "two-sided" / "α=0.025" / "α=0.05"
- "null hypothesis" / "H0:" / "alternative hypothesis" / "H1:" / "Ha:"
- "superiority" / "non-inferiority" / "equivalence"
- "Fisher exact" / "chi-square" / "χ²" / "Cochran-Mantel-Haenszel" / "CMH"
- "confidence interval" / "CI" / "95% CI" / "hazard ratio with 95% CI"

CRITICAL: Extract the EXACT method specified. DO NOT infer based on drug class.

Required field:
- statistical_method: The primary statistical test with full specification
  Example: "Stratified log-rank test, stratified by ECOG PS and region"
  Example: "Fleming-Harrington weighted log-rank test with ρ=0, γ=1"

Optional fields:
- null_hypothesis: e.g., "HR = 1.0" or "HR ≥ 1.0"
- alternative_hypothesis: e.g., "HR < 1.0" or "HR ≠ 1.0"
- test_sidedness: "one-sided" or "two-sided"
- hazard_ratio_method: How HR is estimated (e.g., "unstratified Cox model")

If the statistical method is NOT explicitly stated, return:
"statistical_method": "[STATISTICAL METHOD NOT FOUND IN PROTOCOL - NEEDS REVIEW]"

RESPOND IN JSON:
{{
    "statistical_method": "<exact method from protocol or [STATISTICAL METHOD NOT FOUND IN PROTOCOL - NEEDS REVIEW]>",
    "null_hypothesis": "<H0>" or null,
    "alternative_hypothesis": "<H1>" or null,
    "test_sidedness": "<sidedness>",
    "hazard_ratio_method": "<HR estimation method>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'interim_analysis': '''Extract INTERIM ANALYSIS information from this protocol section.

SEMANTIC SEARCH - Look for these CONCEPTS (not just exact phrases):
- "interim analysis" / "interim look" / "planned looks" / "group sequential"
- "### events" / "### deaths" / "### PFS events" / "### OS events" / "target events"
- "information fraction" / "information time" / "% of events" / "% information"
- "alpha spending" / "spending function" / "O'Brien-Fleming" / "Lan-DeMets" / "Pocock"
- "stopping boundary" / "efficacy boundary" / "futility boundary" / "early stopping"
- "one-sided alpha" / "two-sided alpha" / "α=" / "alpha="
- Tables showing: IA1, IA2, FA or Interim 1, Interim 2, Final
- "first interim at ###" / "second interim at ###" / "final at ###"

Required fields:
- has_interim_analysis: true if ANY interim analysis is mentioned
- num_interim_analyses: Count distinct interim looks (IA1, IA2, etc.)

CRITICAL fields - extract ALL numbers you find:
- interim_events: Events at each interim [e.g., [175, 350] for 2 interims]
- final_events: Events at final analysis [e.g., 500]
- information_fractions: [e.g., [0.35, 0.70, 1.0] for 35%, 70%, 100%]
- alpha_spending_function: The spending function name
- alpha_at_interim: Alpha spent at each interim [e.g., [0.0001, 0.005]]
- alpha_at_final: Remaining alpha [e.g., 0.0199]
- stopping_boundaries: HR thresholds or Z-values for stopping
- interim_by_endpoint: SEPARATE structure per endpoint (PFS vs OS often differ!)

RESPOND IN JSON:
{{
    "has_interim_analysis": <true/false>,
    "num_interim_analyses": <number>,
    "interim_events": [<events1>, <events2>] or null,
    "final_events": <number> or null,
    "information_fractions": [<frac1>, <frac2>, 1.0] or null,
    "alpha_spending_function": "<function>" or null,
    "alpha_at_interim": [<alpha1>, <alpha2>] or null,
    "alpha_at_final": <number> or null,
    "stopping_boundaries": "<description>" or null,
    "interim_by_endpoint": [
        {{"endpoint": "PFS", "timing": "<when>", "events": <n>, "alpha": <a>}},
        {{"endpoint": "OS", "timing": "<when>", "events": <n>, "alpha": <a>}}
    ] or [],
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'multiplicity': '''Extract MULTIPLICITY information from this protocol section.

SEMANTIC SEARCH - Look for these CONCEPTS:
- "multiplicity" / "multiple testing" / "multiple endpoints" / "multiple hypotheses"
- "H1" / "H2" / "H3" / "H4" / "H5" / "hypothesis 1" / "hypothesis 2"
- "hierarchical testing" / "gatekeeping" / "fixed sequence" / "sequential testing"
- "graphical approach" / "Maurer-Bretz" / "weighted Bonferroni"
- "Hochberg" / "Holm" / "Bonferroni" / "Simes"
- "alpha allocation" / "α=" / "one-sided 0.0###" / "two-sided 0.0###"
- "type I error" / "FWER" / "familywise error rate"
- "primary hypothesis" / "secondary hypothesis" / "key secondary"
- "tested at α=" / "tested at alpha" / "significance level"
- Diagrams or tables showing hypothesis structure

Required field:
- has_multiplicity: true if ANY alpha adjustment or multiple hypothesis testing is mentioned

CRITICAL fields - extract the FULL hypothesis structure:
- hypotheses_list: List each hypothesis with its definition
  Example: ["H1: PFS in ITT", "H2: OS in ITT", "H3: PFS in PD-L1≥50%", "H4: OS in PD-L1≥50%"]
- alpha_per_hypothesis: Alpha for EACH hypothesis
  Example: {{"H1": 0.0125, "H2": 0.0125, "H3": 0.0125, "H4": 0.0125}}
- adjustment_method: The specific method used
- testing_sequence: Order of testing (which hypotheses are tested first, second, etc.)
- alpha_propagation: How alpha is recycled when hypotheses are rejected

RESPOND IN JSON:
{{
    "has_multiplicity": <true/false>,
    "adjustment_method": "<method>" or null,
    "hypotheses_list": ["H1: <definition>", "H2: <definition>", ...] or [],
    "testing_sequence": ["<H1>", "<H2>", ...] or [],
    "alpha_per_hypothesis": {{"H1": <alpha>, "H2": <alpha>, ...}} or {{}},
    "alpha_propagation": "<how alpha flows between hypotheses>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'missing_data': '''Extract MISSING DATA handling information from this protocol section.

Fields:
- censoring_rules: List of censoring rules for time-to-event endpoints
- treatment_discontinuation_strategy: How treatment discontinuation is handled
- tipping_point_analysis: true/false
- subsequent_therapy_handling: How subsequent therapies are handled

RESPOND IN JSON:
{{
    "censoring_rules": ["<rule1>", "<rule2>", ...],
    "treatment_discontinuation_strategy": "<strategy>" or null,
    "tipping_point_analysis": <true/false>,
    "subsequent_therapy_handling": "<handling>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'populations': '''Extract ANALYSIS POPULATIONS from this protocol section.

Fields:
- itt_definition: Intent-to-treat population definition
- fas_definition: Full Analysis Set definition (often same as ITT)
- per_protocol_definition: Per-protocol population definition
- safety_population_definition: Safety population definition

RESPOND IN JSON:
{{
    "itt_definition": "<definition>",
    "fas_definition": "<definition>" or null,
    "per_protocol_definition": "<definition>" or null,
    "safety_population_definition": "<definition>",
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'estimand': '''Extract ESTIMAND information from this protocol section (ICH E9 R1).

The estimand framework has 5 attributes:
1. Population: Target patient population
2. Variable: Endpoint being measured
3. Intercurrent events: Events occurring post-randomization that affect interpretation
4. Strategy: How each intercurrent event is handled
5. Population-level summary: Statistical measure (e.g., hazard ratio)

RESPOND IN JSON:
{{
    "estimand_population": "<population description>" or null,
    "estimand_variable": "<endpoint>" or null,
    "intercurrent_events": [
        {{"event": "<event1>", "strategy": "<strategy1>"}},
        {{"event": "<event2>", "strategy": "<strategy2>"}}
    ] or [],
    "primary_estimand": "<full estimand statement>" or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'crossover': '''Extract CROSSOVER/TREATMENT SWITCHING information from this protocol section.

Fields:
- has_crossover: true/false - is crossover permitted?
- crossover_description: When/how crossover is allowed
- crossover_adjustment_methods: Statistical methods for adjusting crossover bias
  (e.g., "RPSFT", "IPCW", "Two-stage")

RESPOND IN JSON:
{{
    "has_crossover": <true/false>,
    "crossover_description": "<description>" or null,
    "crossover_adjustment_methods": ["<method1>", "<method2>"] or [],
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}'''
    }

    # Map our section names to ProtocolSectionParser section names
    SECTION_MAPPING = {
        'study_design': ['study_design', 'objectives'],
        'stratification': ['study_design', 'statistical_methods'],
        'sample_size': ['sample_size', 'statistical_methods'],
        'endpoints': ['endpoints', 'objectives'],
        'statistical_methods': ['statistical_methods', 'sample_size'],
        'interim_analysis': ['interim_analysis', 'statistical_methods'],
        'multiplicity': ['multiplicity', 'statistical_methods'],
        'missing_data': ['missing_data', 'statistical_methods', 'sensitivity'],
        'populations': ['populations', 'analysis_sets'],
        'estimand': ['estimand', 'endpoints', 'statistical_methods'],
        'crossover': ['statistical_methods', 'sensitivity'],
    }

    def __init__(self, llm_client=None):
        """
        Initialize sectioned extractor.

        Args:
            llm_client: LLM client with chat() method
        """
        self.llm = llm_client
        self.section_parser = ProtocolSectionParser()
        self._parsed_protocol: Optional[ParsedProtocol] = None

    def _get_relevant_text(self, section_name: str, protocol_text: str, max_chars: int = 25000) -> str:
        """
        Get relevant text for a section by:
        1. Parsing protocol into sections
        2. Returning combined text from relevant sections
        3. Falling back to keyword search if parsing fails
        """
        # Parse protocol if not already done
        if self._parsed_protocol is None or self._parsed_protocol.raw_text != protocol_text:
            self._parsed_protocol = self.section_parser.parse(protocol_text)
            print(f"[SectionedExtractor] Parsed protocol into {len(self._parsed_protocol.sections)} sections")

        # Get relevant section names
        relevant_sections = self.SECTION_MAPPING.get(section_name, [section_name])

        # Combine text from relevant sections
        combined_text = []
        for sect in relevant_sections:
            content = self._parsed_protocol.get(sect, "")
            if content:
                combined_text.append(f"=== {sect.upper()} SECTION ===\n{content}")

        result = "\n\n".join(combined_text) if combined_text else ""
        print(f"[SectionedExtractor] Found {len(result)} chars from parsed sections for {section_name}")
        return result[:max_chars]

    def extract_section(
        self,
        section_name: str,
        protocol_text: str,
        max_tokens: int = 1500
    ) -> SectionExtractionResult:
        """
        Extract a single section from the protocol.

        Uses intelligent section parsing to find relevant text instead of
        simple truncation.

        Args:
            section_name: Name of section to extract
            protocol_text: Full protocol text (extractor will find relevant parts)
            max_tokens: Max tokens for LLM response

        Returns:
            SectionExtractionResult with extracted fields and confidence
        """
        if section_name not in self.SECTION_PROMPTS:
            raise ValueError(f"Unknown section: {section_name}")

        prompt = self.SECTION_PROMPTS[section_name]

        # Get RELEVANT text for this section (not just truncation!)
        relevant_text = self._get_relevant_text(section_name, protocol_text, max_chars=25000)

        # Diagnostic: Show first 500 chars of relevant text
        print(f"[Extractor] {section_name}: {len(relevant_text)} chars of relevant text")
        print(f"[Extractor] {section_name} preview: {relevant_text[:500]}...")

        # Build full prompt with section-relevant text
        full_prompt = f"""You are extracting structured information from a clinical trial protocol.

RELEVANT PROTOCOL SECTIONS FOR {section_name.upper()}:
{relevant_text}

{prompt}

Remember: Extract ONLY what is explicitly stated. Mark fields as [NOT FOUND] if not present.
"""

        try:
            response = self.llm.chat(full_prompt, max_tokens=max_tokens)

            # Handle different response types
            if hasattr(response, 'content'):
                response_text = response.content
            elif isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)

            # Diagnostic: Show LLM response
            print(f"[Extractor] {section_name} LLM response: {response_text[:800]}...")

            # Parse JSON response
            result = self._parse_section_response(section_name, response_text)
            return result

        except Exception as e:
            print(f"[SectionedExtractor] Error extracting {section_name}: {e}")
            return SectionExtractionResult(
                section_name=section_name,
                extracted_fields={},
                confidence=0.0,
                fields_found=[],
                fields_not_found=self.SECTIONS[section_name].get('required', []),
                needs_review=self.SECTIONS[section_name].get('critical', []),
                notes=[f"Extraction failed: {str(e)}"]
            )

    def _parse_section_response(
        self,
        section_name: str,
        response_text: str
    ) -> SectionExtractionResult:
        """Parse LLM response for a section."""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                raise ValueError("No JSON found in response")

            data = json.loads(json_match.group())

            # Analyze what was found vs not found
            section_def = self.SECTIONS[section_name]
            required = section_def.get('required', [])
            critical = section_def.get('critical', [])

            fields_found = []
            fields_not_found = []
            needs_review = []

            for field in required + section_def.get('optional', []):
                value = data.get(field)

                if value is None or value == "" or value == [] or value == {}:
                    fields_not_found.append(field)
                    if field in critical:
                        needs_review.append(field)
                elif isinstance(value, str) and '[NOT FOUND]' in value:
                    fields_not_found.append(field)
                    if field in critical:
                        needs_review.append(field)
                elif isinstance(value, str) and '[NEEDS REVIEW]' in value:
                    needs_review.append(field)
                    fields_found.append(field)
                else:
                    fields_found.append(field)

            return SectionExtractionResult(
                section_name=section_name,
                extracted_fields=data,
                confidence=data.get('confidence', 0.5),
                fields_found=fields_found,
                fields_not_found=fields_not_found,
                needs_review=needs_review,
                notes=data.get('notes', [])
            )

        except json.JSONDecodeError as e:
            return SectionExtractionResult(
                section_name=section_name,
                extracted_fields={},
                confidence=0.0,
                fields_found=[],
                fields_not_found=[],
                needs_review=[],
                notes=[f"JSON parse error: {str(e)}"]
            )

    def extract_all_sections(
        self,
        protocol_text: str,
        sections: Optional[List[str]] = None
    ) -> Tuple[ExtractedProtocolFacts, Dict[str, SectionExtractionResult]]:
        """
        Extract all sections from a protocol.

        Args:
            protocol_text: Full protocol text
            sections: Optional list of sections to extract (default: all)

        Returns:
            Tuple of (ExtractedProtocolFacts, dict of section results)
        """
        if sections is None:
            sections = list(self.SECTIONS.keys())

        section_results = {}
        combined_data = {}

        for section_name in sections:
            print(f"[SectionedExtractor] Extracting: {section_name}")
            result = self.extract_section(section_name, protocol_text)
            section_results[section_name] = result

            # Merge extracted fields
            for field, value in result.extracted_fields.items():
                if field not in ['confidence', 'notes']:
                    combined_data[field] = value

            print(f"  - Confidence: {result.confidence:.0%}")
            print(f"  - Found: {len(result.fields_found)} fields")
            print(f"  - Not found: {len(result.fields_not_found)} fields")
            if result.needs_review:
                print(f"  - NEEDS REVIEW: {result.needs_review}")

        # Convert to ExtractedProtocolFacts
        facts = from_claude_extraction(combined_data)

        # Calculate overall confidence
        if section_results:
            facts.confidence.overall_confidence = sum(
                r.confidence for r in section_results.values()
            ) / len(section_results)

            facts.confidence.section_confidence = {
                name: r.confidence for name, r in section_results.items()
            }

            facts.confidence.needs_review = []
            facts.confidence.not_found = []
            for r in section_results.values():
                facts.confidence.needs_review.extend(r.needs_review)
                facts.confidence.not_found.extend(r.fields_not_found)

        return facts, section_results


def create_sectioned_extractor(llm_client=None) -> SectionedProtocolExtractor:
    """Factory function for sectioned extractor."""
    return SectionedProtocolExtractor(llm_client=llm_client)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Sectioned Protocol Extractor")
    print("=" * 60)

    # Test section prompts
    extractor = SectionedProtocolExtractor()

    print(f"\nSections defined: {len(extractor.SECTIONS)}")
    for section in extractor.SECTIONS:
        section_def = extractor.SECTIONS[section]
        print(f"  {section}:")
        print(f"    - Required: {len(section_def.get('required', []))} fields")
        print(f"    - Optional: {len(section_def.get('optional', []))} fields")
        print(f"    - Critical: {section_def.get('critical', [])}")
