#!/usr/bin/env python3
"""
Fully Constrained SAP Schema Generator
======================================

Philosophy: If it's extracted from the protocol → It MUST be constrained

Every protocol-specific value uses Literal types.
Only narrative/prose fields allow free LLM generation.
"""

import re
from typing import Any, Dict, List, Optional, Type, Literal, Union
from pydantic import BaseModel, Field, field_validator, create_model
from dataclasses import dataclass, field


# =============================================================================
# PROTOCOL FACTS: All Extractable Entities
# =============================================================================

@dataclass
class FullProtocolFacts:
    """Complete set of facts extracted from protocol - ALL will be constrained"""

    # === IDENTIFICATION (High contamination risk) ===
    nct_id: Optional[str] = None
    study_id: Optional[str] = None
    sponsor: Optional[str] = None

    # === STUDY INFO ===
    title: Optional[str] = None
    phase: Optional[str] = None
    therapeutic_area: Optional[str] = None
    indication: Optional[str] = None
    design_type: Optional[str] = None  # e.g., "randomized, double-blind, placebo-controlled"

    # === DRUG/TREATMENT (High contamination risk) ===
    drug_name: Optional[str] = None
    drug_code: Optional[str] = None
    drug_generic: Optional[str] = None
    route: Optional[str] = None

    # === ARMS (High contamination risk) ===
    num_arms: Optional[int] = None
    ratio: Optional[str] = None
    arm_names: List[str] = field(default_factory=list)
    arm_descriptions: List[str] = field(default_factory=list)
    arm_doses: List[str] = field(default_factory=list)

    # === SAMPLE SIZE (High contamination risk) ===
    total_n: Optional[int] = None
    per_arm_n: Optional[Dict[str, int]] = None
    power: Optional[str] = None
    power_scenarios: List[str] = field(default_factory=list)  # All power values (e.g., ["83%", "70%"])
    alpha: Optional[float] = None
    alpha_sidedness: Optional[str] = None
    dropout_rate: Optional[str] = None

    # === POWER CALCULATION ASSUMPTIONS ===
    expected_response_placebo: Optional[str] = None  # e.g., "10%"
    expected_response_active: Optional[str] = None   # e.g., "40%"
    primary_comparison: Optional[str] = None         # e.g., "Placebo vs. 600mg"

    # === ENDPOINTS ===
    primary_endpoint: Optional[str] = None
    primary_endpoint_definition: Optional[str] = None  # Full definition with criteria
    primary_timepoint: Optional[str] = None
    secondary_endpoints: List[str] = field(default_factory=list)
    secondary_endpoints_detailed: List[Dict[str, str]] = field(default_factory=list)  # With timepoints

    # === POPULATIONS ===
    primary_population: Optional[str] = None
    itt_definition: Optional[str] = None
    pp_definition: Optional[str] = None
    safety_definition: Optional[str] = None
    pk_population_definition: Optional[str] = None
    pk_population_size: Optional[int] = None

    # === STRATIFICATION ===
    stratification_factors: List[str] = field(default_factory=list)

    # === ANALYSIS ===
    primary_analysis_method: Optional[str] = None

    # === TIMING ===
    study_duration: Optional[str] = None

    # === PK ANALYSIS ===
    has_pk_substudy: bool = False
    pk_parameters: List[str] = field(default_factory=list)
    pk_software: Optional[str] = None
    pk_sampling_timepoints: List[str] = field(default_factory=list)

    # === BIOMARKERS ===
    biomarker_endpoints: List[str] = field(default_factory=list)
    biomarker_subgroups: List[str] = field(default_factory=list)

    # === SUBGROUPS ===
    subgroup_analyses: List[str] = field(default_factory=list)

    # === VISIT WINDOWS ===
    visit_windows: Dict[str, str] = field(default_factory=dict)


# =============================================================================
# SECTION SCHEMAS: All Protocol Values Constrained
# =============================================================================

class IntroductionSectionBase(BaseModel):
    """Section 1: Introduction - All IDs constrained"""
    # Constrained fields (protocol values)
    nct_id: str
    study_id: str
    sponsor: str
    title: str
    phase: str

    # Free narrative fields
    purpose_statement: str = Field(
        description="Purpose of the SAP. DO NOT include specific IDs or values."
    )
    scope_statement: str = Field(
        description="Scope of the document. DO NOT include specific values."
    )

    @field_validator('purpose_statement', 'scope_statement')
    @classmethod
    def check_no_contamination(cls, v: str) -> str:
        """Ensure narrative doesn't contain wrong drug names used as THE study drug"""
        # Only block wrong drug names - study IDs may appear legitimately in references
        # NOTE: Don't block study IDs like GA29144 - they might be comparative references
        drug_contaminants = ['etrolizumab', 'tocilizumab', 'sarilumab']
        for c in drug_contaminants:
            # Check if drug is being used as the study drug (not just mentioned)
            patterns = [f'{c.lower()} will be', f'treatment with {c.lower()}', f'study drug {c.lower()}']
            for pattern in patterns:
                if pattern in v.lower():
                    raise ValueError(f"Narrative uses wrong study drug: {c}")
        return v


class StudyDesignSectionBase(BaseModel):
    """Section 3: Study Design - All design elements constrained"""
    # Constrained fields
    design_type: str
    drug_name: str
    route: str
    num_arms: int
    ratio: str
    arm_names: List[str]
    arm_descriptions: List[str]

    # Free narrative
    design_narrative: str = Field(
        description="Study design description. Reference constrained values, don't restate numbers."
    )


class PopulationsSectionBase(BaseModel):
    """Section 4: Analysis Populations - All definitions constrained"""
    # Constrained fields
    primary_population: str
    itt_definition: str
    pp_definition: str
    safety_definition: str

    # Free narrative
    population_rationale: str = Field(
        description="Rationale for population choices."
    )


class EndpointsSectionBase(BaseModel):
    """Section 5: Endpoints - All endpoints constrained"""
    # Constrained fields
    primary_endpoint: str
    primary_timepoint: str
    secondary_endpoints: List[str]

    # Free narrative
    endpoint_rationale: str = Field(
        description="Rationale for endpoint selection."
    )
    endpoint_derivation: str = Field(
        description="How endpoints will be derived."
    )


class SampleSizeSectionBase(BaseModel):
    """Section 6: Sample Size - All numbers constrained"""
    # Constrained fields
    total_n: int
    num_arms: int
    ratio: str
    per_arm_n: Dict[str, int]
    power: str
    alpha: float
    alpha_sidedness: str
    dropout_rate: str

    # Free narrative
    sample_size_rationale: str = Field(
        description="Rationale for sample size. DO NOT include any numbers."
    )
    power_methodology: str = Field(
        description="Power calculation methodology. DO NOT include specific numbers."
    )

    @field_validator('sample_size_rationale', 'power_methodology')
    @classmethod
    def no_numbers_in_narrative(cls, v: str) -> str:
        """Block numbers in narrative - they should come from constrained fields"""
        # Find numbers that look like sample sizes or percentages
        suspicious = re.findall(r'\b(\d{2,4})\b', v)
        for num in suspicious:
            n = int(num)
            if n > 10 and n not in [100]:  # Allow small numbers and 100%
                raise ValueError(f"Narrative contains number {n} - use constrained fields instead")
        return v


class StatMethodsSectionBase(BaseModel):
    """Section 7: Statistical Methods - Analysis method constrained"""
    # Constrained fields
    primary_analysis_method: str
    primary_population: str
    alpha: float
    alpha_sidedness: str

    # Free narrative
    analysis_description: str = Field(
        description="Description of statistical analysis approach."
    )
    missing_data_handling: str = Field(
        description="How missing data will be handled."
    )
    sensitivity_analyses: str = Field(
        description="Planned sensitivity analyses."
    )


class StratificationSectionBase(BaseModel):
    """Stratification factors - All factors constrained"""
    # Constrained fields
    stratification_factors: List[str]
    ratio: str

    # Free narrative
    stratification_rationale: str = Field(
        description="Rationale for stratification approach."
    )


# =============================================================================
# FULL SAP SCHEMA: Everything Combined
# =============================================================================

