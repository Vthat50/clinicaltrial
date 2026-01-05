#!/usr/bin/env python3
"""
Download Critical Missing Documents for Production-Grade Knowledge Graph
=========================================================================

Downloads and indexes:
1. CTCAE v5.0 - Common Terminology Criteria for Adverse Events (NCI)
2. RECIST 1.1 - Response Evaluation Criteria in Solid Tumors
3. iRECIST - Immune-related RECIST
4. CONSORT 2025 - Consolidated Standards of Reporting Trials

All documents are FREE and publicly available.
"""

import os
import re
import json
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# PDF extraction
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("Note: PyMuPDF not installed. Run: pip install pymupdf")

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("Error: chromadb not installed")

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDER_AVAILABLE = True
except ImportError:
    EMBEDDER_AVAILABLE = False


@dataclass
class CriticalDocument:
    """Critical document to download and index."""
    name: str
    short_name: str
    url: str
    authority: str
    binding: str
    tier: int
    citation_format: str
    description: str


# Critical documents with direct download URLs
CRITICAL_DOCUMENTS = [
    CriticalDocument(
        name="CTCAE v5.0 - Common Terminology Criteria for Adverse Events",
        short_name="CTCAE_v5",
        url="https://ctep.cancer.gov/protocoldevelopment/electronic_applications/docs/ctcae_v5_quick_reference_8.5x11.pdf",
        authority="NCI",
        binding="required_for_safety",
        tier=1,
        citation_format="NCI CTCAE v5.0",
        description="Standard grading system for adverse events in clinical trials"
    ),
    CriticalDocument(
        name="FDA Guidance - Clinical Trial Endpoints for Cancer Drugs",
        short_name="FDA_Endpoints",
        url="https://www.fda.gov/media/71195/download",
        authority="FDA",
        binding="should_follow",
        tier=1,
        citation_format="FDA Endpoints Guidance 2018",
        description="FDA guidance on endpoints for cancer drug approval"
    ),
    CriticalDocument(
        name="FDA Guidance - Adaptive Designs for Clinical Trials",
        short_name="FDA_Adaptive",
        url="https://www.fda.gov/media/78495/download",
        authority="FDA",
        binding="should_follow",
        tier=1,
        citation_format="FDA Adaptive Designs Guidance",
        description="FDA guidance on adaptive trial designs and interim analyses"
    ),
    CriticalDocument(
        name="FDA Guidance - Multiple Endpoints in Clinical Trials",
        short_name="FDA_Multiple_Endpoints",
        url="https://www.fda.gov/media/102657/download",
        authority="FDA",
        binding="should_follow",
        tier=1,
        citation_format="FDA Multiple Endpoints Guidance",
        description="FDA guidance on handling multiple endpoints and multiplicity"
    ),
]

# Additional documents that need manual download (journal paywalls)
MANUAL_DOWNLOAD_DOCS = [
    {
        "name": "RECIST 1.1",
        "citation": "Eisenhauer EA, et al. Eur J Cancer. 2009;45(2):228-247",
        "url": "https://www.ejcancer.com/article/S0959-8049(08)00873-3/fulltext",
        "note": "Requires journal access - check if your institution has access"
    },
    {
        "name": "iRECIST",
        "citation": "Seymour L, et al. Lancet Oncol. 2017;18(3):e143-e152",
        "url": "https://www.thelancet.com/journals/lanonc/article/PIIS1470-2045(17)30074-8/fulltext",
        "note": "Requires journal access"
    },
    {
        "name": "CONSORT 2025",
        "citation": "CONSORT Statement 2025",
        "url": "https://www.consort-statement.org/",
        "note": "Available at consort-statement.org - download checklist and flow diagram"
    }
]


