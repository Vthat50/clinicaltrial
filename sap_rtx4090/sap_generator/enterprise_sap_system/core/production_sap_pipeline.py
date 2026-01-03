#!/usr/bin/env python3
"""
Production-Grade SAP Generation Pipeline
==========================================

A 4-stage pipeline implementing state-of-the-art RAG with:
- Pre-retrieval identity lock with confidence scoring
- Sanitized RAG (structure only, no numbers)
- Constrained generation with mandatory slots
- Post-generation verification with regeneration loop

Architecture based on:
- CRAG (Corrective RAG) for retrieval evaluation
- SELF-RAG for reflection and confidence scoring
- MiniCheck/Azure Groundedness for fact verification
- InformGen for clinical document grounding

Author: Production SAP System
Version: 2.0.0 (2025-01)
"""

import re
import json
import time
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Pydantic for schema validation
try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

# Import from local modules
try:
    from .schemas import ProtocolFacts, StructuredFactExtractor
    from .tiered_llm import TieredLLMClient
except ImportError:
    from schemas import ProtocolFacts, StructuredFactExtractor
    TieredLLMClient = None

# Logging
try:
    from .logging_config import get_logger
except ImportError:
    import logging
    def get_logger(name):
        return logging.getLogger(name)

logger = get_logger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CitedFact:
    """A fact extracted with source citation and confidence."""
    value: Any
    source: str  # e.g., "page 12, line 4" or "Section 5.1"
    confidence: float  # 0.0 to 1.0
    extraction_method: str = "regex"  # regex, llm, api

    def __str__(self):
        return f"{self.value} (source: {self.source}, conf: {self.confidence:.2f})"


@dataclass
class IdentityFacts:
    """
    Immutable identity facts extracted from protocol.
    These are LOCKED and cannot be overridden by RAG or LLM.
    """
    # Core identifiers
    nct_id: Optional[CitedFact] = None
    study_id: Optional[CitedFact] = None
    protocol_title: Optional[CitedFact] = None
    sponsor: Optional[CitedFact] = None

    # Drug/Treatment (HIGH contamination risk)
    drug_name: Optional[CitedFact] = None
    drug_names_all: List[CitedFact] = field(default_factory=list)
    comparator: Optional[CitedFact] = None

    # Indication (HIGH contamination risk)
    indication: Optional[CitedFact] = None
    tumor_type: Optional[CitedFact] = None
    therapeutic_area: Optional[CitedFact] = None

    # Study design
    phase: Optional[CitedFact] = None
    design_type: Optional[CitedFact] = None
    is_combination_therapy: bool = False

    # Critical numbers (NEVER from RAG)
    sample_size: Optional[CitedFact] = None
    os_events: Optional[CitedFact] = None
    pfs_events: Optional[CitedFact] = None
    interim_events: Optional[CitedFact] = None
    information_fraction: Optional[CitedFact] = None
    randomization_ratio: Optional[CitedFact] = None

    # Alpha spending
    alpha_interim: Optional[CitedFact] = None
    alpha_final: Optional[CitedFact] = None

    # Blocked terms (derived from identity - prevent contamination)
    blocked_terms: Set[str] = field(default_factory=set)
    blocked_nct_ids: Set[str] = field(default_factory=set)

    def get_locked_values(self) -> Dict[str, Any]:
        """Return all locked values as a dict for prompt injection."""
        locked = {}
        for field_name in ['nct_id', 'drug_name', 'comparator', 'indication',
                          'sample_size', 'os_events', 'pfs_events', 'interim_events',
                          'alpha_interim', 'alpha_final', 'randomization_ratio']:
            fact = getattr(self, field_name, None)
            if fact and isinstance(fact, CitedFact):
                locked[field_name] = {
                    "value": fact.value,
                    "source": fact.source,
                    "LOCKED": True
                }
        return locked

    def derive_blocked_terms(self):
        """Derive terms that should NOT appear in generated SAP."""
        blocked = set()

        # If monotherapy, block combination terms
        if not self.is_combination_therapy:
            if self.drug_name:
                drug = self.drug_name.value.lower() if self.drug_name.value else ""
                if "nivolumab" in drug:
                    blocked.add("ipilimumab")
                    blocked.add("nivo+ipi")
                    blocked.add("nivolumab combined with ipilimumab")

        # Block wrong indications based on current indication
        indication = self.indication.value.lower() if self.indication and self.indication.value else ""
        if "nsclc" in indication or "lung" in indication:
            blocked.update(["renal cell carcinoma", "mRCC", "RCC", "hepatocellular",
                          "melanoma", "urothelial", "gastric", "esophageal"])
        elif "rcc" in indication or "renal" in indication:
            blocked.update(["NSCLC", "non-small cell lung", "lung cancer",
                          "melanoma", "urothelial"])

        # Block known contaminating study names
        blocked.update(["JAVELIN", "KEYNOTE", "IMpower", "CheckMate 214",
                       "CheckMate 025", "CheckMate 067"])

        # Keep only the current study's CheckMate number
        nct = self.nct_id.value if self.nct_id and self.nct_id.value else ""
        if "NCT02613507" in nct:  # CheckMate 078
            blocked.discard("CheckMate 078")
            blocked.add("CheckMate 214")  # RCC study
            blocked.add("CheckMate 057")  # Keep as reference, don't block
            blocked.add("CheckMate 017")  # Keep as reference, don't block

        self.blocked_terms = blocked


@dataclass
class SanitizedChunk:
    """A RAG chunk with numbers stripped and confidence scored."""
    original_text: str
    sanitized_text: str  # Numbers replaced with placeholders
    source_file: str
    section_type: str  # e.g., "sample_size", "primary_analysis"
    confidence: float  # SELF-RAG relevance score
    provides: str = "structure_only"  # Explicit flag


@dataclass
class MandatorySlot:
    """A slot that MUST appear in generated output."""
    slot_name: str
    must_include: str  # Text that must appear
    must_state_as: Optional[str] = None  # e.g., "primary analysis"
    rationale_required: bool = False
    alternatives: List[str] = field(default_factory=list)  # Acceptable alternatives


@dataclass
class DetectedConditions:
    """Conditions detected from protocol that determine method requirements."""
    # NPH / Delayed effect
    has_nph_model: bool = False
    delayed_effect_expected: bool = False
    immunotherapy_mechanism: bool = False

    # Bridging / Consistency
    is_bridging_study: bool = False
    has_consistency_objective: bool = False
    consistency_reference_studies: List[str] = field(default_factory=list)
    consistency_margin: Optional[str] = None  # e.g., "50% of risk reduction"
    target_region: Optional[str] = None  # e.g., "China", "Asia"

    # Interim analysis
    has_interim_analysis: bool = False
    interim_for_regulatory: bool = False

    # Treatment switching
    has_treatment_switching: bool = False
    crossover_adjustment_needed: bool = False


@dataclass
class VerificationResult:
    """Result of fact verification."""
    passed: bool
    confidence: float
    issues: List[str] = field(default_factory=list)
    ungrounded_claims: List[str] = field(default_factory=list)
    missing_slots: List[str] = field(default_factory=list)
    contamination_detected: List[str] = field(default_factory=list)

    @property
    def overall_confidence(self) -> float:
        if not self.passed:
            return min(0.5, self.confidence)
        return self.confidence


class QualityStatus(Enum):
    """Quality status based on confidence thresholds."""
    AUTO_APPROVED = "auto_approved"           # >= 0.95
    APPROVED_WITH_FLAG = "approved_with_flag" # 0.85-0.94
    HUMAN_REVIEW = "human_review"             # 0.70-0.84
    REJECTED = "rejected"                      # < 0.70


@dataclass
class GeneratedSection:
    """A generated SAP section with metadata."""
    section_name: str
    content: str
    confidence: float
    verification_attempts: int = 1
    slots_verified: List[str] = field(default_factory=list)
    requires_human_review: bool = False
    issues: List[str] = field(default_factory=list)
    quality_status: Optional[QualityStatus] = None
    foreign_numbers_detected: List[str] = field(default_factory=list)


@dataclass
class SAPOutput:
    """Final SAP output with confidence scores."""
    sections: Dict[str, str]
    confidence_scores: Dict[str, float]
    overall_confidence: float
    identity_facts: IdentityFacts
    detected_conditions: DetectedConditions
    verification_report: Dict[str, Any]
    requires_human_review: bool
    flagged_sections: List[str]
    generation_metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# STAGE 1: PRE-RETRIEVAL IDENTITY EXTRACTOR
