#!/usr/bin/env python3
"""
SAP Accuracy Testing Script
============================
Tests the production pipeline by comparing generated SAPs against original SAPs.

Usage:
    python test_sap_accuracy.py --test-dir "C:/Users/vijay/Downloads/Testing"

    Or specify individual files:
    python test_sap_accuracy.py --protocol "path/to/protocol.pdf" --original-sap "path/to/sap.pdf"

Requirements:
    pip install llama-cloud-services anthropic PyMuPDF rich
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Rich for nice terminal output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Note: Install 'rich' for better output: pip install rich")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import production pipeline
try:
    from enterprise_sap_system.core.two_pass_extractor import TwoPassExtractor
    PIPELINE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import TwoPassExtractor: {e}")
    PIPELINE_AVAILABLE = False

# Import integrated pipeline (with LLM extraction + RAG)
try:
    from enterprise_sap_system.core.integrated_pipeline import IntegratedPipeline as IntegratedSAPPipeline
    INTEGRATED_PIPELINE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import IntegratedPipeline: {e}")
    INTEGRATED_PIPELINE_AVAILABLE = False

# LlamaParse for PDF extraction
try:
    from llama_cloud_services import LlamaParse
    import asyncio
    LLAMAPARSE_AVAILABLE = True
except ImportError:
    LLAMAPARSE_AVAILABLE = False

# Anthropic for comparison
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


@dataclass
class SectionComparison:
    """Comparison result for a single SAP section"""
    section_name: str
    status: str  # "correct", "partial", "missing", "extra", "wrong"
    correct_elements: List[str] = field(default_factory=list)
    missing_elements: List[str] = field(default_factory=list)
    wrong_elements: List[str] = field(default_factory=list)
    extra_elements: List[str] = field(default_factory=list)
    score: float = 0.0
    notes: str = ""


@dataclass
class AccuracyReport:
    """Full accuracy report for a protocol/SAP pair"""
    protocol_name: str
    generation_time_s: float
    overall_score: float
    section_scores: Dict[str, float] = field(default_factory=dict)
    section_comparisons: List[SectionComparison] = field(default_factory=list)
    critical_gaps: List[str] = field(default_factory=list)
    summary: str = ""
    generated_sap_path: str = ""

    def to_dict(self) -> Dict:
        return {
            "protocol_name": self.protocol_name,
            "generation_time_s": self.generation_time_s,
            "overall_score": self.overall_score,
            "section_scores": self.section_scores,
            "section_comparisons": [asdict(s) for s in self.section_comparisons],
            "critical_gaps": self.critical_gaps,
            "summary": self.summary,
            "generated_sap_path": self.generated_sap_path
        }


class SAPAccuracyTester:
    """
    Tests SAP generation accuracy by comparing generated SAPs to original SAPs.

    Supports two pipeline modes:
    - "direct": TwoPassExtractor (discovery + generation, no RAG)
    - "integrated": IntegratedSAPPipeline (LLM extraction + RAG + KnowledgeGraph)
    """

    SAP_SECTIONS = [
        "introduction",
        "study_design",
        "objectives_endpoints",
        "populations",
        "statistical_hypotheses",
        "interim_analysis",
        "statistical_methods",
        "safety_analysis",
        "missing_data",
        "pharmacokinetics",
        "pharmacodynamics",
        "pharmacogenetics",
        "data_handling",
        "demographics",
        "treatment_exposure",
    ]

    COMPARISON_PROMPT = """You are comparing a GENERATED SAP against an ORIGINAL SAP to assess accuracy.

For each section, identify:
1. CORRECT elements: Items in generated SAP that match the original
2. MISSING elements: Items in original SAP that are absent from generated
3. WRONG elements: Items in generated SAP that contradict the original
4. EXTRA elements: Items in generated SAP not in original (may be acceptable)

Return JSON:
{
    "sections": [
        {
            "section_name": "string",
            "status": "correct|partial|missing|wrong",
            "correct_elements": ["list of correct items"],
            "missing_elements": ["list of missing items with specific details"],
            "wrong_elements": ["list of incorrect items with what's wrong"],
            "extra_elements": ["list of extra items"],
            "score": 0.0-1.0,
            "notes": "brief explanation"
        }
    ],
    "overall_score": 0.0-1.0,
    "critical_gaps": ["list of most important missing/wrong items"],
    "summary": "2-3 sentence overall assessment"
}

