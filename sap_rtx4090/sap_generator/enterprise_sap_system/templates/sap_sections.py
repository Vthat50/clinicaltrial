#!/usr/bin/env python3
"""
Enterprise SAP Generation System - SAP Section Templates
==========================================================
TIER 6: Full SAP Document Generation

TransCelerate-aligned SAP section templates with
placeholder handling and formatting.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Use relative imports for consistent module resolution
try:
    from ..core.schemas import ParsedProtocol, Estimand, QualityReport
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from core.schemas import ParsedProtocol, Estimand, QualityReport


@dataclass
class SectionTemplate:
    """Template for a SAP section"""
    id: str
    title: str
    subsections: List[str]
    template_content: str
    required: bool = True


class SAPTemplateManager:
    """
    Manager for SAP section templates.
    Provides TransCelerate-aligned structure and formatting.
    """

    # Section templates aligned with TransCelerate template
    TEMPLATES = {
        "1_introduction": SectionTemplate(
            id="1_introduction",
            title="1. INTRODUCTION",
            subsections=[
                "1.1 Purpose of the Statistical Analysis Plan",
                "1.2 Scope",
                "1.3 Responsibilities",
                "1.4 Timing of SAP and Amendments"
            ],
            template_content="""## 1. INTRODUCTION

### 1.1 Purpose of the Statistical Analysis Plan

This Statistical Analysis Plan (SAP) describes the planned statistical analyses for study {nct_id}: "{study_title}".

The SAP provides sufficient detail to enable replication of all planned analyses and serves as the primary guidance for statistical programming. This document supplements the protocol and takes precedence over the protocol for statistical analysis specifications.

This SAP is aligned with:
- ICH E9 Statistical Principles for Clinical Trials
- ICH E9(R1) Addendum on Estimands and Sensitivity Analysis
- ICH E6(R2) Good Clinical Practice
- TransCelerate Common Protocol Template Statistical Sections

### 1.2 Scope

This document specifies:
- Analysis populations and their definitions
- Estimands for all trial objectives per ICH E9(R1)
- Statistical methods for primary, secondary, and exploratory analyses
- Handling of missing data and sensitivity analyses
- Multiplicity adjustments
- Tables, listings, and figures (TLF) specifications

This SAP does not include:
- Database specifications (covered in separate Data Management Plan)
- SDTM mapping specifications (covered in SDTM Specifications)
- ADaM specifications beyond analysis requirements (covered in ADaM Specifications)

### 1.3 Responsibilities

| Role | Responsibility |
|------|----------------|
| Lead Biostatistician | SAP development, statistical oversight, final review |
| Statistical Programmer | SAP implementation, programming validation |
| Medical Monitor | Clinical interpretation, safety review |
| Data Manager | Data review, database lock timing |
| Medical Writer | CSR statistical sections alignment |

### 1.4 Timing of SAP and Amendments

The SAP was finalized prior to database lock for the primary analysis. Any amendments after database lock will be documented with rationale and timing relative to unblinding.

| Version | Date | Description |
|---------|------|-------------|
| 1.0 | {sap_date} | Initial version |
"""
        ),

        "2_objectives_estimands": SectionTemplate(
            id="2_objectives_estimands",
            title="2. STUDY OBJECTIVES AND ESTIMANDS",
            subsections=[
                "2.1 Primary Objective and Estimand",
                "2.2 Secondary Objectives and Estimands",
                "2.3 Exploratory Objectives",
                "2.4 Safety Objectives"
            ],
            template_content="""## 2. STUDY OBJECTIVES AND ESTIMANDS

This section defines the trial objectives aligned with the ICH E9(R1) estimand framework. Each estimand is specified by its five key attributes: treatment, population, variable, intercurrent event handling, and summary measure.

### 2.1 Primary Objective and Estimand

**Primary Objective:** {primary_objective}

**Primary Estimand:**

| Attribute | Specification |
|-----------|---------------|
| **Treatment** | {primary_treatment} |
| **Population** | {primary_population} |
| **Variable** | {primary_variable} |
| **Summary Measure** | {primary_summary_measure} |

