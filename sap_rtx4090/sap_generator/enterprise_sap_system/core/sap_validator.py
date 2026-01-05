#!/usr/bin/env python3
"""
SAP Validator - Pre and post-generation validation rules
Prevents common errors and contradictions in SAP generation

Location: enterprise_sap_system/core/sap_validator.py
"""

from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Structured validation error"""
    severity: str  # 'CRITICAL', 'ERROR', 'WARNING'
    category: str  # 'extraction', 'logic', 'consistency', 'missing'
    message: str
    field: Optional[str] = None
    suggested_fix: Optional[str] = None


class SAPValidator:
    """
    Comprehensive SAP validation

    Pre-generation validation:
    - Checks extracted protocol facts for completeness
    - Validates logical consistency
    - Auto-fixes common errors

    Post-generation validation:
    - Checks generated SAP for contradictions
    - Validates against protocol facts
    - Detects placeholders and hallucinations
    """

    def __init__(self, strict_mode: bool = True):
        """
        Initialize validator

        Args:
            strict_mode: If True, raise errors for CRITICAL issues
        """
        self.strict_mode = strict_mode
        self.validation_rules = self._load_validation_rules()

    def validate_before_generation(self, protocol_facts) -> Dict[str, Any]:
        """
        Validate extracted protocol facts BEFORE SAP generation

        Args:
            protocol_facts: ExtractedProtocolFacts from sectioned_extractor

        Returns:
            Dict with keys: 'valid', 'errors', 'warnings', 'auto_fixes'
        """
        all_issues = []
        auto_fixes = []

        logger.info("[SAPValidator] Running pre-generation validation...")

        # Rule 1: Study design consistency
        all_issues.extend(self._validate_study_design(protocol_facts))

        # Rule 2: Population definitions
        all_issues.extend(self._validate_populations(protocol_facts))

        # Rule 3: Required fields
        all_issues.extend(self._validate_required_fields(protocol_facts))

        # Rule 4: Endpoint consistency
        all_issues.extend(self._validate_endpoints(protocol_facts))

        # Rule 5: Sample size
        all_issues.extend(self._validate_sample_size(protocol_facts))

        # Rule 6: Estimands
        all_issues.extend(self._validate_estimands(protocol_facts))

        # Rule 7: Interim analysis
        all_issues.extend(self._validate_interim_analysis(protocol_facts))

        # Apply auto-fixes
        self._apply_auto_fixes(protocol_facts, all_issues)

        # Separate errors and warnings
        critical_errors = [e for e in all_issues if e.severity == 'CRITICAL']
        errors = [e for e in all_issues if e.severity in ('CRITICAL', 'ERROR')]
        warnings = [e for e in all_issues if e.severity == 'WARNING']

        # Collect auto-fixes from errors that have them
        for issue in all_issues:
            if issue.suggested_fix and 'AUTO-FIXED' in str(issue.suggested_fix):
                auto_fixes.append({
                    'field': issue.field,
                    'message': issue.message,
                    'fix': issue.suggested_fix
                })

        is_valid = len(critical_errors) == 0

        if critical_errors:
            logger.error(f"[SAPValidator] Pre-generation FAILED: {len(critical_errors)} critical errors")
            for error in critical_errors:
                logger.error(f"  - {error.message}")
        else:
            logger.info(f"[SAPValidator] Pre-generation PASSED (warnings: {len(warnings)})")

        return {
            'valid': is_valid,
            'errors': errors,
            'warnings': warnings,
            'auto_fixes': auto_fixes
        }

    def validate_after_generation(self, sap_text: str, protocol_facts) -> Dict[str, Any]:
        """
        Validate generated SAP text AFTER generation

        Args:
            sap_text: Generated SAP text
            protocol_facts: Original extracted protocol facts

        Returns:
            Dict with keys: 'valid', 'errors', 'warnings', 'overall_confidence', 'human_review_sections'
        """
        all_issues = []
        human_review_sections = []

        logger.info("[SAPValidator] Running post-generation validation...")

        # Rule 1: No contradictions with study design
        all_issues.extend(self._check_design_contradictions(sap_text, protocol_facts))

        # Rule 2: No placeholders
        all_issues.extend(self._check_placeholders(sap_text))

        # Rule 3: All endpoints present
        all_issues.extend(self._check_endpoints_present(sap_text, protocol_facts))

        # Rule 4: No hallucinated content
        all_issues.extend(self._check_hallucinations(sap_text, protocol_facts))

        # Rule 5: Sample size matches
        all_issues.extend(self._check_sample_size_match(sap_text, protocol_facts))

        # Rule 6: Population definitions consistent
        all_issues.extend(self._check_population_consistency(sap_text, protocol_facts))

        # Rule 7: Statistical methods present
        all_issues.extend(self._check_statistical_methods(sap_text, protocol_facts))

        # Separate errors and warnings
        critical_errors = [e for e in all_issues if e.severity == 'CRITICAL']
        errors = [e for e in all_issues if e.severity in ('CRITICAL', 'ERROR')]
        warnings = [e for e in all_issues if e.severity == 'WARNING']

        is_valid = len(critical_errors) == 0

        # Calculate confidence based on error severity
        if critical_errors:
            overall_confidence = 0.3
        elif errors:
            overall_confidence = 0.6
        elif warnings:
            overall_confidence = 0.8
        else:
            overall_confidence = 0.95

        # Identify sections needing human review
        for issue in all_issues:
            if issue.severity in ('CRITICAL', 'ERROR') and issue.field:
                section_name = issue.field.split('.')[0] if '.' in issue.field else issue.field
                if section_name not in human_review_sections:
                    human_review_sections.append(section_name)

        if critical_errors:
            logger.error(f"[SAPValidator] Post-generation FAILED: {len(critical_errors)} critical errors")
            for error in critical_errors:
                logger.error(f"  - {error.message}")
        else:
            logger.info("[SAPValidator] Post-generation PASSED")

        return {
            'valid': is_valid,
            'errors': errors,
            'warnings': warnings,
            'overall_confidence': overall_confidence,
            'human_review_sections': human_review_sections
        }

    # ========================================================================
    # PRE-GENERATION VALIDATION RULES
    # ========================================================================

    def _validate_study_design(self, protocol_facts) -> List[ValidationError]:
        """Validate study design consistency"""
        errors = []

        if not hasattr(protocol_facts, 'study_design'):
            return errors

        study_design = protocol_facts.study_design

        # Check num_arms vs randomized
        num_arms = getattr(study_design, 'num_arms', None)
        randomized = getattr(study_design, 'is_randomized', None)
        if randomized is None:
            randomized = getattr(study_design, 'randomized', None)

        if num_arms == 1 and randomized == True:
            errors.append(ValidationError(
                severity='ERROR',
                category='logic',
                message="Study design contradiction: num_arms=1 but randomized=True",
                field='study_design',
                suggested_fix="Set randomized=False for single-arm study"
            ))

        if num_arms and num_arms > 1 and randomized == False:
            errors.append(ValidationError(
                severity='WARNING',
                category='logic',
                message=f"Study design unusual: num_arms={num_arms} but randomized=False",
                field='study_design',
                suggested_fix="Verify if this is a multi-arm non-randomized study"
            ))

        # Check for missing critical fields
        if not getattr(study_design, 'phase', None):
            errors.append(ValidationError(
                severity='WARNING',
                category='missing',
                message="Study phase not extracted",
                field='study_design.phase'
            ))

        return errors

    def _validate_populations(self, protocol_facts) -> List[ValidationError]:
        """Validate analysis population definitions"""
        errors = []

        if not hasattr(protocol_facts, 'populations'):
            return errors

        populations = protocol_facts.populations
        study_design = protocol_facts.study_design if hasattr(protocol_facts, 'study_design') else None

        # ITT definition consistency
        itt_def = getattr(populations, 'itt_definition', '') or ''

        if study_design:
            num_arms = getattr(study_design, 'num_arms', 1) or 1
            randomized = getattr(study_design, 'is_randomized', None)
            if randomized is None:
                randomized = getattr(study_design, 'randomized', False)

            if (num_arms == 1 or not randomized) and itt_def and 'randomized' in itt_def.lower():
                errors.append(ValidationError(
                    severity='CRITICAL',
                    category='logic',
                    message="ITT definition says 'randomized subjects' but study is single-arm/non-randomized",
                    field='populations.itt_definition',
                    suggested_fix="Change to 'enrolled subjects' or 'treated subjects'"
                ))

        return errors

    def _validate_required_fields(self, protocol_facts) -> List[ValidationError]:
        """Validate that required fields are present"""
        errors = []

        # Define required field checks with their paths
        required_checks = [
            ('endpoints', 'primary_endpoint', 'Primary endpoint', 'CRITICAL'),
            ('sample_size', 'sample_size', 'Sample size', 'CRITICAL'),
            ('study_design', 'phase', 'Study phase', 'WARNING'),
            ('study_design', 'disease_type', 'Disease type', 'WARNING'),
        ]

        for section, field, field_name, severity in required_checks:
            try:
                section_obj = getattr(protocol_facts, section, None)
                if section_obj:
                    value = getattr(section_obj, field, None)
                    if value is None or (isinstance(value, str) and value.strip() == ''):
                        errors.append(ValidationError(
                            severity=severity,
                            category='missing',
                            message=f"{field_name} is missing from extraction",
                            field=f'{section}.{field}',
                            suggested_fix="Re-extract or manually specify"
                        ))
                else:
                    errors.append(ValidationError(
                        severity=severity,
                        category='missing',
                        message=f"{field_name} section not found",
                        field=section
                    ))
            except AttributeError:
                pass

        return errors

    def _validate_endpoints(self, protocol_facts) -> List[ValidationError]:
        """Validate endpoint definitions"""
        errors = []

        if not hasattr(protocol_facts, 'endpoints'):
            return errors

        endpoints = protocol_facts.endpoints

        # Check primary endpoint
        primary = getattr(endpoints, 'primary_endpoint', None)
        if not primary or (isinstance(primary, str) and primary.strip() == ''):
            errors.append(ValidationError(
                severity='CRITICAL',
                category='missing',
                message="Primary endpoint is empty",
                field='endpoints.primary_endpoint'
            ))

        # Check secondary endpoints type
        secondary = getattr(endpoints, 'secondary_endpoints', None)
        if secondary and not isinstance(secondary, (list, tuple)):
            errors.append(ValidationError(
                severity='WARNING',
                category='extraction',
                message="Secondary endpoints should be a list",
                field='endpoints.secondary_endpoints',
                suggested_fix="Convert to list format"
            ))

        return errors

    def _validate_sample_size(self, protocol_facts) -> List[ValidationError]:
        """Validate sample size"""
        errors = []

        if not hasattr(protocol_facts, 'sample_size'):
            return errors

        sample_size_obj = protocol_facts.sample_size
        n = getattr(sample_size_obj, 'sample_size', None)

        if n is None:
            errors.append(ValidationError(
                severity='CRITICAL',
                category='missing',
                message="Sample size not extracted",
                field='sample_size.sample_size'
            ))
        elif isinstance(n, (int, float)):
            if n <= 0:
                errors.append(ValidationError(
                    severity='ERROR',
                    category='extraction',
                    message=f"Sample size is invalid: {n}",
                    field='sample_size.sample_size'
                ))
            elif n > 10000:
                errors.append(ValidationError(
                    severity='WARNING',
                    category='extraction',
                    message=f"Sample size unusually large: {n} - verify extraction",
                    field='sample_size.sample_size'
                ))

        return errors

    def _validate_estimands(self, protocol_facts) -> List[ValidationError]:
        """Validate estimand framework (ICH E9 R1)"""
        errors = []

        if not hasattr(protocol_facts, 'estimand'):
            return errors

        estimand = protocol_facts.estimand

        # If estimand section exists and has content, validate components
        if estimand:
            population = getattr(estimand, 'population', None) or getattr(estimand, 'estimand_population', None)
            if population:
                # Has estimand - validate components
                required_components = [
                    ('variable', 'estimand_variable'),
                    ('intercurrent_events', 'intercurrent_events'),
                ]

                for primary_name, alt_name in required_components:
                    value = getattr(estimand, primary_name, None) or getattr(estimand, alt_name, None)
                    if not value:
                        errors.append(ValidationError(
                            severity='WARNING',
                            category='incomplete',
                            message=f"Estimand component '{primary_name}' is missing",
                            field=f'estimand.{primary_name}'
                        ))

        return errors

    def _validate_interim_analysis(self, protocol_facts) -> List[ValidationError]:
        """Validate interim analysis configuration"""
        errors = []

        if not hasattr(protocol_facts, 'interim_analysis'):
            return errors

        ia = protocol_facts.interim_analysis
        has_interim = getattr(ia, 'has_interim_analysis', None)

        if has_interim:
            # Check for required fields when interim analysis is present
            num_interim = getattr(ia, 'num_interim_analyses', None)
            if num_interim is None:
                errors.append(ValidationError(
                    severity='WARNING',
                    category='missing',
                    message="Number of interim analyses not specified",
                    field='interim_analysis.num_interim_analyses'
                ))

            alpha_spending = getattr(ia, 'alpha_spending_function', None)
            if not alpha_spending:
                errors.append(ValidationError(
                    severity='WARNING',
                    category='missing',
                    message="Alpha spending function not specified for interim analysis",
                    field='interim_analysis.alpha_spending_function'
                ))

        return errors

    # ========================================================================
    # POST-GENERATION VALIDATION RULES
    # ========================================================================

    def _check_design_contradictions(self, sap_text: str, protocol_facts) -> List[ValidationError]:
        """Check for contradictions with study design"""
        errors = []

        if not hasattr(protocol_facts, 'study_design'):
            return errors

        study_design = protocol_facts.study_design
        num_arms = getattr(study_design, 'num_arms', 1) or 1
        randomized = getattr(study_design, 'is_randomized', None)
        if randomized is None:
            randomized = getattr(study_design, 'randomized', False)

        sap_lower = sap_text.lower()

        # Check 1: Single-arm shouldn't say "randomized"
        if num_arms == 1 or not randomized:
            if re.search(r'\ball randomized (subjects|patients)\b', sap_lower):
                errors.append(ValidationError(
                    severity='CRITICAL',
                    category='contradiction',
                    message="SAP says 'all randomized subjects' but study is single-arm/non-randomized",
                    suggested_fix="Replace with 'all enrolled subjects' or 'all treated subjects'"
                ))

            # Allow "randomization" in context like "no randomization"
            if 'randomization' in sap_lower and num_arms == 1:
                if not re.search(r'(no|without|non-|not)\s*randomiz', sap_lower):
                    # Check if it's in a negation context
                    if 'this is a single-arm' not in sap_lower and 'non-randomized' not in sap_lower:
                        errors.append(ValidationError(
                            severity='WARNING',
                            category='contradiction',
                            message="SAP mentions randomization but study is single-arm"
                        ))

        # Check 2: Study design descriptors
        if num_arms == 1:
            if re.search(r'\bcomparator\s+arm\b', sap_lower):
                errors.append(ValidationError(
                    severity='ERROR',
                    category='contradiction',
                    message="SAP mentions comparator arm but study is single-arm"
                ))

            if re.search(r'\bcontrol\s+arm\b', sap_lower) and 'historical control' not in sap_lower:
                errors.append(ValidationError(
                    severity='WARNING',
                    category='contradiction',
                    message="SAP mentions control arm but study is single-arm"
                ))

        return errors

    def _check_placeholders(self, sap_text: str) -> List[ValidationError]:
        """Check for placeholder text that should not be in final SAP"""
        errors = []

        placeholders = [
            (r'\[To be specified\]', 'CRITICAL'),
            (r'\[NEEDS REVIEW\]', 'CRITICAL'),
            (r'\[TBD\]', 'CRITICAL'),
            (r'\[INSERT.*?\]', 'CRITICAL'),
            (r'\[STATISTICAL METHOD NOT FOUND', 'CRITICAL'),
            (r'<PLACEHOLDER>', 'CRITICAL'),
            (r'\[PROTOCOL SPECIFIC\]', 'WARNING'),
            (r'\[.*?to be determined.*?\]', 'WARNING'),
        ]

        for pattern, severity in placeholders:
            matches = re.findall(pattern, sap_text, re.IGNORECASE)
            if matches:
                errors.append(ValidationError(
                    severity=severity,
                    category='incomplete',
                    message=f"Placeholder found in SAP: {matches[0]}",
                    suggested_fix="Replace with actual content or extract from protocol"
                ))

        return errors

    def _check_endpoints_present(self, sap_text: str, protocol_facts) -> List[ValidationError]:
        """Check that all extracted endpoints appear in SAP"""
        errors = []

        if not hasattr(protocol_facts, 'endpoints'):
            return errors

        endpoints = protocol_facts.endpoints
        sap_lower = sap_text.lower()

        # Check primary endpoint
        primary = getattr(endpoints, 'primary_endpoint', None)
        if primary and isinstance(primary, str) and len(primary.strip()) > 5:
            # Extract key terms from endpoint (ignore common words)
            stop_words = {'endpoint', 'defined', 'measured', 'the', 'and', 'or', 'is', 'as', 'of', 'to', 'for'}
            key_terms = [term for term in primary.lower().split()
                        if len(term) > 4 and term not in stop_words]

            if key_terms and not any(term in sap_lower for term in key_terms[:3]):
                errors.append(ValidationError(
                    severity='CRITICAL',
                    category='missing',
                    message=f"Primary endpoint '{primary[:50]}...' does not appear in SAP",
                    field='endpoints.primary_endpoint'
                ))

        # Check secondary endpoints (less strict)
        secondary = getattr(endpoints, 'secondary_endpoints', [])
        if isinstance(secondary, list):
            missing_count = 0
            for endpoint in secondary[:5]:  # Check first 5
                if endpoint and isinstance(endpoint, str) and len(endpoint.strip()) > 5:
                    key_terms = [term for term in endpoint.lower().split()
                                if len(term) > 4]

                    if key_terms and not any(term in sap_lower for term in key_terms[:2]):
                        missing_count += 1

            if missing_count > 2:
                errors.append(ValidationError(
                    severity='WARNING',
                    category='missing',
                    message=f"{missing_count} secondary endpoints may be missing from SAP"
                ))

        return errors

    def _check_hallucinations(self, sap_text: str, protocol_facts) -> List[ValidationError]:
        """Check for content added that's not in original protocol"""
        errors = []

        sap_lower = sap_text.lower()

        # Check 1: Estimands section
        if 'estimand' in sap_lower or 'ich e9(r1)' in sap_lower:
            has_estimand = False
            if hasattr(protocol_facts, 'estimand'):
                estimand = protocol_facts.estimand
                has_estimand = bool(getattr(estimand, 'population', None) or
                                   getattr(estimand, 'estimand_population', None))

            if not has_estimand:
                errors.append(ValidationError(
                    severity='WARNING',
                    category='hallucination',
                    message="SAP includes estimands section but original protocol may not have explicit estimands",
                    suggested_fix="Verify protocol has estimands or mark as 'derived from objectives'"
                ))

        # Check 2: Interim analysis
        if 'interim analysis' in sap_lower and 'no interim' not in sap_lower:
            if hasattr(protocol_facts, 'interim_analysis'):
                has_interim = getattr(protocol_facts.interim_analysis, 'has_interim_analysis', None)
                if has_interim == False:
                    errors.append(ValidationError(
                        severity='ERROR',
                        category='hallucination',
                        message="SAP mentions interim analysis but protocol says has_interim=False"
                    ))

        # Check 3: Specific multiplicity methods
        multiplicity_methods = ['bonferroni', 'hochberg', 'holm', 'benjamini', 'false discovery',
                               'gatekeeping', 'graphical approach']
        for method in multiplicity_methods:
            if method in sap_lower:
                if hasattr(protocol_facts, 'multiplicity'):
                    adjustment_method = getattr(protocol_facts.multiplicity, 'adjustment_method', None)
                    if not adjustment_method or adjustment_method.lower() == 'none':
                        errors.append(ValidationError(
                            severity='WARNING',
                            category='hallucination',
                            message=f"SAP mentions '{method}' but protocol does not specify multiplicity adjustment"
                        ))
                break

        return errors

    def _check_sample_size_match(self, sap_text: str, protocol_facts) -> List[ValidationError]:
        """Check that sample size in SAP matches protocol"""
        errors = []

        if not hasattr(protocol_facts, 'sample_size'):
            return errors

        expected_n = getattr(protocol_facts.sample_size, 'sample_size', None)

        if expected_n and isinstance(expected_n, (int, float)):
            expected_n = int(expected_n)

            # Look for N= or n= followed by number
            matches = re.findall(r'\b[Nn]\s*=\s*(\d+)', sap_text)

            if matches:
                sap_n_values = [int(m) for m in matches]

                # Check if expected value appears anywhere
                if expected_n not in sap_n_values:
                    # Allow some tolerance for per-arm calculations
                    close_match = any(abs(v - expected_n) < expected_n * 0.1 for v in sap_n_values)
                    if not close_match:
                        errors.append(ValidationError(
                            severity='WARNING',
                            category='inconsistency',
                            message=f"Sample size mismatch: protocol has N={expected_n} but SAP mentions {sap_n_values}",
                            field='sample_size.sample_size'
                        ))

        return errors

    def _check_population_consistency(self, sap_text: str, protocol_facts) -> List[ValidationError]:
        """Check that population definitions are consistent"""
        errors = []

        if not hasattr(protocol_facts, 'study_design'):
            return errors

        study_design = protocol_facts.study_design
        num_arms = getattr(study_design, 'num_arms', 1) or 1
        randomized = getattr(study_design, 'is_randomized', None)
        if randomized is None:
            randomized = getattr(study_design, 'randomized', False)

        # Extract ITT definition from SAP
        itt_pattern = r'(?:ITT|Intent-to-Treat)[^.]*(?:defined as|is|includes|consists of)\s+([^.]{10,100})'
        itt_matches = re.findall(itt_pattern, sap_text, re.IGNORECASE)

        if itt_matches:
            itt_text = itt_matches[0].lower()

            if (num_arms == 1 or not randomized) and 'randomized' in itt_text:
                errors.append(ValidationError(
                    severity='CRITICAL',
                    category='contradiction',
                    message="ITT definition in SAP says 'randomized' but study is single-arm/non-randomized"
                ))

        return errors

    def _check_statistical_methods(self, sap_text: str, protocol_facts) -> List[ValidationError]:
        """Check that statistical methods are specified"""
        errors = []

        sap_lower = sap_text.lower()

        # Check for primary analysis method
        method_indicators = [
            'log-rank', 'cox', 'kaplan-meier', 'ancova', 'anova',
            't-test', 'chi-square', 'fisher', 'wilcoxon', 'mann-whitney',
            'binomial', 'clopper-pearson', 'logistic regression'
        ]

        has_method = any(indicator in sap_lower for indicator in method_indicators)

        if not has_method:
            errors.append(ValidationError(
                severity='WARNING',
                category='incomplete',
                message="No specific statistical method found in SAP",
                suggested_fix="Add primary analysis method (e.g., log-rank test, ANCOVA)"
            ))

        return errors

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _apply_auto_fixes(self, protocol_facts, errors: List[ValidationError]) -> None:
        """Apply automatic fixes to protocol facts"""

        for error in errors:
            if error.severity == 'CRITICAL' and error.field == 'populations.itt_definition':
                # Auto-fix ITT definition
                if hasattr(protocol_facts, 'populations'):
                    populations = protocol_facts.populations
                    itt_def = getattr(populations, 'itt_definition', '') or ''

                    if itt_def and 'randomized' in itt_def.lower():
                        fixed_def = itt_def
                        fixed_def = re.sub(r'(?i)randomized subjects', 'enrolled subjects', fixed_def)
                        fixed_def = re.sub(r'(?i)randomized patients', 'enrolled patients', fixed_def)
                        fixed_def = re.sub(r'(?i)all randomized', 'all enrolled', fixed_def)

                        if fixed_def != itt_def:
                            populations.itt_definition = fixed_def
                            error.suggested_fix = f"AUTO-FIXED: Changed to '{fixed_def}'"
                            logger.info(f"[SAPValidator] Auto-fixed ITT definition")

    def _load_validation_rules(self) -> Dict[str, Any]:
        """Load validation rules configuration"""
        return {
            "required_fields": [
                "study_design.phase",
                "study_design.disease_type",
                "endpoints.primary_endpoint",
                "sample_size.sample_size"
            ],
            "forbidden_patterns": [
                r"\[To be specified\]",
                r"\[NEEDS REVIEW\]",
                r"\[TBD\]"
            ],
            "consistency_checks": [
                "itt_vs_randomization",
                "sample_size_match",
                "endpoint_presence"
            ]
        }

    def format_validation_report(self, errors: List[ValidationError]) -> str:
        """Format validation errors into readable report"""
        if not errors:
            return "No validation errors found"

        report = []
        report.append(f"\n{'='*80}")
        report.append(f"VALIDATION REPORT - {len(errors)} issues found")
        report.append(f"{'='*80}\n")

        # Group by severity
        critical = [e for e in errors if e.severity == 'CRITICAL']
        errors_list = [e for e in errors if e.severity == 'ERROR']
        warnings = [e for e in errors if e.severity == 'WARNING']

        if critical:
            report.append(f"CRITICAL ERRORS ({len(critical)}):")
            for i, error in enumerate(critical, 1):
                report.append(f"  {i}. {error.message}")
                if error.field:
                    report.append(f"     Field: {error.field}")
                if error.suggested_fix:
                    report.append(f"     Fix: {error.suggested_fix}")
                report.append("")

        if errors_list:
            report.append(f"ERRORS ({len(errors_list)}):")
            for i, error in enumerate(errors_list, 1):
                report.append(f"  {i}. {error.message}")
                if error.suggested_fix:
                    report.append(f"     Fix: {error.suggested_fix}")
                report.append("")

        if warnings:
            report.append(f"WARNINGS ({len(warnings)}):")
            for i, error in enumerate(warnings, 1):
                report.append(f"  {i}. {error.message}")
                report.append("")

        return "\n".join(report)