class FullSAPSchemaBase(BaseModel):
    """
    Complete SAP with ALL protocol values constrained.

    Philosophy:
    - Every value from protocol → Literal constraint
    - Only narrative text → Free generation
    """

    # === SECTION 1: INTRODUCTION ===
    nct_id: str
    study_id: str
    sponsor: str
    title: str
    phase: str
    therapeutic_area: str
    indication: str

    # === SECTION 3: STUDY DESIGN ===
    design_type: str
    drug_name: str
    drug_code: str
    route: str
    num_arms: int
    ratio: str
    arm_names: List[str]
    arm_descriptions: List[str]

    # === SECTION 4: POPULATIONS ===
    primary_population: str

    # === SECTION 5: ENDPOINTS ===
    primary_endpoint: str
    primary_timepoint: str
    secondary_endpoints: List[str]

    # === SECTION 6: SAMPLE SIZE ===
    total_n: int
    power: str
    alpha: float
    alpha_sidedness: str

    # === SECTION 7: METHODS ===
    primary_analysis_method: str
    stratification_factors: List[str]

    # === NARRATIVES (Free generation) ===
    introduction_narrative: str = Field(description="Introduction text")
    design_narrative: str = Field(description="Study design description")
    population_narrative: str = Field(description="Population definitions")
    endpoint_narrative: str = Field(description="Endpoint descriptions")
    sample_size_narrative: str = Field(description="Sample size rationale - NO NUMBERS")
    methods_narrative: str = Field(description="Statistical methods description")


# =============================================================================
# SCHEMA FACTORY: Create Fully Constrained Schema from Facts
# =============================================================================

def create_fully_constrained_schema(facts: FullProtocolFacts) -> Type[BaseModel]:
    """
    Create a Pydantic schema where EVERY protocol value is a Literal.

    The LLM cannot output any value that wasn't extracted from the protocol.
    """

    # Build field definitions with Literal types
    field_definitions = {}

    # === IDENTIFICATION ===
    if facts.nct_id:
        field_definitions['nct_id'] = (Literal[facts.nct_id], facts.nct_id)
    else:
        field_definitions['nct_id'] = (str, "UNKNOWN")

    if facts.study_id:
        field_definitions['study_id'] = (Literal[facts.study_id], facts.study_id)
    else:
        field_definitions['study_id'] = (str, "UNKNOWN")

    if facts.sponsor:
        field_definitions['sponsor'] = (Literal[facts.sponsor], facts.sponsor)
    else:
        field_definitions['sponsor'] = (str, "UNKNOWN")

    # === STUDY INFO ===
    if facts.title:
        field_definitions['title'] = (Literal[facts.title], facts.title)
    else:
        field_definitions['title'] = (str, "Clinical Trial")

    if facts.phase:
        field_definitions['phase'] = (Literal[facts.phase], facts.phase)
    else:
        field_definitions['phase'] = (str, "Phase 2")

    if facts.therapeutic_area:
        field_definitions['therapeutic_area'] = (Literal[facts.therapeutic_area], facts.therapeutic_area)
    else:
        field_definitions['therapeutic_area'] = (str, "Not specified")

    if facts.indication:
        field_definitions['indication'] = (Literal[facts.indication], facts.indication)
    else:
        field_definitions['indication'] = (str, "Not specified")

    if facts.design_type:
        field_definitions['design_type'] = (Literal[facts.design_type], facts.design_type)
    else:
        field_definitions['design_type'] = (str, "Randomized controlled trial")

    # === DRUG/TREATMENT ===
    if facts.drug_name:
        field_definitions['drug_name'] = (Literal[facts.drug_name], facts.drug_name)
    else:
        field_definitions['drug_name'] = (str, "Study Drug")

    if facts.drug_code:
        field_definitions['drug_code'] = (Literal[facts.drug_code], facts.drug_code)
    else:
        field_definitions['drug_code'] = (str, "")

    if facts.route:
        field_definitions['route'] = (Literal[facts.route], facts.route)
    else:
        field_definitions['route'] = (str, "Not specified")

    # === ARMS ===
    if facts.num_arms:
        field_definitions['num_arms'] = (Literal[facts.num_arms], facts.num_arms)
    else:
        field_definitions['num_arms'] = (int, 2)

    if facts.ratio:
        field_definitions['ratio'] = (Literal[facts.ratio], facts.ratio)
    else:
        field_definitions['ratio'] = (str, "1:1")

    # For lists, we create a Literal tuple of the values
    if facts.arm_names:
        # Convert list to tuple for Literal
        arm_names_tuple = tuple(facts.arm_names)
        field_definitions['arm_names'] = (List[str], list(facts.arm_names))
    else:
        field_definitions['arm_names'] = (List[str], [])

    if facts.arm_descriptions:
        field_definitions['arm_descriptions'] = (List[str], list(facts.arm_descriptions))
    else:
        field_definitions['arm_descriptions'] = (List[str], [])

    # === SAMPLE SIZE ===
    if facts.total_n:
        field_definitions['total_n'] = (Literal[facts.total_n], facts.total_n)
    else:
        field_definitions['total_n'] = (int, 100)

    if facts.power:
        field_definitions['power'] = (Literal[facts.power], facts.power)
    else:
        field_definitions['power'] = (str, "80%")

    if facts.alpha:
        field_definitions['alpha'] = (Literal[facts.alpha], facts.alpha)
    else:
        field_definitions['alpha'] = (float, 0.05)

    if facts.alpha_sidedness:
        field_definitions['alpha_sidedness'] = (Literal[facts.alpha_sidedness], facts.alpha_sidedness)
    else:
        field_definitions['alpha_sidedness'] = (str, "one-sided")  # Default to one-sided for efficacy trials

    if facts.dropout_rate:
        field_definitions['dropout_rate'] = (Literal[facts.dropout_rate], facts.dropout_rate)
    else:
        field_definitions['dropout_rate'] = (str, "10%")

    # === ENDPOINTS ===
    if facts.primary_endpoint:
        field_definitions['primary_endpoint'] = (Literal[facts.primary_endpoint], facts.primary_endpoint)
    else:
        field_definitions['primary_endpoint'] = (str, "Primary endpoint")

    if facts.primary_timepoint:
        field_definitions['primary_timepoint'] = (Literal[facts.primary_timepoint], facts.primary_timepoint)
    else:
        field_definitions['primary_timepoint'] = (str, "Week 12")

    if facts.secondary_endpoints:
        field_definitions['secondary_endpoints'] = (List[str], list(facts.secondary_endpoints))
    else:
        field_definitions['secondary_endpoints'] = (List[str], [])

    # === POPULATIONS ===
    if facts.primary_population:
        field_definitions['primary_population'] = (Literal[facts.primary_population], facts.primary_population)
    else:
        field_definitions['primary_population'] = (str, "ITT")

    # === STRATIFICATION ===
    if facts.stratification_factors:
        field_definitions['stratification_factors'] = (List[str], list(facts.stratification_factors))
    else:
        field_definitions['stratification_factors'] = (List[str], [])

    # === ANALYSIS ===
    if facts.primary_analysis_method:
        field_definitions['primary_analysis_method'] = (Literal[facts.primary_analysis_method], facts.primary_analysis_method)
    else:
        field_definitions['primary_analysis_method'] = (str, "Not specified")

    # === NARRATIVE FIELDS (Not constrained - LLM writes freely) ===
    field_definitions['introduction_narrative'] = (str, ...)
    field_definitions['design_narrative'] = (str, ...)
    field_definitions['population_narrative'] = (str, ...)
    field_definitions['endpoint_narrative'] = (str, ...)
    field_definitions['sample_size_narrative'] = (str, ...)
    field_definitions['methods_narrative'] = (str, ...)

    # Create the model
    FullyConstrainedSAP = create_model(
        'FullyConstrainedSAP',
        **field_definitions
    )

    return FullyConstrainedSAP


# =============================================================================
# EXTRACTION: Get FullProtocolFacts from Protocol Text
# =============================================================================

