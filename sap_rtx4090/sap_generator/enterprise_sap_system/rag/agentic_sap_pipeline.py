#!/usr/bin/env python3
"""
Agentic HybridRAG SAP Pipeline
==============================

Production-grade SAP generation using:
1. Agent 1: Protocol Analyzer - Extract structured facts
2. Agent 2: Hybrid Retriever - Vector + Graph search
3. Agent 3: Method Extractor - Read chunks, extract methods
4. Agent 4: SAP Generator - Generate using chunk examples
5. Agent 5: Validator - Compare output to source chunks

This replaces the old RuleBasedSAPPipeline with a data-driven approach
that learns from the 23K SAP chunks instead of hardcoded rules.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from enterprise_sap_system.rag.hybrid_retriever import (
    HybridRetriever, HybridResult, ProtocolCharacteristics, create_hybrid_retriever
)
from enterprise_sap_system.rag.method_extractor_agent import (
    MethodExtractorAgent, ExtractedMethods, create_method_extractor
)


@dataclass
class ValidationResult:
    """Result of validating generated SAP against source chunks."""
    is_valid: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    method_matches: Dict[str, bool] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class SAPGenerationResult:
    """Result of SAP generation."""
    success: bool
    sap_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)

    # Traceability
    source_trials: List[str] = field(default_factory=list)
    extracted_methods: Optional[ExtractedMethods] = None
    validation: Optional[ValidationResult] = None
    characteristics: Optional[ProtocolCharacteristics] = None

    # Metadata
    warnings: List[str] = field(default_factory=list)
    confidence: float = 0.0


class ValidatorAgent:
    """
    Agent 5: Validates generated SAP against source chunks.

    Checks:
    1. Did we use the methods that similar trials used?
    2. Is the terminology consistent with source chunks?
    3. Are there any obvious errors or hallucinations?
    """

    def __init__(self, retriever: Optional[HybridRetriever] = None):
        self.retriever = retriever or create_hybrid_retriever()

    def validate(
        self,
        generated_sap: str,
        extracted_methods: ExtractedMethods,
        characteristics: ProtocolCharacteristics,
        source_chunks: List[HybridResult],
    ) -> ValidationResult:
        """
        Validate generated SAP against source chunks.

        Args:
            generated_sap: Generated SAP text
            extracted_methods: Methods extracted from similar trials
            characteristics: Protocol characteristics
            source_chunks: Source chunks used for generation

        Returns:
            ValidationResult
        """
        issues = []
        warnings = []
        method_matches = {}

        sap_lower = generated_sap.lower()

        # Check 1: Primary analysis method consistency
        primary_method = extracted_methods.primary_analysis.get("method", "")
        if primary_method == "fleming_harrington":
            if "fleming" not in sap_lower and "harrington" not in sap_lower:
                issues.append(
                    f"Similar trials use Fleming-Harrington but generated SAP doesn't mention it. "
                    f"Source: {extracted_methods.primary_analysis.get('rationale', '')}"
                )
                method_matches["primary_analysis"] = False
            else:
                method_matches["primary_analysis"] = True
        elif primary_method == "log_rank":
            if "log-rank" not in sap_lower and "logrank" not in sap_lower:
                warnings.append("Expected log-rank test but not found in SAP")
                method_matches["primary_analysis"] = False
            else:
                method_matches["primary_analysis"] = True

        # Check 2: Interim analysis consistency
        interim_method = extracted_methods.interim_analysis.get("method", "")
        if interim_method == "lan_demets":
            if "lan" not in sap_lower or "demets" not in sap_lower:
                if "alpha spending" not in sap_lower:
                    warnings.append("Similar trials use Lan-DeMets but not clearly stated in SAP")
                    method_matches["interim_analysis"] = False
                else:
                    method_matches["interim_analysis"] = True
            else:
                method_matches["interim_analysis"] = True

        # Check 3: Crossover adjustment consistency
        sensitivity = extracted_methods.sensitivity_analysis
        if isinstance(sensitivity, dict):
            crossover_method = sensitivity.get("crossover_adjustment", "none")
            if crossover_method == "rpsft":
                if "rpsft" not in sap_lower and "rank preserving" not in sap_lower:
                    if "crossover" in (characteristics.conditions or []):
                        issues.append("Protocol has crossover but RPSFT not mentioned in SAP")
                        method_matches["sensitivity_analysis"] = False
                    else:
                        method_matches["sensitivity_analysis"] = True
                else:
                    method_matches["sensitivity_analysis"] = True

        # Check 4: Hierarchical testing consistency
        multiplicity = extracted_methods.multiplicity
        if isinstance(multiplicity, dict) and multiplicity.get("method") == "hierarchical":
            if "hierarchical" not in sap_lower and "gatekeeping" not in sap_lower:
                warnings.append("Similar trials use hierarchical testing but not found in SAP")
                method_matches["multiplicity"] = False
            else:
                method_matches["multiplicity"] = True

        # Check 5: Drug class specific checks
        if "checkpoint_inhibitor" in (characteristics.drug_classes or []):
            # Immunotherapy should mention delayed effect considerations
            if "delayed" not in sap_lower and "non-proportional" not in sap_lower:
                warnings.append(
                    "Immunotherapy trial should consider delayed treatment effect in SAP"
                )

        # Calculate confidence
        total_checks = len(method_matches)
        matches = sum(1 for v in method_matches.values() if v)
        confidence = matches / total_checks if total_checks > 0 else 0.5

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            method_matches=method_matches,
            confidence=confidence
        )


class SAPGeneratorAgent:
    """
    Agent 4: Generates SAP sections using extracted methods and chunk examples.
    """

    SECTION_TEMPLATE = """Based on the following methodology extracted from similar clinical trials,
