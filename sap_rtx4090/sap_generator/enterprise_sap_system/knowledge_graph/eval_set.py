#!/usr/bin/env python3
"""
SAP Eval Set Framework
======================

Compares generated SAPs against reference (ground truth) SAPs.

This is the proper eval set approach:
1. Load protocol + reference SAP pairs from ground_truth/
2. Generate SAP from protocol
3. Compare generated vs reference
4. Score accuracy, completeness, factual correctness

Usage:
    python eval_set.py --list                          # List available eval pairs
    python eval_set.py --run NCT03422848              # Run single eval
    python eval_set.py --run all                       # Run all evals
    python eval_set.py --run all --limit 10           # Run first 10
    python eval_set.py --run all --export results.json

Author: SAP Generation System
"""

import json
import os
import sys
import re
import time
import difflib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import Counter

# =============================================================================
# CONFIGURATION
# =============================================================================

GROUND_TRUTH_DIR = Path(__file__).parent.parent.parent / "data" / "ground_truth"

# SAP section patterns to extract and compare
SAP_SECTIONS = [
    ("introduction", r"(?:1\.|introduction)", "Introduction"),
    ("study_design", r"(?:2\.|study design)", "Study Design"),
    ("sample_size", r"(?:sample size|power)", "Sample Size"),
    ("objectives", r"(?:objectives|aims)", "Objectives"),
    ("endpoints", r"(?:endpoints|outcomes)", "Endpoints/Outcomes"),
    ("populations", r"(?:populations|analysis sets)", "Analysis Populations"),
    ("efficacy", r"(?:efficacy|primary analysis)", "Efficacy Analysis"),
    ("safety", r"(?:safety)", "Safety Analysis"),
    ("missing_data", r"(?:missing data)", "Missing Data"),
    ("sensitivity", r"(?:sensitivity)", "Sensitivity Analysis"),
    ("subgroups", r"(?:subgroup)", "Subgroup Analysis"),
]

