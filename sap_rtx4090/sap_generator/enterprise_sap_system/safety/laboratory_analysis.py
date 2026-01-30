"""
Laboratory Safety Analysis Methods
===================================

Statistical methods for clinical laboratory data in safety assessment.

Regulatory guidance:
- FDA: "Evaluation of Safety Data from Controlled Trials" (2017)
- ICH E3: Structure and Content of Clinical Study Reports (Section 12.2)

Laboratory data categories:
- Hematology
- Chemistry (including liver function)
- Coagulation
- Urinalysis

Analysis methods:
- Shift tables (baseline to worst post-baseline)
- Laboratory abnormalities (grade 3/4)
- Potentially clinically significant abnormalities (PCSA)
- Hy's Law cases (hepatotoxicity)
- Time course/longitudinal plots
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LabCategory(Enum):
    """Laboratory test categories"""
    HEMATOLOGY = "Hematology"
    CHEMISTRY = "Chemistry"
    LIVER_FUNCTION = "Liver Function Tests"
    RENAL_FUNCTION = "Renal Function"
    COAGULATION = "Coagulation"
    URINALYSIS = "Urinalysis"
    LIPIDS = "Lipid Panel"


class ToxicityGrade(Enum):
    """CTCAE toxicity grades for lab values"""
    NORMAL = "Normal"
    GRADE_1 = "Grade 1"
    GRADE_2 = "Grade 2"
    GRADE_3 = "Grade 3"
    GRADE_4 = "Grade 4"


@dataclass
class LabParameter:
    """Specification for a laboratory parameter"""
    param_code: str                    # e.g., "ALT", "PLAT"
    param_name: str                    # Full name
    category: LabCategory

    # Units and reference ranges
    standard_unit: str = ""            # SI or conventional
    reference_range_low: Optional[float] = None
    reference_range_high: Optional[float] = None

    # CTCAE grading
    has_ctcae_grading: bool = True
    grade_thresholds: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    # Clinical significance thresholds
    pcsa_threshold_low: Optional[float] = None   # Potentially clinically significant abnormality
    pcsa_threshold_high: Optional[float] = None


@dataclass
class ShiftTableSpec:
    """
    Specification for shift table (baseline to post-baseline).

    Shows movement between normal/abnormal categories.
    """
    parameter: LabParameter

    # Categories
    categories: List[str] = field(default_factory=lambda: [
        "Low", "Normal", "High"
    ])

    # Alternative: CTCAE grades
    use_ctcae_grades: bool = False

    # Time point
    post_baseline_timepoint: str = "Worst Post-Baseline"  # or specific visit


@dataclass
class HysLawAnalysis:
    """
    Hy's Law analysis for hepatotoxicity assessment.

    FDA guidance on drug-induced liver injury (DILI).
    """
    # Criteria
    alt_threshold: float = 3.0         # × ULN
    ast_threshold: float = 3.0         # × ULN
    tbili_threshold: float = 2.0       # × ULN
    alp_threshold: float = 2.0         # × ULN (exclusion)

    # Timing
    concurrent: bool = True            # ALT/AST and TBILI concurrent

    # Analysis
    identify_cases: bool = True
    narrative_required: bool = True


@dataclass
class LaboratoryAnalysisSpec:
    """
    Complete laboratory safety analysis specification.

    Defines all lab analyses for SAP.
    """
    # Parameters to analyze
    hematology_params: List[LabParameter] = field(default_factory=list)
    chemistry_params: List[LabParameter] = field(default_factory=list)
    liver_function_params: List[LabParameter] = field(default_factory=list)

    # Analysis types
    descriptive_statistics: bool = True
    shift_tables: bool = True
    grade_3_4_abnormalities: bool = True
    pcsa_analysis: bool = True

    # Hepatotoxicity
    perform_hys_law: bool = True
    hys_law_spec: Optional[HysLawAnalysis] = None

    # Visualization
    time_course_plots: bool = True
    by_treatment_plots: bool = True


class LaboratoryAnalysisService:
    """
    Service for laboratory safety analysis specifications.

    Provides standardized lab analysis methods.
    """

    # Standard hematology parameters
    STANDARD_HEMATOLOGY = [
        LabParameter(
            param_code="HGB",
            param_name="Hemoglobin",
            category=LabCategory.HEMATOLOGY,
            standard_unit="g/dL",
            reference_range_low=12.0,
            reference_range_high=16.0,
            has_ctcae_grading=True
        ),
        LabParameter(
            param_code="WBC",
            param_name="White Blood Cell Count",
            category=LabCategory.HEMATOLOGY,
            standard_unit="10^9/L",
            reference_range_low=4.0,
            reference_range_high=11.0
        ),
        LabParameter(
            param_code="PLAT",
            param_name="Platelet Count",
            category=LabCategory.HEMATOLOGY,
            standard_unit="10^9/L",
            reference_range_low=150.0,
            reference_range_high=400.0
        ),
        LabParameter(
            param_code="ANC",
            param_name="Absolute Neutrophil Count",
            category=LabCategory.HEMATOLOGY,
            standard_unit="10^9/L",
            reference_range_low=1.5,
            reference_range_high=7.5
        ),
    ]

    # Standard liver function tests
    STANDARD_LFT = [
        LabParameter(
            param_code="ALT",
            param_name="Alanine Aminotransferase",
            category=LabCategory.LIVER_FUNCTION,
            standard_unit="U/L",
            reference_range_high=40.0,
            has_ctcae_grading=True
        ),
        LabParameter(
            param_code="AST",
            param_name="Aspartate Aminotransferase",
            category=LabCategory.LIVER_FUNCTION,
            standard_unit="U/L",
            reference_range_high=40.0,
            has_ctcae_grading=True
        ),
        LabParameter(
            param_code="BILI",
            param_name="Total Bilirubin",
            category=LabCategory.LIVER_FUNCTION,
            standard_unit="mg/dL",
            reference_range_high=1.2,
            has_ctcae_grading=True
        ),
        LabParameter(
            param_code="ALP",
            param_name="Alkaline Phosphatase",
            category=LabCategory.LIVER_FUNCTION,
            standard_unit="U/L",
            reference_range_high=120.0
        ),
    ]

    def __init__(self):
        """Initialize laboratory analysis service"""
        pass

    def create_standard_lab_spec(self) -> LaboratoryAnalysisSpec:
        """Create standard laboratory analysis specification"""
        return LaboratoryAnalysisSpec(
            hematology_params=self.STANDARD_HEMATOLOGY,
            chemistry_params=[],
            liver_function_params=self.STANDARD_LFT,
            descriptive_statistics=True,
            shift_tables=True,
            grade_3_4_abnormalities=True,
            pcsa_analysis=True,
            perform_hys_law=True,
            hys_law_spec=HysLawAnalysis()
        )

    def generate_laboratory_methodology(
        self,
        spec: LaboratoryAnalysisSpec
    ) -> str:
        """
        Generate laboratory analysis methodology for SAP.

        Args:
            spec: Laboratory analysis specification

        Returns:
            Formatted SAP text
        """
        text = """