generate the {section_name} section for a Statistical Analysis Plan.

PROTOCOL CHARACTERISTICS:
{characteristics}

METHODS TO USE (from similar trials):
{methods}

EXAMPLE CHUNKS FROM SIMILAR TRIALS:
{examples}

Generate a detailed {section_name} section that:
1. Uses the methods found in similar trials
2. Follows the style and terminology from the examples
3. Is specific to the protocol characteristics above

Section:"""

    def __init__(self, llm_client: Optional[Any] = None):
        if llm_client is None:
            try:
                from enterprise_sap_system.core.tiered_llm import TieredLLMClient
                self.llm = TieredLLMClient()
            except ImportError:
                self.llm = None
        else:
            self.llm = llm_client

    def _generate_section_with_llm(
        self,
        section_name: str,
        characteristics: ProtocolCharacteristics,
        methods: ExtractedMethods,
        chunks: List[HybridResult]
    ) -> str:
        """Generate a section using LLM with chunk examples."""
        if self.llm is None:
            # NO FALLBACK TEMPLATES - use actual chunk content
            return self._use_real_chunk_content(section_name, chunks, methods)

        # Format characteristics
        chars_text = f"""
Drug class: {', '.join(characteristics.drug_classes) if characteristics.drug_classes else 'Not specified'}
Indication: {characteristics.indication or 'Not specified'}
Phase: {characteristics.phase or 'Not specified'}
Primary endpoint: {characteristics.endpoint_type or 'Not specified'}
Conditions: {', '.join(characteristics.conditions) if characteristics.conditions else 'None'}
"""

        # Format methods
        methods_text = f"""
