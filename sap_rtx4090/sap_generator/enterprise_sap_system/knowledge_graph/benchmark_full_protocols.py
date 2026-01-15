"""
Full Protocol Benchmark - Tests SAP generation against real SAPs.

This benchmark:
1. Extracts text from full protocol PDFs
2. Sends to the SAP generation system
3. Compares generated SAP to real SAP (from pharma)
4. Scores using LLM judge
"""

import os
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import requests
import anthropic
import PyPDF2

# Paths
CT_DOWNLOADS = Path("/mnt/c/Users/vijay/Desktop/sap_data/ct_downloads")
REFERENCE_SAPS = Path("/mnt/c/Users/vijay/OneDrive/Documents/Github/clinicaltrial/sap_rtx4090/sap_generator/enterprise_sap_system/knowledge_graph/reference_saps")

# 5 selected trials for validation
VALIDATION_TRIALS = [
    {
        "name": "ADAURA",
        "protocol": REFERENCE_SAPS / "protocols" / "ADAURA_Protocol.pdf",
        "sap": REFERENCE_SAPS / "full_saps" / "ADAURA_SAP.pdf",
        "indication": "NSCLC",
        "phase": "Phase 3"
    },
    {
        "name": "KEYNOTE-042",
        "protocol": REFERENCE_SAPS / "protocols" / "KEYNOTE-042_ProtSAP.pdf",
        "sap": REFERENCE_SAPS / "full_saps" / "KEYNOTE-042_SAP.pdf",
        "indication": "NSCLC",
        "phase": "Phase 3"
    },
    {
        "name": "NCT01515748",
        "protocol": CT_DOWNLOADS / "all_protocols" / "NCT01515748_Protocol.pdf",
        "sap": CT_DOWNLOADS / "all_saps" / "NCT01515748_SAP.pdf",
        "indication": "Gastric Cancer",
        "phase": "Phase 3"
    },
    {
        "name": "CheckMate-901",
        "protocol": REFERENCE_SAPS / "protocols" / "CheckMate-901_ProtSAP.pdf",
        "sap": REFERENCE_SAPS / "full_saps" / "CheckMate-901_SAP.pdf",
        "indication": "Urothelial",
        "phase": "Phase 3"
    },
    {
        "name": "VISION",
        "protocol": REFERENCE_SAPS / "protocols" / "VISION_Protocol.pdf",
        "sap": REFERENCE_SAPS / "full_saps" / "VISION_SAP.pdf",
        "indication": "Prostate",
        "phase": "Phase 3"
    }
]

# Sections to evaluate
SECTIONS_TO_EVALUATE = [
    ("analysis_populations", "5", ["analysis population", "study population", "full analysis", "intent to treat", "per protocol"]),
    ("sample_size", "4", ["sample size", "power calculation", "power analysis", "number of patients", "enrollment"]),
    ("statistical_methods", "7", ["statistical method", "statistical analysis", "primary analysis", "efficacy analysis"]),
    ("missing_data", "9", ["missing data", "missing value", "imputation"]),
    ("safety_analysis", "12", ["safety analysis", "adverse event", "safety endpoint"]),
    ("interim_analysis", "13", ["interim analysis", "interim look", "data monitoring", "dmc", "dsmb"]),
]


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract all text from a PDF file."""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n".join(text_parts)
    except Exception as e:
        print(f"Error extracting PDF {pdf_path}: {e}")
        return ""


def extract_section_from_sap(sap_text: str, section_keywords: List[str]) -> str:
    """Extract a section from SAP text based on keywords."""
    lines = sap_text.split('\n')

    # Find section start
    start_idx = -1
    for i, line in enumerate(lines):
        line_lower = line.lower()
        for keyword in section_keywords:
            if keyword in line_lower and len(line.strip()) < 200:  # Likely a header
                start_idx = i
                break
        if start_idx != -1:
            break

    if start_idx == -1:
        return ""

    # Find section end (next major header or 5000 chars)
    end_idx = min(start_idx + 200, len(lines))  # Default to 200 lines
    section_text = '\n'.join(lines[start_idx:end_idx])

    # Limit to 5000 chars
    return section_text[:5000].strip()


def generate_sap_section(api_url: str, workspace_id: str, section_id: str) -> str:
    """Generate a single section using the workbench API."""
    try:
        resp = requests.post(
            f"{api_url}/workbench/{workspace_id}/generate/{section_id}",
            timeout=180
        )
        if resp.status_code == 200:
            return resp.json().get("content", "")
        else:
            print(f"  API error: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        print(f"  Error generating section: {e}")
    return ""


def compare_sections_with_llm(
    generated: str,
    reference: str,
    section_name: str,
    client: anthropic.Anthropic
) -> Dict:
    """Use Claude to compare generated vs reference section."""

    if not generated.strip():
        return {
            "accuracy": 1,
            "completeness": 1,
            "quality": 1,
            "summary": "No content generated",
            "gaps": ["Section not generated"]
        }

    if not reference.strip():
        return {
            "accuracy": 5,
            "completeness": 5,
            "quality": 7,
            "summary": "No reference section found for comparison",
            "gaps": ["Cannot compare - reference section not found"]
        }

    prompt = f"""Compare this GENERATED SAP section to the REFERENCE SAP section.

