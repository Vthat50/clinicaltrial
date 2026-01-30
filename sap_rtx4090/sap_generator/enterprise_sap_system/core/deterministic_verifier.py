#!/usr/bin/env python3
"""
Deterministic Verification Layer
=================================

Production-grade verification that does NOT use LLM-as-judge.

Principle: "Don't trust the LLM to compute or judge; trust it only to translate."
           - If an AI output cannot be proven, it should not go to production.

Verification Steps:
1. EXTRACTION VERIFICATION - Do extracted values exist in protocol?
2. CALCULATION VERIFICATION - Do SAP calculations match R output?
3. CONSISTENCY VERIFICATION - Are values used consistently in SAP?
4. COMPLETENESS VERIFICATION - Are required sections present?

Each verification is deterministic and auditable.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from enum import Enum


class VerificationStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class VerificationItem:
    """A single verification check."""
    check_name: str
    status: VerificationStatus
    expected: Optional[str] = None
    actual: Optional[str] = None
    source_location: Optional[str] = None  # Page/section in protocol
    message: str = ""


@dataclass
class AuditReport:
    """Complete audit report for regulatory submission."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    protocol_id: str = ""

    # Verification results
    extraction_checks: List[VerificationItem] = field(default_factory=list)
    calculation_checks: List[VerificationItem] = field(default_factory=list)
    consistency_checks: List[VerificationItem] = field(default_factory=list)
    completeness_checks: List[VerificationItem] = field(default_factory=list)

    # Summary
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warning_checks: int = 0

    # Flags
    requires_human_review: bool = False
    critical_failures: List[str] = field(default_factory=list)

    def calculate_summary(self):
        """Calculate summary statistics."""
        all_checks = (
            self.extraction_checks +
            self.calculation_checks +
            self.consistency_checks +
            self.completeness_checks
        )
        self.total_checks = len(all_checks)
        self.passed_checks = sum(1 for c in all_checks if c.status == VerificationStatus.PASSED)
        self.failed_checks = sum(1 for c in all_checks if c.status == VerificationStatus.FAILED)
        self.warning_checks = sum(1 for c in all_checks if c.status == VerificationStatus.WARNING)

        # Determine if human review needed
        self.requires_human_review = self.failed_checks > 0 or self.warning_checks > 2

        # Collect critical failures
        self.critical_failures = [
            c.message for c in all_checks
            if c.status == VerificationStatus.FAILED
        ]


