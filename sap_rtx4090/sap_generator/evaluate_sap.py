#!/usr/bin/env python3
"""
SAP Evaluation Script
=====================
Compares generated SAPs against ground truth real-world SAPs.

Usage:
    python evaluate_sap.py --nct NCT03422848
    python evaluate_sap.py --all
    python evaluate_sap.py --generated path/to/generated_sap.txt --ground-truth NCT03422848
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


@dataclass
class SAPSection:
    """A section from a SAP document"""
    name: str
    content: str
    line_count: int


@dataclass
class EvaluationResult:
    """Results of SAP evaluation"""
    nct_id: str
    ground_truth_lines: int
    generated_lines: int

    # Section coverage
    sections_in_ground_truth: List[str]
    sections_in_generated: List[str]
    sections_matched: List[str]
    sections_missing: List[str]
    section_coverage_pct: float

    # Content metrics
    keyword_overlap_pct: float
    statistical_terms_found: List[str]
    statistical_terms_missing: List[str]

    # Structure metrics
    has_primary_endpoint: bool
    has_secondary_endpoint: bool
    has_sample_size: bool
    has_analysis_populations: bool
    has_statistical_methods: bool
    has_missing_data: bool

    # Quality score (0-100)
    overall_score: float

    def to_dict(self) -> dict:
        return asdict(self)


class SAPEvaluator:
    """Evaluates generated SAPs against ground truth"""

    # Key SAP sections to look for
    SAP_SECTIONS = [
        "introduction",
        "study design",
        "study objectives",
        "endpoints",
        "primary endpoint",
        "secondary endpoint",
        "sample size",
        "analysis populations",
        "statistical methods",
        "primary analysis",
        "secondary analysis",
        "sensitivity analysis",
        "subgroup analysis",
        "missing data",
        "interim analysis",
        "multiplicity",
        "safety analysis",
        "tables",
        "figures",
        "appendix",
    ]

    # Statistical terms that should appear
    STATISTICAL_TERMS = [
        "intent-to-treat", "itt", "per-protocol", "full analysis set",
        "modified intent-to-treat", "mitt", "safety population",
        "primary efficacy", "type i error", "alpha", "power",
        "confidence interval", "p-value", "hypothesis",
        "null hypothesis", "alternative hypothesis",
        "two-sided", "one-sided", "significance level",
        "mixed model", "ancova", "anova", "logistic regression",
        "cox regression", "kaplan-meier", "log-rank",
        "chi-square", "fisher's exact", "t-test", "wilcoxon",
        "last observation carried forward", "locf",
        "multiple imputation", "sensitivity analysis",
        "subgroup analysis", "forest plot",
        "odds ratio", "hazard ratio", "relative risk",
        "treatment difference", "least squares mean",
    ]

    def __init__(self, ground_truth_dir: str = "data/ground_truth"):
        self.ground_truth_dir = Path(ground_truth_dir)

    def get_available_ground_truth(self) -> List[str]:
        """Get list of NCT IDs with ground truth SAPs"""
        nct_ids = set()
        for f in self.ground_truth_dir.glob("*_sap.txt"):
            nct_id = f.stem.replace("_sap", "")
            nct_ids.add(nct_id)
        return sorted(nct_ids)

    def load_ground_truth(self, nct_id: str) -> Tuple[str, str]:
        """Load ground truth protocol and SAP"""
        protocol_path = self.ground_truth_dir / f"{nct_id}_protocol.txt"
        sap_path = self.ground_truth_dir / f"{nct_id}_sap.txt"

        if not protocol_path.exists():
            raise FileNotFoundError(f"Protocol not found: {protocol_path}")
        if not sap_path.exists():
            raise FileNotFoundError(f"SAP not found: {sap_path}")

        protocol = protocol_path.read_text(encoding='utf-8', errors='ignore')
        sap = sap_path.read_text(encoding='utf-8', errors='ignore')

        return protocol, sap

    def extract_sections(self, text: str) -> Dict[str, SAPSection]:
        """Extract sections from SAP text"""
        sections = {}
        text_lower = text.lower()

        for section_name in self.SAP_SECTIONS:
            # Look for section headers
            patterns = [
                rf'\n\s*\d*\.?\s*{section_name}[:\s]*\n',
                rf'\n\s*{section_name.upper()}[:\s]*\n',
                rf'\n\s*{section_name.title()}[:\s]*\n',
            ]

            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    # Extract content until next section
                    start = match.end()
                    end = len(text)

                    # Find next section header
                    for next_section in self.SAP_SECTIONS:
                        if next_section == section_name:
                            continue
                        next_patterns = [
                            rf'\n\s*\d*\.?\s*{next_section}[:\s]*\n',
                            rf'\n\s*{next_section.upper()}[:\s]*\n',
                        ]
                        for np in next_patterns:
                            next_match = re.search(np, text_lower[start:])
                            if next_match:
                                end = min(end, start + next_match.start())

                    content = text[start:end].strip()
                    sections[section_name] = SAPSection(
                        name=section_name,
                        content=content[:2000],  # Limit for comparison
                        line_count=len(content.split('\n'))
                    )
                    break

        return sections

    def find_statistical_terms(self, text: str) -> List[str]:
        """Find statistical terms in text"""
        text_lower = text.lower()
        found = []

        for term in self.STATISTICAL_TERMS:
            if term in text_lower:
                found.append(term)

        return found

    def evaluate(
        self,
        generated_sap: str,
        ground_truth_sap: str,
        nct_id: str = "unknown"
    ) -> EvaluationResult:
        """Evaluate generated SAP against ground truth"""

        # Line counts
        gt_lines = len(ground_truth_sap.split('\n'))
        gen_lines = len(generated_sap.split('\n'))

        # Extract sections
        gt_sections = self.extract_sections(ground_truth_sap)
        gen_sections = self.extract_sections(generated_sap)

        gt_section_names = set(gt_sections.keys())
        gen_section_names = set(gen_sections.keys())

        matched = gt_section_names & gen_section_names
        missing = gt_section_names - gen_section_names

        section_coverage = len(matched) / len(gt_section_names) * 100 if gt_section_names else 0

        # Statistical terms
        gt_terms = set(self.find_statistical_terms(ground_truth_sap))
        gen_terms = set(self.find_statistical_terms(generated_sap))

        terms_found = list(gt_terms & gen_terms)
        terms_missing = list(gt_terms - gen_terms)

        keyword_overlap = len(terms_found) / len(gt_terms) * 100 if gt_terms else 0

        # Structure checks
        gen_lower = generated_sap.lower()

        has_primary = any(x in gen_lower for x in ["primary endpoint", "primary efficacy", "primary outcome", "primary analysis"])
        has_secondary = any(x in gen_lower for x in ["secondary endpoint", "secondary efficacy", "secondary outcome"])
        has_sample_size = any(x in gen_lower for x in ["sample size", "power calculation", "statistical power"])
        has_populations = any(x in gen_lower for x in ["analysis population", "intent-to-treat", "per-protocol", "full analysis set"])
        has_methods = any(x in gen_lower for x in ["statistical method", "statistical model", "ancova", "anova", "mixed model", "regression"])
        has_missing = any(x in gen_lower for x in ["missing data", "imputation", "locf", "last observation"])

        # Calculate overall score
        score = 0

        # Section coverage (40 points)
        score += section_coverage * 0.4

        # Statistical terms (30 points)
        score += keyword_overlap * 0.3

        # Structure completeness (30 points)
        structure_checks = [has_primary, has_secondary, has_sample_size, has_populations, has_methods, has_missing]
        structure_score = sum(structure_checks) / len(structure_checks) * 30
        score += structure_score

        return EvaluationResult(
            nct_id=nct_id,
            ground_truth_lines=gt_lines,
            generated_lines=gen_lines,
            sections_in_ground_truth=list(gt_section_names),
            sections_in_generated=list(gen_section_names),
            sections_matched=list(matched),
            sections_missing=list(missing),
            section_coverage_pct=round(section_coverage, 1),
            keyword_overlap_pct=round(keyword_overlap, 1),
            statistical_terms_found=terms_found,
            statistical_terms_missing=terms_missing[:10],  # Limit output
            has_primary_endpoint=has_primary,
            has_secondary_endpoint=has_secondary,
            has_sample_size=has_sample_size,
            has_analysis_populations=has_populations,
            has_statistical_methods=has_methods,
            has_missing_data=has_missing,
            overall_score=round(score, 1)
        )

    def print_result(self, result: EvaluationResult):
        """Pretty print evaluation result"""
        print("\n" + "="*60)
        print(f"SAP EVALUATION: {result.nct_id}")
        print("="*60)

        print(f"\n📊 Document Size:")
        print(f"   Ground Truth: {result.ground_truth_lines} lines")
        print(f"   Generated:    {result.generated_lines} lines")

        print(f"\n📋 Section Coverage: {result.section_coverage_pct}%")
        print(f"   Matched:  {len(result.sections_matched)}")
        print(f"   Missing:  {len(result.sections_missing)}")
        if result.sections_missing:
            print(f"   → {', '.join(result.sections_missing[:5])}")

        print(f"\n📈 Statistical Terms: {result.keyword_overlap_pct}%")
        print(f"   Found:   {len(result.statistical_terms_found)}")
        print(f"   Missing: {len(result.statistical_terms_missing)}")
        if result.statistical_terms_missing:
            print(f"   → {', '.join(result.statistical_terms_missing[:5])}")

        print(f"\n✓ Structure Checklist:")
        checks = [
            ("Primary Endpoint", result.has_primary_endpoint),
            ("Secondary Endpoint", result.has_secondary_endpoint),
            ("Sample Size", result.has_sample_size),
            ("Analysis Populations", result.has_analysis_populations),
            ("Statistical Methods", result.has_statistical_methods),
            ("Missing Data Handling", result.has_missing_data),
        ]
        for name, present in checks:
            status = "✓" if present else "✗"
            print(f"   {status} {name}")

        print(f"\n{'='*60}")
        print(f"🎯 OVERALL SCORE: {result.overall_score}/100")
        print("="*60)


def generate_sap_for_protocol(protocol_text: str) -> str:
    """Generate SAP using the enterprise system"""
    from enterprise_sap_system.core.constrained_pipeline import ConstrainedSAPPipeline

    pipeline = ConstrainedSAPPipeline()
    result = pipeline.generate(protocol_text)

    if result.get("success"):
        return result.get("sap_document", "")
    else:
        raise RuntimeError(f"Generation failed: {result.get('error')}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate SAP generation against ground truth")
    parser.add_argument("--nct", type=str, help="NCT ID to evaluate (e.g., NCT03422848)")
    parser.add_argument("--all", action="store_true", help="Evaluate all ground truth pairs")
    parser.add_argument("--generated", type=str, help="Path to pre-generated SAP file")
    parser.add_argument("--ground-truth-dir", type=str, default="data/ground_truth")
    parser.add_argument("--output", type=str, help="Output JSON file for results")
    parser.add_argument("--skip-generation", action="store_true", help="Only compare, don't generate")

    args = parser.parse_args()

    evaluator = SAPEvaluator(args.ground_truth_dir)

    # Get NCT IDs to evaluate
    if args.all:
        nct_ids = evaluator.get_available_ground_truth()
    elif args.nct:
        nct_ids = [args.nct]
    else:
        print("Available ground truth NCT IDs:")
        for nct_id in evaluator.get_available_ground_truth():
            print(f"  - {nct_id}")
        print("\nUsage: python evaluate_sap.py --nct NCT03422848")
        return

    results = []

    for nct_id in nct_ids:
        print(f"\n{'='*60}")
        print(f"Processing {nct_id}...")
        print("="*60)

        try:
            # Load ground truth
            protocol, ground_truth_sap = evaluator.load_ground_truth(nct_id)

            # Get generated SAP
            if args.generated:
                with open(args.generated) as f:
                    generated_sap = f.read()
            elif args.skip_generation:
                print("Skipping generation (--skip-generation)")
                continue
            else:
                print("Generating SAP from protocol...")
                generated_sap = generate_sap_for_protocol(protocol)

            # Evaluate
            result = evaluator.evaluate(generated_sap, ground_truth_sap, nct_id)
            evaluator.print_result(result)
            results.append(result.to_dict())

        except Exception as e:
            print(f"Error processing {nct_id}: {e}")
            import traceback
            traceback.print_exc()

    # Save results
    if args.output and results:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")

    # Print summary
    if len(results) > 1:
        avg_score = sum(r['overall_score'] for r in results) / len(results)
        print(f"\n{'='*60}")
        print(f"SUMMARY: {len(results)} evaluations, Average Score: {avg_score:.1f}/100")
        print("="*60)


if __name__ == "__main__":
    main()
