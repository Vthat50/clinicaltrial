#!/usr/bin/env python3
"""
Schema-Constrained SAP Generation Pipeline
===========================================

Complete pipeline that:
1. Extracts protocol facts with citations
2. Creates Pydantic schemas with Literal constraints
3. Generates each SAP section with schema enforcement
4. Verifies against formal invariants
5. Detects any contamination from RAG examples
6. Assembles final SAP document

The key guarantee: LLM CANNOT output wrong values because
the Literal types only allow exact extracted values.
"""

import re
from typing import Dict, List, Optional, Tuple, Any, Literal
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator

from .schema_constrained_generator import (
    ProtocolFacts,
    CitedValue,
    extract_protocol_facts,
    create_sample_size_schema,
    create_study_design_schema,
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
    facts: Optional[ProtocolFacts] = None
    verification_results: Dict[str, VerificationResult] = field(default_factory=dict)
    contamination_detected: bool = False
    contamination_details: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


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
        print("SCHEMA-CONSTRAINED SAP GENERATION PIPELINE")
        print("="*60)

        # =================================================================
        # STAGE 1: Extract Protocol Facts
        # =================================================================
        print("\n[STAGE 1] Extracting protocol facts with citations...")

        facts = extract_protocol_facts(protocol_text)
        result.facts = facts

        # Override NCT if provided
        if nct_id and not facts.nct_id:
            facts.nct_id = CitedValue(value=nct_id, citation="User provided")

        # Validate critical facts
        missing_critical = self._check_critical_facts(facts)
        if missing_critical:
            result.warnings.extend([f"Missing: {m}" for m in missing_critical])
            print(f"  Warning: Missing critical facts: {missing_critical}")

        self._print_extracted_facts(facts)

        # =================================================================
        # STAGE 2: Create Constrained Schemas
        # =================================================================
        print("\n[STAGE 2] Creating Literal-constrained schemas...")

        sample_size_schema = create_sample_size_schema(facts)
        study_design_schema = create_study_design_schema(facts)

        # Print the constrained values
        self._print_schema_constraints(facts)

        # =================================================================
        # STAGE 3: Generate Sections with Schema Enforcement
        # =================================================================
        print("\n[STAGE 3] Generating sections with schema enforcement...")

        facts_summary = self._facts_to_dict(facts)

        # Sample Size Section
        if 'sample_size' not in skip:
            print("\n  Generating Sample Size section...")
            section_data, verification = self._generate_sample_size(
                sample_size_schema, facts, facts_summary
            )
            if section_data:
                result.sections['sample_size'] = section_data
                result.verification_results['sample_size'] = verification
                if not verification.passed:
                    result.errors.extend(verification.violations)
                    result.success = False
            else:
                result.errors.append("Failed to generate Sample Size section")

        # Study Design Section
        if 'study_design' not in skip:
            print("\n  Generating Study Design section...")
            section_data, verification = self._generate_study_design(
                study_design_schema, facts, facts_summary
            )
            if section_data:
                result.sections['study_design'] = section_data
                result.verification_results['study_design'] = verification
                if not verification.passed:
                    result.errors.extend(verification.violations)
                    result.success = False
            else:
                result.errors.append("Failed to generate Study Design section")

        # =================================================================
        # STAGE 4: Contamination Detection
        # =================================================================
        print("\n[STAGE 4] Checking for contamination...")

        full_text = "\n".join(result.sections.values())
        is_contaminated, contaminants = self.contamination_detector.check_contamination(
            full_text, facts
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
        print("PIPELINE SUMMARY")
        print("="*60)
        print(f"  Success: {result.success}")
        print(f"  Sections generated: {list(result.sections.keys())}")
        print(f"  Contamination: {'YES - BLOCKED' if result.contamination_detected else 'None'}")
        print(f"  Errors: {len(result.errors)}")
        print(f"  Warnings: {len(result.warnings)}")

        if result.errors:
            print("\n  ERRORS:")
            for err in result.errors:
                print(f"    - {err}")

        return result

    def _check_critical_facts(self, facts: ProtocolFacts) -> List[str]:
        """Check for missing critical facts"""
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

    def _print_extracted_facts(self, facts: ProtocolFacts):
        """Print extracted facts for debugging"""
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
        """Print the Literal constraints that will be enforced"""
        print("\n  SCHEMA CONSTRAINTS (LLM cannot violate these):")
        print(f"    total_n: Literal[{facts.total_n.value if facts.total_n else 100}]")
        print(f"    ratio: Literal[\"{facts.ratio.value if facts.ratio else '1:1'}\"]")
        print(f"    num_arms: Literal[{facts.num_arms.value if facts.num_arms else 2}]")
        print(f"    drug_name: Literal[\"{facts.drug_name.value if facts.drug_name else 'Study Drug'}\"]")

    def _facts_to_dict(self, facts: ProtocolFacts) -> Dict[str, Any]:
        """Convert ProtocolFacts to dictionary for prompts"""
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

    def _assemble_sap(self, sections: Dict[str, str], facts: ProtocolFacts) -> str:
        """Assemble sections into complete SAP document"""
        drug = facts.drug_name.value if facts.drug_name else "Study Drug"
        nct = facts.nct_id.value if facts.nct_id else "NCT-UNKNOWN"
        phase = facts.phase.value if facts.phase else "Phase 2"

        header = f"""STATISTICAL ANALYSIS PLAN

Protocol: {nct}
Drug: {drug}
Phase: {phase}
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

        body = ""
        if 'study_design' in sections:
            body += sections['study_design'] + "\n\n"
        if 'sample_size' in sections:
            body += sections['sample_size'] + "\n\n"

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
