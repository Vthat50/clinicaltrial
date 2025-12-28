#!/usr/bin/env python3
"""
SAP Validation Script
=====================

Automatically validates a generated SAP against protocol requirements.
Run after SAP generation to get a detailed quality assessment.

Usage:
    python validate_sap.py <sap_file> [protocol_file]
    python validate_sap.py --latest  # Validates most recent SAP in output/

Output:
    - Detailed section-by-section assessment
    - Scores for each component
    - List of issues and recommendations
"""

import re
import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ValidationResult:
    """Result for a single validation check"""
    name: str
    passed: bool
    score: int  # 0-100
    status: str  # "PASS", "PARTIAL", "FAIL", "MISSING"
    message: str
    details: List[str] = field(default_factory=list)
    expected: Optional[str] = None
    actual: Optional[str] = None


@dataclass
class SectionScore:
    """Score for an entire section"""
    name: str
    score: int  # 0-100
    max_score: int
    checks: List[ValidationResult] = field(default_factory=list)

    @property
    def percentage(self) -> float:
        return (self.score / self.max_score * 100) if self.max_score > 0 else 0


class SAPValidator:
    """
    Validates SAP content against protocol requirements and best practices.
    """

    def __init__(self, sap_text: str, protocol_text: str = None):
        self.sap_text = sap_text
        self.protocol_text = protocol_text or ""
        self.results: Dict[str, SectionScore] = {}
        self.overall_score = 0

        # Extract key values from protocol if available
        self.protocol_facts = self._extract_protocol_facts() if protocol_text else {}

    def _extract_protocol_facts(self) -> Dict[str, Any]:
        """Extract key facts from protocol for validation"""
        facts = {}

        # NCT ID
        nct_match = re.search(r'(NCT\d{8})', self.protocol_text)
        if nct_match:
            facts['nct_id'] = nct_match.group(1)

        # Drug name
        drug_patterns = [
            r'(?:Investigational\s+Product|IMP)[:\s]+([A-Za-z][A-Za-z0-9-]{2,})',
            r'\b([A-Z]{2,3}\d{3,4})\b',
        ]
        for pattern in drug_patterns:
            match = re.search(pattern, self.protocol_text, re.I)
            if match and match.group(1).upper() not in ['NCT', 'THE', 'AND']:
                facts['drug_name'] = match.group(1)
                break

        # Sample size
        n_match = re.search(r'(?:total\s+of\s+)?(\d{2,4})\s+(?:patients?|subjects?)', self.protocol_text, re.I)
        if n_match:
            facts['total_n'] = int(n_match.group(1))

        # Power values
        power_matches = re.findall(r'(\d{2})%?\s*power|power\s+(?:of\s+)?(\d{2})%?', self.protocol_text, re.I)
        facts['power_values'] = [m[0] or m[1] for m in power_matches if m[0] or m[1]]

        # Alpha sidedness
        if re.search(r'one[- ]sided', self.protocol_text, re.I):
            facts['alpha_sidedness'] = 'one-sided'
        elif re.search(r'two[- ]sided', self.protocol_text, re.I):
            facts['alpha_sidedness'] = 'two-sided'

        # Doses
        dose_matches = re.findall(r'(\d+)\s*(?:mg|mcg)', self.protocol_text, re.I)
        facts['doses'] = list(set(dose_matches))

        # Primary endpoint type
        if re.search(r'remission|response|responder', self.protocol_text, re.I):
            facts['endpoint_type'] = 'binary'
        else:
            facts['endpoint_type'] = 'continuous'

        # Analysis method
        if re.search(r'logistic\s+regression', self.protocol_text, re.I):
            facts['analysis_method'] = 'Logistic Regression'

        return facts

    def validate_all(self) -> Dict[str, SectionScore]:
        """Run all validation checks"""
        self.results = {}

        # Validate each section
        self.results['study_design'] = self._validate_study_design()
        self.results['analysis_populations'] = self._validate_populations()
        self.results['primary_endpoint'] = self._validate_primary_endpoint()
        self.results['secondary_endpoints'] = self._validate_secondary_endpoints()
        self.results['sample_size'] = self._validate_sample_size()
        self.results['primary_analysis'] = self._validate_primary_analysis()
        self.results['missing_data'] = self._validate_missing_data()
        self.results['safety_analysis'] = self._validate_safety()
        self.results['pk_analysis'] = self._validate_pk()
        self.results['subgroups'] = self._validate_subgroups()
        self.results['multiplicity'] = self._validate_multiplicity()
        self.results['visit_windows'] = self._validate_visit_windows()
        self.results['biomarkers'] = self._validate_biomarkers()
        self.results['treatment_arms'] = self._validate_treatment_arms()
        self.results['immunogenicity'] = self._validate_immunogenicity()

        # Calculate overall score
        total_score = sum(s.score for s in self.results.values())
        max_score = sum(s.max_score for s in self.results.values())
        self.overall_score = int(total_score / max_score * 100) if max_score > 0 else 0

        return self.results

    def _validate_study_design(self) -> SectionScore:
        """Validate Study Design section"""
        checks = []

        # Check for study design section
        has_section = bool(re.search(r'(?:##?\s*)?(?:\d+\.?\s*)?study\s+design', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Study Design Section Present",
            passed=has_section,
            score=20 if has_section else 0,
            status="PASS" if has_section else "FAIL",
            message="Study Design section found" if has_section else "Study Design section missing"
        ))

        # Check for randomization ratio
        has_ratio = bool(re.search(r'\d+:\d+(?::\d+)?', self.sap_text))
        checks.append(ValidationResult(
            name="Randomization Ratio",
            passed=has_ratio,
            score=20 if has_ratio else 0,
            status="PASS" if has_ratio else "FAIL",
            message="Randomization ratio specified" if has_ratio else "Missing randomization ratio"
        ))

        # Check for blinding description
        has_blinding = bool(re.search(r'double[- ]blind|single[- ]blind|open[- ]label', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Blinding Description",
            passed=has_blinding,
            score=20 if has_blinding else 10,
            status="PASS" if has_blinding else "PARTIAL",
            message="Blinding described" if has_blinding else "Blinding not explicitly described"
        ))

        # Check for drug name
        has_drug = bool(re.search(r'investigational\s+product|study\s+drug|IMP', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Drug Name Present",
            passed=has_drug,
            score=20 if has_drug else 0,
            status="PASS" if has_drug else "FAIL",
            message="Drug/IMP mentioned" if has_drug else "Drug name missing"
        ))

        # Check for route of administration
        has_route = bool(re.search(r'intravenous|subcutaneous|oral|IV|SC|topical', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Route of Administration",
            passed=has_route,
            score=20 if has_route else 0,
            status="PASS" if has_route else "FAIL",
            message="Route specified" if has_route else "Route of administration missing"
        ))

        total = sum(c.score for c in checks)
        return SectionScore(name="Study Design", score=total, max_score=100, checks=checks)

    def _validate_populations(self) -> SectionScore:
        """Validate Analysis Populations section"""
        checks = []

        populations = ['ITT', 'FAS', 'PP', 'Safety', 'Per-Protocol']
        found = []

        for pop in populations:
            if re.search(rf'\b{pop}\b', self.sap_text, re.I):
                found.append(pop)

        score = min(len(found) * 25, 100)
        checks.append(ValidationResult(
            name="Analysis Populations Defined",
            passed=len(found) >= 3,
            score=score,
            status="PASS" if len(found) >= 4 else "PARTIAL" if len(found) >= 2 else "FAIL",
            message=f"Found populations: {', '.join(found)}",
            details=[f"- {p}" for p in found]
        ))

        return SectionScore(name="Analysis Populations", score=score, max_score=100, checks=checks)

    def _validate_primary_endpoint(self) -> SectionScore:
        """Validate Primary Endpoint section"""
        checks = []

        # Check for primary endpoint section
        has_section = bool(re.search(r'primary\s+(?:efficacy\s+)?endpoint', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Primary Endpoint Section",
            passed=has_section,
            score=30 if has_section else 0,
            status="PASS" if has_section else "FAIL",
            message="Primary endpoint section found" if has_section else "Primary endpoint section missing"
        ))

        # Check for endpoint definition
        has_definition = bool(re.search(
            r'(?:defined\s+as|definition)[:\s]+[^\n]+',
            self.sap_text, re.I
        ))
        checks.append(ValidationResult(
            name="Endpoint Definition",
            passed=has_definition,
            score=35 if has_definition else 0,
            status="PASS" if has_definition else "FAIL",
            message="Endpoint definition provided" if has_definition else "Missing endpoint definition"
        ))

        # Check for timepoint
        has_timepoint = bool(re.search(r'(?:Week|Day|Month)\s+\d+', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Primary Timepoint",
            passed=has_timepoint,
            score=35 if has_timepoint else 0,
            status="PASS" if has_timepoint else "FAIL",
            message="Primary timepoint specified" if has_timepoint else "Missing primary timepoint"
        ))

        total = sum(c.score for c in checks)
        return SectionScore(name="Primary Endpoint", score=total, max_score=100, checks=checks)

    def _validate_secondary_endpoints(self) -> SectionScore:
        """Validate Secondary Endpoints section"""
        checks = []

        # Check for secondary endpoints section
        secondary_section = re.search(
            r'secondary\s+(?:efficacy\s+)?endpoints?(.*?)(?:###|##|\n\n\d+\.)',
            self.sap_text, re.I | re.DOTALL
        )

        has_section = secondary_section is not None
        checks.append(ValidationResult(
            name="Secondary Endpoints Section",
            passed=has_section,
            score=20 if has_section else 0,
            status="PASS" if has_section else "FAIL",
            message="Secondary endpoints section found" if has_section else "Missing secondary endpoints section"
        ))

        if has_section:
            section_text = secondary_section.group(1)

            # Check for corruption (analysis method text in endpoints)
            corruption_patterns = [
                r'will\s+be\s+analy[sz]ed',
                r'using\s+(?:a\s+)?(?:logistic|repeated|regression)',
                r'model\s+(?:will|is)',
            ]
            is_corrupted = any(re.search(p, section_text, re.I) for p in corruption_patterns)
            checks.append(ValidationResult(
                name="Endpoints Not Corrupted",
                passed=not is_corrupted,
                score=30 if not is_corrupted else 0,
                status="PASS" if not is_corrupted else "FAIL",
                message="Endpoints are clean" if not is_corrupted else "CORRUPTED: Contains analysis method text instead of endpoints"
            ))

            # Count valid endpoints
            endpoint_patterns = [
                r'remission', r'response', r'healing', r'mayo', r'score',
                r'change\s+from\s+baseline', r'improvement'
            ]
            endpoint_count = sum(1 for p in endpoint_patterns if re.search(p, section_text, re.I))

            score = min(endpoint_count * 10, 50)
            checks.append(ValidationResult(
                name="Number of Endpoints",
                passed=endpoint_count >= 5,
                score=score,
                status="PASS" if endpoint_count >= 5 else "PARTIAL" if endpoint_count >= 3 else "FAIL",
                message=f"Found {endpoint_count} endpoint-related terms"
            ))
        else:
            checks.append(ValidationResult(
                name="Endpoints Not Corrupted",
                passed=False,
                score=0,
                status="MISSING",
                message="Cannot check - section missing"
            ))
            checks.append(ValidationResult(
                name="Number of Endpoints",
                passed=False,
                score=0,
                status="MISSING",
                message="Cannot check - section missing"
            ))

        total = sum(c.score for c in checks)
        return SectionScore(name="Secondary Endpoints", score=total, max_score=100, checks=checks)

    def _validate_sample_size(self) -> SectionScore:
        """Validate Sample Size section"""
        checks = []

        # Check for sample size section
        has_section = bool(re.search(r'sample\s+size', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Sample Size Section",
            passed=has_section,
            score=15 if has_section else 0,
            status="PASS" if has_section else "FAIL",
            message="Sample size section found" if has_section else "Missing sample size section"
        ))

        # Check for power value
        power_match = re.search(r'(\d{2})%?\s*power', self.sap_text, re.I)
        power_value = int(power_match.group(1)) if power_match else None

        # Check against protocol if available
        expected_power = self.protocol_facts.get('power_values', [])
        if expected_power and power_value:
            highest_expected = max(int(p) for p in expected_power) if expected_power else 80
            power_correct = power_value >= highest_expected - 5  # Allow 5% tolerance
            checks.append(ValidationResult(
                name="Power Value",
                passed=power_correct,
                score=25 if power_correct else 10,
                status="PASS" if power_correct else "PARTIAL",
                message=f"Power: {power_value}%",
                expected=f"{highest_expected}%",
                actual=f"{power_value}%"
            ))
        else:
            checks.append(ValidationResult(
                name="Power Value",
                passed=power_value is not None,
                score=20 if power_value else 0,
                status="PASS" if power_value else "FAIL",
                message=f"Power: {power_value}%" if power_value else "Power not specified"
            ))

        # Check for alpha sidedness (should be one-sided for efficacy)
        has_one_sided = bool(re.search(r'one[- ]sided', self.sap_text, re.I))
        has_two_sided = bool(re.search(r'two[- ]sided', self.sap_text, re.I))

        # For efficacy trials, one-sided is typically correct
        alpha_correct = has_one_sided
        checks.append(ValidationResult(
            name="Alpha Sidedness",
            passed=alpha_correct,
            score=20 if alpha_correct else 5,
            status="PASS" if alpha_correct else "PARTIAL" if has_two_sided else "FAIL",
            message="One-sided alpha (correct for efficacy)" if has_one_sided else
                    "Two-sided alpha specified" if has_two_sided else "Alpha sidedness not specified",
            expected="one-sided (for efficacy trials)"
        ))

        # Check for expected response rates
        has_rates = bool(re.search(r'(?:expected|assumed)\s+(?:response\s+)?rate|(\d{1,2})%?\s*(?:vs\.?|versus)\s*(\d{1,2})%?', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Expected Response Rates",
            passed=has_rates,
            score=20 if has_rates else 0,
            status="PASS" if has_rates else "FAIL",
            message="Expected response rates specified" if has_rates else "Missing expected response rates"
        ))

        # Check for total N
        n_match = re.search(r'(?:total\s+of\s+)?(\d{2,4})\s*(?:patients?|subjects?)', self.sap_text, re.I)
        has_n = n_match is not None
        checks.append(ValidationResult(
            name="Total Sample Size",
            passed=has_n,
            score=20 if has_n else 0,
            status="PASS" if has_n else "FAIL",
            message=f"N = {n_match.group(1)}" if has_n else "Total N not specified"
        ))

        total = sum(c.score for c in checks)
        return SectionScore(name="Sample Size", score=total, max_score=100, checks=checks)

    def _validate_primary_analysis(self) -> SectionScore:
        """Validate Primary Analysis Method"""
        checks = []

        # Check for statistical methods section
        has_section = bool(re.search(r'statistical\s+methods?|primary\s+(?:efficacy\s+)?analysis', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Statistical Methods Section",
            passed=has_section,
            score=20 if has_section else 0,
            status="PASS" if has_section else "FAIL",
            message="Statistical methods section found" if has_section else "Missing statistical methods section"
        ))

        # Check analysis method matches endpoint type
        endpoint_type = self.protocol_facts.get('endpoint_type', 'binary')

        has_logistic = bool(re.search(r'logistic\s+regression', self.sap_text, re.I))
        has_ancova = bool(re.search(r'ANCOVA|analysis\s+of\s+covariance', self.sap_text, re.I))
        has_gee = bool(re.search(r'\bGEE\b|generalized\s+estimating', self.sap_text, re.I))

        if endpoint_type == 'binary':
            # For binary endpoints, Logistic Regression is preferred
            method_correct = has_logistic
            method_partial = has_gee or has_ancova  # GEE is acceptable, ANCOVA is wrong

            if method_correct:
                status = "PASS"
                score = 40
                message = "Logistic Regression (correct for binary endpoint)"
            elif has_gee:
                status = "PARTIAL"
                score = 25
                message = "GEE used (acceptable but protocol may specify Logistic Regression)"
            elif has_ancova:
                status = "FAIL"
                score = 0
                message = "ANCOVA used (WRONG for binary endpoint - use Logistic Regression)"
            else:
                status = "FAIL"
                score = 0
                message = "No appropriate analysis method found for binary endpoint"

            checks.append(ValidationResult(
                name="Analysis Method for Binary Endpoint",
                passed=method_correct,
                score=score,
                status=status,
                message=message,
                expected="Logistic Regression"
            ))
        else:
            # For continuous endpoints
            method_correct = has_ancova or bool(re.search(r'MMRM|mixed.+model', self.sap_text, re.I))
            checks.append(ValidationResult(
                name="Analysis Method for Continuous Endpoint",
                passed=method_correct,
                score=40 if method_correct else 0,
                status="PASS" if method_correct else "FAIL",
                message="ANCOVA/MMRM found" if method_correct else "Missing appropriate method for continuous endpoint",
                expected="ANCOVA or MMRM"
            ))

        # Check for model specification
        has_model = bool(re.search(r'model|equation|β|logit|covariate', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Model Specification",
            passed=has_model,
            score=20 if has_model else 0,
            status="PASS" if has_model else "FAIL",
            message="Model specification provided" if has_model else "Missing model specification"
        ))

        # Check for hypothesis
        has_hypothesis = bool(re.search(r'H[₀0]|H[₁1]|null\s+hypothesis|alternative', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Hypothesis Statement",
            passed=has_hypothesis,
            score=20 if has_hypothesis else 0,
            status="PASS" if has_hypothesis else "FAIL",
            message="Hypothesis stated" if has_hypothesis else "Missing hypothesis statement"
        ))

        total = sum(c.score for c in checks)
        return SectionScore(name="Primary Analysis", score=total, max_score=100, checks=checks)

    def _validate_missing_data(self) -> SectionScore:
        """Validate Missing Data Handling section"""
        checks = []

        # Check for missing data section
        has_section = bool(re.search(r'missing\s+data', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Missing Data Section",
            passed=has_section,
            score=30 if has_section else 0,
            status="PASS" if has_section else "FAIL",
            message="Missing data section found" if has_section else "Missing data section not found"
        ))

        # Check for imputation methods
        imputation_methods = ['LOCF', 'NRI', 'non-responder', 'imputation', 'MICE', 'MAR', 'MNAR']
        found_methods = [m for m in imputation_methods if re.search(m, self.sap_text, re.I)]

        checks.append(ValidationResult(
            name="Imputation Methods",
            passed=len(found_methods) >= 2,
            score=min(len(found_methods) * 15, 40),
            status="PASS" if len(found_methods) >= 2 else "PARTIAL" if found_methods else "FAIL",
            message=f"Methods: {', '.join(found_methods)}" if found_methods else "No imputation methods specified",
            details=found_methods
        ))

        # Check for sensitivity analyses
        has_sensitivity = bool(re.search(r'sensitivity\s+analy|tipping\s+point|pattern\s+mixture', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Sensitivity Analyses",
            passed=has_sensitivity,
            score=30 if has_sensitivity else 0,
            status="PASS" if has_sensitivity else "FAIL",
            message="Sensitivity analyses described" if has_sensitivity else "Missing sensitivity analyses"
        ))

        total = sum(c.score for c in checks)
        return SectionScore(name="Missing Data", score=total, max_score=100, checks=checks)

    def _validate_safety(self) -> SectionScore:
        """Validate Safety Analysis section"""
        checks = []

        # Check for safety section
        has_section = bool(re.search(r'safety\s+analysis', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Safety Section",
            passed=has_section,
            score=25 if has_section else 0,
            status="PASS" if has_section else "FAIL",
            message="Safety section found" if has_section else "Missing safety section"
        ))

        # Check for AE analysis
        ae_terms = ['TEAE', 'adverse event', 'SAE', 'serious adverse']
        found_ae = [t for t in ae_terms if re.search(t, self.sap_text, re.I)]
        checks.append(ValidationResult(
            name="Adverse Event Analysis",
            passed=len(found_ae) >= 2,
            score=25 if len(found_ae) >= 2 else 10 if found_ae else 0,
            status="PASS" if len(found_ae) >= 2 else "PARTIAL" if found_ae else "FAIL",
            message=f"AE terms: {', '.join(found_ae)}"
        ))

        # Check for MedDRA
        has_meddra = bool(re.search(r'MedDRA|SOC|preferred\s+term', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="MedDRA Coding",
            passed=has_meddra,
            score=25 if has_meddra else 0,
            status="PASS" if has_meddra else "FAIL",
            message="MedDRA coding mentioned" if has_meddra else "MedDRA not mentioned"
        ))

        # Check for lab/vitals
        has_labs = bool(re.search(r'laboratory|hematology|chemistry|vital\s+sign', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Laboratory/Vitals Analysis",
            passed=has_labs,
            score=25 if has_labs else 0,
            status="PASS" if has_labs else "FAIL",
            message="Lab/vitals analysis included" if has_labs else "Missing lab/vitals analysis"
        ))

        total = sum(c.score for c in checks)
        return SectionScore(name="Safety Analysis", score=total, max_score=100, checks=checks)

    def _validate_pk(self) -> SectionScore:
        """Validate PK Analysis section"""
        checks = []

        # Check for PK section
        has_section = bool(re.search(r'pharmacokinetic|PK\s+analysis', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="PK Section",
            passed=has_section,
            score=30 if has_section else 0,
            status="PASS" if has_section else "FAIL",
            message="PK section found" if has_section else "Missing PK section"
        ))

        if has_section:
            # Check for PK parameters
            pk_params = ['AUC', 'Cmax', 'tmax', 't½', 'half-life', 'clearance']
            found_params = [p for p in pk_params if re.search(p, self.sap_text, re.I)]
            checks.append(ValidationResult(
                name="PK Parameters",
                passed=len(found_params) >= 3,
                score=min(len(found_params) * 10, 35),
                status="PASS" if len(found_params) >= 3 else "PARTIAL" if found_params else "FAIL",
                message=f"Parameters: {', '.join(found_params)}"
            ))

            # Check for NCA mention
            has_nca = bool(re.search(r'non-compartmental|NCA|WinNonlin|Phoenix', self.sap_text, re.I))
            checks.append(ValidationResult(
                name="NCA Methodology",
                passed=has_nca,
                score=35 if has_nca else 0,
                status="PASS" if has_nca else "FAIL",
                message="NCA methodology mentioned" if has_nca else "Missing NCA methodology"
            ))
        else:
            checks.append(ValidationResult(
                name="PK Parameters",
                passed=False,
                score=0,
                status="MISSING",
                message="Cannot check - PK section missing"
            ))
            checks.append(ValidationResult(
                name="NCA Methodology",
                passed=False,
                score=0,
                status="MISSING",
                message="Cannot check - PK section missing"
            ))

        total = sum(c.score for c in checks)
        return SectionScore(name="PK Analysis", score=total, max_score=100, checks=checks)

    def _validate_subgroups(self) -> SectionScore:
        """Validate Subgroup Analysis section"""
        checks = []

        has_subgroup = bool(re.search(r'subgroup\s+analy', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Subgroup Analysis Section",
            passed=has_subgroup,
            score=40 if has_subgroup else 0,
            status="PASS" if has_subgroup else "FAIL",
            message="Subgroup analysis described" if has_subgroup else "Missing subgroup analysis"
        ))

        # Check for specific subgroups
        subgroups = ['age', 'sex', 'gender', 'region', 'baseline', 'prior', 'IL-6', 'biomarker']
        found = [s for s in subgroups if re.search(s, self.sap_text, re.I)]

        checks.append(ValidationResult(
            name="Subgroup Factors",
            passed=len(found) >= 3,
            score=min(len(found) * 10, 60),
            status="PASS" if len(found) >= 3 else "PARTIAL" if found else "FAIL",
            message=f"Subgroups: {', '.join(found)}"
        ))

        total = sum(c.score for c in checks)
        return SectionScore(name="Subgroup Analysis", score=total, max_score=100, checks=checks)

    def _validate_multiplicity(self) -> SectionScore:
        """Validate Multiplicity Adjustment section"""
        checks = []

        has_multiplicity = bool(re.search(r'multiplic|hierarchical|gate[- ]?keep|family[- ]?wise|bonferroni|hochberg|holm', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Multiplicity Adjustment",
            passed=has_multiplicity,
            score=60 if has_multiplicity else 0,
            status="PASS" if has_multiplicity else "FAIL",
            message="Multiplicity adjustment described" if has_multiplicity else "Missing multiplicity adjustment"
        ))

        # Check for testing hierarchy
        has_hierarchy = bool(re.search(r'priority|order|first.*then|sequential', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Testing Hierarchy",
            passed=has_hierarchy,
            score=40 if has_hierarchy else 0,
            status="PASS" if has_hierarchy else "FAIL",
            message="Testing hierarchy specified" if has_hierarchy else "Missing testing hierarchy"
        ))

        total = sum(c.score for c in checks)
        return SectionScore(name="Multiplicity", score=total, max_score=100, checks=checks)

    def _validate_visit_windows(self) -> SectionScore:
        """Validate Visit Windows section"""
        checks = []

        has_windows = bool(re.search(r'visit\s+window|±\s*\d+\s*day|day\s+\d+\s*±', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Visit Windows Defined",
            passed=has_windows,
            score=100 if has_windows else 0,
            status="PASS" if has_windows else "FAIL",
            message="Visit windows specified" if has_windows else "Missing visit windows"
        ))

        return SectionScore(name="Visit Windows", score=100 if has_windows else 0, max_score=100, checks=checks)

    def _validate_biomarkers(self) -> SectionScore:
        """Validate Biomarker section"""
        checks = []

        biomarkers = ['ESR', 'CRP', 'IL-6', 'calprotectin', 'biomarker']
        found = [b for b in biomarkers if re.search(b, self.sap_text, re.I)]

        has_biomarkers = len(found) >= 1
        checks.append(ValidationResult(
            name="Biomarker Endpoints",
            passed=has_biomarkers,
            score=min(len(found) * 25, 100),
            status="PASS" if len(found) >= 2 else "PARTIAL" if found else "FAIL",
            message=f"Biomarkers: {', '.join(found)}" if found else "No biomarkers mentioned"
        ))

        return SectionScore(name="Biomarkers", score=min(len(found) * 25, 100), max_score=100, checks=checks)

    def _validate_treatment_arms(self) -> SectionScore:
        """Validate Treatment Arms specification"""
        checks = []

        # Check for specific doses (not just "high dose", "low dose")
        dose_patterns = [
            r'\d+\s*(?:mg|mcg|g)',  # Specific doses like "600 mg"
            r'Q\d+W|every\s+\d+\s+weeks?',  # Dosing schedule
        ]

        has_specific_dose = any(re.search(p, self.sap_text, re.I) for p in dose_patterns)

        # Check for generic arm names (bad)
        generic_patterns = [
            r'(?:in\s+)?high\s+dose',
            r'(?:in\s+)?low\s+dose',
            r'treatment\s+arm\s+\d+',
        ]
        has_generic = any(re.search(p, self.sap_text, re.I) for p in generic_patterns)

        if has_specific_dose and not has_generic:
            score = 100
            status = "PASS"
            message = "Specific doses specified (e.g., 600 mg, 300 mg)"
        elif has_specific_dose and has_generic:
            score = 70
            status = "PARTIAL"
            message = "Mix of specific and generic arm names"
        elif has_generic:
            score = 40
            status = "FAIL"
            message = "Only generic arm names (e.g., 'high dose') - should specify actual doses"
        else:
            score = 0
            status = "FAIL"
            message = "No treatment arm specifications found"

        checks.append(ValidationResult(
            name="Treatment Arm Specification",
            passed=score >= 70,
            score=score,
            status=status,
            message=message
        ))

        # Check for placebo
        has_placebo = bool(re.search(r'placebo', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Placebo Arm",
            passed=has_placebo,
            score=0,  # Already included in main score
            status="PASS" if has_placebo else "FAIL",
            message="Placebo arm mentioned" if has_placebo else "Placebo not mentioned"
        ))

        return SectionScore(name="Treatment Arms", score=score, max_score=100, checks=checks)

    def _validate_immunogenicity(self) -> SectionScore:
        """Validate Immunogenicity section"""
        checks = []

        # Check for immunogenicity section
        has_section = bool(re.search(r'immunogenicity|anti[- ]drug\s+antibod|ADA', self.sap_text, re.I))
        checks.append(ValidationResult(
            name="Immunogenicity Section",
            passed=has_section,
            score=30 if has_section else 0,
            status="PASS" if has_section else "FAIL",
            message="Immunogenicity section found" if has_section else "Missing immunogenicity section"
        ))

        if has_section:
            # Check for classification
            classifications = ['treatment-emergent', 'persistent', 'transient', 'baseline']
            found_class = [c for c in classifications if re.search(c, self.sap_text, re.I)]
            checks.append(ValidationResult(
                name="ADA Classification",
                passed=len(found_class) >= 2,
                score=min(len(found_class) * 15, 40),
                status="PASS" if len(found_class) >= 2 else "PARTIAL" if found_class else "FAIL",
                message=f"Classifications: {', '.join(found_class)}" if found_class else "No ADA classifications"
            ))

            # Check for NAb
            has_nab = bool(re.search(r'neutralizing|NAb', self.sap_text, re.I))
            checks.append(ValidationResult(
                name="Neutralizing Antibodies",
                passed=has_nab,
                score=30 if has_nab else 0,
                status="PASS" if has_nab else "FAIL",
                message="NAb assessment included" if has_nab else "NAb assessment missing"
            ))
        else:
            checks.append(ValidationResult(
                name="ADA Classification",
                passed=False,
                score=0,
                status="MISSING",
                message="Cannot check - section missing"
            ))
            checks.append(ValidationResult(
                name="Neutralizing Antibodies",
                passed=False,
                score=0,
                status="MISSING",
                message="Cannot check - section missing"
            ))

        total = sum(c.score for c in checks)
        return SectionScore(name="Immunogenicity", score=total, max_score=100, checks=checks)

    def generate_report(self) -> str:
        """Generate a formatted validation report"""
        if not self.results:
            self.validate_all()

        lines = []
        lines.append("=" * 70)
        lines.append("SAP VALIDATION REPORT")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 70)
        lines.append("")

        # Overall score
        lines.append(f"OVERALL SCORE: {self.overall_score}%")
        lines.append("")

        # Score bar
        filled = int(self.overall_score / 5)
        bar = "█" * filled + "░" * (20 - filled)
        lines.append(f"[{bar}] {self.overall_score}/100")
        lines.append("")

        # Summary table
        lines.append("-" * 70)
        lines.append(f"{'Section':<30} {'Score':<10} {'Status':<15}")
        lines.append("-" * 70)

        for name, section in self.results.items():
            status = "✅" if section.percentage >= 80 else "⚠️" if section.percentage >= 50 else "❌"
            lines.append(f"{section.name:<30} {section.score}/{section.max_score:<6} {status} {section.percentage:.0f}%")

        lines.append("-" * 70)
        lines.append("")

        # Detailed results
        lines.append("DETAILED RESULTS")
        lines.append("=" * 70)

        for name, section in self.results.items():
            lines.append("")
            status_icon = "✅" if section.percentage >= 80 else "⚠️" if section.percentage >= 50 else "❌"
            lines.append(f"### {section.name} ({section.score}/{section.max_score}) {status_icon}")
            lines.append("")

            for check in section.checks:
                icon = "✓" if check.status == "PASS" else "◐" if check.status == "PARTIAL" else "✗"
                lines.append(f"  {icon} {check.name}: {check.message}")
                if check.expected and check.actual:
                    lines.append(f"      Expected: {check.expected}")
                    lines.append(f"      Actual: {check.actual}")
                if check.details:
                    for detail in check.details[:5]:
                        lines.append(f"      {detail}")

        # Issues summary
        lines.append("")
        lines.append("=" * 70)
        lines.append("ISSUES REQUIRING ATTENTION")
        lines.append("=" * 70)

        critical = []
        warnings = []

        for name, section in self.results.items():
            for check in section.checks:
                if check.status == "FAIL":
                    critical.append(f"[{section.name}] {check.name}: {check.message}")
                elif check.status == "PARTIAL":
                    warnings.append(f"[{section.name}] {check.name}: {check.message}")

        if critical:
            lines.append("")
            lines.append("🔴 CRITICAL ISSUES:")
            for issue in critical:
                lines.append(f"   • {issue}")

        if warnings:
            lines.append("")
            lines.append("🟡 WARNINGS:")
            for issue in warnings:
                lines.append(f"   • {issue}")

        if not critical and not warnings:
            lines.append("")
            lines.append("🟢 No critical issues found!")

        lines.append("")
        lines.append("=" * 70)
        lines.append("END OF VALIDATION REPORT")
        lines.append("=" * 70)

        return "\n".join(lines)

    def get_json_report(self) -> Dict:
        """Get validation results as JSON-serializable dict"""
        if not self.results:
            self.validate_all()

        return {
            'overall_score': self.overall_score,
            'timestamp': datetime.now().isoformat(),
            'sections': {
                name: {
                    'name': section.name,
                    'score': section.score,
                    'max_score': section.max_score,
                    'percentage': section.percentage,
                    'checks': [
                        {
                            'name': check.name,
                            'passed': check.passed,
                            'score': check.score,
                            'status': check.status,
                            'message': check.message,
                            'expected': check.expected,
                            'actual': check.actual,
                        }
                        for check in section.checks
                    ]
                }
                for name, section in self.results.items()
            }
        }