# Key facts to extract and compare
KEY_FACT_PATTERNS = {
    "primary_endpoint": [
        r"primary\s+(?:endpoint|outcome|efficacy)[:\s]+([^\n.]+)",
        r"primary[:\s]+([^\n.]+)"
    ],
    "sample_size": [
        r"sample\s+size[:\s]+(\d+)",
        r"(?:n\s*=\s*|enroll[^\d]*?)(\d+)\s+(?:subjects|patients|participants)"
    ],
    "alpha": [
        r"(?:alpha|significance\s+level|type\s+I\s+error)[:\s=]+(\d+\.?\d*%?)",
        r"two-sided\s+(\d+\.?\d*%?)"
    ],
    "power": [
        r"(?:power)[:\s=]+(\d+\.?\d*%?)",
    ],
    "randomization": [
        r"randomiz(?:ed|ation)[^\d]*(\d+:\d+)",
    ],
    "statistical_method": [
        r"(?:analyzed|analysis)[^\n]*(?:using|by)\s+([^\n.]+)",
        r"(ANCOVA|ANOVA|t-test|log-rank|Cox|Kaplan-Meier|chi-square|Fisher)",
    ],
    "confidence_interval": [
        r"(\d+%?)\s+confidence\s+interval",
    ],
    "itt_population": [
        r"(intent(?:ion)?-to-treat|ITT)",
    ],
    "per_protocol": [
        r"(per-protocol|PP)",
    ],
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class SectionComparison:
    """Comparison result for a single section."""
    section_name: str
    found_in_reference: bool
    found_in_generated: bool
    reference_length: int
    generated_length: int
    similarity_score: float  # 0-100, based on text similarity
    key_phrases_matched: List[str]
    key_phrases_missing: List[str]


@dataclass
class FactComparison:
    """Comparison of a specific fact."""
    fact_name: str
    reference_value: Optional[str]
    generated_value: Optional[str]
    match: bool  # True if values match or are semantically equivalent


@dataclass
class EvalResult:
    """Complete evaluation result for one protocol/SAP pair."""
    nct_id: str
    timestamp: str

    # Timing
    generation_time_seconds: float
    evaluation_time_seconds: float

    # Overall scores
    overall_score: float  # 0-100
    section_coverage_score: float  # 0-100
    content_similarity_score: float  # 0-100
    fact_accuracy_score: float  # 0-100

    # Section-level results
    section_comparisons: List[SectionComparison]
    sections_in_reference: int
    sections_in_generated: int
    sections_matched: int

    # Fact-level results
    fact_comparisons: List[FactComparison]
    facts_matched: int
    facts_total: int

    # Content metrics
    reference_word_count: int
    generated_word_count: int

    # Statistical term coverage
    statistical_terms_in_reference: List[str]
    statistical_terms_in_generated: List[str]
    statistical_terms_matched: List[str]
    statistical_terms_missing: List[str]

    # Raw content (truncated for storage)
    reference_preview: str
    generated_preview: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class EvalSetSummary:
    """Summary of running the full eval set."""
    timestamp: str
    total_cases: int
    successful_cases: int
    failed_cases: int

    # Aggregate scores
    avg_overall_score: float
    avg_section_coverage: float
    avg_content_similarity: float
    avg_fact_accuracy: float

    # Score distribution
    score_distribution: Dict[str, int]  # "0-20", "20-40", etc.

    # Common issues
    most_missed_sections: List[Tuple[str, int]]
    most_missed_facts: List[Tuple[str, int]]

    # Individual results
    results: List[EvalResult]


# =============================================================================
# EVAL SET LOADER
# =============================================================================

class EvalSetLoader:
    """Loads protocol/SAP pairs from ground_truth directory."""

    def __init__(self, ground_truth_dir: Path = GROUND_TRUTH_DIR):
        self.ground_truth_dir = Path(ground_truth_dir)

    def list_available(self) -> List[str]:
        """List all available NCT IDs with both protocol and SAP."""
        nct_ids = set()

        for f in self.ground_truth_dir.glob("*_protocol.txt"):
            nct_id = f.stem.replace("_protocol", "")
            sap_path = self.ground_truth_dir / f"{nct_id}_sap.txt"
            if sap_path.exists():
                nct_ids.add(nct_id)

        return sorted(nct_ids)

    def load(self, nct_id: str) -> Tuple[str, str]:
        """Load protocol and reference SAP for an NCT ID."""
        protocol_path = self.ground_truth_dir / f"{nct_id}_protocol.txt"
        sap_path = self.ground_truth_dir / f"{nct_id}_sap.txt"

        if not protocol_path.exists():
            raise FileNotFoundError(f"Protocol not found: {protocol_path}")
        if not sap_path.exists():
            raise FileNotFoundError(f"SAP not found: {sap_path}")

        protocol = protocol_path.read_text(encoding='utf-8', errors='ignore')
        sap = sap_path.read_text(encoding='utf-8', errors='ignore')

        return protocol, sap

    def get_metadata(self, nct_id: str) -> Dict[str, Any]:
        """Extract metadata from protocol."""
        protocol, _ = self.load(nct_id)

        metadata = {"nct_id": nct_id}

        # Extract key fields
        patterns = {
            "phase": r"Phase:\s*(.+)",
            "indication": r"(?:Condition|Disease):\s*(.+)",
            "design": r"(?:Study Type|Design):\s*(.+)",
            "enrollment": r"Enrollment:\s*(\d+)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, protocol, re.IGNORECASE)
            if match:
                metadata[key] = match.group(1).strip()

        return metadata


# =============================================================================
# COMPARISON ENGINE
# =============================================================================

class SAPComparator:
    """Compares generated SAP against reference SAP."""

    # Statistical terms to look for
    STATISTICAL_TERMS = [
        "intent-to-treat", "itt", "per-protocol", "pp",
        "full analysis set", "safety population",
        "ancova", "anova", "t-test", "chi-square", "fisher",
        "log-rank", "cox", "kaplan-meier", "hazard ratio",
        "confidence interval", "p-value", "alpha", "power",
        "two-sided", "one-sided", "significance",
        "mixed model", "mmrm", "locf", "multiple imputation",
        "sensitivity analysis", "subgroup analysis",
        "interim analysis", "stopping rule", "futility",
        "multiplicity", "adjustment", "bonferroni", "hochberg",
    ]

    def __init__(self):
        pass

    def extract_sections(self, text: str) -> Dict[str, str]:
        """Extract sections from SAP text."""
        sections = {}
        text_lower = text.lower()

        for section_id, pattern, name in SAP_SECTIONS:
            # Find section header
            match = re.search(pattern, text_lower)
            if match:
                start = match.end()

                # Find next section or end
                end = len(text)
                for other_id, other_pattern, _ in SAP_SECTIONS:
                    if other_id == section_id:
                        continue
                    next_match = re.search(other_pattern, text_lower[start:])
                    if next_match:
                        end = min(end, start + next_match.start())

                content = text[start:end].strip()
                if len(content) > 50:  # Only count if substantial
                    sections[section_id] = content

        return sections

    def extract_facts(self, text: str) -> Dict[str, str]:
        """Extract key facts from SAP text."""
        facts = {}
        text_lower = text.lower()

        for fact_name, patterns in KEY_FACT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    facts[fact_name] = match.group(1).strip()
                    break

        return facts

    def extract_statistical_terms(self, text: str) -> List[str]:
        """Find statistical terms in text."""
        text_lower = text.lower()
        found = []

        for term in self.STATISTICAL_TERMS:
            if term in text_lower:
                found.append(term)

        return found

    def compute_text_similarity(self, text1: str, text2: str) -> float:
        """Compute similarity between two texts (0-100)."""
        if not text1 or not text2:
            return 0.0

        # Normalize texts
        text1 = ' '.join(text1.lower().split())
        text2 = ' '.join(text2.lower().split())

        # Use SequenceMatcher for similarity
        ratio = difflib.SequenceMatcher(None, text1, text2).ratio()
        return ratio * 100

    def compare_sections(
        self,
        ref_sections: Dict[str, str],
        gen_sections: Dict[str, str]
    ) -> List[SectionComparison]:
        """Compare sections between reference and generated SAP."""
        results = []

        all_section_ids = set(ref_sections.keys()) | set(gen_sections.keys())

        for section_id in all_section_ids:
            section_name = next(
                (name for sid, _, name in SAP_SECTIONS if sid == section_id),
                section_id
            )

            ref_content = ref_sections.get(section_id, "")
            gen_content = gen_sections.get(section_id, "")

            # Compute similarity
            similarity = self.compute_text_similarity(ref_content, gen_content)

            # Extract key phrases (words 4+ chars that appear in both)
            ref_words = set(w for w in re.findall(r'\b\w{4,}\b', ref_content.lower()))
            gen_words = set(w for w in re.findall(r'\b\w{4,}\b', gen_content.lower()))

            matched = list(ref_words & gen_words)[:20]  # Top 20
            missing = list(ref_words - gen_words)[:20]

            results.append(SectionComparison(
                section_name=section_name,
                found_in_reference=bool(ref_content),
                found_in_generated=bool(gen_content),
                reference_length=len(ref_content),
                generated_length=len(gen_content),
                similarity_score=round(similarity, 1),
                key_phrases_matched=matched,
                key_phrases_missing=missing
            ))

        return results

    def compare_facts(
        self,
        ref_facts: Dict[str, str],
        gen_facts: Dict[str, str]
    ) -> List[FactComparison]:
        """Compare extracted facts."""
        results = []

        all_fact_names = set(ref_facts.keys()) | set(gen_facts.keys())

        for fact_name in all_fact_names:
            ref_value = ref_facts.get(fact_name)
            gen_value = gen_facts.get(fact_name)

            # Check if values match (with some normalization)
            match = False
            if ref_value and gen_value:
                # Normalize for comparison
                ref_norm = re.sub(r'[^\w\d]', '', ref_value.lower())
                gen_norm = re.sub(r'[^\w\d]', '', gen_value.lower())
                match = ref_norm == gen_norm or ref_norm in gen_norm or gen_norm in ref_norm

            results.append(FactComparison(
                fact_name=fact_name,
                reference_value=ref_value,
                generated_value=gen_value,
                match=match
            ))

        return results

    def compare(self, reference_sap: str, generated_sap: str) -> Dict[str, Any]:
        """
        Full comparison between reference and generated SAP.

        Returns dict with all comparison metrics.
        """
        # Extract components
        ref_sections = self.extract_sections(reference_sap)
        gen_sections = self.extract_sections(generated_sap)

        ref_facts = self.extract_facts(reference_sap)
        gen_facts = self.extract_facts(generated_sap)

        ref_terms = self.extract_statistical_terms(reference_sap)
        gen_terms = self.extract_statistical_terms(generated_sap)

        # Compare
        section_comparisons = self.compare_sections(ref_sections, gen_sections)
        fact_comparisons = self.compare_facts(ref_facts, gen_facts)

        # Calculate scores
        sections_matched = sum(
            1 for sc in section_comparisons
            if sc.found_in_reference and sc.found_in_generated
        )
        sections_in_ref = sum(1 for sc in section_comparisons if sc.found_in_reference)

        section_coverage = (sections_matched / sections_in_ref * 100) if sections_in_ref > 0 else 0

        content_similarity = (
            sum(sc.similarity_score for sc in section_comparisons if sc.found_in_reference)
            / max(sections_in_ref, 1)
        )

        facts_matched = sum(1 for fc in fact_comparisons if fc.match)
        facts_total = len(fact_comparisons)
        fact_accuracy = (facts_matched / facts_total * 100) if facts_total > 0 else 0

        # Statistical terms
        terms_matched = list(set(ref_terms) & set(gen_terms))
        terms_missing = list(set(ref_terms) - set(gen_terms))

        # Overall score (weighted average)
        overall_score = (
            section_coverage * 0.3 +
            content_similarity * 0.4 +
            fact_accuracy * 0.3
        )

        return {
            "overall_score": round(overall_score, 1),
            "section_coverage_score": round(section_coverage, 1),
            "content_similarity_score": round(content_similarity, 1),
            "fact_accuracy_score": round(fact_accuracy, 1),
            "section_comparisons": section_comparisons,
            "sections_in_reference": sections_in_ref,
            "sections_in_generated": sum(1 for sc in section_comparisons if sc.found_in_generated),
            "sections_matched": sections_matched,
            "fact_comparisons": fact_comparisons,
            "facts_matched": facts_matched,
            "facts_total": facts_total,
            "reference_word_count": len(reference_sap.split()),
            "generated_word_count": len(generated_sap.split()),
            "statistical_terms_in_reference": ref_terms,
            "statistical_terms_in_generated": gen_terms,
            "statistical_terms_matched": terms_matched,
            "statistical_terms_missing": terms_missing,
        }


# =============================================================================
# EVAL SET RUNNER
# =============================================================================

class EvalSetRunner:
    """Runs evaluation across the entire eval set."""

    def __init__(
        self,
        ground_truth_dir: Path = GROUND_TRUTH_DIR,
        generator=None,
        verbose: bool = False
    ):
        self.loader = EvalSetLoader(ground_truth_dir)
        self.comparator = SAPComparator()
        self.generator = generator
        self.verbose = verbose
        self.results: List[EvalResult] = []

    def generate_sap(self, protocol: str) -> str:
        """Generate SAP from protocol using configured generator."""
        if self.generator is None:
            raise ValueError("No generator configured. Pass generator to __init__ or use compare_only mode.")

        # Try different generator interfaces
        if hasattr(self.generator, 'generate'):
            result = self.generator.generate(protocol)
            if isinstance(result, dict):
                return result.get('sap_document', '') or result.get('content', '')
            return str(result)
        elif hasattr(self.generator, 'generate_full_sap'):
            return self.generator.generate_full_sap(protocol)
        elif callable(self.generator):
            return self.generator(protocol)
        else:
            raise ValueError(f"Unknown generator type: {type(self.generator)}")

    def run_single(
        self,
        nct_id: str,
        generated_sap: str = None
    ) -> EvalResult:
        """
        Run evaluation for a single NCT ID.

        Args:
            nct_id: The NCT ID to evaluate
            generated_sap: Pre-generated SAP (if None, will generate)
        """
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"Evaluating: {nct_id}")
            print(f"{'='*60}")

        # Load data
        protocol, reference_sap = self.loader.load(nct_id)

        # Generate if needed
        gen_start = time.time()
        if generated_sap is None:
            if self.verbose:
                print("  Generating SAP...")
            generated_sap = self.generate_sap(protocol)
        gen_time = time.time() - gen_start

        # Compare
        eval_start = time.time()
        comparison = self.comparator.compare(reference_sap, generated_sap)
        eval_time = time.time() - eval_start

        if self.verbose:
            print(f"  Overall Score: {comparison['overall_score']:.1f}/100")
            print(f"  Section Coverage: {comparison['section_coverage_score']:.1f}%")
            print(f"  Content Similarity: {comparison['content_similarity_score']:.1f}%")
            print(f"  Fact Accuracy: {comparison['fact_accuracy_score']:.1f}%")

        result = EvalResult(
            nct_id=nct_id,
            timestamp=datetime.now().isoformat(),
            generation_time_seconds=round(gen_time, 2),
            evaluation_time_seconds=round(eval_time, 2),
            overall_score=comparison['overall_score'],
            section_coverage_score=comparison['section_coverage_score'],
            content_similarity_score=comparison['content_similarity_score'],
            fact_accuracy_score=comparison['fact_accuracy_score'],
            section_comparisons=comparison['section_comparisons'],
            sections_in_reference=comparison['sections_in_reference'],
            sections_in_generated=comparison['sections_in_generated'],
            sections_matched=comparison['sections_matched'],
            fact_comparisons=comparison['fact_comparisons'],
            facts_matched=comparison['facts_matched'],
            facts_total=comparison['facts_total'],
            reference_word_count=comparison['reference_word_count'],
            generated_word_count=comparison['generated_word_count'],
            statistical_terms_in_reference=comparison['statistical_terms_in_reference'],
            statistical_terms_in_generated=comparison['statistical_terms_in_generated'],
            statistical_terms_matched=comparison['statistical_terms_matched'],
            statistical_terms_missing=comparison['statistical_terms_missing'],
            reference_preview=reference_sap[:500],
            generated_preview=generated_sap[:500] if generated_sap else ""
        )

        self.results.append(result)
        return result

    def run_all(
        self,
        nct_ids: List[str] = None,
        limit: int = None,
        generated_saps: Dict[str, str] = None
    ) -> EvalSetSummary:
        """
        Run evaluation across multiple NCT IDs.

        Args:
            nct_ids: List of NCT IDs to evaluate (None = all available)
            limit: Maximum number to evaluate
            generated_saps: Dict mapping NCT ID to pre-generated SAP
        """
        if nct_ids is None:
            nct_ids = self.loader.list_available()

        if limit:
            nct_ids = nct_ids[:limit]

        print(f"\nRunning eval set: {len(nct_ids)} cases")
        print("-" * 60)

        self.results = []
        generated_saps = generated_saps or {}

        for i, nct_id in enumerate(nct_ids, 1):
            print(f"[{i}/{len(nct_ids)}] {nct_id}...", end=" ")

            try:
                gen_sap = generated_saps.get(nct_id)
                result = self.run_single(nct_id, generated_sap=gen_sap)
                print(f"Score: {result.overall_score:.1f}")
            except Exception as e:
                print(f"ERROR: {e}")

        return self.summarize()

    def summarize(self) -> EvalSetSummary:
        """Generate summary of all results."""
        if not self.results:
            raise ValueError("No results to summarize")

        successful = [r for r in self.results if r.overall_score >= 0]

        # Score distribution
        distribution = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
        for r in successful:
            if r.overall_score < 20:
                distribution["0-20"] += 1
            elif r.overall_score < 40:
                distribution["20-40"] += 1
            elif r.overall_score < 60:
                distribution["40-60"] += 1
            elif r.overall_score < 80:
                distribution["60-80"] += 1
            else:
                distribution["80-100"] += 1

        # Most missed sections
        section_misses = Counter()
        for r in successful:
            for sc in r.section_comparisons:
                if sc.found_in_reference and not sc.found_in_generated:
                    section_misses[sc.section_name] += 1

        # Most missed facts
        fact_misses = Counter()
        for r in successful:
            for fc in r.fact_comparisons:
                if fc.reference_value and not fc.match:
                    fact_misses[fc.fact_name] += 1

        summary = EvalSetSummary(
            timestamp=datetime.now().isoformat(),
            total_cases=len(self.results),
            successful_cases=len(successful),
            failed_cases=len(self.results) - len(successful),
            avg_overall_score=sum(r.overall_score for r in successful) / len(successful) if successful else 0,
            avg_section_coverage=sum(r.section_coverage_score for r in successful) / len(successful) if successful else 0,
            avg_content_similarity=sum(r.content_similarity_score for r in successful) / len(successful) if successful else 0,
            avg_fact_accuracy=sum(r.fact_accuracy_score for r in successful) / len(successful) if successful else 0,
            score_distribution=distribution,
            most_missed_sections=section_misses.most_common(5),
            most_missed_facts=fact_misses.most_common(5),
            results=self.results
        )

        return summary

    def print_summary(self, summary: EvalSetSummary = None):
        """Print summary to console."""
        if summary is None:
            summary = self.summarize()

        print(f"\n{'='*60}")
        print("EVAL SET SUMMARY")
        print(f"{'='*60}")
        print(f"Total Cases: {summary.total_cases}")
        print(f"Successful: {summary.successful_cases}")
        print(f"Failed: {summary.failed_cases}")

        print(f"\nAggregate Scores:")
        print(f"  Overall:            {summary.avg_overall_score:.1f}/100")
        print(f"  Section Coverage:   {summary.avg_section_coverage:.1f}%")
        print(f"  Content Similarity: {summary.avg_content_similarity:.1f}%")
        print(f"  Fact Accuracy:      {summary.avg_fact_accuracy:.1f}%")

        print(f"\nScore Distribution:")
        for bucket, count in summary.score_distribution.items():
            bar = "█" * count
            print(f"  {bucket}: {bar} ({count})")

        if summary.most_missed_sections:
            print(f"\nMost Missed Sections:")
            for section, count in summary.most_missed_sections:
                print(f"  - {section}: {count} times")

        if summary.most_missed_facts:
            print(f"\nMost Missed Facts:")
            for fact, count in summary.most_missed_facts:
                print(f"  - {fact}: {count} times")

        # Top/bottom performers
        sorted_results = sorted(self.results, key=lambda r: r.overall_score, reverse=True)

        print(f"\nTop 5 Performers:")
        for r in sorted_results[:5]:
            print(f"  {r.nct_id}: {r.overall_score:.1f}")

        print(f"\nBottom 5 Performers:")
        for r in sorted_results[-5:]:
            print(f"  {r.nct_id}: {r.overall_score:.1f}")

    def export(self, filepath: str, summary: EvalSetSummary = None):
        """Export results to JSON."""
        if summary is None:
            summary = self.summarize()

        # Convert to serializable dict
        output = {
            "timestamp": summary.timestamp,
            "total_cases": summary.total_cases,
            "successful_cases": summary.successful_cases,
            "failed_cases": summary.failed_cases,
            "avg_overall_score": round(summary.avg_overall_score, 2),
            "avg_section_coverage": round(summary.avg_section_coverage, 2),
            "avg_content_similarity": round(summary.avg_content_similarity, 2),
            "avg_fact_accuracy": round(summary.avg_fact_accuracy, 2),
            "score_distribution": summary.score_distribution,
            "most_missed_sections": summary.most_missed_sections,
            "most_missed_facts": summary.most_missed_facts,
            "results": []
        }

        for r in summary.results:
            result_dict = {
                "nct_id": r.nct_id,
                "overall_score": r.overall_score,
                "section_coverage_score": r.section_coverage_score,
                "content_similarity_score": r.content_similarity_score,
                "fact_accuracy_score": r.fact_accuracy_score,
                "sections_matched": r.sections_matched,
                "sections_in_reference": r.sections_in_reference,
                "facts_matched": r.facts_matched,
                "facts_total": r.facts_total,
                "statistical_terms_matched": len(r.statistical_terms_matched),
                "statistical_terms_missing": r.statistical_terms_missing[:5],
                "generation_time_seconds": r.generation_time_seconds,
            }
            output["results"].append(result_dict)

        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\nResults exported to {filepath}")


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="SAP Eval Set Framework")
    parser.add_argument("--list", "-l", action="store_true", help="List available eval pairs")
    parser.add_argument("--run", "-r", type=str, help="Run eval: NCT ID or 'all'")
    parser.add_argument("--limit", type=int, help="Limit number of cases to run")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--export", "-e", type=str, help="Export results to JSON")
    parser.add_argument("--compare-only", action="store_true",
                       help="Compare existing SAPs without generation (requires --generated-dir)")
    parser.add_argument("--generated-dir", type=str,
                       help="Directory containing pre-generated SAPs (NCT*_generated.txt)")

    args = parser.parse_args()

    loader = EvalSetLoader()

    if args.list:
        available = loader.list_available()
        print(f"\nAvailable eval pairs: {len(available)}\n")
        for nct_id in available:
            try:
                metadata = loader.get_metadata(nct_id)
                phase = metadata.get('phase', 'N/A')
                print(f"  {nct_id}  (Phase: {phase})")
            except:
                print(f"  {nct_id}")
        return

    if args.run:
        # Load pre-generated SAPs if provided
        generated_saps = {}
        if args.generated_dir:
            gen_dir = Path(args.generated_dir)
            for f in gen_dir.glob("*_generated.txt"):
                nct_id = f.stem.replace("_generated", "")
                generated_saps[nct_id] = f.read_text(encoding='utf-8', errors='ignore')
            print(f"Loaded {len(generated_saps)} pre-generated SAPs")

        # For compare-only mode, we don't need a generator
        generator = None
        if not args.compare_only and not generated_saps:
            # Try to load the generation pipeline
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                from enterprise_sap_system.core.constrained_pipeline import ConstrainedSAPPipeline
                generator = ConstrainedSAPPipeline()
                print("Generator loaded successfully")
            except Exception as e:
                print(f"Could not load generator: {e}")
                print("Use --compare-only with --generated-dir to compare pre-generated SAPs")
                return

        runner = EvalSetRunner(generator=generator, verbose=args.verbose)

        if args.run == "all":
            summary = runner.run_all(limit=args.limit, generated_saps=generated_saps)
        else:
            runner.run_single(args.run, generated_sap=generated_saps.get(args.run))
            summary = runner.summarize()

        runner.print_summary(summary)

        if args.export:
            runner.export(args.export, summary)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
