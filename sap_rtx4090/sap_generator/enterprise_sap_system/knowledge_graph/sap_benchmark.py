"""
SAP Benchmark - Simple field-by-field comparison using Groq (free)

Usage:
    python sap_benchmark.py --generated /path/to/generated.txt --reference /path/to/reference.txt

    OR run on eval set:
    python sap_benchmark.py --eval-set ./data/eval_set --limit 10
"""

import json
import requests
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Groq API (free)
GROQ_API_KEY = "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"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


# ============================================================================
# FIELD EXTRACTION using Groq
# ============================================================================

EXTRACTION_PROMPT = """Extract these fields from the SAP document. Return ONLY valid JSON.

{
  "sample_size": <number or null>,
  "randomization_ratio": "<e.g. 2:1 or null>",
  "alpha": <e.g. 0.025 or null>,
  "alpha_sided": "<two-sided or one-sided or null>",
  "power_pfs": <e.g. 95 or null>,
  "power_os": <e.g. 85 or null>,
  "pfs_events": <number or null>,
  "os_events": <number or null>,
  "pfs_hr": <e.g. 0.67 or null>,
  "os_hr": <e.g. 0.73 or null>,
  "primary_endpoints": ["list of endpoints like OS, PFS"],
  "primary_test": "<e.g. stratified log-rank or null>",
  "stratification_factors": ["list like age, sex, smoking"],
  "interim_count": <number or null>,
  "alpha_spending": "<e.g. Lan-DeMets or null>",
  "missing_data_method": "<e.g. multiple imputation or null>",
  "multiplicity_method": "<e.g. Bonferroni or null>",
  "itt_definition": "<brief definition or null>",
  "safety_population": "<brief definition or null>"
}

SAP TEXT:
"""


def extract_fields_groq(sap_text: str, max_chars: int = 30000) -> Dict[str, Any]:
    """Extract fields from SAP using Groq/Llama 3.3 (free)."""

    # Truncate if needed (context limit)
    text = sap_text[:max_chars]

    try:
        response = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": EXTRACTION_PROMPT + text}],
                "temperature": 0,
                "max_tokens": 1000
            },
            timeout=60
        )

        result = response.json()

        if 'choices' in result:
            content = result['choices'][0]['message']['content']
            # Parse JSON from response (handle markdown code blocks)
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        else:
            print(f"Groq error: {result}")
            return {}

    except Exception as e:
        print(f"Extraction error: {e}")
        return {}


# ============================================================================
# FIELD COMPARISON
# ============================================================================

def compare_value(gen_val: Any, ref_val: Any, field_name: str) -> Tuple[float, str]:
    """Compare two values and return (score, explanation)."""

    # Both null
    if gen_val is None and ref_val is None:
        return 0.0, "both missing"

    # One null
    if gen_val is None:
        return 0.0, f"generated missing (ref: {ref_val})"
    if ref_val is None:
        return 0.5, f"reference missing (gen: {gen_val})"

    # Lists (endpoints, stratification)
    if isinstance(gen_val, list) and isinstance(ref_val, list):
        if not gen_val and not ref_val:
            return 0.0, "both empty"
        if not ref_val:
            return 0.5, "reference empty"

        gen_set = set(str(x).lower() for x in gen_val)
        ref_set = set(str(x).lower() for x in ref_val)

        if gen_set == ref_set:
            return 1.0, "exact match"

        overlap = len(gen_set & ref_set)
        total = len(ref_set)
        score = overlap / total if total > 0 else 0
        return score, f"partial ({overlap}/{total})"

    # Numbers
    if isinstance(gen_val, (int, float)) and isinstance(ref_val, (int, float)):
        if gen_val == ref_val:
            return 1.0, "exact match"

        # Allow 5% tolerance for numbers
        if ref_val != 0:
            diff = abs(gen_val - ref_val) / abs(ref_val)
            if diff <= 0.05:
                return 0.9, f"close ({gen_val} vs {ref_val})"
            elif diff <= 0.15:
                return 0.5, f"different ({gen_val} vs {ref_val})"

        return 0.0, f"mismatch ({gen_val} vs {ref_val})"

    # Strings
    gen_str = str(gen_val).lower().strip()
    ref_str = str(ref_val).lower().strip()

    if gen_str == ref_str:
        return 1.0, "exact match"

    # Partial string match
    if gen_str in ref_str or ref_str in gen_str:
        return 0.7, f"partial match"

    return 0.0, f"mismatch ({gen_val} vs {ref_val})"


def compare_fields(generated: Dict, reference: Dict) -> Dict[str, Any]:
    """Compare all fields between generated and reference."""

    fields = [
        # Critical fields
        'sample_size', 'randomization_ratio', 'alpha', 'alpha_sided',
        'primary_endpoints', 'primary_test',
        # Important fields
        'power_pfs', 'power_os', 'pfs_events', 'os_events', 'pfs_hr', 'os_hr',
        'stratification_factors', 'interim_count', 'alpha_spending',
        # Supporting fields
        'missing_data_method', 'multiplicity_method', 'itt_definition', 'safety_population'
    ]

    results = {}
    total_score = 0
    field_count = 0

    for field in fields:
        gen_val = generated.get(field)
        ref_val = reference.get(field)
        score, explanation = compare_value(gen_val, ref_val, field)

        results[field] = {
            'generated': gen_val,
            'reference': ref_val,
            'score': score,
            'explanation': explanation
        }

        total_score += score
        field_count += 1

    results['overall_score'] = total_score / field_count if field_count > 0 else 0

    return results


