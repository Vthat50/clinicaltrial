#!/usr/bin/env python3
"""
Fact Verifier - SELF-RAG Pattern for SAP Verification
======================================================

Based on SELF-RAG (ICLR 2024 Oral, top 1%):
"Self-RAG significantly outperforms state-of-the-art LLMs and retrieval-augmented
models on a diverse set of tasks... it shows significant gains in improving
factuality and citation accuracy for long-form generations."

This module:
1. Verifies generated SAP matches extracted facts
2. Identifies specific errors (wrong numbers, missing methods)
3. Generates correction prompts for regeneration
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class VerificationError:
    """A single verification error."""
    field: str
    expected: Any
    found: Any
    severity: str  # "critical", "high", "medium", "low"
    context: str = ""  # Text snippet where error was found


@dataclass
class VerificationResult:
    """Result of verification."""
    passed: bool
    errors: List[VerificationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_slots: List[str] = field(default_factory=list)  # For compatibility with RuleBasedPipeline
    score: float = 1.0  # 0.0 to 1.0


class FactVerifier:
    """
    Verifies generated SAP against extracted facts.
    Implements SELF-RAG reflection pattern.
    """

    # Common wrong values from RAG contamination
    COMMON_RAG_CONTAMINATION = {
        'event_counts': ['639', '500', '400', '300', '250', '200'],
        'sample_sizes': ['1000', '800', '600', '500', '400'],
        'alpha_values': ['0.05', '0.025'],  # Default values
    }

    def __init__(self):
        self.errors: List[VerificationError] = []
        self.warnings: List[str] = []

    def verify(
        self,
        generated_text: str,
        facts: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None
    ) -> VerificationResult:
        """
        Verify generated SAP against extracted facts.

        Args:
            generated_text: The generated SAP text
            facts: Extracted protocol facts (ground truth)
            constraints: Method constraints from knowledge graph

        Returns:
            VerificationResult with pass/fail and error list
        """
        self.errors = []
        self.warnings = []

        text_lower = generated_text.lower()

        # 1. Verify numerical values (CRITICAL)
        self._verify_event_counts(generated_text, facts)
        self._verify_sample_size(generated_text, facts)
        self._verify_alpha_values(generated_text, facts)
        self._verify_interim_count(generated_text, facts)
        self._verify_hazard_ratio(generated_text, facts)
        self._verify_power(generated_text, facts)

        # 2. Verify method constraints
        if constraints:
            self._verify_methods(generated_text, constraints)

        # 3. Check for RAG contamination (wrong trial data)
        self._check_rag_contamination(generated_text, facts)

        # Calculate score
        critical_errors = [e for e in self.errors if e.severity == "critical"]
        high_errors = [e for e in self.errors if e.severity == "high"]

        if critical_errors:
            score = 0.0
        elif high_errors:
            score = 0.5 - (len(high_errors) * 0.1)
        else:
            score = 1.0 - (len(self.errors) * 0.05)

        score = max(0.0, min(1.0, score))

        return VerificationResult(
            passed=len(critical_errors) == 0 and len(high_errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
            score=score
        )

    def _verify_event_counts(self, text: str, facts: Dict[str, Any]):
        """Verify event counts match extraction."""

        # Final events
        final_events = facts.get('final_events') or facts.get('final_analysis_events')
        if final_events:
            if str(final_events) not in text:
                # Check if a wrong number is present
                wrong_found = self._find_wrong_number(
                    text, final_events, 'event', ['death', 'event', 'os event']
                )
                if wrong_found:
                    self.errors.append(VerificationError(
                        field="final_events",
                        expected=final_events,
                        found=wrong_found,
                        severity="critical",
                        context=f"Found {wrong_found} instead of {final_events} events"
                    ))

        # Interim events
        interim_events = facts.get('interim_events') or facts.get('interim_analysis_events')
        if interim_events:
            if isinstance(interim_events, list):
                for i, events in enumerate(interim_events):
                    if str(events) not in text:
                        self.warnings.append(f"Interim {i+1} events ({events}) not found in text")
            elif str(interim_events) not in text:
                wrong_found = self._find_wrong_number(
                    text, interim_events, 'interim', ['interim', 'first analysis']
                )
                if wrong_found:
                    self.errors.append(VerificationError(
                        field="interim_events",
                        expected=interim_events,
                        found=wrong_found,
                        severity="high",
                        context=f"Found {wrong_found} instead of {interim_events} at interim"
                    ))

    def _verify_sample_size(self, text: str, facts: Dict[str, Any]):
        """Verify sample size matches extraction."""
        sample_size = facts.get('sample_size')
        if sample_size:
            if str(sample_size) not in text:
                wrong_found = self._find_wrong_number(
                    text, sample_size, 'sample', ['patient', 'subject', 'participant', 'n =']
                )
                if wrong_found:
                    self.errors.append(VerificationError(
                        field="sample_size",
                        expected=sample_size,
                        found=wrong_found,
                        severity="high",
                        context=f"Found {wrong_found} instead of {sample_size} patients"
                    ))

    def _verify_alpha_values(self, text: str, facts: Dict[str, Any]):
        """Verify alpha values match extraction."""

        # Alpha at interim
        alpha_interim = facts.get('alpha_at_interim') or facts.get('alpha_interim')
        if alpha_interim and alpha_interim != 0.05:  # 0.05 is default, might be correct
            alpha_str = f"{alpha_interim:.3f}".rstrip('0').rstrip('.')
            if alpha_str not in text and str(alpha_interim) not in text:
                # Check if default 0.05 is used instead
                if '0.05' in text or '5%' in text.replace(' ', ''):
                    self.errors.append(VerificationError(
                        field="alpha_interim",
                        expected=alpha_interim,
                        found="0.05 (default)",
                        severity="critical",
                        context=f"Using default 0.05 instead of {alpha_interim}"
                    ))

        # Alpha at final
        alpha_final = facts.get('alpha_at_final') or facts.get('alpha_final')
        if alpha_final and alpha_final not in [0.05, 0.025]:  # Common values
            alpha_str = f"{alpha_final:.3f}".rstrip('0').rstrip('.')
            if alpha_str not in text and str(alpha_final) not in text:
                self.errors.append(VerificationError(
                    field="alpha_final",
                    expected=alpha_final,
                    found="not found",
                    severity="high",
                    context=f"Alpha at final ({alpha_final}) not found"
                ))

    def _verify_interim_count(self, text: str, facts: Dict[str, Any]):
        """Verify number of interim analyses matches extraction."""
        num_interim = facts.get('num_interim_analyses') or facts.get('num_interim')

        if num_interim:
            text_lower = text.lower()

            # Check for wrong counts
            if num_interim == 1:
                if 'two interim' in text_lower or '2 interim' in text_lower:
                    self.errors.append(VerificationError(
                        field="num_interim_analyses",
                        expected=1,
                        found=2,
                        severity="critical",
                        context="Text says 'two interim' but protocol has 1"
                    ))
                if 'three interim' in text_lower or '3 interim' in text_lower:
                    self.errors.append(VerificationError(
                        field="num_interim_analyses",
                        expected=1,
                        found=3,
                        severity="critical",
                        context="Text says 'three interim' but protocol has 1"
                    ))
            elif num_interim == 2:
                if 'one interim' in text_lower or 'single interim' in text_lower:
                    self.errors.append(VerificationError(
                        field="num_interim_analyses",
                        expected=2,
                        found=1,
                        severity="critical",
                        context="Text says 'one interim' but protocol has 2"
                    ))

    def _verify_hazard_ratio(self, text: str, facts: Dict[str, Any]):
        """Verify hazard ratio matches extraction."""
        hr = facts.get('expected_hazard_ratio') or facts.get('hazard_ratio') or facts.get('hr')

        if hr:
            hr_str = f"{hr:.2f}"
            if hr_str not in text and str(hr) not in text:
                # Find what HR is mentioned
                hr_match = re.search(r'HR\s*(?:=|of)?\s*(0\.\d+)', text, re.IGNORECASE)
                if hr_match:
                    found_hr = hr_match.group(1)
                    if found_hr != hr_str:
                        self.errors.append(VerificationError(
                            field="hazard_ratio",
                            expected=hr,
                            found=found_hr,
                            severity="high",
                            context=f"Found HR={found_hr} instead of {hr}"
                        ))

    def _verify_power(self, text: str, facts: Dict[str, Any]):
        """Verify power matches extraction."""
        power = facts.get('power') or facts.get('statistical_power')

        if power:
            # Convert to percentage if needed
            power_pct = power if power > 1 else power * 100
            power_str = f"{int(power_pct)}"

            if power_str not in text:
                # Find what power is mentioned
                power_match = re.search(r'(\d{2})\s*%?\s*power', text, re.IGNORECASE)
                if power_match:
                    found_power = power_match.group(1)
                    if found_power != power_str:
                        self.warnings.append(f"Power {found_power}% found, expected {power_str}%")

    def _verify_methods(self, text: str, constraints: Dict[str, Any]):
        """
        Verify method constraints are satisfied.

        NEW ARCHITECTURE: We do NOT force specific methods (like Fleming-Harrington).
        Instead, we check that the protocol-specified method is used.
        Discrepancies are flagged as NOTES, not ERRORS.
        """
        text_lower = text.lower()

        # Check for [NEEDS REVIEW] markers in generated text
        if '[needs review]' in text_lower or '[to be specified]' in text_lower:
            self.warnings.append(
                "Generated text contains [NEEDS REVIEW] or [To be specified] markers - "
                "manual review required to fill in missing information"
            )

        # Primary test - verify protocol-specified method is present
        primary_test = constraints.get('primary_test', '')
        if primary_test:
            primary_lower = primary_test.lower()

            # Skip validation if it's a [NEEDS REVIEW] marker
            if 'needs review' in primary_lower or 'not found' in primary_lower:
                self.warnings.append(
                    f"Primary statistical method was not extracted from protocol. "
                    f"Generated SAP may have used a placeholder."
                )
            else:
                # Check if the protocol-specified method is mentioned
                # (but don't require specific methods like Fleming-Harrington)
                method_keywords = self._extract_method_keywords(primary_test)
                method_found = any(kw in text_lower for kw in method_keywords)

                if not method_found:
                    # This is a WARNING, not a critical error
                    # The protocol method should be used, but we don't override
                    self.warnings.append(
                        f"Protocol-specified method '{primary_test}' not clearly found in text. "
                        f"Verify the generated SAP uses the correct method."
                    )

        # NOTE: We no longer enforce "forbidden_primary" strictly.
        # If the protocol specifies a method, we use it regardless of drug class.
        # Discrepancies are logged as informational notes, not errors.
        forbidden = constraints.get('forbidden_primary', '')
        if forbidden and forbidden.strip():
            # Only warn if this appears in a descriptive context (single-arm study)
            # For comparative studies, we respect the protocol-specified method
            if 'descriptive' in forbidden.lower():
                # This is for single-arm studies where comparative methods are forbidden
                primary_section = text_lower.split('sensitivity')[0] if 'sensitivity' in text_lower else text_lower
                for method in ['log-rank', 'cox regression', 'fleming-harrington']:
                    if method in primary_section and 'primary' in primary_section:
                        self.errors.append(VerificationError(
                            field="forbidden_primary",
                            expected="Descriptive statistics (single-arm study)",
                            found=method,
                            severity="high",
                            context=f"Comparative method '{method}' used in single-arm study"
                        ))
                        break

    def _extract_method_keywords(self, method_name: str) -> List[str]:
        """Extract searchable keywords from a method name."""
        method_lower = method_name.lower()
        keywords = []

        # Common method keyword mappings
        if 'log-rank' in method_lower or 'logrank' in method_lower:
            keywords.extend(['log-rank', 'logrank', 'log rank'])
        if 'stratified' in method_lower:
            keywords.append('stratified')
        if 'fleming' in method_lower:
            keywords.extend(['fleming', 'fh(', 'harrington'])
        if 'cox' in method_lower:
            keywords.extend(['cox', 'proportional hazard'])
        if 'kaplan' in method_lower:
            keywords.extend(['kaplan', 'km'])
        if 'descriptive' in method_lower:
            keywords.extend(['descriptive', 'summary statistics'])

        # Fallback: use first few significant words
        if not keywords:
            words = [w for w in method_lower.split() if len(w) > 3]
            keywords.extend(words[:3])

        return keywords

    def _check_rag_contamination(self, text: str, facts: Dict[str, Any]):
        """Check for common RAG contamination patterns."""

        # Check for common wrong event counts
        final_events = facts.get('final_events') or facts.get('final_analysis_events')
        if final_events:
            for wrong_count in self.COMMON_RAG_CONTAMINATION['event_counts']:
                if wrong_count != str(final_events) and wrong_count in text:
                    # Check if it's in an events context
                    if re.search(rf'{wrong_count}\s*(?:deaths?|events?)', text, re.IGNORECASE):
                        self.warnings.append(
                            f"Possible RAG contamination: {wrong_count} events found "
                            f"(expected {final_events})"
                        )

    def _find_wrong_number(
        self,
        text: str,
        expected: int,
        field_type: str,
        context_keywords: List[str]
    ) -> Optional[str]:
        """Find a wrong number in the relevant context."""

        for keyword in context_keywords:
            # Look for numbers near the keyword
            pattern = rf'{keyword}[^.]*?(\d{{2,4}})'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if match != str(expected):
                    return match

            # Also check reverse pattern
            pattern = rf'(\d{{2,4}})[^.]*?{keyword}'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if match != str(expected):
                    return match

        return None

    def generate_correction_prompt(
        self,
        original_text: str,
        facts: Dict[str, Any]
    ) -> str:
        """
        Generate a correction prompt for SELF-RAG regeneration.

        Args:
            original_text: The generated text with errors
            facts: The correct facts

        Returns:
            Prompt for regeneration with corrections
        """
        error_descriptions = []
        corrections = []

        for error in self.errors:
            error_descriptions.append(
                f"- {error.field}: Found '{error.found}', should be '{error.expected}'"
            )
            corrections.append(
                f"- {error.field} MUST be exactly: {error.expected}"
            )

        return f"""The following SAP section contains factual errors that need correction.

