#!/usr/bin/env python3
"""
Method Extractor Agent
======================

Agent 3 in the Agentic HybridRAG architecture.

This agent:
1. Takes retrieved chunks from hybrid retriever
2. Uses LLM to READ the chunks and extract actual methods used
3. If insufficient info, queries again with refined terms (iterative)
4. Returns structured method recommendations based on what similar trials ACTUALLY did

Key insight: Instead of using frequency statistics, we have the LLM
actually READ what methods similar trials used and WHY.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Tuple

from enterprise_sap_system.rag.hybrid_retriever import (
    HybridRetriever, HybridResult, ProtocolCharacteristics, create_hybrid_retriever
)


@dataclass
class ExtractedMethods:
    """Methods extracted from similar SAP chunks by the LLM."""
    primary_analysis: Dict[str, Any] = field(default_factory=dict)
    interim_analysis: Dict[str, Any] = field(default_factory=dict)
    sensitivity_analysis: Dict[str, Any] = field(default_factory=dict)
    multiplicity: Dict[str, Any] = field(default_factory=dict)
    missing_data: Dict[str, Any] = field(default_factory=dict)

    # Source tracking
    source_trials: List[str] = field(default_factory=list)
    source_chunks: List[str] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""


class MethodExtractorAgent:
    """
    Agent that reads retrieved chunks and extracts actual methods used.

    This is the key differentiator from rule-based systems:
    - Rules say "if immunotherapy, use FH"
    - This agent says "similar trials used FH because of delayed effect"
    """

    EXTRACTION_PROMPT = """You are a statistical methodology expert analyzing clinical trial SAPs.

Given the following SAP chunks from similar clinical trials, extract the statistical methods used.

PROTOCOL CHARACTERISTICS:
{characteristics}

RETRIEVED SAP CHUNKS FROM SIMILAR TRIALS:
{chunks}

Based on these similar trials, extract the methods they used. For each method category, provide:
1. The specific method used
2. The rationale (why this method was chosen)
3. Confidence level (how many similar trials used this)

Respond in JSON format:
{{
    "primary_analysis": {{
        "method": "log_rank | fleming_harrington | rmst | maxcombo",
        "specification": "e.g., FH(0,1) or stratified log-rank",
        "rationale": "why this method based on the chunks",
        "confidence": 0.0-1.0
    }},
    "interim_analysis": {{
        "method": "lan_demets | obrien_fleming | pocock | none",
        "specification": "e.g., O'Brien-Fleming spending function",
        "rationale": "why this approach",
        "confidence": 0.0-1.0
    }},
    "sensitivity_analysis": {{
        "methods": ["list of sensitivity methods used"],
        "crossover_adjustment": "rpsft | ipcw | none",
        "rationale": "why these methods",
        "confidence": 0.0-1.0
    }},
    "multiplicity": {{
        "method": "hierarchical | gatekeeping | bonferroni | none",
        "testing_order": ["ordered list of endpoints"],
        "rationale": "why this approach",
        "confidence": 0.0-1.0
    }},
    "overall_reasoning": "Summary of why these methods are appropriate for this type of trial"
}}

IMPORTANT:
- Base your recommendations ONLY on what the similar trials actually used
- If chunks show Fleming-Harrington was used for immunotherapy with delayed effect, recommend that
- Include specific parameters (e.g., FH(0,1) not just "Fleming-Harrington")
- If information is insufficient, set confidence low and explain what's missing
"""

    REFINEMENT_PROMPT = """The initial retrieval didn't provide enough information about {missing_info}.

Search for more specific information about:
{refined_query}

From the following additional chunks:
{chunks}

