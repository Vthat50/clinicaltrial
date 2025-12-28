#!/usr/bin/env python3
"""
Contamination Guard for SAP Generation
=======================================
Prevents cross-protocol contamination where content from one study
appears in the SAP for a different study.

PROTOCOL-AGNOSTIC: Works with ANY therapeutic area (IBD, oncology, cardiology, etc.)
by dynamically extracting drug names from the protocol rather than hardcoded lists.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field


@dataclass
class ProtocolIdentity:
    """Core identity elements extracted from protocol."""
    nct_id: str = ""
    study_id: str = ""  # Internal study ID (e.g., CTJ301UC201)
    drug_name: str = ""
    drug_names_all: List[str] = field(default_factory=list)
    sponsor: str = ""
    indication: str = ""
    therapeutic_area: str = ""
    sample_size: int = 0
    num_arms: int = 0
    phase: str = ""
    # Store all extracted identifiers for contamination checking
    all_identifiers: Set[str] = field(default_factory=set)


@dataclass
class ContaminationReport:
    """Report of contamination found in generated SAP."""
    is_contaminated: bool = False
    contamination_sources: List[str] = field(default_factory=list)
    wrong_drug_names: List[str] = field(default_factory=list)
    wrong_sample_sizes: List[int] = field(default_factory=list)
    wrong_study_ids: List[str] = field(default_factory=list)
    foreign_drugs_in_sap: List[str] = field(default_factory=list)
    severity: str = "none"  # none, low, medium, high, critical


class ProtocolIdentityExtractor:
    """
    Extracts the core identity of a protocol.
    PROTOCOL-AGNOSTIC: Works with any therapeutic area.
    """

    # Generic patterns for drug/compound names (works across all therapeutic areas)
    DRUG_PATTERNS = [
        # Investigational product statements
        r'(?:investigational\s+(?:product|drug|compound|agent)|IMP|study\s+drug)[:\s]+([A-Za-z][A-Za-z0-9-]{2,})',
        # "X will be administered/given"
        r'([A-Z][a-z]+(?:mab|nib|lib|zumab|ximab|tinib|ciclib|rafenib|lizumab|cillin|mycin|statin|pril|sartan|olol|dipine|azole|prazole|setron|gliptin|glutide|parib|platin))\s+(?:will\s+be\s+)?(?:administered|given|infused|dosed)',
        # Drug code patterns (universal: XX-123456, XXX123, etc.)
        r'\b([A-Z]{2,4}[-\s]?\d{4,8})\b',
        # Generic name patterns (biologics ending in -mab, -nib, etc.)
        r'\b([A-Za-z]+(?:mab|nib|lib|tinib|ciclib|rafenib|cillin|mycin|statin|pril|sartan|olol|dipine|azole|prazole|setron|gliptin|glutide|parib|platin))\b',
    ]

    # Study ID patterns
    STUDY_ID_PATTERNS = [
        r'NCT\d{8}',
        r'NCT[-\s]?\d{8}',
        r'EudraCT\s*\d{4}-\d{6}-\d{2}',
        r'\b([A-Z]{2,5}\d{3,4}[A-Z]{0,3}\d{0,3})\b',  # Internal IDs like CTJ301UC201
    ]

    # Sample size patterns (universal)
    SAMPLE_SIZE_PATTERNS = [
        r'(?:approximately\s+)?(\d+)\s+(?:patients?|subjects?|participants?)\s+(?:will\s+be\s+)?(?:enrolled|randomized|recruited)',
        r'(?:enroll|randomize|recruit)\s+(?:approximately\s+)?(\d+)\s+(?:patients?|subjects?|participants?)',
        r'sample\s+size[:\s]+(?:approximately\s+)?(\d+)',
        r'(?:total\s+of\s+)?(\d+)\s+(?:patients?|subjects?)\s+(?:are\s+)?(?:planned|expected)',
        r'N\s*[=:]\s*(\d+)',
    ]

    # Therapeutic area detection (expanded)
    THERAPEUTIC_AREA_PATTERNS = {
        'IBD': r'ulcerative\s+colitis|crohn|IBD|inflammatory\s+bowel',
        'Oncology': r'cancer|tumor|oncology|carcinoma|lymphoma|leukemia|melanoma|sarcoma|metastatic|neoplasm',
        'Cardiology': r'heart\s+failure|cardiac|cardiovascular|myocardial|atrial|ventricular|hypertension|arrhythmia',
        'Neurology': r'alzheimer|parkinson|multiple\s+sclerosis|epilepsy|stroke|dementia|neuropathy|migraine',
        'Rheumatology': r'rheumatoid|arthritis|lupus|psoriatic|ankylosing|spondylitis|fibromyalgia',
        'Dermatology': r'psoriasis|atopic\s+dermatitis|eczema|acne|rosacea|vitiligo',
        'Pulmonology': r'asthma|COPD|pulmonary|respiratory|lung\s+disease|bronchitis',
        'Endocrinology': r'diabetes|thyroid|adrenal|pituitary|metabolic|obesity',
        'Infectious': r'HIV|hepatitis|infection|bacterial|viral|fungal|antibiotic',
        'Hematology': r'anemia|thrombocytopenia|hemophilia|blood\s+disorder|coagulation',
        'Ophthalmology': r'macular|retinal|glaucoma|uveitis|dry\s+eye|ophthalmic',
        'Nephrology': r'kidney|renal|dialysis|nephropathy|glomerular',
        'Gastroenterology': r'GERD|liver|hepatic|cirrhosis|pancreatitis|gastroparesis',
    }

    def extract_identity(self, protocol_text: str) -> ProtocolIdentity:
        """Extract core identity from protocol - works with ANY therapeutic area."""
        identity = ProtocolIdentity()

        # Extract NCT ID
        nct_match = re.search(r'NCT\d{8}', protocol_text, re.IGNORECASE)
        if nct_match:
            identity.nct_id = nct_match.group(0).upper()
            identity.all_identifiers.add(identity.nct_id)

        # Extract internal study ID
        study_id_match = re.search(r'\b([A-Z]{2,5}\d{3,4}[A-Z]{0,3}\d{0,3})\b', protocol_text)
        if study_id_match:
            identity.study_id = study_id_match.group(1)
            identity.all_identifiers.add(identity.study_id)

        # Extract drug names dynamically
        identity.drug_names_all = self._extract_drug_names_dynamic(protocol_text)
        if identity.drug_names_all:
            identity.drug_name = identity.drug_names_all[0]
            for drug in identity.drug_names_all:
                identity.all_identifiers.add(drug.lower())

        # Extract sample size
        identity.sample_size = self._extract_sample_size(protocol_text)

        # Extract number of arms
        identity.num_arms = self._extract_num_arms(protocol_text)

        # Extract phase
        phase_match = re.search(r'phase\s*([1-4]|I{1,3}V?|one|two|three|four)', protocol_text, re.IGNORECASE)
        if phase_match:
            identity.phase = phase_match.group(1)

        # Detect therapeutic area
        identity.therapeutic_area = self._detect_therapeutic_area(protocol_text)

        # Extract indication
        identity.indication = self._extract_indication(protocol_text)

        return identity

    def _extract_drug_names_dynamic(self, protocol_text: str) -> List[str]:
        """Dynamically extract drug names from ANY protocol."""
        drug_names = set()

        # Pattern 1: Look for investigational product/drug declarations
        imp_patterns = [
            r'(?:investigational\s+(?:product|drug|medicinal\s+product)|IMP|study\s+drug)[:\s]+([A-Za-z][A-Za-z0-9-]{2,})',
            r'(?:active\s+(?:treatment|drug|compound))[:\s]+([A-Za-z][A-Za-z0-9-]{2,})',
        ]
        for pattern in imp_patterns:
            matches = re.findall(pattern, protocol_text, re.IGNORECASE)
            for match in matches:
                if len(match) > 2 and not match.lower() in ['the', 'and', 'for', 'with', 'will', 'are', 'was']:
                    drug_names.add(match.lower())

        # Pattern 2: Drug codes (XX-123456, XXX123, etc.)
        code_patterns = [
            r'\b([A-Z]{2,4}[-]?\d{5,8})\b',  # PF-06480605
            r'\b([A-Z]{2,3}\d{3,4})\b',  # TJ301
        ]
        for pattern in code_patterns:
            matches = re.findall(pattern, protocol_text)
            for match in matches:
                # Filter out common non-drug codes
                if not re.match(r'^(NCT|EUR|IND|NDA|BLA)\d', match, re.IGNORECASE):
                    drug_names.add(match.upper())

        # Pattern 3: Biologic drug suffixes (-mab, -nib, etc.)
        biologic_pattern = r'\b([A-Za-z]{4,}(?:mab|nib|lib|zumab|ximab|tinib|ciclib|rafenib|lizumab))\b'
        matches = re.findall(biologic_pattern, protocol_text, re.IGNORECASE)
        for match in matches:
            drug_names.add(match.lower())

        # Pattern 4: Small molecule suffixes
        small_mol_pattern = r'\b([A-Za-z]{4,}(?:cillin|mycin|statin|pril|sartan|olol|dipine|azole|prazole|setron|gliptin|glutide|parib|platin))\b'
        matches = re.findall(small_mol_pattern, protocol_text, re.IGNORECASE)
        for match in matches:
            drug_names.add(match.lower())

        # Pattern 5: Context-based extraction ("X vs placebo", "X arm", "receive X")
        context_patterns = [
            r'(\b[A-Z][a-z]+(?:[A-Z][a-z]+)?\b)\s+(?:versus|vs\.?|or)\s+placebo',
            r'(\b[A-Z][a-z]+(?:[A-Z][a-z]+)?\b)\s+(?:arm|group|treatment)',
            r'receive\s+(?:\d+\s*(?:mg|mcg|µg|g|ml|mL)\s+(?:of\s+)?)?(\b[A-Z][a-z]+(?:[A-Z][a-z]+)?\b)',
        ]
        for pattern in context_patterns:
            matches = re.findall(pattern, protocol_text)
            for match in matches:
                if len(match) > 3 and not match.lower() in ['placebo', 'active', 'control', 'treatment', 'study', 'group', 'arm']:
                    drug_names.add(match.lower())

        # Filter out common false positives
        false_positives = {
            'patients', 'subjects', 'participants', 'investigator', 'sponsor',
            'protocol', 'study', 'trial', 'treatment', 'placebo', 'control',
            'randomization', 'stratification', 'efficacy', 'safety', 'analysis',
            'endpoint', 'primary', 'secondary', 'baseline', 'visit', 'week',
            'month', 'day', 'dose', 'dosing', 'administration', 'infusion',
            'injection', 'oral', 'intravenous', 'subcutaneous', 'intramuscular',
        }
        drug_names = {d for d in drug_names if d.lower() not in false_positives}

        return list(drug_names)

    def _extract_sample_size(self, protocol_text: str) -> int:
        """Extract sample size from protocol."""
        for pattern in self.SAMPLE_SIZE_PATTERNS:
            match = re.search(pattern, protocol_text, re.IGNORECASE)
            if match:
                try:
                    size = int(match.group(1))
                    if 10 <= size <= 100000:  # Reasonable range
                        return size
                except ValueError:
                    continue
        return 0

    def _extract_num_arms(self, protocol_text: str) -> int:
        """Extract number of treatment arms."""
        # Look for ratio patterns (1:1:1 = 3 arms)
        ratio_match = re.search(r'(\d+:\d+(?::\d+)*)', protocol_text)
        if ratio_match:
            return len(ratio_match.group(1).split(':'))

        # Look for explicit arm count
        arms_patterns = [
            r'(\d+)\s+(?:treatment\s+)?(?:arms?|groups?)',
            r'(?:randomized?\s+to|assigned\s+to)\s+(\d+)',
        ]
        for pattern in arms_patterns:
            match = re.search(pattern, protocol_text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        return 0

    def _detect_therapeutic_area(self, protocol_text: str) -> str:
        """Detect therapeutic area from protocol."""
        for area, pattern in self.THERAPEUTIC_AREA_PATTERNS.items():
            if re.search(pattern, protocol_text, re.IGNORECASE):
                return area
        return "Other"

    def _extract_indication(self, protocol_text: str) -> str:
        """Extract indication from protocol."""
        indication_patterns = [
            r'(?:patients?\s+with|diagnosis\s+of|treatment\s+of)\s+([\w\s\'-]+(?:disease|syndrome|disorder|cancer|carcinoma|failure))',
            r'(?:indication)[:\s]+([\w\s\'-]+)',
        ]
        for pattern in indication_patterns:
            match = re.search(pattern, protocol_text, re.IGNORECASE)
            if match:
                indication = match.group(1).strip()
                if len(indication) > 3 and len(indication) < 100:
                    return indication
        return ""


class ContaminationDetector:
    """
    Detects contamination in generated SAP.
    PROTOCOL-AGNOSTIC: Compares SAP content against protocol identity dynamically.
    """

    def __init__(self, identity_extractor: ProtocolIdentityExtractor):
        self.identity_extractor = identity_extractor

    def detect_contamination(
        self,
        sap_text: str,
        protocol_identity: ProtocolIdentity
    ) -> ContaminationReport:
        """Check SAP for contamination from other protocols."""
        report = ContaminationReport()

        # Check for foreign drug names (drugs in SAP but NOT in protocol)
        foreign_drugs = self._check_foreign_drugs(sap_text, protocol_identity)
        if foreign_drugs:
            report.foreign_drugs_in_sap = foreign_drugs
            report.wrong_drug_names = foreign_drugs
            report.is_contaminated = True
            for drug in foreign_drugs:
                report.contamination_sources.append(f"Foreign drug '{drug}' not in protocol")

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
        elif report.wrong_sample_sizes and protocol_identity.sample_size > 0:
            max_diff = max(abs(s - protocol_identity.sample_size) for s in report.wrong_sample_sizes)
            if max_diff > 100:
                report.severity = "critical"
            else:
                report.severity = "high"
        elif report.wrong_study_ids:
            report.severity = "medium"
        elif report.is_contaminated:
            report.severity = "low"

        return report

    def _check_foreign_drugs(self, sap_text: str, identity: ProtocolIdentity) -> List[str]:
        """Check for drug names in SAP that are NOT in the protocol."""
        foreign_drugs = []
        protocol_drugs = set(d.lower() for d in identity.drug_names_all)

        # Extract all potential drug names from SAP
        sap_drugs = self.identity_extractor._extract_drug_names_dynamic(sap_text)

        for drug in sap_drugs:
            drug_lower = drug.lower()
            # Check if this drug is NOT in the protocol
            if drug_lower not in protocol_drugs:
                # Also check if it's not a variant of a protocol drug
                is_variant = False
                for protocol_drug in protocol_drugs:
                    if drug_lower in protocol_drug or protocol_drug in drug_lower:
                        is_variant = True
                        break
                if not is_variant:
                    foreign_drugs.append(drug)

        return list(set(foreign_drugs))

    def _check_wrong_sample_sizes(self, sap_text: str, identity: ProtocolIdentity) -> List[int]:
        """Check for sample sizes that don't match protocol."""
        wrong_sizes = []

        if identity.sample_size == 0:
            return wrong_sizes

        # Find all sample size mentions in SAP
        size_patterns = [
            r'(\d+)\s+(?:patients?|subjects?|participants?)',
            r'N\s*[=:]\s*(\d+)',
            r'sample\s+size[:\s]+(\d+)',
        ]

        found_sizes = set()
        for pattern in size_patterns:
            matches = re.findall(pattern, sap_text, re.IGNORECASE)
            for match in matches:
                try:
                    found_sizes.add(int(match))
                except ValueError:
                    continue

        for size in found_sizes:
            # Only check substantial numbers (>50)
            if size > 50:
                # Calculate tolerance (20% or at least 10)
                tolerance = max(identity.sample_size * 0.2, 10)

                if abs(size - identity.sample_size) > tolerance:
                    # Check if it's a per-arm size
                    if identity.num_arms > 1:
                        per_arm = identity.sample_size // identity.num_arms
                        if abs(size - per_arm) <= tolerance:
                            continue  # It's a valid per-arm size

                    # Check if it's a common multiple (e.g., 2x for 2 cohorts)
                    for multiplier in [2, 3, 4]:
                        if abs(size - identity.sample_size * multiplier) <= tolerance:
                            continue

                    wrong_sizes.append(size)

        return list(set(wrong_sizes))

    def _check_wrong_study_ids(self, sap_text: str, identity: ProtocolIdentity) -> List[str]:
        """Check for study IDs that don't match protocol."""
        wrong_ids = []

        # Find all NCT IDs in SAP
        nct_matches = re.findall(r'NCT\d{8}', sap_text, re.IGNORECASE)

        for nct_id in nct_matches:
            nct_clean = nct_id.upper()
            if identity.nct_id and nct_clean != identity.nct_id:
                wrong_ids.append(nct_clean)

        # Find internal study IDs
        if identity.study_id:
            internal_ids = re.findall(r'\b([A-Z]{2,5}\d{3,4}[A-Z]{0,3}\d{0,3})\b', sap_text)
            for study_id in internal_ids:
                if study_id != identity.study_id and study_id not in identity.all_identifiers:
                    # Check if it's not a common code pattern
                    if not re.match(r'^(ICH|GCP|FDA|EMA|CDISC|SDTM|ADaM|TLF)\d', study_id):
                        wrong_ids.append(study_id)

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
        """Clean contamination from SAP."""
        changes = []
        cleaned = sap_text

        # Replace wrong drug names with correct drug name
        if contamination_report.wrong_drug_names and protocol_identity.drug_name:
            for wrong_drug in contamination_report.wrong_drug_names:
                pattern = rf'\b{re.escape(wrong_drug)}\b'
                if re.search(pattern, cleaned, re.IGNORECASE):
                    cleaned = re.sub(pattern, protocol_identity.drug_name, cleaned, flags=re.IGNORECASE)
                    changes.append(f"Replaced '{wrong_drug}' with '{protocol_identity.drug_name}'")

        # Replace wrong sample sizes
        if contamination_report.wrong_sample_sizes and protocol_identity.sample_size > 0:
            for wrong_size in contamination_report.wrong_sample_sizes:
                pattern = rf'\b{wrong_size}\s+(patients?|subjects?|participants?)'
                replacement = f"{protocol_identity.sample_size} \\1"
                if re.search(pattern, cleaned, re.IGNORECASE):
                    cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
                    changes.append(f"Replaced sample size {wrong_size} with {protocol_identity.sample_size}")

        # Replace wrong NCT IDs
        if contamination_report.wrong_study_ids and protocol_identity.nct_id:
            for wrong_id in contamination_report.wrong_study_ids:
                if wrong_id.startswith('NCT') and wrong_id in cleaned:
                    cleaned = cleaned.replace(wrong_id, protocol_identity.nct_id)
                    changes.append(f"Replaced study ID {wrong_id} with {protocol_identity.nct_id}")

        return cleaned, changes


