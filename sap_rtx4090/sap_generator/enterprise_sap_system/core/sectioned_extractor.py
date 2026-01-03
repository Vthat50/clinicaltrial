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
            'optional': ['null_hypothesis', 'alternative_hypothesis', 'test_sidedness'],
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
            'optional': ['adjustment_method', 'testing_sequence', 'alpha_per_hypothesis'],
            'critical': ['alpha_per_hypothesis']
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

Required fields:
- stratification_factors: List of randomization stratification factors

Critical field (must extract with detail):
- stratification_factor_levels: For EACH stratification factor, list the EXACT levels/categories.
  Example: {{"PD-L1 status": ["<1%", "1-49%", "≥50%"], "ECOG PS": ["0", "1"]}}

RESPOND IN JSON:
{{
    "stratification_factors": ["<factor1>", "<factor2>", ...],
    "stratification_factor_levels": {{"<factor>": ["<level1>", "<level2>"], ...}},
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'sample_size': '''Extract SAMPLE SIZE information from this protocol section.

Required fields:
- sample_size: Total number of patients to be enrolled
- power: Statistical power (e.g., 0.80 for 80%, 0.90 for 90%)

Optional fields:
- sample_size_per_arm: Number per treatment arm
- sample_size_rationale: Text describing the calculation basis
- hazard_ratio: Expected/assumed hazard ratio

RESPOND IN JSON:
{{
    "sample_size": <number>,
    "power": <0.0-1.0>,
    "sample_size_per_arm": [<arm1_n>, <arm2_n>] or null,
    "sample_size_rationale": "<text>" or null,
    "hazard_ratio": <number> or null,
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'endpoints': '''Extract ENDPOINT information from this protocol section.

Required fields:
- primary_endpoint: The primary efficacy endpoint with definition

Optional fields:
- secondary_endpoints: List of secondary endpoints
- is_co_primary: true/false - are there co-primary endpoints?
- co_primary_endpoints: List if is_co_primary is true
- assessment_criteria: e.g., "RECIST 1.1", "irRECIST"

RESPOND IN JSON:
{{
    "primary_endpoint": "<endpoint name and definition>",
    "secondary_endpoints": ["<endpoint1>", "<endpoint2>", ...],
    "is_co_primary": <true/false>,
    "co_primary_endpoints": ["<endpoint1>", "<endpoint2>"] or [],
    "assessment_criteria": "<criteria>",
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'statistical_methods': '''Extract STATISTICAL METHODS information from this protocol section.

CRITICAL: Extract the EXACT method specified in the protocol. DO NOT infer based on drug class.

Required field (MUST extract from protocol text, not infer):
- statistical_method: The primary statistical test. Look for:
  - "log-rank test" (with or without stratification)
  - "stratified log-rank test"
  - "Fleming-Harrington" or "weighted log-rank" (with rho/gamma parameters if specified)
  - "Cox proportional hazards"
  - "Fisher's exact test", "Chi-square test" (for binary endpoints)

Optional fields:
- null_hypothesis: e.g., "HR = 1.0"
- alternative_hypothesis: e.g., "HR < 1.0"
- test_sidedness: "one-sided" or "two-sided"

If the statistical method is NOT explicitly stated, return:
"statistical_method": "[STATISTICAL METHOD NOT FOUND IN PROTOCOL - NEEDS REVIEW]"

RESPOND IN JSON:
{{
    "statistical_method": "<exact method from protocol or [STATISTICAL METHOD NOT FOUND IN PROTOCOL - NEEDS REVIEW]>",
    "null_hypothesis": "<H0>" or null,
    "alternative_hypothesis": "<H1>" or null,
    "test_sidedness": "<sidedness>",
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'interim_analysis': '''Extract INTERIM ANALYSIS information from this protocol section.

Required fields:
- has_interim_analysis: true/false
- num_interim_analyses: Number of planned interim analyses (0 if none)

Optional but critical fields (if has_interim_analysis is true):
- interim_events: Events required at each interim [list of integers]
- final_events: Events required at final analysis [integer]
- information_fractions: Proportion of information at each look [list of floats]
- alpha_spending_function: e.g., "Lan-DeMets O'Brien-Fleming", "Pocock"
- alpha_at_interim: Alpha spent at each interim [list of floats]
- alpha_at_final: Alpha remaining for final analysis [float]
- stopping_boundaries: Description of stopping rules
- interim_by_endpoint: Per-endpoint IA structure if multiple endpoints

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
        {{"endpoint": "PFS", "timing": "<timing>", "events": <n>, "alpha": <a>}},
        {{"endpoint": "OS", "timing": "<timing>", "events": <n>, "alpha": <a>}}
    ] or [],
    "confidence": <0.0-1.0>,
    "notes": ["<any extraction notes>"]
}}''',

        'multiplicity': '''Extract MULTIPLICITY information from this protocol section.

Required field:
- has_multiplicity: true/false - is there multiplicity adjustment?

Critical optional field:
- alpha_per_hypothesis: Explicit alpha allocation per hypothesis/endpoint
  Example: {{"PFS": 0.025, "OS": 0.025}} or {{"PFS": 0.0125, "OS": 0.0125, "ORR": 0.025}}

Other optional fields:
- adjustment_method: e.g., "Hierarchical", "Graphical (Maurer & Bretz)", "Hochberg"
- testing_sequence: Order of hypothesis testing

RESPOND IN JSON:
{{
    "has_multiplicity": <true/false>,
    "adjustment_method": "<method>" or null,
    "testing_sequence": ["<H1>", "<H2>", ...] or [],
    "alpha_per_hypothesis": {{"<endpoint>": <alpha>, ...}} or {{}},
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

    def __init__(self, llm_client=None):
        """
        Initialize sectioned extractor.

        Args:
            llm_client: LLM client with chat() method
        """
        self.llm = llm_client

    def extract_section(
        self,
        section_name: str,
        protocol_text: str,
        max_tokens: int = 1500
    ) -> SectionExtractionResult:
        """
        Extract a single section from the protocol.

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

        # Build full prompt with protocol text
        full_prompt = f"""You are extracting structured information from a clinical trial protocol.

PROTOCOL TEXT:
{protocol_text[:15000]}  # Limit to avoid token overflow

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
