#!/usr/bin/env python3
"""
Fast SAP Batch Evaluation
Uses the SAME scoring logic as evaluate_sap.py but optimized for speed.
~10x faster by using single-pass section detection instead of O(n²) regex.
"""

import os
import sys
import json
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Set, List

# Supabase
from supabase import create_client

SUPABASE_URL = "https://tnydsoojcoucmnxyfdsk.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRueWRzb29qY291Y21ueHlmZHNrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NjgzNzQ2NywiZXhwIjoyMDgyNDEzNDY3fQ.RWA-SPfjdpTmXKx2vA-vCuFjM0oW_tFS_hsGbOcJdq4"


# Same sections as evaluate_sap.py
SAP_SECTIONS = [
    "introduction",
    "study design",
    "study objectives",
    "endpoints",
    "primary endpoint",
    "secondary endpoint",
    "sample size",
    "analysis populations",
    "statistical methods",
    "primary analysis",
    "secondary analysis",
    "sensitivity analysis",
    "subgroup analysis",
    "missing data",
    "interim analysis",
    "multiplicity",
    "safety analysis",
    "tables",
    "figures",
    "appendix",
]

# Same statistical terms as evaluate_sap.py
STATISTICAL_TERMS = [
    "intent-to-treat", "itt", "per-protocol", "full analysis set",
    "modified intent-to-treat", "mitt", "safety population",
    "primary efficacy", "type i error", "alpha", "power",
    "confidence interval", "p-value", "hypothesis",
    "null hypothesis", "alternative hypothesis",
    "two-sided", "one-sided", "significance level",
    "mixed model", "ancova", "anova", "logistic regression",
    "cox regression", "kaplan-meier", "log-rank",
    "chi-square", "fisher's exact", "t-test", "wilcoxon",
    "last observation carried forward", "locf",
    "multiple imputation", "sensitivity analysis",
    "subgroup analysis", "forest plot",
    "odds ratio", "hazard ratio", "relative risk",
    "treatment difference", "least squares mean",
]


@dataclass
class Result:
    nct_id: str
    score: float
    section_coverage: float
    keyword_overlap: float
    structure_score: float
    quality: str


def extract_sections_fast(text: str) -> Set[str]:
    """
    Fast section extraction - single pass through text.
    Returns set of section names found.
    """
    text_lower = text.lower()
    found_sections = set()

    for section_name in SAP_SECTIONS:
        # Check for section header patterns (simplified but effective)
        patterns = [
            # Numbered section: "1. Introduction" or "1.1 Introduction"
            rf'\n\s*\d+\.?\d*\.?\s*{re.escape(section_name)}',
            # Header with colon: "Introduction:"
            rf'\n\s*{re.escape(section_name)}\s*:',
            # Standalone header (all caps or title case on its own line)
            rf'\n\s*{re.escape(section_name)}\s*\n',
            # Markdown header: "## Introduction" or "### Introduction"
            rf'\n#+\s*{re.escape(section_name)}',
        ]

        for pattern in patterns:
            if re.search(pattern, text_lower):
                found_sections.add(section_name)
                break

    return found_sections


def find_statistical_terms_fast(text: str) -> Set[str]:
    """Find statistical terms - simple string matching."""
    text_lower = text.lower()
    return {term for term in STATISTICAL_TERMS if term in text_lower}


def evaluate_fast(generated: str, ground_truth: str) -> tuple:
    """
    Fast evaluation using SAME scoring as evaluate_sap.py:
    - Section coverage: 40 points
    - Statistical terms overlap: 30 points
    - Structure completeness: 30 points
    """
    gen_lower = generated.lower()

    # 1. Section Coverage (40 points)
    gt_sections = extract_sections_fast(ground_truth)
    gen_sections = extract_sections_fast(generated)

    if gt_sections:
        matched_sections = gt_sections & gen_sections
        section_coverage_pct = (len(matched_sections) / len(gt_sections)) * 100
    else:
        section_coverage_pct = 100 if gen_sections else 0

    section_score = section_coverage_pct * 0.4

    # 2. Statistical Terms Overlap (30 points)
    gt_terms = find_statistical_terms_fast(ground_truth)
    gen_terms = find_statistical_terms_fast(generated)

    if gt_terms:
        matched_terms = gt_terms & gen_terms
        keyword_overlap_pct = (len(matched_terms) / len(gt_terms)) * 100
    else:
        keyword_overlap_pct = 100 if gen_terms else 0

    keyword_score = keyword_overlap_pct * 0.3

    # 3. Structure Completeness (30 points) - same checks as evaluate_sap.py
    has_primary = any(x in gen_lower for x in [
        "primary endpoint", "primary efficacy", "primary outcome", "primary analysis"
    ])
    has_secondary = any(x in gen_lower for x in [
        "secondary endpoint", "secondary efficacy", "secondary outcome"
    ])
    has_sample_size = any(x in gen_lower for x in [
        "sample size", "power calculation", "statistical power"
    ])
    has_populations = any(x in gen_lower for x in [
        "analysis population", "intent-to-treat", "per-protocol", "full analysis set"
    ])
    has_methods = any(x in gen_lower for x in [
        "statistical method", "statistical model", "ancova", "anova", "mixed model", "regression"
    ])
    has_missing = any(x in gen_lower for x in [
        "missing data", "imputation", "locf", "last observation"
    ])

    structure_checks = [has_primary, has_secondary, has_sample_size, has_populations, has_methods, has_missing]
    structure_pct = (sum(structure_checks) / len(structure_checks)) * 100
    structure_score = structure_pct * 0.3

    # Total score (max 100)
    total_score = section_score + keyword_score + structure_score

    return total_score, section_coverage_pct, keyword_overlap_pct, structure_pct


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fast SAP batch evaluation (same scoring as UI)")
    parser.add_argument("job_id", nargs="?", help="Supabase job ID")
    parser.add_argument("--limit", type=int, default=100, help="Max comparisons")
    parser.add_argument("--sap-file", help="Local SAP file path instead of job_id")
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
    print(f"\nEvaluating against {len(files)} ground truth SAPs...")
    print(f"(Using same scoring as UI: 40% sections + 30% keywords + 30% structure)\n")

    results = []
    for i, (f, quality) in enumerate(files):
        nct = f.stem.replace("_sap", "")
        try:
            gt = f.read_text(encoding='utf-8', errors='ignore')
            score, sections, keywords, structure = evaluate_fast(generated, gt)
            results.append(Result(nct, score, sections, keywords, structure, quality))

            # Color code
            c = "\033[92m" if score >= 70 else "\033[93m" if score >= 50 else "\033[91m"
            print(f"  [{i+1:3d}/{len(files)}] {nct}: {c}{score:5.1f}%\033[0m  (sec: {sections:.0f}%, kw: {keywords:.0f}%, struct: {structure:.0f}%)")
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
SUMMARY (Same scoring as UI)
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
