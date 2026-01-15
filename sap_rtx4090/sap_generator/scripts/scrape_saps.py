#!/usr/bin/env python3
"""
Scrape SAP and Protocol pairs from ClinicalTrials.gov
=====================================================

Finds oncology Phase 2/3 trials with publicly available SAP documents.

Usage:
    python scrape_saps.py --search          # Search for trials with SAPs
    python scrape_saps.py --download        # Download found SAPs
    python scrape_saps.py --search --download --limit 100
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

# ClinicalTrials.gov API v2
API_BASE = "https://clinicaltrials.gov/api/v2/studies"
DOCS_CDN = "https://cdn.clinicaltrials.gov/large-docs"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "scraped_saps"

# Search parameters for oncology trials
ONCOLOGY_CONDITIONS = [
    "cancer", "carcinoma", "lymphoma", "leukemia", "myeloma",
    "melanoma", "sarcoma", "tumor", "neoplasm", "oncology",
    "NSCLC", "SCLC", "breast cancer", "lung cancer", "colorectal cancer",
    "prostate cancer", "ovarian cancer", "pancreatic cancer"
]


@dataclass
class TrialInfo:
    """Information about a clinical trial."""
    nct_id: str
    title: str
    phase: str
    conditions: List[str]
    status: str
    has_sap: bool
    has_protocol: bool
    sap_url: Optional[str]
    protocol_url: Optional[str]
    sponsor: str
    enrollment: Optional[int]


# =============================================================================
# API FUNCTIONS
# =============================================================================

def search_oncology_trials(
    phases: List[str] = ["PHASE2", "PHASE3"],
    limit: int = 100,
    has_results: bool = True
) -> List[Dict]:
    """
    Search ClinicalTrials.gov for oncology trials.

    Args:
        phases: Phase filters (PHASE1, PHASE2, PHASE3, PHASE4)
        limit: Maximum number of trials to return
        has_results: Only return trials with results posted
    """
    trials = []
    page_size = 100
    page_token = None

    # Build query for oncology
    condition_query = " OR ".join(f'AREA[Condition]"{c}"' for c in ONCOLOGY_CONDITIONS[:5])

    params = {
        "format": "json",
        "pageSize": min(page_size, limit),
        "filter.overallStatus": "COMPLETED",
        "query.cond": "cancer OR carcinoma OR tumor OR lymphoma OR leukemia",
    }

    # Add phase filter
    if phases:
        params["filter.phase"] = ",".join(phases)

    print(f"Searching ClinicalTrials.gov for oncology Phase {phases} trials...")

    while len(trials) < limit:
        if page_token:
            params["pageToken"] = page_token

        try:
            response = requests.get(API_BASE, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            studies = data.get("studies", [])
            if not studies:
                break

            trials.extend(studies)
            print(f"  Found {len(trials)} trials so far...")

            # Get next page token
            page_token = data.get("nextPageToken")
            if not page_token:
                break

            # Rate limiting
            time.sleep(1.5)

        except Exception as e:
            print(f"  Error: {e}")
            break

    return trials[:limit]


def check_sap_availability(nct_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Check if SAP and Protocol documents are available for a trial.

    Returns:
        Tuple of (sap_url, protocol_url) or (None, None)
    """
    # Extract the folder ID (last 2 digits of NCT number)
    folder_id = nct_id[-2:]

    # Common document patterns
    doc_patterns = [
        f"{DOCS_CDN}/{folder_id}/{nct_id}/SAP_000.pdf",
        f"{DOCS_CDN}/{folder_id}/{nct_id}/SAP_001.pdf",
        f"{DOCS_CDN}/{folder_id}/{nct_id}/SAP_002.pdf",
        f"{DOCS_CDN}/{folder_id}/{nct_id}/Prot_SAP_000.pdf",
        f"{DOCS_CDN}/{folder_id}/{nct_id}/Prot_SAP_001.pdf",
        f"{DOCS_CDN}/{folder_id}/{nct_id}/Prot_000.pdf",
        f"{DOCS_CDN}/{folder_id}/{nct_id}/Prot_001.pdf",
    ]

    sap_url = None
    protocol_url = None

    for url in doc_patterns:
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                if "SAP" in url:
                    sap_url = url
                if "Prot" in url:
                    protocol_url = url
                if sap_url and protocol_url:
                    break
        except:
            continue

    return sap_url, protocol_url


def extract_trial_info(study: Dict) -> TrialInfo:
    """Extract relevant info from API response."""
    protocol = study.get("protocolSection", {})

    # Identification
    id_module = protocol.get("identificationModule", {})
    nct_id = id_module.get("nctId", "")
    title = id_module.get("briefTitle", "") or id_module.get("officialTitle", "")

    # Design
    design_module = protocol.get("designModule", {})
    phases = design_module.get("phases", [])
    phase = ", ".join(phases) if phases else "N/A"
    enrollment_info = design_module.get("enrollmentInfo", {})
    enrollment = enrollment_info.get("count")

    # Conditions
    conditions_module = protocol.get("conditionsModule", {})
    conditions = conditions_module.get("conditions", [])

    # Status
    status_module = protocol.get("statusModule", {})
    status = status_module.get("overallStatus", "")

    # Sponsor
    sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
    lead_sponsor = sponsor_module.get("leadSponsor", {})
    sponsor = lead_sponsor.get("name", "")

    return TrialInfo(
        nct_id=nct_id,
        title=title[:100],
        phase=phase,
        conditions=conditions[:3],
        status=status,
        has_sap=False,
        has_protocol=False,
        sap_url=None,
        protocol_url=None,
        sponsor=sponsor[:50],
        enrollment=enrollment
    )


