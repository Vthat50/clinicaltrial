#!/usr/bin/env python3
"""
Full Data Audit Script for Eval Set
Classifies files as SAP vs Protocol and assesses quality/completeness
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

EVAL_SET_DIR = "/mnt/c/Users/vijay/OneDrive/Documents/Github/clinicaltrial/sap_rtx4090/sap_generator/data/eval_set"

# Keywords that indicate a file is a REAL SAP (not a protocol)
SAP_STRONG_INDICATORS = [
    r"statistical\s+analysis\s+plan",
    r"SAP\s+version",
    r"SAP\s+v\d",
    r"analysis\s+plan\s+version",
    r"primary\s+analysis\s+plan",
    r"final\s+statistical\s+analysis",
]

# Keywords that indicate a file is a PROTOCOL (not a SAP)
PROTOCOL_INDICATORS = [
    r"clinical\s+study\s+protocol",
    r"study\s+protocol",
    r"investigator'?s?\s+brochure",
    r"protocol\s+version",
    r"protocol\s+amendment",
    r"protocol\s+update",
    r"irb\s+protocol",
    r"informed\s+consent",
    r"investigational\s+new\s+drug",
    r"IND\s+application",
]

# Key SAP sections to look for (completeness check)
SAP_SECTIONS = {
    "sample_size": [
        r"sample\s+size",
        r"power\s+calculation",
        r"power\s+analysis",
        r"statistical\s+power",
        r"sample\s+size\s+justification",
        r"N\s*=\s*\d+",
        r"\d+\s+patients?\s+will\s+be\s+enrolled",
    ],
    "populations": [
        r"analysis\s+population",
        r"intent.?to.?treat",
        r"ITT\s+population",
        r"per.?protocol\s+population",
        r"safety\s+population",
        r"full\s+analysis\s+set",
        r"FAS\s+population",
        r"modified\s+ITT",
        r"mITT",
    ],
    "endpoints": [
        r"primary\s+endpoint",
        r"secondary\s+endpoint",
        r"efficacy\s+endpoint",
        r"primary\s+outcome",
        r"overall\s+survival",
        r"progression.?free\s+survival",
        r"objective\s+response\s+rate",
        r"ORR",
        r"OS\s+endpoint",
        r"PFS\s+endpoint",
    ],
    "statistical_methods": [
        r"statistical\s+method",
        r"statistical\s+analysis",
        r"log.?rank\s+test",
        r"cox\s+regression",
        r"kaplan.?meier",
        r"hazard\s+ratio",
        r"confidence\s+interval",
        r"chi.?square",
        r"fisher'?s?\s+exact",
        r"ANCOVA",
        r"ANOVA",
        r"mixed\s+model",
        r"MMRM",
        r"stratified\s+analysis",
    ],
    "missing_data": [
        r"missing\s+data",
        r"missing\s+value",
        r"imputation",
        r"LOCF",
        r"last\s+observation\s+carried\s+forward",
        r"multiple\s+imputation",
        r"MAR",
        r"MCAR",
        r"MNAR",
        r"sensitivity\s+analysis",
    ],
    "interim_analysis": [
        r"interim\s+analysis",
        r"interim\s+analyses",
        r"data\s+monitoring",
        r"DSMB",
        r"DMC",
        r"O'?Brien.?Fleming",
        r"Lan.?DeMets",
        r"alpha\s+spending",
        r"group\s+sequential",
        r"stopping\s+rule",
        r"futility",
    ],
    "safety_analysis": [
        r"safety\s+analysis",
        r"adverse\s+event",
        r"AE\s+analysis",
        r"SAE\s+analysis",
        r"serious\s+adverse",
        r"toxicity\s+analysis",
        r"safety\s+population",
    ],
    "multiplicity": [
        r"multiplicity",
        r"multiple\s+comparison",
        r"bonferroni",
        r"hochberg",
        r"holm",
        r"gate.?keeping",
        r"hierarchical\s+testing",
        r"fixed.?sequence",
        r"alpha\s+allocation",
        r"familywise\s+error",
        r"FWER",
    ],
}

# Specific numerical values that indicate depth
DEPTH_INDICATORS = {
    "alpha_value": [r"alpha\s*[=:]\s*0\.\d+", r"significance\s+level\s*[=:]\s*0\.\d+", r"α\s*[=:]\s*0\.\d+"],
    "power_value": [r"power\s*[=:]\s*\d+%", r"power\s*[=:]\s*0\.\d+", r"\d+%\s+power"],
    "hazard_ratio": [r"hazard\s+ratio\s*[=:]\s*\d+\.?\d*", r"HR\s*[=:]\s*\d+\.?\d*"],
    "enrollment_number": [r"enroll\s+\d+\s+patient", r"N\s*=\s*\d{2,}", r"sample\s+size\s+of\s+\d+"],
}


def read_file_content(filepath: str, max_chars: int = 50000) -> str:
    """Read file content with encoding fallback"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read(max_chars)
    except UnicodeDecodeError:
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                return f.read(max_chars)
        except:
            return ""
    except:
        return ""


