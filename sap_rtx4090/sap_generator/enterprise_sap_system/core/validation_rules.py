#!/usr/bin/env python3
"""
Clinical Trial Validation Rules - Faithfulness Checks
======================================================
Validates extracted values against actual protocol text.
Catches hallucinations before they reach the SAP.
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class ValidationSeverity(Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    rule_id: str
    severity: ValidationSeverity
    field: str
    message: str
    suggestion: str = ""


@dataclass
class ValidationReport:
    is_valid: bool = True
    critical_issues: List[ValidationIssue] = field(default_factory=list)
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)

    def add_issue(self, issue: ValidationIssue):
        if issue.severity == ValidationSeverity.CRITICAL:
            self.critical_issues.append(issue)
            self.is_valid = False
        elif issue.severity == ValidationSeverity.ERROR:
            self.errors.append(issue)
        else:
            self.warnings.append(issue)

    def summary(self) -> str:
        return f"Valid: {self.is_valid} | Critical: {len(self.critical_issues)} | Errors: {len(self.errors)}"


class ClinicalTrialValidator:
    """Validates protocol extraction against source text."""

    def __init__(self, protocol_text: str = ""):
        self.protocol_text = protocol_text.lower()

    def validate(self, parsed_protocol: Any) -> ValidationReport:
        report = ValidationReport()
        data = self._to_dict(parsed_protocol) if hasattr(parsed_protocol, '__dict__') else parsed_protocol

        self._validate_route(data, report)
        self._validate_sample_size(data, report)
        self._validate_stratification(data, report)
        self._validate_therapeutic_area(data, report)

        return report

    def _to_dict(self, protocol: Any) -> Dict:
        data = {}
        if hasattr(protocol, 'arms'):
            data['arms'] = [{'name': a.name, 'route': a.route} for a in protocol.arms]
        if hasattr(protocol, 'sample_size') and protocol.sample_size:
            data['sample_size'] = {'total_n': protocol.sample_size.total_n}
        if hasattr(protocol, 'stratification_factors'):
            data['stratification_factors'] = protocol.stratification_factors or []
        if hasattr(protocol, 'therapeutic_area'):
            data['therapeutic_area'] = protocol.therapeutic_area
        return data

    def _validate_route(self, data: Dict, report: ValidationReport):
        """Check extracted route matches protocol text."""
        if not self.protocol_text:
            return

        # Find routes in protocol
        protocol_routes = set()
        if re.search(r'intra[\-\s]?venous|(?<!\w)iv(?!\w)|i\.v\.|infusion\s+over', self.protocol_text):
            protocol_routes.add('intravenous')
        if re.search(r'sub[\-\s]?cutaneous|(?<!\w)sc(?!\w)|s\.c\.', self.protocol_text):
            protocol_routes.add('subcutaneous')

        for arm in data.get('arms', []):
            route = (arm.get('route') or '').lower()
            if 'subcutaneous' in route and 'intravenous' in protocol_routes and 'subcutaneous' not in protocol_routes:
                report.add_issue(ValidationIssue(
                    rule_id="ROUTE_001",
                    severity=ValidationSeverity.CRITICAL,
                    field="route",
                    message=f"MISMATCH: Protocol says IV but extracted subcutaneous",
                    suggestion="Check protocol for route of administration"
                ))

    def _validate_sample_size(self, data: Dict, report: ValidationReport):
        """Check sample size matches enrollment statements."""
        if not self.protocol_text:
            return

        ss = data.get('sample_size', {})
        extracted_n = ss.get('total_n', 0)
        if not extracted_n:
            return

        # Find enrollment numbers in protocol
        patterns = [
            r'(\d+)\s*patients?\s*will\s*be\s*(?:enrolled|randomized)',
            r'total\s*of\s*(\d+)\s*patients',
        ]
        protocol_ns = []
        for p in patterns:
            for m in re.finditer(p, self.protocol_text):
                n = int(m.group(1))
                if 10 <= n <= 5000:
                    protocol_ns.append(n)

        if protocol_ns:
            expected = max(set(protocol_ns), key=protocol_ns.count)
            if extracted_n != expected and abs(extracted_n - expected) > 10:
                report.add_issue(ValidationIssue(
                    rule_id="SS_001",
                    severity=ValidationSeverity.CRITICAL,
                    field="sample_size",
                    message=f"MISMATCH: Extracted N={extracted_n} but protocol says N={expected}",
                    suggestion="Check enrollment statements in protocol"
                ))

    def _validate_stratification(self, data: Dict, report: ValidationReport):
        """Check for hallucinated stratification factors."""
        if not self.protocol_text:
            return

        hallucinated = ["disease severity", "prior biologic", "geographic region", "baseline severity"]
        for factor in data.get('stratification_factors', []):
            factor_lower = factor.lower()
            for h in hallucinated:
                if h in factor_lower and h not in self.protocol_text:
                    report.add_issue(ValidationIssue(
                        rule_id="STRAT_001",
                        severity=ValidationSeverity.CRITICAL,
                        field="stratification",
                        message=f"Likely hallucinated: '{factor}' not in protocol",
                        suggestion="Verify stratification factors in protocol"
                    ))

    def _validate_therapeutic_area(self, data: Dict, report: ValidationReport):
        """Detect cross-TA contamination (oncology terms in non-oncology)."""
        if not self.protocol_text:
            return

        # Detect TA
        is_oncology = any(t in self.protocol_text for t in ['cancer', 'tumor', 'carcinoma'])
        is_immunology = any(t in self.protocol_text for t in ['ulcerative colitis', 'crohn', 'rheumatoid'])

        if is_immunology and not is_oncology:
            oncology_terms = ['tumor assessment', 'recist', 'progression-free survival', 'target lesion']
            for factor in data.get('stratification_factors', []):
                for term in oncology_terms:
                    if term in factor.lower():
                        report.add_issue(ValidationIssue(
                            rule_id="TA_001",
                            severity=ValidationSeverity.CRITICAL,
                            field="therapeutic_area",
                            message=f"Cross-TA contamination: oncology term '{term}' in immunology trial",
                            suggestion="Remove oncology-specific terms"
                        ))


def create_validator(protocol_text: str = "") -> ClinicalTrialValidator:
    return ClinicalTrialValidator(protocol_text)
