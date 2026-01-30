#!/usr/bin/env python3
"""
Download Specialized SAPs for RAG Training
==========================================

Downloads immunotherapy, interim analysis, and PRO SAPs from ClinicalTrials.gov
to improve RAG coverage for specialized trial types.
"""

import os
import sys
import requests
from pathlib import Path
from typing import Dict, List
import time

# SAP sources organized by category
SPECIALIZED_SAPS = {
    "immunotherapy": [
        {
            "nct_id": "NCT02743819",
            "url": "https://cdn.clinicaltrials.gov/large-docs/19/NCT02743819/Prot_SAP_000.pdf",
            "drug": "Pembrolizumab + Ipilimumab",
            "indication": "Advanced Cancer",
            "features": ["checkpoint_inhibitor", "combination_immunotherapy"]
        },
        {
            "nct_id": "NCT03117309",
            "url": "https://cdn.clinicaltrials.gov/large-docs/09/NCT03117309/Prot_SAP_000.pdf",
            "drug": "Nivolumab",
            "indication": "Various",
            "features": ["checkpoint_inhibitor", "front_line"]
        },
        {
            "nct_id": "NCT04008030",
            "url": "https://cdn.clinicaltrials.gov/large-docs/30/NCT04008030/Prot_SAP_000.pdf",
            "drug": "Nivolumab ± Ipilimumab",
            "indication": "Colorectal Cancer dMMR/MSI-H",
            "features": ["checkpoint_inhibitor", "biomarker_selected", "phase3"]
        },
        {
            "nct_id": "NCT02864251",
            "url": "https://cdn.clinicaltrials.gov/large-docs/51/NCT02864251/Prot_SAP_000.pdf",
            "drug": "Nivolumab",
            "indication": "NSCLC",
            "features": ["checkpoint_inhibitor", "randomized", "phase3"]
        },
        {
            "nct_id": "NCT03906071",
            "url": "https://cdn.clinicaltrials.gov/large-docs/71/NCT03906071/Prot_SAP_000.pdf",
            "drug": "Sitravatinib + Nivolumab",
            "indication": "NSCLC",
            "features": ["checkpoint_inhibitor", "combination", "phase3", "os_endpoint"]
        },
        {
            "nct_id": "NCT03502330",
            "url": "https://cdn.clinicaltrials.gov/large-docs/30/NCT03502330/Prot_SAP_000.pdf",
            "drug": "APX005M + Nivolumab + Cabiralizumab",
            "indication": "Advanced Melanoma",
            "features": ["checkpoint_inhibitor", "triple_combination"]
        },
        {
            "nct_id": "NCT03377023",
            "url": "https://cdn.clinicaltrials.gov/large-docs/23/NCT03377023/Prot_SAP_000.pdf",
            "drug": "Ipilimumab/Nivolumab + Nintedanib",
            "indication": "Various Solid Tumors",
            "features": ["checkpoint_inhibitor", "tki_combination"]
        },
        {
            "nct_id": "NCT03836066",
            "url": "https://cdn.clinicaltrials.gov/large-docs/66/NCT03836066/Prot_SAP_000.pdf",
            "drug": "TELMA Immunotherapy",
            "indication": "NSCLC",
            "features": ["immunotherapy", "lung_cancer"]
        },
        {
            "nct_id": "NCT02362594",
            "url": "https://cdn.clinicaltrials.gov/large-docs/94/NCT02362594/Prot_SAP_000.pdf",
            "drug": "Pembrolizumab",
            "indication": "Melanoma",
            "features": ["checkpoint_inhibitor", "randomized", "stratified"]
        },
        {
            "nct_id": "NCT02060188",
            "url": "https://cdn.clinicaltrials.gov/large-docs/88/NCT02060188/Prot_SAP_000.pdf",
            "drug": "Nivolumab",
            "indication": "Various",
            "features": ["checkpoint_inhibitor", "phase2"]
        },
    ],
    "interim_analysis": [
        {
            "nct_id": "NCT03298451",
            "url": "https://cdn.clinicaltrials.gov/large-docs/51/NCT03298451/SAP_017.pdf",
            "study": "HIMALAYA",
            "drug": "Durvalumab + Tremelimumab",
            "indication": "HCC",
            "features": ["os_primary", "two_interim_analyses", "lan_demets", "obrien_fleming"]
        },
        {
            "nct_id": "NCT02231749",
            "url": "https://cdn.clinicaltrials.gov/large-docs/49/NCT02231749/SAP_000.pdf",
            "drug": "BMS Oncology",
            "indication": "Various",
            "features": ["os_interim", "stratified_logrank", "dmc_oversight"]
        },
        {
            "nct_id": "NCT01772472",
            "url": "https://cdn.clinicaltrials.gov/large-docs/72/NCT01772472/SAP_003.pdf",
            "drug": "Trastuzumab Emtansine",
            "indication": "Breast Cancer",
            "features": ["two_os_interim", "final_os", "lan_demets", "obrien_fleming", "12year_followup"]
        },
        {
            "nct_id": "NCT02763579",
            "url": "https://cdn.clinicaltrials.gov/large-docs/79/NCT02763579/Prot_SAP_000.pdf",
            "drug": "Atezolizumab",
            "indication": "Various",
            "features": ["delayed_effect_acknowledged", "os_interim", "event_ratio_timing"]
        },
        {
            "nct_id": "NCT02395172",
            "url": "https://cdn.clinicaltrials.gov/large-docs/72/NCT02395172/SAP_000.pdf",
            "drug": "Avelumab",
            "indication": "NSCLC",
            "features": ["hierarchical_testing", "lan_demets", "obrien_fleming", "os_superiority"]
        },
        {
            "nct_id": "NCT03822351",
            "url": "https://cdn.clinicaltrials.gov/large-docs/51/NCT03822351/SAP_003.pdf",
            "drug": "MedImmune/AstraZeneca",
            "indication": "Various",
            "features": ["os_interim", "phase3"]
        },
        {
            "nct_id": "NCT02034110",
            "url": "https://cdn.clinicaltrials.gov/large-docs/10/NCT02034110/SAP_001.pdf",
            "drug": "Various",
            "indication": "Oncology",
            "features": ["interim_analysis", "phase3"]
        },
        {
            "nct_id": "NCT01339910",
            "url": "https://cdn.clinicaltrials.gov/large-docs/10/NCT01339910/SAP_001.pdf",
            "study": "BMT CTN 0901",
            "drug": "Stem Cell Transplant",
            "indication": "AML/MDS",
            "features": ["os_primary", "interim_analysis", "phase3"]
        },
    ],
    "pro_endpoints": [
        {
            "nct_id": "NCT03089125",
            "url": "https://cdn.clinicaltrials.gov/large-docs/25/NCT03089125/Prot_SAP_000.pdf",
            "focus": "Dyspnea Intervention",
            "indication": "Advanced Lung Cancer",
            "features": ["patient_reported_outcomes", "qol", "symptom_management"]
        },
        {
            "nct_id": "NCT03494166",
            "url": "https://cdn.clinicaltrials.gov/large-docs/66/NCT03494166/Prot_SAP_001.pdf",
            "focus": "Post-Chemotherapy Symptom Management",
            "indication": "Solid Tumors",
            "features": ["patient_reported_outcomes", "symptom_burden"]
        },
        {
            "nct_id": "NCT02054741",
            "url": "https://cdn.clinicaltrials.gov/large-docs/41/NCT02054741/Prot_SAP_000.pdf",
            "focus": "Geriatric Assessment",
            "indication": "Various Cancers",
            "features": ["patient_reported_toxicity", "functional_status", "qol"]
        },
        {
            "nct_id": "NCT05775289",
            "url": "https://cdn.clinicaltrials.gov/large-docs/89/NCT05775289/Prot_SAP_000.pdf",
            "drug": "Tobemstomig (Roche)",
            "indication": "NSCLC",
            "features": ["hrqol", "pfs", "os", "orr"]
        },
        {
            "nct_id": "NCT03566810",
            "url": "https://cdn.clinicaltrials.gov/large-docs/10/NCT03566810/SAP_001.pdf",
            "focus": "TTF Endpoint",
            "indication": "Various",
            "features": ["ttf", "time_to_treatment_failure", "china_regulatory"]
        },
    ],
    "methodology": [
        {
            "name": "fleming_harrington_stanford",
            "url": "https://med.stanford.edu/content/dam/sm/dbds/documents/biostats-workshop/Methods-for-tackling-nonPH-2019-SBR-preprint-.pdf",
            "topic": "Fleming-Harrington Weighted Log-Rank Tests",
            "features": ["weighted_logrank", "non_proportional_hazards", "delayed_effect"]
        },
        {
            "name": "weighted_logrank_sas",
            "url": "https://support.sas.com/resources/papers/proceedings20/5062-2020.pdf",
            "topic": "Combination Weighted Log-Rank Tests",
            "features": ["weighted_logrank", "maxcombo", "implementation"]
        },
        {
            "name": "nph_asa_2018",
            "url": "https://ww2.amstat.org/meetings/proceedings/2018/data/assets/pdf/867098.pdf",
            "topic": "Non-Proportional Hazards in Immunotherapy",
            "features": ["non_proportional_hazards", "immunotherapy", "delayed_effect"]
        },
        {
            "name": "weighted_logrank_properties",
            "url": "https://arxiv.org/pdf/1806.11294",
            "topic": "Properties of Weighted Log-Rank Test",
            "features": ["weighted_logrank", "power_analysis", "clinical_trial_design"]
        },
    ]
}


