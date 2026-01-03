#!/usr/bin/env python3
"""
PIPELINE DIAGNOSTIC WITH SIMULATED RAG
=======================================

Simulates what happens when RAG provides examples with contaminating values
to identify exactly where contamination enters the final SAP.
"""

import os
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Known correct values for TJ301 protocol
EXPECTED = {
    'drug': 'TJ301',
    'n': 90,
    'ratio': '1:1:1',
    'arms': 3,
}

# Contaminating values from RAG
CONTAMINANT = {
    'drug': 'etrolizumab',
    'study_id': 'GA29144',
    'n': 1150,
    'ratio': '1:2:2',
}


def print_header(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def check_values(text: str, label: str):
    """Check what values appear in text"""
    print(f"\n  [{label}] Value Check:")

    # Check for expected vs contaminating values
    has_correct_n = str(EXPECTED['n']) in text
    has_wrong_n = str(CONTAMINANT['n']) in text
    has_correct_drug = EXPECTED['drug'].lower() in text.lower()
    has_wrong_drug = CONTAMINANT['drug'].lower() in text.lower()
    has_correct_ratio = EXPECTED['ratio'] in text
    has_wrong_ratio = CONTAMINANT['ratio'] in text

    print(f"    Drug: {'✓ ' + EXPECTED['drug'] if has_correct_drug else ''}{'✗ ' + CONTAMINANT['drug'] if has_wrong_drug else ''}")
    print(f"    Sample N: {'✓ ' + str(EXPECTED['n']) if has_correct_n else ''}{'✗ ' + str(CONTAMINANT['n']) if has_wrong_n else ''}")
    print(f"    Ratio: {'✓ ' + EXPECTED['ratio'] if has_correct_ratio else ''}{'✗ ' + CONTAMINANT['ratio'] if has_wrong_ratio else ''}")

    # Return contamination status
    is_contaminated = has_wrong_n or has_wrong_drug or has_wrong_ratio
    return is_contaminated, {
        'has_correct_n': has_correct_n,
        'has_wrong_n': has_wrong_n,
        'has_correct_drug': has_correct_drug,
        'has_wrong_drug': has_wrong_drug,
        'has_correct_ratio': has_correct_ratio,
        'has_wrong_ratio': has_wrong_ratio,
    }


def run_diagnostic():
    """Run step-by-step diagnostic"""

    # TJ301 Protocol text
    protocol_text = """
CLINICAL TRIAL PROTOCOL

Study ID: CTJ301UC201
ClinicalTrials.gov ID: NCT02394028

1. INVESTIGATIONAL PRODUCT
Investigational Product: TJ301 (FE 999301)
Generic Name: olamkicept

2. STUDY DESIGN
This is a Phase 2, randomized, double-blind, placebo-controlled study.

A total of 90 patients will be randomized in a 1:1:1 ratio to receive:
- Arm A: TJ301 600mg IV every 2 weeks
- Arm B: TJ301 300mg IV every 2 weeks
- Arm C: Placebo IV every 2 weeks

Each arm will have approximately 30 patients.

Route of administration: intravenous (IV)

3. SAMPLE SIZE
Total sample size: 90 patients
Power: 80%
Alpha: 0.05 (one-sided)

4. PRIMARY ENDPOINT
Clinical response at Week 12 defined as reduction in Mayo score.

5. INDICATION
Ulcerative Colitis (moderate to severe)
"""

    # Simulated RAG example (contaminating)
    rag_example = """
## Similar SAP Example (from GA29144)

Protocol: GA29144
Drug: etrolizumab
Sample size: 1150 patients randomized 1:2:2 to:
- Placebo (N=230)
- etrolizumab 105mg (N=460)
- etrolizumab 210mg (N=460)

Section 6: Sample Size
The study will enroll 1150 patients with a randomization ratio of 1:2:2.
Power is 90% with two-sided alpha of 0.05.
"""

    contamination_points = []

    # ========================================================================
    print_header("STEP 0: RAW PROTOCOL")
    # ========================================================================
    is_contaminated, _ = check_values(protocol_text, "Protocol Text")
    if is_contaminated:
        contamination_points.append("Step 0: Raw Protocol")
        print("    ⚠️ CONTAMINATION IN RAW PROTOCOL")
    else:
        print("    ✓ Protocol is clean")

    # ========================================================================
    print_header("STEP 1: STRUCTURED EXTRACTION")
    # ========================================================================
    try:
        from enterprise_sap_system.core.schemas import StructuredFactExtractor
        extractor = StructuredFactExtractor()
        facts = extractor.extract_all(protocol_text)

        print(f"\n  Extracted values:")
        print(f"    drug_name: {facts.drug_name}")
        print(f"    total_n: {facts.sample_size.total_n if facts.sample_size else 'NONE'}")
        print(f"    num_arms: {facts.num_arms}")
        print(f"    ratio: {facts.randomization_ratio}")

        extraction_str = f"{facts.drug_name} {facts.sample_size.total_n if facts.sample_size else ''} {facts.randomization_ratio}"
        is_contaminated, _ = check_values(extraction_str, "Extraction")

        if facts.drug_name != EXPECTED['drug']:
            print(f"    ⚠️ WRONG DRUG EXTRACTED: {facts.drug_name}")
            contamination_points.append("Step 1: Wrong drug extracted")
        if facts.sample_size and facts.sample_size.total_n != EXPECTED['n']:
            print(f"    ⚠️ WRONG N EXTRACTED: {facts.sample_size.total_n}")
            contamination_points.append("Step 1: Wrong N extracted")
        if facts.randomization_ratio != EXPECTED['ratio']:
            print(f"    ⚠️ WRONG RATIO EXTRACTED: {facts.randomization_ratio}")
            contamination_points.append("Step 1: Wrong ratio extracted")

    except Exception as e:
        print(f"  ✗ Extraction failed: {e}")
        facts = None

    # ========================================================================
    print_header("STEP 2: RAG CONTEXT (Simulated)")
    # ========================================================================
    print(f"\n  RAG Example being passed to LLM:")
    print(f"  {'-'*50}")
    print(f"  {rag_example[:500]}")
    print(f"  {'-'*50}")

    is_contaminated, details = check_values(rag_example, "RAG Example")
    if is_contaminated:
        print("    ⚠️ RAG EXAMPLE CONTAINS CONTAMINATING VALUES")
        contamination_points.append("Step 2: RAG example has contamination")

    # ========================================================================
    print_header("STEP 3: SAP GENERATION (with RAG context)")
    # ========================================================================

    try:
        from enterprise_sap_system.agents.specialized_agents import SAPWriterAgent
        from enterprise_sap_system.core.schemas import ParsedProtocol, StudyPhase, SampleSizeCalc, TreatmentArm

        # Build parsed protocol from facts
        parsed = ParsedProtocol(
            nct_id="NCT02394028",
            study_title="Study of TJ301 in UC",
            phase=StudyPhase.PHASE_2,
            therapeutic_area="Immunology",
        )
        parsed.sample_size = SampleSizeCalc(
            total_n=90,
            power=0.80,
            alpha=0.05,
            per_arm_n={"Arm A": 30, "Arm B": 30, "Arm C": 30}
        )
        parsed.arms = [
            TreatmentArm(name="Arm A", description="TJ301 600mg IV", dose="600mg", route="IV"),
            TreatmentArm(name="Arm B", description="TJ301 300mg IV", dose="300mg", route="IV"),
            TreatmentArm(name="Arm C", description="Placebo IV", is_control=True),
        ]

        writer = SAPWriterAgent()

        # Case A: WITHOUT RAG context
        print("\n  [Case A] Generating WITHOUT RAG context...")
        section_no_rag = writer.execute(
            section_name="6_sample_size",
            parsed_protocol=parsed,
            estimands={},
            methods={},
            few_shot_examples=[],
            knowledge_context=""  # No RAG
        )

        print(f"\n  OUTPUT (no RAG):")
        print(f"  {'-'*50}")
        print(f"  {section_no_rag[:800]}")
        print(f"  {'-'*50}")

        is_contaminated_no_rag, details_no_rag = check_values(section_no_rag, "SAP without RAG")
        if is_contaminated_no_rag:
            contamination_points.append("Step 3a: SAP (no RAG) contaminated")

        # Case B: WITH RAG context
        print("\n\n  [Case B] Generating WITH contaminated RAG context...")
        section_with_rag = writer.execute(
            section_name="6_sample_size",
            parsed_protocol=parsed,
            estimands={},
            methods={},
            few_shot_examples=[],
            knowledge_context=rag_example  # With contaminating RAG
        )

        print(f"\n  OUTPUT (with RAG):")
        print(f"  {'-'*50}")
        print(f"  {section_with_rag[:800]}")
        print(f"  {'-'*50}")

        is_contaminated_with_rag, details_with_rag = check_values(section_with_rag, "SAP with RAG")
        if is_contaminated_with_rag:
            contamination_points.append("Step 3b: SAP (with RAG) contaminated")

        # ========================================================================
        print_header("COMPARISON: RAG Impact")
        # ========================================================================
        print("\n  Without RAG:")
        print(f"    Has correct N (90): {details_no_rag['has_correct_n']}")
        print(f"    Has wrong N (1150): {details_no_rag['has_wrong_n']}")
        print(f"    Has correct ratio (1:1:1): {details_no_rag['has_correct_ratio']}")
        print(f"    Has wrong ratio (1:2:2): {details_no_rag['has_wrong_ratio']}")

        print("\n  With RAG:")
        print(f"    Has correct N (90): {details_with_rag['has_correct_n']}")
        print(f"    Has wrong N (1150): {details_with_rag['has_wrong_n']}")
        print(f"    Has correct ratio (1:1:1): {details_with_rag['has_correct_ratio']}")
        print(f"    Has wrong ratio (1:2:2): {details_with_rag['has_wrong_ratio']}")

        if details_with_rag['has_wrong_n'] and not details_no_rag['has_wrong_n']:
            print("\n  ⚠️ CONFIRMED: RAG context is introducing contamination!")
            print("     The LLM copies values from RAG examples instead of using protocol values.")

    except Exception as e:
        print(f"  ✗ Generation failed: {e}")
        import traceback
        traceback.print_exc()

    # ========================================================================
    print_header("DIAGNOSTIC SUMMARY")
    # ========================================================================
    print("\n  Contamination detected at:")
    for point in contamination_points:
        print(f"    - {point}")

    print("\n  ROOT CAUSE ANALYSIS:")
    print("  " + "-"*50)
    print("  The LLM is trained to follow examples.")
    print("  When RAG provides examples with specific values (1150, 1:2:2),")
    print("  the LLM mimics those values even when the protocol says otherwise.")
    print("")
    print("  SOLUTION: Schema-constrained generation")
    print("  - Use Pydantic Literal types: total_n: Literal[90]")
    print("  - LLM cannot output 1150 - it's not in the type!")
    print("  " + "-"*50)


if __name__ == "__main__":
    run_diagnostic()
