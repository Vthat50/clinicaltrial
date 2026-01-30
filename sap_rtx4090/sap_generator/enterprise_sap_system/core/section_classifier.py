#!/usr/bin/env python3
"""
Section Classifier
==================

Classifies ALL protocol content into SAP sections based on keywords.

Flow:
1. Extract ALL content from protocol (LlamaParse)
2. Split into paragraphs (don't lose ANY content)
3. For EACH paragraph: score against ALL section patterns
4. Assign to highest-scoring SAP section
5. If no match → "unclassified" bucket
"""

import re
from typing import Dict, List, Tuple, Optional


# =============================================================================
# SECTION PATTERNS - Keywords that indicate content belongs to a section
# =============================================================================

SECTION_PATTERNS = {
    "introduction": {
        "keywords": ["introduction", "background", "rationale", "study title", "protocol number", "sponsor"],
        "weight": 1.0
    },
    "objectives": {
        "keywords": ["primary objective", "secondary objective", "exploratory objective", "aim of the study", "purpose of the study", "objective of this study", "study objective", "the objective"],
        "weight": 1.0
    },
    "endpoints": {
        "keywords": ["primary endpoint", "secondary endpoint", "endpoint definition", "outcome measure", "efficacy endpoint"],
        "weight": 1.0
    },
    "study_design": {
        "keywords": ["study design", "randomized", "double-blind", "placebo-controlled", "open-label", "parallel", "crossover", "treatment arm"],
        "weight": 1.0
    },
    "sample_size": {
        "keywords": ["sample size", "power", "alpha", "significance level", "patients", "n =", "subjects", "hazard ratio", "effect size", "dropout"],
        "weight": 1.0
    },
    "analysis_populations": {
        "keywords": ["analysis population", "analysis set", "itt", "intent-to-treat", "per-protocol", "full analysis set", "safety population", "fas", "pp population"],
        "weight": 1.0
    },
    "statistical_methods": {
        "keywords": ["log-rank", "cox", "kaplan-meier", "t-test", "chi-square", "regression", "anova", "ancova", "mmrm", "stratified analysis", "covariate"],
        "weight": 1.0
    },
    "efficacy_analysis": {
        "keywords": ["response", "tumor assessment", "recist", "efficacy", "orr", "pfs", "os", "complete response", "partial response", "disease control"],
        "weight": 1.0
    },
    "safety_analysis": {
        "keywords": ["adverse event", "ae", "sae", "safety", "toxicity", "dlt", "dose limiting", "serious adverse", "meddra", "ctcae"],
        "weight": 1.0
    },
    "interim_analysis": {
        "keywords": ["interim analysis", "interim analyses", "alpha spending", "stopping rule", "lan-demets", "o'brien-fleming", "pocock", "futility", "dmc", "idmc", "dsmb", "group sequential", "data monitoring committee", "early stopping"],
        "weight": 1.0
    },
    "multiplicity": {
        "keywords": ["multiplicity", "multiple comparison", "multiple testing", "type i error", "familywise", "hierarchical testing", "gatekeeping", "bonferroni", "hochberg", "holm", "alpha allocation", "adjustment for multiplicity"],
        "weight": 1.0
    },
    "missing_data": {
        "keywords": ["missing data", "censoring", "imputation", "locf", "bocf", "lost to follow-up", "discontinuation", "withdrawal", "mar", "mcar", "mnar"],
        "weight": 1.0
    },
    "sensitivity_analysis": {
        "keywords": ["sensitivity analysis", "sensitivity analyses", "tipping point", "per-protocol analysis", "robustness", "supportive analysis", "alternative analysis", "as-treated", "completer analysis"],
        "weight": 1.0
    },
    "subgroup_analysis": {
        "keywords": ["subgroup analysis", "subgroup analyses", "subgroups", "forest plot", "interaction test", "stratified by", "by age", "by sex", "by gender", "by region", "exploratory subgroup", "pre-specified subgroup"],
        "weight": 1.0
    },
    "pharmacokinetics": {
        "keywords": ["pharmacokinetic", "pk", "auc", "cmax", "tmax", "half-life", "clearance", "bioavailability", "drug concentration"],
        "weight": 1.0
    },
}


def classify_paragraph(paragraph: str) -> Tuple[str, float]:
    """
    Classify a paragraph into the best-matching SAP section.

    Args:
        paragraph: Text paragraph from protocol

    Returns:
        (section_name, confidence_score)
    """
    paragraph_lower = paragraph.lower()
    scores = {}

    for section, config in SECTION_PATTERNS.items():
        score = 0
        for keyword in config["keywords"]:
            if keyword.lower() in paragraph_lower:
                score += config["weight"]
        scores[section] = score

    max_score = max(scores.values())
    if max_score == 0:
        return ("unclassified", 0.0)

    best_section = max(scores, key=scores.get)
    return (best_section, scores[best_section])


def classify_all_content(full_text: str) -> Dict[str, List[Dict]]:
    """
    Classify all paragraphs from protocol into SAP sections.

    Args:
        full_text: Full protocol text from LlamaParse

    Returns:
        Dict mapping section names to list of {content, confidence}
    """
    # Split into paragraphs (preserve all content)
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', full_text) if p.strip()]

    # Initialize all sections
    classified = {section: [] for section in SECTION_PATTERNS}
    classified["unclassified"] = []

    for para in paragraphs:
        # Skip very short paragraphs (likely noise)
        if len(para) < 30:
            continue

        section, confidence = classify_paragraph(para)
        classified[section].append({
            "content": para,
            "confidence": confidence
        })

    return classified


