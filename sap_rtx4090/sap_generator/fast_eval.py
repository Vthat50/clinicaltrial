#!/usr/bin/env python3
"""
Fast SAP Batch Evaluation
~10x faster than original by using simple string matching instead of complex regex.
"""

import os
import sys
import json
from pathlib import Path
from dataclasses import dataclass

# Supabase
from supabase import create_client

SUPABASE_URL = "https://tnydsoojcoucmnxyfdsk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRueWRzb29qY291Y21ueHlmZHNrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NjgzNzQ2NywiZXhwIjoyMDgyNDEzNDY3fQ.RWA-SPfjdpTmXKx2vA-vCuFjM0oW_tFS_hsGbOcJdq4"


# Key sections to check (lowercase)
SECTIONS = [
    "introduction", "study design", "endpoints", "primary endpoint",
    "secondary endpoint", "sample size", "analysis populations",
    "statistical methods", "missing data", "safety", "appendix"
]

# Key statistical terms
TERMS = [
    "intent-to-treat", "itt", "per-protocol", "ancova", "anova",
    "confidence interval", "p-value", "alpha", "power", "hypothesis",
    "logistic regression", "cox", "kaplan-meier", "chi-square",
    "hazard ratio", "odds ratio", "sensitivity analysis"
]


@dataclass
class Result:
    nct_id: str
    score: float
    sections: float
    keywords: float
    quality: str


def fast_evaluate(generated: str, ground_truth: str) -> tuple:
    """Fast evaluation - simple string matching."""
    gen_lower = generated.lower()
    gt_lower = ground_truth.lower()

    # Count sections - how many required sections does generated have?
    gen_sections = [s for s in SECTIONS if s in gen_lower]
    gt_sections = [s for s in SECTIONS if s in gt_lower]

    # Section coverage: what % of ground truth sections are in generated?
    if gt_sections:
        matched = sum(1 for s in gt_sections if s in gen_lower)
        section_pct = (matched / len(gt_sections)) * 100
    else:
        section_pct = 100 if gen_sections else 50

    # Count statistical terms
    gen_terms = [t for t in TERMS if t in gen_lower]
    gt_terms = [t for t in TERMS if t in gt_lower]

    # Keyword overlap: what % of ground truth terms are in generated?
    if gt_terms:
        matched = sum(1 for t in gt_terms if t in gen_lower)
        keyword_pct = (matched / len(gt_terms)) * 100
    else:
        keyword_pct = min(100, len(gen_terms) * 10)  # Reward having terms

    # Overall score (capped at 100)
    score = min(100, (section_pct * 0.4) + (keyword_pct * 0.6))

    return score, section_pct, keyword_pct


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id", nargs="?")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--sap-file", help="Local SAP file path")
    args = parser.parse_args()

    # Get generated SAP
    if args.sap_file:
        generated = Path(args.sap_file).read_text()
        print(f"Loaded from file: {len(generated)} chars")
    elif args.job_id:
        print(f"Fetching job {args.job_id}...")
        db = create_client(SUPABASE_URL, SUPABASE_KEY)
        result = db.table("sap_jobs").select("generated_sap").eq("id", args.job_id).execute()
        if not result.data:
            print("Job not found")
            return
        generated = result.data[0].get("generated_sap", "")
        print(f"Fetched: {len(generated)} chars")
    else:
        print("Need job_id or --sap-file")
        return

    # Find ground truth files
    base = Path(__file__).parent / "data"
    gt_dir = base / "ground_truth"
    ap_dir = base / "all_pairs"

    files = []
    if gt_dir.exists():
        files.extend([(f, "high") for f in sorted(gt_dir.glob("*_sap.txt"))])
    if ap_dir.exists():
        seen = {f.stem.replace("_sap", "") for f, _ in files}
        files.extend([(f, "std") for f in sorted(ap_dir.glob("*_sap.txt"))
                      if f.stem.replace("_sap", "") not in seen])

    files = files[:args.limit]
    print(f"\nEvaluating against {len(files)} ground truth SAPs...\n")

    results = []
    for i, (f, quality) in enumerate(files):
        nct = f.stem.replace("_sap", "")
        try:
            gt = f.read_text(encoding='utf-8', errors='ignore')
            score, sections, keywords = fast_evaluate(generated, gt)
            results.append(Result(nct, score, sections, keywords, quality))

            # Color code
            c = "\033[92m" if score >= 70 else "\033[93m" if score >= 50 else "\033[91m"
            print(f"  [{i+1:3d}/{len(files)}] {nct}: {c}{score:5.1f}%\033[0m  (sec: {sections:.0f}%, kw: {keywords:.0f}%)")
        except Exception as e:
            print(f"  [{i+1:3d}/{len(files)}] {nct}: ERROR - {e}")

    # Summary
    if results:
        scores = [r.score for r in results]
        avg = sum(scores) / len(scores)

        excellent = sum(1 for s in scores if s >= 80)
        good = sum(1 for s in scores if 70 <= s < 80)
        fair = sum(1 for s in scores if 50 <= s < 70)
        poor = sum(1 for s in scores if s < 50)

        c = "\033[92m" if avg >= 70 else "\033[93m" if avg >= 50 else "\033[91m"

        print(f"""
{'='*60}
SUMMARY
{'='*60}

  Total: {len(results)}
  Average Score: {c}{avg:.1f}%\033[0m

  Distribution:
    Excellent (80%+): {excellent} ({excellent/len(results)*100:.0f}%)
    Good (70-79%):    {good} ({good/len(results)*100:.0f}%)
    Fair (50-69%):    {fair} ({fair/len(results)*100:.0f}%)
    Poor (<50%):      {poor} ({poor/len(results)*100:.0f}%)

  Best:  {max(results, key=lambda r: r.score).nct_id} ({max(scores):.1f}%)
  Worst: {min(results, key=lambda r: r.score).nct_id} ({min(scores):.1f}%)

{'='*60}
""")


if __name__ == "__main__":
    main()
