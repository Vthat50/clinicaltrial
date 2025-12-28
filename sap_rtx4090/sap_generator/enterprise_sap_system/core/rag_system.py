#!/usr/bin/env python3
"""
RAG (Retrieval Augmented Generation) System for SAP Generation
===============================================================
Uses real protocol-SAP pairs as few-shot examples for improved generation.

Architecture:
1. Filter high-quality protocol-SAP pairs
2. Create embeddings for protocols using sentence transformers
3. At runtime: retrieve top-k similar protocols and their SAPs
4. SANITIZE examples to remove specific values (prevent contamination)
5. Use as few-shot examples in LLM prompt

CRITICAL: Examples are SANITIZED before passing to LLM to prevent
cross-protocol contamination (e.g., etrolizumab appearing in TJ301 SAP).
"""

import os
import re
import json
import hashlib
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict


@dataclass
class ProtocolSAPPair:
    """A protocol-SAP training pair"""
    nct_id: str
    protocol_text: str
    sap_text: str
    therapeutic_area: str
    phase: str
    quality_score: float
    protocol_length: int
    sap_length: int


class RAGSystem:
    """
    Retrieval Augmented Generation system for SAP generation.
    Retrieves similar real protocol-SAP pairs as few-shot examples.
    """

    # Quality thresholds
    MIN_SAP_LINES = 150
    MIN_PROTOCOL_LINES = 100

    # Therapeutic area keywords
    TA_KEYWORDS = {
        "ONCOLOGY": [
            "cancer", "tumor", "carcinoma", "melanoma", "lymphoma", "leukemia",
            "nsclc", "breast cancer", "colorectal", "pancreatic", "hepatocellular",
            "chemotherapy", "immunotherapy", "recist", "progression-free"
        ],
        "IBD": [
            "ulcerative colitis", "crohn", "inflammatory bowel", "ibd",
            "mayo score", "cdai", "endoscopic", "mucosal healing"
        ],
        "RHEUMATOLOGY": [
            "rheumatoid arthritis", "psoriatic arthritis", "ankylosing",
            "acr20", "acr50", "das28", "dmard"
        ],
        "DERMATOLOGY": [
            "psoriasis", "atopic dermatitis", "eczema", "pasi", "easi"
        ],
        "NEUROLOGY": [
            "multiple sclerosis", "alzheimer", "parkinson", "epilepsy"
        ],
        "CARDIOLOGY": [
            "heart failure", "cardiovascular", "atrial fibrillation"
        ],
        "INFECTIOUS": [
            "hiv", "hepatitis", "covid", "influenza", "bacterial infection"
        ],
    }

    # Phase patterns
    PHASE_PATTERNS = {
        "1": r'\bphase\s*[1iI]\b(?!\s*[/\\]\s*[23])',
        "1/2": r'\bphase\s*[1iI]\s*[/\\]\s*[2iI]',
        "2": r'\bphase\s*[2iI]{1,2}\b(?!\s*[/\\])',
        "3": r'\bphase\s*[3iI]{1,3}\b',
        "4": r'\bphase\s*[4iIvV]',
    }

    def __init__(self, data_dir: str = None, cache_dir: str = None):
        """
        Initialize RAG system.

        Args:
            data_dir: Directory containing protocol-SAP pairs
            cache_dir: Directory for caching embeddings
        """
        if data_dir is None:
            # Default path
            base = Path(__file__).parent.parent.parent
            data_dir = base / "data" / "all_pairs"

        self.data_dir = Path(data_dir)
        self.cache_dir = Path(cache_dir) if cache_dir else self.data_dir.parent / "rag_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.pairs: List[ProtocolSAPPair] = []
        self.embeddings: Optional[np.ndarray] = None
        self.embedding_model = None

    def load_and_filter_pairs(self) -> int:
        """
        Load and filter high-quality protocol-SAP pairs.

        Returns:
            Number of high-quality pairs loaded
        """
        print(f"Loading pairs from {self.data_dir}")

        # Find all protocol files
        protocol_files = list(self.data_dir.glob("*_protocol.txt"))
        print(f"Found {len(protocol_files)} protocol files")

        for protocol_file in protocol_files:
            nct_id = protocol_file.stem.replace("_protocol", "")
            sap_file = self.data_dir / f"{nct_id}_sap.txt"

            if not sap_file.exists():
                continue

            try:
                protocol_text = protocol_file.read_text(encoding='utf-8', errors='ignore')
                sap_text = sap_file.read_text(encoding='utf-8', errors='ignore')
            except Exception as e:
                continue

            # Quality checks
            protocol_lines = len(protocol_text.split('\n'))
            sap_lines = len(sap_text.split('\n'))

            if protocol_lines < self.MIN_PROTOCOL_LINES:
                continue
            if sap_lines < self.MIN_SAP_LINES:
                continue

            # Check for proper SAP structure
            sap_lower = sap_text.lower()
            has_sap_structure = any([
                "statistical analysis plan" in sap_lower,
                "statistical methods" in sap_lower,
                "primary efficacy" in sap_lower,
                "sample size" in sap_lower,
                "analysis population" in sap_lower,
            ])

            if not has_sap_structure:
                continue

            # Check for encoding issues (garbled text)
            if self._has_encoding_issues(protocol_text) or self._has_encoding_issues(sap_text):
                continue

            # Detect therapeutic area and phase
            ta = self._detect_therapeutic_area(protocol_text)
            phase = self._detect_phase(protocol_text)

            # Calculate quality score
            quality_score = self._calculate_quality_score(
                protocol_text, sap_text, protocol_lines, sap_lines
            )

            pair = ProtocolSAPPair(
                nct_id=nct_id,
                protocol_text=protocol_text,
                sap_text=sap_text,
                therapeutic_area=ta,
                phase=phase,
                quality_score=quality_score,
                protocol_length=protocol_lines,
                sap_length=sap_lines
            )

            self.pairs.append(pair)

        # Sort by quality score
        self.pairs.sort(key=lambda x: x.quality_score, reverse=True)

        print(f"Loaded {len(self.pairs)} high-quality pairs")
        self._print_distribution()

        return len(self.pairs)

    def _has_encoding_issues(self, text: str) -> bool:
        """Check if text has encoding/extraction issues"""
        # Check for long strings of uppercase letters (garbled PDF)
        if re.search(r'[A-Z0-9]{40,}', text[:500]):
            return True
        # Check for excessive special characters
        special_ratio = len(re.findall(r'[^a-zA-Z0-9\s.,;:\-()]', text[:1000])) / 1000
        if special_ratio > 0.3:
            return True
        return False

    def _detect_therapeutic_area(self, text: str) -> str:
        """Detect therapeutic area from protocol text"""
        text_lower = text.lower()
        scores = {}

        for ta, keywords in self.TA_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            scores[ta] = score

        if max(scores.values()) >= 2:
            return max(scores, key=scores.get)
        return "OTHER"

    def _detect_phase(self, text: str) -> str:
        """Detect study phase from protocol text"""
        text_lower = text.lower()

        for phase, pattern in self.PHASE_PATTERNS.items():
            if re.search(pattern, text_lower):
                return phase
        return "unknown"

    def _calculate_quality_score(
        self, protocol: str, sap: str,
        protocol_lines: int, sap_lines: int
    ) -> float:
        """Calculate quality score for a pair"""
        score = 0.0

        # Length bonus (longer = more complete)
        score += min(protocol_lines / 500, 1.0) * 20
        score += min(sap_lines / 500, 1.0) * 20

        # SAP structure bonus
        sap_lower = sap.lower()
        structure_keywords = [
            "table of contents", "primary endpoint", "secondary endpoint",
            "sample size", "analysis population", "statistical methods",
            "interim analysis", "missing data", "sensitivity analysis"
        ]
        score += sum(5 for kw in structure_keywords if kw in sap_lower)

        # Protocol structure bonus
        protocol_lower = protocol.lower()
        protocol_keywords = [
            "primary objective", "secondary objective", "inclusion criteria",
            "exclusion criteria", "study design", "randomization"
        ]
        score += sum(3 for kw in protocol_keywords if kw in protocol_lower)

        return score

    def _print_distribution(self):
        """Print distribution of pairs by TA and phase"""
        ta_counts = {}
        phase_counts = {}

        for pair in self.pairs:
            ta_counts[pair.therapeutic_area] = ta_counts.get(pair.therapeutic_area, 0) + 1
            phase_counts[pair.phase] = phase_counts.get(pair.phase, 0) + 1

        print("\nTherapeutic Area Distribution:")
        for ta, count in sorted(ta_counts.items(), key=lambda x: -x[1]):
            print(f"  {ta}: {count}")

        print("\nPhase Distribution:")
        for phase, count in sorted(phase_counts.items()):
            print(f"  Phase {phase}: {count}")

    def create_embeddings(self, use_openai: bool = True):
        """
        Create embeddings for all protocols.

        Args:
            use_openai: Use OpenAI embeddings (default True for production, lighter weight)
        """
        cache_file = self.cache_dir / "embeddings.npz"
        index_file = self.cache_dir / "index.json"

        # Check cache
        if cache_file.exists() and index_file.exists():
            print("Loading cached embeddings...")
            data = np.load(cache_file)
            self.embeddings = data['embeddings']

            with open(index_file) as f:
                cached_index = json.load(f)

            # Verify cache matches current pairs
            current_ids = [p.nct_id for p in self.pairs]
            if cached_index == current_ids:
                print(f"Loaded {len(self.embeddings)} cached embeddings")
                return
            else:
                print("Cache mismatch, regenerating...")

        print(f"Creating embeddings for {len(self.pairs)} protocols...")

        if use_openai:
            self._create_openai_embeddings()
        else:
            self._create_sentence_transformer_embeddings()

        # Save cache
        np.savez(cache_file, embeddings=self.embeddings)
        with open(index_file, 'w') as f:
            json.dump([p.nct_id for p in self.pairs], f)

        print(f"Created and cached {len(self.embeddings)} embeddings")

    def _create_sentence_transformer_embeddings(self):
        """Create embeddings using sentence-transformers"""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print("Installing sentence-transformers...")
            import subprocess
            subprocess.run(["pip", "install", "sentence-transformers"], check=True)
            from sentence_transformers import SentenceTransformer

        # Use a model good for scientific/medical text
        model = SentenceTransformer('all-MiniLM-L6-v2')

        # Create summary of each protocol for embedding
        texts = []
        for pair in self.pairs:
            # Extract key sections for embedding
            summary = self._extract_protocol_summary(pair.protocol_text)
            texts.append(summary)

        self.embeddings = model.encode(texts, show_progress_bar=True)
        self.embedding_model = model

    def _create_openai_embeddings(self):
        """Create embeddings using OpenAI API"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required for OpenAI embeddings")

        client = OpenAI()
        embeddings = []

        for i, pair in enumerate(self.pairs):
            if i % 50 == 0:
                print(f"  Processing {i}/{len(self.pairs)}...")

            summary = self._extract_protocol_summary(pair.protocol_text)
            # Truncate to fit token limit
            summary = summary[:8000]

            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=summary
            )
            embeddings.append(response.data[0].embedding)

        self.embeddings = np.array(embeddings)

    def _extract_protocol_summary(self, protocol: str, max_chars: int = 2000) -> str:
        """Extract key information from protocol for embedding"""
        sections = []

        # Try to find key sections
        patterns = [
            (r'(?:title|study\s+title)[:\s]+([^\n]+)', "Title"),
            (r'(?:primary\s+(?:objective|endpoint))[:\s]+([^\n]+(?:\n(?![A-Z])[^\n]+)*)', "Primary"),
            (r'(?:study\s+design)[:\s]+([^\n]+(?:\n(?![A-Z])[^\n]+)*)', "Design"),
            (r'(?:indication|disease)[:\s]+([^\n]+)', "Indication"),
        ]

        for pattern, label in patterns:
            match = re.search(pattern, protocol, re.IGNORECASE)
            if match:
                sections.append(f"{label}: {match.group(1).strip()[:300]}")

        # If no sections found, use first part of protocol
        if not sections:
            sections.append(protocol[:max_chars])

        return " ".join(sections)[:max_chars]

    def retrieve_similar(
        self,
        query_protocol: str,
        k: int = 3,
        therapeutic_area: str = None,
        phase: str = None
    ) -> List[ProtocolSAPPair]:
        """
        Retrieve k most similar protocol-SAP pairs.

        Args:
            query_protocol: The input protocol text
            k: Number of similar pairs to retrieve
            therapeutic_area: Filter by therapeutic area (optional)
            phase: Filter by phase (optional)

        Returns:
            List of k most similar ProtocolSAPPair objects
        """
        if self.embeddings is None:
            raise ValueError("Embeddings not created. Call create_embeddings() first.")

        # Create embedding for query
        query_summary = self._extract_protocol_summary(query_protocol)

        if self.embedding_model:
            query_embedding = self.embedding_model.encode([query_summary])[0]
        else:
            # Assume OpenAI embeddings
            from openai import OpenAI
            client = OpenAI()
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=query_summary[:8000]
            )
            query_embedding = np.array(response.data[0].embedding)

        # Calculate cosine similarity
        similarities = np.dot(self.embeddings, query_embedding) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Apply filters
        filtered_indices = list(range(len(self.pairs)))

        if therapeutic_area and therapeutic_area != "OTHER":
            filtered_indices = [
                i for i in filtered_indices
                if self.pairs[i].therapeutic_area == therapeutic_area
            ]

        if phase and phase != "unknown":
            # Match similar phases (e.g., Phase 2 matches 2, 2a, 2b)
            base_phase = phase.replace("a", "").replace("b", "")
            filtered_indices = [
                i for i in filtered_indices
                if self.pairs[i].phase.startswith(base_phase)
            ]

        # Get top-k from filtered
        if filtered_indices:
            filtered_similarities = [(i, similarities[i]) for i in filtered_indices]
            filtered_similarities.sort(key=lambda x: x[1], reverse=True)
            top_indices = [i for i, _ in filtered_similarities[:k]]
        else:
            # Fall back to all pairs if no matches
            top_indices = np.argsort(similarities)[-k:][::-1]

        return [self.pairs[i] for i in top_indices]

    def sanitize_example(self, text: str) -> str:
        """
        Sanitize example text by replacing specific values with placeholders.

        This PREVENTS cross-protocol contamination by ensuring the LLM
        never sees specific drug names, sample sizes, or NCT IDs from examples.

        Args:
            text: Raw example text (protocol or SAP)

        Returns:
            Sanitized text with placeholders
        """
        sanitized = text

        # 1. Replace NCT IDs
        sanitized = re.sub(r'NCT\d{8}', '{NCT_ID}', sanitized, flags=re.IGNORECASE)

        # 2. Replace drug codes (TJ301, PF-06480605, etc.)
        sanitized = re.sub(r'\b[A-Z]{2,4}[-]?\d{5,8}\b', '{DRUG_CODE}', sanitized)
        sanitized = re.sub(r'\b[A-Z]{2,3}\d{3,4}\b', '{DRUG_CODE}', sanitized)

        # 3. Replace known drug names (biologics)
        drug_patterns = [
            r'\b(etrolizumab|vedolizumab|ustekinumab|adalimumab|infliximab)\b',
            r'\b(golimumab|tofacitinib|filgotinib|ozanimod|risankizumab)\b',
            r'\b(mirikizumab|guselkumab|etrasimod|obefazimod|ontamalimab)\b',
            r'\b(brazikumab|olamkicept|pembrolizumab|nivolumab|atezolizumab)\b',
            r'\b([a-z]+(?:mab|nib|lib|tinib|ciclib))\b',
        ]
        for pattern in drug_patterns:
            sanitized = re.sub(pattern, '{DRUG_NAME}', sanitized, flags=re.IGNORECASE)

        # 4. Replace sample sizes (numbers followed by patients/subjects)
        sanitized = re.sub(
            r'\b(\d{2,4})\s+(patients?|subjects?|participants?)',
            '{SAMPLE_SIZE} \\2',
            sanitized,
            flags=re.IGNORECASE
        )

        # 5. Replace specific sample sizes in context
        sanitized = re.sub(
            r'N\s*[=:]\s*\d{2,4}',
            'N = {SAMPLE_SIZE}',
            sanitized
        )

        # 6. Replace cohort references
        sanitized = re.sub(
            r'Cohort\s+\d+',
            '{COHORT}',
            sanitized,
            flags=re.IGNORECASE
        )

        # 7. Replace specific doses
        sanitized = re.sub(
            r'\b\d+\s*(?:mg|mcg|µg|g)\b',
            '{DOSE}',
            sanitized,
            flags=re.IGNORECASE
        )

        # 8. Replace sponsor names
        sponsor_patterns = [
            r'\b(Roche|Pfizer|Merck|Novartis|AstraZeneca|BMS|Lilly|Amgen|Gilead|AbbVie)\b',
            r'\b(Genentech|Johnson\s*&\s*Johnson|Sanofi|GSK|Takeda|Biogen)\b',
        ]
        for pattern in sponsor_patterns:
            sanitized = re.sub(pattern, '{SPONSOR}', sanitized, flags=re.IGNORECASE)

        return sanitized

    def format_few_shot_examples(
        self,
        similar_pairs: List[ProtocolSAPPair],
        max_protocol_chars: int = 3000,
        max_sap_chars: int = 8000,
        sanitize: bool = True
    ) -> str:
        """
        Format retrieved pairs as few-shot examples for the LLM prompt.

        Args:
            similar_pairs: List of similar protocol-SAP pairs
            max_protocol_chars: Max chars to include from each protocol
            max_sap_chars: Max chars to include from each SAP
            sanitize: Whether to sanitize examples (HIGHLY RECOMMENDED)

        Returns:
            Formatted string with examples
        """
        examples = []

        # Add warning header if sanitizing
        if sanitize:
            examples.append("""