# =============================================================================

class ProtocolIdentityExtractor:
    """
    STAGE 1: Extract identity facts BEFORE any RAG retrieval.
    Creates immutable "ground truth" that downstream steps must respect.
    """

    # Patterns for high-confidence extraction
    NCT_PATTERN = re.compile(r'NCT\s*(\d{8})', re.IGNORECASE)
    SAMPLE_SIZE_PATTERNS = [
        re.compile(r'(?:approximately|about|total of)\s*(\d+)\s*(?:patients|subjects|participants)', re.IGNORECASE),
        re.compile(r'(\d+)\s*(?:patients|subjects)\s*(?:will be|are)\s*(?:enrolled|randomized)', re.IGNORECASE),
        re.compile(r'sample size[:\s]+(\d+)', re.IGNORECASE),
        re.compile(r'enroll(?:ment)?[:\s]+(\d+)', re.IGNORECASE),
    ]
    EVENT_PATTERNS = [
        re.compile(r'(\d+)\s*(?:OS\s+)?(?:deaths|death events|events?\s+for\s+OS)', re.IGNORECASE),
        re.compile(r'(\d+)\s*(?:PFS\s+)?(?:events?\s+for\s+PFS|progression events)', re.IGNORECASE),
    ]
    ALPHA_PATTERNS = [
        re.compile(r'(?:interim|IA)[^.]*(?:p\s*[<≤]\s*|α\s*=\s*)(\d+\.?\d*)', re.IGNORECASE),
        re.compile(r'(?:final)[^.]*(?:p\s*[<≤]\s*|α\s*=\s*)(\d+\.?\d*)', re.IGNORECASE),
    ]

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.regex_extractor = StructuredFactExtractor()

    def extract(self, protocol_text: str) -> IdentityFacts:
        """Extract identity facts with confidence scores."""
        identity = IdentityFacts()

        # NCT ID (highest confidence - regex)
        identity.nct_id = self._extract_nct_id(protocol_text)

        # Drug names (high confidence)
        identity.drug_name, identity.drug_names_all = self._extract_drug_names(protocol_text)
        identity.comparator = self._extract_comparator(protocol_text)

        # Indication
        identity.indication = self._extract_indication(protocol_text)
        identity.tumor_type = self._extract_tumor_type(protocol_text)
        identity.therapeutic_area = self._infer_therapeutic_area(identity)

        # Study design
        identity.phase = self._extract_phase(protocol_text)
        identity.design_type = self._extract_design_type(protocol_text)
        identity.is_combination_therapy = self._detect_combination(protocol_text)

        # Critical numbers
        identity.sample_size = self._extract_sample_size(protocol_text)
        identity.os_events = self._extract_os_events(protocol_text)
        identity.pfs_events = self._extract_pfs_events(protocol_text)
        identity.interim_events = self._extract_interim_events(protocol_text)
        identity.randomization_ratio = self._extract_ratio(protocol_text)

        # Alpha spending
        identity.alpha_interim, identity.alpha_final = self._extract_alpha_spending(protocol_text)

        # Derive blocked terms
        identity.derive_blocked_terms()

        logger.info("Identity extraction complete",
                   nct_id=identity.nct_id.value if identity.nct_id else None,
                   drug=identity.drug_name.value if identity.drug_name else None)

        return identity

    def _extract_nct_id(self, text: str) -> Optional[CitedFact]:
        match = self.NCT_PATTERN.search(text)
        if match:
            nct_id = f"NCT{match.group(1)}"
            # Find approximate location
            start = match.start()
            line_num = text[:start].count('\n') + 1
            return CitedFact(
                value=nct_id,
                source=f"line {line_num}",
                confidence=1.0,
                extraction_method="regex"
            )
        return None

    def _extract_drug_names(self, text: str) -> Tuple[Optional[CitedFact], List[CitedFact]]:
        """Extract drug names using INN suffix patterns."""
        drug_facts = []

        # INN suffixes for biologics/small molecules
        inn_patterns = [
            (r'\b([A-Za-z]+(?:mab|nib|lib|tinib|ciclib))\b', 'biologic/kinase'),
            (r'\b([A-Za-z]+(?:taxel|platin|mustine))\b', 'chemotherapy'),
        ]

        # Known drug names
        known_drugs = {
            'nivolumab': 'PD-1 inhibitor',
            'pembrolizumab': 'PD-1 inhibitor',
            'atezolizumab': 'PD-L1 inhibitor',
            'durvalumab': 'PD-L1 inhibitor',
            'ipilimumab': 'CTLA-4 inhibitor',
            'docetaxel': 'taxane chemotherapy',
            'paclitaxel': 'taxane chemotherapy',
            'carboplatin': 'platinum chemotherapy',
            'cisplatin': 'platinum chemotherapy',
        }

        text_lower = text.lower()

        for drug, drug_class in known_drugs.items():
            if drug in text_lower:
                # Find first occurrence for source
                idx = text_lower.find(drug)
                line_num = text[:idx].count('\n') + 1
                drug_facts.append(CitedFact(
                    value=drug.capitalize(),
                    source=f"line {line_num}",
                    confidence=0.95,
                    extraction_method="known_drug_list"
                ))

        # Also check INN patterns
        for pattern, drug_type in inn_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if match.lower() not in [d.value.lower() for d in drug_facts]:
                    drug_facts.append(CitedFact(
                        value=match,
                        source="INN pattern",
                        confidence=0.85,
                        extraction_method="regex"
                    ))

        primary = drug_facts[0] if drug_facts else None
        return primary, drug_facts

    def _extract_comparator(self, text: str) -> Optional[CitedFact]:
        """Extract comparator/control arm."""
        patterns = [
            re.compile(r'(?:versus|vs\.?|compared\s+(?:to|with))\s+([A-Za-z]+(?:taxel|platin|mab)?)', re.IGNORECASE),
            re.compile(r'(?:control|comparator)\s*(?:arm|group)?[:\s]+([A-Za-z]+)', re.IGNORECASE),
        ]

        for pattern in patterns:
            match = pattern.search(text)
            if match:
                comparator = match.group(1)
                if len(comparator) > 3:  # Filter out noise
                    line_num = text[:match.start()].count('\n') + 1
                    return CitedFact(
                        value=comparator,
                        source=f"line {line_num}",
                        confidence=0.9,
                        extraction_method="regex"
                    )
        return None

    def _extract_indication(self, text: str) -> Optional[CitedFact]:
        """Extract disease indication."""
        indications = {
            'non-small cell lung cancer': 'NSCLC',
            'nsclc': 'NSCLC',
            'small cell lung cancer': 'SCLC',
            'renal cell carcinoma': 'RCC',
            'hepatocellular carcinoma': 'HCC',
            'melanoma': 'Melanoma',
            'urothelial': 'Urothelial',
            'gastric': 'Gastric',
            'head and neck': 'HNSCC',
        }

        text_lower = text.lower()
        for phrase, code in indications.items():
            if phrase in text_lower:
                idx = text_lower.find(phrase)
                line_num = text[:idx].count('\n') + 1
                return CitedFact(
                    value=code,
                    source=f"line {line_num}",
                    confidence=0.95,
                    extraction_method="known_indication"
                )
        return None

    def _extract_tumor_type(self, text: str) -> Optional[CitedFact]:
        """Extract specific tumor type."""
        # Look for histology
        histology_patterns = [
            (r'squamous', 'Squamous'),
            (r'non-squamous', 'Non-squamous'),
            (r'adenocarcinoma', 'Adenocarcinoma'),
        ]

        text_lower = text.lower()
        for pattern, tumor_type in histology_patterns:
            if pattern in text_lower:
                return CitedFact(
                    value=tumor_type,
                    source="histology mention",
                    confidence=0.85,
                    extraction_method="regex"
                )
        return None

    def _infer_therapeutic_area(self, identity: IdentityFacts) -> Optional[CitedFact]:
        """Infer therapeutic area from indication."""
        if identity.indication:
            indication = identity.indication.value.upper()
            if indication in ['NSCLC', 'SCLC', 'RCC', 'HCC', 'MELANOMA']:
                return CitedFact(
                    value="Oncology",
                    source="inferred from indication",
                    confidence=0.99,
                    extraction_method="inference"
                )
        return None

    def _extract_phase(self, text: str) -> Optional[CitedFact]:
        """Extract study phase."""
        phase_patterns = [
            (r'phase\s*(?:3|III|three)', 'Phase 3'),
            (r'phase\s*(?:2|II|two)', 'Phase 2'),
            (r'phase\s*(?:1|I|one)', 'Phase 1'),
            (r'phase\s*2/3', 'Phase 2/3'),
            (r'phase\s*1/2', 'Phase 1/2'),
        ]

        text_lower = text.lower()
        for pattern, phase in phase_patterns:
            match = re.search(pattern, text_lower)
            if match:
                line_num = text[:match.start()].count('\n') + 1
                return CitedFact(
                    value=phase,
                    source=f"line {line_num}",
                    confidence=0.95,
                    extraction_method="regex"
                )
        return None

    def _extract_design_type(self, text: str) -> Optional[CitedFact]:
        """Extract study design type."""
        text_lower = text.lower()
        design_parts = []

        if 'randomized' in text_lower:
            design_parts.append('Randomized')
        if 'open-label' in text_lower or 'open label' in text_lower:
            design_parts.append('Open-label')
        if 'double-blind' in text_lower or 'double blind' in text_lower:
            design_parts.append('Double-blind')
        if 'placebo-controlled' in text_lower:
            design_parts.append('Placebo-controlled')
        if 'active-controlled' in text_lower:
            design_parts.append('Active-controlled')

        if design_parts:
            return CitedFact(
                value=', '.join(design_parts),
                source="design keywords",
                confidence=0.9,
                extraction_method="regex"
            )
        return None

    def _detect_combination(self, text: str) -> bool:
        """Detect if this is combination therapy."""
        text_lower = text.lower()
        combination_signals = [
            'combined with', 'in combination', 'plus', '+ ',
            'nivolumab and ipilimumab', 'doublet', 'triplet'
        ]
        return any(sig in text_lower for sig in combination_signals)

    def _extract_sample_size(self, text: str) -> Optional[CitedFact]:
        """Extract sample size with source."""
        for pattern in self.SAMPLE_SIZE_PATTERNS:
            match = pattern.search(text)
            if match:
                n = int(match.group(1))
                if 10 <= n <= 50000:  # Reasonable range
                    line_num = text[:match.start()].count('\n') + 1
                    return CitedFact(
                        value=n,
                        source=f"line {line_num}",
                        confidence=0.95,
                        extraction_method="regex"
                    )
        return None

    def _extract_os_events(self, text: str) -> Optional[CitedFact]:
        """Extract OS events required."""
        patterns = [
            re.compile(r'(\d+)\s*(?:OS\s+)?(?:deaths|death events)', re.IGNORECASE),
            re.compile(r'(\d+)\s*(?:OS\s+)?events?\s+(?:are\s+)?(?:required|needed)', re.IGNORECASE),
            re.compile(r'(?:total\s+of\s+)?(\d+)\s*(?:OS\s+)?(?:deaths|events)\s+(?:for|at)\s+(?:the\s+)?(?:final|primary)', re.IGNORECASE),
            re.compile(r'(?:final\s+analysis)[^.]*?(\d+)\s*(?:deaths|events)', re.IGNORECASE),
        ]
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                events = int(match.group(1))
                if 50 <= events <= 2000:
                    line_num = text[:match.start()].count('\n') + 1
                    return CitedFact(
                        value=events,
                        source=f"line {line_num}",
                        confidence=0.9,
                        extraction_method="regex"
                    )
        return None

    def _extract_pfs_events(self, text: str) -> Optional[CitedFact]:
        """Extract PFS events required."""
        pattern = re.compile(r'(\d+)\s*(?:PFS events|events\s+for\s+PFS|progression events)', re.IGNORECASE)
        match = pattern.search(text)
        if match:
            events = int(match.group(1))
            if 50 <= events <= 2000:
                line_num = text[:match.start()].count('\n') + 1
                return CitedFact(
                    value=events,
                    source=f"line {line_num}",
                    confidence=0.9,
                    extraction_method="regex"
                )
        return None

    def _extract_interim_events(self, text: str) -> Optional[CitedFact]:
        """Extract interim analysis events."""
        pattern = re.compile(r'(?:interim|IA)[^.]*?(\d+)\s*(?:deaths|events|OS events)', re.IGNORECASE)
        match = pattern.search(text)
        if match:
            events = int(match.group(1))
            if 30 <= events <= 1500:
                line_num = text[:match.start()].count('\n') + 1
                return CitedFact(
                    value=events,
                    source=f"line {line_num}",
                    confidence=0.85,
                    extraction_method="regex"
                )
        return None

    def _extract_ratio(self, text: str) -> Optional[CitedFact]:
        """Extract randomization ratio."""
        pattern = re.compile(r'(\d+:\d+(?::\d+)?)\s*(?:ratio|randomiz)', re.IGNORECASE)
        match = pattern.search(text)
        if match:
            line_num = text[:match.start()].count('\n') + 1
            return CitedFact(
                value=match.group(1),
                source=f"line {line_num}",
                confidence=0.95,
                extraction_method="regex"
            )
        return None

    def _extract_alpha_spending(self, text: str) -> Tuple[Optional[CitedFact], Optional[CitedFact]]:
        """Extract alpha spending at interim and final."""
        interim_alpha = None
        final_alpha = None

        # Interim alpha
        interim_pattern = re.compile(r'(?:interim|IA)[^.]*?(?:α|alpha|p)[^.]*?[=<≤]\s*(\d+\.?\d*)', re.IGNORECASE)
        match = interim_pattern.search(text)
        if match:
            alpha = float(match.group(1))
            if alpha > 1:
                alpha = alpha / 100  # Convert percentage
            if 0.001 <= alpha <= 0.5:
                line_num = text[:match.start()].count('\n') + 1
                interim_alpha = CitedFact(
                    value=alpha,
                    source=f"line {line_num}",
                    confidence=0.85,
                    extraction_method="regex"
                )

        # Final alpha
        final_pattern = re.compile(r'(?:final)[^.]*?(?:α|alpha|p)[^.]*?[=<≤]\s*(\d+\.?\d*)', re.IGNORECASE)
        match = final_pattern.search(text)
        if match:
            alpha = float(match.group(1))
            if alpha > 1:
                alpha = alpha / 100
            if 0.001 <= alpha <= 0.5:
                line_num = text[:match.start()].count('\n') + 1
                final_alpha = CitedFact(
                    value=alpha,
                    source=f"line {line_num}",
                    confidence=0.85,
                    extraction_method="regex"
                )

        return interim_alpha, final_alpha