def classify_file(content: str) -> Tuple[str, float]:
    """
    Classify a file as SAP, PROTOCOL, or UNKNOWN
    Returns (classification, confidence)
    """
    content_lower = content.lower()

    # Count SAP indicators
    sap_score = 0
    for pattern in SAP_STRONG_INDICATORS:
        if re.search(pattern, content_lower):
            sap_score += 2

    # Count Protocol indicators
    protocol_score = 0
    for pattern in PROTOCOL_INDICATORS:
        if re.search(pattern, content_lower):
            protocol_score += 2

    # Check first 1000 chars for document type declaration
    first_section = content_lower[:1000]
    if re.search(r"statistical\s+analysis\s+plan", first_section):
        sap_score += 5
    if re.search(r"(study|clinical)\s+protocol", first_section):
        protocol_score += 5

    # Decision logic
    if sap_score > protocol_score + 2:
        confidence = min(1.0, sap_score / 10)
        return "SAP", confidence
    elif protocol_score > sap_score + 2:
        confidence = min(1.0, protocol_score / 10)
        return "PROTOCOL", confidence
    else:
        # Ambiguous - could be a protocol with stats section
        # Look for SAP section structure
        sap_section_count = 0
        for section_patterns in SAP_SECTIONS.values():
            for pattern in section_patterns:
                if re.search(pattern, content_lower):
                    sap_section_count += 1
                    break

        if sap_section_count >= 5:
            return "SAP", 0.6
        elif sap_section_count >= 3:
            return "MIXED", 0.5
        else:
            return "UNKNOWN", 0.3


def assess_completeness(content: str) -> Dict[str, bool]:
    """Check which key SAP sections are present"""
    content_lower = content.lower()
    completeness = {}

    for section_name, patterns in SAP_SECTIONS.items():
        found = False
        for pattern in patterns:
            if re.search(pattern, content_lower):
                found = True
                break
        completeness[section_name] = found

    return completeness


def assess_depth(content: str) -> Dict[str, List[str]]:
    """Check for specific numerical/methodological depth"""
    content_lower = content.lower()
    depth = {}

    for indicator_name, patterns in DEPTH_INDICATORS.items():
        matches = []
        for pattern in patterns:
            found = re.findall(pattern, content_lower)
            matches.extend(found)
        depth[indicator_name] = matches[:3]  # Keep first 3 matches

    return depth


def calculate_quality_score(
    classification: str,
    completeness: Dict[str, bool],
    depth: Dict[str, List[str]],
    file_size: int
) -> float:
    """Calculate overall quality score (0-100)"""
    score = 0

    # Base score for classification
    if classification == "SAP":
        score += 30
    elif classification == "MIXED":
        score += 15
    elif classification == "PROTOCOL":
        score += 5

    # Completeness score (up to 40 points)
    sections_present = sum(completeness.values())
    score += (sections_present / len(SAP_SECTIONS)) * 40

    # Depth score (up to 20 points)
    depth_count = sum(1 for matches in depth.values() if matches)
    score += (depth_count / len(DEPTH_INDICATORS)) * 20

    # File size bonus (longer = more detailed, up to 10 points)
    if file_size > 50000:
        score += 10
    elif file_size > 20000:
        score += 7
    elif file_size > 10000:
        score += 5
    elif file_size > 5000:
        score += 3

    return round(score, 1)


def audit_eval_set():
    """Run full audit on eval set"""
    results = []
    stats = defaultdict(int)

    # Find all SAP files
    sap_files = sorted(Path(EVAL_SET_DIR).glob("*_sap.txt"))
    print(f"Found {len(sap_files)} SAP files to audit\n")

    for i, sap_path in enumerate(sap_files):
        nct_id = sap_path.stem.replace("_sap", "")
        protocol_path = sap_path.parent / f"{nct_id}_protocol.txt"

        # Read SAP content
        sap_content = read_file_content(str(sap_path))
        sap_size = len(sap_content)

        # Check if protocol exists
        has_protocol = protocol_path.exists()
        protocol_size = 0
        if has_protocol:
            protocol_content = read_file_content(str(protocol_path))
            protocol_size = len(protocol_content)

        # Classify the SAP file
        classification, confidence = classify_file(sap_content)

        # Assess completeness and depth
        completeness = assess_completeness(sap_content)
        depth = assess_depth(sap_content)

        # Calculate quality score
        quality_score = calculate_quality_score(classification, completeness, depth, sap_size)

        # Update stats
        stats[classification] += 1
        stats["total"] += 1
        if has_protocol:
            stats["has_protocol"] += 1
        if quality_score >= 60:
            stats["high_quality"] += 1

        result = {
            "nct_id": nct_id,
            "classification": classification,
            "confidence": confidence,
            "quality_score": quality_score,
            "sap_size_chars": sap_size,
            "has_protocol": has_protocol,
            "protocol_size_chars": protocol_size,
            "completeness": completeness,
            "sections_present": sum(completeness.values()),
            "depth_indicators": {k: len(v) for k, v in depth.items()},
        }
        results.append(result)

        # Progress output
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(sap_files)}...")

    return results, dict(stats)


