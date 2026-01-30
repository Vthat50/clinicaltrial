"""
SAP Benchmark Runner v2.0
=========================
Runs comprehensive benchmark using the new section-specific criteria.

Usage:
    python run_benchmark_v2.py --trials 1
    python run_benchmark_v2.py --trial-id NCT01784848
    python run_benchmark_v2.py --all
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
import anthropic

# Import benchmark system
from sap_benchmark_v2 import (
    SAPBenchmark,
    BenchmarkResult,
    map_generated_to_benchmark_sections,
    extract_reference_sections,
    SECTION_CONFIGS
)

# Try importing PDF extraction
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("Warning: PyPDF2 not installed. Install with: pip install PyPDF2")

# =============================================================================
# CONFIGURATION
# =============================================================================

# Paths
CT_DOWNLOADS = Path("/mnt/c/Users/vijay/Desktop/sap_data/ct_downloads")
RESULTS_DIR = Path(__file__).parent / "benchmark_results_v2"
RESULTS_DIR.mkdir(exist_ok=True)

# API
API_URL = "http://localhost:8001"

# Validation trials (non-overlapping with training data)
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
    },
    {
        "trial_id": "NCT02998528",
        "protocol": CT_DOWNLOADS / "all_protocols" / "NCT02998528_Protocol.pdf",
        "sap": CT_DOWNLOADS / "all_saps" / "NCT02998528_SAP.pdf",
        "indication": "NSCLC",
        "phase": "Phase 3"
    },
    {
        "trial_id": "NCT04003610",
        "protocol": CT_DOWNLOADS / "all_protocols" / "NCT04003610_Protocol.pdf",
        "sap": CT_DOWNLOADS / "all_saps" / "NCT04003610_SAP.pdf",
        "indication": "Urothelial",
        "phase": "Phase 2"
    }
]

# Section mapping from workbench to benchmark
WORKBENCH_TO_BENCHMARK = {
    # Workbench section ID -> Benchmark section ID
    "1": "1_title_page",
    "2": "2_objectives_endpoints_estimands",
    "3": "3_study_design",
    "5": "3_study_design",  # Analysis Populations -> combine with Study Design
    "6": "2_objectives_endpoints_estimands",  # Endpoints -> combine with Objectives
    "7": "4_statistical_analyses",
    "9": "4_statistical_analyses",  # Missing Data -> combine with Statistical
    "10": "6_efficacy",  # Sensitivity -> Efficacy
    "11": "6_efficacy",  # Subgroups -> Efficacy
    "12": "7_safety",
    "14": "11_appendices",
    "18": "11_appendices",
    "A": "11_appendices",
}


# =============================================================================
# PDF EXTRACTION
# =============================================================================

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF file."""
    if not PDF_AVAILABLE:
        return ""

    if not pdf_path.exists():
        print(f"  PDF not found: {pdf_path}")
        return ""

    try:
        text_parts = []
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                try:
                    text_parts.append(page.extract_text() or "")
                except Exception:
                    continue

        return "\n".join(text_parts)
    except Exception as e:
        print(f"  Error extracting PDF: {e}")
        return ""


# =============================================================================
# WORKBENCH API INTEGRATION
# =============================================================================

def check_backend():
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
            timeout=60
        )

        if resp.status_code == 200:
            return resp.json().get("id")  # API returns "id" not "workspace_id"
        else:
            print(f"  Create workspace failed: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"  Create workspace error: {e}")
        return None


def generate_section(workspace_id: str, section_id: str, max_retries: int = 3) -> Optional[str]:
    """Generate a single section."""
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{API_URL}/workbench/{workspace_id}/generate/{section_id}",
                timeout=300
            )

            if resp.status_code == 200:
                content = resp.json().get("content", "")
                if content.strip():
                    return content
            elif resp.status_code == 404:
                # Section not applicable
                return None

            print(f"  Section {section_id} attempt {attempt + 1} failed: {resp.status_code}")
            time.sleep(5)

        except requests.exceptions.Timeout:
            print(f"  Section {section_id} timeout, retrying...")
            time.sleep(10)
        except Exception as e:
            print(f"  Section {section_id} error: {e}")
            time.sleep(5)

    return None


