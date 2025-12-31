#!/usr/bin/env python3
"""
Vector Store for SAP RAG System
================================
Uses Chroma for local vector storage and retrieval.

Features:
- Separate collections for each section type
- Metadata filtering by therapeutic area, endpoint type, phase
- Semantic similarity search with embeddings
- Efficient batch operations
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("Warning: chromadb not installed. Run: pip install chromadb")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("Warning: sentence-transformers not installed. Run: pip install sentence-transformers")


@dataclass
class RetrievalResult:
    """Result from vector store retrieval"""
    nct_id: str
    content: str
    section_type: str
    metadata: Dict[str, Any]
    distance: float
    relevance_score: float


class SAPVectorStore:
    """
    Vector store for SAP sections using Chroma.

    Supports:
    - Semantic search across section types
    - Metadata filtering (therapeutic area, endpoint type, phase)
    - Batch indexing and retrieval
    """

    COLLECTION_NAMES = [
        "endpoints",
        "methods",
        "stratification",
        "safety",
        "populations",
        "study_design",
        "missing_data",
        "sample_size"
    ]

    def __init__(
        self,
        persist_directory: Path = None,
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize vector store.

        Args:
            persist_directory: Directory for persistent storage
            embedding_model: Sentence transformer model for embeddings
        """
        if not CHROMA_AVAILABLE:
            raise ImportError("chromadb is required. Install with: pip install chromadb")

        self.persist_directory = persist_directory or Path(__file__).parent.parent.parent / "data" / "chroma_db"
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize Chroma client with persistence
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )

        # Initialize embedding model
        self.embedding_model_name = embedding_model
        self._embedder = None

        # Initialize collections
        self.collections: Dict[str, Any] = {}
        self._init_collections()

    def _init_collections(self):
        """Initialize or get existing collections"""
        for name in self.COLLECTION_NAMES:
            try:
                self.collections[name] = self.client.get_or_create_collection(
                    name=f"sap_{name}",
                    metadata={"description": f"SAP {name} sections for RAG"}
                )
            except Exception as e:
                print(f"Error creating collection {name}: {e}")

    @property
    def embedder(self):
        """Lazy load embedding model"""
        if self._embedder is None:
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                self._embedder = SentenceTransformer(self.embedding_model_name)
            else:
                raise ImportError("sentence-transformers required for embeddings")
        return self._embedder

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text"""
        return self.embedder.encode(text).tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch of texts"""
        return self.embedder.encode(texts).tolist()

    def add_section(
        self,
        section_type: str,
        nct_id: str,
        content: str,
        metadata: Dict[str, Any]
    ):
        """
        Add a single section to the vector store.

        Args:
            section_type: Type of section (endpoints, methods, etc.)
            nct_id: NCT ID
            content: Section content
            metadata: Section metadata
        """
        if section_type not in self.collections:
            print(f"Unknown section type: {section_type}")
            return

        collection = self.collections[section_type]
        doc_id = f"{nct_id}_{section_type}"

        # Prepare metadata (Chroma requires flat structure with allowed types)
        flat_metadata = self._flatten_metadata(metadata)

        # Generate embedding
        embedding = self.embed_text(content)

        # Upsert (add or update)
        try:
            collection.upsert(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[flat_metadata]
            )
        except Exception as e:
            print(f"Error adding {doc_id}: {e}")

    def add_sections_batch(
        self,
        section_type: str,
        sections: List[Dict[str, Any]]
    ):
        """
        Add multiple sections to the vector store.

        Args:
            section_type: Type of section
            sections: List of {nct_id, content, metadata} dicts
        """
        if section_type not in self.collections:
            print(f"Unknown section type: {section_type}")
            return

        if not sections:
            return

        collection = self.collections[section_type]

        ids = []
        contents = []
        metadatas = []

        for s in sections:
            doc_id = f"{s['nct_id']}_{section_type}"
            ids.append(doc_id)
            contents.append(s['content'])
            metadatas.append(self._flatten_metadata(s.get('metadata', {})))

        # Batch embed
        print(f"  Embedding {len(contents)} {section_type} sections...")
        embeddings = self.embed_batch(contents)

        # Batch upsert
        try:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=contents,
                metadatas=metadatas
            )
            print(f"  Added {len(ids)} sections to {section_type} collection")
        except Exception as e:
            print(f"Error batch adding to {section_type}: {e}")

    def _flatten_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten metadata to Chroma-compatible format"""
        flat = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                flat[key] = value
            elif isinstance(value, list):
                flat[key] = json.dumps(value)
            elif value is None:
                flat[key] = ""
            else:
                flat[key] = str(value)
        return flat

    def query(
        self,
        section_type: str,
        query_text: str,
        n_results: int = 5,
        filters: Dict[str, Any] = None
    ) -> List[RetrievalResult]:
        """
        Query the vector store for similar sections.

        Args:
            section_type: Type of section to search
            query_text: Query text
            n_results: Number of results to return
            filters: Metadata filters (e.g., {"therapeutic_area": "oncology"})

        Returns:
            List of RetrievalResult objects
        """
        if section_type not in self.collections:
            print(f"Unknown section type: {section_type}")
            return []

        collection = self.collections[section_type]

        # Generate query embedding
        query_embedding = self.embed_text(query_text)

        # Build where clause for filtering
        where_clause = None
        if filters:
            where_conditions = []
            for key, value in filters.items():
                if value:
                    where_conditions.append({key: value})
            if where_conditions:
                if len(where_conditions) == 1:
                    where_clause = where_conditions[0]
                else:
                    where_clause = {"$and": where_conditions}

        # Query
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            print(f"Query error: {e}")
            return []

        # Convert to RetrievalResult objects
        retrieval_results = []
        if results and results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                nct_id = doc_id.replace(f"_{section_type}", "")
                distance = results['distances'][0][i] if results['distances'] else 0
                # Convert distance to relevance score (lower distance = higher relevance)
                relevance_score = max(0, 1 - distance / 2)

                retrieval_results.append(RetrievalResult(
                    nct_id=nct_id,
                    content=results['documents'][0][i] if results['documents'] else "",
                    section_type=section_type,
                    metadata=results['metadatas'][0][i] if results['metadatas'] else {},
                    distance=distance,
                    relevance_score=relevance_score
                ))

        return retrieval_results

    def query_multiple_sections(
        self,
        query_text: str,
        section_types: List[str] = None,
        n_results_per_section: int = 3,
        filters: Dict[str, Any] = None
    ) -> Dict[str, List[RetrievalResult]]:
        """
        Query multiple section types at once.

        Args:
            query_text: Query text
            section_types: List of section types (default: all)
            n_results_per_section: Results per section type
            filters: Metadata filters

        Returns:
            Dictionary mapping section_type to results
        """
        if section_types is None:
            section_types = self.COLLECTION_NAMES

        results = {}
        for section_type in section_types:
            results[section_type] = self.query(
                section_type=section_type,
                query_text=query_text,
                n_results=n_results_per_section,
                filters=filters
            )

        return results

    def get_collection_stats(self) -> Dict[str, int]:
        """Get count of documents in each collection"""
        stats = {}
        for name, collection in self.collections.items():
            try:
                stats[name] = collection.count()
            except Exception:
                stats[name] = 0
        return stats

    def delete_all(self):
        """Delete all collections (use with caution)"""
        for name in self.COLLECTION_NAMES:
            try:
                self.client.delete_collection(f"sap_{name}")
            except Exception:
                pass
        self._init_collections()

    def load_from_training_data(self, training_data_dir: Path):
        """
        Load sections from training data directory.

        Expected structure:
        training_data_dir/
            endpoints/
                NCT12345_endpoints.txt
            methods/
                NCT12345_methods.txt
            metadata/
                NCT12345_endpoints.json
        """
        training_data_dir = Path(training_data_dir)
        metadata_dir = training_data_dir / "metadata"

        total_loaded = 0

        for section_type in self.COLLECTION_NAMES:
            section_dir = training_data_dir / section_type
            if not section_dir.exists():
                continue

            sections = []
            section_files = list(section_dir.glob("*.txt"))

            for content_file in section_files:
                nct_id = content_file.stem.replace(f"_{section_type}", "")

                # Read content
                content = content_file.read_text(encoding='utf-8', errors='ignore')

                # Read metadata
                metadata_file = metadata_dir / f"{nct_id}_{section_type}.json"
                metadata = {}
                if metadata_file.exists():
                    try:
                        metadata = json.loads(metadata_file.read_text())
                    except Exception:
                        pass

                sections.append({
                    'nct_id': nct_id,
                    'content': content,
                    'metadata': metadata
                })

            if sections:
                print(f"Loading {len(sections)} {section_type} sections...")
                self.add_sections_batch(section_type, sections)
                total_loaded += len(sections)

        print(f"\nTotal loaded: {total_loaded} sections")
        return total_loaded


def create_vector_store(persist_directory: Path = None) -> SAPVectorStore:
    """Factory function to create vector store"""
    return SAPVectorStore(persist_directory=persist_directory)


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SAP Vector Store Management")
    parser.add_argument("command", choices=["load", "stats", "query", "reset"])
    parser.add_argument("--training-dir", type=str, help="Training data directory")
    parser.add_argument("--query", type=str, help="Query text")
    parser.add_argument("--section", type=str, default="endpoints", help="Section type")
    parser.add_argument("--n", type=int, default=5, help="Number of results")
    args = parser.parse_args()

    store = create_vector_store()

    if args.command == "load":
        if args.training_dir:
            store.load_from_training_data(Path(args.training_dir))
        else:
            # Default path
            default_dir = Path(__file__).parent.parent.parent / "rag_training_data"
            store.load_from_training_data(default_dir)

    elif args.command == "stats":
        stats = store.get_collection_stats()
        print("\nCollection Statistics:")
        for name, count in stats.items():
            print(f"  {name}: {count} documents")

    elif args.command == "query":
        if not args.query:
            print("Please provide --query")
        else:
            results = store.query(args.section, args.query, args.n)
            print(f"\nTop {len(results)} results for '{args.query}':")
            for i, r in enumerate(results, 1):
                print(f"\n{i}. {r.nct_id} (relevance: {r.relevance_score:.2f})")
                print(f"   {r.content[:200]}...")

    elif args.command == "reset":
        confirm = input("This will delete all data. Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            store.delete_all()
            print("All collections deleted.")
