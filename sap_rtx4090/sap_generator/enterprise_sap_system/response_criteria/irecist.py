"""
iRECIST Implementation
======================

Immune-modified RECIST for Immunotherapy Trials

Official reference:
Seymour L, et al. iRECIST: guidelines for response criteria for use in trials
testing immunotherapeutics. Lancet Oncol. 2017;18(3):e143-e152.

iRECIST accounts for atypical response patterns seen with immunotherapy:
- Pseudoprogression
- Delayed response
- Dissociated response
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import logging

from .recist_1_1 import (
    RECISTResponse,
    TumorAssessment,
    Lesion,
    LesionType,
    RECISTCriteria
)

logger = logging.getLogger(__name__)


class iRECISTResponse(Enum):
    """iRECIST response categories"""
    iCR = "immune Complete Response"
    iPR = "immune Partial Response"
    iSD = "immune Stable Disease"
    iUPD = "immune Unconfirmed Progressive Disease"
    iCPD = "immune Confirmed Progressive Disease"
    iNE = "immune Not Evaluable"


@dataclass
class ImmuneAssessment(TumorAssessment):
    """
    Tumor assessment with iRECIST classification.

    Extends RECIST 1.1 assessment to track immune-specific responses.
    """
    # iRECIST-specific
    irecist_response: iRECISTResponse = iRECISTResponse.iNE

    # Progression tracking
    is_upd: bool = False              # Unconfirmed PD
    upd_date: str = ""                # Date of first UPD
    is_cpd: bool = False              # Confirmed PD
    cpd_date: str = ""                # Date of CPD confirmation

    # Pseudoprogression tracking
    suspected_pseudoprogression: bool = False
    confirmed_pseudoprogression: bool = False

    def assess_irecist_response(self) -> iRECISTResponse:
        """
        Assess response using iRECIST criteria.

        Key difference from RECIST: First PD becomes iUPD,
        requiring confirmation at next assessment.
        """
        # Use base RECIST assessment
        base_response = self.determine_overall_response()

        # Map RECIST to iRECIST
        if base_response == RECISTResponse.CR:
            return iRECISTResponse.iCR
        elif base_response == RECISTResponse.PR:
            return iRECISTResponse.iPR
        elif base_response == RECISTResponse.SD:
            return iRECISTResponse.iSD
        elif base_response == RECISTResponse.PD:
            # First PD is iUPD (unconfirmed)
            if not self.is_upd and not self.is_cpd:
                return iRECISTResponse.iUPD
            # Confirmed on next assessment
            elif self.is_cpd:
                return iRECISTResponse.iCPD
            else:
                return iRECISTResponse.iUPD
        else:
            return iRECISTResponse.iNE


@dataclass
class iRECISTCriteria(RECISTCriteria):
    """
    iRECIST-specific criteria extending RECIST 1.1.

    Key differences:
    - PD requires confirmation
    - Treatment can continue after iUPD
    - New lesions require confirmation
    """
    # iRECIST-specific
    require_pd_confirmation: bool = True
    allow_treatment_beyond_progression: bool = True

    # Confirmation timing
    pd_confirmation_interval_weeks: int = 4

    # Pseudoprogression handling
    allow_pseudoprogression_assessment: bool = True
    max_time_to_reassess_upd_weeks: int = 12


class iRECISTService:
    """
    Service for iRECIST tumor response assessment in immunotherapy trials.

    Handles atypical response patterns specific to immune checkpoint inhibitors.
    """

    def __init__(self, criteria: iRECISTCriteria = None):
        """
        Initialize iRECIST service.

        Args:
            criteria: Protocol-specific iRECIST criteria
        """
        self.criteria = criteria or iRECISTCriteria()

    def process_assessment_sequence(
        self,
        assessments: List[ImmuneAssessment]
    ) -> List[ImmuneAssessment]:
        """
        Process sequence of assessments to apply iRECIST rules.

        Args:
            assessments: List of tumor assessments over time

        Returns:
            Updated assessments with iRECIST responses
        """
        if not assessments:
            return []

        # Sort by date
        sorted_assessments = sorted(assessments, key=lambda x: x.assessment_date)

        # Track progression state
        upd_assessment = None

        for i, assessment in enumerate(sorted_assessments):
            # Determine base response
            assessment.irecist_response = assessment.assess_irecist_response()

            # Handle iUPD
            if assessment.irecist_response == iRECISTResponse.iUPD:
                if upd_assessment is None:
                    # First iUPD
                    assessment.is_upd = True
                    assessment.upd_date = assessment.assessment_date
                    upd_assessment = assessment
                    logger.info(f"iUPD recorded at {assessment.assessment_date}")

            # Check for iCPD (confirmation of PD)
            elif assessment.irecist_response == iRECISTResponse.iCPD or \
                 (upd_assessment and i > 0):
                # Check if this confirms previous iUPD
                prev_assessment = sorted_assessments[i - 1]

                if prev_assessment.is_upd:
                    # Check if still meets PD criteria
                    if assessment.determine_overall_response() == RECISTResponse.PD:
                        assessment.is_cpd = True
                        assessment.cpd_date = assessment.assessment_date
                        logger.info(f"iCPD confirmed at {assessment.assessment_date}")
                    else:
                        # Pseudoprogression confirmed
                        prev_assessment.confirmed_pseudoprogression = True
                        prev_assessment.suspected_pseudoprogression = True
                        upd_assessment = None  # Reset
                        logger.info(f"Pseudoprogression confirmed at {assessment.assessment_date}")

        return sorted_assessments

    def determine_best_overall_response(
        self,
        assessments: List[ImmuneAssessment]
    ) -> iRECISTResponse:
        """
        Determine best overall response per iRECIST.

        Args:
            assessments: List of immune assessments

        Returns:
            Best overall iRECIST response
        """
        if not assessments:
            return iRECISTResponse.iNE

        # Process assessments
        processed = self.process_assessment_sequence(assessments)

        # Track best response
        has_icpd = False
        has_icr = False
        has_ipr = False
        has_isd = False

        for assessment in processed:
            response = assessment.irecist_response

            if response == iRECISTResponse.iCPD:
                has_icpd = True

            if response == iRECISTResponse.iCR:
                has_icr = True

            if response == iRECISTResponse.iPR:
                has_ipr = True

            if response == iRECISTResponse.iSD:
                has_isd = True

        # Determine best
        if has_icpd:
            return iRECISTResponse.iCPD

        if has_icr:
            return iRECISTResponse.iCR

        if has_ipr:
            return iRECISTResponse.iPR

        if has_isd:
            return iRECISTResponse.iSD

        return iRECISTResponse.iNE

    def calculate_immune_objective_response(
        self,
        best_overall_response: iRECISTResponse
    ) -> bool:
        """
        Determine if subject achieved immune objective response (iCR or iPR).

        Args:
            best_overall_response: Best overall iRECIST response

        Returns:
            True if iCR or iPR, False otherwise
        """
        return best_overall_response in [iRECISTResponse.iCR, iRECISTResponse.iPR]

    def identify_pseudoprogression_cases(
        self,
        assessments: List[ImmuneAssessment]
    ) -> List[str]:
        """
        Identify subjects with confirmed pseudoprogression.

        Args:
            assessments: List of assessments

        Returns:
            List of subject IDs with pseudoprogression
        """
        pseudoprogression_subjects = []

        for assessment in assessments:
            if assessment.confirmed_pseudoprogression:
                if assessment.subject_id not in pseudoprogression_subjects:
                    pseudoprogression_subjects.append(assessment.subject_id)

        return pseudoprogression_subjects

    def generate_irecist_sap_text(self) -> str:
        """
        Generate iRECIST methodology text for SAP.

        Returns:
            Formatted text for SAP
        """
        text = """
