"""
Immune-Related Response Criteria (irRC)
========================================

Response assessment criteria for immunotherapy trials.

Published: Wolchok JD, et al. Clin Cancer Res. 2009;15(23):7412-7420.

Key features:
- Accounts for pseudoprogression
- Incorporates new lesions into total tumor burden
- Requires confirmation of progression
- Different from iRECIST (which is RECIST-based)

Response categories:
- irCR: Complete response
- irPR: Partial response
- irSD: Stable disease
- irPD: Progressive disease

Differences from WHO/RECIST:
- New lesions do not automatically mean PD
- Total tumor burden includes new measurable lesions
- Confirmation required for PD
- Emphasis on best overall response

Applications:
- Early immunotherapy trials (before iRECIST)
- Some checkpoint inhibitor studies
- Melanoma, renal cell carcinoma trials
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class irRC_Response(Enum):
    """Immune-related response categories"""
    irCR = "irCR"  # Complete Response
    irPR = "irPR"  # Partial Response
    irSD = "irSD"  # Stable Disease
    irPD = "irPD"  # Progressive Disease
    NE = "Not Evaluable"


@dataclass
class irRC_Assessment:
    """
    Single tumor assessment using irRC.

    Differs from RECIST by including new lesions in total burden.
    """
    assessment_date: str
    assessment_number: int

    # Bidimensional measurements (WHO-based, not RECIST unidimensional)
    baseline_burden: float = 0.0       # Sum of products of perpendicular diameters
    current_burden: float = 0.0        # Including new measurable lesions

    # New lesions
    new_lesions_present: bool = False
    new_lesions_measurable: bool = False
    new_lesion_burden: float = 0.0     # Contribution from new lesions

    # Calculated
    total_burden: float = 0.0          # Current + new lesion burden
    percent_change: float = 0.0        # From baseline

    # Response determination
    response: irRC_Response = irRC_Response.NE
    confirmed: bool = False
    confirmation_date: Optional[str] = None

    def calculate_burden(self):
        """Calculate total tumor burden including new lesions"""
        if self.new_lesions_measurable:
            self.total_burden = self.current_burden + self.new_lesion_burden
        else:
            self.total_burden = self.current_burden

        if self.baseline_burden > 0:
            self.percent_change = ((self.total_burden - self.baseline_burden) /
                                  self.baseline_burden * 100)

    def determine_response(self) -> irRC_Response:
        """
        Determine immune-related response.

        Key difference: New lesions incorporated into burden calculation.
        """
        # irCR: Complete disappearance
        if self.total_burden == 0:
            return irRC_Response.irCR

        # irPR: ≥50% decrease from baseline
        if self.percent_change <= -50:
            return irRC_Response.irPR

        # irPD: ≥25% increase from nadir (minimum)
        # Note: Should track nadir across all assessments
        if self.percent_change >= 25:
            return irRC_Response.irPD

        # irSD: Neither PR nor PD
        return irRC_Response.irSD


@dataclass
class irRC_Criteria:
    """
    Complete irRC criteria implementation.

    Manages sequence of assessments and response determination.
    """
    study_id: str
    baseline_assessment: irRC_Assessment
    assessments: List[irRC_Assessment] = field(default_factory=list)

    # Response tracking
    best_response: irRC_Response = irRC_Response.NE
    nadir_burden: float = float('inf')  # Minimum burden observed

    def add_assessment(self, assessment: irRC_Assessment):
        """Add new assessment and update responses"""
        assessment.calculate_burden()
        assessment.response = self._determine_response_with_nadir(assessment)

        self.assessments.append(assessment)

        # Update nadir
        if assessment.total_burden < self.nadir_burden:
            self.nadir_burden = assessment.total_burden

        # Update best response
        self._update_best_response()

    def _determine_response_with_nadir(self, assessment: irRC_Assessment) -> irRC_Response:
        """Determine response considering nadir"""
        # irCR
        if assessment.total_burden == 0:
            return irRC_Response.irCR

        # irPR: ≥50% decrease from baseline
        baseline_change = ((assessment.total_burden - self.baseline_assessment.baseline_burden) /
                          self.baseline_assessment.baseline_burden * 100)
        if baseline_change <= -50:
            return irRC_Response.irPR

        # irPD: ≥25% increase from nadir (and minimum 10 mm² increase)
        if self.nadir_burden < float('inf'):
            nadir_change = ((assessment.total_burden - self.nadir_burden) /
                           self.nadir_burden * 100)
            absolute_increase = assessment.total_burden - self.nadir_burden

            if nadir_change >= 25 and absolute_increase >= 10:
                return irRC_Response.irPD

        # irSD
        return irRC_Response.irSD

    def _update_best_response(self):
        """Update best overall response"""
        # Response hierarchy (best to worst)
        hierarchy = [irRC_Response.irCR, irRC_Response.irPR,
                    irRC_Response.irSD, irRC_Response.irPD]

        for response in hierarchy:
            if any(a.response == response and a.confirmed for a in self.assessments):
                self.best_response = response
                return

        # If no confirmed responses, use best unconfirmed
        for response in hierarchy:
            if any(a.response == response for a in self.assessments):
                self.best_response = response
                return

    def check_confirmation(self) -> List[irRC_Assessment]:
        """
        Identify assessments requiring confirmation.

        irRC requires confirmation for irPD (minimum 4 weeks).
        """
        needing_confirmation = []

        for i, assessment in enumerate(self.assessments):
            if assessment.response == irRC_Response.irPD and not assessment.confirmed:
                # Check if next assessment confirms
                if i + 1 < len(self.assessments):
                    next_assessment = self.assessments[i + 1]

                    # Check time interval (≥4 weeks)
                    # Simplified: would need actual date comparison

                    if next_assessment.response == irRC_Response.irPD:
                        assessment.confirmed = True
                        assessment.confirmation_date = next_assessment.assessment_date
                    else:
                        # Not confirmed - was pseudoprogression
                        needing_confirmation.append(assessment)

        return needing_confirmation


class irRC_Service:
    """
    Service for immune-related response criteria.

    Provides methodology and documentation for irRC-based trials.
    """

    def __init__(self):
        """Initialize irRC service"""
        pass

    def generate_irrc_methodology(self) -> str:
        """
        Generate irRC methodology for SAP.

        Returns:
            Formatted SAP text
        """
        text = """
