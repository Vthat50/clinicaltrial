#!/usr/bin/env python3
"""Main pipeline orchestrator for clinical trial protocol processing."""
import sys
import json
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import PROTOCOLS_DIR, SAPS_DIR, PROCESSED_DIR, DATABASE_DIR
from src.ingestion.downloader import download_all_protocols
from src.ingestion.pdf_extractor import PDFExtractor
from src.parsing.protocol_parser import ProtocolParser
from src.database.models import init_db
from src.database.operations import DatabaseOperations
from src.sap_generation.generator import SAPGenerator
from src.sap_comparison.compare import SAPComparator

console = Console()


def step_download():
    """Step 1: Download protocol-SAP pairs."""
    console.print(Panel("[bold cyan]Step 1: Downloading Protocol-SAP Pairs[/bold cyan]"))
    results = download_all_protocols(skip_existing=True)
    return results


def step_extract_pdfs():
    """Step 2: Extract text from PDFs."""
    console.print(Panel("[bold cyan]Step 2: Extracting Text from PDFs[/bold cyan]"))

    extractor = PDFExtractor()
    extracted = {"protocols": [], "saps": []}

    # Extract protocols
    for pdf_file in PROTOCOLS_DIR.glob("*.pdf"):
        console.print(f"[blue]Extracting {pdf_file.name}...[/blue]")
        output_file = PROCESSED_DIR / f"{pdf_file.stem}.txt"

        if output_file.exists():
            console.print(f"  [yellow]Skipping (exists)[/yellow]")
            extracted["protocols"].append(pdf_file.stem)
            continue

        if extractor.extract_to_file(pdf_file, output_file):
            extracted["protocols"].append(pdf_file.stem)
            console.print(f"  [green]Done[/green]")
        else:
            console.print(f"  [red]Failed[/red]")

    # Extract SAPs (for comparison)
    for pdf_file in SAPS_DIR.glob("*.pdf"):
        console.print(f"[blue]Extracting {pdf_file.name}...[/blue]")
        output_file = PROCESSED_DIR / f"{pdf_file.stem}.txt"

        if output_file.exists():
            console.print(f"  [yellow]Skipping (exists)[/yellow]")
            extracted["saps"].append(pdf_file.stem)
            continue

        if extractor.extract_to_file(pdf_file, output_file):
            extracted["saps"].append(pdf_file.stem)
            console.print(f"  [green]Done[/green]")

    console.print(f"\n[green]Extracted {len(extracted['protocols'])} protocols, {len(extracted['saps'])} SAPs[/green]")
    return extracted


def step_parse_protocols(use_claude: bool = True):
    """Step 3: Parse protocols into structured data."""
    console.print(Panel("[bold cyan]Step 3: Parsing Protocols[/bold cyan]"))

    parser = ProtocolParser(use_claude=use_claude)
    parsed = []

    for txt_file in PROCESSED_DIR.glob("*_Protocol.txt"):
        nct_id = txt_file.stem.replace("_Protocol", "")
        console.print(f"[blue]Parsing {nct_id}...[/blue]")

        with open(txt_file, 'r', encoding='utf-8') as f:
            text = f.read()

        protocol = parser.parse(text, nct_id)
        parsed.append(protocol)

        console.print(f"  Title: {protocol.title[:50] if protocol.title else 'N/A'}...")
        console.print(f"  Sections: {len(protocol.sections)}")

    console.print(f"\n[green]Parsed {len(parsed)} protocols[/green]")
    return parsed


def step_store_database(parsed_protocols):
    """Step 4: Store parsed data in database."""
    console.print(Panel("[bold cyan]Step 4: Storing in Database[/bold cyan]"))

    init_db()
    db = DatabaseOperations()

    for protocol in parsed_protocols:
        console.print(f"[blue]Storing {protocol.nct_id}...[/blue]")

        # Get or create trial
        trial = db.get_or_create_trial(
            nct_id=protocol.nct_id,
            title=protocol.title,
            phase=protocol.phase,
            sponsor=protocol.sponsor,
        )

        # Find raw text file
        raw_text_file = PROCESSED_DIR / f"{protocol.nct_id}_Protocol.txt"
        raw_text = ""
        if raw_text_file.exists():
            raw_text = raw_text_file.read_text(encoding='utf-8')

        # Save protocol with sections
        db.save_protocol(
            trial=trial,
            file_path=str(PROTOCOLS_DIR / f"{protocol.nct_id}_Protocol.pdf"),
            raw_text=raw_text,
            parsed_protocol=protocol,
        )

    stats = db.get_statistics()
    db.close()

    console.print(f"\n[green]Database updated:[/green]")
    for key, value in stats.items():
        console.print(f"  {key}: {value}")

    return stats


