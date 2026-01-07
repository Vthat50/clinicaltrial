#!/usr/bin/env python3
"""
SAP Verification Layer
======================

This is NOT for generation. This is for CHECKING the generated SAP.

Architecture:
1. Extract "anchors" from protocol (sentences with numbers/stats)
2. Generate SAP using V2 (unchanged)
3. Verify SAP against anchors
4. Output discrepancy report

Key principle: Generate freely, verify rigorously.
"""

import re
import os
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"  # Must fix before submission
    WARNING = "warning"    # Should review
    INFO = "info"          # FYI


@dataclass
class Anchor:
    """A verifiable statement from the protocol."""
    text: str              # The actual sentence
    category: str          # sample_size, alpha, endpoint, etc.
    numbers: List[str]     # Numbers found in this sentence
    location: str          # Where in protocol (section hint)


@dataclass
class ProtocolAnchors:
    """All anchors extracted from a protocol."""
    sample_size: List[Anchor] = field(default_factory=list)
    alpha: List[Anchor] = field(default_factory=list)
    power: List[Anchor] = field(default_factory=list)
    randomization: List[Anchor] = field(default_factory=list)
    endpoints: List[Anchor] = field(default_factory=list)
    interim_analysis: List[Anchor] = field(default_factory=list)
    hypotheses: List[Anchor] = field(default_factory=list)
    boundaries: List[Anchor] = field(default_factory=list)

    def all_anchors(self) -> List[Anchor]:
        """Get all anchors as a flat list."""
        return (
            self.sample_size + self.alpha + self.power +
            self.randomization + self.endpoints +
            self.interim_analysis + self.hypotheses + self.boundaries
        )

    def summary(self) -> Dict[str, int]:
        """Count anchors by category."""
        return {
            "sample_size": len(self.sample_size),
            "alpha": len(self.alpha),
            "power": len(self.power),
            "randomization": len(self.randomization),
            "endpoints": len(self.endpoints),
            "interim_analysis": len(self.interim_analysis),
            "hypotheses": len(self.hypotheses),
            "boundaries": len(self.boundaries),
            "total": len(self.all_anchors())
        }


@dataclass
class Issue:
    """A verification issue found."""
    severity: Severity
    category: str
    message: str
    anchor: Optional[Anchor] = None  # The anchor that caused this issue
    rule: Optional[str] = None       # Regulatory rule if applicable


@dataclass
class VerificationReport:
    """Complete verification report."""
    issues: List[Issue] = field(default_factory=list)
    anchors_found: int = 0
    anchors_verified: int = 0
    anchors_missing: int = 0
    unexpected_numbers: Set[str] = field(default_factory=set)
    confidence_score: float = 0.0

    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    def needs_human_review(self) -> bool:
        return self.critical_count() > 0 or self.confidence_score < 0.8

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "VERIFICATION REPORT",
            "=" * 60,
            f"Anchors found in protocol: {self.anchors_found}",
            f"Anchors verified in SAP: {self.anchors_verified}",
            f"Anchors missing from SAP: {self.anchors_missing}",
            f"Unexpected numbers in SAP: {len(self.unexpected_numbers)}",
            "",
            f"Critical issues: {self.critical_count()}",
            f"Warnings: {self.warning_count()}",
            f"Confidence score: {self.confidence_score:.1%}",
            f"Human review required: {'YES' if self.needs_human_review() else 'NO'}",
            "=" * 60,
        ]

        if self.issues:
            lines.append("\nISSUES:")
            for issue in self.issues:
                prefix = "🔴" if issue.severity == Severity.CRITICAL else "🟡" if issue.severity == Severity.WARNING else "🔵"
                lines.append(f"  {prefix} [{issue.category}] {issue.message}")
                if issue.rule:
                    lines.append(f"      Rule: {issue.rule}")

        if self.unexpected_numbers:
            lines.append(f"\nUnexpected numbers: {', '.join(list(self.unexpected_numbers)[:10])}")

        return "\n".join(lines)


# =============================================================================
# ANCHOR EXTRACTION
# =============================================================================

# Patterns for finding statistical sentences
STATISTICAL_TERMS = [
    # Sample size
    r'\b(sample size|n\s*=|patients|subjects|participants|enrolled?|recruit)',
    # Alpha/significance
    r'\b(alpha|α|significance|p-value|p\s*<|p\s*=|type.?i.?error|one.?sided|two.?sided)',
    # Power
    r'\b(power|β|beta|type.?ii.?error)',
    # Effect size
    r'\b(hazard ratio|hr\s*=|odds ratio|or\s*=|risk ratio|rr\s*=|effect size)',
    # Randomization
    r'\b(randomi[sz]|allocation|1:1|2:1|1:2|stratif)',
    # Endpoints
    r'\b(endpoint|primary|secondary|efficacy|outcome|pfs|os\b|dfs|rfs|orr|dcr|dor)',
    # Interim
    r'\b(interim|futility|efficacy.?bound|stopping|idmc|dsmb|dmec)',
    # Hypotheses
    r'\b(hypothesis|hypotheses|superiority|non.?inferiority|ni.?margin|equivalence)',
    # Boundaries
    r'\b(o.?brien|fleming|lan.?demets|alpha.?spending|boundary|z.?score)',
    # Methods
    r'\b(log.?rank|cox|kaplan.?meier|stratified|anova|ancova|mmrm|glm)',
]

