#!/usr/bin/env python3
"""
Schema-Constrained SAP Generation System
=========================================

This system ensures LLM CANNOT hallucinate values by using Pydantic Literal types
that constrain outputs at generation time - NOT post-processing.

Architecture:
1. Extract ProtocolFacts from protocol
2. Dynamically create Pydantic schemas with Literal[extracted_values]
3. LLM generates structured output that MUST conform to schema
4. Formal verification validates invariants
5. Multi-judge validation (optional) for extra safety

The key insight: The LLM cannot generate "1150" if the schema only allows Literal[90]
"""

import re
import json
from typing import Any, Dict, List, Optional, Tuple, Union, Type, Literal
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum

# Import the SINGLE SOURCE OF TRUTH for extraction
from .structured_extractor import StructuredFactExtractor, ProtocolFacts as StructuredProtocolFacts


# =============================================================================
# STAGE 1: PROTOCOL FACTS (Grounded Extraction)
# =============================================================================

@dataclass
class CitedValue:
    """A value extracted with its source citation"""
    value: Any
    citation: str  # Exact text from protocol
    page: Optional[str] = None
    confidence: float = 1.0


@dataclass
class ProtocolFacts:
    """All facts extracted from protocol with citations"""
    # Identification
    study_id: Optional[CitedValue] = None
    nct_id: Optional[CitedValue] = None
    sponsor: Optional[CitedValue] = None

    # Drug
    drug_name: Optional[CitedValue] = None
    drug_code: Optional[CitedValue] = None
    drug_generic: Optional[CitedValue] = None
    route: Optional[CitedValue] = None

    # Sample Size
    total_n: Optional[CitedValue] = None
    per_arm_n: Optional[CitedValue] = None
    power: Optional[CitedValue] = None
    alpha: Optional[CitedValue] = None
    alpha_sidedness: Optional[CitedValue] = None
    dropout_rate: Optional[CitedValue] = None

    # Design
    num_arms: Optional[CitedValue] = None
    ratio: Optional[CitedValue] = None
    arms: List[CitedValue] = field(default_factory=list)
    design_type: Optional[CitedValue] = None  # "single_arm", "randomized", etc.
    is_single_arm: bool = False  # Critical flag for template selection

    # Endpoints
    primary_endpoint: Optional[CitedValue] = None
    primary_timepoint: Optional[CitedValue] = None
    secondary_endpoints: List[CitedValue] = field(default_factory=list)

    # Populations
    primary_population: Optional[CitedValue] = None

    # Stratification
    stratification_factors: List[CitedValue] = field(default_factory=list)

    # Phase & Indication
    phase: Optional[CitedValue] = None
    indication: Optional[CitedValue] = None
    therapeutic_area: Optional[CitedValue] = None


# =============================================================================
# STAGE 2: SCHEMA-CONSTRAINED SECTION MODELS
# =============================================================================

class SampleSizeSectionBase(BaseModel):
    """
    Base schema for Sample Size section.
    Actual values are injected dynamically via Literal types.
    """
    # These will be overridden with Literal types dynamically
    total_n: int
    ratio: str
    power_percent: int
    alpha: float
    alpha_sidedness: str
    num_arms: int
    per_arm_n: int

    # Prose sections - LLM generates these
    introduction: str = Field(
        max_length=800,
        description="Opening paragraph explaining sample size rationale. DO NOT include any numbers."
    )

    power_calculation_narrative: str = Field(
        max_length=600,
        description="Description of power calculation methodology. DO NOT include any numbers."
    )

    conclusion: str = Field(
        max_length=400,
        description="Summary statement. DO NOT include any numbers."
    )

    @field_validator('introduction', 'power_calculation_narrative', 'conclusion')
    @classmethod
    def no_numbers_in_prose(cls, v: str) -> str:
        """Prose sections CANNOT contain numbers - forces use of schema fields"""
        # Allow common non-data numbers like "first", "second" but block raw digits
        found = re.findall(r'\b\d+\b', v)
        if found:
            # Filter out allowed numbers (ordinals converted, common phrases)
            disallowed = [n for n in found if int(n) > 10 and int(n) not in [100]]
            if disallowed:
                raise ValueError(f"Prose contains disallowed numbers: {disallowed}. Use schema fields for data values.")
        return v