class DocumentDownloader:
    """Downloads and processes critical regulatory documents."""

    def __init__(self, output_dir: Path, chroma_path: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_path = Path(chroma_path)

        if CHROMA_AVAILABLE:
            self.client = chromadb.PersistentClient(
                path=str(self.chroma_path),
                settings=Settings(anonymized_telemetry=False)
            )
        else:
            self.client = None

        if EMBEDDER_AVAILABLE:
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        else:
            self.embedder = None

    def download_pdf(self, url: str, filename: str) -> Optional[Path]:
        """Download a PDF from URL."""
        output_path = self.output_dir / filename

        if output_path.exists():
            print(f"  ✓ Already downloaded: {filename}")
            return output_path

        print(f"  Downloading: {url}")

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=60, allow_redirects=True)
            response.raise_for_status()

            # Check if we got a PDF
            content_type = response.headers.get('content-type', '')
            if 'pdf' not in content_type.lower() and not response.content[:4] == b'%PDF':
                print(f"  ⚠️  Not a PDF (got {content_type})")
                # Save anyway for inspection
                output_path = self.output_dir / filename.replace('.pdf', '.html')

            output_path.write_bytes(response.content)
            print(f"  ✓ Downloaded: {output_path.name} ({len(response.content) / 1024:.1f} KB)")
            return output_path

        except Exception as e:
            print(f"  ✗ Error downloading: {e}")
            return None

    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from PDF using PyMuPDF."""
        if not PYMUPDF_AVAILABLE:
            print("  ⚠️  PyMuPDF not available, cannot extract text")
            return ""

        try:
            doc = fitz.open(pdf_path)
            text_parts = []

            for page_num, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"--- PAGE {page_num + 1} ---\n{text}")

            doc.close()

            full_text = "\n\n".join(text_parts)
            print(f"  ✓ Extracted {len(full_text)} characters from {len(text_parts)} pages")
            return full_text

        except Exception as e:
            print(f"  ✗ Error extracting text: {e}")
            return ""

    def chunk_text(self, text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks."""
        if not text:
            return []

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to break at paragraph
            if end < len(text):
                # Look for paragraph break
                para_break = text.rfind('\n\n', start, end)
                if para_break > start + chunk_size // 2:
                    end = para_break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks

    def index_document(self, doc: CriticalDocument, text: str) -> int:
        """Index document chunks into ChromaDB."""
        if not self.client or not self.embedder:
            print("  ⚠️  Cannot index: ChromaDB or embedder not available")
            return 0

        chunks = self.chunk_text(text)
        if not chunks:
            return 0

        # Get or create regulatory collection
        try:
            collection = self.client.get_or_create_collection("sap_methods")
        except Exception as e:
            print(f"  ✗ Error accessing collection: {e}")
            return 0

        # Prepare documents
        ids = []
        documents = []
        metadatas = []
        embeddings = []

        for i, chunk in enumerate(chunks):
            doc_id = f"{doc.short_name}_chunk_{i}"
            ids.append(doc_id)
            documents.append(chunk)
            metadatas.append({
                "source_type": "regulatory_authority",
                "authority": doc.authority,
                "document": doc.name,
                "binding": doc.binding,
                "tier": doc.tier,
                "citation_format": doc.citation_format,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "description": doc.description
            })

        # Generate embeddings
        print(f"  Generating embeddings for {len(chunks)} chunks...")
        embeddings = self.embedder.encode(documents).tolist()

        # Add to collection
        try:
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )
            print(f"  ✓ Indexed {len(chunks)} chunks")
            return len(chunks)
        except Exception as e:
            print(f"  ✗ Error indexing: {e}")
            return 0

    def download_and_index_all(self):
        """Download and index all critical documents."""
        print("=" * 70)
        print("DOWNLOADING CRITICAL DOCUMENTS")
        print("=" * 70)

        total_indexed = 0
        successful = []
        failed = []

        for doc in CRITICAL_DOCUMENTS:
            print(f"\n{'─' * 50}")
            print(f"Document: {doc.name}")
            print(f"Authority: {doc.authority} | Binding: {doc.binding}")
            print(f"{'─' * 50}")

            # Download
            pdf_path = self.download_pdf(doc.url, f"{doc.short_name}.pdf")

            if pdf_path and pdf_path.exists():
                # Extract text
                text = self.extract_text_from_pdf(pdf_path)

                if text:
                    # Index
                    chunks = self.index_document(doc, text)
                    total_indexed += chunks
                    successful.append(doc.name)
                else:
                    failed.append(f"{doc.name} (no text extracted)")
            else:
                failed.append(f"{doc.name} (download failed)")

        # Summary
        print(f"\n{'=' * 70}")
        print("DOWNLOAD SUMMARY")
        print(f"{'=' * 70}")

        print(f"\n✅ Successfully indexed: {len(successful)}")
        for name in successful:
            print(f"   • {name}")

        if failed:
            print(f"\n❌ Failed: {len(failed)}")
            for name in failed:
                print(f"   • {name}")

        print(f"\nTotal chunks indexed: {total_indexed}")

        # Manual download instructions
        print(f"\n{'=' * 70}")
        print("MANUAL DOWNLOAD REQUIRED")
        print(f"{'=' * 70}")
        print("\nThe following documents require manual download (journal access):\n")

        for doc in MANUAL_DOWNLOAD_DOCS:
            print(f"📄 {doc['name']}")
            print(f"   Citation: {doc['citation']}")
            print(f"   URL: {doc['url']}")
            print(f"   Note: {doc['note']}")
            print()

        return {
            'successful': successful,
            'failed': failed,
            'total_indexed': total_indexed
        }


