"""SAP section templates and structure definitions."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class SAPSectionDef:
    """Definition of a SAP section."""
    key: str
    title: str
    description: str
    source_sections: list[str]  # Protocol sections to extract from
    required: bool = True


# SAP section definitions
SAP_SECTIONS = [
    SAPSectionDef(
        key="introduction",
        title="1. Introduction",
        description="Study identification, title, NCT ID, version, and document purpose",
        source_sections=["study_identification"],
        required=True,
    ),
    SAPSectionDef(
        key="objectives_endpoints",
        title="2. Study Objectives and Endpoints",
        description="Primary and secondary objectives with corresponding endpoints",
        source_sections=["objectives", "endpoints"],
        required=True,
    ),
    SAPSectionDef(
        key="study_design",
        title="3. Study Design Summary",
        description="Design overview, treatment arms, randomization, blinding",
        source_sections=["study_design", "treatments"],
        required=True,
    ),
    SAPSectionDef(
        key="analysis_populations",
        title="4. Analysis Populations",
        description="ITT, mITT, Per-Protocol, Safety population definitions",
        source_sections=["analysis_populations", "population"],
        required=True,
    ),
    SAPSectionDef(
        key="sample_size",
        title="5. Sample Size",
        description="Sample size justification, power calculations, assumptions",
        source_sections=["sample_size"],
        required=True,
    ),
    SAPSectionDef(
        key="statistical_methods",
        title="6. Statistical Methods",
        description="Primary and secondary analysis methods, missing data handling",
        source_sections=["statistical_methods"],
        required=True,
    ),
    SAPSectionDef(
        key="efficacy_analyses",
        title="7. Efficacy Analyses",
        description="Detailed efficacy endpoint analyses",
        source_sections=["endpoints", "statistical_methods"],
        required=True,
    ),
    SAPSectionDef(
        key="safety_analyses",
        title="8. Safety Analyses",
        description="AE/SAE summaries, laboratory parameters, safety assessments",
        source_sections=["safety", "schedule_of_assessments"],
        required=True,
    ),
]


SAP_TEMPLATE = """# Statistical Analysis Plan (Abbreviated)

## Study: {study_title}
## NCT ID: {nct_id}
## Version: 1.0
## Date: {date}

---

{sections}

---

## Document History

| Version | Date | Author | Description |
|---------|------|--------|-------------|
| 1.0 | {date} | Auto-generated | Initial abbreviated SAP |

---

*This is an abbreviated SAP generated from the study protocol. For complete statistical analysis details, refer to the full Statistical Analysis Plan.*
"""


SECTION_TEMPLATE = """
{title}

{content}
"""


# Prompts for LLM extraction
LLM_EXTRACTION_PROMPTS = {
    "objectives": """Extract the study objectives from the following protocol text.
Identify and list:
1. Primary objective(s)
2. Secondary objective(s)
3. Exploratory objectives (if any)

Format as a clear bulleted list.

Protocol text:
{text}""",

    "endpoints": """Extract all study endpoints from the following protocol text.
Identify and categorize:
1. Primary endpoint(s) - with measurement details
2. Secondary endpoint(s) - with measurement details
3. Exploratory endpoints (if any)

Include timing of assessments where mentioned.

Protocol text:
{text}""",

    "study_design": """Extract the study design information from the following protocol text.
Include:
1. Study type (e.g., randomized, double-blind, placebo-controlled)
2. Treatment arms/groups
3. Randomization ratio
4. Blinding details
5. Study duration
6. Key visits/phases

Protocol text:
{text}""",

    "sample_size": """Extract sample size and power calculation details from the following protocol text.
Include:
1. Target sample size (per arm and total)
2. Power (e.g., 80%, 90%)
3. Significance level (alpha)
4. Expected effect size or treatment difference
5. Key assumptions
6. Dropout rate assumptions (if mentioned)

Protocol text:
{text}""",

    "statistical_methods": """Extract statistical methods from the following protocol text.
Include:
1. Primary analysis method
2. Secondary analysis methods
3. Missing data handling approach
4. Multiplicity adjustments
5. Sensitivity analyses planned
6. Interim analyses (if any)

Protocol text:
{text}""",

    "analysis_populations": """Extract analysis population definitions from the following protocol text.
Include definitions for:
1. Intent-to-Treat (ITT) population
2. Modified ITT (mITT) if applicable
3. Per-Protocol (PP) population
4. Safety population
5. Any other analysis sets

Protocol text:
{text}""",

    "safety": """Extract safety analysis information from the following protocol text.
Include:
1. Adverse event collection and coding
2. Serious adverse event handling
3. Laboratory parameter analyses
4. Vital signs assessments
5. Safety stopping rules (if any)

Protocol text:
{text}""",
}