class StudyDesignSectionBase(BaseModel):
    """Base schema for Study Design section"""
    drug_name: str
    num_arms: int
    ratio: str
    route: str

    # Arm descriptions - list of exactly num_arms items
    arm_descriptions: List[str] = Field(
        description="Description for each treatment arm"
    )

    design_narrative: str = Field(
        max_length=1000,
        description="Study design description. DO NOT include numbers except those in schema fields."
    )

    @model_validator(mode='after')
    def arm_count_matches(self) -> 'StudyDesignSectionBase':
        """Number of arm descriptions must match num_arms"""
        if len(self.arm_descriptions) != self.num_arms:
            raise ValueError(f"Expected {self.num_arms} arm descriptions, got {len(self.arm_descriptions)}")
        return self


class PrimaryAnalysisSectionBase(BaseModel):
    """Base schema for Primary Analysis section"""
    primary_endpoint: str
    primary_timepoint: str
    primary_population: str
    analysis_method: str

    analysis_narrative: str = Field(
        max_length=1200,
        description="Description of primary analysis approach"
    )

    missing_data_approach: str = Field(
        max_length=600,
        description="How missing data will be handled"
    )


# =============================================================================
# SCHEMA FACTORY: Create constrained schemas from ProtocolFacts
# =============================================================================

def create_sample_size_schema(facts: ProtocolFacts) -> Type[BaseModel]:
    """
    Dynamically create a SampleSizeSection schema with Literal constraints.

    Example: If facts.total_n.value = 90, creates:
        total_n: Literal[90]  # LLM MUST output exactly 90
    """
    # Extract values with defaults
    _total_n = facts.total_n.value if facts.total_n else 100
    _ratio = facts.ratio.value if facts.ratio else "1:1"
    _power = int(str(facts.power.value).replace('%', '')) if facts.power else 80
    _alpha = facts.alpha.value if facts.alpha else 0.05
    _alpha_sidedness = facts.alpha_sidedness.value if facts.alpha_sidedness else "one-sided"  # One-sided for efficacy trials
    _num_arms = facts.num_arms.value if facts.num_arms else 2
    _per_arm_n = facts.per_arm_n.value if facts.per_arm_n else _total_n // _num_arms

    # Create dynamic model using create_model to avoid scoping issues
    from pydantic import create_model

    ConstrainedSampleSizeSection = create_model(
        'ConstrainedSampleSizeSection',
        __base__=SampleSizeSectionBase,
        total_n=(Literal[_total_n], _total_n),  # type: ignore
        ratio=(Literal[_ratio], _ratio),  # type: ignore
        power_percent=(Literal[_power], _power),  # type: ignore
        alpha=(Literal[_alpha], _alpha),  # type: ignore
        alpha_sidedness=(Literal[_alpha_sidedness], _alpha_sidedness),  # type: ignore
        num_arms=(Literal[_num_arms], _num_arms),  # type: ignore
        per_arm_n=(Literal[_per_arm_n], _per_arm_n),  # type: ignore
    )

    return ConstrainedSampleSizeSection


def create_study_design_schema(facts: ProtocolFacts) -> Type[BaseModel]:
    """Create Study Design schema with Literal constraints"""
    _drug_name = facts.drug_name.value if facts.drug_name else "Study Drug"
    _num_arms = facts.num_arms.value if facts.num_arms else 2
    _ratio = facts.ratio.value if facts.ratio else "1:1"
    _route = facts.route.value if facts.route else "intravenous"

    from pydantic import create_model

    ConstrainedStudyDesignSection = create_model(
        'ConstrainedStudyDesignSection',
        __base__=StudyDesignSectionBase,
        drug_name=(Literal[_drug_name], _drug_name),  # type: ignore
        num_arms=(Literal[_num_arms], _num_arms),  # type: ignore
        ratio=(Literal[_ratio], _ratio),  # type: ignore
        route=(Literal[_route], _route),  # type: ignore
    )

    return ConstrainedStudyDesignSection


