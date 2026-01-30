#!/usr/bin/env python3
"""
Pre-warm ChromaDB
=================
Run this script on startup/deploy to index ChromaDB BEFORE first request.
This avoids the 5-10 minute delay on first user request.

Usage:
    python scripts/prewarm_chromadb.py

Add to your Docker entrypoint or startup script:
    python scripts/prewarm_chromadb.py && uvicorn web.backend.main:app ...
"""

import sys
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def prewarm():
    """Pre-warm ChromaDB by loading/indexing if needed."""
    start = time.time()
    print("=" * 60)
    print("ChromaDB Pre-Warm Script")
    print("=" * 60)

    from enterprise_sap_system.rag.vector_store import create_vector_store

    # Create store with auto_index=True (will index if empty)
    print("\n[1/3] Initializing vector store...")
    store = create_vector_store(auto_index=True)

    # Check stats
    print("\n[2/3] Checking collection stats...")
    stats = store.get_collection_stats()
    total_chunks = sum(stats.values())

    print(f"\nCollection Stats:")
    for name, count in sorted(stats.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  {name}: {count} chunks")

    print(f"\n  TOTAL: {total_chunks} chunks")

    # Verify embedder is loaded (this is the slow part)
    print("\n[3/3] Loading embedding model...")
    _ = store.embedder  # Force load

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"Pre-warm complete in {elapsed:.1f}s")
    print(f"ChromaDB ready with {total_chunks} chunks")
    print(f"{'=' * 60}")

    return total_chunks


if __name__ == "__main__":
    chunks = prewarm()

    if chunks == 0:
        print("\nWARNING: No chunks indexed! Check rag_training_data directory.")
        sys.exit(1)

    sys.exit(0)
