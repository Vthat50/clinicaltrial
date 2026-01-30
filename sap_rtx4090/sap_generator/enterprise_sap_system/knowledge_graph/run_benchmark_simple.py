"""
Simple SAP Benchmark Runner
============================
Runs the simplified keyword-based benchmark.

Usage:
    python run_benchmark_simple.py --trials 1
    python run_benchmark_simple.py --trial-id NCT01784848
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import requests

# Import benchmark
from sap_benchmark_simple import (
    SimpleBenchmark,
    BenchmarkResult,
    map_workbench_sections,
    WORKBENCH_TO_BENCHMARK,
    CRITICAL_ELEMENTS
)
import anthropic

# PDF extraction
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("Warning: PyPDF2 not installed")


# =============================================================================
# CONFIGURATION
# =============================================================================

CT_DOWNLOADS = Path("/mnt/c/Users/vijay/Desktop/sap_data/ct_downloads")
RESULTS_DIR = Path(__file__).parent / "benchmark_results_simple"
RESULTS_DIR.mkdir(exist_ok=True)

API_URL = "http://localhost:8001"

VALIDATION_TRIALS = [
    {
        "trial_id": "NCT01784848",
        "protocol": CT_DOWNLOADS / "all_protocols" / "NCT01784848_Protocol.pdf",
        "sap": CT_DOWNLOADS / "all_saps" / "NCT01784848_SAP.pdf",
        "indication": "Gastric",
        "phase": "Phase 3"
    },
    {
        "trial_id": "NCT02129205",
        "protocol": CT_DOWNLOADS / "all_protocols" / "NCT02129205_Protocol.pdf",
        "sap": CT_DOWNLOADS / "all_saps" / "NCT02129205_SAP.pdf",
        "indication": "Lung Cancer",
        "phase": "Phase 2"
    },
    {
        "trial_id": "NCT02756364",
        "protocol": CT_DOWNLOADS / "all_protocols" / "NCT02756364_Protocol.pdf",
        "sap": CT_DOWNLOADS / "all_saps" / "NCT02756364_SAP.pdf",
        "indication": "Breast",
        "phase": "Phase 2"
    }
]


# =============================================================================
# HELPERS
# =============================================================================

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF."""
    if not PDF_AVAILABLE or not pdf_path.exists():
        return ""

    try:
        text_parts = []
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages[:100]:  # Limit pages
                try:
                    text_parts.append(page.extract_text() or "")
                except:
                    continue
        return "\n".join(text_parts)
    except Exception as e:
        print(f"  Error extracting PDF: {e}")
        return ""


def check_backend() -> bool:
    """Check if backend is available."""
    try:
        resp = requests.get(f"{API_URL}/health", timeout=5)
        return resp.status_code == 200
    except:
        return False


def create_workspace(protocol_text: str, trial_info: Dict) -> Optional[str]:
    """Create workspace and return ID."""
    try:
        resp = requests.post(
            f"{API_URL}/workbench/create",
            json={
                "name": f"Benchmark_{trial_info['trial_id']}",
                "protocol_content": protocol_text,
                "protocol_filename": f"{trial_info['trial_id']}_Protocol.pdf",
                "phase": trial_info["phase"],
                "therapeutic_area": "Oncology",
                "indication": trial_info["indication"]
            },
            timeout=120
        )
        if resp.status_code == 200:
            return resp.json().get("id")
        else:
            print(f"  Create failed: {resp.status_code}")
            return None
    except Exception as e:
        print(f"  Create error: {e}")
        return None


def generate_section(workspace_id: str, section_id: str) -> Optional[str]:
    """Generate a single section."""
    try:
        resp = requests.post(
            f"{API_URL}/workbench/{workspace_id}/generate/{section_id}",
            timeout=300
        )
        if resp.status_code == 200:
            return resp.json().get("content", "")
        return None
    except Exception as e:
        print(f"  Section {section_id} error: {e}")
        return None


def generate_all_sections(workspace_id: str) -> Dict[str, str]:
    """Generate all sections."""
    sections = {}
    section_ids = ["2", "3", "5", "6", "7", "9", "10", "11", "12", "18"]

    for section_id in section_ids:
        print(f"    Generating section {section_id}...", end=" ")
        content = generate_section(workspace_id, section_id)
        if content:
            sections[section_id] = content
            print(f"✓ ({len(content):,} chars)")
        else:
            print("✗")

    return sections


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

