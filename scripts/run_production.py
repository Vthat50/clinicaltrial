#!/usr/bin/env python3
"""Production pipeline: Azure DI → Claude → Validation → Human Review."""
import sys
import json
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import PROTOCOLS_DIR, SAPS_DIR, PROCESSED_DIR
from src.config_production import ProductionConfig
from src.ingestion.azure_extractor import HybridExtractor
from src.parsing.protocol_parser import ProtocolParser
from src.sap_generation.claude_transformer import ClaudeTransformer
from src.sap_generation.validator import SAPValidator
from src.sap_generation.docx_writer import create_sap_docx
from src.sap_comparison.compare import SAPComparator

console = Console()


def run_production_pipeline(nct_ids: list[str] = None, output_format: str = "both"):
    """Run the full production pipeline.

    Args:
        nct_ids: List of NCT IDs to process (None = all)
        output_format: "md", "docx", or "both"
    """
    config = ProductionConfig.load()

    # Print configuration status
    console.print(Panel("[bold]Production Pipeline Configuration[/bold]"))
    status = config.validate()
    for key, value in status.items():
        icon = "✅" if value else "❌"
        console.print(f"  {icon} {key}: {value}")
    console.print()

    # Initialize components
    extractor = HybridExtractor()
    parser = ProtocolParser(use_claude=config.claude is not None)
    transformer = ClaudeTransformer() if config.claude else None
    validator = SAPValidator()

    # Output directories
    output_dir = PROCESSED_DIR / "production_output"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "saps").mkdir(exist_ok=True)
    (output_dir / "qc_checklists").mkdir(exist_ok=True)
    (output_dir / "structured_data").mkdir(exist_ok=True)

    # Get protocols to process
    if nct_ids:
        protocol_files = [PROTOCOLS_DIR / f"{nct}_Protocol.pdf" for nct in nct_ids]
        protocol_files = [p for p in protocol_files if p.exists()]
    else:
        protocol_files = list(PROTOCOLS_DIR.glob("*.pdf"))

    console.print(f"[blue]Processing {len(protocol_files)} protocols...[/blue]\n")

    results = []

    for pdf_path in protocol_files:
        nct_id = pdf_path.stem.replace("_Protocol", "")
        console.print(Panel(f"[bold cyan]Processing {nct_id}[/bold cyan]"))

        try:
            # Step 1: Extract with Azure DI / pdfplumber
            console.print("[blue]Step 1: Extracting document structure...[/blue]")
            extraction = extractor.extract(pdf_path)
            if not extraction:
                console.print(f"[red]Extraction failed for {nct_id}[/red]")
                continue

            # Save structured extraction
            extraction_path = output_dir / "structured_data" / f"{nct_id}_extracted.json"
            with open(extraction_path, 'w') as f:
                json.dump({
                    "nct_id": nct_id,
                    "total_pages": extraction.total_pages,
                    "tables_count": len(extraction.tables),
                    "sections_count": len(extraction.sections),
                    "key_value_pairs": extraction.key_value_pairs,
                }, f, indent=2)

            # Step 2: Parse protocol
            console.print("[blue]Step 2: Parsing protocol structure...[/blue]")
            protocol = parser.parse(extraction.raw_text, nct_id)

            # Step 3: Transform to SAP language with Claude
            console.print("[blue]Step 3: Transforming to SAP language...[/blue]")
            sections = {s.section_type.value: s.content for s in protocol.sections}

            if transformer:
                transformed = transformer.transform_protocol_to_sap(
                    sections,
                    {"title": protocol.title, "phase": protocol.phase, "nct_id": nct_id}
                )
                # Use transformed content
                sap_sections = {k: v.sap_content for k, v in transformed.items()}

                # Generate missing recommended sections using Claude
                # These sections are required for high validation scores
                recommended_sections = ["missing_data", "multiplicity", "sensitivity_analyses", "interim_analyses", "subgroup_analyses"]
                stats_content = sections.get("statistical_methods", "") + "\n" + sections.get("efficacy_analyses", "")

                for rec_section in recommended_sections:
                    if rec_section not in sap_sections or len(sap_sections.get(rec_section, "")) < 50:
                        console.print(f"  Generating {rec_section}...")
                        result = transformer.transform_section(rec_section, stats_content,
                            {"title": protocol.title, "phase": protocol.phase, "nct_id": nct_id})
                        if result and result.confidence > 0:
                            sap_sections[rec_section] = result.sap_content
            else:
                sap_sections = sections
                console.print("[yellow]Claude not available - using raw extracted content[/yellow]")

            # Step 4: Validate
            console.print("[blue]Step 4: Validating SAP content...[/blue]")
            full_sap_content = "\n\n".join(sap_sections.values())
            validation = validator.validate(full_sap_content, sap_sections, nct_id)
            validator.print_report(validation)

            # Step 5: Generate outputs
            console.print("[blue]Step 5: Generating outputs...[/blue]")

            # Markdown output
            if output_format in ("md", "both"):
                md_path = output_dir / "saps" / f"{nct_id}_SAP.md"
                with open(md_path, 'w') as f:
                    f.write(f"# Statistical Analysis Plan\n\n")
                    f.write(f"## {protocol.title or nct_id}\n\n")
                    f.write(f"**NCT ID:** {nct_id}\n")
                    f.write(f"**Version:** 1.0\n")
                    f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n")
                    f.write(f"**Validation Score:** {validation.score}/100\n\n")
                    f.write("---\n\n")

                    for section_type, content in sap_sections.items():
                        f.write(f"## {section_type.replace('_', ' ').title()}\n\n")
                        f.write(f"{content}\n\n")

                console.print(f"  [green]Saved: {md_path.name}[/green]")

            # DOCX output
            if output_format in ("docx", "both"):
                docx_path = create_sap_docx(
                    nct_id=nct_id,
                    title=protocol.title or f"Study {nct_id}",
                    sections=sap_sections,
                    output_dir=output_dir / "saps",
                    validation_score=validation.score
                )
                if docx_path:
                    console.print(f"  [green]Saved: {docx_path.name}[/green]")

            # QC Checklist
            qc_path = output_dir / "qc_checklists" / f"{nct_id}_QC_Checklist.md"
            with open(qc_path, 'w') as f:
                f.write(validator.generate_qc_checklist(validation))
            console.print(f"  [green]Saved: {qc_path.name}[/green]")

            results.append({
                "nct_id": nct_id,
                "validation_score": validation.score,
                "is_valid": validation.is_valid,
                "sections_present": len(validation.sections_present),
                "errors": len(validation.get_errors()),
                "warnings": len(validation.get_warnings()),
            })

        except Exception as e:
            console.print(f"[red]Error processing {nct_id}: {e}[/red]")
            import traceback
            traceback.print_exc()

    # Summary
    console.print(Panel("[bold]Pipeline Complete[/bold]"))

    if results:
        table = Table(title="Processing Summary")
        table.add_column("NCT ID")
        table.add_column("Score")
        table.add_column("Valid")
        table.add_column("Sections")
        table.add_column("Errors")
        table.add_column("Warnings")

        for r in results:
            table.add_row(
                r["nct_id"],
                f"{r['validation_score']:.1f}",
                "✅" if r["is_valid"] else "❌",
                str(r["sections_present"]),
                str(r["errors"]),
                str(r["warnings"])
            )

        console.print(table)

        avg_score = sum(r["validation_score"] for r in results) / len(results)
        valid_count = sum(1 for r in results if r["is_valid"])

        console.print(f"\n[bold]Average Score:[/bold] {avg_score:.1f}/100")
        console.print(f"[bold]Valid SAPs:[/bold] {valid_count}/{len(results)}")
        console.print(f"\n[blue]Output directory:[/blue] {output_dir}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Production SAP Pipeline")
    parser.add_argument("--nct", nargs="+", help="Specific NCT IDs to process")
    parser.add_argument("--format", choices=["md", "docx", "both"], default="both",
                        help="Output format")
    parser.add_argument("--list", action="store_true", help="List available protocols")

    args = parser.parse_args()

    if args.list:
        console.print("[bold]Available protocols:[/bold]")
        for pdf in PROTOCOLS_DIR.glob("*.pdf"):
            console.print(f"  - {pdf.stem.replace('_Protocol', '')}")
        return

    run_production_pipeline(nct_ids=args.nct, output_format=args.format)


if __name__ == "__main__":
    main()
