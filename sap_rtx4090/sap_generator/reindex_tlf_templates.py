#!/usr/bin/env python3
"""
Reindex TLF Collection with Template-Based Shells
=================================================

Replaces PDF-extracted TLF shells (which have poor quality) with
high-quality template-based shells from tlf_shells.py.

Templates include:
- Column specifications (header, width, alignment)
- Row structures with indentation levels
- Footnotes
- Source datasets
- Programming notes
- Mock ASCII tables
"""

import os
import sys
import hashlib
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import chromadb
from chromadb.utils import embedding_functions

from enterprise_sap_system.core.schemas import EndpointType
from enterprise_sap_system.specs.tlf_shells import TLFShellGenerator, TLFType

CHROMA_DB_PATH = "./chroma_db/sap_rag_3col"
COLLECTION_TLF = "sap_tlf"


class MockProtocol:
    """Simple mock protocol for TLF shell generation."""
    def __init__(self, nct_id: str, endpoint_type: EndpointType, phase: str, indication: str):
        self.nct_id = nct_id
        self.phase = phase
        self.indication = indication
        self.treatment_arms = ["Treatment A", "Treatment B"]

        # Create mock primary estimand
        self.primary_estimand = type('Estimand', (), {
            'variable_type': endpoint_type,
            'objective': f"To evaluate {endpoint_type.value}",
            'population': "ITT Population"
        })()


def create_mock_protocol(endpoint_type: EndpointType, phase: str, indication: str):
    """Create a mock protocol for shell generation."""
    nct_id = f"NCT_TEMPLATE_{endpoint_type.value}"
    return MockProtocol(nct_id, endpoint_type, phase, indication)


def generate_all_template_shells():
    """Generate TLF shells for all endpoint types and phases."""
    generator = TLFShellGenerator()
    all_shells = []

    # Generate shells for different endpoint types
    endpoint_types = [
        (EndpointType.PFS, "Phase 3", "Oncology - Solid Tumor"),
        (EndpointType.OS, "Phase 3", "Oncology - Solid Tumor"),
        (EndpointType.ORR, "Phase 2", "Oncology - Solid Tumor"),
        (EndpointType.EFFICACY, "Phase 3", "Cardiovascular"),
        (EndpointType.SAFETY, "Phase 1", "Oncology - Dose Escalation"),
    ]

    for endpoint_type, phase, indication in endpoint_types:
        print(f"  Generating shells for {endpoint_type.value} ({phase}, {indication})...")

        protocol = create_mock_protocol(endpoint_type, phase, indication)
        estimands = {"primary": {"type": endpoint_type.value}}

        try:
            shells = generator.generate_all_shells(protocol, estimands)

            for category, category_shells in shells.items():
                for shell in category_shells:
                    all_shells.append({
                        "shell": shell,
                        "endpoint_type": endpoint_type.value,
                        "phase": phase,
                        "indication": indication,
                        "category": category
                    })
        except Exception as e:
            print(f"    Warning: Error generating {endpoint_type.value} shells: {e}")

    return all_shells


def reindex_tlf_collection():
    """Clear and reindex TLF collection with template shells."""
    print("=" * 60)
    print("TLF Collection Reindex with Template Shells")
    print("=" * 60)

    # Initialize ChromaDB
    print("\n[1] Initializing ChromaDB...")
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # Delete existing TLF collection
    print("[2] Clearing existing TLF collection...")
    try:
        client.delete_collection(COLLECTION_TLF)
        print("    Deleted existing collection")
    except Exception as e:
        print(f"    No existing collection to delete: {e}")

    # Create new collection
    tlf_collection = client.get_or_create_collection(
        name=COLLECTION_TLF,
        embedding_function=embedding_fn,
        metadata={"description": "TLF shells from templates"}
    )

    # Generate all template shells
    print("[3] Generating template shells...")
    all_shells = generate_all_template_shells()
    print(f"    Generated {len(all_shells)} total shells")

    # Index shells
    print("[4] Indexing shells to ChromaDB...")

    ids = []
    documents = []
    metadatas = []

    for i, shell_data in enumerate(all_shells):
        shell = shell_data["shell"]

        # Generate markdown content
        markdown_content = shell.to_markdown()

        # Create ID
        shell_id = hashlib.md5(
            f"{shell_data['endpoint_type']}_{shell_data['category']}_{shell.number}_{i}".encode()
        ).hexdigest()[:12]

        # Metadata
        meta = {
            "tlf_type": shell.tlf_type.value,
            "tlf_number": shell.number,
            "tlf_title": shell.title[:200],
            "category": shell_data["category"],
            "endpoint_type": shell_data["endpoint_type"],
            "phase": shell_data["phase"],
            "indication": shell_data["indication"],
            "population": shell.population,
            "source_dataset": shell.source_dataset,
            "has_mock": bool(shell.mock_data),
            "num_columns": len(shell.columns),
            "num_rows": len(shell.stub_rows),
            "num_footnotes": len(shell.footnotes),
        }

        ids.append(shell_id)
        documents.append(markdown_content)
        metadatas.append(meta)

    # Add to collection in batches
    batch_size = 50
    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        tlf_collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end]
        )
        print(f"    Indexed batch {i//batch_size + 1}: {end}/{len(ids)} shells")

    # Verify
    print("\n[5] Verification...")
    final_count = tlf_collection.count()
    print(f"    TLF collection now has {final_count} shells")

    # Show sample
    print("\n[6] Sample shells:")
    sample = tlf_collection.get(limit=3, include=["documents", "metadatas"])
    for i, (doc, meta) in enumerate(zip(sample["documents"], sample["metadatas"])):
        print(f"\n    === Shell {i+1}: {meta['tlf_title'][:50]}... ===")
        print(f"    Type: {meta['tlf_type']} | Category: {meta['category']}")
        print(f"    Endpoint: {meta['endpoint_type']} | Phase: {meta['phase']}")
        print(f"    Columns: {meta['num_columns']} | Rows: {meta['num_rows']} | Footnotes: {meta['num_footnotes']}")
        print(f"    Content preview:\n{doc[:400]}...")

    print("\n" + "=" * 60)
    print("Reindex Complete!")
    print("=" * 60)

    return final_count


if __name__ == "__main__":
    count = reindex_tlf_collection()
    print(f"\nTotal TLF shells indexed: {count}")
