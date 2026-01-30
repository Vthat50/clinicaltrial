"""SAP validation rules engine - checks required sections and terminology."""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from rich.console import Console
from rich.table import Table

console = Console()


class Severity(str, Enum):
    """Validation issue severity."""
    ERROR = "error"      # Must fix before submission
    WARNING = "warning"  # Should review
    INFO = "info"        # Suggestion


@dataclass
class ValidationIssue:
    """A validation issue found in the SAP."""
    section: str
    rule: str
    message: str
    severity: Severity
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Complete validation result."""
    nct_id: str
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    score: float = 0.0  # 0-100 quality score
    sections_present: list[str] = field(default_factory=list)
    sections_missing: list[str] = field(default_factory=list)

    def get_errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    def get_warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]


# Required SAP sections per ICH E9
REQUIRED_SECTIONS = [
    "objectives",
    "endpoints",
    "study_design",
    "sample_size",
    "analysis_populations",
    "statistical_methods",
    "efficacy_analyses",
    "safety_analyses",
]

# Recommended sections
RECOMMENDED_SECTIONS = [
    "interim_analyses",
    "missing_data",
    "multiplicity",
    "subgroup_analyses",
    "sensitivity_analyses",
]

# Required terminology patterns per section
TERMINOLOGY_RULES = {
    "sample_size": [
        (r"(?i)(power|1-beta)", "Must specify statistical power"),
        (r"(?i)(alpha|type\s*i\s*error|significance\s*level)", "Must specify alpha/significance level"),
        (r"(?i)(effect\s*size|treatment\s*difference|hazard\s*ratio)", "Must specify expected effect size"),
    ],
    "statistical_methods": [
        (r"(?i)(primary\s*analysis|primary\s*endpoint\s*analysis)", "Must describe primary analysis method"),
        (r"(?i)(confidence\s*interval|CI)", "Should specify confidence interval approach"),
        (r"(?i)(two-sided|one-sided)", "Should specify sidedness of tests"),
    ],
    "analysis_populations": [
        (r"(?i)(intent.to.treat|ITT)", "Must define ITT population"),
        (r"(?i)(safety\s*population|safety\s*analysis\s*set)", "Must define safety population"),
    ],
    "efficacy_analyses": [
        (r"(?i)(null\s*hypothesis|H0|H₀)", "Should state null hypothesis"),
        (r"(?i)(point\s*estimate|treatment\s*effect)", "Should describe point estimate"),
    ],
    "safety_analyses": [
        (r"(?i)(adverse\s*event|AE)", "Must describe AE analysis"),
        (r"(?i)(MedDRA|coding)", "Should specify AE coding dictionary"),
    ],
    "missing_data": [
        (r"(?i)(missing\s*data|missingness)", "Must address missing data"),
        (r"(?i)(imputation|LOCF|MMRM|MAR|MCAR|MNAR)", "Should specify missing data handling method"),
    ],
}

# Quality check patterns
QUALITY_PATTERNS = {
    "specific_numbers": r"\d+\.?\d*\s*%",  # Should have specific percentages
    "confidence_level": r"(?i)95\s*%\s*(?:CI|confidence)",
    "software_mentioned": r"(?i)(SAS|R\s+version|STATA|SPSS)",
    "model_specified": r"(?i)(ANCOVA|ANOVA|Cox|logistic|linear|mixed\s*model|MMRM)",
}


class SAPValidator:
    """Validate generated SAP against regulatory requirements."""

    def __init__(self):
        self.console = Console()

    def validate(self, sap_content: str, sections: dict[str, str], nct_id: str) -> ValidationResult:
        """Validate SAP content.

        Args:
            sap_content: Full SAP text
            sections: Dict of section_type -> content
            nct_id: Study NCT ID

        Returns:
            ValidationResult with issues and score
        """
        issues = []

        # Check required sections
        present = []
        missing = []
        for section in REQUIRED_SECTIONS:
            if section in sections and len(sections[section]) > 50:
                present.append(section)
            else:
                missing.append(section)
                issues.append(ValidationIssue(
                    section=section,
                    rule="required_section",
                    message=f"Required section '{section}' is missing or empty",
                    severity=Severity.ERROR,
                    suggestion=f"Add {section} section with appropriate content"
                ))

        # Check recommended sections
        for section in RECOMMENDED_SECTIONS:
            if section not in sections or len(sections.get(section, "")) < 50:
                issues.append(ValidationIssue(
                    section=section,
                    rule="recommended_section",
                    message=f"Recommended section '{section}' is missing",
                    severity=Severity.WARNING,
                    suggestion=f"Consider adding {section} section"
                ))

        # Check terminology per section
        for section_type, rules in TERMINOLOGY_RULES.items():
            content = sections.get(section_type, "")
            for pattern, message in rules:
                if not re.search(pattern, content):
                    issues.append(ValidationIssue(
                        section=section_type,
                        rule="terminology",
                        message=message,
                        severity=Severity.WARNING,
                        suggestion=f"Review {section_type} section for completeness"
                    ))

        # Quality checks on full content
        quality_score = self._calculate_quality_score(sap_content)

        # Check for placeholder text
        if re.search(r"\[.*not\s*found.*\]|\[.*N/A.*\]|\[TBD\]|\[TODO\]", sap_content, re.I):
            issues.append(ValidationIssue(
                section="general",
                rule="placeholder_text",
                message="SAP contains placeholder text that needs to be filled",
                severity=Severity.ERROR,
                suggestion="Replace all placeholder text with actual content"
            ))

        # Calculate overall score
        error_count = len([i for i in issues if i.severity == Severity.ERROR])
        warning_count = len([i for i in issues if i.severity == Severity.WARNING])

        base_score = 100
        score = base_score - (error_count * 15) - (warning_count * 5)
        score = max(0, min(100, score * (quality_score / 100)))

        is_valid = error_count == 0

        return ValidationResult(
            nct_id=nct_id,
            is_valid=is_valid,
            issues=issues,
            score=round(score, 1),
            sections_present=present,
            sections_missing=missing
        )

    def _calculate_quality_score(self, content: str) -> float:
        """Calculate quality score based on content patterns."""
        score = 50  # Base score

        # Check for specific numbers/percentages
        if re.search(QUALITY_PATTERNS["specific_numbers"], content):
            score += 15

        # Check for confidence intervals
        if re.search(QUALITY_PATTERNS["confidence_level"], content):
            score += 10

        # Check for software specification
        if re.search(QUALITY_PATTERNS["software_mentioned"], content):
            score += 10

        # Check for statistical models
        if re.search(QUALITY_PATTERNS["model_specified"], content):
            score += 15

        return min(100, score)

    def print_report(self, result: ValidationResult):
        """Print validation report to console."""
        self.console.print(f"\n[bold]Validation Report: {result.nct_id}[/bold]\n")

        # Summary
        status = "[green]VALID[/green]" if result.is_valid else "[red]INVALID[/red]"
        self.console.print(f"Status: {status}")
        self.console.print(f"Quality Score: {result.score}/100")
        self.console.print(f"Sections Present: {len(result.sections_present)}/{len(REQUIRED_SECTIONS)}")

        # Issues table
        if result.issues:
            table = Table(title="Validation Issues")
            table.add_column("Severity", style="bold")
            table.add_column("Section")
            table.add_column("Issue")
            table.add_column("Suggestion")

            for issue in sorted(result.issues, key=lambda x: x.severity.value):
                severity_style = {
                    Severity.ERROR: "red",
                    Severity.WARNING: "yellow",
                    Severity.INFO: "blue"
                }[issue.severity]

                table.add_row(
                    f"[{severity_style}]{issue.severity.value.upper()}[/{severity_style}]",
                    issue.section,
                    issue.message,
                    issue.suggestion or "-"
                )

            self.console.print(table)

        # Missing sections
        if result.sections_missing:
            self.console.print(f"\n[red]Missing required sections:[/red] {', '.join(result.sections_missing)}")

    def generate_qc_checklist(self, result: ValidationResult) -> str:
        """Generate human QC checklist markdown."""
        checklist = f"""# SAP Quality Control Checklist

