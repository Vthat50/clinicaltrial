#!/usr/bin/env python3
"""
Contamination Guard for SAP Generation
=======================================
Prevents cross-protocol contamination where content from one study
appears in the SAP for a different study.

This solves:
- Drug name contamination (etrolizumab appearing in TJ301 SAP)
- Sample size hallucination (1150 when protocol says 90)
- Study ID mismatches
- Endpoint contamination from different therapeutic areas
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field


@dataclass
class ProtocolIdentity:
    """Core identity elements extracted from protocol."""
    nct_id: str = ""
    drug_name: str = ""
    drug_names_all: List[str] = field(default_factory=list)
    sponsor: str = ""
    indication: str = ""
    therapeutic_area: str = ""
    sample_size: int = 0
    num_arms: int = 0
    phase: str = ""


@dataclass
class ContaminationReport:
    """Report of contamination found in generated SAP."""
    is_contaminated: bool = False
    contamination_sources: List[str] = field(default_factory=list)
    wrong_drug_names: List[str] = field(default_factory=list)
    wrong_sample_sizes: List[int] = field(default_factory=list)
    wrong_study_ids: List[str] = field(default_factory=list)
    severity: str = "none"  # none, low, medium, high, critical


class ProtocolIdentityExtractor:
    """
    Extracts the core identity of a protocol.
    These elements MUST match in the generated SAP.
    """

    # Known drug names that might contaminate (from RAG examples)
    KNOWN_DRUG_NAMES = [
        'etrolizumab', 'vedolizumab', 'ustekinumab', 'adalimumab',
        'infliximab', 'golimumab', 'tofacitinib', 'filgotinib',
        'ozanimod', 'risankizumab', 'mirikizumab', 'guselkumab',
        'etrasimod', 'obefazimod', 'ontamalimab', 'brazikumab',
        'tj301', 'olamkicept', 'pf-06480605', 'pf-00547659'
    ]

    # Patterns to extract NCT ID
    NCT_PATTERNS = [
        r'NCT\d{8}',
        r'NCT[-\s]?\d{8}',
    ]

    # Patterns to extract drug name
    DRUG_PATTERNS = [
        r'(?:study\s+drug|investigational\s+(?:drug|product)|IMP)[:\s]+(\w+)',
        r'(\w+)\s+(?:will\s+be\s+)?(?:administered|given|infused)',
        r'receive\s+(?:\d+\s*mg\s+)?(\w+)',
    ]

    def extract_identity(self, protocol_text: str) -> ProtocolIdentity:
        """Extract core identity from protocol."""
        identity = ProtocolIdentity()

        # Extract NCT ID
        for pattern in self.NCT_PATTERNS:
            match = re.search(pattern, protocol_text, re.IGNORECASE)
            if match:
                identity.nct_id = match.group(0).upper().replace(' ', '').replace('-', '')
                break

        # Extract drug names
        identity.drug_names_all = self._extract_drug_names(protocol_text)
        if identity.drug_names_all:
            identity.drug_name = identity.drug_names_all[0]

        # Extract sample size
        sample_match = re.search(
            r'(\d+)\s+(?:patients?|subjects?)\s+will\s+be\s+(?:enrolled|randomized)',
            protocol_text,
            re.IGNORECASE
        )
        if sample_match:
            identity.sample_size = int(sample_match.group(1))

        # Extract number of arms
        ratio_match = re.search(r'(\d+:\d+(?::\d+)?)', protocol_text)
        if ratio_match:
            identity.num_arms = len(ratio_match.group(1).split(':'))

        arms_match = re.search(
            r'(?:randomized?\s+to|assigned\s+to)\s+(\d+)\s+(?:groups?|arms?)',
            protocol_text,
            re.IGNORECASE
        )
        if arms_match:
            identity.num_arms = max(identity.num_arms, int(arms_match.group(1)))

        # Extract indication
        indication_patterns = [
            r'(?:patients?\s+with|diagnosis\s+of|treatment\s+of)\s+([\w\s\'-]+(?:disease|colitis|syndrome|disorder))',
            r'(ulcerative\s+colitis|crohn\'?s?\s+disease|inflammatory\s+bowel)',
        ]
        for pattern in indication_patterns:
            match = re.search(pattern, protocol_text, re.IGNORECASE)
            if match:
                identity.indication = match.group(1).strip()
                break

        # Determine therapeutic area
        if re.search(r'ulcerative\s+colitis|crohn|IBD|inflammatory\s+bowel', protocol_text, re.IGNORECASE):
            identity.therapeutic_area = "IBD"
        elif re.search(r'cancer|tumor|oncology|carcinoma', protocol_text, re.IGNORECASE):
            identity.therapeutic_area = "Oncology"
        elif re.search(r'rheumatoid|arthritis|lupus', protocol_text, re.IGNORECASE):
            identity.therapeutic_area = "Rheumatology"

        return identity

    def _extract_drug_names(self, protocol_text: str) -> List[str]:
        """Extract all drug names mentioned in protocol."""
        drug_names = []

        # Look for known drug names
        for drug in self.KNOWN_DRUG_NAMES:
            if re.search(rf'\b{drug}\b', protocol_text, re.IGNORECASE):
                drug_names.append(drug.lower())

        # Look for code names (e.g., TJ301, PF-06480605)
        code_matches = re.findall(
            r'\b([A-Z]{2,3}[-\s]?\d{3,8})\b',
            protocol_text
        )
        for code in code_matches:
            code_clean = code.replace(' ', '').replace('-', '').upper()
            if code_clean not in [d.upper() for d in drug_names]:
                drug_names.append(code_clean)

        return list(set(drug_names))


class ContaminationDetector:
    """
    Detects contamination in generated SAP.
    Checks if content from other protocols has leaked into the SAP.
    """

    # Drug names that indicate contamination if found but not in protocol
    CONTAMINATION_INDICATORS = {
        'etrolizumab': 'Roche UC study',
        'vedolizumab': 'Entyvio',
        'ustekinumab': 'Stelara',
        'adalimumab': 'Humira',
        'infliximab': 'Remicade',
        'tofacitinib': 'Xeljanz',
        'filgotinib': 'Jyseleca',
        'ozanimod': 'Zeposia',
        'risankizumab': 'Skyrizi',
        'cohort 3': 'Multi-cohort study contamination',
        'cohort 2': 'Multi-cohort study contamination',
    }

    def __init__(self, identity_extractor: ProtocolIdentityExtractor):
        self.identity_extractor = identity_extractor

    def detect_contamination(
        self,
        sap_text: str,
        protocol_identity: ProtocolIdentity
    ) -> ContaminationReport:
        """
        Check SAP for contamination from other protocols.
        """
        report = ContaminationReport()

        # Check for wrong drug names
        wrong_drugs = self._check_wrong_drugs(sap_text, protocol_identity)
        if wrong_drugs:
            report.wrong_drug_names = wrong_drugs
            report.is_contaminated = True
            for drug in wrong_drugs:
                source = self.CONTAMINATION_INDICATORS.get(drug.lower(), f"Unknown study with {drug}")
                report.contamination_sources.append(source)

        # Check for wrong sample sizes
        wrong_sizes = self._check_wrong_sample_sizes(sap_text, protocol_identity)
        if wrong_sizes:
            report.wrong_sample_sizes = wrong_sizes
            report.is_contaminated = True

        # Check for wrong study IDs
        wrong_ids = self._check_wrong_study_ids(sap_text, protocol_identity)
        if wrong_ids:
            report.wrong_study_ids = wrong_ids
            report.is_contaminated = True

        # Determine severity
        if report.wrong_drug_names:
            report.severity = "critical"
        elif report.wrong_sample_sizes and any(abs(s - protocol_identity.sample_size) > 100 for s in report.wrong_sample_sizes):
            report.severity = "critical"
        elif report.wrong_sample_sizes:
            report.severity = "high"
        elif report.wrong_study_ids:
            report.severity = "medium"
        elif report.is_contaminated:
            report.severity = "low"

        return report

    def _check_wrong_drugs(self, sap_text: str, identity: ProtocolIdentity) -> List[str]:
        """Check for drug names that shouldn't be in the SAP."""
        wrong_drugs = []
        protocol_drugs = set(d.lower() for d in identity.drug_names_all)

        for drug, source in self.CONTAMINATION_INDICATORS.items():
            if drug.lower() not in protocol_drugs:
                if re.search(rf'\b{drug}\b', sap_text, re.IGNORECASE):
                    wrong_drugs.append(drug)

        return wrong_drugs

    def _check_wrong_sample_sizes(self, sap_text: str, identity: ProtocolIdentity) -> List[int]:
        """Check for sample sizes that don't match protocol."""
        wrong_sizes = []

        if identity.sample_size == 0:
            return wrong_sizes

        # Find all sample size mentions in SAP
        size_matches = re.findall(
            r'(\d+)\s+(?:patients?|subjects?|participants?)',
            sap_text,
            re.IGNORECASE
        )

        for match in size_matches:
            size = int(match)
            # Allow some tolerance (within 20% or ±10)
            if size > 50:  # Only check substantial numbers
                tolerance = max(identity.sample_size * 0.2, 10)
                if abs(size - identity.sample_size) > tolerance:
                    # Check if it's a per-arm size
                    per_arm = identity.sample_size // max(identity.num_arms, 1)
                    if abs(size - per_arm) > tolerance:
                        wrong_sizes.append(size)

        return list(set(wrong_sizes))

    def _check_wrong_study_ids(self, sap_text: str, identity: ProtocolIdentity) -> List[str]:
        """Check for NCT IDs that don't match protocol."""
        wrong_ids = []

        if not identity.nct_id:
            return wrong_ids

        # Find all NCT IDs in SAP
        nct_matches = re.findall(r'NCT\d{8}', sap_text, re.IGNORECASE)

        for nct_id in nct_matches:
            nct_clean = nct_id.upper()
            if nct_clean != identity.nct_id:
                wrong_ids.append(nct_clean)

        return list(set(wrong_ids))


