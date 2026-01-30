"""
Safety Module
=============

Comprehensive safety data management for oncology trials.

Components:
- CTCAE v5.0/v6.0: Adverse event grading
- MedDRA: Medical terminology coding
- Safety analysis specifications
"""

from .ctcae_model import (
    CTCAETerm,
    CTCAEGrade,
    CTCAECategory,
    CTCAEVersion,
    CTCAEAdverseEvent,
    CTCAESafetyProfile,
    CTCAEGradeDefinition
)

from .ctcae_service import CTCAEService, get_ctcae_service

from .meddra_integration import (
    MedDRAService,
    MedDRAPreferredTerm,
    MedDRASystemOrganClass,
    MedDRALevel,
    get_meddra_service
)

__all__ = [
    # CTCAE
    'CTCAETerm',
    'CTCAEGrade',
    'CTCAECategory',
    'CTCAEVersion',
    'CTCAEAdverseEvent',
    'CTCAESafetyProfile',
    'CTCAEGradeDefinition',
    'CTCAEService',
    'get_ctcae_service',

    # MedDRA
    'MedDRAService',
    'MedDRAPreferredTerm',
    'MedDRASystemOrganClass',
    'MedDRALevel',
    'get_meddra_service',
]
