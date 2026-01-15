"""
SAP Full Benchmark - Automated Pipeline (with GPU + Parallel Processing)

1. Reads protocol from eval set
2. Calls YOUR backend API to generate SAP (parallel)
3. Compares generated SAP to reference SAP using Claude or local Ollama
4. Outputs scores

Usage:
    # With Claude Sonnet (fast, ~$6 for 280 protocols)
    python sap_benchmark_full.py --api-url http://localhost:8001 --use-claude --parallel 4
    python sap_benchmark_full.py --api-url http://localhost:8001 --use-claude --limit 10

    # With local Ollama (free, slower)
    python sap_benchmark_full.py --api-url http://localhost:8001 --limit 5
    python sap_benchmark_full.py --api-url http://localhost:8001 --nct-id NCT02125461
"""

import json
import requests
import time
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Claude API
try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

# ============================================================================
# CONFIG
# ============================================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3:8b"

# Your backend endpoint (change if different)
# Options: /generate-full (fast, rule-based), /generate-direct (slow, LLM)
BACKEND_ENDPOINT = "/generate-full"

# 8 Essential Oncology SAP Sections (for faster benchmarking)
ESSENTIAL_SECTIONS = [
    "4",   # Sample Size & Power
    "5",   # Analysis Populations
    "6",   # Endpoints & Estimands
    "7",   # Statistical Methods
    "8",   # Censoring Rules
    "9",   # Missing Data Handling
    "12",  # Safety Analysis
    "13",  # Interim Analysis
]


# ============================================================================
# BACKEND API - Generate SAP from protocol
# ============================================================================

def generate_sap_from_backend(api_url: str, protocol_text: str, nct_id: str = None, use_workbench: bool = True) -> str:
    """Call your backend to generate SAP from protocol.

    If use_workbench=True, uses the Workbench mode (section-by-section with tool-calling).
    If use_workbench=False, uses the Quick Protocol mode (/generate-full).
    """

    base_url = api_url.rstrip('/')

    if use_workbench:
        return generate_sap_workbench_mode(base_url, protocol_text, nct_id)
    else:
        return generate_sap_quick_mode(base_url, protocol_text, nct_id)


def generate_sap_quick_mode(base_url: str, protocol_text: str, nct_id: str = None) -> str:
    """Quick Protocol mode - single API call with tool-calling."""

    url = f"{base_url}{BACKEND_ENDPOINT}"

    try:
        print(f"  Calling backend API (Quick Protocol mode)...")
        response = requests.post(
            url,
            json={
                "protocol_text": protocol_text,
                "nct_id": nct_id
            },
            timeout=None
        )

        if response.status_code == 200:
            data = response.json()
            sap = data.get("sap") or data.get("sap_text") or data.get("generated_sap") or data.get("result", "")
            if sap:
                print(f"  Generated SAP: {len(sap):,} chars")
                return sap
            else:
                print(f"  Warning: Empty SAP in response. Keys: {list(data.keys())}")
                return ""
        else:
            print(f"  Error: {response.status_code} - {response.text[:200]}")
            return ""

    except Exception as e:
        print(f"  Error: {e}")
        return ""


