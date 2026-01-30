#!/usr/bin/env python3
"""
Index Specialized SAPs into Vector Store
=========================================

Reads parsed SAP sections and adds them to the Chroma vector store
for RAG retrieval. Specialized sections get higher quality tier.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from enterprise_sap_system.rag.vector_store import SAPVectorStore, create_vector_store
    VECTOR_STORE_AVAILABLE = True
except ImportError as e:
    VECTOR_STORE_AVAILABLE = False
    print(f"Warning: Vector store not available: {e}")


def load_section(content_path: Path, metadata_path: Path) -> Dict[str, Any]:
    """Load a section from content and metadata files."""
    section = {}

    # Load content
    with open(content_path, 'r', encoding='utf-8') as f:
        section['content'] = f.read()

    # Load metadata
    if metadata_path.exists():
        with open(metadata_path, 'r', encoding='utf-8') as f:
            section['metadata'] = json.load(f)
    else:
        # Extract basic metadata from filename
        parts = content_path.stem.split('_')
        section['metadata'] = {
            'nct_id': parts[0] if parts else 'UNKNOWN',
            'section_type': parts[1] if len(parts) > 1 else 'unknown',
        }

    return section


def find_all_sections(rag_dir: Path) -> List[Dict[str, Any]]:
    """Find all section files in RAG training directory."""
    sections = []

    # Section types to index
    section_types = [
        "endpoints", "methods", "safety", "populations",
        "sample_size", "missing_data", "stratification", "study_design",
        "interim_analysis", "pro_endpoints"
    ]

    for section_type in section_types:
        section_dir = rag_dir / section_type
        if not section_dir.exists():
            continue

        for content_path in section_dir.glob("*.txt"):
            # Find corresponding metadata
            metadata_filename = content_path.stem + ".json"
            metadata_path = rag_dir / "metadata" / metadata_filename

            try:
                section = load_section(content_path, metadata_path)
                section['section_type'] = section_type
                section['file_path'] = str(content_path)
                sections.append(section)
            except Exception as e:
                print(f"  Error loading {content_path}: {e}")

    return sections


def index_sections(sections: List[Dict[str, Any]], vector_store: 'SAPVectorStore'):
    """Index sections into vector store."""
    indexed = 0
    errors = 0

    for section in sections:
        try:
            metadata = section.get('metadata', {})
            nct_id = metadata.get('nct_id', 'UNKNOWN')
            section_type = section.get('section_type', 'unknown')
            content = section.get('content', '')

            if not content or len(content) < 50:
                continue

            # Add to vector store
            vector_store.add_section(
                section_type=section_type,
                nct_id=nct_id,
                content=content,
                metadata=metadata
            )
            indexed += 1

            if indexed % 50 == 0:
                print(f"  Indexed {indexed} sections...")

        except Exception as e:
            errors += 1
            if errors < 10:  # Only print first 10 errors
                print(f"  Error indexing section: {e}")

    return indexed, errors


def main():
    script_dir = Path(__file__).parent
    default_rag_dir = script_dir.parent / "rag_training_data"

    rag_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else default_rag_dir

    if not rag_dir.exists():
        print(f"RAG directory not found: {rag_dir}")
        sys.exit(1)

    print(f"RAG Training Data: {rag_dir}")

    # Find all sections
    print(f"\n{'='*60}")
    print("FINDING SECTIONS")
    print(f"{'='*60}")

    sections = find_all_sections(rag_dir)
    print(f"Found {len(sections)} sections to index")

    # Count by type
    type_counts = {}
    for section in sections:
        st = section.get('section_type', 'unknown')
        type_counts[st] = type_counts.get(st, 0) + 1

    for st, count in sorted(type_counts.items()):
        print(f"  {st}: {count}")

    # Count specialized sections
    specialized = [s for s in sections if s.get('metadata', {}).get('specialized', False)]
    print(f"\n  Specialized sections: {len(specialized)}")

    if not VECTOR_STORE_AVAILABLE:
        print("\n⚠ Vector store not available - cannot index")
        print("Install dependencies: pip install chromadb sentence-transformers")
        return

    # Initialize vector store
    print(f"\n{'='*60}")
    print("INITIALIZING VECTOR STORE")
    print(f"{'='*60}")

    try:
        vector_store = create_vector_store()
        print("✓ Vector store initialized")
    except Exception as e:
        print(f"✗ Failed to initialize vector store: {e}")
        sys.exit(1)

    # Index sections
    print(f"\n{'='*60}")
    print("INDEXING SECTIONS")
    print(f"{'='*60}")

    indexed, errors = index_sections(sections, vector_store)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Indexed: {indexed} sections")
    print(f"  Errors: {errors}")
    print(f"\n✓ RAG index updated successfully")


if __name__ == "__main__":
    main()