def find_latest_sap(output_dir: str = "output") -> Optional[str]:
    """Find the most recently generated SAP file"""
    output_path = Path(output_dir)
    if not output_path.exists():
        return None

    sap_files = list(output_path.glob("**/sap*.md")) + list(output_path.glob("**/sap*.txt")) + list(output_path.glob("**/*sap*.md"))

    if not sap_files:
        return None

    # Sort by modification time
    sap_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(sap_files[0])


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Validate a generated SAP")
    parser.add_argument('sap_file', nargs='?', help="Path to SAP file")
    parser.add_argument('protocol_file', nargs='?', help="Path to protocol file (optional)")
    parser.add_argument('--latest', action='store_true', help="Validate most recent SAP in output/")
    parser.add_argument('--json', action='store_true', help="Output as JSON")
    parser.add_argument('--output', '-o', help="Output file path")

    args = parser.parse_args()

    # Find SAP file
    sap_file = args.sap_file
    if args.latest or not sap_file:
        sap_file = find_latest_sap()
        if not sap_file:
            print("Error: No SAP file found. Specify a file or use --latest with SAPs in output/")
            sys.exit(1)
        print(f"Using: {sap_file}")

    # Read files
    try:
        with open(sap_file, 'r', encoding='utf-8') as f:
            sap_text = f.read()
    except Exception as e:
        print(f"Error reading SAP file: {e}")
        sys.exit(1)

    protocol_text = None
    if args.protocol_file:
        try:
            with open(args.protocol_file, 'r', encoding='utf-8') as f:
                protocol_text = f.read()
        except Exception as e:
            print(f"Warning: Could not read protocol file: {e}")

    # Validate
    validator = SAPValidator(sap_text, protocol_text)
    validator.validate_all()

    # Output
    if args.json:
        output = json.dumps(validator.get_json_report(), indent=2)
    else:
        output = validator.generate_report()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    # Exit with appropriate code
    sys.exit(0 if validator.overall_score >= 80 else 1)


if __name__ == "__main__":
    main()