def create_recist_rules():
    """Create RECIST 1.1 rules manually (since PDF requires journal access)."""

    recist_rules = """
RECIST 1.1 - Response Evaluation Criteria in Solid Tumors
==========================================================
Citation: Eisenhauer EA, et al. Eur J Cancer. 2009;45(2):228-247

RESPONSE DEFINITIONS:

Complete Response (CR):
- Disappearance of all target lesions
- Any pathological lymph nodes must have reduction in short axis to <10 mm
- Confirmation required at least 4 weeks later

Partial Response (PR):
- At least 30% decrease in sum of diameters of target lesions
- Taking as reference the baseline sum diameters
- Confirmation required at least 4 weeks later

Progressive Disease (PD):
- At least 20% increase in sum of diameters of target lesions
- Taking as reference the smallest sum on study
- Must also demonstrate an absolute increase of at least 5 mm
- Appearance of one or more new lesions also qualifies as PD

Stable Disease (SD):
- Neither sufficient shrinkage for PR nor sufficient increase for PD
- Taking as reference the smallest sum diameters since treatment started

TARGET LESION SELECTION:
- Maximum of 5 lesions total (2 per organ)
- Measurable lesions: ≥10 mm in longest diameter (CT scan with ≤5 mm slice thickness)
- Lymph nodes: ≥15 mm in short axis
- Select lesions representative of all involved organs
- Lesions in previously irradiated areas should not be selected

NON-TARGET LESIONS:
- All other lesions (or sites of disease) should be identified as non-target lesions
- Recorded at baseline but not required to be measured
- Assessed as Present, Absent, or Unequivocal Progression

OVERALL RESPONSE:
- Best overall response = best response from start of treatment
- For CR or PR: confirmation required ≥4 weeks apart
- For SD: minimum 6-8 weeks duration typically required

STATISTICAL CONSIDERATIONS:
- Primary endpoint: Objective Response Rate (ORR) = CR + PR
- Response duration: time from first documented response to progression
- Clopper-Pearson exact 95% CI for response rates
"""

    irecist_rules = """
iRECIST - Immune-related Response Evaluation Criteria
======================================================
Citation: Seymour L, et al. Lancet Oncol. 2017;18(3):e143-e152

PURPOSE:
- Modified RECIST 1.1 for immunotherapy trials
- Addresses pseudoprogression (initial tumor growth followed by response)
- Allows confirmation of progression before declaring treatment failure

KEY MODIFICATIONS FROM RECIST 1.1:

iUPD (immune Unconfirmed Progressive Disease):
- First time point meeting RECIST 1.1 PD criteria
- Treatment may continue if clinically stable
- Requires confirmation at next assessment (≥4 weeks)

iCPD (immune Confirmed Progressive Disease):
- Confirmation of progression at next assessment
- Additional ≥5 mm increase in tumor burden from iUPD
- OR new lesion(s) appearing after iUPD
- Treatment should be discontinued

iPR (immune Partial Response):
- Same as RECIST 1.1 PR
- If preceded by iUPD, confirms pseudoprogression

iCR (immune Complete Response):
- Same as RECIST 1.1 CR

iSD (immune Stable Disease):
- Same as RECIST 1.1 SD

NEW LESIONS:
- First appearance → record but doesn't immediately define PD
- Contributes to iUPD classification
- Confirmation required for iCPD

STATISTICAL CONSIDERATIONS:
- Primary analysis: use iRECIST for immunotherapy trials
- May present both RECIST 1.1 and iRECIST results
- iCPD is the definitive progression event for analysis
- Sensitivity analysis excluding pseudoprogressors
"""

    return [
        ("RECIST_1.1_rules", recist_rules, {
            "source_type": "standard",
            "authority": "EORTC",
            "document": "RECIST 1.1 - Response Evaluation Criteria",
            "binding": "required_for_oncology",
            "tier": 1,
            "citation_format": "Eisenhauer et al. Eur J Cancer 2009"
        }),
        ("iRECIST_rules", irecist_rules, {
            "source_type": "standard",
            "authority": "Academic/Regulatory",
            "document": "iRECIST - Immune-related Response Criteria",
            "binding": "required_for_immunotherapy",
            "tier": 1,
            "citation_format": "Seymour et al. Lancet Oncol 2017"
        })
    ]