**Intercurrent Events and Strategies:**

| Intercurrent Event | Strategy | Rationale |
|--------------------|----------|-----------|
{primary_ice_table}

**Primary Analysis Method:** {primary_analysis_method}

### 2.2 Secondary Objectives and Estimands

{secondary_estimands_content}

### 2.3 Exploratory Objectives

{exploratory_objectives}

### 2.4 Safety Objectives

The safety objective is to characterize the safety profile of the study treatment, including:
- Incidence, severity, and causality of adverse events
- Incidence of serious adverse events
- Clinically significant laboratory abnormalities
- Vital sign abnormalities
- Treatment discontinuations due to adverse events
"""
        ),

        "3_study_design": SectionTemplate(
            id="3_study_design",
            title="3. STUDY DESIGN",
            subsections=[
                "3.1 Overview of Study Design",
                "3.2 Randomization and Stratification",
                "3.3 Blinding",
                "3.4 Study Schema"
            ],
            template_content="""## 3. STUDY DESIGN

### 3.1 Overview of Study Design

This is a {phase} {design_type} study in patients with {indication}.

**Key Design Features:**
- Phase: {phase}
- Design: {design_type}
- Blinding: {blinding}
- Randomization Ratio: {randomization_ratio}
- Treatment Duration: As specified in protocol
- Follow-up: As specified in protocol

### 3.2 Randomization and Stratification

Subjects will be randomized in a {randomization_ratio} ratio to the treatment arms using an interactive response technology (IRT) system.

**Stratification Factors:**
{stratification_factors}

The randomization schedule will be generated by an independent statistician using a validated randomization program with a permuted block design. Block sizes will not be disclosed to maintain blinding.

### 3.3 Blinding

This study is {blinding}.

{blinding_details}

### 3.4 Study Schema

{study_schema}

**Treatment Arms:**
{treatment_arms}
"""
        ),

        "4_analysis_populations": SectionTemplate(
            id="4_analysis_populations",
            title="4. ANALYSIS POPULATIONS",
            subsections=[
                "4.1 Intent-to-Treat (ITT) Population",
                "4.2 Modified Intent-to-Treat (mITT) Population",
                "4.3 Per-Protocol (PP) Population",
                "4.4 Safety Population",
                "4.5 PK Population (if applicable)"
            ],
            template_content="""## 4. ANALYSIS POPULATIONS

### 4.1 Intent-to-Treat (ITT) Population

**Definition:** All randomized subjects, analyzed according to randomized treatment assignment regardless of actual treatment received.

**Use:** Primary efficacy analysis

**ADSL Flag:** ITTFL = 'Y'

### 4.2 Modified Intent-to-Treat (mITT) Population

**Definition:** {mitt_definition}

**Use:** {mitt_use}

**ADSL Flag:** MITTFL = 'Y'

### 4.3 Per-Protocol (PP) Population

**Definition:** All ITT subjects who:
- Received at least {min_treatment_exposure} of planned treatment
- Had no major protocol deviations affecting endpoint assessment
- Had at least one post-baseline efficacy assessment

**Major Protocol Deviations Excluding from PP:**
- Violation of key eligibility criteria
- Use of prohibited concomitant medications
- Treatment exposure less than minimum required
- Missing primary endpoint assessment not due to documented progression/death

**Use:** Supportive efficacy analysis

**ADSL Flag:** PPROTFL = 'Y'

### 4.4 Safety Population

**Definition:** All subjects who received at least one dose (complete or partial) of study treatment, analyzed according to treatment actually received.

**Use:** All safety analyses

**ADSL Flag:** SAFFL = 'Y'

### 4.5 Population Summary

| Analysis | Primary Population | Sensitivity Population |
|----------|-------------------|----------------------|
| Primary Efficacy | ITT | PP |
| Secondary Efficacy | ITT | mITT |
| Safety | Safety | Safety |

### 4.6 Handling of Population Overlaps

