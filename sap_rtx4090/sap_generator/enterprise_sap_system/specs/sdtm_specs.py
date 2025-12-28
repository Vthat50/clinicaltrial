#!/usr/bin/env python3
"""
SDTM Specification Generator - SAP-Driven Implementation
=========================================================

Generates CDISC SDTM domain specifications by parsing the generated SAP document.
This implements Sandy's vision: SAP text → SDTM Specs with traceability.

Key features:
1. Parses SAP text to extract endpoints, populations, variables
2. Maps extracted elements to specific SDTM domains
3. Creates traceable links (SAP section → SDTM domain)
4. Generates study-specific variable requirements

References:
- CDISC SDTM v1.7: https://www.cdisc.org/standards/foundational/sdtm
- SDTMIG v3.4: https://www.cdisc.org/standards/foundational/sdtmig
- FDA Study Data Technical Conformance Guide
"""

from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import re


class VariableCore(Enum):
    """CDISC Core classification for variables."""
    REQUIRED = "Req"      # Cannot be null
    EXPECTED = "Exp"      # Must include, can be null
    PERMISSIBLE = "Perm"  # Optional based on data collected


class DomainClass(Enum):
    """SDTM Domain Classes per CDISC."""
    SPECIAL_PURPOSE = "Special Purpose"
    TRIAL_DESIGN = "Trial Design"
    INTERVENTIONS = "Interventions"
    EVENTS = "Events"
    FINDINGS = "Findings"
    FINDINGS_ABOUT = "Findings About"
    RELATIONSHIP = "Relationship"


@dataclass
class SAPTraceability:
    """Links an SDTM element back to its source in the SAP."""
    sap_section: str           # e.g., "4.1 Primary Endpoint"
    sap_text: str              # The actual text from SAP
    sdtm_element: str          # e.g., "QS domain - CDAI Score"
    rationale: str             # Why this mapping was made


@dataclass
class SDTMVariable:
    """Specification for a single SDTM variable."""
    name: str
    label: str
    type: str  # "Char" or "Num"
    length: Optional[int] = None
    core: VariableCore = VariableCore.PERMISSIBLE
    codelist: Optional[str] = None
    description: str = ""
    source: str = ""  # Where data comes from (CRF, derived, etc.)
    sap_source: Optional[str] = None  # SAP section that requires this

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "length": self.length,
            "core": self.core.value,
            "codelist": self.codelist,
            "description": self.description,
            "source": self.source,
            "sap_source": self.sap_source
        }


@dataclass
class SDTMDomain:
    """Specification for a complete SDTM domain."""
    code: str  # Two-letter domain code (DM, AE, etc.)
    name: str
    label: str
    domain_class: DomainClass
    structure: str  # "One record per subject", etc.
    variables: List[SDTMVariable] = field(default_factory=list)
    description: str = ""
    purpose: str = ""
    required_for: List[str] = field(default_factory=list)  # Which TLFs need this
    traceability: List[SAPTraceability] = field(default_factory=list)  # SAP links
    study_specific_notes: List[str] = field(default_factory=list)  # Study-specific requirements

    def to_dict(self) -> Dict:
        return {
            "code": self.code,
            "name": self.name,
            "label": self.label,
            "class": self.domain_class.value,
            "structure": self.structure,
            "description": self.description,
            "purpose": self.purpose,
            "required_for": self.required_for,
            "variables": [v.to_dict() for v in self.variables],
            "traceability": [
                {
                    "sap_section": t.sap_section,
                    "sap_text": t.sap_text[:200] + "..." if len(t.sap_text) > 200 else t.sap_text,
                    "sdtm_element": t.sdtm_element,
                    "rationale": t.rationale
                }
                for t in self.traceability
            ],
            "study_specific_notes": self.study_specific_notes
        }

    def to_markdown(self) -> str:
        """Generate markdown documentation for this domain."""
        lines = [
            f"### {self.code} - {self.name}",
            "",
            f"**Label:** {self.label}",
            f"**Class:** {self.domain_class.value}",
            f"**Structure:** {self.structure}",
            "",
            f"**Purpose:** {self.purpose}",
            "",
        ]

        # Add study-specific notes
        if self.study_specific_notes:
            lines.append("**Study-Specific Requirements:**")
            for note in self.study_specific_notes:
                lines.append(f"- {note}")
            lines.append("")

        # Add traceability
        if self.traceability:
            lines.append("**SAP Traceability:**")
            lines.append("")
            lines.append("| SAP Section | SAP Requirement | SDTM Element |")
            lines.append("|-------------|-----------------|--------------|")
            for t in self.traceability:
                sap_text_short = t.sap_text[:80] + "..." if len(t.sap_text) > 80 else t.sap_text
                lines.append(f"| {t.sap_section} | {sap_text_short} | {t.sdtm_element} |")
            lines.append("")

        # Variables table
        lines.append("#### Variables")
        lines.append("")
        lines.append("| Variable | Label | Type | Core | SAP Source |")
        lines.append("|----------|-------|------|------|------------|")

        for var in self.variables:
            sap_src = var.sap_source or "-"
            lines.append(f"| {var.name} | {var.label} | {var.type} | {var.core.value} | {sap_src} |")

        if self.required_for:
            lines.extend([
                "",
                f"**Required for TLFs:** {', '.join(self.required_for)}"
            ])

        return "\n".join(lines)


@dataclass
class ExtractedSAPElement:
    """An element extracted from SAP text."""
    element_type: str  # "endpoint", "population", "variable", "timepoint", etc.
    name: str
    description: str
    section: str  # SAP section where found
    original_text: str  # Original SAP text
    sdtm_domains: List[str] = field(default_factory=list)  # Mapped domains


@dataclass
class SDTMSpecification:
    """Complete SDTM specification for a study."""
    protocol_id: str
    generated_at: str
    sdtm_version: str = "3.4"
    domains: List[SDTMDomain] = field(default_factory=list)
    define_xml_notes: List[str] = field(default_factory=list)
    extracted_elements: List[ExtractedSAPElement] = field(default_factory=list)
    sap_summary: Dict[str, Any] = field(default_factory=dict)

    def get_domain(self, code: str) -> Optional[SDTMDomain]:
        """Get domain by code."""
        for domain in self.domains:
            if domain.code == code:
                return domain
        return None

    def get_all_domain_codes(self) -> List[str]:
        """Return list of all domain codes."""
        return [d.code for d in self.domains]

    def to_markdown(self) -> str:
        """Generate full markdown specification document."""
        lines = [
            f"# SDTM Specification",
            f"## Protocol: {self.protocol_id}",
            "",
            f"**Generated:** {self.generated_at}",
            f"**SDTM Version:** {self.sdtm_version}",
            "",
            "---",
            "",
            "## SAP-Derived Requirements",
            "",
        ]

        # Add SAP summary
        if self.sap_summary:
            if self.sap_summary.get('primary_endpoint'):
                lines.append(f"**Primary Endpoint:** {self.sap_summary['primary_endpoint']}")
            if self.sap_summary.get('primary_timepoint'):
                lines.append(f"**Primary Timepoint:** {self.sap_summary['primary_timepoint']}")
            if self.sap_summary.get('populations'):
                lines.append(f"**Analysis Populations:** {', '.join(self.sap_summary['populations'])}")
            if self.sap_summary.get('secondary_endpoints'):
                lines.append(f"**Secondary Endpoints:** {len(self.sap_summary['secondary_endpoints'])} defined")
            lines.append("")

        # Domains summary
        lines.extend([
            "---",
            "",
            "## SDTM Domains Required",
            "",
            "| Domain | Name | Class | SAP-Derived Requirements |",
            "|--------|------|-------|--------------------------|",
        ])

        for domain in self.domains:
            trace_count = len(domain.traceability)
            trace_info = f"{trace_count} SAP links" if trace_count > 0 else "Standard"
            lines.append(f"| {domain.code} | {domain.name} | {domain.domain_class.value} | {trace_info} |")

        lines.extend(["", "---", ""])

        # Add each domain specification
        for domain in self.domains:
            lines.append(domain.to_markdown())
            lines.append("")
            lines.append("---")
            lines.append("")

        # Add Define-XML notes
        if self.define_xml_notes:
            lines.extend([
                "## Define-XML Notes",
                "",
            ])
            for note in self.define_xml_notes:
                lines.append(f"- {note}")

        return "\n".join(lines)


