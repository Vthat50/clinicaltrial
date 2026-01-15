#!/usr/bin/env python3
"""
Run Golden Set Evaluation with Live Generation
===============================================

This script runs the golden set evaluator with actual SAP generation
from the workbench, rather than mock data.

Usage:
    python run_golden_eval.py --case lung_phase3_pfs
    python run_golden_eval.py --all --export results.json
    python run_golden_eval.py --category oncology --verbose

Author: SAP Generation System
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add parent paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from golden_set_eval import (
    GoldenSetEvaluator,
    GoldenSetCase,
    GOLDEN_SET_CASES,
)


def create_workspace_for_case(workbench, case: GoldenSetCase) -> str:
    """Create a workspace with the test case protocol."""
    workspace = workbench.create_workspace(
        study_id=case.protocol.get("study_id", case.case_id),
        protocol_text=json.dumps(case.protocol, indent=2),
    )
    return workspace.workspace_id


def generate_sections_for_case(
    workbench,
    case: GoldenSetCase,
    use_tools: bool = True,
    verbose: bool = False
) -> tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Generate all expected sections for a golden set case.

    Returns:
        Tuple of (sections_content, tools_by_section)
    """
    sections = {}
    tools_by_section = {}

    # Create workspace
    workspace_id = create_workspace_for_case(workbench, case)

    for expectation in case.section_expectations:
        section_id = expectation.section_id

        if verbose:
            print(f"  Generating section {section_id} ({expectation.section_name})...")

        try:
            result = workbench.generate_section(
                workspace_id=workspace_id,
                section_id=section_id,
                use_tools=use_tools
            )

            if result.get("success"):
                sections[section_id] = result.get("content", "")
                tools_by_section[section_id] = result.get("tools_called", [])

                if verbose:
                    content_len = len(sections[section_id])
                    tools_count = len(tools_by_section[section_id])
                    print(f"    Generated {content_len} chars, called {tools_count} tools")
            else:
                if verbose:
                    print(f"    Failed: {result.get('error', 'Unknown error')}")
                sections[section_id] = ""
                tools_by_section[section_id] = []

        except Exception as e:
            if verbose:
                print(f"    Error: {e}")
            sections[section_id] = ""
            tools_by_section[section_id] = []

    return sections, tools_by_section


def run_live_evaluation(
    cases: List[GoldenSetCase],
    use_tools: bool = True,
    verbose: bool = False,
    export_path: str = None
):
    """Run live evaluation with actual generation."""
    try:
        from workbench.workbench_core import WorkbenchCore
        workbench = WorkbenchCore()
        print("Workbench loaded successfully")
    except Exception as e:
        print(f"Could not load workbench: {e}")
        print("Run with mock data instead: python golden_set_eval.py --run all --mock")
        return

    evaluator = GoldenSetEvaluator(verbose=verbose)

    print(f"\nRunning live evaluation for {len(cases)} cases...")
    print(f"Tool-calling mode: {'enabled' if use_tools else 'disabled'}")
    print("-" * 60)

    for case in cases:
        print(f"\n[{case.case_id}] {case.description}")

        # Generate sections
        sections, tools_by_section = generate_sections_for_case(
            workbench, case, use_tools=use_tools, verbose=verbose
        )

        # Evaluate
        result = evaluator.run_case(
            case,
            generated_sections=sections,
            tools_by_section=tools_by_section
        )

        # Print result
        status = "PASS" if result.passed else "FAIL"
        print(f"  Result: {status} (score: {result.overall_score:.0f}/100)")

        if result.critical_failures:
            print(f"  Critical failures:")
            for cf in result.critical_failures[:3]:
                print(f"    - {cf}")

    # Summary
    evaluator.print_summary()

    # Export
    if export_path:
        evaluator.export_results(export_path)


def main():
    parser = argparse.ArgumentParser(description="Run Golden Set Evaluation with Live Generation")
    parser.add_argument("--case", "-c", type=str, help="Run specific case")
    parser.add_argument("--all", "-a", action="store_true", help="Run all cases")
    parser.add_argument("--category", type=str, help="Filter by category")
    parser.add_argument("--tag", type=str, help="Filter by tag")
    parser.add_argument("--no-tools", action="store_true", help="Disable tool-calling mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--export", "-e", type=str, help="Export results to JSON")
    parser.add_argument("--list", "-l", action="store_true", help="List available cases")

    args = parser.parse_args()

    if args.list:
        print(f"\nAvailable Golden Set Cases ({len(GOLDEN_SET_CASES)}):\n")
        for case in GOLDEN_SET_CASES:
            print(f"  {case.case_id:<25} - {case.description}")
        return

    cases = GOLDEN_SET_CASES

    if args.case:
        case = next((c for c in cases if c.case_id == args.case), None)
        if not case:
            print(f"Case not found: {args.case}")
            return
        cases = [case]
    elif args.all:
        if args.category:
            cases = [c for c in cases if c.category == args.category]
        if args.tag:
            cases = [c for c in cases if args.tag in c.tags]
    else:
        parser.print_help()
        return

    run_live_evaluation(
        cases=cases,
        use_tools=not args.no_tools,
        verbose=args.verbose,
        export_path=args.export
    )


if __name__ == "__main__":
    main()
