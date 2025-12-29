#!/usr/bin/env python3
"""
FACTUAL Accuracy Test
=====================
Measures REAL accuracy by comparing extracted FACTS, not just keywords.

Checks:
1. Drug name - Is it correct?
2. Study design - Single-arm vs RCT, open-label vs double-blind?
3. Sample size - Is N correct?
4. Primary endpoint - Is it correctly extracted?
5. Statistical approach - Appropriate for study design?
6. Phase - Correct?
7. Indication - Correct?

Usage:
    python factual_accuracy_test.py --limit 5
    python factual_accuracy_test.py --nct NCT03422848
"""

import sys
import re
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict

sys.path.insert(0, str(Path(__file__).parent))

from enterprise_sap_system.core.constrained_pipeline import ConstrainedSAPPipeline


@dataclass
class ExtractedFacts:
    """Key facts extracted from a SAP document"""
    # Identification
    nct_id: Optional[str] = None
    study_id: Optional[str] = None
    sponsor: Optional[str] = None

    # Drug
    drug_name: Optional[str] = None
    drug_names_all: List[str] = field(default_factory=list)

    # Study Design
    phase: Optional[str] = None
    indication: Optional[str] = None
    is_randomized: Optional[bool] = None
    is_double_blind: Optional[bool] = None
    is_open_label: Optional[bool] = None
    is_single_arm: Optional[bool] = None
    is_placebo_controlled: Optional[bool] = None
    num_arms: Optional[int] = None

    # Sample Size
    total_n: Optional[int] = None

    # Endpoints
    primary_endpoint: Optional[str] = None
    primary_endpoint_type: Optional[str] = None  # binary, continuous, time-to-event

    # Statistical Approach
    uses_hypothesis_testing: Optional[bool] = None
    uses_descriptive_only: Optional[bool] = None
    primary_analysis_method: Optional[str] = None  # logistic regression, ANCOVA, Kaplan-Meier, etc.