Extract the specific methods used for {missing_info}.
Respond in JSON format with the same structure as before.
"""

    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        llm_client: Optional[Any] = None,
        max_iterations: int = 3,
    ):
        """
        Initialize method extractor agent.

        Args:
            retriever: Hybrid retriever for fetching chunks
            llm_client: LLM client for extraction (defaults to TieredLLMClient)
            max_iterations: Maximum retrieval iterations
        """
        self.retriever = retriever or create_hybrid_retriever()
        self.max_iterations = max_iterations

        # Initialize LLM client
        if llm_client is None:
            try:
                from enterprise_sap_system.core.tiered_llm import TieredLLMClient
                self.llm = TieredLLMClient()
            except ImportError:
                self.llm = None
                print("Warning: TieredLLMClient not available")
        else:
            self.llm = llm_client

    def _format_chunks_for_prompt(self, chunks: List[HybridResult], max_chars: int = 15000) -> str:
        """Format retrieved chunks for the LLM prompt."""
        formatted = []
        total_chars = 0

        for i, chunk in enumerate(chunks):
            chunk_text = f"""
--- CHUNK {i+1} (Trial: {chunk.nct_id}, Score: {chunk.combined_score:.2f}) ---
Section: {chunk.section_type}
Methods detected: {', '.join(chunk.methods_found) if chunk.methods_found else 'none'}