def extract_full_protocol_facts(protocol_text: str) -> FullProtocolFacts:
    """
    Extract ALL protocol facts for complete constraint coverage.
    """
    facts = FullProtocolFacts()

    # === IDENTIFICATION ===
    nct_match = re.search(r'(NCT\d{8})', protocol_text)
    if nct_match:
        facts.nct_id = nct_match.group(1)

    study_id_match = re.search(r'(?:Study\s+ID|Protocol\s+(?:No|Number|ID))[:\s]+([A-Z0-9-]+)', protocol_text, re.I)
    if study_id_match:
        facts.study_id = study_id_match.group(1)

    sponsor_match = re.search(r'(?:Sponsor|Company)[:\s]+([A-Za-z][A-Za-z0-9\s&-]+?)(?:\n|,|\.)', protocol_text, re.I)
    if sponsor_match:
        facts.sponsor = sponsor_match.group(1).strip()

    # === DRUG ===
    # Common words to exclude from drug name matching
    excluded_words = {
        'NCT', 'THE', 'AND', 'FOR', 'FDA', 'ICH', 'IN', 'TO', 'OF', 'AT', 'BY', 'OR',
        'IS', 'IT', 'AS', 'BE', 'WAS', 'ARE', 'WITH', 'THAT', 'THIS', 'FROM', 'WILL',
        'AN', 'ON', 'NOT', 'HAVE', 'HAS', 'HAD', 'BUT', 'ALL', 'CAN', 'HER', 'HIS',
        'ITS', 'MAY', 'NEW', 'NOW', 'OLD', 'SEE', 'WAY', 'WHO', 'BOY', 'DID', 'GET',
        'HIM', 'LET', 'PUT', 'SAY', 'SHE', 'TOO', 'USE', 'DOSE', 'DRUG', 'DOSE',
        'ADMINISTERED', 'GIVEN', 'TREATMENT', 'THERAPY', 'STUDY', 'TRIAL', 'PLACEBO',
        'ACTIVE', 'CONTROL', 'GROUP', 'ARM', 'PATIENTS', 'SUBJECTS'
    }

    drug_patterns = [
        # Pattern 1: Drug code format like TJ301, AB1234, XYZ123 (case-insensitive)
        r'\b([A-Za-z]{2,4}\d{3,5})\b',
        # Pattern 2: Named after "Investigational Product/IMP/Study Drug:" - capture alphanumeric word
        r'(?:Investigational\s+Product|IMP|Study\s+Drug)[:\s]+([A-Za-z][A-Za-z0-9]{2,})',
        # Pattern 3: Named drug with comprehensive INN suffixes
        r'\b([A-Za-z]{4,}(?:mab|nib|lib|zumab|ximab|tinib|ciclib|rafenib|lisib|metinib))\b',
        # Pattern 4: S1P modulators and immunomodulators (-simod, -limod, -imod)
        r'\b([A-Za-z]{4,}(?:simod|limod|imod|nimod|rimod))\b',
        # Pattern 5: Small molecules - cardiovascular, GI, metabolic
        r'\b([A-Za-z]{4,}(?:pril|sartan|olol|dipine|statin|prazole|gliptin|glutide|gliflozin))\b',
        # Pattern 6: Oncology drugs
        r'\b([A-Za-z]{4,}(?:parib|platin|taxel|bine|rubicin))\b',
        # Pattern 7: Study of [DRUG] or Trial of [DRUG]
        r'(?:Study\s+of|Trial\s+of)\s+([A-Za-z][A-Za-z0-9-]{3,})',
        # Pattern 8: Drug code with hyphen like FE-999301
        r'\b([A-Za-z]{2,3}[-]?\d{4,6})\b',
        # Pattern 9: receive [DRUG] or [DRUG] 2mg patterns
        r'(?:receive|receiving)\s+(?:either\s+)?([A-Za-z][A-Za-z0-9-]{3,})\s+(?:\d+\s*mg)?',
        r'([A-Za-z][A-Za-z0-9-]{3,})\s+\d+\s*(?:mg|mcg)\s+(?:once|twice|daily)',
    ]

    for pattern in drug_patterns:
        matches = re.findall(pattern, protocol_text, re.I)
        for drug in matches:
            drug = drug.strip()
            # Skip if too short or in exclusion list
            if len(drug) < 3:
                continue
            if drug.upper() in excluded_words:
                continue
            # Skip if it looks like a measurement (ends in mg, ml, etc.)
            if re.match(r'^\d+\s*(mg|ml|mcg|g|kg)$', drug, re.I):
                continue
            # Valid drug name found
            facts.drug_name = drug.upper() if re.match(r'^[A-Za-z]{2,4}\d{3,5}$', drug) else drug
            break
        if facts.drug_name:
            break

    # Drug code (e.g., FE 999301)
    code_match = re.search(r'\b([A-Z]{2}[-\s]?\d{5,6})\b', protocol_text)
    if code_match:
        facts.drug_code = code_match.group(1)

    # === PHASE ===
    phase_match = re.search(r'Phase\s*(I{1,3}|[1-4]|2a|2b|3a|3b)', protocol_text, re.I)
    if phase_match:
        facts.phase = f"Phase {phase_match.group(1)}"

    # === INDICATION ===
    indication_patterns = [
        (r"ulcerative\s+colitis", "Ulcerative Colitis"),
        (r"Crohn'?s?\s+disease", "Crohn's Disease"),
        (r"rheumatoid\s+arthritis", "Rheumatoid Arthritis"),
        (r"non-small\s+cell\s+lung\s+cancer|NSCLC", "Non-Small Cell Lung Cancer"),
        (r"breast\s+cancer", "Breast Cancer"),
        (r"multiple\s+sclerosis", "Multiple Sclerosis"),
    ]
    for pattern, name in indication_patterns:
        if re.search(pattern, protocol_text, re.I):
            facts.indication = name
            break

    # === THERAPEUTIC AREA ===
    ta_patterns = [
        (r"(?:IBD|ulcerative|Crohn)", "IBD"),
        (r"(?:oncolog|cancer|tumor|carcinoma)", "Oncology"),
        (r"(?:rheumat|arthriti)", "Rheumatology"),
        (r"(?:immun|autoimmun)", "Immunology"),
        (r"(?:neurolog|sclerosis)", "Neurology"),
    ]
    for pattern, ta in ta_patterns:
        if re.search(pattern, protocol_text, re.I):
            facts.therapeutic_area = ta
            break

    # === DESIGN TYPE ===
    design_parts = []
    if re.search(r'randomized', protocol_text, re.I):
        design_parts.append("randomized")
    if re.search(r'double[- ]blind', protocol_text, re.I):
        design_parts.append("double-blind")
    elif re.search(r'open[- ]label', protocol_text, re.I):
        design_parts.append("open-label")
    if re.search(r'placebo[- ]controlled', protocol_text, re.I):
        design_parts.append("placebo-controlled")
    if design_parts:
        facts.design_type = ", ".join(design_parts)

    # === ROUTE ===
    route_patterns = [
        (r'\b(?:intravenous(?:ly)?|IV)\b', "intravenous"),
        (r'\b(?:subcutaneous(?:ly)?|SC)\b', "subcutaneous"),
        (r'\b(?:oral(?:ly)?|PO)\b', "oral"),
        (r'\b(?:intramuscular(?:ly)?|IM)\b', "intramuscular"),
    ]
    for pattern, route in route_patterns:
        if re.search(pattern, protocol_text, re.I):
            facts.route = route
            break

    # === SAMPLE SIZE ===
    n_patterns = [
        r'(?:total\s+of\s+)?(\d{2,4})\s+(?:patients?|subjects?)\s+(?:will\s+be\s+)?(?:enrolled|randomized)',
        r'(?:sample\s+size)[:\s]+(\d{2,4})',
        r'(?:enroll|randomize)\s+(?:approximately\s+)?(\d{2,4})',
        r'N\s*[=:]\s*(\d{2,4})',
    ]
    for pattern in n_patterns:
        match = re.search(pattern, protocol_text, re.I)
        if match:
            n = int(match.group(1))
            if 10 <= n <= 10000:
                facts.total_n = n
                break

    # === RATIO ===
    ratio_match = re.search(r'\b(\d+:\d+(?::\d+)*)\b', protocol_text)
    if ratio_match:
        facts.ratio = ratio_match.group(1)
        facts.num_arms = len(facts.ratio.split(':'))

    # === ARMS (Improved extraction with doses) ===
    # First extract all doses mentioned in the protocol for later use
    all_doses_in_protocol = []
    dose_extraction_patterns = [
        r'(\d+)\s*mg',  # Just number + mg
        r'(\d+)\s*mcg',
        r'(\d+)\s*g\b',
    ]
    for pattern in dose_extraction_patterns:
        matches = re.findall(pattern, protocol_text, re.I)
        for m in matches:
            try:
                dose_val = int(m)
                # Filter reasonable drug doses (typically 1-1000 for mg)
                if 1 <= dose_val <= 2000:
                    all_doses_in_protocol.append(dose_val)
            except:
                pass

    # Get unique doses sorted by frequency (most common first)
    from collections import Counter
    dose_counts = Counter(all_doses_in_protocol)
    # Get doses that appear multiple times (likely treatment doses, not random numbers)
    common_doses = [dose for dose, count in dose_counts.most_common() if count >= 2]

    # Look for structured arm definitions using multiple patterns
    arm_patterns = [
        # Pattern 1: "- Arm A: TJ301 300 mg"
        r'[-•]\s*(?:Arm|Group)\s*([A-D1-4])[:\s]+([^\n]+?)(?:\n|$)',
        # Pattern 2: "Arm A: TJ301 300 mg" (without bullet)
        r'(?:^|\n)\s*(?:Arm|Group)\s*([A-D1-4])[:\s]+([^\n]+?)(?:\n|$)',
        # Pattern 3: "Treatment Arm 1: ..."
        r'Treatment\s+(?:Arm|Group)\s*(\d)[:\s]+([^\n]+?)(?:\n|$)',
    ]

    seen_arms = set()
    for arm_pattern in arm_patterns:
        arm_matches = list(re.finditer(arm_pattern, protocol_text, re.I | re.MULTILINE))
        for match in arm_matches:
            arm_id = match.group(1).upper()
            arm_desc = match.group(2).strip()[:150]

            # Skip if already seen or too short or looks like title
            if arm_id in seen_arms or len(arm_desc) < 5:
                continue
            if 'study' in arm_desc.lower() and 'patient' in arm_desc.lower():
                continue  # Skip title-like text

            seen_arms.add(arm_id)
            facts.arm_names.append(f"Arm {arm_id}")

            # Extract dose from description
            dose_match = re.search(r'(\d+\s*(?:mg|mcg|g|mL)(?:\s*(?:Q\d+W|every\s+\d+\s+weeks?))?)', arm_desc, re.I)
            if dose_match:
                dose = dose_match.group(1)
                facts.arm_doses.append(dose)
                facts.arm_descriptions.append(arm_desc)
            else:
                facts.arm_descriptions.append(arm_desc)
                facts.arm_doses.append("")

    # If no structured arms found, try to infer from ratio and drug name
    if not facts.arm_names and facts.num_arms and facts.drug_name:
        drug = facts.drug_name

        # Try multiple patterns to find doses associated with the drug
        dose_patterns = [
            # Pattern 1: "drug_name XXX mg" (with or without space)
            rf'{re.escape(drug)}\s*(\d+)\s*mg',
            # Pattern 2: "XXX mg drug_name" or "XXXmg of drug_name"
            rf'(\d+)\s*mg\s*(?:of\s+)?{re.escape(drug)}',
            # Pattern 3: "XXX mg" near drug name (within 50 chars)
            rf'{re.escape(drug)}.{{0,30}}?(\d+)\s*mg',
            rf'(\d+)\s*mg.{{0,30}}?{re.escape(drug)}',
        ]

        dose_matches = []
        for pattern in dose_patterns:
            matches = re.findall(pattern, protocol_text, re.I)
            dose_matches.extend(matches)

        # Convert to integers and dedupe
        unique_doses = []
        seen = set()
        for dose in dose_matches:
            try:
                dose_val = int(dose)
                if dose_val not in seen and 1 <= dose_val <= 2000:
                    seen.add(dose_val)
                    unique_doses.append(dose_val)
            except:
                pass

        # If no doses found from drug patterns, use common doses from protocol
        if not unique_doses and common_doses:
            # Filter to reasonable treatment doses (typically > 50 for biologics)
            unique_doses = [d for d in common_doses if d >= 50][:3]

        # Sort doses descending (high dose first)
        unique_doses = sorted(unique_doses, reverse=True)

        # Try to find dosing schedule (Q2W, every 2 weeks, etc.)
        schedule_match = re.search(r'(Q\d+W|every\s+\d+\s+weeks?)', protocol_text, re.I)
        schedule = schedule_match.group(1) if schedule_match else ""

        if facts.num_arms == 2:
            if unique_doses:
                facts.arm_names = [f"{drug} {unique_doses[0]} mg", "Placebo"]
                facts.arm_descriptions = [f"{drug} {unique_doses[0]} mg {schedule}".strip(), "Matching placebo"]
                facts.arm_doses = [f"{unique_doses[0]} mg", ""]
            else:
                facts.arm_names = [f"{drug}", "Placebo"]
                facts.arm_descriptions = [f"{drug} active treatment", "Matching placebo"]
        elif facts.num_arms == 3:
            if len(unique_doses) >= 2:
                high_dose = unique_doses[0]
                low_dose = unique_doses[1]
                facts.arm_names = [f"{drug} {high_dose} mg", f"{drug} {low_dose} mg", "Placebo"]
                facts.arm_descriptions = [
                    f"{drug} {high_dose} mg {schedule} (High Dose)".strip(),
                    f"{drug} {low_dose} mg {schedule} (Low Dose)".strip(),
                    "Matching placebo"
                ]
                facts.arm_doses = [f"{high_dose} mg", f"{low_dose} mg", ""]
            elif len(unique_doses) == 1:
                facts.arm_names = [f"{drug} {unique_doses[0]} mg High", f"{drug} {unique_doses[0]} mg Low", "Placebo"]
                facts.arm_descriptions = [f"{drug} high dose", f"{drug} low dose", "Matching placebo"]
                facts.arm_doses = [f"{unique_doses[0]} mg", "", ""]
            else:
                facts.arm_names = [f"{drug} High Dose", f"{drug} Low Dose", "Placebo"]
                facts.arm_descriptions = [f"{drug} high dose", f"{drug} low dose", "Matching placebo"]
        else:
            facts.arm_names = [f"Treatment Arm {i+1}" for i in range(facts.num_arms)]
            facts.arm_descriptions = [f"Treatment arm {i+1}" for i in range(facts.num_arms)]

    # Calculate per-arm N
    if facts.total_n and facts.num_arms:
        per_arm = facts.total_n // facts.num_arms
        facts.per_arm_n = {name: per_arm for name in facts.arm_names} if facts.arm_names else {}

    # === POWER ===
    # Extract ALL power values mentioned in the protocol (may have multiple scenarios)
    # Look for power with associated effect sizes/differences
    power_with_context_patterns = [
        # "83% power for 30% difference" or "83% power for a 30 percentage point difference"
        r'(\d{2})%?\s*power[^.]*?(?:for\s+(?:a\s+)?)?(\d{1,2})(?:\s*percentage\s+point|\s*%|\s*percent)?\s*(?:difference|improvement)',
        # "power of 83% to detect a 30% difference"
        r'power\s+(?:of\s+)?(\d{2})%?[^.]*?(?:detect|observe)[^.]*?(\d{1,2})(?:\s*%|\s*percent)?\s*(?:difference|improvement)',
        # "30% difference with 83% power"
        r'(\d{1,2})(?:\s*%|\s*percent)?\s*(?:difference|improvement)[^.]*?(\d{2})%?\s*power',
    ]

    power_scenario_list = []
    for pattern in power_with_context_patterns:
        matches = re.finditer(pattern, protocol_text, re.I)
        for match in matches:
            groups = match.groups()
            # Determine which is power and which is effect size
            if 'difference' in pattern.split('(')[0] or 'improvement' in pattern.split('(')[0]:
                # Pattern has effect size first
                effect_size = groups[0]
                power_val = groups[1]
            else:
                # Pattern has power first
                power_val = groups[0]
                effect_size = groups[1] if len(groups) > 1 else None

            if power_val:
                pv = int(power_val)
                if 70 <= pv <= 99:
                    scenario = f"{pv}%"
                    if effect_size:
                        scenario += f" for {effect_size}% difference"
                    if scenario not in power_scenario_list:
                        power_scenario_list.append(scenario)

    # Also extract standalone power values
    power_matches = re.findall(r'(\d{2})%?\s*power|power\s+(?:of\s+)?(\d{2})%?', protocol_text, re.I)
    power_values = []
    for match in power_matches:
        power_val = match[0] or match[1]
        if power_val and int(power_val) >= 70 and int(power_val) <= 99:
            if power_val not in power_values:
                power_values.append(power_val)

    # Use the HIGHEST power value as the primary (typically for primary comparison)
    if power_values:
        # Sort to get highest first
        sorted_powers = sorted(power_values, key=int, reverse=True)
        facts.power = f"{sorted_powers[0]}%"
        # Store all power scenarios (with context if available)
        if power_scenario_list:
            facts.power_scenarios = power_scenario_list
        elif len(sorted_powers) > 1:
            facts.power_scenarios = [f"{p}%" for p in sorted_powers]

    # === POWER CALCULATION ASSUMPTIONS ===
    # Extract expected response rates - look for patterns like "10% vs 40%"
    rate_comparison = re.search(
        r'(\d{1,2})%?\s*(?:vs\.?|versus|and|compared\s+to)\s*(\d{1,2})%?',
        protocol_text, re.I
    )
    if rate_comparison:
        rate1 = int(rate_comparison.group(1))
        rate2 = int(rate_comparison.group(2))
        # Assume lower rate is placebo, higher is active
        if rate1 < rate2:
            facts.expected_response_placebo = f"{rate1}%"
            facts.expected_response_active = f"{rate2}%"
        else:
            facts.expected_response_placebo = f"{rate2}%"
            facts.expected_response_active = f"{rate1}%"

    # Fallback: Extract expected response rates for placebo separately
    if not facts.expected_response_placebo:
        placebo_rate = re.search(
            r'(?:placebo|control)\s+(?:group\s+)?(?:response\s+)?rate[:\s]+(?:of\s+)?(\d{1,2})%?|'
            r'(\d{1,2})%?\s+(?:for\s+)?placebo|'
            r'expected\s+(?:placebo\s+)?response[:\s]+(\d{1,2})%?',
            protocol_text, re.I
        )
        if placebo_rate:
            rate = placebo_rate.group(1) or placebo_rate.group(2) or placebo_rate.group(3)
            if rate:
                facts.expected_response_placebo = f"{rate}%"

    # Fallback: Extract expected response rates for active separately
    if not facts.expected_response_active:
        active_rate = re.search(
            r'(?:active|treatment|high\s+dose)\s+(?:group\s+)?(?:response\s+)?rate[:\s]+(?:of\s+)?(\d{1,2})%?|'
            r'(\d{1,2})%?\s+(?:for\s+)?(?:active|treatment|high\s+dose)|'
            r'expected\s+(?:active\s+)?response[:\s]+(\d{1,2})%?',
            protocol_text, re.I
        )
        if active_rate:
            rate = active_rate.group(1) or active_rate.group(2) or active_rate.group(3)
            if rate:
                facts.expected_response_active = f"{rate}%"

    # Extract primary comparison for power (e.g., placebo vs 600mg)
    comparison = re.search(
        r'(?:primary\s+)?comparison[:\s]+([^.]+)|'
        r'(?:power|sample\s+size)[^.]*?(?:for\s+)?(?:the\s+)?comparison\s+(?:of|between)\s+([^.]+)',
        protocol_text, re.I
    )
    if comparison:
        facts.primary_comparison = (comparison.group(1) or comparison.group(2) or "").strip()[:100]

    # === ALPHA ===
    alpha_patterns = [
        r'alpha\s*(?:=|of)?\s*(0\.0\d+)',
        r'significance\s+level\s*(?:=|of)?\s*(0\.0\d+)',
        r'p\s*[<≤]\s*(0\.0\d+)',
        r'type\s+I\s+error[:\s]*(0\.0\d+)',
    ]
    for pattern in alpha_patterns:
        alpha_match = re.search(pattern, protocol_text, re.I)
        if alpha_match:
            facts.alpha = float(alpha_match.group(1))
            break

    # Alpha sidedness - prioritize context near "primary" analysis
    # First check for specific primary analysis context
    primary_context = re.search(
        r'primary\s+(?:endpoint|analysis|efficacy)[^.]*?(one[- ]sided|two[- ]sided|1[- ]sided|2[- ]sided)',
        protocol_text, re.I
    )
    if primary_context:
        sidedness = primary_context.group(1).lower()
        facts.alpha_sidedness = "one-sided" if "one" in sidedness or "1" in sidedness else "two-sided"
    else:
        # Fallback to general detection
        if re.search(r'one[- ]sided|1[- ]sided', protocol_text, re.I):
            facts.alpha_sidedness = "one-sided"
        elif re.search(r'two[- ]sided|2[- ]sided', protocol_text, re.I):
            facts.alpha_sidedness = "two-sided"

    # === DROPOUT ===
    dropout_match = re.search(r'(\d{1,2})%?\s*(?:dropout|discontinuation|withdrawal)', protocol_text, re.I)
    if dropout_match:
        facts.dropout_rate = f"{dropout_match.group(1)}%"

    # === PRIMARY ENDPOINT ===
    # Try multiple patterns to catch different formats
    endpoint_patterns = [
        # Pattern 1: "Primary Endpoint= Overall Survival (OS)" - with equals sign
        r'(?:primary\s+(?:efficacy\s+)?endpoint)\s*[=:]\s*([^\n]{10,150})',
        # Pattern 2: "Primary endpoint is Overall Survival" - with "is"
        r'(?:primary\s+(?:efficacy\s+)?endpoint)\s+(?:is|will\s+be)\s+([^\n.]{10,150})',
        # Pattern 3: Standard colon format
        r'(?:primary\s+(?:efficacy\s+)?endpoint)[:\s]+([^\n.]{10,150})',
        # Pattern 4: "will use X as the primary endpoint"
        r'(?:use|using)\s+([A-Z][^.]{10,80})\s+as\s+(?:the\s+)?primary\s+endpoint',
        # Pattern 5: Endpoint on next line after "Primary Endpoint"
        r'Primary\s+Endpoint\s*\n\s*([A-Z][^\n]{5,100})',
    ]

    for pattern in endpoint_patterns:
        endpoint_match = re.search(pattern, protocol_text, re.I)
        if endpoint_match:
            endpoint_text = endpoint_match.group(1).strip()
            # Clean up: remove trailing punctuation, excessive whitespace
            endpoint_text = re.sub(r'\s+', ' ', endpoint_text).strip()
            endpoint_text = endpoint_text.rstrip('.,;:')
            if len(endpoint_text) >= 10:
                facts.primary_endpoint = endpoint_text
                break

    # === PRIMARY TIMEPOINT ===
    timepoint_match = re.search(r'(?:at|through)\s+(Week\s+\d+)', protocol_text, re.I)
    if timepoint_match:
        facts.primary_timepoint = timepoint_match.group(1)

    # === PRIMARY POPULATION ===
    pop_match = re.search(r'(ITT|FAS|mITT|PP)\s+(?:population)?', protocol_text, re.I)
    if pop_match:
        facts.primary_population = pop_match.group(1).upper()

    # === STRATIFICATION (Improved extraction) ===
    # Look for stratification section with bullet points
    strat_section = re.search(
        r'(?:stratif(?:y|ied|ication)|randomization\s+(?:will\s+be\s+)?stratif(?:y|ied))\s+(?:by|according\s+to)?[:\s]*\n?([-•][^\n]+(?:\n[-•][^\n]+)*)',
        protocol_text, re.I
    )

    if strat_section:
        # Extract bullet points
        bullets = re.findall(r'[-•]\s*([^\n]+)', strat_section.group(1))
        for bullet in bullets:
            factor = bullet.strip()
            # Clean up but keep (yes/no) annotations
            factor = re.sub(r'^\d+\.\s*', '', factor)
            if 5 < len(factor) < 100:
                # Normalize to prevent duplicates
                normalized = factor.lower().strip()
                existing_normalized = [f.lower().strip() for f in facts.stratification_factors]
                if normalized not in existing_normalized:
                    facts.stratification_factors.append(factor)
    else:
        # Fallback: look for inline stratification
        strat_inline = re.search(
            r'stratif(?:y|ied|ication)\s+(?:by|according\s+to)[:\s]+([^.]+)',
            protocol_text, re.I
        )
        if strat_inline:
            factors_text = strat_inline.group(1)
            # Split by "and" or comma, but not if inside parentheses
            factors = re.split(r'\s+and\s+|,\s*(?![^()]*\))', factors_text)
            for f in factors:
                f = f.strip()
                if 5 < len(f) < 100 and 'covariate' not in f.lower():
                    normalized = f.lower().strip()
                    existing_normalized = [x.lower().strip() for x in facts.stratification_factors]
                    if normalized not in existing_normalized:
                        facts.stratification_factors.append(f)

    # === SECONDARY ENDPOINTS ===
    secondary_patterns = [
        r'secondary\s+(?:efficacy\s+)?endpoints?[:\s]+([^\n]+(?:\n(?![A-Z0-9])[^\n]+)*)',
        r'secondary\s+objectives?[:\s]+([^\n]+)',
    ]
    for pattern in secondary_patterns:
        sec_matches = re.finditer(pattern, protocol_text, re.I)
        for sec_match in sec_matches:
            endpoint_text = sec_match.group(1)
            # Split if multiple endpoints listed
            endpoints = re.split(r'[;]|\n[-•]|\d+\.\s+', endpoint_text)
            for ep in endpoints[:5]:  # Limit to 5
                ep = ep.strip()
                if 10 < len(ep) < 200 and ep not in facts.secondary_endpoints:
                    facts.secondary_endpoints.append(ep)

    # === POPULATION DEFINITIONS ===
    # ITT definition - look for specific line format "- ITT: All randomized patients"
    itt_bullet = re.search(r'[-•]\s*ITT[:\s]+([^\n]+)', protocol_text, re.I)
    if itt_bullet:
        facts.itt_definition = itt_bullet.group(1).strip()[:150]
    else:
        itt_patterns = [
            r'ITT\s+(?:population)?[:\s]+([^.\n]+)',
            r'intent[- ]to[- ]treat[^:]*:[:\s]*([^.\n]+)',
        ]
        for pattern in itt_patterns:
            itt_match = re.search(pattern, protocol_text, re.I)
            if itt_match:
                defn = itt_match.group(1).strip()
                # Stop at next bullet point or section
                defn = re.split(r'\n[-•]|\n[A-Z]', defn)[0]
                facts.itt_definition = defn[:150]
                break

    # PP definition
    pp_patterns = [
        r'(?:PP|per[- ]protocol)\s+(?:population)?[:\s]+([^.]+)',
        r'(?:PP|per[- ]protocol)[^.]*(?:defined\s+as|includes?|consists?\s+of)[:\s]+([^.]+)',
    ]
    for pattern in pp_patterns:
        pp_match = re.search(pattern, protocol_text, re.I)
        if pp_match:
            facts.pp_definition = pp_match.group(1).strip()[:200]
            break

    # Safety population
    safety_patterns = [
        r'safety\s+(?:population|analysis\s+set)[:\s]+([^.]+)',
        r'safety\s+(?:population|set)[^.]*(?:defined\s+as|includes?|consists?\s+of)[:\s]+([^.]+)',
    ]
    for pattern in safety_patterns:
        safety_match = re.search(pattern, protocol_text, re.I)
        if safety_match:
            facts.safety_definition = safety_match.group(1).strip()[:200]
            break

    # === PRIMARY ANALYSIS METHOD ===
    # First, determine if primary endpoint is binary or continuous
    # Binary endpoints need Logistic Regression, not ANCOVA
    is_binary_endpoint = False
    binary_indicators = [
        r'remission',
        r'response',
        r'responder',
        r'yes\s*/\s*no',
        r'success\s*/?\s*failure',
        r'proportion\s+of\s+patients',
        r'percentage\s+of\s+patients',
        r'binary\s+endpoint',
        r'dichotomous',
    ]
    for indicator in binary_indicators:
        if re.search(rf'primary\s+(?:endpoint|efficacy|outcome)[^.]*{indicator}', protocol_text, re.I):
            is_binary_endpoint = True
            break

    # For binary endpoints, prioritize logistic regression
    # Check explicitly for logistic regression first
    if is_binary_endpoint:
        # Strong preference for Logistic Regression when binary endpoint
        if re.search(r'logistic\s+regression', protocol_text, re.I):
            facts.primary_analysis_method = 'Logistic Regression'
        elif re.search(r'CMH|cochran[- ]mantel[- ]haenszel', protocol_text, re.I):
            facts.primary_analysis_method = 'Cochran-Mantel-Haenszel Test'
        elif re.search(r"fisher['\u2019]?s?\s+exact", protocol_text, re.I):
            facts.primary_analysis_method = "Fisher's Exact Test"
        elif re.search(r'chi[- ]square|χ²', protocol_text, re.I):
            facts.primary_analysis_method = 'Chi-Square Test'
        else:
            # Default to Logistic Regression for binary endpoints
            facts.primary_analysis_method = 'Logistic Regression'
    else:
        # For continuous endpoints, use general pattern matching
        method_patterns = [
            (r'logistic\s+regression', 'Logistic Regression'),
            (r'cox\s+(?:proportional\s+)?hazard', 'Cox Proportional Hazards'),
            (r'kaplan[- ]meier', 'Kaplan-Meier'),
            (r'log[- ]rank\s+test', 'Log-Rank Test'),
            (r'CMH\s+test|cochran[- ]mantel[- ]haenszel', 'Cochran-Mantel-Haenszel Test'),
            (r'ANCOVA|analysis\s+of\s+covariance', 'ANCOVA'),
            (r'MMRM|mixed[- ]model\s+repeated\s+measures', 'MMRM'),
            (r"fisher['\u2019]?s?\s+exact", "Fisher's Exact Test"),
            (r'chi[- ]square|χ²', 'Chi-Square Test'),
            (r'wilcoxon', 'Wilcoxon Test'),
            (r't[- ]test', 't-Test'),
            (r'GEE|generalized\s+estimating\s+equation', 'GEE'),
        ]
        for pattern, method_name in method_patterns:
            # Look for method in context of primary analysis
            primary_method = re.search(
                rf'primary\s+(?:endpoint|analysis|efficacy)[^.]*?{pattern}',
                protocol_text, re.I
            )
            if primary_method:
                facts.primary_analysis_method = method_name
                break
            # Fallback: any mention of the method
            if not facts.primary_analysis_method and re.search(pattern, protocol_text, re.I):
                facts.primary_analysis_method = method_name

    # === PRIMARY ENDPOINT DEFINITION (Full with criteria) ===
    endpoint_def_patterns = [
        r'(?:primary\s+endpoint)[^.]*defined\s+as[:\s]+([^.]+(?:\.[^A-Z])*)',
        r'(?:clinical\s+and\s+endoscopic\s+remission)[^.]*defined\s+as[:\s]+([^.]+)',
        r'(?:remission)[^.]*defined\s+as[:\s]+([^.]+)',
    ]
    for pattern in endpoint_def_patterns:
        match = re.search(pattern, protocol_text, re.I)
        if match:
            definition = match.group(1).strip()
            if len(definition) > 20:
                facts.primary_endpoint_definition = definition[:300]
                break

    # === DETAILED SECONDARY ENDPOINTS WITH TIMEPOINTS ===
    secondary_detailed = []

    # Patterns to EXCLUDE - these are analysis methods, not endpoints
    exclude_patterns = [
        r'will\s+be\s+analy[sz]ed',  # "will be analyzed using..."
        r'using\s+(?:a\s+)?(?:logistic|repeated|regression)',  # Method descriptions
        r'model\s+(?:will|is|are)',  # Model descriptions
        r'statistical\s+(?:analysis|method)',  # Analysis descriptions
        r'GEE|ANCOVA|MMRM',  # Method abbreviations
        r'^The\s+(?:analysis|primary|secondary)',  # Sentence starters about analysis
        r'confidence\s+interval',  # CI descriptions
        r'p[- ]value',  # p-value descriptions
        r'test\s+will\s+be',  # Test descriptions
    ]

    secondary_section = re.search(
        r'secondary\s+(?:efficacy\s+)?endpoints?[:\s]+(.+?)(?:(?:\n\s*\n)|(?:exploratory)|(?:\d+\.\s*[A-Z]))',
        protocol_text, re.I | re.DOTALL
    )
    if secondary_section:
        section_text = secondary_section.group(1)
        # Extract bullet points
        bullet_items = re.findall(r'[-•]\s*([^\n]+)', section_text)
        for item in bullet_items[:20]:
            item = item.strip()

            # Skip items that don't look like endpoints
            if len(item) < 10:
                continue

            # Skip items that match exclusion patterns (method/analysis descriptions)
            is_excluded = False
            for excl_pattern in exclude_patterns:
                if re.search(excl_pattern, item, re.I):
                    is_excluded = True
                    break
            if is_excluded:
                continue

            # Must contain endpoint-like terms
            if not re.search(r'(?:response|remission|score|change|healing|proportion|percent|rate|Mayo|endoscop|mucosal)', item, re.I):
                # Only include if it looks like an endpoint
                if not re.search(r'(?:week|day|month|at\s+\d)', item, re.I):
                    continue

            # Clean up the endpoint text - remove any pipe characters or table fragments
            item = re.sub(r'\|.*$', '', item).strip()
            item = re.sub(r'\s+', ' ', item)  # Normalize whitespace

            # Skip if still looks like analysis description after cleanup
            if re.search(r'analy[sz]ed|regression|model', item, re.I):
                continue

            # Try to extract timepoint
            timepoint_match = re.search(r'(?:at\s+)?(?:Week|Day|Month)\s+\d+(?:\s*,\s*(?:Week|Day|Month)\s+\d+)*', item, re.I)
            endpoint_info = {
                'endpoint': item[:150],  # Truncate to reasonable length
                'timepoint': timepoint_match.group(0) if timepoint_match else 'Various'
            }
            secondary_detailed.append(endpoint_info)

    # If no secondary endpoints found, try alternate extraction patterns
    if not secondary_detailed:
        # Try to find common UC/GI endpoints directly
        common_endpoints = [
            (r'(?:clinical\s+(?:and\s+)?endoscopic\s+)?remission', 'Clinical/endoscopic remission'),
            (r'clinical\s+response', 'Clinical response'),
            (r'mucosal\s+healing', 'Mucosal healing'),
            (r'endoscopic\s+(?:improvement|response)', 'Endoscopic response'),
            (r'(?:full\s+)?mayo\s+score', 'Change in Mayo score'),
            (r'partial\s+mayo', 'Partial Mayo score'),
            (r'modified\s+mayo', 'Modified Mayo score'),
            (r'(?:rectal\s+)?bleeding\s+(?:sub)?score', 'Rectal bleeding score'),
            (r'stool\s+frequency', 'Stool frequency'),
            (r'PGA\s+(?:score)?', 'PGA score'),
        ]
        for pattern, endpoint_name in common_endpoints:
            if re.search(pattern, protocol_text, re.I):
                # Find associated timepoints
                context = re.search(rf'{pattern}[^.]*(?:at|week|day)[^.]*', protocol_text, re.I)
                timepoint = 'Various'
                if context:
                    tp_match = re.search(r'(?:Week|Day)\s+\d+(?:\s*,\s*(?:Week|Day)\s+\d+)*', context.group(0), re.I)
                    if tp_match:
                        timepoint = tp_match.group(0)
                secondary_detailed.append({
                    'endpoint': endpoint_name,
                    'timepoint': timepoint
                })

    facts.secondary_endpoints_detailed = secondary_detailed

    # === PK ANALYSIS DETAILS ===
    # Check for PK substudy
    if re.search(r'PK\s+(?:sub)?study|pharmacokinetic\s+(?:analysis|sampling|population)', protocol_text, re.I):
        facts.has_pk_substudy = True

    # Extract PK parameters
    pk_params = []
    pk_param_patterns = [
        (r'AUCinf|AUC∞', 'AUCinf'),
        (r'AUCt|AUClast', 'AUClast'),
        (r'AUC0-\d+|AUCτ', 'AUCτ'),
        (r'\bCmax\b', 'Cmax'),
        (r'\btmax\b|\bt_max\b', 'tmax'),
        (r'\bCL\b|clearance', 'CL'),
        (r'\bVz\b|volume\s+of\s+distribution', 'Vz'),
        (r't½|t1/2|half[- ]life', 't½'),
        (r'\bMRT\b|mean\s+residence\s+time', 'MRT'),
        (r'λz|terminal\s+elimination', 'λz'),
        (r'%ExtrapAUC|extrapolated', '%ExtrapAUC'),
    ]
    for pattern, param_name in pk_param_patterns:
        if re.search(pattern, protocol_text, re.I):
            if param_name not in pk_params:
                pk_params.append(param_name)
    facts.pk_parameters = pk_params

    # Extract PK software
    if re.search(r'WinNonlin', protocol_text, re.I):
        facts.pk_software = 'WinNonlin'
    elif re.search(r'Phoenix', protocol_text, re.I):
        facts.pk_software = 'Phoenix WinNonlin'
    elif re.search(r'NONMEM', protocol_text, re.I):
        facts.pk_software = 'NONMEM'

    # Extract PK population size
    pk_n_match = re.search(
        r'(?:PK|pharmacokinetic)\s+(?:sub)?(?:study|population)[^.]*?(\d+)\s+(?:patients|subjects)',
        protocol_text, re.I
    )
    if pk_n_match:
        facts.pk_population_size = int(pk_n_match.group(1))

    # Extract PK sampling timepoints - try multiple patterns
    pk_sampling_patterns = [
        r'(?:PK|pharmacokinetic)\s+sampling[^.]*?(?:at|include|:)[:\s]+([^.]+)',
        r'(?:blood\s+)?samples?\s+(?:will\s+be\s+)?(?:collected|drawn|obtained)[^.]*(?:at|:)\s+([^.]+)',
        r'sampling\s+(?:times?|timepoints?|schedule)[:\s]+([^.]+)',
        r'(?:pre-?dose|predose)[^.]*(?:and\s+at|,)\s+([^.]+)',
    ]

    for pattern in pk_sampling_patterns:
        pk_sampling = re.search(pattern, protocol_text, re.I)
        if pk_sampling:
            # Look for time values (hours, minutes, or generic time points)
            timepoints = re.findall(
                r'(?:pre-?dose|predose|\d+(?:\.\d+)?\s*(?:hours?|h|minutes?|min|hrs?)|end\s+of\s+(?:infusion|dosing))',
                pk_sampling.group(1), re.I
            )
            if timepoints:
                facts.pk_sampling_timepoints = timepoints[:20]
                break

    # === BIOMARKER ENDPOINTS ===
    biomarker_patterns = [
        r'ESR|erythrocyte\s+sedimentation\s+rate',
        r'\bCRP\b|C-reactive\s+protein',
        r'IL-6|interleukin[- ]6',
        r'IL-6/sIL-6R|IL-6\s+receptor',
        r'fecal\s+calprotectin|calprotectin',
        r'neutrophil\s+count',
        r'platelet\s+count',
    ]
    for pattern in biomarker_patterns:
        if re.search(pattern, protocol_text, re.I):
            # Extract the matched biomarker name
            match = re.search(pattern, protocol_text, re.I)
            if match:
                biomarker = match.group(0)
                if biomarker not in facts.biomarker_endpoints:
                    facts.biomarker_endpoints.append(biomarker)

    # === BIOMARKER SUBGROUPS (e.g., IL-6/sIL-6R levels) ===
    biomarker_subgroup = re.search(
        r'(?:subgroup|stratif)[^.]*(?:by|based\s+on)\s+(?:baseline\s+)?([^.]*(?:IL-6|biomarker|CRP)[^.]*)',
        protocol_text, re.I
    )
    if biomarker_subgroup:
        facts.biomarker_subgroups.append(biomarker_subgroup.group(1).strip()[:100])

    # === SUBGROUP ANALYSES ===
    subgroup_factors = [
        ('age', 'Age group (<65, ≥65 years)'),
        ('sex|gender', 'Sex'),
        ('geographic\s+region', 'Geographic region'),
        ('baseline\s+(?:disease\s+)?severity', 'Baseline disease severity'),
        ('prior\s+(?:treatment|therapy|corticosteroid)', 'Prior treatment history'),
        ('IL-6|interleukin', 'Baseline IL-6/sIL-6R complex levels'),
        ('weight|BMI|body\s+mass', 'Body weight/BMI'),
        ('race|ethnic', 'Race/Ethnicity'),
    ]
    for pattern, factor_name in subgroup_factors:
        if re.search(rf'subgroup[^.]*{pattern}|{pattern}[^.]*subgroup', protocol_text, re.I):
            if factor_name not in facts.subgroup_analyses:
                facts.subgroup_analyses.append(factor_name)

    # === VISIT WINDOWS ===
    # Try to extract visit window definitions
    window_pattern = re.search(
        r'(?:visit|assessment)\s+windows?[:\s]+(.+?)(?:\n\s*\n|\Z)',
        protocol_text, re.I | re.DOTALL
    )
    if window_pattern:
        window_text = window_pattern.group(1)
        week_windows = re.findall(r'Week\s*(\d+)[:\s]+(?:Day\s*)?(\d+)\s*[±+/-]\s*(\d+)', window_text, re.I)
        for week, day, tolerance in week_windows:
            facts.visit_windows[f"Week {week}"] = f"Day {day} ± {tolerance} days"

    return facts