# ============================================================================
# MAIN BENCHMARK
# ============================================================================

def benchmark_single(generated_sap: str, reference_sap: str, nct_id: str = "unknown") -> Dict:
    """Benchmark a single generated SAP against reference."""

    print(f"\nExtracting fields from generated SAP...")
    gen_fields = extract_fields_groq(generated_sap)

    print(f"Extracting fields from reference SAP...")
    ref_fields = extract_fields_groq(reference_sap)

    print(f"Comparing fields...")
    comparison = compare_fields(gen_fields, ref_fields)

    return {
        'nct_id': nct_id,
        'generated_fields': gen_fields,
        'reference_fields': ref_fields,
        'comparison': comparison,
        'overall_score': comparison['overall_score']
    }


def print_results(results: Dict):
    """Print benchmark results in a nice format."""

    print("\n" + "=" * 70)
    print(f"BENCHMARK RESULTS: {results['nct_id']}")
    print("=" * 70)

    comparison = results['comparison']

    # Group by score
    matches = []
    partials = []
    mismatches = []

    for field, data in comparison.items():
        if field == 'overall_score':
            continue

        score = data['score']
        if score >= 0.9:
            matches.append((field, data))
        elif score >= 0.5:
            partials.append((field, data))
        else:
            mismatches.append((field, data))

    print(f"\n✅ MATCHES ({len(matches)}):")
    for field, data in matches:
        print(f"   {field}: {data['generated']}")

    print(f"\n⚠️ PARTIAL ({len(partials)}):")
    for field, data in partials:
        print(f"   {field}: {data['explanation']}")

    print(f"\n❌ MISMATCHES ({len(mismatches)}):")
    for field, data in mismatches:
        print(f"   {field}: {data['explanation']}")

    overall = comparison['overall_score'] * 100
    print(f"\n" + "=" * 70)
    print(f"OVERALL SCORE: {overall:.1f}%")
    print("=" * 70)

    return overall


def run_eval_set(eval_set_path: str, limit: int = None, api_url: str = None):
    """Run benchmark on eval set."""

    eval_path = Path(eval_set_path)
    pairs = []

    for sap_file in eval_path.glob("*_sap.txt"):
        nct_id = sap_file.stem.replace("_sap", "")
        protocol_file = eval_path / f"{nct_id}_protocol.txt"
        if protocol_file.exists():
            pairs.append((nct_id, protocol_file, sap_file))

    pairs = sorted(pairs)
    if limit:
        pairs = pairs[:limit]

    print(f"Found {len(pairs)} protocol-SAP pairs")

    all_scores = []

    for i, (nct_id, protocol_path, sap_path) in enumerate(pairs, 1):
        print(f"\n[{i}/{len(pairs)}] {nct_id}")

        with open(sap_path, encoding='utf-8') as f:
            reference_sap = f.read()

        # If API URL provided, generate SAP from protocol
        if api_url:
            with open(protocol_path, encoding='utf-8') as f:
                protocol = f.read()
            # TODO: Call API to generate SAP
            print("  (API generation not implemented yet)")
            continue
        else:
            # For now, compare reference to itself (sanity check)
            # In real usage, you'd load the generated SAP here
            print("  (No generated SAP - skipping)")
            continue

    if all_scores:
        avg = sum(all_scores) / len(all_scores)
        print(f"\n{'=' * 70}")
        print(f"AVERAGE SCORE: {avg:.1f}%")
        print(f"{'=' * 70}")


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SAP Benchmark")
    parser.add_argument('--generated', type=str, help='Path to generated SAP')
    parser.add_argument('--reference', type=str, help='Path to reference SAP')
    parser.add_argument('--nct-id', type=str, default='unknown', help='NCT ID')
    parser.add_argument('--eval-set', type=str, help='Path to eval set directory')
    parser.add_argument('--limit', type=int, help='Limit number of evaluations')
    parser.add_argument('--api-url', type=str, help='Your backend API URL')

    args = parser.parse_args()

    if args.generated and args.reference:
        # Single benchmark
        with open(args.generated, encoding='utf-8') as f:
            generated = f.read()
        with open(args.reference, encoding='utf-8') as f:
            reference = f.read()

        results = benchmark_single(generated, reference, args.nct_id)
        print_results(results)

    elif args.eval_set:
        # Eval set benchmark
        run_eval_set(args.eval_set, args.limit, args.api_url)

    else:
        print("Usage:")
        print("  python sap_benchmark.py --generated <path> --reference <path>")
        print("  python sap_benchmark.py --eval-set <path> --limit 10")
