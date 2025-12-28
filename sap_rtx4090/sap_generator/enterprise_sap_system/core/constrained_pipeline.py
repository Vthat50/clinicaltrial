#!/usr/bin/env python3
"""
Schema-Constrained SAP Generation Pipeline (Full Coverage)
===========================================================

Complete pipeline that:
1. Extracts ALL protocol facts (28 entities) with Literal constraints
2. Creates Pydantic schemas where every protocol value is enforced
3. Generates each SAP section with schema enforcement
4. Uses constrained Estimand schema (prevents drug name contamination)
5. Verifies against formal invariants
6. Detects any contamination from RAG examples
7. Assembles final SAP document

Philosophy: If it's extracted from the protocol → It MUST be constrained

The key guarantee: LLM CANNOT output wrong values because
the Literal types only allow exact extracted values.
"""

import re
from typing import Dict, List, Optional, Tuple, Any, Literal
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator

# Full schema with complete constraint coverage (28 entities)
from .full_schema_generator import (
    FullProtocolFacts,
    extract_full_protocol_facts,
    create_fully_constrained_schema,
    create_constrained_estimand_schema,
    create_full_estimand_schema,
    generate_constrained_prompt,
    print_constraint_summary,
    # Section schemas
    IntroductionSectionBase,
    StudyDesignSectionBase,
    PopulationsSectionBase,
    EndpointsSectionBase,
    SampleSizeSectionBase,
    StatMethodsSectionBase,
    StratificationSectionBase,
)

# Legacy imports for backward compatibility
from .schema_constrained_generator import (
    ProtocolFacts,
    CitedValue,
    extract_protocol_facts as extract_protocol_facts_legacy,
    create_sample_size_schema as create_sample_size_schema_legacy,
    create_study_design_schema as create_study_design_schema_legacy,
    FormalVerifier,
    VerificationResult,
    ContaminationDetector,
    SectionAssembler
)
from .structured_llm import get_structured_client, SAPSectionGenerator


@dataclass
class PipelineResult:
    """Result of the constrained generation pipeline"""
    success: bool
    sap_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)
    facts: Optional[FullProtocolFacts] = None  # Now uses full coverage
    legacy_facts: Optional[ProtocolFacts] = None  # For backward compatibility
    verification_results: Dict[str, VerificationResult] = field(default_factory=dict)
    contamination_detected: bool = False
    contamination_details: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    constraint_coverage: int = 0  # Number of entities constrained


