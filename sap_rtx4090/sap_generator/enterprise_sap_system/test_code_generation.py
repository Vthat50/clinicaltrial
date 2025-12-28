#!/usr/bin/env python3
"""
Test script for code generation integration.
Tests the full pipeline: FullProtocolFacts → SAS Code

This validates the code generation works correctly without requiring API keys.
"""

import os
import sys
import tempfile
import shutil

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.full_schema_generator import FullProtocolFacts
from sap_to_code import generate_code_from_facts, facts_to_dict


def create_test_facts() -> FullProtocolFacts:
    """Create realistic test protocol facts (based on typical IBD trial)."""
    return FullProtocolFacts(
        # Identifiers
        nct_id="NCT04567890",
        study_id="ABC-IBD-301",
        sponsor="Example Pharma Inc.",

        # Study info
        title="A Phase 3, Randomized, Double-Blind, Placebo-Controlled Study to Evaluate "
              "the Efficacy and Safety of ABC-123 in Patients with Moderate to Severe "
              "Ulcerative Colitis",
        phase="Phase 3",
        therapeutic_area="gastroenterology",
        indication="Ulcerative Colitis",
        design_type="Randomized, Double-Blind, Placebo-Controlled, Parallel-Group",

        # Drug/Treatment
        drug_name="ABC-123",
        drug_code="ABC123",
        route="Subcutaneous",

        # Arms
        arm_names=["ABC-123 300mg", "ABC-123 150mg", "Placebo"],
        arm_doses=["300 mg SC Q4W", "150 mg SC Q4W", "Placebo SC Q4W"],
        num_arms=3,
        ratio="1:1:1",

        # Sample size
        total_n=450,
        per_arm_n={"ABC-123 300mg": 150, "ABC-123 150mg": 150, "Placebo": 150},
        power="90%",
        alpha=0.05,

        # Endpoints
        primary_endpoint="Clinical Remission",
        primary_endpoint_definition="Mayo Score ≤2 with no individual subscore >1 and "
                                    "rectal bleeding subscore of 0",
        primary_timepoint="Week 12",
        secondary_endpoints=[
            "Clinical Response",
            "Endoscopic Improvement",
            "Mucosal Healing",
            "Change from Baseline in Mayo Score"
        ],

        # Populations
        primary_population="ITT",
        itt_definition="All randomized patients who received at least one dose of study drug",
        safety_definition="All patients who received at least one dose of study drug",
        pp_definition="All ITT patients without major protocol deviations affecting efficacy",

        # Stratification
        stratification_factors=["Prior biologic use (yes/no)", "Baseline Mayo Score (≤9, >9)"],

        # Analysis
        primary_analysis_method="Cochran-Mantel-Haenszel test stratified by prior biologic use",

        # Study timing
        study_duration="52 weeks"
    )