## Laboratory Safety Analysis

### Laboratory Assessments

Clinical laboratory tests will be performed at:
- Screening
- Baseline (Day 1 pre-dose)
- On-treatment visits per schedule
- End of treatment
- Safety follow-up (if applicable)

**Laboratory Parameters:**

"""

        if spec.hematology_params:
            text += """
**Hematology:**
"""
            for param in spec.hematology_params:
                text += f"- {param.param_name} ({param.param_code})\n"
            text += "\n"

        if spec.liver_function_params:
            text += """
**Liver Function Tests:**
"""
            for param in spec.liver_function_params:
                text += f"- {param.param_name} ({param.param_code})\n"
            text += "\n"

        text += """
**Laboratory Standards:**
- All tests performed at central laboratory
- Results reported in SI units
- Reference ranges provided by central laboratory

"""

        # Reference ranges
        text += self._generate_reference_ranges_section()

        # Analysis methods
        text += self._generate_lab_analysis_methods(spec)

        # Shift tables
        if spec.shift_tables:
            text += self._generate_shift_table_section()

        # CTCAE grading
        if spec.grade_3_4_abnormalities:
            text += self._generate_ctcae_grading_section()

        # PCSA
        if spec.pcsa_analysis:
            text += self._generate_pcsa_section()

        # Hy's Law
        if spec.perform_hys_law:
            text += self._generate_hys_law_section(spec.hys_law_spec)

        return text.strip()

    def _generate_reference_ranges_section(self) -> str:
        """Generate reference ranges section"""
        return """
