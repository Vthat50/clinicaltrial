"""Section type definitions and pattern mappings for protocol parsing."""
from enum import Enum
from dataclasses import dataclass
import re


class SectionType(str, Enum):
    """Types of sections in a clinical trial protocol."""
    STUDY_IDENTIFICATION = "study_identification"
    OBJECTIVES = "objectives"
    STUDY_DESIGN = "study_design"
    ENDPOINTS = "endpoints"
    POPULATION = "population"
    TREATMENTS = "treatments"
    SAMPLE_SIZE = "sample_size"
    STATISTICAL_METHODS = "statistical_methods"
    ANALYSIS_POPULATIONS = "analysis_populations"
    SCHEDULE_OF_ASSESSMENTS = "schedule_of_assessments"
    SAFETY = "safety"
    EFFICACY_ANALYSES = "efficacy_analyses"
    SAFETY_ANALYSES = "safety_analyses"
    MISSING_DATA = "missing_data"
    INTERIM_ANALYSES = "interim_analyses"
    MULTIPLICITY = "multiplicity"
    SENSITIVITY_ANALYSES = "sensitivity_analyses"
    SUBGROUP_ANALYSES = "subgroup_analyses"
    UNKNOWN = "unknown"


@dataclass
class SectionPattern:
    """Pattern definition for identifying a section."""
    section_type: SectionType
    patterns: list[str]
    priority: int = 0  # Higher priority patterns match first


# Regex patterns to identify each section type
SECTION_PATTERNS = [
    SectionPattern(
        section_type=SectionType.STUDY_IDENTIFICATION,
        patterns=[
            r"(?i)^[\d\.]*\s*protocol\s+summary",
            r"(?i)^[\d\.]*\s*title\s+page",
            r"(?i)^[\d\.]*\s*study\s+identification",
            r"(?i)^[\d\.]*\s*protocol\s+synopsis",
            r"(?i)^[\d\.]*\s*synopsis",
        ],
        priority=10
    ),
    SectionPattern(
        section_type=SectionType.OBJECTIVES,
        patterns=[
            r"(?i)^[\d\.]*\s*study\s+objectives?",
            r"(?i)^[\d\.]*\s*objectives?\s*$",
            r"(?i)^[\d\.]*\s*primary\s+objective",
            r"(?i)^[\d\.]*\s*objectives?\s+and\s+endpoints?",
        ],
        priority=9
    ),
    SectionPattern(
        section_type=SectionType.ENDPOINTS,
        patterns=[
            r"(?i)^[\d\.]*\s*endpoints?",
            r"(?i)^[\d\.]*\s*primary\s+endpoint",
            r"(?i)^[\d\.]*\s*study\s+endpoints?",
            r"(?i)^[\d\.]*\s*efficacy\s+endpoints?",
            r"(?i)^[\d\.]*\s*outcome\s+measures?",
        ],
        priority=8
    ),
    SectionPattern(
        section_type=SectionType.STUDY_DESIGN,
        patterns=[
            r"(?i)^[\d\.]*\s*study\s+design",
            r"(?i)^[\d\.]*\s*overall\s+design",
            r"(?i)^[\d\.]*\s*trial\s+design",
            r"(?i)^[\d\.]*\s*design\s+and\s+methodology",
            r"(?i)^[\d\.]*\s*study\s+plan",
        ],
        priority=7
    ),
    SectionPattern(
        section_type=SectionType.POPULATION,
        patterns=[
            r"(?i)^[\d\.]*\s*study\s+population",
            r"(?i)^[\d\.]*\s*patient\s+selection",
            r"(?i)^[\d\.]*\s*eligibility\s+criteria",
            r"(?i)^[\d\.]*\s*inclusion\s+criteria",
            r"(?i)^[\d\.]*\s*subject\s+selection",
            r"(?i)^[\d\.]*\s*patient\s+population",
        ],
        priority=6
    ),
    SectionPattern(
        section_type=SectionType.TREATMENTS,
        patterns=[
            r"(?i)^[\d\.]*\s*study\s+treatment",
            r"(?i)^[\d\.]*\s*investigational\s+product",
            r"(?i)^[\d\.]*\s*treatment\s+arms?",
            r"(?i)^[\d\.]*\s*dosing\s+regimen",
            r"(?i)^[\d\.]*\s*drug\s+administration",
        ],
        priority=5
    ),
    SectionPattern(
        section_type=SectionType.SAMPLE_SIZE,
        patterns=[
            r"(?i)^[\d\.]*\s*sample\s+size",
            r"(?i)^[\d\.]*\s*statistical\s+sample\s+size",
            r"(?i)^[\d\.]*\s*power\s+calculation",
            r"(?i)^[\d\.]*\s*sample\s+size\s+determination",
            r"(?i)^[\d\.]*\s*number\s+of\s+(?:patients?|subjects?)",
        ],
        priority=4
    ),
    SectionPattern(
        section_type=SectionType.STATISTICAL_METHODS,
        patterns=[
            r"(?i)^[\d\.]*\s*statistical\s+(?:methods?|analysis|considerations?)",
            r"(?i)^[\d\.]*\s*data\s+analysis",
            r"(?i)^[\d\.]*\s*statistical\s+plan",
            r"(?i)^[\d\.]*\s*analysis\s+methods?",
            r"(?i)^[\d\.]*\s*statistical\s+methodology",
        ],
        priority=3
    ),
    SectionPattern(
        section_type=SectionType.ANALYSIS_POPULATIONS,
        patterns=[
            r"(?i)^[\d\.]*\s*analysis\s+populations?",
            r"(?i)^[\d\.]*\s*study\s+populations?\s+for\s+analysis",
            r"(?i)^[\d\.]*\s*intent.to.treat",
            r"(?i)^[\d\.]*\s*per.protocol\s+population",
            r"(?i)^[\d\.]*\s*evaluable\s+population",
        ],
        priority=2
    ),
    SectionPattern(
        section_type=SectionType.SCHEDULE_OF_ASSESSMENTS,
        patterns=[
            r"(?i)^[\d\.]*\s*schedule\s+of\s+(?:assessments?|events?|activities?)",
            r"(?i)^[\d\.]*\s*study\s+schedule",
            r"(?i)^[\d\.]*\s*visit\s+schedule",
            r"(?i)^[\d\.]*\s*study\s+procedures?",
        ],
        priority=1
    ),
    SectionPattern(
        section_type=SectionType.SAFETY,
        patterns=[
            r"(?i)^[\d\.]*\s*safety\s+(?:assessments?|evaluations?|monitoring)",
            r"(?i)^[\d\.]*\s*adverse\s+events?",
            r"(?i)^[\d\.]*\s*safety\s+parameters?",
        ],
        priority=1
    ),
]


def get_compiled_patterns() -> list[tuple[SectionType, re.Pattern, int]]:
    """Get compiled regex patterns sorted by priority."""
    compiled = []
    for sp in SECTION_PATTERNS:
        for pattern in sp.patterns:
            compiled.append((
                sp.section_type,
                re.compile(pattern, re.MULTILINE),
                sp.priority
            ))
    return sorted(compiled, key=lambda x: -x[2])


COMPILED_PATTERNS = get_compiled_patterns()
