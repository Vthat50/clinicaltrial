"""
CDISC Controlled Terminology Validator
Validates ADaM/SDTM datasets and code against CDISC CT
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from .terminology_service import get_terminology_service, CDISCTerminologyService
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """CT validation issue"""
    severity: str  # error, warning, info
    variable: str
    value: str
    expected_codelist: str
    message: str
    line_number: Optional[int] = None


class ValidationSeverity(Enum):
    ERROR = "error"      # Invalid CT value
    WARNING = "warning"  # Valid but deprecated or unexpected
    INFO = "info"        # Informational message


class CDISCCTValidator:
    """Validates data against CDISC CT"""

    def __init__(self, terminology_service: CDISCTerminologyService = None):
        self.terminology_service = terminology_service or get_terminology_service()

    def validate_dataset(
        self,
        dataset: Dict[str, List],
        dataset_name: str,
        ct_version: str = None
    ) -> List[ValidationIssue]:
        """
        Validate entire dataset against CT.

        Args:
            dataset: Dict of column_name -> list of values
            dataset_name: "ADSL", "ADTTE", etc.
            ct_version: CT version to validate against

        Returns:
            List of validation issues
        """
        issues = []

        # Get variables to validate for this dataset
        variables_to_check = self._get_ct_variables_for_dataset(dataset_name)

        for var_name in variables_to_check:
            if var_name in dataset:
                var_issues = self.validate_variable(
                    var_name=var_name,
                    values=dataset[var_name],
                    dataset_name=dataset_name,
                    ct_version=ct_version
                )
                issues.extend(var_issues)

        return issues

    def validate_variable(
        self,
        var_name: str,
        values: List[str],
        dataset_name: str = None,
        ct_version: str = None
    ) -> List[ValidationIssue]:
        """
        Validate variable values against appropriate codelist.

        Args:
            var_name: Variable name (e.g., "SEX", "PARAMCD")
            values: List of values to validate
            dataset_name: Context dataset
            ct_version: CT version

        Returns:
            List of validation issues
        """
        issues = []

        # Get appropriate codelist
        codelist = self.terminology_service.get_codelist_for_variable(
            var_name,
            domain=dataset_name,
            version=ct_version
        )

        if not codelist:
            # Variable doesn't have a CT codelist
            return issues

        # Build set of valid values
        valid_values = {item.submission_value for item in codelist.items}

        # Check each value
        for idx, value in enumerate(values):
            if value and value not in valid_values:
                # Check if extensible list
                if codelist.extensible:
                    severity = ValidationSeverity.WARNING
                    message = (f"Value '{value}' not in standard codelist '{codelist.name}' "
                              f"(extensible list - sponsor-defined values allowed)")
                else:
                    severity = ValidationSeverity.ERROR
                    message = (f"Invalid value '{value}' for {var_name}. "
                              f"Must be one of: {', '.join(sorted(valid_values))}")

                issues.append(ValidationIssue(
                    severity=severity.value,
                    variable=var_name,
                    value=value,
                    expected_codelist=codelist.name,
                    message=message,
                    line_number=idx + 1
                ))

        return issues

    def validate_paramcd(
        self,
        paramcd: str,
        param: str,
        ct_version: str = None
    ) -> List[ValidationIssue]:
        """
        Validate PARAMCD/PARAM pair.

        Args:
            paramcd: Parameter code (e.g., "OS")
            param: Parameter decode (e.g., "Overall Survival")
            ct_version: CT version

        Returns:
            List of validation issues
        """
        issues = []

        # Get PARAMCD codelist
        codelist = self.terminology_service.get_codelist("PARAMCD", ct_version)
        if not codelist:
            return issues

        # Find matching item
        matching_items = [
            item for item in codelist.items
            if item.submission_value == paramcd
        ]

        if not matching_items:
            # Check if extensible
            if codelist.extensible:
                issues.append(ValidationIssue(
                    severity="info",
                    variable="PARAMCD",
                    value=paramcd,
                    expected_codelist="PARAMCD",
                    message=f"Sponsor-defined PARAMCD '{paramcd}' (not in standard CT)"
                ))
            else:
                issues.append(ValidationIssue(
                    severity="error",
                    variable="PARAMCD",
                    value=paramcd,
                    expected_codelist="PARAMCD",
                    message=f"Invalid PARAMCD '{paramcd}' not found in CT"
                ))
        else:
            # Validate PARAM matches
            ct_param = matching_items[0].preferred_term
            if param != ct_param:
                issues.append(ValidationIssue(
                    severity="warning",
                    variable="PARAM",
                    value=param,
                    expected_codelist="PARAMCD",
                    message=f"PARAM '{param}' doesn't match CT preferred term '{ct_param}'"
                ))

        return issues

    def validate_codelist(
        self,
        codelist_name: str,
        ct_version: str = None
    ) -> List[ValidationIssue]:
        """
        Validate that a codelist exists in CT.

        Args:
            codelist_name: Codelist name
            ct_version: CT version

        Returns:
            List of validation issues
        """
        issues = []

        codelist = self.terminology_service.get_codelist(codelist_name, ct_version)

        if not codelist:
            issues.append(ValidationIssue(
                severity="error",
                variable="",
                value="",
                expected_codelist=codelist_name,
                message=f"Codelist '{codelist_name}' not found in CT version {ct_version or 'default'}"
            ))

        return issues

    def get_validation_summary(self, issues: List[ValidationIssue]) -> Dict[str, int]:
        """
        Get summary of validation issues by severity.

        Args:
            issues: List of validation issues

        Returns:
            Dict with counts by severity
        """
        summary = {
            "error": 0,
            "warning": 0,
            "info": 0,
            "total": len(issues)
        }

        for issue in issues:
            if issue.severity in summary:
                summary[issue.severity] += 1

        return summary

    def format_validation_report(
        self,
        issues: List[ValidationIssue],
        dataset_name: str = ""
    ) -> str:
        """
        Format validation issues as a report.

        Args:
            issues: List of validation issues
            dataset_name: Optional dataset name

        Returns:
            Formatted report string
        """
        if not issues:
            return f"✓ No validation issues found for {dataset_name}\n"

        summary = self.get_validation_summary(issues)

        lines = []
        lines.append("="*70)
        lines.append(f"CDISC CT Validation Report{' - ' + dataset_name if dataset_name else ''}")
        lines.append("="*70)
        lines.append("")
        lines.append("Summary:")
        lines.append(f"  Total Issues: {summary['total']}")
        lines.append(f"  Errors:       {summary['error']}")
        lines.append(f"  Warnings:     {summary['warning']}")
        lines.append(f"  Info:         {summary['info']}")
        lines.append("")
        lines.append("="*70)
        lines.append("")

        # Group by severity
        for severity in ["error", "warning", "info"]:
            severity_issues = [i for i in issues if i.severity == severity]
            if severity_issues:
                lines.append(f"{severity.upper()}S ({len(severity_issues)}):")
                lines.append("-"*70)

                for issue in severity_issues:
                    lines.append(f"\n  Variable: {issue.variable}")
                    lines.append(f"  Value: {issue.value}")
                    lines.append(f"  Codelist: {issue.expected_codelist}")
                    lines.append(f"  Message: {issue.message}")
                    if issue.line_number:
                        lines.append(f"  Line: {issue.line_number}")

                lines.append("")

        return "\n".join(lines)

    def _get_ct_variables_for_dataset(self, dataset_name: str) -> List[str]:
        """Get list of CT-controlled variables for a dataset"""
        CT_VARIABLES = {
            "ADSL": ["SEX", "RACE", "ETHNIC", "COUNTRY"],
            "ADTTE": ["PARAMCD", "PARAM"],
            "ADEFF": ["PARAMCD", "PARAM", "AVALC"],
            "ADRS": ["PARAMCD", "PARAM", "AVALC"],
            "ADAE": ["AESEV", "AESER", "AEREL", "AEACN", "AEOUT"],
            "AE": ["AESEV", "AESER", "AEREL", "AEACN", "AEOUT"],
            "DM": ["SEX", "RACE", "ETHNIC", "COUNTRY"],
        }
        return CT_VARIABLES.get(dataset_name, [])


def validate_dataset(
    dataset: Dict[str, List],
    dataset_name: str,
    terminology_service: CDISCTerminologyService = None,
    print_report: bool = False
) -> List[ValidationIssue]:
    """
    Convenience function to validate a dataset.

    Args:
        dataset: Dataset as dict of column -> values
        dataset_name: Dataset name
        terminology_service: Optional terminology service
        print_report: Whether to print formatted report

    Returns:
        List of validation issues
    """
    validator = CDISCCTValidator(terminology_service)
    issues = validator.validate_dataset(dataset, dataset_name)

    if print_report:
        report = validator.format_validation_report(issues, dataset_name)
        print(report)

    return issues
