"""
QA Module for SAP Generation
============================
Issue detection, consistency checking, and warning system.

Month 3-4 Implementation Target: 85-90% quality
"""

from .issue_detector import (
    IssueDetector,
    Issue,
    IssueSeverity,
    create_issue_detector
)

__all__ = [
    'IssueDetector',
    'Issue',
    'IssueSeverity',
    'create_issue_detector',
]
