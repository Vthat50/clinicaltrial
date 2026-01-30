#!/usr/bin/env python3
"""
Structured Fact Extractor for Production SAP Generation
========================================================
Extracts ALL protocol facts as structured data using regex/rules.
NO LLM involved - pure deterministic extraction.

This is LAYER 1 of the production pipeline:
Protocol → StructuredFactExtractor → JSON Facts → LLM Generation → Validation
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pydantic import BaseModel, Field
from enum import Enum


class RouteOfAdministration(str, Enum):
    IV = "intravenous"
    SC = "subcutaneous"
    IM = "intramuscular"
    ORAL = "oral"
    TOPICAL = "topical"
    INHALED = "inhaled"
    OTHER = "other"


class StudyPhase(str, Enum):
    PHASE_1 = "Phase 1"
    PHASE_1_2 = "Phase 1/2"
    PHASE_2 = "Phase 2"
    PHASE_2_3 = "Phase 2/3"
    PHASE_3 = "Phase 3"
    PHASE_4 = "Phase 4"
    UNKNOWN = "Unknown"


class TrialDesignType(str, Enum):
    """Critical: Determines template selection and statistical approach"""
    SINGLE_ARM = "single_arm"                    # No control, descriptive stats only
    RANDOMIZED_CONTROLLED = "randomized_controlled"  # RCT with control arm
    RANDOMIZED_OPEN_LABEL = "randomized_open_label"  # Randomized but not blinded
    NON_RANDOMIZED_COMPARATIVE = "non_randomized_comparative"  # Comparative but not randomized
    UNKNOWN = "unknown"


class TreatmentArm(BaseModel):
    """
    A treatment arm in the study.

    Note: This is the canonical TreatmentArm definition used throughout the pipeline.
    The schemas.py version is deprecated - use this one.
    """
    name: str
    description: Optional[str] = None  # Added for compatibility with schemas.py
    dose: Optional[str] = None
    schedule: Optional[str] = None     # Added for compatibility with schemas.py
    route: Optional[str] = None
    frequency: Optional[str] = None
    n_patients: Optional[int] = None
    is_placebo: bool = False
    is_control: bool = False           # Added for compatibility with schemas.py
    is_active_comparator: bool = False

    def __init__(self, **data):
        # Auto-populate description from name if not provided
        if 'description' not in data or data['description'] is None:
            data['description'] = data.get('name', '')
        super().__init__(**data)


class EndpointDefinition(BaseModel):
    """Definition of an endpoint"""
    name: str
    definition: str
    timepoint: Optional[str] = None
    scoring_system: Optional[str] = None
    components: List[str] = Field(default_factory=list)


class AlphaSpecification(BaseModel):
    """Alpha/significance level specification"""
    primary_alpha: float = 0.05
    sidedness: str = "two-sided"  # "one-sided" or "two-sided"
    additional_levels: List[float] = Field(default_factory=list)
    multiplicity_adjustment: Optional[str] = None


class SampleSizeSpec(BaseModel):
    """Sample size specification"""
    total_n: int
    per_arm: Dict[str, int] = Field(default_factory=dict)
    power: Optional[float] = None
    effect_size: Optional[str] = None
    dropout_rate: Optional[float] = None


class PKSubstudy(BaseModel):
    """PK substudy specification"""
    has_pk_substudy: bool = False
    pk_population_size: Optional[int] = None
    pk_sampling_timepoints: List[str] = Field(default_factory=list)
    pk_parameters: List[str] = Field(default_factory=list)  # AUC, Cmax, etc.
    pk_analysis_software: Optional[str] = None  # WinNonlin, Phoenix, etc.


class ImmunogenicityAssessment(BaseModel):
    """Immunogenicity/ADA specification"""
    has_immunogenicity: bool = False
    ada_sampling_timepoints: List[str] = Field(default_factory=list)
    antibody_type: Optional[str] = None  # Anti-drug antibodies
    assay_method: Optional[str] = None


class SubgroupAnalysis(BaseModel):
    """Subgroup analysis specification"""
    factor: str
    categories: List[str] = Field(default_factory=list)
    rationale: Optional[str] = None


class InterimAnalysis(BaseModel):
    """Interim analysis specification"""
    has_interim: bool = False
    interim_timepoints: List[str] = Field(default_factory=list)
    monitoring_committee: Optional[str] = None  # DMC, SRC, etc.
    stopping_rules: List[str] = Field(default_factory=list)


class ProtocolFacts(BaseModel):
    """
    Complete structured facts extracted from protocol.
    This is the SINGLE SOURCE OF TRUTH for SAP generation.
    """
    # Identifiers
    nct_id: Optional[str] = None
    study_id: Optional[str] = None
    protocol_title: Optional[str] = None
    sponsor: Optional[str] = None

    # Study Design
    phase: StudyPhase = StudyPhase.UNKNOWN
    therapeutic_area: Optional[str] = None
    indication: Optional[str] = None
    design_type: Optional[str] = None  # "randomized", "open-label", etc.
    is_blinded: bool = False
    blinding_type: Optional[str] = None  # "double-blind", "single-blind", "open-label"

    # Drug/Treatment
    drug_name: Optional[str] = None
    drug_names_all: List[str] = Field(default_factory=list)
    route_of_administration: RouteOfAdministration = RouteOfAdministration.OTHER

    # Arms and Randomization
    num_arms: int = 0
    arms: List[TreatmentArm] = Field(default_factory=list)
    randomization_ratio: Optional[str] = None
    stratification_factors: List[str] = Field(default_factory=list)

    # Sample Size
    sample_size: SampleSizeSpec = Field(default_factory=lambda: SampleSizeSpec(total_n=0))

    # Endpoints
    primary_endpoint: Optional[EndpointDefinition] = None
    secondary_endpoints: List[EndpointDefinition] = Field(default_factory=list)

    # Statistical
    alpha: AlphaSpecification = Field(default_factory=AlphaSpecification)
    primary_analysis_method: Optional[str] = None
    primary_analysis_population: Optional[str] = None  # ITT, FAS, PP, etc.

    # Populations
    itt_definition: Optional[str] = None
    fas_definition: Optional[str] = None
    pp_definition: Optional[str] = None
    safety_population_definition: Optional[str] = None
    pk_population_definition: Optional[str] = None

    # Timepoints
    primary_timepoint: Optional[str] = None
    study_duration: Optional[str] = None
    treatment_duration: Optional[str] = None

    # PK Analysis (NEW)
    pk_substudy: PKSubstudy = Field(default_factory=PKSubstudy)

    # Immunogenicity (NEW)
    immunogenicity: ImmunogenicityAssessment = Field(default_factory=ImmunogenicityAssessment)

    # Subgroup Analyses (NEW)
    subgroup_analyses: List[SubgroupAnalysis] = Field(default_factory=list)

    # Interim Analysis (NEW)
    interim_analysis: InterimAnalysis = Field(default_factory=InterimAnalysis)


class StructuredFactExtractor:
    """
    Extracts ALL protocol facts using regex/rules - NO LLM.

    This ensures:
    1. Deterministic extraction (same input → same output)
    2. No hallucination (only extracts what's actually there)
    3. Fast execution (no API calls)
    4. Auditable (every extraction has a pattern)
    """

    def extract_all(self, protocol_text: str) -> ProtocolFacts:
        """
        Extract all facts from protocol.

        Args:
            protocol_text: Full protocol document text

        Returns:
            ProtocolFacts with all extracted values
        """
        facts = ProtocolFacts()

        # Identifiers
        facts.nct_id = self._extract_nct_id(protocol_text)
        facts.study_id = self._extract_study_id(protocol_text)
        facts.protocol_title = self._extract_title(protocol_text)
        facts.sponsor = self._extract_sponsor(protocol_text)

        # Study Design
        facts.phase = self._extract_phase(protocol_text)
        facts.therapeutic_area = self._extract_therapeutic_area(protocol_text)
        facts.indication = self._extract_indication(protocol_text)
        facts.design_type = self._extract_design_type(protocol_text)
        facts.is_blinded, facts.blinding_type = self._extract_blinding(protocol_text)

        # Drug/Treatment
        facts.drug_name, facts.drug_names_all = self._extract_drug_names(protocol_text)
        facts.route_of_administration = self._extract_route(protocol_text)

        # Arms and Randomization
        facts.arms = self._extract_arms(protocol_text)
        facts.num_arms = len(facts.arms) if facts.arms else self._extract_num_arms(protocol_text)
        facts.randomization_ratio = self._extract_randomization_ratio(protocol_text)
        facts.stratification_factors = self._extract_stratification_factors(protocol_text)

        # CRITICAL: Ensure consistency between design_type and num_arms
        # If design says "single-arm", force num_arms=1 regardless of arm extraction
        if facts.design_type and 'single-arm' in facts.design_type.lower():
            if facts.num_arms != 1:
                print(f"[DEBUG] Design says single-arm but found {facts.num_arms} arms - forcing num_arms=1")
                facts.num_arms = 1
                facts.arms = facts.arms[:1] if facts.arms else []  # Keep only first arm if any

        # Sample Size
        facts.sample_size = self._extract_sample_size(protocol_text, facts.num_arms)

        # Endpoints
        facts.primary_endpoint = self._extract_primary_endpoint(protocol_text)
        facts.secondary_endpoints = self._extract_secondary_endpoints(protocol_text)

        # Statistical
        facts.alpha = self._extract_alpha(protocol_text)
        facts.primary_analysis_method = self._extract_primary_analysis_method(protocol_text)
        facts.primary_analysis_population = self._extract_analysis_population(protocol_text)

        # Populations
        facts.itt_definition = self._extract_population_definition(protocol_text, "ITT")
        facts.fas_definition = self._extract_population_definition(protocol_text, "FAS")
        facts.pp_definition = self._extract_population_definition(protocol_text, "PP")
        facts.safety_population_definition = self._extract_population_definition(protocol_text, "safety")

        # Timepoints
        facts.primary_timepoint = self._extract_primary_timepoint(protocol_text)
        facts.study_duration = self._extract_study_duration(protocol_text)

        # PK Substudy (NEW)
        facts.pk_substudy = self._extract_pk_substudy(protocol_text)
        facts.pk_population_definition = self._extract_population_definition(protocol_text, "PK")

        # Immunogenicity (NEW)
        facts.immunogenicity = self._extract_immunogenicity(protocol_text)

        # Subgroup Analyses (NEW)
        facts.subgroup_analyses = self._extract_subgroup_analyses(protocol_text)

        # Interim Analysis (NEW)
        facts.interim_analysis = self._extract_interim_analysis(protocol_text)

        return facts

    def _extract_nct_id(self, text: str) -> Optional[str]:
        """Extract NCT ID - handles various formats"""
        # Try multiple patterns for NCT ID
        patterns = [
            r'NCT\d{8}',              # Standard: NCT02613507
            r'NCT[-\s]?\d{8}',        # With dash/space: NCT-02613507 or NCT 02613507
            r'NCT[-\s]?\d{2}[-\s]?\d{6}',  # Split: NCT02-613507
            r'NCT\s*#?\s*\d{8}',      # With hash: NCT# 02613507
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Extract just the digits and format properly
                digits = re.sub(r'[^\d]', '', match.group(0))
                if len(digits) == 8:
                    return f"NCT{digits}"
        return None

    def _extract_study_id(self, text: str) -> Optional[str]:
        """Extract internal study ID (e.g., CTJ301UC201)"""
        patterns = [
            r'\b([A-Z]{2,5}\d{3,4}[A-Z]{0,3}\d{0,3})\b',
            r'(?:study|protocol)\s+(?:id|number|#)?[:\s]+([A-Z0-9-]{5,20})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                study_id = match.group(1)
                # Filter out common non-study-ID patterns
                if not re.match(r'^(NCT|EUR|IND|NDA|BLA|ICH|FDA|EMA)\d', study_id):
                    return study_id
        return None

    def _extract_title(self, text: str) -> Optional[str]:
        """Extract protocol title"""
        patterns = [
            r'(?:protocol\s+)?title[:\s]+([^\n]+)',
            r'^([A-Z][^.]+(?:study|trial|evaluation)[^.]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text[:3000], re.IGNORECASE | re.MULTILINE)
            if match:
                title = match.group(1).strip()
                if len(title) > 20 and len(title) < 500:
                    return title
        return None

    def _extract_sponsor(self, text: str) -> Optional[str]:
        """Extract sponsor name - handles hyphens and complex names"""
        # Known pharma company names (direct match first)
        known_sponsors = [
            'Bristol-Myers Squibb', 'Bristol Myers Squibb', 'BMS',
            'Pfizer', 'Merck', 'Novartis', 'Roche', 'Genentech',
            'AstraZeneca', 'Johnson & Johnson', 'Janssen', 'Eli Lilly',
            'Sanofi', 'GlaxoSmithKline', 'GSK', 'AbbVie', 'Amgen',
            'Gilead', 'Biogen', 'Regeneron', 'Takeda', 'Bayer',
            'Boehringer Ingelheim', 'Novo Nordisk', 'Astellas',
        ]
        text_lower = text.lower()
        for sponsor in known_sponsors:
            if sponsor.lower() in text_lower:
                return sponsor

        # Pattern-based extraction (handles hyphens and various formats)
        patterns = [
            # "Sponsor: Company Name" or "Sponsored by Company Name"
            r'(?:sponsor|sponsored\s+by)[:\s]+([A-Za-z][A-Za-z\s&,\-\.]+(?:Inc\.?|LLC|Ltd\.?|Corp\.?|Company|Pharma(?:ceuticals)?|Therapeutics|Sciences)?)',
            # "conducted by" or "supported by"
            r'(?:conducted\s+by|supported\s+by)[:\s]+([A-Za-z][A-Za-z\s&,\-\.]+)',
            # Company name followed by "is the sponsor"
            r'([A-Z][A-Za-z\s&,\-\.]+(?:Inc\.?|LLC|Ltd\.?|Corp\.?|Company))\s+(?:is\s+the\s+)?sponsor',
        ]
        for pattern in patterns:
            match = re.search(pattern, text[:10000], re.IGNORECASE)
            if match:
                sponsor = match.group(1).strip()
                # Clean up and validate
                sponsor = re.sub(r'\s+', ' ', sponsor)  # Normalize whitespace
                if len(sponsor) > 3 and len(sponsor) < 100:
                    # Filter out false positives
                    if sponsor.lower() not in ['the', 'this', 'a', 'an', 'study', 'trial']:
                        return sponsor
        return None

    def _extract_phase(self, text: str) -> StudyPhase:
        """Extract study phase"""
        text_lower = text.lower()

        if re.search(r'phase\s*[12]/[23]|phase\s*1/2|phase\s*2/3', text_lower):
            if 'phase 1/2' in text_lower or 'phase i/ii' in text_lower:
                return StudyPhase.PHASE_1_2
            return StudyPhase.PHASE_2_3
        elif re.search(r'phase\s*(?:4|iv|four)', text_lower):
            return StudyPhase.PHASE_4
        elif re.search(r'phase\s*(?:3|iii|three)', text_lower):
            return StudyPhase.PHASE_3
        elif re.search(r'phase\s*(?:2|ii|two)', text_lower):
            return StudyPhase.PHASE_2
        elif re.search(r'phase\s*(?:1|i|one)', text_lower):
            return StudyPhase.PHASE_1

        return StudyPhase.UNKNOWN

    def _extract_therapeutic_area(self, text: str) -> Optional[str]:
        """Extract therapeutic area"""
        text_lower = text.lower()

        ta_patterns = {
            'IBD': r'ulcerative\s+colitis|crohn|inflammatory\s+bowel|IBD',
            'Oncology': r'cancer|tumor|carcinoma|lymphoma|leukemia|melanoma|metastatic|neoplasm',
            'Cardiology': r'heart\s+failure|cardiac|cardiovascular|myocardial|hypertension',
            'Neurology': r'alzheimer|parkinson|multiple\s+sclerosis|epilepsy|stroke',
            'Rheumatology': r'rheumatoid|arthritis|lupus|psoriatic|ankylosing',
            'Dermatology': r'psoriasis|atopic\s+dermatitis|eczema',
            'Pulmonology': r'asthma|COPD|pulmonary|respiratory',
            'Endocrinology': r'diabetes|thyroid|metabolic',
            'Infectious': r'HIV|hepatitis|infection|bacterial|viral',
        }

        for ta, pattern in ta_patterns.items():
            if re.search(pattern, text_lower):
                return ta

        return None

    def _extract_indication(self, text: str) -> Optional[str]:
        """Extract disease indication"""
        patterns = [
            r'(?:patients?\s+with|diagnosis\s+of|treatment\s+of)\s+([a-zA-Z\s\'-]+(?:disease|syndrome|disorder|cancer|colitis|arthritis))',
            r'(?:indication)[:\s]+([^\n]+)',
            r'(?:moderate[- ]to[- ]severe|mild[- ]to[- ]moderate)\s+([a-zA-Z\s\']+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text[:10000], re.IGNORECASE)
            if match:
                indication = match.group(1).strip()
                if len(indication) > 5 and len(indication) < 100:
                    return indication
        return None

    def _extract_design_type(self, text: str) -> Optional[str]:
        """Extract study design type"""
        text_lower = text.lower()

        design_parts = []

        # CRITICAL: Check for single-arm FIRST (takes priority)
        is_single_arm = any(x in text_lower for x in [
            'single-arm', 'single arm', 'one-arm', 'one arm',
            'non-randomized', 'nonrandomized'
        ])

        if is_single_arm:
            design_parts.append('single-arm')
        elif 'randomized' in text_lower or 'randomised' in text_lower:
            design_parts.append('randomized')

        if 'double-blind' in text_lower or 'double blind' in text_lower:
            design_parts.append('double-blind')
        elif 'single-blind' in text_lower or 'single blind' in text_lower:
            design_parts.append('single-blind')
        elif 'open-label' in text_lower or 'open label' in text_lower:
            design_parts.append('open-label')
        if 'placebo-controlled' in text_lower or 'placebo controlled' in text_lower:
            design_parts.append('placebo-controlled')
        if 'parallel' in text_lower:
            design_parts.append('parallel-group')
        if 'crossover' in text_lower:
            design_parts.append('crossover')

        return ', '.join(design_parts) if design_parts else None

    def _extract_blinding(self, text: str) -> Tuple[bool, Optional[str]]:
        """Extract blinding information"""
        text_lower = text.lower()

        if 'double-blind' in text_lower or 'double blind' in text_lower:
            return True, 'double-blind'
        elif 'single-blind' in text_lower or 'single blind' in text_lower:
            return True, 'single-blind'
        elif 'open-label' in text_lower or 'open label' in text_lower:
            return False, 'open-label'

        return False, None

    def _extract_drug_names(self, text: str) -> Tuple[Optional[str], List[str]]:
        """Extract drug/compound names"""
        drug_names = set()

        # Pattern 1: Drug codes (TJ301, PF-06480605, etc.)
        code_patterns = [
            r'\b([A-Z]{2,4}[-]?\d{5,8})\b',  # PF-06480605
            r'\b([A-Z]{2,3}\d{3,4})\b',  # TJ301
        ]
        for pattern in code_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if not re.match(r'^(NCT|EUR|IND|NDA|BLA)\d', match, re.IGNORECASE):
                    drug_names.add(match.upper())

        # Pattern 2: INN names (biologics: -mab, -nib; small molecules: -statin, etc.)
        # Comprehensive list of INN stems covering all drug classes
        inn_patterns = [
            # Biologics (monoclonal antibodies, fusion proteins)
            r'\b([A-Za-z]{4,}(?:mab|nib|lib|zumab|ximab|tinib|ciclib|rafenib|lisib|metinib))\b',
            # S1P modulators and immunomodulators
            r'\b([A-Za-z]{4,}(?:simod|limod|imod|nimod|rimod))\b',
            # Small molecules - cardiovascular
            r'\b([A-Za-z]{4,}(?:pril|sartan|olol|dipine|afil|tadil|denafil))\b',
            # Small molecules - anti-infective
            r'\b([A-Za-z]{4,}(?:cillin|mycin|cycline|floxacin|azole|conazole|fungin))\b',
            # Small molecules - metabolic
            r'\b([A-Za-z]{4,}(?:statin|fibrate|gliptin|glutide|gliflozin|formin))\b',
            # Small molecules - GI/acid
            r'\b([A-Za-z]{4,}(?:prazole|tidine|pride))\b',
            # Oncology - targeted therapy
            r'\b([A-Za-z]{4,}(?:parib|platin|taxel|mustine|bine|rubicin|mycin))\b',
            # Oncology - kinase inhibitors
            r'\b([A-Za-z]{4,}(?:tinib|nib|fenib|ertinib|afenib|anib))\b',
            # JAK inhibitors
            r'\b([A-Za-z]{4,}(?:citinib|itinib))\b',
            # Other common stems
            r'\b([A-Za-z]{4,}(?:vir|navir|tegravir|buvir))\b',  # Antivirals
            r'\b([A-Za-z]{4,}(?:lukast|zumab|ximab))\b',  # Anti-inflammatory
        ]
        for pattern in inn_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                drug_names.add(match.lower())

        # Pattern 3: Named as investigational product or in study title
        ip_patterns = [
            r'(?:investigational\s+(?:product|drug|medicinal\s+product)|IMP)[:\s]+([A-Za-z][A-Za-z0-9-]{2,})',
            r'(?:study\s+drug)[:\s]+([A-Za-z][A-Za-z0-9-]{2,})',
            # Study title patterns
            r'(?:Study\s+of|Trial\s+of)\s+([A-Za-z][A-Za-z0-9-]{3,})',
            r'(?:Controlled\s+Study\s+of)\s+([A-Za-z][A-Za-z0-9-]{3,})',
            # Receive patterns
            r'(?:receive|receiving)\s+(?:either\s+)?([A-Za-z][A-Za-z0-9-]{3,})\s+(?:\d+\s*mg)?',
            r'(?:randomized\s+to)\s+(?:receive\s+)?([A-Za-z][A-Za-z0-9-]{3,})',
            # Drug vs placebo patterns
            r'([A-Za-z][A-Za-z0-9-]{3,})\s+(?:versus|vs\.?)\s+placebo',
            r'([A-Za-z][A-Za-z0-9-]{3,})\s+\d+\s*(?:mg|mcg|ug)\s+(?:once|twice|daily|weekly)',
        ]
        for pattern in ip_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 2 and name.lower() not in ['the', 'and', 'or', 'with']:
                    drug_names.add(name)

        # Filter out common false positives and biomarker codes
        false_positives = {'patients', 'subjects', 'treatment', 'placebo', 'study', 'trial'}
        # CD### patterns are usually biomarkers (CD137, CD19, CD20), not drug names
        biomarker_pattern = re.compile(r'^CD\d{1,3}$', re.IGNORECASE)
        drug_names = {d for d in drug_names
                      if d.lower() not in false_positives
                      and not biomarker_pattern.match(d)}

        drug_list = list(drug_names)

        # DEBUG: Print all found drug names for troubleshooting
        if drug_list:
            print(f"[DEBUG] All drug names found in protocol: {drug_list}")

        # PRIORITY 0: Investigational Product explicitly named
        # Look for "Study of X" or "investigational product: X" patterns
        investigational_patterns = [
            r'(?:investigational\s+(?:product|drug|medicinal\s+product)|IMP)[:\s]+([A-Za-z][A-Za-z0-9-]{2,})',
            r'(?:study\s+drug)[:\s]+([A-Za-z][A-Za-z0-9-]{2,})',
            r'BMS-\d+\s*\(([A-Za-z]+)\)',  # BMS-936558 (Nivolumab)
            r'Study\s+of\s+([A-Za-z]+(?:mab|nib|mod))\s+(?:versus|vs)',  # Study of Nivolumab vs
        ]
        for pattern in investigational_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                inv_drug = match.group(1).strip()
                if inv_drug.lower() in [d.lower() for d in drug_list]:
                    print(f"[DEBUG] Investigational product found: {inv_drug}")
                    return inv_drug, drug_list

        # PRIORITY 1: INN drug names (end in -mab, -nib, -mod, etc.) - HIGHEST PRIORITY
        # These are actual drug names, not codes
        inn_suffixes = ('mab', 'nib', 'lib', 'mod', 'vir', 'pril', 'statin', 'sartan',
                        'olol', 'prazole', 'tidine', 'cillin', 'mycin', 'zole', 'parib',
                        'platin', 'taxel', 'tinib', 'ciclib', 'lukast', 'gliptin', 'glutide')

        # KNOWN REFERENCE/COMPARATOR drugs - these are NOT the investigational drug
        # These are commonly used as comparators or mentioned as prior therapy
        known_reference_drugs = {
            # IBD/Rheumatology reference drugs
            'adalimumab', 'infliximab', 'vedolizumab', 'ustekinumab', 'golimumab',
            'certolizumab', 'natalizumab', 'etanercept', 'rituximab', 'tocilizumab',
            'sarilumab', 'secukinumab', 'ixekizumab', 'guselkumab', 'risankizumab',
            'tofacitinib', 'baricitinib', 'upadacitinib', 'filgotinib',
            # Oncology - Checkpoint inhibitors
            'ipilimumab', 'pembrolizumab', 'nivolumab', 'atezolizumab', 'durvalumab',
            'avelumab', 'cemiplimab', 'tremelimumab',
            # Oncology - Other targeted antibodies
            'bevacizumab', 'trastuzumab', 'cetuximab', 'panitumumab', 'pertuzumab',
            'ramucirumab', 'necitumumab', 'obinutuzumab', 'daratumumab', 'elotuzumab',
            # Oncology - Small molecule targeted therapies
            'erlotinib', 'gefitinib', 'afatinib', 'osimertinib', 'crizotinib',
            'alectinib', 'ceritinib', 'brigatinib', 'lorlatinib', 'entrectinib',
            'imatinib', 'dasatinib', 'nilotinib', 'bosutinib', 'ponatinib',
            'vemurafenib', 'dabrafenib', 'trametinib', 'cobimetinib', 'binimetinib',
            'olaparib', 'rucaparib', 'niraparib', 'talazoparib',
            'palbociclib', 'ribociclib', 'abemaciclib',
            'sorafenib', 'sunitinib', 'pazopanib', 'axitinib', 'cabozantinib', 'lenvatinib',
            'lapatinib', 'neratinib', 'tucatinib',
            # Oncology - Chemotherapy (commonly compared against)
            'carboplatin', 'cisplatin', 'oxaliplatin', 'paclitaxel', 'docetaxel',
            'gemcitabine', 'pemetrexed', 'capecitabine', 'fluorouracil', 'irinotecan',
            'doxorubicin', 'epirubicin', 'cyclophosphamide', 'etoposide', 'vinorelbine',
            # Oncology - Hormone therapies
            'tamoxifen', 'letrozole', 'anastrozole', 'exemestane', 'fulvestrant',
            'enzalutamide', 'abiraterone', 'apalutamide', 'darolutamide',
            # Other common reference drugs
            'methotrexate', 'azathioprine', 'mercaptopurine', 'prednisone', 'budesonide',
            'leflunomide', 'sulfasalazine', 'hydroxychloroquine',
        }

        # PRIORITY 1: Drug codes (TJ301, BMS-936558, PF-06480605, etc.)
        # Check these FIRST because they're clearly investigational products
        drug_codes = [d for d in drug_list if re.match(r'^[A-Z]{2,4}[-]?\d{3,}$', d)]
        if drug_codes:
            # Prefer codes with company prefix pattern (BMS-, PF-, etc.)
            company_codes = [d for d in drug_codes if re.match(r'^[A-Z]{2,3}[-]\d{5,}$', d)]
            if company_codes:
                print(f"[DEBUG] Company drug codes found: {company_codes}, selecting: {company_codes[0]}")
                return company_codes[0], drug_list
            # Fallback to any drug code
            drug_codes.sort(key=len, reverse=True)
            print(f"[DEBUG] Drug codes found: {drug_codes}, selecting: {drug_codes[0]}")
            return drug_codes[0], drug_list

        # PRIORITY 2: INN names that are NOT known reference drugs
        inn_names = [d for d in drug_list if any(d.lower().endswith(s) for s in inn_suffixes)]
        if inn_names:
            # EXCLUDE known reference drugs - they're not the investigational drug
            investigational_inn = [d for d in inn_names if d.lower() not in known_reference_drugs]

            if investigational_inn:
                # Prefer monoclonal antibodies (-mab) as they're usually investigational
                mab_drugs = [d for d in investigational_inn if d.lower().endswith('mab')]
                if mab_drugs:
                    print(f"[DEBUG] MAB drugs found: {mab_drugs}, selecting: {mab_drugs[0]}")
                    return mab_drugs[0], drug_list
                # Then prefer other targeted therapies (-nib, -mod)
                targeted = [d for d in investigational_inn if d.lower().endswith(('nib', 'mod', 'tinib'))]
                if targeted:
                    print(f"[DEBUG] Targeted therapy drugs found: {targeted}, selecting: {targeted[0]}")
                    return targeted[0], drug_list
                # Fallback to any non-reference INN name
                investigational_inn.sort(key=len, reverse=True)
                print(f"[DEBUG] INN drug names found: {investigational_inn}, selecting: {investigational_inn[0]}")
                return investigational_inn[0], drug_list
            # If only reference drugs found, DON'T return them - fall through to fallback
            print(f"[DEBUG] Only reference drugs found in INN: {inn_names}, skipping to fallback")

        # PRIORITY 3: Any remaining drug name (last resort)
        if drug_list:
            print(f"[DEBUG] Fallback drug names: {drug_list}, selecting: {drug_list[0]}")
            return drug_list[0], drug_list

        return None, []

    def _extract_route(self, text: str) -> RouteOfAdministration:
        """Extract route of administration"""
        text_lower = text.lower()

        if re.search(r'\biv\b|intravenous|iv\s+infusion', text_lower):
            return RouteOfAdministration.IV
        elif re.search(r'\bsc\b|subcutaneous|subcutaneously', text_lower):
            return RouteOfAdministration.SC
        elif re.search(r'\bim\b|intramuscular', text_lower):
            return RouteOfAdministration.IM
        elif re.search(r'\boral|orally|tablet|capsule', text_lower):
            return RouteOfAdministration.ORAL
        elif re.search(r'topical|cream|ointment', text_lower):
            return RouteOfAdministration.TOPICAL
        elif re.search(r'inhal|nebuliz', text_lower):
            return RouteOfAdministration.INHALED

        return RouteOfAdministration.OTHER

    def _extract_arms(self, text: str) -> List[TreatmentArm]:
        """Extract treatment arms"""
        arms = []
        seen_arm_ids = set()  # Track unique arm identifiers to avoid duplicates

        # Look for arm/group descriptions - more restrictive patterns
        arm_patterns = [
            # "Arm A: description" or "Group 1: description"
            r'(?:arm|group)\s*([A-D1-4])[:\s]+([^\n]{5,100})',
            # "treatment arm A: description"
            r'(?:treatment\s+)?(?:arm|group)\s+([A-D1-4])[:\s]+([^\n]{5,100})',
            # "- Arm A: description"
            r'-\s*(?:arm|group)\s*([A-D1-4])[:\s]+([^\n]{5,100})',
        ]

        for pattern in arm_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                arm_id = match[0].upper() if len(match) > 1 else match[0].upper()
                arm_desc = match[1] if len(match) > 1 else ""

                # Skip if we've already seen this arm identifier
                if arm_id in seen_arm_ids:
                    continue

                # VALIDATION: Skip garbage text
                # Must have at least one letter, not just numbers/punctuation
                if not re.search(r'[a-zA-Z]{3,}', arm_desc):
                    continue
                # Skip if it looks like a sentence fragment
                if arm_desc.strip().startswith(('nd ', 'of ', 'in ', 'to ', 'or ')):
                    continue

                seen_arm_ids.add(arm_id)

                is_placebo = 'placebo' in arm_desc.lower()

                arm = TreatmentArm(
                    name=arm_desc.strip() if arm_desc else f"Arm {arm_id}",
                    is_placebo=is_placebo
                )

                # Extract dose if present
                dose_match = re.search(r'(\d+\s*(?:mg|mcg|g|ml|mL))', arm_desc)
                if dose_match:
                    arm.dose = dose_match.group(1)

                arms.append(arm)

        # If no arms found, try to extract from randomization description
        if not arms:
            ratio_match = re.search(r'(\d+:\d+(?::\d+)*)', text)
            if ratio_match:
                ratio_parts = ratio_match.group(1).split(':')
                for i, _ in enumerate(ratio_parts):
                    arms.append(TreatmentArm(name=f"Arm {i+1}"))

        return arms

    def _extract_num_arms(self, text: str) -> int:
        """Extract number of treatment arms"""
        text_lower = text.lower()

        # CRITICAL: Check for single-arm FIRST
        if any(x in text_lower for x in [
            'single-arm', 'single arm', 'one-arm', 'one arm',
            'non-randomized', 'nonrandomized'
        ]):
            return 1

        # From ratio
        ratio_match = re.search(r'(\d+:\d+(?::\d+)*)', text)
        if ratio_match:
            return len(ratio_match.group(1).split(':'))

        # From explicit statement
        arms_patterns = [
            r'(\d+)\s+(?:treatment\s+)?(?:arms?|groups?)',
            r'(?:randomized?\s+to|assigned\s+to)\s+(\d+)',
        ]
        for pattern in arms_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return 0

    def _extract_randomization_ratio(self, text: str) -> Optional[str]:
        """Extract randomization ratio"""
        match = re.search(r'(\d+:\d+(?::\d+)*)', text)
        return match.group(1) if match else None

    def _extract_stratification_factors(self, text: str) -> List[str]:
        """Extract stratification factors"""
        factors = []

        patterns = [
            r'(?:stratif(?:y|ied|ication)\s+(?:by|factors?)[:\s]+)([^\n.]+)',
            r'(?:randomization\s+stratif(?:y|ied|ication)[:\s]+)([^\n.]+)',
            r'(?:stratified\s+by)[:\s]+([^\n.]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                factor_text = match.group(1)

                # Smart splitting: Don't break on "and" within parentheses or within factor names
                # First, try to identify complete factors by looking for patterns like "X (yes/no)"
                # Pattern: factor name optionally followed by (levels)
                factor_pattern = r'([^,;]+?\s*(?:\([^)]+\))?)'
                potential_factors = re.findall(factor_pattern, factor_text)

                if potential_factors:
                    for part in potential_factors:
                        part = part.strip().strip(',').strip(';').strip()
                        # Remove leading "and " but keep "and" within the factor name
                        if part.lower().startswith('and '):
                            part = part[4:].strip()
                        if len(part) > 3 and len(part) < 100:
                            # Don't add duplicates
                            if part not in factors:
                                factors.append(part)
                else:
                    # Fallback: split only on comma and semicolon, NOT on "and"
                    parts = re.split(r'[,;]', factor_text)
                    for part in parts:
                        part = part.strip()
                        # Remove leading "and " but keep compound names
                        if part.lower().startswith('and '):
                            part = part[4:].strip()
                        if len(part) > 3 and len(part) < 100:
                            if part not in factors:
                                factors.append(part)

        return factors

    def _extract_sample_size(self, text: str, num_arms: int) -> SampleSizeSpec:
        """Extract sample size specification"""
        spec = SampleSizeSpec(total_n=0)

        # Total sample size - comprehensive patterns
        total_patterns = [
            # Standard enrollment statements
            r'(?:approximately\s+)?(\d+)\s+(?:patients?|subjects?|participants?)\s+(?:will\s+be\s+)?(?:enrolled|randomized|recruited)',
            r'(?:total\s+(?:of\s+)?)?(\d+)\s+(?:patients?|subjects?)\s+(?:planned|expected)',
            r'(?:sample\s+size)[:\s]+(?:approximately\s+)?(\d+)',
            r'(?:enroll|randomize)\s+(?:approximately\s+)?(\d+)',
            r'N\s*[=:]\s*(\d+)',
            # Additional patterns for common phrasings
            r'(\d+)\s+(?:patients?|subjects?|participants?)\s+(?:in\s+a|randomized|across)',
            r'(\d+)\s+(?:patients?|subjects?|participants?)\s+(?:will\s+be\s+)?(?:assigned|allocated)',
            # Ratio-based patterns (e.g., "400 patients will be randomized in a 2:1 ratio")
            r'(\d+)\s+(?:patients?|subjects?|participants?)\s+(?:will\s+be\s+)?randomized\s+in\s+a\s+\d+:\d+',
            # "A total of X" patterns
            r'[Aa]\s+total\s+of\s+(\d+)\s+(?:patients?|subjects?|participants?)',
            # "Up to X patients"
            r'[Uu]p\s+to\s+(\d+)\s+(?:patients?|subjects?|participants?)',
            # "Enroll approximately X"
            r'[Ee]nroll\s+(?:approximately\s+)?(\d+)',
            # Just "X patients" at start of sentence
            r'^\s*(\d+)\s+(?:patients?|subjects?|participants?)\s+will',
            # "will include X patients"
            r'(?:will\s+)?include\s+(?:approximately\s+)?(\d+)\s+(?:patients?|subjects?)',
        ]

        # Collect ALL matches and take the LARGEST (not first)
        # This handles cases where background mentions "100 patients" but actual size is "400 randomized"
        all_sizes = []
        for pattern in total_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                n = int(match.group(1))
                if 10 <= n <= 100000:  # Reasonable range
                    all_sizes.append(n)

        if all_sizes:
            # Take the LARGEST sample size found (usually the actual total)
            spec.total_n = max(all_sizes)
            if len(set(all_sizes)) > 1:
                print(f"[DEBUG] Multiple sample sizes found: {sorted(set(all_sizes))}, using largest: {spec.total_n}")

        # Per-arm if available
        if spec.total_n > 0 and num_arms > 0:
            per_arm = spec.total_n // num_arms
            for i in range(num_arms):
                spec.per_arm[f"Arm {i+1}"] = per_arm

        # Power
        power_match = re.search(r'(\d{2})\s*%?\s*power', text, re.IGNORECASE)
        if power_match:
            spec.power = float(power_match.group(1)) / 100

        # Dropout rate
        dropout_match = re.search(r'(\d{1,2})\s*%?\s*(?:dropout|discontinuation|withdrawal)', text, re.IGNORECASE)
        if dropout_match:
            spec.dropout_rate = float(dropout_match.group(1)) / 100

        return spec

    def _extract_primary_endpoint(self, text: str) -> Optional[EndpointDefinition]:
        """Extract primary endpoint definition"""
        patterns = [
            # More specific patterns - capture until sentence end or section break
            r'(?:primary\s+(?:efficacy\s+)?endpoint)[:\s]+([^.]+\.(?:\s+[^.]+\.)?)',
            r'(?:primary\s+(?:efficacy\s+)?outcome)[:\s]+([^.]+\.(?:\s+[^.]+\.)?)',
            r'(?:primary\s+objective)[:\s]+([^.]+\.(?:\s+[^.]+\.)?)',
            # Oncology-specific
            r'(?:primary\s+(?:efficacy\s+)?variable)[:\s]+([^.]+\.(?:\s+[^.]+\.)?)',
            # Fallback: capture to end of line with continuation
            r'(?:primary\s+(?:efficacy\s+)?endpoint)[:\s]+([^\n]+(?:\n(?![A-Z0-9•\-\d])[^\n]+)*)',
            # Named endpoints
            r'(?:objective\s+response\s+rate|ORR)[:\s]*([^\n]*)',
            r'(?:overall\s+survival|OS)[:\s]*([^\n]*)',
            r'(?:progression[- ]free\s+survival|PFS)[:\s]*([^\n]*)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                endpoint_text = match.group(1).strip()

                # Clean up: remove trailing partial sentences
                # If text ends mid-word (no space after last char) and no period, it's truncated
                if endpoint_text and not endpoint_text.endswith('.') and len(endpoint_text) > 50:
                    # Find last complete sentence
                    last_period = endpoint_text.rfind('.')
                    if last_period > 20:  # Keep if substantial text before period
                        endpoint_text = endpoint_text[:last_period + 1]

                # VALIDATION: Skip if definition is too short or just a number
                if len(endpoint_text) < 10:
                    continue  # Too short to be a real endpoint definition
                if endpoint_text.isdigit():
                    continue  # Just a number, not a definition
                if re.match(r'^[\d.%]+$', endpoint_text):
                    continue  # Just numbers/percentages

                # Extract timepoint if present
                timepoint = None
                time_match = re.search(r'(?:at|by|week)\s*(\d+)', endpoint_text, re.IGNORECASE)
                if time_match:
                    timepoint = f"Week {time_match.group(1)}"

                # Extract scoring system if present
                scoring = None
                scoring_patterns = ['CDAI', 'Mayo', 'PASI', 'ACR', 'DAS28', 'RECIST', 'ECOG', 'irRC', 'iRECIST']
                for score in scoring_patterns:
                    if score.lower() in endpoint_text.lower():
                        scoring = score
                        break

                return EndpointDefinition(
                    name="Primary Endpoint",
                    definition=endpoint_text[:500],
                    timepoint=timepoint,
                    scoring_system=scoring
                )

        # Fallback: Look for common oncology endpoints in the full text
        oncology_endpoints = [
            (r'objective\s+response\s+rate\s*\(?\s*ORR\s*\)?', 'Objective Response Rate (ORR)'),
            (r'overall\s+survival\s*\(?\s*OS\s*\)?', 'Overall Survival (OS)'),
            (r'progression[- ]free\s+survival\s*\(?\s*PFS\s*\)?', 'Progression-Free Survival (PFS)'),
            (r'disease[- ]free\s+survival\s*\(?\s*DFS\s*\)?', 'Disease-Free Survival (DFS)'),
            (r'duration\s+of\s+response\s*\(?\s*DOR\s*\)?', 'Duration of Response (DOR)'),
        ]

        for pattern, name in oncology_endpoints:
            if re.search(pattern, text, re.IGNORECASE):
                return EndpointDefinition(
                    name="Primary Endpoint",
                    definition=name,
                    scoring_system='RECIST' if 'response' in name.lower() else None
                )

        return None

    def _extract_secondary_endpoints(self, text: str) -> List[EndpointDefinition]:
        """Extract secondary endpoints"""
        endpoints = []

        patterns = [
            # Capture until sentence end
            r'(?:secondary\s+(?:endpoint|efficacy\s+endpoint|outcome)s?)[:\s]+([^.]+\.)',
            # Fallback: capture to end of line
            r'(?:secondary\s+(?:endpoint|efficacy\s+endpoint|outcome)s?)[:\s]+([^\n]+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:5]:  # Limit to 5
                endpoint_text = match.strip()

                # VALIDATION: Skip garbage text
                if len(endpoint_text) < 10:
                    continue  # Too short
                if endpoint_text.isdigit() or re.match(r'^[\d.%]+$', endpoint_text):
                    continue  # Just numbers
                if not re.search(r'[a-zA-Z]{3,}', endpoint_text):
                    continue  # Must have at least one word
                if endpoint_text.startswith(('of ', 'in ', 'to ', 'or ', 'and ')):
                    continue  # Fragment

                endpoints.append(EndpointDefinition(
                    name="Secondary Endpoint",
                    definition=endpoint_text[:300]
                ))

        return endpoints

    def _extract_alpha(self, text: str) -> AlphaSpecification:
        """Extract alpha/significance level specification"""
        spec = AlphaSpecification()

        # Sidedness
        if re.search(r'one[- ]sided|1[- ]sided', text, re.IGNORECASE):
            spec.sidedness = "one-sided"
        elif re.search(r'two[- ]sided|2[- ]sided', text, re.IGNORECASE):
            spec.sidedness = "two-sided"

        # Alpha level
        alpha_patterns = [
            r'(?:alpha|significance\s+level|type\s+I\s+error)[:\s=]+(\d+\.?\d*)\s*%?',
            r'(\d+\.?\d*)\s*%?\s+(?:alpha|significance)',
            r'p\s*[<≤]\s*(\d+\.?\d*)',
        ]

        for pattern in alpha_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                alpha_val = float(match.group(1))
                if alpha_val > 1:  # Percentage
                    alpha_val = alpha_val / 100
                if 0.001 <= alpha_val <= 0.5:
                    spec.primary_alpha = alpha_val
                    break

        # Additional alpha levels (e.g., 20% for exploratory)
        if re.search(r'20\s*%\s*(?:significance|alpha|level)', text, re.IGNORECASE):
            spec.additional_levels.append(0.20)

        return spec

    def _extract_primary_analysis_method(self, text: str) -> Optional[str]:
        """Extract primary analysis method"""
        method_patterns = [
            (r'logistic\s+regression', 'Logistic Regression'),
            (r'cox\s+(?:proportional\s+)?hazard', 'Cox Proportional Hazards'),
            (r'kaplan[- ]meier', 'Kaplan-Meier'),
            (r'log[- ]rank\s+test', 'Log-Rank Test'),
            (r'CMH\s+test|cochran[- ]mantel[- ]haenszel', 'CMH Test'),
            (r'ANCOVA|analysis\s+of\s+covariance', 'ANCOVA'),
            (r'MMRM|mixed[- ]model\s+repeated\s+measures', 'MMRM'),
            (r"fisher['\u2019]?s?\s+exact", "Fisher's Exact Test"),
            (r'chi[- ]square|χ²', 'Chi-Square Test'),
            (r'wilcoxon', 'Wilcoxon Test'),
            (r't[- ]test', 't-Test'),
        ]

        for pattern, method_name in method_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return method_name

        return None

    def _extract_analysis_population(self, text: str) -> Optional[str]:
        """Extract primary analysis population"""
        patterns = [
            r'(?:primary\s+analysis\s+(?:will\s+be\s+)?(?:performed|conducted)\s+(?:on|using)\s+(?:the\s+)?)(ITT|FAS|PP|mITT)',
            r'(?:primary\s+(?:analysis\s+)?population)[:\s]+(ITT|FAS|PP|mITT|intent[- ]to[- ]treat|full\s+analysis\s+set)',
            # Simpler patterns for common phrasings
            r'(?:primary\s+analysis)\s+(?:on|using)\s+(?:the\s+)?(ITT|FAS|PP|mITT)',
            r'(?:primary\s+efficacy\s+analysis)[^.]*(?:on|using|for)\s+(?:the\s+)?(ITT|FAS|PP|mITT)',
            r'(ITT|FAS|PP|mITT)\s+(?:population\s+)?(?:will\s+be\s+)?(?:used\s+)?(?:for|as)\s+(?:the\s+)?primary',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                pop = match.group(1).upper()
                if 'INTENT' in pop or pop == 'ITT':
                    return 'ITT'
                elif 'FULL' in pop or pop == 'FAS':
                    return 'FAS'
                return pop

        return None

    def _extract_population_definition(self, text: str, pop_type: str) -> Optional[str]:
        """Extract population definition"""
        patterns = {
            'ITT': r'(?:ITT|intent[- ]to[- ]treat)[^.]*(?:defined\s+as|includes?|consists?\s+of)[:\s]+([^.]+)',
            'FAS': r'(?:FAS|full\s+analysis\s+set)[^.]*(?:defined\s+as|includes?|consists?\s+of)[:\s]+([^.]+)',
            'PP': r'(?:PP|per[- ]protocol)[^.]*(?:defined\s+as|includes?|consists?\s+of)[:\s]+([^.]+)',
            'safety': r'(?:safety\s+(?:population|set|analysis\s+set))[^.]*(?:defined\s+as|includes?|consists?\s+of)[:\s]+([^.]+)',
        }

        pattern = patterns.get(pop_type)
        if pattern:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:300]

        return None

    def _extract_primary_timepoint(self, text: str) -> Optional[str]:
        """Extract primary timepoint"""
        patterns = [
            r'(?:primary\s+(?:endpoint|analysis))[^.]*(?:at|by)\s+(week\s+\d+|day\s+\d+|month\s+\d+)',
            r'(?:week\s+\d+|day\s+\d+)\s+(?:primary|endpoint)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) if match.lastindex else match.group(0)

        return None

    def _extract_study_duration(self, text: str) -> Optional[str]:
        """Extract study duration"""
        patterns = [
            r'(?:study|treatment)\s+(?:duration|period)[:\s]+(\d+\s+(?:weeks?|months?|years?))',
            r'(?:followed\s+for|up\s+to)\s+(\d+\s+(?:weeks?|months?|years?))',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_pk_substudy(self, text: str) -> PKSubstudy:
        """Extract PK substudy information"""
        pk = PKSubstudy()

        # Check if PK substudy exists
        pk_patterns = [
            r'(?:PK|pharmacokinetic)\s+(?:sub)?study',
            r'(?:PK|pharmacokinetic)\s+(?:population|subgroup|sampling)',
            r'(?:PK|pharmacokinetic)\s+analysis',
            r'intensive\s+PK\s+sampling',
        ]
        for pattern in pk_patterns:
            if re.search(pattern, text, re.I):
                pk.has_pk_substudy = True
                break

        if not pk.has_pk_substudy:
            return pk

        # Extract PK population size
        pk_n_patterns = [
            r'(?:PK|pharmacokinetic)\s+(?:sub)?(?:study|group|population)[^.]*?(\d+)\s+(?:patients?|subjects?)',
            r'(\d+)\s+(?:patients?|subjects?)[^.]*?(?:PK|pharmacokinetic)',
        ]
        for pattern in pk_n_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                n = int(match.group(1))
                if 5 <= n <= 500:
                    pk.pk_population_size = n
                    break

        # Extract PK parameters
        pk_param_patterns = [
            r'AUC(?:inf|τ|last|0-\d+)?',
            r'Cmax',
            r'Tmax',
            r'CL(?:/F)?',
            r'Vz(?:/F)?',
            r't½|t1/2|half[- ]life',
            r'MRT',
            r'λz|lambda',
        ]
        for pattern in pk_param_patterns:
            if re.search(pattern, text, re.I):
                # Normalize parameter name
                param = pattern.replace('(?:', '').replace(')?', '').replace('|', '/')
                if param not in pk.pk_parameters:
                    pk.pk_parameters.append(param)

        # Extract PK software
        software_patterns = [
            (r'WinNonlin', 'WinNonlin'),
            (r'Phoenix', 'Phoenix WinNonlin'),
            (r'NONMEM', 'NONMEM'),
            (r'Monolix', 'Monolix'),
        ]
        for pattern, name in software_patterns:
            if re.search(pattern, text, re.I):
                pk.pk_analysis_software = name
                break

        return pk

    def _extract_immunogenicity(self, text: str) -> ImmunogenicityAssessment:
        """Extract immunogenicity/ADA assessment information"""
        immuno = ImmunogenicityAssessment()

        # Check if immunogenicity assessment exists
        immuno_patterns = [
            r'immunogenicity',
            r'anti[- ]drug\s+antibod(?:y|ies)',
            r'ADA\s+(?:testing|assessment|analysis)',
            r'anti[- ]\w+\s+antibod(?:y|ies)',
        ]
        for pattern in immuno_patterns:
            if re.search(pattern, text, re.I):
                immuno.has_immunogenicity = True
                break

        if not immuno.has_immunogenicity:
            return immuno

        # Extract antibody type
        ab_match = re.search(r'anti[- ](\w+)\s+antibod(?:y|ies)', text, re.I)
        if ab_match:
            immuno.antibody_type = f"Anti-{ab_match.group(1)} antibodies"

        # Extract sampling timepoints
        timepoint_match = re.search(
            r'(?:ADA|immunogenicity|antibod(?:y|ies))[^.]*?(?:visits?|weeks?)[:\s]+([^.]+)',
            text, re.I
        )
        if timepoint_match:
            timepoints = re.findall(r'(?:Visit|Week)\s*\d+', timepoint_match.group(1), re.I)
            immuno.ada_sampling_timepoints = timepoints[:10]

        return immuno

    def _extract_subgroup_analyses(self, text: str) -> List[SubgroupAnalysis]:
        """Extract planned subgroup analyses"""
        subgroups = []

        # Common subgroup factors
        subgroup_patterns = [
            (r'age\s+(?:group|subgroup)', 'Age', ['<65 years', '≥65 years']),
            (r'sex|gender', 'Sex', ['Male', 'Female']),
            (r'race|ethnic', 'Race/Ethnicity', []),
            (r'geographic\s+region', 'Geographic Region', []),
            (r'baseline\s+(?:disease\s+)?severity', 'Baseline Severity', []),
            (r'prior\s+(?:treatment|therapy)', 'Prior Treatment', ['Yes', 'No']),
            (r'biomarker', 'Biomarker Status', []),
            (r'IL-6|interleukin', 'IL-6 Levels', ['High', 'Low']),
        ]

        # Check for explicit subgroup analysis section
        subgroup_section = re.search(
            r'subgroup\s+analy(?:sis|ses)[:\s]+([^#]+?)(?:(?:\d+\.\s)|$)',
            text, re.I | re.DOTALL
        )

        text_to_search = subgroup_section.group(1) if subgroup_section else text

        for pattern, factor_name, default_categories in subgroup_patterns:
            if re.search(pattern, text_to_search, re.I):
                subgroup = SubgroupAnalysis(
                    factor=factor_name,
                    categories=default_categories
                )
                subgroups.append(subgroup)

        return subgroups

    def _extract_interim_analysis(self, text: str) -> InterimAnalysis:
        """Extract interim analysis and monitoring information"""
        interim = InterimAnalysis()

        # Check for interim analysis
        interim_patterns = [
            r'interim\s+analysis',
            r'DMC|DSMB|data\s+(?:monitoring|safety)\s+(?:committee|board)',
            r'SRC|safety\s+review\s+committee',
            r'stopping\s+rules?',
            r'futility\s+analysis',
        ]

        for pattern in interim_patterns:
            if re.search(pattern, text, re.I):
                interim.has_interim = True
                break

        if not interim.has_interim:
            return interim

        # Extract monitoring committee
        committee_patterns = [
            (r'DMC|data\s+monitoring\s+committee', 'Data Monitoring Committee (DMC)'),
            (r'DSMB|data\s+safety\s+monitoring\s+board', 'Data Safety Monitoring Board (DSMB)'),
            (r'SRC|safety\s+review\s+committee', 'Safety Review Committee (SRC)'),
            (r'IDMC|independent\s+data\s+monitoring', 'Independent Data Monitoring Committee (IDMC)'),
        ]
        for pattern, name in committee_patterns:
            if re.search(pattern, text, re.I):
                interim.monitoring_committee = name
                break

        # Extract interim timepoints
        interim_tp_match = re.search(
            r'interim\s+analysis[^.]*?(?:at|after)\s+(\d+\s+(?:patients?|subjects?|events?|%|percent))',
            text, re.I
        )
        if interim_tp_match:
            interim.interim_timepoints.append(interim_tp_match.group(1))

        # Extract stopping rules
        stopping_patterns = [
            r'(?:stop|terminate)[^.]*?(?:for|due\s+to)\s+([^.]+)',
            r'futility[^.]*?(?:if|when)\s+([^.]+)',
        ]
        for pattern in stopping_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                rule = match.group(1).strip()[:100]
                if rule and rule not in interim.stopping_rules:
                    interim.stopping_rules.append(rule)

        return interim

    def to_prompt_context(self, facts: ProtocolFacts) -> str:
        """
        Convert facts to a prompt context string for LLM.
        This is what gets injected into the SAP generation prompt.
        """
        lines = [
            "## MANDATORY PROTOCOL FACTS",
            "Use these values EXACTLY. Do NOT change or hallucinate any values.",
            ""
        ]

        if facts.nct_id:
            lines.append(f"- NCT ID: {facts.nct_id}")
        if facts.study_id:
            lines.append(f"- Study ID: {facts.study_id}")
        if facts.drug_name:
            lines.append(f"- Drug/Compound: {facts.drug_name}")
        if facts.route_of_administration != RouteOfAdministration.OTHER:
            lines.append(f"- Route: {facts.route_of_administration.value}")
        if facts.phase != StudyPhase.UNKNOWN:
            lines.append(f"- Phase: {facts.phase.value}")
        if facts.therapeutic_area:
            lines.append(f"- Therapeutic Area: {facts.therapeutic_area}")
        if facts.indication:
            lines.append(f"- Indication: {facts.indication}")

        lines.append("")
        lines.append("### Study Design")
        if facts.design_type:
            lines.append(f"- Design: {facts.design_type}")
        lines.append(f"- Number of Arms: {facts.num_arms}")
        if facts.randomization_ratio:
            lines.append(f"- Randomization Ratio: {facts.randomization_ratio}")
        if facts.arms:
            lines.append("- Treatment Arms:")
            for arm in facts.arms:
                arm_str = f"  - {arm.name}"
                if arm.dose:
                    arm_str += f" ({arm.dose})"
                if arm.is_placebo:
                    arm_str += " [PLACEBO]"
                lines.append(arm_str)
        if facts.stratification_factors:
            lines.append(f"- Stratification Factors: {', '.join(facts.stratification_factors)}")

        lines.append("")
        lines.append("### Sample Size")
        lines.append(f"- Total N: {facts.sample_size.total_n}")
        if facts.sample_size.per_arm:
            for arm, n in facts.sample_size.per_arm.items():
                lines.append(f"  - {arm}: {n}")
        if facts.sample_size.power:
            lines.append(f"- Power: {facts.sample_size.power * 100:.0f}%")

        lines.append("")
        lines.append("### Statistical")
        lines.append(f"- Alpha: {facts.alpha.primary_alpha} ({facts.alpha.sidedness})")
        if facts.alpha.additional_levels:
            lines.append(f"- Additional Alpha Levels: {facts.alpha.additional_levels}")
        if facts.primary_analysis_method:
            lines.append(f"- Primary Analysis Method: {facts.primary_analysis_method}")
        if facts.primary_analysis_population:
            lines.append(f"- Primary Analysis Population: {facts.primary_analysis_population}")

        if facts.primary_endpoint:
            lines.append("")
            lines.append("### Primary Endpoint")
            lines.append(f"- Definition: {facts.primary_endpoint.definition}")
            if facts.primary_endpoint.timepoint:
                lines.append(f"- Timepoint: {facts.primary_endpoint.timepoint}")
            if facts.primary_endpoint.scoring_system:
                lines.append(f"- Scoring System: {facts.primary_endpoint.scoring_system}")

        return "\n".join(lines)


# Convenience function
def extract_protocol_facts(protocol_text: str) -> ProtocolFacts:
    """Extract all facts from protocol text"""
    extractor = StructuredFactExtractor()
    return extractor.extract_all(protocol_text)
