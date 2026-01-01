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

# Import configuration
try:
    from ..config import KNOWN_CONTAMINANTS, REQUIRED_SAP_SECTIONS
except ImportError:
    # Fallback for direct script execution
    KNOWN_CONTAMINANTS = {
        'etrolizumab': 'Roche UC study',
        'vedolizumab': 'Entyvio study',
        'ustekinumab': 'Stelara study',
        'adalimumab': 'Humira study',
        'infliximab': 'Remicade study',
    }
    REQUIRED_SAP_SECTIONS = {}


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

    # Use configuration for known contaminants
    KNOWN_CONTAMINANTS = KNOWN_CONTAMINANTS

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

        # 10. CRITICAL: Check for empty sections
        empty_sections = self._check_empty_sections(sap_text)
        if empty_sections:
            total_checks += 1
            for section in empty_sections:
                issues.append(ValidationIssue(
                    field=f"section_{section}",
                    expected="Non-empty section content",
                    found="Empty or missing",
                    severity=ValidationSeverity.CRITICAL,
                    message=f"Required section '{section}' is empty or missing"
                ))
        else:
            total_checks += 1
            checks_passed += 1

        # 11. HIGH: Check for required SAP structure elements
        structure_issues = self._check_sap_structure(sap_text)
        total_checks += 1
        if not structure_issues:
            checks_passed += 1
        else:
            for element in structure_issues:
                issues.append(ValidationIssue(
                    field=f"structure_{element}",
                    expected=f"Section '{element}' content",
                    found="Missing or inadequate",
                    severity=ValidationSeverity.HIGH,
                    message=f"SAP structure issue: '{element}' section content is inadequate"
                ))

        # 12. MEDIUM: Check stratification factors mentioned
        if facts.stratification_factors:
            total_checks += 1
            strat_found = False
            for factor in facts.stratification_factors:
                # Check if factor or key words from factor are in SAP
                factor_words = [w for w in factor.lower().split() if len(w) > 3]
                for word in factor_words:
                    if word in sap_text.lower():
                        strat_found = True
                        break
            if strat_found:
                checks_passed += 1
            else:
                issues.append(ValidationIssue(
                    field="stratification_factors",
                    expected=", ".join(facts.stratification_factors),
                    found="Not mentioned",
                    severity=ValidationSeverity.MEDIUM,
                    message=f"Stratification factors not found in SAP"
                ))

        # 13. HIGH: Primary endpoint definition present
        if facts.primary_endpoint:
            total_checks += 1
            endpoint_def = facts.primary_endpoint.definition if hasattr(facts.primary_endpoint, 'definition') else str(facts.primary_endpoint)
            # Check if key words from endpoint definition are in SAP
            endpoint_keywords = [w.lower() for w in endpoint_def.split() if len(w) > 3]
            keywords_found = sum(1 for kw in endpoint_keywords[:5] if kw in sap_text.lower())
            if keywords_found >= 2:  # At least 2 key words should match
                checks_passed += 1
            else:
                issues.append(ValidationIssue(
                    field="primary_endpoint",
                    expected=endpoint_def[:100],
                    found=self._find_primary_endpoint_in_sap(sap_text),
                    severity=ValidationSeverity.HIGH,
                    message=f"Primary endpoint definition not adequately described in SAP"
                ))

        # 14. MEDIUM: Primary timepoint mentioned
        if facts.primary_endpoint and hasattr(facts.primary_endpoint, 'timepoint') and facts.primary_endpoint.timepoint:
            total_checks += 1
            timepoint = facts.primary_endpoint.timepoint.lower()
            if timepoint in sap_text.lower() or self._check_timepoint_present(sap_text, timepoint):
                checks_passed += 1
            else:
                issues.append(ValidationIssue(
                    field="primary_timepoint",
                    expected=facts.primary_endpoint.timepoint,
                    found="Not found or different",
                    severity=ValidationSeverity.MEDIUM,
                    message=f"Primary timepoint '{facts.primary_endpoint.timepoint}' not found in SAP"
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

    def validate_against_protocol(self, sap_text: str, protocol_text: str) -> ValidationResult:
        """
        Validate SAP against ORIGINAL protocol text (not extracted facts).

        This is more robust than validate() because it re-extracts facts
        from the protocol, avoiding issues where initial extraction was wrong.

        Args:
            sap_text: Generated SAP text
            protocol_text: ORIGINAL protocol document text

        Returns:
            ValidationResult with pass/fail and issues
        """
        # Import extractor here to avoid circular imports
        try:
            from .structured_extractor import StructuredFactExtractor
        except ImportError:
            from structured_extractor import StructuredFactExtractor

        # Fresh extraction from original protocol
        extractor = StructuredFactExtractor()
        fresh_facts = extractor.extract_all(protocol_text)

        # Also do direct pattern matching on protocol for critical facts
        issues = []
        checks_passed = 0
        total_checks = 0

        # 1. CRITICAL: Drug name from protocol must be in SAP
        # Do independent extraction to double-check
        protocol_drug = self._extract_drug_from_text(protocol_text)
        sap_drug = self._find_drug_in_sap(sap_text)

        if protocol_drug:
            total_checks += 1
            if self._check_drug_name(sap_text, protocol_drug):
                checks_passed += 1
            else:
                issues.append(ValidationIssue(
                    field="drug_name",
                    expected=protocol_drug,
                    found=sap_drug or "Not found",
                    severity=ValidationSeverity.CRITICAL,
                    message=f"PROTOCOL says drug is '{protocol_drug}' but SAP has '{sap_drug}'"
                ))

        # 2. CRITICAL: Sample size from protocol must be in SAP
        protocol_n = self._extract_sample_size_from_text(protocol_text)
        sap_n = self._find_sample_size_in_sap(sap_text)

        if protocol_n and protocol_n > 0:
            total_checks += 1
            if self._check_sample_size(sap_text, protocol_n):
                checks_passed += 1
            else:
                issues.append(ValidationIssue(
                    field="sample_size",
                    expected=protocol_n,
                    found=sap_n or "Not found",
                    severity=ValidationSeverity.CRITICAL,
                    message=f"PROTOCOL says N={protocol_n} but SAP has N={sap_n}"
                ))

        # 3. CRITICAL: NCT ID from protocol must be in SAP
        protocol_nct = self._extract_nct_from_text(protocol_text)
        if protocol_nct:
            total_checks += 1
            if protocol_nct.upper() in sap_text.upper():
                checks_passed += 1
            else:
                issues.append(ValidationIssue(
                    field="nct_id",
                    expected=protocol_nct,
                    found="Not found",
                    severity=ValidationSeverity.HIGH,
                    message=f"PROTOCOL NCT ID '{protocol_nct}' not found in SAP"
                ))

        # Run standard validation with fresh facts
        standard_result = self.validate(sap_text, fresh_facts)

        # Merge issues (avoid duplicates)
        existing_fields = {i.field for i in issues}
        for issue in standard_result.issues:
            if issue.field not in existing_fields:
                issues.append(issue)

        # Calculate score
        score = (checks_passed / max(total_checks, 1)) * 100 if total_checks > 0 else standard_result.score

        # Determine if we should block
        has_critical = any(i.severity == ValidationSeverity.CRITICAL for i in issues)
        has_high = any(i.severity == ValidationSeverity.HIGH for i in issues)

        if self.strict_mode:
            block_output = has_critical or has_high
        else:
            block_output = has_critical

        return ValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            score=score,
            block_output=block_output
        )

    def _extract_drug_from_text(self, text: str) -> Optional[str]:
        """Extract drug name directly from text"""
        # INN suffixes for drug names
        inn_pattern = r'\b([A-Za-z]{4,}(?:mab|nib|lib|mod|vir|pril|statin|sartan|olol|prazole|tinib|ciclib|parib|platin|taxel))\b'
        matches = re.findall(inn_pattern, text, re.IGNORECASE)
        if matches:
            # Return longest match (most specific)
            return max(matches, key=len)
        return None

    def _extract_sample_size_from_text(self, text: str) -> Optional[int]:
        """Extract sample size directly from text"""
        patterns = [
            r'(\d+)\s+(?:patients?|subjects?|participants?)\s+(?:will\s+be\s+)?randomized',
            r'[Aa]\s+total\s+of\s+(\d+)\s+(?:patients?|subjects?|participants?)',
            r'[Nn]\s*[=:]\s*(\d+)',
            r'sample\s+size[:\s]+(\d+)',
            r'enroll\s+(?:up\s+to\s+)?(\d+)\s+(?:patients?|subjects?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                n = int(match.group(1))
                if 10 <= n <= 100000:  # Reasonable sample size
                    return n
        return None

    def _extract_nct_from_text(self, text: str) -> Optional[str]:
        """Extract NCT ID directly from text"""
        patterns = [
            r'NCT\d{8}',
            r'NCT[-\s]?\d{8}',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                digits = re.sub(r'[^\d]', '', match.group(0))
                if len(digits) == 8:
                    return f"NCT{digits}"
        return None

    def _check_drug_name(self, sap_text: str, drug_name: str) -> bool:
        """Check if drug name appears in SAP"""
        try:
            if not sap_text or not drug_name:
                return False
            # Handle case insensitivity and common variations
            pattern = rf'\b{re.escape(drug_name)}\b'
            return bool(re.search(pattern, sap_text, re.IGNORECASE))
        except (re.error, TypeError) as e:
            print(f"[WARNING] Regex error in _check_drug_name: {e}")
            return False

    def _check_sample_size(self, sap_text: str, expected_n: int) -> bool:
        """Check if correct sample size appears in SAP"""
        try:
            if not sap_text or not expected_n or expected_n <= 0:
                return False
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
        except (re.error, TypeError) as e:
            print(f"[WARNING] Regex error in _check_sample_size: {e}")
            return False

    def _check_contamination(self, sap_text: str, facts: ProtocolFacts) -> List[Tuple[str, str]]:
        """Check for contamination from other protocols"""
        contamination = []

        try:
            if not sap_text or not facts:
                return contamination

            # Get all valid drug names from current protocol - handle multiple formats
            valid_drugs = set()
            if hasattr(facts, 'drug_names_all') and facts.drug_names_all:
                valid_drugs = set(d.lower() for d in facts.drug_names_all)
            if hasattr(facts, 'drug_name') and facts.drug_name:
                drug_name = facts.drug_name
                # Handle CitedValue format
                if hasattr(drug_name, 'value'):
                    drug_name = drug_name.value
                if drug_name:
                    valid_drugs.add(drug_name.lower())

            # Check for known contaminants
            for drug, source in self.KNOWN_CONTAMINANTS.items():
                if drug.lower() not in valid_drugs:
                    try:
                        if re.search(rf'\b{re.escape(drug)}\b', sap_text, re.IGNORECASE):
                            contamination.append((drug, source))
                    except re.error:
                        pass  # Skip invalid pattern

            # Check for wrong sample sizes (>50% different from expected)
            total_n = 0
            if hasattr(facts, 'sample_size') and hasattr(facts.sample_size, 'total_n'):
                total_n = facts.sample_size.total_n or 0
            elif hasattr(facts, 'total_n'):
                total_n = facts.total_n if isinstance(facts.total_n, int) else 0

            if total_n > 0:
                found_sizes = self._find_all_sample_sizes(sap_text)
                num_arms = getattr(facts, 'num_arms', 0)
                if hasattr(num_arms, 'value'):
                    num_arms = num_arms.value or 0

                for size in found_sizes:
                    if size > 50:  # Only check substantial numbers
                        diff_pct = abs(size - total_n) / total_n
                        if diff_pct > 0.5:  # More than 50% different
                            # Check if it's a per-arm size
                            if num_arms > 0:
                                per_arm = total_n // num_arms
                                if per_arm > 0 and abs(size - per_arm) > per_arm * 0.2:
                                    contamination.append((f"sample_size_{size}", "Wrong study"))

        except Exception as e:
            print(f"[WARNING] Error in _check_contamination: {e}")

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
        # Biomarker filter - CD137, CD19, CD20, etc. are NOT drugs
        biomarker_pattern = re.compile(r'^CD\d{1,3}$', re.IGNORECASE)

        for pattern in patterns:
            match = re.search(pattern, sap_text)
            if match:
                candidate = match.group(1)
                # Skip biomarkers
                if not biomarker_pattern.match(candidate):
                    return candidate
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

    def _find_primary_endpoint_in_sap(self, sap_text: str) -> str:
        """Find primary endpoint mentioned in SAP"""
        patterns = [
            r'(?:primary\s+endpoint)[:\s]+([^\n.]+)',
            r'(?:primary\s+efficacy\s+endpoint)[:\s]+([^\n.]+)',
            r'(?:primary\s+outcome)[:\s]+([^\n.]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, sap_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:100]
        return "Not found"

    def _check_timepoint_present(self, sap_text: str, expected_timepoint: str) -> bool:
        """Check if a timepoint (e.g., 'Week 12') is present in SAP"""
        # Extract week number from expected timepoint
        week_match = re.search(r'week\s*(\d+)', expected_timepoint, re.IGNORECASE)
        if week_match:
            week_num = week_match.group(1)
            # Check various formats: Week 12, Week-12, W12, at 12 weeks
            patterns = [
                rf'week\s*{week_num}\b',
                rf'w{week_num}\b',
                rf'{week_num}\s*weeks?\b',
                rf'at\s+{week_num}\s*weeks?\b',
            ]
            for pattern in patterns:
                if re.search(pattern, sap_text, re.IGNORECASE):
                    return True
        return False

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

    def _check_empty_sections(self, sap_text: str) -> List[str]:
        """
        Check for empty or missing required SAP sections.
        Returns list of section names that are empty or missing.
        """
        empty_sections = []

        # Required sections and their expected headers/markers (more flexible patterns)
        # Each entry: name -> (header patterns, content patterns that indicate the section exists)
        required_sections = {
            'Introduction': (
                [r'#+\s*\d*\.?\s*introduction', r'\bintroduction\b'],
                [r'statistical\s+analysis\s+plan', r'SAP\s+describes', r'study\s+overview']
            ),
            'Objectives': (
                [r'#+\s*\d*\.?\s*(?:objectives|estimands)', r'\bobjectives?\b.*\bestimand'],
                [r'primary\s+objective', r'estimand', r'treatment\s+effect']
            ),
            'Study Design': (
                [r'#+\s*\d*\.?\s*study\s*design', r'\bstudy\s+design\b'],
                [r'randomized', r'double[- ]blind', r'treatment\s+arms?', r'\d+:\d+']
            ),
            'Analysis Populations': (
                [r'#+\s*\d*\.?\s*(?:analysis\s*)?populations?', r'\bpopulations?\b'],
                [r'ITT\s+(?:population)?', r'FAS', r'PP\s+(?:population)?', r'safety\s+population']
            ),
            'Endpoints': (
                [r'#+\s*\d*\.?\s*endpoints?', r'\bendpoints?\b'],
                [r'primary\s+(?:efficacy\s+)?endpoint', r'secondary\s+endpoint']
            ),
            'Sample Size': (
                [r'#+\s*\d*\.?\s*sample\s*size', r'\bsample\s+size\b'],
                [r'\d+\s+patients?', r'power', r'alpha', r'N\s*[=:]']
            ),
            'Statistical Methods': (
                [r'#+\s*\d*\.?\s*statistical\s*(?:methods?|analysis)?', r'\bstatistical\s+(?:methods?|analysis)\b'],
                [r'logistic\s+regression', r'ANCOVA', r'MMRM', r'chi[- ]square', r'significance\s+level']
            ),
            'Missing Data': (
                [r'#+\s*\d*\.?\s*missing\s*data', r'\bmissing\s+data\b'],
                [r'imputation', r'non[- ]responder', r'LOCF', r'MAR', r'MCAR']
            ),
            'Safety Analysis': (
                [r'#+\s*\d*\.?\s*safety', r'\bsafety\s+analysis\b'],
                [r'adverse\s+events?', r'AE', r'TEAE', r'MedDRA', r'SOC', r'laboratory']
            ),
        }

        for section_name, (header_patterns, content_patterns) in required_sections.items():
            section_found = False

            # First check if any header pattern matches
            for pattern in header_patterns:
                if re.search(pattern, sap_text, re.IGNORECASE):
                    section_found = True
                    break

            # If header not found, check if content patterns indicate section exists
            if not section_found:
                content_matches = sum(1 for p in content_patterns if re.search(p, sap_text, re.I))
                # If at least 2 content patterns match, section likely exists
                if content_matches >= 2:
                    section_found = True

            if not section_found:
                empty_sections.append(section_name)

        return empty_sections

    def _check_sap_structure(self, sap_text: str) -> List[str]:
        """
        Check for structural issues in SAP.
        Returns list of structural elements that are missing or inadequate.
        """
        issues = []

        # Check for minimal required content
        min_requirements = {
            'primary_endpoint_definition': (
                r'primary\s+(?:efficacy\s+)?endpoint[:\s]+\w{10,}',
                'Primary endpoint definition is missing or too short'
            ),
            'population_definitions': (
                r'(?:ITT|FAS|PP|Safety)\s+(?:population|set)[:\s]+\w{10,}',
                'Population definitions are missing or too short'
            ),
            'statistical_method': (
                r'(?:logistic\s+regression|ANCOVA|MMRM|chi[- ]square|t[- ]test|cox|kaplan)',
                'Statistical analysis method not specified'
            ),
            'alpha_level': (
                r'(?:alpha|significance\s+level)[:\s]*(?:0\.0\d+|\d+\s*%)',
                'Alpha/significance level not specified'
            ),
        }

        for element, (pattern, message) in min_requirements.items():
            if not re.search(pattern, sap_text, re.IGNORECASE):
                issues.append(element)

        return issues


def validate_sap(sap_text: str, facts: ProtocolFacts, strict: bool = True) -> ValidationResult:
    """Convenience function to validate SAP"""
    validator = HardValidator(strict_mode=strict)
    return validator.validate(sap_text, facts)
