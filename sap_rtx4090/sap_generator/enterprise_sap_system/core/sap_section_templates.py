#!/usr/bin/env python3
"""
SAP Section Templates
=====================
Production-grade templates for SAP sections that are frequently missing or incomplete.

These templates are filled programmatically from extracted protocol data,
ensuring accuracy and consistency.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class SAPSectionTemplate:
    """Template for a SAP section."""
    section_number: str
    title: str
    content: str
    required_fields: List[str]


class SAPSectionGenerator:
    """
    Generates SAP sections from templates and extracted data.
    Uses programmatic filling - NOT LLM generation for critical content.
    """

    @staticmethod
    def generate_diary_data_section(diary_rules: Any) -> str:
        """Generate Handling of Diary Data section."""
        exclusions = "\n".join(f"  - {rule}" for rule in diary_rules.exclusion_rules) if diary_rules.exclusion_rules else "  - None specified"

        return f"""### 3.X Handling of Diary Data

#### 3.X.1 Calculation of Patient-Reported Mayo Subscores

Patient-reported diary data (stool frequency and rectal bleeding) will be used to calculate Mayo subscores according to the following rules:

**Averaging Period:**
- Subscores will be calculated as the average of {diary_rules.days_to_average} days of diary data prior to each visit

**Exclusion Rules:**
The following days will be excluded from the calculation:
{exclusions}

**Minimum Data Requirements:**
- A minimum of {diary_rules.minimum_days} valid diary days is required for subscore calculation
- If fewer than {diary_rules.minimum_days} days are available, the subscore will be {diary_rules.handling_if_insufficient}

**Rounding:**
- Averaged subscores will be rounded to the nearest integer
- Standard rounding rules apply (0.5 rounds up)

#### 3.X.2 Missing Diary Data

- Individual missing diary entries will not be imputed
- If the minimum number of valid diary days is not met, the visit subscore will be treated as missing
- Missing visit subscores will be handled according to the missing data rules specified in Section 7
"""

    @staticmethod
    def generate_pk_section(pk_spec: Any) -> str:
        """Generate enhanced PK Analysis section."""
        params_list = ", ".join(pk_spec.parameters) if pk_spec.parameters else "AUC, Cmax, Tmax, t½, CL, Vz"

        # Format sampling windows table
        windows_table = "| Timepoint | Target | Window |\n|-----------|--------|--------|\n"
        for window in pk_spec.sampling_windows:
            windows_table += f"| {window.timepoint} | {window.target_time} | ±{window.window_minus} |\n"

        if not pk_spec.sampling_windows:
            windows_table = "Sampling windows to be specified per protocol."

        return f"""### 8.X Pharmacokinetic Analysis

#### 8.X.1 PK Analysis Set

The PK Analysis Set includes all patients in the Safety Population who:
- Received at least one dose of study drug
- Have at least one evaluable PK sample
- Have no major protocol deviations affecting PK assessment

#### 8.X.2 PK Parameters

The following pharmacokinetic parameters will be calculated:

**Primary PK Parameters:**
{params_list}

**Calculation Method:**
- Method: {pk_spec.method}
- Software: {pk_spec.software} or validated equivalent

#### 8.X.3 Acceptable Sampling Windows

PK samples must be collected within the following windows to be considered valid:

{windows_table}

**Handling of Samples Outside Windows:**
- Samples collected outside acceptable windows will be flagged as protocol deviations
- These samples may be excluded from primary PK analysis at the discretion of the PK scientist
- Sensitivity analysis including all samples regardless of timing may be performed

#### 8.X.4 PK Summary Statistics

Plasma concentration data will be summarized by:
- Nominal sampling time
- Treatment group
- Visit (if applicable)

Summary statistics will include:
- N, Mean, SD, CV%, Median, Min, Max
- Geometric mean and geometric CV% for concentration and exposure parameters

#### 8.X.5 Concentration-Time Profiles

Individual and mean concentration-time profiles will be presented:
- Linear and semi-logarithmic scales
- By treatment group
- With standard deviation or standard error bars for mean profiles
"""

    @staticmethod
    def generate_scoring_section(modifications: List[Any]) -> str:
        """Generate Modified Scoring Criteria section."""
        if not modifications:
            return ""

        mods_text = ""
        for mod in modifications:
            mods_text += f"""
**{mod.score_name}:**
- Original criteria: {mod.original_criteria}
- Modified criteria: {mod.modified_criteria}
- Source: {mod.source_section}

"""

        return f"""### 3.X Modified Scoring Criteria