class ContaminationCleaner:
    """
    Cleans contamination from generated SAP.
    Removes or replaces contaminated content.
    """

    def __init__(self, detector: ContaminationDetector):
        self.detector = detector

    def clean_sap(
        self,
        sap_text: str,
        protocol_identity: ProtocolIdentity,
        contamination_report: ContaminationReport
    ) -> Tuple[str, List[str]]:
        """
        Clean contamination from SAP.

        Returns:
            Tuple of (cleaned_text, list of changes made)
        """
        changes = []
        cleaned = sap_text

        # Replace wrong drug names with correct drug name
        if contamination_report.wrong_drug_names and protocol_identity.drug_name:
            for wrong_drug in contamination_report.wrong_drug_names:
                pattern = rf'\b{wrong_drug}\b'
                if re.search(pattern, cleaned, re.IGNORECASE):
                    cleaned = re.sub(pattern, protocol_identity.drug_name, cleaned, flags=re.IGNORECASE)
                    changes.append(f"Replaced '{wrong_drug}' with '{protocol_identity.drug_name}'")

        # Replace wrong sample sizes with protocol sample size
        if contamination_report.wrong_sample_sizes and protocol_identity.sample_size > 0:
            for wrong_size in contamination_report.wrong_sample_sizes:
                # Be careful not to replace valid numbers
                pattern = rf'\b{wrong_size}\s+(patients?|subjects?|participants?)'
                replacement = f"{protocol_identity.sample_size} \\1"
                if re.search(pattern, cleaned, re.IGNORECASE):
                    cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
                    changes.append(f"Replaced sample size {wrong_size} with {protocol_identity.sample_size}")

        # Replace wrong NCT IDs
        if contamination_report.wrong_study_ids and protocol_identity.nct_id:
            for wrong_id in contamination_report.wrong_study_ids:
                if wrong_id in cleaned:
                    cleaned = cleaned.replace(wrong_id, protocol_identity.nct_id)
                    changes.append(f"Replaced study ID {wrong_id} with {protocol_identity.nct_id}")

        # Remove cohort contamination language
        cohort_patterns = [
            r'Cohort\s+\d+[^.]*\.',
            r'For\s+Cohort\s+\d+[^.]*\.',
            r'In\s+Cohort\s+\d+[^.]*\.',
        ]
        for pattern in cohort_patterns:
            if re.search(pattern, cleaned, re.IGNORECASE):
                cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
                changes.append("Removed cohort-specific contamination")

        return cleaned, changes


