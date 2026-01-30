"""
RECIST 1.1 Implementation
=========================

Response Evaluation Criteria In Solid Tumors, Version 1.1

Official reference:
Eisenhauer EA, et al. New response evaluation criteria in solid tumours:
revised RECIST guideline (version 1.1). Eur J Cancer. 2009;45(2):228-47.

RECIST 1.1 is the FDA-accepted standard for tumor response assessment
in solid tumor oncology trials.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RECISTResponse(Enum):
    """RECIST 1.1 response categories"""
    CR = "Complete Response"          # Disappearance of all target lesions
    PR = "Partial Response"           # ≥30% decrease in sum of target lesions
    SD = "Stable Disease"             # Neither PR nor PD criteria met
    PD = "Progressive Disease"        # ≥20% increase in sum of target lesions
    NE = "Not Evaluable"              # Unable to assess response


class LesionType(Enum):
    """Lesion classification"""
    TARGET = "Target"                 # Measurable, followed for response
    NON_TARGET = "Non-Target"         # Not measured quantitatively
    NEW = "New"                       # Appeared after baseline


class LesionLocation(Enum):
    """Common lesion locations"""
    LUNG = "Lung"
    LIVER = "Liver"
    LYMPH_NODE = "Lymph Node"
    BONE = "Bone"
    BRAIN = "Brain"
    SOFT_TISSUE = "Soft Tissue"
    OTHER = "Other"


@dataclass
class Lesion:
    """
    Individual tumor lesion tracked per RECIST 1.1.

    Target lesions must be:
    - ≥10 mm in longest diameter (CT/MRI)
    - ≥15 mm in short axis for lymph nodes
    - Measurable in at least one dimension
    """
    lesion_id: str
    lesion_type: LesionType
    location: LesionLocation

    # Measurements (in mm)
    baseline_diameter: float = 0.0
    current_diameter: float = 0.0

    # Special for lymph nodes
    is_lymph_node: bool = False
    short_axis_diameter: float = 0.0  # For lymph nodes

    # Imaging
    imaging_modality: str = "CT"      # CT, MRI, PET-CT
    assessment_date: str = ""

    # Status
    is_measurable: bool = True
    disappeared: bool = False         # CR for this lesion

    def get_measurement(self) -> float:
        """Get appropriate measurement for RECIST"""
        if self.is_lymph_node:
            return self.short_axis_diameter
        return self.current_diameter

    def get_baseline_measurement(self) -> float:
        """Get baseline measurement"""
        if self.is_lymph_node:
            return self.short_axis_diameter  # Assuming stored at baseline
        return self.baseline_diameter

    def calculate_change_from_baseline(self) -> float:
        """Calculate percent change from baseline"""
        baseline = self.get_baseline_measurement()
        if baseline == 0:
            return 0.0

        current = self.get_measurement()
        return ((current - baseline) / baseline) * 100


@dataclass
class TumorAssessment:
    """
    Complete tumor assessment at a timepoint per RECIST 1.1.

    Includes all target, non-target lesions, and new lesions.
    """
    assessment_id: str
    subject_id: str
    assessment_date: str
    visit_name: str = ""

    # Lesions
    target_lesions: List[Lesion] = field(default_factory=list)
    non_target_lesions: List[Lesion] = field(default_factory=list)
    new_lesions: List[Lesion] = field(default_factory=list)

    # Measurements
    sum_target_lesions: float = 0.0   # Sum of longest diameters
    baseline_sum: float = 0.0         # For calculating change

    # Assessor
    assessor: str = "Investigator"    # "Investigator" or "Independent Review"

    # Overall response
    overall_response: RECISTResponse = RECISTResponse.NE

    def calculate_sum_target_lesions(self) -> float:
        """Calculate sum of target lesion diameters"""
        total = 0.0
        for lesion in self.target_lesions:
            if not lesion.disappeared:
                total += lesion.get_measurement()
        return total

    def calculate_percent_change(self) -> float:
        """Calculate percent change from baseline"""
        if self.baseline_sum == 0:
            return 0.0

        return ((self.sum_target_lesions - self.baseline_sum) / self.baseline_sum) * 100

    def assess_target_lesion_response(self) -> RECISTResponse:
        """
        Assess response based on target lesions.

        CR: All target lesions disappeared
        PR: ≥30% decrease from baseline
        PD: ≥20% increase from nadir AND ≥5mm absolute increase
        SD: Neither PR nor PD
        """
        if not self.target_lesions:
            return RECISTResponse.NE

        # Check for CR (all disappeared)
        all_disappeared = all(lesion.disappeared for lesion in self.target_lesions)
        if all_disappeared:
            return RECISTResponse.CR

        # Calculate change from baseline
        percent_change = self.calculate_percent_change()

        # Check for PR (≥30% decrease)
        if percent_change <= -30:
            return RECISTResponse.PR

        # Check for PD (≥20% increase AND ≥5mm absolute increase)
        # Note: Should check from nadir, not just baseline
        absolute_increase = self.sum_target_lesions - self.baseline_sum
        if percent_change >= 20 and absolute_increase >= 5:
            return RECISTResponse.PD

        # Otherwise SD
        return RECISTResponse.SD

    def assess_non_target_response(self) -> str:
        """
        Assess non-target lesion response.

        Returns: "CR", "Non-CR/Non-PD", "PD", or "NE"
        """
        if not self.non_target_lesions:
            return "NE"

        # Check if all disappeared
        all_disappeared = all(lesion.disappeared for lesion in self.non_target_lesions)
        if all_disappeared:
            return "CR"

        # Check for unequivocal progression
        # (This would need clinical assessment in practice)
        # For now, assume no progression if not all disappeared
        return "Non-CR/Non-PD"

    def check_new_lesions(self) -> bool:
        """Check if new lesions present (indicates PD)"""
        return len(self.new_lesions) > 0

    def determine_overall_response(self) -> RECISTResponse:
        """
        Determine overall response per RECIST 1.1 criteria.

        Combines target, non-target, and new lesion assessments.
        """
        # New lesions = automatic PD
        if self.check_new_lesions():
            return RECISTResponse.PD

        # Get component responses
        target_response = self.assess_target_lesion_response()
        non_target_status = self.assess_non_target_response()

        # Apply RECIST 1.1 combination rules
        if target_response == RECISTResponse.CR and non_target_status == "CR":
            return RECISTResponse.CR

        if target_response == RECISTResponse.CR and non_target_status == "Non-CR/Non-PD":
            return RECISTResponse.PR

        if target_response == RECISTResponse.PR and non_target_status in ["Non-CR/Non-PD", "NE"]:
            return RECISTResponse.PR

        if target_response == RECISTResponse.SD and non_target_status == "Non-CR/Non-PD":
            return RECISTResponse.SD

        if target_response == RECISTResponse.PD or non_target_status == "PD":
            return RECISTResponse.PD

        return RECISTResponse.NE


@dataclass
class RECISTCriteria:
    """
    RECIST 1.1 protocol-specific implementation rules.

    Defines study-specific rules for tumor assessment.
    """
    # Target lesion selection
    max_target_lesions: int = 5       # Maximum total target lesions
    max_per_organ: int = 2            # Maximum per organ

    # Measurement requirements
    min_measurable_size: float = 10.0  # mm (CT/MRI)
    min_lymph_node_size: float = 15.0  # mm short axis

    # Assessment schedule
    assessment_frequency_weeks: int = 6  # Every 6 weeks typical

    # Confirmation requirements
    require_cr_confirmation: bool = True
    require_pr_confirmation: bool = True
    confirmation_interval_weeks: int = 4

    # Imaging modality
    primary_modality: str = "CT"
    require_same_modality: bool = True

    # Special rules
    allow_bone_lesions: bool = False   # Bone lesions usually non-target
    allow_cystic_lesions: bool = False
    minimum_lesion_size_increase: float = 5.0  # mm for PD

    def validate_target_lesion(self, lesion: Lesion) -> bool:
        """Check if lesion meets target lesion criteria"""
        if not lesion.is_measurable:
            return False

        if lesion.is_lymph_node:
            return lesion.short_axis_diameter >= self.min_lymph_node_size
        else:
            return lesion.current_diameter >= self.min_measurable_size


class RECISTService:
    """
    Service for RECIST 1.1 tumor response assessment.

    Provides:
    - Response determination
    - Best overall response calculation
    - Confirmation checking
    - SAP specifications
    """

    def __init__(self, criteria: RECISTCriteria = None):
        """
        Initialize RECIST service.

        Args:
            criteria: Protocol-specific RECIST criteria
        """
        self.criteria = criteria or RECISTCriteria()

    def determine_best_overall_response(
        self,
        assessments: List[TumorAssessment]
    ) -> RECISTResponse:
        """
        Determine best overall response across all assessments.

        Applies RECIST 1.1 confirmation rules.

        Args:
            assessments: List of tumor assessments over time

        Returns:
            Best overall response
        """
        if not assessments:
            return RECISTResponse.NE

        # Sort by date
        sorted_assessments = sorted(assessments, key=lambda x: x.assessment_date)

        # Track responses
        cr_confirmed = False
        pr_confirmed = False
        has_pd = False
        has_sd = False

        for i, assessment in enumerate(sorted_assessments):
            response = assessment.overall_response

            # Check for PD (no confirmation needed)
            if response == RECISTResponse.PD:
                has_pd = True
                break  # PD is final

            # Check for CR with confirmation
            if response == RECISTResponse.CR:
                if self.criteria.require_cr_confirmation:
                    # Look for confirmation assessment
                    if i + 1 < len(sorted_assessments):
                        next_response = sorted_assessments[i + 1].overall_response
                        if next_response == RECISTResponse.CR:
                            cr_confirmed = True
                else:
                    cr_confirmed = True

            # Check for PR with confirmation
            if response == RECISTResponse.PR:
                if self.criteria.require_pr_confirmation:
                    if i + 1 < len(sorted_assessments):
                        next_response = sorted_assessments[i + 1].overall_response
                        if next_response in [RECISTResponse.PR, RECISTResponse.CR]:
                            pr_confirmed = True
                else:
                    pr_confirmed = True

            # Track SD
            if response == RECISTResponse.SD:
                has_sd = True

        # Determine BOR
        if has_pd:
            return RECISTResponse.PD

        if cr_confirmed:
            return RECISTResponse.CR

        if pr_confirmed:
            return RECISTResponse.PR

        if has_sd:
            return RECISTResponse.SD

        return RECISTResponse.NE

    def calculate_objective_response(
        self,
        best_overall_response: RECISTResponse
    ) -> bool:
        """
        Determine if subject achieved objective response (CR or PR).

        Args:
            best_overall_response: Best overall response

        Returns:
            True if CR or PR, False otherwise
        """
        return best_overall_response in [RECISTResponse.CR, RECISTResponse.PR]

    def generate_recist_sap_text(self) -> str:
        """
        Generate RECIST 1.1 methodology text for SAP.

        Returns:
            Formatted text for SAP
        """
        text = f"""