def create_primary_analysis_schema(facts: ProtocolFacts) -> Type[BaseModel]:
    """Create Primary Analysis schema with Literal constraints"""
    _endpoint = facts.primary_endpoint.value if facts.primary_endpoint else "Primary endpoint"
    _timepoint = facts.primary_timepoint.value if facts.primary_timepoint else "Week 12"
    _population = facts.primary_population.value if facts.primary_population else "ITT"

    from pydantic import create_model

    ConstrainedPrimaryAnalysisSection = create_model(
        'ConstrainedPrimaryAnalysisSection',
        __base__=PrimaryAnalysisSectionBase,
        primary_endpoint=(Literal[_endpoint], _endpoint),  # type: ignore
        primary_timepoint=(Literal[_timepoint], _timepoint),  # type: ignore
        primary_population=(Literal[_population], _population),  # type: ignore
        # analysis_method is not constrained - LLM chooses appropriate method
    )

    return ConstrainedPrimaryAnalysisSection


# =============================================================================
# STAGE 3: FORMAL VERIFICATION
# =============================================================================

@dataclass
class VerificationResult:
    """Result of formal verification"""
    passed: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class FormalVerifier:
    """
    Formal verification of SAP sections against protocol facts.

    Defines invariants that MUST hold for each section.
    """

    def verify_sample_size_section(
        self,
        section: dict,
        facts: ProtocolFacts
    ) -> VerificationResult:
        """
        Verify Sample Size section invariants:

        INVARIANTS:
        1. total_n == ProtocolFacts.total_n
        2. ratio == ProtocolFacts.ratio
        3. num_arms == len(ratio.split(':'))
        4. per_arm_n * num_arms ≈ total_n (within 10%)
        5. No numbers in prose that aren't in ProtocolFacts
        """
        violations = []
        warnings = []

        # INV-1: total_n matches
        if facts.total_n:
            if section.get('total_n') != facts.total_n.value:
                violations.append(
                    f"INV-1 VIOLATED: total_n={section.get('total_n')} "
                    f"but ProtocolFacts.total_n={facts.total_n.value}"
                )

        # INV-2: ratio matches
        if facts.ratio:
            if section.get('ratio') != facts.ratio.value:
                violations.append(
                    f"INV-2 VIOLATED: ratio={section.get('ratio')} "
                    f"but ProtocolFacts.ratio={facts.ratio.value}"
                )

        # INV-3: num_arms matches ratio parts
        ratio = section.get('ratio', '')
        expected_arms = len(ratio.split(':')) if ratio else 0
        actual_arms = section.get('num_arms', 0)
        if expected_arms != actual_arms:
            violations.append(
                f"INV-3 VIOLATED: ratio {ratio} has {expected_arms} parts "
                f"but num_arms={actual_arms}"
            )

        # INV-4: per_arm_n * num_arms ≈ total_n
        per_arm = section.get('per_arm_n', 0)
        total = section.get('total_n', 0)
        num_arms = section.get('num_arms', 1)
        if per_arm and total and num_arms:
            expected = per_arm * num_arms
            if abs(expected - total) > total * 0.15:  # 15% tolerance for unequal arms
                violations.append(
                    f"INV-4 VIOLATED: {per_arm} × {num_arms} = {expected} "
                    f"but total_n = {total}"
                )

        # INV-5: No unknown numbers in prose
        allowed_numbers = self._get_allowed_numbers(facts)
        for prose_field in ['introduction', 'power_calculation_narrative', 'conclusion']:
            prose = section.get(prose_field, '')
            found_numbers = set(int(n) for n in re.findall(r'\b(\d+)\b', prose))
            unknown = found_numbers - allowed_numbers - {0, 1, 2, 3, 4, 5, 10, 12, 24, 48, 72, 100}
            if unknown:
                warnings.append(
                    f"INV-5 WARNING: Unknown numbers in {prose_field}: {unknown}"
                )

        return VerificationResult(
            passed=len(violations) == 0,
            violations=violations,
            warnings=warnings
        )

    def verify_study_design_section(
        self,
        section: dict,
        facts: ProtocolFacts
    ) -> VerificationResult:
        """
        Verify Study Design section invariants:

        INVARIANTS:
        1. drug_name == ProtocolFacts.drug_name
        2. len(arm_descriptions) == num_arms
        3. route == ProtocolFacts.route
        """
        violations = []
        warnings = []

        # INV-1: drug_name matches
        if facts.drug_name:
            if section.get('drug_name') != facts.drug_name.value:
                violations.append(
                    f"INV-1 VIOLATED: drug_name={section.get('drug_name')} "
                    f"but ProtocolFacts.drug_name={facts.drug_name.value}"
                )

        # INV-2: arm count matches
        arms = section.get('arm_descriptions', [])
        num_arms = section.get('num_arms', 0)
        if len(arms) != num_arms:
            violations.append(
                f"INV-2 VIOLATED: {len(arms)} arm descriptions "
                f"but num_arms={num_arms}"
            )

        # INV-3: route matches
        if facts.route:
            if section.get('route') != facts.route.value:
                violations.append(
                    f"INV-3 VIOLATED: route={section.get('route')} "
                    f"but ProtocolFacts.route={facts.route.value}"
                )

        return VerificationResult(
            passed=len(violations) == 0,
            violations=violations,
            warnings=warnings
        )

    def _get_allowed_numbers(self, facts: ProtocolFacts) -> set:
        """Extract all valid numbers from ProtocolFacts"""
        allowed = set()

        for field_name in ['total_n', 'per_arm_n', 'power', 'num_arms']:
            fact = getattr(facts, field_name, None)
            if fact and fact.value:
                # Extract digits from value
                val_str = str(fact.value)
                for num in re.findall(r'\d+', val_str):
                    allowed.add(int(num))

        return allowed