# Pattern for numbers (including decimals, percentages, ratios)
NUMBER_PATTERN = re.compile(
    r'\b(\d+(?:,\d{3})*(?:\.\d+)?%?|\d+:\d+|\d+\.\d+|\.\d+)\b'
)


def extract_numbers(text: str) -> Set[str]:
    """Extract all numbers from text."""
    matches = NUMBER_PATTERN.findall(text)
    # Normalize: remove commas, standardize
    normalized = set()
    for m in matches:
        # Skip very small numbers that are likely not important
        clean = m.replace(',', '')
        try:
            val = float(clean.rstrip('%'))
            if val >= 0.0001:  # Skip tiny decimals
                normalized.add(clean)
        except ValueError:
            if ':' in m:  # Ratios like 1:1
                normalized.add(m)
    return normalized


def find_anchor_sentences(text: str, patterns: List[str], category: str) -> List[Anchor]:
    """Find sentences matching statistical patterns."""
    anchors = []

    # Better sentence splitting: split on periods, newlines, colons followed by newlines
    # First normalize newlines
    text = re.sub(r'\n+', '\n', text)

    # Split into lines first, then sentences
    lines = text.split('\n')
    sentences = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Split line into sentences
        line_sentences = re.split(r'(?<=[.!?])\s+', line)
        sentences.extend(line_sentences)

    # Compile patterns
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]

    seen_texts = set()  # Avoid duplicates

    for sentence in sentences:
        sentence = sentence.strip()

        # Skip too short or too long
        if len(sentence) < 15 or len(sentence) > 500:
            continue

        # Skip if already seen (similar text)
        text_key = sentence[:50].lower()
        if text_key in seen_texts:
            continue

        # Check if sentence matches any pattern
        matches_pattern = any(p.search(sentence) for p in compiled)

        # Check if sentence has numbers
        numbers = list(extract_numbers(sentence))

        # Must have both: pattern match AND numbers
        if matches_pattern and numbers:
            seen_texts.add(text_key)
            anchors.append(Anchor(
                text=sentence,
                category=category,
                numbers=numbers,
                location=""
            ))

    return anchors


def extract_anchors(protocol_text: str) -> ProtocolAnchors:
    """
    Extract anchor sentences from protocol.

    These are NOT for generation. They are for VERIFICATION.
    We store the raw sentences, not parsed values.
    """

    anchors = ProtocolAnchors()

    # Sample size anchors
    anchors.sample_size = find_anchor_sentences(
        protocol_text,
        [r'\b(sample size|n\s*=|patients|subjects|participants|enroll)',
         r'\b(\d+)\s*(patients|subjects|participants)'],
        "sample_size"
    )

    # Alpha anchors
    anchors.alpha = find_anchor_sentences(
        protocol_text,
        [r'\b(alpha|α|significance|type.?i)', r'\b(one.?sided|two.?sided)', r'p\s*[<=]'],
        "alpha"
    )

    # Power anchors
    anchors.power = find_anchor_sentences(
        protocol_text,
        [r'\b(power|\d+%\s*power)', r'\b(type.?ii|beta|β)'],
        "power"
    )

    # Randomization anchors
    anchors.randomization = find_anchor_sentences(
        protocol_text,
        [r'\b(randomi[sz]|allocation)', r'\b(\d:\d)'],
        "randomization"
    )

    # Endpoint anchors
    anchors.endpoints = find_anchor_sentences(
        protocol_text,
        [r'\b(primary\s*endpoint|secondary\s*endpoint|co.?primary)',
         r'\b(pfs|os\b|dfs|rfs|orr|dcr|dor|ttf|ttp)'],
        "endpoints"
    )

    # Interim analysis anchors
    anchors.interim_analysis = find_anchor_sentences(
        protocol_text,
        [r'\b(interim\s*anal)', r'\b(idmc|dsmb|dmec)', r'\b(futility|efficacy.?stop)'],
        "interim_analysis"
    )

    # Hypothesis anchors
    anchors.hypotheses = find_anchor_sentences(
        protocol_text,
        [r'\b(hypothesis|hypotheses)', r'\b(superiority|non.?inferiority|equivalence)',
         r'\b(ni.?margin|margin\s*of)'],
        "hypotheses"
    )

    # Boundary anchors
    anchors.boundaries = find_anchor_sentences(
        protocol_text,
        [r'\b(o.?brien|fleming|lan.?demets)', r'\b(alpha.?spending|spending.?function)',
         r'\b(stopping.?bound|efficacy.?bound|z.?score)'],
        "boundaries"
    )

    return anchors