## Response Assessment: Immune-Related Response Criteria (irRC)

### Background

Immune-related Response Criteria (irRC) were developed specifically for immunotherapy
trials to account for unique response patterns seen with immune checkpoint inhibitors.

**Key Differences from RECIST:**

1. **New Lesions:** Incorporated into total tumor burden (not automatic PD)
2. **Measurement:** Bidimensional (WHO-based product of diameters)
3. **Confirmation:** Required for progressive disease
4. **Pseudoprogression:** Accounted for by confirmation requirement

**Reference:**
Wolchok JD, Hoos A, O'Day S, et al. Guidelines for the evaluation of immune
therapy activity in solid tumors: immune-related response criteria. Clin Cancer Res.
2009;15(23):7412-7420.

### Tumor Measurements

**Target Lesions:**
- Up to 5 lesions per organ
- Up to 10 lesions total
- Measured bidimensionally (longest diameter × perpendicular diameter)
- Sum of products (SPD) = total tumor burden

**New Lesions:**
- Measured bidimensionally if measurable (≥5 × 5 mm)
- Contribution added to SPD
- Do NOT automatically signify progression

**Non-Target Lesions:**
- Assessed qualitatively (present/absent/unequivocal progression)

### Response Definitions

**irCR (Immune-Related Complete Response):**
- Complete disappearance of all lesions
- No new lesions
- Confirmation ≥4 weeks from date first documented

**irPR (Immune-Related Partial Response):**
- ≥50% decrease in tumor burden (SPD) compared to baseline
- Includes measurable new lesions in SPD calculation
- Confirmation ≥4 weeks from date first documented

**irSD (Immune-Related Stable Disease):**
- Does not meet criteria for irCR, irPR, or irPD
- Includes patients with new lesions that do not meet irPD criteria

**irPD (Immune-Related Progressive Disease):**
- ≥25% increase in tumor burden compared to nadir (minimum SPD)
- **AND** minimum 10 mm² absolute increase
- Includes measurable new lesions in burden calculation
- **Confirmation Required:** Assess again ≥4 weeks later to confirm PD

### Confirmation Requirement

**Progressive Disease Must Be Confirmed:**

Initial PD → Repeat assessment ≥4 weeks → Confirmed if still PD

**Rationale:**
- Pseudoprogression: Initial increase followed by tumor shrinkage
- Seen in 5-10% of immunotherapy patients
- Can occur due to immune cell infiltration or inflammation
- Early discontinuation would deny patients potential benefit

