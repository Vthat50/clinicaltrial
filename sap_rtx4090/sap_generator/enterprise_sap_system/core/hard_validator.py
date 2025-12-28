#!/usr/bin/env python3
"""
Hard Validator for Production SAP Generation
=============================================
BLOCKS output if ANY critical fact is wrong or missing.

This is LAYER 3 of the production pipeline:
Protocol → Extract Facts → Generate SAP → HardValidator → Output (or BLOCK)

Unlike the contamination guard which tries to clean up after the fact,
the HardValidator PREVENTS bad output from ever being returned.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Import from structured_extractor
try:
    from .structured_extractor import ProtocolFacts, RouteOfAdministration
except ImportError:
    from structured_extractor import ProtocolFacts, RouteOfAdministration


class ValidationSeverity(str, Enum):
    """Severity of validation failure"""
    CRITICAL = "critical"  # MUST block output
    HIGH = "high"          # Should block output
    MEDIUM = "medium"      # Warning, may proceed with caution
    LOW = "low"            # Minor issue, proceed


@dataclass
class ValidationIssue:
    """A single validation issue"""
    field: str
    expected: Any
    found: Any
    severity: ValidationSeverity
    message: str


@dataclass
class ValidationResult:
    """Result of validation"""
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    score: float = 0.0  # 0-100, percentage of checks passed
    block_output: bool = False  # If True, do NOT return this SAP

    @property
    def critical_issues(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.CRITICAL]

    @property
    def high_issues(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.HIGH]

    def summary(self) -> str:
        """Get human-readable summary"""
        if self.valid:
            return f"✓ VALID (score: {self.score:.1f}%)"
        else:
            return f"✗ INVALID - {len(self.critical_issues)} critical, {len(self.high_issues)} high issues (score: {self.score:.1f}%)"


class HardValidator:
    """
    Validates generated SAP against extracted protocol facts.

    BLOCKS output if:
    - Drug name doesn't match
    - Sample size is wrong
    - Number of arms doesn't match
    - Contamination from other protocols detected
    - Wrong NCT ID
    """

    # Known contaminants from RAG examples
    KNOWN_CONTAMINANTS = {
        'etrolizumab': 'Roche UC study',
        'vedolizumab': 'Entyvio study',
        'ustekinumab': 'Stelara study',
        'adalimumab': 'Humira study',
        'infliximab': 'Remicade study',
        'pembrolizumab': 'Keytruda study',
        'nivolumab': 'Opdivo study',
    }

    def __init__(self, strict_mode: bool = True):
        """
        Initialize validator.

        Args:
            strict_mode: If True, block on any critical issue.
                        If False, allow output with warnings.
        """
        self.strict_mode = strict_mode

    def validate(self, sap_text: str, facts: ProtocolFacts) -> ValidationResult:
        """
        Validate SAP against protocol facts.

        Args:
            sap_text: Generated SAP text
            facts: Extracted protocol facts

        Returns:
            ValidationResult with pass/fail and issues
        """
        issues = []
        checks_passed = 0
        total_checks = 0

        # 1. CRITICAL: Drug name must be present
        if facts.drug_name:
            total_checks += 1
            if self._check_drug_name(sap_text, facts.drug_name):
                checks_passed += 1
            else:
                issues.append(ValidationIssue(
                    field="drug_name",
                    expected=facts.drug_name,
                    found=self._find_drug_in_sap(sap_text),
                    severity=ValidationSeverity.CRITICAL,
                    message=f"Drug name '{facts.drug_name}' not found in SAP"
                ))

        # 2. CRITICAL: Sample size must be correct
        if facts.sample_size.total_n > 0:
            total_checks += 1
            if self._check_sample_size(sap_text, facts.sample_size.total_n):
                checks_passed += 1
            else:
                found_size = self._find_sample_size_in_sap(sap_text)
                issues.append(ValidationIssue(
                    field="sample_size",
                    expected=facts.sample_size.total_n,
                    found=found_size,
                    severity=ValidationSeverity.CRITICAL,
                    message=f"Sample size should be {facts.sample_size.total_n}, found {found_size}"
                ))

        # 3. CRITICAL: Check for contamination
        total_checks += 1
        contamination = self._check_contamination(sap_text, facts)
        if not contamination:
            checks_passed += 1
        else:
            for drug, source in contamination:
                issues.append(ValidationIssue(
                    field="contamination",
                    expected="No foreign drugs",
                    found=drug,
                    severity=ValidationSeverity.CRITICAL,
                    message=f"Contamination detected: '{drug}' from {source}"
                ))

        # 4. HIGH: Number of arms must match
        if facts.num_arms > 0:
            total_checks += 1
            if self._check_num_arms(sap_text, facts.num_arms):
                checks_passed += 1
            else:
                issues.append(ValidationIssue(
                    field="num_arms",
                    expected=facts.num_arms,
                    found=self._find_num_arms_in_sap(sap_text),
                    severity=ValidationSeverity.HIGH,
                    message=f"Expected {facts.num_arms} arms"
                ))

        # 5. HIGH: Randomization ratio
        if facts.randomization_ratio:
            total_checks += 1
            if facts.randomization_ratio in sap_text:
                checks_passed += 1
            else:
                issues.append(ValidationIssue(
                    field="randomization_ratio",
                    expected=facts.randomization_ratio,
                    found=self._find_ratio_in_sap(sap_text),
                    severity=ValidationSeverity.HIGH,
                    message=f"Randomization ratio '{facts.randomization_ratio}' not found"
                ))

        # 6. HIGH: Route of administration
        if facts.route_of_administration != RouteOfAdministration.OTHER:
            total_checks += 1
            if self._check_route(sap_text, facts.route_of_administration):
                checks_passed += 1
            else:
                issues.append(ValidationIssue(
                    field="route",
                    expected=facts.route_of_administration.value,
                    found=self._find_route_in_sap(sap_text),
                    severity=ValidationSeverity.HIGH,
                    message=f"Route should be {facts.route_of_administration.value}"
                ))

        # 7. MEDIUM: NCT ID present
        if facts.nct_id:
            total_checks += 1
            if facts.nct_id in sap_text:
                checks_passed += 1
            else:
                issues.append(ValidationIssue(
                    field="nct_id",
                    expected=facts.nct_id,
                    found="Not found",
                    severity=ValidationSeverity.MEDIUM,
                    message=f"NCT ID '{facts.nct_id}' not found in SAP"
                ))

        # 8. MEDIUM: Alpha specification
        if facts.alpha.sidedness:
            total_checks += 1
            if self._check_alpha(sap_text, facts.alpha):
                checks_passed += 1
            else:
                issues.append(ValidationIssue(
                    field="alpha",
                    expected=f"{facts.alpha.sidedness} {facts.alpha.primary_alpha}",
                    found="Mismatch or not found",
                    severity=ValidationSeverity.MEDIUM,
                    message=f"Alpha should be {facts.alpha.sidedness} at {facts.alpha.primary_alpha}"
                ))

        # 9. LOW: Phase mentioned
        if facts.phase.value != "Unknown":
            total_checks += 1
            if facts.phase.value.lower() in sap_text.lower():
                checks_passed += 1
            else:
                issues.append(ValidationIssue(
                    field="phase",
                    expected=facts.phase.value,
                    found="Not found",
                    severity=ValidationSeverity.LOW,
                    message=f"Phase '{facts.phase.value}' not found in SAP"
                ))

        # Calculate score
        score = (checks_passed / total_checks * 100) if total_checks > 0 else 0

        # Determine if we should block
        has_critical = any(i.severity == ValidationSeverity.CRITICAL for i in issues)
        has_high = any(i.severity == ValidationSeverity.HIGH for i in issues)

        block_output = False
        if self.strict_mode:
            block_output = has_critical or has_high
        else:
            block_output = has_critical

        valid = len(issues) == 0

        return ValidationResult(
            valid=valid,
            issues=issues,
            score=score,
            block_output=block_output
        )

    def _check_drug_name(self, sap_text: str, drug_name: str) -> bool:
        """Check if drug name appears in SAP"""
        # Handle case insensitivity and common variations
        pattern = rf'\b{re.escape(drug_name)}\b'
        return bool(re.search(pattern, sap_text, re.IGNORECASE))

    def _check_sample_size(self, sap_text: str, expected_n: int) -> bool:
        """Check if correct sample size appears in SAP"""
        # Look for the number in sample size context
        patterns = [
            rf'\b{expected_n}\s+(?:patients?|subjects?|participants?)',
            rf'N\s*[=:]\s*{expected_n}\b',
            rf'sample\s+size[:\s]+{expected_n}\b',
        ]
        for pattern in patterns:
            if re.search(pattern, sap_text, re.IGNORECASE):
                return True
        return False

    def _check_contamination(self, sap_text: str, facts: ProtocolFacts) -> List[Tuple[str, str]]:
        """Check for contamination from other protocols"""
        contamination = []

        # Get all valid drug names from current protocol
        valid_drugs = set(d.lower() for d in facts.drug_names_all)
        if facts.drug_name:
            valid_drugs.add(facts.drug_name.lower())

        # Check for known contaminants
        for drug, source in self.KNOWN_CONTAMINANTS.items():
            if drug.lower() not in valid_drugs:
                if re.search(rf'\b{drug}\b', sap_text, re.IGNORECASE):
                    contamination.append((drug, source))

        # Check for wrong sample sizes (>20% different from expected)
        if facts.sample_size.total_n > 0:
            found_sizes = self._find_all_sample_sizes(sap_text)
            for size in found_sizes:
                if size > 50:  # Only check substantial numbers
                    diff_pct = abs(size - facts.sample_size.total_n) / facts.sample_size.total_n
                    if diff_pct > 0.5:  # More than 50% different
                        # Check if it's a per-arm size
                        if facts.num_arms > 0:
                            per_arm = facts.sample_size.total_n // facts.num_arms
                            if abs(size - per_arm) > per_arm * 0.2:
                                contamination.append((f"sample_size_{size}", "Wrong study"))

        return contamination

    def _check_num_arms(self, sap_text: str, expected_arms: int) -> bool:
        """Check if correct number of arms is mentioned"""
        # Look for arm count or ratio
        ratio_pattern = r'(\d+(?::\d+)+)'
        match = re.search(ratio_pattern, sap_text)
        if match:
            found_arms = len(match.group(1).split(':'))
            if found_arms == expected_arms:
                return True

        # Look for explicit arm count
        arm_patterns = [
            rf'\b{expected_arms}\s+(?:treatment\s+)?(?:arms?|groups?)',
            rf'(?:three|3)\s+(?:treatment\s+)?(?:arms?|groups?)' if expected_arms == 3 else None,
            rf'(?:two|2)\s+(?:treatment\s+)?(?:arms?|groups?)' if expected_arms == 2 else None,
        ]
        for pattern in arm_patterns:
            if pattern and re.search(pattern, sap_text, re.IGNORECASE):
                return True

        return False

    def _check_route(self, sap_text: str, expected_route: RouteOfAdministration) -> bool:
        """Check if correct route of administration is mentioned"""
        route_patterns = {
            RouteOfAdministration.IV: r'\b(iv|intravenous|iv\s+infusion)\b',
            RouteOfAdministration.SC: r'\b(sc|subcutaneous|subcutaneously)\b',
            RouteOfAdministration.IM: r'\b(im|intramuscular)\b',
            RouteOfAdministration.ORAL: r'\b(oral|orally|tablet|capsule)\b',
        }
        pattern = route_patterns.get(expected_route)
        if pattern:
            return bool(re.search(pattern, sap_text, re.IGNORECASE))
        return True  # Can't validate OTHER

    def _check_alpha(self, sap_text: str, alpha_spec) -> bool:
        """Check if alpha specification is correct"""
        # Check sidedness
        if alpha_spec.sidedness == "one-sided":
            if not re.search(r'one[- ]sided|1[- ]sided', sap_text, re.IGNORECASE):
                return False
        elif alpha_spec.sidedness == "two-sided":
            if not re.search(r'two[- ]sided|2[- ]sided', sap_text, re.IGNORECASE):
                return False

        # Check alpha value
        alpha_val = alpha_spec.primary_alpha
        if alpha_val == 0.05:
            if not re.search(r'0\.05|5\s*%|alpha\s*=\s*0\.05', sap_text, re.IGNORECASE):
                return False

        return True

    def _find_drug_in_sap(self, sap_text: str) -> str:
        """Find what drug name appears in SAP"""
        # Look for drug patterns
        patterns = [
            r'\b([A-Z]{2,4}[-]?\d{5,8})\b',
            r'\b([A-Z]{2,3}\d{3,4})\b',
            r'\b([a-z]+(?:mab|nib|lib))\b',
        ]
        for pattern in patterns:
            match = re.search(pattern, sap_text)
            if match:
                return match.group(1)
        return "None found"

    def _find_sample_size_in_sap(self, sap_text: str) -> Optional[int]:
        """Find sample size mentioned in SAP"""
        patterns = [
            r'(\d+)\s+(?:patients?|subjects?|participants?)',
            r'N\s*[=:]\s*(\d+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, sap_text, re.IGNORECASE)
            for match in matches:
                n = int(match)
                if n > 10:  # Likely a sample size
                    return n
        return None

    def _find_all_sample_sizes(self, sap_text: str) -> List[int]:
        """Find all sample sizes mentioned in SAP"""
        sizes = set()
        patterns = [
            r'(\d+)\s+(?:patients?|subjects?|participants?)',
            r'N\s*[=:]\s*(\d+)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, sap_text, re.IGNORECASE)
            for match in matches:
                n = int(match)
                if n > 10:
                    sizes.add(n)
        return list(sizes)

    def _find_num_arms_in_sap(self, sap_text: str) -> Optional[int]:
        """Find number of arms mentioned in SAP"""
        ratio_match = re.search(r'(\d+(?::\d+)+)', sap_text)
        if ratio_match:
            return len(ratio_match.group(1).split(':'))

        arm_match = re.search(r'(\d+)\s+(?:treatment\s+)?(?:arms?|groups?)', sap_text, re.IGNORECASE)
        if arm_match:
            return int(arm_match.group(1))

        return None

    def _find_ratio_in_sap(self, sap_text: str) -> Optional[str]:
        """Find randomization ratio in SAP"""
        match = re.search(r'(\d+:\d+(?::\d+)*)', sap_text)
        return match.group(1) if match else None

    def _find_route_in_sap(self, sap_text: str) -> Optional[str]:
        """Find route of administration in SAP"""
        routes = [
            (r'\b(intravenous|iv)\b', 'IV'),
            (r'\b(subcutaneous|sc)\b', 'SC'),
            (r'\b(intramuscular|im)\b', 'IM'),
            (r'\b(oral|orally)\b', 'Oral'),
        ]
        for pattern, name in routes:
            if re.search(pattern, sap_text, re.IGNORECASE):
                return name
        return None


def validate_sap(sap_text: str, facts: ProtocolFacts, strict: bool = True) -> ValidationResult:
    """Convenience function to validate SAP"""
    validator = HardValidator(strict_mode=strict)
    return validator.validate(sap_text, facts)
