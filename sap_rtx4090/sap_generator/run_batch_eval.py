#!/usr/bin/env python3
"""
Batch SAP Evaluation Script
Run locally to evaluate a generated SAP against all ground truth SAPs.
No timeout - runs until complete.

Usage:
  python run_batch_eval.py <job_id>
  python run_batch_eval.py <job_id> --limit 50
  python run_batch_eval.py --sap-file output.md
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from evaluate_sap import SAPEvaluator
from supabase import create_client

# Supabase config
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://tnydsoojcoucmnxyfdsk.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRueWRzb29qY291Y21ueHlmZHNrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NjgzNzQ2NywiZXhwIjoyMDgyNDEzNDY3fQ.RWA-SPfjdpTmXKx2vA-vCuFjM0oW_tFS_hsGbOcJdq4")


def get_generated_sap(job_id: str) -> str:
    """Fetch generated SAP from Supabase by job_id."""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    result = supabase.table("sap_jobs").select("*").eq("id", job_id).execute()

    if not result.data:
        raise ValueError(f"Job not found: {job_id}")

    job = result.data[0]
    if job["status"] != "completed":
        raise ValueError(f"Job not completed. Status: {job['status']}")

    sap = job.get("generated_sap", "")
    if not sap:
        raise ValueError("No generated SAP found in job")

    return sap


def run_batch_evaluation(generated_sap: str, limit: int = None, verbose: bool = True):
    """
    Evaluate generated SAP against all ground truth SAPs.

    Returns dict with aggregate metrics and individual results.
    """
    base_dir = Path(__file__).parent / "data"
    ground_truth_dir = base_dir / "ground_truth"
    all_pairs_dir = base_dir / "all_pairs"

    results = []

    # Collect all SAP files
    sap_files = []

    if ground_truth_dir.exists():
        for f in sorted(ground_truth_dir.glob("*_sap.txt")):
            sap_files.append((f, "high"))

    if all_pairs_dir.exists():
        seen = {f.stem.replace("_sap", "") for f, _ in sap_files}
        for f in sorted(all_pairs_dir.glob("*_sap.txt")):
            nct_id = f.stem.replace("_sap", "")
            if nct_id not in seen:
                sap_files.append((f, "standard"))

    if limit:
        sap_files = sap_files[:limit]

    total = len(sap_files)
    print(f"\n{'='*60}")
    print(f"BATCH EVALUATION - {total} Ground Truth SAPs")
    print(f"{'='*60}\n")

    for i, (sap_file, quality) in enumerate(sap_files):
        nct_id = sap_file.stem.replace("_sap", "")

        try:
            ground_truth_sap = sap_file.read_text(encoding='utf-8', errors='ignore')
            evaluator = SAPEvaluator(str(sap_file.parent))
            eval_result = evaluator.evaluate(generated_sap, ground_truth_sap, nct_id)

            result = {
                "nct_id": nct_id,
                "quality": quality,
                "overall_score": eval_result.overall_score,
                "section_coverage_pct": eval_result.section_coverage_pct,
                "keyword_overlap_pct": eval_result.keyword_overlap_pct,
                "has_primary_endpoint": eval_result.has_primary_endpoint,
                "has_statistical_methods": eval_result.has_statistical_methods,
                "ground_truth_lines": eval_result.ground_truth_lines,
            }
            results.append(result)

            if verbose:
                score = eval_result.overall_score
                color = "\033[92m" if score >= 70 else "\033[93m" if score >= 50 else "\033[91m"
                reset = "\033[0m"
                print(f"  [{i+1:3d}/{total}] {nct_id}: {color}{score:5.1f}%{reset}  (sections: {eval_result.section_coverage_pct:.0f}%, keywords: {eval_result.keyword_overlap_pct:.0f}%)")

        except Exception as e:
            if verbose:
                print(f"  [{i+1:3d}/{total}] {nct_id}: ERROR - {e}")

    # Calculate aggregates
    if results:
        scores = [r["overall_score"] for r in results]
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)

        avg_section = sum(r["section_coverage_pct"] for r in results) / len(results)
        avg_keyword = sum(r["keyword_overlap_pct"] for r in results) / len(results)

        primary_pct = sum(1 for r in results if r["has_primary_endpoint"]) / len(results) * 100
        stats_pct = sum(1 for r in results if r["has_statistical_methods"]) / len(results) * 100

        # Score distribution
        excellent = sum(1 for s in scores if s >= 80)
        good = sum(1 for s in scores if 70 <= s < 80)
        fair = sum(1 for s in scores if 50 <= s < 70)
        poor = sum(1 for s in scores if s < 50)

        sorted_results = sorted(results, key=lambda x: x["overall_score"], reverse=True)

        aggregate = {
            "total_comparisons": len(results),
            "avg_overall_score": round(avg_score, 1),
            "min_score": round(min_score, 1),
            "max_score": round(max_score, 1),
            "avg_section_coverage_pct": round(avg_section, 1),
            "avg_keyword_overlap_pct": round(avg_keyword, 1),
            "primary_endpoint_pct": round(primary_pct, 1),
            "statistical_methods_pct": round(stats_pct, 1),
            "score_distribution": {
                "excellent_80+": excellent,
                "good_70_79": good,
                "fair_50_69": fair,
                "poor_below_50": poor,
            },
            "best_match": sorted_results[0] if sorted_results else None,
            "worst_match": sorted_results[-1] if sorted_results else None,
        }
    else:
        aggregate = {"total_comparisons": 0, "avg_overall_score": 0}

    return {
        "aggregate": aggregate,
        "results": results,
    }


def print_summary(evaluation: dict):
    """Print a formatted summary of evaluation results."""
    agg = evaluation["aggregate"]

    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")

    avg = agg["avg_overall_score"]
    color = "\033[92m" if avg >= 70 else "\033[93m" if avg >= 50 else "\033[91m"
    reset = "\033[0m"

    print(f"""
  Total Comparisons:     {agg['total_comparisons']}

  SCORES:
    Average Score:       {color}{avg:.1f}%{reset}
    Min Score:           {agg['min_score']:.1f}%
    Max Score:           {agg['max_score']:.1f}%

  COVERAGE:
    Section Coverage:    {agg['avg_section_coverage_pct']:.1f}%
    Keyword Overlap:     {agg['avg_keyword_overlap_pct']:.1f}%

  KEY ELEMENTS:
    Has Primary Endpoint:    {agg['primary_endpoint_pct']:.1f}%
    Has Stats Methods:       {agg['statistical_methods_pct']:.1f}%

  SCORE DISTRIBUTION:
    Excellent (80%+):    {agg['score_distribution']['excellent_80+']} ({agg['score_distribution']['excellent_80+']/agg['total_comparisons']*100:.0f}%)
    Good (70-79%):       {agg['score_distribution']['good_70_79']} ({agg['score_distribution']['good_70_79']/agg['total_comparisons']*100:.0f}%)
    Fair (50-69%):       {agg['score_distribution']['fair_50_69']} ({agg['score_distribution']['fair_50_69']/agg['total_comparisons']*100:.0f}%)
    Poor (<50%):         {agg['score_distribution']['poor_below_50']} ({agg['score_distribution']['poor_below_50']/agg['total_comparisons']*100:.0f}%)
