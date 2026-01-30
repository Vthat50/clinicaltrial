#!/usr/bin/env python3
"""
SAP Benchmark - LLM-as-Judge (Section-by-Section Comparison)

Compares generated SAP sections to reference SAP sections using Claude.
"""

import json
import requests
import re
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import anthropic

EVAL_SET_DIR = "/mnt/c/Users/vijay/OneDrive/Documents/Github/clinicaltrial/sap_rtx4090/sap_generator/data/eval_set"

# Section mapping - what to look for in reference SAPs
SECTION_PATTERNS = {
    "sample_size": [
        r"sample\s*size",
        r"power\s*calculation",
        r"power\s*analysis",
        r"sample\s*size\s*justification",
    ],
    "analysis_populations": [
        r"analysis\s*population",
        r"study\s*population",
        r"intent.to.treat",
        r"ITT",
        r"per.protocol",
    ],
    "endpoints": [
        r"endpoint",
        r"primary\s*outcome",
        r"efficacy\s*variable",
        r"primary\s*variable",
    ],
    "statistical_methods": [
        r"statistical\s*method",
        r"statistical\s*analysis",
        r"efficacy\s*analysis",
        r"primary\s*analysis",
    ],
    "missing_data": [
        r"missing\s*data",
        r"missing\s*value",
        r"data\s*handling",
    ],
    "interim_analysis": [
        r"interim\s*analysis",
        r"interim\s*analyses",
        r"data\s*monitoring",
    ],
    "safety_analysis": [
        r"safety\s*analysis",
        r"adverse\s*event",
        r"safety\s*evaluation",
    ],
}


def extract_section_from_text(text: str, section_name: str, patterns: List[str]) -> str:
    """Extract a section from SAP text based on patterns.

    Skips table of contents entries (which have '....' or page numbers).
    """
    lines = text.split('\n')

    # Find all matches, skip TOC entries
    start_line_idx = -1
    for i, line in enumerate(lines):
        line_lower = line.lower()
        # Skip TOC entries (have dots or just page numbers)
        if '...' in line or re.search(r'\.\s*\d+\s*$', line):
            continue
        # Check if line matches any pattern
        for pattern in patterns:
            if re.search(pattern, line_lower):
                start_line_idx = i
                break
        if start_line_idx != -1:
            break

    if start_line_idx == -1:
        return ""

    # Find next major section (starts with number like "3.2" or "4 ")
    end_line_idx = len(lines)
    for i in range(start_line_idx + 1, min(start_line_idx + 150, len(lines))):
        line = lines[i].strip()
        # Skip empty lines
        if not line:
            continue
        # Check for next major section header (e.g., "3.2 ", "4 INTERIM")
        if re.match(r'^\d+\.?\d*\s+[A-Z]', line) and '...' not in line:
            # Make sure it's not a subsection of current section
            if re.match(r'^\d+\s+[A-Z]', line) or re.match(r'^\d+\.\d+\s+[A-Z]', line):
                end_line_idx = i
                break

    # Extract section content
    section_lines = lines[start_line_idx:end_line_idx]
    section_text = '\n'.join(section_lines)

    # Limit to ~5000 chars per section
    return section_text[:5000].strip()


def generate_sap_section(api_url: str, workspace_id: str, section_id: str, use_tools: bool = False) -> str:
    """Generate a single section using the workbench API."""
    try:
        resp = requests.post(
            f"{api_url}/workbench/{workspace_id}/generate/{section_id}",
            params={"use_tools": use_tools},
            timeout=300 if use_tools else 120  # Tool-calling needs more time
        )
        if resp.status_code == 200:
            return resp.json().get("content", "")
    except Exception as e:
        print(f"Error generating section: {e}")
    return ""