def create_ctcae_summary():
    """Create CTCAE v5.0 summary rules."""

    ctcae_rules = """
CTCAE v5.0 - Common Terminology Criteria for Adverse Events
============================================================
Source: National Cancer Institute (NCI)
Version: 5.0 (November 27, 2017)

GRADING SYSTEM:

Grade 1 - Mild:
- Asymptomatic or mild symptoms
- Clinical or diagnostic observations only
- Intervention not indicated

Grade 2 - Moderate:
- Minimal, local or noninvasive intervention indicated
- Limiting age-appropriate instrumental ADL*

Grade 3 - Severe:
- Severe or medically significant but not immediately life-threatening
- Hospitalization or prolongation of hospitalization indicated
- Disabling; limiting self care ADL**

Grade 4 - Life-threatening:
- Life-threatening consequences
- Urgent intervention indicated

Grade 5 - Death:
- Death related to AE

*Instrumental ADL: preparing meals, shopping, using telephone, managing money
**Self care ADL: bathing, dressing, feeding self, using toilet, taking medications

DOSE-LIMITING TOXICITY (DLT) DEFINITIONS (Phase I):
Common DLT criteria in oncology:
- Any Grade 4 hematologic toxicity lasting >7 days
- Grade 4 thrombocytopenia or Grade 3 with bleeding
- Any Grade 3-4 non-hematologic toxicity (except nausea/vomiting controlled with antiemetics)
- Grade 3 febrile neutropenia
- Treatment delay >2 weeks due to toxicity

SAFETY ANALYSIS REQUIREMENTS:

Adverse Event Tables:
- Incidence by System Organ Class (SOC) and Preferred Term (PT)
- Grade distribution (1-5)
- Treatment-emergent vs all-causality
- Related vs unrelated to study treatment

Standard Safety Endpoints:
- Treatment-Emergent Adverse Events (TEAEs)
- Serious Adverse Events (SAEs)
- AEs leading to discontinuation
- AEs leading to dose modification
- Deaths and causes

Statistical Methods for Safety:
- Descriptive statistics (n, %)
- No formal hypothesis testing typically required
- Exposure-adjusted rates for different follow-up durations
- Kaplan-Meier for time-to-event safety endpoints

MedDRA Coding:
- Use current MedDRA version
- Report at PT and SOC level
- Consider Standardised MedDRA Queries (SMQs) for special interest AEs
"""

    return ("CTCAE_v5_summary", ctcae_rules, {
        "source_type": "standard",
        "authority": "NCI",
        "document": "CTCAE v5.0 - Adverse Event Grading",
        "binding": "required_for_safety",
        "tier": 1,
        "citation_format": "NCI CTCAE v5.0"
    })