def extract_facts_from_text(text: str) -> ExtractedFacts:
    """Extract key facts from SAP or protocol text."""
    facts = ExtractedFacts()
    text_lower = text.lower()

    # === NCT ID ===
    nct_match = re.search(r'(NCT\d{8})', text, re.I)
    if nct_match:
        facts.nct_id = nct_match.group(1).upper()

    # === Study ID ===
    study_id_patterns = [
        r'Protocol[:\s]+([A-Z]{2,5}[-]?\d{3,6}[A-Z]{0,3})',
        r'Study\s+(?:ID|Number)[:\s]+([A-Z0-9-]+)',
    ]
    for pattern in study_id_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            facts.study_id = match.group(1)
            break

    # === Sponsor ===
    sponsor_patterns = [
        r'Sponsor[:\s]+([A-Za-z][A-Za-z0-9\s&-]+?)(?:\n|,|\.)',
        r'(?:Prepared\s+by|Prepared\s+for)[:\s]+([A-Za-z][A-Za-z0-9\s&-]+?)(?:\n|,|\.)',
    ]
    for pattern in sponsor_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            facts.sponsor = match.group(1).strip()
            break

    # === Drug Names ===
    drug_patterns = [
        # Explicit declarations
        r'(?:Investigational\s+Product|IMP|Study\s+Drug|Test\s+Article)[:\s]+([A-Za-z][A-Za-z0-9-]{2,})',
        # Drug codes (TJ301, AB1234, etc.)
        r'\b([A-Z]{2,4}[-]?\d{3,6})\b',
        # Named drugs with common suffixes
        r'\b([A-Za-z]{4,}(?:mab|nib|ib|zumab|ximab|tinib|ciclib|parin|statin|sartan|pril|olol))\b',
    ]

    excluded = {'NCT', 'THE', 'AND', 'FOR', 'FDA', 'ICH', 'STUDY', 'TRIAL', 'PLACEBO',
                'DOSE', 'DRUG', 'TREATMENT', 'THERAPY', 'PHASE', 'PROTOCOL'}

    all_drugs = []
    for pattern in drug_patterns:
        matches = re.findall(pattern, text, re.I)
        for drug in matches:
            drug = drug.strip()
            if len(drug) >= 3 and drug.upper() not in excluded:
                all_drugs.append(drug)

    # Deduplicate and get primary drug
    seen = set()
    unique_drugs = []
    for d in all_drugs:
        d_lower = d.lower()
        if d_lower not in seen:
            seen.add(d_lower)
            unique_drugs.append(d)

    facts.drug_names_all = unique_drugs[:5]  # Top 5
    if unique_drugs:
        facts.drug_name = unique_drugs[0]

    # === Phase ===
    phase_match = re.search(r'Phase\s*(I{1,3}|[1-4]|1/?2|2/?3|2[ab]?|3[ab]?)', text, re.I)
    if phase_match:
        phase = phase_match.group(1)
        # Normalize
        phase_map = {'I': '1', 'II': '2', 'III': '3', 'IV': '4'}
        for roman, arabic in phase_map.items():
            phase = phase.replace(roman, arabic)
        facts.phase = f"Phase {phase}"

    # === Indication ===
    indication_patterns = [
        (r"ulcerative\s+colitis", "Ulcerative Colitis"),
        (r"crohn'?s?\s+disease", "Crohn's Disease"),
        (r"rheumatoid\s+arthritis", "Rheumatoid Arthritis"),
        (r"non-?small\s+cell\s+lung\s+cancer|NSCLC", "NSCLC"),
        (r"breast\s+cancer", "Breast Cancer"),
        (r"melanoma", "Melanoma"),
        (r"solid\s+tumou?rs?", "Solid Tumors"),
        (r"refractory\s+solid\s+tumou?rs?", "Refractory Solid Tumors"),
        (r"advanced\s+(?:solid\s+)?tumou?rs?", "Advanced Solid Tumors"),
        (r"multiple\s+sclerosis", "Multiple Sclerosis"),
        (r"type\s+2\s+diabetes", "Type 2 Diabetes"),
        (r"psoriasis", "Psoriasis"),
        (r"atopic\s+dermatitis", "Atopic Dermatitis"),
    ]
    for pattern, name in indication_patterns:
        if re.search(pattern, text, re.I):
            facts.indication = name
            break

    # === Study Design ===
    facts.is_randomized = bool(re.search(r'\brandomiz', text_lower))
    facts.is_double_blind = bool(re.search(r'double[- ]?blind', text_lower))
    facts.is_open_label = bool(re.search(r'open[- ]?label', text_lower))
    facts.is_placebo_controlled = bool(re.search(r'placebo[- ]?control', text_lower))

    # Single-arm detection
    single_arm_indicators = [
        r'single[- ]?arm',
        r'non[- ]?randomiz',
        r'uncontrolled\s+(?:study|trial)',
        r'no\s+(?:control|comparator)\s+(?:group|arm)',
        r'all\s+(?:patients?|subjects?)\s+(?:will\s+)?receive',
    ]
    facts.is_single_arm = any(re.search(p, text_lower) for p in single_arm_indicators)

    # If not randomized and not explicitly single-arm, check context
    if not facts.is_randomized and not facts.is_single_arm:
        # Check for "randomization" in negative context
        if re.search(r'randomization[:\s]+(?:not\s+applicable|n/?a|none)', text_lower):
            facts.is_single_arm = True

    # Number of arms
    arm_patterns = [
        r'(\d+)[- ]?arm',
        r'(\d+)\s+treatment\s+(?:arms?|groups?)',
    ]
    for pattern in arm_patterns:
        match = re.search(pattern, text_lower)
        if match:
            facts.num_arms = int(match.group(1))
            break

    # Infer from ratio if not found
    if not facts.num_arms:
        ratio_match = re.search(r'\b(\d+:\d+(?::\d+)*)\b', text)
        if ratio_match:
            facts.num_arms = len(ratio_match.group(1).split(':'))

    # === Sample Size ===
    n_patterns = [
        r'(?:N|n)\s*[=:]\s*(\d{2,4})\b',
        r'(?:sample\s+size)[:\s]+(\d{2,4})',
        r'(\d{2,4})\s+(?:patients?|subjects?)\s+(?:will\s+be\s+)?(?:enrolled|randomized)',
        r'(?:total\s+of\s+)?(\d{2,4})\s+(?:patients?|subjects?)',
        r'(?:enroll|randomize)\s+(?:approximately\s+)?(\d{2,4})',
    ]
    for pattern in n_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            n = int(match.group(1))
            if 10 <= n <= 10000:
                facts.total_n = n
                break

    # === Primary Endpoint ===
    endpoint_patterns = [
        r'primary\s+(?:efficacy\s+)?endpoint[:\s]+([^\n\.]{10,200})',
        r'primary\s+(?:outcome|objective)[:\s]+([^\n\.]{10,200})',
    ]
    for pattern in endpoint_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            facts.primary_endpoint = match.group(1).strip()[:200]
            break

    # Endpoint type detection
    endpoint_text = (facts.primary_endpoint or "") + " " + text[:5000]
    endpoint_lower = endpoint_text.lower()

    if any(x in endpoint_lower for x in ['proportion', 'percentage', 'rate', 'responder', 'remission', 'response']):
        facts.primary_endpoint_type = "binary"
    elif any(x in endpoint_lower for x in ['change from baseline', 'mean change', 'cfb', 'difference']):
        facts.primary_endpoint_type = "continuous"
    elif any(x in endpoint_lower for x in ['survival', 'time to', 'pfs', 'os', 'dfs', 'kaplan']):
        facts.primary_endpoint_type = "time-to-event"

    # === Statistical Approach ===
    # Descriptive-only indicators
    descriptive_indicators = [
        r'no\s+(?:formal\s+)?(?:statistical\s+)?(?:hypothesis\s+)?test',
        r'descriptive\s+(?:statistics?\s+)?(?:only|analysis)',
        r'exploratory\s+(?:study|analysis)',
        r'no\s+(?:formal\s+)?sample\s+size\s+(?:calculation|estimation)',
        r'sample\s+size[:\s]+(?:not\s+applicable|n/?a)',
    ]
    facts.uses_descriptive_only = any(re.search(p, text_lower) for p in descriptive_indicators)

    # Hypothesis testing indicators
    hypothesis_indicators = [
        r'null\s+hypothesis',
        r'alternative\s+hypothesis',
        r'type\s+[iI1]\s+error',
        r'α\s*[=:]\s*0\.\d+',
        r'alpha\s*[=:]\s*0\.\d+',
        r'statistical\s+significance',
        r'p[- ]?value',
        r'reject\s+(?:the\s+)?(?:null\s+)?hypothesis',
    ]
    facts.uses_hypothesis_testing = any(re.search(p, text_lower) for p in hypothesis_indicators)

    # Primary analysis method
    method_patterns = [
        (r'logistic\s+regression', 'logistic regression'),
        (r'ANCOVA|analysis\s+of\s+covariance', 'ANCOVA'),
        (r'ANOVA|analysis\s+of\s+variance', 'ANOVA'),
        (r'MMRM|mixed\s+model.*repeated\s+measures', 'MMRM'),
        (r'cox\s+(?:proportional\s+hazards?)?(?:\s+regression)?', 'Cox regression'),
        (r'kaplan[- ]meier', 'Kaplan-Meier'),
        (r'log[- ]?rank', 'log-rank test'),
        (r'chi[- ]?square|χ²', 'chi-square'),
        (r"fisher'?s?\s+exact", "Fisher's exact"),
        (r't[- ]?test', 't-test'),
        (r'wilcoxon', 'Wilcoxon'),
        (r'mann[- ]?whitney', 'Mann-Whitney'),
    ]
    for pattern, method in method_patterns:
        if re.search(pattern, text_lower):
            facts.primary_analysis_method = method
            break

    return facts