SECTIONS TO COMPARE:
1. Introduction/Study Design (blinding, phases, dosing schedules, sample size)
2. Objectives and Endpoints (primary, secondary, exploratory)
3. Analysis Populations (Safety, DLT-evaluable, PK-evaluable, Response-evaluable)
4. Statistical Hypotheses (or lack thereof for Phase 1)
5. Interim Analysis (if applicable)
6. Statistical Methods for Efficacy (ORR, PFS, DOR definitions, censoring rules)
7. Safety Analysis (TEAE definition, AE categories, lab parameters, ECG analysis)
8. Missing Data Handling (date imputation rules)
9. Pharmacokinetics (parameters, BLQ handling, dose proportionality)
10. Pharmacodynamics (biomarkers, IHC)
11. Pharmacogenetics (if applicable)
12. Data Handling Conventions (baseline, visit windowing)
13. Demographics/Baseline (formulas, categories)
14. Treatment Exposure (dose intensity, modifications)

Be SPECIFIC about what's missing. Don't just say "missing details" - say exactly what details are missing.

===== ORIGINAL SAP =====
{original_sap}

===== GENERATED SAP =====
{generated_sap}

Return ONLY valid JSON:"""

    def __init__(self, output_dir: str = None, verbose: bool = True, pipeline: str = "integrated"):
        """
        Initialize the tester.

        Args:
            output_dir: Directory to save generated SAPs and reports
            verbose: Print progress information
            pipeline: Which pipeline to use - "direct" or "integrated" (default)
        """
        self.output_dir = Path(output_dir) if output_dir else Path("./test_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        self.pipeline_type = pipeline

        # Initialize components
        self.console = Console() if RICH_AVAILABLE else None
        self.anthropic = Anthropic() if ANTHROPIC_AVAILABLE else None

        # Initialize the selected pipeline
        if pipeline == "integrated":
            if INTEGRATED_PIPELINE_AVAILABLE:
                self.pipeline = IntegratedSAPPipeline()
                print(f"[*] Using IntegratedSAPPipeline (LLM extraction + RAG + KnowledgeGraph)")
            else:
                print("[!] IntegratedSAPPipeline not available, falling back to TwoPassExtractor")
                self.pipeline = TwoPassExtractor() if PIPELINE_AVAILABLE else None
                self.pipeline_type = "direct"
        else:
            self.pipeline = TwoPassExtractor() if PIPELINE_AVAILABLE else None
            print(f"[*] Using TwoPassExtractor (discovery + generation)")

        # Check requirements
        self._check_requirements()

    def _check_requirements(self):
        """Check that all required components are available"""
        missing = []

        if not PIPELINE_AVAILABLE:
            missing.append("TwoPassExtractor (production pipeline)")
        if not LLAMAPARSE_AVAILABLE:
            missing.append("LlamaParse (pip install llama-cloud-services)")
        if not ANTHROPIC_AVAILABLE:
            missing.append("Anthropic (pip install anthropic)")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            missing.append("ANTHROPIC_API_KEY environment variable")
        if not (os.environ.get("LLAMAPARSE_API_KEY") or os.environ.get("LLAMA_CLOUD_API_KEY")):
            missing.append("LLAMAPARSE_API_KEY or LLAMA_CLOUD_API_KEY environment variable")

        if missing:
            print("\n[!] Missing requirements:")
            for m in missing:
                print(f"    - {m}")
            print("\nSome functionality may be limited.\n")

    def extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text from PDF using LlamaParse"""
        if not LLAMAPARSE_AVAILABLE:
            # Fallback to PyMuPDF
            try:
                import fitz
                doc = fitz.open(pdf_path)
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                return text
            except ImportError:
                raise ImportError("Install PyMuPDF: pip install PyMuPDF")

        api_key = os.environ.get("LLAMAPARSE_API_KEY") or os.environ.get("LLAMA_CLOUD_API_KEY")
        if not api_key:
            raise ValueError("Set LLAMAPARSE_API_KEY or LLAMA_CLOUD_API_KEY")

        if self.verbose:
            print(f"  Extracting text from: {Path(pdf_path).name}")

        llamaparse = LlamaParse(
            api_key=api_key,
            result_type="markdown",
            verbose=False
        )

        # Run async parse
        async def async_parse():
            return await llamaparse.aparse(pdf_path)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(async_parse())
        finally:
            loop.close()

        # Get markdown
        markdown_docs = result.get_markdown_documents(split_by_page=False)
        if markdown_docs:
            return "\n\n".join(doc.text for doc in markdown_docs)

        return ""

    def generate_sap(self, protocol_path: str) -> Tuple[str, float]:
        """
        Generate SAP from protocol using selected pipeline.

        Returns:
            Tuple of (generated_sap_text, generation_time_seconds)
        """
        if not self.pipeline:
            raise RuntimeError("No pipeline available")

        if self.verbose:
            print(f"\n[*] Generating SAP from: {Path(protocol_path).name}")
            print(f"    Pipeline: {self.pipeline_type}")

        start_time = time.time()

        # Extract protocol text first
        protocol_text = self.extract_pdf_text(protocol_path)

        if self.pipeline_type == "integrated":
            # Use IntegratedSAPPipeline
            result = self.pipeline.generate(protocol_text)
            sap_text = result.sap_text if hasattr(result, 'sap_text') else str(result)

            # Print extraction details if available
            if self.verbose and hasattr(result, 'facts') and result.facts:
                facts = result.facts
                if facts.get('interim_analysis'):
                    ia = facts['interim_analysis']
                    print(f"    Interim analyses found: {ia.get('num_interim_analyses', 0)}")
                if facts.get('power_calculations'):
                    pc = facts['power_calculations']
                    print(f"    Power calculations: PFS={pc.get('pfs_power', 'N/A')}")
                if facts.get('censoring_rules'):
                    cr = facts['censoring_rules']
                    print(f"    Censoring rules: PFS={len(cr.get('pfs_censoring', []))}, DOR={len(cr.get('dor_censoring', []))}")
        else:
            # Use TwoPassExtractor
            result = self.pipeline.process_protocol(
                protocol_text=protocol_text,
                protocol_id=Path(protocol_path).stem,
                validate=False,
                verbose=self.verbose
            )
            sap_text = result.get("sap_text", "")

        elapsed = time.time() - start_time

        if self.verbose:
            print(f"  Generated {len(sap_text):,} characters in {elapsed:.1f}s")

        return sap_text, elapsed

    def compare_saps(self, generated_sap: str, original_sap: str) -> Dict[str, Any]:
        """
        Compare generated SAP against original using LLM.

        Returns:
            Comparison result dictionary
        """
        if not self.anthropic:
            raise RuntimeError("Anthropic client not available")

        if self.verbose:
            print("\n[*] Comparing SAPs...")

        # Truncate if too long
        max_chars = 80000
        if len(original_sap) > max_chars:
            original_sap = original_sap[:max_chars] + "\n...[truncated]"
        if len(generated_sap) > max_chars:
            generated_sap = generated_sap[:max_chars] + "\n...[truncated]"

        prompt = self.COMPARISON_PROMPT.format(
            original_sap=original_sap,
            generated_sap=generated_sap
        )

        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text

        # Parse JSON
        try:
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            return json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            print(f"  Warning: Could not parse comparison result: {e}")
            return {
                "sections": [],
                "overall_score": 0.0,
                "critical_gaps": ["Comparison parsing failed"],
                "summary": response_text[:500]
            }

    def test_single(self, protocol_path: str, original_sap_path: str) -> AccuracyReport:
        """
        Test a single protocol/SAP pair.

        Args:
            protocol_path: Path to protocol PDF
            original_sap_path: Path to original SAP PDF

        Returns:
            AccuracyReport with detailed comparison
        """
        protocol_name = Path(protocol_path).stem

        if self.verbose:
            print(f"\n{'='*70}")
            print(f"TESTING: {protocol_name}")
            print(f"{'='*70}")

        # 1. Generate SAP
        generated_sap, gen_time = self.generate_sap(protocol_path)

        # Save generated SAP
        gen_sap_path = self.output_dir / f"{protocol_name}_generated.txt"
        with open(gen_sap_path, "w", encoding="utf-8") as f:
            f.write(generated_sap)

        # 2. Extract original SAP text
        if self.verbose:
            print("\n[*] Extracting original SAP...")
        original_sap = self.extract_pdf_text(original_sap_path)

        # 3. Compare
        comparison = self.compare_saps(generated_sap, original_sap)

        # 4. Build report
        report = AccuracyReport(
            protocol_name=protocol_name,
            generation_time_s=gen_time,
            overall_score=comparison.get("overall_score", 0.0),
            critical_gaps=comparison.get("critical_gaps", []),
            summary=comparison.get("summary", ""),
            generated_sap_path=str(gen_sap_path)
        )

        # Add section comparisons
        for section in comparison.get("sections", []):
            sc = SectionComparison(
                section_name=section.get("section_name", "Unknown"),
                status=section.get("status", "unknown"),
                correct_elements=section.get("correct_elements", []),
                missing_elements=section.get("missing_elements", []),
                wrong_elements=section.get("wrong_elements", []),
                extra_elements=section.get("extra_elements", []),
                score=section.get("score", 0.0),
                notes=section.get("notes", "")
            )
            report.section_comparisons.append(sc)
            report.section_scores[sc.section_name] = sc.score

        # Save report
        report_path = self.output_dir / f"{protocol_name}_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)

        if self.verbose:
            self._print_report(report)

        return report

    def test_directory(self, test_dir: str) -> List[AccuracyReport]:
        """
        Test all protocol/SAP pairs in a directory.

        Expects files named like:
        - test1protocol.pdf, test1sap.pdf
        - test2protocol.pdf, test2sap.pdf

        Returns:
            List of AccuracyReports
        """
        test_dir = Path(test_dir)
        if not test_dir.exists():
            raise ValueError(f"Directory not found: {test_dir}")

        # Find all protocol files
        protocol_files = list(test_dir.glob("*protocol*.pdf")) + list(test_dir.glob("*Protocol*.pdf"))

        reports = []

        for protocol_path in sorted(protocol_files):
            # Find matching SAP
            name = protocol_path.stem.lower().replace("protocol", "")

            # Try different naming conventions
            sap_patterns = [
                f"*{name}sap*.pdf",
                f"*{name}SAP*.pdf",
                f"*{name}_sap*.pdf",
                f"*sap*{name}*.pdf",
            ]

            sap_path = None
            for pattern in sap_patterns:
                matches = list(test_dir.glob(pattern))
                if matches:
                    sap_path = matches[0]
                    break

            if not sap_path:
                print(f"Warning: No SAP found for {protocol_path.name}")
                continue

            try:
                report = self.test_single(str(protocol_path), str(sap_path))
                reports.append(report)
            except Exception as e:
                print(f"Error testing {protocol_path.name}: {e}")
                import traceback
                traceback.print_exc()

        # Print summary
        if reports:
            self._print_summary(reports)

        return reports

    def _print_report(self, report: AccuracyReport):
        """Print a single accuracy report"""
        if RICH_AVAILABLE and self.console:
            # Rich output
            self.console.print(f"\n[bold]Results for {report.protocol_name}[/bold]")
            self.console.print(f"Generation time: {report.generation_time_s:.1f}s")
            self.console.print(f"Overall score: [{'green' if report.overall_score >= 0.7 else 'yellow' if report.overall_score >= 0.5 else 'red'}]{report.overall_score:.1%}[/]")

            # Section table
            table = Table(title="Section Scores")
            table.add_column("Section", style="cyan")
            table.add_column("Score", justify="right")
            table.add_column("Status")
            table.add_column("Missing Elements", style="red")

            for sc in report.section_comparisons:
                score_color = "green" if sc.score >= 0.7 else "yellow" if sc.score >= 0.5 else "red"
                missing = ", ".join(sc.missing_elements[:3])
                if len(sc.missing_elements) > 3:
                    missing += f" (+{len(sc.missing_elements)-3} more)"

                table.add_row(
                    sc.section_name,
                    f"[{score_color}]{sc.score:.0%}[/]",
                    sc.status,
                    missing[:80]
                )

            self.console.print(table)

            # Critical gaps
            if report.critical_gaps:
                self.console.print("\n[bold red]Critical Gaps:[/bold red]")
                for gap in report.critical_gaps[:10]:
                    self.console.print(f"  - {gap}")

            self.console.print(f"\n[bold]Summary:[/bold] {report.summary}")
            self.console.print(f"Generated SAP saved to: {report.generated_sap_path}")
        else:
            # Plain output
            print(f"\nResults for {report.protocol_name}")
            print(f"Generation time: {report.generation_time_s:.1f}s")
            print(f"Overall score: {report.overall_score:.1%}")
            print("\nSection Scores:")
            for sc in report.section_comparisons:
                print(f"  {sc.section_name}: {sc.score:.0%} ({sc.status})")
                if sc.missing_elements:
                    print(f"    Missing: {', '.join(sc.missing_elements[:3])}")

            if report.critical_gaps:
                print("\nCritical Gaps:")
                for gap in report.critical_gaps[:10]:
                    print(f"  - {gap}")

            print(f"\nSummary: {report.summary}")

    def _print_summary(self, reports: List[AccuracyReport]):
        """Print summary of all tests"""
        print(f"\n{'='*70}")
        print("OVERALL SUMMARY")
        print(f"{'='*70}")

        avg_score = sum(r.overall_score for r in reports) / len(reports)
        avg_time = sum(r.generation_time_s for r in reports) / len(reports)

        print(f"Tests run: {len(reports)}")
        print(f"Average score: {avg_score:.1%}")
        print(f"Average generation time: {avg_time:.1f}s")

        # Best and worst
        best = max(reports, key=lambda r: r.overall_score)
        worst = min(reports, key=lambda r: r.overall_score)

        print(f"\nBest: {best.protocol_name} ({best.overall_score:.1%})")
        print(f"Worst: {worst.protocol_name} ({worst.overall_score:.1%})")

        # Common missing elements
        all_missing = []
        for r in reports:
            for sc in r.section_comparisons:
                all_missing.extend(sc.missing_elements)

        if all_missing:
            from collections import Counter
            common = Counter(all_missing).most_common(10)
            print("\nMost commonly missing elements:")
            for elem, count in common:
                print(f"  - {elem} (missing in {count} SAPs)")

        # Save summary
        summary_path = self.output_dir / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "tests_run": len(reports),
                "average_score": avg_score,
                "average_generation_time": avg_time,
                "reports": [r.to_dict() for r in reports]
            }, f, indent=2)

        print(f"\nFull results saved to: {self.output_dir}")