## ERRORS FOUND:
{chr(10).join(error_descriptions)}

## CORRECT VALUES (from protocol - USE THESE EXACTLY):
{chr(10).join(corrections)}

## ORIGINAL TEXT WITH ERRORS:
{original_text}

## TASK:
Rewrite the section correcting ONLY the errors listed above.
Keep all other content, structure, and prose style the same.
Replace ONLY the incorrect values with the correct ones.

CRITICAL: Do not introduce any new numbers or values. Use ONLY the correct values provided above.
"""

    def get_error_summary(self) -> str:
        """Get a human-readable error summary."""
        if not self.errors:
            return "No errors found."

        lines = ["Verification Errors:"]
        for error in self.errors:
            lines.append(f"  [{error.severity.upper()}] {error.field}: {error.context}")

        if self.warnings:
            lines.append("\nWarnings:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        return "\n".join(lines)


def test_verifier():
    """Test the verifier with new architecture."""

    verifier = FactVerifier()

    print("=" * 60)
    print("TEST 1: Numerical errors (should flag)")
    print("=" * 60)

    # Simulated generated text with NUMERICAL errors
    generated = """
    The study will enroll 504 patients. The primary analysis will be performed
    at 639 death events. At interim analysis (291 events, 50% information),
    H0 will be rejected if p < 0.05. Two interim analyses are planned.

    The primary comparison will use the stratified log-rank test.
    """

    # Correct facts
    facts = {
        'sample_size': 504,
        'final_events': 382,  # Wrong in text (639) - SHOULD FLAG
        'interim_events': 291,
        'num_interim_analyses': 1,  # Wrong in text (two) - SHOULD FLAG
        'alpha_at_interim': 0.020,  # Wrong in text (0.05) - SHOULD FLAG
    }

    # NEW ARCHITECTURE: Protocol specifies stratified log-rank
    # We should NOT force Fleming-Harrington anymore
    constraints = {
        'primary_test': 'stratified log-rank test',  # What the protocol says
        'forbidden_primary': '',  # No forced method restrictions for comparative studies
    }

    result = verifier.verify(generated, facts, constraints)

    print(f"Passed: {result.passed}")
    print(f"Score: {result.score:.2f}")
    print(verifier.get_error_summary())

    print("\n" + "=" * 60)
    print("TEST 2: Method correctly used (should pass)")
    print("=" * 60)

    # Generated text that uses protocol-specified method
    generated2 = """
    The study will enroll 504 patients. The primary analysis will be performed
    at 382 death events. At interim analysis (291 events),
    H0 will be rejected if p < 0.020. One interim analysis is planned.

    The primary comparison will use the stratified log-rank test.
    """

    result2 = verifier.verify(generated2, facts, constraints)

    print(f"Passed: {result2.passed}")
    print(f"Score: {result2.score:.2f}")
    print(verifier.get_error_summary())

    print("\n" + "=" * 60)
    print("TEST 3: Single-arm study with comparative method (should flag)")
    print("=" * 60)

    # Single-arm study shouldn't use comparative methods
    generated3 = """
    This single-arm Phase II study will enroll 50 patients.
    The primary analysis will use the log-rank test for survival comparison.
    """

    facts3 = {
        'sample_size': 50,
        'is_single_arm': True,
    }

    constraints3 = {
        'primary_test': 'Descriptive statistics only',
        'forbidden_primary': 'Descriptive (log-rank test, Cox regression inappropriate for single-arm study)',
    }

    result3 = verifier.verify(generated3, facts3, constraints3)

    print(f"Passed: {result3.passed}")
    print(f"Score: {result3.score:.2f}")
    print(verifier.get_error_summary())


if __name__ == "__main__":
    test_verifier()