**IMPORTANT:** The following scoring criteria used in this study differ from standard/original criteria:

{mods_text}

These modifications must be applied consistently throughout all analyses and clearly documented in the Clinical Study Report.
"""

    @staticmethod
    def generate_withdrawal_section(criteria: List[Any]) -> str:
        """Generate Protocol Deviations and Withdrawal section."""
        if not criteria:
            criteria_text = "- Specific worsening criteria as defined in protocol Appendix"
        else:
            criteria_text = "\n".join(
                f"- {c.criterion}: {c.threshold}" + (f" ({c.confirmation_required})" if c.confirmation_required else "")
                for c in criteria
            )

        return f"""### 4.X Protocol Deviations and Withdrawals

#### 4.X.1 Major Protocol Deviations

The following are considered major protocol deviations that may lead to exclusion from the Per-Protocol Population:

**Efficacy-Related:**
- Failure to meet key inclusion/exclusion criteria
- Use of prohibited concomitant medications
- Treatment exposure less than X% of planned dose
- Inadequate baseline or post-baseline efficacy assessments

**PK-Related:**
- PK samples collected outside acceptable windows (see Section 8.X.3)
- Missing critical PK timepoints

#### 4.X.2 Worsening Criteria

Patients meeting the following criteria will be considered to have clinical worsening:

{criteria_text}

#### 4.X.3 Handling of Withdrawals in Analysis

| Population | Handling of Early Withdrawals |
|------------|------------------------------|
| ITT | Included regardless of withdrawal reason |
| FAS | Included if at least one post-baseline assessment |
| PP | Excluded if withdrawal due to protocol deviation |
| Safety | Included if received any study drug |

**Patients Withdrawn for Worsening:**
- Included in ITT/FAS populations
- Last observation used for imputation per missing data rules
- Clearly identified in data listings
"""

    @staticmethod
    def generate_subgroup_section(subgroup_specs: List[Any]) -> str:
        """Generate Subgroup Analysis section."""
        if not subgroup_specs:
            return ""

        subgroup_text = ""
        for spec in subgroup_specs:
            subgroups = " vs ".join(spec.subgroups) if spec.subgroups else "High vs Low"
            subgroup_text += f"""
**{spec.biomarker} Subgroups:**
- Cutoff determination: {spec.cutoff_method}
- Subgroups: {subgroups}
- Analysis approach: {spec.analysis_approach}
"""

        return f"""### 5.X Subgroup Analyses

#### 5.X.1 Pre-specified Subgroup Analyses

The following subgroup analyses are pre-specified in the protocol:

{subgroup_text}

#### 5.X.2 Methodology

For each subgroup analysis:
1. Subgroups will be defined based on baseline values
2. The primary analysis model will be applied within each subgroup
3. Treatment-by-subgroup interaction will be tested (exploratory)
4. Forest plots will display treatment effects by subgroup

#### 5.X.3 Interpretation

Given the exploratory nature of subgroup analyses:
- No multiplicity adjustment will be applied
- Results should be interpreted with caution
- Subgroup findings are hypothesis-generating only
"""

    @staticmethod
    def generate_sensitivity_section(sensitivity_analyses: List[Any], primary_method: str = "") -> str:
        """Generate Sensitivity Analysis section."""
        if not sensitivity_analyses:
            # Default sensitivity analyses
            sensitivity_text = """
| Analysis | Description | Differs from Primary |
|----------|-------------|---------------------|
| Per-Protocol | Analysis on PP population | Population definition |
| LOCF | Last observation carried forward | Missing data handling |
| Complete Cases | Observed data only | Excludes patients with missing data |
"""
        else:
            sensitivity_text = "| Analysis | Description | Differs from Primary |\n|----------|-------------|---------------------|\n"
            for sa in sensitivity_analyses:
                sensitivity_text += f"| {sa.name} | {sa.description} | {sa.differs_from_primary} |\n"

        return f"""### 5.X Sensitivity Analyses

#### 5.X.1 Overview

Sensitivity analyses will be performed to assess the robustness of the primary analysis results. These analyses will evaluate the impact of:
- Different analysis populations
- Alternative missing data assumptions
- Model assumptions

#### 5.X.2 Pre-specified Sensitivity Analyses

{sensitivity_text}

#### 5.X.3 Interpretation

- Sensitivity analyses are supportive and not subject to multiplicity adjustment
- Consistency of results across sensitivity analyses supports robustness of conclusions
- Discrepancies between primary and sensitivity analyses will be discussed in the CSR
"""

    @staticmethod
    def generate_alpha_section(alpha_assignments: Dict) -> str:
        """Generate Statistical Testing section."""
        return f"""### 5.X Statistical Significance and Hypothesis Testing