### Reference Ranges and Abnormality Definitions

**Normal Range:**
Values within the laboratory-specific reference range (sex-specific where applicable).

**Low/High:**
Values outside the normal range are classified as:
- **Low:** Below lower limit of normal (LLN)
- **High:** Above upper limit of normal (ULN)

**Multiples of ULN/LLN:**
For grading, values expressed as:
- xULN: Value / Upper Limit of Normal
- xLLN: Value / Lower Limit of Normal

**Baseline Value:**
Last non-missing value before first dose of study treatment.

**Post-Baseline:**
All values collected after first dose while on treatment.

**Worst Post-Baseline:**
Most extreme value (furthest from normal) during treatment.

"""

    def _generate_lab_analysis_methods(self, spec: LaboratoryAnalysisSpec) -> str:
        """Generate analysis methods section"""
        text = """
### Statistical Analysis Methods

"""

        if spec.descriptive_statistics:
            text += """
#### Descriptive Statistics

For each laboratory parameter, the following will be summarized by treatment group
and visit:

- N (number of subjects with data)
- Mean
- Standard deviation
- Median
- Minimum, Maximum
- Q1, Q3 (quartiles)

**Change from Baseline:**
Also summarized for post-baseline visits:
- Change = Post-baseline value - Baseline value
- Percent change = (Change / Baseline) × 100%

**Presentation:**
- Summary statistics tables by visit
- Separate for each laboratory category (hematology, chemistry, etc.)

"""

        if spec.time_course_plots:
            text += """
#### Time Course Plots

Mean (±SE) laboratory values over time will be plotted by treatment group:
- X-axis: Study visit/time
- Y-axis: Laboratory value
- Reference range shaded
- Separate lines for each treatment

**Purpose:** Visualize trends and identify systematic changes over time.

"""

        return text

    def _generate_shift_table_section(self) -> str:
        """Generate shift table section"""
        return """
#### Shift Tables

Shift tables show the change in laboratory abnormality status from baseline to
worst post-baseline.

**Categories:**
- **Low:** <LLN
- **Normal:** Within reference range
- **High:** >ULN

**Format:**
```
                    Worst Post-Baseline
Baseline      Low      Normal      High      Total
--------------------------------------------------------
Low           n (%)    n (%)       n (%)     n (%)
Normal        n (%)    n (%)       n (%)     n (%)
High          n (%)    n (%)       n (%)     n (%)
Total         n (%)    n (%)       n (%)     n (%)
```

**Interpretation:**
- Diagonal cells: No change in category
- Off-diagonal: Shift from baseline category
- Lower-right: Worsening (normal → high, low → normal/high)
- Upper-left: Improvement

**Clinical Significance:**
Focus on shifts to abnormal from normal baseline, particularly:
- Normal → High (new abnormalities)
- Low/High → More extreme (worsening)

"""

    def _generate_ctcae_grading_section(self) -> str:
        """Generate CTCAE grading section"""
        return """
#### Grade 3 and 4 Laboratory Abnormalities

Laboratory values will be graded using CTCAE v5.0.

**Grade 3:** Severe, requiring intervention
**Grade 4:** Life-threatening, urgent intervention required

**Analysis:**
- Number and percentage of subjects with Grade 3 or 4 lab abnormalities
- Presented by parameter and treatment group
- Separate table for each category (hematology, chemistry)

**Example Grading Criteria:**