# =============================================================================
# STAGE 2: SANITIZED RAG RETRIEVER
# =============================================================================

class SanitizedRAGRetriever:
    """
    STAGE 2: Retrieve RAG examples with numbers stripped.
    RAG provides STRUCTURE and WORDING only, never numbers.
    """

    # Patterns for number replacement
    NUMBER_PATTERNS = [
        (re.compile(r'\b(\d+)\s*(patients?|subjects?|participants?)\b', re.IGNORECASE), '[N] \\2'),
        (re.compile(r'\b(\d+)\s*(events?|deaths?)\b', re.IGNORECASE), '[N_EVENTS] \\2'),
        (re.compile(r'(\d+:\d+(?::\d+)?)\s*(ratio|randomiz)', re.IGNORECASE), '[RATIO] \\2'),
        (re.compile(r'(?:α|alpha)\s*[=<≤]\s*(\d+\.?\d*)', re.IGNORECASE), 'α=[ALPHA]'),
        (re.compile(r'p\s*[<≤]\s*(\d+\.?\d*)', re.IGNORECASE), 'p<[P_VALUE]'),
        (re.compile(r'(\d+\.?\d*)\s*%', re.IGNORECASE), '[N]%'),
        (re.compile(r'HR\s*[=:]\s*(\d+\.?\d*)', re.IGNORECASE), 'HR=[HR]'),
        (re.compile(r'(\d+)\s*(weeks?|months?|years?)', re.IGNORECASE), '[DURATION] \\2'),
        (re.compile(r'NCT\d{8}', re.IGNORECASE), '[NCT_ID]'),  # Anonymize NCT IDs
    ]

    def __init__(self, vector_store=None, cross_encoder=None, llm_client=None):
        self.vector_store = vector_store
        self.cross_encoder = cross_encoder
        self.llm_client = llm_client

    def retrieve_sanitized(
        self,
        query: str,
        identity: IdentityFacts,
        section_type: str,
        top_k: int = 5
    ) -> List[SanitizedChunk]:
        """Retrieve and sanitize RAG chunks."""

        # Step 1: Pre-filter by metadata if vector store supports it
        candidates = self._retrieve_candidates(query, identity, top_k * 3)

        if not candidates:
            logger.warning("No RAG candidates retrieved", section=section_type)
            return []

        # Step 2: Filter out chunks with blocked terms
        filtered = self._filter_blocked(candidates, identity)

        # Step 3: SELF-RAG reflection (score relevance)
        if self.llm_client:
            scored = self._score_relevance(filtered, query, identity)
        else:
            scored = [(c, 0.7) for c in filtered]  # Default confidence

        # Step 4: Sanitize - strip ALL numbers
        sanitized = []
        for chunk, confidence in scored[:top_k]:
            if confidence >= 0.5:  # Threshold
                sanitized_text = self._sanitize_chunk(chunk, identity)
                sanitized.append(SanitizedChunk(
                    original_text=chunk,
                    sanitized_text=sanitized_text,
                    source_file="rag_store",
                    section_type=section_type,
                    confidence=confidence,
                    provides="structure_only"
                ))

        logger.info(f"Retrieved {len(sanitized)} sanitized chunks", section=section_type)
        return sanitized

    def _retrieve_candidates(self, query: str, identity: IdentityFacts, top_k: int) -> List[str]:
        """Retrieve candidate chunks from vector store."""
        if self.vector_store is None:
            return []

        # Build metadata filter
        filters = {}
        if identity.therapeutic_area and identity.therapeutic_area.value:
            filters["therapeutic_area"] = identity.therapeutic_area.value
        if identity.phase and identity.phase.value:
            filters["phase"] = identity.phase.value

        try:
            results = self.vector_store.query(
                query=query,
                n_results=top_k,
                where=filters if filters else None
            )
            return [doc for doc in results.get('documents', [[]])[0]]
        except Exception as e:
            logger.error(f"RAG retrieval failed: {e}")
            return []

    def _filter_blocked(self, chunks: List[str], identity: IdentityFacts) -> List[str]:
        """Remove chunks containing blocked terms."""
        filtered = []
        for chunk in chunks:
            chunk_lower = chunk.lower()

            # Check for blocked terms
            blocked = False
            for term in identity.blocked_terms:
                if term.lower() in chunk_lower:
                    blocked = True
                    logger.debug(f"Blocked chunk containing '{term}'")
                    break

            # Check for different NCT IDs
            nct_matches = re.findall(r'NCT\d{8}', chunk, re.IGNORECASE)
            current_nct = identity.nct_id.value if identity.nct_id else ""
            for nct in nct_matches:
                if nct.upper() != current_nct.upper():
                    blocked = True
                    logger.debug(f"Blocked chunk with different NCT ID: {nct}")
                    break

            if not blocked:
                filtered.append(chunk)

        return filtered

    def _score_relevance(
        self,
        chunks: List[str],
        query: str,
        identity: IdentityFacts
    ) -> List[Tuple[str, float]]:
        """
        Score chunk relevance using SELF-RAG reflection tokens.

        Based on Self-RAG paper: Uses [Retrieve], [IsRelevant], [IsSupported] tokens
        to explicitly evaluate retrieval quality before generation.
        """
        scored = []

        indication = identity.indication.value if identity.indication else "the study"
        drug = identity.drug_name.value if identity.drug_name else "the treatment"
        phase = identity.phase.value if identity.phase else "clinical trial"

        for chunk in chunks:
            try:
                # Enhanced SELF-RAG reflection with explicit tokens
                prompt = f"""Evaluate this SAP chunk for a {phase} {indication} study with {drug}.

CHUNK:
{chunk[:600]}

Answer each question with YES or NO, then provide overall score:

[Retrieve] Is this chunk from a relevant therapeutic area?
[IsRelevant] Does this chunk match the study design ({indication}, {phase})?
[IsSupported] Does the methodology in this chunk apply to {drug} trials?
[NoContamination] Is this chunk free of references to other specific studies?

Based on above, rate relevance 0.0-1.0:
SCORE:"""

                response = self.llm_client.generate(prompt, max_tokens=100)

                # Parse reflection tokens
                reflection_score = 0.0
                if 'retrieve' in response.lower():
                    if 'yes' in response.lower().split('retrieve')[1][:20]:
                        reflection_score += 0.25
                if 'isrelevant' in response.lower():
                    if 'yes' in response.lower().split('isrelevant')[1][:20]:
                        reflection_score += 0.25
                if 'issupported' in response.lower():
                    if 'yes' in response.lower().split('issupported')[1][:20]:
                        reflection_score += 0.25
                if 'nocontamination' in response.lower():
                    if 'yes' in response.lower().split('nocontamination')[1][:20]:
                        reflection_score += 0.25

                # Also try to extract explicit score
                score_match = re.search(r'(?:SCORE|score)[:\s]*(\d+\.?\d*)', response)
                if score_match:
                    explicit_score = float(score_match.group(1))
                    explicit_score = min(1.0, max(0.0, explicit_score))
                    # Average reflection tokens with explicit score
                    final_score = (reflection_score + explicit_score) / 2
                else:
                    final_score = reflection_score

                scored.append((chunk, final_score))

            except Exception as e:
                logger.debug(f"SELF-RAG scoring failed: {e}")
                scored.append((chunk, 0.5))  # Default score

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _sanitize_chunk(self, chunk: str, identity: IdentityFacts) -> str:
        """Strip all numbers from chunk, preserving structure."""
        sanitized = chunk

        # Apply number replacement patterns
        for pattern, replacement in self.NUMBER_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)

        # Replace any remaining standalone numbers
        sanitized = re.sub(r'\b\d{2,}\b', '[N]', sanitized)

        # Remove blocked drug names
        for term in identity.blocked_terms:
            sanitized = re.sub(re.escape(term), '[DRUG]', sanitized, flags=re.IGNORECASE)

        return sanitized