**Clinical Management:**
- Clinically stable patients with initial PD can continue treatment
- Reassess in ≥4 weeks to confirm true progression
- If confirmed PD: discontinue treatment
- If not confirmed: reclassify response based on subsequent assessments

### Best Overall Response (BOR)

**Determination:**

The BOR is the best response recorded from start of treatment until disease
progression/recurrence (taking as reference for PD the nadir).

**Hierarchy:**
1. irCR (confirmed)
2. irPR (confirmed)
3. irSD
4. irPD (confirmed)

**Time Point Analysis:**
Responses assessed at scheduled intervals (e.g., every 8-12 weeks).

### Statistical Analysis

**Primary Endpoint: irORR (Immune-Related Objective Response Rate)**

irORR = (irCR + irPR) / Evaluable Population

**Analysis:**
- Exact 95% confidence interval (Clopper-Pearson)
- Comparison between arms using CMH test (if randomized)

**Secondary Endpoints:**
- Disease Control Rate (irDCR): irCR + irPR + irSD
- Duration of Response (irDOR): Time from first irCR/irPR to irPD
- Time to Response (irTTR): Time from first dose to first irCR/irPR
- Progression-Free Survival using irRC (irPFS)

### Handling of Pseudoprogression

**Definition:**
Initial increase in tumor burden (≥25%) followed by response or stabilization.

**Frequency:** ~5-10% in melanoma with anti-CTLA-4, varies by tumor type

**Clinical Scenarios:**

1. **Confirmed Progression:**
   - Initial PD → Reassessment shows continued/further progression
   - True PD: discontinue treatment

2. **Unconfirmed Progression (Pseudoprogression):**
   - Initial PD → Reassessment shows tumor shrinkage or stabilization
   - Reclassify based on subsequent assessment
   - Patient may achieve irPR or irSD

3. **New Lesions Resolving:**
   - New lesions appear → Subsequently disappear or shrink
   - Do not automatically signify PD
   - Track as part of total burden

**Reporting:**
Document and report cases of pseudoprogression as exploratory endpoint.

### Comparison with RECIST 1.1 and iRECIST

| Feature | RECIST 1.1 | iRECIST | irRC |
|---------|-----------|---------|------|
| Measurement | Unidimensional | Unidimensional | Bidimensional |
| New Lesions | Immediate PD | iUPD → Confirm | Added to burden |
| Confirmation | For CR/PR | For PD | For all responses |
| Basis | WHO criteria | Modified RECIST | WHO criteria |
| Primary Use | Standard trials | Immunotherapy | Immunotherapy |

**Note:** iRECIST is newer and more widely adopted than irRC for current
immunotherapy trials. irRC may be specified for consistency with earlier studies.

### Assessment Schedule

Tumor assessments performed:
- Baseline (within 4 weeks of first dose)
- Every 8-12 weeks during treatment
- At treatment discontinuation
- During follow-up (if clinically indicated)

**Imaging Modality:** CT (preferred) or MRI
**Same modality must be used throughout study**

### Clinical Considerations

**When to Use irRC:**
- Immunotherapy trials (checkpoint inhibitors, cancer vaccines)
- Studies designed before iRECIST adoption
- Melanoma, RCC, NSCLC with immunotherapy

**Advantages:**
- Captures delayed responses characteristic of immunotherapy
- Prevents premature discontinuation due to pseudoprogression
- Well-established in immunotherapy literature

**Limitations:**
- Bidimensional measurements more variable than unidimensional
- Requires clinically stable patients to continue through initial PD
- Less commonly used now (replaced by iRECIST)

### Regulatory Considerations

**FDA Acceptance:**
- irRC accepted for immunotherapy trials
- Must be pre-specified in protocol
- Recommend parallel RECIST 1.1 assessment for comparison

**Documentation:**
- Blinded independent central review (BICR) recommended for pivotal trials
- Concordance between investigator and BICR should be reported
- Individual lesion measurements archived

"""

        return text.strip()


# Singleton instance
_irrc_service: Optional[irRC_Service] = None


def get_irrc_service() -> irRC_Service:
    """
    Get irRC service instance.

    Returns:
        irRC_Service instance
    """
    global _irrc_service

    if _irrc_service is None:
        _irrc_service = irRC_Service()

    return _irrc_service
