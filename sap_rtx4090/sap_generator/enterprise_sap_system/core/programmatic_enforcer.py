#!/usr/bin/env python3
"""
Programmatic Enforcement Module for SAP Generation
===================================================
This module ENFORCES protocol faithfulness through code, NOT LLM instructions.

Key principle: LLMs cannot reliably follow rules. Therefore:
1. Extract critical content using regex (not LLM)
2. Let LLM generate prose
3. PROGRAMMATICALLY verify and correct the output

This solves:
- Primary endpoint definition mismatch
- Primary/secondary endpoint swapping
- FAS definition drift ("took at least one dose" added)
- Missing stratification factors
- Alpha sidedness drift
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class VerbatimDefinition:
    """Stores an exact definition extracted from protocol."""
    text: str
    source_section: str
    position: str  # "PRIMARY", "SECONDARY", "EXPLORATORY"
    char_span: Tuple[int, int]


@dataclass
class EnforcementResult:
    """Result of programmatic enforcement."""
    original: str
    corrected: str
    violations_found: List[str]
    corrections_made: List[str]


class ProtocolVerbatimExtractor:
    """
    Extracts critical definitions from protocol using REGEX, not LLM.
    These extracted values are treated as ground truth.
    """

    # Patterns to find primary endpoint definition
    PRIMARY_ENDPOINT_PATTERNS = [
        # "Primary endpoint: <definition>" or "The primary endpoint is <definition>"
        r'primary\s+(?:efficacy\s+)?endpoint[:\s]+["\']?(.+?)["\']?(?=\s*(?:secondary|key secondary|\n\n|\d+\.\d+\s+[A-Z]))',
        r'the\s+primary\s+(?:efficacy\s+)?endpoint\s+(?:is|will\s+be)[:\s]+["\']?(.+?)["\']?(?=\.)',
        r'primary\s+endpoint\s+for\s+this\s+study[:\s]+["\']?(.+?)["\']?(?=\s*(?:secondary|\n))',
    ]

    # Patterns to find FAS/ITT population definitions
    POPULATION_PATTERNS = {
        'FAS': [
            # "Full Analysis Set (FAS): all randomised patients..."
            r'(?:full\s+analysis\s+set|FAS)[:\s]+all\s+(.+?)(?=\s*(?:\n\n|\d+\.\d+|per[\s-]?protocol|safety\s+population|PP\s*:))',
            r'(?:full\s+analysis\s+set|FAS)\s*[:=]\s*["\']?(.+?)["\']?(?=\s*(?:\n|per[\s-]protocol|safety|PP\b))',
            r'(?:full\s+analysis\s+set|FAS)\s+(?:is\s+)?(?:defined\s+as|includes?|consists?\s+of)[:\s]+["\']?(.+?)["\']?(?=\.)',
            # "FAS: all randomized..." pattern
            r'FAS[:\s]+all\s+(.+?)(?=\s*(?:\.|PP|safety|per[\s-]protocol|\n\n))',
            # Simple pattern for "all randomised patients with..."
            r'(?:FAS|full\s+analysis\s+set)[:\s]+(all\s+randomi[sz]ed\s+patients?.+?)(?=\s*(?:\n\n|\d+\.))',
        ],
        'ITT': [
            r'(?:intent(?:ion)?[\s-]to[\s-]treat|ITT)\s*[:=]\s*["\']?(.+?)["\']?(?=\s*(?:\n|FAS|safety|PP\b))',
            r'(?:intent(?:ion)?[\s-]to[\s-]treat|ITT)\s+(?:is\s+)?(?:defined\s+as|includes?)[:\s]+["\']?(.+?)["\']?(?=\.)',
        ],
    }

    # Patterns to find stratification factors
    STRATIFICATION_PATTERNS = [
        r'stratif(?:ied|ication)\s+(?:by|factors?)[:\s]+(.+?)(?=\s*(?:\.|randomiz|subjects?\s+will))',
        r'stratification\s+factors?\s*[:=]\s*(.+?)(?=\s*(?:\n\n|\d+\.\d+))',
        r'balanced\s+by[:\s]+(.+?)(?=\.)',
    ]

    # Patterns for alpha/significance level
    ALPHA_PATTERNS = [
        # "one-sided 5% level" or "one-sided 20% level"
        r'(one[\s-]?sided)\s+(\d+)\s*%?\s*(?:level|significance)?',
        r'(two[\s-]?sided)\s+(\d+)\s*%?\s*(?:level|significance)?',
        r'(one[\s-]?sided|two[\s-]?sided)\s+(?:alpha|significance|α)\s*(?:level\s+)?(?:of\s+)?(\d+\.?\d*)\s*%?',
        r'α\s*=\s*(\d+\.?\d*)\s*(?:\(?(one[\s-]?sided|two[\s-]?sided)\)?)?',
        r'significance\s+level\s+(?:of\s+)?(\d+\.?\d*)\s*%?\s*(?:\(?(one[\s-]?sided|two[\s-]?sided)\)?)?',
    ]

    def extract_primary_endpoint_verbatim(self, protocol_text: str) -> Optional[VerbatimDefinition]:
        """
        Extract the EXACT primary endpoint text from protocol.
        Returns None if not found (should trigger manual review).
        """
        for pattern in self.PRIMARY_ENDPOINT_PATTERNS:
            match = re.search(pattern, protocol_text, re.IGNORECASE | re.DOTALL)
            if match:
                text = match.group(1).strip()
                # Clean up any trailing punctuation but preserve internal content
                text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
                return VerbatimDefinition(
                    text=text,
                    source_section="Primary Endpoint Section",
                    position="PRIMARY",
                    char_span=match.span(1)
                )
        return None

    def extract_population_verbatim(self, protocol_text: str, pop_name: str) -> Optional[VerbatimDefinition]:
        """Extract exact population definition from protocol."""
        # Try specific patterns first
        patterns = self.POPULATION_PATTERNS.get(pop_name, [])
        for pattern in patterns:
            match = re.search(pattern, protocol_text, re.IGNORECASE | re.DOTALL)
            if match:
                text = match.group(1).strip()
                text = re.sub(r'\s+', ' ', text)
                return VerbatimDefinition(
                    text=text,
                    source_section="Analysis Populations Section",
                    position=pop_name,
                    char_span=match.span(1)
                )

        # Fallback: Look for section-based extraction
        if pop_name == 'FAS':
            # Look for "Full Analysis Set (FAS):" followed by definition
            fas_section = re.search(
                r'(?:full\s+analysis\s+set|FAS)[^:]*:[^\n]*\n?\s*(all\s+[^\n]+)',
                protocol_text,
                re.IGNORECASE | re.DOTALL
            )
            if fas_section:
                text = fas_section.group(1).strip()
                text = re.sub(r'\s+', ' ', text)
                # Clean up trailing section markers
                text = re.sub(r'\s*\d+\.\d+.*$', '', text)
                return VerbatimDefinition(
                    text=text,
                    source_section="Analysis Populations Section",
                    position=pop_name,
                    char_span=fas_section.span(1)
                )

        return None

    def extract_all_stratification_factors(self, protocol_text: str) -> List[str]:
        """
        Extract ALL stratification factors.
        Returns raw list - does NOT filter or modify.
        """
        factors = []
        for pattern in self.STRATIFICATION_PATTERNS:
            matches = re.findall(pattern, protocol_text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                # Split on common delimiters
                raw = match if isinstance(match, str) else match[0]
                # Handle "X and Y" or "X, Y" patterns
                parts = re.split(r'\s+and\s+|,\s*', raw, flags=re.IGNORECASE)
                for part in parts:
                    cleaned = part.strip().strip('"\'')
                    if cleaned and len(cleaned) > 3:  # Skip empty/tiny matches
                        factors.append(cleaned)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for f in factors:
            f_lower = f.lower()
            if f_lower not in seen:
                seen.add(f_lower)
                unique.append(f)

        return unique

    def extract_alpha_specification(self, protocol_text: str) -> Dict:
        """Extract alpha level and sidedness."""
        result = {
            'primary_alpha': 0.05,  # Default
            'sidedness': 'two-sided',  # Default
            'additional_levels': [],
        }

        # First check for one-sided mentions
        if re.search(r'one[\s-]?sided', protocol_text, re.IGNORECASE):
            result['sidedness'] = 'one-sided'

        # Find all percentage levels mentioned with one-sided
        one_sided_levels = re.findall(
            r'one[\s-]?sided\s+(\d+)\s*%',
            protocol_text,
            re.IGNORECASE
        )

        if one_sided_levels:
            # Convert to floats
            levels = [float(l) / 100 for l in one_sided_levels]
            # The smaller one is usually primary (5%), larger is exploratory (20%)
            levels = sorted(set(levels))
            if levels:
                result['primary_alpha'] = min(levels)
                result['additional_levels'] = [l for l in levels if l != result['primary_alpha']]

        # Standard alpha patterns for fallback
        for pattern in self.ALPHA_PATTERNS:
            match = re.search(pattern, protocol_text, re.IGNORECASE)
            if match:
                groups = match.groups()
                for g in groups:
                    if g:
                        if 'one' in g.lower():
                            result['sidedness'] = 'one-sided'
                        elif 'two' in g.lower():
                            result['sidedness'] = 'two-sided'
                        elif re.match(r'^\d+\.?\d*$', g):
                            val = float(g)
                            if val > 1:
                                val = val / 100  # Convert percentage
                            if val not in result['additional_levels'] and val != result['primary_alpha']:
                                if val < result['primary_alpha']:
                                    result['additional_levels'].append(result['primary_alpha'])
                                    result['primary_alpha'] = val
                                else:
                                    result['additional_levels'].append(val)

        return result


class SAPOutputEnforcer:
    """
    PROGRAMMATICALLY enforces that SAP output matches protocol.
    This is the key innovation: don't trust LLM to follow rules - verify and correct.
    """

    # Common phrases LLMs add that shouldn't be there
    UNAUTHORIZED_FAS_ADDITIONS = [
        r'who\s+(?:took|received)\s+at\s+least\s+one\s+dose',
        r'and\s+had\s+at\s+least\s+one\s+post[\s-]?baseline',
        r'who\s+received\s+(?:any\s+)?study\s+(?:drug|medication)',
        r'and\s+(?:had|have)\s+at\s+least\s+one\s+efficacy',
    ]

    # Patterns that indicate wrong endpoint type
    ENDPOINT_TYPE_ERRORS = {
        'partial_for_full': (r'partial\s+mayo', r'full\s+mayo'),
        'missing_endoscopy': (r'(?<!endoscop)clinical\s+remission(?!\s*and\s*endoscop)', r'clinical\s+and\s+endoscopic\s+remission'),
    }

    def __init__(self, extractor: ProtocolVerbatimExtractor):
        self.extractor = extractor

    def enforce_primary_endpoint(
        self,
        sap_text: str,
        protocol_endpoint: VerbatimDefinition
    ) -> EnforcementResult:
        """
        Ensure primary endpoint in SAP matches protocol EXACTLY.
        If not, FORCE correction.
        """
        violations = []
        corrections = []
        corrected = sap_text

        # Check if protocol endpoint appears verbatim in SAP
        if protocol_endpoint.text.lower() not in sap_text.lower():
            # Find what SAP actually says for primary endpoint
            sap_endpoint_match = re.search(
                r'(?:primary\s+endpoint|primary\s+efficacy\s+endpoint)[:\s]+["\']?(.+?)["\']?(?=\s*(?:\n|secondary|key))',
                sap_text,
                re.IGNORECASE | re.DOTALL
            )

            if sap_endpoint_match:
                sap_endpoint = sap_endpoint_match.group(1).strip()

                # Check how different they are
                similarity = SequenceMatcher(
                    None,
                    protocol_endpoint.text.lower(),
                    sap_endpoint.lower()
                ).ratio()

                if similarity < 0.9:  # Less than 90% similar = significant drift
                    violations.append(
                        f"Primary endpoint drift detected (similarity: {similarity:.0%}):\n"
                        f"  Protocol: {protocol_endpoint.text}\n"
                        f"  SAP:      {sap_endpoint}"
                    )

                    # FORCE correction - replace SAP text with protocol text
                    corrected = corrected.replace(sap_endpoint, protocol_endpoint.text)
                    corrections.append(f"Replaced SAP endpoint with protocol verbatim text")

        return EnforcementResult(
            original=sap_text,
            corrected=corrected,
            violations_found=violations,
            corrections_made=corrections
        )

    def enforce_population_definition(
        self,
        sap_text: str,
        protocol_definition: VerbatimDefinition,
        pop_name: str
    ) -> EnforcementResult:
        """
        Ensure population definition hasn't been modified.
        Common error: Adding "took at least one dose" to FAS (makes it mITT).
        """
        violations = []
        corrections = []
        corrected = sap_text

        if pop_name in ['FAS', 'ITT']:
            for pattern in self.UNAUTHORIZED_FAS_ADDITIONS:
                match = re.search(pattern, sap_text, re.IGNORECASE)
                if match:
                    # Check if this phrase is actually in the protocol
                    if not re.search(pattern, protocol_definition.text, re.IGNORECASE):
                        violations.append(
                            f"Unauthorized addition to {pop_name} definition: '{match.group()}'"
                        )
                        # Remove the unauthorized addition
                        corrected = re.sub(
                            pattern + r',?\s*',
                            '',
                            corrected,
                            flags=re.IGNORECASE
                        )
                        corrections.append(f"Removed unauthorized phrase: '{match.group()}'")

        return EnforcementResult(
            original=sap_text,
            corrected=corrected,
            violations_found=violations,
            corrections_made=corrections
        )

    def enforce_stratification_factors(
        self,
        sap_text: str,
        protocol_factors: List[str]
    ) -> EnforcementResult:
        """
        Ensure ALL stratification factors from protocol appear in SAP.
        """
        violations = []
        corrections = []
        corrected = sap_text

        missing_factors = []
        for factor in protocol_factors:
            # Check if factor (or close variant) appears in SAP
            factor_pattern = re.escape(factor)
            if not re.search(factor_pattern, sap_text, re.IGNORECASE):
                # Try partial match
                words = factor.split()
                if len(words) >= 2:
                    partial_pattern = r'\b' + r'.*'.join(re.escape(w) for w in words[:2]) + r'\b'
                    if not re.search(partial_pattern, sap_text, re.IGNORECASE):
                        missing_factors.append(factor)

        if missing_factors:
            violations.append(
                f"Missing stratification factors: {missing_factors}"
            )

            # Find where stratification is mentioned and add missing factors
            strat_section_match = re.search(
                r'(stratification\s+factors?[:\s]+.+?)(?=\n\n|\d+\.\d+)',
                corrected,
                re.IGNORECASE | re.DOTALL
            )

            if strat_section_match:
                existing_text = strat_section_match.group(1)
                additions = ", ".join(missing_factors)
                new_text = existing_text.rstrip('.') + f", {additions}."
                corrected = corrected.replace(existing_text, new_text)
                corrections.append(f"Added missing factors: {missing_factors}")

        return EnforcementResult(
            original=sap_text,
            corrected=corrected,
            violations_found=violations,
            corrections_made=corrections
        )

    def enforce_alpha_specification(
        self,
        sap_text: str,
        protocol_alpha: Dict
    ) -> EnforcementResult:
        """
        Ensure alpha sidedness matches protocol.
        Common error: Defaulting to two-sided when protocol says one-sided.
        """
        violations = []
        corrections = []
        corrected = sap_text

        protocol_sidedness = protocol_alpha['sidedness']

        # Check what SAP says
        if protocol_sidedness == 'one-sided':
            if re.search(r'two[\s-]?sided', sap_text, re.IGNORECASE):
                if not re.search(r'one[\s-]?sided', sap_text, re.IGNORECASE):
                    violations.append(
                        f"Alpha sidedness mismatch: Protocol says '{protocol_sidedness}' but SAP says 'two-sided'"
                    )
                    # Correct: replace two-sided with one-sided
                    corrected = re.sub(
                        r'two[\s-]?sided',
                        'one-sided',
                        corrected,
                        flags=re.IGNORECASE
                    )
                    corrections.append("Replaced 'two-sided' with 'one-sided'")

        return EnforcementResult(
            original=sap_text,
            corrected=corrected,
            violations_found=violations,
            corrections_made=corrections
        )

    def enforce_all(
        self,
        sap_text: str,
        protocol_text: str
    ) -> EnforcementResult:
        """
        Run all enforcement checks and corrections.
        """
        all_violations = []
        all_corrections = []
        current_text = sap_text

        # 1. Extract ground truth from protocol
        primary_endpoint = self.extractor.extract_primary_endpoint_verbatim(protocol_text)
        fas_definition = self.extractor.extract_population_verbatim(protocol_text, 'FAS')
        stratification = self.extractor.extract_all_stratification_factors(protocol_text)
        alpha = self.extractor.extract_alpha_specification(protocol_text)

        # 2. Enforce primary endpoint
        if primary_endpoint:
            result = self.enforce_primary_endpoint(current_text, primary_endpoint)
            current_text = result.corrected
            all_violations.extend(result.violations_found)
            all_corrections.extend(result.corrections_made)

        # 3. Enforce population definitions
        if fas_definition:
            result = self.enforce_population_definition(current_text, fas_definition, 'FAS')
            current_text = result.corrected
            all_violations.extend(result.violations_found)
            all_corrections.extend(result.corrections_made)

        # 4. Enforce stratification factors
        if stratification:
            result = self.enforce_stratification_factors(current_text, stratification)
            current_text = result.corrected
            all_violations.extend(result.violations_found)
            all_corrections.extend(result.corrections_made)

        # 5. Enforce alpha specification
        result = self.enforce_alpha_specification(current_text, alpha)
        current_text = result.corrected
        all_violations.extend(result.violations_found)
        all_corrections.extend(result.corrections_made)

        return EnforcementResult(
            original=sap_text,
            corrected=current_text,
            violations_found=all_violations,
            corrections_made=all_corrections
        )


class TemplateBasedSectionGenerator:
    """
    Generates critical SAP sections using templates with locked slots.
    LLM fills narrative portions ONLY - cannot modify verbatim content.
    """

    SECTION_2_1_TEMPLATE = """## 2.1 Primary Endpoint