# =============================================================================
# VERIFICATION
# =============================================================================

def verify_anchor_in_sap(anchor: Anchor, sap_text: str) -> Tuple[bool, str]:
    """
    Check if an anchor's information appears in the SAP.

    We don't require exact text match. We check:
    1. Are the key numbers present?
    2. Is the concept addressed?
    """
    sap_lower = sap_text.lower()
    anchor_lower = anchor.text.lower()

    # Check if key numbers are present
    sap_numbers = extract_numbers(sap_text)
    numbers_found = sum(1 for n in anchor.numbers if n in sap_numbers)
    numbers_ratio = numbers_found / len(anchor.numbers) if anchor.numbers else 1.0

    # Check for key terms from anchor
    key_terms = re.findall(r'\b[a-z]{4,}\b', anchor_lower)
    terms_found = sum(1 for t in key_terms if t in sap_lower)
    terms_ratio = terms_found / len(key_terms) if key_terms else 1.0

    # Consider verified if most numbers present and some terms match
    verified = numbers_ratio >= 0.5 and terms_ratio >= 0.3

    reason = f"Numbers: {numbers_found}/{len(anchor.numbers)}, Terms: {terms_found}/{len(key_terms)}"

    return verified, reason


def check_regulatory_compliance(sap_text: str) -> List[Issue]:
    """
    Check SAP against regulatory requirements.

    This is the Knowledge Graph's new job: CHECKING, not generating.
    """
    issues = []
    sap_lower = sap_text.lower()

    # ICH E9: Sample size justification
    has_sample_size = bool(re.search(r'sample\s*size', sap_lower))
    has_power_justification = bool(re.search(r'(power|precision).*(\d+%|\d+\.\d+)', sap_lower))
    if has_sample_size and not has_power_justification:
        issues.append(Issue(
            severity=Severity.WARNING,
            category="regulatory",
            message="Sample size mentioned without power/precision justification",
            rule="ICH E9 Section 3.5"
        ))

    # ICH E9 R1: Estimand framework
    has_estimand = bool(re.search(r'estimand', sap_lower))
    if not has_estimand:
        issues.append(Issue(
            severity=Severity.INFO,
            category="regulatory",
            message="Estimand framework not explicitly mentioned (recommended per ICH E9 R1)",
            rule="ICH E9(R1)"
        ))

    # FDA: Missing data handling
    has_missing_data = bool(re.search(r'missing\s*(data|value)', sap_lower))
    if not has_missing_data:
        issues.append(Issue(
            severity=Severity.WARNING,
            category="regulatory",
            message="Missing data handling not addressed",
            rule="FDA Statistical Guidance"
        ))

    # Multiplicity
    has_multiple_endpoints = len(re.findall(r'(primary|secondary)\s*endpoint', sap_lower)) > 1
    has_multiplicity = bool(re.search(r'(multiplicity|alpha.*allocation|bonferroni|hochberg|gatekeep)', sap_lower))
    if has_multiple_endpoints and not has_multiplicity:
        issues.append(Issue(
            severity=Severity.WARNING,
            category="regulatory",
            message="Multiple endpoints without multiplicity adjustment discussion",
            rule="ICH E9 Section 2.2.5"
        ))

    # Interim analysis requirements
    has_interim = bool(re.search(r'interim\s*anal', sap_lower))
    has_alpha_spending = bool(re.search(r'(alpha.*spending|o.?brien|lan.?demets)', sap_lower))
    if has_interim and not has_alpha_spending:
        issues.append(Issue(
            severity=Severity.WARNING,
            category="regulatory",
            message="Interim analysis without alpha spending function specified",
            rule="FDA Guidance on Adaptive Designs"
        ))

    return issues