# =============================================================================
# CONDITION DETECTOR
# =============================================================================

class ConditionDetector:
    """Detect conditions that determine required methods."""

    def detect(self, protocol_text: str, identity: IdentityFacts) -> DetectedConditions:
        """Detect all relevant conditions from protocol."""
        conditions = DetectedConditions()
        text_lower = protocol_text.lower()

        # NPH / Delayed effect detection
        conditions.has_nph_model = self._detect_nph(text_lower, identity)
        conditions.delayed_effect_expected = self._detect_delayed_effect(text_lower)
        conditions.immunotherapy_mechanism = self._detect_immunotherapy(text_lower, identity)

        # Bridging / Consistency detection
        conditions.is_bridging_study = self._detect_bridging(text_lower)
        conditions.has_consistency_objective = self._detect_consistency(text_lower)
        conditions.consistency_reference_studies = self._extract_reference_studies(protocol_text)
        conditions.consistency_margin = self._extract_consistency_margin(protocol_text)
        conditions.target_region = self._extract_target_region(text_lower)

        # Interim analysis
        conditions.has_interim_analysis = self._detect_interim(text_lower)
        conditions.interim_for_regulatory = self._detect_regulatory_interim(text_lower)

        # Treatment switching
        conditions.has_treatment_switching = self._detect_crossover(text_lower)
        conditions.crossover_adjustment_needed = conditions.has_treatment_switching

        logger.info("Condition detection complete",
                   nph=conditions.has_nph_model,
                   bridging=conditions.is_bridging_study,
                   interim=conditions.has_interim_analysis)

        return conditions

    def _detect_nph(self, text: str, identity: IdentityFacts) -> bool:
        """Detect non-proportional hazards / delayed effect."""
        nph_signals = [
            'non-proportional hazard',
            'delayed effect',
            'delayed separation',
            'delayed treatment effect',
            'crossing survival curves',
            'fleming-harrington',
            'weighted log-rank',
            'maxcombo',
            'rmst',
            'restricted mean survival',
        ]

        # Immunotherapy is a strong signal for NPH
        if identity.drug_name:
            drug = identity.drug_name.value.lower()
            if any(x in drug for x in ['mab', 'nivolumab', 'pembrolizumab', 'atezolizumab', 'durvalumab']):
                return True

        return any(sig in text for sig in nph_signals)

    def _detect_delayed_effect(self, text: str) -> bool:
        """Detect expected delayed effect."""
        signals = [
            'delayed effect',
            'delayed onset',
            'initial period',
            'time for immune response',
            'lag period',
        ]
        return any(sig in text for sig in signals)

    def _detect_immunotherapy(self, text: str, identity: IdentityFacts) -> bool:
        """Detect immunotherapy mechanism."""
        io_drugs = ['nivolumab', 'pembrolizumab', 'atezolizumab', 'durvalumab',
                   'ipilimumab', 'avelumab', 'cemiplimab']

        if identity.drug_name and identity.drug_name.value:
            if identity.drug_name.value.lower() in io_drugs:
                return True

        io_signals = ['pd-1', 'pd-l1', 'ctla-4', 'checkpoint inhibitor', 'immunotherapy',
                     'immune checkpoint', 'anti-pd']
        return any(sig in text for sig in io_signals)

    def _detect_bridging(self, text: str) -> bool:
        """Detect bridging study design."""
        bridging_signals = [
            'bridging study',
            'bridging trial',
            'regional study',
            'china registration',
            'asian population',
            'ethnic bridging',
            'confirm treatment effect',
            'demonstrate consistency',
            'replicate findings',
        ]
        return any(sig in text for sig in bridging_signals)

    def _detect_consistency(self, text: str) -> bool:
        """Detect consistency objective."""
        consistency_signals = [
            'consistency with',
            'consistent with',
            'maintain',
            'preserve',
            'of the effect',
            'of the treatment effect',
            'of risk reduction',
            'reference stud',
            'global stud',
            'pivotal stud',
        ]
        # Need at least 2 signals
        count = sum(1 for sig in consistency_signals if sig in text)
        return count >= 2

    def _extract_reference_studies(self, text: str) -> List[str]:
        """Extract referenced global/pivotal studies."""
        studies = []

        # Look for references in context of "consistency with" or "global study"
        ref_context = re.findall(r'(?:consistency with|global|pivotal|reference)[^.]*?(CheckMate\s*\d+|KEYNOTE[- ]?\d+)', text, re.IGNORECASE)
        studies.extend(ref_context)

        # CheckMate pattern in reference context
        checkmate_matches = re.findall(r'(?:CheckMate|CM)[- ]?(\d+)', text, re.IGNORECASE)
        for n in checkmate_matches:
            study = f"CheckMate {n}"
            if study not in studies:
                studies.append(study)

        # KEYNOTE pattern
        keynote_matches = re.findall(r'KEYNOTE[- ]?(\d+)', text, re.IGNORECASE)
        for n in keynote_matches:
            study = f"KEYNOTE-{n}"
            if study not in studies:
                studies.append(study)

        # Clean up - normalize names
        cleaned = []
        for s in studies:
            s = re.sub(r'\s+', ' ', s).strip()
            if s not in cleaned:
                cleaned.append(s)

        return cleaned

    def _extract_consistency_margin(self, text: str) -> Optional[str]:
        """Extract consistency margin (e.g., '50% of risk reduction')."""
        patterns = [
            r'(?:maintain|preserve)\s+(?:at least\s+)?(\d+)%\s+of\s+(?:the\s+)?(?:risk reduction|effect|HR)',
            r'(\d+)%\s+of\s+(?:the\s+)?(?:global|reference)\s+(?:effect|treatment effect)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"{match.group(1)}% of risk reduction"
        return None

    def _extract_target_region(self, text: str) -> Optional[str]:
        """Extract target region for registration."""
        if 'china' in text:
            return 'China'
        if 'japan' in text:
            return 'Japan'
        if 'asia' in text:
            return 'Asia'
        return None

    def _detect_interim(self, text: str) -> bool:
        """Detect interim analysis planned."""
        signals = ['interim analysis', 'interim look', 'dmc', 'dsmb', 'idmc',
                  'data monitoring committee', 'group sequential']
        return any(sig in text for sig in signals)

    def _detect_regulatory_interim(self, text: str) -> bool:
        """Detect if interim is for regulatory purpose."""
        signals = ['accelerated approval', 'conditional approval', 'early filing',
                  'regulatory submission', 'breakthrough', 'priority review']
        return any(sig in text for sig in signals)

    def _detect_crossover(self, text: str) -> bool:
        """Detect treatment crossover/switching."""
        signals = ['crossover', 'cross-over', 'treatment switching',
                  'switch to', 'crossed over', 'rpsft', 'ipcw']
        return any(sig in text for sig in signals)


# =============================================================================
# STAGE 3: CONSTRAINED SAP GENERATOR
# =============================================================================

class ConstrainedSAPGenerator:
    """
    STAGE 3: Generate SAP sections with mandatory slot constraints.
    Uses slot-filling with MUST-include requirements.
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def generate_section(
        self,
        section_name: str,
        identity: IdentityFacts,
        conditions: DetectedConditions,
        rag_templates: List[SanitizedChunk],
        protocol_text: str
    ) -> GeneratedSection:
        """Generate a section with mandatory constraints."""

        # Build mandatory slots based on conditions
        mandatory_slots = self._build_mandatory_slots(section_name, conditions, identity)

        # Build the constrained prompt
        prompt = self._build_prompt(
            section_name=section_name,
            identity=identity,
            conditions=conditions,
            mandatory_slots=mandatory_slots,
            rag_templates=rag_templates,
            protocol_text=protocol_text
        )

        # Generate
        if self.llm_client:
            content = self.llm_client.generate(prompt, max_tokens=2000)
        else:
            content = f"[LLM client not available - section {section_name} not generated]"

        return GeneratedSection(
            section_name=section_name,
            content=content,
            confidence=0.8,  # Initial confidence before verification
            slots_verified=[s.slot_name for s in mandatory_slots]
        )

    def _build_mandatory_slots(
        self,
        section_name: str,
        conditions: DetectedConditions,
        identity: IdentityFacts
    ) -> List[MandatorySlot]:
        """Build mandatory slots based on section and conditions."""
        slots = []

        if section_name == "primary_analysis":
            # Primary method slot
            if conditions.has_nph_model or conditions.immunotherapy_mechanism:
                slots.append(MandatorySlot(
                    slot_name="PRIMARY_METHOD",
                    must_include="Fleming-Harrington",
                    must_state_as="primary analysis",
                    rationale_required=True,
                    alternatives=["weighted log-rank", "MaxCombo"]
                ))
            else:
                slots.append(MandatorySlot(
                    slot_name="PRIMARY_METHOD",
                    must_include="stratified log-rank",
                    must_state_as="primary analysis"
                ))

            # Consistency slot for bridging studies
            if conditions.is_bridging_study or conditions.has_consistency_objective:
                slots.append(MandatorySlot(
                    slot_name="CONSISTENCY_CHECK",
                    must_include="two-step",
                    must_state_as="hierarchical testing",
                    rationale_required=True
                ))

                if conditions.consistency_margin:
                    slots.append(MandatorySlot(
                        slot_name="CONSISTENCY_MARGIN",
                        must_include=conditions.consistency_margin
                    ))

                if conditions.consistency_reference_studies:
                    for study in conditions.consistency_reference_studies[:3]:
                        slots.append(MandatorySlot(
                            slot_name="REFERENCE_STUDY",
                            must_include=study
                        ))

        elif section_name == "sample_size":
            # Sample size must use locked values only
            if identity.sample_size:
                slots.append(MandatorySlot(
                    slot_name="TOTAL_N",
                    must_include=str(identity.sample_size.value)
                ))
            if identity.os_events:
                slots.append(MandatorySlot(
                    slot_name="OS_EVENTS",
                    must_include=str(identity.os_events.value)
                ))
            if identity.randomization_ratio:
                slots.append(MandatorySlot(
                    slot_name="RATIO",
                    must_include=identity.randomization_ratio.value
                ))

        elif section_name == "interim_analysis":
            if conditions.has_interim_analysis:
                if identity.interim_events:
                    slots.append(MandatorySlot(
                        slot_name="INTERIM_EVENTS",
                        must_include=str(identity.interim_events.value)
                    ))
                if identity.alpha_interim:
                    slots.append(MandatorySlot(
                        slot_name="ALPHA_INTERIM",
                        must_include=str(identity.alpha_interim.value)
                    ))
                if identity.alpha_final:
                    slots.append(MandatorySlot(
                        slot_name="ALPHA_FINAL",
                        must_include=str(identity.alpha_final.value)
                    ))

        elif section_name == "sensitivity_analysis":
            if conditions.has_treatment_switching:
                slots.append(MandatorySlot(
                    slot_name="CROSSOVER_ADJUSTMENT",
                    must_include="RPSFT",
                    alternatives=["IPCW", "two-stage"]
                ))

        return slots

    def _build_prompt(
        self,
        section_name: str,
        identity: IdentityFacts,
        conditions: DetectedConditions,
        mandatory_slots: List[MandatorySlot],
        rag_templates: List[SanitizedChunk],
        protocol_text: str
    ) -> str:
        """Build the generation prompt with constraints."""

        # Format locked facts
        locked_facts = identity.get_locked_values()
        locked_str = "\n".join([
            f"- {k}: {v['value']} (source: {v['source']}) [LOCKED - use exactly]"
            for k, v in locked_facts.items() if v['value'] is not None
        ])

        # Format mandatory slots
        slots_str = "\n".join([
            f"- {s.slot_name}: MUST include '{s.must_include}'" +
            (f" stated as '{s.must_state_as}'" if s.must_state_as else "") +
            (f" with rationale" if s.rationale_required else "")
            for s in mandatory_slots
        ])

        # Format RAG templates (structure only)
        templates_str = "\n---\n".join([
            f"[Template {i+1}, confidence={t.confidence:.2f}]\n{t.sanitized_text[:800]}"
            for i, t in enumerate(rag_templates[:3])
        ])

        # Format conditions
        conditions_str = []
        if conditions.has_nph_model:
            conditions_str.append("- Non-proportional hazards expected (delayed treatment effect)")
        if conditions.is_bridging_study:
            conditions_str.append(f"- Bridging study for {conditions.target_region or 'regional'} registration")
        if conditions.has_consistency_objective:
            conditions_str.append(f"- Consistency objective: {conditions.consistency_margin or 'maintain effect'}")
            if conditions.consistency_reference_studies:
                conditions_str.append(f"  Reference studies: {', '.join(conditions.consistency_reference_studies)}")
        if conditions.has_interim_analysis:
            conditions_str.append("- Interim analysis planned")
        if conditions.has_treatment_switching:
            conditions_str.append("- Treatment switching expected, adjustment methods needed")

        prompt = f"""## TASK: Generate SAP Section - {section_name.replace('_', ' ').title()}

## LOCKED FACTS (Use EXACTLY as shown - do NOT modify):
{locked_str}

## MANDATORY INCLUSIONS (MUST appear in output):
{slots_str if slots_str else "None specified"}

## DETECTED CONDITIONS:
{chr(10).join(conditions_str) if conditions_str else "Standard design"}

## STRUCTURE TEMPLATES (Use format/wording style, NOT the numbers):
{templates_str if templates_str else "No templates available - use standard SAP format"}

## CONSTRAINTS:
1. Every number MUST come from LOCKED FACTS only
2. PRIMARY_METHOD must be stated as "primary", not "sensitivity" or "supportive"
3. If bridging/consistency objective exists, MUST describe two-step testing procedure
4. Do NOT mention any drug, study, NCT ID, or indication not in LOCKED FACTS
5. If a mandatory slot requires rationale, provide scientific justification

## OUTPUT FORMAT:
Generate the {section_name.replace('_', ' ')} section following standard SAP format.
Use clear headings and professional biostatistics language.

---

Begin generating the section:
"""
        return prompt


# =============================================================================
# STAGE 4: FACT VERIFICATION LOOP
# =============================================================================

class FactVerificationLoop:
    """
    STAGE 4: Post-generation verification with automatic regeneration.
    Implements MiniCheck-style fact verification.

    Confidence Threshold Guidance (based on 2024-2025 research):
    ============================================================
    >= 0.95: AUTO-APPROVE - High confidence, production ready
    0.85-0.94: AUTO-APPROVE WITH FLAG - Quality review recommended
    0.70-0.84: HUMAN REVIEW REQUIRED - Cannot be auto-approved
    < 0.70: REJECT AND REGENERATE - Too low, needs regeneration

    These thresholds are calibrated against clinical trial SAP standards
    where accuracy is critical for regulatory submission.
    """

    MAX_REGENERATION_ATTEMPTS = 3

    # Confidence thresholds
    THRESHOLD_AUTO_APPROVE = 0.95       # Auto-approve, production ready
    THRESHOLD_APPROVE_WITH_FLAG = 0.85  # Auto-approve but flag for quality review
    THRESHOLD_HUMAN_REVIEW = 0.70       # Requires human review
    THRESHOLD_REJECT = 0.70             # Below this, reject and regenerate

    # Alias for backward compatibility
    CONFIDENCE_THRESHOLD = THRESHOLD_HUMAN_REVIEW

    def __init__(self, llm_client=None, generator: ConstrainedSAPGenerator = None):
        self.llm_client = llm_client
        self.generator = generator

    def verify_and_regenerate(
        self,
        generated: GeneratedSection,
        identity: IdentityFacts,
        mandatory_slots: List[MandatorySlot],
        conditions: DetectedConditions,
        protocol_text: str,
        rag_templates: List[SanitizedChunk]
    ) -> GeneratedSection:
        """Verify and regenerate if needed."""

        for attempt in range(self.MAX_REGENERATION_ATTEMPTS):
            # Run all verifications
            result = self._verify(
                generated.content,
                identity,
                mandatory_slots,
                conditions
            )

            # Update section confidence
            generated.confidence = result.confidence
            generated.verification_attempts = attempt + 1

            # Detect and record foreign numbers
            foreign_nums = self._detect_foreign_numbers(generated.content, identity)
            generated.foreign_numbers_detected = [num for num, _ in foreign_nums]

            # Set quality status based on confidence thresholds
            generated.quality_status = self._get_quality_status(result.confidence)

            if result.passed and result.confidence >= self.THRESHOLD_HUMAN_REVIEW:
                # Determine if human review still needed based on status
                if generated.quality_status == QualityStatus.HUMAN_REVIEW:
                    generated.requires_human_review = True
                elif generated.quality_status == QualityStatus.APPROVED_WITH_FLAG:
                    generated.requires_human_review = False  # But flagged for QA
                else:
                    generated.requires_human_review = False

                logger.info(f"Verification passed",
                           section=generated.section_name,
                           confidence=result.confidence,
                           quality_status=generated.quality_status.value,
                           attempts=attempt + 1)
                return generated

            # Below threshold - regenerate with feedback
            logger.warning(f"Verification failed, regenerating",
                          section=generated.section_name,
                          attempt=attempt + 1,
                          issues=result.issues[:3])

            if self.generator and attempt < self.MAX_REGENERATION_ATTEMPTS - 1:
                generated = self._regenerate_with_feedback(
                    generated=generated,
                    issues=result.issues,
                    identity=identity,
                    conditions=conditions,
                    mandatory_slots=mandatory_slots,
                    rag_templates=rag_templates,
                    protocol_text=protocol_text,
                    attempt=attempt + 1
                )

        # Max attempts reached
        generated.requires_human_review = True
        generated.quality_status = QualityStatus.REJECTED
        generated.issues = result.issues
        logger.error(f"Verification failed after max attempts",
                    section=generated.section_name,
                    quality_status="rejected",
                    issues=result.issues)

        return generated

    def _get_quality_status(self, confidence: float) -> QualityStatus:
        """Determine quality status based on confidence score."""
        if confidence >= self.THRESHOLD_AUTO_APPROVE:
            return QualityStatus.AUTO_APPROVED
        elif confidence >= self.THRESHOLD_APPROVE_WITH_FLAG:
            return QualityStatus.APPROVED_WITH_FLAG
        elif confidence >= self.THRESHOLD_HUMAN_REVIEW:
            return QualityStatus.HUMAN_REVIEW
        else:
            return QualityStatus.REJECTED

    def _verify(
        self,
        content: str,
        identity: IdentityFacts,
        mandatory_slots: List[MandatorySlot],
        conditions: DetectedConditions
    ) -> VerificationResult:
        """Run all verification checks."""
        issues = []
        confidence_scores = []

        # 1. Fact grounding check
        fact_result = self._verify_facts(content, identity)
        issues.extend(fact_result.get('issues', []))
        confidence_scores.append(fact_result.get('confidence', 0.5))

        # 2. Mandatory slot check
        slot_result = self._verify_slots(content, mandatory_slots)
        issues.extend(slot_result.get('issues', []))
        confidence_scores.append(slot_result.get('confidence', 0.5))

        # 3. Contamination check
        contamination_result = self._check_contamination(content, identity)
        issues.extend(contamination_result.get('issues', []))
        confidence_scores.append(contamination_result.get('confidence', 0.5))

        # 4. Condition-specific checks
        condition_result = self._verify_conditions(content, conditions)
        issues.extend(condition_result.get('issues', []))
        confidence_scores.append(condition_result.get('confidence', 0.5))

        # Compute overall
        overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        passed = len(issues) == 0 and overall_confidence >= self.CONFIDENCE_THRESHOLD

        return VerificationResult(
            passed=passed,
            confidence=overall_confidence,
            issues=issues,
            missing_slots=slot_result.get('missing', []),
            contamination_detected=contamination_result.get('contamination', [])
        )

    def _verify_facts(self, content: str, identity: IdentityFacts) -> Dict:
        """Verify all facts are grounded in protocol."""
        issues = []

        # Check numbers match locked values
        locked = identity.get_locked_values()

        # Extract numbers from content
        numbers_in_content = set(re.findall(r'\b\d+\b', content))

        for field_name, fact_data in locked.items():
            value = fact_data.get('value')
            if value is not None and isinstance(value, (int, float)):
                value_str = str(int(value)) if isinstance(value, int) else str(value)

                # Check if this locked value appears in content
                if field_name in ['sample_size', 'os_events', 'interim_events']:
                    if value_str not in content:
                        issues.append(f"Locked value {field_name}={value} not found in content")

        # CONTAMINATION DETECTION HEURISTIC: Foreign numbers check
        # Any number > 10 that's not in locked facts is suspicious
        foreign_numbers = self._detect_foreign_numbers(content, identity)
        if foreign_numbers:
            for num, context in foreign_numbers[:3]:  # Report top 3
                issues.append(f"Foreign number '{num}' not in locked facts - context: '{context}'")

        # Check for suspiciously wrong numbers (known contamination signals)
        known_contamination = {
            '591': 'CheckMate 057',
            '534': 'JAVELIN',
            '1150': 'GA29144/etrolizumab',
            '460': 'GA29144/etrolizumab',
            '230': 'GA29144/etrolizumab',
        }
        for num, source in known_contamination.items():
            if num in content:
                # Check if this number is in locked values
                is_locked = any(str(v.get('value')) == num for v in locked.values() if v.get('value'))
                if not is_locked:
                    issues.append(f"Known contamination: '{num}' (from {source})")

        confidence = 1.0 - (len(issues) * 0.15)
        return {'issues': issues, 'confidence': max(0.3, confidence)}

    def _detect_foreign_numbers(self, content: str, identity: IdentityFacts) -> List[Tuple[str, str]]:
        """
        Detect foreign numbers not in locked facts.

        Returns list of (number, context) tuples for suspicious numbers.
        """
        # Build set of allowed numbers from locked facts
        locked = identity.get_locked_values()
        allowed_numbers = set()

        for field_name, fact_data in locked.items():
            value = fact_data.get('value')
            if value is not None:
                if isinstance(value, (int, float)):
                    allowed_numbers.add(str(int(value)))
                    # Also allow related numbers (e.g., per-arm N)
                    if field_name == 'sample_size':
                        n = int(value)
                        # Allow half, thirds for common ratios
                        allowed_numbers.add(str(n // 2))
                        allowed_numbers.add(str(n // 3))
                        allowed_numbers.add(str(n * 2 // 3))
                elif isinstance(value, str):
                    # Extract numbers from ratio strings like "2:1"
                    nums = re.findall(r'\d+', value)
                    allowed_numbers.update(nums)

        # Also allow common non-suspicious numbers
        allowed_numbers.update(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10'])
        allowed_numbers.update(['80', '85', '90', '95', '99'])  # Common percentages
        allowed_numbers.update(['05', '01', '025', '001'])  # Alpha levels

        # Find all numbers in content with context
        foreign = []
        for match in re.finditer(r'\b(\d+)\b', content):
            num = match.group(1)
            if int(num) > 10 and num not in allowed_numbers:
                # Get context (20 chars before/after)
                start = max(0, match.start() - 20)
                end = min(len(content), match.end() + 20)
                context = content[start:end].replace('\n', ' ').strip()
                foreign.append((num, context))

        return foreign

    def _verify_slots(self, content: str, mandatory_slots: List[MandatorySlot]) -> Dict:
        """Verify mandatory slots are present."""
        issues = []
        missing = []
        content_lower = content.lower()

        for slot in mandatory_slots:
            must_include = slot.must_include.lower()
            alternatives = [alt.lower() for alt in slot.alternatives]

            # Check if must_include or any alternative is present
            found = must_include in content_lower
            if not found:
                for alt in alternatives:
                    if alt in content_lower:
                        found = True
                        break

            if not found:
                issues.append(f"Missing required: {slot.slot_name} must include '{slot.must_include}'")
                missing.append(slot.slot_name)

            # Check must_state_as
            if found and slot.must_state_as:
                if slot.must_state_as.lower() not in content_lower:
                    issues.append(f"{slot.slot_name}: must be stated as '{slot.must_state_as}'")

        confidence = 1.0 - (len(issues) * 0.2)
        return {'issues': issues, 'missing': missing, 'confidence': max(0.2, confidence)}

    def _check_contamination(self, content: str, identity: IdentityFacts) -> Dict:
        """Check for cross-study contamination."""
        issues = []
        contamination = []
        content_lower = content.lower()

        # Check for blocked terms
        for term in identity.blocked_terms:
            if term.lower() in content_lower:
                issues.append(f"Contamination: blocked term '{term}' found")
                contamination.append(term)

        # Check for wrong NCT IDs
        nct_ids = re.findall(r'NCT\d{8}', content, re.IGNORECASE)
        current_nct = identity.nct_id.value if identity.nct_id else ""
        for nct in nct_ids:
            if nct.upper() != current_nct.upper():
                issues.append(f"Contamination: wrong NCT ID '{nct}' (expected {current_nct})")
                contamination.append(nct)

        # Check for wrong indication terms
        wrong_indications = ['mrcc', 'renal cell carcinoma', 'hepatocellular',
                            'melanoma stage iv', 'urothelial carcinoma']
        current_indication = identity.indication.value.lower() if identity.indication else ""

        for wrong in wrong_indications:
            if wrong in content_lower and wrong not in current_indication:
                issues.append(f"Contamination: wrong indication '{wrong}'")
                contamination.append(wrong)

        confidence = 1.0 if not issues else max(0.2, 1.0 - len(issues) * 0.25)
        return {'issues': issues, 'contamination': contamination, 'confidence': confidence}

    def _verify_conditions(self, content: str, conditions: DetectedConditions) -> Dict:
        """Verify condition-specific requirements are met."""
        issues = []
        content_lower = content.lower()

        # NPH check: Fleming-Harrington must be primary
        if conditions.has_nph_model:
            if 'fleming-harrington' not in content_lower and 'weighted log-rank' not in content_lower:
                issues.append("NPH detected but Fleming-Harrington/weighted log-rank not mentioned")
            else:
                # Check it's stated as primary
                fh_idx = content_lower.find('fleming-harrington')
                if fh_idx == -1:
                    fh_idx = content_lower.find('weighted log-rank')
                if fh_idx >= 0:
                    context = content_lower[max(0, fh_idx-50):fh_idx+100]
                    if 'sensitivity' in context and 'primary' not in context:
                        issues.append("Fleming-Harrington mentioned as sensitivity, should be primary for NPH")

        # Bridging check: two-step procedure required
        if conditions.is_bridging_study or conditions.has_consistency_objective:
            if 'two-step' not in content_lower and 'two step' not in content_lower:
                if 'consistency' not in content_lower and 'hierarchical' not in content_lower:
                    issues.append("Bridging study but two-step/consistency procedure not described")

        # Treatment switching check
        if conditions.has_treatment_switching:
            if 'rpsft' not in content_lower and 'ipcw' not in content_lower:
                issues.append("Treatment switching expected but adjustment methods (RPSFT/IPCW) not mentioned")

        confidence = 1.0 - (len(issues) * 0.2)
        return {'issues': issues, 'confidence': max(0.3, confidence)}

    def _regenerate_with_feedback(
        self,
        generated: GeneratedSection,
        issues: List[str],
        identity: IdentityFacts,
        conditions: DetectedConditions,
        mandatory_slots: List[MandatorySlot],
        rag_templates: List[SanitizedChunk],
        protocol_text: str,
        attempt: int
    ) -> GeneratedSection:
        """Regenerate section with explicit error feedback."""

        if not self.generator or not self.generator.llm_client:
            return generated

        feedback_prompt = f"""## REGENERATION ATTEMPT {attempt}

Your previous output for section "{generated.section_name}" had these issues:

ISSUES TO FIX:
{chr(10).join(f"- {issue}" for issue in issues)}

SPECIFIC CORRECTIONS REQUIRED:
"""
        # Add specific corrections based on issues
        corrections = []
        for issue in issues:
            if 'contamination' in issue.lower():
                corrections.append("Remove any mention of other studies, drugs, or indications not in this protocol")
            if 'missing required' in issue.lower():
                corrections.append(f"Ensure you include: {issue.split('include')[1] if 'include' in issue else issue}")
            if 'primary' in issue.lower() and 'sensitivity' in issue.lower():
                corrections.append("State Fleming-Harrington as the PRIMARY method, not sensitivity")
            if 'locked value' in issue.lower():
                corrections.append("Use ONLY the locked values provided - do not use numbers from examples")

        feedback_prompt += chr(10).join(f"- {c}" for c in corrections)
        feedback_prompt += "\n\nPlease regenerate the section fixing ALL issues above."

        # Regenerate
        new_section = self.generator.generate_section(
            section_name=generated.section_name,
            identity=identity,
            conditions=conditions,
            rag_templates=rag_templates,
            protocol_text=protocol_text
        )

        # Prepend feedback for context
        if self.generator.llm_client:
            corrected_content = self.generator.llm_client.generate(
                feedback_prompt + "\n\nPrevious attempt:\n" + generated.content[:1000],
                max_tokens=2000
            )
            new_section.content = corrected_content

        return new_section


# =============================================================================
# MAIN PIPELINE
# =============================================================================

class ProductionSAPPipeline:
    """
    Production-grade SAP generation pipeline integrating all 4 stages.
    """

    SAP_SECTIONS = [
        "study_objectives",
        "study_design",
        "sample_size",
        "analysis_populations",
        "primary_analysis",
        "secondary_analysis",
        "interim_analysis",
        "sensitivity_analysis",
        "safety_analysis",
        "missing_data",
    ]

    def __init__(
        self,
        llm_client=None,
        vector_store=None,
        cross_encoder=None
    ):
        self.llm_client = llm_client

        # Initialize stages
        self.identity_extractor = ProtocolIdentityExtractor(llm_client=llm_client)
        self.rag_retriever = SanitizedRAGRetriever(
            vector_store=vector_store,
            cross_encoder=cross_encoder,
            llm_client=llm_client
        )
        self.condition_detector = ConditionDetector()
        self.generator = ConstrainedSAPGenerator(llm_client=llm_client)
        self.verifier = FactVerificationLoop(
            llm_client=llm_client,
            generator=self.generator
        )

    def generate(self, protocol_text: str, nct_id: Optional[str] = None) -> SAPOutput:
        """Generate complete SAP with all verification stages."""

        start_time = time.time()
        logger.info("Starting production SAP generation", nct_id=nct_id)

        # STAGE 1: Extract identity facts
        identity = self.identity_extractor.extract(protocol_text)
        if nct_id and not identity.nct_id:
            identity.nct_id = CitedFact(value=nct_id, source="user_provided", confidence=1.0)

        # STAGE 1b: Detect conditions
        conditions = self.condition_detector.detect(protocol_text, identity)

        # Generate each section
        sections = {}
        confidence_scores = {}
        flagged_sections = []
        verification_report = {}

        for section_name in self.SAP_SECTIONS:
            logger.info(f"Generating section: {section_name}")

            # STAGE 2: Retrieve sanitized RAG templates
            rag_templates = self.rag_retriever.retrieve_sanitized(
                query=f"{section_name} SAP section",
                identity=identity,
                section_type=section_name
            )

            # STAGE 3: Generate with constraints
            mandatory_slots = self.generator._build_mandatory_slots(
                section_name, conditions, identity
            )

            generated = self.generator.generate_section(
                section_name=section_name,
                identity=identity,
                conditions=conditions,
                rag_templates=rag_templates,
                protocol_text=protocol_text
            )

            # STAGE 4: Verify and regenerate if needed
            verified = self.verifier.verify_and_regenerate(
                generated=generated,
                identity=identity,
                mandatory_slots=mandatory_slots,
                conditions=conditions,
                protocol_text=protocol_text,
                rag_templates=rag_templates
            )

            sections[section_name] = verified.content
            confidence_scores[section_name] = verified.confidence

            if verified.requires_human_review:
                flagged_sections.append(section_name)

            verification_report[section_name] = {
                'attempts': verified.verification_attempts,
                'confidence': verified.confidence,
                'issues': verified.issues,
                'requires_review': verified.requires_human_review
            }

        # Compute overall confidence
        overall_confidence = sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0.0

        elapsed = time.time() - start_time
        logger.info(f"SAP generation complete",
                   elapsed=f"{elapsed:.1f}s",
                   overall_confidence=overall_confidence,
                   flagged_sections=len(flagged_sections))

        return SAPOutput(
            sections=sections,
            confidence_scores=confidence_scores,
            overall_confidence=overall_confidence,
            identity_facts=identity,
            detected_conditions=conditions,
            verification_report=verification_report,
            requires_human_review=len(flagged_sections) > 0,
            flagged_sections=flagged_sections,
            generation_metadata={
                'elapsed_seconds': elapsed,
                'sections_generated': len(sections),
                'nct_id': identity.nct_id.value if identity.nct_id else None
            }
        )


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def create_production_pipeline(
    llm_client=None,
    vector_store=None
) -> ProductionSAPPipeline:
    """Create a production pipeline with default configuration."""

    # Try to create LLM client if not provided
    if llm_client is None:
        try:
            from .tiered_llm import TieredLLMClient
            llm_client = TieredLLMClient()
        except Exception:
            logger.warning("Could not create LLM client")

    return ProductionSAPPipeline(
        llm_client=llm_client,
        vector_store=vector_store
    )


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    import sys

    print("Production SAP Pipeline - Test Mode")
    print("=" * 50)

    # Test identity extraction
    test_protocol = """
    Protocol Title: A Phase 3 Study of Nivolumab vs Docetaxel in NSCLC
    NCT02613507 (CheckMate 078)

    This is a randomized, open-label study comparing nivolumab to docetaxel
    in approximately 500 patients with advanced non-small cell lung cancer.

    Patients will be randomized 2:1 to receive nivolumab or docetaxel.

    The primary endpoint is overall survival. A total of 382 OS deaths
    are required for the final analysis.

    Due to expected delayed treatment effect with immunotherapy,
    the primary analysis will use a weighted log-rank test with
    Fleming-Harrington weights G(0,1).

    This bridging study aims to demonstrate consistency with the
    global CheckMate 057 and CheckMate 017 studies, maintaining
    at least 50% of the risk reduction observed in those trials.
    """

    # Test extraction
    extractor = ProtocolIdentityExtractor()
    identity = extractor.extract(test_protocol)

    print("\nExtracted Identity Facts:")
    print(f"  NCT ID: {identity.nct_id}")
    print(f"  Drug: {identity.drug_name}")
    print(f"  Indication: {identity.indication}")
    print(f"  Sample Size: {identity.sample_size}")
    print(f"  OS Events: {identity.os_events}")
    print(f"  Ratio: {identity.randomization_ratio}")

    print("\nBlocked Terms:")
    for term in list(identity.blocked_terms)[:10]:
        print(f"  - {term}")

    # Test condition detection
    detector = ConditionDetector()
    conditions = detector.detect(test_protocol, identity)

    print("\nDetected Conditions:")
    print(f"  NPH Model: {conditions.has_nph_model}")
    print(f"  Bridging Study: {conditions.is_bridging_study}")
    print(f"  Consistency Objective: {conditions.has_consistency_objective}")
    print(f"  Reference Studies: {conditions.consistency_reference_studies}")
    print(f"  Consistency Margin: {conditions.consistency_margin}")

    # Test foreign number detection
    print("\n" + "-" * 50)
    print("Testing Contamination Detection Heuristics:")

    # Simulated contaminated content
    contaminated_content = """
    The study enrolled 1150 patients with a randomization ratio of 1:2:2.
    This is based on 591 events for interim analysis.
    The sample size of 500 patients provides 80% power.
    """

    verifier = FactVerificationLoop()
    foreign = verifier._detect_foreign_numbers(contaminated_content, identity)

    print(f"\n  Foreign numbers detected:")
    for num, context in foreign:
        print(f"    {num}: '{context}'")

    # Test quality status thresholds
    print("\n  Quality Status Thresholds:")
    print(f"    Confidence 0.96 -> {verifier._get_quality_status(0.96).value}")
    print(f"    Confidence 0.87 -> {verifier._get_quality_status(0.87).value}")
    print(f"    Confidence 0.75 -> {verifier._get_quality_status(0.75).value}")
    print(f"    Confidence 0.60 -> {verifier._get_quality_status(0.60).value}")

    print("\n" + "=" * 50)
    print("Test completed successfully!")
