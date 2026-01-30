#!/usr/bin/env python3
"""
Download and Process Eval Set
=============================

Downloads Protocol+SAP pairs and extracts text for eval.

Usage:
    python download_eval_set.py --download    # Download PDFs
    python download_eval_set.py --extract     # Extract text from PDFs
    python download_eval_set.py --all         # Do both
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
PAIRS_FILE = DATA_DIR / "scraped_saps" / "protocol_sap_pairs.json"
PDF_DIR = DATA_DIR / "eval_pdfs"
TEXT_DIR = DATA_DIR / "eval_set"


def download_pdfs(limit: int = None):
    """Download PDFs from ClinicalTrials.gov."""
    with open(PAIRS_FILE) as f:
        pairs = json.load(f)

    if limit:
        pairs = pairs[:limit]

    PDF_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {len(pairs)} PDFs...")
    downloaded = 0

    for i, pair in enumerate(pairs, 1):
        nct_id = pair['nct_id']
        url = pair['url']

        pdf_path = PDF_DIR / f"{nct_id}.pdf"

        if pdf_path.exists():
            print(f"[{i}/{len(pairs)}] {nct_id}: already exists")
            downloaded += 1
            continue

        try:
            print(f"[{i}/{len(pairs)}] {nct_id}: downloading...", end=" ")
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            pdf_path.write_bytes(response.content)
            downloaded += 1
            print(f"OK ({len(response.content)//1024}KB)")

            time.sleep(0.5)
        except Exception as e:
            print(f"FAILED: {e}")

    print(f"\nDownloaded {downloaded}/{len(pairs)} PDFs to {PDF_DIR}")
    return downloaded


def extract_text():
    """Extract text from PDFs using PyPDF2."""
    try:
        import PyPDF2
    except ImportError:
        print("Installing PyPDF2...")
        os.system(f"{sys.executable} -m pip install PyPDF2")
        import PyPDF2

    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = list(PDF_DIR.glob("*.pdf"))
    print(f"Extracting text from {len(pdfs)} PDFs...")

    extracted = 0

    for i, pdf_path in enumerate(pdfs, 1):
        nct_id = pdf_path.stem
        txt_path = TEXT_DIR / f"{nct_id}_sap.txt"

        if txt_path.exists():
            print(f"[{i}/{len(pdfs)}] {nct_id}: already extracted")
            extracted += 1
            continue

        try:
            print(f"[{i}/{len(pdfs)}] {nct_id}: extracting...", end=" ")

            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text_parts = []

                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)

                full_text = "\n\n".join(text_parts)

            txt_path.write_text(full_text, encoding='utf-8')
            extracted += 1
            print(f"OK ({len(full_text)} chars)")

        except Exception as e:
            print(f"FAILED: {e}")

    print(f"\nExtracted {extracted}/{len(pdfs)} to {TEXT_DIR}")
    return extracted


def fetch_protocols():
    """Fetch protocol info from ClinicalTrials.gov API."""
    with open(PAIRS_FILE) as f:
        pairs = json.load(f)

    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching protocol info for {len(pairs)} trials...")
    fetched = 0

    for i, pair in enumerate(pairs, 1):
        nct_id = pair['nct_id']
        prot_path = TEXT_DIR / f"{nct_id}_protocol.txt"

        if prot_path.exists():
            print(f"[{i}/{len(pairs)}] {nct_id}: already fetched")
            fetched += 1
            continue

        try:
            print(f"[{i}/{len(pairs)}] {nct_id}: fetching...", end=" ")

            url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
            response = requests.get(url, params={'format': 'json'}, timeout=30)
            response.raise_for_status()

            data = response.json()
            protocol = data.get('protocolSection', {})

            # Format protocol info as text
            lines = []
            lines.append(f"STUDY IDENTIFICATION")
            lines.append(f"NCT ID: {nct_id}")

            id_mod = protocol.get('identificationModule', {})
            lines.append(f"Brief Title: {id_mod.get('briefTitle', '')}")
            lines.append(f"Official Title: {id_mod.get('officialTitle', '')}")

            sponsor = protocol.get('sponsorCollaboratorsModule', {}).get('leadSponsor', {})
            lines.append(f"Sponsor: {sponsor.get('name', '')}")

            status = protocol.get('statusModule', {})
            lines.append(f"\nSTUDY STATUS")
            lines.append(f"Overall Status: {status.get('overallStatus', '')}")
            lines.append(f"Start Date: {status.get('startDateStruct', {}).get('date', '')}")

            design = protocol.get('designModule', {})
            lines.append(f"\nSTUDY DESIGN")
            lines.append(f"Study Type: {design.get('studyType', '')}")
            lines.append(f"Phase: {design.get('phases', [])}")
            lines.append(f"Allocation: {design.get('designInfo', {}).get('allocation', '')}")
            lines.append(f"Masking: {design.get('designInfo', {}).get('maskingInfo', {}).get('masking', '')}")
            lines.append(f"Enrollment: {design.get('enrollmentInfo', {}).get('count', '')}")

            arms = protocol.get('armsInterventionsModule', {})
            lines.append(f"\nTREATMENT ARMS")
            for arm in arms.get('armGroups', []):
                lines.append(f"  {arm.get('label', '')}: {arm.get('description', '')[:100]}")

            outcomes = protocol.get('outcomesModule', {})
            lines.append(f"\nPRIMARY OUTCOMES")
            for out in outcomes.get('primaryOutcomes', []):
                lines.append(f"  {out.get('measure', '')}")
                lines.append(f"    Time Frame: {out.get('timeFrame', '')}")

            lines.append(f"\nSECONDARY OUTCOMES")
            for out in outcomes.get('secondaryOutcomes', [])[:10]:
                lines.append(f"  {out.get('measure', '')}")

            elig = protocol.get('eligibilityModule', {})
            lines.append(f"\nELIGIBILITY")
            lines.append(f"Sex: {elig.get('sex', '')}")
            lines.append(f"Minimum Age: {elig.get('minimumAge', '')}")
            lines.append(f"Maximum Age: {elig.get('maximumAge', '')}")
            lines.append(f"Criteria:\n{elig.get('eligibilityCriteria', '')[:2000]}")

            desc = protocol.get('descriptionModule', {})
            lines.append(f"\nSTUDY DESCRIPTION")
            lines.append(f"Brief Summary:\n{desc.get('briefSummary', '')}")

            full_text = "\n".join(lines)
            prot_path.write_text(full_text, encoding='utf-8')
            fetched += 1
            print(f"OK ({len(full_text)} chars)")

            time.sleep(0.3)

        except Exception as e:
            print(f"FAILED: {e}")

    print(f"\nFetched {fetched}/{len(pairs)} protocols to {TEXT_DIR}")
    return fetched


def create_summary():
    """Create summary of the eval set."""
    with open(PAIRS_FILE) as f:
        pairs = json.load(f)

    saps = list(TEXT_DIR.glob("*_sap.txt"))
    protocols = list(TEXT_DIR.glob("*_protocol.txt"))

    # Find complete pairs
    sap_ids = {p.stem.replace('_sap', '') for p in saps}
    prot_ids = {p.stem.replace('_protocol', '') for p in protocols}
    complete = sap_ids & prot_ids

    print(f"\n{'='*60}")
    print("EVAL SET SUMMARY")
    print(f"{'='*60}")
    print(f"Protocol+SAP pairs found: {len(pairs)}")
    print(f"SAPs extracted: {len(saps)}")
    print(f"Protocols fetched: {len(protocols)}")
    print(f"Complete pairs: {len(complete)}")
    print(f"\nLocation: {TEXT_DIR}")

    # Save list of complete pairs
    summary = {
        'total_pairs': len(complete),
        'nct_ids': sorted(complete),
    }
    with open(TEXT_DIR / 'eval_set_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    return len(complete)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Download and process eval set")
    parser.add_argument("--download", action="store_true", help="Download PDFs")
    parser.add_argument("--extract", action="store_true", help="Extract text from PDFs")
    parser.add_argument("--protocols", action="store_true", help="Fetch protocol info")
    parser.add_argument("--all", action="store_true", help="Do everything")
    parser.add_argument("--limit", type=int, help="Limit number of downloads")
    parser.add_argument("--summary", action="store_true", help="Show summary")

    args = parser.parse_args()

    if args.all or args.download:
        download_pdfs(limit=args.limit)

    if args.all or args.extract:
        extract_text()

    if args.all or args.protocols:
        fetch_protocols()

    if args.all or args.summary:
        create_summary()

    if not any([args.all, args.download, args.extract, args.protocols, args.summary]):
        parser.print_help()


if __name__ == "__main__":
    main()