def verify_sap(
    sap_text: str,
    protocol_text: str,
    anchors: Optional[ProtocolAnchors] = None
) -> VerificationReport:
    """
    Verify a generated SAP against the protocol.

    This is the main verification function.
    """

    # Extract anchors if not provided
    if anchors is None:
        anchors = extract_anchors(protocol_text)

    report = VerificationReport()
    report.anchors_found = len(anchors.all_anchors())

    # Verify each anchor
    for anchor in anchors.all_anchors():
        verified, reason = verify_anchor_in_sap(anchor, sap_text)

        if verified:
            report.anchors_verified += 1
        else:
            report.anchors_missing += 1
            report.issues.append(Issue(
                severity=Severity.WARNING if anchor.category in ['boundaries', 'power'] else Severity.CRITICAL,
                category=anchor.category,
                message=f"Protocol anchor not found in SAP: {anchor.text[:100]}...",
                anchor=anchor
            ))

    # Check for unexpected numbers
    protocol_numbers = extract_numbers(protocol_text)
    sap_numbers = extract_numbers(sap_text)
    report.unexpected_numbers = sap_numbers - protocol_numbers

    # Filter out common expected numbers
    common_numbers = {'0', '1', '2', '3', '4', '5', '0.05', '0.025', '0.01', '95', '90', '80', '100'}
    report.unexpected_numbers -= common_numbers

    if report.unexpected_numbers:
        report.issues.append(Issue(
            severity=Severity.WARNING,
            category="numbers",
            message=f"SAP contains {len(report.unexpected_numbers)} numbers not found in protocol"
        ))

    # Regulatory compliance
    regulatory_issues = check_regulatory_compliance(sap_text)
    report.issues.extend(regulatory_issues)

    # Calculate confidence score
    if report.anchors_found > 0:
        anchor_score = report.anchors_verified / report.anchors_found
    else:
        anchor_score = 0.5  # No anchors found is uncertain

    # Penalize for issues
    critical_penalty = report.critical_count() * 0.1
    warning_penalty = report.warning_count() * 0.02

    report.confidence_score = max(0, anchor_score - critical_penalty - warning_penalty)

    return report


# =============================================================================
# CLI / TEST
# =============================================================================

def test_locally():
    """Test the verification system locally."""

    # Test with a sample protocol excerpt
    sample_protocol = """
    STUDY DESIGN AND SAMPLE SIZE

    This is a Phase 3, randomized, open-label study. Patients will be randomized
    in a 1:1 ratio to receive either pembrolizumab plus lenvatinib or chemotherapy.

    The total sample size is 875 patients, with 612 patients in the pMMR population
    and approximately 263 patients in the dMMR population.

    STATISTICAL HYPOTHESES

    The primary hypothesis (H1) tests superiority of PFS in the pMMR population
    with alpha = 0.005 (one-sided). The secondary hypothesis (H3) tests OS
    non-inferiority with a margin of 1.1 and alpha = 0.02 (one-sided).

    SAMPLE SIZE JUSTIFICATION

    The study has 90% power to detect a hazard ratio of 0.7 for PFS, assuming
    a median PFS of 6.0 months in the control arm.

    INTERIM ANALYSES

    Three interim analyses are planned at approximately 27, 36, and 42 months.
    The Lan-DeMets alpha spending function with O'Brien-Fleming boundaries will
    be used to control type I error. At IA1 (~354 PFS events), the efficacy
    boundary is Z = 2.96 (p = 0.0015, HR ≤ 0.72).
    """

    # Test with a sample SAP (some things correct, some missing)
    sample_sap = """
    STATISTICAL ANALYSIS PLAN

    1. STUDY DESIGN

    This is a Phase 3, randomized, open-label study with 1:1 randomization
    between pembrolizumab plus lenvatinib and chemotherapy.

    2. SAMPLE SIZE

    A total of 875 patients will be enrolled. The study is powered at 90%
    to detect a hazard ratio of 0.7.

    3. HYPOTHESES

    H1: PFS superiority in pMMR population (alpha = 0.005, one-sided)
    H3: OS non-inferiority with margin of 1.1 (alpha = 0.02, one-sided)

    4. INTERIM ANALYSES

    Three interim analyses are planned using Lan-DeMets alpha spending
    with O'Brien-Fleming boundaries.

    5. MISSING DATA

    Missing data will be handled using multiple imputation.
    """

    print("=" * 60)
    print("TESTING SAP VERIFICATION LOCALLY")
    print("=" * 60)

    # Extract anchors
    print("\n[Step 1] Extracting anchors from protocol...")
    anchors = extract_anchors(sample_protocol)

    print(f"\nAnchors found:")
    for cat, count in anchors.summary().items():
        if count > 0 and cat != 'total':
            print(f"  {cat}: {count}")
    print(f"  TOTAL: {anchors.summary()['total']}")

    # Show some anchor examples
    print("\nExample anchors:")
    for anchor in anchors.all_anchors()[:5]:
        print(f"  [{anchor.category}] Numbers: {anchor.numbers}")
        print(f"    \"{anchor.text[:80]}...\"")

    # Verify SAP
    print("\n[Step 2] Verifying SAP against anchors...")
    report = verify_sap(sample_sap, sample_protocol, anchors)

    # Print report
    print("\n" + report.summary())

    return report


if __name__ == "__main__":
    test_locally()