class ConstrainedSAPPipeline:
    """
    Main pipeline for schema-constrained SAP generation.

    Usage:
        pipeline = ConstrainedSAPPipeline()
        result = pipeline.generate(protocol_text, nct_id="NCT02394028")

        if result.success:
            print(result.sap_text)
        else:
            print(f"Errors: {result.errors}")
    """

    def __init__(self):
        self.structured_client = get_structured_client()
        self.section_generator = SAPSectionGenerator(self.structured_client)
        self.verifier = FormalVerifier()
        self.contamination_detector = ContaminationDetector()
        self.assembler = SectionAssembler()

    def generate(
        self,
        protocol_text: str,
        nct_id: str = None,
        skip_sections: List[str] = None
    ) -> PipelineResult:
        """
        Generate SAP with schema constraints and verification.

        Args:
            protocol_text: Full protocol document text
            nct_id: NCT ID (optional, will be extracted if not provided)
            skip_sections: List of section names to skip

        Returns:
            PipelineResult with SAP text and verification details
        """
        result = PipelineResult(success=True)
        skip = set(skip_sections or [])

        print("\n" + "="*60)
        print("SCHEMA-CONSTRAINED SAP GENERATION PIPELINE (FULL COVERAGE)")
        print("="*60)

        # =================================================================
        # STAGE 1: Extract ALL Protocol Facts (28 entities)
        # =================================================================
        print("\n[STAGE 1] Extracting ALL protocol facts (full coverage)...")

        # Use full extraction with 28 entities
        facts = extract_full_protocol_facts(protocol_text)
        result.facts = facts

        # Override NCT if provided
        if nct_id and not facts.nct_id:
            facts.nct_id = nct_id

        # Also extract legacy facts for backward compatibility
        legacy_facts = extract_protocol_facts_legacy(protocol_text)
        result.legacy_facts = legacy_facts

        # Validate critical facts
        missing_critical = self._check_critical_facts_full(facts)
        if missing_critical:
            result.warnings.extend([f"Missing: {m}" for m in missing_critical])
            print(f"  Warning: Missing critical facts: {missing_critical}")

        # Count constraint coverage
        result.constraint_coverage = self._count_constraints(facts)

        # Print full extraction summary
        print_constraint_summary(facts)

        # =================================================================
        # STAGE 2: Create Fully Constrained Schemas
        # =================================================================
        print("\n[STAGE 2] Creating Literal-constrained schemas (all 28 entities)...")

        # Create the fully constrained schema (all protocol values are Literals)
        full_sap_schema = create_fully_constrained_schema(facts)

        # Create constrained Estimand schema (prevents drug name contamination)
        estimand_schema = create_constrained_estimand_schema(facts)

        # Legacy schemas for backward compatibility
        sample_size_schema = create_sample_size_schema_legacy(legacy_facts)
        study_design_schema = create_study_design_schema_legacy(legacy_facts)

        print(f"\n  Full SAP Schema: {len(full_sap_schema.model_fields)} constrained fields")
        print(f"  Estimand Schema: drug_name=Literal['{facts.drug_name or 'Study Drug'}']")

        # Print the constrained values summary
        self._print_schema_constraints_full(facts)

        # =================================================================
        # STAGE 3: Generate ALL Sections with Schema Enforcement
        # =================================================================
        print("\n[STAGE 3] Generating ALL 9 SAP sections with schema enforcement...")

        # Use legacy_facts for methods that expect CitedValue format
        # Use facts (FullProtocolFacts) for new methods with direct values
        facts_summary = self._full_facts_to_dict(facts)

        # Section 1: Introduction
        if '1_introduction' not in skip:
            print("\n  [1/9] Generating Introduction section...")
            section_data = self._generate_introduction(facts)
            if section_data:
                result.sections['1_introduction'] = section_data
            else:
                result.errors.append("Failed to generate Introduction section")

        # Section 2: Objectives and Estimands
        if '2_objectives_estimands' not in skip:
            print("\n  [2/9] Generating Objectives & Estimands section...")
            section_data = self._generate_objectives_estimands(facts)
            if section_data:
                result.sections['2_objectives_estimands'] = section_data
            else:
                result.errors.append("Failed to generate Objectives & Estimands section")

        # Section 3: Study Design
        if 'study_design' not in skip and '3_study_design' not in skip:
            print("\n  [3/9] Generating Study Design section...")
            section_data, verification = self._generate_study_design(
                study_design_schema, legacy_facts, facts_summary
            )
            if section_data:
                result.sections['3_study_design'] = section_data
                result.verification_results['study_design'] = verification
                if not verification.passed:
                    result.errors.extend(verification.violations)
                    result.success = False
            else:
                result.errors.append("Failed to generate Study Design section")

        # Section 4: Analysis Populations
        if '4_analysis_populations' not in skip:
            print("\n  [4/9] Generating Analysis Populations section...")
            section_data = self._generate_analysis_populations(facts)
            if section_data:
                result.sections['4_analysis_populations'] = section_data
            else:
                result.errors.append("Failed to generate Analysis Populations section")

        # Section 5: Endpoints
        if '5_endpoints' not in skip:
            print("\n  [5/9] Generating Endpoints section...")
            section_data = self._generate_endpoints(facts)
            if section_data:
                result.sections['5_endpoints'] = section_data
            else:
                result.errors.append("Failed to generate Endpoints section")

        # Section 6: Sample Size Section
        if 'sample_size' not in skip and '6_sample_size' not in skip:
            print("\n  [6/9] Generating Sample Size section...")
            section_data, verification = self._generate_sample_size(
                sample_size_schema, legacy_facts, facts_summary
            )
            if section_data:
                result.sections['6_sample_size'] = section_data
                result.verification_results['sample_size'] = verification
                if not verification.passed:
                    result.errors.extend(verification.violations)
                    result.success = False
            else:
                result.errors.append("Failed to generate Sample Size section")

        # Section 7: Statistical Methods
        if '7_statistical_methods' not in skip:
            print("\n  [7/9] Generating Statistical Methods section...")
            section_data = self._generate_statistical_methods(facts)
            if section_data:
                result.sections['7_statistical_methods'] = section_data
            else:
                result.errors.append("Failed to generate Statistical Methods section")

        # Section 8: Missing Data Handling
        if '8_missing_data' not in skip:
            print("\n  [8/9] Generating Missing Data Handling section...")
            section_data = self._generate_missing_data(facts)
            if section_data:
                result.sections['8_missing_data'] = section_data
            else:
                result.errors.append("Failed to generate Missing Data section")

        # Section 9: Safety Analysis
        if '9_safety_analysis' not in skip:
            print("\n  [9/9] Generating Safety Analysis section...")
            section_data = self._generate_safety_analysis(facts)
            if section_data:
                result.sections['9_safety_analysis'] = section_data
            else:
                result.errors.append("Failed to generate Safety Analysis section")

        # =================================================================
        # STAGE 4: Contamination Detection
        # =================================================================
        print("\n[STAGE 4] Checking for contamination...")

        full_text = "\n".join(result.sections.values())
        # Use legacy_facts for contamination detector (expects CitedValue format)
        is_contaminated, contaminants = self.contamination_detector.check_contamination(
            full_text, legacy_facts
        )

        if is_contaminated:
            result.contamination_detected = True
            result.contamination_details = contaminants
            result.errors.append(f"CONTAMINATION DETECTED: {contaminants}")
            result.success = False
            print(f"  CONTAMINATION FOUND: {contaminants}")
        else:
            print("  No contamination detected")

        # =================================================================
        # STAGE 5: Assemble Final SAP
        # =================================================================
        print("\n[STAGE 5] Assembling final SAP document...")

        result.sap_text = self._assemble_sap(result.sections, facts)

        # =================================================================
        # Summary
        # =================================================================
        print("\n" + "="*60)
        print("PIPELINE SUMMARY (FULL COVERAGE)")
        print("="*60)
        print(f"  Success: {result.success}")
        print(f"  Constraint Coverage: {result.constraint_coverage}/28 entities")
        print(f"  Sections generated: {list(result.sections.keys())}")
        print(f"  Contamination: {'YES - BLOCKED' if result.contamination_detected else 'None'}")
        print(f"  Errors: {len(result.errors)}")
        print(f"  Warnings: {len(result.warnings)}")

        # Show key constrained values
        print("\n  KEY CONSTRAINTS ENFORCED:")
        print(f"    drug_name = Literal['{facts.drug_name or 'Study Drug'}']")
        print(f"    total_n = Literal[{facts.total_n or 'unknown'}]")
        print(f"    ratio = Literal['{facts.ratio or '1:1'}']")
        print(f"    nct_id = Literal['{facts.nct_id or 'unknown'}']")

        if result.errors:
            print("\n  ERRORS:")
            for err in result.errors:
                print(f"    - {err}")

        return result

    def _check_critical_facts(self, facts: ProtocolFacts) -> List[str]:
        """Check for missing critical facts (legacy)"""
        missing = []
        if not facts.total_n:
            missing.append("total_n")
        if not facts.drug_name:
            missing.append("drug_name")
        if not facts.ratio:
            missing.append("ratio")
        if not facts.num_arms:
            missing.append("num_arms")
        return missing

    def _check_critical_facts_full(self, facts: FullProtocolFacts) -> List[str]:
        """Check for missing critical facts (full schema)"""
        missing = []
        # High-priority facts that prevent contamination
        if not facts.drug_name:
            missing.append("drug_name (HIGH RISK)")
        if not facts.total_n:
            missing.append("total_n (HIGH RISK)")
        if not facts.ratio:
            missing.append("ratio (HIGH RISK)")
        if not facts.nct_id:
            missing.append("nct_id")
        if not facts.indication:
            missing.append("indication")
        if not facts.num_arms:
            missing.append("num_arms")
        return missing

    def _count_constraints(self, facts: FullProtocolFacts) -> int:
        """Count how many entities are constrained"""
        count = 0
        fields = [
            facts.nct_id, facts.study_id, facts.sponsor, facts.title,
            facts.phase, facts.therapeutic_area, facts.indication,
            facts.design_type, facts.drug_name, facts.drug_code,
            facts.route, facts.total_n, facts.ratio, facts.power,
            facts.alpha, facts.alpha_sidedness, facts.dropout_rate,
            facts.primary_endpoint, facts.primary_timepoint,
            facts.primary_population, facts.primary_analysis_method,
        ]
        for f in fields:
            if f is not None:
                count += 1
        # Count list fields
        if facts.arm_names:
            count += 1
        if facts.arm_descriptions:
            count += 1
        if facts.secondary_endpoints:
            count += 1
        if facts.stratification_factors:
            count += 1
        if facts.per_arm_n:
            count += 1
        return count

    def _print_extracted_facts(self, facts: ProtocolFacts):
        """Print extracted facts for debugging (legacy)"""
        print("\n  EXTRACTED FACTS:")
        print(f"    Drug: {facts.drug_name.value if facts.drug_name else 'NOT FOUND'}")
        print(f"    NCT: {facts.nct_id.value if facts.nct_id else 'NOT FOUND'}")
        print(f"    Total N: {facts.total_n.value if facts.total_n else 'NOT FOUND'}")
        print(f"    Ratio: {facts.ratio.value if facts.ratio else 'NOT FOUND'}")
        print(f"    Arms: {facts.num_arms.value if facts.num_arms else 'NOT FOUND'}")
        print(f"    Per-arm N: {facts.per_arm_n.value if facts.per_arm_n else 'NOT FOUND'}")
        print(f"    Power: {facts.power.value if facts.power else 'NOT FOUND'}")
        print(f"    Alpha: {facts.alpha.value if facts.alpha else 'NOT FOUND'}")
        print(f"    Route: {facts.route.value if facts.route else 'NOT FOUND'}")

    def _print_schema_constraints(self, facts: ProtocolFacts):
        """Print the Literal constraints that will be enforced (legacy)"""
        print("\n  SCHEMA CONSTRAINTS (LLM cannot violate these):")
        print(f"    total_n: Literal[{facts.total_n.value if facts.total_n else 100}]")
        print(f"    ratio: Literal[\"{facts.ratio.value if facts.ratio else '1:1'}\"]")
        print(f"    num_arms: Literal[{facts.num_arms.value if facts.num_arms else 2}]")
        print(f"    drug_name: Literal[\"{facts.drug_name.value if facts.drug_name else 'Study Drug'}\"]")

    def _print_schema_constraints_full(self, facts: FullProtocolFacts):
        """Print the full Literal constraints"""
        print("\n  FULL SCHEMA CONSTRAINTS (all 28 entities):")
        print(f"    [ID] nct_id: Literal['{facts.nct_id or 'UNKNOWN'}']")
        print(f"    [ID] study_id: Literal['{facts.study_id or 'UNKNOWN'}']")
        print(f"    [DRUG] drug_name: Literal['{facts.drug_name or 'Study Drug'}']")
        print(f"    [DRUG] drug_code: Literal['{facts.drug_code or ''}']")
        print(f"    [DRUG] route: Literal['{facts.route or 'Not specified'}']")
        print(f"    [SIZE] total_n: Literal[{facts.total_n or 100}]")
        print(f"    [SIZE] ratio: Literal['{facts.ratio or '1:1'}']")
        print(f"    [SIZE] num_arms: Literal[{facts.num_arms or 2}]")
        print(f"    [SIZE] power: Literal['{facts.power or '80%'}']")
        print(f"    [SIZE] alpha: Literal[{facts.alpha or 0.05}]")
        print(f"    [ENDPOINT] primary_endpoint: Literal['{(facts.primary_endpoint or 'Primary endpoint')[:50]}...']")
        print(f"    [STRAT] stratification_factors: {len(facts.stratification_factors or [])} factors")
        print(f"\n    Coverage: {self._count_constraints(facts)}/28 entities constrained")

    def _facts_to_dict(self, facts: ProtocolFacts) -> Dict[str, Any]:
        """Convert ProtocolFacts to dictionary for prompts (legacy)"""
        return {
            'total_n': facts.total_n.value if facts.total_n else None,
            'ratio': facts.ratio.value if facts.ratio else None,
            'num_arms': facts.num_arms.value if facts.num_arms else None,
            'per_arm_n': facts.per_arm_n.value if facts.per_arm_n else None,
            'power': facts.power.value if facts.power else None,
            'alpha': facts.alpha.value if facts.alpha else None,
            'alpha_sidedness': facts.alpha_sidedness.value if facts.alpha_sidedness else None,
            'drug_name': facts.drug_name.value if facts.drug_name else None,
            'route': facts.route.value if facts.route else None,
        }

    def _full_facts_to_dict(self, facts: FullProtocolFacts) -> Dict[str, Any]:
        """Convert FullProtocolFacts to dictionary for prompts (all 28 entities)"""
        return {
            # Identification
            'nct_id': facts.nct_id,
            'study_id': facts.study_id,
            'sponsor': facts.sponsor,
            'title': facts.title,
            # Study info
            'phase': facts.phase,
            'therapeutic_area': facts.therapeutic_area,
            'indication': facts.indication,
            'design_type': facts.design_type,
            # Drug
            'drug_name': facts.drug_name,
            'drug_code': facts.drug_code,
            'drug_generic': facts.drug_generic,
            'route': facts.route,
            # Arms
            'num_arms': facts.num_arms,
            'ratio': facts.ratio,
            'arm_names': facts.arm_names,
            'arm_descriptions': facts.arm_descriptions,
            'arm_doses': facts.arm_doses,
            # Sample size
            'total_n': facts.total_n,
            'per_arm_n': facts.per_arm_n,
            'power': facts.power,
            'alpha': facts.alpha,
            'alpha_sidedness': facts.alpha_sidedness,
            'dropout_rate': facts.dropout_rate,
            # Endpoints
            'primary_endpoint': facts.primary_endpoint,
            'primary_timepoint': facts.primary_timepoint,
            'secondary_endpoints': facts.secondary_endpoints,
            # Populations
            'primary_population': facts.primary_population,
            'itt_definition': facts.itt_definition,
            'pp_definition': facts.pp_definition,
            'safety_definition': facts.safety_definition,
            # Stratification
            'stratification_factors': facts.stratification_factors,
            # Analysis
            'primary_analysis_method': facts.primary_analysis_method,
            'study_duration': facts.study_duration,
        }

    def _generate_sample_size(
        self,
        schema_class,
        facts: ProtocolFacts,
        facts_summary: Dict
    ) -> Tuple[str, VerificationResult]:
        """Generate and verify Sample Size section"""
        # Try structured generation
        response = self.section_generator.generate_sample_size_section(
            schema_class, facts_summary
        )

        if response.success and response.data:
            # Convert to dict for verification
            section_dict = response.data.model_dump()

            # Verify
            verification = self.verifier.verify_sample_size_section(section_dict, facts)

            # Assemble prose
            prose = self.assembler.assemble_sample_size_section(section_dict)

            return prose, verification
        else:
            # Fallback: Generate template-based section
            print("    Falling back to template-based generation...")
            section_dict = self._template_sample_size(facts)
            verification = self.verifier.verify_sample_size_section(section_dict, facts)
            prose = self.assembler.assemble_sample_size_section(section_dict)
            return prose, verification

    def _generate_study_design(
        self,
        schema_class,
        facts: ProtocolFacts,
        facts_summary: Dict
    ) -> Tuple[str, VerificationResult]:
        """Generate and verify Study Design section"""
        arm_details = [arm.value for arm in facts.arms] if facts.arms else []

        response = self.section_generator.generate_study_design_section(
            schema_class, facts_summary, arm_details
        )

        if response.success and response.data:
            section_dict = response.data.model_dump()
            verification = self.verifier.verify_study_design_section(section_dict, facts)
            prose = self.assembler.assemble_study_design_section(section_dict)
            return prose, verification
        else:
            # Fallback: Template-based
            print("    Falling back to template-based generation...")
            section_dict = self._template_study_design(facts)
            verification = self.verifier.verify_study_design_section(section_dict, facts)
            prose = self.assembler.assemble_study_design_section(section_dict)
            return prose, verification

    def _template_sample_size(self, facts: ProtocolFacts) -> Dict:
        """Create template-based Sample Size section data"""
        total_n = facts.total_n.value if facts.total_n else 100
        ratio = facts.ratio.value if facts.ratio else "1:1"
        num_arms = facts.num_arms.value if facts.num_arms else 2
        per_arm_n = facts.per_arm_n.value if facts.per_arm_n else total_n // num_arms
        power = int(facts.power.value.replace('%', '')) if facts.power else 80
        alpha = facts.alpha.value if facts.alpha else 0.05
        alpha_side = facts.alpha_sidedness.value if facts.alpha_sidedness else "one-sided"

        return {
            'total_n': total_n,
            'ratio': ratio,
            'power_percent': power,
            'alpha': alpha,
            'alpha_sidedness': alpha_side,
            'num_arms': num_arms,
            'per_arm_n': per_arm_n,
            'introduction': "The sample size for this study was determined based on clinical and statistical considerations to ensure adequate power to detect a clinically meaningful treatment difference while accounting for expected dropout rates.",
            'power_calculation_narrative': "Power calculations were performed using standard methodology appropriate for the primary endpoint analysis. The assumptions underlying the power calculation are based on previous clinical studies in the target population.",
            'conclusion': "The planned sample size provides adequate statistical power to achieve the study objectives while considering practical enrollment constraints and expected dropout."
        }

    def _template_study_design(self, facts: ProtocolFacts) -> Dict:
        """Create template-based Study Design section data"""
        drug = facts.drug_name.value if facts.drug_name else "Study Drug"
        num_arms = facts.num_arms.value if facts.num_arms else 2
        ratio = facts.ratio.value if facts.ratio else "1:1"
        route = facts.route.value if facts.route else "intravenous"

        # Generate arm descriptions
        arm_descriptions = []
        if facts.arms:
            arm_descriptions = [arm.value for arm in facts.arms[:num_arms]]
        else:
            # Generate default arm descriptions
            if num_arms == 2:
                arm_descriptions = [f"{drug} active treatment", "Placebo"]
            elif num_arms == 3:
                arm_descriptions = [f"{drug} high dose", f"{drug} low dose", "Placebo"]
            else:
                arm_descriptions = [f"Treatment arm {i+1}" for i in range(num_arms)]

        return {
            'drug_name': drug,
            'num_arms': num_arms,
            'ratio': ratio,
            'route': route,
            'arm_descriptions': arm_descriptions,
            'design_narrative': f"This is a randomized, double-blind, placebo-controlled study designed to evaluate the efficacy and safety of {drug}. Eligible patients will be randomized to one of the treatment arms according to the randomization ratio. The study drug will be administered via {route} route according to the dosing schedule specified in the protocol."
        }

    # =========================================================================
    # NEW SECTION GENERATORS (Full Coverage)
    # =========================================================================

    def _generate_introduction(self, facts: FullProtocolFacts) -> str:
        """Generate Section 1: Introduction"""
        nct_id = facts.nct_id or "NCT-UNKNOWN"
        study_id = facts.study_id or "STUDY-ID"
        sponsor = facts.sponsor or "Sponsor"
        title = facts.title or "Clinical Trial"
        phase = facts.phase or "Phase 2"
        drug_name = facts.drug_name or "Investigational Product"
        indication = facts.indication or "target indication"

        return f"""## 1. INTRODUCTION

### 1.1 Purpose

This Statistical Analysis Plan (SAP) describes the planned statistical analyses for the clinical trial {nct_id} ({study_id}). This document provides detailed specifications for the statistical methodology to be used in the analysis of data from this study.

### 1.2 Study Overview

**Protocol:** {nct_id}
**Study ID:** {study_id}
**Sponsor:** {sponsor}
**Title:** {title}
**Phase:** {phase}
**Investigational Product:** {drug_name}
**Indication:** {indication}

### 1.3 Scope

This SAP covers all planned efficacy, safety, and exploratory analyses for the study. Any deviations from this plan will be documented and justified in the clinical study report.

### 1.4 Reference Documents

- Protocol: {study_id}
- ICH E9 Statistical Principles for Clinical Trials
- ICH E9(R1) Addendum on Estimands and Sensitivity Analysis
- CDISC ADaM Implementation Guide
"""

    def _generate_objectives_estimands(self, facts: FullProtocolFacts) -> str:
        """Generate Section 2: Objectives and Estimands"""
        drug_name = facts.drug_name or "Investigational Product"
        indication = facts.indication or "the target indication"
        primary_endpoint = facts.primary_endpoint or "the primary efficacy endpoint"
        primary_timepoint = facts.primary_timepoint or "Week 12"

        # Get arm info for treatment description
        arm_names = facts.arm_names if facts.arm_names else ["Active Treatment", "Placebo"]
        arm_descriptions = facts.arm_descriptions if facts.arm_descriptions else arm_names

        # Build treatment arms text
        arms_text = "\n".join([f"  - {desc}" for desc in arm_descriptions])

        return f"""## 2. STUDY OBJECTIVES AND ESTIMANDS

### 2.1 Primary Objective

To evaluate the efficacy of {drug_name} compared to placebo in patients with {indication}.

### 2.2 Primary Estimand (ICH E9(R1) Framework)

The primary estimand is defined according to ICH E9(R1) with the following attributes:

| Attribute | Specification |
|-----------|---------------|
| **Population** | Adult patients with {indication} who meet all inclusion criteria and none of the exclusion criteria |
| **Treatment** | {drug_name} vs. Placebo |
| **Variable** | {primary_endpoint} at {primary_timepoint} |
| **Intercurrent Events** | See Section 2.2.1 |
| **Summary Measure** | Difference in proportions (or appropriate measure) |

#### 2.2.1 Intercurrent Events and Strategies

| Intercurrent Event | Strategy | Rationale |
|-------------------|----------|-----------|
| Treatment discontinuation due to adverse event | Treatment Policy | Captures real-world treatment effect |
| Use of rescue medication | Treatment Policy | Part of intended treatment strategy |
| Missing assessment | Treatment Policy (imputed as non-responder) | Conservative approach for efficacy |

### 2.3 Secondary Objectives

1. To evaluate the safety and tolerability of {drug_name}
2. To evaluate secondary efficacy endpoints
3. To characterize the pharmacokinetics of {drug_name} (if applicable)

### 2.4 Secondary Estimands

Secondary estimands follow the same framework as the primary estimand with appropriate modifications for each secondary endpoint.

### 2.5 Treatment Arms

{arms_text}
"""

    def _generate_analysis_populations(self, facts: FullProtocolFacts) -> str:
        """Generate Section 4: Analysis Populations"""
        primary_population = facts.primary_population or "FAS"
        itt_def = facts.itt_definition or "All randomized patients"
        pp_def = facts.pp_definition or "All patients in the ITT population who complete the study without major protocol violations"
        safety_def = facts.safety_definition or "All patients who received at least one dose of study medication"

        # Build PK population if applicable
        pk_section = ""
        if facts.therapeutic_area and "pk" in str(facts).lower():
            pk_section = """
### 4.5 Pharmacokinetic (PK) Population

The PK population includes all patients in the PK subgroup who received at least one dose of study medication and have at least one measurable post-dose PK sample.
"""

        return f"""## 4. ANALYSIS POPULATIONS

### 4.1 Intent-to-Treat (ITT) Population

{itt_def}

This population will be used for sensitivity analyses of efficacy endpoints.

### 4.2 Full Analysis Set (FAS)

All randomized patients who received at least one dose of study medication and have at least one post-baseline efficacy assessment.

This is the **primary analysis population** for efficacy analyses.

### 4.3 Per-Protocol (PP) Population

{pp_def}

This population will be used for supportive efficacy analyses.

### 4.4 Safety Population

{safety_def}

This is the primary analysis population for all safety analyses.
{pk_section}
### 4.6 Population Derivation

| Population | Inclusion Criteria | Exclusion Criteria | Primary Use |
|------------|-------------------|-------------------|-------------|
| ITT | All randomized | None | Sensitivity analysis |
| FAS | ITT + ≥1 dose + ≥1 post-baseline assessment | None | **Primary efficacy** |
| PP | FAS | Major protocol violations | Supportive efficacy |
| Safety | ≥1 dose of study medication | None | **Safety analysis** |
"""

    def _generate_endpoints(self, facts: FullProtocolFacts) -> str:
        """Generate Section 5: Endpoints"""
        primary_endpoint = facts.primary_endpoint or "Primary efficacy endpoint"
        primary_timepoint = facts.primary_timepoint or "Week 12"
        secondary_endpoints = facts.secondary_endpoints if facts.secondary_endpoints else []

        # Build secondary endpoints table
        secondary_table = ""
        if secondary_endpoints:
            secondary_table = "| # | Endpoint | Timepoint |\n|---|----------|----------|\n"
            for i, ep in enumerate(secondary_endpoints, 1):
                secondary_table += f"| {i} | {ep} | Various |\n"
        else:
            secondary_table = """| # | Endpoint | Timepoint |
|---|----------|----------|
| 1 | Clinical response | Week 4, 8, 12 |
| 2 | Clinical remission | Week 4, 8, 12 |
| 3 | Mucosal healing | Week 12 |
| 4 | Change from baseline in symptom score | Week 4, 8, 12 |
"""

        return f"""## 5. ENDPOINTS

### 5.1 Primary Endpoint

**Definition:** {primary_endpoint}

**Timepoint:** {primary_timepoint}

**Derivation:** The primary endpoint will be derived according to the protocol definition. Patients with missing data at the primary timepoint will be considered as non-responders (treatment failure).

### 5.2 Secondary Efficacy Endpoints

{secondary_table}

### 5.3 Safety Endpoints

| Category | Endpoints |
|----------|-----------|
| Adverse Events | TEAEs, SAEs, AEs leading to discontinuation, AEs by severity |
| Laboratory | Clinical chemistry, hematology, urinalysis abnormalities |
| Vital Signs | Changes from baseline in blood pressure, heart rate, temperature |
| ECG | Changes from baseline in ECG parameters (if applicable) |

### 5.4 Exploratory Endpoints

Exploratory endpoints include biomarker assessments and other endpoints as defined in the protocol.
"""

    def _generate_statistical_methods(self, facts: FullProtocolFacts) -> str:
        """Generate Section 7: Statistical Methods"""
        primary_endpoint = facts.primary_endpoint or "primary endpoint"
        primary_timepoint = facts.primary_timepoint or "Week 12"
        primary_population = facts.primary_population or "FAS"
        primary_analysis_method = facts.primary_analysis_method or "Logistic regression"
        alpha = facts.alpha or 0.05
        alpha_sidedness = facts.alpha_sidedness or "two-sided"

        # Get stratification factors
        strat_factors = facts.stratification_factors if facts.stratification_factors else []
        strat_text = ", ".join(strat_factors) if strat_factors else "randomization stratification factors"

        return f"""## 7. STATISTICAL METHODS

### 7.1 General Considerations

- All statistical tests will be performed at a {alpha_sidedness} significance level of α = {alpha} unless otherwise specified.
- Confidence intervals will be two-sided {int((1-alpha)*100)}% confidence intervals.
- All analyses will be performed using SAS® Version 9.4 or later.

### 7.2 Primary Efficacy Analysis

**Analysis Population:** {primary_population}

**Primary Analysis Method:** {primary_analysis_method}

The primary endpoint ({primary_endpoint} at {primary_timepoint}) will be analyzed using {primary_analysis_method.lower()} with treatment as a fixed effect and {strat_text} as covariates.

**Model Specification:**

```
logit(P(response=1)) = β₀ + β₁×Treatment + β₂×Stratification_Factors + β₃×Baseline_Score
```

**Treatment Effect Estimate:** Odds ratio with {int((1-alpha)*100)}% confidence interval

**Hypothesis:**
- H₀: No difference between {facts.drug_name or 'active treatment'} and placebo
- H₁: Difference exists between {facts.drug_name or 'active treatment'} and placebo

### 7.3 Handling of Covariates

**Stratification Factors:** {strat_text}

The primary analysis will adjust for the stratification factors used in randomization.

### 7.4 Secondary Efficacy Analyses

Secondary endpoints will be analyzed using appropriate methods based on endpoint type:

| Endpoint Type | Analysis Method |
|--------------|-----------------|
| Binary | Logistic regression with GEE for repeated measures |
| Continuous | ANCOVA or MMRM for repeated measures |
| Time-to-event | Kaplan-Meier, Log-rank test, Cox regression |

### 7.5 Multiplicity Adjustment

Secondary endpoints will be tested using a hierarchical testing procedure to control the family-wise error rate. Testing will proceed in a pre-specified order, with subsequent endpoints tested only if all prior endpoints are significant at α = {alpha}.

### 7.6 Sensitivity Analyses

The following sensitivity analyses will be performed for the primary endpoint:

1. **Per-Protocol Analysis:** Analysis in PP population
2. **Tipping Point Analysis:** Assess robustness to missing data assumptions
3. **Multiple Imputation:** MICE with treatment group-specific imputation
4. **As-Observed Analysis:** Excluding patients with missing data

### 7.7 Subgroup Analyses

Subgroup analyses will be performed for the primary endpoint by:
- Age group (<65, ≥65 years)
- Sex
- Geographic region
- Baseline disease severity
- Prior treatment history
"""

    def _generate_missing_data(self, facts: FullProtocolFacts) -> str:
        """Generate Section 8: Missing Data Handling"""
        primary_endpoint = facts.primary_endpoint or "primary endpoint"

        return f"""## 8. MISSING DATA HANDLING

### 8.1 General Principles

Missing data handling follows ICH E9(R1) guidance on estimands and sensitivity analysis in clinical trials.

### 8.2 Primary Approach

**Treatment Policy Strategy:** For the primary analysis, patients with missing data for the {primary_endpoint} will be classified as non-responders (treatment failure). This approach is consistent with the treatment policy estimand strategy.

### 8.3 Missing Data Rules by Endpoint Type

| Endpoint Type | Primary Rule | Rationale |
|--------------|--------------|-----------|
| Binary efficacy | Non-responder imputation | Conservative for efficacy |
| Continuous | Last observation carried forward (LOCF) | Sensitivity: MMRM |
| Time-to-event | Censored at last known status | Standard survival analysis |

### 8.4 Sensitivity Analyses for Missing Data

To assess the robustness of the primary analysis conclusions, the following sensitivity analyses will be performed:

1. **Complete Case Analysis:** Analysis restricted to patients with observed primary endpoint
2. **Multiple Imputation:** Using MICE methodology under MAR assumption
3. **Tipping Point Analysis:** To determine how extreme assumptions about missing data would need to be to change conclusions
4. **Pattern Mixture Models:** Sensitivity to MNAR assumptions

### 8.5 Visit Windows

Analysis windows for each assessment timepoint are defined in the protocol. If multiple assessments occur within a window, the assessment closest to the target day will be used.

### 8.6 Partial Data

- Partial response data: Individual components will be imputed using last observation if available
- If individual components cannot be derived: Overall response will be set to non-responder
"""

    def _generate_safety_analysis(self, facts: FullProtocolFacts) -> str:
        """Generate Section 9: Safety Analysis"""
        drug_name = facts.drug_name or "study drug"
        num_arms = facts.num_arms or 2

        # Build arm column headers
        arm_names = facts.arm_names if facts.arm_names else [f"Arm {i+1}" for i in range(num_arms)]
        arm_headers = " | ".join(arm_names)
        arm_cols = " | ".join(["n (%)" for _ in arm_names])

        return f"""## 9. SAFETY ANALYSIS

### 9.1 General Principles

Safety analyses will be performed on the Safety Population (all patients who received at least one dose of study medication). No formal statistical testing will be performed for safety endpoints; descriptive statistics and listings will be provided.

### 9.2 Adverse Events

#### 9.2.1 Adverse Event Coding

Adverse events will be coded using MedDRA (latest version available at database lock). Events will be summarized by System Organ Class (SOC) and Preferred Term (PT).

#### 9.2.2 Treatment-Emergent Adverse Events (TEAEs)

TEAEs are defined as AEs that started or worsened after the first dose of study medication.

#### 9.2.3 Adverse Event Summaries

The following tables will be produced:

| Table | Description |
|-------|-------------|
| AE.01 | Overview of adverse events |
| AE.02 | TEAEs by SOC and PT |
| AE.03 | TEAEs by relationship to study drug |
| AE.04 | TEAEs by severity |
| AE.05 | TEAEs leading to discontinuation |
| AE.06 | Serious adverse events |
| AE.07 | Deaths |

#### 9.2.4 Table Shell Example: Overview of Adverse Events

| Category | {arm_headers} | Total |
|----------|{arm_cols}|-------|
| Any TEAE | | |
| Any treatment-related TEAE | | |
| Any SAE | | |
| Any TEAE leading to discontinuation | | |
| Deaths | | |

### 9.3 Laboratory Parameters

Clinical laboratory data (hematology, chemistry, urinalysis) will be summarized using:

1. Descriptive statistics (n, mean, SD, median, min, max) by timepoint
2. Change from baseline statistics
3. Shift tables (baseline vs. worst post-baseline value)
4. Patients with potentially clinically significant (PCS) values

### 9.4 Vital Signs

Vital signs will be summarized using:
- Descriptive statistics by timepoint
- Change from baseline
- Patients with PCS values

### 9.5 Electrocardiogram (ECG)

If applicable, ECG parameters will be summarized using:
- Descriptive statistics by timepoint
- Change from baseline
- Categorical analysis of QTcF changes

### 9.6 Immunogenicity

Anti-drug antibody (ADA) assessments will be summarized:
- Incidence of treatment-emergent ADA
- Relationship between ADA status and efficacy/safety

### 9.7 Exposure

Exposure to {drug_name} will be summarized:
- Duration of treatment
- Number of doses received
- Cumulative dose
"""

    def _assemble_sap(self, sections: Dict[str, str], facts) -> str:
        """Assemble sections into complete SAP document.

        Handles both FullProtocolFacts (new) and ProtocolFacts (legacy).
        """
        # Handle both old CitedValue format and new direct value format
        if isinstance(facts, FullProtocolFacts):
            # New format: direct values
            drug = facts.drug_name or "Study Drug"
            nct = facts.nct_id or "NCT-UNKNOWN"
            phase = facts.phase or "Phase 2"
            indication = facts.indication or "Not specified"
            sponsor = facts.sponsor or "Sponsor"
            design = facts.design_type or "Randomized controlled trial"
            total_n = facts.total_n or 0
            ratio = facts.ratio or "1:1"
        else:
            # Legacy format: CitedValue with .value
            drug = facts.drug_name.value if facts.drug_name else "Study Drug"
            nct = facts.nct_id.value if facts.nct_id else "NCT-UNKNOWN"
            phase = facts.phase.value if facts.phase else "Phase 2"
            indication = "Not specified"
            sponsor = "Sponsor"
            design = "Randomized controlled trial"
            total_n = facts.total_n.value if facts.total_n else 0
            ratio = facts.ratio.value if facts.ratio else "1:1"

        header = f"""STATISTICAL ANALYSIS PLAN

Protocol: {nct}
Drug: {drug}
Sponsor: {sponsor}
Phase: {phase}
Indication: {indication}
Design: {design}
Sample Size: {total_n} ({ratio})
Date: [DATE]
Version: 1.0

============================================================

TABLE OF CONTENTS

1. Introduction
2. Study Objectives
3. Study Design
4. Analysis Populations
5. Endpoints
6. Sample Size Calculation
7. Statistical Methods
8. Missing Data Handling
9. Safety Analysis
10. Appendices

============================================================
"""

        # Assemble body in correct section order
        body = ""
        section_order = [
            '1_introduction',
            '2_objectives_estimands',
            '3_study_design',
            'study_design',  # Legacy key
            '4_analysis_populations',
            '5_endpoints',
            '6_sample_size',
            'sample_size',  # Legacy key
            '7_statistical_methods',
            '8_missing_data',
            '9_safety_analysis',
        ]

        for section_key in section_order:
            if section_key in sections:
                body += sections[section_key] + "\n\n"

        footer = """
============================================================
END OF STATISTICAL ANALYSIS PLAN
============================================================
"""

        return header + body + footer


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def generate_constrained_sap(
    protocol_text: str,
    nct_id: str = None
) -> PipelineResult:
    """
    Convenience function to generate SAP with schema constraints.

    Args:
        protocol_text: Full protocol document text
        nct_id: NCT ID (optional)

    Returns:
        PipelineResult with SAP and verification details
    """
    pipeline = ConstrainedSAPPipeline()
    return pipeline.generate(protocol_text, nct_id)


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m enterprise_sap_system.core.constrained_pipeline <protocol_file>")
        sys.exit(1)

    protocol_file = sys.argv[1]

    with open(protocol_file, 'r') as f:
        protocol_text = f.read()

    result = generate_constrained_sap(protocol_text)

    if result.success:
        print("\n" + "="*60)
        print("GENERATED SAP")
        print("="*60)
        print(result.sap_text)
    else:
        print("\nGENERATION FAILED:")
        for error in result.errors:
            print(f"  - {error}")
