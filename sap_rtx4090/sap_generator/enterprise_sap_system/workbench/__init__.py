"""
SAP Workbench Module
====================

Section-by-section SAP generation with:
- Protocol understanding view
- Section-level generation
- Traceability/provenance
- Change management

This is SEPARATE from the one-shot generation.
"""

from .workbench_core import (
    SAPWorkbench,
    StudyWorkspace,
    SAPSection,
    SectionStatus,
    ProtocolMetadata,
)

__all__ = [
    "SAPWorkbench",
    "StudyWorkspace",
    "SAPSection",
    "SectionStatus",
    "ProtocolMetadata",
]