def compare_sections_with_llm(
    generated_section: str,
    reference_section: str,
    section_name: str,
    client: anthropic.Anthropic
) -> Dict:
    """Use Claude to compare two sections."""

    prompt = f"""You are evaluating a generated SAP (Statistical Analysis Plan) section against a reference SAP section.

SECTION: {section_name.upper().replace('_', ' ')}

GENERATED SECTION:
{generated_section[:4000] if generated_section else "[SECTION NOT GENERATED]"}

REFERENCE SECTION (Ground Truth):
{reference_section[:4000] if reference_section else "[SECTION NOT FOUND IN REFERENCE]"}

Evaluate the generated section and provide scores:

1. ACCURACY (1-10): Does the generated section contain correct information that matches the reference?
   - 10 = Perfectly accurate, all facts match
   - 5 = Some correct info, some errors or contradictions
   - 1 = Mostly incorrect or contradictory

2. COMPLETENESS (1-10): Does the generated section cover the same key details as the reference?
   - 10 = Covers all key details from reference
   - 5 = Covers about half of key details
   - 1 = Missing most key details

3. QUALITY (1-10): Is the generated section well-written and professionally structured?
   - 10 = Publication-ready, professional quality
   - 5 = Acceptable but needs editing
   - 1 = Poor quality, needs major rewrite

Return ONLY valid JSON:
{{
    "accuracy": <1-10>,
    "completeness": <1-10>,
    "quality": <1-10>,
    "key_matches": ["list of things that match well"],
    "key_gaps": ["list of things missing or wrong"],
    "summary": "One sentence overall assessment"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text

        # Parse JSON
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        return json.loads(content.strip())

    except Exception as e:
        print(f"LLM comparison error: {e}")
        return {
            "accuracy": 0,
            "completeness": 0,
            "quality": 0,
            "key_matches": [],
            "key_gaps": ["Error during comparison"],
            "summary": f"Error: {str(e)}"
        }


def generate_sap_quick_mode(api_url: str, protocol_text: str, nct_id: str) -> str:
    """Generate full SAP using Quick Protocol mode."""
    try:
        resp = requests.post(
            f"{api_url}/generate-full",
            json={
                "protocol_text": protocol_text,
                "nct_id": nct_id
            },
            timeout=None  # No timeout - can take 10+ minutes
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("sap") or data.get("sap_text") or data.get("generated_sap") or data.get("result", "")
    except Exception as e:
        print(f"Error in quick mode: {e}")
    return ""


def extract_section_from_generated(text: str, section_name: str) -> str:
    """Extract a section from generated SAP (which uses markdown headers)."""
    # Generated SAPs use ## headers like "## SAMPLE SIZE & POWER"
    section_headers = {
        "sample_size": ["sample size", "power calculation"],
        "analysis_populations": ["analysis population", "study population"],
        "endpoints": ["endpoint", "estimand"],
        "statistical_methods": ["statistical method", "statistical analysis"],
        "missing_data": ["missing data"],
        "interim_analysis": ["interim analysis"],
        "safety_analysis": ["safety analysis", "safety evaluation"],
    }

    patterns = section_headers.get(section_name, [])
    lines = text.split('\n')

    start_idx = -1
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if line.startswith('#'):
            for pattern in patterns:
                if pattern in line_lower:
                    start_idx = i
                    break
        if start_idx != -1:
            break

    if start_idx == -1:
        return ""

    # Find next header
    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        if lines[i].startswith('#'):
            end_idx = i
            break

    return '\n'.join(lines[start_idx:end_idx])[:5000].strip()


def run_single_benchmark(
    api_url: str,
    nct_id: str,
    client: anthropic.Anthropic,
    mode: str = "workbench"
) -> Dict:
    """Run benchmark on a single protocol."""

    print(f"\n{'='*60}")
    print(f"BENCHMARKING: {nct_id} (MODE: {mode.upper()})")
    print(f"{'='*60}")

    # Load protocol and reference SAP
    protocol_path = Path(EVAL_SET_DIR) / f"{nct_id}_protocol.txt"
    sap_path = Path(EVAL_SET_DIR) / f"{nct_id}_sap.txt"

    with open(protocol_path, encoding='utf-8') as f:
        protocol_text = f.read()
    with open(sap_path, encoding='utf-8') as f:
        reference_sap = f.read()

    print(f"Protocol: {len(protocol_text):,} chars")
    print(f"Reference SAP: {len(reference_sap):,} chars")

    # Both modes use workbench API - "quick" uses tool-calling, "workbench" uses standard
    mode_desc = "TOOL-CALLING" if mode == "quick" else "STANDARD"
    print(f"\n[1/4] Creating workspace ({mode_desc})...")
    resp = requests.post(
        f"{api_url}/workbench/create",
        json={
            "protocol_content": protocol_text,
            "protocol_filename": f"{nct_id}_protocol.txt",
            "phase": "",
            "therapeutic_area": "oncology",
            "indication": ""
        },
        timeout=120
    )

    if resp.status_code != 200:
        return {"error": f"Failed to create workspace: {resp.text}"}

    workspace_id = resp.json().get("id")
    print(f"Workspace: {workspace_id}")

    # Map our section names to workbench section IDs (6 key sections)
    section_mapping = {
        "analysis_populations": "5",
        "sample_size": "4",
        "statistical_methods": "7",
        "missing_data": "9",
        "safety_analysis": "12",
        "interim_analysis": "13",
    }

    # Generate and compare each section
    print("\n[3/4] Generating sections and comparing...")
    results = {}

    for section_name, section_id in section_mapping.items():
        print(f"\n  --- {section_name.upper().replace('_', ' ')} ---")

        # Generate section based on mode
        print(f"  Generating...")
        use_tools = (mode == "quick")  # quick = tool-calling, workbench = standard
        generated = generate_sap_section(api_url, workspace_id, section_id, use_tools=use_tools)
        print(f"  Generated: {len(generated):,} chars")

        # Extract reference section
        patterns = SECTION_PATTERNS.get(section_name, [])
        reference = extract_section_from_text(reference_sap, section_name, patterns)
        print(f"  Reference: {len(reference):,} chars")

        # Compare with LLM
        print(f"  Comparing with LLM...")
        comparison = compare_sections_with_llm(generated, reference, section_name, client)

        results[section_name] = {
            "generated_chars": len(generated),
            "reference_chars": len(reference),
            "accuracy": comparison.get("accuracy", 0),
            "completeness": comparison.get("completeness", 0),
            "quality": comparison.get("quality", 0),
            "key_matches": comparison.get("key_matches", []),
            "key_gaps": comparison.get("key_gaps", []),
            "summary": comparison.get("summary", "")
        }

        print(f"  Scores: accuracy={comparison.get('accuracy')}, completeness={comparison.get('completeness')}, quality={comparison.get('quality')}")
        print(f"  Summary: {comparison.get('summary', '')[:100]}")

    # Calculate overall scores
    print("\n[4/4] Calculating overall scores...")

    accuracy_scores = [r["accuracy"] for r in results.values() if r["accuracy"] > 0]
    completeness_scores = [r["completeness"] for r in results.values() if r["completeness"] > 0]
    quality_scores = [r["quality"] for r in results.values() if r["quality"] > 0]

    overall = {
        "nct_id": nct_id,
        "sections_evaluated": len(results),
        "avg_accuracy": sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0,
        "avg_completeness": sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0,
        "avg_quality": sum(quality_scores) / len(quality_scores) if quality_scores else 0,
        "section_results": results
    }

    overall["overall_score"] = (overall["avg_accuracy"] + overall["avg_completeness"] + overall["avg_quality"]) / 3

    return overall


def main():
    import argparse

    parser = argparse.ArgumentParser(description="SAP Benchmark - LLM Judge")
    parser.add_argument('--api-url', type=str, default="http://localhost:8001")
    parser.add_argument('--nct-id', type=str, required=True, help='NCT ID to benchmark')
    parser.add_argument('--mode', type=str, default="workbench", choices=["workbench", "quick"],
                        help='Generation mode: workbench (section-by-section) or quick (full SAP)')

    args = parser.parse_args()

    # Initialize Claude client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return

    client = anthropic.Anthropic(api_key=api_key)

    # Run benchmark
    result = run_single_benchmark(args.api_url, args.nct_id, client, mode=args.mode)

    # Print results
    print(f"\n{'='*60}")
    print("BENCHMARK RESULTS")
    print(f"{'='*60}")
    print(f"\nNCT ID: {result.get('nct_id')}")
    print(f"Sections Evaluated: {result.get('sections_evaluated')}")
    print(f"\nOVERALL SCORES:")
    print(f"  Accuracy:     {result.get('avg_accuracy', 0):.1f}/10")
    print(f"  Completeness: {result.get('avg_completeness', 0):.1f}/10")
    print(f"  Quality:      {result.get('avg_quality', 0):.1f}/10")
    print(f"  -----------------------")
    print(f"  OVERALL:      {result.get('overall_score', 0):.1f}/10")

    print(f"\nPER-SECTION BREAKDOWN:")
    for section_name, section_data in result.get("section_results", {}).items():
        print(f"\n  {section_name.upper().replace('_', ' ')}:")
        print(f"    Accuracy: {section_data.get('accuracy', 0)}/10, Completeness: {section_data.get('completeness', 0)}/10, Quality: {section_data.get('quality', 0)}/10")
        print(f"    Summary: {section_data.get('summary', '')[:80]}")
        if section_data.get('key_gaps'):
            print(f"    Gaps: {', '.join(section_data.get('key_gaps', [])[:3])}")

    # Save results
    output_file = Path("benchmark_llm_judge_results.json")
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