SECTION: {section_name.replace('_', ' ').upper()}

GENERATED:
{generated[:4000]}

REFERENCE (from real pharma SAP):
{reference[:4000]}

Score on three dimensions (1-10 scale):

1. ACCURACY (1-10): Does the generated content contain correct statistical methods and values?
   - Are the methods appropriate for this trial type?
   - Are any methods wrong or inappropriate?

2. COMPLETENESS (1-10): Does it cover the same key elements as the reference?
   - Missing critical components?
   - Reference has elements that generated lacks?

3. QUALITY (1-10): Is it professionally written and FDA-ready?
   - Clear, well-structured?
   - Appropriate statistical language?

Return JSON only:
{{"accuracy": <1-10>, "completeness": <1-10>, "quality": <1-10>, "summary": "<1 sentence>", "gaps": ["<gap1>", "<gap2>"]}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text
        # Extract JSON
        if '{' in text and '}' in text:
            json_str = text[text.find('{'):text.rfind('}')+1]
            return json.loads(json_str)
    except Exception as e:
        print(f"  LLM comparison error: {e}")

    return {"accuracy": 5, "completeness": 5, "quality": 5, "summary": "Comparison failed", "gaps": []}


def run_trial_benchmark(
    trial: Dict,
    api_url: str,
    client: anthropic.Anthropic
) -> Dict:
    """Run benchmark on a single trial."""

    print(f"\n{'='*70}")
    print(f"BENCHMARKING: {trial['name']} ({trial['indication']}, {trial['phase']})")
    print(f"{'='*70}")

    # Step 1: Extract protocol text
    print("\n[1/5] Extracting protocol PDF...")
    protocol_text = extract_text_from_pdf(trial['protocol'])
    print(f"  Protocol: {len(protocol_text):,} chars from {trial['protocol'].name}")

    if len(protocol_text) < 1000:
        return {"error": "Failed to extract protocol text"}

    # Step 2: Extract reference SAP text
    print("\n[2/5] Extracting reference SAP PDF...")
    reference_sap = extract_text_from_pdf(trial['sap'])
    print(f"  Reference SAP: {len(reference_sap):,} chars from {trial['sap'].name}")

    # Step 3: Create workspace
    print("\n[3/5] Creating workspace and generating SAP...")
    try:
        resp = requests.post(
            f"{api_url}/workbench/create",
            json={
                "protocol_content": protocol_text[:200000],  # Limit to 200K chars
                "protocol_filename": trial['protocol'].name,
                "phase": trial['phase'],
                "therapeutic_area": "oncology",
                "indication": trial['indication']
            },
            timeout=120
        )

        if resp.status_code != 200:
            return {"error": f"Failed to create workspace: {resp.text[:200]}"}

        workspace_id = resp.json().get("id")
        print(f"  Workspace: {workspace_id}")
    except Exception as e:
        return {"error": f"Workspace creation failed: {e}"}

    # Step 4: Generate and compare each section
    print("\n[4/5] Generating and comparing sections...")
    results = {}

    for section_name, section_id, keywords in SECTIONS_TO_EVALUATE:
        print(f"\n  --- {section_name.upper().replace('_', ' ')} ---")

        # Generate section
        generated = generate_sap_section(api_url, workspace_id, section_id)
        print(f"  Generated: {len(generated):,} chars")

        # Extract reference section
        reference = extract_section_from_sap(reference_sap, keywords)
        print(f"  Reference: {len(reference):,} chars")

        # Compare with LLM
        print(f"  Comparing...")
        comparison = compare_sections_with_llm(generated, reference, section_name, client)
        print(f"  Scores: acc={comparison.get('accuracy')}, comp={comparison.get('completeness')}, qual={comparison.get('quality')}")

        results[section_name] = {
            "generated_chars": len(generated),
            "reference_chars": len(reference),
            **comparison
        }

    # Step 5: Calculate overall scores
    print("\n[5/5] Calculating overall scores...")

    accuracies = [r.get("accuracy", 0) for r in results.values()]
    completeness = [r.get("completeness", 0) for r in results.values()]
    qualities = [r.get("quality", 0) for r in results.values()]

    overall = {
        "trial": trial['name'],
        "indication": trial['indication'],
        "phase": trial['phase'],
        "protocol_chars": len(protocol_text),
        "reference_sap_chars": len(reference_sap),
        "accuracy": sum(accuracies) / len(accuracies) if accuracies else 0,
        "completeness": sum(completeness) / len(completeness) if completeness else 0,
        "quality": sum(qualities) / len(qualities) if qualities else 0,
        "sections": results
    }

    overall["overall_score"] = (overall["accuracy"] + overall["completeness"] + overall["quality"]) / 3

    return overall


def print_results(results: List[Dict]):
    """Print formatted benchmark results."""

    print("\n" + "="*70)
    print("BENCHMARK RESULTS SUMMARY")
    print("="*70)

    # Per-trial results
    print("\nPER-TRIAL SCORES:")
    print("-"*70)
    print(f"{'Trial':<20} {'Accuracy':>10} {'Complete':>10} {'Quality':>10} {'Overall':>10}")
    print("-"*70)

    for r in results:
        if "error" in r:
            print(f"{r.get('trial', 'Unknown'):<20} {'ERROR':>10}")
        else:
            print(f"{r['trial']:<20} {r['accuracy']:>10.1f} {r['completeness']:>10.1f} {r['quality']:>10.1f} {r['overall_score']:>10.1f}")

    # Overall averages
    valid_results = [r for r in results if "error" not in r]
    if valid_results:
        avg_acc = sum(r['accuracy'] for r in valid_results) / len(valid_results)
        avg_comp = sum(r['completeness'] for r in valid_results) / len(valid_results)
        avg_qual = sum(r['quality'] for r in valid_results) / len(valid_results)
        avg_overall = sum(r['overall_score'] for r in valid_results) / len(valid_results)

        print("-"*70)
        print(f"{'AVERAGE':<20} {avg_acc:>10.1f} {avg_comp:>10.1f} {avg_qual:>10.1f} {avg_overall:>10.1f}")
        print("="*70)

        print(f"\n*** BENCHMARK SCORE: {avg_overall:.1f}/10 ***\n")


def main():
    parser = argparse.ArgumentParser(description="Full Protocol SAP Benchmark")
    parser.add_argument('--api-url', type=str, default="http://localhost:8001")
    parser.add_argument('--trials', type=int, default=5, help="Number of trials to run (max 5 for validation)")

    args = parser.parse_args()

    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return

    client = anthropic.Anthropic(api_key=api_key)

    # Check backend
    try:
        resp = requests.get(f"{args.api_url}/health", timeout=5)
        print(f"Backend status: {resp.status_code}")
    except:
        print(f"ERROR: Backend not available at {args.api_url}")
        return

    # Run benchmark
    trials_to_run = VALIDATION_TRIALS[:args.trials]
    print(f"\nRunning benchmark on {len(trials_to_run)} trials...")

    results = []
    for trial in trials_to_run:
        result = run_trial_benchmark(trial, args.api_url, client)
        result["trial"] = trial["name"]
        results.append(result)

    # Print results
    print_results(results)

    # Save results
    output_file = Path(__file__).parent / "benchmark_full_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
