#!/usr/bin/env python3
"""
Anchor-Based Grounded SAP Generation System
============================================

This system ensures LLM cannot hallucinate values by:
1. Extracting all values with citations from protocol
2. LLM generates prose with ANCHORS only (<<TOTAL_N>>, <<DRUG_NAME>>)
3. Anchors are substituted with extracted values POST-generation
4. Validation catches any contamination

The LLM NEVER sees actual values, only anchor placeholders.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


@dataclass
class ExtractedValue:
    """A value extracted from the protocol with citation"""
    value: Any  # The actual value (90, "1:1:1", "TJ301", etc.)
    citation: str  # The exact text from protocol where this was found
    location: str  # Page/section reference
    confidence: float = 1.0  # 0-1 confidence score


@dataclass
class ProtocolAnchors:
    """All extractable anchors from a protocol"""
    # Study identification
    STUDY_ID: Optional[ExtractedValue] = None
    NCT_ID: Optional[ExtractedValue] = None
    SPONSOR: Optional[ExtractedValue] = None

    # Drug/treatment
    DRUG_NAME: Optional[ExtractedValue] = None
    DRUG_GENERIC: Optional[ExtractedValue] = None
    DRUG_CODE: Optional[ExtractedValue] = None
    ROUTE: Optional[ExtractedValue] = None

    # Sample size
    TOTAL_N: Optional[ExtractedValue] = None
    PER_ARM_N: Optional[ExtractedValue] = None
    POWER: Optional[ExtractedValue] = None
    ALPHA: Optional[ExtractedValue] = None
    ALPHA_SIDEDNESS: Optional[ExtractedValue] = None
    DROPOUT_RATE: Optional[ExtractedValue] = None

    # Design
    NUM_ARMS: Optional[ExtractedValue] = None
    RATIO: Optional[ExtractedValue] = None
    ARM_1: Optional[ExtractedValue] = None
    ARM_2: Optional[ExtractedValue] = None
    ARM_3: Optional[ExtractedValue] = None
    ARM_4: Optional[ExtractedValue] = None

    # Endpoints
    PRIMARY_ENDPOINT: Optional[ExtractedValue] = None
    PRIMARY_TIMEPOINT: Optional[ExtractedValue] = None
    SECONDARY_ENDPOINTS: Optional[ExtractedValue] = None

    # Populations
    PRIMARY_POPULATION: Optional[ExtractedValue] = None

    # Stratification
    STRAT_FACTOR_1: Optional[ExtractedValue] = None
    STRAT_FACTOR_2: Optional[ExtractedValue] = None

    # Assumptions
    PLACEBO_RATE: Optional[ExtractedValue] = None
    TREATMENT_RATE: Optional[ExtractedValue] = None
    EFFECT_SIZE: Optional[ExtractedValue] = None

    # Phase and indication
    PHASE: Optional[ExtractedValue] = None
    INDICATION: Optional[ExtractedValue] = None
    THERAPEUTIC_AREA: Optional[ExtractedValue] = None

    def to_substitution_dict(self) -> Dict[str, str]:
        """Convert to dictionary for anchor substitution"""
        result = {}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if value is not None and value.value is not None:
                result[field_name] = str(value.value)
        return result

    def get_missing_critical(self) -> List[str]:
        """Get list of missing critical anchors"""
        critical = ['DRUG_NAME', 'TOTAL_N', 'NUM_ARMS', 'RATIO']
        return [a for a in critical if getattr(self, a) is None]


class AnchorExtractor:
    """
    Extracts values from protocol text with citations.

    Unlike StructuredFactExtractor, this captures the EXACT text
    where each value was found for traceability.
    """

    def extract_all(self, protocol_text: str) -> ProtocolAnchors:
        """Extract all anchors from protocol text"""
        anchors = ProtocolAnchors()

        # NCT ID
        anchors.NCT_ID = self._extract_with_citation(
            protocol_text,
            r'(NCT\d{8})',
            "NCT ID"
        )

        # Drug name - prioritize explicit declarations
        anchors.DRUG_NAME = self._extract_drug_name(protocol_text)
        anchors.DRUG_CODE = self._extract_drug_code(protocol_text)
        anchors.DRUG_GENERIC = self._extract_generic_name(protocol_text)

        # Sample size
        anchors.TOTAL_N = self._extract_total_n(protocol_text)
        anchors.POWER = self._extract_power(protocol_text)
        anchors.ALPHA, anchors.ALPHA_SIDEDNESS = self._extract_alpha(protocol_text)
        anchors.DROPOUT_RATE = self._extract_dropout(protocol_text)

        # Design
        anchors.RATIO = self._extract_ratio(protocol_text)
        anchors.NUM_ARMS = self._extract_num_arms(protocol_text, anchors.RATIO)

        # Treatment arms
        arm_info = self._extract_arms(protocol_text)
        if len(arm_info) >= 1:
            anchors.ARM_1 = arm_info[0]
        if len(arm_info) >= 2:
            anchors.ARM_2 = arm_info[1]
        if len(arm_info) >= 3:
            anchors.ARM_3 = arm_info[2]
        if len(arm_info) >= 4:
            anchors.ARM_4 = arm_info[3]

        # Calculate per-arm N
        if anchors.TOTAL_N and anchors.NUM_ARMS:
            total = anchors.TOTAL_N.value
            num_arms = anchors.NUM_ARMS.value
            if total and num_arms and num_arms > 0:
                per_arm = total // num_arms
                anchors.PER_ARM_N = ExtractedValue(
                    value=per_arm,
                    citation=f"Calculated: {total} / {num_arms} arms",
                    location="Derived"
                )

        # Route
        anchors.ROUTE = self._extract_route(protocol_text)

        # Primary endpoint
        anchors.PRIMARY_ENDPOINT = self._extract_primary_endpoint(protocol_text)
        anchors.PRIMARY_TIMEPOINT = self._extract_primary_timepoint(protocol_text)

        # Population
        anchors.PRIMARY_POPULATION = self._extract_population(protocol_text)

        # Stratification
        strat_factors = self._extract_stratification(protocol_text)
        if len(strat_factors) >= 1:
            anchors.STRAT_FACTOR_1 = strat_factors[0]
        if len(strat_factors) >= 2:
            anchors.STRAT_FACTOR_2 = strat_factors[1]

        # Phase
        anchors.PHASE = self._extract_phase(protocol_text)

        # Indication
        anchors.INDICATION = self._extract_indication(protocol_text)

        return anchors

    def _extract_with_citation(
        self,
        text: str,
        pattern: str,
        description: str,
        context_chars: int = 100
    ) -> Optional[ExtractedValue]:
        """Extract a value with surrounding context as citation"""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start = max(0, match.start() - context_chars)
            end = min(len(text), match.end() + context_chars)
            citation = text[start:end].replace('\n', ' ').strip()

            # Try to find page reference
            location = self._find_location(text, match.start())

            return ExtractedValue(
                value=match.group(1) if match.groups() else match.group(0),
                citation=f"...{citation}...",
                location=location
            )
        return None

    def _find_location(self, text: str, position: int) -> str:
        """Try to find page/section reference near position"""
        # Look backwards for page marker
        search_start = max(0, position - 500)
        context = text[search_start:position]

        page_match = re.search(r'page\s+(\d+)', context, re.IGNORECASE)
        if page_match:
            return f"Page {page_match.group(1)}"

        section_match = re.search(r'section\s+([\d.]+)', context, re.IGNORECASE)
        if section_match:
            return f"Section {section_match.group(1)}"

        return "Location unknown"

    def _extract_drug_name(self, text: str) -> Optional[ExtractedValue]:
        """Extract primary drug name with citation"""
        # Priority 1: Explicit "Investigational Product:" declaration
        patterns = [
            (r'(?:Investigational\s+Product|IMP|Study\s+Drug)[:\s]+([A-Za-z][A-Za-z0-9-]{2,})', 'Explicit declaration'),
            (r'\b([A-Z]{2,3}\d{3,4})\b', 'Drug code format'),  # TJ301, AB123
        ]

        for pattern, source in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                name = match.group(1).strip()
                # Filter out false positives
                if name.upper() not in ['NCT', 'THE', 'AND', 'FOR', 'WITH']:
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    citation = text[start:end].replace('\n', ' ')
                    return ExtractedValue(
                        value=name,
                        citation=f"...{citation}...",
                        location=self._find_location(text, match.start())
                    )
        return None

    def _extract_drug_code(self, text: str) -> Optional[ExtractedValue]:
        """Extract drug code (e.g., FE 999301)"""
        pattern = r'\b([A-Z]{2}[-\s]?\d{5,6})\b'
        return self._extract_with_citation(text, pattern, "Drug code")

    def _extract_generic_name(self, text: str) -> Optional[ExtractedValue]:
        """Extract generic/INN name (e.g., olamkicept)"""
        pattern = r'\b([a-z]{5,}(?:mab|nib|cept|tinib|ciclib))\b'
        return self._extract_with_citation(text, pattern, "Generic name")

    def _extract_total_n(self, text: str) -> Optional[ExtractedValue]:
        """Extract total sample size with citation"""
        patterns = [
            r'(?:total\s+of\s+)?(\d{2,4})\s+(?:patients?|subjects?)\s+(?:will\s+be\s+)?(?:enrolled|randomized)',
            r'(?:sample\s+size)[:\s]+(\d{2,4})',
            r'(?:enroll|randomize)\s+(?:approximately\s+)?(\d{2,4})',
            r'N\s*[=:]\s*(\d{2,4})',
            r'(\d{2,4})\s+(?:patients?|subjects?)\s+(?:in\s+a|across)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                n = int(match.group(1))
                if 10 <= n <= 10000:  # Reasonable range
                    start = max(0, match.start() - 80)
                    end = min(len(text), match.end() + 80)
                    citation = text[start:end].replace('\n', ' ')
                    return ExtractedValue(
                        value=n,
                        citation=f"...{citation}...",
                        location=self._find_location(text, match.start())
                    )
        return None

    def _extract_power(self, text: str) -> Optional[ExtractedValue]:
        """Extract statistical power"""
        patterns = [
            r'(\d{2})%?\s*power',
            r'power\s+(?:of\s+)?(\d{2})%?',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                power = int(match.group(1))
                if 70 <= power <= 99:
                    return ExtractedValue(
                        value=f"{power}%",
                        citation=text[max(0, match.start()-30):match.end()+30].replace('\n', ' '),
                        location=self._find_location(text, match.start())
                    )
        return None

    def _extract_alpha(self, text: str) -> Tuple[Optional[ExtractedValue], Optional[ExtractedValue]]:
        """Extract alpha level and sidedness"""
        alpha_val = None
        sidedness = None

        # Alpha value
        alpha_match = re.search(r'alpha\s*(?:=|of)?\s*(0\.0\d+)', text, re.IGNORECASE)
        if alpha_match:
            alpha_val = ExtractedValue(
                value=float(alpha_match.group(1)),
                citation=text[max(0, alpha_match.start()-30):alpha_match.end()+30].replace('\n', ' '),
                location=self._find_location(text, alpha_match.start())
            )

        # Sidedness
        if re.search(r'one[- ]sided|1[- ]sided', text, re.IGNORECASE):
            sidedness = ExtractedValue(value="one-sided", citation="one-sided", location="")
        elif re.search(r'two[- ]sided|2[- ]sided', text, re.IGNORECASE):
            sidedness = ExtractedValue(value="two-sided", citation="two-sided", location="")

        return alpha_val, sidedness

    def _extract_dropout(self, text: str) -> Optional[ExtractedValue]:
        """Extract dropout rate"""
        match = re.search(r'(\d{1,2})%?\s*(?:dropout|discontinuation|withdrawal)', text, re.IGNORECASE)
        if match:
            return ExtractedValue(
                value=f"{match.group(1)}%",
                citation=text[max(0, match.start()-30):match.end()+30].replace('\n', ' '),
                location=self._find_location(text, match.start())
            )
        return None

    def _extract_ratio(self, text: str) -> Optional[ExtractedValue]:
        """Extract randomization ratio"""
        match = re.search(r'\b(\d+:\d+(?::\d+)*)\b', text)
        if match:
            return ExtractedValue(
                value=match.group(1),
                citation=text[max(0, match.start()-50):match.end()+50].replace('\n', ' '),
                location=self._find_location(text, match.start())
            )
        return None

    def _extract_num_arms(self, text: str, ratio: Optional[ExtractedValue]) -> Optional[ExtractedValue]:
        """Extract number of arms"""
        # From ratio
        if ratio and ratio.value:
            num = len(ratio.value.split(':'))
            return ExtractedValue(
                value=num,
                citation=f"Derived from ratio {ratio.value}",
                location="Derived"
            )

        # From explicit statement
        match = re.search(r'(\d+)\s+(?:treatment\s+)?(?:arms?|groups?)', text, re.IGNORECASE)
        if match:
            return ExtractedValue(
                value=int(match.group(1)),
                citation=text[max(0, match.start()-30):match.end()+30].replace('\n', ' '),
                location=self._find_location(text, match.start())
            )
        return None

    def _extract_arms(self, text: str) -> List[ExtractedValue]:
        """Extract treatment arm descriptions"""
        arms = []

        # Look for arm/group descriptions
        patterns = [
            r'(?:Arm|Group)\s*([A-D1-4])[:\s]+([^\n]+)',
            r'-\s*(?:Arm|Group)\s*([A-D1-4])[:\s]*([^\n]+)',
        ]

        seen = set()
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                arm_id = match.group(1).upper()
                if arm_id not in seen:
                    seen.add(arm_id)
                    arms.append(ExtractedValue(
                        value=match.group(2).strip()[:100],
                        citation=match.group(0)[:150],
                        location=self._find_location(text, match.start())
                    ))

        return arms

    def _extract_route(self, text: str) -> Optional[ExtractedValue]:
        """Extract route of administration"""
        routes = [
            (r'\b(intravenous(?:ly)?|IV)\b', 'intravenous'),
            (r'\b(subcutaneous(?:ly)?|SC)\b', 'subcutaneous'),
            (r'\b(oral(?:ly)?)\b', 'oral'),
            (r'\b(intramuscular(?:ly)?|IM)\b', 'intramuscular'),
        ]

        for pattern, normalized in routes:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return ExtractedValue(
                    value=normalized,
                    citation=text[max(0, match.start()-30):match.end()+30].replace('\n', ' '),
                    location=self._find_location(text, match.start())
                )
        return None

    def _extract_primary_endpoint(self, text: str) -> Optional[ExtractedValue]:
        """Extract primary endpoint definition"""
        patterns = [
            r'(?:primary\s+(?:efficacy\s+)?endpoint)[:\s]+([^\n.]{20,150})',
            r'(?:primary\s+(?:efficacy\s+)?outcome)[:\s]+([^\n.]{20,150})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return ExtractedValue(
                    value=match.group(1).strip(),
                    citation=match.group(0),
                    location=self._find_location(text, match.start())
                )
        return None

    def _extract_primary_timepoint(self, text: str) -> Optional[ExtractedValue]:
        """Extract primary endpoint timepoint"""
        patterns = [
            r'(?:at|through)\s+(Week\s+\d+)',
            r'(Week\s+\d+)\s+(?:primary|endpoint)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return ExtractedValue(
                    value=match.group(1),
                    citation=text[max(0, match.start()-20):match.end()+20].replace('\n', ' '),
                    location=self._find_location(text, match.start())
                )
        return None

    def _extract_population(self, text: str) -> Optional[ExtractedValue]:
        """Extract primary analysis population"""
        patterns = [
            r'(?:primary\s+analysis)\s+(?:on|using)\s+(?:the\s+)?(ITT|FAS|mITT|PP)',
            r'(ITT|FAS|mITT|PP)\s+(?:population\s+)?(?:will\s+be\s+)?(?:used\s+)?(?:for|as)\s+(?:the\s+)?primary',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return ExtractedValue(
                    value=match.group(1).upper(),
                    citation=text[max(0, match.start()-30):match.end()+30].replace('\n', ' '),
                    location=self._find_location(text, match.start())
                )
        return None

    def _extract_stratification(self, text: str) -> List[ExtractedValue]:
        """Extract stratification factors"""
        factors = []

        # Find stratification section
        match = re.search(
            r'(?:stratif(?:y|ied|ication)\s+(?:by|factors?)[:\s]+)([^\n.]+)',
            text, re.IGNORECASE
        )

        if match:
            factor_text = match.group(1)
            # Split by delimiters
            parts = re.split(r'[,;]|\band\b', factor_text)
            for part in parts:
                part = part.strip()
                if 5 < len(part) < 100:
                    factors.append(ExtractedValue(
                        value=part,
                        citation=match.group(0),
                        location=self._find_location(text, match.start())
                    ))

        return factors

    def _extract_phase(self, text: str) -> Optional[ExtractedValue]:
        """Extract study phase"""
        match = re.search(r'phase\s*(I{1,3}|[1-4]|2a|2b|3a|3b)', text, re.IGNORECASE)
        if match:
            return ExtractedValue(
                value=f"Phase {match.group(1)}",
                citation=text[max(0, match.start()-20):match.end()+20].replace('\n', ' '),
                location=self._find_location(text, match.start())
            )
        return None

    def _extract_indication(self, text: str) -> Optional[ExtractedValue]:
        """Extract indication/disease"""
        indications = [
            (r"(?:ulcerative\s+colitis|UC)", "Ulcerative Colitis"),
            (r"(?:Crohn'?s?\s+disease|CD)", "Crohn's Disease"),
            (r"(?:rheumatoid\s+arthritis|RA)", "Rheumatoid Arthritis"),
            (r"(?:multiple\s+sclerosis|MS)", "Multiple Sclerosis"),
        ]

        for pattern, normalized in indications:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return ExtractedValue(
                    value=normalized,
                    citation=text[max(0, match.start()-30):match.end()+30].replace('\n', ' '),
                    location=self._find_location(text, match.start())
                )
        return None


class AnchorValidator:
    """Validates anchor consistency before and after generation"""

    def validate_pre_generation(self, anchors: ProtocolAnchors) -> Tuple[bool, List[str]]:
        """
        Validate extracted anchors before generation.
        Returns (is_valid, list_of_issues)
        """
        issues = []

        # Check critical anchors exist
        missing = anchors.get_missing_critical()
        if missing:
            issues.append(f"Missing critical anchors: {missing}")

        # Mathematical consistency: ratio parts = num arms
        if anchors.RATIO and anchors.NUM_ARMS:
            ratio_parts = len(anchors.RATIO.value.split(':'))
            if ratio_parts != anchors.NUM_ARMS.value:
                issues.append(
                    f"Ratio {anchors.RATIO.value} has {ratio_parts} parts "
                    f"but NUM_ARMS is {anchors.NUM_ARMS.value}"
                )

        # Mathematical consistency: per_arm * num_arms ≈ total
        if anchors.TOTAL_N and anchors.PER_ARM_N and anchors.NUM_ARMS:
            expected_total = anchors.PER_ARM_N.value * anchors.NUM_ARMS.value
            actual_total = anchors.TOTAL_N.value
            if abs(expected_total - actual_total) > actual_total * 0.1:  # 10% tolerance
                issues.append(
                    f"Math check failed: {anchors.PER_ARM_N.value} × "
                    f"{anchors.NUM_ARMS.value} = {expected_total}, "
                    f"but TOTAL_N = {actual_total}"
                )

        return len(issues) == 0, issues

    def validate_post_generation(
        self,
        generated_text: str,
        anchors: ProtocolAnchors
    ) -> Tuple[bool, List[str]]:
        """
        Validate generated SAP for contamination.
        Returns (is_valid, list_of_issues)
        """
        issues = []

        # Check for unsubstituted anchors
        remaining = re.findall(r'<<[A-Z_]+>>', generated_text)
        if remaining:
            issues.append(f"Unsubstituted anchors: {remaining}")

        # Check for forbidden approximation patterns
        forbidden = [
            (r'approximately\s+\d+', "approximation"),
            (r'about\s+\d+', "approximation"),
            (r'~\d+', "approximation"),
            (r'\d+\s*-\s*\d+\s*(?:patients?|subjects?)', "range"),
        ]

        for pattern, name in forbidden:
            if re.search(pattern, generated_text, re.IGNORECASE):
                issues.append(f"Found forbidden {name} pattern")

        # Check for numbers not in extracted values
        valid_numbers = set()
        for field_name in anchors.__dataclass_fields__:
            val = getattr(anchors, field_name)
            if val and val.value:
                # Extract all numbers from the value
                nums = re.findall(r'\d+', str(val.value))
                valid_numbers.update(int(n) for n in nums)

        # Find all numbers in generated text
        found_numbers = set(int(n) for n in re.findall(r'\b(\d{2,4})\b', generated_text))

        # Check for unexpected numbers (excluding common ones like percentages, days)
        suspicious = found_numbers - valid_numbers - {0, 1, 2, 3, 4, 5, 10, 12, 24, 48, 72, 100}
        if suspicious:
            issues.append(f"Suspicious numbers not in protocol: {suspicious}")

        return len(issues) == 0, issues


class AnchorSubstituter:
    """Substitutes anchors with extracted values"""

    def substitute(self, text: str, anchors: ProtocolAnchors) -> str:
        """Replace all <<ANCHOR>> placeholders with values"""
        result = text

        substitutions = anchors.to_substitution_dict()

        for anchor_name, value in substitutions.items():
            placeholder = f"<<{anchor_name}>>"
            result = result.replace(placeholder, str(value))

        return result

    def get_anchor_list(self) -> List[str]:
        """Get list of all available anchor names"""
        return list(ProtocolAnchors.__dataclass_fields__.keys())