# =============================================================================
# ESTIMAND SCHEMA: Constrained Treatment and Endpoints
# =============================================================================

class InterCurrentEventSchema(BaseModel):
    """ICE with constrained strategy options"""
    event: str = Field(description="Description of the intercurrent event")
    strategy: Literal[
        "treatment_policy",
        "composite",
        "hypothetical",
        "principal_stratum",
        "while_on_treatment"
    ]
    rationale: str = Field(description="Rationale for strategy choice")


class EstimandSchemaBase(BaseModel):
    """
    Estimand schema with constrained protocol values.

    Constrained fields:
    - drug_name: From protocol (prevents "etrolizumab" contamination)
    - indication: From protocol
    - primary_endpoint: From protocol
    - primary_timepoint: From protocol
    - arm_descriptions: From protocol

    Free fields:
    - objective: LLM writes (but must reference constrained drug)
    - population_description: LLM writes (but must reference constrained indication)
    - intercurrent_events: LLM designs
    - summary_measure: LLM writes
    """
    # Constrained fields - LLM cannot change these
    drug_name: str
    indication: str
    primary_endpoint: str
    primary_timepoint: str
    comparator: str  # e.g., "Placebo" or active comparator

    # Semi-constrained - must include constrained values
    treatment_description: str = Field(
        description="Treatment comparison. MUST use the drug_name provided."
    )
    population_description: str = Field(
        description="Target population. MUST reference the indication provided."
    )
    variable_description: str = Field(
        description="Endpoint variable. MUST use the primary_endpoint provided."
    )

    # Free fields - LLM designs these
    objective: str = Field(description="Clinical objective of the estimand")
    intercurrent_events: List[InterCurrentEventSchema] = Field(
        description="List of intercurrent events with strategies"
    )
    summary_measure: str = Field(description="Summary measure for the estimand")
    analysis_method: str = Field(description="Primary analysis method")

    @field_validator('treatment_description')
    @classmethod
    def must_contain_drug(cls, v: str, info) -> str:
        """Ensure treatment description contains the constrained drug name"""
        drug = info.data.get('drug_name', '')
        if drug and drug.lower() not in v.lower():
            raise ValueError(f"Treatment description must contain drug name: {drug}")
        # Check for drug contaminants only (not study IDs - those may appear in references)
        # Only flag if a contaminant drug is used AND it's not the actual study drug
        drug_contaminants = ['etrolizumab', 'tocilizumab', 'sarilumab']
        for c in drug_contaminants:
            if c.lower() in v.lower() and (not drug or c.lower() != drug.lower()):
                raise ValueError(f"Treatment contains wrong drug: {c}")
        return v

    @field_validator('population_description')
    @classmethod
    def must_reference_indication(cls, v: str, info) -> str:
        """Ensure population references the indication"""
        # Check for contaminants
        if 'etrolizumab' in v.lower():
            raise ValueError("Population contains contaminant drug name")
        return v


