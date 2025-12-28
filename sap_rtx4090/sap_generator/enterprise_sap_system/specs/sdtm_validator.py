#!/usr/bin/env python3
"""
SDTM Specification Validator
=============================

Validates generated SDTM specifications against CDISC standards.

References (Official Sources):
- CDISC SDTMIG v3.4: https://www.cdisc.org/standards/foundational/sdtmig/sdtmig-v3-4
- FDA Study Data Technical Conformance Guide v5.7: https://www.fda.gov/media/136460/download
- CDISC SDTM v2.0: https://www.cdisc.org/standards/foundational/sdtm

Core Classification (per CDISC SDTMIG Section 4.1.5):
- Req (Required): Cannot be null, essential key variables
- Exp (Expected): Must be included, can be null if no data collected
- Perm (Permissible): Include if data collected, otherwise omit

Validation checks:
1. Required variables present in each domain
2. Core classifications correct per CDISC standards
3. Domain structures valid (identifiers, topic, timing)
"""

import json
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ValidationSeverity(Enum):
    """Severity levels for validation findings."""
    ERROR = "ERROR"      # Must fix - violates CDISC standard
    WARNING = "WARNING"  # Should fix - best practice violation
    INFO = "INFO"        # Informational - suggestion


@dataclass
class ValidationFinding:
    """A single validation finding."""
    domain: str
    severity: ValidationSeverity
    rule_id: str
    message: str
    variable: Optional[str] = None
    cdisc_reference: str = ""


@dataclass
class ValidationResult:
    """Complete validation result."""
    is_valid: bool
    total_errors: int = 0
    total_warnings: int = 0
    total_info: int = 0
    findings: List[ValidationFinding] = field(default_factory=list)
    domains_validated: List[str] = field(default_factory=list)

    def add_finding(self, finding: ValidationFinding):
        self.findings.append(finding)
        if finding.severity == ValidationSeverity.ERROR:
            self.total_errors += 1
            self.is_valid = False
        elif finding.severity == ValidationSeverity.WARNING:
            self.total_warnings += 1
        else:
            self.total_info += 1


# =============================================================================
# CDISC SDTMIG v3.4 Reference Standards
# Source: https://www.cdisc.org/standards/foundational/sdtmig/sdtmig-v3-4
# =============================================================================

# Required variables for ALL domains (SDTMIG Section 4.1.2)
UNIVERSAL_REQUIRED_VARIABLES = {
    "STUDYID": {"label": "Study Identifier", "type": "Char", "core": "Req"},
    "DOMAIN": {"label": "Domain Abbreviation", "type": "Char", "core": "Req"},
    "USUBJID": {"label": "Unique Subject Identifier", "type": "Char", "core": "Req"},
}