Subjects will be assigned to populations based on the definitions above. A subject may be included in multiple populations (e.g., both ITT and Safety). Subject disposition by population will be summarized.
"""
        ),

        "5_statistical_methods": SectionTemplate(
            id="5_statistical_methods",
            title="5. STATISTICAL METHODS",
            subsections=[
                "5.1 General Considerations",
                "5.2 Primary Endpoint Analysis",
                "5.3 Secondary Endpoint Analyses",
                "5.4 Exploratory Analyses",
                "5.5 Safety Analyses",
                "5.6 Sensitivity Analyses",
                "5.7 Subgroup Analyses",
                "5.8 Multiplicity Adjustments"
            ],
            template_content="""## 5. STATISTICAL METHODS

### 5.1 General Considerations

All statistical analyses will be performed using SAS version 9.4 or later (SAS Institute, Cary, NC). All statistical tests will be two-sided at a significance level of {alpha} unless otherwise specified.

**General Analysis Principles:**
- Continuous variables: n, mean, SD, median, Q1, Q3, min, max
- Categorical variables: frequency counts and percentages
- Time-to-event: Kaplan-Meier estimates with 95% CI
- Confidence intervals: Two-sided {ci_level}% confidence intervals

### 5.2 Primary Endpoint Analysis

**Endpoint:** {primary_endpoint}

**Analysis Population:** Intent-to-Treat (ITT)

**Statistical Method:**
{primary_method_details}

**Hypothesis:**
- H₀: {null_hypothesis}
- H₁: {alternative_hypothesis}

**Test Statistic:** {test_statistic}

**Decision Rule:** The null hypothesis will be rejected if the two-sided p-value is < {alpha}.

**Handling of Ties:** {tie_handling}

**Covariate Adjustment:** {covariate_adjustment}

### 5.3 Secondary Endpoint Analyses

{secondary_analyses}

### 5.4 Exploratory Analyses

{exploratory_analyses}

### 5.5 Safety Analyses

**Adverse Events:**
- Treatment-emergent adverse events (TEAEs) by System Organ Class and Preferred Term
- TEAEs by severity grade
- TEAEs by relationship to study treatment
- Serious adverse events (SAEs)
- Adverse events leading to treatment discontinuation
- Deaths

**Laboratory Parameters:**
- Shift tables from baseline to worst post-baseline grade
- Clinically significant abnormalities
- Change from baseline summary statistics

**Vital Signs:**
- Summary statistics by visit
- Change from baseline

### 5.6 Sensitivity Analyses

{sensitivity_analyses}

### 5.7 Subgroup Analyses

Subgroup analyses will be performed for the primary endpoint for the following pre-specified subgroups:
{subgroup_list}

Subgroup analyses will be presented using forest plots. These analyses are exploratory and not adjusted for multiplicity.

### 5.8 Multiplicity Adjustments

{multiplicity_adjustment}
"""
        ),

        "6_sample_size": SectionTemplate(
            id="6_sample_size",
            title="6. SAMPLE SIZE AND POWER",
            subsections=[
                "6.1 Sample Size Calculation",
                "6.2 Assumptions",
                "6.3 Power Calculation",
                "6.4 Sample Size Re-estimation (if applicable)"
            ],
            template_content="""## 6. SAMPLE SIZE AND POWER

### 6.1 Sample Size Calculation

A total of {total_n} subjects ({per_arm_n}) will be enrolled in this study.

**Primary Endpoint:** {primary_endpoint}
**Analysis Method:** {analysis_method}

### 6.2 Assumptions

| Parameter | Assumed Value | Source/Rationale |
|-----------|---------------|------------------|
{assumptions_table}

### 6.3 Power Calculation

{power_calculation}

**Software:** Sample size calculation was performed using {software}.

### 6.4 Sample Size Re-estimation

{ssr_content}
"""
        ),

        "7_data_handling": SectionTemplate(
            id="7_data_handling",
            title="7. DATA HANDLING CONVENTIONS",
            subsections=[
                "7.1 Visit Windows",
                "7.2 Baseline Definition",
                "7.3 Date Imputations",
                "7.4 Handling of Missing Data",
                "7.5 Derived Variables",
                "7.6 Multiple Assessments"
            ],
            template_content="""## 7. DATA HANDLING CONVENTIONS