def download_file(url: str, output_path: Path, max_retries: int = 3) -> bool:
    """Download a file with retries."""
    for attempt in range(max_retries):
        try:
            print(f"  Downloading: {url[:80]}...")
            response = requests.get(url, timeout=60, stream=True)
            response.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"  ✓ Saved to: {output_path}")
            return True

        except Exception as e:
            print(f"  ✗ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)

    return False


def download_all_saps(output_dir: Path) -> Dict[str, List[Path]]:
    """Download all specialized SAPs."""
    downloaded = {category: [] for category in SPECIALIZED_SAPS.keys()}

    for category, saps in SPECIALIZED_SAPS.items():
        print(f"\n{'='*60}")
        print(f"Category: {category.upper()}")
        print(f"{'='*60}")

        category_dir = output_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)

        for sap in saps:
            # Determine filename
            if "nct_id" in sap:
                filename = f"{sap['nct_id']}_SAP.pdf"
            else:
                filename = f"{sap['name']}.pdf"

            output_path = category_dir / filename

            # Skip if already downloaded
            if output_path.exists():
                print(f"  ⊘ Already exists: {filename}")
                downloaded[category].append(output_path)
                continue

            if download_file(sap["url"], output_path):
                downloaded[category].append(output_path)

            # Be nice to the server
            time.sleep(1)

    return downloaded


def print_summary(downloaded: Dict[str, List[Path]]):
    """Print download summary."""
    print(f"\n{'='*60}")
    print("DOWNLOAD SUMMARY")
    print(f"{'='*60}")

    total = 0
    for category, files in downloaded.items():
        print(f"  {category}: {len(files)} files")
        total += len(files)

    print(f"\n  TOTAL: {total} files downloaded")


if __name__ == "__main__":
    # Default output directory
    script_dir = Path(__file__).parent
    default_output = script_dir.parent / "rag_training_data" / "specialized_saps"

    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else default_output

    print(f"Downloading specialized SAPs to: {output_dir}")

    downloaded = download_all_saps(output_dir)
    print_summary(downloaded)

    print(f"\nNext step: Run parse_specialized_saps.py to extract sections")