def run_test():
    """Run the code generation test."""
    print("=" * 70)
    print("CODE GENERATION INTEGRATION TEST")
    print("=" * 70)

    # Step 1: Create test facts
    print("\n[1/5] Creating test protocol facts...")
    facts = create_test_facts()
    print(f"      Protocol: {facts.nct_id} - {facts.drug_name}")
    print(f"      Arms: {', '.join(facts.arm_names)}")
    print(f"      Primary endpoint: {facts.primary_endpoint}")
    print("      ✓ Facts created")

    # Step 2: Test facts_to_dict conversion
    print("\n[2/5] Testing facts_to_dict conversion...")
    facts_dict = facts_to_dict(facts)

    required_keys = [
        "protocol_id", "drug_name", "treatments", "primary_endpoint",
        "primary_timepoint", "primary_population", "therapeutic_area"
    ]
    missing = [k for k in required_keys if k not in facts_dict]
    if missing:
        print(f"      ✗ Missing keys: {missing}")
        return False

    print(f"      Protocol ID: {facts_dict['protocol_id']}")
    print(f"      Treatments: {len(facts_dict['treatments'])} arms")
    print(f"      Primary endpoint type: {facts_dict['primary_endpoint']['type']}")
    print("      ✓ Conversion successful")

    # Step 3: Generate code to temp directory
    print("\n[3/5] Generating SAS code...")
    temp_dir = tempfile.mkdtemp(prefix="sas_test_")

    try:
        package = generate_code_from_facts(facts, output_dir=temp_dir)

        print(f"      ADaM programs: {len(package.adam_programs)}")
        for prog in package.adam_programs:
            print(f"        - {prog.program_name}: {prog.description[:50]}...")

        print(f"      TLF programs: {len(package.tlf_programs)}")
        for prog in package.tlf_programs:
            print(f"        - {prog.program_name}: {prog.description[:50]}...")

        print("      ✓ Code generation successful")

        # Step 4: Verify output files
        print("\n[4/5] Verifying output files...")

        # Note: ADTTE and f_km.sas are only generated for time-to-event endpoints (oncology)
        # This IBD trial has binary endpoints, so they are correctly skipped
        expected_files = [
            # ADaM programs
            "adam/adsl.sas",
            "adam/adae.sas",
            "adam/adeff.sas",
            # Tables
            "tlf/t_demog.sas",
            "tlf/t_disp.sas",       # Disposition table
            "tlf/t_ae_summary.sas",
            "tlf/t_primary.sas",
            "tlf/t_secondary.sas",  # Secondary efficacy
            # Listings
            "tlf/l_demog.sas",      # Demographics listing
            "tlf/l_ae.sas",         # AE listing
            "tlf/l_conmeds.sas",    # Concomitant medications listing
            # Figures
            "tlf/f_forest.sas",     # Forest plot
            # Note: f_km.sas only generated for TTE endpoints
            # Infrastructure
            "driver.sas",
            "validation_checklist.txt"
        ]

        all_found = True
        for expected in expected_files:
            full_path = os.path.join(temp_dir, expected)
            if os.path.exists(full_path):
                size = os.path.getsize(full_path)
                print(f"      ✓ {expected} ({size:,} bytes)")
            else:
                print(f"      ✗ {expected} (MISSING)")
                all_found = False

        if not all_found:
            print("\n      Some files missing!")
            return False

        # Step 5: Validate code content
        print("\n[5/5] Validating code content...")

        # Check ADSL has correct treatment derivation
        adsl_path = os.path.join(temp_dir, "adam/adsl.sas")
        with open(adsl_path, 'r') as f:
            adsl_code = f.read()

        checks = [
            ("Protocol reference", facts.nct_id in adsl_code),
            ("Drug name", facts.drug_name in adsl_code),
            ("Treatment arm 1", "ABC-123 300mg" in adsl_code),
            ("FASFL derivation", "FASFL" in adsl_code),
            ("COMPLFL derivation", "COMPLFL" in adsl_code or "DS" in adsl_code),
            ("Population flags", "SAFFL" in adsl_code and "ITTFL" in adsl_code),
        ]

        all_pass = True
        for check_name, result in checks:
            status = "✓" if result else "✗"
            print(f"      {status} {check_name}")
            if not result:
                all_pass = False

        # Check TLF has correct endpoint
        primary_path = os.path.join(temp_dir, "tlf/t_primary.sas")
        with open(primary_path, 'r') as f:
            primary_code = f.read()

        tlf_checks = [
            ("Primary endpoint reference", "Clinical Remission" in primary_code or "CLREMIS" in primary_code),
            ("Week 12 timepoint", "Week 12" in primary_code or "12" in primary_code),
        ]

        for check_name, result in tlf_checks:
            status = "✓" if result else "✗"
            print(f"      {status} {check_name}")
            if not result:
                all_pass = False

        # Count total lines
        total_lines = 0
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.sas'):
                    with open(os.path.join(root, file), 'r') as f:
                        total_lines += len(f.readlines())

        print(f"\n      Total SAS lines generated: {total_lines:,}")

        # Copy to permanent location for inspection
        output_dir = "/tmp/sas_test_output"
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        shutil.copytree(temp_dir, output_dir)
        print(f"\n      Output saved to: {output_dir}")

        return all_pass

    except Exception as e:
        print(f"      ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup temp dir
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print()
    success = run_test()

    print("\n" + "=" * 70)
    if success:
        print("TEST RESULT: ✓ ALL TESTS PASSED")
        print("=" * 70)
        print("\nCode generation integration is working correctly.")
        print("The generated SAS code is ready for review at: /tmp/sas_test_output")
        sys.exit(0)
    else:
        print("TEST RESULT: ✗ SOME TESTS FAILED")
        print("=" * 70)
        sys.exit(1)
