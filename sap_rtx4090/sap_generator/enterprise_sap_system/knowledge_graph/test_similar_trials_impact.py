"""
A/B Test: Impact of get_similar_trials on each section
========================================================

Tests Workbench generation:
  A) use_tools=False (pre-fetch mode - most sections don't get similar trials)
  B) use_tools=True (tool-calling mode - Claude can call get_similar_trials)
"""

import sys
import json
import requests
from pathlib import Path
from typing import Dict, List
from datetime import datetime

# Backend API URL
API_URL = "http://localhost:8001"


def generate_section_via_workbench(
    protocol_text: str,
    section_id: str,
    use_tools: bool = False
) -> tuple:
    """Generate a section using the Workbench API."""

    # Step 1: Create workspace
    try:
        resp = requests.post(
            f"{API_URL}/workbench/create",
            json={
                "protocol_content": protocol_text,
                "protocol_filename": "test_protocol.txt"
            },
            timeout=120
        )
        resp.raise_for_status()
        workspace_data = resp.json()
        workspace_id = workspace_data.get("id")  # API returns "id" not "workspace_id"
        print(f"    Created workspace: {workspace_id}")
    except Exception as e:
        print(f"    Failed to create workspace: {e}")
        return "", []

    # Step 2: Generate section
    try:
        resp = requests.post(
            f"{API_URL}/workbench/{workspace_id}/generate/{section_id}",
            params={"use_tools": use_tools},
            timeout=180
        )
        resp.raise_for_status()
        section_data = resp.json()
        content = section_data.get("content", "")
        kb_tools_used = section_data.get("kb_tools_used", [])
        return content, kb_tools_used
    except Exception as e:
        print(f"    Failed to generate section: {e}")
        return "", []


def test_section(
    section_id: str,
    section_title: str,
    protocol_text: str,
) -> Dict:
    """Test a section with both modes."""

    results = {
        "section_id": section_id,
        "section_title": section_title,
        "prefetch_mode": {"content": "", "kb_tools": [], "length": 0},
        "toolcall_mode": {"content": "", "kb_tools": [], "length": 0},
        "comparison": {}
    }

    print(f"\n{'='*60}")
    print(f"Section {section_id}: {section_title}")
    print(f"{'='*60}")

    # A) Pre-fetch mode
    print(f"\n[A] PRE-FETCH mode (use_tools=False)...")
    content_a, kb_a = generate_section_via_workbench(protocol_text, section_id, use_tools=False)
    results["prefetch_mode"]["content"] = content_a
    results["prefetch_mode"]["kb_tools"] = kb_a
    results["prefetch_mode"]["length"] = len(content_a)
    print(f"    Generated: {len(content_a):,} chars")
    print(f"    KB tools used: {[t.get('tool_name') for t in kb_a]}")

    # B) Tool-calling mode
    print(f"\n[B] TOOL-CALLING mode (use_tools=True)...")
    content_b, kb_b = generate_section_via_workbench(protocol_text, section_id, use_tools=True)
    results["toolcall_mode"]["content"] = content_b
    results["toolcall_mode"]["kb_tools"] = kb_b
    results["toolcall_mode"]["length"] = len(content_b)
    print(f"    Generated: {len(content_b):,} chars")
    print(f"    KB tools used: {[t.get('tool_name') for t in kb_b]}")

    # Compare
    print(f"\n[COMPARISON]")

    # Check if get_similar_trials was used
    used_similar_a = any("similar_trials" in str(t).lower() for t in kb_a)
    used_similar_b = any("similar_trials" in str(t).lower() for t in kb_b)
    print(f"  - Used get_similar_trials (A): {used_similar_a}")
    print(f"  - Used get_similar_trials (B): {used_similar_b}")

    # Check for trial citations in content
    trial_keywords = ["keynote", "checkmate", "pacific", "precedent", "similar trial"]
    has_citations_a = any(kw in content_a.lower() for kw in trial_keywords)
    has_citations_b = any(kw in content_b.lower() for kw in trial_keywords)
    print(f"  - Has trial citations (A): {has_citations_a}")
    print(f"  - Has trial citations (B): {has_citations_b}")

    len_diff = len(content_b) - len(content_a)
    print(f"  - Length diff (B - A): {len_diff:+,} chars")

    results["comparison"] = {
        "used_similar_trials_a": used_similar_a,
        "used_similar_trials_b": used_similar_b,
        "has_citations_a": has_citations_a,
        "has_citations_b": has_citations_b,
        "length_diff": len_diff,
        "improved": used_similar_b and not used_similar_a
    }

    return results


def run_test(protocol_path: str):
    """Run the A/B test."""

    # Check backend
    try:
        resp = requests.get(f"{API_URL}/health", timeout=5)
        print(f"Backend: OK ({resp.json().get('status')})")
    except:
        print(f"ERROR: Backend not running at {API_URL}")
        return []

    # Load protocol
    protocol_text = Path(protocol_path).read_text(encoding='utf-8', errors='ignore')
    print(f"Protocol: {len(protocol_text):,} chars from {Path(protocol_path).name}")

    # Test sections
    sections = [
        ("7", "STATISTICAL METHODS"),
        ("8", "CENSORING RULES"),
    ]

    results = []
    for section_id, title in sections:
        try:
            result = test_section(section_id, title, protocol_text)
            results.append(result)
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

    # Save
    output_path = Path(__file__).parent / f"ab_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        c = r["comparison"]
        print(f"\nSection {r['section_id']}: {r['section_title']}")
        print(f"  Pre-fetch: {r['prefetch_mode']['length']:,} chars, similar_trials={c['used_similar_trials_a']}")
        print(f"  Tool-call: {r['toolcall_mode']['length']:,} chars, similar_trials={c['used_similar_trials_b']}")

    print(f"\nResults saved: {output_path}")
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python test_similar_trials_impact.py <protocol_path>")
        sys.exit(1)
    run_test(sys.argv[1])
