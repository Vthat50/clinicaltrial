#!/usr/bin/env python3
"""
Test Code Generators
====================

Tests the SAS code generation pipeline with sample protocol facts.
"""

import os
import sys
import tempfile

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code_generators import CodeGenerationOrchestrator


def get_sample_protocol_facts():
    """Sample protocol facts for IBD trial."""
    return {
        "protocol_id": "ABC-123-IBD",
        "therapeutic_area": "ibd",
        "indication": "Ulcerative Colitis",
        "phase": "Phase 3",
        "treatments": [
            {"name": "Placebo", "code": "PBO", "n": "1"},
            {"name": "Drug X 200mg", "code": "DRG200", "n": "2"},
            {"name": "Drug X 400mg", "code": "DRG400", "n": "3"},
        ],
        "primary_endpoint": {
            "name": "Clinical Remission at Week 12",
            "parameter": "CLREMIS",
            "type": "binary",
            "definition": "Mayo score <=2 with no individual subscore >1"
        },
        "secondary_endpoints": [
            {
                "name": "Endoscopic Improvement",
                "parameter": "ENDOIMP",
                "type": "binary"
            },
            {
                "name": "Clinical Response",
                "parameter": "CLRESP",
                "type": "binary"
            },
        ],
        "primary_timepoint": {
            "visit": "Week 12",
            "avisit": "WEEK 12",
            "avisitn": 12
        },
        "populations": {
            "ITT": "All randomized subjects",
            "Safety": "All subjects who received at least one dose",
            "Per-Protocol": "All ITT subjects without major protocol violations"
        },
        "efficacy_population": "ITTFL",
        "safety_population": "SAFFL",
        "demographics_population": "SAFFL",
        "stratification_factors": [
            "Prior biologic use (Yes/No)",
            "Baseline disease severity (Moderate/Severe)"
        ],
    }


def test_full_generation():
    """Test full code generation pipeline."""
    print("=" * 60)
    print("Testing SAS Code Generation Pipeline")
    print("=" * 60)

    # Get sample protocol facts
    facts = get_sample_protocol_facts()
    print(f"\nProtocol: {facts['protocol_id']}")
    print(f"Therapeutic Area: {facts['therapeutic_area']}")
    print(f"Treatments: {len(facts['treatments'])} arms")

    # Initialize orchestrator
    orchestrator = CodeGenerationOrchestrator()

    # Generate all programs
    print("\nGenerating programs...")
    package = orchestrator.generate_all(facts)

    # Summary
    print(f"\n{'=' * 60}")
    print("GENERATION SUMMARY")
    print(f"{'=' * 60}")
    print(f"Protocol ID: {package.protocol_id}")
    print(f"Generated At: {package.generated_at}")
    print(f"Therapeutic Area: {package.therapeutic_area}")

    print(f"\nADaM Programs ({len(package.adam_programs)}):")
    for prog in package.adam_programs:
        print(f"  - {prog.program_name}: {prog.description}")
        print(f"    Inputs: {', '.join(prog.input_datasets)}")
        print(f"    Outputs: {', '.join(prog.output_datasets)}")

    print(f"\nTLF Programs ({len(package.tlf_programs)}):")
    for prog in package.tlf_programs:
        print(f"  - {prog.program_name}: {prog.description}")
        print(f"    Inputs: {', '.join(prog.input_datasets)}")

    # Show sample code
    print(f"\n{'=' * 60}")
    print("SAMPLE CODE PREVIEW (ADSL - first 50 lines)")
    print(f"{'=' * 60}")
    adsl_code = package.adam_programs[0].code
    for i, line in enumerate(adsl_code.split('\n')[:50], 1):
        print(f"{i:4d}  {line}")
    print("...")

    # Save to temp directory
    print(f"\n{'=' * 60}")
    print("SAVING TO TEMP DIRECTORY")
    print(f"{'=' * 60}")

    with tempfile.TemporaryDirectory() as tmpdir:
        saved = orchestrator.save_to_directory(package, tmpdir)
        print(f"Saved {len(saved)} files to: {tmpdir}")
        for name, path in saved.items():
            size = os.path.getsize(path)
            print(f"  - {name}: {size:,} bytes")

    # Validation checklist
    print(f"\n{'=' * 60}")
    print("VALIDATION CHECKLIST")
    print(f"{'=' * 60}")
    for item in package.validation_checklist[:15]:
        print(item)
    print("... (truncated)")

    print(f"\n{'=' * 60}")
    print("TEST COMPLETED SUCCESSFULLY")
    print(f"{'=' * 60}")

    return package


def test_individual_generators():
    """Test individual generators."""
    from code_generators.adam import ADSLGenerator, ADAEGenerator, ADTTEGenerator, ADEFFGenerator
    from code_generators.tlf import DemographicsTableGenerator, AESummaryTableGenerator, PrimaryEfficacyTableGenerator

    facts = get_sample_protocol_facts()

    print("\n" + "=" * 60)
    print("Testing Individual Generators")
    print("=" * 60)

    generators = [
        ("ADSLGenerator", ADSLGenerator()),
        ("ADAEGenerator", ADAEGenerator()),
        ("ADTTEGenerator", ADTTEGenerator()),
        ("ADEFFGenerator", ADEFFGenerator()),
        ("DemographicsTableGenerator", DemographicsTableGenerator()),
        ("AESummaryTableGenerator", AESummaryTableGenerator()),
        ("PrimaryEfficacyTableGenerator", PrimaryEfficacyTableGenerator()),
    ]

    for name, gen in generators:
        result = gen.generate(facts)
        lines = len(result.code.split('\n'))
        print(f"  {name}: {result.program_name} ({lines} lines)")

    print("\nAll individual generators working correctly!")


if __name__ == "__main__":
    test_individual_generators()
    test_full_generation()
