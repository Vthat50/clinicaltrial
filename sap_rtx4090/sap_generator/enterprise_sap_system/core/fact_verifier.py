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
        """Verify method constraints are satisfied."""
        text_lower = text.lower()

        # Primary test
        primary_test = constraints.get('primary_test', '')
        if primary_test:
            primary_lower = primary_test.lower()
            # Check various formulations
            if 'fleming' in primary_lower:
                if 'fleming' not in text_lower and 'fh' not in text_lower:
                    self.errors.append(VerificationError(
                        field="primary_test",
                        expected=primary_test,
                        found="not found",
                        severity="critical",
                        context="Fleming-Harrington test required but not found"
                    ))

        # Forbidden primary
        forbidden = constraints.get('forbidden_primary', '')
        if forbidden and forbidden.lower() in text_lower:
            # Check if it's used as PRIMARY (not sensitivity)
            primary_section = text_lower.split('sensitivity')[0] if 'sensitivity' in text_lower else text_lower
            if 'primary' in primary_section:
                forbidden_pos = primary_section.find(forbidden.lower())
                if forbidden_pos != -1:
                    context_start = max(0, forbidden_pos - 50)
                    context_end = min(len(primary_section), forbidden_pos + 50)
                    context = primary_section[context_start:context_end]
                    if 'primary' in context:
                        self.errors.append(VerificationError(
                            field="forbidden_primary",
                            expected=f"NOT {forbidden}",
                            found=forbidden,
                            severity="critical",
                            context=f"Forbidden method '{forbidden}' used as primary"
                        ))

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
    """Test the verifier."""

    verifier = FactVerifier()

    # Simulated generated text with errors
    generated = """
    The study will enroll 504 patients. The primary analysis will be performed
    at 639 death events. At interim analysis (291 events, 50% information),
    H0 will be rejected if p < 0.05. Two interim analyses are planned.

    The primary comparison will use the stratified log-rank test.
    """

    # Correct facts
    facts = {
        'sample_size': 504,
        'final_events': 382,  # Wrong in text (639)
        'interim_events': 291,
        'num_interim_analyses': 1,  # Wrong in text (two)
        'alpha_at_interim': 0.020,  # Wrong in text (0.05)
    }

    constraints = {
        'primary_test': 'Fleming-Harrington',
        'forbidden_primary': 'stratified log-rank',
    }

    result = verifier.verify(generated, facts, constraints)

    print("=" * 60)
    print("VERIFICATION RESULT")
    print("=" * 60)
    print(f"Passed: {result.passed}")
    print(f"Score: {result.score:.2f}")
    print()
    print(verifier.get_error_summary())

    if not result.passed:
        print("\n" + "=" * 60)
        print("CORRECTION PROMPT")
        print("=" * 60)
        print(verifier.generate_correction_prompt(generated, facts))


if __name__ == "__main__":
    test_verifier()