The primary endpoint for this study is:

> **{PRIMARY_ENDPOINT_VERBATIM}**

{LLM_CONTEXT}

### 2.1.1 Endpoint Components

{ENDPOINT_COMPONENTS}

### 2.1.2 Assessment Details

{ASSESSMENT_DETAILS}
"""

    SECTION_4_2_TEMPLATE = """## 4.2 Analysis Populations

### 4.2.1 Full Analysis Set (FAS)

The Full Analysis Set is defined as:

> **{FAS_DEFINITION_VERBATIM}**

This is the primary analysis population for efficacy endpoints.

### 4.2.2 Per-Protocol Population

{PP_DEFINITION}

### 4.2.3 Safety Population

{SAFETY_DEFINITION}
"""

    SECTION_6_TEMPLATE = """## 6 Randomization and Stratification

### 6.1 Randomization

{RANDOMIZATION_TEXT}

### 6.2 Stratification Factors

Randomization will be stratified by the following factors:

{STRATIFICATION_FACTORS_LIST}

These factors will be included as covariates in the primary analysis model.
"""

    def generate_section_2_1(
        self,
        protocol_endpoint: VerbatimDefinition,
        llm_client,
        protocol_context: str
    ) -> str:
        """
        Generate Section 2.1 with LOCKED primary endpoint definition.
        LLM cannot modify the verbatim definition.
        """
        # LLM generates ONLY the context paragraph
        llm_context = llm_client.generate(
            prompt=f"""Write 2-3 sentences explaining why this primary endpoint
            is appropriate for this study. DO NOT restate the endpoint definition.

            Endpoint: {protocol_endpoint.text}
            Study context: {protocol_context}
            """,
            temperature=0.2
        )

        # Programmatically parse endpoint components
        components = self._parse_endpoint_components(protocol_endpoint.text)

        # Assessment details based on endpoint type
        assessment = self._determine_assessment_details(protocol_endpoint.text)

        return self.SECTION_2_1_TEMPLATE.format(
            PRIMARY_ENDPOINT_VERBATIM=protocol_endpoint.text,  # LOCKED
            LLM_CONTEXT=llm_context,
            ENDPOINT_COMPONENTS=components,
            ASSESSMENT_DETAILS=assessment
        )

    def generate_section_4_2(
        self,
        fas_definition: VerbatimDefinition,
        llm_client,
        protocol_context: str
    ) -> str:
        """
        Generate Section 4.2 with LOCKED population definitions.
        """
        # Generate PP and Safety definitions (less critical, LLM can help)
        pp_def = llm_client.generate(
            prompt=f"Write the per-protocol population definition for a clinical trial. Keep it standard and brief.",
            temperature=0.2
        )

        safety_def = llm_client.generate(
            prompt=f"Write the safety population definition for a clinical trial. Keep it standard and brief.",
            temperature=0.2
        )

        return self.SECTION_4_2_TEMPLATE.format(
            FAS_DEFINITION_VERBATIM=fas_definition.text,  # LOCKED
            PP_DEFINITION=pp_def,
            SAFETY_DEFINITION=safety_def
        )

    def generate_section_6(
        self,
        stratification_factors: List[str],
        llm_client,
        randomization_info: str
    ) -> str:
        """
        Generate Section 6 with ALL stratification factors.
        """
        # LLM describes randomization
        randomization_text = llm_client.generate(
            prompt=f"Describe the randomization procedure for this study: {randomization_info}",
            temperature=0.2
        )

        # Stratification factors are listed programmatically - LLM cannot omit any
        factors_list = "\n".join(f"- {factor}" for factor in stratification_factors)

        return self.SECTION_6_TEMPLATE.format(
            RANDOMIZATION_TEXT=randomization_text,
            STRATIFICATION_FACTORS_LIST=factors_list  # ALL factors, programmatically
        )

    def _parse_endpoint_components(self, endpoint_text: str) -> str:
        """Programmatically extract endpoint components."""
        components = []

        # Mayo score components
        mayo_match = re.search(r'(full|partial|9-point)?\s*mayo\s+score\s*[≤<]\s*(\d+)',
                               endpoint_text, re.IGNORECASE)
        if mayo_match:
            mayo_type = mayo_match.group(1) or "full"
            threshold = mayo_match.group(2)
            components.append(f"- **Mayo Score**: {mayo_type.title()} Mayo score ≤ {threshold}")

        # Subscore requirements
        subscore_matches = re.findall(r'(\w+)\s+subscore\s*[=≤<]\s*(\d+)',
                                       endpoint_text, re.IGNORECASE)
        for name, value in subscore_matches:
            components.append(f"- **{name.title()} Subscore**: = {value}")

        # Endoscopy requirement
        if 'endoscop' in endpoint_text.lower():
            components.append("- **Endoscopic Assessment**: Required")

        # Individual subscore constraint
        if 'no individual subscore' in endpoint_text.lower():
            match = re.search(r'no\s+individual\s+subscore\s*>\s*(\d+)', endpoint_text, re.IGNORECASE)
            if match:
                components.append(f"- **Individual Subscores**: None > {match.group(1)}")

        return "\n".join(components) if components else "See definition above for component details."

    def _determine_assessment_details(self, endpoint_text: str) -> str:
        """Generate assessment details based on endpoint type."""
        details = []

        if 'endoscop' in endpoint_text.lower():
            details.append("- Endoscopy will be performed at Week 12")
            details.append("- Central reading will be used for endpoint determination")

        if 'mayo' in endpoint_text.lower():
            details.append("- Mayo score components will be assessed per standard scoring")
            details.append("- Stool frequency and rectal bleeding subscores based on patient diary")

        return "\n".join(details) if details else "Assessment per protocol-specified procedures."