Primary analysis: {methods.primary_analysis.get('method', 'log_rank')} ({methods.primary_analysis.get('rationale', '')})
Interim analysis: {methods.interim_analysis.get('method', 'none')}
Sensitivity: {methods.sensitivity_analysis.get('methods', []) if isinstance(methods.sensitivity_analysis, dict) else []}
Multiplicity: {methods.multiplicity.get('method', 'none') if isinstance(methods.multiplicity, dict) else 'none'}
"""

        # Format example chunks
        relevant_chunks = [c for c in chunks if section_name.lower() in c.section_type.lower()][:3]
        if not relevant_chunks:
            relevant_chunks = chunks[:3]

        examples_text = "\n\n".join([
            f"--- Example from {c.nct_id} ---\n{c.content[:1500]}..."
            for c in relevant_chunks
        ])

        prompt = self.SECTION_TEMPLATE.format(
            section_name=section_name,
            characteristics=chars_text,
            methods=methods_text,
            examples=examples_text
        )

        try:
            response = self.llm.chat(prompt, max_tokens=2000)
            if hasattr(response, 'content') and response.content:
                return response.content
        except Exception as e:
            print(f"LLM error generating {section_name}: {e}")

        # NO FALLBACK TEMPLATES - use actual chunk content
        return self._use_real_chunk_content(section_name, chunks, methods)

    def _use_real_chunk_content(
        self,
        section_name: str,
        chunks: List[HybridResult],
        methods: ExtractedMethods
    ) -> str:
        """
        USE REAL SAP CONTENT from retrieved chunks.
        NO TEMPLATES - actual methodology from similar trials.
        """
        # Find chunks matching this section type
        section_keywords = {
            "primary_analysis": ["primary analysis", "primary endpoint", "efficacy analysis", "log-rank", "fleming-harrington", "hazard ratio"],
            "interim_analysis": ["interim analysis", "interim look", "alpha spending", "lan-demets", "o'brien-fleming", "data monitoring"],
            "sensitivity_analysis": ["sensitivity analysis", "sensitivity analyses", "robustness", "rpsft", "ipcw", "censoring"],
            "multiplicity": ["multiplicity", "multiple endpoints", "hierarchical", "gatekeeping", "type i error", "alpha allocation"]
        }

        keywords = section_keywords.get(section_name, [section_name])

        # Score chunks by relevance to this section
        scored_chunks = []
        for chunk in chunks:
            content_lower = chunk.content.lower()
            score = sum(1 for kw in keywords if kw in content_lower)
            # Boost score if method matches
            if methods.primary_analysis.get('method') == 'fleming_harrington':
                if 'fleming' in content_lower or 'harrington' in content_lower:
                    score += 5
            if methods.interim_analysis.get('method') == 'lan_demets':
                if 'lan-demets' in content_lower or 'alpha spending' in content_lower:
                    score += 5
            if score > 0:
                scored_chunks.append((score, chunk))

        # Sort by score, get best matches
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        best_chunks = [c for _, c in scored_chunks[:3]]

        if not best_chunks:
            # No matching chunks - use any chunks
            best_chunks = chunks[:2]

        # Combine real chunk content
        section_title = section_name.replace("_", " ").title()
        content_parts = [f"## {section_title}\n"]

        for chunk in best_chunks:
            # Clean and use the ACTUAL content
            content = chunk.content.strip()
            # Add source attribution
            content_parts.append(f"\n{content}\n")
            content_parts.append(f"\n[Source: {chunk.nct_id}]\n")

        return "\n".join(content_parts)

    def _format_method_name(self, method: str) -> str:
        """Format method name for display."""
        names = {
            "log_rank": "stratified log-rank",
            "fleming_harrington": "Fleming-Harrington weighted log-rank",
            "rmst": "restricted mean survival time (RMST)",
            "maxcombo": "MaxCombo",
            "cox_regression": "Cox proportional hazards",
        }
        return names.get(method, method)

    def generate_sap(
        self,
        characteristics: ProtocolCharacteristics,
        methods: ExtractedMethods,
        chunks: List[HybridResult]
    ) -> Dict[str, str]:
        """Generate all SAP sections."""
        sections = {}

        section_names = [
            "primary_analysis",
            "interim_analysis",
            "sensitivity_analysis",
            "multiplicity"
        ]

        for section_name in section_names:
            sections[section_name] = self._generate_section_with_llm(
                section_name, characteristics, methods, chunks
            )

        return sections


class AgenticSAPPipeline:
    """
    Production-grade SAP generation pipeline using Agentic HybridRAG.

    Flow:
    1. Extract characteristics from protocol
    2. Retrieve similar trials (hybrid: vector + graph)
    3. Extract methods from similar trials
    4. Generate SAP sections
    5. Validate against source chunks
    6. If validation fails, iterate
    """

    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        method_extractor: Optional[MethodExtractorAgent] = None,
        generator: Optional[SAPGeneratorAgent] = None,
        validator: Optional[ValidatorAgent] = None,
        max_iterations: int = 2,
    ):
        self.retriever = retriever or create_hybrid_retriever()
        self.method_extractor = method_extractor or create_method_extractor(self.retriever)
        self.generator = generator or SAPGeneratorAgent()
        self.validator = validator or ValidatorAgent(self.retriever)
        self.max_iterations = max_iterations

    def generate(self, protocol_text: str) -> SAPGenerationResult:
        """
        Generate SAP from protocol text using agentic pipeline.

        Args:
            protocol_text: Raw protocol text

        Returns:
            SAPGenerationResult with generated SAP and traceability
        """
        warnings = []

        # Step 1: Extract characteristics
        characteristics = self.retriever.extract_characteristics(protocol_text)
        print(f"[Agent 1] Extracted: drug={characteristics.drug_classes}, indication={characteristics.indication}")

        # Step 2: Retrieve similar trials
        chunks = self.retriever.retrieve(characteristics, n_results=15)
        source_trials = list(set(c.nct_id for c in chunks if c.nct_id))
        print(f"[Agent 2] Retrieved {len(chunks)} chunks from {len(source_trials)} trials")

        # Step 3: Extract methods from similar trials
        methods = self.method_extractor.extract_methods(characteristics, chunks)
        print(f"[Agent 3] Extracted methods: primary={methods.primary_analysis.get('method')}, "
              f"interim={methods.interim_analysis.get('method')}")

        # Step 4: Generate SAP
        sections = self.generator.generate_sap(characteristics, methods, chunks)
        print(f"[Agent 4] Generated {len(sections)} sections")

        # Assemble SAP
        sap_text = self._assemble_sap(sections, characteristics)

        # Step 5: Validate
        validation = self.validator.validate(sap_text, methods, characteristics, chunks)
        print(f"[Agent 5] Validation: valid={validation.is_valid}, confidence={validation.confidence:.1%}")

        if not validation.is_valid:
            warnings.extend(validation.issues)
        warnings.extend(validation.warnings)

        # If validation fails and we have iterations left, could iterate here
        # For now, just return with warnings

        return SAPGenerationResult(
            success=True,
            sap_text=sap_text,
            sections=sections,
            source_trials=source_trials,
            extracted_methods=methods,
            validation=validation,
            characteristics=characteristics,
            warnings=warnings,
            confidence=validation.confidence
        )

    def _assemble_sap(
        self,
        sections: Dict[str, str],
        characteristics: ProtocolCharacteristics
    ) -> str:
        """Assemble sections into complete SAP document."""
        header = f"""# STATISTICAL ANALYSIS PLAN