class SAPParser:
    """
    Parses SAP text to extract study-specific requirements.
    """

    # SAP Section patterns
    SECTION_PATTERNS = {
        'population': [
            r'(?:analysis\s+)?population[s]?\s*(?:definition)?',
            r'study\s+population',
            r'subject\s+population',
            r'(?:itt|mITT|pp|safety)\s+(?:population|analysis\s+set)',
        ],
        'primary_endpoint': [
            r'primary\s+(?:endpoint|efficacy\s+endpoint|outcome)',
            r'primary\s+analysis',
        ],
        'secondary_endpoint': [
            r'secondary\s+(?:endpoint|efficacy\s+endpoint|outcome)',
            r'key\s+secondary',
        ],
        'safety': [
            r'safety\s+(?:analysis|endpoint|assessment)',
            r'adverse\s+event',
        ],
        'demographics': [
            r'demographic',
            r'baseline\s+characteristic',
        ],
        'disposition': [
            r'disposition',
            r'study\s+completion',
            r'discontinuation',
        ],
        'efficacy': [
            r'efficacy\s+(?:analysis|endpoint)',
        ],
        'laboratory': [
            r'laboratory',
            r'lab\s+(?:test|value|parameter)',
        ],
        'vital_signs': [
            r'vital\s+sign',
        ],
        'concomitant_medications': [
            r'concomitant\s+medication',
            r'prior\s+medication',
        ],
        'medical_history': [
            r'medical\s+history',
            r'prior\s+(?:condition|disease)',
        ],
    }

    # Clinical assessment patterns that map to specific domains
    ASSESSMENT_TO_DOMAIN = {
        # Questionnaires/PRO (QS domain) - includes diary-derived data
        'mayo score': ('QS', 'Mayo Score (total and subscores)'),
        'stool frequency': ('QS', 'Stool frequency subscore'),
        'rectal bleeding': ('QS', 'Rectal bleeding subscore'),
        'physician global assessment': ('QS', 'Physician Global Assessment subscore'),
        'endoscopic subscore': ('QS', 'Endoscopic subscore'),
        'diary': ('QS', 'Patient diary data'),
        'cdai': ('QS', 'CDAI Score assessment'),
        'sf-36': ('QS', 'SF-36 Quality of Life'),
        'sf36': ('QS', 'SF-36 Quality of Life'),
        'eq-5d': ('QS', 'EQ-5D Quality of Life'),
        'eq5d': ('QS', 'EQ-5D Quality of Life'),
        'ibdq': ('QS', 'IBDQ assessment'),
        'dlqi': ('QS', 'Dermatology Life Quality Index'),
        'pasi': ('QS', 'PASI Score'),
        'das28': ('QS', 'DAS28 Score'),
        'cdlqi': ('QS', 'CDLQI assessment'),
        'patient reported': ('QS', 'Patient Reported Outcomes'),
        'quality of life': ('QS', 'Quality of Life assessment'),
        'qol': ('QS', 'Quality of Life assessment'),
        'ham-d': ('QS', 'Hamilton Depression Scale'),
        'hamd': ('QS', 'Hamilton Depression Scale'),
        'madrs': ('QS', 'MADRS Depression Scale'),
        'adas-cog': ('QS', 'ADAS-Cog assessment'),
        'mmse': ('QS', 'MMSE assessment'),
        'cgi-s': ('QS', 'CGI-S assessment'),
        'cgi-i': ('QS', 'CGI-I assessment'),
        'pain score': ('QS', 'Pain assessment'),
        'vas score': ('QS', 'VAS assessment'),
        'nancy score': ('QS', 'Nancy Histological Score'),
        'geboes score': ('QS', 'Geboes Histological Score'),

        # Tumor assessments (TR/RS domains)
        'recist': ('TR', 'RECIST tumor assessment'),
        'tumor response': ('RS', 'Tumor response assessment'),
        'objective response': ('RS', 'Objective response rate'),
        'orr': ('RS', 'Objective Response Rate'),
        'complete response': ('RS', 'Complete response'),
        'partial response': ('RS', 'Partial response'),
        'progression-free': ('RS', 'Progression-free survival'),
        'pfs': ('RS', 'Progression-free survival'),
        'disease control': ('RS', 'Disease control rate'),

        # ECG (EG domain)
        'ecg': ('EG', 'ECG parameters (HR, PR, QRS, QT, QTc)'),
        'electrocardiogram': ('EG', 'ECG parameters'),
        'qtc': ('EG', 'QTc interval'),
        'qt interval': ('EG', 'QT interval'),
        'pr interval': ('EG', 'PR interval'),
        'qrs': ('EG', 'QRS duration'),

        # Lab tests - HEMATOLOGY (LB domain)
        'hemoglobin': ('LB', 'Hemoglobin'),
        'hematocrit': ('LB', 'Hematocrit'),
        'rbc': ('LB', 'Red blood cell count'),
        'wbc': ('LB', 'White blood cell count'),
        'white blood cell': ('LB', 'White blood cell count with differential'),
        'neutrophil': ('LB', 'Neutrophils'),
        'lymphocyte': ('LB', 'Lymphocytes'),
        'monocyte': ('LB', 'Monocytes'),
        'eosinophil': ('LB', 'Eosinophils'),
        'basophil': ('LB', 'Basophils'),
        'platelet': ('LB', 'Platelet count'),
        'mcv': ('LB', 'Mean corpuscular volume'),
        'mch': ('LB', 'Mean corpuscular hemoglobin'),
        'mchc': ('LB', 'Mean corpuscular hemoglobin concentration'),

        # Lab tests - CHEMISTRY (LB domain)
        'crp': ('LB', 'C-reactive protein'),
        'c-reactive protein': ('LB', 'C-reactive protein'),
        'fecal calprotectin': ('LB', 'Fecal calprotectin'),
        'calprotectin': ('LB', 'Fecal calprotectin'),
        'albumin': ('LB', 'Albumin'),
        'alt': ('LB', 'Alanine aminotransferase'),
        'alanine aminotransferase': ('LB', 'ALT'),
        'ast': ('LB', 'Aspartate aminotransferase'),
        'aspartate aminotransferase': ('LB', 'AST'),
        'alkaline phosphatase': ('LB', 'Alkaline phosphatase'),
        'alp': ('LB', 'Alkaline phosphatase'),
        'ggt': ('LB', 'Gamma-glutamyl transferase'),
        'gamma-glutamyl': ('LB', 'GGT'),
        'bilirubin': ('LB', 'Bilirubin (total and direct)'),
        'creatinine': ('LB', 'Creatinine'),
        'bun': ('LB', 'Blood urea nitrogen'),
        'urea': ('LB', 'Urea'),
        'sodium': ('LB', 'Sodium'),
        'potassium': ('LB', 'Potassium'),
        'chloride': ('LB', 'Chloride'),
        'bicarbonate': ('LB', 'Bicarbonate'),
        'calcium': ('LB', 'Calcium'),
        'phosphorus': ('LB', 'Phosphorus'),
        'magnesium': ('LB', 'Magnesium'),
        'glucose': ('LB', 'Glucose'),
        'hba1c': ('LB', 'HbA1c'),
        'lipid': ('LB', 'Lipid panel'),
        'ldl': ('LB', 'LDL cholesterol'),
        'hdl': ('LB', 'HDL cholesterol'),
        'cholesterol': ('LB', 'Total cholesterol'),
        'triglyceride': ('LB', 'Triglycerides'),

        # Lab tests - COAGULATION (LB domain)
        'pt': ('LB', 'Prothrombin time'),
        'prothrombin': ('LB', 'Prothrombin time'),
        'inr': ('LB', 'International normalized ratio'),
        'aptt': ('LB', 'Activated partial thromboplastin time'),
        'ptt': ('LB', 'Partial thromboplastin time'),
        'fibrinogen': ('LB', 'Fibrinogen'),

        # Lab tests - URINALYSIS (LB domain)
        'urinalysis': ('LB', 'Urinalysis'),
        'urine': ('LB', 'Urinalysis'),

        # Lab tests - IMMUNOLOGY/BIOMARKERS (LB domain)
        'il-6': ('LB', 'Interleukin-6'),
        'sil-6r': ('LB', 'Soluble IL-6 receptor'),
        'interleukin': ('LB', 'Interleukin levels'),
        'antibod': ('LB', 'Anti-drug antibodies'),
        'ada': ('LB', 'Anti-drug antibodies'),
        'nab': ('LB', 'Neutralizing antibodies'),
        'immunogenicity': ('LB', 'Immunogenicity testing'),
        'esr': ('LB', 'Erythrocyte sedimentation rate'),

        # Lab tests - SCREENING/INFECTIOUS DISEASE (LB domain)
        'hiv': ('LB', 'HIV testing'),
        'hepatitis': ('LB', 'Hepatitis testing'),
        'hbsag': ('LB', 'Hepatitis B surface antigen'),
        'hbv': ('LB', 'Hepatitis B testing'),
        'hcv': ('LB', 'Hepatitis C testing'),
        'ebv': ('LB', 'Epstein-Barr virus testing'),
        'cmv': ('LB', 'Cytomegalovirus testing'),
        'tuberculosis': ('LB', 'TB testing'),
        'quantiferon': ('LB', 'QuantiFERON-TB Gold'),
        'tb gold': ('LB', 'TB testing'),
        'c. difficile': ('LB', 'C. difficile testing'),
        'clostridium': ('LB', 'C. difficile testing'),
        'stool culture': ('LB', 'Stool culture'),

        # Lab tests - PREGNANCY (LB domain)
        'pregnancy test': ('LB', 'Pregnancy testing'),
        'beta-hcg': ('LB', 'Beta-HCG'),
        'serum pregnancy': ('LB', 'Serum pregnancy test'),
        'urine pregnancy': ('LB', 'Urine pregnancy test'),

        # Physical exam (PE domain)
        'physical exam': ('PE', 'Physical examination'),

        # Vital signs (VS domain) - comprehensive
        'vital sign': ('VS', 'Vital signs'),
        'blood pressure': ('VS', 'Blood pressure (systolic/diastolic)'),
        'systolic': ('VS', 'Systolic blood pressure'),
        'diastolic': ('VS', 'Diastolic blood pressure'),
        'heart rate': ('VS', 'Heart rate'),
        'pulse': ('VS', 'Pulse rate'),
        'respiratory rate': ('VS', 'Respiratory rate'),
        'respiration': ('VS', 'Respiratory rate'),
        'temperature': ('VS', 'Body temperature'),
        'weight': ('VS', 'Body weight'),
        'height': ('VS', 'Height'),
        'bmi': ('VS', 'Body mass index'),

        # Exposure (EX domain)
        'dose': ('EX', 'Study drug dose'),
        'dosing': ('EX', 'Dosing regimen'),
        'infusion': ('EX', 'Infusion administration'),
        'treatment exposure': ('EX', 'Treatment exposure'),
        'q2w': ('EX', 'Dosing frequency (Q2W)'),
        'placebo': ('EX', 'Placebo treatment'),

        # PK Concentrations (PC domain)
        'pk concentration': ('PC', 'Drug concentration measurement'),
        'serum concentration': ('PC', 'Serum drug concentration'),
        'plasma concentration': ('PC', 'Plasma drug concentration'),
        'pk sample': ('PC', 'PK sampling'),
        'pk substudy': ('PC', 'PK substudy samples'),
        'trough concentration': ('PC', 'Trough concentration'),
        'cmin': ('PC', 'Minimum concentration'),

        # PK Parameters (PP domain)
        'auc': ('PP', 'Area under curve'),
        'cmax': ('PP', 'Maximum concentration'),
        'tmax': ('PP', 'Time to maximum concentration'),
        'half-life': ('PP', 'Elimination half-life'),
        't1/2': ('PP', 'Elimination half-life'),
        'clearance': ('PP', 'Drug clearance'),
        'volume of distribution': ('PP', 'Volume of distribution'),
        'nca': ('PP', 'Non-compartmental analysis'),

        # Endoscopy/Procedures (FA domain) - NOT diary data
        'endoscop': ('FA', 'Endoscopy findings'),
        'colonoscop': ('FA', 'Colonoscopy findings'),
        'sigmoidoscop': ('FA', 'Sigmoidoscopy findings'),
        'biopsy': ('FA', 'Biopsy findings'),
        'histolog': ('FA', 'Histological findings'),
        'mucosal': ('FA', 'Mucosal assessment'),
    }

    def __init__(self):
        self.extracted_elements: List[ExtractedSAPElement] = []
        self.domain_requirements: Dict[str, List[SAPTraceability]] = {}

    def parse(self, sap_text: str) -> Dict[str, Any]:
        """
        Parse SAP text and extract study-specific requirements.

        Returns dictionary with:
        - study_id: str (extracted from SAP)
        - primary_endpoint: str
        - primary_timepoint: str
        - secondary_endpoints: List[str]
        - populations: List[str]
        - assessments: List[Dict] with domain mappings
        - variables_mentioned: List[str]
        - traceability: Dict[domain_code -> List[SAPTraceability]]
        """
        self.extracted_elements = []
        self.domain_requirements = {}

        result = {
            'study_id': self._extract_study_id(sap_text),
            'drug_name': self._extract_drug_name(sap_text),
            'primary_endpoint': self._extract_primary_endpoint(sap_text),
            'primary_timepoint': self._extract_primary_timepoint(sap_text),
            'secondary_endpoints': self._extract_secondary_endpoints(sap_text),
            'populations': self._extract_populations(sap_text),
            'assessments': self._extract_assessments(sap_text),
            'variables_mentioned': self._extract_variables(sap_text),
            'treatment_arms': self._extract_treatment_arms(sap_text),
            'sample_size': self._extract_sample_size(sap_text),
            'extracted_elements': self.extracted_elements,
            'domain_requirements': self.domain_requirements,
        }

        # Consolidate redundant traceability entries
        self._consolidate_traceability()
        result['domain_requirements'] = self.domain_requirements

        return result

    def _extract_study_id(self, sap_text: str) -> Optional[str]:
        """Extract study identifier from SAP text."""
        patterns = [
            # Protocol numbers like CTJ301UC201, ABC-123-456
            r'(?:protocol|study)\s*(?:number|id|identifier)?[:\s]+([A-Z]{2,5}[-]?\d{2,4}[-]?[A-Z]{0,3}[-]?\d{0,4})',
            r'(?:protocol|study)[:\s]+([A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+)',
            r'([A-Z]{2,5}\d{3}[A-Z]{2}\d{3})',  # Pattern like CTJ301UC201
            # NCT numbers
            r'(NCT\d{8})',
            # EudraCT numbers
            r'(\d{4}-\d{6}-\d{2})',
            # Generic protocol patterns
            r'protocol[:\s]+([A-Z0-9-]{6,20})',
        ]

        for pattern in patterns:
            match = re.search(pattern, sap_text, re.IGNORECASE)
            if match:
                study_id = match.group(1).strip()
                # Clean up and standardize
                if study_id and len(study_id) >= 6:
                    return study_id.upper()

        return None

    def _extract_drug_name(self, sap_text: str) -> Optional[str]:
        """Extract drug/treatment name from SAP text."""
        patterns = [
            r'(?:study\s+drug|investigational\s+product|treatment)[:\s]+([A-Za-z0-9-]+)',
            r'([A-Z]{2,3}[-]?\d{3,4})\s+(?:mg|dose)',
            r'(?:active\s+treatment|study\s+medication)[:\s]+([A-Za-z0-9-]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, sap_text, re.IGNORECASE)
            if match:
                drug = match.group(1).strip()
                if drug and len(drug) >= 3:
                    return drug

        return None

    def _consolidate_traceability(self):
        """Remove redundant traceability entries and consolidate similar ones."""
        for domain_code in self.domain_requirements:
            traces = self.domain_requirements[domain_code]
            seen = set()
            unique_traces = []

            for trace in traces:
                # Create a key for deduplication
                key = (trace.sap_section, trace.sdtm_element)
                if key not in seen:
                    seen.add(key)
                    unique_traces.append(trace)

            self.domain_requirements[domain_code] = unique_traces

    def _extract_primary_endpoint(self, sap_text: str) -> Optional[str]:
        """Extract primary endpoint from SAP."""
        patterns = [
            r'primary\s+(?:efficacy\s+)?endpoint[:\s]+([^\n]+)',
            r'primary\s+endpoint\s+is\s+([^\n\.]+)',
            r'primary\s+outcome[:\s]+([^\n]+)',
            r'the\s+primary\s+(?:efficacy\s+)?endpoint\s+(?:is|will be)\s+([^\n\.]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, sap_text, re.IGNORECASE)
            if match:
                endpoint = match.group(1).strip()
                # Clean up
                endpoint = re.sub(r'\s+', ' ', endpoint)
                endpoint = endpoint.rstrip('.')

                self.extracted_elements.append(ExtractedSAPElement(
                    element_type='primary_endpoint',
                    name=endpoint,
                    description='Primary efficacy endpoint',
                    section='Primary Endpoint',
                    original_text=match.group(0),
                ))

                # Map to SDTM domain based on endpoint type
                self._map_endpoint_to_domain(endpoint, 'Primary Endpoint', match.group(0))

                return endpoint

        return None

    def _extract_primary_timepoint(self, sap_text: str) -> Optional[str]:
        """Extract primary analysis timepoint."""
        patterns = [
            r'(?:primary\s+(?:analysis\s+)?timepoint|primary\s+endpoint\s+at)\s*(?:is\s+)?(?:at\s+)?week\s+(\d+)',
            r'week\s+(\d+)\s+(?:as\s+)?(?:the\s+)?primary\s+(?:timepoint|endpoint)',
            r'primary\s+analysis\s+(?:will\s+be\s+)?(?:performed\s+)?at\s+week\s+(\d+)',
            r'at\s+week\s+(\d+)[^\.]*primary',
            r'primary[^\.]*at\s+week\s+(\d+)',  # "primary ... at Week 12"
            r'primary[^\.]*week\s+(\d+)',  # Broader: "primary ... Week 12"
        ]

        for pattern in patterns:
            match = re.search(pattern, sap_text, re.IGNORECASE)
            if match:
                return f"Week {match.group(1)}"

        return None

    def _extract_secondary_endpoints(self, sap_text: str) -> List[str]:
        """Extract ALL secondary endpoints from SAP comprehensively."""
        endpoints = []
        seen_endpoints = set()  # Avoid duplicates

        # Pattern 1: Find secondary endpoint section and extract list
        section_patterns = [
            r'secondary\s+(?:efficacy\s+)?endpoint[s]?[:\s]+([^\n]+(?:\n(?![A-Z0-9]+\.\s+[A-Z])[^\n]+)*)',
            r'(?:key\s+)?secondary\s+endpoint[s]?\s+include[:\s]+([^\n]+(?:\n(?![A-Z0-9]+\.\s+[A-Z])[^\n]+)*)',
            r'secondary\s+(?:efficacy\s+)?(?:endpoint|variable)[s]?\s*(?:are|include)?[:\s]*\n((?:[•\-\d\.]+[^\n]+\n?)+)',
        ]

        for pattern in section_patterns:
            matches = re.findall(pattern, sap_text, re.IGNORECASE | re.MULTILINE)
            for text in matches:
                # Split by bullet points, numbers, semicolons, newlines
                items = re.split(r'(?:[;•\-]\s*|\n\s*[•\-]\s*|\n\s*\d+[\.\)]\s*)', text)
                for item in items:
                    item = item.strip()
                    # Clean up leading characters
                    item = re.sub(r'^[\d\.\)\-•\s]+', '', item).strip()
                    if len(item) > 15 and len(item) < 500 and item.lower() not in seen_endpoints:
                        seen_endpoints.add(item.lower())
                        endpoints.append(item)

        # Pattern 2: Find specific endpoint types mentioned
        endpoint_types = [
            (r'clinical\s+(?:and\s+endoscopic\s+)?response\s+at\s+(?:week[s]?\s+)?[\d,\s]+', 'Clinical response'),
            (r'clinical\s+remission\s+at\s+(?:week[s]?\s+)?[\d,\s]+', 'Clinical remission'),
            (r'endoscopic\s+(?:response|remission|improvement)\s+at\s+(?:week[s]?\s+)?[\d,\s]+', 'Endoscopic response'),
            (r'mucosal\s+healing\s+at\s+(?:week[s]?\s+)?[\d,\s]+', 'Mucosal healing'),
            (r'change\s+(?:from\s+baseline\s+)?in\s+(?:total\s+)?mayo\s+score', 'Change in Mayo score'),
            (r'(?:fda|regulatory)[- ]defined\s+(?:remission|response)', 'Regulatory-defined remission'),
            (r'(?:pk|pharmacokinetic)\s+(?:parameter|endpoint|analysis)', 'PK parameters'),
            (r'immunogenicity\s+(?:endpoint|analysis|assessment)', 'Immunogenicity'),
            (r'(?:ada|anti[- ]drug\s+antibod)', 'Anti-drug antibodies'),
            (r'(?:safety|tolerability)\s+(?:endpoint|assessment)', 'Safety assessment'),
        ]

        for pattern, name in endpoint_types:
            match = re.search(pattern, sap_text, re.IGNORECASE)
            if match and name.lower() not in seen_endpoints:
                full_match = match.group(0).strip()
                seen_endpoints.add(name.lower())
                endpoints.append(full_match if len(full_match) < 100 else name)

        # Add extracted elements and map to domains
        for endpoint in endpoints:
            self.extracted_elements.append(ExtractedSAPElement(
                element_type='secondary_endpoint',
                name=endpoint,
                description='Secondary efficacy endpoint',
                section='Secondary Endpoints',
                original_text=endpoint,
            ))
            # Map to SDTM domain
            self._map_endpoint_to_domain(endpoint, 'Secondary Endpoints', endpoint)

        return endpoints  # Return all found endpoints

    def _extract_populations(self, sap_text: str) -> List[str]:
        """Extract analysis populations from SAP."""
        populations = []

        # Common population patterns
        pop_patterns = [
            (r'intent[- ]to[- ]treat\s*\(?ITT\)?', 'Intent-to-Treat (ITT)'),
            (r'modified\s+intent[- ]to[- ]treat\s*\(?mITT\)?', 'Modified Intent-to-Treat (mITT)'),
            (r'(?:full\s+)?analysis\s+set\s*\(?FAS\)?', 'Full Analysis Set (FAS)'),
            (r'per[- ]protocol\s*\(?PP\)?', 'Per-Protocol (PP)'),
            (r'safety\s+(?:population|analysis\s+set)', 'Safety Population'),
            (r'efficacy\s+(?:evaluable|population)', 'Efficacy Evaluable'),
            (r'pharmacokinetic\s*\(?PK\)?\s+(?:population|analysis)', 'PK Population'),
        ]

        for pattern, name in pop_patterns:
            if re.search(pattern, sap_text, re.IGNORECASE):
                populations.append(name)

                self.extracted_elements.append(ExtractedSAPElement(
                    element_type='population',
                    name=name,
                    description='Analysis population',
                    section='Analysis Populations',
                    original_text=name,
                    sdtm_domains=['DM', 'DS']
                ))

                # Add DM traceability
                self._add_domain_requirement('DM', SAPTraceability(
                    sap_section='Analysis Populations',
                    sap_text=f'{name} population defined',
                    sdtm_element='DM - Subject identifier',
                    rationale=f'Required to define {name} population membership'
                ))

        return populations

    def _extract_assessments(self, sap_text: str) -> List[Dict]:
        """Extract clinical assessments and map to SDTM domains."""
        assessments = []
        sap_lower = sap_text.lower()
        seen_contexts = set()  # Avoid duplicate mappings

        # Words that indicate QS domain (diary/PRO data) - should NOT go to FA
        qs_indicators = ['diary', 'patient-reported', 'pro', 'questionnaire', 'subscore']

        for assessment_key, (domain, description) in self.ASSESSMENT_TO_DOMAIN.items():
            if assessment_key in sap_lower:
                # Find the context
                pattern = rf'[^\n]*{re.escape(assessment_key)}[^\n]*'
                matches = re.findall(pattern, sap_text, re.IGNORECASE)

                for match in matches:
                    context = match[:200]
                    context_lower = context.lower()

                    # Skip if we've already processed very similar context
                    context_key = context_lower[:50]
                    if context_key in seen_contexts:
                        continue

                    # CRITICAL: If mapping to FA but context contains QS indicators,
                    # this is diary/PRO data that should go to QS, not FA
                    if domain == 'FA':
                        if any(qs_ind in context_lower for qs_ind in qs_indicators):
                            # Skip this FA mapping - it's diary data
                            continue

                    seen_contexts.add(context_key)

                    assessments.append({
                        'name': description,
                        'domain': domain,
                        'context': context
                    })

                    self.extracted_elements.append(ExtractedSAPElement(
                        element_type='assessment',
                        name=description,
                        description=f'Maps to {domain} domain',
                        section='Assessments',
                        original_text=context,
                        sdtm_domains=[domain]
                    ))

                    # Add domain traceability
                    self._add_domain_requirement(domain, SAPTraceability(
                        sap_section='Assessments',
                        sap_text=context,
                        sdtm_element=f'{domain} - {description}',
                        rationale=f'SAP specifies {description}'
                    ))

                    break  # Only use first valid match per assessment key

        return assessments

    def _extract_variables(self, sap_text: str) -> List[str]:
        """Extract specific variables mentioned in SAP."""
        variables = []

        # Common variable patterns
        var_patterns = [
            (r'(?:baseline|screening)\s+([a-zA-Z\s]+?)(?:\s+will|\s+is|\s+are)', 'baseline'),
            (r'change\s+from\s+baseline\s+in\s+([a-zA-Z\s]+?)(?:\s+at|\s+will|\s*\.)', 'change'),
            (r'(?:proportion|percentage)\s+of\s+(?:subjects|patients)\s+(?:with|achieving)\s+([a-zA-Z\s]+?)(?:\s+at|\s+will|\s*\.)', 'proportion'),
        ]

        for pattern, var_type in var_patterns:
            matches = re.findall(pattern, sap_text, re.IGNORECASE)
            for match in matches:
                clean_var = match.strip()
                if 3 < len(clean_var) < 100:
                    variables.append(clean_var)

        return list(set(variables))[:20]

    def _extract_treatment_arms(self, sap_text: str) -> List[str]:
        """Extract treatment arms from SAP."""
        arms = []

        # Look for treatment arm patterns
        patterns = [
            r'(?:treatment\s+)?arm[s]?[:\s]+([^\n]+)',
            r'(?:randomized|assigned)\s+to\s+([^\n\.]+)',
            r'placebo\s+(?:group|arm)',
            r'(\d+\s*mg)\s+(?:group|arm|dose)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, sap_text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, str) and len(match) > 3:
                    arms.append(match.strip())

        return list(set(arms))[:5]

    def _extract_sample_size(self, sap_text: str) -> Optional[int]:
        """Extract sample size from SAP."""
        patterns = [
            r'(?:total\s+of\s+)?(\d+)\s+(?:subjects|patients)\s+(?:will\s+be\s+)?(?:enrolled|randomized)',
            r'sample\s+size[:\s]+(\d+)',
            r'n\s*=\s*(\d+)',
            r'(\d+)\s+(?:subjects|patients)\s+per\s+(?:group|arm)',
        ]

        for pattern in patterns:
            match = re.search(pattern, sap_text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue

        return None

    def _map_endpoint_to_domain(self, endpoint: str, section: str, original_text: str):
        """Map an endpoint to SDTM domains."""
        endpoint_lower = endpoint.lower()

        # Check against assessment mappings
        for assessment_key, (domain, description) in self.ASSESSMENT_TO_DOMAIN.items():
            if assessment_key in endpoint_lower:
                self._add_domain_requirement(domain, SAPTraceability(
                    sap_section=section,
                    sap_text=original_text,
                    sdtm_element=f'{domain} - {description}',
                    rationale=f'Endpoint requires {description}'
                ))

        # Default mappings based on keywords
        if any(kw in endpoint_lower for kw in ['remission', 'response', 'clinical']):
            # Usually requires questionnaires or findings
            self._add_domain_requirement('QS', SAPTraceability(
                sap_section=section,
                sap_text=original_text,
                sdtm_element='QS - Clinical assessment',
                rationale='Clinical endpoint typically uses questionnaire data'
            ))

        if any(kw in endpoint_lower for kw in ['adverse', 'safety', 'tolerability']):
            self._add_domain_requirement('AE', SAPTraceability(
                sap_section=section,
                sap_text=original_text,
                sdtm_element='AE - Adverse Events',
                rationale='Safety endpoint requires AE data'
            ))

        if any(kw in endpoint_lower for kw in ['survival', 'death', 'mortality']):
            self._add_domain_requirement('DS', SAPTraceability(
                sap_section=section,
                sap_text=original_text,
                sdtm_element='DS - Disposition',
                rationale='Survival endpoint requires disposition data'
            ))

    def _add_domain_requirement(self, domain_code: str, traceability: SAPTraceability):
        """Add a traceability requirement for a domain."""
        if domain_code not in self.domain_requirements:
            self.domain_requirements[domain_code] = []
        self.domain_requirements[domain_code].append(traceability)


class SDTMSpecGenerator:
    """
    Generates SDTM specifications by parsing SAP text.

    This implements Sandy's vision:
    1. Parse the generated SAP document
    2. Extract specific endpoints, populations, variables
    3. Map those to SDTM domains/variables
    4. Create traceable links (SAP section → SDTM domain)
    """

    # Standard domain templates with CDISC-compliant variables
    DOMAIN_TEMPLATES: Dict[str, SDTMDomain] = {}

    def __init__(self):
        """Initialize with standard domain templates."""
        self._init_domain_templates()
        self.parser = SAPParser()

    def _init_domain_templates(self):
        """Initialize all standard SDTM domain templates."""

        # ===== SPECIAL PURPOSE DOMAINS =====

        self.DOMAIN_TEMPLATES["DM"] = SDTMDomain(
            code="DM",
            name="Demographics",
            label="Demographics",
            domain_class=DomainClass.SPECIAL_PURPOSE,
            structure="One record per subject",
            purpose="Parent domain for all subject observations",
            description="Contains demographic information for each subject in the study",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("SUBJID", "Subject Identifier for the Study", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("RFSTDTC", "Subject Reference Start Date/Time", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("RFENDTC", "Subject Reference End Date/Time", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("RFXSTDTC", "Date/Time of First Study Treatment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("RFXENDTC", "Date/Time of Last Study Treatment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("RFICDTC", "Date/Time of Informed Consent", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("RFPENDTC", "Date/Time of End of Participation", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("SITEID", "Study Site Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("BRTHDTC", "Date/Time of Birth", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("AGE", "Age", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("AGEU", "Age Units", "Char", 10, VariableCore.EXPECTED, codelist="AGEU"),
                SDTMVariable("SEX", "Sex", "Char", 1, VariableCore.REQUIRED, codelist="SEX"),
                SDTMVariable("RACE", "Race", "Char", 60, VariableCore.EXPECTED, codelist="RACE"),
                SDTMVariable("ETHNIC", "Ethnicity", "Char", 40, VariableCore.EXPECTED, codelist="ETHNIC"),
                SDTMVariable("ARMCD", "Planned Arm Code", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("ARM", "Description of Planned Arm", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("ACTARMCD", "Actual Arm Code", "Char", 20, VariableCore.EXPECTED),
                SDTMVariable("ACTARM", "Description of Actual Arm", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("COUNTRY", "Country", "Char", 3, VariableCore.REQUIRED, codelist="COUNTRY"),
                SDTMVariable("DTHFL", "Subject Death Flag", "Char", 1, VariableCore.EXPECTED, codelist="NY"),
                SDTMVariable("DTHDTC", "Date/Time of Death", "Char", 19, VariableCore.EXPECTED),
            ]
        )

        # ===== TRIAL DESIGN DOMAINS =====

        self.DOMAIN_TEMPLATES["TS"] = SDTMDomain(
            code="TS",
            name="Trial Summary",
            label="Trial Summary",
            domain_class=DomainClass.TRIAL_DESIGN,
            structure="One record per trial summary parameter",
            purpose="Contains trial-level metadata required by FDA",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("TSSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("TSPARMCD", "Trial Summary Parameter Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("TSPARM", "Trial Summary Parameter", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("TSVAL", "Parameter Value", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("TSVALNF", "Parameter Null Flavor", "Char", 2, VariableCore.EXPECTED),
                SDTMVariable("TSVALCD", "Parameter Value Code", "Char", 200, VariableCore.EXPECTED),
            ]
        )

        self.DOMAIN_TEMPLATES["TA"] = SDTMDomain(
            code="TA",
            name="Trial Arms",
            label="Trial Arms",
            domain_class=DomainClass.TRIAL_DESIGN,
            structure="One record per planned Element per Arm",
            purpose="Describes treatment arms and their elements",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("ARMCD", "Planned Arm Code", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("ARM", "Description of Planned Arm", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("TAESSION", "Planned Arm Code", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("ETCD", "Element Code", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("ELEMENT", "Description of Element", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("TABESSION", "Branch", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.REQUIRED, codelist="EPOCH"),
            ]
        )

        # ===== INTERVENTIONS DOMAINS =====

        self.DOMAIN_TEMPLATES["EX"] = SDTMDomain(
            code="EX",
            name="Exposure",
            label="Exposure",
            domain_class=DomainClass.INTERVENTIONS,
            structure="One record per constant-dosing interval per subject",
            purpose="Documents study treatment administration",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("EXSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("EXTRT", "Name of Treatment", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("EXDOSE", "Dose", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("EXDOSU", "Dose Units", "Char", 40, VariableCore.EXPECTED, codelist="UNIT"),
                SDTMVariable("EXDOSFRM", "Dose Form", "Char", 40, VariableCore.EXPECTED, codelist="FRM"),
                SDTMVariable("EXDOSFRQ", "Dosing Frequency per Interval", "Char", 40, VariableCore.EXPECTED, codelist="FREQ"),
                SDTMVariable("EXROUTE", "Route of Administration", "Char", 40, VariableCore.EXPECTED, codelist="ROUTE"),
                SDTMVariable("EXSTDTC", "Start Date/Time of Treatment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EXENDTC", "End Date/Time of Treatment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["CM"] = SDTMDomain(
            code="CM",
            name="Concomitant Medications",
            label="Concomitant/Prior Medications",
            domain_class=DomainClass.INTERVENTIONS,
            structure="One record per medication per subject",
            purpose="Documents prior and concomitant medications",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("CMSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("CMTRT", "Reported Name of Drug or Therapy", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("CMDECOD", "Standardized Medication Name", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("CMCAT", "Category for Medication", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("CMDOSE", "Dose per Administration", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("CMDOSU", "Dose Units", "Char", 40, VariableCore.EXPECTED, codelist="UNIT"),
                SDTMVariable("CMROUTE", "Route of Administration", "Char", 40, VariableCore.EXPECTED, codelist="ROUTE"),
                SDTMVariable("CMSTDTC", "Start Date/Time of Medication", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("CMENDTC", "End Date/Time of Medication", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("CMINDC", "Indication", "Char", 200, VariableCore.EXPECTED),
            ]
        )

        # ===== EVENTS DOMAINS =====

        self.DOMAIN_TEMPLATES["AE"] = SDTMDomain(
            code="AE",
            name="Adverse Events",
            label="Adverse Events",
            domain_class=DomainClass.EVENTS,
            structure="One record per adverse event per subject",
            purpose="Documents all adverse events during the study",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("AESEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("AESPID", "Sponsor-Defined Identifier", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("AETERM", "Reported Term for the Adverse Event", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("AEDECOD", "Dictionary-Derived Term", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("AEBODSYS", "Body System or Organ Class", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("AEBDSYCD", "Body System or Organ Class Code", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("AESEV", "Severity/Intensity", "Char", 20, VariableCore.EXPECTED, codelist="AESEV"),
                SDTMVariable("AESER", "Serious Event", "Char", 1, VariableCore.REQUIRED, codelist="NY"),
                SDTMVariable("AEACN", "Action Taken with Study Treatment", "Char", 40, VariableCore.EXPECTED, codelist="ACN"),
                SDTMVariable("AEREL", "Causality", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("AEOUT", "Outcome of Adverse Event", "Char", 40, VariableCore.EXPECTED, codelist="OUT"),
                SDTMVariable("AESTDTC", "Start Date/Time of Adverse Event", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("AEENDTC", "End Date/Time of Adverse Event", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["DS"] = SDTMDomain(
            code="DS",
            name="Disposition",
            label="Disposition",
            domain_class=DomainClass.EVENTS,
            structure="One record per disposition status per subject",
            purpose="Documents subject disposition and study completion status",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("DSSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("DSTERM", "Reported Term for Disposition Event", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("DSDECOD", "Standardized Disposition Term", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("DSCAT", "Category for Disposition Event", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("DSSCAT", "Subcategory for Disposition Event", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("DSSTDTC", "Start Date/Time of Disposition Event", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["MH"] = SDTMDomain(
            code="MH",
            name="Medical History",
            label="Medical History",
            domain_class=DomainClass.EVENTS,
            structure="One record per medical history event per subject",
            purpose="Documents prior medical history",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("MHSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("MHTERM", "Reported Term for the Medical History", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("MHDECOD", "Dictionary-Derived Term", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("MHCAT", "Category for Medical History", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("MHBODSYS", "Body System or Organ Class", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("MHSTDTC", "Start Date/Time of History Event", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("MHENDTC", "End Date/Time of History Event", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("MHENRF", "End Relative to Reference Period", "Char", 10, VariableCore.EXPECTED),
            ]
        )

        self.DOMAIN_TEMPLATES["DV"] = SDTMDomain(
            code="DV",
            name="Protocol Deviations",
            label="Protocol Deviations",
            domain_class=DomainClass.EVENTS,
            structure="One record per protocol deviation per subject",
            purpose="Documents protocol deviations for BIMO review",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("DVSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("DVTERM", "Protocol Deviation Term", "Char", 200, VariableCore.REQUIRED),
                SDTMVariable("DVDECOD", "Standardized Protocol Deviation Term", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("DVCAT", "Category for Protocol Deviation", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("DVSCAT", "Subcategory for Protocol Deviation", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("DVSTDTC", "Start Date/Time of Deviation", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("DVENDTC", "End Date/Time of Deviation", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        # ===== FINDINGS DOMAINS =====

        self.DOMAIN_TEMPLATES["LB"] = SDTMDomain(
            code="LB",
            name="Laboratory Test Results",
            label="Laboratory Test Results",
            domain_class=DomainClass.FINDINGS,
            structure="One record per lab test per time point per subject",
            purpose="Documents laboratory test results",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("LBSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("LBTESTCD", "Lab Test or Examination Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("LBTEST", "Lab Test or Examination Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("LBCAT", "Category for Lab Test", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("LBORRES", "Result or Finding in Original Units", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("LBORRESU", "Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("LBORNRLO", "Reference Range Lower Limit-Orig Unit", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("LBORNRHI", "Reference Range Upper Limit-Orig Unit", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("LBSTRESC", "Character Result/Finding in Std Format", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("LBSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("LBSTRESU", "Standard Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("LBNRIND", "Reference Range Indicator", "Char", 10, VariableCore.EXPECTED),
                SDTMVariable("LBSPEC", "Specimen Type", "Char", 40, VariableCore.EXPECTED, codelist="SPECTYPE"),
                SDTMVariable("LBBLFL", "Baseline Flag", "Char", 1, VariableCore.EXPECTED, codelist="NY"),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("LBDTC", "Date/Time of Specimen Collection", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("LBDY", "Study Day of Specimen Collection", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["VS"] = SDTMDomain(
            code="VS",
            name="Vital Signs",
            label="Vital Signs",
            domain_class=DomainClass.FINDINGS,
            structure="One record per vital sign per time point per subject",
            purpose="Documents vital sign measurements",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("VSSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("VSTESTCD", "Vital Signs Test Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("VSTEST", "Vital Signs Test Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("VSPOS", "Vital Signs Position of Subject", "Char", 40, VariableCore.EXPECTED, codelist="POSITION"),
                SDTMVariable("VSORRES", "Result or Finding in Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VSORRESU", "Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VSSTRESC", "Character Result/Finding in Std Format", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VSSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VSSTRESU", "Standard Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VSLOC", "Location of Vital Signs Measurement", "Char", 40, VariableCore.EXPECTED, codelist="LOC"),
                SDTMVariable("VSBLFL", "Baseline Flag", "Char", 1, VariableCore.EXPECTED, codelist="NY"),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VSDTC", "Date/Time of Measurements", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("VSDY", "Study Day of Vital Signs", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["EG"] = SDTMDomain(
            code="EG",
            name="ECG Test Results",
            label="ECG Test Results",
            domain_class=DomainClass.FINDINGS,
            structure="One record per ECG observation per time point per subject",
            purpose="Documents electrocardiogram findings",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("EGSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("EGTESTCD", "ECG Test Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("EGTEST", "ECG Test Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("EGORRES", "Result or Finding in Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("EGORRESU", "Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("EGSTRESC", "Character Result/Finding in Std Format", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("EGSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("EGSTRESU", "Standard Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("EGBLFL", "Baseline Flag", "Char", 1, VariableCore.EXPECTED, codelist="NY"),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("EGDTC", "Date/Time of ECG", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["QS"] = SDTMDomain(
            code="QS",
            name="Questionnaires",
            label="Questionnaires",
            domain_class=DomainClass.FINDINGS,
            structure="One record per questionnaire item per time point per subject",
            purpose="Documents patient-reported outcomes and questionnaires",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("QSSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("QSTESTCD", "Question Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("QSTEST", "Question Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("QSCAT", "Category for Questionnaire", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("QSSCAT", "Subcategory for Questionnaire", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("QSORRES", "Result or Finding in Original Units", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("QSSTRESC", "Character Result/Finding in Std Format", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("QSSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("QSBLFL", "Baseline Flag", "Char", 1, VariableCore.EXPECTED, codelist="NY"),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("QSDTC", "Date/Time of Assessment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["TR"] = SDTMDomain(
            code="TR",
            name="Tumor Results",
            label="Tumor/Lesion Results",
            domain_class=DomainClass.FINDINGS,
            structure="One record per tumor assessment per time point per subject",
            purpose="Documents tumor measurements for RECIST evaluation",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("TRSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("TRLNKID", "Link ID", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TRTESTCD", "Tumor Test Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("TRTEST", "Tumor Test Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("TRORRES", "Result or Finding in Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TRORRESU", "Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TRSTRESC", "Character Result/Finding in Std Format", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TRSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("TRSTRESU", "Standard Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TRMETHOD", "Method of Test", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TREVAL", "Evaluator", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("TRDTC", "Date/Time of Tumor Assessment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["RS"] = SDTMDomain(
            code="RS",
            name="Disease Response",
            label="Disease Response",
            domain_class=DomainClass.FINDINGS,
            structure="One record per response assessment per subject",
            purpose="Documents overall disease response (RECIST)",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("RSSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("RSTESTCD", "Response Test Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("RSTEST", "Response Test Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("RSCAT", "Category for Response", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("RSORRES", "Result or Finding in Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("RSSTRESC", "Character Result in Standard Format", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("RSEVAL", "Evaluator", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("RSDTC", "Date/Time of Response Assessment", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["FA"] = SDTMDomain(
            code="FA",
            name="Findings About",
            label="Findings About Events or Interventions",
            domain_class=DomainClass.FINDINGS_ABOUT,
            structure="One record per finding about per event/intervention per subject",
            purpose="Documents findings about other events or interventions (e.g., endoscopy, biopsy)",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("FASEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("FATESTCD", "Findings About Test Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("FATEST", "Findings About Test Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("FACAT", "Category for Findings About", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("FAOBJ", "Object of the Observation", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("FAORRES", "Result or Finding in Original Units", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("FASTRESC", "Character Result/Finding in Std Format", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("FASTRESN", "Numeric Result/Finding in Standard Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("FADTC", "Date/Time of Collection", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        # ===== PK DOMAINS =====

        self.DOMAIN_TEMPLATES["PC"] = SDTMDomain(
            code="PC",
            name="Pharmacokinetic Concentrations",
            label="Pharmacokinetic Concentrations",
            domain_class=DomainClass.FINDINGS,
            structure="One record per analyte per timepoint per subject",
            purpose="Documents drug concentration measurements over time",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("PCSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("PCGRPID", "Group ID", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("PCTESTCD", "Pharmacokinetic Test Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("PCTEST", "Pharmacokinetic Test Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("PCCAT", "Category for PK", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("PCORRES", "Result or Finding in Original Units", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("PCORRESU", "Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("PCSTRESC", "Character Result/Finding in Std Format", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("PCSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("PCSTRESU", "Standard Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("PCSTAT", "Completion Status", "Char", 8, VariableCore.PERMISSIBLE),
                SDTMVariable("PCREASND", "Reason Not Done", "Char", 200, VariableCore.PERMISSIBLE),
                SDTMVariable("PCSPEC", "Specimen Type", "Char", 40, VariableCore.EXPECTED, codelist="SPECTYPE"),
                SDTMVariable("PCLLOQ", "Lower Limit of Quantitation", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("PCDTC", "Date/Time of Specimen Collection", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("PCDY", "Study Day of Specimen Collection", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("PCTPT", "Planned Time Point Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("PCTPTNUM", "Planned Time Point Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("PCELTM", "Planned Elapsed Time from Reference", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("PCTPTREF", "Time Point Reference", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

        self.DOMAIN_TEMPLATES["PP"] = SDTMDomain(
            code="PP",
            name="Pharmacokinetic Parameters",
            label="Pharmacokinetic Parameters",
            domain_class=DomainClass.FINDINGS,
            structure="One record per PK parameter per analyte per subject",
            purpose="Documents derived PK parameters from NCA analysis",
            variables=[
                SDTMVariable("STUDYID", "Study Identifier", "Char", 20, VariableCore.REQUIRED),
                SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, VariableCore.REQUIRED),
                SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("PPSEQ", "Sequence Number", "Num", 8, VariableCore.REQUIRED),
                SDTMVariable("PPGRPID", "Group ID", "Char", 40, VariableCore.PERMISSIBLE),
                SDTMVariable("PPTESTCD", "Parameter Short Name", "Char", 8, VariableCore.REQUIRED),
                SDTMVariable("PPTEST", "Parameter Name", "Char", 40, VariableCore.REQUIRED),
                SDTMVariable("PPCAT", "Category for Parameter", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("PPORRES", "Result or Finding in Original Units", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("PPORRESU", "Original Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("PPSTRESC", "Character Result/Finding in Std Format", "Char", 200, VariableCore.EXPECTED),
                SDTMVariable("PPSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("PPSTRESU", "Standard Units", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("PPSPEC", "Specimen Type", "Char", 40, VariableCore.EXPECTED, codelist="SPECTYPE"),
                SDTMVariable("VISITNUM", "Visit Number", "Num", 8, VariableCore.EXPECTED),
                SDTMVariable("VISIT", "Visit Name", "Char", 40, VariableCore.EXPECTED),
                SDTMVariable("PPDTC", "Date/Time of Parameter", "Char", 19, VariableCore.PERMISSIBLE),
                SDTMVariable("PPRFTDTC", "Date/Time of Reference Point", "Char", 19, VariableCore.EXPECTED),
                SDTMVariable("EPOCH", "Epoch", "Char", 40, VariableCore.EXPECTED, codelist="EPOCH"),
            ]
        )

    def generate(self, protocol_facts: Dict[str, Any]) -> SDTMSpecification:
        """
        Generate SDTM specification from protocol facts.

        This is the main entry point. If SAP text is provided, it parses it to
        extract study-specific requirements and create traceable links.

        Args:
            protocol_facts: Dictionary containing protocol/SAP information
                - sap_text: The generated SAP document text (required for traceability)
                - protocol_id: Study identifier (fallback if not in SAP)
                - therapeutic_area: Optional therapeutic area hint

        Returns:
            SDTMSpecification with study-specific domains and traceability
        """
        sap_text = protocol_facts.get('sap_text', '')

        # Parse SAP text first to extract study_id
        sap_parsed = {}
        if sap_text:
            sap_parsed = self.parser.parse(sap_text)

        # Use extracted study_id, fall back to provided protocol_id, then UNKNOWN
        protocol_id = (
            sap_parsed.get('study_id') or
            protocol_facts.get('protocol_id') or
            protocol_facts.get('nct_id') or
            'UNKNOWN'
        )

        spec = SDTMSpecification(
            protocol_id=protocol_id,
            generated_at=datetime.now().isoformat(),
            sdtm_version="3.4"
        )

        if sap_parsed:
            spec.extracted_elements = sap_parsed.get('extracted_elements', [])
            spec.sap_summary = {
                'study_id': sap_parsed.get('study_id'),
                'drug_name': sap_parsed.get('drug_name'),
                'primary_endpoint': sap_parsed.get('primary_endpoint'),
                'primary_timepoint': sap_parsed.get('primary_timepoint'),
                'secondary_endpoints': sap_parsed.get('secondary_endpoints', []),
                'populations': sap_parsed.get('populations', []),
                'treatment_arms': sap_parsed.get('treatment_arms', []),
                'sample_size': sap_parsed.get('sample_size'),
            }

        # Determine which domains are needed
        required_domains = self._determine_required_domains(protocol_facts, sap_parsed)

        # Generate specification for each domain
        domain_requirements = sap_parsed.get('domain_requirements', {})
        for domain_code in required_domains:
            domain = self._generate_domain_spec(domain_code, protocol_facts, domain_requirements)
            if domain:
                spec.domains.append(domain)

        # Add Define-XML notes
        spec.define_xml_notes = self._generate_define_notes(protocol_facts, sap_parsed, required_domains, protocol_id)

        return spec

    def _determine_required_domains(self, protocol_facts: Dict[str, Any], sap_parsed: Dict) -> List[str]:
        """Determine which SDTM domains are required based on SAP parsing."""
        required = set()

        # ===== ALWAYS REQUIRED =====
        required.add("DM")   # Demographics - always required
        required.add("AE")   # Adverse Events - always required for safety
        required.add("DS")   # Disposition - always required
        required.add("EX")   # Exposure - always required
        required.add("TS")   # Trial Summary - required by FDA
        required.add("TA")   # Trial Arms - required for randomized studies

        # ===== USUALLY REQUIRED =====
        required.add("CM")   # Concomitant Meds - almost always needed
        required.add("MH")   # Medical History - usually collected
        required.add("VS")   # Vital Signs - standard safety measure
        required.add("LB")   # Labs - standard safety measure
        required.add("DV")   # Protocol deviations - required by FDA

        # ===== SAP-DERIVED REQUIREMENTS =====
        # Add domains based on what was found in the SAP
        domain_requirements = sap_parsed.get('domain_requirements', {})
        for domain_code in domain_requirements.keys():
            if domain_code in self.DOMAIN_TEMPLATES:
                required.add(domain_code)

        # Check assessments found in SAP
        assessments = sap_parsed.get('assessments', [])
        for assessment in assessments:
            domain = assessment.get('domain')
            if domain and domain in self.DOMAIN_TEMPLATES:
                required.add(domain)

        return sorted(list(required))

    def _generate_domain_spec(self, domain_code: str, protocol_facts: Dict[str, Any],
                             domain_requirements: Dict[str, List[SAPTraceability]]) -> Optional[SDTMDomain]:
        """Generate specification for a specific domain with traceability."""
        if domain_code not in self.DOMAIN_TEMPLATES:
            return None

        template = self.DOMAIN_TEMPLATES[domain_code]

        # Create a copy with protocol-specific customizations
        domain = SDTMDomain(
            code=template.code,
            name=template.name,
            label=template.label,
            domain_class=template.domain_class,
            structure=template.structure,
            purpose=template.purpose,
            description=template.description,
            variables=[
                SDTMVariable(
                    name=v.name,
                    label=v.label,
                    type=v.type,
                    length=v.length,
                    core=v.core,
                    codelist=v.codelist,
                    description=v.description,
                    source=v.source,
                )
                for v in template.variables
            ]
        )

        # Add traceability from SAP parsing
        if domain_code in domain_requirements:
            domain.traceability = domain_requirements[domain_code]

        # Add study-specific notes based on SAP
        domain.study_specific_notes = self._get_study_specific_notes(domain_code, protocol_facts, domain_requirements)

        # Map to TLFs
        domain.required_for = self._map_domain_to_tlf(domain_code, protocol_facts)

        return domain

    def _get_study_specific_notes(self, domain_code: str, protocol_facts: Dict[str, Any],
                                  domain_requirements: Dict[str, List[SAPTraceability]]) -> List[str]:
        """Generate study-specific notes for a domain based on SAP analysis."""
        notes = []

        if domain_code in domain_requirements:
            traces = domain_requirements[domain_code]
            for trace in traces[:3]:  # Limit to top 3
                notes.append(f"Required for: {trace.sdtm_element} (from {trace.sap_section})")

        return notes

    def _map_domain_to_tlf(self, domain_code: str, protocol_facts: Dict[str, Any]) -> List[str]:
        """Map domain to TLFs that require it."""
        mapping = {
            "DM": ["Table 14.1.1 Demographics", "Listing 16.2.1 Demographics"],
            "AE": ["Table 14.3.1 AE Summary", "Table 14.3.2 AE by SOC/PT", "Listing 16.2.7 Adverse Events"],
            "DS": ["Table 14.1.2 Disposition"],
            "EX": ["Table 14.1.3 Exposure Summary"],
            "CM": ["Listing 16.2.4 Concomitant Medications"],
            "MH": ["Table 14.1.4 Medical History"],
            "LB": ["Table 14.3.8 Laboratory Shift Tables"],
            "VS": ["Table 14.3.9 Vital Signs Summary"],
            "EG": ["Table 14.3.10 ECG Findings"],
            "QS": ["Table 14.2.x Efficacy Endpoints (PRO)"],
            "TR": ["Table 14.2.x Tumor Response"],
            "RS": ["Table 14.2.x Disease Response (RECIST)"],
            "DV": ["Listing 16.1.2 Protocol Deviations"],
            "FA": ["Listing 16.2.x Findings About Events"],
        }
        return mapping.get(domain_code, [])

    def _generate_define_notes(self, protocol_facts: Dict[str, Any], sap_parsed: Dict,
                              domains: List[str], study_id: str) -> List[str]:
        """Generate notes for Define-XML preparation."""
        notes = [
            "Define-XML v2.1 should be used for FDA submissions",
            f"Study identifier: {study_id}",
            f"Total domains: {len(domains)}",
            "Ensure all codelists are mapped to NCI CDISC controlled terminology",
            "MedDRA version should be documented in Define-XML",
        ]

        # Add drug name if extracted
        if sap_parsed.get('drug_name'):
            notes.append(f"Study drug: {sap_parsed['drug_name']}")

        # Add SAP-derived notes
        if sap_parsed.get('primary_endpoint'):
            endpoint = sap_parsed['primary_endpoint']
            if len(endpoint) > 100:
                endpoint = endpoint[:100] + "..."
            notes.append(f"Primary endpoint: {endpoint}")

        if sap_parsed.get('primary_timepoint'):
            notes.append(f"Primary timepoint: {sap_parsed['primary_timepoint']}")

        if sap_parsed.get('populations'):
            notes.append(f"Analysis populations: {', '.join(sap_parsed['populations'])}")

        if sap_parsed.get('secondary_endpoints'):
            notes.append(f"Secondary endpoints: {len(sap_parsed['secondary_endpoints'])} defined")

        return notes

    def save_specification(self, spec: SDTMSpecification, output_dir: str) -> Dict[str, str]:
        """Save specification to files."""
        import os
        import json

        os.makedirs(output_dir, exist_ok=True)
        saved_files = {}

        # Save markdown documentation
        md_path = os.path.join(output_dir, "sdtm_specification.md")
        with open(md_path, 'w') as f:
            f.write(spec.to_markdown())
        saved_files['markdown'] = md_path

        # Save JSON for programmatic use
        json_path = os.path.join(output_dir, "sdtm_specification.json")
        with open(json_path, 'w') as f:
            json.dump({
                "protocol_id": spec.protocol_id,
                "generated_at": spec.generated_at,
                "sdtm_version": spec.sdtm_version,
                "sap_summary": spec.sap_summary,
                "domains": [d.to_dict() for d in spec.domains],
                "define_xml_notes": spec.define_xml_notes
            }, f, indent=2)
        saved_files['json'] = json_path

        return saved_files


# Factory function
def create_sdtm_spec_generator() -> SDTMSpecGenerator:
    """Create an SDTM specification generator."""
    return SDTMSpecGenerator()