def get_section_content(classified: Dict[str, List[Dict]], section_name: str) -> str:
    """
    Get combined content for a section, sorted by confidence.

    Args:
        classified: Output from classify_all_content
        section_name: SAP section to get content for

    Returns:
        Combined content string
    """
    if section_name not in classified:
        return ""

    items = classified[section_name]
    if not items:
        return ""

    # Sort by confidence (highest first)
    items_sorted = sorted(items, key=lambda x: x["confidence"], reverse=True)

    # Combine content
    return "\n\n".join(item["content"] for item in items_sorted)


# =============================================================================
# SAP SECTION ORDER
# =============================================================================

SAP_SECTION_ORDER = [
    "introduction",
    "objectives",
    "endpoints",
    "study_design",
    "sample_size",
    "analysis_populations",
    "statistical_methods",
    "efficacy_analysis",
    "safety_analysis",
    "pharmacokinetics",
    "interim_analysis",
    "multiplicity",
    "missing_data",
    "sensitivity_analysis",
    "subgroup_analysis",
]


# =============================================================================
# VERIFICATION - Check if we missed anything
# =============================================================================

# Broader search terms to verify content exists in protocol
VERIFICATION_TERMS = {
    "objectives": ["objective", "aim", "purpose", "goal"],
    "endpoints": ["endpoint", "outcome", "measure"],
    "study_design": ["design", "randomiz", "blind", "placebo", "arm"],
    "sample_size": ["sample", "power", "alpha", "patient", "subject", "n=", "n ="],
    "analysis_populations": ["population", "itt", "intent", "per-protocol", "analysis set"],
    "statistical_methods": ["statistical", "analysis", "test", "method", "model"],
    "efficacy_analysis": ["efficacy", "response", "recist", "tumor", "survival"],
    "safety_analysis": ["safety", "adverse", "ae", "toxicity", "sae"],
    "interim_analysis": ["interim", "stopping", "futility", "dmc", "idmc"],
    "multiplicity": ["multiplic", "type i", "alpha", "adjustment"],
    "missing_data": ["missing", "censor", "imputation", "withdraw", "discontinu"],
    "sensitivity_analysis": ["sensitivity", "robust", "supportive"],
    "subgroup_analysis": ["subgroup", "forest", "interaction"],
    "pharmacokinetics": ["pharmacokinetic", "pk", "auc", "cmax", "concentration"],
}


def recover_missed_content(full_text: str, section_name: str) -> Optional[str]:
    """
    For a section with no classified content, search the full text
    using broader terms and EXTRACT the content.

    This is active recovery - not just verification.

    Args:
        full_text: Full protocol text
        section_name: Section to find content for

    Returns:
        Extracted content if found, None otherwise
    """
    terms = VERIFICATION_TERMS.get(section_name, [])
    if not terms:
        return None

    # Split into paragraphs
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', full_text) if p.strip() and len(p.strip()) > 50]

    # Find paragraphs containing any of the broader terms
    matching_paragraphs = []
    seen = set()

    for para in paragraphs:
        para_lower = para.lower()
        for term in terms:
            if term.lower() in para_lower:
                # Avoid duplicates
                para_key = para[:100]
                if para_key not in seen:
                    matching_paragraphs.append(para)
                    seen.add(para_key)
                break

    if matching_paragraphs:
        return "\n\n".join(matching_paragraphs)
    return None


def classify_with_recovery(full_text: str) -> Dict[str, List[Dict]]:
    """
    Classify all content AND recover any missed sections.

    Two-pass approach:
    1. First pass: keyword classification
    2. Second pass: for empty sections, use broader search to recover content

    Args:
        full_text: Full protocol text

    Returns:
        Dict with all sections populated (no missed content)
    """
    # First pass: keyword classification
    classified = classify_all_content(full_text)

    # Second pass: recover missed content
    for section in SAP_SECTION_ORDER:
        if not classified.get(section):
            # Try to recover with broader search
            recovered = recover_missed_content(full_text, section)
            if recovered:
                # Add as recovered content
                classified[section] = [{
                    "content": recovered,
                    "confidence": 0.5,  # Lower confidence for recovered content
                    "recovered": True
                }]

    return classified


def get_unclassified_sample(classified: Dict[str, List[Dict]], n: int = 5) -> List[str]:
    """
    Get a sample of unclassified paragraphs for manual review.
    """
    unclassified = classified.get("unclassified", [])
    sample = []
    for item in unclassified[:n]:
        content = item["content"]
        # Truncate long paragraphs
        if len(content) > 200:
            content = content[:200] + "..."
        sample.append(content)
    return sample


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    # Test with sample text
    test_text = """
    The primary objective of this study is to evaluate the efficacy of Drug X.

    The sample size is 300 patients with 80% power and alpha = 0.025 one-sided.

    The primary endpoint is overall survival analyzed using stratified log-rank test.

    Adverse events will be coded using MedDRA and summarized by system organ class.

    An interim analysis will be performed at 50% of events using Lan-DeMets alpha spending.

    Missing data will be handled using multiple imputation under MAR assumption.
    """

    classified = classify_all_content(test_text)

    print("Classification Results:")
    print("=" * 50)
    for section in SAP_SECTION_ORDER:
        items = classified.get(section, [])
        if items:
            print(f"\n{section}: {len(items)} paragraphs")
            for item in items:
                print(f"  - [{item['confidence']:.1f}] {item['content'][:60]}...")
