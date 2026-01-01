#!/usr/bin/env python3
"""
LLM-Based Section Generator for SAP
====================================

This module ACTUALLY uses LLM to generate SAP sections.
No templates. No hardcoded content. Real LLM synthesis.

For each section:
1. Retrieve relevant examples from RAG
2. Build a prompt with facts + examples
3. Call LLM to generate section content
4. Validate and return

This replaces the fake "RAG" generators that were just templates.
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# Import the tiered LLM client
from .tiered_llm import get_tiered_client, TieredLLMClient, LLMResponse


@dataclass
class GeneratedSection:
    """Result from LLM section generation"""
    content: str
    section_name: str
    llm_source: str  # claude, openai, groq
    rag_examples_used: List[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


class LLMSectionGenerator:
    """
    Generates SAP sections using actual LLM calls.

    Uses RAG examples as few-shot examples for the LLM,
    NOT for regex pattern matching.
    """

    def __init__(self, rag_adapter=None):
        """
        Initialize with optional RAG adapter for retrieving examples.

        Args:
            rag_adapter: HybridRAGAdapter instance for retrieving similar SAP sections
        """
        self.rag_adapter = rag_adapter
        self.llm_client: TieredLLMClient = get_tiered_client()

    def _retrieve_examples(
        self,
        section_type: str,
        facts: Dict[str, Any],
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """Retrieve RAG examples for a section type."""
        if not self.rag_adapter:
            print(f"[LLM Generator] No RAG adapter - generating {section_type} without examples")
            return []

        try:
            examples = self.rag_adapter.retrieve_for_section(
                section_type=section_type,
                protocol_data=facts,
                n_results=n_results
            )
            if examples:
                print(f"[LLM Generator] Retrieved {len(examples)} examples for {section_type}")
            return examples
        except Exception as e:
            print(f"[LLM Generator] Error retrieving examples: {e}")
            return []

    def _format_examples_for_prompt(self, examples: List[Dict[str, Any]], max_chars: int = 4000) -> str:
        """Format RAG examples for inclusion in LLM prompt."""
        if not examples:
            return "No similar examples available."

        formatted = []
        total_chars = 0

        for i, ex in enumerate(examples, 1):
            content = ex.get('content', '')
            nct_id = ex.get('nct_id', 'Unknown')

            # Truncate if needed
            if len(content) > 1500:
                content = content[:1500] + "..."

            if total_chars + len(content) > max_chars:
                break

            formatted.append(f"=== Example {i} (from {nct_id}) ===\n{content}")
            total_chars += len(content)

        return "\n\n".join(formatted)

    def _format_facts_for_prompt(self, facts: Dict[str, Any]) -> str:
        """Format protocol facts for LLM prompt."""
        important_facts = [
            ('drug_name', 'Study Drug'),
            ('comparator', 'Comparator'),
            ('phase', 'Phase'),
            ('design_type', 'Study Design'),
            ('randomization_ratio', 'Randomization Ratio'),
            ('sample_size', 'Sample Size'),
            ('primary_endpoint', 'Primary Endpoint'),
            ('primary_timepoint', 'Primary Timepoint'),
            ('secondary_endpoints', 'Secondary Endpoints'),
            ('therapeutic_area', 'Therapeutic Area'),
            ('indication', 'Indication'),
            ('stratification_factors', 'Stratification Factors'),
            ('nct_id', 'NCT ID'),
            ('sponsor', 'Sponsor'),
            ('is_single_arm', 'Single-Arm Study'),
            ('num_arms', 'Number of Arms'),
            ('arms', 'Treatment Arms'),
        ]

        lines = []
        for key, label in important_facts:
            value = facts.get(key)
            if value is not None and value != '' and value != []:
                if isinstance(value, list):
                    value = ', '.join(str(v) for v in value)
                lines.append(f"- {label}: {value}")

        return "\n".join(lines) if lines else "No protocol facts available."

    def generate_introduction(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Introduction section using LLM."""
        examples = self._retrieve_examples('introduction', facts, n_results=2)

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write a professional Introduction section for an SAP. Include:
1. Study identification (NCT ID, protocol number, title)
2. Purpose of the SAP
3. Scope of analyses covered
4. Regulatory alignment (mention ICH E9, ICH E9(R1))
5. Roles and responsibilities overview

Use the protocol facts provided. Write in formal scientific language.
Do NOT use placeholder text like [X] or [INSERT]. Use actual values from the facts.
If a value is missing, make a reasonable assumption or omit that detail."""

        user_prompt = f"""Write the Introduction section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