## TEMPLATE EXAMPLES (FOR STRUCTURE ONLY)
The following examples show SAP STRUCTURE and FORMATTING only.
All specific values have been replaced with {PLACEHOLDERS}.
DO NOT copy these placeholder values - use the MANDATORY FACTS provided separately.
""")

        for i, pair in enumerate(similar_pairs, 1):
            # Extract key sections from protocol
            protocol_excerpt = self._extract_key_sections(
                pair.protocol_text, max_protocol_chars
            )

            # Extract key sections from SAP
            sap_excerpt = self._extract_key_sections(
                pair.sap_text, max_sap_chars
            )

            # SANITIZE if enabled (default: True)
            if sanitize:
                protocol_excerpt = self.sanitize_example(protocol_excerpt)
                sap_excerpt = self.sanitize_example(sap_excerpt)

            example = f"""
=== TEMPLATE {i}: {pair.therapeutic_area}, Phase {pair.phase} ===

PROTOCOL STRUCTURE:
{protocol_excerpt}

SAP STRUCTURE (copy format, NOT values):
{sap_excerpt}
"""
            examples.append(example)

        return "\n".join(examples)

    def _extract_key_sections(self, text: str, max_chars: int) -> str:
        """Extract key sections from a document"""
        if len(text) <= max_chars:
            return text

        # Try to find important sections
        sections = []

        # Look for table of contents, primary endpoint, statistical methods
        important_headers = [
            "primary", "statistical", "sample size", "analysis population",
            "endpoint", "objective", "efficacy"
        ]

        lines = text.split('\n')
        current_section = []
        in_important = False

        for line in lines:
            line_lower = line.lower()

            # Check if this is an important section header
            is_header = any(h in line_lower for h in important_headers)

            if is_header:
                if current_section and in_important:
                    sections.append('\n'.join(current_section))
                current_section = [line]
                in_important = True
            elif in_important:
                current_section.append(line)
                # Stop after ~500 chars per section
                if len('\n'.join(current_section)) > 500:
                    sections.append('\n'.join(current_section))
                    current_section = []
                    in_important = False

        if current_section and in_important:
            sections.append('\n'.join(current_section))

        result = '\n\n'.join(sections)

        # If we didn't find good sections, just use the start
        if len(result) < 500:
            result = text[:max_chars]

        return result[:max_chars]

    def save_filtered_pairs(self, output_file: str = None):
        """Save filtered pairs metadata to JSON"""
        if output_file is None:
            output_file = self.cache_dir / "filtered_pairs.json"

        data = []
        for pair in self.pairs:
            data.append({
                "nct_id": pair.nct_id,
                "therapeutic_area": pair.therapeutic_area,
                "phase": pair.phase,
                "quality_score": pair.quality_score,
                "protocol_length": pair.protocol_length,
                "sap_length": pair.sap_length,
            })

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Saved {len(data)} pairs to {output_file}")


# Singleton instance
_rag_instance: Optional[RAGSystem] = None


def get_rag_system(data_dir: str = None) -> RAGSystem:
    """Get or create the RAG system singleton"""
    global _rag_instance

    if _rag_instance is None:
        _rag_instance = RAGSystem(data_dir=data_dir)
        _rag_instance.load_and_filter_pairs()
        _rag_instance.create_embeddings()

    return _rag_instance


def retrieve_similar_saps(
    protocol_text: str,
    k: int = 3,
    therapeutic_area: str = None,
    phase: str = None
) -> str:
    """
    Convenience function to retrieve similar SAPs as few-shot examples.

    Args:
        protocol_text: Input protocol text
        k: Number of examples to retrieve
        therapeutic_area: Filter by TA
        phase: Filter by phase

    Returns:
        Formatted few-shot examples string
    """
    rag = get_rag_system()
    similar = rag.retrieve_similar(
        protocol_text, k=k,
        therapeutic_area=therapeutic_area,
        phase=phase
    )
    return rag.format_few_shot_examples(similar)


if __name__ == "__main__":
    # Test the RAG system
    print("Initializing RAG system...")
    rag = RAGSystem()

    print("\n" + "="*60)
    print("STEP 1: Loading and filtering pairs")
    print("="*60)
    num_pairs = rag.load_and_filter_pairs()

    print("\n" + "="*60)
    print("STEP 2: Creating embeddings")
    print("="*60)
    rag.create_embeddings()

    print("\n" + "="*60)
    print("STEP 3: Saving filtered pairs")
    print("="*60)
    rag.save_filtered_pairs()

    print("\n" + "="*60)
    print("STEP 4: Testing retrieval")
    print("="*60)

    # Test with a sample query
    test_query = """
    Phase 2, randomized, double-blind study to evaluate the efficacy and safety
    of Drug X in patients with moderate-to-severe ulcerative colitis.
    Primary endpoint: Clinical remission at Week 12 defined by Mayo score.
    """

    similar = rag.retrieve_similar(test_query, k=3, therapeutic_area="IBD")

    print(f"\nTop 3 similar protocols for IBD Phase 2 query:")
    for i, pair in enumerate(similar, 1):
        print(f"  {i}. {pair.nct_id} - {pair.therapeutic_area}, Phase {pair.phase} (score: {pair.quality_score:.1f})")

    print("\n" + "="*60)
    print("RAG System Ready!")
    print("="*60)