### 7.1 Visit Windows

Analysis visits will be assigned based on nominal visit windows. If multiple assessments fall within a single window, the assessment closest to the target day will be used.

| Analysis Visit | Target Day | Window (Days) |
|----------------|------------|---------------|
| Baseline | Day 1 | ≤1 |
{visit_windows}

### 7.2 Baseline Definition

Baseline is defined as the last non-missing assessment prior to the first dose of study treatment.

For subjects who do not receive study treatment, baseline is the last assessment prior to randomization.

### 7.3 Date Imputations

**Partial Date Imputation Rules:**

| Missing Component | Imputation Rule |
|-------------------|-----------------|
| Day only | First of month (for start dates), Last of month (for end dates) |
| Day and month | January 1 (start), December 31 (end) |
| Complete date missing | Not imputed; flagged in listings |

### 7.4 Handling of Missing Data

**Primary Analysis:** {missing_data_primary}

**Sensitivity Analyses for Missing Data:**
- Complete case analysis
- Multiple imputation
- Pattern mixture models (if applicable)
- Tipping point analysis

### 7.5 Derived Variables

{derived_variables}

### 7.6 Multiple Assessments

If multiple assessments are performed at the same timepoint:
- Laboratory: Use the first non-missing value
- Efficacy: As specified per endpoint
- Safety: All values will be included in listings
"""
        ),

        "8_cdisc_alignment": SectionTemplate(
            id="8_cdisc_alignment",
            title="8. CDISC ADaM ALIGNMENT",
            subsections=[
                "8.1 Overview",
                "8.2 Key Analysis Datasets",
                "8.3 Traceability"
            ],
            template_content="""## 8. CDISC ADaM ALIGNMENT

{cdisc_content}
"""
        ),

        "9_tlf_specifications": SectionTemplate(
            id="9_tlf_specifications",
            title="9. TABLES, LISTINGS, AND FIGURES",
            subsections=[
                "9.1 TLF Overview",
                "9.2 Table Numbering Convention",
                "9.3 Key Efficacy Tables",
                "9.4 Key Safety Tables",
                "9.5 Key Figures",
                "9.6 Listings"
            ],
            template_content="""## 9. TABLES, LISTINGS, AND FIGURES (TLFs)

### 9.1 TLF Overview

All TLFs will be produced in accordance with the specifications in this section. Mock shells are provided in Appendix A.

**General Formatting:**
- Page size: Letter (8.5" x 11")
- Orientation: Portrait for tables, Landscape for wide tables
- Font: Courier New 8pt for tables, Arial for figures
- Page numbering: Page X of Y per output

### 9.2 Table Numbering Convention

| Series | Content |
|--------|---------|
| 14.1.x | Demographics and Baseline Characteristics |
| 14.2.x | Efficacy Analyses |
| 14.3.x | Safety Analyses |
| 16.1.x | Subject Data Listings |
| 16.2.x | Individual Patient Data |

### 9.3 Key Efficacy Tables

{efficacy_tables}

### 9.4 Key Safety Tables

| Table | Title | Population |
|-------|-------|------------|
| 14.3.1 | Overall Summary of Treatment-Emergent Adverse Events | Safety |
| 14.3.2 | TEAEs by System Organ Class and Preferred Term | Safety |
| 14.3.3 | TEAEs by Maximum Severity | Safety |
| 14.3.4 | TEAEs by Relationship to Study Treatment | Safety |
| 14.3.5 | Serious Adverse Events | Safety |
| 14.3.6 | Adverse Events Leading to Treatment Discontinuation | Safety |
| 14.3.7 | Deaths | Safety |
| 14.3.8 | Laboratory Shift Tables | Safety |

### 9.5 Key Figures

{figures}

### 9.6 Listings