**Indication:** {characteristics.indication or 'Not specified'}
**Phase:** {characteristics.phase or 'Not specified'}
**Primary Endpoint:** {characteristics.endpoint_type or 'Not specified'}
**Drug Class:** {', '.join(characteristics.drug_classes) if characteristics.drug_classes else 'Not specified'}

---

"""
        body = "\n\n".join(sections.values())

        footer = """
---

*This SAP was generated using Agentic HybridRAG, learning from similar clinical trials.*
"""

        return header + body + footer


def create_agentic_pipeline() -> AgenticSAPPipeline:
    """Factory function to create the agentic pipeline."""
    return AgenticSAPPipeline()


if __name__ == "__main__":
    print("=" * 70)
    print("AGENTIC HYBRIDRAG SAP PIPELINE TEST")
    print("=" * 70)

    pipeline = create_agentic_pipeline()

    # Test with immunotherapy protocol
    test_protocol = """
    A Phase 3, Randomized, Open-Label Study of Nivolumab versus Docetaxel
    in Patients with Advanced Non-Small Cell Lung Cancer (NSCLC) Who Have
    Progressed on Prior Platinum-Based Chemotherapy

    Primary Endpoint: Overall Survival (OS), defined as time from randomization
    to death from any cause.

    Secondary Endpoints:
    - Progression-Free Survival (PFS)
    - Overall Response Rate (ORR)

    Given the mechanism of action of checkpoint inhibitors, a delayed
    treatment effect may be observed. The study includes provisions for
    crossover to nivolumab upon disease progression.

    An independent Data Monitoring Committee will conduct interim analyses.

    Sample Size: 600 patients randomized 1:1
    """

    result = pipeline.generate(test_protocol)

    print("\n" + "=" * 70)
    print("GENERATION RESULT")
    print("=" * 70)

    print(f"\nSuccess: {result.success}")
    print(f"Confidence: {result.confidence:.1%}")
    print(f"Source trials: {result.source_trials[:5]}")

    print("\nExtracted Methods:")
    if result.extracted_methods:
        print(f"  Primary: {result.extracted_methods.primary_analysis}")
        print(f"  Interim: {result.extracted_methods.interim_analysis}")

    print("\nValidation:")
    if result.validation:
        print(f"  Valid: {result.validation.is_valid}")
        print(f"  Issues: {result.validation.issues}")
        print(f"  Warnings: {result.validation.warnings}")

    print("\n" + "-" * 70)
    print("GENERATED SAP:")
    print("-" * 70)
    print(result.sap_text[:3000])