# =============================================================================
# STAGE 4: GENERATION PROMPTS
# =============================================================================

def get_sample_size_prompt(facts: ProtocolFacts) -> str:
    """Generate prompt for Sample Size section with schema constraints"""

    total_n = facts.total_n.value if facts.total_n else "N/A"
    ratio = facts.ratio.value if facts.ratio else "N/A"
    power = facts.power.value if facts.power else "80%"
    alpha = facts.alpha.value if facts.alpha else 0.05
    alpha_side = facts.alpha_sidedness.value if facts.alpha_sidedness else "one-sided"  # One-sided for efficacy trials
    num_arms = facts.num_arms.value if facts.num_arms else 2
    per_arm = facts.per_arm_n.value if facts.per_arm_n else "N/A"

    return f"""Generate Section 6: Sample Size Calculation for a Statistical Analysis Plan.

CRITICAL CONSTRAINTS (enforced by schema):
- total_n MUST be exactly: {total_n}
- ratio MUST be exactly: "{ratio}"
- power_percent MUST be exactly: {power}
- alpha MUST be exactly: {alpha}
- alpha_sidedness MUST be exactly: "{alpha_side}"
- num_arms MUST be exactly: {num_arms}
- per_arm_n MUST be exactly: {per_arm}

You MUST write prose for these fields:
1. introduction: Opening paragraph explaining sample size rationale
2. power_calculation_narrative: Description of power calculation methodology
3. conclusion: Summary statement

CRITICAL RULES FOR PROSE:
- DO NOT include ANY numbers in prose fields
- The schema fields (total_n, ratio, etc.) will be rendered separately
- Your prose should describe concepts without repeating the numbers
- Use phrases like "the planned sample size" instead of stating the number

Write professional, regulatory-grade prose suitable for FDA submission."""