@dataclass
class FactComparison:
    """Comparison result for a single fact"""
    fact_name: str
    expected: str
    actual: str
    match: bool
    critical: bool  # Is this a critical fact?
    score: float  # 1.0 = perfect match, 0.5 = partial, 0 = wrong


def compare_facts(expected: ExtractedFacts, actual: ExtractedFacts) -> Dict:
    """Compare extracted facts and calculate accuracy."""
    comparisons = []

    def add_comparison(name: str, exp, act, critical: bool = False):
        """Add a fact comparison."""
        exp_str = str(exp) if exp is not None else "NOT FOUND"
        act_str = str(act) if act is not None else "NOT FOUND"

        # Calculate match score
        if exp is None and act is None:
            score = 1.0
            match = True
        elif exp is None or act is None:
            score = 0.0
            match = False
        elif isinstance(exp, bool):
            score = 1.0 if exp == act else 0.0
            match = exp == act
        elif isinstance(exp, int):
            # For numbers, check if within 10%
            if exp == act:
                score = 1.0
                match = True
            elif exp > 0 and abs(exp - act) / exp < 0.1:
                score = 0.5
                match = False
            else:
                score = 0.0
                match = False
        elif isinstance(exp, str):
            exp_lower = exp.lower().strip()
            act_lower = act.lower().strip() if isinstance(act, str) else str(act).lower()

            if exp_lower == act_lower:
                score = 1.0
                match = True
            elif exp_lower in act_lower or act_lower in exp_lower:
                score = 0.5
                match = False
            else:
                score = 0.0
                match = False
        else:
            score = 1.0 if exp == act else 0.0
            match = exp == act

        comparisons.append(FactComparison(
            fact_name=name,
            expected=exp_str,
            actual=act_str,
            match=match,
            critical=critical,
            score=score
        ))

    # Critical facts (wrong = major failure)
    add_comparison("Drug Name", expected.drug_name, actual.drug_name, critical=True)
    add_comparison("Is Randomized", expected.is_randomized, actual.is_randomized, critical=True)
    add_comparison("Is Single-Arm", expected.is_single_arm, actual.is_single_arm, critical=True)
    add_comparison("Is Double-Blind", expected.is_double_blind, actual.is_double_blind, critical=True)
    add_comparison("Is Open-Label", expected.is_open_label, actual.is_open_label, critical=True)
    add_comparison("Uses Hypothesis Testing", expected.uses_hypothesis_testing, actual.uses_hypothesis_testing, critical=True)
    add_comparison("Uses Descriptive Only", expected.uses_descriptive_only, actual.uses_descriptive_only, critical=True)

    # Important facts
    add_comparison("Phase", expected.phase, actual.phase, critical=False)
    add_comparison("Indication", expected.indication, actual.indication, critical=False)
    add_comparison("Sample Size", expected.total_n, actual.total_n, critical=False)
    add_comparison("Number of Arms", expected.num_arms, actual.num_arms, critical=False)
    add_comparison("Primary Endpoint Type", expected.primary_endpoint_type, actual.primary_endpoint_type, critical=False)
    add_comparison("Primary Analysis Method", expected.primary_analysis_method, actual.primary_analysis_method, critical=False)

    # Calculate scores
    critical_facts = [c for c in comparisons if c.critical]
    all_facts = comparisons

    critical_score = sum(c.score for c in critical_facts) / len(critical_facts) * 100 if critical_facts else 0
    overall_score = sum(c.score for c in all_facts) / len(all_facts) * 100 if all_facts else 0

    # Weighted score (critical facts count 2x)
    weighted_score = (critical_score * 2 + overall_score) / 3

    critical_matches = sum(1 for c in critical_facts if c.match)
    total_matches = sum(1 for c in all_facts if c.match)

    return {
        "comparisons": comparisons,
        "critical_score": critical_score,
        "overall_score": overall_score,
        "weighted_score": weighted_score,
        "critical_matches": f"{critical_matches}/{len(critical_facts)}",
        "total_matches": f"{total_matches}/{len(all_facts)}",
        "critical_failures": [c for c in critical_facts if not c.match],
    }


