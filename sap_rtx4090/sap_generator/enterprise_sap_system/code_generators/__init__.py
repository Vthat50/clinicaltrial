#!/usr/bin/env python3
"""
Enterprise SAP System - Executable Code Generators
====================================================

Generates production-ready SAS code from protocol facts.
This module bridges SAP specifications to executable programs.

Usage:
    from enterprise_sap_system.code_generators import CodeGenerationOrchestrator

    orchestrator = CodeGenerationOrchestrator()
    result = orchestrator.generate_all(protocol_facts)

    # Access generated programs
    print(result.adam_programs['adsl.sas'])
    print(result.tlf_programs['t_14_1_1_demog.sas'])
"""

from .base import SASCodeGenerator, CodeGenerationResult
from .orchestrator import CodeGenerationOrchestrator, GenerationPackage

# ADaM generators
from .adam import (
    ADSLGenerator,
    ADAEGenerator,
    ADTTEGenerator,
    ADEFFGenerator,
)

# TLF generators
from .tlf import (
    DemographicsTableGenerator,
    AESummaryTableGenerator,
    PrimaryEfficacyTableGenerator,
)

__all__ = [
    # Core classes
    'SASCodeGenerator',
    'CodeGenerationResult',
    'CodeGenerationOrchestrator',
    'GenerationPackage',
    # ADaM generators
    'ADSLGenerator',
    'ADAEGenerator',
    'ADTTEGenerator',
    'ADEFFGenerator',
    # TLF generators
    'DemographicsTableGenerator',
    'AESummaryTableGenerator',
    'PrimaryEfficacyTableGenerator',
]