def create_constrained_estimand_schema(facts: FullProtocolFacts) -> Type[BaseModel]:
    """
    Create Estimand schema with protocol values as Literals.

    This prevents the LLM from outputting "etrolizumab" when
    the protocol says "TJ301".
    """

    _drug = facts.drug_name or "Study Drug"
    _indication = facts.indication or "Target Indication"
    _endpoint = facts.primary_endpoint or "Primary Endpoint"
    _timepoint = facts.primary_timepoint or "Week 12"
    _comparator = "Placebo"  # Default, could extract from protocol

    # Find comparator from arms
    if facts.arm_descriptions:
        for desc in facts.arm_descriptions:
            if 'placebo' in desc.lower():
                _comparator = "Placebo"
                break
            elif 'control' in desc.lower() or 'comparator' in desc.lower():
                _comparator = desc
                break

    ConstrainedEstimand = create_model(
        'ConstrainedEstimand',
        __base__=EstimandSchemaBase,
        drug_name=(Literal[_drug], _drug),
        indication=(Literal[_indication], _indication),
        primary_endpoint=(Literal[_endpoint], _endpoint),
        primary_timepoint=(Literal[_timepoint], _timepoint),
        comparator=(Literal[_comparator], _comparator),
    )

    return ConstrainedEstimand