class DeterministicVerifier:
    """
    Deterministic verification of SAP against protocol and calculations.

    NO LLM CALLS - Pure deterministic verification.
    """

    # Key fields to verify
    KEY_FIELDS = [
        'sample_size',
        'alpha',
        'power',
        'hazard_ratio',
        'events',
        'randomization_ratio',
    ]

    # Required SAP sections
    REQUIRED_SECTIONS = [
        "INTRODUCTION",
        "STUDY OBJECTIVES",
        "STUDY DESIGN",
        "ANALYSIS POPULATIONS",
        "STATISTICAL HYPOTHESES",
        "STATISTICAL METHODS",
        "INTERIM ANALYSES",
        "SAFETY ANALYSES",
        "MISSING DATA",
    ]

    def __init__(self):
        self.report = None

    def verify(
        self,
        sap_text: str,
        protocol_text: str,
        discovered_elements: List[Any],
        r_boundaries: Optional[Dict] = None
    ) -> AuditReport:
        """
        Run complete verification suite.

        Args:
            sap_text: Generated SAP text
            protocol_text: Original protocol text
            discovered_elements: Elements discovered in Pass 1
            r_boundaries: Pre-calculated boundaries from R (if available)

        Returns:
            AuditReport with all verification results
        """
        self.report = AuditReport()

        # 1. Extraction verification - do values exist in protocol?
        self._verify_extractions(discovered_elements, protocol_text)

        # 2. Calculation verification - do SAP values match R?
        if r_boundaries:
            self._verify_calculations(sap_text, r_boundaries)

        # 3. Consistency verification - are values consistent in SAP?
        self._verify_consistency(sap_text, discovered_elements)

        # 4. Completeness verification - are required sections present?
        self._verify_completeness(sap_text)

        # Calculate summary
        self.report.calculate_summary()

        return self.report

    def _verify_extractions(
        self,
        discovered_elements: List[Any],
        protocol_text: str
    ):
        """Verify that extracted values actually exist in protocol.

        Uses source_page and source_context from DiscoveredElement for traceability.
        """

        for elem in discovered_elements:
            name = getattr(elem, 'name', '') or ''
            value = getattr(elem, 'value', '') or getattr(elem, 'description', '') or ''
            category = getattr(elem, 'category', '') or ''
            # Source traceability fields
            source_page = getattr(elem, 'source_page', None)
            source_context = getattr(elem, 'source_context', None)

            if not value or not isinstance(value, str):
                continue

            # Extract numbers from value
            numbers = re.findall(r'\d+\.?\d*', str(value))

            for num in numbers[:3]:  # Check first 3 numbers
                # Verify number exists in protocol
                if num in protocol_text:
                    # Build source location from traceability data
                    if source_page:
                        source_loc = f"Page {source_page}"
                        if source_context:
                            source_loc += f": \"{source_context[:50]}...\""
                    else:
                        # Find approximate location in text
                        idx = protocol_text.find(num)
                        # Try to find page marker
                        page_marker_pos = protocol_text.rfind('--- PAGE ', 0, idx)
                        if page_marker_pos >= 0:
                            page_end = protocol_text.find(' ---', page_marker_pos)
                            page_num = protocol_text[page_marker_pos + 9:page_end]
                            source_loc = f"Page {page_num}"
                        else:
                            context_start = max(0, idx - 30)
                            context_end = min(len(protocol_text), idx + 30)
                            source_loc = f"...{protocol_text[context_start:context_end]}..."

                    self.report.extraction_checks.append(VerificationItem(
                        check_name=f"Extract: {name}",
                        status=VerificationStatus.PASSED,
                        expected=num,
                        actual=num,
                        source_location=source_loc,
                        message=f"Value '{num}' verified in protocol"
                    ))
                else:
                    self.report.extraction_checks.append(VerificationItem(
                        check_name=f"Extract: {name}",
                        status=VerificationStatus.WARNING,
                        expected=num,
                        actual="NOT FOUND",
                        source_location=f"Page {source_page}" if source_page else "Unknown",
                        message=f"Value '{num}' not found in protocol text"
                    ))

    def _verify_calculations(self, sap_text: str, r_boundaries: Dict):
        """Verify SAP boundary values match R calculations."""

        # Extract Z-boundaries from SAP text
        z_pattern = r'[Zz][-\s]*(?:boundary|score|statistic)?\s*[=:]\s*(-?\d+\.?\d*)'
        sap_z_values = re.findall(z_pattern, sap_text)

        # Get R-calculated Z values
        r_z_values = r_boundaries.get('z_boundaries', [])

        if r_z_values:
            for i, r_z in enumerate(r_z_values):
                r_z_str = f"{float(r_z):.3f}"

                # Check if this Z value appears in SAP
                found = False
                for sap_z in sap_z_values:
                    try:
                        if abs(float(sap_z) - float(r_z)) < 0.01:
                            found = True
                            self.report.calculation_checks.append(VerificationItem(
                                check_name=f"Z-boundary {i+1}",
                                status=VerificationStatus.PASSED,
                                expected=r_z_str,
                                actual=sap_z,
                                message=f"Z-boundary matches R calculation"
                            ))
                            break
                    except ValueError:
                        continue

                if not found:
                    self.report.calculation_checks.append(VerificationItem(
                        check_name=f"Z-boundary {i+1}",
                        status=VerificationStatus.FAILED,
                        expected=r_z_str,
                        actual="NOT FOUND or MISMATCH",
                        message=f"R calculated Z={r_z_str} but SAP doesn't match"
                    ))

        # Verify alpha spending
        r_alpha = r_boundaries.get('cumulative_alpha', [])
        if r_alpha:
            alpha_pattern = r'cumulative\s*(?:alpha|α)\s*[=:]\s*(\d+\.?\d*)'
            sap_alphas = re.findall(alpha_pattern, sap_text, re.IGNORECASE)

            for i, expected_alpha in enumerate(r_alpha):
                expected_str = f"{float(expected_alpha):.6f}"
                found = any(
                    abs(float(a) - float(expected_alpha)) < 0.0001
                    for a in sap_alphas
                    if a
                )

                self.report.calculation_checks.append(VerificationItem(
                    check_name=f"Cumulative Alpha {i+1}",
                    status=VerificationStatus.PASSED if found else VerificationStatus.WARNING,
                    expected=expected_str,
                    actual="Found" if found else "Not explicitly stated",
                    message="Alpha spending verified" if found else "Alpha spending not explicitly shown"
                ))

    def _verify_consistency(self, sap_text: str, discovered_elements: List[Any]):
        """Verify values are used consistently throughout SAP."""

        # Build map of key values
        key_values = {}
        for elem in discovered_elements:
            category = (getattr(elem, 'category', '') or '').lower()
            value = getattr(elem, 'value', '') or getattr(elem, 'description', '')

            if 'sample' in category:
                numbers = re.findall(r'\d+', str(value))
                if numbers:
                    key_values['sample_size'] = numbers[0]
            elif 'alpha' in category or 'significance' in category:
                numbers = re.findall(r'0\.\d+', str(value))
                if numbers:
                    key_values['alpha'] = numbers[0]

        # Check sample size consistency
        if 'sample_size' in key_values:
            expected_n = key_values['sample_size']
            # Find all sample size mentions in SAP
            n_pattern = r'(\d+)\s*(?:patients|participants|subjects)'
            sap_n_values = re.findall(n_pattern, sap_text, re.IGNORECASE)

            if sap_n_values:
                # Check if expected value is the most common
                from collections import Counter
                n_counts = Counter(sap_n_values)
                most_common = n_counts.most_common(1)[0][0]

                if most_common == expected_n:
                    self.report.consistency_checks.append(VerificationItem(
                        check_name="Sample Size Consistency",
                        status=VerificationStatus.PASSED,
                        expected=expected_n,
                        actual=most_common,
                        message=f"Sample size {expected_n} used consistently"
                    ))
                else:
                    self.report.consistency_checks.append(VerificationItem(
                        check_name="Sample Size Consistency",
                        status=VerificationStatus.WARNING,
                        expected=expected_n,
                        actual=f"Multiple values: {dict(n_counts)}",
                        message="Sample size values inconsistent in SAP"
                    ))

    def _verify_completeness(self, sap_text: str):
        """Verify required sections are present."""

        sap_upper = sap_text.upper()

        for section in self.REQUIRED_SECTIONS:
            # Check if section heading exists
            if section in sap_upper:
                self.report.completeness_checks.append(VerificationItem(
                    check_name=f"Section: {section}",
                    status=VerificationStatus.PASSED,
                    message=f"Section '{section}' present"
                ))
            else:
                self.report.completeness_checks.append(VerificationItem(
                    check_name=f"Section: {section}",
                    status=VerificationStatus.WARNING,
                    message=f"Section '{section}' not found"
                ))

    def format_audit_report(self) -> str:
        """Format audit report as human-readable text."""

        if not self.report:
            return "No verification has been run."

        lines = [
            "=" * 70,
            "DETERMINISTIC VERIFICATION AUDIT REPORT",
            "=" * 70,
            f"Timestamp: {self.report.timestamp}",
            f"Protocol: {self.report.protocol_id}",
            "",
            f"SUMMARY:",
            f"  Total Checks: {self.report.total_checks}",
            f"  Passed: {self.report.passed_checks}",
            f"  Failed: {self.report.failed_checks}",
            f"  Warnings: {self.report.warning_checks}",
            f"  Requires Human Review: {'YES' if self.report.requires_human_review else 'NO'}",
            "",
        ]

        # Extraction checks
        if self.report.extraction_checks:
            lines.append("-" * 70)
            lines.append("EXTRACTION VERIFICATION (Values exist in protocol)")
            lines.append("-" * 70)
            for check in self.report.extraction_checks:
                status_icon = "✓" if check.status == VerificationStatus.PASSED else "⚠" if check.status == VerificationStatus.WARNING else "✗"
                lines.append(f"  {status_icon} {check.check_name}: {check.message}")
                if check.source_location:
                    lines.append(f"      Source: {check.source_location}")

        # Calculation checks
        if self.report.calculation_checks:
            lines.append("")
            lines.append("-" * 70)
            lines.append("CALCULATION VERIFICATION (SAP matches R output)")
            lines.append("-" * 70)
            for check in self.report.calculation_checks:
                status_icon = "✓" if check.status == VerificationStatus.PASSED else "⚠" if check.status == VerificationStatus.WARNING else "✗"
                lines.append(f"  {status_icon} {check.check_name}")
                lines.append(f"      Expected (R): {check.expected}")
                lines.append(f"      Actual (SAP): {check.actual}")

        # Consistency checks
        if self.report.consistency_checks:
            lines.append("")
            lines.append("-" * 70)
            lines.append("CONSISTENCY VERIFICATION (Values consistent in SAP)")
            lines.append("-" * 70)
            for check in self.report.consistency_checks:
                status_icon = "✓" if check.status == VerificationStatus.PASSED else "⚠" if check.status == VerificationStatus.WARNING else "✗"
                lines.append(f"  {status_icon} {check.check_name}: {check.message}")

        # Completeness checks
        if self.report.completeness_checks:
            lines.append("")
            lines.append("-" * 70)
            lines.append("COMPLETENESS VERIFICATION (Required sections present)")
            lines.append("-" * 70)
            for check in self.report.completeness_checks:
                status_icon = "✓" if check.status == VerificationStatus.PASSED else "⚠" if check.status == VerificationStatus.WARNING else "✗"
                lines.append(f"  {status_icon} {check.check_name}")

        # Critical failures
        if self.report.critical_failures:
            lines.append("")
            lines.append("=" * 70)
            lines.append("CRITICAL FAILURES - REQUIRE HUMAN REVIEW")
            lines.append("=" * 70)
            for failure in self.report.critical_failures:
                lines.append(f"  ✗ {failure}")

        lines.append("")
        lines.append("=" * 70)
        lines.append("END OF AUDIT REPORT")
        lines.append("=" * 70)

        return "\n".join(lines)


def verify_sap_deterministic(
    sap_text: str,
    protocol_text: str,
    discovered_elements: List[Any],
    r_boundaries: Optional[Dict] = None,
    protocol_id: str = "unknown"
) -> Tuple[AuditReport, str]:
    """
    Main entry point for deterministic verification.

    Returns:
        Tuple of (AuditReport object, formatted report string)
    """
    verifier = DeterministicVerifier()
    report = verifier.verify(
        sap_text=sap_text,
        protocol_text=protocol_text,
        discovered_elements=discovered_elements,
        r_boundaries=r_boundaries
    )
    report.protocol_id = protocol_id

    formatted = verifier.format_audit_report()

    return report, formatted
