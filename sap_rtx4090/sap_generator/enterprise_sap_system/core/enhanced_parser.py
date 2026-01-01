#!/usr/bin/env python3
"""
Enhanced Protocol Parser with LLM Fallback
============================================
Improves accuracy by using LLM when pattern-based confidence is low.

Production Features:
- Structured logging for all operations
- Specific exception handling (no silent failures)
- Graceful degradation with fallback to pattern matching
"""

import os
import re
import json
from typing import Dict, Tuple, Optional, Any
from pathlib import Path

from .protocol_parser import ProtocolParser
from .schemas import (
    ParsedProtocol, Estimand, EndpointType, StudyPhase,
    ICEStrategy, InterCurrentEvent, DesignType, BlindingType
)
from .config import get_config

# Import logging
try:
    from .logging_config import get_logger, ExtractionError
except ImportError:
    import logging
    def get_logger(name):
        return logging.getLogger(name)
    class ExtractionError(Exception):
        pass

logger = get_logger(__name__)


class EnhancedProtocolParser(ProtocolParser):
    """
    Enhanced parser that uses LLM for low-confidence extractions.
    Achieves higher accuracy by combining pattern matching with LLM.
    """

    LLM_EXTRACTION_PROMPT = """You are an expert biostatistician analyzing a clinical trial protocol. Your task is to identify the PRIMARY endpoint of this study.

PROTOCOL EXCERPT:
{text}

CRITICAL INSTRUCTIONS:
1. Focus ONLY on the PRIMARY endpoint, not secondary endpoints
2. Look for explicit statements like "primary endpoint", "primary objective", "primary outcome"
3. Phase 1 studies almost always have SAFETY as primary (MTD, DLT, tolerability)
4. If a survival endpoint (OS, PFS, DFS) is mentioned as PRIMARY, classify it accordingly
5. ORR is common in Phase 2 oncology studies

CLASSIFICATION RULES:
- SAFETY: Primary is safety/tolerability, MTD, DLT, RP2D, dose-finding, first-in-human
- OS: Primary is overall survival, time to death from any cause
- PFS: Primary is progression-free survival, time to disease progression or death
- ORR: Primary is objective response rate, overall response rate, tumor response by RECIST
- DFS: Primary is disease-free survival, recurrence-free survival (adjuvant setting)
- EFS: Primary is event-free survival (composite of multiple events)
- PK: Primary is pharmacokinetics (AUC, Cmax, bioavailability, drug-drug interaction)
- OTHER: ONLY use if none of the above fit AND you cannot determine the primary endpoint

Respond with JSON only:
{{
    "phase": "1" | "1a" | "1b" | "1/2" | "2" | "2a" | "2b" | "2/3" | "3" | "3a" | "3b" | "4" | "unknown",
    "primary_endpoint_type": "SAFETY" | "ORR" | "PFS" | "OS" | "DFS" | "EFS" | "PK" | "OTHER",
    "primary_endpoint_description": "exact description from protocol",
    "therapeutic_area": "Oncology" | "Cardiovascular" | "CNS" | "Infectious Disease" | "Metabolic" | "Respiratory" | "Immunology" | "Other",
    "design_type": "parallel" | "crossover" | "single_arm" | "adaptive",
    "reasoning": "brief explanation of why you chose this endpoint type",
    "confidence": 0.0 to 1.0
}}

IMPORTANT: Be specific. Avoid defaulting to OTHER unless truly necessary."""

    def __init__(self, llm_client=None, use_llm_fallback: bool = True):
        """
        Initialize enhanced parser.

        Args:
            llm_client: LLM client (will be created if not provided)
            use_llm_fallback: Whether to use LLM when confidence is low
        """
        super().__init__(llm_client)
        self.use_llm_fallback = use_llm_fallback
        self.config = get_config()
        self._use_tiered = False

        # Confidence threshold for LLM fallback (lower = more LLM usage)
        self.confidence_threshold = 0.6  # Trigger LLM if below 60% confidence

        logger.info(
            "EnhancedProtocolParser initialized",
            use_llm_fallback=use_llm_fallback,
            confidence_threshold=self.confidence_threshold
        )

    def parse(self, protocol_text: str, nct_id: str = "") -> ParsedProtocol:
        """
        Parse protocol with LLM enhancement for low-confidence fields.
        """
        logger.debug("Starting enhanced parse", nct_id=nct_id, text_length=len(protocol_text))

        # First, use pattern-based parsing
        result = super().parse(protocol_text, nct_id)

        # Check if LLM fallback is needed
        needs_llm = False

        if self.use_llm_fallback:
            # Check confidence scores
            endpoint_conf = result.extraction_confidence.get('endpoint_type', 0)
            phase_conf = result.extraction_confidence.get('phase', 0)

            if endpoint_conf < self.confidence_threshold or phase_conf < self.confidence_threshold:
                needs_llm = True
                logger.debug(
                    "Low confidence triggers LLM fallback",
                    endpoint_confidence=endpoint_conf,
                    phase_confidence=phase_conf,
                    threshold=self.confidence_threshold
                )

            # Also trigger LLM if endpoint is OTHER with low confidence
            if result.primary_estimand and result.primary_estimand.variable_type == EndpointType.OTHER:
                needs_llm = True
                logger.debug("OTHER endpoint type triggers LLM fallback")

        if needs_llm and self._has_llm_client():
            result = self._enhance_with_llm(result, protocol_text)

        return result

    def _has_llm_client(self) -> bool:
        """Check if LLM client is available (uses TieredLLMClient)"""
        if self.llm_client:
            return True

        # Use TieredLLMClient for automatic fallback through Claude → OpenAI → Groq
        try:
            from .tiered_llm import get_tiered_client
            tiered_client = get_tiered_client()
            available_tiers = tiered_client.get_available_tiers()
            if available_tiers:
                self.llm_client = tiered_client
                self._use_tiered = True
                logger.debug("Using TieredLLMClient", available_tiers=available_tiers)
                return True
            else:
                logger.warning("TieredLLMClient has no available tiers")
        except ImportError as e:
            logger.warning("Failed to import TieredLLMClient", error=str(e))
        except Exception as e:
            logger.error("Error initializing TieredLLMClient", exc_info=True, error=str(e))

        # Fallback to Groq-only if tiered fails
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            try:
                from groq import Groq
                self.llm_client = Groq(api_key=api_key)
                self._use_tiered = False
                logger.info("Using direct Groq client as fallback")
                return True
            except ImportError:
                logger.warning("groq package not installed", install_cmd="pip install groq")

        logger.warning("No LLM client available - pattern matching only")
        return False

    def _enhance_with_llm(self, result: ParsedProtocol, protocol_text: str) -> ParsedProtocol:
        """Use LLM to enhance low-confidence extractions (supports tiered fallback)"""
        logger.debug("Enhancing extraction with LLM")

        try:
            # Extract relevant section for LLM
            relevant_text = self._extract_relevant_section(protocol_text)
            logger.debug("Extracted relevant section", section_length=len(relevant_text))

            # Call LLM
            prompt = self.LLM_EXTRACTION_PROMPT.format(text=relevant_text)

            # Check if using TieredLLMClient
            if getattr(self, '_use_tiered', False):
                # Use tiered client for automatic fallback
                response = self.llm_client.chat(
                    prompt=prompt,
                    temperature=0.1,
                    max_tokens=500,
                    json_mode=True
                )
                if response.success:
                    try:
                        llm_result = json.loads(response.content)
                        logger.info(
                            "LLM extraction successful",
                            source=response.source,
                            latency_ms=response.latency_ms
                        )
                    except json.JSONDecodeError as e:
                        logger.warning(
                            "LLM returned invalid JSON",
                            error=str(e),
                            content_preview=response.content[:100] if response.content else ""
                        )
                        return result  # Keep pattern-based result
                else:
                    logger.warning("LLM call failed", error=response.error)
                    return result  # Keep pattern-based result
            else:
                # Legacy single-client mode (Groq direct)
                try:
                    response = self.llm_client.chat.completions.create(
                        model=self.config.model.fast_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=500,
                        response_format={"type": "json_object"}
                    )

                    # Null-safe response extraction
                    if response is None or not hasattr(response, 'choices') or not response.choices:
                        logger.warning("Groq returned empty response")
                        return result

                    message = response.choices[0].message
                    if message is None or not hasattr(message, 'content') or message.content is None:
                        logger.warning("Groq message has no content")
                        return result

                    llm_result = json.loads(message.content)
                    logger.info("Groq extraction successful")

                except json.JSONDecodeError as e:
                    logger.warning("Groq returned invalid JSON", error=str(e))
                    return result
                except AttributeError as e:
                    logger.error("Groq response structure error", exc_info=True, error=str(e))
                    return result

            # Update result with LLM extractions
            result = self._merge_llm_result(result, llm_result)
            logger.debug("Merged LLM result with pattern-based extraction")

        except json.JSONDecodeError as e:
            logger.warning(
                "JSON parsing failed in LLM enhancement",
                error=str(e),
                error_type="JSONDecodeError"
            )
        except ConnectionError as e:
            logger.error(
                "Network error during LLM call",
                error=str(e),
                error_type="ConnectionError"
            )
        except TimeoutError as e:
            logger.error(
                "Timeout during LLM call",
                error=str(e),
                error_type="TimeoutError"
            )
        except Exception as e:
            # Log unexpected errors with full traceback
            logger.error(
                "Unexpected error in LLM enhancement - falling back to pattern matching",
                exc_info=True,
                error_type=type(e).__name__,
                error=str(e)
            )

        return result

    def _extract_relevant_section(self, text: str, max_chars: int = 6000) -> str:
        """Extract most relevant section for LLM analysis - comprehensive approach"""
        sections = []

        # Priority 1: Primary endpoint section
        primary_patterns = [
            r'(?:^|\n)\s*(?:\d+\.?\d*\.?\s*)?primary\s+(?:endpoint|objective|outcome)s?\s*[:\n](.*?)(?=\n\s*(?:\d+\.|secondary|exploratory)|\Z)',
            r'primary\s+(?:efficacy\s+)?endpoint[:\s]+(.*?)(?=\n\s*secondary|\n\n|\Z)',
        ]
        for pattern in primary_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                sections.append(("PRIMARY ENDPOINT SECTION:\n" + match.group(0)[:1500], 1))
                break

        # Priority 2: Objectives section
        obj_patterns = [
            r'(?:^|\n)\s*(?:\d+\.?\d*\.?\s*)?(?:study\s+)?objectives?\s+and\s+endpoints?\s*[:\n](.*?)(?=\n\s*\d+\.|\Z)',
            r'(?:^|\n)\s*(?:\d+\.?\d*\.?\s*)?(?:study\s+)?objectives?\s*[:\n](.*?)(?=\n\s*\d+\.|\Z)',
        ]
        for pattern in obj_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                sections.append(("OBJECTIVES SECTION:\n" + match.group(0)[:2000], 2))
                break

        # Priority 3: Synopsis
        synopsis_match = re.search(
            r'(?:^|\n)\s*synopsis\s*[:\n](.*?)(?=\n\s*\d+\.|\n\s*table\s+of\s+contents|\Z)',
            text, re.IGNORECASE | re.DOTALL
        )
        if synopsis_match:
            sections.append(("SYNOPSIS:\n" + synopsis_match.group(1)[:2000], 3))

        # Combine sections, prioritizing most relevant
        if sections:
            sections.sort(key=lambda x: x[1])
            combined = "\n\n".join([s[0] for s in sections])
            return combined[:max_chars]

        # Fallback: first part of document
        logger.debug("No specific sections found, using document start")
        return "PROTOCOL EXCERPT:\n" + text[:max_chars]

    def _merge_llm_result(self, result: ParsedProtocol, llm_result: Dict) -> ParsedProtocol:
        """Merge LLM extraction with pattern-based result"""

        # Update phase if LLM is confident
        llm_phase = llm_result.get('phase', 'unknown')
        llm_conf = llm_result.get('confidence', 0.5)

        if llm_phase != 'unknown' and llm_conf > 0.6:
            try:
                # Map to StudyPhase enum
                phase_mapping = {
                    '1': StudyPhase.PHASE_1,
                    '1a': StudyPhase.PHASE_1A,
                    '1b': StudyPhase.PHASE_1B,
                    '1/2': StudyPhase.PHASE_1_2,
                    '2': StudyPhase.PHASE_2,
                    '2a': StudyPhase.PHASE_2A,
                    '2b': StudyPhase.PHASE_2B,
                    '2/3': StudyPhase.PHASE_2_3,
                    '3': StudyPhase.PHASE_3,
                    '3a': StudyPhase.PHASE_3A,
                    '3b': StudyPhase.PHASE_3B,
                    '4': StudyPhase.PHASE_4,
                }
                if llm_phase in phase_mapping:
                    result.phase = phase_mapping[llm_phase]
                    result.extraction_confidence['phase'] = llm_conf
                    logger.debug("Updated phase from LLM", phase=llm_phase, confidence=llm_conf)
                else:
                    logger.debug("Unknown phase value from LLM", phase=llm_phase)
            except ValueError as e:
                logger.warning("Invalid phase value from LLM", phase=llm_phase, error=str(e))
            except KeyError as e:
                logger.warning("Phase mapping error", phase=llm_phase, error=str(e))

        # Update endpoint type if LLM is confident
        llm_endpoint = llm_result.get('primary_endpoint_type', 'OTHER')

        if llm_endpoint != 'OTHER' or llm_conf > 0.7:
            try:
                endpoint_type = EndpointType(llm_endpoint)

                # Update or create primary estimand
                if result.primary_estimand:
                    result.primary_estimand.variable_type = endpoint_type
                    if llm_result.get('primary_endpoint_description'):
                        result.primary_estimand.variable = llm_result['primary_endpoint_description']
                else:
                    result.primary_estimand = self._build_estimand(
                        "", endpoint_type,
                        llm_result.get('primary_endpoint_description', ''),
                        is_primary=True
                    )
                    result.primary_estimand.variable_type = endpoint_type

                result.extraction_confidence['endpoint_type'] = llm_conf
                logger.debug(
                    "Updated endpoint type from LLM",
                    endpoint_type=llm_endpoint,
                    confidence=llm_conf
                )
            except ValueError as e:
                logger.warning(
                    "Invalid endpoint type from LLM",
                    endpoint_type=llm_endpoint,
                    error=str(e)
                )

        # Update therapeutic area
        if llm_result.get('therapeutic_area') and llm_result['therapeutic_area'] != 'Other':
            result.therapeutic_area = llm_result['therapeutic_area']
            result.extraction_confidence['therapeutic_area'] = llm_conf
            logger.debug("Updated therapeutic area from LLM", area=llm_result['therapeutic_area'])

        # Update design type
        design_mapping = {
            'parallel': DesignType.PARALLEL,
            'crossover': DesignType.CROSSOVER,
            'single_arm': DesignType.SINGLE_ARM,
            'adaptive': DesignType.ADAPTIVE,
        }
        if llm_result.get('design_type') in design_mapping:
            result.design_type = design_mapping[llm_result['design_type']]
            result.extraction_confidence['design_type'] = llm_conf
            logger.debug("Updated design type from LLM", design=llm_result['design_type'])

        return result


def create_enhanced_parser(use_llm_fallback: bool = True) -> EnhancedProtocolParser:
    """Create an enhanced parser instance"""
    return EnhancedProtocolParser(use_llm_fallback=use_llm_fallback)
