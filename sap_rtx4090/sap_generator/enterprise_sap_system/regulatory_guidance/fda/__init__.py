"""
FDA Regulatory Guidance Module
================================

Provides access to FDA guidance documents for oncology clinical trials.

US Focus: Comprehensive coverage of FDA requirements for Phase 2/3 trials.
"""

from .guidance_service import FDAGuidanceService, get_fda_guidance_service

__all__ = [
    'FDAGuidanceService',
    'get_fda_guidance_service',
]
