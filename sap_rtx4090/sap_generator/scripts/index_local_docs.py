#!/usr/bin/env python3
"""
Index Local Critical Documents
==============================

Indexes RECIST, CONSORT, and CTCAE from local PDF files.
"""

import re
from pathlib import Path
from typing import List, Dict, Any

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: Install PyMuPDF: pip install pymupdf")
    exit(1)

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


# Document configurations
DOCUMENTS = {
    "RECIST": {
        "path": "/mnt/c/Users/vijay/Downloads/RECISTGuidelines.pdf",
        "name": "RECIST 1.1 - Response Evaluation Criteria in Solid Tumors",
        "short_name": "RECIST_1.1",
        "authority": "EORTC",
        "binding": "required_for_oncology",
        "tier": 1,
        "citation_format": "Eisenhauer et al. Eur J Cancer 2009",
        "description": "Standard response criteria for solid tumors"
    },
    "CONSORT": {
        "path": "/mnt/c/Users/vijay/Downloads/jama_hopewell_2025_sc_250003_1744230151.85133.pdf",
        "name": "CONSORT 2025 - Consolidated Standards of Reporting Trials",
        "short_name": "CONSORT_2025",
        "authority": "CONSORT",
        "binding": "required_for_reporting",
        "tier": 1,
        "citation_format": "Hopewell et al. JAMA 2025",
        "description": "Updated reporting guidelines for randomized trials"
    },
    "CTCAE": {
        "path": "/mnt/c/Users/vijay/Downloads/CTCAE_v5_Quick_Reference_5x7.pdf",
        "name": "CTCAE v5.0 - Common Terminology Criteria for Adverse Events",
        "short_name": "CTCAE_v5",
        "authority": "NCI",
        "binding": "required_for_safety",
        "tier": 1,
        "citation_format": "NCI CTCAE v5.0",
        "description": "Standard grading system for adverse events"
    }
}


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF."""
    path = Path(pdf_path)
    if not path.exists():
        print(f"  ✗ File not found: {pdf_path}")
        return ""

    try:
        doc = fitz.open(path)
        text_parts = []

        for page_num, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                text_parts.append(f"--- PAGE {page_num + 1} ---\n{text}")

        doc.close()

        full_text = "\n\n".join(text_parts)
        print(f"  ✓ Extracted {len(full_text):,} characters from {len(text_parts)} pages")
        return full_text

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return ""


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks."""
    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end < len(text):
            # Try to break at paragraph
            para_break = text.rfind('\n\n', start, end)
            if para_break > start + chunk_size // 2:
                end = para_break

        chunk = text[start:end].strip()
        if chunk and len(chunk) > 100:
            chunks.append(chunk)

        start = end - overlap

    return chunks


def index_document(client, embedder, doc_key: str, doc_config: Dict) -> int:
    """Index a single document into ChromaDB."""
    print(f"\n{'─' * 50}")
    print(f"Document: {doc_config['name']}")
    print(f"{'─' * 50}")

    # Extract text
    text = extract_text_from_pdf(doc_config['path'])
    if not text:
        return 0

    # Chunk text
    chunks = chunk_text(text)
    print(f"  Created {len(chunks)} chunks")

    if not chunks:
        return 0

    # Get collection
    collection = client.get_or_create_collection("sap_methods")

    # Prepare data
    ids = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        doc_id = f"{doc_config['short_name']}_chunk_{i:03d}"
        ids.append(doc_id)
        documents.append(chunk)
        metadatas.append({
            "source_type": "standard",
            "authority": doc_config['authority'],
            "document": doc_config['name'],
            "binding": doc_config['binding'],
            "tier": doc_config['tier'],
            "citation_format": doc_config['citation_format'],
            "description": doc_config['description'],
            "chunk_index": i,
            "total_chunks": len(chunks)
        })

    # Generate embeddings
    print(f"  Generating embeddings...")
    embeddings = embedder.encode(documents).tolist()

    # Check for existing documents and remove them first
    try:
        existing = collection.get(where={"document": doc_config['name']})
        if existing['ids']:
            print(f"  Removing {len(existing['ids'])} existing chunks...")
            collection.delete(ids=existing['ids'])
    except:
        pass

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
        print(f"  ✗ Error: {e}")
        return 0


def main():
    print("=" * 70)
    print("INDEXING LOCAL CRITICAL DOCUMENTS")
    print("=" * 70)

    # Initialize
    chroma_path = "/mnt/c/Users/vijay/OneDrive/Documents/Github/clinicaltrial/sap_rtx4090/sap_generator/data/chroma_db"

    print("\nInitializing...")
    client = chromadb.PersistentClient(
        path=chroma_path,
        settings=Settings(anonymized_telemetry=False)
    )
    embedder = SentenceTransformer('all-MiniLM-L6-v2')
    print("  ✓ ChromaDB and embedder ready")

    # Check files exist
    print("\nChecking files...")
    missing = []
    for key, config in DOCUMENTS.items():
        path = Path(config['path'])
        if path.exists():
            size = path.stat().st_size / 1024
            print(f"  ✓ {key}: {path.name} ({size:.1f} KB)")
        else:
            print(f"  ✗ {key}: NOT FOUND - {config['path']}")
            missing.append(key)

    if missing:
        print(f"\n⚠️  Missing files: {missing}")
        print("Please check the file paths above.")

    # Index documents
    total_indexed = 0
    successful = []

    for key, config in DOCUMENTS.items():
        if key in missing:
            continue

        chunks = index_document(client, embedder, key, config)
        if chunks > 0:
            total_indexed += chunks
            successful.append(config['name'])

    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")

    print(f"\n✅ Successfully indexed: {len(successful)} documents")
    for name in successful:
        print(f"   • {name}")

    print(f"\n📊 Total chunks indexed: {total_indexed}")

    # Verify Tier 1 count
    print(f"\n{'=' * 70}")
    print("TIER 1 DOCUMENTS (Final Count)")
    print(f"{'=' * 70}")

    collection = client.get_collection("sap_methods")
    tier1 = collection.get(where={"tier": 1}, include=['metadatas'])

    # Get unique documents
    unique_docs = set()
    for meta in tier1['metadatas']:
        unique_docs.add(meta.get('document', 'Unknown'))

    print(f"\n✅ Tier 1 Documents: {len(unique_docs)}")
    for doc in sorted(unique_docs):
        print(f"   • {doc}")


if __name__ == '__main__':
    main()