def generate_sap_workbench_mode(base_url: str, protocol_text: str, nct_id: str = None, essential_only: bool = True) -> str:
    """Workbench mode - section-by-section generation with tool-calling.

    Args:
        essential_only: If True, only generate the 8 essential oncology sections.
    """

    try:
        # Step 1: Create workspace with protocol
        print(f"  [Workbench] Creating workspace...")
        resp = requests.post(
            f"{base_url}/workbench/create",
            json={
                "protocol_content": protocol_text,
                "protocol_filename": f"{nct_id or 'benchmark'}_protocol.txt",
                "phase": "",
                "therapeutic_area": "oncology",
                "indication": ""
            },
            timeout=300  # 5 min timeout for workspace creation (can be slow under load)
        )
        if resp.status_code != 200:
            print(f"  Error creating workspace: {resp.status_code} - {resp.text[:200]}")
            return ""

        workspace_id = resp.json().get("id")
        print(f"  [Workbench] Workspace created: {workspace_id}")

        # Step 2: Get section outline
        print(f"  [Workbench] Getting section outline...")
        resp = requests.get(f"{base_url}/workbench/{workspace_id}/outline", timeout=120)
        if resp.status_code != 200:
            print(f"  Error getting outline: {resp.status_code}")
            return ""

        all_sections = resp.json().get("sections", [])

        # Filter to essential sections only
        if essential_only:
            sections = [s for s in all_sections if s.get("id") in ESSENTIAL_SECTIONS]
            print(f"  [Workbench] Generating {len(sections)}/8 essential sections (skipping {len(all_sections) - len(sections)} others)")
        else:
            sections = all_sections
            print(f"  [Workbench] Generating all {len(sections)} sections")

        # Step 3: Generate each section with tool-calling
        all_content = []
        for i, section in enumerate(sections, 1):
            section_id = section.get("id")
            section_name = section.get("display_name", section.get("name", section_id))
            print(f"  [Workbench] Generating section {i}/{len(sections)}: {section_name}...")

            resp = requests.post(
                f"{base_url}/workbench/{workspace_id}/generate/{section_id}",
                timeout=None  # No timeout
            )

            if resp.status_code == 200:
                content = resp.json().get("content", "")
                if content:
                    all_content.append(f"## {section_name}\n\n{content}")
                    print(f"    Generated {len(content):,} chars")
                else:
                    print(f"    Warning: Empty content")
            else:
                print(f"    Error: {resp.status_code} - {resp.text[:100]}")

        # Step 4: Combine all sections
        full_sap = "\n\n".join(all_content)
        print(f"  [Workbench] Complete SAP: {len(full_sap):,} chars from {len(all_content)} sections")
        return full_sap

    except Exception as e:
        print(f"  [Workbench] Error: {e}")
        import traceback
        traceback.print_exc()
        return ""


# ============================================================================
# OLLAMA - Extract fields locally (FREE)
# ============================================================================

EXTRACTION_PROMPT = """You are extracting statistical parameters from a clinical trial SAP (Statistical Analysis Plan).

Extract these fields. Look for synonyms and variations. Return ONLY valid JSON.

FIELD DEFINITIONS:
- sample_size: Total number of patients/subjects (look for "N=", "n=", "sample size", "patients enrolled", "subjects")
- randomization_ratio: Allocation ratio (e.g., "1:1", "2:1", "1:1:1"). Look for "randomized", "allocated", "assigned"
- alpha: Significance level (e.g., 0.05, 0.025, 0.01). Look for "alpha", "significance level", "type I error", "p<"
- alpha_sided: "one-sided" or "two-sided". Look for "1-sided", "2-sided", "one-tailed", "two-tailed"
- power_pfs: Power for PFS endpoint (e.g., 80, 90). Look for "power", "%" near PFS/progression-free
- power_os: Power for OS endpoint (e.g., 80, 90). Look for "power", "%" near OS/overall survival
- primary_endpoints: List of primary endpoints. Synonyms: OS=Overall Survival, PFS=Progression-Free Survival, ORR=Overall Response Rate, DOR=Duration of Response, CR=Complete Response, TTF=Time to Treatment Failure
- primary_test: Statistical test for primary analysis. Look for "log-rank", "Cox", "Fisher", "chi-square", "t-test", "Wilcoxon", "ANOVA", "Kaplan-Meier"
- stratification_factors: Factors used for stratified randomization. Look for "stratified by", "stratification factors"
- interim_count: Number of interim analyses (0 if none). Look for "interim analysis", "interim analyses", "DSMB"
- alpha_spending: Alpha spending function. Look for "O'Brien-Fleming", "Lan-DeMets", "Pocock", "alpha spending"
- missing_data_method: Method for handling missing data. Look for "LOCF", "MMRM", "multiple imputation", "complete case", "censored"
- multiplicity_method: Method for multiple comparisons. Look for "Bonferroni", "Hochberg", "Holm", "gatekeeping", "hierarchical", "fixed-sequence"

IMPORTANT:
- If a field is not mentioned, return null
- For primary_endpoints, use standard abbreviations: OS, PFS, ORR, DOR, CR, PR, TTF, EFS, DFS
- For numbers, return just the number (not string)
- Be thorough - search the entire document

Return JSON:
{
  "sample_size": <number or null>,
  "randomization_ratio": "<e.g. 2:1>" or null,
  "alpha": <e.g. 0.025> or null,
  "alpha_sided": "<two-sided or one-sided>" or null,
  "power_pfs": <e.g. 90> or null,
  "power_os": <e.g. 80> or null,
  "primary_endpoints": ["OS", "PFS"] or null,
  "primary_test": "<e.g. stratified log-rank>" or null,
  "stratification_factors": ["factor1", "factor2"] or null,
  "interim_count": <number> or null,
  "alpha_spending": "<method>" or null,
  "missing_data_method": "<method>" or null,
  "multiplicity_method": "<method>" or null
}

SAP TEXT:
"""


