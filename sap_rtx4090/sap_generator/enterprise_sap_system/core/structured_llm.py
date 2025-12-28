#!/usr/bin/env python3
"""
Structured LLM Client with Pydantic Schema Enforcement
=======================================================

Wraps the tiered LLM client with instructor for schema-constrained generation.
The LLM MUST return outputs conforming to Pydantic schemas.

Usage:
    from .structured_llm import get_structured_client

    # Define your schema
    class SampleSizeSection(BaseModel):
        total_n: Literal[90]  # LLM MUST output exactly 90
        ratio: Literal["1:1:1"]
        narrative: str

    client = get_structured_client()
    result = client.generate(SampleSizeSection, prompt="Generate sample size section")
    # result.total_n is GUARANTEED to be 90
"""

import os
import json
import re
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel
from dataclasses import dataclass


T = TypeVar('T', bound=BaseModel)


# Anti-contamination system message - uses POSITIVE framing to prevent value leakage
# NOTE: Do NOT list specific forbidden values here - listing them causes LLM to use them!
ANTI_CONTAMINATION_PROMPT = """
CRITICAL DATA INTEGRITY RULES:
You MUST extract and use ONLY values that appear in the provided protocol document.

For each value you write, verify it comes from the protocol:
- Drug name: Use ONLY the drug name(s) from THIS protocol
- Study ID: Use ONLY the NCT ID or study identifier from THIS protocol
- Sample size: Use ONLY the enrollment number from THIS protocol
- Randomization ratio: Use ONLY the ratio specified in THIS protocol

If you cannot find a specific value in the protocol, write "[TO BE CONFIRMED]" rather than guessing or using memorized values from other studies.
"""


@dataclass
class StructuredResponse:
    """Response from structured generation"""
    data: Any  # The parsed Pydantic model
    source: str  # "groq", "openai", "claude"
    model: str
    success: bool
    error: Optional[str] = None
    raw_response: Optional[str] = None


