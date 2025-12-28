#!/usr/bin/env python3
"""
PIPELINE DIAGNOSTIC TRACER
===========================

Traces through the SAP generation pipeline step-by-step to identify
EXACTLY where hallucination/contamination is introduced.

For each step, shows:
- Input values
- Output values
- Whether contamination was detected
- The exact point where wrong values appear
"""

import os
import sys
import re
import json
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Known correct values for TJ301 protocol
EXPECTED_VALUES = {
    'drug_name': 'TJ301',
    'total_n': 90,
    'num_arms': 3,
    'ratio': '1:1:1',
    'per_arm_n': 30,
}

# Known contaminants from RAG examples
CONTAMINANTS = {
    'drug_names': ['etrolizumab', 'GA29144', 'GA29145', 'PRO145223', 'tocilizumab'],
    'sample_sizes': [1150, 769, 728, 600, 500, 400, 300],
    'ratios': ['1:2:2', '2:1', '1:1:1:1', '3:1'],
}


def print_step(step_num: int, step_name: str, status: str = ""):
    """Print a step header"""
    icon = "✓" if status == "ok" else "✗" if status == "fail" else "→"
    print(f"\n{'='*60}")
    print(f"[{icon}] STEP {step_num}: {step_name}")
    print(f"{'='*60}")


def check_for_contamination(text: str, field_name: str = "") -> list:
    """Check text for known contaminants"""
    found = []

    for drug in CONTAMINANTS['drug_names']:
        if drug.lower() in text.lower():
            found.append(f"CONTAMINANT DRUG: {drug}")

    for size in CONTAMINANTS['sample_sizes']:
        if str(size) in text:
            found.append(f"CONTAMINANT SIZE: {size}")

    for ratio in CONTAMINANTS['ratios']:
        if ratio in text and ratio != '1:1:1':
            found.append(f"CONTAMINANT RATIO: {ratio}")

    return found