class ContaminationGuard:
    """
    Main interface for contamination protection.
    Use this in the orchestrator pipeline.
    """

    def __init__(self):
        self.identity_extractor = ProtocolIdentityExtractor()
        self.detector = ContaminationDetector(self.identity_extractor)
        self.cleaner = ContaminationCleaner(self.detector)

    def extract_protocol_identity(self, protocol_text: str) -> ProtocolIdentity:
        """Extract identity from protocol."""
        return self.identity_extractor.extract_identity(protocol_text)

    def check_and_clean(
        self,
        sap_text: str,
        protocol_text: str
    ) -> Tuple[str, ContaminationReport, List[str]]:
        """
        Check SAP for contamination and clean if found.

        Args:
            sap_text: Generated SAP text
            protocol_text: Original protocol text

        Returns:
            Tuple of (cleaned_sap, contamination_report, changes_made)
        """
        # Extract protocol identity
        identity = self.identity_extractor.extract_identity(protocol_text)

        # Detect contamination
        report = self.detector.detect_contamination(sap_text, identity)

        # Clean if contaminated
        changes = []
        cleaned_sap = sap_text

        if report.is_contaminated:
            cleaned_sap, changes = self.cleaner.clean_sap(sap_text, identity, report)

        return cleaned_sap, report, changes

    def validate_sap_identity(
        self,
        sap_text: str,
        protocol_identity: ProtocolIdentity
    ) -> Dict[str, Any]:
        """
        Validate that SAP matches protocol identity.

        Returns dict with validation results.
        """
        results = {
            'valid': True,
            'issues': [],
            'protocol_identity': {
                'nct_id': protocol_identity.nct_id,
                'drug_name': protocol_identity.drug_name,
                'sample_size': protocol_identity.sample_size,
                'num_arms': protocol_identity.num_arms,
            }
        }

        # Check NCT ID appears in SAP
        if protocol_identity.nct_id:
            if protocol_identity.nct_id not in sap_text:
                results['valid'] = False
                results['issues'].append(f"NCT ID {protocol_identity.nct_id} not found in SAP")

        # Check drug name appears in SAP
        if protocol_identity.drug_name:
            if not re.search(rf'\b{protocol_identity.drug_name}\b', sap_text, re.IGNORECASE):
                results['valid'] = False
                results['issues'].append(f"Drug name {protocol_identity.drug_name} not found in SAP")

        # Check sample size mentioned correctly
        if protocol_identity.sample_size > 0:
            if str(protocol_identity.sample_size) not in sap_text:
                results['valid'] = False
                results['issues'].append(f"Sample size {protocol_identity.sample_size} not found in SAP")

        return results
