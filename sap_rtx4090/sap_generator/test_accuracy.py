#!/usr/bin/env python3
"""
Proper SAP Accuracy Test
========================
1. Take a protocol that has a matching ground truth SAP
2. Generate a SAP from that protocol using our system
3. Compare generated vs ground truth
4. THIS is the correct way to measure accuracy
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from enterprise_sap_system.core.constrained_pipeline import ConstrainedSAPPipeline
from fast_eval import evaluate_fast, extract_sections_fast, find_statistical_terms_fast


def test_single_pair(nct_id: str):
    """Test accuracy for a single protocol-SAP pair."""
    base = Path(__file__).parent / "data" / "ground_truth"

    protocol_file = base / f"{nct_id}_protocol.txt"
    sap_file = base / f"{nct_id}_sap.txt"

    if not protocol_file.exists():
        print(f"Protocol not found: {protocol_file}")
        return
    if not sap_file.exists():
        print(f"Ground truth SAP not found: {sap_file}")
        return

    # Load files
    protocol = protocol_file.read_text(encoding='utf-8', errors='ignore')
    ground_truth_sap = sap_file.read_text(encoding='utf-8', errors='ignore')

    print(f"=" * 60)
    print(f"PROPER ACCURACY TEST: {nct_id}")
    print(f"=" * 60)
    print(f"\nProtocol: {len(protocol)} chars, {len(protocol.splitlines())} lines")
    print(f"Ground Truth SAP: {len(ground_truth_sap)} chars, {len(ground_truth_sap.splitlines())} lines")

    # Generate SAP from protocol
    print(f"\nGenerating SAP from protocol...")
    pipeline = ConstrainedSAPPipeline()
    result = pipeline.generate(protocol)

    # Handle both dict and object result types
    if hasattr(result, 'success'):
        success = result.success
        # Try sap_text first, then sap_document
        generated_sap = getattr(result, 'sap_text', None) or getattr(result, 'sap_document', "") or ""
        error = getattr(result, 'error', None)
    else:
        success = result.get("success", False)
        generated_sap = result.get("sap_text", "") or result.get("sap_document", "")
        error = result.get("error")

    if not success:
        print(f"Generation failed: {error}")
        return
    print(f"Generated SAP: {len(generated_sap)} chars, {len(generated_sap.splitlines())} lines")

    # Compare
    score, sections, keywords, structure = evaluate_fast(generated_sap, ground_truth_sap)

    # Detailed breakdown
    gt_sections = extract_sections_fast(ground_truth_sap)
    gen_sections = extract_sections_fast(generated_sap)
    gt_terms = find_statistical_terms_fast(ground_truth_sap)
    gen_terms = find_statistical_terms_fast(generated_sap)

    matched_sections = gt_sections & gen_sections
    missing_sections = gt_sections - gen_sections
    extra_sections = gen_sections - gt_sections

    matched_terms = gt_terms & gen_terms
    missing_terms = gt_terms - gen_terms

    print(f"\n{'=' * 60}")
    print(f"RESULTS")
    print(f"{'=' * 60}")

    color = "\033[92m" if score >= 80 else "\033[93m" if score >= 60 else "\033[91m"
    print(f"\nOVERALL SCORE: {color}{score:.1f}%\033[0m")

    print(f"\n1. SECTION COVERAGE: {sections:.1f}%  ({len(matched_sections)}/{len(gt_sections)} sections)")
    print(f"   Matched: {', '.join(sorted(matched_sections)) or 'none'}")
    if missing_sections:
        print(f"   Missing: {', '.join(sorted(missing_sections))}")
    if extra_sections:
        print(f"   Extra:   {', '.join(sorted(extra_sections))}")

    print(f"\n2. KEYWORD OVERLAP: {keywords:.1f}%  ({len(matched_terms)}/{len(gt_terms)} terms)")
    if missing_terms:
        print(f"   Missing: {', '.join(sorted(list(missing_terms)[:10]))}")

    print(f"\n3. STRUCTURE: {structure:.1f}%")

    print(f"\n{'=' * 60}")

    # Save generated SAP for manual review
    output_file = Path(__file__).parent / f"generated_{nct_id}_sap.txt"
    output_file.write_text(generated_sap)
    print(f"\nGenerated SAP saved to: {output_file}")
    print(f"Ground truth SAP at: {sap_file}")
    print(f"\nYou can manually compare these files to see the differences.")


if __name__ == "__main__":
    nct_id = sys.argv[1] if len(sys.argv) > 1 else "NCT03422848"
    test_single_pair(nct_id)
