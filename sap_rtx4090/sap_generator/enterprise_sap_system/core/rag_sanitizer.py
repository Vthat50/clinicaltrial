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

IMPORTANT UPDATE (2025-01):
- Interim analysis values are PRESERVED to teach structural patterns
- Alpha spending, information fractions, and boundary values are kept
- This allows LLM to learn the FORMAT of interim analysis specifications
"""

import re
from typing import List, Dict, Any, Optional


class RAGSanitizer:
    """
    Strips trial-specific numerical values from RAG examples.
    RAG is for PROSE STYLE only, not for facts.
    """

    # CRITICAL: Patterns to strip metadata leakage FIRST
    METADATA_PATTERNS = [
        (r'Chunk\s*ID[:\s]*\d+', ''),
        (r'Source[:\s]*[^\n]+', ''),
        (r'Relevance[:\s]*[\d.]+', ''),
        (r'Score[:\s]*[\d.]+', ''),
        (r'Confidence[:\s]*[\d.]+', ''),
    ]

    # CRITICAL: Strip study names to prevent cross-study contamination
    STUDY_NAME_PATTERNS = [
        (r'CheckMate[\s-]*\d+', '[STUDY]'),
        (r'KEYNOTE[\s-]*\d+', '[STUDY]'),
        (r'JAVELIN[\s\w]*\d*', '[STUDY]'),
        (r'IMpower[\s-]*\d+', '[STUDY]'),
        (r'OAK\s+study', '[STUDY]'),
        (r'POPLAR\s+study', '[STUDY]'),
        (r'GA\d{5}', '[STUDY_ID]'),
        (r'BMS-\d+', '[STUDY_ID]'),
        (r'MK-\d+', '[STUDY_ID]'),
    ]

    # CRITICAL: Strip drug names
    DRUG_NAME_PATTERNS = [
        (r'\betrolizumab\b', '[DRUG]'),
        (r'\bavelumab\b', '[DRUG]'),
        (r'\bipilimumab\b', '[DRUG]'),
        (r'\batezolizumab\b', '[DRUG]'),
        (r'\bdurvalumab\b', '[DRUG]'),
        (r'\bpembrolizumab\b', '[DRUG]'),
        (r'\bnivolumab\b', '[DRUG]'),
        (r'\bdocetaxel\b', '[COMPARATOR]'),
        (r'\bpaclitaxel\b', '[COMPARATOR]'),
    ]

    # CRITICAL: Strip indication terms to prevent cross-indication contamination
    INDICATION_PATTERNS = [
        (r'\bmRCC\b', '[INDICATION]'),
        (r'\bRCC\b(?!\w)', '[INDICATION]'),  # Avoid "occurrence"
        (r'\brenal cell carcinoma\b', '[INDICATION]'),
        (r'\bhepatocellular\b', '[INDICATION]'),
        (r'\bHCC\b(?!\w)', '[INDICATION]'),
        (r'\bmelanoma\b', '[INDICATION]'),
        (r'\burothelial\b', '[INDICATION]'),
        (r'\bNSCLC\b', '[INDICATION]'),
        (r'\bnon-small cell lung\b', '[INDICATION]'),
        (r'\bSCLC\b', '[INDICATION]'),
        (r'\bsmall cell lung\b', '[INDICATION]'),
    ]

    # Patterns to strip with their replacements
    SANITIZATION_PATTERNS = [
        # Event counts (deaths, events, occurrences)
        (r'\b(\d{2,4})\s*(?:deaths?|death events?|os events?)\b', '[N_DEATHS] deaths'),
        (r'\b(\d{2,4})\s*(?:events?|event)\b', '[N_EVENTS] events'),
        (r'\b(\d{2,4})\s*(?:pfs events?|progression events?)\b', '[N_PFS_EVENTS] events'),

        # Sample sizes
        (r'\b(\d{2,4})\s*(?:patients?|subjects?|participants?)\b', '[N] patients'),
        (r'(?:n\s*=\s*)(\d{2,4})\b', 'N = [N]'),
        (r'(?:sample size[:\s]+)(\d{2,4})\b', 'sample size: [N]'),
        (r'\b(\d{2,4})\s*(?:per arm|per group|in each arm)\b', '[N_PER_ARM] per arm'),

        # Alpha levels (significance)
        (r'(?:alpha|α)\s*(?:=|of|level)?\s*(0\.0\d+)', 'alpha = [ALPHA]'),
        (r'(?:significance level[:\s]+)(0\.0\d+)', 'significance level: [ALPHA]'),
        (r'(?:one-sided[:\s]+)(0\.0\d+)', 'one-sided: [ALPHA]'),
        (r'(?:two-sided[:\s]+)(0\.0\d+)', 'two-sided: [ALPHA]'),
        (r'\bp\s*<\s*(0\.0\d+)', 'p < [ALPHA]'),
        (r'\bp\s*=\s*(0\.0\d+)', 'p = [P_VALUE]'),

        # Information fractions
        (r'(\d{1,3}(?:\.\d+)?)\s*%?\s*(?:information fraction|IF|information)', '[IF]% information'),
        (r'(?:at\s+)(\d{1,2}(?:\.\d+)?)\s*%\s*(?:of\s+)?(?:events?|information)', 'at [IF]% of events'),

        # Hazard ratios
        (r'(?:HR|hazard ratio)\s*(?:=|of)?\s*(0\.\d+)', 'HR = [HR]'),
        (r'(?:HR|hazard ratio)\s*(?:=|of)?\s*(1\.\d+)', 'HR = [HR]'),

        # Confidence intervals
        (r'(\d{1,2})\s*%\s*(?:CI|confidence interval)', '[CI_LEVEL]% CI'),

        # Power
        (r'(\d{2,3})\s*%\s*(?:power|statistical power)', '[POWER]% power'),
        (r'(?:power[:\s]+)(\d{2,3})\s*%', 'power: [POWER]%'),

        # Specific interim/final event counts
        (r'(?:interim[^.]*?)(\d{2,4})\s*(?:events?|deaths?)', 'interim: [N_INTERIM_EVENTS] events'),
        (r'(?:final[^.]*?)(\d{2,4})\s*(?:events?|deaths?)', 'final: [N_FINAL_EVENTS] events'),

        # NCT IDs (replace with placeholder to avoid confusion)
        (r'NCT\d{8}', '[NCT_ID]'),

        # Generic large numbers that might be events/patients
        (r'(?:approximately|~|about|around)\s*(\d{2,4})\b', 'approximately [N]'),

        # Randomization ratios with numbers
        (r'(\d+:\d+(?::\d+)?)\s*(?:randomization|ratio)', '[RATIO] randomization'),
        (r'\b\d+:\d+(?::\d+)?\b', '[RATIO]'),

        # Median survival times
        (r'(?:median[^.]*?)(\d+(?:\.\d+)?)\s*(?:months?|weeks?|years?)', 'median: [MEDIAN] months'),

        # Follow-up times
        (r'(?:follow-up[^.]*?)(\d+(?:\.\d+)?)\s*(?:months?|weeks?|years?)', 'follow-up: [FOLLOWUP]'),

        # Catch-all for remaining large numbers
        (r'\b\d{2,}\b', '[N]'),
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

    # INTERIM ANALYSIS PATTERNS TO PRESERVE (not sanitize)
    # These patterns capture the STRUCTURE of interim analysis specifications
    INTERIM_PRESERVE_PATTERNS = [
        # Alpha spending at each analysis (e.g., "α₁=0.003, α₂=0.019")
        r'(?:α|alpha)\s*[₁₂₃₄1234]?\s*[=:]\s*0\.\d+',
        # Information fractions (e.g., "50% information", "at 50% of events")
        r'\b\d{1,3}(?:\.\d+)?%?\s*(?:information|IF\b)',
        r'at\s+\d{1,3}(?:\.\d+)?%\s*(?:of\s+)?(?:events?|information)',
        # Interim analysis timing (e.g., "IA1 at 27 months", "first interim at 354 events")
        r'(?:IA|interim\s*analysis)\s*[123]?\s*(?:at|when)\s*~?\d+',
        r'(?:first|second|third|final)\s+(?:interim\s+)?analysis\s+(?:at|when)\s*~?\d+',
        # Event counts for interim (e.g., "354 PFS events", "316 OS events")
        r'\b\d{2,4}\s+(?:PFS|OS|EFS|DFS)\s+events?',
        # Stopping boundaries (e.g., "Z = 4.33", "p < 0.003")
        r'[Zz]\s*[=<>]\s*[\d.]+',
        r'(?:boundary|threshold)\s*[=:]\s*[\d.]+',
        # Lan-DeMets / O'Brien-Fleming spending
        r'Lan-DeMets',
        r"O'Brien-Fleming",
        r'Pocock',
        r'spending\s+function',
        # Hazard ratio at boundary
        r'HR\s*(?:at\s+boundary|threshold)\s*[=:]\s*[\d.]+',
        # Power for specific HR (e.g., "90% power for HR 0.7")
        r'\d{2}%\s*power\s*(?:for|to detect)\s*HR\s*[\d.]+',
        # Median survival assumptions
        r'(?:control|placebo)\s+median\s+(?:PFS|OS)[:\s]+[\d.]+\s*months?',
    ]

    def __init__(self, aggressive: bool = True, preserve_interim: bool = True):
        """
        Initialize sanitizer.

        Args:
            aggressive: If True, strip more aggressively (recommended)
            preserve_interim: If True, preserve interim analysis values (NEW - default True)
        """
        self.aggressive = aggressive
        self.preserve_interim = preserve_interim
        self._compile_patterns()
        self._compile_preserve_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        # CRITICAL: Compile in order of priority
        self.compiled_metadata = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.METADATA_PATTERNS
        ]
        self.compiled_studies = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.STUDY_NAME_PATTERNS
        ]
        self.compiled_drugs = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.DRUG_NAME_PATTERNS
        ]
        self.compiled_indications = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.INDICATION_PATTERNS
        ]
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.SANITIZATION_PATTERNS
        ]
        self.compiled_context = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.CONTEXT_PATTERNS
        ]

    def _compile_preserve_patterns(self):
        """Compile patterns for interim analysis values to preserve."""
        self.compiled_preserve = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.INTERIM_PRESERVE_PATTERNS
        ]

    def _extract_preserved_values(self, text: str) -> Dict[str, str]:
        """
        Extract interim analysis values that should be preserved.
        Returns a dict of placeholder -> original value.
        """
        preserved = {}
        counter = 0
        for pattern in self.compiled_preserve:
            for match in pattern.finditer(text):
                placeholder = f"__PRESERVE_{counter}__"
                preserved[placeholder] = match.group(0)
                counter += 1
        return preserved

    def _mark_preserved(self, text: str, preserved: Dict[str, str]) -> str:
        """Replace preserved values with temporary placeholders."""
        result = text
        for placeholder, original in preserved.items():
            result = result.replace(original, placeholder, 1)
        return result

    def _restore_preserved(self, text: str, preserved: Dict[str, str]) -> str:
        """Restore preserved values from placeholders."""
        result = text
        for placeholder, original in preserved.items():
            result = result.replace(placeholder, original)
        return result

    def sanitize(self, text: str) -> str:
        """
        Remove all trial-specific content from text.

        CRITICAL ORDER:
        0. (NEW) Preserve interim analysis values if enabled
        1. Metadata (Chunk ID, Source, etc.)
        2. Study names (CheckMate, JAVELIN, etc.)
        3. Drug names (nivolumab, avelumab, etc.)
        4. Indication terms (mRCC, NSCLC, etc.)
        5. Numbers (sample sizes, events, etc.)
        6. (NEW) Restore preserved interim analysis values

        Args:
            text: RAG example text with contaminating content

        Returns:
            Sanitized text with placeholders (but interim values preserved)
        """
        if not text:
            return text

        result = text

        # STEP 0: Extract and mark interim analysis values to preserve
        preserved = {}
        if self.preserve_interim:
            preserved = self._extract_preserved_values(result)
            result = self._mark_preserved(result, preserved)

        # STEP 1: Strip metadata FIRST
        for pattern, replacement in self.compiled_metadata:
            result = pattern.sub(replacement, result)

        # STEP 2: Strip study names
        for pattern, replacement in self.compiled_studies:
            result = pattern.sub(replacement, result)

        # STEP 3: Strip drug names
        for pattern, replacement in self.compiled_drugs:
            result = pattern.sub(replacement, result)

        # STEP 4: Strip indication terms
        for pattern, replacement in self.compiled_indications:
            result = pattern.sub(replacement, result)

        # STEP 5: Apply context patterns (more specific number patterns)
        for pattern, replacement in self.compiled_context:
            result = pattern.sub(replacement, result)

        # STEP 6: Apply general number patterns
        for pattern, replacement in self.compiled_patterns:
            result = pattern.sub(replacement, result)

        # STEP 7: Aggressive mode: catch any remaining standalone numbers
        if self.aggressive:
            result = self._aggressive_cleanup(result)

        # STEP 8: Restore preserved interim analysis values
        if self.preserve_interim and preserved:
            result = self._restore_preserved(result, preserved)

        # STEP 9: Clean up whitespace
        result = re.sub(r'\s+', ' ', result).strip()

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

    # Test with interim preservation enabled (default)
    sanitizer = RAGSanitizer(preserve_interim=True)

    test_text = """
    The primary analysis will be based on 639 death events. The study enrolled
    504 patients randomized 2:1 to treatment arms. Alpha of 0.025 (one-sided)
    will be used for the primary analysis.

    Three interim analyses will be conducted:
    - IA1 at ~27 months (~354 PFS events for pMMR population)
    - IA2 at ~36 months (~472 PFS events for pMMR population)
    - IA3 at ~42 months (~316 OS events for pMMR population)
    - Final analysis at ~48 months (~359 OS events)

    Alpha allocation using Lan-DeMets O'Brien-Fleming spending function:
    - PFS alpha (pMMR): α = 0.005 (one-sided)
    - OS alpha (pMMR): α = 0.02 (one-sided)

    Power: 90% power for HR 0.7 (PFS), 82% power for HR 0.8 (OS NI)
    Control median PFS: 8.8 months, Control median OS: 23 months

    At 50% information fraction, efficacy boundary Z = 4.33, p < 0.003

    NCT02041533 is the registration ID.
    """

    print("=" * 60)
    print("ORIGINAL TEXT:")
    print("=" * 60)
    print(test_text)

    print("\n" + "=" * 60)
    print("SANITIZED TEXT (with interim values PRESERVED):")
    print("=" * 60)
    print(sanitizer.sanitize(test_text))

    # Also test without preservation
    print("\n" + "=" * 60)
    print("SANITIZED TEXT (without preservation - OLD behavior):")
    print("=" * 60)
    old_sanitizer = RAGSanitizer(preserve_interim=False)
    print(old_sanitizer.sanitize(test_text))


if __name__ == "__main__":
    test_sanitizer()
