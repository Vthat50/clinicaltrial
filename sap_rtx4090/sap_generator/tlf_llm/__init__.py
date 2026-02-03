"""LLM-Driven TLF Shell Generation System.

Generates Tables, Listings, and Figures shell specifications for any clinical
trial protocol by combining domain knowledge (INSTRUCTIONS.md), example matching
against 50 reference SAPs, and LLM reasoning.
"""

from .generator import generate_tlf_shells_llm

__all__ = ["generate_tlf_shells_llm"]
