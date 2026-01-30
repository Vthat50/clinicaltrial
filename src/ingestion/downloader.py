"""Download protocols and SAPs from ClinicalTrials.gov."""
import requests
from pathlib import Path
from rich.console import Console
from rich.progress import Progress

from src.config import PROTOCOLS_DIR, SAPS_DIR

console = Console()

# Trial NCT IDs to download
TRIAL_IDS = [
    "NCT01772472",  # Breast Cancer KATHERINE
    "NCT02855944",  # Ovarian ARIEL4
    "NCT03337724",  # Breast TNBC Ipatasertib
    "NCT04005716",  # NSCLC Tislelizumab
    "NCT03777657",  # Esophageal Tislelizumab
    "NCT02402062",  # Neuroendocrine SUNINET
    "NCT01515748",  # Gastric DOS
    "NCT04648033",  # NSCLC ARCADIAN
    "NCT02705105",  # Solid Tumors
    "NCT05126433",  # Lurbinectedin
]


def get_document_urls(nct_id: str) -> dict:
    """Fetch document URLs from ClinicalTrials.gov API.

    Returns dict with 'protocol' and 'sap' URLs if available.
    """
    api_url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"

    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json()

        docs = data.get('documentSection', {}).get('largeDocumentModule', {}).get('largeDocs', [])

        urls = {}
        # Get last 2 digits of NCT ID for URL path
        nct_suffix = nct_id[-2:]

        for doc in docs:
            doc_type = doc.get('typeAbbrev', '')
            filename = doc.get('filename', '')

            if filename:
                url = f"https://cdn.clinicaltrials.gov/large-docs/{nct_suffix}/{nct_id}/{filename}"

                if doc_type == 'Prot':
                    urls['protocol'] = url
                elif doc_type == 'SAP':
                    urls['sap'] = url
                elif doc_type == 'Prot_SAP':
                    # Combined file - use as both if no separate files
                    if 'protocol' not in urls:
                        urls['protocol'] = url
                    if 'sap' not in urls:
                        urls['sap'] = url

        return urls

    except Exception as e:
        console.print(f"[red]Error fetching docs for {nct_id}: {e}[/red]")
        return {}


def download_file(url: str, output_path: Path) -> bool:
    """Download a file from URL to the specified path."""
    try:
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        console.print(f"[red]Error downloading {url}: {e}[/red]")
        return False


def download_all_protocols(skip_existing: bool = True) -> dict:
    """Download all protocol-SAP pairs.

    Args:
        skip_existing: Skip files that already exist

    Returns:
        Dictionary with download results
    """
    results = {"success": [], "failed": [], "skipped": [], "no_docs": []}

    console.print("[cyan]Fetching document URLs from ClinicalTrials.gov API...[/cyan]\n")

    for nct_id in TRIAL_IDS:
        console.print(f"[blue]Processing {nct_id}...[/blue]")

        # Get URLs from API
        urls = get_document_urls(nct_id)

        if not urls:
            console.print(f"  [yellow]No documents found[/yellow]")
            results["no_docs"].append(nct_id)
            continue

        # Download protocol
        if 'protocol' in urls:
            protocol_path = PROTOCOLS_DIR / f"{nct_id}_Protocol.pdf"
            if skip_existing and protocol_path.exists():
                console.print(f"  [yellow]Protocol exists, skipping[/yellow]")
                results["skipped"].append(f"{nct_id}_Protocol")
            else:
                console.print(f"  [blue]Downloading Protocol...[/blue]")
                if download_file(urls['protocol'], protocol_path):
                    results["success"].append(f"{nct_id}_Protocol")
                    console.print(f"  [green]Protocol downloaded[/green]")
                else:
                    results["failed"].append(f"{nct_id}_Protocol")

        # Download SAP
        if 'sap' in urls:
            sap_path = SAPS_DIR / f"{nct_id}_SAP.pdf"
            if skip_existing and sap_path.exists():
                console.print(f"  [yellow]SAP exists, skipping[/yellow]")
                results["skipped"].append(f"{nct_id}_SAP")
            else:
                console.print(f"  [blue]Downloading SAP...[/blue]")
                if download_file(urls['sap'], sap_path):
                    results["success"].append(f"{nct_id}_SAP")
                    console.print(f"  [green]SAP downloaded[/green]")
                else:
                    results["failed"].append(f"{nct_id}_SAP")

    console.print(f"\n[bold]Download Summary:[/bold]")
    console.print(f"  [green]Downloaded: {len(results['success'])}[/green]")
    console.print(f"  [yellow]Skipped: {len(results['skipped'])}[/yellow]")
    console.print(f"  [red]Failed: {len(results['failed'])}[/red]")
    console.print(f"  [yellow]No docs available: {len(results['no_docs'])}[/yellow]")

    return results


if __name__ == "__main__":
    download_all_protocols(skip_existing=False)