def download_document(url: str, output_path: Path) -> bool:
    """Download a document from URL."""
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return True
    except Exception as e:
        print(f"    Error downloading: {e}")
        return False


# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def find_trials_with_saps(
    phases: List[str] = ["PHASE2", "PHASE3"],
    limit: int = 200,
    check_docs: bool = True
) -> List[TrialInfo]:
    """
    Find oncology trials that have SAP documents available.
    """
    # Search for trials
    studies = search_oncology_trials(phases=phases, limit=limit)
    print(f"\nFound {len(studies)} total trials")

    # Extract info and check for SAPs
    trials_with_saps = []

    print("\nChecking for SAP documents...")
    for i, study in enumerate(studies):
        info = extract_trial_info(study)

        if check_docs:
            print(f"  [{i+1}/{len(studies)}] {info.nct_id}...", end=" ")
            sap_url, protocol_url = check_sap_availability(info.nct_id)

            if sap_url:
                info.has_sap = True
                info.sap_url = sap_url
                print(f"SAP found!", end=" ")

            if protocol_url:
                info.has_protocol = True
                info.protocol_url = protocol_url
                print(f"Protocol found!", end=" ")

            if sap_url or protocol_url:
                trials_with_saps.append(info)
                print()
            else:
                print("No docs")

            # Rate limiting
            time.sleep(0.5)
        else:
            trials_with_saps.append(info)

    return trials_with_saps


def download_saps(trials: List[TrialInfo], output_dir: Path = OUTPUT_DIR) -> int:
    """Download SAP and protocol documents for trials."""
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0

    for trial in trials:
        if not trial.sap_url:
            continue

        print(f"\nDownloading {trial.nct_id}...")

        # Download SAP
        if trial.sap_url:
            sap_path = output_dir / f"{trial.nct_id}_sap.pdf"
            if download_document(trial.sap_url, sap_path):
                print(f"  SAP: {sap_path.name}")
                downloaded += 1

        # Download Protocol
        if trial.protocol_url:
            prot_path = output_dir / f"{trial.nct_id}_protocol.pdf"
            if download_document(trial.protocol_url, prot_path):
                print(f"  Protocol: {prot_path.name}")

        # Save metadata
        meta_path = output_dir / f"{trial.nct_id}_meta.json"
        with open(meta_path, 'w') as f:
            json.dump(asdict(trial), f, indent=2)

        time.sleep(1)

    return downloaded


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Scrape SAPs from ClinicalTrials.gov")
    parser.add_argument("--search", action="store_true", help="Search for trials with SAPs")
    parser.add_argument("--download", action="store_true", help="Download found SAPs")
    parser.add_argument("--limit", type=int, default=200, help="Max trials to search")
    parser.add_argument("--phases", type=str, default="PHASE2,PHASE3", help="Phase filter")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR), help="Output directory")
    parser.add_argument("--cache", type=str, help="Load/save search results to cache file")

    args = parser.parse_args()

    output_dir = Path(args.output)
    phases = args.phases.split(",")

    trials = []

    # Load from cache if available
    cache_path = Path(args.cache) if args.cache else output_dir / "search_cache.json"

    if args.search:
        print("="*60)
        print("SEARCHING FOR ONCOLOGY TRIALS WITH SAPs")
        print("="*60)

        trials = find_trials_with_saps(phases=phases, limit=args.limit)

        # Save cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump([asdict(t) for t in trials], f, indent=2)

        print(f"\n{'='*60}")
        print(f"RESULTS: Found {len(trials)} trials with SAP documents")
        print(f"{'='*60}")

        for t in trials[:20]:
            print(f"  {t.nct_id}: {t.title[:50]}... [{t.phase}]")

        if len(trials) > 20:
            print(f"  ... and {len(trials) - 20} more")

        print(f"\nCache saved to: {cache_path}")

    elif cache_path.exists():
        # Load from cache
        with open(cache_path) as f:
            data = json.load(f)
            trials = [TrialInfo(**d) for d in data]
        print(f"Loaded {len(trials)} trials from cache")

    if args.download and trials:
        print(f"\n{'='*60}")
        print("DOWNLOADING SAP DOCUMENTS")
        print(f"{'='*60}")

        downloaded = download_saps(trials, output_dir)

        print(f"\n{'='*60}")
        print(f"Downloaded {downloaded} SAP documents to {output_dir}")
        print(f"{'='*60}")

    if not args.search and not args.download:
        parser.print_help()


if __name__ == "__main__":
    main()