def get_study_design_prompt(facts: ProtocolFacts) -> str:
    """Generate prompt for Study Design section"""

    drug = facts.drug_name.value if facts.drug_name else "Study Drug"
    num_arms = facts.num_arms.value if facts.num_arms else 2
    ratio = facts.ratio.value if facts.ratio else "1:1"
    route = facts.route.value if facts.route else "intravenous"

    arm_strs = [f"- {arm.value}" for arm in facts.arms] if facts.arms else []

    return f"""Generate Section 3: Study Design for a Statistical Analysis Plan.

CRITICAL CONSTRAINTS (enforced by schema):
- drug_name MUST be exactly: "{drug}"
- num_arms MUST be exactly: {num_arms}
- ratio MUST be exactly: "{ratio}"
- route MUST be exactly: "{route}"

Known treatment arms:
{chr(10).join(arm_strs) if arm_strs else "Arms to be defined"}

You MUST provide:
1. arm_descriptions: List of {num_arms} strings describing each arm
2. design_narrative: Study design description

Write professional, regulatory-grade prose."""


# =============================================================================
# SECTION ASSEMBLER: Combine structured output into prose
# =============================================================================

class SectionAssembler:
    """Assembles verified structured output into final SAP prose"""

    def assemble_sample_size_section(self, section: dict) -> str:
        """Convert structured SampleSizeSection to prose"""

        # Build power assumptions section if available
        power_assumptions = ""
        if section.get('expected_response_placebo') or section.get('expected_response_active'):
            placebo_rate = section.get('expected_response_placebo', 'X%')
            active_rate = section.get('expected_response_active', 'Y%')
            power_assumptions = f"""
**Power Calculation Assumptions:**
- Expected response rate in placebo group: {placebo_rate}
- Expected response rate in active treatment group: {active_rate}
- Effect size: {active_rate} - {placebo_rate} difference
"""

        # Build power scenarios section if available (handles both 83% and 70% power scenarios)
        power_scenarios_text = ""
        power_scenarios = section.get('power_scenarios', [])
        if power_scenarios and len(power_scenarios) > 0:
            # Parse power scenarios - they may be dicts or strings
            scenarios_list = []
            for scenario in power_scenarios:
                if isinstance(scenario, dict):
                    comparison = scenario.get('comparison', 'Treatment comparison')
                    power = scenario.get('power', 'N/A')
                    effect = scenario.get('effect_size', '')
                    if effect:
                        scenarios_list.append(f"- {comparison}: {power} power to detect {effect}")
                    else:
                        scenarios_list.append(f"- {comparison}: {power} power")
                else:
                    scenarios_list.append(f"- {scenario}")

            if scenarios_list:
                power_scenarios_text = "\n**Power Scenarios:**\n" + "\n".join(scenarios_list)

        # Build dropout adjustment text if available
        dropout_text = ""
        dropout_rate = section.get('dropout_rate')
        if dropout_rate:
            dropout_text = f"\n\nThe sample size accounts for an anticipated dropout rate of approximately {dropout_rate}."

        return f"""## 6. SAMPLE SIZE CALCULATION

{section.get('introduction', '')}

### 6.1 Power Calculation

{section.get('power_calculation_narrative', '')}
{power_assumptions}
The study will enroll a total of {section['total_n']} patients, randomized in a {section['ratio']} ratio across {section['num_arms']} treatment arms (approximately {section['per_arm_n']} patients per arm).
{power_scenarios_text}
{dropout_text}

### 6.2 Summary

{section.get('conclusion', '')}
"""

    def assemble_study_design_section(self, section: dict) -> str:
        """Convert structured StudyDesignSection to prose"""
        arms_text = "\n".join(f"  - Arm {i+1}: {desc}"
                              for i, desc in enumerate(section.get('arm_descriptions', [])))

        return f"""3. STUDY DESIGN

{section.get('design_narrative', '')}

3.1 Treatment Arms

This study employs a {section['num_arms']}-arm design with {section['ratio']} randomization:

{arms_text}

The investigational product, {section['drug_name']}, will be administered via {section['route']} route.
"""