class StructuredLLMClient:
    """
    LLM client that enforces Pydantic schema on outputs.

    Uses instructor library when available for strict schema enforcement.
    Falls back to JSON mode + validation otherwise.
    """

    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        self.groq_client = None
        self.openai_client = None
        self.anthropic_client = None

        self.instructor_groq = None
        self.instructor_openai = None

        self._init_clients()

    def _init_clients(self):
        """Initialize LLM clients with instructor wrappers"""
        # Try instructor first (preferred for schema enforcement)
        try:
            import instructor
            HAS_INSTRUCTOR = True
        except ImportError:
            HAS_INSTRUCTOR = False
            print("Note: instructor not installed. Using JSON mode fallback.")
            print("  Install with: pip install instructor")

        # Groq (free tier, good for development)
        if self.groq_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_key)
                if HAS_INSTRUCTOR:
                    self.instructor_groq = instructor.from_groq(self.groq_client)
                print("Groq structured client initialized")
            except ImportError:
                print("Note: groq not installed (pip install groq)")

        # OpenAI (more reliable for complex schemas)
        if self.openai_key:
            try:
                import openai
                self.openai_client = openai.OpenAI(api_key=self.openai_key)
                if HAS_INSTRUCTOR:
                    self.instructor_openai = instructor.from_openai(self.openai_client)
                print("OpenAI structured client initialized")
            except ImportError:
                print("Note: openai not installed (pip install openai)")

    def generate(
        self,
        response_model: Type[T],
        prompt: str,
        system_prompt: str = "",
        max_retries: int = 3,
        preferred_provider: str = None,
        temperature: float = 0.1,
        **kwargs
    ) -> StructuredResponse:
        """
        Generate structured output conforming to a Pydantic schema.

        Args:
            response_model: Pydantic model class (with Literal constraints)
            prompt: User prompt
            system_prompt: Optional system prompt
            max_retries: Number of retries on validation failure
            preferred_provider: "groq", "openai", or None for auto
            temperature: Generation temperature (lower = more deterministic)

        Returns:
            StructuredResponse with parsed model in .data
        """
        providers = self._get_providers(preferred_provider)

        for provider in providers:
            try:
                if provider == "groq" and self.instructor_groq:
                    return self._generate_with_instructor_groq(
                        response_model, prompt, system_prompt, max_retries, temperature
                    )
                elif provider == "openai" and self.instructor_openai:
                    return self._generate_with_instructor_openai(
                        response_model, prompt, system_prompt, max_retries, temperature
                    )
                elif provider == "groq" and self.groq_client:
                    return self._generate_with_json_mode(
                        response_model, prompt, system_prompt, max_retries, "groq"
                    )
                elif provider == "openai" and self.openai_client:
                    return self._generate_with_json_mode(
                        response_model, prompt, system_prompt, max_retries, "openai"
                    )
            except Exception as e:
                print(f"  {provider} structured generation failed: {str(e)[:100]}")
                continue

        return StructuredResponse(
            data=None,
            source="none",
            model="",
            success=False,
            error="All providers failed"
        )

    def _get_providers(self, preferred: str = None) -> List[str]:
        """Get ordered list of available providers"""
        available = []
        if self.groq_client:
            available.append("groq")
        if self.openai_client:
            available.append("openai")

        if preferred and preferred in available:
            available.remove(preferred)
            available.insert(0, preferred)

        return available

    def _generate_with_instructor_groq(
        self,
        response_model: Type[T],
        prompt: str,
        system_prompt: str,
        max_retries: int,
        temperature: float
    ) -> StructuredResponse:
        """Generate using instructor-wrapped Groq"""
        # Always include anti-contamination rules
        full_system = ANTI_CONTAMINATION_PROMPT
        if system_prompt:
            full_system = f"{ANTI_CONTAMINATION_PROMPT}\n\n{system_prompt}"

        messages = [{"role": "system", "content": full_system}]
        messages.append({"role": "user", "content": prompt})

        result = self.instructor_groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            response_model=response_model,
            messages=messages,
            max_retries=max_retries,
            temperature=temperature,
        )

        return StructuredResponse(
            data=result,
            source="groq",
            model="llama-3.3-70b-versatile",
            success=True
        )

    def _generate_with_instructor_openai(
        self,
        response_model: Type[T],
        prompt: str,
        system_prompt: str,
        max_retries: int,
        temperature: float
    ) -> StructuredResponse:
        """Generate using instructor-wrapped OpenAI"""
        # Always include anti-contamination rules
        full_system = ANTI_CONTAMINATION_PROMPT
        if system_prompt:
            full_system = f"{ANTI_CONTAMINATION_PROMPT}\n\n{system_prompt}"

        messages = [{"role": "system", "content": full_system}]
        messages.append({"role": "user", "content": prompt})

        result = self.instructor_openai.chat.completions.create(
            model="gpt-4o-mini",
            response_model=response_model,
            messages=messages,
            max_retries=max_retries,
            temperature=temperature,
        )

        return StructuredResponse(
            data=result,
            source="openai",
            model="gpt-4o-mini",
            success=True
        )

    def _generate_with_json_mode(
        self,
        response_model: Type[T],
        prompt: str,
        system_prompt: str,
        max_retries: int,
        provider: str
    ) -> StructuredResponse:
        """Fallback: Use JSON mode and parse/validate manually"""
        # Get JSON schema from Pydantic model
        schema = response_model.model_json_schema()
        schema_str = json.dumps(schema, indent=2)

        # Modify prompt to include schema
        enhanced_prompt = f"""{prompt}

You MUST respond with valid JSON matching this exact schema:
{schema_str}

Respond with ONLY the JSON object, no other text."""

        # Always include anti-contamination rules
        full_system = ANTI_CONTAMINATION_PROMPT
        if system_prompt:
            full_system = f"{ANTI_CONTAMINATION_PROMPT}\n\n{system_prompt}"

        messages = [{"role": "system", "content": full_system}]
        messages.append({"role": "user", "content": enhanced_prompt})

        for attempt in range(max_retries):
            try:
                if provider == "groq":
                    response = self.groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=0.1
                    )
                    raw = response.choices[0].message.content
                else:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=0.1
                    )
                    raw = response.choices[0].message.content

                # Parse JSON
                data = json.loads(raw)

                # Validate against Pydantic model
                validated = response_model.model_validate(data)

                return StructuredResponse(
                    data=validated,
                    source=provider,
                    model="llama-3.3-70b-versatile" if provider == "groq" else "gpt-4o-mini",
                    success=True,
                    raw_response=raw
                )

            except Exception as e:
                if attempt < max_retries - 1:
                    # Add error to messages for self-correction
                    messages.append({
                        "role": "assistant",
                        "content": raw if 'raw' in dir() else ""
                    })
                    messages.append({
                        "role": "user",
                        "content": f"Error: {str(e)}. Please fix and try again with valid JSON."
                    })
                    continue
                else:
                    return StructuredResponse(
                        data=None,
                        source=provider,
                        model="",
                        success=False,
                        error=str(e),
                        raw_response=raw if 'raw' in dir() else None
                    )

        return StructuredResponse(
            data=None,
            source="none",
            model="",
            success=False,
            error="Max retries exceeded"
        )


