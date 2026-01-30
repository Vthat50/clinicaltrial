"""
SAP Benchmark using LOCAL Ollama (FREE, no API costs)

Usage (run on Windows PowerShell):
    python sap_benchmark_local.py --generated path/to/generated.txt --reference path/to/reference.txt

    OR test on your PACIFIC SAP:
    python sap_benchmark_local.py --test-pacific
"""

import json
import requests
from pathlib import Path
from typing import Dict, Any, Tuple

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3:8b"


def extract_fields(sap_text: str) -> Dict[str, Any]:
    """Extract fields from SAP using local Ollama."""

    prompt = f"""Extract these fields from the SAP document. Return ONLY valid JSON, nothing else.

{{
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
  "primary_endpoints": ["list like OS, PFS"],
  "primary_test": "<e.g. stratified log-rank or null>",
  "stratification_factors": ["list like age, sex, smoking"],
  "interim_count": <number or null>,
  "alpha_spending": "<e.g. Lan-DeMets or null>",
  "missing_data_method": "<method or null>",
  "multiplicity_method": "<method or null>"
}}

SAP TEXT (first 8000 chars):
{sap_text[:8000]}
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        result = response.json()
        content = result.get("response", "")

        # Extract JSON from response
        content = content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        return json.loads(content)

    except Exception as e:
        print(f"  Error: {e}")
        return {}


def compare_fields(gen: Dict, ref: Dict) -> Dict[str, Any]:
    """Compare extracted fields."""

    fields = [
        'sample_size', 'randomization_ratio', 'alpha', 'alpha_sided',
        'primary_endpoints', 'primary_test', 'stratification_factors',
        'power_pfs', 'power_os', 'pfs_events', 'os_events', 'pfs_hr', 'os_hr',
        'interim_count', 'alpha_spending', 'missing_data_method', 'multiplicity_method'
    ]

    results = {"matches": [], "partial": [], "mismatches": []}
    total_score = 0

    for field in fields:
        g = gen.get(field)
        r = ref.get(field)

        # Both null/empty
        if not g and not r:
            results["partial"].append((field, "both missing"))
            total_score += 0.25
            continue

        # One missing
        if not g:
            results["mismatches"].append((field, f"generated missing, ref={r}"))
            continue
        if not r:
            results["partial"].append((field, f"ref missing, gen={g}"))
            total_score += 0.5
            continue

        # Compare lists
        if isinstance(g, list) and isinstance(r, list):
            g_set = set(str(x).lower() for x in g)
            r_set = set(str(x).lower() for x in r)
            if g_set == r_set:
                results["matches"].append((field, str(g)))
                total_score += 1
            elif g_set & r_set:
                results["partial"].append((field, f"overlap: gen={g}, ref={r}"))
                total_score += 0.5
            else:
                results["mismatches"].append((field, f"gen={g}, ref={r}"))
            continue

        # Compare numbers
        if isinstance(g, (int, float)) and isinstance(r, (int, float)):
            if g == r:
                results["matches"].append((field, str(g)))
                total_score += 1
            elif abs(g - r) / max(abs(r), 1) < 0.05:
                results["partial"].append((field, f"close: gen={g}, ref={r}"))
                total_score += 0.8
            else:
                results["mismatches"].append((field, f"gen={g}, ref={r}"))
            continue

        # Compare strings
        if str(g).lower() == str(r).lower():
            results["matches"].append((field, str(g)))
            total_score += 1
        elif str(g).lower() in str(r).lower() or str(r).lower() in str(g).lower():
            results["partial"].append((field, f"partial: gen={g}, ref={r}"))
            total_score += 0.7
        else:
            results["mismatches"].append((field, f"gen={g}, ref={r}"))

    results["score"] = total_score / len(fields) * 100
    return results


def benchmark(generated_sap: str, reference_sap: str, nct_id: str = "unknown"):
    """Run benchmark comparison."""

    print(f"\n{'='*60}")
    print(f"BENCHMARK: {nct_id}")
    print(f"{'='*60}")
    print(f"Generated SAP: {len(generated_sap):,} chars")
    print(f"Reference SAP: {len(reference_sap):,} chars")

    print("\n[1/2] Extracting fields from GENERATED SAP...")
    gen_fields = extract_fields(generated_sap)
    print(f"  Found {sum(1 for v in gen_fields.values() if v)} fields")

    print("\n[2/2] Extracting fields from REFERENCE SAP...")
    ref_fields = extract_fields(reference_sap)
    print(f"  Found {sum(1 for v in ref_fields.values() if v)} fields")

    print("\nComparing fields...")
    results = compare_fields(gen_fields, ref_fields)

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")

    print(f"\n✅ MATCHES ({len(results['matches'])}):")
    for field, val in results['matches']:
        print(f"   {field}: {val}")

    print(f"\n⚠️  PARTIAL ({len(results['partial'])}):")
    for field, val in results['partial']:
        print(f"   {field}: {val}")

    print(f"\n❌ MISMATCHES ({len(results['mismatches'])}):")
    for field, val in results['mismatches']:
        print(f"   {field}: {val}")

    print(f"\n{'='*60}")
    print(f"SCORE: {results['score']:.1f}%")
    print(f"{'='*60}")

    return results


def test_pacific():
    """Test on PACIFIC SAP (NCT02125461)."""

    base_path = Path(__file__).parent.parent.parent

    gen_path = base_path / "data" / "eval_set" / "NCT02125461_sap.txt"  # Use reference as test
    ref_path = base_path / "data" / "eval_set" / "NCT02125461_sap.txt"

    # Check for generated SAP
    temp_gen = Path(r"C:\Users\vijay\AppData\Local\Temp\generated_sap.txt")
    if temp_gen.exists():
        gen_path = temp_gen

    print("Loading SAPs...")
    with open(gen_path, encoding='utf-8') as f:
        generated = f.read()
    with open(ref_path, encoding='utf-8') as f:
        reference = f.read()

    benchmark(generated, reference, "NCT02125461")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SAP Benchmark (Local Ollama)")
    parser.add_argument('--generated', type=str, help='Path to generated SAP')
    parser.add_argument('--reference', type=str, help='Path to reference SAP')
    parser.add_argument('--nct-id', type=str, default='unknown')
    parser.add_argument('--test-pacific', action='store_true', help='Test on PACIFIC SAP')

    args = parser.parse_args()

    if args.test_pacific:
        test_pacific()
    elif args.generated and args.reference:
        with open(args.generated, encoding='utf-8') as f:
            gen = f.read()
        with open(args.reference, encoding='utf-8') as f:
            ref = f.read()
        benchmark(gen, ref, args.nct_id)
    else:
        print("Usage:")
        print("  python sap_benchmark_local.py --test-pacific")
        print("  python sap_benchmark_local.py --generated <path> --reference <path>")