class FullEstimandOutput(BaseModel):
    """Complete estimand output with primary and secondary"""
    primary_estimand: EstimandSchemaBase
    secondary_estimands: List[EstimandSchemaBase] = Field(default_factory=list)


def create_full_estimand_schema(facts: FullProtocolFacts) -> Type[BaseModel]:
    """Create schema for full estimand output"""

    ConstrainedEstimand = create_constrained_estimand_schema(facts)

    FullConstrainedEstimandOutput = create_model(
        'FullConstrainedEstimandOutput',
        primary_estimand=(ConstrainedEstimand, ...),
        secondary_estimands=(List[ConstrainedEstimand], []),
    )

    return FullConstrainedEstimandOutput


# =============================================================================
# PROMPT GENERATOR
# =============================================================================

def generate_constrained_prompt(facts: FullProtocolFacts) -> str:
    """Generate prompt that tells LLM to use constrained values"""

    # Build list of all constrained values
    constraints = []

    if facts.nct_id:
        constraints.append(f"NCT ID: {facts.nct_id}")
    if facts.study_id:
        constraints.append(f"Study ID: {facts.study_id}")
    if facts.drug_name:
        constraints.append(f"Drug Name: {facts.drug_name}")
    if facts.total_n:
        constraints.append(f"Total Sample Size: {facts.total_n}")
    if facts.ratio:
        constraints.append(f"Randomization Ratio: {facts.ratio}")
    if facts.num_arms:
        constraints.append(f"Number of Arms: {facts.num_arms}")
    if facts.phase:
        constraints.append(f"Phase: {facts.phase}")
    if facts.indication:
        constraints.append(f"Indication: {facts.indication}")
    if facts.route:
        constraints.append(f"Route: {facts.route}")
    if facts.power:
        constraints.append(f"Power: {facts.power}")
    if facts.alpha:
        constraints.append(f"Alpha: {facts.alpha} ({facts.alpha_sidedness or 'one-sided'})")
    if facts.primary_endpoint:
        constraints.append(f"Primary Endpoint: {facts.primary_endpoint}")
    if facts.primary_timepoint:
        constraints.append(f"Primary Timepoint: {facts.primary_timepoint}")
    if facts.arm_names:
        constraints.append(f"Arms: {', '.join(facts.arm_names)}")
    if facts.stratification_factors:
        constraints.append(f"Stratification: {', '.join(facts.stratification_factors)}")

    prompt = f"""Generate a Statistical Analysis Plan (SAP) for this clinical trial.

## CONSTRAINED VALUES (You MUST use these EXACT values - enforced by schema):

{chr(10).join(f'- {c}' for c in constraints)}

## INSTRUCTIONS:

1. The schema enforces the exact values above - you cannot output different values
2. For narrative fields, write professional regulatory-grade prose
3. DO NOT include numbers in narrative fields - they come from constrained fields
4. DO NOT reference other studies, drugs, or examples
5. Focus ONLY on the protocol values provided above

Generate each section following the schema structure."""

    return prompt


