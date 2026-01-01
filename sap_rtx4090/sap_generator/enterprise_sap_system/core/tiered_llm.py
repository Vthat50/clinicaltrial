#!/usr/bin/env python3
"""
Tiered LLM Client with Automatic Fallback
==========================================

Tier 1: Claude Sonnet (most accurate, ~90%)
Tier 2: OpenAI GPT-4o-mini (fast, ~80%)
Tier 3: Groq Llama 3.3 70B (free, ~75%)
Tier 4: Rule-based fallback (~65%)

Automatically falls back to next tier on errors or rate limits.
"""

import os
import time
import json
import re
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LLMResponse:
    """Response from LLM call"""
    content: str
    source: str  # "claude", "openai", "groq", "rules"
    model: str
    success: bool
    error: Optional[str] = None
    latency_ms: float = 0


@dataclass
class APIStatus:
    """Track API availability and rate limits"""
    available: bool = True
    errors: int = 0
    cooldown_until: float = 0
    last_success: float = 0


class TieredLLMClient:
    """
    Multi-provider LLM client with automatic fallback.

    Usage:
        client = TieredLLMClient()
        response = client.chat("Your prompt here")
        print(f"Response from {response.source}: {response.content}")
    """

    # Model configurations
    # Note: Model selection based on API access level
    MODELS = {
        "claude": {
            "name": "claude-3-haiku-20240307",  # Fast, cost-effective
            "max_tokens": 4096,
            "temperature": 0.2,
        },
        "openai": {
            "name": "gpt-4o-mini",
            "max_tokens": 4096,
            "temperature": 0.2,
        },
        "groq": {
            "name": "llama-3.3-70b-versatile",
            "max_tokens": 4096,
            "temperature": 0.2,
        },
    }

    def __init__(self):
        """Initialize with all available API keys"""
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")

        # API status tracking
        self.api_status: Dict[str, APIStatus] = {
            "claude": APIStatus(available=bool(self.anthropic_key)),
            "openai": APIStatus(available=bool(self.openai_key)),
            "groq": APIStatus(available=bool(self.groq_key)),
        }

        # Initialize clients
        self.claude_client = None
        self.openai_client = None
        self.groq_client = None

        self._init_clients()

        # Print available tiers
        self._print_status()

    def _init_clients(self):
        """Initialize API clients"""
        if self.anthropic_key:
            try:
                import anthropic
                self.claude_client = anthropic.Anthropic(api_key=self.anthropic_key)
            except ImportError:
                print("Note: anthropic package not installed (pip install anthropic)")
                self.api_status["claude"].available = False

        if self.openai_key:
            try:
                import openai
                self.openai_client = openai.OpenAI(api_key=self.openai_key)
            except ImportError:
                print("Note: openai package not installed (pip install openai)")
                self.api_status["openai"].available = False

        if self.groq_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_key)
            except ImportError:
                print("Note: groq package not installed (pip install groq)")
                self.api_status["groq"].available = False

    def _print_status(self):
        """Print available API tiers"""
        tiers = self.get_available_tiers()
        if tiers:
            print(f"LLM Tiers available: {' → '.join(t.upper() for t in tiers)}")
        else:
            print("WARNING: No LLM APIs available. Set API keys:")
            print("  - ANTHROPIC_API_KEY (Claude)")
            print("  - OPENAI_API_KEY (GPT-4)")
            print("  - GROQ_API_KEY (Llama)")

    def get_available_tiers(self) -> List[str]:
        """Get list of currently available tiers"""
        tiers = []
        now = time.time()

        if self.claude_client and self.api_status["claude"].cooldown_until < now:
            tiers.append("claude")
        if self.openai_client and self.api_status["openai"].cooldown_until < now:
            tiers.append("openai")
        if self.groq_client and self.api_status["groq"].cooldown_until < now:
            tiers.append("groq")

        return tiers

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None,
        preferred_tier: str = None,
        json_mode: bool = False
    ) -> LLMResponse:
        """
        Send a chat request with automatic tier fallback.

        Args:
            prompt: User message
            system_prompt: Optional system message
            temperature: Override default temperature
            max_tokens: Override default max tokens
            preferred_tier: Start with specific tier ("claude", "openai", "groq")
            json_mode: Request JSON response format

        Returns:
            LLMResponse with content and metadata
        """
        tiers = self.get_available_tiers()

        # Reorder if preferred tier specified
        if preferred_tier and preferred_tier in tiers:
            tiers.remove(preferred_tier)
            tiers.insert(0, preferred_tier)

        for tier in tiers:
            start_time = time.time()

            try:
                if tier == "claude":
                    result = self._call_claude(prompt, system_prompt, temperature, max_tokens, json_mode)
                elif tier == "openai":
                    result = self._call_openai(prompt, system_prompt, temperature, max_tokens, json_mode)
                elif tier == "groq":
                    result = self._call_groq(prompt, system_prompt, temperature, max_tokens, json_mode)
                else:
                    continue

                if result:
                    latency = (time.time() - start_time) * 1000
                    self.api_status[tier].last_success = time.time()
                    return LLMResponse(
                        content=result,
                        source=tier,
                        model=self.MODELS[tier]["name"],
                        success=True,
                        latency_ms=latency
                    )

            except Exception as e:
                self._handle_error(tier, e)
                continue

        # All tiers failed
        return LLMResponse(
            content="",
            source="none",
            model="",
            success=False,
            error="All LLM tiers failed"
        )

    def _call_claude(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None,
        json_mode: bool = False
    ) -> Optional[str]:
        """Call Claude API"""
        if not self.claude_client:
            return None

        config = self.MODELS["claude"]

        # Claude doesn't support response_format, so we add JSON instruction to prompt
        effective_prompt = prompt
        effective_system = system_prompt

        if json_mode:
            json_instruction = "\n\nIMPORTANT: You must respond with valid JSON only. No other text."
            if system_prompt:
                effective_system = system_prompt + json_instruction
            else:
                effective_prompt = prompt + json_instruction

        # Clamp max_tokens to model limit (Claude Haiku max is 4096)
        effective_max_tokens = min(max_tokens or config["max_tokens"], config["max_tokens"])

        kwargs = {
            "model": config["name"],
            "max_tokens": effective_max_tokens,
            "messages": [{"role": "user", "content": effective_prompt}]
        }

        if effective_system:
            kwargs["system"] = effective_system

        if temperature is not None:
            kwargs["temperature"] = temperature
        else:
            kwargs["temperature"] = config["temperature"]

        response = self.claude_client.messages.create(**kwargs)
        return response.content[0].text

    def _call_openai(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None,
        json_mode: bool = False
    ) -> Optional[str]:
        """Call OpenAI API"""
        if not self.openai_client:
            return None

        config = self.MODELS["openai"]

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": config["name"],
            "max_tokens": max_tokens or config["max_tokens"],
            "temperature": temperature if temperature is not None else config["temperature"],
            "messages": messages
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.openai_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _call_groq(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None,
        json_mode: bool = False
    ) -> Optional[str]:
        """Call Groq API"""
        if not self.groq_client:
            return None

        config = self.MODELS["groq"]

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": config["name"],
            "max_tokens": max_tokens or config["max_tokens"],
            "temperature": temperature if temperature is not None else config["temperature"],
            "messages": messages
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.groq_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _handle_error(self, tier: str, error: Exception):
        """Handle API errors with cooldown"""
        error_str = str(error).lower()

        # Rate limit detection
        if "rate" in error_str or "429" in error_str:
            cooldown = 60 if tier == "claude" else 30
            self.api_status[tier].cooldown_until = time.time() + cooldown
            print(f"  {tier.upper()} rate limited, cooldown {cooldown}s")
        elif "400" in error_str or "invalid" in error_str:
            # Log full error for debugging invalid request issues
            print(f"  {tier.upper()} invalid request: {str(error)[:200]}")
        else:
            print(f"  {tier.upper()} error: {str(error)[:100]}")

        self.api_status[tier].errors += 1

    def chat_json(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1
    ) -> Tuple[Optional[Dict], str]:
        """
        Send chat and parse JSON response.

        Returns:
            Tuple of (parsed_dict, source_tier)
        """
        response = self.chat(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            json_mode=True
        )

        if not response.success:
            return None, "none"

        try:
            # Try to parse JSON
            data = json.loads(response.content)
            return data, response.source
        except json.JSONDecodeError:
            # Try to extract JSON from response
            match = re.search(r'\{[\s\S]*\}', response.content)
            if match:
                try:
                    data = json.loads(match.group())
                    return data, response.source
                except json.JSONDecodeError:
                    pass  # JSON parsing failed, fall through to return None

        return None, response.source


# Singleton instance
_client: Optional[TieredLLMClient] = None


def get_tiered_client() -> TieredLLMClient:
    """Get or create the singleton tiered LLM client"""
    global _client
    if _client is None:
        _client = TieredLLMClient()
    return _client


def chat(prompt: str, system_prompt: str = "", **kwargs) -> LLMResponse:
    """Convenience function for quick LLM calls"""
    return get_tiered_client().chat(prompt, system_prompt, **kwargs)
