#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Few-Shot Example Selector
==============================================================
TIER 4: Few-Shot Learning with Real SAP Examples

Features:
- Load and parse real protocol-SAP pairs
- Embedding-based similarity search
- MMR (Maximal Marginal Relevance) for diversity
- Section-level example extraction
"""

import os
import json
import re
import pickle
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
from collections import defaultdict

# Use relative imports for consistent module resolution
try:
    from ..core.config import get_config
    from ..core.schemas import ParsedProtocol, SAPExamplePair, EndpointType
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from core.config import get_config
    from core.schemas import ParsedProtocol, SAPExamplePair, EndpointType

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


@dataclass
class ProcessedSAPPair:
    """Processed SAP pair with extracted sections and embeddings"""
    nct_id: str
    protocol_text: str
    sap_text: str

    # Extracted metadata
    phase: str = ""
    therapeutic_area: str = ""
    endpoint_type: str = ""

    # Parsed sections
    sap_sections: Dict[str, str] = field(default_factory=dict)

    # Embeddings
    protocol_embedding: Optional[np.ndarray] = None
    sap_embedding: Optional[np.ndarray] = None

    # Quality score (based on content completeness)
    quality_score: float = 0.8


class SAPPairDatabase:
    """
    Database of real protocol-SAP pairs for few-shot learning.
    Loads pairs from disk and provides similarity-based retrieval.
    """

    # SAP section patterns for extraction
    SECTION_PATTERNS = {
        "1_introduction": [
            r'(?:^|\n)\s*1\.?\s*introduction\s*(?:\n|$)(.*?)(?=\n\s*2\.|\Z)',
            r'(?:^|\n)\s*introduction\s*(?:\n|$)(.*?)(?=\n\s*(?:\d+\.|objectives?|study\s+design)|\Z)',
        ],
        "2_objectives_estimands": [
            r'(?:^|\n)\s*2\.?\s*(?:study\s+)?objectives?\s*(?:and\s+(?:endpoints?|estimands?))?\s*(?:\n|$)(.*?)(?=\n\s*3\.|\Z)',
            r'(?:^|\n)\s*(?:study\s+)?objectives?\s*(?:\n|$)(.*?)(?=\n\s*(?:\d+\.|study\s+design|analysis)|\Z)',
        ],
        "3_study_design": [
            r'(?:^|\n)\s*3\.?\s*(?:study\s+)?design\s*(?:\n|$)(.*?)(?=\n\s*4\.|\Z)',
            r'(?:^|\n)\s*study\s+design\s*(?:\n|$)(.*?)(?=\n\s*(?:\d+\.|analysis|populations?)|\Z)',
        ],
        "4_analysis_populations": [
            r'(?:^|\n)\s*4\.?\s*(?:analysis\s+)?populations?\s*(?:\n|$)(.*?)(?=\n\s*5\.|\Z)',
            r'(?:^|\n)\s*(?:analysis\s+)?(?:populations?|analysis\s+sets?)\s*(?:\n|$)(.*?)(?=\n\s*(?:\d+\.|statistical|methods?)|\Z)',
        ],
        "5_statistical_methods": [
            r'(?:^|\n)\s*5\.?\s*statistical\s*(?:methods?|analysis|methodology)\s*(?:\n|$)(.*?)(?=\n\s*6\.|\Z)',
            r'(?:^|\n)\s*statistical\s*(?:methods?|analysis)\s*(?:\n|$)(.*?)(?=\n\s*(?:\d+\.|sample\s+size|data\s+handling)|\Z)',
        ],
        "6_sample_size": [
            r'(?:^|\n)\s*6\.?\s*sample\s+size\s*(?:\n|$)(.*?)(?=\n\s*7\.|\Z)',
            r'(?:^|\n)\s*sample\s+size\s*(?:and\s+power)?\s*(?:\n|$)(.*?)(?=\n\s*(?:\d+\.|data\s+handling|missing)|\Z)',
        ],
        "7_data_handling": [
            r'(?:^|\n)\s*7\.?\s*(?:data\s+)?handling\s*(?:\n|$)(.*?)(?=\n\s*8\.|\Z)',
            r'(?:^|\n)\s*(?:data\s+handling|missing\s+data)\s*(?:\n|$)(.*?)(?=\n\s*(?:\d+\.|cdisc|tables?)|\Z)',
        ],
        "8_cdisc_alignment": [
            r'(?:^|\n)\s*8\.?\s*(?:cdisc|adam)\s*(?:\n|$)(.*?)(?=\n\s*9\.|\Z)',
            r'(?:^|\n)\s*(?:cdisc|adam)\s*(?:alignment|mapping|datasets?)?\s*(?:\n|$)(.*?)(?=\n\s*(?:\d+\.|tables?|figures?|listings?)|\Z)',
        ],
        "9_tlf_specifications": [
            r'(?:^|\n)\s*9\.?\s*(?:tables?,?\s*(?:listings?,?\s*)?(?:and\s+)?figures?|tlf)\s*(?:\n|$)(.*?)(?=\n\s*10\.|\n\s*appendi|\Z)',
            r'(?:^|\n)\s*(?:tables?,?\s*(?:listings?,?\s*)?(?:and\s+)?figures?|tlf\s+specifications?)\s*(?:\n|$)(.*?)(?=\n\s*(?:\d+\.|appendi)|\Z)',
        ],
    }

    # Endpoint classification patterns
    ENDPOINT_PATTERNS = {
        "SAFETY": [r'safety', r'tolerability', r'dlt', r'mtd', r'dose.?limiting', r'maximum.?tolerated'],
        "ORR": [r'response\s+rate', r'\borr\b', r'objective\s+response', r'recist'],
        "PFS": [r'progression.?free', r'\bpfs\b'],
        "OS": [r'overall\s+survival', r'\bos\b(?!.*operating)'],
        "DFS": [r'disease.?free', r'\bdfs\b', r'recurrence.?free'],
        "PK": [r'pharmacokinetic', r'\bpk\b', r'\bauc\b', r'\bcmax\b'],
    }

    # Phase patterns
    PHASE_PATTERNS = {
        "1": [r'phase\s*[1iI]\b(?!\s*[/\\]\s*[23])'],
        "1/2": [r'phase\s*[1iI]\s*[/\\]\s*[2iI]'],
        "2": [r'phase\s*[2iI]{1,2}\b(?!\s*[/\\])'],
        "3": [r'phase\s*[3iI]{1,3}\b'],
        "4": [r'phase\s*[4iIvV]'],
    }

    def __init__(self, data_dir: str = None, load_on_init: bool = True):
        """
        Initialize the SAP pair database.

        Args:
            data_dir: Directory containing protocol-SAP pairs
            load_on_init: Whether to load pairs on initialization
        """
        self.config = get_config()
        self.data_dir = Path(data_dir) if data_dir else self.config.paths.all_pairs_dir

        self.pairs: List[ProcessedSAPPair] = []
        self.embedding_model = None

        # Index structures
        self.by_endpoint: Dict[str, List[int]] = defaultdict(list)
        self.by_phase: Dict[str, List[int]] = defaultdict(list)
        self.by_therapeutic_area: Dict[str, List[int]] = defaultdict(list)

        # Initialize embedding model
        if SentenceTransformer is not None:
            try:
                self.embedding_model = SentenceTransformer(
                    self.config.model.embedding_model
                )
            except Exception as e:
                print(f"WARNING: Could not load embedding model: {e}")

        if load_on_init:
            self.load_pairs()

    def load_pairs(self, max_pairs: int = None) -> int:
        """
        Load protocol-SAP pairs from the data directory.

        Args:
            max_pairs: Maximum number of pairs to load (None for all)

        Returns:
            Number of pairs loaded
        """
        if not self.data_dir.exists():
            print(f"WARNING: Data directory not found: {self.data_dir}")
            return 0

        # Find all protocol files
        protocol_files = sorted(self.data_dir.glob("*_protocol.txt"))

        if max_pairs:
            protocol_files = protocol_files[:max_pairs]

        loaded = 0
        for protocol_path in protocol_files:
            # Find corresponding SAP file
            nct_id = protocol_path.stem.replace("_protocol", "")
            sap_path = self.data_dir / f"{nct_id}_sap.txt"

            if not sap_path.exists():
                continue

            try:
                # Load texts
                protocol_text = protocol_path.read_text(encoding='utf-8', errors='ignore')
                sap_text = sap_path.read_text(encoding='utf-8', errors='ignore')

                # Skip if too short
                if len(sap_text) < 1000:
                    continue

                # Create processed pair
                pair = ProcessedSAPPair(
                    nct_id=nct_id,
                    protocol_text=protocol_text,
                    sap_text=sap_text
                )

                # Extract metadata
                pair.phase = self._classify_phase(protocol_text + sap_text)
                pair.endpoint_type = self._classify_endpoint(protocol_text + sap_text)
                pair.therapeutic_area = self._classify_therapeutic_area(protocol_text)

                # Extract SAP sections
                pair.sap_sections = self._extract_sections(sap_text)

                # Calculate quality score
                pair.quality_score = self._calculate_quality_score(pair)

                # Add to database
                idx = len(self.pairs)
                self.pairs.append(pair)

                # Update indices
                if pair.endpoint_type:
                    self.by_endpoint[pair.endpoint_type].append(idx)
                if pair.phase:
                    self.by_phase[pair.phase].append(idx)
                if pair.therapeutic_area:
                    self.by_therapeutic_area[pair.therapeutic_area].append(idx)

                loaded += 1

            except Exception as e:
                print(f"Error loading {nct_id}: {e}")
                continue

        print(f"Loaded {loaded} protocol-SAP pairs")
        return loaded

    def compute_embeddings(self) -> int:
        """
        Compute embeddings for all pairs.

        Returns:
            Number of embeddings computed
        """
        if self.embedding_model is None:
            print("WARNING: Embedding model not available")
            return 0

        computed = 0
        for pair in self.pairs:
            try:
                # Create summary text for embedding
                protocol_summary = pair.protocol_text[:3000]
                sap_summary = pair.sap_text[:3000]

                pair.protocol_embedding = self.embedding_model.encode(protocol_summary)
                pair.sap_embedding = self.embedding_model.encode(sap_summary)
                computed += 1

            except Exception as e:
                print(f"Error computing embedding for {pair.nct_id}: {e}")

        print(f"Computed embeddings for {computed} pairs")
        return computed

    def _classify_phase(self, text: str) -> str:
        """Classify study phase from text"""
        text_lower = text.lower()

        for phase, patterns in self.PHASE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return phase

        return ""

    def _classify_endpoint(self, text: str) -> str:
        """Classify primary endpoint type from text"""
        text_lower = text.lower()
        scores = defaultdict(int)

        for endpoint, patterns in self.ENDPOINT_PATTERNS.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                scores[endpoint] += matches

        if not scores:
            return ""

        return max(scores, key=scores.get)

    def _classify_therapeutic_area(self, text: str) -> str:
        """Classify therapeutic area from text"""
        text_lower = text.lower()

        ta_patterns = {
            "Oncology": [r'cancer', r'tumor', r'carcinoma', r'malignant', r'oncology'],
            "Cardiovascular": [r'cardiovascular', r'cardiac', r'heart', r'coronary'],
            "CNS": [r'neurological', r'cns', r'brain', r'alzheimer', r'parkinson'],
            "Infectious Disease": [r'infectious', r'infection', r'viral', r'bacterial'],
            "Metabolic": [r'diabetes', r'metabolic', r'glucose', r'insulin'],
            "Respiratory": [r'respiratory', r'pulmonary', r'lung', r'asthma'],
            "Immunology": [r'immunology', r'autoimmune', r'rheumatoid'],
        }

        scores = defaultdict(int)
        for ta, patterns in ta_patterns.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                scores[ta] += matches

        if not scores:
            return "Other"

        return max(scores, key=scores.get)

    def _extract_sections(self, sap_text: str) -> Dict[str, str]:
        """Extract sections from SAP text"""
        sections = {}

        for section_name, patterns in self.SECTION_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, sap_text, re.IGNORECASE | re.DOTALL)
                if match:
                    content = match.group(1).strip()
                    if len(content) > 100:  # Only keep substantial sections
                        sections[section_name] = content[:5000]  # Limit size
                    break

        return sections

    def _calculate_quality_score(self, pair: ProcessedSAPPair) -> float:
        """Calculate quality score for a pair"""
        score = 0.5  # Base score

        # Bonus for having many sections
        score += min(len(pair.sap_sections) * 0.05, 0.25)

        # Bonus for substantial content
        if len(pair.sap_text) > 10000:
            score += 0.1
        if len(pair.sap_text) > 20000:
            score += 0.1

        # Bonus for having metadata
        if pair.phase:
            score += 0.02
        if pair.endpoint_type:
            score += 0.02
        if pair.therapeutic_area:
            score += 0.01

        return min(score, 1.0)

    def find_similar(
        self,
        target_protocol: ParsedProtocol,
        n: int = 3,
        diversity_weight: float = 0.3
    ) -> List[ProcessedSAPPair]:
        """
        Find similar protocol-SAP pairs using MMR.

        Args:
            target_protocol: Target protocol to match
            n: Number of examples to return
            diversity_weight: Weight for diversity (0=pure similarity, 1=pure diversity)

        Returns:
            List of similar pairs
        """
        # Filter candidates by hard constraints
        candidates = self._filter_candidates(target_protocol)

        if not candidates:
            candidates = list(range(len(self.pairs)))

        if len(candidates) <= n:
            return [self.pairs[i] for i in candidates[:n]]

        # If we have embeddings, use similarity-based selection
        if self.embedding_model is not None and all(
            self.pairs[i].protocol_embedding is not None for i in candidates[:10]
        ):
            return self._mmr_selection(target_protocol, candidates, n, diversity_weight)

        # Fallback: score-based selection
        scored = [
            (i, self._score_match(target_protocol, self.pairs[i]))
            for i in candidates
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [self.pairs[i] for i, _ in scored[:n]]

    def _filter_candidates(self, target: ParsedProtocol) -> List[int]:
        """Filter candidates by hard constraints"""
        candidates = set(range(len(self.pairs)))

        # Filter by endpoint type (strongest constraint)
        if target.primary_estimand:
            endpoint_type = target.primary_estimand.variable_type
            if hasattr(endpoint_type, 'value'):
                endpoint_type = endpoint_type.value
            if endpoint_type in self.by_endpoint:
                endpoint_candidates = set(self.by_endpoint[endpoint_type])
                if endpoint_candidates:
                    candidates &= endpoint_candidates

        return list(candidates)

    def _score_match(self, target: ParsedProtocol, pair: ProcessedSAPPair) -> float:
        """Score how well a pair matches the target protocol"""
        score = pair.quality_score * 0.3  # Base on quality

        # Endpoint match
        if target.primary_estimand:
            target_endpoint = target.primary_estimand.variable_type
            if hasattr(target_endpoint, 'value'):
                target_endpoint = target_endpoint.value
            if target_endpoint == pair.endpoint_type:
                score += 0.4

        # Phase match
        target_phase = target.phase.value if hasattr(target.phase, 'value') else str(target.phase)
        if target_phase in pair.phase:
            score += 0.2

        # Therapeutic area match
        if target.therapeutic_area == pair.therapeutic_area:
            score += 0.1

        return score

    def _mmr_selection(
        self,
        target: ParsedProtocol,
        candidates: List[int],
        n: int,
        diversity_weight: float
    ) -> List[ProcessedSAPPair]:
        """Select examples using Maximal Marginal Relevance"""
        # Get target embedding
        target_text = target.to_text() if hasattr(target, 'to_text') else str(target.nct_id)
        target_embedding = self.embedding_model.encode(target_text)

        # Calculate similarities to target
        similarities = {}
        for idx in candidates:
            pair = self.pairs[idx]
            if pair.protocol_embedding is not None:
                sim = np.dot(target_embedding, pair.protocol_embedding) / (
                    np.linalg.norm(target_embedding) * np.linalg.norm(pair.protocol_embedding) + 1e-8
                )
                similarities[idx] = sim

        # MMR selection
        selected = []
        selected_embeddings = []

        while len(selected) < n and similarities:
            # Calculate MMR scores
            mmr_scores = {}
            for idx, sim in similarities.items():
                if not selected_embeddings:
                    diversity = 0
                else:
                    pair_emb = self.pairs[idx].protocol_embedding
                    max_sim_to_selected = max(
                        np.dot(pair_emb, sel_emb) / (
                            np.linalg.norm(pair_emb) * np.linalg.norm(sel_emb) + 1e-8
                        )
                        for sel_emb in selected_embeddings
                    )
                    diversity = max_sim_to_selected

                mmr = (1 - diversity_weight) * sim - diversity_weight * diversity
                mmr_scores[idx] = mmr

            # Select best
            best_idx = max(mmr_scores, key=mmr_scores.get)
            selected.append(best_idx)
            selected_embeddings.append(self.pairs[best_idx].protocol_embedding)
            del similarities[best_idx]

        return [self.pairs[idx] for idx in selected]

    def get_section_examples(
        self,
        section_name: str,
        target_protocol: ParsedProtocol,
        n: int = 2
    ) -> List[str]:
        """
        Get example sections from similar SAPs.

        Args:
            section_name: Name of section to retrieve
            target_protocol: Target protocol for similarity
            n: Number of examples

        Returns:
            List of example section contents
        """
        similar_pairs = self.find_similar(target_protocol, n=n*2)

        examples = []
        for pair in similar_pairs:
            if section_name in pair.sap_sections:
                examples.append(pair.sap_sections[section_name])
                if len(examples) >= n:
                    break

        return examples

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        return {
            "total_pairs": len(self.pairs),
            "by_endpoint": {k: len(v) for k, v in self.by_endpoint.items()},
            "by_phase": {k: len(v) for k, v in self.by_phase.items()},
            "by_therapeutic_area": {k: len(v) for k, v in self.by_therapeutic_area.items()},
            "with_embeddings": sum(1 for p in self.pairs if p.protocol_embedding is not None),
            "avg_quality_score": sum(p.quality_score for p in self.pairs) / len(self.pairs) if self.pairs else 0
        }


class FewShotExampleSelector:
    """
    Selector for few-shot examples during SAP generation.
    Wrapper around SAPPairDatabase with caching.
    """

    def __init__(self, database: SAPPairDatabase = None, data_dir: str = None):
        """
        Initialize the selector.

        Args:
            database: Pre-initialized database
            data_dir: Directory for loading pairs
        """
        self.database = database or SAPPairDatabase(data_dir=data_dir)

    def get_examples(
        self,
        target_protocol: ParsedProtocol,
        n_examples: int = 3
    ) -> Dict[str, List[str]]:
        """
        Get few-shot examples for all sections.

        Args:
            target_protocol: Target protocol
            n_examples: Number of examples per section

        Returns:
            Dictionary mapping section names to example lists
        """
        examples = {}

        for section_name in self.database.SECTION_PATTERNS.keys():
            section_examples = self.database.get_section_examples(
                section_name=section_name,
                target_protocol=target_protocol,
                n=n_examples
            )
            if section_examples:
                examples[section_name] = section_examples

        return examples

    def get_full_sap_examples(
        self,
        target_protocol: ParsedProtocol,
        n: int = 2
    ) -> List[str]:
        """
        Get full SAP examples for reference.

        Args:
            target_protocol: Target protocol
            n: Number of examples

        Returns:
            List of full SAP texts
        """
        similar_pairs = self.database.find_similar(target_protocol, n=n)
        return [pair.sap_text for pair in similar_pairs]


# Factory functions
def create_sap_database(data_dir: str = None) -> SAPPairDatabase:
    """Create a SAP pair database"""
    return SAPPairDatabase(data_dir=data_dir)


def create_few_shot_selector(data_dir: str = None) -> FewShotExampleSelector:
    """Create a few-shot example selector"""
    return FewShotExampleSelector(data_dir=data_dir)