# Domain-specific required and expected variables
# Per CDISC SDTMIG v3.4 domain specifications
DOMAIN_VARIABLE_REQUIREMENTS = {
    # Demographics (DM) - Special Purpose Domain
    # SDTMIG v3.4 Section 5.1
    "DM": {
        "required": ["STUDYID", "DOMAIN", "USUBJID", "SUBJID"],
        "expected": [
            "RFSTDTC",   # Subject Reference Start Date/Time
            "RFENDTC",   # Subject Reference End Date/Time
            "SITEID",    # Study Site Identifier
            "BRTHDTC",   # Date/Time of Birth (or AGE)
            "AGE",       # Age
            "AGEU",      # Age Units
            "SEX",       # Sex
            "RACE",      # Race
            "ETHNIC",    # Ethnicity
            "ARMCD",     # Planned Arm Code
            "ARM",       # Description of Planned Arm
            "COUNTRY",   # Country
        ],
        "structure": "One record per subject",
        "class": "Special Purpose",
    },

    # Adverse Events (AE) - Events Domain
    # SDTMIG v3.4 Section 6.2.1
    "AE": {
        "required": ["STUDYID", "DOMAIN", "USUBJID", "AESEQ", "AETERM", "AEDECOD"],
        "expected": [
            "AESPID",    # Sponsor-Defined Identifier
            "AEBODSYS",  # Body System or Organ Class
            "AESEV",     # Severity/Intensity
            "AESER",     # Serious Event
            "AEACN",     # Action Taken with Study Treatment
            "AEREL",     # Causality
            "AEOUT",     # Outcome of Adverse Event
            "AESTDTC",   # Start Date/Time
            "AEENDTC",   # End Date/Time
            "EPOCH",     # Epoch
        ],
        "structure": "One record per adverse event per subject",
        "class": "Events",
    },

    # Disposition (DS) - Events Domain
    # SDTMIG v3.4 Section 6.2.2
    "DS": {
        "required": ["STUDYID", "DOMAIN", "USUBJID", "DSSEQ", "DSTERM", "DSDECOD"],
        "expected": [
            "DSCAT",     # Category for Disposition Event
            "DSSCAT",    # Subcategory
            "EPOCH",     # Epoch
            "DSSTDTC",   # Start Date/Time
        ],
        "structure": "One record per disposition event per subject",
        "class": "Events",
    },

    # Exposure (EX) - Interventions Domain
    # SDTMIG v3.4 Section 6.1.1
    "EX": {
        "required": ["STUDYID", "DOMAIN", "USUBJID", "EXSEQ", "EXTRT"],
        "expected": [
            "EXDOSE",    # Dose
            "EXDOSU",    # Dose Units
            "EXDOSFRM",  # Dose Form
            "EXROUTE",   # Route of Administration
            "EXSTDTC",   # Start Date/Time
            "EXENDTC",   # End Date/Time
            "EPOCH",     # Epoch
            "VISITNUM",  # Visit Number
            "VISIT",     # Visit Name
        ],
        "structure": "One record per constant-dosing interval per subject",
        "class": "Interventions",
    },

    # Concomitant Medications (CM) - Interventions Domain
    # SDTMIG v3.4 Section 6.1.2
    "CM": {
        "required": ["STUDYID", "DOMAIN", "USUBJID", "CMSEQ", "CMTRT"],
        "expected": [
            "CMDECOD",   # Standardized Medication Name
            "CMCAT",     # Category
            "CMDOSE",    # Dose per Administration
            "CMDOSU",    # Dose Units
            "CMROUTE",   # Route of Administration
            "CMSTDTC",   # Start Date/Time
            "CMENDTC",   # End Date/Time
            "CMINDC",    # Indication
        ],
        "structure": "One record per medication per subject",
        "class": "Interventions",
    },

    # Laboratory Test Results (LB) - Findings Domain
    # SDTMIG v3.4 Section 6.3.4
    "LB": {
        "required": ["STUDYID", "DOMAIN", "USUBJID", "LBSEQ", "LBTESTCD", "LBTEST"],
        "expected": [
            "LBCAT",     # Category
            "LBORRES",   # Result or Finding in Original Units
            "LBORRESU",  # Original Units
            "LBSTRESC",  # Character Result/Finding in Std Format
            "LBSTRESN",  # Numeric Result/Finding in Standard Units
            "LBSTRESU",  # Standard Units
            "LBSTNRLO",  # Reference Range Lower Limit-Std Units
            "LBSTNRHI",  # Reference Range Upper Limit-Std Units
            "LBNRIND",   # Reference Range Indicator
            "LBSPEC",    # Specimen Type
            "VISITNUM",  # Visit Number
            "VISIT",     # Visit Name
            "LBDTC",     # Date/Time of Specimen Collection
            "LBDY",      # Study Day of Specimen Collection
        ],
        "structure": "One record per lab test per time point per subject",
        "class": "Findings",
    },

    # Vital Signs (VS) - Findings Domain
    # SDTMIG v3.4 Section 6.3.7
    "VS": {
        "required": ["STUDYID", "DOMAIN", "USUBJID", "VSSEQ", "VSTESTCD", "VSTEST"],
        "expected": [
            "VSORRES",   # Result or Finding in Original Units
            "VSORRESU",  # Original Units
            "VSSTRESC",  # Character Result in Std Format
            "VSSTRESN",  # Numeric Result in Standard Units
            "VSSTRESU",  # Standard Units
            "VSPOS",     # Vital Signs Position of Subject
            "VSLOC",     # Location of Vital Signs Measurement
            "VISITNUM",  # Visit Number
            "VISIT",     # Visit Name
            "VSDTC",     # Date/Time of Measurements
            "VSDY",      # Study Day of Vital Signs
        ],
        "structure": "One record per vital sign per time point per subject",
        "class": "Findings",
    },

    # Questionnaires (QS) - Findings Domain
    # SDTMIG v3.4 Section 6.3.6
    "QS": {
        "required": ["STUDYID", "DOMAIN", "USUBJID", "QSSEQ", "QSTESTCD", "QSTEST", "QSCAT"],
        "expected": [
            "QSORRES",   # Result or Finding in Original Units
            "QSSTRESC",  # Character Result in Std Format
            "QSSTRESN",  # Numeric Result in Standard Units
            "VISITNUM",  # Visit Number
            "VISIT",     # Visit Name
            "QSDTC",     # Date/Time of Assessment
            "QSBLFL",    # Baseline Flag
            "EPOCH",     # Epoch
        ],
        "structure": "One record per questionnaire item per time point per subject",
        "class": "Findings",
    },

    # Medical History (MH) - Events Domain
    # SDTMIG v3.4 Section 6.2.3
    "MH": {
        "required": ["STUDYID", "DOMAIN", "USUBJID", "MHSEQ", "MHTERM"],
        "expected": [
            "MHDECOD",   # Dictionary-Derived Term
            "MHCAT",     # Category
            "MHBODSYS",  # Body System or Organ Class
            "MHSTDTC",   # Start Date/Time
            "MHENDTC",   # End Date/Time
            "MHENRF",    # End Relative to Reference Period
        ],
        "structure": "One record per medical history event per subject",
        "class": "Events",
    },

    # Protocol Deviations (DV) - Events Domain
    # SDTMIG v3.4 Section 6.2.5
    "DV": {
        "required": ["STUDYID", "DOMAIN", "USUBJID", "DVSEQ", "DVTERM"],
        "expected": [
            "DVDECOD",   # Dictionary-Derived Term
            "DVCAT",     # Category
            "DVSCAT",    # Subcategory
            "DVSTDTC",   # Start Date/Time
            "DVENDTC",   # End Date/Time
            "EPOCH",     # Epoch
        ],
        "structure": "One record per protocol deviation per subject",
        "class": "Events",
    },

    # Trial Arms (TA) - Trial Design Domain
    # SDTMIG v3.4 Section 7.2
    "TA": {
        "required": ["STUDYID", "DOMAIN", "ARMCD", "ARM", "TAESSION", "ETCD", "ELEMENT"],
        "expected": [
            "TABESSION",  # Branch Session Number
            "EPOCH",      # Epoch
        ],
        "structure": "One record per element per arm",
        "class": "Trial Design",
    },

    # Trial Summary (TS) - Trial Design Domain
    # SDTMIG v3.4 Section 7.1
    "TS": {
        "required": ["STUDYID", "DOMAIN", "TSSEQ", "TSPARMCD", "TSPARM"],
        "expected": [
            "TSVAL",      # Parameter Value
            "TSVALNF",    # Parameter Null Flavor
            "TSVALCD",    # Parameter Value Code
        ],
        "structure": "One record per trial summary parameter",
        "class": "Trial Design",
    },

    # ECG Test Results (EG) - Findings Domain
    # SDTMIG v3.4 Section 6.3.2
    "EG": {
        "required": ["STUDYID", "DOMAIN", "USUBJID", "EGSEQ", "EGTESTCD", "EGTEST"],
        "expected": [
            "EGORRES",   # Result or Finding in Original Units
            "EGORRESU",  # Original Units
            "EGSTRESC",  # Character Result in Std Format
            "EGSTRESN",  # Numeric Result in Standard Units
            "EGSTRESU",  # Standard Units
            "VISITNUM",  # Visit Number
            "VISIT",     # Visit Name
            "EGDTC",     # Date/Time of ECG
        ],
        "structure": "One record per ECG observation per time point per subject",
        "class": "Findings",
    },

    # Tumor Results (TR) - Findings Domain - Oncology
    # SDTMIG v3.4
    "TR": {
        "required": ["STUDYID", "DOMAIN", "USUBJID", "TRSEQ", "TRTESTCD", "TRTEST", "TRLNKID"],
        "expected": [
            "TRORRES",   # Result or Finding in Original Units
            "TRSTRESC",  # Character Result in Std Format
            "TRSTRESN",  # Numeric Result
            "TRMETHOD",  # Method of Test or Examination
            "TRLOC",     # Location of Tumor
            "VISITNUM",  # Visit Number
            "VISIT",     # Visit Name
            "TRDTC",     # Date/Time of Tumor Assessment
        ],
        "structure": "One record per tumor measurement per time point per subject",
        "class": "Findings",
    },

    # Disease Response (RS) - Findings Domain - Oncology
    # SDTMIG v3.4
    "RS": {
        "required": ["STUDYID", "DOMAIN", "USUBJID", "RSSEQ", "RSTESTCD", "RSTEST"],
        "expected": [
            "RSCAT",     # Category
            "RSORRES",   # Result or Finding in Original Units
            "RSSTRESC",  # Character Result in Std Format
            "RSEVAL",    # Evaluator
            "VISITNUM",  # Visit Number
            "VISIT",     # Visit Name
            "RSDTC",     # Date/Time of Response Assessment
        ],
        "structure": "One record per response assessment per subject",
        "class": "Findings",
    },
}

