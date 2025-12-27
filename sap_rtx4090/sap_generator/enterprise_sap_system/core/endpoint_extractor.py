#!/usr/bin/env python3
"""
Advanced Endpoint Extraction System
=====================================
Implements: Structured Section Parsing + LLM Chain-of-Thought + Phase Validation

Based on research showing this approach achieves 85-90% accuracy:
1. Parse document structure to find PRIMARY endpoint section (not secondary)
2. Use LLM with chain-of-thought to classify the extracted section
3. Validate against study phase (Phase 1 = SAFETY)
4. Ensemble: combine rule-based + LLM predictions
"""

import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


@dataclass
class ExtractionResult:
    """Result of endpoint extraction"""
    endpoint_type: str  # OS, PFS, ORR, SAFETY, PK, DFS, EFS, OTHER
    confidence: float
    source: str  # "rules", "llm", "ensemble"
    reasoning: str
    primary_section_text: str = ""
    phase: str = ""


class StructuredEndpointExtractor:
    """
    Advanced endpoint extractor using structured parsing + LLM + validation.
    """

    # ICH E6 standard section patterns for primary endpoint/objective
    PRIMARY_SECTION_PATTERNS = [
        # Numbered sections (e.g., "2.1 Primary Objective")
        r'(?:^|\n)\s*(?:\d+\.?\d*\.?\d*\s+)?primary\s+(?:efficacy\s+)?(?:endpoint|objective|outcome)s?\s*[:\n](.*?)(?=\n\s*(?:\d+\.?\d*\.?\d*\s+)?(?:secondary|exploratory|key\s+secondary)|$)',

        # Header style (e.g., "Primary Endpoint:")
        r'(?:^|\n)\s*primary\s+(?:efficacy\s+)?(?:endpoint|objective|outcome)s?\s*[:\-]\s*(.*?)(?=\n\s*(?:secondary|exploratory)|$)',

        # "The primary endpoint is..."
        r'(?:the\s+)?primary\s+(?:efficacy\s+)?(?:endpoint|objective|outcome)\s+(?:is|will\s+be|of\s+this\s+study\s+is)\s+([^.]+\.)',

        # Synopsis format
        r'primary\s+(?:endpoint|objective)[:\s]+([^\n]+(?:\n(?!\s*secondary)[^\n]+)*)',
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

    # Endpoint keywords for rule-based detection (only applied to PRIMARY section)
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
        "SAFETY": [
            "dose-limiting toxicity", "dose limiting toxicity", "dlt",
            "maximum tolerated dose", "mtd", "safety and tolerability",
            "recommended phase 2 dose", "rp2d", "tolerability",
            "adverse events", "safety profile"
        ],
        "PK": [
            "pharmacokinetic", "pharmacokinetics", "pk parameters",
            "auc", "cmax", "bioavailability", "drug-drug interaction"
        ],
    }

    # LLM Chain-of-Thought prompt
    COT_PROMPT = """You are an expert biostatistician. Analyze this clinical trial PRIMARY ENDPOINT section and classify it.

PRIMARY ENDPOINT SECTION (extracted from protocol):
{primary_section}

STUDY PHASE: {phase}

STEP-BY-STEP ANALYSIS:

Step 1: What specific outcome measure is described as the PRIMARY endpoint?
Step 2: Is this a time-to-event endpoint (survival), a response rate, safety/tolerability, or pharmacokinetics?
Step 3: For Phase 1 studies - is the primary focus on MTD/DLT/safety (even if efficacy is mentioned)?
Step 4: Based on the above, classify into exactly ONE category:

CLASSIFICATION RULES:
- SAFETY: MTD, DLT, RP2D, tolerability, safety profile, dose-finding (common in Phase 1)
- OS: Overall survival, time to death
- PFS: Progression-free survival, time to disease progression
- ORR: Objective response rate, tumor response, RECIST-based response
- DFS: Disease-free survival, recurrence-free (adjuvant setting)
- EFS: Event-free survival (composite events)
- PK: Pharmacokinetic parameters (AUC, Cmax, bioavailability)
- OTHER: Only if none of the above clearly apply

Respond in JSON format:
{{"step1": "...", "step2": "...", "step3": "...", "endpoint_type": "OS|PFS|ORR|SAFETY|DFS|EFS|PK|OTHER", "confidence": 0.0-1.0, "reasoning": "..."}}"""

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
        Extract primary endpoint type using structured parsing + LLM + validation.

        Args:
            protocol_text: Full protocol document text

        Returns:
            ExtractionResult with endpoint type, confidence, and reasoning
        """
        # Step 1: Detect study phase
        phase = self._detect_phase(protocol_text)

        # Step 2: Extract PRIMARY endpoint section (structured parsing)
        primary_section = self._extract_primary_section(protocol_text)

        # Step 3: Rule-based classification on PRIMARY section only
        rule_result = self._rule_based_classify(primary_section, phase)

        # Step 4: LLM chain-of-thought classification
        llm_result = self._llm_classify(primary_section, phase)

        # Step 5: Ensemble combination with phase validation
        final_result = self._ensemble_combine(rule_result, llm_result, phase, primary_section)

        return final_result

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
        This is the key differentiator - we don't search the whole document.
        """
        # Try each pattern
        for pattern in self.PRIMARY_SECTION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                section = match.group(1).strip()
                # Clean up and limit length
                section = re.sub(r'\s+', ' ', section)
                return section[:1500]  # Limit to relevant content

        # Fallback: Look for synopsis and extract primary from there
        synopsis_match = re.search(
            r'synopsis[:\s]*(.*?)(?=\n\s*\d+\.\s+[A-Z]|\Z)',
            text, re.IGNORECASE | re.DOTALL
        )
        if synopsis_match:
            synopsis = synopsis_match.group(1)
            # Try to find primary within synopsis
            for pattern in self.PRIMARY_SECTION_PATTERNS[:2]:
                match = re.search(pattern, synopsis, re.IGNORECASE | re.DOTALL)
                if match:
                    return match.group(1).strip()[:1500]
            return synopsis[:1000]

        # Last resort: first 1000 chars
        return text[:1000]

    def _rule_based_classify(self, primary_section: str, phase: str) -> ExtractionResult:
        """
        Rule-based classification on the PRIMARY section only.
        """
        section_lower = primary_section.lower()
        scores = {ep: 0 for ep in self.ENDPOINT_KEYWORDS}

        for endpoint, keywords in self.ENDPOINT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in section_lower:
                    # Higher weight for exact matches
                    scores[endpoint] += 10

        # Phase-based boost
        if phase.startswith("1") and phase != "1/2":
            scores["SAFETY"] += 15
            scores["PK"] += 5

        # Find best match
        max_score = max(scores.values())
        if max_score == 0:
            return ExtractionResult(
                endpoint_type="OTHER",
                confidence=0.3,
                source="rules",
                reasoning="No endpoint keywords found in primary section",
                primary_section_text=primary_section,
                phase=phase
            )

        best_endpoint = max(scores, key=scores.get)
        confidence = min(max_score / 30, 0.9)

        return ExtractionResult(
            endpoint_type=best_endpoint,
            confidence=confidence,
            source="rules",
            reasoning=f"Keyword match in primary section (score: {max_score})",
            primary_section_text=primary_section,
            phase=phase
        )

    def _llm_classify(self, primary_section: str, phase: str) -> Optional[ExtractionResult]:
        """
        LLM classification with chain-of-thought reasoning.
        """
        if self.llm_client is None:
            return None

        try:
            prompt = self.COT_PROMPT.format(
                primary_section=primary_section,
                phase=phase if phase != "unknown" else "Not specified"
            )

            response = self.llm_client.chat(
                prompt=prompt,
                temperature=0.1,
                max_tokens=500,
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
                    phase=phase
                )
        except Exception as e:
            pass

        return None

    def _ensemble_combine(
        self,
        rule_result: ExtractionResult,
        llm_result: Optional[ExtractionResult],
        phase: str,
        primary_section: str
    ) -> ExtractionResult:
        """
        Combine rule-based and LLM results with phase validation.
        """
        # If no LLM result, use rules with phase validation
        if llm_result is None:
            return self._apply_phase_validation(rule_result, phase)

        # If both agree, high confidence
        if rule_result.endpoint_type == llm_result.endpoint_type:
            return ExtractionResult(
                endpoint_type=rule_result.endpoint_type,
                confidence=min(0.95, max(rule_result.confidence, llm_result.confidence) + 0.1),
                source="ensemble",
                reasoning=f"Rules and LLM agree: {rule_result.endpoint_type}",
                primary_section_text=primary_section,
                phase=phase
            )

        # Phase validation: Phase 1 should have SAFETY unless strong evidence otherwise
        if phase.startswith("1") and phase != "1/2":
            if llm_result.endpoint_type == "SAFETY" or rule_result.endpoint_type == "SAFETY":
                return ExtractionResult(
                    endpoint_type="SAFETY",
                    confidence=0.85,
                    source="ensemble",
                    reasoning=f"Phase 1 study - SAFETY is typical primary endpoint",
                    primary_section_text=primary_section,
                    phase=phase
                )

        # Trust LLM over rules when they disagree (LLM has context understanding)
        if llm_result.confidence > 0.6:
            return ExtractionResult(
                endpoint_type=llm_result.endpoint_type,
                confidence=llm_result.confidence * 0.9,  # Slight penalty for disagreement
                source="ensemble",
                reasoning=f"LLM ({llm_result.endpoint_type}) preferred over rules ({rule_result.endpoint_type}): {llm_result.reasoning}",
                primary_section_text=primary_section,
                phase=phase
            )

        # Fall back to rules if LLM is low confidence
        return self._apply_phase_validation(rule_result, phase)

    def _apply_phase_validation(self, result: ExtractionResult, phase: str) -> ExtractionResult:
        """Apply phase-based validation to a result - but don't override strong evidence"""
        # Phase 1 validation - but respect explicit endpoint mentions
        if phase.startswith("1") and phase != "1/2":
            if result.endpoint_type not in ["SAFETY", "PK"]:
                # Check if primary section EXPLICITLY mentions the endpoint
                section_lower = result.primary_section_text.lower()

                # Don't override if there's explicit evidence for the predicted endpoint
                explicit_evidence = {
                    "PFS": ["progression-free survival", "pfs", "time to progression"],
                    "OS": ["overall survival", "time to death"],
                    "ORR": ["response rate", "orr", "objective response"],
                    "DFS": ["disease-free survival", "dfs"],
                }

                has_explicit = False
                if result.endpoint_type in explicit_evidence:
                    for keyword in explicit_evidence[result.endpoint_type]:
                        if keyword in section_lower:
                            has_explicit = True
                            break

                # Only override if no explicit evidence AND low confidence
                if not has_explicit and result.confidence < 0.7:
                    return ExtractionResult(
                        endpoint_type="SAFETY",
                        confidence=0.7,
                        source=result.source,
                        reasoning=f"Phase 1 study - adjusted from {result.endpoint_type} to SAFETY",
                        primary_section_text=result.primary_section_text,
                        phase=phase
                    )

        return result


def create_endpoint_extractor(llm_client=None) -> StructuredEndpointExtractor:
    """Factory function to create an endpoint extractor"""
    return StructuredEndpointExtractor(llm_client=llm_client)