## Tumor Response Assessment (iRECIST)

### Response Evaluation Criteria for Immunotherapy

Tumor response will be assessed using immune-modified RECIST (iRECIST) [Seymour et al., 2017], which accounts for atypical response patterns seen with immunotherapy.

**Key Differences from RECIST 1.1:**

1. **Unconfirmed Progressive Disease (iUPD)**: First assessment meeting PD criteria is classified as iUPD
2. **Confirmed Progressive Disease (iCPD)**: PD must be confirmed at next scheduled assessment (≥4 weeks after iUPD)
3. **Treatment Beyond Progression**: Treatment may continue after iUPD pending confirmation
4. **Pseudoprogression**: Initial increase in tumor burden followed by decrease

**iRECIST Response Categories:**

- **iCR (immune Complete Response)**: Disappearance of all lesions
- **iPR (immune Partial Response)**: ≥30% decrease in target lesion sum
- **iSD (immune Stable Disease)**: Neither iPR nor iCPD criteria met
- **iUPD (immune Unconfirmed Progressive Disease)**: Initial assessment meeting PD criteria
- **iCPD (immune Confirmed Progressive Disease)**: Confirmed PD at subsequent assessment

### Handling of Progression

At the first assessment meeting RECIST 1.1 PD criteria:
- Response will be recorded as iUPD
- Treatment may continue at investigator discretion
- Repeat assessment required within 4-12 weeks

At subsequent assessment after iUPD:
- If PD criteria still met → iCPD (confirmed progression, treatment discontinuation)
- If PD criteria not met → Pseudoprogression confirmed (continue treatment)

### Pseudoprogression

Pseudoprogression is defined as initial increase in tumor burden (meeting iUPD criteria) followed by subsequent decrease below iUPD threshold.

Suspected pseudoprogression cases will be:
- Reviewed by independent radiology committee
- Analyzed separately in sensitivity analyses
- Documented with imaging examples

### Immune Objective Response Rate (iORR)

iORR is defined as the proportion of subjects with best overall response of iCR or iPR.

### Immune Duration of Response (iDOR)

iDOR is measured from first date of iCR or iPR until iCPD or death.

### Analysis Considerations

- Primary analysis will use iRECIST
- Sensitivity analysis using RECIST 1.1 will be performed
- Waterfall plots will illustrate response patterns including pseudoprogression
- Time to iCPD will be analyzed separately from traditional PFS

### Reference

Seymour L, Bogaerts J, Perrone A, et al. iRECIST: guidelines for response criteria for use in trials testing immunotherapeutics. Lancet Oncol. 2017;18(3):e143-e152.
"""
        return text.strip()


# Singleton instance
_irecist_service: Optional[iRECISTService] = None


def get_irecist_service(criteria: iRECISTCriteria = None) -> iRECISTService:
    """
    Get iRECIST service instance.

    Args:
        criteria: Optional protocol-specific criteria

    Returns:
        iRECISTService instance
    """
    global _irecist_service

    if _irecist_service is None or criteria is not None:
        _irecist_service = iRECISTService(criteria=criteria)

    return _irecist_service