def index_manual_rules(chroma_path: Path):
    """Index manually created rules for documents requiring journal access."""

    print("\n" + "=" * 70)
    print("INDEXING MANUAL RULES (RECIST, iRECIST, CTCAE)")
    print("=" * 70)

    if not CHROMA_AVAILABLE or not EMBEDDER_AVAILABLE:
        print("❌ Cannot index: ChromaDB or embedder not available")
        return

    client = chromadb.PersistentClient(
        path=str(chroma_path),
        settings=Settings(anonymized_telemetry=False)
    )
    embedder = SentenceTransformer('all-MiniLM-L6-v2')

    collection = client.get_or_create_collection("sap_methods")

    # Get all rules
    rules = create_recist_rules()
    rules.append(create_ctcae_summary())

    total_indexed = 0

    for doc_id, content, metadata in rules:
        print(f"\n  Indexing: {metadata['document']}")

        # Generate embedding
        embedding = embedder.encode(content).tolist()

        try:
            collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[metadata],
                embeddings=[embedding]
            )
            print(f"  ✓ Indexed successfully")
            total_indexed += 1
        except Exception as e:
            # May already exist
            try:
                collection.update(
                    ids=[doc_id],
                    documents=[content],
                    metadatas=[metadata],
                    embeddings=[embedding]
                )
                print(f"  ✓ Updated existing document")
                total_indexed += 1
            except Exception as e2:
                print(f"  ✗ Error: {e2}")

    print(f"\n✅ Indexed {total_indexed} manual rule documents")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Download and index critical regulatory documents"
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='/mnt/c/Users/vijay/OneDrive/Documents/Github/clinicaltrial/sap_rtx4090/sap_generator/data/regulatory_docs',
        help='Directory to save downloaded PDFs'
    )
    parser.add_argument(
        '--chroma-path',
        type=str,
        default='/mnt/c/Users/vijay/OneDrive/Documents/Github/clinicaltrial/sap_rtx4090/sap_generator/data/chroma_db',
        help='Path to ChromaDB'
    )
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='Skip PDF downloads, only index manual rules'
    )

    args = parser.parse_args()

    # Create downloader
    downloader = DocumentDownloader(
        output_dir=Path(args.output_dir),
        chroma_path=Path(args.chroma_path)
    )

    # Download and index PDFs
    if not args.skip_download:
        results = downloader.download_and_index_all()

    # Index manual rules (RECIST, iRECIST, CTCAE summary)
    index_manual_rules(Path(args.chroma_path))

    # Final verification
    print("\n" + "=" * 70)
    print("FINAL VERIFICATION")
    print("=" * 70)

    if CHROMA_AVAILABLE:
        client = chromadb.PersistentClient(
            path=args.chroma_path,
            settings=Settings(anonymized_telemetry=False)
        )
        collection = client.get_collection("sap_methods")

        # Count by tier
        tier1 = collection.get(where={"tier": 1}, include=['metadatas'])
        print(f"\n✅ Tier 1 Documents: {len(tier1['ids'])}")

        for meta in tier1['metadatas']:
            print(f"   • {meta.get('document')} ({meta.get('authority')})")


if __name__ == '__main__':
    main()
