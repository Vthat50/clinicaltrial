#!/usr/bin/env python3
"""
Enterprise SAP Generation System - Specifications Module
=========================================================
Production-level generators for:
- SDTM Domain Specifications (NEW - from Protocol/SAP)
- TLF Shell Specifications
- ADaM Derivation Specifications
- Programming Specifications

These are real, usable specifications - not placeholders.
"""

from .derivation_specs import DerivationSpecGenerator, create_derivation_generator
from .tlf_shells import TLFShellGenerator, create_tlf_generator
from .programming_specs import ProgrammingSpecGenerator, create_programming_generator
from .sdtm_specs import SDTMSpecGenerator, create_sdtm_spec_generator

__all__ = [
    # SDTM Specifications
    "SDTMSpecGenerator",
    "create_sdtm_spec_generator",
    # ADaM Derivation Specifications
    "DerivationSpecGenerator",
    "create_derivation_generator",
    # TLF Specifications
    "TLFShellGenerator",
    "create_tlf_generator",
    # Programming Specifications
    "ProgrammingSpecGenerator",
    "create_programming_generator",
]