def convert_windows_path(path: str) -> str:
    """Convert Windows path to WSL path if running on WSL"""
    if not path:
        return path

    # Check if we're on WSL and path is Windows-style
    import platform
    is_wsl = 'microsoft' in platform.uname().release.lower() or 'wsl' in platform.uname().release.lower()

    if is_wsl and len(path) >= 2 and path[1] == ':':
        # Convert C:\path to /mnt/c/path
        drive = path[0].lower()
        rest = path[2:].replace('\\', '/')
        return f"/mnt/{drive}{rest}"

    # Also handle backslashes on any platform
    return path.replace('\\', '/')


def main():
    parser = argparse.ArgumentParser(
        description="Test SAP generation accuracy against original SAPs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test all files in a directory (works with Windows or WSL paths)
  python test_sap_accuracy.py --test-dir "C:/Users/vijay/Downloads/Testing"
  python test_sap_accuracy.py --test-dir "/mnt/c/Users/vijay/Downloads/Testing"

  # Test a single protocol/SAP pair
  python test_sap_accuracy.py --protocol "path/to/protocol.pdf" --original-sap "path/to/sap.pdf"

  # Specify output directory
  python test_sap_accuracy.py --test-dir "./Testing" --output-dir "./results"
"""
    )

    parser.add_argument(
        "--test-dir", "-d",
        help="Directory containing protocol and SAP PDFs to test"
    )
    parser.add_argument(
        "--protocol", "-p",
        help="Path to single protocol PDF"
    )
    parser.add_argument(
        "--original-sap", "-s",
        help="Path to original SAP PDF (for single test)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="./test_results",
        help="Directory to save results (default: ./test_results)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Reduce output verbosity"
    )
    parser.add_argument(
        "--pipeline",
        choices=["integrated", "direct"],
        default="integrated",
        help="Pipeline to use: 'integrated' (LLM extraction + RAG, default) or 'direct' (TwoPassExtractor)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.test_dir and not (args.protocol and args.original_sap):
        parser.error("Either --test-dir or both --protocol and --original-sap are required")

    if args.protocol and not args.original_sap:
        parser.error("--original-sap is required when using --protocol")

    # Convert Windows paths to WSL paths if needed
    test_dir = convert_windows_path(args.test_dir) if args.test_dir else None
    protocol = convert_windows_path(args.protocol) if args.protocol else None
    original_sap = convert_windows_path(args.original_sap) if args.original_sap else None
    output_dir = convert_windows_path(args.output_dir)

    # Show converted paths for debugging
    if args.test_dir and test_dir != args.test_dir:
        print(f"[*] Converted path: {args.test_dir} -> {test_dir}")

    # Run tests
    tester = SAPAccuracyTester(
        output_dir=output_dir,
        verbose=not args.quiet,
        pipeline=args.pipeline
    )

    if test_dir:
        tester.test_directory(test_dir)
    else:
        tester.test_single(protocol, original_sap)


if __name__ == "__main__":
    main()