def run_trial_benchmark(trial: Dict, benchmark: SimpleBenchmark) -> Optional[BenchmarkResult]:
    """Run benchmark for a single trial."""

    print(f"\n{'=' * 60}")
    print(f"BENCHMARKING: {trial['trial_id']}")
    print(f"{'=' * 60}")

    # Extract protocol
    print("\n[1/4] Extracting protocol...")
    protocol_text = extract_pdf_text(trial["protocol"])
    if not protocol_text:
        print("  ERROR: Could not extract protocol")
        return None
    print(f"  Protocol: {len(protocol_text):,} chars")

    # Extract reference SAP (for length comparison)
    print("\n[2/4] Extracting reference SAP...")
    reference_text = extract_pdf_text(trial["sap"])
    print(f"  Reference: {len(reference_text):,} chars")

    # Create workspace and generate
    print("\n[3/4] Generating SAP sections...")
    workspace_id = create_workspace(protocol_text, trial)
    if not workspace_id:
        print("  ERROR: Could not create workspace")
        return None

    workbench_sections = generate_all_sections(workspace_id)
    if not workbench_sections:
        print("  ERROR: No sections generated")
        return None

    # Map to benchmark sections
    benchmark_sections = map_workbench_sections(workbench_sections)
    print(f"  Mapped to {len(benchmark_sections)} benchmark sections")

    # Run benchmark
    print("\n[4/4] Running benchmark...")
    result = benchmark.evaluate_full_sap(
        generated_sections=benchmark_sections,
        reference_sections={},  # Could add reference parsing here
        trial_id=trial["trial_id"]
    )

    return result


def run_all_benchmarks(num_trials: int = None, specific_trial: str = None) -> List[BenchmarkResult]:
    """Run benchmarks for trials."""

    if not check_backend():
        print(f"ERROR: Backend not available at {API_URL}")
        return []

    benchmark = SimpleBenchmark()

    # Select trials
    if specific_trial:
        trials = [t for t in VALIDATION_TRIALS if t["trial_id"] == specific_trial]
    else:
        trials = VALIDATION_TRIALS[:num_trials] if num_trials else VALIDATION_TRIALS

    print(f"\n{'#' * 60}")
    print(f"SIMPLE SAP BENCHMARK - {len(trials)} trials")
    print(f"{'#' * 60}")

    results = []

    for i, trial in enumerate(trials, 1):
        print(f"\n[{i}/{len(trials)}] {trial['trial_id']}...")

        try:
            result = run_trial_benchmark(trial, benchmark)
            if result:
                results.append(result)
                print(f"\n  SCORE: {result.overall_score}/10")
                print(f"  PASS: {'✓' if result.critical_pass else '✗'}")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    return results


def save_results(results: List[BenchmarkResult], benchmark: SimpleBenchmark):
    """Save results to files."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_path = RESULTS_DIR / f"benchmark_simple_{timestamp}.json"
    json_data = []

    for result in results:
        json_data.append({
            "trial_id": result.trial_id,
            "timestamp": result.timestamp,
            "overall_score": result.overall_score,
            "critical_pass": result.critical_pass,
            "summary": result.summary,
            "sections": {
                sid: {
                    "score": sr.score,
                    "required": f"{sr.required_found}/{sr.required_total}",
                    "length_ratio": sr.length_ratio,
                    "elements": [
                        {"name": e.name, "found": e.found, "required": e.required}
                        for e in sr.element_results
                    ]
                }
                for sid, sr in result.section_results.items()
            }
        })

    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2)
    print(f"\nResults saved: {json_path}")

    # Save reports
    for result in results:
        report = benchmark.generate_report(result)
        report_path = RESULTS_DIR / f"report_{result.trial_id}_{timestamp}.txt"
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"Report saved: {report_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"{'Trial':<15} {'Score':<10} {'Pass':<10}")
    print("-" * 60)

    for result in results:
        status = "✓ PASS" if result.critical_pass else "✗ FAIL"
        print(f"{result.trial_id:<15} {result.overall_score:<10} {status:<10}")

    if results:
        avg = sum(r.overall_score for r in results) / len(results)
        print("-" * 60)
        print(f"{'AVERAGE':<15} {avg:.1f}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    global API_URL

    parser = argparse.ArgumentParser(description="Simple SAP Benchmark")
    parser.add_argument("--trials", type=int, default=1, help="Number of trials")
    parser.add_argument("--trial-id", type=str, help="Specific trial ID")
    parser.add_argument("--api-url", type=str, default=API_URL, help="Backend URL")

    args = parser.parse_args()
    API_URL = args.api_url

    # Run benchmarks
    if args.trial_id:
        results = run_all_benchmarks(specific_trial=args.trial_id)
    else:
        results = run_all_benchmarks(num_trials=args.trials)

    # Save results
    if results:
        benchmark = SimpleBenchmark()
        save_results(results, benchmark)
    else:
        print("\nNo results to save.")


if __name__ == "__main__":
    main()
