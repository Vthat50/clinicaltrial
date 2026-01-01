#!/usr/bin/env python3
"""
Hybrid SAP Generation Pipeline
==============================

Unified pipeline that uses the hybrid reasoning engine for section generation.
This replaces the fragmented template-based approach with proper reasoning:

- Decision Trees for deterministic sections (Populations, Derivations, TEAE)
- RAG for domain-specific sections (Endpoints, Methods, Stratification, Windows)
- Regex for simple pattern extraction (Arms)

Usage:
    from hybrid_pipeline import HybridSAPPipeline

    pipeline = HybridSAPPipeline()
    result = pipeline.generate(protocol_text, nct_id="NCT12345678")
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

# Import components
from .structured_extractor import StructuredFactExtractor, ProtocolFacts
from .hybrid_reasoning import (
    HybridReasoningEngine,
    ReasoningResult,
    ReasoningType,
    create_hybrid_engine
)
from .rag_adapter import create_rag_adapter, HybridRAGAdapter

# Try to import validation components
try:
    from .hard_validator import HardValidator, ValidationResult
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False

try:
    from .contamination_guard import ContaminationGuard
    CONTAMINATION_GUARD_AVAILABLE = True
except ImportError:
    CONTAMINATION_GUARD_AVAILABLE = False


@dataclass
class HybridPipelineResult:
    """Result from hybrid pipeline generation"""
    success: bool = True
    sap_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)
    reasoning_results: Dict[str, ReasoningResult] = field(default_factory=dict)
    facts: Optional[ProtocolFacts] = None
    validation: Optional[Any] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Metrics
    decision_tree_sections: int = 0
    rag_sections: int = 0
    template_fallback_sections: int = 0

    def get_reasoning_summary(self) -> str:
        """Get summary of reasoning approaches used"""
        lines = ["Reasoning Approaches Used:", "=" * 40]

        for section, result in self.reasoning_results.items():
            icon = {
                ReasoningType.DECISION_TREE: "🌳",
                ReasoningType.RAG: "📚",
                ReasoningType.REGEX: "📝",
                ReasoningType.TEMPLATE: "📄"
            }.get(result.reasoning_type, "?")

            conf = f"{result.confidence:.0%}"
            sources = ", ".join(result.rag_examples_used[:2]) if result.rag_examples_used else ""
            sources_str = f" (from: {sources})" if sources else ""

            lines.append(f"  {icon} {section}: {result.reasoning_type.value} [{conf}]{sources_str}")

        lines.append("")
        lines.append(f"Decision Tree: {self.decision_tree_sections} sections")
        lines.append(f"RAG-enhanced: {self.rag_sections} sections")
        lines.append(f"Template fallback: {self.template_fallback_sections} sections")

        return "\n".join(lines)


class HybridSAPPipeline:
    """
    Unified SAP generation pipeline using hybrid reasoning.

    This is the MAIN ENTRY POINT for SAP generation.
    All other pipelines should delegate to this one.
    """

    def __init__(
        self,
        use_rag: bool = True,
        use_validation: bool = True,
        strict_validation: bool = False,
        verbose: bool = True
    ):
        """
        Initialize hybrid pipeline.

        Args:
            use_rag: Enable RAG for enhanced sections
            use_validation: Enable post-generation validation
            strict_validation: Block output on validation failures
            verbose: Print progress messages
        """
        self.verbose = verbose
        self.use_validation = use_validation
        self.strict_validation = strict_validation

        # Initialize extractor
        self.extractor = StructuredFactExtractor()

        # Initialize RAG adapter
        self.rag_adapter = create_rag_adapter() if use_rag else None

        # Initialize hybrid reasoning engine with RAG
        self.reasoning_engine = create_hybrid_engine(
            rag_retriever=self.rag_adapter
        )

        # Initialize validators
        self.validator = HardValidator(strict_mode=strict_validation) if VALIDATOR_AVAILABLE and use_validation else None
        self.contamination_guard = ContaminationGuard() if CONTAMINATION_GUARD_AVAILABLE else None

        if self.verbose:
            print("[Hybrid Pipeline] Initialized")
            print(f"  RAG: {'enabled' if use_rag and self.rag_adapter else 'disabled'}")
            print(f"  Validation: {'enabled' if use_validation else 'disabled'}")
            print(self.reasoning_engine.get_reasoning_summary())

    def generate(
        self,
        protocol_text: str,
        nct_id: str = None
    ) -> HybridPipelineResult:
        """
        Generate SAP using hybrid reasoning.

        Args:
            protocol_text: Full protocol document text
            nct_id: NCT ID (optional, will be extracted if not provided)

        Returns:
            HybridPipelineResult with SAP and metadata
        """
        result = HybridPipelineResult()

        try:
            # =================================================================
            # LAYER 1: EXTRACTION
            # =================================================================
            if self.verbose:
                print("\n[LAYER 1] Extracting protocol facts...")

            facts = self.extractor.extract_all(protocol_text)
            if nct_id:
                facts.nct_id = nct_id
            result.facts = facts

            # Convert to dict for reasoning engine
            facts_dict = self._facts_to_dict(facts)

            if self.verbose:
                print(f"  Drug: {facts.drug_name}")
                print(f"  Design: {facts.design_type} (single-arm: {facts_dict.get('is_single_arm', False)})")
                print(f"  Sample Size: {facts.sample_size.total_n if facts.sample_size else 0}")
                print(f"  Primary Endpoint: {facts.primary_endpoint}")

            # =================================================================
            # LAYER 2: HYBRID REASONING
            # =================================================================
            if self.verbose:
                print("\n[LAYER 2] Generating sections with hybrid reasoning...")

            # Generate sections using hybrid engine
            reasoning_results = self.reasoning_engine.generate_all_sections(facts_dict)
            result.reasoning_results = reasoning_results

            # Count reasoning types used
            for section, rr in reasoning_results.items():
                result.sections[section] = rr.content
                if rr.reasoning_type == ReasoningType.DECISION_TREE:
                    result.decision_tree_sections += 1
                elif rr.reasoning_type == ReasoningType.RAG:
                    result.rag_sections += 1
                else:
                    result.template_fallback_sections += 1

                if self.verbose:
                    icon = "🌳" if rr.reasoning_type == ReasoningType.DECISION_TREE else "📚" if rr.reasoning_type == ReasoningType.RAG else "📄"
                    print(f"  {icon} {section}: {rr.reasoning_type.value} ({rr.confidence:.0%})")

            # =================================================================
            # LAYER 3: ADDITIONAL SECTIONS (LLM-based)
            # =================================================================
            if self.verbose:
                print("\n[LAYER 3] Generating additional sections...")

            # Generate sections not covered by hybrid engine
            result.sections['introduction'] = self._generate_introduction(facts_dict)
            result.sections['objectives'] = self._generate_objectives(facts_dict)
            result.sections['study_design'] = self._generate_study_design(facts_dict)
            result.sections['sample_size'] = self._generate_sample_size(facts_dict)
            result.sections['missing_data'] = self._generate_missing_data(facts_dict)

            # =================================================================
            # LAYER 4: ASSEMBLY
            # =================================================================
            if self.verbose:
                print("\n[LAYER 4] Assembling SAP document...")

            result.sap_text = self._assemble_sap(result.sections, facts_dict)

            # =================================================================
            # LAYER 5: VALIDATION
            # =================================================================
            if self.use_validation and self.validator:
                if self.verbose:
                    print("\n[LAYER 5] Validating SAP...")

                validation = self.validator.validate(result.sap_text, facts)
                result.validation = validation

                if self.verbose:
                    print(f"  {validation.summary()}")

                if validation.block_output and self.strict_validation:
                    result.success = False
                    result.errors.append("Validation failed - output blocked")

            # Check for contamination
            if self.contamination_guard:
                cleaned, report, changes = self.contamination_guard.check_and_clean(
                    result.sap_text, protocol_text
                )
                if report.is_contaminated:
                    result.warnings.append(f"Contamination detected: {report.contamination_sources}")
                    result.sap_text = cleaned

            result.success = True

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            if self.verbose:
                print(f"\n[ERROR] Pipeline failed: {e}")

        return result

    def _facts_to_dict(self, facts: ProtocolFacts) -> Dict[str, Any]:
        """Convert ProtocolFacts to dictionary for reasoning engine"""
        # Determine if single-arm
        is_single_arm = (
            facts.num_arms == 1 or
            (facts.design_type and 'single' in facts.design_type.lower()) or
            not facts.randomization_ratio
        )

        # Safely get optional attributes
        def safe_get(obj, attr, default=None):
            return getattr(obj, attr, default) if obj else default

        return {
            'nct_id': facts.nct_id,
            'drug_name': facts.drug_name,
            'drug_names_all': facts.drug_names_all if facts.drug_names_all else [],
            'design_type': facts.design_type,
            'is_single_arm': is_single_arm,
            'is_blinded': safe_get(facts, 'is_blinded', False),
            'blinding_type': safe_get(facts, 'blinding_type'),
            'num_arms': facts.num_arms if facts.num_arms else (1 if is_single_arm else 2),
            'arms': [arm.name for arm in facts.arms] if facts.arms else [],
            'randomization_ratio': facts.randomization_ratio,
            'stratification_factors': facts.stratification_factors if facts.stratification_factors else [],
            'sample_size': facts.sample_size.total_n if facts.sample_size else 0,
            'power': facts.sample_size.power if facts.sample_size else None,
            'alpha': facts.alpha.primary_alpha if facts.alpha else 0.05,
            'alpha_sidedness': facts.alpha.sidedness if facts.alpha else 'two-sided',
            'primary_endpoint': facts.primary_endpoint.definition if facts.primary_endpoint else '',
            'primary_endpoint_name': facts.primary_endpoint.name if facts.primary_endpoint else 'Primary Endpoint',
            'primary_timepoint': facts.primary_endpoint.timepoint if facts.primary_endpoint and hasattr(facts.primary_endpoint, 'timepoint') else 'Week 12',
            'secondary_endpoints': [ep.definition for ep in facts.secondary_endpoints] if facts.secondary_endpoints else [],
            'therapeutic_area': safe_get(facts, 'therapeutic_area'),
            'indication': safe_get(facts, 'indication'),
            'phase': facts.phase.value if facts.phase else 'Phase 3',
            'route_of_administration': facts.route_of_administration.value if facts.route_of_administration else 'IV',
            'itt_definition': safe_get(facts, 'itt_definition'),
            'fas_definition': safe_get(facts, 'fas_definition'),
            'pp_definition': safe_get(facts, 'pp_definition'),
            'safety_definition': safe_get(facts, 'safety_definition'),
            'primary_analysis_method': safe_get(facts, 'primary_analysis_method'),
            'primary_analysis_population': safe_get(facts, 'primary_analysis_population'),
        }

    def _generate_introduction(self, facts: Dict[str, Any]) -> str:
        """Generate introduction section"""
        drug = facts.get('drug_name', 'study drug')
        nct = facts.get('nct_id', 'NCT########')
        phase = facts.get('phase', 'Phase 3')
        indication = facts.get('indication', 'the target indication')

        return f"""## 1. INTRODUCTION