def trace_pipeline(protocol_text: str, nct_id: str = ""):
    """Trace through the pipeline step by step"""

    print("\n" + "="*70)
    print("PIPELINE DIAGNOSTIC TRACE")
    print("="*70)
    print(f"Expected values: {EXPECTED_VALUES}")
    print("="*70)

    contamination_points = []

    # ========================================================================
    # STEP 0: RAW PROTOCOL INPUT
    # ========================================================================
    print_step(0, "RAW PROTOCOL INPUT")

    # Check what values are in the raw protocol
    drug_match = re.search(r'(?:Investigational\s+Product|IMP)[:\s]+([A-Za-z][A-Za-z0-9-]+)', protocol_text, re.I)
    sample_match = re.search(r'(\d{2,4})\s+(?:patients?|subjects?)', protocol_text, re.I)
    ratio_match = re.search(r'\b(\d+:\d+(?::\d+)*)\b', protocol_text)

    print(f"  Drug in protocol: {drug_match.group(1) if drug_match else 'NOT FOUND'}")
    print(f"  Sample size in protocol: {sample_match.group(1) if sample_match else 'NOT FOUND'}")
    print(f"  Ratio in protocol: {ratio_match.group(1) if ratio_match else 'NOT FOUND'}")

    contam = check_for_contamination(protocol_text[:5000], "raw_protocol")
    if contam:
        print(f"  ⚠️ CONTAMINATION IN RAW PROTOCOL: {contam}")
        contamination_points.append(("Step 0: Raw Protocol", contam))
    else:
        print(f"  ✓ No contamination in raw protocol")

    # ========================================================================
    # STEP 1: STRUCTURED FACT EXTRACTION (Regex)
    # ========================================================================
    print_step(1, "STRUCTURED FACT EXTRACTION (StructuredFactExtractor)")

    try:
        from enterprise_sap_system.core.structured_extractor import StructuredFactExtractor
        extractor = StructuredFactExtractor()
        facts = extractor.extract_all(protocol_text)

        print(f"  Extracted drug_name: {facts.drug_name}")
        print(f"  Extracted total_n: {facts.sample_size.total_n if facts.sample_size else 'NONE'}")
        print(f"  Extracted num_arms: {facts.num_arms}")
        print(f"  Extracted ratio: {facts.randomization_ratio}")
        print(f"  Extracted arms: {[a.name for a in facts.arms] if facts.arms else []}")

        # Check if extraction is correct
        issues = []
        if facts.drug_name and facts.drug_name != EXPECTED_VALUES['drug_name']:
            issues.append(f"Wrong drug: {facts.drug_name} (expected {EXPECTED_VALUES['drug_name']})")
        if facts.sample_size and facts.sample_size.total_n != EXPECTED_VALUES['total_n']:
            issues.append(f"Wrong N: {facts.sample_size.total_n} (expected {EXPECTED_VALUES['total_n']})")
        if facts.randomization_ratio and facts.randomization_ratio != EXPECTED_VALUES['ratio']:
            issues.append(f"Wrong ratio: {facts.randomization_ratio} (expected {EXPECTED_VALUES['ratio']})")

        if issues:
            print(f"  ✗ EXTRACTION ERRORS: {issues}")
            contamination_points.append(("Step 1: Structured Extraction", issues))
        else:
            print(f"  ✓ Extraction looks correct")

    except Exception as e:
        print(f"  ✗ EXTRACTION FAILED: {e}")
        facts = None

    # ========================================================================
    # STEP 2: PROTOCOL PARSER (LLM-based)
    # ========================================================================
    print_step(2, "PROTOCOL PARSER (ProtocolParser - uses LLM)")

    try:
        from enterprise_sap_system.core.protocol_parser import ProtocolParser
        parser = ProtocolParser()

        # This is where LLM is first called!
        print("  Calling LLM to parse protocol...")
        parsed = parser.parse(protocol_text, nct_id)

        print(f"  Parsed study_title: {parsed.study_title[:80] if parsed.study_title else 'NONE'}...")
        print(f"  Parsed phase: {parsed.phase}")
        print(f"  Parsed therapeutic_area: {parsed.therapeutic_area}")
        print(f"  Parsed arms: {[a.name for a in parsed.arms] if parsed.arms else []}")
        print(f"  Parsed sample_size: {parsed.sample_size.total_n if parsed.sample_size else 'NONE'}")

        # Check for contamination in parsed output
        parsed_str = str(parsed)
        contam = check_for_contamination(parsed_str, "parsed_protocol")
        if contam:
            print(f"  ⚠️ CONTAMINATION IN PARSER OUTPUT: {contam}")
            contamination_points.append(("Step 2: Protocol Parser (LLM)", contam))
        else:
            print(f"  ✓ No contamination in parser output")

    except Exception as e:
        print(f"  ✗ PARSER FAILED: {e}")
        parsed = None

    # ========================================================================
    # STEP 3: RAG RETRIEVAL
    # ========================================================================
    print_step(3, "RAG RETRIEVAL (Similar SAP Examples)")

    try:
        from enterprise_sap_system.core.rag_system import RAGSystem
        rag = RAGSystem()
        num_pairs = rag.load_and_filter_pairs()

        if num_pairs > 0:
            rag.create_embeddings()

            # Retrieve similar protocols
            similar = rag.retrieve_similar(
                query_protocol=protocol_text[:5000],
                k=2
            )

            print(f"  Retrieved {len(similar)} similar SAPs")
            for pair in similar:
                print(f"    - {pair.nct_id}: {pair.therapeutic_area}")

                # Check each retrieved example for contaminating values
                contam_in_example = check_for_contamination(pair.sap_text[:2000], f"RAG example {pair.nct_id}")
                if contam_in_example:
                    print(f"      ⚠️ THIS EXAMPLE CONTAINS: {contam_in_example}")

            # Format few-shot examples WITHOUT sanitization
            raw_examples = rag.format_few_shot_examples(similar, sanitize=False)
            print(f"\n  RAW few-shot examples (first 500 chars):")
            print(f"  {raw_examples[:500]}...")

            contam = check_for_contamination(raw_examples, "raw_rag_examples")
            if contam:
                print(f"\n  ⚠️ CONTAMINATION IN RAW RAG EXAMPLES: {contam}")
                contamination_points.append(("Step 3: RAG Examples (unsanitized)", contam))

            # Format few-shot examples WITH sanitization
            sanitized_examples = rag.format_few_shot_examples(similar, sanitize=True)
            print(f"\n  SANITIZED few-shot examples (first 500 chars):")
            print(f"  {sanitized_examples[:500]}...")

            contam_sanitized = check_for_contamination(sanitized_examples, "sanitized_rag_examples")
            if contam_sanitized:
                print(f"\n  ⚠️ CONTAMINATION STILL IN SANITIZED EXAMPLES: {contam_sanitized}")
                contamination_points.append(("Step 3: RAG Examples (sanitized)", contam_sanitized))
            else:
                print(f"\n  ✓ Sanitization removed contaminants")
        else:
            print(f"  No RAG pairs available")

    except Exception as e:
        print(f"  ✗ RAG FAILED: {e}")
        import traceback
        traceback.print_exc()

    # ========================================================================
    # STEP 4: ESTIMAND AGENT (LLM)
    # ========================================================================
    print_step(4, "ESTIMAND ARCHITECT AGENT (LLM)")

    if parsed:
        try:
            from enterprise_sap_system.agents.specialized_agents import EstimandArchitectAgent
            estimand_agent = EstimandArchitectAgent()

            print("  Calling LLM to design estimands...")
            estimands = estimand_agent.execute(parsed_protocol=parsed, knowledge_context="")

            estimand_str = json.dumps(estimands, default=str)[:2000]
            print(f"  Estimand output preview: {estimand_str[:500]}...")

            contam = check_for_contamination(estimand_str, "estimands")
            if contam:
                print(f"  ⚠️ CONTAMINATION IN ESTIMANDS: {contam}")
                contamination_points.append(("Step 4: Estimand Agent (LLM)", contam))
            else:
                print(f"  ✓ No contamination in estimands")

        except Exception as e:
            print(f"  ✗ ESTIMAND AGENT FAILED: {e}")
            estimands = None
    else:
        print("  Skipped (no parsed protocol)")
        estimands = None

    # ========================================================================
    # STEP 5: METHODS AGENT (LLM)
    # ========================================================================
    print_step(5, "METHODS SELECTOR AGENT (LLM)")

    if parsed and estimands:
        try:
            from enterprise_sap_system.agents.specialized_agents import MethodsSelectorAgent
            methods_agent = MethodsSelectorAgent()

            print("  Calling LLM to select methods...")
            methods = methods_agent.execute(
                parsed_protocol=parsed,
                estimands=estimands,
                knowledge_context=""
            )

            methods_str = json.dumps(methods, default=str)[:2000]
            print(f"  Methods output preview: {methods_str[:500]}...")

            contam = check_for_contamination(methods_str, "methods")
            if contam:
                print(f"  ⚠️ CONTAMINATION IN METHODS: {contam}")
                contamination_points.append(("Step 5: Methods Agent (LLM)", contam))
            else:
                print(f"  ✓ No contamination in methods")

        except Exception as e:
            print(f"  ✗ METHODS AGENT FAILED: {e}")
            methods = None
    else:
        print("  Skipped (no parsed protocol or estimands)")
        methods = None

    # ========================================================================
    # STEP 6: SAP WRITER AGENT (LLM)
    # ========================================================================
    print_step(6, "SAP WRITER AGENT (LLM) - MAIN GENERATION")

    if parsed:
        try:
            from enterprise_sap_system.agents.specialized_agents import SAPWriterAgent
            writer_agent = SAPWriterAgent()

            # Get RAG context that would be passed
            rag_context = ""
            if 'sanitized_examples' in dir():
                rag_context = sanitized_examples if sanitized_examples else ""

            print(f"  RAG context length: {len(rag_context)} chars")
            print(f"  RAG context preview: {rag_context[:300]}...")

            # Generate sample size section (most problematic)
            print("\n  Generating Section 6: Sample Size...")
            section = writer_agent.execute(
                section_name="6_sample_size",
                parsed_protocol=parsed,
                estimands=estimands or {},
                methods=methods or {},
                few_shot_examples=[],
                knowledge_context=rag_context
            )

            print(f"\n  GENERATED SECTION OUTPUT:")
            print(f"  {'-'*50}")
            print(f"  {section[:1500]}...")
            print(f"  {'-'*50}")

            contam = check_for_contamination(section, "generated_section")
            if contam:
                print(f"\n  ⚠️ CONTAMINATION IN GENERATED SAP: {contam}")
                contamination_points.append(("Step 6: SAP Writer Agent (LLM)", contam))
            else:
                print(f"\n  ✓ No contamination in generated section")

            # Check for correct values
            if str(EXPECTED_VALUES['total_n']) in section:
                print(f"  ✓ Contains correct sample size: {EXPECTED_VALUES['total_n']}")
            else:
                print(f"  ✗ Missing correct sample size: {EXPECTED_VALUES['total_n']}")

            if EXPECTED_VALUES['ratio'] in section:
                print(f"  ✓ Contains correct ratio: {EXPECTED_VALUES['ratio']}")
            else:
                print(f"  ✗ Missing correct ratio: {EXPECTED_VALUES['ratio']}")

        except Exception as e:
            print(f"  ✗ WRITER AGENT FAILED: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("  Skipped (no parsed protocol)")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "="*70)
    print("DIAGNOSTIC SUMMARY")
    print("="*70)

    if contamination_points:
        print("\n⚠️ CONTAMINATION DETECTED AT THESE STEPS:")
        for step, issues in contamination_points:
            print(f"\n  [{step}]")
            for issue in issues:
                print(f"    - {issue}")

        print("\n" + "-"*70)
        first_contamination = contamination_points[0][0]
        print(f"FIRST CONTAMINATION POINT: {first_contamination}")
        print("-"*70)
        print("\nThis is where you need to focus your fix!")
    else:
        print("\n✓ No contamination detected in traced steps")

    return contamination_points


if __name__ == "__main__":
    # Read protocol from file or use test text
    if len(sys.argv) > 1:
        protocol_file = sys.argv[1]
        with open(protocol_file, 'r') as f:
            protocol_text = f.read()
    else:
        # Use a minimal test protocol with TJ301 values
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

3. SAMPLE SIZE
Total sample size: 90 patients
Power: 80%
Alpha: 0.05 (one-sided)

4. INDICATION
Ulcerative Colitis (moderate to severe)
"""
        print("Using test protocol with TJ301 values...")

    trace_pipeline(protocol_text, nct_id="NCT02394028")