| Parameter | Grade 3 | Grade 4 |
|-----------|---------|---------|
| Hemoglobin | <8.0 g/dL | Life-threatening |
| ANC | <1.0 × 10⁹/L | <0.5 × 10⁹/L |
| Platelets | <50 × 10⁹/L | <25 × 10⁹/L |
| ALT | >5-20 × ULN | >20 × ULN |
| Total Bilirubin | >3-10 × ULN | >10 × ULN |
| Creatinine | >3-6 × baseline | >6 × baseline |

**Listing:**
All Grade 3 and 4 laboratory abnormalities will be listed with:
- Subject ID
- Parameter
- Grade
- Value and date
- Baseline value
- Outcome/resolution

"""

    def _generate_pcsa_section(self) -> str:
        """Generate PCSA section"""
        return """
#### Potentially Clinically Significant Abnormalities (PCSA)

PCSAs are pre-defined laboratory values that may require clinical intervention,
regardless of CTCAE grade.

**PCSA Criteria Examples:**

**Hematology:**
- Hemoglobin: <8 g/dL or decrease ≥3 g/dL from baseline
- WBC: <2 × 10⁹/L or >20 × 10⁹/L
- Platelets: <50 × 10⁹/L
- ANC: <1.0 × 10⁹/L

**Liver Function:**
- ALT or AST: >3 × ULN
- Total Bilirubin: >2 × ULN
- ALP: >3 × ULN
- Combined: ALT >3 × ULN AND Total Bilirubin >2 × ULN (Hy's Law)

**Renal Function:**
- Creatinine: >1.5 × ULN or >1.5 × baseline

**Analysis:**
- Number and percentage of subjects with at least one PCSA
- By parameter and treatment group
- Narrative description of management and outcome

**Purpose:**
Identify clinically relevant changes that may not reach Grade 3/4 but still
require attention.

"""

    def _generate_hys_law_section(self, hys_spec: Optional[HysLawAnalysis]) -> str:
        """Generate Hy's Law analysis section"""
        if not hys_spec:
            hys_spec = HysLawAnalysis()

        return f"""
#### Hy's Law Analysis (Drug-Induced Liver Injury)

**Hy's Law Definition:**
Per FDA guidance, potential Hy's Law cases are defined as:

1. **ALT or AST** >{hys_spec.alt_threshold} × ULN, **AND**
2. **Total Bilirubin** >{hys_spec.tbili_threshold} × ULN, **AND**
3. **Alkaline Phosphatase** <{hys_spec.alp_threshold} × ULN (to rule out cholestasis)

**Clinical Significance:**
Concurrent elevation of transaminases and bilirubin suggests severe hepatocellular
injury with high risk of liver failure.

**Analysis:**

1. **Case Identification:**
   - Screen all subjects for criteria above
   - Evaluate temporal relationship (concurrent elevations)
   - Review for alternative causes

2. **Laboratory Monitoring:**
   - eDISH plot (ALT vs. Total Bilirubin scatter plot)
   - Each point represents one subject's worst values
   - Quadrants:
     - Temple's Corollary: ALT >3× ULN, TBILI >2× ULN (Hy's Law region)
     - Cholestatic: ALP elevated, ALT <3× ULN
     - Normal zone
     - Hepatocellular injury without bilirubin elevation

3. **Narrative:**
   For each potential Hy's Law case:
   - Timeline of lab elevations
   - Concomitant medications
   - Underlying liver disease
   - Other potential causes
   - Clinical course and outcome
   - Treatment modifications

**Regulatory Importance:**
Hy's Law cases are reportable to FDA and may impact drug approval.
Even one case requires thorough investigation and may lead to:
- Boxed warning
- REMS (Risk Evaluation and Mitigation Strategy)
- Denial of approval

"""


# Singleton instance
_laboratory_service: Optional[LaboratoryAnalysisService] = None


def get_laboratory_analysis_service() -> LaboratoryAnalysisService:
    """
    Get laboratory analysis service instance.

    Returns:
        LaboratoryAnalysisService instance
    """
    global _laboratory_service

    if _laboratory_service is None:
        _laboratory_service = LaboratoryAnalysisService()

    return _laboratory_service