def generate_all_sections(workspace_id: str) -> Dict[str, str]:
    """Generate all SAP sections."""
    sections = {}

    # Core sections to generate
    section_ids = ["2", "3", "5", "6", "7", "9", "10", "11", "12", "14"]

    for section_id in section_ids:
        print(f"    Generating section {section_id}...")
        content = generate_section(workspace_id, section_id)
        if content:
            sections[section_id] = content
            print(f"    ✓ Section {section_id}: {len(content):,} chars")
        else:
            print(f"    ✗ Section {section_id}: not generated")

    return sections


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

def run_trial_benchmark(trial: Dict, benchmark: SAPBenchmark) -> Optional[BenchmarkResult]:
    """Run benchmark for a single trial."""

    print(f"\n{'=' * 70}")
    print(f"BENCHMARKING: {trial['trial_id']} ({trial['indication']}, {trial['phase']})")
    print(f"{'=' * 70}")

    trial_info = {
        "trial_id": trial["trial_id"],
        "indication": trial["indication"],
        "phase": trial["phase"]
    }

    # Step 1: Extract protocol
    print("\n[1/5] Extracting protocol PDF...")
    protocol_text = extract_text_from_pdf(trial["protocol"])
    if not protocol_text:
        print("  ERROR: Could not extract protocol")
        return None
    print(f"  Protocol: {len(protocol_text):,} chars")

    # Step 2: Extract reference SAP
    print("\n[2/5] Extracting reference SAP...")
    reference_sap_text = extract_text_from_pdf(trial["sap"])
    if not reference_sap_text:
        print("  WARNING: Could not extract reference SAP")
    else:
        print(f"  Reference SAP: {len(reference_sap_text):,} chars")

    # Step 3: Create workspace and generate
    print("\n[3/5] Creating workspace and generating SAP...")
    workspace_id = create_workspace(protocol_text, trial_info)
    if not workspace_id:
        print("  ERROR: Could not create workspace")
        return None
    print(f"  Workspace: {workspace_id}")

    # Generate sections
    workbench_sections = generate_all_sections(workspace_id)
    if not workbench_sections:
        print("  ERROR: No sections generated")
        return None
    print(f"  Generated {len(workbench_sections)} sections")

    # Step 4: Map sections to benchmark format
    print("\n[4/5] Mapping sections to benchmark format...")

    # Combine workbench sections into benchmark sections
    generated_sections = {}
    for wb_id, content in workbench_sections.items():
        bench_id = WORKBENCH_TO_BENCHMARK.get(wb_id)
        if bench_id:
            if bench_id in generated_sections:
                generated_sections[bench_id] += "\n\n---\n\n" + content
            else:
                generated_sections[bench_id] = content

    print(f"  Mapped to {len(generated_sections)} benchmark sections")

    # Extract reference sections using LLM
    print("  Extracting reference sections...")
    reference_sections = {}
    if reference_sap_text:
        reference_sections = extract_reference_sections(
            reference_sap_text,
            benchmark.client
        )
        print(f"  Extracted {len(reference_sections)} reference sections")

    # Step 5: Run benchmark evaluation
    print("\n[5/5] Running benchmark evaluation...")
    result = benchmark.evaluate_full_sap(
        generated_sections=generated_sections,
        reference_sections=reference_sections,
        trial_info=trial_info
    )

    return result