""")

    if agg.get("best_match"):
        print(f"  Best Match:  {agg['best_match']['nct_id']} ({agg['best_match']['overall_score']:.1f}%)")
    if agg.get("worst_match"):
        print(f"  Worst Match: {agg['worst_match']['nct_id']} ({agg['worst_match']['overall_score']:.1f}%)")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Batch evaluate SAP against ground truth")
    parser.add_argument("job_id", nargs="?", help="Supabase job ID")
    parser.add_argument("--sap-file", help="Path to local SAP file instead of job_id")
    parser.add_argument("--limit", type=int, help="Limit number of comparisons")
    parser.add_argument("--output", help="Save results to JSON file")
    parser.add_argument("-q", "--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args()

    if not args.job_id and not args.sap_file:
        parser.error("Either job_id or --sap-file is required")

    # Get generated SAP
    if args.sap_file:
        print(f"Loading SAP from: {args.sap_file}")
        generated_sap = Path(args.sap_file).read_text(encoding='utf-8')
    else:
        print(f"Fetching job: {args.job_id}")
        generated_sap = get_generated_sap(args.job_id)

    print(f"Generated SAP: {len(generated_sap)} characters, {len(generated_sap.splitlines())} lines")

    # Run evaluation
    evaluation = run_batch_evaluation(
        generated_sap,
        limit=args.limit,
        verbose=not args.quiet
    )

    # Print summary
    print_summary(evaluation)

    # Save to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(evaluation, f, indent=2)
        print(f"Results saved to: {args.output}")

    # Return exit code based on average score
    avg = evaluation["aggregate"]["avg_overall_score"]
    if avg >= 80:
        print("PRODUCTION READY")
        return 0
    elif avg >= 70:
        print("GOOD - Minor improvements needed")
        return 0
    elif avg >= 50:
        print("FAIR - Significant improvements needed")
        return 1
    else:
        print("POOR - Major improvements needed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