{chunk.content[:2000]}...
"""
            if total_chars + len(chunk_text) > max_chars:
                break

            formatted.append(chunk_text)
            total_chars += len(chunk_text)

        return "\n".join(formatted)

    def _format_characteristics(self, chars: ProtocolCharacteristics) -> str:
        """Format protocol characteristics for the prompt."""
        parts = []

        if chars.drug_classes:
            parts.append(f"Drug class: {', '.join(chars.drug_classes)}")
        if chars.indication:
            parts.append(f"Indication: {chars.indication}")
        if chars.phase:
            parts.append(f"Phase: {chars.phase}")
        if chars.endpoint_type:
            parts.append(f"Primary endpoint: {chars.endpoint_type}")
        if chars.conditions:
            parts.append(f"Conditions: {', '.join(chars.conditions)}")
        if chars.regions:
            parts.append(f"Regions: {', '.join(chars.regions)}")

        return "\n".join(parts)

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from LLM."""
        # Try to extract JSON from response
        try:
            # Find JSON block
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        # Return empty structure if parsing fails
        return {
            "primary_analysis": {"method": "unknown", "confidence": 0.0},
            "interim_analysis": {"method": "unknown", "confidence": 0.0},
            "sensitivity_analysis": {"methods": [], "confidence": 0.0},
            "multiplicity": {"method": "unknown", "confidence": 0.0},
            "overall_reasoning": "Failed to parse LLM response"
        }

    def _check_confidence(self, extracted: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Check if extraction has sufficient confidence, return missing areas."""
        missing = []
        threshold = 0.5

        if extracted.get("primary_analysis", {}).get("confidence", 0) < threshold:
            missing.append("primary_analysis")

        if extracted.get("interim_analysis", {}).get("confidence", 0) < threshold:
            missing.append("interim_analysis")

        if extracted.get("sensitivity_analysis", {}).get("confidence", 0) < threshold:
            missing.append("sensitivity_analysis")

        return len(missing) == 0, missing

    def _get_refined_query(self, missing_areas: List[str], chars: ProtocolCharacteristics) -> str:
        """Generate refined query for missing information."""
        queries = {
            "primary_analysis": f"primary analysis method {chars.endpoint_type} endpoint statistical test log-rank Fleming-Harrington",
            "interim_analysis": f"interim analysis alpha spending Lan-DeMets O'Brien-Fleming stopping boundary",
            "sensitivity_analysis": f"sensitivity analysis crossover RPSFT IPCW treatment switching per-protocol",
            "multiplicity": f"multiplicity adjustment hierarchical testing gatekeeping multiple endpoints",
        }

        return " ".join(queries.get(area, "") for area in missing_areas)

    def extract_methods(
        self,
        characteristics: ProtocolCharacteristics,
        initial_chunks: Optional[List[HybridResult]] = None,
    ) -> ExtractedMethods:
        """
        Extract methods from similar trials using iterative retrieval.

        Args:
            characteristics: Protocol characteristics
            initial_chunks: Pre-retrieved chunks (optional)

        Returns:
            ExtractedMethods with methods and reasoning
        """
        # Get initial chunks if not provided
        if initial_chunks is None:
            initial_chunks = self.retriever.retrieve(characteristics, n_results=15)

        if not initial_chunks:
            return ExtractedMethods(
                confidence=0.0,
                reasoning="No similar trials found in the database"
            )

        # Track sources
        source_trials = list(set(c.nct_id for c in initial_chunks if c.nct_id))
        source_chunks = [c.chunk_id for c in initial_chunks]

        # If no LLM available, fall back to pattern-based extraction
        if self.llm is None:
            return self._pattern_based_extraction(initial_chunks, source_trials, source_chunks)

        # Build prompt
        prompt = self.EXTRACTION_PROMPT.format(
            characteristics=self._format_characteristics(characteristics),
            chunks=self._format_chunks_for_prompt(initial_chunks)
        )

        # Call LLM
        try:
            response = self.llm.chat(prompt, max_tokens=2000)
            if hasattr(response, 'content') and response.content:
                response_text = response.content
            elif hasattr(response, 'success') and response.success and response.content:
                response_text = response.content
            else:
                # LLM returned empty - use fallback
                print("LLM returned empty response, using pattern-based extraction")
                return self._pattern_based_extraction(initial_chunks, source_trials, source_chunks)
        except Exception as e:
            print(f"LLM error: {e}, using pattern-based extraction")
            return self._pattern_based_extraction(initial_chunks, source_trials, source_chunks)

        # Parse response
        extracted = self._parse_llm_response(response_text)

        # Check confidence and iterate if needed
        sufficient, missing = self._check_confidence(extracted)
        iteration = 0

        while not sufficient and iteration < self.max_iterations:
            iteration += 1

            # Get refined query
            refined_query = self._get_refined_query(missing, characteristics)

            # Retrieve more chunks
            additional_chunks = self.retriever.retrieve(
                characteristics,
                section_types=missing,  # Focus on missing areas
                n_results=10
            )

            if not additional_chunks:
                break

            # Refine extraction
            refinement_prompt = self.REFINEMENT_PROMPT.format(
                missing_info=", ".join(missing),
                refined_query=refined_query,
                chunks=self._format_chunks_for_prompt(additional_chunks)
            )

            try:
                response = self.llm.chat(refinement_prompt, max_tokens=1500)
                if hasattr(response, 'content'):
                    response_text = response.content
                else:
                    response_text = str(response)

                refined = self._parse_llm_response(response_text)

                # Merge refined results
                for area in missing:
                    if refined.get(area, {}).get("confidence", 0) > extracted.get(area, {}).get("confidence", 0):
                        extracted[area] = refined[area]

            except Exception as e:
                print(f"Refinement error: {e}")
                break

            # Update tracking
            source_chunks.extend([c.chunk_id for c in additional_chunks])

            sufficient, missing = self._check_confidence(extracted)

        # Build result
        return ExtractedMethods(
            primary_analysis=extracted.get("primary_analysis", {}),
            interim_analysis=extracted.get("interim_analysis", {}),
            sensitivity_analysis=extracted.get("sensitivity_analysis", {}),
            multiplicity=extracted.get("multiplicity", {}),
            source_trials=source_trials,
            source_chunks=source_chunks,
            confidence=self._calculate_overall_confidence(extracted),
            reasoning=extracted.get("overall_reasoning", "")
        )

    def _pattern_based_extraction(
        self,
        chunks: List[HybridResult],
        source_trials: List[str],
        source_chunks: List[str]
    ) -> ExtractedMethods:
        """Fallback pattern-based extraction when LLM is unavailable."""
        # Collect all methods found from chunk metadata
        all_methods = {}
        for chunk in chunks:
            for method in chunk.methods_found:
                all_methods[method] = all_methods.get(method, 0) + 1

        # ALSO scan chunk content for methods (more thorough)
        for chunk in chunks:
            content_lower = chunk.content.lower()

            # Check for Fleming-Harrington
            if any(p in content_lower for p in ["fleming-harrington", "fleming harrington", "fh(", "g(0,1)", "g(1,0)", "weighted log-rank", "weighted logrank"]):
                all_methods["fleming_harrington"] = all_methods.get("fleming_harrington", 0) + 1

            # Check for other methods
            if "log-rank" in content_lower or "logrank" in content_lower:
                all_methods["log_rank"] = all_methods.get("log_rank", 0) + 1

            if "rmst" in content_lower or "restricted mean survival" in content_lower:
                all_methods["rmst"] = all_methods.get("rmst", 0) + 1

            if "maxcombo" in content_lower or "max-combo" in content_lower:
                all_methods["maxcombo"] = all_methods.get("maxcombo", 0) + 1

            if "rpsft" in content_lower or "rank preserving" in content_lower:
                all_methods["rpsft"] = all_methods.get("rpsft", 0) + 1

            if "ipcw" in content_lower or "inverse probability" in content_lower:
                all_methods["ipcw"] = all_methods.get("ipcw", 0) + 1

            if "lan-demets" in content_lower or "lan demets" in content_lower or "alpha spending" in content_lower:
                all_methods["lan_demets"] = all_methods.get("lan_demets", 0) + 1

            if "o'brien-fleming" in content_lower or "obrien-fleming" in content_lower:
                all_methods["obrien_fleming"] = all_methods.get("obrien_fleming", 0) + 1

            if "hierarchical" in content_lower or "gatekeeping" in content_lower:
                all_methods["hierarchical_testing"] = all_methods.get("hierarchical_testing", 0) + 1

        # Determine primary analysis - prioritize FH for immunotherapy-like trials
        primary_method = "log_rank"  # default
        primary_rationale = "default"

        # If FH is mentioned, prefer it (especially for immunotherapy)
        if all_methods.get("fleming_harrington", 0) >= 1:
            primary_method = "fleming_harrington"
            primary_rationale = f"Found in {all_methods.get('fleming_harrington', 0)} chunks from similar trials"
        elif all_methods.get("maxcombo", 0) >= 1:
            primary_method = "maxcombo"
            primary_rationale = f"Found in {all_methods.get('maxcombo', 0)} chunks"
        elif all_methods.get("rmst", 0) >= 2:
            primary_method = "rmst"
            primary_rationale = f"Found in {all_methods.get('rmst', 0)} chunks"
        elif all_methods.get("log_rank", 0) >= 1:
            primary_method = "log_rank"
            primary_rationale = f"Found in {all_methods.get('log_rank', 0)} chunks"

        # Determine interim
        interim_method = "none"
        interim_spec = ""
        if all_methods.get("lan_demets", 0) >= 1:
            interim_method = "lan_demets"
            if all_methods.get("obrien_fleming", 0) >= 1:
                interim_spec = "with O'Brien-Fleming spending function"

        # Determine sensitivity
        sensitivity_methods = []
        if all_methods.get("rpsft", 0) >= 1:
            sensitivity_methods.append("rpsft")
        if all_methods.get("ipcw", 0) >= 1:
            sensitivity_methods.append("ipcw")

        # Determine multiplicity
        multiplicity_method = "none"
        if all_methods.get("hierarchical_testing", 0) >= 1:
            multiplicity_method = "hierarchical"

        # Build detailed reasoning
        methods_summary = ", ".join(f"{k}:{v}" for k, v in sorted(all_methods.items(), key=lambda x: -x[1]) if v > 0)

        return ExtractedMethods(
            primary_analysis={
                "method": primary_method,
                "specification": "stratified" if all_methods.get("log_rank", 0) > 0 else "",
                "confidence": 0.7 if all_methods.get(primary_method, 0) >= 2 else 0.5,
                "rationale": primary_rationale
            },
            interim_analysis={
                "method": interim_method,
                "specification": interim_spec,
                "confidence": 0.6 if all_methods.get("lan_demets", 0) >= 1 else 0.3,
                "rationale": f"Found in {all_methods.get('lan_demets', 0)} chunks"
            },
            sensitivity_analysis={
                "methods": sensitivity_methods,
                "crossover_adjustment": "rpsft" if "rpsft" in sensitivity_methods else ("ipcw" if "ipcw" in sensitivity_methods else "none"),
                "confidence": 0.6 if sensitivity_methods else 0.3,
                "rationale": f"Methods found: {', '.join(sensitivity_methods) if sensitivity_methods else 'none'}"
            },
            multiplicity={
                "method": multiplicity_method,
                "confidence": 0.6 if all_methods.get("hierarchical_testing", 0) >= 1 else 0.3,
                "rationale": f"Found in {all_methods.get('hierarchical_testing', 0)} chunks"
            },
            source_trials=source_trials,
            source_chunks=source_chunks,
            confidence=0.6,
            reasoning=f"Extracted from {len(chunks)} chunks. Methods found: {methods_summary}"
        )

    def _calculate_overall_confidence(self, extracted: Dict[str, Any]) -> float:
        """Calculate overall confidence from individual components."""
        confidences = [
            extracted.get("primary_analysis", {}).get("confidence", 0),
            extracted.get("interim_analysis", {}).get("confidence", 0),
            extracted.get("sensitivity_analysis", {}).get("confidence", 0),
            extracted.get("multiplicity", {}).get("confidence", 0),
        ]
        return sum(confidences) / len(confidences) if confidences else 0.0

    def extract_for_protocol(self, protocol_text: str) -> ExtractedMethods:
        """
        Extract methods from protocol text.

        Args:
            protocol_text: Raw protocol text

        Returns:
            ExtractedMethods
        """
        # Extract characteristics
        chars = self.retriever.extract_characteristics(protocol_text)

        # Extract methods
        return self.extract_methods(chars)


def create_method_extractor(
    retriever: Optional[HybridRetriever] = None,
    llm_client: Optional[Any] = None,
) -> MethodExtractorAgent:
    """Factory function to create method extractor agent."""
    return MethodExtractorAgent(retriever=retriever, llm_client=llm_client)


if __name__ == "__main__":
    print("=" * 70)
    print("METHOD EXTRACTOR AGENT TEST")
    print("=" * 70)

    # Create agent
    agent = create_method_extractor()

    # Test: Checkpoint inhibitor + NSCLC + delayed effect
    print("\n--- Test: Checkpoint Inhibitor + NSCLC + Delayed Effect ---")

    chars = ProtocolCharacteristics(
        drug_classes=["checkpoint_inhibitor"],
        indication="nsclc",
        phase="3",
        endpoint_type="OS",
        conditions=["delayed_effect", "interim_analysis", "crossover"]
    )

    result = agent.extract_methods(chars)

    print(f"\nSource trials: {result.source_trials[:5]}")
    print(f"Confidence: {result.confidence:.1%}")

    print("\nExtracted Methods:")
    print(f"  Primary: {result.primary_analysis}")
    print(f"  Interim: {result.interim_analysis}")
    print(f"  Sensitivity: {result.sensitivity_analysis}")
    print(f"  Multiplicity: {result.multiplicity}")

    print(f"\nReasoning: {result.reasoning[:500]}...")

    # Test from protocol text
    print("\n--- Test: From Protocol Text ---")

    test_protocol = """
    A Phase 3, Randomized Study of Pembrolizumab versus Chemotherapy
    in Patients with Advanced Melanoma

    Primary Endpoint: Overall Survival

    Given the mechanism of action of checkpoint inhibitors, a delayed
    treatment effect is expected. Fleming-Harrington weighted log-rank
    test may be considered for sensitivity analysis.

    Interim analyses will be conducted using the Lan-DeMets alpha spending
    function with O'Brien-Fleming boundaries.

    Patients randomized to chemotherapy may cross over to pembrolizumab
    upon disease progression. RPSFT analysis will be conducted.
    """

    result2 = agent.extract_for_protocol(test_protocol)

    print(f"\nExtracted from text:")
    print(f"  Primary: {result2.primary_analysis.get('method', 'unknown')}")
    print(f"  Interim: {result2.interim_analysis.get('method', 'unknown')}")
    print(f"  Sensitivity: {result2.sensitivity_analysis.get('methods', [])}")
    print(f"  Confidence: {result2.confidence:.1%}")