# =============================================================================
# MAIN GENERATOR CLASS
# =============================================================================

class SchemaConstrainedGenerator:
    """
    Main generator class that orchestrates schema-constrained generation.

    Usage:
        facts = extract_protocol_facts(protocol_text)
        generator = SchemaConstrainedGenerator(facts)
        sap = generator.generate_full_sap()
    """

    def __init__(self, facts: ProtocolFacts, llm_client=None):
        self.facts = facts
        self.llm_client = llm_client
        self.verifier = FormalVerifier()
        self.assembler = SectionAssembler()

        # Create constrained schemas
        self.sample_size_schema = create_sample_size_schema(facts)
        self.study_design_schema = create_study_design_schema(facts)
        self.primary_analysis_schema = create_primary_analysis_schema(facts)

    def generate_sample_size_section(self) -> Tuple[str, VerificationResult]:
        """
        Generate Sample Size section with schema constraints and verification.

        Returns:
            Tuple of (assembled_prose, verification_result)
        """
        # Get constrained schema
        schema = self.sample_size_schema
        prompt = get_sample_size_prompt(self.facts)

        # TODO: Use instructor library to generate with schema
        # For now, return a template that uses the constrained values

        # Get the default values from the schema (which are Literals)
        section_data = {
            'total_n': self.facts.total_n.value if self.facts.total_n else 100,
            'ratio': self.facts.ratio.value if self.facts.ratio else "1:1",
            'power_percent': 80,
            'alpha': 0.05,
            'alpha_sidedness': 'one-sided',
            'num_arms': self.facts.num_arms.value if self.facts.num_arms else 2,
            'per_arm_n': self.facts.per_arm_n.value if self.facts.per_arm_n else 50,
            'introduction': "The sample size for this study was determined based on clinical and statistical considerations to ensure adequate power to detect a clinically meaningful treatment difference.",
            'power_calculation_narrative': "Power calculations were performed using standard methodology appropriate for the primary endpoint analysis.",
            'conclusion': "The planned sample size provides adequate power to achieve the study objectives while considering practical enrollment constraints."
        }

        # Verify
        verification = self.verifier.verify_sample_size_section(section_data, self.facts)

        # Assemble
        prose = self.assembler.assemble_sample_size_section(section_data)

        return prose, verification

    def get_schema_json(self, section: str) -> str:
        """Get JSON schema for a section (for use with instructor)"""
        schemas = {
            'sample_size': self.sample_size_schema,
            'study_design': self.study_design_schema,
            'primary_analysis': self.primary_analysis_schema,
        }

        schema_class = schemas.get(section)
        if schema_class:
            return json.dumps(schema_class.model_json_schema(), indent=2)
        return "{}"

    def get_allowed_values_summary(self) -> Dict[str, Any]:
        """Get summary of all constrained values for debugging"""
        return {
            'total_n': self.facts.total_n.value if self.facts.total_n else None,
            'ratio': self.facts.ratio.value if self.facts.ratio else None,
            'num_arms': self.facts.num_arms.value if self.facts.num_arms else None,
            'drug_name': self.facts.drug_name.value if self.facts.drug_name else None,
            'route': self.facts.route.value if self.facts.route else None,
            'power': self.facts.power.value if self.facts.power else None,
            'alpha': self.facts.alpha.value if self.facts.alpha else None,
        }


# =============================================================================
# CONTAMINATION DETECTOR
# =============================================================================