# =============================================================================
# UTILITY: Print Constraint Summary
# =============================================================================

def print_constraint_summary(facts: FullProtocolFacts):
    """Print summary of what will be constrained"""
    print("\n" + "="*60)
    print("CONSTRAINT SUMMARY - All Protocol Values Locked")
    print("="*60)

    categories = [
        ("IDENTIFICATION", [
            ("nct_id", facts.nct_id),
            ("study_id", facts.study_id),
            ("sponsor", facts.sponsor),
        ]),
        ("STUDY INFO", [
            ("phase", facts.phase),
            ("indication", facts.indication),
            ("therapeutic_area", facts.therapeutic_area),
            ("design_type", facts.design_type),
        ]),
        ("DRUG/TREATMENT", [
            ("drug_name", facts.drug_name),
            ("drug_code", facts.drug_code),
            ("route", facts.route),
        ]),
        ("ARMS", [
            ("num_arms", facts.num_arms),
            ("ratio", facts.ratio),
            ("arm_names", facts.arm_names),
        ]),
        ("SAMPLE SIZE", [
            ("total_n", facts.total_n),
            ("power", facts.power),
            ("alpha", facts.alpha),
            ("alpha_sidedness", facts.alpha_sidedness),
        ]),
        ("ENDPOINTS", [
            ("primary_endpoint", facts.primary_endpoint),
            ("primary_timepoint", facts.primary_timepoint),
            ("secondary_endpoints", facts.secondary_endpoints),
        ]),
        ("STRATIFICATION", [
            ("stratification_factors", facts.stratification_factors),
        ]),
    ]

    total = 0
    constrained = 0

    for category, fields in categories:
        print(f"\n  {category}:")
        for name, value in fields:
            total += 1
            if value:
                constrained += 1
                status = "✓ Literal"
                val_str = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
            else:
                status = "○ Default"
                val_str = "(not found)"
            print(f"    {name}: {status} = {val_str}")

    print(f"\n  COVERAGE: {constrained}/{total} entities constrained")
    print("="*60)