def print_summary(results: List[Dict], stats: Dict):
    """Print audit summary"""
    print("\n" + "=" * 70)
    print("EVAL SET DATA AUDIT SUMMARY")
    print("=" * 70)

    print(f"\nTotal files audited: {stats['total']}")
    print(f"  - Confirmed SAPs: {stats.get('SAP', 0)}")
    print(f"  - Protocols (mislabeled): {stats.get('PROTOCOL', 0)}")
    print(f"  - Mixed (protocol w/ stats): {stats.get('MIXED', 0)}")
    print(f"  - Unknown: {stats.get('UNKNOWN', 0)}")
    print(f"  - With matching protocol: {stats.get('has_protocol', 0)}")
    print(f"  - High quality (score >= 60): {stats.get('high_quality', 0)}")

    # Top quality files
    sorted_results = sorted(results, key=lambda x: x['quality_score'], reverse=True)

    print("\n" + "-" * 70)
    print("TOP 20 HIGHEST QUALITY SAPs (for benchmarking)")
    print("-" * 70)
    for i, r in enumerate(sorted_results[:20], 1):
        protocol_status = "✓ protocol" if r['has_protocol'] else "✗ no protocol"
        print(f"{i:2}. {r['nct_id']}: score={r['quality_score']:.1f}, "
              f"type={r['classification']}, sections={r['sections_present']}/8, "
              f"size={r['sap_size_chars']:,} chars, {protocol_status}")

    # Quality tiers
    print("\n" + "-" * 70)
    print("QUALITY TIERS")
    print("-" * 70)

    tier_a = [r for r in results if r['quality_score'] >= 70 and r['classification'] == 'SAP' and r['has_protocol']]
    tier_b = [r for r in results if r['quality_score'] >= 50 and r['classification'] in ['SAP', 'MIXED'] and r['has_protocol']]
    tier_c = [r for r in results if r['quality_score'] >= 30 and r['has_protocol']]

    print(f"\nTier A (Best - score>=70, confirmed SAP, has protocol): {len(tier_a)} files")
    print(f"Tier B (Good - score>=50, SAP/MIXED, has protocol): {len(tier_b)} files")
    print(f"Tier C (Usable - score>=30, has protocol): {len(tier_c)} files")

    # Section coverage
    print("\n" + "-" * 70)
    print("SECTION COVERAGE ACROSS ALL FILES")
    print("-" * 70)

    section_counts = defaultdict(int)
    for r in results:
        for section, present in r['completeness'].items():
            if present:
                section_counts[section] += 1

    for section, count in sorted(section_counts.items(), key=lambda x: -x[1]):
        pct = (count / len(results)) * 100
        print(f"  {section:20}: {count:3} files ({pct:.1f}%)")

    # Mislabeled files (protocols labeled as SAPs)
    protocols = [r for r in results if r['classification'] == 'PROTOCOL']
    if protocols:
        print("\n" + "-" * 70)
        print(f"MISLABELED FILES ({len(protocols)} protocols labeled as SAPs)")
        print("-" * 70)
        for r in protocols[:10]:
            print(f"  - {r['nct_id']}_sap.txt (size={r['sap_size_chars']:,} chars)")

    return tier_a, tier_b, tier_c


def main():
    print("=" * 70)
    print("EVAL SET DATA AUDIT")
    print("=" * 70)
    print(f"Directory: {EVAL_SET_DIR}")
    print("Analyzing all *_sap.txt files...\n")

    results, stats = audit_eval_set()
    tier_a, tier_b, tier_c = print_summary(results, stats)

    # Save full results
    output_path = Path(__file__).parent / "audit_results.json"
    with open(output_path, 'w') as f:
        json.dump({
            "stats": stats,
            "results": results,
            "tier_a_nct_ids": [r['nct_id'] for r in tier_a],
            "tier_b_nct_ids": [r['nct_id'] for r in tier_b],
            "tier_c_nct_ids": [r['nct_id'] for r in tier_c],
        }, f, indent=2)

    print(f"\n✓ Full results saved to: {output_path}")

    # Recommendation
    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    print(f"\nFor benchmarking, use Tier A files ({len(tier_a)} high-quality pairs).")
    print("These are confirmed SAPs with:")
    print("  - Clear 'Statistical Analysis Plan' document type")
    print("  - Most key sections present (sample size, endpoints, methods, etc.)")
    print("  - Specific numerical values (alpha, power, sample size)")
    print("  - Matching protocol file available")


if __name__ == "__main__":
    main()
