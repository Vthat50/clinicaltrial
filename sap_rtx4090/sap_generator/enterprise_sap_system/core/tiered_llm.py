#!/usr/bin/env python3
"""
Tiered LLM Client with Automatic Fallback
==========================================

Tier 1: Claude Opus 4.5 (most accurate, best extraction)
Tier 2: OpenAI GPT-4o-mini (fast, ~80%)
Tier 3: Groq Llama 3.3 70B (free, ~75%)

Automatically falls back to next tier on errors or rate limits.

Production Features:
- Thread-safe singleton initialization
- Structured logging
- Circuit breaker pattern for API failures
- Null-safe response handling
"""

import os
import time
import json
import re
import threading
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Import logging
try:
    from .logging_config import get_logger, LLMError
except ImportError:
    # Fallback if logging not available
    import logging
    def get_logger(name):
        return logging.getLogger(name)
    class LLMError(Exception):
        def __init__(self, message, provider=None, model=None):
            self.provider = provider
            self.model = model
            super().__init__(message)

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM call"""
    content: str
    source: str  # "claude", "openai", "groq", "none"
    model: str
    success: bool
    error: Optional[str] = None
    latency_ms: float = 0


@dataclass
class APIStatus:
    """Track API availability and rate limits with circuit breaker"""
    available: bool = True
    consecutive_errors: int = 0
    cooldown_until: float = 0
    last_success: float = 0
    total_errors: int = 0
    total_successes: int = 0

    # Circuit breaker thresholds
    ERROR_THRESHOLD: int = 3  # Consecutive errors before circuit opens
    COOLDOWN_BASE: int = 30   # Base cooldown in seconds
    COOLDOWN_MAX: int = 300   # Max cooldown (5 minutes)

    def record_success(self):
        """Record a successful call - reset circuit breaker."""
        self.consecutive_errors = 0
        self.last_success = time.time()
        self.total_successes += 1
        self.cooldown_until = 0

    def record_error(self, is_rate_limit: bool = False) -> int:
        """
        Record an error and return cooldown duration.

        Uses exponential backoff for consecutive errors.
        """
        self.consecutive_errors += 1
        self.total_errors += 1

        # Calculate cooldown with exponential backoff
        if is_rate_limit:
            cooldown = min(
                self.COOLDOWN_BASE * (2 ** (self.consecutive_errors - 1)),
                self.COOLDOWN_MAX
            )
        else:
            cooldown = self.COOLDOWN_BASE if self.consecutive_errors >= self.ERROR_THRESHOLD else 0

        if cooldown > 0:
            self.cooldown_until = time.time() + cooldown

        return cooldown

    def is_available(self) -> bool:
        """Check if API is available (circuit closed or half-open)."""
        if not self.available:
            return False
        return time.time() >= self.cooldown_until


class TieredLLMClient:
    """
    Multi-provider LLM client with automatic fallback.

    Thread-safe singleton with circuit breaker pattern.

    Usage:
        client = TieredLLMClient()
        response = client.chat("Your prompt here")
        print(f"Response from {response.source}: {response.content}")
    """

    # Model configurations
    # CRITICAL: Use Opus 4.5 for most accurate extraction
    MODELS = {
        "claude": {
            "name": "claude-opus-4-5-20251101",  # Upgraded to Opus 4.5 for best extraction accuracy
            "max_tokens": 16384,  # Claude supports up to 16K output - needed for full SAP generation
            "temperature": 0.1,  # Lower temp for more precise extraction
        },
        "openai": {
            "name": "gpt-4o-mini",
            "max_tokens": 16384,  # GPT-4o supports high output
            "temperature": 0.2,
        },
        "groq": {
            "name": "llama-3.3-70b-versatile",
            "max_tokens": 8192,  # Groq has lower limits
            "temperature": 0.2,
        },
    }

    def __init__(self):
        """Initialize with all available API keys."""
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")

        # DEBUG: Print key status at startup
        print(f"[LLM INIT] ANTHROPIC_API_KEY: {'SET (' + self.anthropic_key[:15] + '...)' if self.anthropic_key else 'NOT SET'}")
        print(f"[LLM INIT] OPENAI_API_KEY: {'SET' if self.openai_key else 'NOT SET'}")
        print(f"[LLM INIT] GROQ_API_KEY: {'SET' if self.groq_key else 'NOT SET'}")

        # API status tracking with circuit breaker
        self.api_status: Dict[str, APIStatus] = {
            "claude": APIStatus(available=bool(self.anthropic_key)),
            "openai": APIStatus(available=bool(self.openai_key)),
            "groq": APIStatus(available=bool(self.groq_key)),
        }

        # Initialize clients (lazy - None until first use)
        self._claude_client = None
        self._openai_client = None
        self._groq_client = None
        self._clients_initialized = False

        self._log_status()

    def _init_clients(self):
        """Initialize API clients (lazy initialization)."""
        if self._clients_initialized:
            return

        if self.anthropic_key:
            try:
                import anthropic
                self._claude_client = anthropic.Anthropic(api_key=self.anthropic_key)
                logger.info("Claude client initialized", provider="anthropic")
            except ImportError:
                logger.warning("anthropic package not installed", install_cmd="pip install anthropic")
                self.api_status["claude"].available = False
            except Exception as e:
                logger.error("Failed to initialize Claude client", exc_info=True, error=str(e))
                self.api_status["claude"].available = False

        if self.openai_key:
            try:
                import openai
                self._openai_client = openai.OpenAI(api_key=self.openai_key)
                logger.info("OpenAI client initialized", provider="openai")
            except ImportError:
                logger.warning("openai package not installed", install_cmd="pip install openai")
                self.api_status["openai"].available = False
            except Exception as e:
                logger.error("Failed to initialize OpenAI client", exc_info=True, error=str(e))
                self.api_status["openai"].available = False

        if self.groq_key:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=self.groq_key)
                logger.info("Groq client initialized", provider="groq")
            except ImportError:
                logger.warning("groq package not installed", install_cmd="pip install groq")
                self.api_status["groq"].available = False
            except Exception as e:
                logger.error("Failed to initialize Groq client", exc_info=True, error=str(e))
                self.api_status["groq"].available = False

        self._clients_initialized = True

    @property
    def claude_client(self):
        """Lazy-load Claude client."""
        if not self._clients_initialized:
            self._init_clients()
        return self._claude_client

    @property
    def openai_client(self):
        """Lazy-load OpenAI client."""
        if not self._clients_initialized:
            self._init_clients()
        return self._openai_client

    @property
    def groq_client(self):
        """Lazy-load Groq client."""
        if not self._clients_initialized:
            self._init_clients()
        return self._groq_client

    def _log_status(self):
        """Log available API tiers."""
        available = []
        unavailable = []

        for tier, status in self.api_status.items():
            if status.available:
                available.append(tier)
            else:
                unavailable.append(tier)

        if available:
            logger.info(
                "LLM tiers configured",
                available=available,
                unavailable=unavailable
            )
        else:
            logger.warning(
                "No LLM APIs available",
                required_env_vars=["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"]
            )

    def get_available_tiers(self) -> List[str]:
        """Get list of currently available tiers (circuit breaker aware)."""
        tiers = []

        # Claude first (best accuracy for clinical protocol extraction)
        if self.claude_client and self.api_status["claude"].is_available():
            tiers.append("claude")
        if self.openai_client and self.api_status["openai"].is_available():
            tiers.append("openai")
        if self.groq_client and self.api_status["groq"].is_available():
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
        errors_by_tier: Dict[str, str] = {}

        # Reorder if preferred tier specified
        if preferred_tier and preferred_tier in tiers:
            tiers.remove(preferred_tier)
            tiers.insert(0, preferred_tier)

        if not tiers:
            logger.error("No LLM tiers available for request")
            return LLMResponse(
                content="",
                source="none",
                model="",
                success=False,
                error="No LLM APIs available. Check API keys and circuit breaker status."
            )

        for tier in tiers:
            start_time = time.time()

            try:
                logger.debug(f"Attempting {tier}", tier=tier, json_mode=json_mode)

                if tier == "claude":
                    result = self._call_claude(prompt, system_prompt, temperature, max_tokens, json_mode)
                elif tier == "openai":
                    result = self._call_openai(prompt, system_prompt, temperature, max_tokens, json_mode)
                elif tier == "groq":
                    result = self._call_groq(prompt, system_prompt, temperature, max_tokens, json_mode)
                else:
                    continue

                if result is not None:
                    latency = (time.time() - start_time) * 1000
                    self.api_status[tier].record_success()

                    logger.debug(
                        f"LLM call succeeded",
                        tier=tier,
                        latency_ms=round(latency, 2),
                        response_length=len(result)
                    )

                    return LLMResponse(
                        content=result,
                        source=tier,
                        model=self.MODELS[tier]["name"],
                        success=True,
                        latency_ms=latency
                    )
                else:
                    errors_by_tier[tier] = "Empty response"
                    logger.warning(f"Empty response from {tier}", tier=tier)

            except Exception as e:
                error_msg = self._handle_error(tier, e)
                errors_by_tier[tier] = error_msg
                continue

        # All tiers failed
        error_summary = "; ".join(f"{t}: {e}" for t, e in errors_by_tier.items())
        logger.error("All LLM tiers failed", errors=errors_by_tier)

        return LLMResponse(
            content="",
            source="none",
            model="",
            success=False,
            error=f"All LLM tiers failed. {error_summary}"
        )

    def _call_claude(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None,
        json_mode: bool = False
    ) -> Optional[str]:
        """Call Claude API with null-safe response handling."""
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

        # Clamp max_tokens to model limit
        effective_max_tokens = min(max_tokens or config["max_tokens"], config["max_tokens"])

        kwargs = {
            "model": config["name"],
            "max_tokens": effective_max_tokens,
            "messages": [{"role": "user", "content": effective_prompt}]
        }

        if effective_system:
            kwargs["system"] = effective_system

        kwargs["temperature"] = temperature if temperature is not None else config["temperature"]

        response = self.claude_client.messages.create(**kwargs)

        # Null-safe response extraction
        if response is None:
            logger.warning("Claude returned None response")
            return None

        if not hasattr(response, 'content') or not response.content:
            logger.warning("Claude response has no content", response_type=type(response).__name__)
            return None

        if len(response.content) == 0:
            logger.warning("Claude response content is empty")
            return None

        first_block = response.content[0]
        if not hasattr(first_block, 'text'):
            logger.warning("Claude response block has no text", block_type=type(first_block).__name__)
            return None

        return first_block.text

    def _call_openai(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None,
        json_mode: bool = False
    ) -> Optional[str]:
        """Call OpenAI API with null-safe response handling."""
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

        # Null-safe response extraction
        if response is None:
            logger.warning("OpenAI returned None response")
            return None

        if not hasattr(response, 'choices') or not response.choices:
            logger.warning("OpenAI response has no choices", response_type=type(response).__name__)
            return None

        if len(response.choices) == 0:
            logger.warning("OpenAI response choices is empty")
            return None

        first_choice = response.choices[0]
        if not hasattr(first_choice, 'message') or first_choice.message is None:
            logger.warning("OpenAI choice has no message")
            return None

        if not hasattr(first_choice.message, 'content'):
            logger.warning("OpenAI message has no content")
            return None

        return first_choice.message.content

    def _call_groq(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None,
        json_mode: bool = False
    ) -> Optional[str]:
        """Call Groq API with null-safe response handling."""
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

        # Null-safe response extraction
        if response is None:
            logger.warning("Groq returned None response")
            return None

        if not hasattr(response, 'choices') or not response.choices:
            logger.warning("Groq response has no choices", response_type=type(response).__name__)
            return None

        if len(response.choices) == 0:
            logger.warning("Groq response choices is empty")
            return None

        first_choice = response.choices[0]
        if not hasattr(first_choice, 'message') or first_choice.message is None:
            logger.warning("Groq choice has no message")
            return None

        if not hasattr(first_choice.message, 'content'):
            logger.warning("Groq message has no content")
            return None

        return first_choice.message.content

    def _handle_error(self, tier: str, error: Exception) -> str:
        """Handle API errors with circuit breaker and structured logging."""
        error_str = str(error).lower()
        error_type = type(error).__name__

        # DEBUG: Print full error
        print(f"[DEBUG] {tier.upper()} ERROR: {type(error).__name__}: {error}")

        # Detect error type - be more specific
        is_rate_limit = "rate" in error_str or "429" in error_str
        is_auth_error = "401" in error_str or "403" in error_str or "authentication" in error_str or "api_key" in error_str
        is_invalid_request = "400" in error_str or "invalid" in error_str
        is_credit_error = "credit" in error_str or "balance" in error_str or "billing" in error_str

        # Record error and get cooldown
        cooldown = self.api_status[tier].record_error(is_rate_limit=is_rate_limit)

        # Create error message
        if is_rate_limit:
            error_msg = f"Rate limited (cooldown: {cooldown}s)"
            logger.warning(
                f"{tier.upper()} rate limited",
                tier=tier,
                cooldown_seconds=cooldown,
                consecutive_errors=self.api_status[tier].consecutive_errors
            )
        elif is_auth_error:
            error_msg = "Authentication failed"
            logger.error(
                f"{tier.upper()} authentication error",
                tier=tier,
                error_type=error_type,
                hint="Check API key is valid"
            )
        elif is_invalid_request:
            error_msg = f"Invalid request: {str(error)[:100]}"
            logger.error(
                f"{tier.upper()} invalid request",
                tier=tier,
                error_type=error_type,
                error_detail=str(error)[:200]
            )
        else:
            error_msg = f"{error_type}: {str(error)[:100]}"
            logger.error(
                f"{tier.upper()} error",
                tier=tier,
                error_type=error_type,
                error_detail=str(error)[:200],
                exc_info=True
            )

        return error_msg

    def chat_with_vision(
        self,
        prompt: str,
        image_base64: str,
        media_type: str = "image/png",
        max_tokens: int = 1500
    ) -> Optional[str]:
        """
        Send a vision request with an image to Claude.

        Vision is only supported by Claude, so this method uses Claude directly.
        Falls back to text extraction hint if Claude is unavailable.

        Args:
            prompt: Text prompt describing what to analyze
            image_base64: Base64-encoded image data
            media_type: Image MIME type (image/png, image/jpeg, etc.)
            max_tokens: Maximum tokens for response

        Returns:
            Response text from vision analysis, or None if failed
        """
        # Ensure clients are initialized
        if not self._clients_initialized:
            self._init_clients()

        if not self.claude_client:
            logger.warning("Vision request failed - Claude client not available")
            return None

        if not self.api_status["claude"].is_available():
            logger.warning("Vision request failed - Claude API in cooldown")
            return None

        try:
            start_time = time.time()

            # Build multimodal message with image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]

            # Use Claude Sonnet for vision (faster, still accurate for doc analysis)
            response = self.claude_client.messages.create(
                model="gpt-4o-mini",
                max_tokens=max_tokens,
                messages=messages
            )

            latency = (time.time() - start_time) * 1000
            self.api_status["claude"].record_success()

            if response and response.content and len(response.content) > 0:
                result = response.content[0].text
                logger.debug(
                    "Vision call succeeded",
                    latency_ms=round(latency, 2),
                    response_length=len(result)
                )
                return result

            logger.warning("Vision call returned empty response")
            return None

        except Exception as e:
            error_msg = self._handle_error("claude", e)
            logger.error(f"Vision API error: {error_msg}")
            return None

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
            logger.warning("JSON chat failed", error=response.error)
            return None, "none"

        try:
            data = json.loads(response.content)
            return data, response.source
        except json.JSONDecodeError as e:
            logger.debug(
                "Initial JSON parse failed, attempting extraction",
                error=str(e),
                content_preview=response.content[:100] if response.content else ""
            )

            # Try to extract JSON from response
            match = re.search(r'\{[\s\S]*\}', response.content)
            if match:
                try:
                    data = json.loads(match.group())
                    logger.debug("JSON extracted from response")
                    return data, response.source
                except json.JSONDecodeError as e2:
                    logger.warning(
                        "JSON extraction failed",
                        initial_error=str(e),
                        extraction_error=str(e2)
                    )

        return None, response.source

    def get_status(self) -> Dict[str, Any]:
        """Get current status of all API tiers."""
        return {
            tier: {
                "available": status.is_available(),
                "configured": status.available,
                "consecutive_errors": status.consecutive_errors,
                "total_errors": status.total_errors,
                "total_successes": status.total_successes,
                "cooldown_remaining": max(0, status.cooldown_until - time.time())
            }
            for tier, status in self.api_status.items()
        }


# Thread-safe singleton
_client: Optional[TieredLLMClient] = None
_client_lock = threading.Lock()


def get_tiered_client() -> TieredLLMClient:
    """Get or create the singleton tiered LLM client (thread-safe)."""
    global _client

    if _client is not None:
        return _client

    with _client_lock:
        # Double-check locking pattern
        if _client is None:
            _client = TieredLLMClient()

    return _client


def chat(prompt: str, system_prompt: str = "", **kwargs) -> LLMResponse:
    """Convenience function for quick LLM calls."""
    return get_tiered_client().chat(prompt, system_prompt, **kwargs)


def reset_client():
    """Reset the singleton client (for testing)."""
    global _client
    with _client_lock:
        _client = None
