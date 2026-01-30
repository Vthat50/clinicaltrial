"""Compare generated SAP against reference SAP."""
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from src.ingestion.pdf_extractor import PDFExtractor
from .metrics import SAPMetrics, ComparisonResult, SectionMetrics

console = Console()


class SAPComparator:
    """Compare generated SAP against reference SAP files."""

    def __init__(self):
        self.metrics = SAPMetrics()
        self.pdf_extractor = PDFExtractor()

    def compare(
        self,
        generated_sap: str,
        reference_path: Path,
    ) -> ComparisonResult:
        """Compare generated SAP against reference SAP.

        Args:
            generated_sap: Generated SAP text
            reference_path: Path to reference SAP PDF

        Returns:
            ComparisonResult with detailed metrics
        """
        # Extract reference SAP text
        reference_content = self._load_reference(reference_path)
        if not reference_content:
            console.print(f"[red]Could not load reference SAP: {reference_path}[/red]")
            return self._empty_result(reference_path.stem.split('_')[0])

        nct_id = reference_path.stem.split('_')[0]

        # Identify sections in both
        gen_sections = self.metrics.identify_sections(generated_sap)
        ref_sections = self.metrics.identify_sections(reference_content)

        # Calculate section metrics
        section_metrics = []
        all_section_names = set(gen_sections.keys()) | set(ref_sections.keys())

        for section_name in all_section_names:
            gen_content = gen_sections.get(section_name, "")
            ref_content = ref_sections.get(section_name, "")

            similarity = self.metrics.calculate_text_similarity(
                gen_content, ref_content
            ) if gen_content and ref_content else 0.0

            section_metrics.append(SectionMetrics(
                section_name=section_name,
                present_in_generated=bool(gen_content),
                present_in_reference=bool(ref_content),
                similarity_score=similarity,
                word_count_generated=self.metrics.word_count(gen_content),
                word_count_reference=self.metrics.word_count(ref_content),
                coverage_ratio=(
                    self.metrics.word_count(gen_content) /
                    self.metrics.word_count(ref_content)
                    if ref_content else 0
                ),
            ))

        # Calculate overall metrics
        overall_similarity = self.metrics.calculate_text_similarity(
            generated_sap, reference_content
        )

        # Section coverage: how many reference sections are in generated
        ref_section_count = len(ref_sections)
        covered_sections = sum(
            1 for m in section_metrics
            if m.present_in_reference and m.present_in_generated
        )
        section_coverage = covered_sections / ref_section_count if ref_section_count else 0

        # Content coverage via term overlap
        content_coverage = self.metrics.term_coverage(generated_sap, reference_content)

        # Identify missing/extra sections
        missing = [
            m.section_name for m in section_metrics
            if m.present_in_reference and not m.present_in_generated
        ]
        extra = [
            m.section_name for m in section_metrics
            if m.present_in_generated and not m.present_in_reference
        ]

        return ComparisonResult(
            nct_id=nct_id,
            overall_similarity=overall_similarity,
            section_coverage=section_coverage,
            content_coverage=content_coverage,
            section_metrics=section_metrics,
            missing_sections=missing,
            extra_sections=extra,
        )

    def _load_reference(self, path: Path) -> Optional[str]:
        """Load reference SAP from PDF or text file."""
        if path.suffix.lower() == '.pdf':
            content = self.pdf_extractor.extract(path)
            return content.full_text if content else None
        else:
            try:
                return path.read_text(encoding='utf-8')
            except Exception:
                return None

    def _empty_result(self, nct_id: str) -> ComparisonResult:
        """Return empty result when comparison fails."""
        return ComparisonResult(
            nct_id=nct_id,
            overall_similarity=0.0,
            section_coverage=0.0,
            content_coverage=0.0,
        )

    def print_comparison_report(self, result: ComparisonResult):
        """Print a formatted comparison report."""
        console.print(f"\n[bold cyan]SAP Comparison Report: {result.nct_id}[/bold cyan]\n")

        # Overall metrics table
        overall_table = Table(title="Overall Metrics")
        overall_table.add_column("Metric", style="cyan")
        overall_table.add_column("Score", style="green")

        overall_table.add_row("Overall Similarity", f"{result.overall_similarity:.1%}")
        overall_table.add_row("Section Coverage", f"{result.section_coverage:.1%}")
        overall_table.add_row("Term Coverage", f"{result.content_coverage:.1%}")

        console.print(overall_table)

        # Section details table
        if result.section_metrics:
            section_table = Table(title="\nSection Details")
            section_table.add_column("Section", style="cyan")
            section_table.add_column("In Gen", style="yellow")
            section_table.add_column("In Ref", style="yellow")
            section_table.add_column("Similarity", style="green")
            section_table.add_column("Words (Gen/Ref)", style="blue")

            for m in sorted(result.section_metrics, key=lambda x: x.section_name):
                section_table.add_row(
                    m.section_name,
                    "✓" if m.present_in_generated else "✗",
                    "✓" if m.present_in_reference else "✗",
                    f"{m.similarity_score:.1%}" if m.similarity_score else "-",
                    f"{m.word_count_generated}/{m.word_count_reference}",
                )

            console.print(section_table)

        # Missing sections
        if result.missing_sections:
            console.print(f"\n[yellow]Missing sections: {', '.join(result.missing_sections)}[/yellow]")

        if result.extra_sections:
            console.print(f"[blue]Extra sections: {', '.join(result.extra_sections)}[/blue]")

    def batch_compare(
        self,
        generated_saps: dict[str, str],
        reference_dir: Path,
    ) -> list[ComparisonResult]:
        """Compare multiple generated SAPs against references.

        Args:
            generated_saps: Dict mapping NCT ID to generated SAP text
            reference_dir: Directory containing reference SAP PDFs

        Returns:
            List of comparison results
        """
        results = []

        for nct_id, generated in generated_saps.items():
            ref_path = reference_dir / f"{nct_id}_SAP.pdf"
            if ref_path.exists():
                console.print(f"[blue]Comparing {nct_id}...[/blue]")
                result = self.compare(generated, ref_path)
                results.append(result)
                self.print_comparison_report(result)
            else:
                console.print(f"[yellow]No reference SAP found for {nct_id}[/yellow]")

        # Print summary
        if results:
            self._print_summary(results)

        return results

    def _print_summary(self, results: list[ComparisonResult]):
        """Print summary statistics across all comparisons."""
        console.print("\n[bold cyan]═══ Batch Comparison Summary ═══[/bold cyan]\n")

        avg_similarity = sum(r.overall_similarity for r in results) / len(results)
        avg_section_cov = sum(r.section_coverage for r in results) / len(results)
        avg_content_cov = sum(r.content_coverage for r in results) / len(results)

        summary_table = Table(title="Average Metrics")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Average", style="green")

        summary_table.add_row("Overall Similarity", f"{avg_similarity:.1%}")
        summary_table.add_row("Section Coverage", f"{avg_section_cov:.1%}")
        summary_table.add_row("Term Coverage", f"{avg_content_cov:.1%}")
        summary_table.add_row("Trials Compared", str(len(results)))

        console.print(summary_table)
