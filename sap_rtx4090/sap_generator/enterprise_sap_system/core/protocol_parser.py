#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Protocol Parser
====================================================
TIER 1: Protocol Ingestion & Structured Parsing

Features:
- Section-based parsing using ICH E6 structure
- Clinical NER for key entity extraction
- Phase and endpoint classification
- Confidence scoring for extracted fields
"""

import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import os

from .schemas import (
    ParsedProtocol, Estimand, InterCurrentEvent, TreatmentArm,
    SampleSizeCalc, AnalysisPopulation, StatisticalMethod,
    StudyPhase, EndpointType, ICEStrategy, PopulationType,
    DesignType, BlindingType
)
from .config import get_config
from .endpoint_extractor import StructuredEndpointExtractor


class ProtocolParser:
    """
    Clinical trial protocol parser with NER and structured extraction.
    Implements TIER 1 of the enterprise SAP generation system.
    """

    # Phase detection patterns with weights
    PHASE_PATTERNS = {
        StudyPhase.PHASE_1: [
            (r'\bphase\s*[1iI]\b(?!\s*[/\\]\s*[23])', 100),
            (r'\bphase\s*[1iI][aA]\b', 100),
            (r'\bphase\s*[1iI][bB]\b', 100),
            (r'\bfirst[- ]in[- ]human\b', 90),
            (r'\bdose[- ]?escalation\b', 70),
        ],
        StudyPhase.PHASE_1_2: [
            (r'\bphase\s*[1iI]\s*[/\\]\s*[2iI]{1,2}\b', 100),
            (r'\bphase\s*[1iI][bB]?\s*/\s*[2iI]{1,2}[aA]?\b', 100),
        ],
        StudyPhase.PHASE_2: [
            (r'\bphase\s*[2iI]{1,2}\b(?!\s*[/\\]\s*[13])', 100),
            (r'\bphase\s*[2iI]{1,2}[aA]\b', 100),
            (r'\bphase\s*[2iI]{1,2}[bB]\b', 100),
        ],
        StudyPhase.PHASE_2_3: [
            (r'\bphase\s*[2iI]{1,2}\s*[/\\]\s*[3iI]{1,3}\b', 100),
        ],
        StudyPhase.PHASE_3: [
            (r'\bphase\s*[3iI]{1,3}\b(?!\s*[/\\])', 100),
            (r'\bphase\s*[3iI]{1,3}[aAbB]\b', 100),
            (r'\bpivotal\s+(?:study|trial)\b', 70),
            (r'\bconfirmatory\s+(?:study|trial)\b', 70),
        ],
        StudyPhase.PHASE_4: [
            (r'\bphase\s*[4iIvV]{1,2}\b', 100),
            (r'\bpost[- ]?marketing\b', 80),
        ],
    }

    # Endpoint type patterns - expanded for better detection
    # Patterns are applied to PRIMARY ENDPOINT section with boosted weights
    ENDPOINT_PATTERNS = {
        EndpointType.OS: [
            # High confidence - explicit primary mentions
            (r'primary\s+(?:endpoint|objective|outcome)[:\s]+[^.]*overall\s+survival', 150),
            (r'primary\s+(?:efficacy\s+)?endpoint[:\s]+[^.]*\bos\b', 140),
            (r'overall\s+survival\s+(?:is|as)\s+(?:the\s+)?primary', 140),
            # Medium confidence - OS mentioned prominently
            (r'overall\s+survival\s*\([^)]*os[^)]*\)', 100),
            (r'\bos\b[^.]{0,30}primary', 100),
            (r'primary[^.]{0,50}overall\s+survival', 100),
            (r'time\s+(?:from\s+randomization\s+)?to\s+death', 90),
            (r'median\s+overall\s+survival', 80),
            # Lower confidence - OS context
            (r'overall\s+survival', 60),
            (r'\bos\b\s*(?:=|is|defined)', 50),
        ],
        EndpointType.PFS: [
            # High confidence - explicit primary mentions
            (r'primary\s+(?:endpoint|objective|outcome)[:\s]+[^.]*progression[- ]?free', 150),
            (r'primary\s+(?:efficacy\s+)?endpoint[:\s]+[^.]*\bpfs\b', 140),
            (r'progression[- ]?free\s+survival\s+(?:is|as)\s+(?:the\s+)?primary', 140),
            # Medium confidence
            (r'progression[- ]?free\s+survival\s*\([^)]*pfs[^)]*\)', 100),
            (r'\bpfs\b[^.]{0,30}primary', 100),
            (r'primary[^.]{0,50}progression[- ]?free', 100),
            (r'time\s+to\s+(?:disease\s+)?progression', 90),
            (r'median\s+(?:progression[- ]?free\s+survival|pfs)', 80),
            # Lower confidence
            (r'progression[- ]?free\s+survival', 60),
            (r'\bpfs\b\s*(?:=|is|defined|endpoint)', 50),
        ],
        EndpointType.ORR: [
            # High confidence - explicit primary mentions
            (r'primary\s+(?:endpoint|objective|outcome)[:\s]+[^.]*(?:objective|overall)\s+response\s+rate', 150),
            (r'primary\s+(?:efficacy\s+)?endpoint[:\s]+[^.]*\borr\b', 140),
            (r'(?:objective|overall)\s+response\s+rate\s+(?:is|as)\s+(?:the\s+)?primary', 140),
            # Medium confidence
            (r'(?:objective|overall)\s+response\s+rate\s*\([^)]*orr[^)]*\)', 100),
            (r'\borr\b[^.]{0,30}primary', 100),
            (r'primary[^.]{0,50}response\s+rate', 100),
            (r'tumor\s+(?:response|shrinkage)', 80),
            (r'recist\s+(?:v?1\.1|criteria)[^.]*response', 80),
            # Lower confidence
            (r'(?:objective|overall)\s+response\s+rate', 60),
            (r'\borr\b\s*(?:=|is|defined)', 50),
            (r'confirmed\s+(?:complete|partial)\s+response', 50),
        ],
        EndpointType.SAFETY: [
            # High confidence - explicit primary mentions
            (r'primary\s+(?:endpoint|objective|outcome)[:\s]+[^.]*(?:safety|tolerability)', 150),
            (r'primary\s+(?:endpoint|objective)[:\s]+[^.]*(?:mtd|dlt|rp2d)', 150),
            (r'(?:safety|tolerability)\s+(?:is|as)\s+(?:the\s+)?primary', 140),
            # Phase 1 indicators
            (r'phase\s*[1i]\b[^.]*(?:dose[- ]?escalation|dose[- ]?finding)', 120),
            (r'(?:determine|establish|identify)[^.]*(?:mtd|rp2d|maximum\s+tolerated)', 120),
            (r'dose[- ]?limiting\s+toxicit(?:y|ies)', 110),
            (r'maximum\s+tolerated\s+dose', 110),
            # Medium confidence
            (r'first[- ]in[- ]human', 100),
            (r'\brp2d\b', 90),
            (r'\bmtd\b', 90),
            (r'dose[- ]?escalation', 80),
            (r'3\s*\+\s*3\s+design', 80),
            # Lower confidence
            (r'safety\s+and\s+tolerability', 50),
        ],
        EndpointType.PK: [
            # High confidence - explicit primary mentions
            (r'primary\s+(?:endpoint|objective|outcome)[:\s]+[^.]*pharmacokinetic', 150),
            (r'primary\s+(?:endpoint|objective)[:\s]+[^.]*(?:auc|cmax|pk\s+parameter)', 140),
            (r'pharmacokinetic[^.]*(?:is|as)\s+(?:the\s+)?primary', 140),
            # Medium confidence
            (r'pharmacokinetic\s+(?:parameters?|profile|study)', 100),
            (r'\bpk\b\s+(?:parameters?|profile|study)', 100),
            (r'bioavailability\s+(?:study|trial)', 100),
            (r'bioequivalence', 100),
            (r'drug[- ]?drug\s+interaction', 90),
            (r'\b(?:auc|cmax|tmax|clearance)\b[^.]*primary', 90),
            # Lower confidence
            (r'\bauc(?:0-inf|0-t|inf)?\b', 50),
            (r'\bcmax\b', 50),
        ],
        EndpointType.DFS: [
            # High confidence
            (r'primary\s+(?:endpoint|objective|outcome)[:\s]+[^.]*disease[- ]?free', 150),
            (r'disease[- ]?free\s+survival\s+(?:is|as)\s+(?:the\s+)?primary', 140),
            (r'primary[^.]{0,50}(?:disease[- ]?free|dfs)', 100),
            # Medium confidence
            (r'disease[- ]?free\s+survival', 80),
            (r'recurrence[- ]?free\s+survival', 80),
            (r'\bdfs\b\s*(?:=|is|defined)', 60),
            (r'adjuvant[^.]*(?:disease[- ]?free|recurrence)', 70),
        ],
        EndpointType.EFS: [
            # High confidence
            (r'primary\s+(?:endpoint|objective|outcome)[:\s]+[^.]*event[- ]?free', 150),
            (r'event[- ]?free\s+survival\s+(?:is|as)\s+(?:the\s+)?primary', 140),
            # Medium confidence
            (r'event[- ]?free\s+survival', 80),
            (r'\befs\b\s*(?:=|is|defined)', 60),
            (r'composite\s+(?:endpoint|event)', 50),
        ],
    }

    # Therapeutic area patterns
    THERAPEUTIC_AREA_PATTERNS = {
        "Oncology": [
            (r'\b(?:cancer|tumor|tumour|carcinoma|malignant|oncology|neoplasm)\b', 80),
            (r'\b(?:melanoma|leukemia|lymphoma|sarcoma|glioma|myeloma)\b', 90),
            (r'\b(?:chemotherapy|immunotherapy|targeted\s+therapy)\b', 70),
            (r'\brecist\b', 80),
        ],
        "Cardiovascular": [
            (r'\b(?:cardiovascular|cardiac|heart|coronary|arterial|hypertension)\b', 80),
            (r'\b(?:myocardial|arrhythmia|atrial|ventricular|stroke)\b', 90),
            (r'\b(?:cholesterol|lipid|statin|anticoagulant)\b', 70),
        ],
        "CNS": [
            (r'\b(?:neurological|neurodegenerative|cns|brain|alzheimer|parkinson)\b', 80),
            (r'\b(?:epilepsy|seizure|multiple\s+sclerosis|neuropathy)\b', 90),
            (r'\b(?:depression|schizophrenia|anxiety|bipolar)\b', 75),
        ],
        "Immunology": [
            (r'\b(?:immunology|autoimmune|rheumatoid|lupus|psoriasis)\b', 80),
            (r'\b(?:crohn|colitis|inflammatory\s+bowel)\b', 85),
            (r'\b(?:biologics?|monoclonal\s+antibod)\b', 60),
        ],
        "Infectious Disease": [
            (r'\b(?:infectious|infection|viral|bacterial|antibiotic)\b', 70),
            (r'\b(?:hiv|hepatitis|covid|influenza|tuberculosis)\b', 90),
            (r'\b(?:vaccine|antiviral|antimicrobial)\b', 75),
        ],
        "Metabolic": [
            (r'\b(?:diabetes|diabetic|glycemic|insulin|glucose)\b', 85),
            (r'\b(?:obesity|metabolic\s+syndrome|weight\s+loss)\b', 80),
            (r'\b(?:hba1c|fasting\s+glucose)\b', 90),
        ],
        "Respiratory": [
            (r'\b(?:respiratory|pulmonary|lung|asthma|copd)\b', 80),
            (r'\b(?:bronchitis|pneumonia|fibrosis)\b', 85),
            (r'\b(?:fev1|spirometry|inhalation)\b', 75),
        ],
    }

    # Design type patterns
    DESIGN_PATTERNS = {
        DesignType.PARALLEL: [
            (r'\bparallel[- ]?group\b', 100),
            (r'\bparallel[- ]?arm\b', 100),
            (r'\brandomized\s+(?:to|into)\s+(?:\d+|two|three|four)\s+(?:groups?|arms?)\b', 80),
        ],
        DesignType.CROSSOVER: [
            (r'\bcross[- ]?over\b', 100),
            (r'\b(\d+)[- ]period[- ](\d+)[- ]sequence\b', 90),
            (r'\bswitchover\b', 80),
        ],
        DesignType.SINGLE_ARM: [
            (r'\bsingle[- ]?arm\b', 100),
            (r'\bopen[- ]?label\s+(?:single|one)[- ]?arm\b', 95),
            (r'\bnon[- ]?randomized\b', 60),
        ],
        DesignType.ADAPTIVE: [
            (r'\badaptive\s+(?:design|trial|study)\b', 100),
            (r'\bplatform\s+trial\b', 90),
            (r'\bmaster\s+protocol\b', 80),
            (r'\bbasket\s+trial\b', 85),
            (r'\bumbrella\s+trial\b', 85),
        ],
    }

    # Blinding patterns
    BLINDING_PATTERNS = {
        BlindingType.OPEN_LABEL: [
            (r'\bopen[- ]?label\b', 100),
            (r'\bunblinded\b', 90),
            (r'\bnon[- ]?blinded\b', 90),
        ],
        BlindingType.SINGLE_BLIND: [
            (r'\bsingle[- ]?blind\b', 100),
            (r'\bsingle[- ]?masked\b', 100),
        ],
        BlindingType.DOUBLE_BLIND: [
            (r'\bdouble[- ]?blind\b', 100),
            (r'\bdouble[- ]?masked\b', 100),
        ],
    }

    def __init__(self, llm_client=None):
        """Initialize parser with optional LLM client for enhanced extraction"""
        self.config = get_config()
        self.llm_client = llm_client
        # Use advanced endpoint extractor with therapeutic area awareness
        self.endpoint_extractor = StructuredEndpointExtractor(llm_client=llm_client)

    def parse(self, protocol_text: str, nct_id: str = "") -> ParsedProtocol:
        """
        Parse a clinical trial protocol and extract structured data.

        Args:
            protocol_text: Full text of the protocol
            nct_id: NCT identifier if known

        Returns:
            ParsedProtocol with all extracted fields
        """
        # Extract NCT ID if not provided
        if not nct_id:
            nct_id = self._extract_nct_id(protocol_text)

        # Initialize result
        result = ParsedProtocol(
            nct_id=nct_id,
            raw_text_length=len(protocol_text)
        )

        # Extract text sections
        sections = self._extract_sections(protocol_text)

        # Phase detection
        result.phase, phase_conf = self._classify_phase(protocol_text)
        result.extraction_confidence["phase"] = phase_conf

        # Primary endpoint detection
        endpoint_type, endpoint_conf, endpoint_text = self._classify_endpoint(protocol_text)
        result.extraction_confidence["endpoint_type"] = endpoint_conf

        # Therapeutic area detection
        result.therapeutic_area, ta_conf = self._classify_therapeutic_area(protocol_text)
        result.extraction_confidence["therapeutic_area"] = ta_conf

        # Design type detection
        result.design_type, design_conf = self._classify_design(protocol_text)
        result.extraction_confidence["design_type"] = design_conf

        # Blinding detection
        result.blinding, blind_conf = self._classify_blinding(protocol_text)
        result.extraction_confidence["blinding"] = blind_conf

        # Extract protocol metadata
        result.protocol_number = self._extract_protocol_number(protocol_text)
        result.sponsor = self._extract_sponsor(protocol_text)
        result.study_title = self._extract_title(protocol_text)
        result.indication = self._extract_indication(protocol_text)

        # Extract randomization details
        result.randomization_ratio = self._extract_randomization_ratio(protocol_text)
        result.stratification_factors = self._extract_stratification_factors(protocol_text)

        # Extract treatment arms
        result.arms = self._extract_treatment_arms(protocol_text)

        # Extract sample size
        result.sample_size = self._extract_sample_size(protocol_text)

        # Build primary estimand
        result.primary_estimand = self._build_estimand(
            protocol_text, endpoint_type, endpoint_text, is_primary=True
        )

        # Extract analysis populations
        result.populations = self._extract_populations(protocol_text)

        # Infer statistical methods based on endpoint type
        result.statistical_methods = self._infer_statistical_methods(
            endpoint_type, result.design_type, result.phase
        )

        return result

    def _extract_sections(self, text: str) -> Dict[str, str]:
        """Extract protocol sections by headers"""
        sections = {}

        section_patterns = [
            (r'(?:^|\n)\s*(\d+\.?\d*\.?\d*)\s*(SYNOPSIS|ABSTRACT|SUMMARY)[:\s]*(.*?)(?=\n\s*\d+\.|\Z)', "synopsis"),
            (r'(?:^|\n)\s*(\d+\.?\d*\.?\d*)\s*(INTRODUCTION|BACKGROUND)[:\s]*(.*?)(?=\n\s*\d+\.|\Z)', "introduction"),
            (r'(?:^|\n)\s*(\d+\.?\d*\.?\d*)\s*(OBJECTIVES?\s+AND\s+ENDPOINTS?|STUDY\s+OBJECTIVES?)[:\s]*(.*?)(?=\n\s*\d+\.|\Z)', "objectives"),
            (r'(?:^|\n)\s*(\d+\.?\d*\.?\d*)\s*(STUDY\s+DESIGN)[:\s]*(.*?)(?=\n\s*\d+\.|\Z)', "design"),
            (r'(?:^|\n)\s*(\d+\.?\d*\.?\d*)\s*(STATISTICAL\s+(?:ANALYSIS|CONSIDERATIONS?))[:\s]*(.*?)(?=\n\s*\d+\.|\Z)', "statistics"),
            (r'(?:^|\n)\s*(\d+\.?\d*\.?\d*)\s*(SAMPLE\s+SIZE)[:\s]*(.*?)(?=\n\s*\d+\.|\Z)', "sample_size"),
        ]

        for pattern, section_name in section_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                sections[section_name] = match.group(0)[:5000]  # Limit size

        return sections

    def _classify_phase(self, text: str) -> Tuple[StudyPhase, float]:
        """Classify study phase using weighted pattern matching"""
        text_lower = text.lower()
        scores = {phase: 0 for phase in self.PHASE_PATTERNS}

        for phase, patterns in self.PHASE_PATTERNS.items():
            for pattern, weight in patterns:
                if re.search(pattern, text_lower):
                    scores[phase] += weight

        if max(scores.values()) == 0:
            return StudyPhase.UNKNOWN, 0.0

        best_phase = max(scores, key=scores.get)
        confidence = min(scores[best_phase] / 150, 1.0)
        return best_phase, confidence

    def _classify_endpoint(self, text: str) -> Tuple[EndpointType, float, str]:
        """
        Classify primary endpoint type using advanced two-stage extractor.

        Stage 1: Detect therapeutic area (IBD, Oncology, etc.)
        Stage 2: Classify endpoint with TA context and Bayesian priors
        """
        # Use the advanced endpoint extractor with therapeutic area awareness
        result = self.endpoint_extractor.extract(text)

        # Map string endpoint type to EndpointType enum
        endpoint_map = {
            "SAFETY": EndpointType.SAFETY,
            "ORR": EndpointType.ORR,
            "PFS": EndpointType.PFS,
            "OS": EndpointType.OS,
            "DFS": EndpointType.DFS,
            "EFS": EndpointType.EFS,
            "PK": EndpointType.PK,
            "EFFICACY": EndpointType.EFFICACY,
            "OTHER": EndpointType.OTHER,
        }

        endpoint_type = endpoint_map.get(result.endpoint_type, EndpointType.OTHER)

        # Build evidence string
        evidence = f"TA: {result.therapeutic_area}, Phase: {result.phase} - {result.reasoning}"

        return endpoint_type, result.confidence, evidence

    def _extract_synopsis(self, text: str, max_chars: int = 3000) -> str:
        """Extract synopsis section"""
        patterns = [
            r'(?:^|\n)\s*synopsis\s*(?:\n|:)(.*?)(?=\n\s*\d+\.|\n\s*[A-Z]{2,}|\Z)',
            r'(?:^|\n)\s*(?:study\s+)?summary\s*(?:\n|:)(.*?)(?=\n\s*\d+\.|\Z)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1)[:max_chars]
        return ""

    def _extract_primary_section(self, text: str, max_chars: int = 5000) -> str:
        """Extract the most relevant section for primary endpoint"""
        section_patterns = [
            r'(?:^|\n)\s*(?:\d+\.?\d*\.?\s*)?primary\s+(?:study\s+)?(?:endpoint|objective)s?\s*(?:\n|:)(.{100,2000})',
            r'(?:^|\n)\s*(?:\d+\.?\d*\.?\s*)?(?:study\s+)?objectives?\s*(?:\n|:)(.{100,2000})',
            r'(?:^|\n)\s*synopsis\s*(?:\n|:)(.{200,3000})',
        ]

        for pattern in section_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if match:
                return match.group(0)[:max_chars]

        return text[:max_chars]

    def _classify_therapeutic_area(self, text: str) -> Tuple[str, float]:
        """Classify therapeutic area"""
        text_lower = text.lower()
        scores = {ta: 0 for ta in self.THERAPEUTIC_AREA_PATTERNS}

        for ta, patterns in self.THERAPEUTIC_AREA_PATTERNS.items():
            for pattern, weight in patterns:
                if re.search(pattern, text_lower):
                    scores[ta] += weight

        if max(scores.values()) == 0:
            return "Other", 0.0

        best_ta = max(scores, key=scores.get)
        confidence = min(scores[best_ta] / 200, 1.0)
        return best_ta, confidence

    def _classify_design(self, text: str) -> Tuple[DesignType, float]:
        """Classify study design type"""
        text_lower = text.lower()
        scores = {d: 0 for d in self.DESIGN_PATTERNS}

        for design, patterns in self.DESIGN_PATTERNS.items():
            for pattern, weight in patterns:
                if re.search(pattern, text_lower):
                    scores[design] += weight

        if max(scores.values()) == 0:
            return DesignType.PARALLEL, 0.5  # Default assumption

        best_design = max(scores, key=scores.get)
        confidence = min(scores[best_design] / 100, 1.0)
        return best_design, confidence

    def _classify_blinding(self, text: str) -> Tuple[BlindingType, float]:
        """Classify blinding type"""
        text_lower = text.lower()
        scores = {b: 0 for b in self.BLINDING_PATTERNS}

        for blinding, patterns in self.BLINDING_PATTERNS.items():
            for pattern, weight in patterns:
                if re.search(pattern, text_lower):
                    scores[blinding] += weight

        if max(scores.values()) == 0:
            return BlindingType.OPEN_LABEL, 0.5

        best_blinding = max(scores, key=scores.get)
        confidence = min(scores[best_blinding] / 100, 1.0)
        return best_blinding, confidence

    def _extract_nct_id(self, text: str) -> str:
        """Extract NCT ID from protocol text"""
        match = re.search(r'\b(NCT\d{8})\b', text, re.IGNORECASE)
        return match.group(1).upper() if match else ""

    def _extract_protocol_number(self, text: str) -> str:
        """Extract protocol number"""
        patterns = [
            r'protocol\s*(?:number|#|no\.?)[\s:]+([A-Z0-9\-]+)',
            r'study\s*(?:number|#|no\.?)[\s:]+([A-Z0-9\-]+)',
            r'protocol[\s:]+([A-Z]{1,4}\d{4,8})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def _extract_sponsor(self, text: str) -> str:
        """Extract sponsor name"""
        patterns = [
            r'sponsor[\s:]+([A-Z][A-Za-z\s&]+?)(?:\n|,|\.)',
            r'sponsored\s+by[\s:]+([A-Z][A-Za-z\s&]+?)(?:\n|,|\.)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_title(self, text: str) -> str:
        """Extract study title with improved accuracy"""
        # Patterns in order of specificity (most specific first)
        patterns = [
            # Official/Protocol title patterns (highest priority)
            r'(?:official|protocol|full)\s+title[\s:]+([^\n]{20,300})',
            # Study title with clear context
            r'(?:^|\n)\s*study\s+title[\s:]+([^\n]{20,300})',
            # Brief title (common in ClinicalTrials.gov)
            r'brief\s+title[\s:]+([^\n]{20,300})',
            # Synopsis title
            r'synopsis[:\s]*\n[^\n]*title[\s:]+([^\n]{20,300})',
            # Title in header area (first 2000 chars)
            r'^[^\n]*title[\s:]+([^\n]{20,300})',
        ]

        # Exclusion patterns - titles that are NOT study titles
        exclude_patterns = [
            r'location\s+of\s+facility',
            r'facility\s+(?:name|location|title)',
            r'principal\s+investigator',
            r'contact\s+(?:name|title)',
            r'sponsor\s+(?:name|title)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:5000], re.IGNORECASE | re.MULTILINE)
            if match:
                title = match.group(1).strip()
                # Check if this is actually a study title (not facility/contact info)
                title_lower = title.lower()
                is_excluded = any(re.search(p, title_lower) for p in exclude_patterns)

                # Valid titles usually contain drug/disease/phase info
                has_study_keywords = any(kw in title_lower for kw in [
                    'study', 'trial', 'phase', 'patients', 'subjects',
                    'efficacy', 'safety', 'randomized', 'double-blind',
                    'placebo', 'controlled', 'treatment', 'evaluate'
                ])

                if not is_excluded and (has_study_keywords or len(title) > 50):
                    return title[:500]

        # Fallback: Look for a long descriptive sentence in synopsis
        synopsis_match = re.search(
            r'synopsis[:\s]*\n(.{50,500}?)(?:\n\n|\n[A-Z]{2,})',
            text[:3000], re.IGNORECASE | re.DOTALL
        )
        if synopsis_match:
            synopsis_text = synopsis_match.group(1).strip()
            # First substantial sentence is often the title/description
            first_sentence = re.split(r'[.\n]', synopsis_text)[0].strip()
            if len(first_sentence) > 30:
                return first_sentence[:500]

        # Last resort: Extract from "A Phase X study..." pattern
        phase_study_match = re.search(
            r'((?:a\s+)?phase\s+[1-4][ab]?(?:/[1-4][ab]?)?\s*,?\s*[^.]{20,200}(?:study|trial)[^.]*)',
            text[:5000], re.IGNORECASE
        )
        if phase_study_match:
            return phase_study_match.group(1).strip()[:500]

        return ""

    def _extract_indication(self, text: str) -> str:
        """Extract disease indication"""
        patterns = [
            r'indication[\s:]+(.+?)(?:\n)',
            r'(?:patients?\s+with|subjects?\s+with)\s+([^.]+(?:cancer|disease|disorder|syndrome|infection))',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:200]
        return ""

    def _extract_randomization_ratio(self, text: str) -> str:
        """Extract randomization ratio"""
        patterns = [
            r'randomiz(?:ed|ation)\s+(?:ratio\s+)?(?:in\s+a\s+)?(\d+\s*:\s*\d+(?:\s*:\s*\d+)?)',
            r'(\d+\s*:\s*\d+(?:\s*:\s*\d+)?)\s+randomiz',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).replace(" ", "")
        return "1:1"  # Default

    def _extract_stratification_factors(self, text: str) -> List[str]:
        """Extract stratification factors"""
        factors = []
        patterns = [
            r'stratif(?:ied|ication)\s+(?:by|factors?)[\s:]+([^.]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                factor_text = match.group(1)
                # Split by common delimiters
                parts = re.split(r'[,;]|\band\b', factor_text)
                factors.extend([p.strip() for p in parts if p.strip()])
        return factors[:10]  # Limit

    def _extract_treatment_arms(self, text: str) -> List[TreatmentArm]:
        """Extract treatment arms"""
        arms = []

        # Look for arm descriptions
        arm_patterns = [
            r'(?:arm|group)\s*([A-Z1-9])[\s:]+([^.]+)',
            r'(?:treatment|study)\s+(?:arm|group)\s*([A-Z1-9])?[\s:]+([^.]+)',
        ]

        for pattern in arm_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                arm_id = match.group(1) if match.group(1) else str(len(arms) + 1)
                description = match.group(2).strip()[:200]
                arms.append(TreatmentArm(
                    name=f"Arm {arm_id}",
                    description=description,
                    is_control="placebo" in description.lower() or "control" in description.lower()
                ))
                if len(arms) >= 6:
                    break

        return arms

    def _extract_sample_size(self, text: str) -> Optional[SampleSizeCalc]:
        """Extract sample size calculation details"""
        # Find total N
        n_patterns = [
            r'(?:approximately|total\s+of|sample\s+size[:\s]+)(\d+)\s*(?:patients?|subjects?|participants?)',
            r'(\d+)\s*(?:patients?|subjects?|participants?)\s+(?:will\s+be|to\s+be)\s+(?:enrolled|randomized)',
            r'enroll(?:ment|ing)?\s+(?:of\s+)?(\d+)',
        ]

        total_n = None
        for pattern in n_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                total_n = int(match.group(1))
                break

        if not total_n:
            return None

        # Extract power
        power = 0.8  # Default
        power_match = re.search(r'(?:power|powered)\s*(?:of)?\s*(\d{2,3})%?', text, re.IGNORECASE)
        if power_match:
            power = int(power_match.group(1)) / 100

        # Extract alpha
        alpha = 0.05  # Default
        alpha_match = re.search(r'(?:alpha|significance\s+level)\s*(?:of)?\s*(\d+\.?\d*)%?', text, re.IGNORECASE)
        if alpha_match:
            alpha = float(alpha_match.group(1))
            if alpha > 1:
                alpha /= 100

        return SampleSizeCalc(
            total_n=total_n,
            per_arm_n={},
            power=power,
            alpha=alpha,
            assumptions={}
        )

    def _extract_populations(self, text: str) -> List[AnalysisPopulation]:
        """Extract analysis population definitions"""
        populations = []

        # ITT
        itt_match = re.search(
            r'(?:intent[- ]?to[- ]?treat|itt)\s*(?:population)?[\s:]+([^.]+)',
            text, re.IGNORECASE
        )
        if itt_match:
            populations.append(AnalysisPopulation(
                name="Intent-to-Treat (ITT)",
                type=PopulationType.ITT,
                definition=itt_match.group(1).strip()[:300],
                primary_for=["efficacy"]
            ))
        else:
            populations.append(AnalysisPopulation(
                name="Intent-to-Treat (ITT)",
                type=PopulationType.ITT,
                definition="All randomized patients",
                primary_for=["efficacy"]
            ))

        # Safety
        safety_match = re.search(
            r'safety\s*(?:population|analysis\s+set)[\s:]+([^.]+)',
            text, re.IGNORECASE
        )
        populations.append(AnalysisPopulation(
            name="Safety Population",
            type=PopulationType.SAFETY,
            definition=safety_match.group(1).strip()[:300] if safety_match else
            "All patients who received at least one dose of study treatment",
            primary_for=["safety"]
        ))

        # Per-Protocol
        pp_match = re.search(
            r'per[- ]?protocol\s*(?:population)?[\s:]+([^.]+)',
            text, re.IGNORECASE
        )
        if pp_match:
            populations.append(AnalysisPopulation(
                name="Per-Protocol (PP)",
                type=PopulationType.PP,
                definition=pp_match.group(1).strip()[:300]
            ))

        return populations

    def _build_estimand(
        self,
        text: str,
        endpoint_type: EndpointType,
        endpoint_evidence: str,
        is_primary: bool = True
    ) -> Estimand:
        """Build an ICH E9(R1) compliant estimand"""

        # Define default ICE strategies based on endpoint type
        ice_strategies = self._get_default_ice_strategies(endpoint_type)

        # Extract variable description
        variable = self._extract_endpoint_variable(text, endpoint_type)

        # Determine summary measure
        summary_measure = self._get_summary_measure(endpoint_type)

        # Determine analysis method
        analysis_method = self._get_analysis_method(endpoint_type)

        return Estimand(
            objective=f"Evaluate {variable}" if variable else f"Evaluate {endpoint_type.value} endpoint",
            population="All randomized patients meeting eligibility criteria",
            treatment="Study treatment vs. control/comparator",
            variable=variable or endpoint_evidence,
            variable_type=endpoint_type,
            intercurrent_events=ice_strategies,
            summary_measure=summary_measure,
            analysis_method=analysis_method,
            is_primary=is_primary,
            confidence=0.8
        )

    def _get_default_ice_strategies(self, endpoint_type: EndpointType) -> List[InterCurrentEvent]:
        """Get default intercurrent event strategies based on endpoint type"""
        strategies = []

        # Common ICEs
        strategies.append(InterCurrentEvent(
            event="Treatment discontinuation due to adverse event",
            strategy=ICEStrategy.TREATMENT_POLICY,
            rationale="Reflects real-world treatment effect including impact of tolerability"
        ))

        if endpoint_type in [EndpointType.OS, EndpointType.PFS, EndpointType.DFS]:
            strategies.append(InterCurrentEvent(
                event="Initiation of subsequent anticancer therapy",
                strategy=ICEStrategy.TREATMENT_POLICY,
                rationale="Captures overall treatment strategy effect"
            ))
            strategies.append(InterCurrentEvent(
                event="Death before progression assessment",
                strategy=ICEStrategy.COMPOSITE,
                rationale="Death is included in the endpoint definition"
            ))

        elif endpoint_type == EndpointType.SAFETY:
            strategies.append(InterCurrentEvent(
                event="Treatment discontinuation",
                strategy=ICEStrategy.WHILE_ON_TREATMENT,
                rationale="Safety events assessed only during active treatment"
            ))

        elif endpoint_type == EndpointType.PK:
            strategies.append(InterCurrentEvent(
                event="Protocol deviation affecting PK sampling",
                strategy=ICEStrategy.HYPOTHETICAL,
                rationale="Estimate PK parameters as if sampling was per protocol"
            ))

        elif endpoint_type == EndpointType.EFFICACY:
            # IBD/autoimmune disease-specific ICEs
            strategies.append(InterCurrentEvent(
                event="Use of rescue medication or prohibited therapy",
                strategy=ICEStrategy.COMPOSITE,
                rationale="Non-response captured through composite failure definition"
            ))
            strategies.append(InterCurrentEvent(
                event="Missing efficacy assessment",
                strategy=ICEStrategy.TREATMENT_POLICY,
                rationale="Missing data handled using Non-Responder Imputation (NRI)"
            ))

        return strategies

    def _extract_endpoint_variable(self, text: str, endpoint_type: EndpointType) -> str:
        """Extract specific endpoint variable description"""
        patterns = {
            EndpointType.OS: [
                r'overall\s+survival[^.]*defined\s+as\s+([^.]+)',
                r'time\s+from\s+randomization\s+to\s+death',
            ],
            EndpointType.PFS: [
                r'progression[- ]?free\s+survival[^.]*defined\s+as\s+([^.]+)',
                r'time\s+from\s+randomization\s+to\s+(?:disease\s+)?progression\s+or\s+death',
            ],
            EndpointType.ORR: [
                r'objective\s+response\s+rate[^.]*defined\s+as\s+([^.]+)',
                r'(?:complete|partial)\s+response\s+(?:per|by)\s+recist',
            ],
            EndpointType.SAFETY: [
                r'(?:incidence|frequency)\s+of\s+(?:treatment[- ]?emergent\s+)?adverse\s+events',
                r'dose[- ]?limiting\s+toxicit(?:y|ies)',
            ],
            EndpointType.PK: [
                r'pharmacokinetic\s+parameters?\s+(?:including\s+)?([^.]+)',
                r'(?:auc|cmax|tmax)[^.]*',
            ],
        }

        for pattern in patterns.get(endpoint_type, []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)[:200]

        return ""

    def _get_summary_measure(self, endpoint_type: EndpointType) -> str:
        """Get appropriate summary measure for endpoint type"""
        measures = {
            EndpointType.OS: "Hazard ratio with 95% CI",
            EndpointType.PFS: "Hazard ratio with 95% CI",
            EndpointType.DFS: "Hazard ratio with 95% CI",
            EndpointType.EFS: "Hazard ratio with 95% CI",
            EndpointType.ORR: "Difference in response rates with 95% CI",
            EndpointType.EFFICACY: "Difference in proportions with 95% CI",  # IBD remission, ACR20, etc.
            EndpointType.SAFETY: "Incidence rates and 95% CI",
            EndpointType.PK: "Geometric mean ratios with 90% CI",
            EndpointType.OTHER: "Difference or ratio with 95% CI",
        }
        return measures.get(endpoint_type, "Appropriate effect measure with CI")

    def _get_analysis_method(self, endpoint_type: EndpointType) -> str:
        """Get appropriate analysis method for endpoint type"""
        methods = {
            EndpointType.OS: "Kaplan-Meier estimation with stratified log-rank test; Cox proportional hazards model",
            EndpointType.PFS: "Kaplan-Meier estimation with stratified log-rank test; Cox proportional hazards model",
            EndpointType.DFS: "Kaplan-Meier estimation with stratified log-rank test; Cox proportional hazards model",
            EndpointType.EFS: "Kaplan-Meier estimation with stratified log-rank test",
            EndpointType.ORR: "Clopper-Pearson exact confidence interval; CMH test stratified by randomization factors",
            EndpointType.EFFICACY: "CMH test stratified by randomization factors; logistic regression with covariates",
            EndpointType.SAFETY: "Descriptive statistics; exposure-adjusted incidence rates",
            EndpointType.PK: "Non-compartmental analysis; mixed-effects model for log-transformed parameters",
            EndpointType.OTHER: "Appropriate parametric or non-parametric test",
        }
        return methods.get(endpoint_type, "To be determined based on data characteristics")

    def _infer_statistical_methods(
        self,
        endpoint_type: EndpointType,
        design_type: DesignType,
        phase: StudyPhase
    ) -> List[StatisticalMethod]:
        """Infer appropriate statistical methods based on study characteristics"""
        methods = []

        # Time-to-event endpoints
        if endpoint_type in [EndpointType.OS, EndpointType.PFS, EndpointType.DFS, EndpointType.EFS]:
            methods.append(StatisticalMethod(
                name="Kaplan-Meier Method",
                description="Non-parametric estimation of survival function",
                application="Primary analysis of time-to-event endpoints",
                assumptions=["Non-informative censoring", "Independent censoring"],
                implementation="PROC LIFETEST (SAS) / survfit (R)",
                references=["Kaplan EL, Meier P. JASA 1958"]
            ))
            methods.append(StatisticalMethod(
                name="Cox Proportional Hazards Model",
                description="Semi-parametric regression for time-to-event data",
                application="Estimation of hazard ratio with covariate adjustment",
                assumptions=["Proportional hazards", "Non-informative censoring"],
                implementation="PROC PHREG (SAS) / coxph (R)",
                sensitivity_analyses=["Stratified Cox model", "Time-varying covariates"]
            ))
            methods.append(StatisticalMethod(
                name="Log-Rank Test",
                description="Non-parametric test for comparing survival curves",
                application="Primary hypothesis test for time-to-event endpoints",
                assumptions=["Proportional hazards", "Non-informative censoring"],
                implementation="PROC LIFETEST (SAS) / survdiff (R)"
            ))

        # Binary endpoints (ORR)
        elif endpoint_type == EndpointType.ORR:
            methods.append(StatisticalMethod(
                name="Clopper-Pearson Exact Confidence Interval",
                description="Exact binomial confidence interval for proportions",
                application="Estimation of response rate with confidence bounds",
                assumptions=["Independent observations", "Binary outcome"],
                implementation="PROC FREQ (SAS) / binom.test (R)"
            ))
            methods.append(StatisticalMethod(
                name="Cochran-Mantel-Haenszel Test",
                description="Stratified analysis of categorical data",
                application="Comparison of response rates with stratification",
                assumptions=["Homogeneity of odds ratios across strata"],
                implementation="PROC FREQ (SAS) / mantelhaen.test (R)"
            ))

        # PK endpoints
        elif endpoint_type == EndpointType.PK:
            methods.append(StatisticalMethod(
                name="Non-Compartmental Analysis (NCA)",
                description="Model-independent PK parameter estimation",
                application="Primary PK parameter derivation",
                assumptions=["Adequate sampling", "Linear pharmacokinetics"],
                implementation="Phoenix WinNonlin / PKNCA (R)"
            ))
            methods.append(StatisticalMethod(
                name="Linear Mixed-Effects Model",
                description="Analysis of log-transformed PK parameters",
                application="Estimation of geometric mean ratios for bioequivalence",
                assumptions=["Log-normal distribution", "Fixed sequence effects"],
                implementation="PROC MIXED (SAS) / lme (R)"
            ))

        # Safety endpoints
        elif endpoint_type == EndpointType.SAFETY:
            methods.append(StatisticalMethod(
                name="Descriptive Statistics",
                description="Summary tables of adverse events",
                application="Primary safety analysis",
                assumptions=["Complete safety monitoring"],
                implementation="PROC FREQ, PROC MEANS (SAS)"
            ))
            methods.append(StatisticalMethod(
                name="Exposure-Adjusted Incidence Rate",
                description="AE incidence normalized by exposure time",
                application="Safety comparison accounting for differential exposure",
                assumptions=["Constant hazard within treatment groups"],
                implementation="Custom programming"
            ))

        # EFFICACY endpoints (IBD remission, ACR20, PASI, etc.)
        elif endpoint_type == EndpointType.EFFICACY:
            methods.append(StatisticalMethod(
                name="Cochran-Mantel-Haenszel Test",
                description="Stratified analysis of binary efficacy outcomes",
                application="Primary comparison of remission/response rates between treatment groups",
                assumptions=["Homogeneity of odds ratios across strata", "Independent observations"],
                implementation="PROC FREQ (SAS) / mantelhaen.test (R)"
            ))
            methods.append(StatisticalMethod(
                name="Logistic Regression",
                description="Binary outcome regression with covariate adjustment",
                application="Estimation of treatment effect with adjustment for baseline covariates",
                assumptions=["Binary outcome", "Independence of observations"],
                implementation="PROC LOGISTIC (SAS) / glm (R)",
                sensitivity_analyses=["Multiple imputation for missing data", "Tipping point analysis"]
            ))
            methods.append(StatisticalMethod(
                name="Non-Responder Imputation (NRI)",
                description="Missing responder data treated as non-responders",
                application="Conservative handling of missing efficacy data",
                assumptions=["Missing values indicate treatment failure"],
                implementation="Custom programming / SAS macros"
            ))

        return methods


# Factory function for easy instantiation
def create_parser(llm_client=None) -> ProtocolParser:
    """Create a protocol parser instance"""
    return ProtocolParser(llm_client=llm_client)