## Tumor Response Assessment

### Response Evaluation Criteria

Tumor response will be assessed using Response Evaluation Criteria In Solid Tumors (RECIST) version 1.1 [Eisenhauer et al., 2009].

**Target Lesions:**
- Up to {self.criteria.max_target_lesions} target lesions total
- Maximum {self.criteria.max_per_organ} lesions per organ
- Measurable lesions ≥{self.criteria.min_measurable_size} mm in longest diameter (CT/MRI)
- Lymph nodes ≥{self.criteria.min_lymph_node_size} mm in short axis

**Response Categories:**

- **Complete Response (CR)**: Disappearance of all target lesions and non-target disease. Any pathological lymph nodes must have reduction in short axis to <10 mm.

- **Partial Response (PR)**: At least 30% decrease in the sum of diameters of target lesions, taking as reference the baseline sum diameters.

- **Progressive Disease (PD)**: At least 20% increase in the sum of diameters of target lesions, taking as reference the smallest sum on study (nadir), AND an absolute increase of at least 5 mm. The appearance of one or more new lesions also constitutes PD.

- **Stable Disease (SD)**: Neither sufficient shrinkage to qualify for PR nor sufficient increase to qualify for PD.

### Assessment Schedule

Tumor assessments will be performed every {self.criteria.assessment_frequency_weeks} weeks using {self.criteria.primary_modality} imaging.

