#!/usr/bin/env python3
"""
Batch Accuracy Test
====================
PROPER way to measure SAP generation accuracy:

1. For each ground truth pair (protocol + SAP):
   - Generate SAP from protocol using our system
   - Compare generated SAP to ground truth SAP
   - Calculate accuracy score

2. Report aggregate accuracy across all tests

Usage:
    python batch_accuracy_test.py                    # Test 5 random pairs
    python batch_accuracy_test.py --limit 10         # Test 10 pairs
    python batch_accuracy_test.py --nct NCT03422848  # Test specific study
"""

import sys
import random
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from enterprise_sap_system.core.constrained_pipeline import ConstrainedSAPPipeline
from fast_eval import evaluate_fast, extract_sections_fast, find_statistical_terms_fast


def get_ground_truth_pairs():
    """Get all protocol-SAP pairs from ground_truth directory."""
    base = Path(__file__).parent / "data" / "ground_truth"
    pairs = []

    for sap_file in sorted(base.glob("*_sap.txt")):
        nct_id = sap_file.stem.replace("_sap", "")
        protocol_file = base / f"{nct_id}_protocol.txt"

        if protocol_file.exists():
            pairs.append({
                "nct_id": nct_id,
                "protocol_file": protocol_file,
                "sap_file": sap_file
            })

    return pairs


def test_single_pair(nct_id: str, protocol_file: Path, sap_file: Path, pipeline, verbose=True):
    """Test accuracy for a single protocol-SAP pair."""

    # Load files
    protocol = protocol_file.read_text(encoding='utf-8', errors='ignore')
    ground_truth_sap = sap_file.read_text(encoding='utf-8', errors='ignore')

    if verbose:
        print(f"\n  Protocol: {len(protocol)} chars")
        print(f"  Ground Truth SAP: {len(ground_truth_sap)} chars")
        print(f"  Generating SAP...", end=" ", flush=True)

    # Generate SAP
    try:
        result = pipeline.generate(protocol)

        if hasattr(result, 'success'):
            success = result.success
            generated_sap = getattr(result, 'sap_text', None) or ""
        else:
            success = result.get("success", False)
            generated_sap = result.get("sap_text", "") or result.get("sap_document", "")

        if not success or not generated_sap:
            if verbose:
                print("FAILED")
            return None

        if verbose:
            print(f"Done ({len(generated_sap)} chars)")

        # Evaluate
        score, sections, keywords, structure = evaluate_fast(generated_sap, ground_truth_sap)

        return {
            "nct_id": nct_id,
            "score": score,
            "section_coverage": sections,
            "keyword_overlap": keywords,
            "structure": structure,
            "generated_chars": len(generated_sap),
            "gt_chars": len(ground_truth_sap)
        }

    except Exception as e:
        if verbose:
            print(f"ERROR: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Batch accuracy test for SAP generator")
    parser.add_argument("--limit", type=int, default=5, help="Number of pairs to test (default: 5)")
    parser.add_argument("--nct", type=str, help="Test specific NCT ID")
    parser.add_argument("--random", action="store_true", help="Randomize selection")
    parser.add_argument("-q", "--quiet", action="store_true", help="Less output")
    args = parser.parse_args()

    print("=" * 60)
    print("SAP GENERATOR ACCURACY TEST")
    print("=" * 60)
    print(f"\nThis test measures TRUE accuracy by:")
    print("  1. Taking a protocol from ground truth")
    print("  2. Generating SAP using our system")
    print("  3. Comparing to the matching ground truth SAP")
    print()

    # Get pairs
    pairs = get_ground_truth_pairs()
    print(f"Found {len(pairs)} protocol-SAP pairs in ground_truth/")

    if not pairs:
        print("ERROR: No pairs found!")
        return 1

    # Filter/select pairs
    if args.nct:
        pairs = [p for p in pairs if p["nct_id"] == args.nct]
        if not pairs:
            print(f"ERROR: NCT ID {args.nct} not found in ground truth")
            return 1
    else:
        if args.random:
            random.shuffle(pairs)
        pairs = pairs[:args.limit]

    print(f"Testing {len(pairs)} pairs...\n")

    # Initialize pipeline once
    print("Initializing SAP generator...")
    pipeline = ConstrainedSAPPipeline()
    print()

    # Run tests
    results = []
    for i, pair in enumerate(pairs):
        print(f"[{i+1}/{len(pairs)}] {pair['nct_id']}")

        result = test_single_pair(
            pair["nct_id"],
            pair["protocol_file"],
            pair["sap_file"],
            pipeline,
            verbose=not args.quiet
        )

        if result:
            results.append(result)
            color = "\033[92m" if result["score"] >= 80 else "\033[93m" if result["score"] >= 60 else "\033[91m"
            print(f"  Score: {color}{result['score']:.1f}%\033[0m (sec: {result['section_coverage']:.0f}%, kw: {result['keyword_overlap']:.0f}%, struct: {result['structure']:.0f}%)")
        else:
            print(f"  Score: FAILED")

    # Summary
    if results:
        scores = [r["score"] for r in results]
        avg = sum(scores) / len(scores)

        excellent = sum(1 for s in scores if s >= 80)
        good = sum(1 for s in scores if 70 <= s < 80)
        fair = sum(1 for s in scores if 50 <= s < 70)
        poor = sum(1 for s in scores if s < 50)

        color = "\033[92m" if avg >= 80 else "\033[93m" if avg >= 60 else "\033[91m"

        print(f"""
{'=' * 60}
ACCURACY TEST RESULTS
{'=' * 60}

  Tests Run: {len(results)} / {len(pairs)}

  AVERAGE ACCURACY: {color}{avg:.1f}%\033[0m

  Distribution:
    Excellent (80%+): {excellent} ({excellent/len(results)*100:.0f}%)
    Good (70-79%):    {good} ({good/len(results)*100:.0f}%)
    Fair (50-69%):    {fair} ({fair/len(results)*100:.0f}%)
    Poor (<50%):      {poor} ({poor/len(results)*100:.0f}%)

  Best:  {max(results, key=lambda r: r['score'])['nct_id']} ({max(scores):.1f}%)
  Worst: {min(results, key=lambda r: r['score'])['nct_id']} ({min(scores):.1f}%)

{'=' * 60}
""")

        # Verdict
        if avg >= 80:
            print("VERDICT: PRODUCTION READY")
            return 0
        elif avg >= 70:
            print("VERDICT: GOOD - Minor improvements needed")
            return 0
        elif avg >= 50:
            print("VERDICT: FAIR - Significant improvements needed")
            return 1
        else:
            print("VERDICT: POOR - Major improvements needed")
            return 1
    else:
        print("\nERROR: No successful tests!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