# Controlled terminology requirements
# Per CDISC Controlled Terminology and SDTMIG
CONTROLLED_TERMINOLOGY = {
    "SEX": ["M", "F", "U", "UNDIFFERENTIATED"],
    "NY": ["Y", "N"],
    "EPOCH": ["SCREENING", "RUN-IN", "TREATMENT", "FOLLOW-UP"],
    "ACN": ["DRUG WITHDRAWN", "DOSE REDUCED", "DOSE INCREASED", "DOSE NOT CHANGED",
            "UNKNOWN", "NOT APPLICABLE"],
    "OUT": ["RECOVERED/RESOLVED", "RECOVERING/RESOLVING", "NOT RECOVERED/NOT RESOLVED",
            "RECOVERED/RESOLVED WITH SEQUELAE", "FATAL", "UNKNOWN"],
}


class SDTMValidator:
    """
    Validates SDTM specifications against CDISC standards.

    Based on:
    - CDISC SDTMIG v3.4 (https://www.cdisc.org/standards/foundational/sdtmig/sdtmig-v3-4)
    - FDA Study Data Technical Conformance Guide
    """

    def __init__(self):
        self.domain_requirements = DOMAIN_VARIABLE_REQUIREMENTS
        self.universal_required = UNIVERSAL_REQUIRED_VARIABLES

    def validate_specification(self, spec_path: str) -> ValidationResult:
        """
        Validate an SDTM specification JSON file.

        Args:
            spec_path: Path to sdtm_specification.json

        Returns:
            ValidationResult with all findings
        """
        result = ValidationResult(is_valid=True)

        # Load specification
        try:
            with open(spec_path, 'r') as f:
                spec = json.load(f)
        except Exception as e:
            result.add_finding(ValidationFinding(
                domain="SPEC",
                severity=ValidationSeverity.ERROR,
                rule_id="SPEC001",
                message=f"Cannot load specification: {e}",
            ))
            return result

        # Validate each domain
        domains = spec.get("domains", [])
        for domain in domains:
            domain_code = domain.get("code", "UNKNOWN")
            result.domains_validated.append(domain_code)

            # Run all validation checks
            self._check_required_variables(domain, result)
            self._check_core_classifications(domain, result)
            self._check_domain_structure(domain, result)
            self._check_variable_attributes(domain, result)

        # Check for missing required domains
        self._check_required_domains(spec, result)

        return result

    def _check_required_variables(self, domain: Dict, result: ValidationResult):
        """
        Check that all required variables are present.

        Per SDTMIG v3.4 Section 4.1.5:
        "Required variables are any variable that is basic to the identification
        of a data record or is necessary to make the record meaningful."
        """
        domain_code = domain.get("code", "UNKNOWN")
        variables = {v.get("name"): v for v in domain.get("variables", [])}

        # Trial Design domains don't have USUBJID (they are trial-level, not subject-level)
        # Per SDTMIG v3.4 Section 7
        trial_design_domains = ["TA", "TE", "TI", "TS", "TV"]

        # Check universal required variables
        universal_vars = ["STUDYID", "DOMAIN"]
        if domain_code not in trial_design_domains:
            universal_vars.append("USUBJID")

        for var_name in universal_vars:
            if var_name not in variables:
                result.add_finding(ValidationFinding(
                    domain=domain_code,
                    severity=ValidationSeverity.ERROR,
                    rule_id="REQ001",
                    message=f"Missing universal required variable: {var_name}",
                    variable=var_name,
                    cdisc_reference="SDTMIG v3.4 Section 4.1.2",
                ))

        # Check domain-specific required variables
        if domain_code in self.domain_requirements:
            req_vars = self.domain_requirements[domain_code].get("required", [])
            for var_name in req_vars:
                if var_name not in variables:
                    result.add_finding(ValidationFinding(
                        domain=domain_code,
                        severity=ValidationSeverity.ERROR,
                        rule_id="REQ002",
                        message=f"Missing required variable for {domain_code}: {var_name}",
                        variable=var_name,
                        cdisc_reference=f"SDTMIG v3.4 {domain_code} Domain",
                    ))
                else:
                    # Check that required variable has core=Req
                    var = variables[var_name]
                    if var.get("core") != "Req":
                        result.add_finding(ValidationFinding(
                            domain=domain_code,
                            severity=ValidationSeverity.ERROR,
                            rule_id="REQ003",
                            message=f"Required variable {var_name} must have Core='Req', found '{var.get('core')}'",
                            variable=var_name,
                            cdisc_reference="SDTMIG v3.4 Section 4.1.5",
                        ))

    def _check_core_classifications(self, domain: Dict, result: ValidationResult):
        """
        Validate core classifications are correct.

        Per SDTMIG v3.4:
        - Req: Cannot be null
        - Exp: Must include, can be null
        - Perm: Optional based on data collected
        """
        domain_code = domain.get("code", "UNKNOWN")
        variables = domain.get("variables", [])

        valid_cores = ["Req", "Exp", "Perm"]

        for var in variables:
            var_name = var.get("name", "UNKNOWN")
            core = var.get("core", "")

            # Check valid core value
            if core not in valid_cores:
                result.add_finding(ValidationFinding(
                    domain=domain_code,
                    severity=ValidationSeverity.ERROR,
                    rule_id="CORE001",
                    message=f"Invalid Core value '{core}' for {var_name}. Must be Req, Exp, or Perm",
                    variable=var_name,
                    cdisc_reference="SDTMIG v3.4 Section 4.1.5",
                ))

            # Check expected variables have correct core
            if domain_code in self.domain_requirements:
                exp_vars = self.domain_requirements[domain_code].get("expected", [])
                if var_name in exp_vars and core == "Perm":
                    result.add_finding(ValidationFinding(
                        domain=domain_code,
                        severity=ValidationSeverity.WARNING,
                        rule_id="CORE002",
                        message=f"Variable {var_name} is Expected per SDTMIG but marked as Permissible",
                        variable=var_name,
                        cdisc_reference=f"SDTMIG v3.4 {domain_code} Domain",
                    ))

    def _check_domain_structure(self, domain: Dict, result: ValidationResult):
        """
        Validate domain structure meets CDISC requirements.

        Per SDTMIG v3.4:
        - Each domain must have identifiers (STUDYID, USUBJID)
        - Each domain must have a topic variable (--TERM, --TRT, --TESTCD, etc.)
        - Sequence variable (--SEQ) required for most domains
        """
        domain_code = domain.get("code", "UNKNOWN")
        domain_class = domain.get("class", "")
        variables = {v.get("name"): v for v in domain.get("variables", [])}

        # Check sequence variable
        # Not needed for: DM (single record), Trial Design domains (TA, TE, TI, TV)
        # TS uses TSSEQ which we check in domain-specific requirements
        trial_design_no_seq = ["DM", "TA", "TE", "TI", "TV"]
        if domain_code not in trial_design_no_seq:
            seq_var = f"{domain_code}SEQ"
            if seq_var not in variables:
                # Check for alternate naming
                if not any(v.endswith("SEQ") for v in variables.keys()):
                    result.add_finding(ValidationFinding(
                        domain=domain_code,
                        severity=ValidationSeverity.ERROR,
                        rule_id="STRUCT001",
                        message=f"Missing sequence variable {seq_var}",
                        variable=seq_var,
                        cdisc_reference="SDTMIG v3.4 Section 4.1.2",
                    ))

        # Check topic variable based on domain class
        topic_patterns = {
            "Events": ["TERM", "DECOD"],
            "Interventions": ["TRT"],
            "Findings": ["TESTCD", "TEST"],
        }

        if domain_class in topic_patterns:
            has_topic = False
            for pattern in topic_patterns[domain_class]:
                if any(v.endswith(pattern) for v in variables.keys()):
                    has_topic = True
                    break

            if not has_topic:
                result.add_finding(ValidationFinding(
                    domain=domain_code,
                    severity=ValidationSeverity.WARNING,
                    rule_id="STRUCT002",
                    message=f"Missing expected topic variable for {domain_class} domain",
                    cdisc_reference="SDTMIG v3.4 Section 4.1.3",
                ))

        # Check structure description
        structure = domain.get("structure", "")
        if not structure:
            result.add_finding(ValidationFinding(
                domain=domain_code,
                severity=ValidationSeverity.WARNING,
                rule_id="STRUCT003",
                message="Missing structure description",
                cdisc_reference="SDTMIG v3.4 Domain Structure",
            ))

    def _check_variable_attributes(self, domain: Dict, result: ValidationResult):
        """
        Validate variable attributes (type, length, labels).

        Per SDTMIG v3.4:
        - Variables must have type (Char or Num)
        - Character variables should have length
        - Variables must have descriptive labels
        """
        domain_code = domain.get("code", "UNKNOWN")
        variables = domain.get("variables", [])

        for var in variables:
            var_name = var.get("name", "UNKNOWN")
            var_type = var.get("type", "")
            label = var.get("label", "")
            length = var.get("length")

            # Check type
            if var_type not in ["Char", "Num"]:
                result.add_finding(ValidationFinding(
                    domain=domain_code,
                    severity=ValidationSeverity.ERROR,
                    rule_id="ATTR001",
                    message=f"Invalid type '{var_type}' for {var_name}. Must be 'Char' or 'Num'",
                    variable=var_name,
                    cdisc_reference="SDTMIG v3.4 Variable Types",
                ))

            # Check label
            if not label:
                result.add_finding(ValidationFinding(
                    domain=domain_code,
                    severity=ValidationSeverity.WARNING,
                    rule_id="ATTR002",
                    message=f"Missing label for variable {var_name}",
                    variable=var_name,
                    cdisc_reference="SDTMIG v3.4 Variable Labels",
                ))
            elif len(label) > 40:
                result.add_finding(ValidationFinding(
                    domain=domain_code,
                    severity=ValidationSeverity.WARNING,
                    rule_id="ATTR003",
                    message=f"Label for {var_name} exceeds 40 characters: '{label[:40]}...'",
                    variable=var_name,
                    cdisc_reference="SDTMIG v3.4 Section 4.1.4",
                ))

            # Check character variable length
            if var_type == "Char" and length is None:
                result.add_finding(ValidationFinding(
                    domain=domain_code,
                    severity=ValidationSeverity.INFO,
                    rule_id="ATTR004",
                    message=f"Character variable {var_name} has no length specified",
                    variable=var_name,
                ))

    def _check_required_domains(self, spec: Dict, result: ValidationResult):
        """
        Check that required domains are present.

        Per FDA Study Data Technical Conformance Guide:
        - DM is always required
        - TS is required for all studies
        - AE is required for safety studies
        - DS is required for disposition
        """
        domain_codes = [d.get("code") for d in spec.get("domains", [])]

        # DM is always required
        if "DM" not in domain_codes:
            result.add_finding(ValidationFinding(
                domain="SPEC",
                severity=ValidationSeverity.ERROR,
                rule_id="DOM001",
                message="Missing required domain: DM (Demographics)",
                cdisc_reference="SDTMIG v3.4 Section 5.1",
            ))

        # TS required for FDA submissions
        if "TS" not in domain_codes:
            result.add_finding(ValidationFinding(
                domain="SPEC",
                severity=ValidationSeverity.WARNING,
                rule_id="DOM002",
                message="Missing Trial Summary (TS) domain - required for FDA submissions",
                cdisc_reference="FDA Study Data TCG",
            ))

    def generate_report(self, result: ValidationResult) -> str:
        """Generate a formatted validation report."""
        lines = [
            "=" * 70,
            "SDTM SPECIFICATION VALIDATION REPORT",
            "=" * 70,
            f"Based on: CDISC SDTMIG v3.4",
            f"Reference: https://www.cdisc.org/standards/foundational/sdtmig/sdtmig-v3-4",
            "",
            f"Domains Validated: {', '.join(result.domains_validated)}",
            "",
            "-" * 70,
            "SUMMARY",
            "-" * 70,
            f"Status:   {'PASSED' if result.is_valid else 'FAILED'}",
            f"Errors:   {result.total_errors}",
            f"Warnings: {result.total_warnings}",
            f"Info:     {result.total_info}",
            "",
        ]

        if result.findings:
            lines.extend([
                "-" * 70,
                "FINDINGS",
                "-" * 70,
                "",
            ])

            # Group by severity
            for severity in [ValidationSeverity.ERROR, ValidationSeverity.WARNING, ValidationSeverity.INFO]:
                severity_findings = [f for f in result.findings if f.severity == severity]
                if severity_findings:
                    lines.append(f"### {severity.value}S ({len(severity_findings)})")
                    lines.append("")
                    for f in severity_findings:
                        var_info = f" [{f.variable}]" if f.variable else ""
                        lines.append(f"  [{f.rule_id}] {f.domain}{var_info}: {f.message}")
                        if f.cdisc_reference:
                            lines.append(f"           Reference: {f.cdisc_reference}")
                    lines.append("")

        lines.extend([
            "=" * 70,
            "END OF REPORT",
            "=" * 70,
        ])

        return "\n".join(lines)


