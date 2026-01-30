"""
Regulatory Guidance Module
===========================

Provides access to FDA, ICH, and other regulatory guidance documents
for clinical trial design and statistical analysis.

US Focus: Comprehensive FDA guidance library for Phase 2/3 oncology trials
"""

from .guidance_model import (
    GuidanceDocument,
    GuidanceSection,
    GuidanceAuthority,
    GuidanceType,
    BindingLevel,
    RegulatoryChecklist
)

__all__ = [
    'GuidanceDocument',
    'GuidanceSection',
    'GuidanceAuthority',
    'GuidanceType',
    'BindingLevel',
    'RegulatoryChecklist',
]
