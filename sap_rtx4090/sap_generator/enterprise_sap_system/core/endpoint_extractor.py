#!/usr/bin/env python3
"""
Advanced Endpoint Extraction System v2.0
=========================================
Two-Stage Architecture: Therapeutic Area Detection → Endpoint Classification

Based on research showing 93-96% accuracy with:
1. Stage 1: Detect therapeutic area (IBD, Oncology, Rheumatology, etc.)
2. Stage 2: Parse PRIMARY endpoint section with TA-specific keywords
3. Apply Bayesian priors based on Phase + Therapeutic Area
4. LLM chain-of-thought with therapeutic context
5. Ensemble with phase + TA validation
"""

import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    """Result of endpoint extraction"""
    endpoint_type: str  # OS, PFS, ORR, SAFETY, PK, DFS, EFS, EFFICACY, OTHER
    confidence: float
    source: str  # "rules", "llm", "ensemble"
    reasoning: str
    primary_section_text: str = ""
    phase: str = ""
    therapeutic_area: str = ""


class StructuredEndpointExtractor:
    """
    Advanced endpoint extractor with therapeutic area awareness.
    """

    # ====================
    # THERAPEUTIC AREA DETECTION (Stage 1)
    # ====================
    THERAPEUTIC_AREA_KEYWORDS = {
        "IBD": [
            "ulcerative colitis", "crohn's disease", "crohn disease", "inflammatory bowel",
            "ibd", "uc patients", "cd patients", "mayo score", "cdai", "endoscopic",
            "mucosal healing", "colonoscopy", "rectal bleeding", "stool frequency",
            "fecal calprotectin", "bowel", "colitis", "ileitis"
        ],
        "ONCOLOGY": [
            "tumor", "cancer", "carcinoma", "melanoma", "lymphoma", "leukemia",
            "solid tumor", "metastatic", "recist", "progression-free", "overall survival",
            "nsclc", "breast cancer", "colorectal cancer", "pancreatic", "hepatocellular",
            "chemotherapy", "immunotherapy", "checkpoint inhibitor", "pd-1", "pd-l1"
        ],
        "RHEUMATOLOGY": [
            "rheumatoid arthritis", "psoriatic arthritis", "ankylosing spondylitis",
            "acr20", "acr50", "acr70", "das28", "joint", "synovitis", "ra patients",
            "dmard", "biologic", "tnf", "jak inhibitor", "autoimmune arthritis"
        ],
        "DERMATOLOGY": [
            "psoriasis", "atopic dermatitis", "eczema", "pasi", "easi", "iga",
            "pruritus", "lesion", "skin", "plaque psoriasis", "moderate-to-severe psoriasis",
            "itch", "dermatitis"
        ],
        "NEUROLOGY": [
            "multiple sclerosis", "alzheimer", "parkinson", "epilepsy", "migraine",
            "neuropathy", "cns", "brain", "cognitive", "edss", "mri lesion"
        ],
        "CARDIOLOGY": [
            "heart failure", "cardiovascular", "atrial fibrillation", "myocardial",
            "ejection fraction", "lvef", "ace inhibitor", "arrhythmia", "coronary"
        ],
    }

    # Bayesian priors: P(endpoint_type | phase, therapeutic_area)
    # These guide classification when signals are weak
    TA_PHASE_PRIORS = {
        "IBD": {
            "1": {"SAFETY": 0.65, "PK": 0.25, "EFFICACY": 0.10},
            "1b": {"SAFETY": 0.50, "EFFICACY": 0.35, "PK": 0.15},
            "2": {"EFFICACY": 0.85, "SAFETY": 0.10, "PK": 0.05},
            "2a": {"EFFICACY": 0.80, "SAFETY": 0.15, "PK": 0.05},
            "2b": {"EFFICACY": 0.90, "SAFETY": 0.08, "PK": 0.02},
            "3": {"EFFICACY": 0.95, "SAFETY": 0.05, "PK": 0.00},
        },
        "ONCOLOGY": {
            "1": {"SAFETY": 0.75, "PK": 0.15, "ORR": 0.10},
            "1b": {"SAFETY": 0.60, "ORR": 0.30, "PK": 0.10},
            "2": {"ORR": 0.55, "PFS": 0.30, "SAFETY": 0.15},
            "3": {"PFS": 0.40, "OS": 0.35, "ORR": 0.25},
        },
        "RHEUMATOLOGY": {
            "1": {"SAFETY": 0.70, "PK": 0.20, "EFFICACY": 0.10},
            "2": {"EFFICACY": 0.80, "SAFETY": 0.15, "PK": 0.05},
            "3": {"EFFICACY": 0.90, "SAFETY": 0.10, "PK": 0.00},
        },
        "DERMATOLOGY": {
            "1": {"SAFETY": 0.70, "PK": 0.20, "EFFICACY": 0.10},
            "2": {"EFFICACY": 0.85, "SAFETY": 0.10, "PK": 0.05},
            "3": {"EFFICACY": 0.95, "SAFETY": 0.05, "PK": 0.00},
        },
        "GENERAL": {
            "1": {"SAFETY": 0.60, "PK": 0.25, "EFFICACY": 0.15},
            "2": {"EFFICACY": 0.60, "SAFETY": 0.25, "PK": 0.15},
            "3": {"EFFICACY": 0.70, "SAFETY": 0.20, "PK": 0.10},
        },
    }

    # ====================
    # PRIMARY SECTION EXTRACTION PATTERNS
    # ====================
    # Enhanced patterns with stricter boundary detection to exclude secondary objectives
    PRIMARY_SECTION_PATTERNS = [
        # Strict: Stop before secondary/exploratory/pharmacokinetic sections
        r'(?:^|\n)\s*(?:\d+\.?\d*\.?\d*\s+)?primary\s+(?:efficacy\s+)?(?:endpoint|objective|outcome)s?\s*[:\n](.*?)(?=\n\s*(?:\d+\.?\d*\.?\d*\s+)?(?:secondary|exploratory|pharmacokinetic|safety\s+(?:endpoint|objective)|key\s+secondary)|$)',

        # Header style with strict boundary
        r'(?:^|\n)\s*primary\s+(?:efficacy\s+)?(?:endpoint|objective|outcome)s?\s*[:\-]\s*(.*?)(?=\n\s*(?:secondary|exploratory|pharmacokinetic)|$)',

        # "The primary endpoint is..." - single sentence
        r'(?:the\s+)?primary\s+(?:efficacy\s+)?(?:endpoint|objective|outcome)\s+(?:is|will\s+be|of\s+this\s+study\s+is)\s+([^.]+\.)',

        # Synopsis format with boundary
        r'primary\s+(?:endpoint|objective)[:\s]+([^\n]+(?:\n(?!\s*(?:secondary|pharmacokinetic|safety\s+endpoint))[^\n]+)*)',
    ]

    # Phase detection patterns
    PHASE_PATTERNS = {
        "1": r'\bphase\s*[1iI]\b(?!\s*[/\\]\s*[23])',
        "1a": r'\bphase\s*[1iI][aA]\b',
        "1b": r'\bphase\s*[1iI][bB]\b',
        "1/2": r'\bphase\s*[1iI]\s*[/\\]\s*[2iI]{1,2}\b',
        "2": r'\bphase\s*[2iI]{1,2}\b(?!\s*[/\\]\s*[13])',
        "2a": r'\bphase\s*[2iI]{1,2}[aA]\b',
        "2b": r'\bphase\s*[2iI]{1,2}[bB]\b',
        "2/3": r'\bphase\s*[2iI]{1,2}\s*[/\\]\s*[3iI]{1,3}\b',
        "3": r'\bphase\s*[3iI]{1,3}\b(?!\s*[/\\])',
        "4": r'\bphase\s*[4iIvV]{1,2}\b',
    }

    # ====================
    # ENDPOINT KEYWORDS (Expanded with TA-specific terms)
    # ====================
    ENDPOINT_KEYWORDS = {
        "OS": [
            "overall survival", "time to death", "death from any cause",
            "survival time", "os endpoint", "median survival"
        ],
        "PFS": [
            "progression-free survival", "progression free survival",
            "time to progression", "pfs endpoint", "disease progression"
        ],
        "ORR": [
            "objective response rate", "overall response rate",
            "tumor response", "response rate", "orr endpoint",
            "complete response", "partial response", "recist"
        ],
        "DFS": [
            "disease-free survival", "disease free survival",
            "recurrence-free survival", "relapse-free survival"
        ],
        "EFS": [
            "event-free survival", "event free survival"
        ],
        # EFFICACY - comprehensive coverage for IBD, autoimmune, inflammatory diseases
        "EFFICACY": [
            # IBD-specific remission endpoints (FDA UC Guidance)
            "clinical remission", "endoscopic remission", "histologic remission",
            "clinical and endoscopic remission", "remission at week",
            "remission rate", "sustained remission", "corticosteroid-free remission",
            "steroid-free remission", "mucosal healing", "histological healing",

            # IBD-specific response endpoints
            "clinical response", "endoscopic response", "histologic response",
            "endoscopic improvement", "clinical improvement",

            # IBD disease activity scores
            "mayo score", "mayo clinic score", "partial mayo score", "modified mayo",
            "mmayo", "mms", "total mayo score",
            "cdai", "crohn's disease activity index", "harvey-bradshaw", "hbi",
            "simple endoscopic score", "ses-cd", "sescd",
            "ulcerative colitis endoscopic index", "uceis",

            # IBD symptom subscores
            "stool frequency subscore", "rectal bleeding subscore",
            "endoscopy subscore", "physician global assessment",
            "fecal calprotectin", "bowel urgency", "abdominal pain",

            # Rheumatology endpoints
            "acr20", "acr50", "acr70", "acr response",
            "das28", "das28-crp", "das28-esr", "disease activity score",
            "sdai", "cdai remission", "boolean remission",
            "tender joint count", "swollen joint count",

            # Dermatology endpoints
            "pasi 75", "pasi 90", "pasi 100", "pasi response",
            "easi-75", "easi-90", "easi score",
            "iga 0/1", "iga response", "iga success",
            "clear or almost clear", "bsa reduction",

            # General efficacy terms
            "proportion of patients", "proportion of subjects",
            "percentage of patients", "percentage of subjects",
            "change from baseline", "reduction from baseline",
            "improvement from baseline", "decrease from baseline",
            "symptom improvement", "treatment response",
        ],
        "SAFETY": [
            "dose-limiting toxicity", "dose limiting toxicity", "dlt",
            "maximum tolerated dose", "mtd", "safety and tolerability",
            "recommended phase 2 dose", "rp2d", "tolerability",
            "adverse events", "safety profile", "incidence of adverse events",
            "treatment-emergent adverse events", "teae"
        ],
        "PK": [
            "pharmacokinetic", "pharmacokinetics", "pk parameters",
            "pk profile", "pk endpoint", "exposure",
            "auc", "cmax", "tmax", "half-life", "t1/2",
            "bioavailability", "drug-drug interaction",
            "clearance", "volume of distribution"
        ],
    }

    # ====================
    # LLM PROMPT with Therapeutic Area Context
    # ====================
    COT_PROMPT = """You are an expert biostatistician. Analyze this clinical trial PRIMARY ENDPOINT section and classify it.

PRIMARY ENDPOINT SECTION (extracted from protocol):
{primary_section}

STUDY CONTEXT:
- Phase: {phase}
- Therapeutic Area: {therapeutic_area}
- Indication: {indication}

{ta_guidance}

STEP-BY-STEP ANALYSIS:

Step 1: What specific outcome measure is described as the PRIMARY endpoint?
Step 2: What type of endpoint is this? (survival, response/remission, clinical efficacy score, safety, PK)
Step 3: Is this consistent with typical Phase {phase} {therapeutic_area} trials?
Step 4: CRITICAL - For Phase 2/3 non-oncology trials, if BOTH efficacy and PK are mentioned, the PRIMARY is almost always EFFICACY. PK is usually secondary.

CLASSIFICATION RULES (in order of priority):
- EFFICACY: Clinical remission, endoscopic remission, clinical response, disease activity scores (Mayo, CDAI, ACR20, PASI), mucosal healing - TYPICAL FOR PHASE 2/3 IBD, AUTOIMMUNE, INFLAMMATORY
- ORR: Objective response rate, tumor response, RECIST - TYPICAL FOR ONCOLOGY
- PFS: Progression-free survival - TYPICAL FOR ONCOLOGY PHASE 2/3
- OS: Overall survival - TYPICAL FOR ONCOLOGY PHASE 3
- DFS: Disease-free survival, recurrence-free - ADJUVANT ONCOLOGY
- EFS: Event-free survival
- SAFETY: MTD, DLT, RP2D, tolerability, dose-finding - TYPICAL FOR PHASE 1 ALL AREAS
- PK: Pharmacokinetics (AUC, Cmax) - ONLY for Phase 1 PK-specific studies, RARELY primary for Phase 2/3
- OTHER: Only if none of the above apply

Respond in JSON format:
{{"step1": "...", "step2": "...", "step3": "...", "step4": "...", "endpoint_type": "EFFICACY|ORR|PFS|OS|DFS|EFS|SAFETY|PK|OTHER", "confidence": 0.0-1.0, "reasoning": "..."}}"""

    # Therapeutic area-specific guidance for LLM
    TA_GUIDANCE = {
        "IBD": """THERAPEUTIC AREA GUIDANCE (IBD - Inflammatory Bowel Disease):
- Phase 2/3 UC trials: Primary endpoint is almost ALWAYS "clinical remission" or "clinical and endoscopic remission" at Week 8-12
- Mayo score components: stool frequency, rectal bleeding, endoscopy, physician global assessment
- PK is typically SECONDARY in Phase 2 IBD trials, not primary
- If you see "evaluate efficacy and safety" or "safety and efficacy", focus on the EFFICACY endpoint for classification""",

        "ONCOLOGY": """THERAPEUTIC AREA GUIDANCE (Oncology):
- Phase 1: Primarily SAFETY (MTD, DLT, RP2D)
- Phase 2: Primarily ORR (RECIST-based response rate)
- Phase 3: PFS or OS as primary, ORR as secondary""",

        "RHEUMATOLOGY": """THERAPEUTIC AREA GUIDANCE (Rheumatology):
- Phase 2/3 RA trials: ACR20/50/70 response or DAS28 remission
- Joint counts (tender/swollen) are key measures
- PK is typically secondary""",

        "DERMATOLOGY": """THERAPEUTIC AREA GUIDANCE (Dermatology):
- Psoriasis: PASI 75/90/100 or IGA 0/1 response
- Atopic dermatitis: EASI-75 or IGA response
- PK is typically secondary""",

        "GENERAL": """THERAPEUTIC AREA GUIDANCE:
- Phase 1: Typically SAFETY or PK
- Phase 2/3: Typically EFFICACY measure specific to the indication
- When both efficacy and PK are mentioned, efficacy is usually primary for Phase 2/3"""
    }

    def __init__(self, llm_client=None):
        """Initialize extractor with optional LLM client"""
        self.llm_client = llm_client
        self._init_llm()

    def _init_llm(self):
        """Initialize LLM client if not provided"""
        if self.llm_client is None:
            try:
                from .tiered_llm import get_tiered_client
                self.llm_client = get_tiered_client()
            except Exception:
                pass

    def extract(self, protocol_text: str) -> ExtractionResult:
        """
        Extract primary endpoint type using two-stage classification.

        Stage 1: Detect therapeutic area
        Stage 2: Classify endpoint with TA context

        Args:
            protocol_text: Full protocol document text

        Returns:
            ExtractionResult with endpoint type, confidence, and reasoning
        """
        # Stage 1: Detect therapeutic area
        therapeutic_area, ta_confidence = self._detect_therapeutic_area(protocol_text)

        # Detect study phase
        phase = self._detect_phase(protocol_text)

        # Extract indication for LLM context
        indication = self._extract_indication(protocol_text)

        # Stage 2: Extract PRIMARY endpoint section (structured parsing)
        primary_section = self._extract_primary_section(protocol_text)

        # Rule-based classification with TA awareness
        rule_result = self._rule_based_classify(primary_section, phase, therapeutic_area)

        # LLM chain-of-thought classification with TA context
        llm_result = self._llm_classify(primary_section, phase, therapeutic_area, indication)

        # Ensemble combination with phase + TA validation
        final_result = self._ensemble_combine(
            rule_result, llm_result, phase, therapeutic_area, primary_section
        )

        return final_result

    def _detect_therapeutic_area(self, text: str) -> Tuple[str, float]:
        """
        Stage 1: Detect therapeutic area from protocol text.
        Returns (therapeutic_area, confidence)
        """
        text_lower = text.lower()
        ta_scores = {}

        for ta, keywords in self.THERAPEUTIC_AREA_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    # Weight by keyword specificity (longer = more specific)
                    score += 1 + len(keyword.split()) * 0.5
            ta_scores[ta] = score

        # Find best match
        if not ta_scores or max(ta_scores.values()) < 2:
            return "GENERAL", 0.3

        best_ta = max(ta_scores, key=ta_scores.get)
        max_score = ta_scores[best_ta]
        confidence = min(max_score / 10, 0.95)

        return best_ta, confidence

    def _extract_indication(self, text: str) -> str:
        """Extract the disease indication from protocol text"""
        text_lower = text.lower()

        # Common indication patterns
        patterns = [
            r'patients? with\s+([^.]{10,60})',
            r'subjects? with\s+([^.]{10,60})',
            r'treatment of\s+([^.]{10,60})',
            r'indication[:\s]+([^.\n]{10,60})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1).strip()

        return "Not specified"

    def _detect_phase(self, text: str) -> str:
        """Detect study phase from protocol text"""
        text_lower = text.lower()

        # Check patterns in order of specificity
        for phase, pattern in self.PHASE_PATTERNS.items():
            if re.search(pattern, text_lower):
                return phase

        return "unknown"

    def _extract_primary_section(self, text: str) -> str:
        """
        Extract ONLY the primary endpoint/objective section.
        Uses strict boundary detection to exclude secondary/PK objectives.
        """
        # Try each pattern
        for pattern in self.PRIMARY_SECTION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                section = match.group(1).strip()
                # Clean up and limit length
                section = re.sub(r'\s+', ' ', section)

                # Additional safety: truncate if we hit secondary/PK keywords
                for boundary in ["secondary endpoint", "secondary objective",
                                "pharmacokinetic objective", "safety objective",
                                "exploratory endpoint"]:
                    if boundary in section.lower():
                        idx = section.lower().find(boundary)
                        section = section[:idx].strip()

                return section[:1500]

        # Fallback: Look for synopsis and extract primary from there
        synopsis_match = re.search(
            r'synopsis[:\s]*(.*?)(?=\n\s*\d+\.\s+[A-Z]|\Z)',
            text, re.IGNORECASE | re.DOTALL
        )
        if synopsis_match:
            synopsis = synopsis_match.group(1)
            for pattern in self.PRIMARY_SECTION_PATTERNS[:2]:
                match = re.search(pattern, synopsis, re.IGNORECASE | re.DOTALL)
                if match:
                    return match.group(1).strip()[:1500]
            return synopsis[:1000]

        # Last resort: first 1000 chars
        return text[:1000]

    def _rule_based_classify(
        self, primary_section: str, phase: str, therapeutic_area: str
    ) -> ExtractionResult:
        """
        Rule-based classification with therapeutic area awareness.
        """
        section_lower = primary_section.lower()
        scores = {ep: 0.0 for ep in self.ENDPOINT_KEYWORDS}

        # Score each endpoint type based on keyword matches
        for endpoint, keywords in self.ENDPOINT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in section_lower:
                    # Higher weight for longer (more specific) matches
                    weight = 10 + len(keyword.split()) * 2
                    scores[endpoint] += weight

        # Apply Bayesian priors based on Phase + Therapeutic Area
        base_phase = phase.replace("a", "").replace("b", "")  # "2a" -> "2"
        if base_phase in ["1/2"]:
            base_phase = "2"  # Treat 1/2 as Phase 2 for priors

        priors = self.TA_PHASE_PRIORS.get(
            therapeutic_area, self.TA_PHASE_PRIORS["GENERAL"]
        ).get(base_phase, self.TA_PHASE_PRIORS["GENERAL"].get("2", {}))

        # Apply priors as multipliers
        for endpoint, prior in priors.items():
            if endpoint in scores:
                scores[endpoint] += prior * 20  # Prior contributes up to 20 points

        # CRITICAL: Penalize PK for Phase 2/3 non-oncology unless explicitly primary
        if base_phase in ["2", "3"] and therapeutic_area != "ONCOLOGY":
            # Check if PK is explicitly stated as PRIMARY
            pk_primary_patterns = [
                r"primary\s+(?:endpoint|objective).*pharmacokinetic",
                r"pharmacokinetic.*primary\s+(?:endpoint|objective)",
                r"pk\s+(?:is|as)\s+(?:the\s+)?primary",
            ]
            is_explicit_pk = any(
                re.search(p, section_lower) for p in pk_primary_patterns
            )

            if not is_explicit_pk:
                scores["PK"] *= 0.1  # Heavy penalty

        # Find best match
        max_score = max(scores.values())
        if max_score == 0:
            # Use prior as fallback
            best_prior = max(priors.items(), key=lambda x: x[1]) if priors else ("OTHER", 0.3)
            return ExtractionResult(
                endpoint_type=best_prior[0],
                confidence=best_prior[1],
                source="rules",
                reasoning=f"No keywords matched, using {therapeutic_area} Phase {phase} prior",
                primary_section_text=primary_section,
                phase=phase,
                therapeutic_area=therapeutic_area
            )

        best_endpoint = max(scores, key=scores.get)
        confidence = min(max_score / 50, 0.9)

        return ExtractionResult(
            endpoint_type=best_endpoint,
            confidence=confidence,
            source="rules",
            reasoning=f"Keyword match in primary section (score: {max_score:.1f}, TA: {therapeutic_area})",
            primary_section_text=primary_section,
            phase=phase,
            therapeutic_area=therapeutic_area
        )

    def _llm_classify(
        self, primary_section: str, phase: str, therapeutic_area: str, indication: str
    ) -> Optional[ExtractionResult]:
        """
        LLM classification with therapeutic area context.
        """
        if self.llm_client is None:
            return None

        try:
            ta_guidance = self.TA_GUIDANCE.get(therapeutic_area, self.TA_GUIDANCE["GENERAL"])

            prompt = self.COT_PROMPT.format(
                primary_section=primary_section,
                phase=phase if phase != "unknown" else "Not specified",
                therapeutic_area=therapeutic_area,
                indication=indication,
                ta_guidance=ta_guidance
            )

            response = self.llm_client.chat(
                prompt=prompt,
                temperature=0.1,
                max_tokens=600,
                json_mode=True
            )

            if response.success:
                result = json.loads(response.content)
                return ExtractionResult(
                    endpoint_type=result.get("endpoint_type", "OTHER"),
                    confidence=float(result.get("confidence", 0.7)),
                    source="llm",
                    reasoning=result.get("reasoning", "LLM classification"),
                    primary_section_text=primary_section,
                    phase=phase,
                    therapeutic_area=therapeutic_area
                )
        except Exception as e:
            pass

        return None

    def _ensemble_combine(
        self,
        rule_result: ExtractionResult,
        llm_result: Optional[ExtractionResult],
        phase: str,
        therapeutic_area: str,
        primary_section: str
    ) -> ExtractionResult:
        """
        Combine rule-based and LLM results with phase + TA validation.
        """
        # If no LLM result, use rules with validation
        if llm_result is None:
            return self._apply_validation(rule_result, phase, therapeutic_area)

        # If both agree, high confidence
        if rule_result.endpoint_type == llm_result.endpoint_type:
            return ExtractionResult(
                endpoint_type=rule_result.endpoint_type,
                confidence=min(0.95, max(rule_result.confidence, llm_result.confidence) + 0.1),
                source="ensemble",
                reasoning=f"Rules and LLM agree: {rule_result.endpoint_type}",
                primary_section_text=primary_section,
                phase=phase,
                therapeutic_area=therapeutic_area
            )

        # Phase 1 validation: SAFETY is typical
        if phase.startswith("1") and phase != "1/2":
            if llm_result.endpoint_type == "SAFETY" or rule_result.endpoint_type == "SAFETY":
                return ExtractionResult(
                    endpoint_type="SAFETY",
                    confidence=0.85,
                    source="ensemble",
                    reasoning=f"Phase 1 {therapeutic_area} study - SAFETY is typical primary",
                    primary_section_text=primary_section,
                    phase=phase,
                    therapeutic_area=therapeutic_area
                )

        # Phase 2/3 non-oncology: EFFICACY is typical, PK should not win
        base_phase = phase.replace("a", "").replace("b", "")
        if base_phase in ["2", "3", "1/2", "2/3"] and therapeutic_area != "ONCOLOGY":
            # If one says EFFICACY and other says PK, choose EFFICACY
            if rule_result.endpoint_type == "EFFICACY" or llm_result.endpoint_type == "EFFICACY":
                other = llm_result if rule_result.endpoint_type == "EFFICACY" else rule_result
                if other.endpoint_type == "PK":
                    return ExtractionResult(
                        endpoint_type="EFFICACY",
                        confidence=0.85,
                        source="ensemble",
                        reasoning=f"Phase {phase} {therapeutic_area} study - EFFICACY preferred over PK",
                        primary_section_text=primary_section,
                        phase=phase,
                        therapeutic_area=therapeutic_area
                    )

        # Trust LLM over rules when they disagree (LLM has context understanding)
        if llm_result.confidence > 0.6:
            return ExtractionResult(
                endpoint_type=llm_result.endpoint_type,
                confidence=llm_result.confidence * 0.9,
                source="ensemble",
                reasoning=f"LLM ({llm_result.endpoint_type}) preferred: {llm_result.reasoning}",
                primary_section_text=primary_section,
                phase=phase,
                therapeutic_area=therapeutic_area
            )

        # Fall back to rules
        return self._apply_validation(rule_result, phase, therapeutic_area)

    def _apply_validation(
        self, result: ExtractionResult, phase: str, therapeutic_area: str
    ) -> ExtractionResult:
        """Apply phase + therapeutic area validation"""
        # Phase 1 non-PK-explicit studies should have SAFETY
        if phase.startswith("1") and phase != "1/2":
            if result.endpoint_type not in ["SAFETY", "PK"]:
                if result.confidence < 0.7:
                    return ExtractionResult(
                        endpoint_type="SAFETY",
                        confidence=0.7,
                        source=result.source,
                        reasoning=f"Phase 1 study - adjusted from {result.endpoint_type} to SAFETY",
                        primary_section_text=result.primary_section_text,
                        phase=phase,
                        therapeutic_area=therapeutic_area
                    )

        # Phase 2/3 IBD should have EFFICACY, not PK
        base_phase = phase.replace("a", "").replace("b", "")
        if base_phase in ["2", "3"] and therapeutic_area == "IBD":
            if result.endpoint_type == "PK" and result.confidence < 0.8:
                return ExtractionResult(
                    endpoint_type="EFFICACY",
                    confidence=0.75,
                    source=result.source,
                    reasoning=f"Phase {phase} IBD study - adjusted from PK to EFFICACY",
                    primary_section_text=result.primary_section_text,
                    phase=phase,
                    therapeutic_area=therapeutic_area
                )

        return result


def create_endpoint_extractor(llm_client=None) -> StructuredEndpointExtractor:
    """Factory function to create an endpoint extractor"""
    return StructuredEndpointExtractor(llm_client=llm_client)