#### 5.X.1 Significance Levels

Due to the {alpha_assignments.get('rationale', 'exploratory nature of this study')}, statistical testing will be performed at multiple significance levels:

| Endpoint Type | Alpha Level | Sidedness |
|--------------|-------------|-----------|
| Primary | {alpha_assignments.get('primary_alpha', 0.05)} | {alpha_assignments.get('sidedness', 'one-sided')} |
| Secondary | {alpha_assignments.get('secondary_alpha', 0.05)} | {alpha_assignments.get('sidedness', 'one-sided')} |
| Exploratory | {alpha_assignments.get('exploratory_alpha', 0.20)} | {alpha_assignments.get('sidedness', 'one-sided')} |

#### 5.X.2 Interpretation

- P-values will be reported for all inferential analyses
- Confidence intervals will be provided (90% for one-sided tests, 95% for two-sided)
- Given the exploratory nature, results should be interpreted as hypothesis-generating
- The 20% significance level provides increased sensitivity for detecting potential signals

#### 5.X.3 Multiplicity

Due to the exploratory nature of this study:
- No formal multiplicity adjustment will be applied
- All p-values will be reported as nominal (unadjusted)
- The interpretation of results will consider the multiple comparisons made
"""

    @staticmethod
    def generate_visit_window_section(visit_schedule: Dict) -> str:
        """Generate Visit Windows section."""
        if not visit_schedule:
            return ""

        table = "| Visit | Target Day | Acceptable Range |\n|-------|------------|------------------|\n"
        for visit, details in sorted(visit_schedule.items(), key=lambda x: int(x[0].split()[-1]) if x[0].split()[-1].isdigit() else 0):
            table += f"| {visit} | Day {details['target_day']} | Days {details['min_day']}-{details['max_day']} |\n"

        return f"""### 7.X Visit Windows

#### 7.X.1 Protocol-Specified Visit Windows

{table}

#### 7.X.2 Handling of Out-of-Window Visits

- Visits occurring outside the specified windows will be flagged
- Data from out-of-window visits will be included in analysis but noted
- For efficacy analyses, the closest assessment to the target day will be used
- Multiple assessments within a window will be handled as follows:
  - Use the assessment closest to the target day
  - If equidistant, use the later assessment

#### 7.X.3 Visit Mapping for Analysis

- Analysis visits will be defined based on protocol-specified target days
- All assessments will be mapped to the nearest analysis visit
- Unscheduled visits will be included in safety analyses but not efficacy
"""

    def generate_all_missing_sections(self, clinical_details: Dict) -> Dict[str, str]:
        """
        Generate all missing/enhanced SAP sections from extracted clinical details.

        Args:
            clinical_details: Output from ClinicalTrialExtractor.extract_all_clinical_details()

        Returns:
            Dictionary of section_name -> section_content
        """
        sections = {}

        # Diary data section
        if clinical_details.get('diary_data_rules'):
            sections['diary_data'] = self.generate_diary_data_section(
                clinical_details['diary_data_rules']
            )

        # PK section
        if clinical_details.get('pk_analysis_spec'):
            sections['pk_analysis'] = self.generate_pk_section(
                clinical_details['pk_analysis_spec']
            )

        # Scoring modifications
        if clinical_details.get('scoring_modifications'):
            sections['scoring_modifications'] = self.generate_scoring_section(
                clinical_details['scoring_modifications']
            )

        # Withdrawal criteria
        if clinical_details.get('withdrawal_criteria'):
            sections['withdrawal_criteria'] = self.generate_withdrawal_section(
                clinical_details['withdrawal_criteria']
            )

        # Subgroup analyses
        if clinical_details.get('subgroup_specs'):
            sections['subgroup_analyses'] = self.generate_subgroup_section(
                clinical_details['subgroup_specs']
            )

        # Sensitivity analyses
        sections['sensitivity_analyses'] = self.generate_sensitivity_section(
            clinical_details.get('sensitivity_analyses', [])
        )

        # Alpha assignments
        if clinical_details.get('alpha_assignments'):
            sections['statistical_testing'] = self.generate_alpha_section(
                clinical_details['alpha_assignments']
            )

        # Visit windows
        if clinical_details.get('visit_schedule'):
            sections['visit_windows'] = self.generate_visit_window_section(
                clinical_details['visit_schedule']
            )

        return sections