## Study: {result.nct_id}
## Validation Score: {result.score}/100
## Status: {"PASS" if result.is_valid else "REQUIRES REVIEW"}

---

## Required Sections Checklist

"""
        for section in REQUIRED_SECTIONS:
            status = "✅" if section in result.sections_present else "❌"
            checklist += f"- [{status}] {section.replace('_', ' ').title()}\n"

        checklist += "\n## Issues Requiring Review\n\n"

        errors = result.get_errors()
        if errors:
            checklist += "### Errors (Must Fix)\n\n"
            for issue in errors:
                checklist += f"- [ ] **{issue.section}**: {issue.message}\n"
                if issue.suggestion:
                    checklist += f"  - Suggestion: {issue.suggestion}\n"

        warnings = result.get_warnings()
        if warnings:
            checklist += "\n### Warnings (Should Review)\n\n"
            for issue in warnings:
                checklist += f"- [ ] **{issue.section}**: {issue.message}\n"

        checklist += """
---

## Reviewer Sign-off

- [ ] All required sections present and complete
- [ ] Statistical methods appropriate for endpoints
- [ ] Sample size justification adequate
- [ ] Missing data handling specified
- [ ] Ready for regulatory submission

**Reviewer:** _________________  **Date:** _________________

"""
        return checklist