| Listing | Title | Population |
|---------|-------|------------|
| 16.1.1 | Subject Disposition | All Subjects |
| 16.1.2 | Protocol Deviations | All Subjects |
| 16.2.1 | Adverse Events | Safety |
| 16.2.2 | Serious Adverse Events | Safety |
| 16.2.3 | Laboratory Abnormalities | Safety |
"""
        ),
    }

    def __init__(self):
        """Initialize template manager"""
        pass

    def get_template(self, section_id: str) -> Optional[SectionTemplate]:
        """Get a specific template by ID"""
        return self.TEMPLATES.get(section_id)

    def get_all_templates(self) -> Dict[str, SectionTemplate]:
        """Get all templates"""
        return self.TEMPLATES

    def render_template(
        self,
        section_id: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Render a template with context.

        Args:
            section_id: Template ID
            context: Variables to substitute

        Returns:
            Rendered content
        """
        template = self.get_template(section_id)
        if not template:
            return f"## {section_id}\n\n[Section content to be generated]"

        try:
            # Format with context, using empty string for missing keys
            content = template.template_content.format_map(
                {k: v if v else "[TBD]" for k, v in context.items()}
            )
            return content
        except KeyError as e:
            # Return template with placeholders for missing keys
            return template.template_content

    def generate_full_sap(
        self,
        sections: Dict[str, str],
        protocol: ParsedProtocol
    ) -> str:
        """
        Generate complete SAP document from sections.

        Args:
            sections: Dictionary of section contents
            protocol: Parsed protocol

        Returns:
            Complete SAP document
        """
        # Header
        header = f"""# STATISTICAL ANALYSIS PLAN

---

**Study Identifier:** {protocol.nct_id}

**Protocol Number:** {protocol.protocol_number or 'TBD'}

**Study Title:** {protocol.study_title or 'TBD'}

**Sponsor:** {protocol.sponsor or 'TBD'}

**SAP Version:** 1.0

**SAP Date:** {datetime.now().strftime('%d-%b-%Y')}

---

## TABLE OF CONTENTS

1. Introduction
2. Study Objectives and Estimands
3. Study Design
4. Analysis Populations
5. Statistical Methods
6. Sample Size and Power
7. Data Handling Conventions
8. CDISC ADaM Alignment
9. Tables, Listings, and Figures

---

"""
        # Body - ordered sections
        body_parts = []
        for section_id in sorted(self.TEMPLATES.keys()):
            if section_id in sections:
                body_parts.append(sections[section_id])
            else:
                template = self.get_template(section_id)
                if template:
                    body_parts.append(f"## {template.title}\n\n[Content to be added]")

        # Footer
        footer = """
---

## APPENDICES

### Appendix A: Mock TLF Shells

[Mock shells to be attached]

### Appendix B: Derivation Specifications

[Derivation specifications to be attached]

### Appendix C: List of Abbreviations

| Abbreviation | Definition |
|--------------|------------|
| ADaM | Analysis Data Model |
| AE | Adverse Event |
| CI | Confidence Interval |
| CDISC | Clinical Data Interchange Standards Consortium |
| HR | Hazard Ratio |
| ICH | International Council for Harmonisation |
| ITT | Intent-to-Treat |
| KM | Kaplan-Meier |
| ORR | Objective Response Rate |
| OS | Overall Survival |
| PFS | Progression-Free Survival |
| PP | Per-Protocol |
| SAE | Serious Adverse Event |
| SAP | Statistical Analysis Plan |
| SDTM | Study Data Tabulation Model |
| TEAE | Treatment-Emergent Adverse Event |
| TLF | Tables, Listings, and Figures |

---

## DOCUMENT HISTORY

| Version | Date | Author | Description |
|---------|------|--------|-------------|
| 1.0 | {date} | AI-Generated | Initial SAP version |

---

*This Statistical Analysis Plan was generated using the Enterprise SAP Generation System.*

""".format(date=datetime.now().strftime('%d-%b-%Y'))

        return header + "\n\n".join(body_parts) + footer


# Factory function
def create_template_manager() -> SAPTemplateManager:
    """Create a template manager instance"""
    return SAPTemplateManager()
