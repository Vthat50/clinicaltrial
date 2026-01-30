#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Base Agent Module
======================================================
TIER 3: Multi-Agent SAP Generation Workflow

Defines the base agent class and common functionality for all agents.
Uses TieredLLMClient for automatic fallback through Claude → OpenAI → Groq.
"""

import os
import json
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Use relative imports for consistent module resolution
try:
    from ..core.config import get_config
    from ..core.schemas import ParsedProtocol, Estimand, GeneratedSAP, QualityReport
    from ..core.tiered_llm import TieredLLMClient, get_tiered_client, LLMResponse
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from core.config import get_config
    from core.schemas import ParsedProtocol, Estimand, GeneratedSAP, QualityReport
    from core.tiered_llm import TieredLLMClient, get_tiered_client, LLMResponse


@dataclass
class AgentMessage:
    """Message exchanged between agents"""
    sender: str
    receiver: str
    message_type: str  # "request", "response", "error"
    content: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentState:
    """State of an agent during execution"""
    agent_name: str
    status: str = "idle"  # "idle", "running", "completed", "error"
    current_task: str = ""
    progress: float = 0.0
    messages: List[AgentMessage] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class BaseAgent(ABC):
    """
    Base class for all SAP generation agents.
    Provides common functionality for LLM interaction, state management, and messaging.
    """

    def __init__(
        self,
        name: str,
        description: str,
        llm_client: Any = None,
        model: str = None,
        preferred_tier: str = None
    ):
        self.name = name
        self.description = description
        self.config = get_config()
        self.preferred_tier = preferred_tier  # "claude", "openai", "groq"

        # Use TieredLLMClient for automatic fallback
        self.tiered_client: TieredLLMClient = None
        self.llm_client = llm_client  # Legacy support
        self.model = model or self.config.model.primary_model

        # Initialize tiered LLM client
        self._init_llm_client()

        # Agent state
        self.state = AgentState(agent_name=name)

    def _init_llm_client(self):
        """Initialize TieredLLMClient for automatic fallback"""
        try:
            self.tiered_client = get_tiered_client()
        except Exception as e:
            print(f"WARNING: Failed to initialize tiered LLM for agent {self.name}: {e}")

    def call_llm(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None,
        max_tokens: int = None,
        response_format: str = "text"
    ) -> str:
        """
        Call the LLM with automatic tier fallback (Claude → OpenAI → Groq).

        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Override default temperature
            max_tokens: Override default max tokens
            response_format: "text" or "json"

        Returns:
            LLM response text
        """
        # Use TieredLLMClient for automatic fallback
        if self.tiered_client is not None:
            try:
                response: LLMResponse = self.tiered_client.chat(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature or self.config.model.temperature,
                    max_tokens=max_tokens or self.config.model.max_tokens,
                    preferred_tier=self.preferred_tier,
                    json_mode=(response_format == "json")
                )

                if response.success:
                    # Log which tier was used
                    self.state.results.setdefault("llm_tiers_used", []).append(response.source)
                    return response.content
                else:
                    self.state.errors.append(f"All LLM tiers failed: {response.error}")
                    raise RuntimeError(response.error)

            except Exception as e:
                self.state.errors.append(f"Tiered LLM call failed: {str(e)}")
                raise

        # Fallback to legacy single-client mode
        if self.llm_client is None:
            raise RuntimeError(f"No LLM client available for agent {self.name}")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature or self.config.model.temperature,
                "max_tokens": max_tokens or self.config.model.max_tokens
            }

            if response_format == "json":
                kwargs["response_format"] = {"type": "json_object"}

            response = self.llm_client.chat.completions.create(**kwargs)
            return response.choices[0].message.content

        except Exception as e:
            self.state.errors.append(f"LLM call failed: {str(e)}")
            raise

    def call_llm_json(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = None
    ) -> Dict:
        """Call LLM and parse JSON response"""
        response = self.call_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            response_format="json"
        )

        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError(f"Failed to parse JSON response: {e}")

    def update_state(
        self,
        status: str = None,
        current_task: str = None,
        progress: float = None,
        result_key: str = None,
        result_value: Any = None
    ):
        """Update agent state"""
        if status:
            self.state.status = status
            if status == "running" and not self.state.start_time:
                self.state.start_time = datetime.now().isoformat()
            elif status in ["completed", "error"]:
                self.state.end_time = datetime.now().isoformat()

        if current_task:
            self.state.current_task = current_task

        if progress is not None:
            self.state.progress = progress

        if result_key and result_value:
            self.state.results[result_key] = result_value

    def send_message(
        self,
        receiver: str,
        message_type: str,
        content: Dict[str, Any]
    ) -> AgentMessage:
        """Create and log a message to another agent"""
        message = AgentMessage(
            sender=self.name,
            receiver=receiver,
            message_type=message_type,
            content=content
        )
        self.state.messages.append(message)
        return message

    @abstractmethod
    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Execute the agent's main task.
        Must be implemented by subclasses.
        """
        pass

    def validate_input(self, input_data: Any) -> Tuple[bool, List[str]]:
        """
        Validate input data for the agent.
        Override in subclasses for specific validation.
        """
        return True, []

    def get_state(self) -> Dict[str, Any]:
        """Get current agent state as dictionary"""
        return {
            "name": self.state.agent_name,
            "status": self.state.status,
            "current_task": self.state.current_task,
            "progress": self.state.progress,
            "results": self.state.results,
            "errors": self.state.errors,
            "start_time": self.state.start_time,
            "end_time": self.state.end_time
        }


class AgentRegistry:
    """Registry for managing multiple agents"""

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent):
        """Register an agent"""
        self.agents[agent.name] = agent

    def get(self, name: str) -> Optional[BaseAgent]:
        """Get agent by name"""
        return self.agents.get(name)

    def list_agents(self) -> List[str]:
        """List all registered agents"""
        return list(self.agents.keys())

    def get_all_states(self) -> Dict[str, Dict]:
        """Get states of all agents"""
        return {name: agent.get_state() for name, agent in self.agents.items()}
