#!/usr/bin/env python3
"""
RAG Sanitizer - Strip Numerical Values from RAG Examples
=========================================================

Based on 2024-2025 RAG best practices:
- RAG examples should provide PROSE STYLE only
- Numerical values must come from extraction (single source of truth)
- Stripping numbers is deterministic - no reliance on LLM compliance

Reference: "Centralizing retrieval through a single, trusted data source
promotes consistent answers." - AI21 Labs
"""

import re
from typing import List, Dict, Any, Optional


class RAGSanitizer:
    """
    Strips trial-specific numerical values from RAG examples.
    RAG is for PROSE STYLE only, not for facts.
    """

    # Patterns to strip with their replacements
    SANITIZATION_PATTERNS = [
        # Event counts (deaths, events, occurrences)
        (r'\b(\d{2,4})\s*(?:deaths?|death events?|os events?)\b', '[N_DEATHS from protocol]'),
        (r'\b(\d{2,4})\s*(?:events?|event)\b', '[N_EVENTS from protocol]'),
        (r'\b(\d{2,4})\s*(?:pfs events?|progression events?)\b', '[N_PFS_EVENTS from protocol]'),

        # Sample sizes
        (r'\b(\d{2,4})\s*(?:patients?|subjects?|participants?)\b', '[N_PATIENTS from protocol]'),
        (r'(?:n\s*=\s*)(\d{2,4})\b', 'N = [N from protocol]'),
        (r'(?:sample size[:\s]+)(\d{2,4})\b', 'sample size: [N from protocol]'),
        (r'\b(\d{2,4})\s*(?:per arm|per group|in each arm)\b', '[N_PER_ARM from protocol]'),

        # Alpha levels (significance)
        (r'(?:alpha|α)\s*(?:=|of|level)?\s*(0\.0\d+)', 'alpha = [ALPHA from protocol]'),
        (r'(?:significance level[:\s]+)(0\.0\d+)', 'significance level: [ALPHA from protocol]'),
        (r'(?:one-sided[:\s]+)(0\.0\d+)', 'one-sided: [ALPHA from protocol]'),
        (r'(?:two-sided[:\s]+)(0\.0\d+)', 'two-sided: [ALPHA from protocol]'),
        (r'\bp\s*<\s*(0\.0\d+)', 'p < [ALPHA from protocol]'),
        (r'\bp\s*=\s*(0\.0\d+)', 'p = [P_VALUE from protocol]'),

        # Information fractions
        (r'(\d{1,3}(?:\.\d+)?)\s*%?\s*(?:information fraction|IF|information)', '[IF from protocol]% information'),
        (r'(?:at\s+)(\d{1,2}(?:\.\d+)?)\s*%\s*(?:of\s+)?(?:events?|information)', 'at [IF from protocol]% of events'),

        # Hazard ratios
        (r'(?:HR|hazard ratio)\s*(?:=|of)?\s*(0\.\d+)', 'HR = [HR from protocol]'),
        (r'(?:HR|hazard ratio)\s*(?:=|of)?\s*(1\.\d+)', 'HR = [HR from protocol]'),

        # Confidence intervals
        (r'(\d{1,2})\s*%\s*(?:CI|confidence interval)', '[CI_LEVEL from protocol]% CI'),

        # Power
        (r'(\d{2,3})\s*%\s*(?:power|statistical power)', '[POWER from protocol]% power'),
        (r'(?:power[:\s]+)(\d{2,3})\s*%', 'power: [POWER from protocol]%'),

        # Specific interim/final event counts
        (r'(?:interim[^.]*?)(\d{2,4})\s*(?:events?|deaths?)', 'interim: [N_INTERIM_EVENTS from protocol] events'),
        (r'(?:final[^.]*?)(\d{2,4})\s*(?:events?|deaths?)', 'final: [N_FINAL_EVENTS from protocol] events'),

        # NCT IDs (replace with placeholder to avoid confusion)
        (r'NCT\d{8}', '[NCT_ID from protocol]'),

        # Generic large numbers that might be events/patients
        (r'(?:approximately|~|about|around)\s*(\d{2,4})\b', 'approximately [N from protocol]'),

        # Randomization ratios with numbers
        (r'(\d+:\d+)\s*(?:randomization|ratio)', '[RATIO from protocol] randomization'),

        # Median survival times
        (r'(?:median[^.]*?)(\d+(?:\.\d+)?)\s*(?:months?|weeks?|years?)', 'median: [MEDIAN from protocol] months'),

        # Follow-up times
        (r'(?:follow-up[^.]*?)(\d+(?:\.\d+)?)\s*(?:months?|weeks?|years?)', 'follow-up: [FOLLOWUP from protocol]'),
    ]

    # Additional context-aware patterns
    CONTEXT_PATTERNS = [
        # Alpha at specific analyses
        (r'(?:at interim[^.]*?)(0\.0\d+)', 'at interim: [ALPHA_INTERIM from protocol]'),
        (r'(?:at final[^.]*?)(0\.0\d+)', 'at final: [ALPHA_FINAL from protocol]'),

        # Stopping boundaries
        (r'(?:reject[^.]*?if[^.]*?p\s*<\s*)(0\.0\d+)', 'reject if p < [BOUNDARY from protocol]'),
        (r'(?:efficacy boundary[^.]*?)(0\.0\d+)', 'efficacy boundary: [BOUNDARY from protocol]'),
        (r'(?:futility boundary[^.]*?)(0\.0\d+)', 'futility boundary: [BOUNDARY from protocol]'),
    ]

    def __init__(self, aggressive: bool = True):
        """
        Initialize sanitizer.

        Args:
            aggressive: If True, strip more aggressively (recommended)
        """
        self.aggressive = aggressive
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.SANITIZATION_PATTERNS
        ]
        self.compiled_context = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.CONTEXT_PATTERNS
        ]

    def sanitize(self, text: str) -> str:
        """
        Remove all trial-specific numerical values from text.

        Args:
            text: RAG example text with numbers

        Returns:
            Sanitized text with placeholders
        """
        if not text:
            return text

        result = text

        # Apply context patterns first (more specific)
        for pattern, replacement in self.compiled_context:
            result = pattern.sub(replacement, result)

        # Apply general patterns
        for pattern, replacement in self.compiled_patterns:
            result = pattern.sub(replacement, result)

        # Aggressive mode: catch any remaining standalone numbers in key contexts
        if self.aggressive:
            result = self._aggressive_cleanup(result)

        return result

    def _aggressive_cleanup(self, text: str) -> str:
        """
        Additional cleanup for numbers that might have been missed.
        Only applies in key statistical contexts.
        """
        # Find sentences with statistical keywords and strip remaining numbers
        statistical_keywords = [
            'events', 'deaths', 'patients', 'subjects', 'alpha', 'power',
            'interim', 'final', 'hazard', 'ratio', 'significance', 'sample'
        ]

        sentences = text.split('.')
        cleaned_sentences = []

        for sentence in sentences:
            sentence_lower = sentence.lower()
            has_stat_keyword = any(kw in sentence_lower for kw in statistical_keywords)

            if has_stat_keyword:
                # Replace any remaining 2-4 digit numbers in statistical contexts
                # But preserve things like "Phase 3", "Step 1", etc.
                sentence = re.sub(
                    r'(?<![Phase\s])(?<![Step\s])(?<![Stage\s])(?<![Tier\s])\b(\d{2,4})\b(?!\s*(?:Phase|Step|Stage|Tier))',
                    '[N from protocol]',
                    sentence
                )

            cleaned_sentences.append(sentence)

        return '.'.join(cleaned_sentences)

    def sanitize_examples(self, examples: List[str]) -> List[str]:
        """
        Sanitize a list of RAG examples.

        Args:
            examples: List of RAG example texts

        Returns:
            List of sanitized texts
        """
        return [self.sanitize(ex) for ex in examples]

    def sanitize_rag_results(self, results: List[Any]) -> List[Dict[str, Any]]:
        """
        Sanitize RAG retrieval results.

        Args:
            results: List of RAG result objects (dicts or objects with .content)

        Returns:
            List of dicts with sanitized content
        """
        sanitized = []

        for r in results:
            if isinstance(r, dict):
                content = r.get('content', str(r))
            elif hasattr(r, 'content'):
                content = r.content
            else:
                content = str(r)

            sanitized.append({
                'content': self.sanitize(content),
                'original_length': len(content),
                'sanitized': True
            })

        return sanitized


def test_sanitizer():
    """Test the sanitizer with example text."""

    sanitizer = RAGSanitizer()

    test_text = """
    The primary analysis will be based on 639 death events. The study enrolled
    504 patients randomized 2:1 to treatment arms. Alpha of 0.025 (one-sided)
    will be used for the primary analysis.

    Interim analysis will be performed at 291 events (50% information fraction).
    At interim, H0 will be rejected if p < 0.020. At final analysis (382 events),
    H0 will be rejected if p < 0.044.

    The study has 90% power to detect HR = 0.70 at alpha = 0.025.
    NCT02041533 is the registration ID.
    """

    print("=" * 60)
    print("ORIGINAL TEXT:")
    print("=" * 60)
    print(test_text)

    print("\n" + "=" * 60)
    print("SANITIZED TEXT:")
    print("=" * 60)
    print(sanitizer.sanitize(test_text))


if __name__ == "__main__":
    test_sanitizer()
