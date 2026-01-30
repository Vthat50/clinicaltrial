#!/usr/bin/env python3
"""
ORCHESTRATOR DIAGNOSTIC
=======================

Traces the ACTUAL orchestrator pipeline to find where contamination enters.
"""

import os
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Expected values
EXPECTED = {'drug': 'TJ301', 'n': 90, 'ratio': '1:1:1'}
CONTAMINANTS = ['etrolizumab', 'GA29144', 'GA29145', '1150', '1:2:2', '769', '728']


def check_contamination(text: str, label: str) -> bool:
    """Check for contaminating values"""
    found = []
    text_lower = text.lower()
    for c in CONTAMINANTS:
        if c.lower() in text_lower:
            found.append(c)
    if found:
        print(f"  ⚠️ [{label}] CONTAMINATION: {found}")
        return True
    return False


def check_correct(text: str, label: str):
    """Check for correct values"""
    has_drug = EXPECTED['drug'].lower() in text.lower()
    has_n = str(EXPECTED['n']) in text
    has_ratio = EXPECTED['ratio'] in text
    print(f"  [{label}] Correct values: drug={has_drug}, n={has_n}, ratio={has_ratio}")
    return has_drug, has_n, has_ratio


def run():
    """Run orchestrator with tracing"""

    protocol_text = """
CLINICAL TRIAL PROTOCOL

Study ID: CTJ301UC201
ClinicalTrials.gov ID: NCT02394028

1. INVESTIGATIONAL PRODUCT
Investigational Product: TJ301 (FE 999301)
Generic Name: olamkicept

2. STUDY DESIGN
This is a Phase 2, randomized, double-blind, placebo-controlled study in patients
with moderate to severe ulcerative colitis.

A total of 90 patients will be randomized in a 1:1:1 ratio to receive:
- Arm A: TJ301 600mg IV every 2 weeks
- Arm B: TJ301 300mg IV every 2 weeks
- Arm C: Placebo IV every 2 weeks

Route of administration: intravenous (IV)

3. SAMPLE SIZE
Total sample size: 90 patients (30 per arm)
Power: 80%
Alpha: 0.05 (one-sided)
Dropout rate: 10%

4. PRIMARY ENDPOINT
Clinical response at Week 12 defined as reduction in Mayo score >= 3 points
and >= 30% reduction from baseline.

5. STRATIFICATION
Stratification factors:
- Prior biologic use (yes/no)
- Baseline disease severity (moderate/severe)

6. INDICATION
Ulcerative Colitis
"""

    print("\n" + "="*70)
    print("ORCHESTRATOR DIAGNOSTIC")
    print("="*70)
    print(f"Expected: {EXPECTED}")
    print("="*70)

    # ========================================================================
    # STEP 1: Test PRODUCTION mode
    # ========================================================================
    print("\n\n### TESTING PRODUCTION MODE ###\n")

    try:
        from enterprise_sap_system.agents.orchestrator import SAPGenerationOrchestrator

        print("Creating orchestrator...")
        orchestrator = SAPGenerationOrchestrator(use_rag=True)

        print("\n--- Generating with PRODUCTION mode ---")
        result = orchestrator.generate_sap(
            protocol_text=protocol_text,
            nct_id="NCT02394028",
            production_mode=True,
            constrained_mode=False,  # Use production, not constrained
            verbose=True
        )

        if result.success:
            sap_text = result.sap_document.full_document

            print("\n\n### PRODUCTION MODE RESULT ###")
            print("="*70)

            # Check for contamination
            contaminated = check_contamination(sap_text, "Full SAP")

            # Check for correct values
            check_correct(sap_text, "Full SAP")

            # Print sample size section specifically
            print("\n--- Sample Size Section ---")
            for section_name, content in result.sap_document.sections.items():
                if 'sample' in section_name.lower() or '6' in section_name:
                    print(f"\n[{section_name}]")
                    print(content[:1500])
                    check_contamination(content, section_name)
                    check_correct(content, section_name)

        else:
            print(f"FAILED: {result.errors}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    # ========================================================================
    # STEP 2: Test CONSTRAINED mode
    # ========================================================================
    print("\n\n### TESTING CONSTRAINED MODE ###\n")

    try:
        print("--- Generating with CONSTRAINED mode ---")
        result2 = orchestrator.generate_sap(
            protocol_text=protocol_text,
            nct_id="NCT02394028",
            production_mode=False,
            constrained_mode=True,  # Use new constrained mode
            verbose=True
        )

        if result2.success:
            sap_text2 = result2.sap_document.full_document

            print("\n\n### CONSTRAINED MODE RESULT ###")
            print("="*70)

            # Check for contamination
            contaminated2 = check_contamination(sap_text2, "Full SAP")

            # Check for correct values
            check_correct(sap_text2, "Full SAP")

        else:
            print(f"FAILED: {result2.errors}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    # ========================================================================
    # STEP 3: Test LEGACY mode (for comparison)
    # ========================================================================
    print("\n\n### TESTING LEGACY MODE ###\n")

    try:
        print("--- Generating with LEGACY mode ---")
        result3 = orchestrator.generate_sap(
            protocol_text=protocol_text,
            nct_id="NCT02394028",
            production_mode=False,
            constrained_mode=False,  # Force legacy mode
            verbose=True
        )

        if result3.success:
            sap_text3 = result3.sap_document.full_document

            print("\n\n### LEGACY MODE RESULT ###")
            print("="*70)

            # Check for contamination
            contaminated3 = check_contamination(sap_text3, "Full SAP")

            # Check for correct values
            check_correct(sap_text3, "Full SAP")

            # Print first 2000 chars to see what's happening
            print("\n--- SAP Preview ---")
            print(sap_text3[:2000])

        else:
            print(f"FAILED: {result3.errors}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run()