def validate_sdtm_spec(spec_path: str, print_report: bool = True) -> ValidationResult:
    """
    Convenience function to validate an SDTM specification.

    Args:
        spec_path: Path to sdtm_specification.json
        print_report: Whether to print the validation report

    Returns:
        ValidationResult
    """
    validator = SDTMValidator()
    result = validator.validate_specification(spec_path)

    if print_report:
        report = validator.generate_report(result)
        print(report)

    return result


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate SDTM specification against CDISC standards"
    )
    parser.add_argument(
        "spec_path",
        nargs="?",
        default="/tmp/sas_test_output/sdtm_specs/sdtm_specification.json",
        help="Path to sdtm_specification.json"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    result = validate_sdtm_spec(args.spec_path, print_report=not args.json)

    if args.json:
        import json
        output = {
            "is_valid": result.is_valid,
            "total_errors": result.total_errors,
            "total_warnings": result.total_warnings,
            "total_info": result.total_info,
            "domains_validated": result.domains_validated,
            "findings": [
                {
                    "domain": f.domain,
                    "severity": f.severity.value,
                    "rule_id": f.rule_id,
                    "message": f.message,
                    "variable": f.variable,
                    "cdisc_reference": f.cdisc_reference,
                }
                for f in result.findings
            ]
        }
        print(json.dumps(output, indent=2))

    # Exit with appropriate code
    exit(0 if result.is_valid else 1)