def run_all_benchmarks(num_trials: int = None, specific_trial: str = None) -> List[BenchmarkResult]:
    """Run benchmarks for all trials."""

    # Check backend
    if not check_backend():
        print("ERROR: Backend not available at", API_URL)
        print("Start with: cd web/backend && python -m uvicorn main:app --port 8001")
        return []

    # Initialize benchmark
    benchmark = SAPBenchmark()

    # Select trials
    if specific_trial:
        trials = [t for t in VALIDATION_TRIALS if t["trial_id"] == specific_trial]
        if not trials:
            print(f"Trial {specific_trial} not found")
            return []
    else:
        trials = VALIDATION_TRIALS[:num_trials] if num_trials else VALIDATION_TRIALS

    print(f"\n{'#' * 70}")
    print(f"SAP BENCHMARK v2.0 - {len(trials)} trials")
    print(f"{'#' * 70}")

    results = []

    for i, trial in enumerate(trials, 1):
        print(f"\n[{i}/{len(trials)}] Processing {trial['trial_id']}...")

        try:
            result = run_trial_benchmark(trial, benchmark)
            if result:
                results.append(result)

                # Print summary
                print(f"\n  RESULT: {result.overall_score}/10")
                print(f"  Weakest: {', '.join(result.weakest_sections)}")
                print(f"  Top gaps: {len(result.top_gaps)}")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    return results


def save_results(results: List[BenchmarkResult]):
    """Save benchmark results to files."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON results
    json_path = RESULTS_DIR / f"benchmark_v2_{timestamp}.json"

    json_results = []
    for result in results:
        json_result = {
            "trial_id": result.trial_id,
            "indication": result.indication,
            "phase": result.phase,
            "overall_score": result.overall_score,
            "timestamp": result.timestamp,
            "section_scores": {
                sid: {
                    "score": sr.section_score,
                    "elements_present": sr.elements_present,
                    "critical_met": sr.critical_elements_met,
                    "accuracy": sr.dimension_scores.accuracy,
                    "completeness": sr.dimension_scores.completeness,
                    "specificity": sr.dimension_scores.specificity,
                    "conciseness": sr.dimension_scores.conciseness,
                    "quality": sr.dimension_scores.quality,
                    "gaps": sr.gaps,
                    "summary": sr.summary
                }
                for sid, sr in result.section_results.items()
            },
            "weakest_sections": result.weakest_sections,
            "strongest_sections": result.strongest_sections,
            "critical_failures": result.critical_failures,
            "top_gaps": result.top_gaps
        }
        json_results.append(json_result)

    with open(json_path, 'w') as f:
        json.dump(json_results, f, indent=2)

    print(f"\nResults saved to: {json_path}")

    # Generate and save reports
    benchmark = SAPBenchmark()
    for result in results:
        report = benchmark.generate_report(result)
        report_path = RESULTS_DIR / f"report_{result.trial_id}_{timestamp}.txt"
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"Report saved to: {report_path}")

    # Print summary table
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)
    print(f"{'Trial':<15} {'Indication':<15} {'Phase':<10} {'Score':<8} {'Critical'}")
    print("-" * 80)

    for result in results:
        critical_status = "✓" if not result.critical_failures else f"✗ ({len(result.critical_failures)})"
        print(f"{result.trial_id:<15} {result.indication:<15} {result.phase:<10} {result.overall_score:<8.1f} {critical_status}")

    # Overall average
    if results:
        avg_score = sum(r.overall_score for r in results) / len(results)
        print("-" * 80)
        print(f"{'AVERAGE':<15} {'':<15} {'':<10} {avg_score:<8.1f}")

    return json_path


# =============================================================================
# MAIN
# =============================================================================

def main():
    global API_URL

    parser = argparse.ArgumentParser(description="SAP Benchmark Runner v2.0")
    parser.add_argument("--trials", type=int, default=1, help="Number of trials to run")
    parser.add_argument("--trial-id", type=str, help="Specific trial ID to run")
    parser.add_argument("--all", action="store_true", help="Run all validation trials")
    parser.add_argument("--api-url", type=str, default="http://localhost:8001", help="Backend API URL")

    args = parser.parse_args()
    API_URL = args.api_url

    # Run benchmarks
    if args.trial_id:
        results = run_all_benchmarks(specific_trial=args.trial_id)
    elif args.all:
        results = run_all_benchmarks()
    else:
        results = run_all_benchmarks(num_trials=args.trials)

    # Save and display results
    if results:
        save_results(results)
    else:
        print("\nNo results to save.")


if __name__ == "__main__":
    main()