def test_single_pair(nct_id: str, protocol_file: Path, sap_file: Path, pipeline, verbose=True):
    """Test factual accuracy for a single protocol-SAP pair."""

    # Load files
    protocol = protocol_file.read_text(encoding='utf-8', errors='ignore')
    ground_truth_sap = sap_file.read_text(encoding='utf-8', errors='ignore')

    if verbose:
        print(f"\n  Protocol: {len(protocol)} chars")
        print(f"  Ground Truth SAP: {len(ground_truth_sap)} chars")

    # Extract facts from ground truth
    expected_facts = extract_facts_from_text(ground_truth_sap)

    if verbose:
        print(f"  Ground Truth Drug: {expected_facts.drug_name}")
        print(f"  Ground Truth Design: {'Single-arm' if expected_facts.is_single_arm else 'RCT' if expected_facts.is_randomized else 'Unknown'}")
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

        # Extract facts from generated SAP
        actual_facts = extract_facts_from_text(generated_sap)

        if verbose:
            print(f"  Generated Drug: {actual_facts.drug_name}")
            print(f"  Generated Design: {'Single-arm' if actual_facts.is_single_arm else 'RCT' if actual_facts.is_randomized else 'Unknown'}")

        # Compare facts
        comparison = compare_facts(expected_facts, actual_facts)

        return {
            "nct_id": nct_id,
            "expected": asdict(expected_facts),
            "actual": asdict(actual_facts),
            "comparison": comparison,
            "weighted_score": comparison["weighted_score"],
        }

    except Exception as e:
        if verbose:
            print(f"ERROR: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Factual accuracy test for SAP generator")
    parser.add_argument("--limit", type=int, default=5, help="Number of pairs to test")
    parser.add_argument("--nct", type=str, help="Test specific NCT ID")
    parser.add_argument("--random", action="store_true", help="Randomize selection")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed comparison")
    args = parser.parse_args()

    print("=" * 70)
    print("FACTUAL ACCURACY TEST - Measures REAL accuracy")
    print("=" * 70)
    print(f"\nChecks if generated SAP has CORRECT:")
    print("  - Drug name (not hallucinated)")
    print("  - Study design (single-arm vs RCT)")
    print("  - Blinding (open-label vs double-blind)")
    print("  - Statistical approach (descriptive vs hypothesis testing)")
    print("  - Sample size, phase, indication, etc.")
    print()

    # Get pairs
    base = Path(__file__).parent / "data" / "ground_truth"
    pairs = []

    for sap_file in sorted(base.glob("*_sap.txt")):
        nct_id = sap_file.stem.replace("_sap", "")
        protocol_file = base / f"{nct_id}_protocol.txt"
        if protocol_file.exists():
            pairs.append({"nct_id": nct_id, "protocol_file": protocol_file, "sap_file": sap_file})

    print(f"Found {len(pairs)} protocol-SAP pairs")

    if args.nct:
        pairs = [p for p in pairs if p["nct_id"] == args.nct]
        if not pairs:
            print(f"ERROR: {args.nct} not found")
            return 1
    else:
        if args.random:
            import random
            random.shuffle(pairs)
        pairs = pairs[:args.limit]

    print(f"Testing {len(pairs)} pairs...\n")

    # Initialize pipeline
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
            verbose=True
        )

        if result:
            results.append(result)
            comp = result["comparison"]

            # Color-coded score
            score = comp["weighted_score"]
            color = "\033[92m" if score >= 80 else "\033[93m" if score >= 60 else "\033[91m"

            print(f"\n  FACTUAL ACCURACY: {color}{score:.1f}%\033[0m")
            print(f"  Critical Facts: {comp['critical_matches']} correct")
            print(f"  All Facts: {comp['total_matches']} correct")

            # Show critical failures
            if comp["critical_failures"]:
                print(f"\n  \033[91mCRITICAL FAILURES:\033[0m")
                for cf in comp["critical_failures"]:
                    print(f"    ✗ {cf.fact_name}: Expected '{cf.expected}' but got '{cf.actual}'")

            if args.verbose:
                print(f"\n  ALL COMPARISONS:")
                for c in comp["comparisons"]:
                    status = "✓" if c.match else "✗"
                    crit = "[CRITICAL]" if c.critical else ""
                    print(f"    {status} {c.fact_name}: {c.expected} vs {c.actual} {crit}")
        else:
            print("  GENERATION FAILED")

        print()

    # Summary
    if results:
        scores = [r["weighted_score"] for r in results]
        avg = sum(scores) / len(scores)

        # Count critical failure rate
        critical_failures_total = sum(len(r["comparison"]["critical_failures"]) for r in results)
        critical_facts_total = len(results) * 7  # 7 critical facts per test

        excellent = sum(1 for s in scores if s >= 80)
        good = sum(1 for s in scores if 60 <= s < 80)
        poor = sum(1 for s in scores if s < 60)

        color = "\033[92m" if avg >= 80 else "\033[93m" if avg >= 60 else "\033[91m"

        print("=" * 70)
        print("FACTUAL ACCURACY RESULTS")
        print("=" * 70)
        print(f"""
  Tests Run: {len(results)}

  AVERAGE FACTUAL ACCURACY: {color}{avg:.1f}%\033[0m

  Critical Fact Failures: {critical_failures_total}/{critical_facts_total} ({critical_failures_total/critical_facts_total*100:.0f}% failure rate)

  Distribution:
    Excellent (80%+): {excellent} ({excellent/len(results)*100:.0f}%)
    Acceptable (60-79%): {good} ({good/len(results)*100:.0f}%)
    Poor (<60%): {poor} ({poor/len(results)*100:.0f}%)

  Best:  {max(results, key=lambda r: r['weighted_score'])['nct_id']} ({max(scores):.1f}%)
  Worst: {min(results, key=lambda r: r['weighted_score'])['nct_id']} ({min(scores):.1f}%)
""")

        # Verdict
        if avg >= 80 and critical_failures_total / critical_facts_total < 0.1:
            print("VERDICT: PRODUCTION READY")
        elif avg >= 60:
            print("VERDICT: NEEDS IMPROVEMENT - Critical fact extraction failing")
        else:
            print("VERDICT: NOT READY - Major accuracy issues")

        print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