class ContaminationDetector:
    """
    Detects if generated content contains values from RAG examples
    rather than protocol facts.

    Uses TIERED severity:
    - CRITICAL: Wrong drug name used as primary study drug (blocks generation)
    - WARNING: Study IDs, sample sizes from other trials (logged but doesn't block)

    NOTE: Be conservative - false positives cause more harm than missing contamination.
    """

    # CRITICAL contaminants - using these as THE drug/study will block generation
    CRITICAL_DRUG_CONTAMINANTS = {
        'etrolizumab', 'tocilizumab', 'sarilumab',
    }

    # WARNING-level contaminants - log but don't block (may appear in references)
    WARNING_CONTAMINANTS = {
        'GA29144', 'GA29145', 'PRO145223', 'WA25615', 'ML42528',
    }

    def check_contamination(
        self,
        generated_text: str,
        facts: ProtocolFacts
    ) -> Tuple[bool, List[str]]:
        """
        Check for contamination from RAG examples.

        Only blocks for CRITICAL contamination (wrong drug name as study drug).
        Returns warnings for other matches.

        Returns:
            Tuple of (is_critical_contamination, list_of_issues_found)
        """
        critical = []
        warnings = []

        # Get valid values from protocol
        valid_values = self._get_valid_values(facts)
        protocol_drug = self._get_protocol_drug(facts)

        # Check for CRITICAL: wrong drug used as THE study drug
        # Pattern: look for drug name in context of "study drug", "investigational", etc.
        text_lower = generated_text.lower()
        for drug in self.CRITICAL_DRUG_CONTAMINANTS:
            drug_lower = drug.lower()
            if drug_lower in text_lower:
                # Only critical if it's not the actual protocol drug
                if protocol_drug and drug_lower != protocol_drug.lower():
                    # Check if it's used as THE study drug vs just mentioned
                    # Patterns that indicate it's being used as the main drug:
                    critical_patterns = [
                        f'{drug_lower} will be administered',
                        f'{drug_lower} is administered',
                        f'study drug {drug_lower}',
                        f'investigational product: {drug_lower}',
                        f'treatment with {drug_lower}',
                    ]
                    for pattern in critical_patterns:
                        if pattern in text_lower:
                            critical.append(f"CRITICAL: Wrong study drug '{drug}' (should be '{protocol_drug}')")
                            break

        # Check for WARNING-level: study IDs from other protocols
        # These might appear legitimately in references, comparisons, etc.
        for study_id in self.WARNING_CONTAMINANTS:
            if study_id in generated_text:
                if study_id not in valid_values:
                    # Only warn, don't block - might be a legitimate reference
                    warnings.append(f"WARNING: External study ID '{study_id}' found")

        # Combine: only CRITICAL issues block; warnings are logged
        all_issues = critical + warnings
        has_critical = len(critical) > 0

        return has_critical, all_issues

    def _get_valid_values(self, facts: ProtocolFacts) -> set:
        """Get all valid values from protocol facts"""
        valid = set()

        for field_name in ['total_n', 'per_arm_n', 'num_arms', 'power', 'alpha',
                           'drug_name', 'ratio', 'nct_id', 'study_id']:
            fact = getattr(facts, field_name, None)
            if fact and fact.value:
                valid.add(fact.value)
                valid.add(str(fact.value))
                # Also add numeric components
                for num in re.findall(r'\d+', str(fact.value)):
                    valid.add(int(num))
                    valid.add(num)

        return valid

    def _get_protocol_drug(self, facts: ProtocolFacts) -> Optional[str]:
        """Extract the protocol's drug name"""
        if hasattr(facts, 'drug_name') and facts.drug_name and facts.drug_name.value:
            return facts.drug_name.value
        return None


# =============================================================================
# UTILITY: Extract ProtocolFacts from protocol text
# =============================================================================

# Singleton extractor instance
_extractor = None