### 1.1 Purpose

This Statistical Analysis Plan (SAP) describes the statistical methods for the analysis of data from study {nct}, a {phase} study of {drug} in patients with {indication}.

This SAP is based on the protocol and should be read in conjunction with it. Any deviations from the pre-specified analyses will be documented in the Clinical Study Report.

### 1.2 Scope

This SAP covers:
- All efficacy analyses (primary, secondary, exploratory)
- All safety analyses
- Derivation of analysis datasets (ADaM)
- Table, listing, and figure specifications

### 1.3 Responsibilities

The Biostatistics team is responsible for:
- Implementation of this SAP
- Generation of analysis datasets
- Production of statistical outputs
- Interpretation of results in conjunction with the clinical team
"""

    def _generate_objectives(self, facts: Dict[str, Any]) -> str:
        """Generate objectives section"""
        drug = facts.get('drug_name', 'study drug')
        indication = facts.get('indication', 'the target indication')
        primary_endpoint = facts.get('primary_endpoint', 'the primary efficacy endpoint')
        is_single_arm = facts.get('is_single_arm', False)

        if is_single_arm:
            comparison = f"in patients with {indication}"
            estimand_target = f"the effect of {drug}"
        else:
            comparison = f"compared to placebo in patients with {indication}"
            estimand_target = f"the treatment effect of {drug} versus placebo"

        return f"""## 2. OBJECTIVES AND ESTIMANDS