def extract_fields_ollama(sap_text: str) -> Dict[str, Any]:
    """Extract fields using local Ollama (free)."""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": EXTRACTION_PROMPT + sap_text[:8000],
                "stream": False
            },
            timeout=120
        )

        content = response.json().get("response", "")

        # Parse JSON
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        return json.loads(content.strip())

    except Exception as e:
        print(f"  Ollama error: {e}")
        return {}


def extract_fields_claude(sap_text: str, client: "anthropic.Anthropic") -> Dict[str, Any]:
    """Extract fields using Claude Sonnet (fast, accurate, ~$0.01 per call)."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": EXTRACTION_PROMPT + sap_text[:30000]  # More context for better extraction
            }]
        )

        content = response.content[0].text

        # Parse JSON
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        return json.loads(content.strip())

    except Exception as e:
        print(f"  Claude error: {e}")
        return {}


# ============================================================================
# COMPARISON
# ============================================================================

def compare_fields(gen: Dict, ref: Dict) -> Dict[str, Any]:
    """Compare generated vs reference fields."""

    fields = [
        'sample_size', 'randomization_ratio', 'alpha', 'alpha_sided',
        'primary_endpoints', 'primary_test', 'stratification_factors',
        'power_pfs', 'power_os', 'interim_count', 'alpha_spending',
        'missing_data_method', 'multiplicity_method'
    ]

    matches = []
    partial = []
    mismatches = []
    score = 0

    for field in fields:
        g = gen.get(field)
        r = ref.get(field)

        if not g and not r:
            partial.append(field)
            score += 0.25
        elif not g:
            mismatches.append(field)
        elif not r:
            partial.append(field)
            score += 0.5
        elif isinstance(g, list) and isinstance(r, list):
            g_set = set(str(x).lower() for x in g)
            r_set = set(str(x).lower() for x in r)
            if g_set == r_set:
                matches.append(field)
                score += 1
            elif g_set & r_set:
                partial.append(field)
                score += 0.5
            else:
                mismatches.append(field)
        elif str(g).lower() == str(r).lower():
            matches.append(field)
            score += 1
        elif isinstance(g, (int, float)) and isinstance(r, (int, float)):
            if abs(g - r) / max(abs(r), 1) < 0.05:
                matches.append(field)
                score += 1
            else:
                mismatches.append(field)
        else:
            mismatches.append(field)

    return {
        "matches": matches,
        "partial": partial,
        "mismatches": mismatches,
        "score": score / len(fields) * 100
    }


# ============================================================================
# SINGLE BENCHMARK
# ============================================================================

def benchmark_single(
    api_url: str,
    protocol_text: str,
    reference_sap: str,
    nct_id: str,
    use_claude: bool = False,
    claude_client: "anthropic.Anthropic" = None
) -> Dict[str, Any]:
    """Benchmark a single protocol."""

    print(f"\n{'='*60}")
    print(f"BENCHMARKING: {nct_id}")
    print(f"{'='*60}")

    # Step 1: Generate SAP from your backend
    print("\n[1/3] Generating SAP from your backend...")
    generated_sap = generate_sap_from_backend(api_url, protocol_text, nct_id)

    if not generated_sap:
        return {"nct_id": nct_id, "error": "Failed to generate SAP", "score": 0}

    # Step 2: Extract fields from both SAPs
    if use_claude and claude_client:
        print("\n[2/3] Extracting fields (using Claude Sonnet)...")
        print("  From generated SAP...")
        gen_fields = extract_fields_claude(generated_sap, claude_client)
        print("  From reference SAP...")
        ref_fields = extract_fields_claude(reference_sap, claude_client)
    else:
        print("\n[2/3] Extracting fields (using local Ollama)...")
        print("  From generated SAP...")
        gen_fields = extract_fields_ollama(generated_sap)
        print("  From reference SAP...")
        ref_fields = extract_fields_ollama(reference_sap)

    # Step 3: Compare
    print("\n[3/3] Comparing fields...")
    comparison = compare_fields(gen_fields, ref_fields)

    # Print results
    print(f"\n✅ Matches ({len(comparison['matches'])}): {', '.join(comparison['matches'])}")
    print(f"⚠️  Partial ({len(comparison['partial'])}): {', '.join(comparison['partial'])}")
    print(f"❌ Mismatches ({len(comparison['mismatches'])}): {', '.join(comparison['mismatches'])}")
    print(f"\nSCORE: {comparison['score']:.1f}%")

    return {
        "nct_id": nct_id,
        "score": comparison["score"],
        "matches": comparison["matches"],
        "partial": comparison["partial"],
        "mismatches": comparison["mismatches"],
        "generated_fields": gen_fields,
        "reference_fields": ref_fields
    }


# ============================================================================
# FULL BENCHMARK (Multiple protocols)
# ============================================================================

def process_single_protocol(args):
    """Process a single protocol (for parallel execution)."""
    api_url, nct_id, protocol_path, sap_path, use_claude, claude_client = args

    try:
        with open(protocol_path, encoding='utf-8') as f:
            protocol = f.read()
        with open(sap_path, encoding='utf-8') as f:
            reference = f.read()

        result = benchmark_single(api_url, protocol, reference, nct_id, use_claude, claude_client)
        return result

    except Exception as e:
        return {"nct_id": nct_id, "error": str(e), "score": 0}


def run_full_benchmark(
    api_url: str,
    eval_set_path: str,
    limit: int = None,
    nct_ids: List[str] = None,
    parallel: int = 1,
    use_claude: bool = False
) -> List[Dict]:
    """Run benchmark on eval set with optional parallel processing."""

    # Initialize Claude client if needed
    claude_client = None
    if use_claude:
        if not CLAUDE_AVAILABLE:
            print("ERROR: anthropic package not installed. Run: pip install anthropic")
            return []
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY not set in environment")
            return []
        claude_client = anthropic.Anthropic(api_key=api_key)
        print("Using Claude Sonnet for extraction (~$0.01 per SAP)")

    eval_path = Path(eval_set_path)

    # Get protocol-SAP pairs
    pairs = []
    for sap_file in sorted(eval_path.glob("*_sap.txt")):
        nct_id = sap_file.stem.replace("_sap", "")
        protocol_file = eval_path / f"{nct_id}_protocol.txt"

        if protocol_file.exists():
            if nct_ids and nct_id not in nct_ids:
                continue
            pairs.append((nct_id, protocol_file, sap_file))

    if limit:
        pairs = pairs[:limit]

    print(f"\n{'='*60}")
    print(f"SAP BENCHMARK - {len(pairs)} protocols")
    print(f"API: {api_url}")
    print(f"Eval set: {eval_set_path}")
    print(f"Parallel workers: {parallel}")
    print(f"{'='*60}")

    results = []

    if parallel > 1:
        # Parallel processing
        print(f"\nRunning {len(pairs)} benchmarks with {parallel} parallel workers...")

        tasks = [(api_url, nct_id, proto_path, sap_path, use_claude, claude_client)
                 for nct_id, proto_path, sap_path in pairs]

        with ThreadPoolExecutor(max_workers=parallel) as executor:
            future_to_nct = {executor.submit(process_single_protocol, task): task[1]
                           for task in tasks}

            completed = 0
            for future in as_completed(future_to_nct):
                nct_id = future_to_nct[future]
                completed += 1
                try:
                    result = future.result()
                    results.append(result)
                    score = result.get('score', 0)
                    print(f"[{completed}/{len(pairs)}] {nct_id}: {score:.1f}%")
                except Exception as e:
                    print(f"[{completed}/{len(pairs)}] {nct_id}: ERROR - {e}")
                    results.append({"nct_id": nct_id, "error": str(e), "score": 0})
    else:
        # Sequential processing
        for i, (nct_id, protocol_path, sap_path) in enumerate(pairs, 1):
            print(f"\n[{i}/{len(pairs)}] Processing {nct_id}...")

            try:
                with open(protocol_path, encoding='utf-8') as f:
                    protocol = f.read()
                with open(sap_path, encoding='utf-8') as f:
                    reference = f.read()

                result = benchmark_single(api_url, protocol, reference, nct_id, use_claude, claude_client)
                results.append(result)

                # Small delay between API calls
                time.sleep(1)

            except Exception as e:
                print(f"  Error: {e}")
                results.append({"nct_id": nct_id, "error": str(e), "score": 0})

    # Summary
    print(f"\n{'='*60}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*60}")

    scores = [r["score"] for r in results if "score" in r and r["score"] > 0]

    if scores:
        print(f"\nProtocols tested: {len(pairs)}")
        print(f"Successful: {len(scores)}")
        print(f"Failed: {len(pairs) - len(scores)}")
        print(f"\nAverage Score: {sum(scores)/len(scores):.1f}%")
        print(f"Min Score: {min(scores):.1f}%")
        print(f"Max Score: {max(scores):.1f}%")

        # Per-protocol scores
        print(f"\nPer-protocol scores:")
        for r in results:
            if "error" in r and r.get("score", 0) == 0:
                print(f"  {r['nct_id']}: ERROR - {r['error']}")
            else:
                print(f"  {r['nct_id']}: {r['score']:.1f}%")

    # Save results
    output_file = Path("benchmark_results.json")
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "api_url": api_url,
            "total_protocols": len(pairs),
            "average_score": sum(scores)/len(scores) if scores else 0,
            "results": results
        }, f, indent=2)
    print(f"\nResults saved to: {output_file}")

    return results


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SAP Full Benchmark")
    parser.add_argument('--api-url', type=str, default="http://localhost:8000",
                        help='Your backend API URL')
    parser.add_argument('--eval-set', type=str, default="data/eval_set",
                        help='Path to eval set')
    parser.add_argument('--limit', type=int, help='Limit number of protocols')
    parser.add_argument('--nct-id', type=str, help='Test specific NCT ID')
    parser.add_argument('--parallel', type=int, default=1, help='Number of parallel workers (default: 1)')
    parser.add_argument('--use-claude', action='store_true', help='Use Claude Sonnet for extraction (faster, ~$6 for 280 protocols)')
    parser.add_argument('--tier-a', action='store_true', help='Only use Tier A (high-quality) SAP files from audit')

    args = parser.parse_args()

    nct_ids = None
    if args.nct_id:
        nct_ids = [args.nct_id]
    elif args.tier_a:
        # Load Tier A NCT IDs from audit results
        audit_file = Path(__file__).parent / "audit_results.json"
        if audit_file.exists():
            with open(audit_file) as f:
                audit_data = json.load(f)
            nct_ids = audit_data.get("tier_a_nct_ids", [])
            print(f"Using {len(nct_ids)} Tier A (high-quality) SAPs from audit")
        else:
            print("WARNING: audit_results.json not found. Run data_audit.py first.")
            print("Falling back to all SAP files.")

    run_full_benchmark(
        api_url=args.api_url,
        eval_set_path=args.eval_set,
        limit=args.limit,
        nct_ids=nct_ids,
        parallel=args.parallel,
        use_claude=args.use_claude
    )
