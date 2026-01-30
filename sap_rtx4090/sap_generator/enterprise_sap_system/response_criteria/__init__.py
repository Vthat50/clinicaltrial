"""
Response Criteria Module
========================

Tumor response assessment criteria for oncology trials.

Implementations:
- RECIST 1.1: Standard solid tumor response criteria
- iRECIST: Immune-modified RECIST for immunotherapy
"""

from .recist_1_1 import (
    RECISTResponse,
    LesionType,
    LesionLocation,
    Lesion,
    TumorAssessment,
    RECISTCriteria,
    RECISTService,
    get_recist_service
)

from .irecist import (
    iRECISTResponse,
    ImmuneAssessment,
    iRECISTCriteria,
    iRECISTService,
    get_irecist_service
)

__all__ = [
    # RECIST 1.1
    'RECISTResponse',
    'LesionType',
    'LesionLocation',
    'Lesion',
    'TumorAssessment',
    'RECISTCriteria',
    'RECISTService',
    'get_recist_service',

    # iRECIST
    'iRECISTResponse',
    'ImmuneAssessment',
    'iRECISTCriteria',
    'iRECISTService',
    'get_irecist_service',
]