# =============================================================================
# SECTION-SPECIFIC GENERATION
# =============================================================================

class SAPSectionGenerator:
    """
    Generate SAP sections with schema constraints.

    Each section uses a dynamically created schema with Literal types
    that enforce the exact values from protocol facts.
    """

    def __init__(self, structured_client: StructuredLLMClient = None):
        self.client = structured_client or get_structured_client()

    def generate_sample_size_section(
        self,
        schema_class: Type[BaseModel],
        facts_summary: Dict[str, Any]
    ) -> StructuredResponse:
        """
        Generate Sample Size section with schema enforcement.

        Args:
            schema_class: Dynamically created schema with Literal constraints
            facts_summary: Dictionary of extracted protocol facts

        Returns:
            StructuredResponse with validated SampleSizeSection
        """
        system_prompt = """You are an expert biostatistician writing Statistical Analysis Plans (SAPs) for clinical trials.
Your output must be regulatory-grade, suitable for FDA submission.
You must use ONLY the values specified in the schema - do not invent or modify any numbers."""

        prompt = f"""Generate Section 6: Sample Size Calculation for a Statistical Analysis Plan.

PROTOCOL FACTS (these are the ONLY values you may use):
- Total sample size: {facts_summary.get('total_n', 'N/A')}
- Randomization ratio: {facts_summary.get('ratio', 'N/A')}
- Number of arms: {facts_summary.get('num_arms', 'N/A')}
- Patients per arm: {facts_summary.get('per_arm_n', 'N/A')}
- Power: {facts_summary.get('power', 'N/A')}
- Alpha: {facts_summary.get('alpha', 'N/A')} ({facts_summary.get('alpha_sidedness', 'N/A')})

CRITICAL INSTRUCTIONS:
1. The schema enforces the exact values above - you CANNOT output different numbers
2. Write professional prose for the narrative fields
3. DO NOT include numbers in narrative fields - they will be inserted from schema fields
4. Focus on methodology and rationale, not restating numbers

Generate the section following the provided schema."""

        return self.client.generate(
            response_model=schema_class,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1
        )

    def generate_study_design_section(
        self,
        schema_class: Type[BaseModel],
        facts_summary: Dict[str, Any],
        arm_details: List[str] = None
    ) -> StructuredResponse:
        """Generate Study Design section with schema enforcement"""
        system_prompt = """You are an expert biostatistician writing Statistical Analysis Plans.
Your output must be regulatory-grade. Use ONLY the values specified in the schema."""

        arm_text = "\n".join(f"  - {arm}" for arm in (arm_details or []))

        prompt = f"""Generate Section 3: Study Design for a Statistical Analysis Plan.

PROTOCOL FACTS (these are the ONLY values you may use):
- Investigational product: {facts_summary.get('drug_name', 'N/A')}
- Number of arms: {facts_summary.get('num_arms', 'N/A')}
- Randomization ratio: {facts_summary.get('ratio', 'N/A')}
- Route of administration: {facts_summary.get('route', 'N/A')}
- Treatment arms:
{arm_text}

CRITICAL: The schema enforces exact values. Write professional narrative without restating numbers.

Generate the section following the provided schema."""

        return self.client.generate(
            response_model=schema_class,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1
        )


# =============================================================================
# SINGLETON AND CONVENIENCE
# =============================================================================

_structured_client: Optional[StructuredLLMClient] = None


def get_structured_client() -> StructuredLLMClient:
    """Get or create the singleton structured LLM client"""
    global _structured_client
    if _structured_client is None:
        _structured_client = StructuredLLMClient()
    return _structured_client


def generate_structured(
    response_model: Type[T],
    prompt: str,
    system_prompt: str = "",
    **kwargs
) -> StructuredResponse:
    """Convenience function for quick structured generation"""
    return get_structured_client().generate(
        response_model=response_model,
        prompt=prompt,
        system_prompt=system_prompt,
        **kwargs
    )