### 2.1 Primary Objective

To evaluate the efficacy of {drug} {comparison} as measured by {primary_endpoint}.

### 2.2 Primary Estimand

Following ICH E9(R1), the primary estimand is defined as:

| Attribute | Specification |
|-----------|---------------|
| **Population** | Patients with {indication} meeting eligibility criteria |
| **Treatment** | {drug} {'at specified dose' if is_single_arm else 'vs placebo'} |
| **Variable** | {primary_endpoint} |
| **Intercurrent Events** | Treatment discontinuation: Treatment policy strategy |
| **Summary Measure** | {'Proportion of responders' if 'response' in primary_endpoint.lower() else 'Difference in means'} |

### 2.3 Secondary Objectives

1. To evaluate the safety and tolerability of {drug}
2. To evaluate additional efficacy endpoints
3. To characterize the pharmacokinetics of {drug} (if applicable)
"""

    def _generate_study_design(self, facts: Dict[str, Any]) -> str:
        """Generate study design section"""
        drug = facts.get('drug_name', 'study drug')
        design_type = facts.get('design_type', 'randomized, double-blind, placebo-controlled')
        is_single_arm = facts.get('is_single_arm', False)
        num_arms = facts.get('num_arms', 2)
        ratio = facts.get('randomization_ratio', '1:1')
        phase = facts.get('phase', 'Phase 3')

        # Get stratification from hybrid reasoning result if available
        strat_section = facts.get('stratification_section', '')

        if is_single_arm:
            design_desc = f"""This is a {phase}, open-label, single-arm study of {drug}.