Write the Introduction section now. Start with "## 1. INTRODUCTION" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000
        )

        return GeneratedSection(
            content=response.content if response.success else self._fallback_introduction(facts),
            section_name="introduction",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_objectives(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Objectives/Estimands section using LLM."""
        examples = self._retrieve_examples('endpoints', facts, n_results=3)

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Objectives and Estimands section following ICH E9(R1) guidelines.

For each objective, define the estimand with these 5 attributes:
1. Treatment: What treatments are being compared
2. Population: Target population for the analysis
3. Variable: The endpoint/outcome being measured
4. Intercurrent events: How to handle discontinuation, rescue therapy, death
5. Summary measure: How treatment effect is quantified (HR, OR, mean difference, etc.)

Use the actual comparator from the protocol - do NOT default to "placebo" unless it's actually a placebo-controlled study.
Write in formal scientific language with proper statistical terminology."""

        user_prompt = f"""Write the Objectives and Estimands section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

IMPORTANT:
- Use the actual comparator drug name, not "placebo" unless it IS a placebo study
- Follow ICH E9(R1) estimand framework exactly
- Include primary AND secondary objectives

Write the section now. Start with "## 2. OBJECTIVES AND ESTIMANDS" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2500
        )

        return GeneratedSection(
            content=response.content if response.success else self._fallback_objectives(facts),
            section_name="objectives",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_study_design(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Study Design section using LLM."""
        examples = self._retrieve_examples('study_design', facts, n_results=2)

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Study Design section including:
1. Study design type (randomized, open-label, double-blind, etc.)
2. Treatment arms and descriptions
3. Randomization scheme and ratio
4. Stratification factors
5. Blinding procedures (if applicable)
6. Study schema or flowchart description

Use the actual values from the protocol. Be specific about treatment arms."""

        user_prompt = f"""Write the Study Design section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

Write the section now. Start with "## 3. STUDY DESIGN" as the header.
Include a table showing treatment arms if multiple arms exist."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000
        )

        return GeneratedSection(
            content=response.content if response.success else self._fallback_study_design(facts),
            section_name="study_design",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_sample_size(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Sample Size section using LLM."""
        examples = self._retrieve_examples('methods', facts, n_results=3)

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Sample Size and Power section including:
1. Total sample size and per-arm breakdown
2. Primary endpoint for power calculation
3. Key assumptions (effect size, control rate, standard deviation)
4. Type I error (alpha) and power (1-beta)
5. Dropout/attrition rate adjustment
6. Justification and references for assumptions

Use actual values from the protocol. Show the calculation logic.
If sample size is provided, explain the justification.
If not provided, note that it should be calculated based on the primary endpoint."""

        user_prompt = f"""Write the Sample Size and Power section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs (showing how power calculations are justified):
{self._format_examples_for_prompt(examples)}

Write the section now. Start with "## 6. SAMPLE SIZE AND POWER" as the header.
Include an assumptions table."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000
        )

        return GeneratedSection(
            content=response.content if response.success else self._fallback_sample_size(facts),
            section_name="sample_size",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_missing_data(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Missing Data section using LLM."""
        examples = self._retrieve_examples('methods', facts, n_results=2)

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Missing Data section including:
1. Missing data assumptions (MCAR, MAR, MNAR)
2. Primary analysis approach for handling missing data
3. Imputation methods if applicable (MI, LOCF, BOCF, MMRM)
4. Sensitivity analyses (tipping point, worst-case, best-case)
5. Missing data reporting requirements

Base the approach on the therapeutic area and endpoint type.
For efficacy trials: typically use MI or MMRM
For safety: typically use as-observed data"""

        user_prompt = f"""Write the Missing Data section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

Write the section now. Start with "## 9. MISSING DATA" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1500
        )

        return GeneratedSection(
            content=response.content if response.success else self._fallback_missing_data(facts),
            section_name="missing_data",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_methods(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Statistical Methods section using LLM with RAG examples."""
        examples = self._retrieve_examples('methods', facts, n_results=3)

        # Determine endpoint type for method selection
        primary_endpoint = str(facts.get('primary_endpoint', '')).lower()
        if any(x in primary_endpoint for x in ['survival', 'pfs', 'os', 'time to', 'tte']):
            endpoint_type = "time-to-event"
        elif any(x in primary_endpoint for x in ['response', 'rate', 'proportion', 'remission']):
            endpoint_type = "binary"
        else:
            endpoint_type = "continuous"

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Statistical Methods section including:
1. General statistical principles (significance level, confidence intervals)
2. Primary endpoint analysis method (appropriate for endpoint type)
3. Secondary endpoint analyses
4. Sensitivity analyses
5. Subgroup analyses
6. Multiplicity adjustment strategy

Choose methods appropriate for the endpoint type:
- Time-to-event: Kaplan-Meier, log-rank test, Cox regression
- Binary: CMH test, logistic regression, Fisher's exact
- Continuous: ANCOVA, MMRM, t-test

For oncology/immunotherapy with delayed treatment effects, consider:
- Fleming-Harrington weighted log-rank test
- Restricted mean survival time (RMST)

Use the actual comparator drug name, not "placebo" unless it IS placebo.
Write specific model specifications with covariates."""

        user_prompt = f"""Write the Statistical Methods section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

ENDPOINT TYPE DETECTED: {endpoint_type}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

IMPORTANT:
- Use the actual comparator (not "placebo" unless it really is)
- Be specific about model covariates and stratification
- Include the appropriate test for the endpoint type

Write the section now. Start with "## 7. STATISTICAL METHODS" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=3000
        )

        return GeneratedSection(
            content=response.content if response.success else self._fallback_methods(facts),
            section_name="methods",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_endpoints(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Endpoints section using LLM with RAG examples."""
        examples = self._retrieve_examples('endpoints', facts, n_results=3)

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Endpoints section including:
1. Primary endpoint definition and assessment timepoint
2. Secondary endpoints with definitions
3. Exploratory endpoints
4. Endpoint derivation rules
5. For time-to-event endpoints: censoring rules

Be specific about how each endpoint is measured and derived.
Use the actual values from the protocol."""

        user_prompt = f"""Write the Endpoints section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

Write the section now. Start with "## 5. ENDPOINTS" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000
        )

        return GeneratedSection(
            content=response.content if response.success else self._fallback_endpoints(facts),
            section_name="endpoints",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    def generate_stratification(self, facts: Dict[str, Any]) -> GeneratedSection:
        """Generate Stratification section using LLM with RAG examples."""
        examples = self._retrieve_examples('stratification', facts, n_results=2)

        # Check if single-arm study
        is_single_arm = facts.get('is_single_arm', False)
        num_arms = facts.get('num_arms', 2)

        if is_single_arm or num_arms == 1:
            return GeneratedSection(
                content="""## STRATIFICATION

### Stratification Factors

This is a single-arm study without randomization. Therefore, no stratification factors are applicable for randomization.

For analysis purposes, subgroup analyses may be performed by:
- Baseline disease characteristics
- Prior treatment history
- Geographic region
- Demographic factors

These subgroups will be used for descriptive analyses only.""",
                section_name="stratification",
                llm_source="rules",
                rag_examples_used=[],
                success=True
            )

        system_prompt = """You are a biostatistician writing a Statistical Analysis Plan (SAP).
Write the Stratification section including:
1. List of stratification factors used for randomization
2. Levels within each factor
3. How stratification will be incorporated in analysis
4. Handling of pooling for small strata

Use the actual stratification factors from the protocol."""

        user_prompt = f"""Write the Stratification section for this SAP.

PROTOCOL FACTS:
{self._format_facts_for_prompt(facts)}

EXAMPLES FROM SIMILAR SAPs:
{self._format_examples_for_prompt(examples)}

Write the section now. Start with "## STRATIFICATION" as the header."""

        response = self.llm_client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1500
        )

        return GeneratedSection(
            content=response.content if response.success else self._fallback_stratification(facts),
            section_name="stratification",
            llm_source=response.source,
            rag_examples_used=[ex.get('nct_id', '') for ex in examples],
            success=response.success,
            error=response.error
        )

    # =========================================================================
    # FALLBACK METHODS (when LLM fails)
    # =========================================================================

    def _fallback_introduction(self, facts: Dict[str, Any]) -> str:
        """Minimal fallback when LLM fails for introduction."""
        nct = facts.get('nct_id', 'NCT########')
        drug = facts.get('drug_name', 'study drug')
        return f"""## 1. INTRODUCTION

### 1.1 Study Identification

This Statistical Analysis Plan (SAP) describes the planned statistical analyses for study {nct}.

### 1.2 Purpose

This SAP provides detailed specifications for the statistical analyses of efficacy and safety data for {drug}.

### 1.3 Scope

This document covers all planned analyses for the primary, secondary, and exploratory endpoints.

### 1.4 Regulatory Alignment

All analyses will be conducted in accordance with ICH E9 and ICH E9(R1) guidelines.

[Note: LLM generation failed - this is a minimal fallback. Please review and enhance.]"""

    def _fallback_objectives(self, facts: Dict[str, Any]) -> str:
        """Minimal fallback when LLM fails for objectives."""
        drug = facts.get('drug_name', 'study drug')
        comparator = facts.get('comparator', 'control')
        endpoint = facts.get('primary_endpoint', 'the primary endpoint')
        return f"""## 2. OBJECTIVES AND ESTIMANDS

### 2.1 Primary Objective

To evaluate the efficacy of {drug} compared to {comparator} as measured by {endpoint}.

### 2.2 Primary Estimand (ICH E9(R1))

| Attribute | Specification |
|-----------|---------------|
| Treatment | {drug} vs {comparator} |
| Population | All randomized patients |
| Variable | {endpoint} |
| Intercurrent Events | Treatment policy strategy |
| Summary Measure | To be specified based on endpoint type |

[Note: LLM generation failed - this is a minimal fallback. Please review and enhance.]"""

    def _fallback_study_design(self, facts: Dict[str, Any]) -> str:
        """Minimal fallback when LLM fails for study design."""
        design = facts.get('design_type', 'randomized study')
        ratio = facts.get('randomization_ratio', '1:1')
        return f"""## 3. STUDY DESIGN

### 3.1 Overall Design

This is a {design}.

### 3.2 Randomization

Patients will be randomized in a {ratio} ratio.

[Note: LLM generation failed - this is a minimal fallback. Please review and enhance.]"""

    def _fallback_sample_size(self, facts: Dict[str, Any]) -> str:
        """Minimal fallback when LLM fails for sample size."""
        n = facts.get('sample_size', {})
        total = n.get('total_n', 'TBD') if isinstance(n, dict) else n
        return f"""## 6. SAMPLE SIZE AND POWER

### 6.1 Sample Size

Total sample size: {total} patients

### 6.2 Power Calculation

Power calculations were performed based on the primary endpoint assumptions.

[Note: LLM generation failed - this is a minimal fallback. Please review and enhance.]"""

    def _fallback_missing_data(self, facts: Dict[str, Any]) -> str:
        """Minimal fallback when LLM fails for missing data."""
        return """## 9. MISSING DATA

### 9.1 Missing Data Assumptions

The primary analysis assumes data are missing at random (MAR).

### 9.2 Primary Approach

Mixed Model Repeated Measures (MMRM) will be used for the primary analysis.

### 9.3 Sensitivity Analyses

Sensitivity analyses will include tipping point analysis and multiple imputation.

[Note: LLM generation failed - this is a minimal fallback. Please review and enhance.]"""

    def _fallback_methods(self, facts: Dict[str, Any]) -> str:
        """Minimal fallback when LLM fails for methods."""
        return """## 7. STATISTICAL METHODS

### 7.1 General Considerations

- Two-sided alpha = 0.05
- 95% confidence intervals
- Analyses performed using SAS 9.4

### 7.2 Primary Analysis

The primary endpoint will be analyzed using appropriate statistical methods.

[Note: LLM generation failed - this is a minimal fallback. Please review and enhance.]"""

    def _fallback_endpoints(self, facts: Dict[str, Any]) -> str:
        """Minimal fallback when LLM fails for endpoints."""
        endpoint = facts.get('primary_endpoint', 'Primary efficacy endpoint')
        timepoint = facts.get('primary_timepoint', 'as specified in protocol')
        return f"""## 5. ENDPOINTS

### 5.1 Primary Endpoint

{endpoint}

Assessment timepoint: {timepoint}

[Note: LLM generation failed - this is a minimal fallback. Please review and enhance.]"""

    def _fallback_stratification(self, facts: Dict[str, Any]) -> str:
        """Minimal fallback when LLM fails for stratification."""
        factors = facts.get('stratification_factors', [])
        if factors:
            factor_list = '\n'.join([f"- {f}" for f in factors])
        else:
            factor_list = "- As specified in protocol"
        return f"""## STRATIFICATION

### Stratification Factors

{factor_list}

[Note: LLM generation failed - this is a minimal fallback. Please review and enhance.]"""


# Convenience function
def create_llm_generator(rag_adapter=None) -> LLMSectionGenerator:
    """Factory function to create LLM section generator."""
    return LLMSectionGenerator(rag_adapter=rag_adapter)