def step_generate_saps(parsed_protocols, use_llm: bool = True):
    """Step 5: Generate abbreviated SAPs."""
    console.print(Panel("[bold cyan]Step 5: Generating Abbreviated SAPs[/bold cyan]"))

    generator = SAPGenerator(use_llm=use_llm)
    generated = {}

    output_dir = PROCESSED_DIR / "generated_saps"
    output_dir.mkdir(exist_ok=True)

    for protocol in parsed_protocols:
        console.print(f"[blue]Generating SAP for {protocol.nct_id}...[/blue]")

        sap = generator.generate(protocol)
        generated[protocol.nct_id] = sap

        # Save to file
        output_path = output_dir / f"{protocol.nct_id}_Generated_SAP.md"
        generator.save_sap(sap, str(output_path))

        # Also save structured data as JSON
        json_path = output_dir / f"{protocol.nct_id}_structured.json"
        if protocol.structured_data:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(protocol.to_dict(), f, indent=2)

    console.print(f"\n[green]Generated {len(generated)} SAPs[/green]")
    return generated


def step_compare_saps(generated_saps):
    """Step 6: Compare generated SAPs against reference SAPs."""
    console.print(Panel("[bold cyan]Step 6: Comparing with Reference SAPs[/bold cyan]"))

    comparator = SAPComparator()

    # Get generated SAP content
    generated_content = {
        nct_id: sap.content for nct_id, sap in generated_saps.items()
    }

    results = comparator.batch_compare(generated_content, SAPS_DIR)

    # Save comparison results
    output_dir = PROCESSED_DIR / "comparison_results"
    output_dir.mkdir(exist_ok=True)

    summary = {
        "timestamp": datetime.now().isoformat(),
        "comparisons": [r.to_dict() for r in results],
    }

    with open(output_dir / "comparison_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

    return results


def run_full_pipeline(use_claude: bool = True, skip_download: bool = False):
    """Run the complete pipeline."""
    console.print(Panel(
        "[bold green]Clinical Trial Protocol Processing Pipeline[/bold green]\n"
        f"Using Claude: {use_claude}",
        title="Pipeline Start",
    ))

    start_time = datetime.now()

    # Step 1: Download
    if not skip_download:
        download_results = step_download()
    else:
        console.print("[yellow]Skipping download step[/yellow]")

    # Step 2: Extract PDFs
    extracted = step_extract_pdfs()

    # Step 3: Parse protocols
    parsed = step_parse_protocols(use_claude=use_claude)

    # Step 4: Store in database
    db_stats = step_store_database(parsed)

    # Step 5: Generate SAPs
    generated = step_generate_saps(parsed, use_llm=use_claude)

    # Step 6: Compare with reference SAPs
    comparison_results = step_compare_saps(generated)

    # Final summary
    end_time = datetime.now()
    duration = end_time - start_time

    console.print(Panel(
        f"[bold green]Pipeline Complete![/bold green]\n\n"
        f"Duration: {duration}\n"
        f"Protocols processed: {len(parsed)}\n"
        f"SAPs generated: {len(generated)}\n"
        f"Comparisons made: {len(comparison_results)}",
        title="Summary",
    ))


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Clinical Trial Protocol Pipeline")
    parser.add_argument("--no-claude", action="store_true", help="Disable Claude LLM (use regex only)")
    parser.add_argument("--skip-download", action="store_true", help="Skip downloading files")
    parser.add_argument("--step", choices=["download", "extract", "parse", "store", "generate", "compare"],
                        help="Run only a specific step")

    args = parser.parse_args()

    use_claude = not args.no_claude

    if args.step:
        if args.step == "download":
            step_download()
        elif args.step == "extract":
            step_extract_pdfs()
        elif args.step == "parse":
            parsed = step_parse_protocols(use_claude=use_claude)
        elif args.step == "store":
            parsed = step_parse_protocols(use_claude=use_claude)
            step_store_database(parsed)
        elif args.step == "generate":
            parsed = step_parse_protocols(use_claude=use_claude)
            step_generate_saps(parsed, use_llm=use_claude)
        elif args.step == "compare":
            parsed = step_parse_protocols(use_claude=use_claude)
            generated = step_generate_saps(parsed, use_llm=use_claude)
            step_compare_saps(generated)
    else:
        run_full_pipeline(use_claude=use_claude, skip_download=args.skip_download)


if __name__ == "__main__":
    main()