class ContaminationGuard:
    """
    Main interface for contamination protection.
    PROTOCOL-AGNOSTIC: Works with ANY therapeutic area.
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
        """Check SAP for contamination and clean if found."""
        identity = self.identity_extractor.extract_identity(protocol_text)
        report = self.detector.detect_contamination(sap_text, identity)

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
        """Validate that SAP matches protocol identity."""
        results = {
            'valid': True,
            'issues': [],
            'protocol_identity': {
                'nct_id': protocol_identity.nct_id,
                'drug_name': protocol_identity.drug_name,
                'sample_size': protocol_identity.sample_size,
                'num_arms': protocol_identity.num_arms,
                'therapeutic_area': protocol_identity.therapeutic_area,
            }
        }

        # Check NCT ID appears in SAP
        if protocol_identity.nct_id:
            if protocol_identity.nct_id not in sap_text:
                results['valid'] = False
                results['issues'].append(f"NCT ID {protocol_identity.nct_id} not found in SAP")

        # Check drug name appears in SAP
        if protocol_identity.drug_name:
            if not re.search(rf'\b{re.escape(protocol_identity.drug_name)}\b', sap_text, re.IGNORECASE):
                results['valid'] = False
                results['issues'].append(f"Drug name {protocol_identity.drug_name} not found in SAP")

        # Check sample size mentioned correctly
        if protocol_identity.sample_size > 0:
            if str(protocol_identity.sample_size) not in sap_text:
                results['valid'] = False
                results['issues'].append(f"Sample size {protocol_identity.sample_size} not found in SAP")

        return results
