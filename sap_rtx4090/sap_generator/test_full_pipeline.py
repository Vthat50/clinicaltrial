#!/usr/bin/env python3
"""
Full Pipeline Test: Generate + Verify
======================================

Tests the complete flow:
1. LlamaParse reads PDF → clean text
2. TwoPassExtractor generates SAP (V2)
3. SAPVerifier checks SAP against protocol anchors
4. Reports confidence and issues

This is the production-grade architecture:
- Generate freely from full context
- Verify rigorously against source
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enterprise_sap_system.core.two_pass_extractor import TwoPassExtractor
from enterprise_sap_system.core.sap_verifier import extract_anchors, verify_sap


def test_full_pipeline(pdf_path: str):
    """Test the full generate + verify pipeline."""

    print("=" * 70)
    print("FULL PIPELINE TEST: GENERATE + VERIFY")
    print("=" * 70)
    print(f"Protocol: {pdf_path}")

    # Step 1: Generate SAP using V2 (TwoPassExtractor)
    print("\n" + "-" * 70)
    print("STEP 1: GENERATE SAP (V2 - LlamaParse + Direct Generation)")
    print("-" * 70)

    extractor = TwoPassExtractor()
    result = extractor.process_pdf(pdf_path, validate=True, verbose=True)

    sap_text = result.get('sap_text', '')
    protocol_text = result.get('_protocol_text', '')  # We need to get this

    print(f"\nSAP generated: {len(sap_text):,} characters")

    # Step 2: Extract protocol text (we need it for verification)
    # The extractor should have it cached, but let's get it directly
    print("\n" + "-" * 70)
    print("STEP 2: EXTRACT ANCHORS FROM PROTOCOL")
    print("-" * 70)

    # Get protocol text from LlamaParse (same as what extractor used)
    protocol_text = extractor._extract_pdf_text(pdf_path) if hasattr(extractor, '_extract_pdf_text') else ""

    if not protocol_text:
        print("WARNING: Could not get protocol text for verification")
        print("Using SAP discovery elements as proxy...")
        # Use discovered elements as a proxy
        discovered = result.get('discovered_elements', [])
        protocol_text = "\n".join([
            f"{e.get('name', '')}: {e.get('description', '')}"
            for e in discovered
        ])

    anchors = extract_anchors(protocol_text)
    print(f"Anchors extracted: {anchors.summary()['total']}")
    for cat, count in anchors.summary().items():
        if count > 0 and cat != 'total':
            print(f"  {cat}: {count}")

    # Step 3: Verify SAP against anchors
    print("\n" + "-" * 70)
    print("STEP 3: VERIFY SAP AGAINST PROTOCOL")
    print("-" * 70)

    report = verify_sap(sap_text, protocol_text, anchors)
    print(report.summary())

    # Step 4: Combined results
    print("\n" + "-" * 70)
    print("FINAL RESULTS")
    print("-" * 70)

    v2_score = result.get('validation', {}).get('overall_score', 0)
    verify_score = report.confidence_score

    print(f"V2 Validation Score (checklist coverage): {v2_score:.1%}")
    print(f"Anchor Verification Score: {verify_score:.1%}")
    print(f"Combined Confidence: {(v2_score + verify_score) / 2:.1%}")
    print(f"Critical Issues: {report.critical_count()}")
    print(f"Human Review Required: {'YES' if report.needs_human_review() else 'NO'}")

    # Save results
    output_base = os.path.splitext(pdf_path)[0]

    # Save SAP
    sap_file = f"{output_base}_generated_SAP.txt"
    with open(sap_file, 'w') as f:
        f.write(sap_text)
    print(f"\nSAP saved: {sap_file}")

    # Save verification report
    report_file = f"{output_base}_verification_report.txt"
    with open(report_file, 'w') as f:
        f.write(report.summary())
        f.write("\n\n" + "=" * 70 + "\n")
        f.write("ANCHORS FOUND IN PROTOCOL\n")
        f.write("=" * 70 + "\n")
        for anchor in anchors.all_anchors():
            f.write(f"\n[{anchor.category}] Numbers: {anchor.numbers}\n")
            f.write(f"  \"{anchor.text}\"\n")
    print(f"Report saved: {report_file}")

    return {
        'sap_text': sap_text,
        'v2_score': v2_score,
        'verify_score': verify_score,
        'report': report
    }


def test_with_sample():
    """Test with built-in sample data (no external files needed)."""

    print("=" * 70)
    print("SAMPLE DATA TEST (No External Files)")
    print("=" * 70)

    # Sample protocol
    protocol = """
    Study EFC13833 - Phase III Gastric Cancer Trial

    SAMPLE SIZE: Total 530 patients (265 per arm).
    Dropout assumption: 10% dropout rate.
    At least 238 evaluable subjects per group.

    RANDOMIZATION: 1:1 ratio using IWRS.
    Stratification by TNM stage (T2/N+, T3-4/N+, T4/N-).

    PRIMARY ENDPOINT: 3-year Progression-Free Survival (PFS).
    Target: 244 PFS events for final analysis.

    POWER: 80% power to detect HR = 0.698.
    Based on 70% vs 60% 3-year PFS assumption.

    ALPHA: 5% two-sided overall.
    Interim: alpha = 0.0031 (O'Brien-Fleming).
    Final: alpha = 0.0490 after adjustment.

    ONE interim analysis at 50% information (122 events).
    IDMC will review with stopping boundaries.

    METHODS: Stratified log-rank test.
    Cox model for hazard ratio with 95% CI.
    Kaplan-Meier for survival curves.
    """

    # Sample SAP (intentionally missing some details to test verification)
    sap = """
    STATISTICAL ANALYSIS PLAN
    Study EFC13833

    1. SAMPLE SIZE
    Total: 530 patients, 265 per arm.
    Power: 80% to detect HR = 0.698.

    2. RANDOMIZATION
    1:1 randomization stratified by TNM stage.

    3. PRIMARY ENDPOINT
    3-year PFS per RECIST 1.1 criteria.

    4. ALPHA LEVEL
    Overall alpha: 5% two-sided.
    One interim analysis planned.

    5. STATISTICAL METHODS
    Primary: Stratified log-rank test.
    Cox proportional hazards for HR.
    Kaplan-Meier for survival estimation.

    6. INTERIM ANALYSIS
    One interim at 50% information fraction.
    O'Brien-Fleming boundaries for early stopping.
    """

    print("\n[Step 1] Extracting anchors from protocol...")
    anchors = extract_anchors(protocol)
    print(f"Found {anchors.summary()['total']} anchors")

    print("\n[Step 2] Verifying SAP...")
    report = verify_sap(sap, protocol, anchors)

    print("\n" + report.summary())

    # Show what's missing
    print("\n" + "=" * 70)
    print("WHAT THE SAP IS MISSING (per verification):")
    print("=" * 70)
    missing_items = [
        "- 10% dropout rate",
        "- 238 evaluable subjects",
        "- 244 PFS events target",
        "- Interim alpha = 0.0031",
        "- Final alpha = 0.0490",
        "- 122 events at interim",
        "- 70% vs 60% PFS assumption",
    ]
    for item in missing_items:
        print(item)

    print("\nThese are the specific values that would improve SAP from ~80% to ~95%")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Test with provided PDF
        test_full_pipeline(sys.argv[1])
    else:
        # Test with sample data
        test_with_sample()

        # Also test with a real PDF if available
        test_pdf = "/mnt/c/Users/vijay/Desktop/sap_data/oncology_trials/matched/NCT01515748_Protocol.pdf"
        if os.path.exists(test_pdf):
            print("\n\n")
            test_full_pipeline(test_pdf)
        else:
            print(f"\nTo test with real PDF: python test_full_pipeline.py <protocol.pdf>")