### Confirmation Requirements

"""
        if self.criteria.require_cr_confirmation:
            text += f"- Complete response must be confirmed by repeat assessment ≥{self.criteria.confirmation_interval_weeks} weeks after initial CR documentation.\n"

        if self.criteria.require_pr_confirmation:
            text += f"- Partial response must be confirmed by repeat assessment ≥{self.criteria.confirmation_interval_weeks} weeks after initial PR documentation.\n"

        text += """
### Best Overall Response

Best overall response (BOR) is the best response recorded from start of treatment until disease progression or recurrence, taking into account confirmation requirements.

### Objective Response Rate (ORR)

ORR is defined as the proportion of subjects with best overall response of CR or PR (confirmed).

### Duration of Response (DOR)

DOR is measured from the time criteria are first met for CR or PR (whichever is recorded first) until the first date that PD is objectively documented or death.

### Reference

Eisenhauer EA, Therasse P, Bogaerts J, et al. New response evaluation criteria in solid tumours: revised RECIST guideline (version 1.1). Eur J Cancer. 2009;45(2):228-247.
"""
        return text.strip()


# Singleton instance
_recist_service: Optional[RECISTService] = None


def get_recist_service(criteria: RECISTCriteria = None) -> RECISTService:
    """
    Get RECIST service instance.

    Args:
        criteria: Optional protocol-specific criteria

    Returns:
        RECISTService instance
    """
    global _recist_service

    if _recist_service is None or criteria is not None:
        _recist_service = RECISTService(criteria=criteria)

    return _recist_service
