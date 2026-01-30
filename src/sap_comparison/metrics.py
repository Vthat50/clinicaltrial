"""Metrics for SAP comparison and validation."""
import re
from dataclasses import dataclass, field
from typing import Optional
from difflib import SequenceMatcher


@dataclass
class SectionMetrics:
    """Metrics for a single section comparison."""
    section_name: str
    present_in_generated: bool
    present_in_reference: bool
    similarity_score: float  # 0-1
    word_count_generated: int
    word_count_reference: int
    coverage_ratio: float  # generated/reference word ratio


@dataclass
class ComparisonResult:
    """Full comparison result between generated and reference SAP."""
    nct_id: str
    overall_similarity: float
    section_coverage: float  # % of reference sections found in generated
    content_coverage: float  # % of reference content captured
    section_metrics: list[SectionMetrics] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    extra_sections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "nct_id": self.nct_id,
            "overall_similarity": round(self.overall_similarity, 3),
            "section_coverage": round(self.section_coverage, 3),
            "content_coverage": round(self.content_coverage, 3),
            "missing_sections": self.missing_sections,
            "extra_sections": self.extra_sections,
            "section_metrics": [
                {
                    "section": m.section_name,
                    "similarity": round(m.similarity_score, 3),
                    "word_count_gen": m.word_count_generated,
                    "word_count_ref": m.word_count_reference,
                }
                for m in self.section_metrics
            ],
        }


class SAPMetrics:
    """Calculate metrics for SAP comparison."""

    # Common SAP section patterns
    SECTION_PATTERNS = [
        (r"(?i)introduction", "introduction"),
        (r"(?i)objectives?\s+(?:and\s+)?endpoints?", "objectives_endpoints"),
        (r"(?i)study\s+design", "study_design"),
        (r"(?i)analysis\s+populations?", "analysis_populations"),
        (r"(?i)sample\s+size", "sample_size"),
        (r"(?i)statistical\s+(?:methods?|analysis)", "statistical_methods"),
        (r"(?i)efficacy\s+analy", "efficacy_analyses"),
        (r"(?i)safety\s+analy", "safety_analyses"),
        (r"(?i)missing\s+data", "missing_data"),
        (r"(?i)interim\s+analysis", "interim_analysis"),
        (r"(?i)multiplicity", "multiplicity"),
        (r"(?i)subgroup", "subgroup_analyses"),
    ]

    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using SequenceMatcher."""
        if not text1 or not text2:
            return 0.0

        # Normalize texts
        text1 = self._normalize_text(text1)
        text2 = self._normalize_text(text2)

        return SequenceMatcher(None, text1, text2).ratio()

    def calculate_word_overlap(self, text1: str, text2: str) -> float:
        """Calculate word overlap ratio."""
        if not text1 or not text2:
            return 0.0

        words1 = set(self._normalize_text(text1).split())
        words2 = set(self._normalize_text(text2).split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union)

    def identify_sections(self, text: str) -> dict[str, str]:
        """Identify and extract sections from SAP text."""
        sections = {}
        text_lines = text.split('\n')

        current_section = None
        current_content = []

        for line in text_lines:
            # Check if this line is a section header
            section_match = None
            for pattern, section_name in self.SECTION_PATTERNS:
                if re.search(pattern, line):
                    section_match = section_name
                    break

            if section_match:
                # Save previous section
                if current_section:
                    sections[current_section] = '\n'.join(current_content)

                current_section = section_match
                current_content = [line]
            elif current_section:
                current_content.append(line)

        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def word_count(self, text: str) -> int:
        """Count words in text."""
        return len(self._normalize_text(text).split())

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Lowercase
        text = text.lower()
        # Remove special characters
        text = re.sub(r'[^\w\s]', ' ', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def extract_key_terms(self, text: str) -> set[str]:
        """Extract key statistical/clinical terms."""
        key_patterns = [
            r"(?i)\b(primary\s+endpoint)\b",
            r"(?i)\b(secondary\s+endpoint)\b",
            r"(?i)\b(intent.to.treat|itt)\b",
            r"(?i)\b(per.protocol|pp)\b",
            r"(?i)\b(kaplan.meier)\b",
            r"(?i)\b(cox\s+(?:proportional\s+)?(?:hazards?)?)\b",
            r"(?i)\b(log.rank)\b",
            r"(?i)\b(chi.square|fisher)\b",
            r"(?i)\b(t.test|anova)\b",
            r"(?i)\b(confidence\s+interval)\b",
            r"(?i)\b(hazard\s+ratio)\b",
            r"(?i)\b(odds\s+ratio)\b",
            r"(?i)\b(relative\s+risk)\b",
            r"(?i)\b(p.value)\b",
            r"(?i)\b(alpha|significance\s+level)\b",
            r"(?i)\b(power)\b",
            r"(?i)\b(sample\s+size)\b",
            r"(?i)\b(randomiz\w+)\b",
            r"(?i)\b(stratif\w+)\b",
            r"(?i)\b(blind\w*|mask\w*)\b",
        ]

        terms = set()
        for pattern in key_patterns:
            matches = re.findall(pattern, text)
            terms.update(m.lower() for m in matches)

        return terms

    def term_coverage(self, generated: str, reference: str) -> float:
        """Calculate coverage of key terms from reference in generated."""
        ref_terms = self.extract_key_terms(reference)
        gen_terms = self.extract_key_terms(generated)

        if not ref_terms:
            return 1.0

        covered = ref_terms & gen_terms
        return len(covered) / len(ref_terms)