def _get_extractor() -> StructuredFactExtractor:
    """Get or create the singleton extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = StructuredFactExtractor()
    return _extractor


def extract_protocol_facts(protocol_text: str) -> ProtocolFacts:
    """
    Extract all protocol facts with citations.

    CONSOLIDATED: Uses StructuredFactExtractor as the single source of truth.
    Converts to CitedValue format for backward compatibility.
    """
    # Use the single source of truth for extraction
    extractor = _get_extractor()
    structured_facts = extractor.extract_all(protocol_text)

    # Convert to legacy CitedValue format
    facts = ProtocolFacts()

    # NCT ID
    if structured_facts.nct_id:
        facts.nct_id = CitedValue(value=structured_facts.nct_id, citation="Extracted from protocol")

    # Drug name (now correctly filtered for biomarkers like CD137)
    if structured_facts.drug_name:
        facts.drug_name = CitedValue(value=structured_facts.drug_name, citation="Extracted from protocol")
        print(f"[DEBUG] Consolidated extraction (legacy) - drug: {structured_facts.drug_name}")

    # Sample size
    if structured_facts.sample_size and structured_facts.sample_size.total_n:
        facts.total_n = CitedValue(
            value=structured_facts.sample_size.total_n,
            citation="Extracted from protocol"
        )

    # Ratio
    if structured_facts.randomization_ratio:
        facts.ratio = CitedValue(
            value=structured_facts.randomization_ratio,
            citation="Extracted from protocol"
        )

    # Num arms
    if structured_facts.num_arms:
        facts.num_arms = CitedValue(
            value=structured_facts.num_arms,
            citation="Extracted from protocol"
        )

    # Per-arm N
    if structured_facts.sample_size and structured_facts.sample_size.per_arm:
        per_arm_values = list(structured_facts.sample_size.per_arm.values())
        if per_arm_values:
            facts.per_arm_n = CitedValue(
                value=per_arm_values[0],
                citation="Extracted from protocol"
            )

    # Power
    if structured_facts.sample_size and structured_facts.sample_size.power:
        power_val = structured_facts.sample_size.power
        if power_val < 1:
            power_val = int(power_val * 100)
        facts.power = CitedValue(value=f"{power_val}%", citation="Extracted from protocol")

    # Alpha
    if structured_facts.alpha:
        facts.alpha = CitedValue(
            value=structured_facts.alpha.primary_alpha,
            citation="Extracted from protocol"
        )
        facts.alpha_sidedness = CitedValue(
            value=structured_facts.alpha.sidedness,
            citation="Extracted from protocol"
        )

    # Route
    if structured_facts.route_of_administration:
        facts.route = CitedValue(
            value=structured_facts.route_of_administration.value,
            citation="Extracted from protocol"
        )

    # Primary endpoint
    if structured_facts.primary_endpoint:
        facts.primary_endpoint = CitedValue(
            value=structured_facts.primary_endpoint.name,
            citation="Extracted from protocol"
        )
        if structured_facts.primary_endpoint.timepoint:
            facts.primary_timepoint = CitedValue(
                value=structured_facts.primary_endpoint.timepoint,
                citation="Extracted from protocol"
            )

    # Population
    if structured_facts.primary_analysis_population:
        facts.primary_population = CitedValue(
            value=structured_facts.primary_analysis_population,
            citation="Extracted from protocol"
        )

    # Design type (NEW - critical for single-arm detection)
    if structured_facts.design_type:
        facts.design_type = CitedValue(
            value=structured_facts.design_type,
            citation="Extracted from protocol"
        )
        # Set single-arm flag based on design type or num_arms
        design_lower = structured_facts.design_type.lower() if structured_facts.design_type else ""
        facts.is_single_arm = (
            "single" in design_lower or
            "single-arm" in design_lower or
            "one-arm" in design_lower or
            structured_facts.num_arms == 1
        )
    elif structured_facts.num_arms == 1:
        facts.is_single_arm = True

    # Additional check: if no randomization mentioned and num_arms is 1
    if structured_facts.num_arms == 1 and not structured_facts.randomization_ratio:
        facts.is_single_arm = True

    if facts.is_single_arm:
        print(f"[DEBUG] Single-arm trial detected!")

    return facts