**Study Design:** Single-arm, open-label

**Treatment:** All enrolled patients will receive {drug} at the protocol-specified dose.

**No Randomization:** As a single-arm study, patients are not randomized."""
        else:
            design_desc = f"""This is a {phase}, {design_type} study of {drug}.

**Study Design:** {design_type.title()}

**Randomization:** Patients will be randomized in a {ratio} ratio to:
{self._format_arms(facts)}

**Blinding:** {facts.get('blinding_type', 'Double-blind')}"""

        return f"""## 3. STUDY DESIGN

### 3.1 Overview

{design_desc}

### 3.2 Treatment Arms

| Arm | Treatment | N (planned) |
|-----|-----------|-------------|
{self._format_arms_table(facts)}

### 3.3 Study Duration

- Screening: Up to 4 weeks
- Treatment: Per protocol
- Follow-up: Per protocol

{strat_section}
"""

    def _format_arms(self, facts: Dict[str, Any]) -> str:
        """Format treatment arms list"""
        arms = facts.get('arms', [])
        drug = facts.get('drug_name', 'study drug')

        if not arms:
            if facts.get('is_single_arm'):
                return f"- {drug} (single arm)"
            else:
                return f"- {drug}\n- Placebo"

        return "\n".join([f"- {arm}" for arm in arms])

    def _format_arms_table(self, facts: Dict[str, Any]) -> str:
        """Format arms table rows"""
        arms = facts.get('arms', [])
        drug = facts.get('drug_name', 'study drug')
        n = facts.get('sample_size', 0)
        num_arms = facts.get('num_arms', 2)

        if not arms:
            if facts.get('is_single_arm'):
                return f"| 1 | {drug} | {n} |"
            else:
                per_arm = n // num_arms if n and num_arms else 'TBD'
                return f"| 1 | {drug} | {per_arm} |\n| 2 | Placebo | {per_arm} |"

        per_arm = n // len(arms) if n and arms else 'TBD'
        return "\n".join([f"| {i+1} | {arm} | {per_arm} |" for i, arm in enumerate(arms)])

    def _generate_sample_size(self, facts: Dict[str, Any]) -> str:
        """Generate sample size section"""
        n = facts.get('sample_size', 0)
        power = facts.get('power') or 0.80
        alpha = facts.get('alpha') or 0.05
        is_single_arm = facts.get('is_single_arm', False)
        primary_endpoint = facts.get('primary_endpoint', '')

        # Format power safely
        power_str = f"{power:.0%}" if power else "80%"

        if is_single_arm:
            design_text = """**Single-Arm Design:**

Sample size is based on achieving adequate precision for the primary endpoint estimate."""
        else:
            design_text = f"""**Comparative Design:**

Sample size provides {power_str} power to detect a clinically meaningful difference between treatment groups at a {alpha} significance level."""

        return f"""## 6. SAMPLE SIZE

### 6.1 Sample Size Justification

**Planned Enrollment:** {n if n else 'TBD'} patients

{design_text}

### 6.2 Assumptions

- Primary endpoint: {primary_endpoint if primary_endpoint else 'Per protocol'}
- Significance level: {alpha} ({'one-sided' if facts.get('alpha_sidedness') == 'one-sided' else 'two-sided'})
- Power: {power_str}
- Dropout rate: ~10-15%

### 6.3 Sample Size Formula

