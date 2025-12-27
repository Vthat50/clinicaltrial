#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Specifications Module
=========================================================
Production-level generators for:
- TLF Shell Specifications
- ADaM Derivation Specifications
- Programming Specifications

These are real, usable specifications - not placeholders.
"""

from .derivation_specs import DerivationSpecGenerator, create_derivation_generator
from .tlf_shells import TLFShellGenerator, create_tlf_generator
from .programming_specs import ProgrammingSpecGenerator, create_programming_generator

__all__ = [
    "DerivationSpecGenerator",
    "TLFShellGenerator",
    "ProgrammingSpecGenerator",
    "create_derivation_generator",
    "create_tlf_generator",
    "create_programming_generator"
]