{'Exact binomial CI width for single-arm design' if is_single_arm else 'Chi-square test or t-test as appropriate for endpoint type'}
"""

    def _generate_missing_data(self, facts: Dict[str, Any]) -> str:
        """Generate missing data section"""
        is_single_arm = facts.get('is_single_arm', False)

        return f"""## 9. MISSING DATA

### 9.1 Missing Data Handling

**Primary Approach:** {'Per-protocol analysis with sensitivity analyses' if is_single_arm else 'Treatment policy strategy (all data used regardless of discontinuation)'}

### 9.2 Imputation Methods

| Scenario | Method |
|----------|--------|
| Missing baseline | Patient excluded from analysis |
| Missing post-baseline (binary) | Non-responder imputation (NRI) |
| Missing post-baseline (continuous) | MMRM (implicit imputation) |
| Early discontinuation | Multiple imputation or LOCF sensitivity |

### 9.3 Sensitivity Analyses

1. **Complete Case Analysis:** Patients with complete data only
2. **LOCF:** Last observation carried forward
3. **BOCF:** Baseline observation carried forward
4. **Multiple Imputation:** Under MAR assumption
5. **Tipping Point:** Assess robustness to MNAR scenarios

### 9.4 Missing Data Reporting

Extent of missing data will be summarized:
- By visit and treatment group
- By reason for missing
- Impact on analysis populations
"""

    def _assemble_sap(self, sections: Dict[str, str], facts: Dict[str, Any]) -> str:
        """Assemble final SAP document from sections"""
        drug = facts.get('drug_name', 'Study Drug')
        nct = facts.get('nct_id', 'NCT########')
        phase = facts.get('phase', 'Phase 3')

        # Header
        header = f"""# STATISTICAL ANALYSIS PLAN

**Study:** {nct}
**Drug:** {drug}
**Phase:** {phase}
**Version:** 1.0
**Date:** [DATE]

---

## TABLE OF CONTENTS

1. Introduction
2. Objectives and Estimands
3. Study Design
4. Analysis Populations
5. Endpoints
6. Sample Size
7. Statistical Methods
8. Safety Analysis
9. Missing Data
Appendix A: Variable Derivations

---

"""

        # Order sections properly
        section_order = [
            'introduction',
            'objectives',
            'study_design',
            'stratification',      # From hybrid engine
            'populations',         # From hybrid engine
            'endpoints',           # From hybrid engine
            'sample_size',
            'methods',             # From hybrid engine
            'teae_logic',          # From hybrid engine (safety)
            'missing_data',
            'derivations',         # From hybrid engine
            'follow_up_windows',   # From hybrid engine
        ]

        body_parts = []
        for section_name in section_order:
            if section_name in sections and sections[section_name]:
                body_parts.append(sections[section_name])

        body = "\n\n".join(body_parts)

        return header + body


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_hybrid_pipeline(
    use_rag: bool = True,
    use_validation: bool = True,
    verbose: bool = True
) -> HybridSAPPipeline:
    """Create a hybrid SAP pipeline instance"""
    return HybridSAPPipeline(
        use_rag=use_rag,
        use_validation=use_validation,
        verbose=verbose
    )


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("HYBRID SAP GENERATION PIPELINE")
    print("=" * 60)

    # Create pipeline
    pipeline = create_hybrid_pipeline(use_rag=True, verbose=True)

    # Test with sample protocol
    test_protocol = """
    A Phase 2, Open-Label, Single-Arm Study of Pembrolizumab in Patients with
    Advanced Solid Tumors Expressing CD137.

    NCT03422848

    Approximately 50 patients will be enrolled to receive Pembrolizumab 200mg IV Q3W.

    The primary endpoint is objective response rate (ORR) per RECIST v1.1 at Week 12.

    Secondary endpoints include:
    - Duration of response
    - Progression-free survival
    - Overall survival

    This is a single-arm, open-label study. No randomization.
    """

    result = pipeline.generate(test_protocol, nct_id="NCT03422848")

    print("\n" + "=" * 60)
    print("GENERATION COMPLETE")
    print("=" * 60)
    print(f"Success: {result.success}")
    print(f"Errors: {result.errors}")
    print(f"Warnings: {result.warnings}")
    print("\n" + result.get_reasoning_summary())

    if result.sap_text:
        print("\n" + "=" * 60)
        print("GENERATED SAP (first 2000 chars)")
        print("=" * 60)
        print(result.sap_text[:2000])
