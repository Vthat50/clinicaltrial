"""Claude semantic transformer - converts protocol sections to SAP prose."""
import os
import json
from dataclasses import dataclass
from typing import Optional

from rich.console import Console

console = Console()


@dataclass
class TransformedSection:
    """A protocol section transformed to SAP language."""
    section_type: str
    original_content: str
    sap_content: str
    confidence: float


SAP_TRANSFORMATION_PROMPTS = {
    "objectives": """Transform this clinical trial protocol objectives section into formal ICH E9(R1) compliant SAP language.

INPUT (Protocol Objectives):
{content}

OUTPUT REQUIREMENTS (MANDATORY - include ALL of these):
- Write in formal regulatory SAP prose, NOT bullet points
- Structure with clear "Primary Objective:" and "Secondary Objectives:" headers
- State the statistical hypothesis explicitly (e.g., "To demonstrate superiority of Treatment A vs Control")
- Include the estimand framework components where applicable
- Reference the target population and treatment effect of interest

EXAMPLE FORMAT:
"Primary Objective: To evaluate the efficacy of [drug] compared to [comparator] as measured by [endpoint] in patients with [condition]. The null hypothesis (H0) states that there is no difference between treatment groups..."

Write the SAP Objectives section:""",

    "endpoints": """Transform these protocol endpoints into formal SAP endpoint definitions with precise statistical specifications.

INPUT (Protocol Endpoints):
{content}

OUTPUT REQUIREMENTS (MANDATORY - include ALL of these):
- Define each endpoint with PRECISE measurement methodology
- Specify exact timing of assessments (e.g., "assessed at Week 12 ± 3 days")
- Include derivation rules and handling of missing components
- Use standard SAP terminology: "Time to event defined as...", "Change from baseline calculated as..."
- For composite endpoints, specify how components are combined
- Include censoring rules for time-to-event endpoints

EXAMPLE FORMAT:
"Primary Endpoint: Progression-free survival (PFS), defined as the time from randomization to the first documented disease progression per RECIST v1.1 or death from any cause, whichever occurs first. Patients without progression will be censored at the date of last tumor assessment."

Write the SAP Endpoints section:""",

    "sample_size": """Transform this sample size section into formal SAP sample size justification with complete statistical rationale.

INPUT (Protocol Sample Size):
{content}

OUTPUT REQUIREMENTS (MANDATORY - include ALL of these):
- State the null hypothesis (H0) and alternative hypothesis (H1) explicitly
- Specify Type I error rate: "alpha = 0.05 (two-sided)" or "alpha = 0.025 (one-sided)"
- Specify statistical power: "power = 80%" or "power = 90% (1-beta)"
- Document the expected effect size with clinical rationale (e.g., "hazard ratio of 0.70")
- Include dropout/attrition assumptions
- Reference software used (e.g., "calculated using PASS 2021" or "nQuery Advisor")
- State final sample size per arm AND total enrollment target

EXAMPLE FORMAT:
"Sample Size Justification: The null hypothesis (H0) states that the hazard ratio equals 1.0. Assuming a hazard ratio of 0.70 favoring the experimental arm, with 80% power and a two-sided alpha of 0.05, approximately 250 events are required. With an expected dropout rate of 10%, a total of 400 patients (200 per arm) will be enrolled. Calculations performed using EAST 6.5."

Write the SAP Sample Size section:""",

    "statistical_methods": """Transform this into comprehensive SAP statistical analysis methods with ICH E9(R1) estimand framework.

INPUT (Protocol Statistical Methods):
{content}

OUTPUT REQUIREMENTS (MANDATORY - include ALL of these):
- Specify the EXACT statistical test for primary analysis (e.g., "stratified log-rank test", "Cox proportional hazards model", "ANCOVA", "MMRM")
- Include model specification with covariates and stratification factors
- State confidence interval approach: "95% CI using Wald method" or "95% CI using profile likelihood"
- Specify two-sided or one-sided testing explicitly
- Multiplicity adjustment: Describe alpha-spending function (e.g., Lan-DeMets O'Brien-Fleming), gatekeeping procedures, or Hochberg/Holm adjustments
- Missing data: Specify primary approach (MMRM, multiple imputation, LOCF) with sensitivity analyses (tipping point, delta-adjustment, pattern mixture models)
- Specify analysis software: "SAS version 9.4" or "R version 4.2"

ESTIMAND FRAMEWORK (ICH E9 R1):
- Treatment: Describe the treatment regimen
- Population: Define the target population
- Variable: Specify the endpoint variable
- Intercurrent events: How discontinuations, rescue medication, deaths are handled
- Summary measure: Treatment effect measure (difference in means, hazard ratio, odds ratio)

EXAMPLE FORMAT:
"Primary Analysis: The primary endpoint will be analyzed using a stratified log-rank test, stratified by [factors]. A Cox proportional hazards model will estimate the hazard ratio with 95% confidence interval. The model will include treatment as a fixed effect and stratification factors as covariates. All tests will be two-sided at alpha = 0.05. Missing data will be handled using multiple imputation under the missing at random (MAR) assumption, with sensitivity analyses using pattern mixture models. Analysis will be performed using SAS version 9.4."

Write the SAP Statistical Methods section:""",

    "analysis_populations": """Transform into formal SAP analysis population definitions per ICH E9 guidelines.

INPUT (Protocol Population Info):
{content}

OUTPUT REQUIREMENTS (MANDATORY - include ALL of these):
- Intent-to-Treat (ITT) Population: "All randomized patients according to randomized treatment assignment"
- Modified ITT (mITT): Specify exact inclusion criteria (e.g., "received at least one dose", "had baseline and one post-baseline assessment")
- Per-Protocol (PP) Population: List major protocol deviations that exclude patients
- Safety Population: "All patients who received at least one dose of study medication, analyzed according to actual treatment received"
- Specify which population is PRIMARY for efficacy analysis
- Include handling of protocol deviations and treatment discontinuations

EXAMPLE FORMAT:
"Intent-to-Treat (ITT) Population: All randomized patients will be included in the ITT population and analyzed according to randomized treatment assignment, regardless of actual treatment received. This is the primary population for all efficacy analyses.

Safety Population: All patients who received at least one dose (complete or partial) of study medication will be included in the safety population and analyzed according to actual treatment received."

Write the SAP Analysis Populations section:""",

    "efficacy_analyses": """Transform into detailed SAP efficacy analysis section with complete statistical specifications.

INPUT (Protocol Efficacy Info):
{content}

OUTPUT REQUIREMENTS (MANDATORY - include ALL of these):
- State the NULL HYPOTHESIS explicitly: "H0: HR = 1.0" or "H0: μA - μB = 0"
- Describe the POINT ESTIMATE and how treatment effect will be quantified
- Specify 95% CONFIDENCE INTERVAL methodology
- Primary analysis: Full model specification with test statistic
- Secondary analyses: Methods for each secondary endpoint
- Subgroup analyses: Pre-specified subgroups with forest plot specifications
- Sensitivity analyses: Alternative methods to assess robustness

EXAMPLE FORMAT:
"Primary Efficacy Analysis:
Null Hypothesis (H0): The hazard ratio for progression-free survival equals 1.0 (no treatment difference).
Alternative Hypothesis (H1): The hazard ratio differs from 1.0.

The primary analysis will use a stratified log-rank test at a two-sided significance level of 0.05. The point estimate of the treatment effect (hazard ratio) will be obtained from a Cox proportional hazards model, along with the associated 95% confidence interval. The model will include treatment group as the primary factor and stratification factors (ECOG status, prior therapy) as covariates.

Subgroup Analyses: Pre-specified subgroup analyses will be performed for age (<65 vs ≥65), sex, ECOG status, and biomarker status. Results will be displayed in a forest plot with interaction p-values."

Write the SAP Efficacy Analyses section:""",

    "safety_analyses": """Transform into comprehensive SAP safety analysis section per ICH E9 and regulatory requirements.

INPUT (Protocol Safety Info):
{content}

OUTPUT REQUIREMENTS (MANDATORY - include ALL of these):
- Adverse Event (AE) coding: "AEs will be coded using MedDRA version 25.0"
- AE tabulation: "Summarized by System Organ Class (SOC) and Preferred Term (PT)"
- Severity grading: Reference CTCAE version or other grading system
- Serious Adverse Events (SAE): Specific handling and reporting
- Laboratory analyses: Shift tables, clinically significant values, reference ranges
- Vital signs: Summary statistics and clinically notable values
- Exposure summary: Treatment duration, dose intensity, compliance

EXAMPLE FORMAT:
"Safety Analyses:

Adverse Events: All AEs will be coded using the Medical Dictionary for Regulatory Activities (MedDRA) version 25.0. AEs will be summarized by System Organ Class (SOC) and Preferred Term (PT), displaying the number and percentage of patients experiencing each event. Severity will be graded according to CTCAE version 5.0.

Treatment-emergent adverse events (TEAEs) are defined as AEs that started or worsened after the first dose of study medication. Summary tables will present TEAEs, treatment-related TEAEs, Grade ≥3 TEAEs, serious AEs, and AEs leading to discontinuation.

Laboratory Parameters: Shift tables will display changes from baseline (normal/low/high) to worst post-baseline value. Clinically significant laboratory abnormalities will be flagged based on predefined criteria.

Exposure: Treatment exposure will be summarized including duration of treatment, cumulative dose, and relative dose intensity."

Write the SAP Safety Analyses section:""",

    "study_design": """Transform into formal SAP study design description.

INPUT (Protocol Study Design):
{content}

OUTPUT REQUIREMENTS:
- Design type with precise terminology (randomized, double-blind, placebo-controlled, parallel-group)
- Randomization: ratio, method (IWRS/IXRS), stratification factors
- Blinding: who is blinded, unblinding procedures
- Treatment arms: complete description of each arm
- Study duration: treatment period, follow-up period

Write the SAP Study Design section:""",

    "missing_data": """Generate a comprehensive missing data handling section for this SAP.

INPUT (Available Protocol Information):
{content}

OUTPUT REQUIREMENTS (MANDATORY):
- State the primary missing data assumption (MAR, MCAR, MNAR)
- Describe the primary imputation/analysis method (MMRM, multiple imputation, mixed models)
- Sensitivity analyses: tipping point analysis, delta-adjustment, pattern mixture models, jump to reference
- Handling of intercurrent events per ICH E9(R1) estimand framework
- Specify percentage thresholds that trigger sensitivity analyses

EXAMPLE FORMAT:
"Missing Data Handling:

Primary Approach: The primary analysis will use a mixed-effects model for repeated measures (MMRM) which inherently handles missing data under the missing at random (MAR) assumption. The model will include treatment, visit, treatment-by-visit interaction, baseline value, and stratification factors.

Sensitivity Analyses:
1. Multiple Imputation: Missing values will be imputed using multiple imputation (m=50 imputations) under the MAR assumption.
2. Tipping Point Analysis: The robustness of conclusions will be assessed by systematically worsening imputed values for the experimental arm.
3. Jump to Reference: Patients who discontinue treatment will be assumed to have outcomes similar to the control arm.
4. Pattern Mixture Models: To assess MNAR scenarios."

Write the SAP Missing Data section:""",

    "multiplicity": """Generate a comprehensive multiplicity adjustment section for this SAP.

INPUT (Available Protocol Information):
{content}

OUTPUT REQUIREMENTS (MANDATORY):
- Describe the overall Type I error control strategy
- Specify alpha allocation across primary/secondary endpoints
- Detail the testing hierarchy or gatekeeping procedure
- Include graphical testing procedure if applicable
- Specify adjustment methods (Bonferroni, Holm, Hochberg, Hommel, etc.)

EXAMPLE FORMAT:
"Multiplicity Adjustments:

Overall Strategy: The overall familywise Type I error rate will be controlled at the two-sided 0.05 level using a hierarchical testing procedure.

Testing Hierarchy:
1. Primary Endpoint (PFS): Tested first at alpha = 0.05 (two-sided)
2. Key Secondary Endpoint (OS): Tested at alpha = 0.05 only if the primary endpoint is statistically significant
3. Other Secondary Endpoints: Tested using Hochberg procedure at alpha = 0.05, contingent on significance of the key secondary endpoint

Alpha-Spending for Interim Analyses: For the interim analysis, the Lan-DeMets alpha-spending function with O'Brien-Fleming boundaries will be used to preserve the overall Type I error rate."

Write the SAP Multiplicity section:""",

    "sensitivity_analyses": """Generate a comprehensive sensitivity analyses section for this SAP.

INPUT (Available Protocol Information):
{content}

OUTPUT REQUIREMENTS (MANDATORY):
- List all pre-specified sensitivity analyses
- Describe the rationale for each sensitivity analysis
- Specify alternative statistical methods or assumptions
- Include robustness assessments for key findings

EXAMPLE FORMAT:
"Sensitivity Analyses:

The following sensitivity analyses will be performed to assess the robustness of the primary analysis:

1. Per-Protocol Analysis: The primary endpoint will be analyzed in the per-protocol population to assess the treatment effect in patients who adhered to the protocol.

2. Alternative Censoring Rules: Sensitivity analyses will assess the impact of different censoring rules for intercurrent events.

3. Covariate Adjustment: Additional covariates (age, sex, baseline disease severity) will be included in the Cox model.

4. Subgroup Consistency: Treatment effects will be evaluated across pre-specified subgroups to assess consistency.

5. Alternative Missing Data Assumptions: Pattern mixture models assuming missing not at random (MNAR) will be fitted."

Write the SAP Sensitivity Analyses section:""",

    "interim_analyses": """Generate an interim analyses section for this SAP based on available information.

INPUT (Available Protocol Information):
{content}

OUTPUT REQUIREMENTS (MANDATORY):
- Describe the timing and number of interim analyses
- Specify the alpha-spending function
- Detail stopping boundaries for efficacy and/or futility
- Describe the role of the Data Monitoring Committee (DMC/DSMB)
- Include statistical software for boundary calculations

EXAMPLE FORMAT:
"Interim Analyses:

Timing: One interim analysis is planned when approximately 50% of the required events have been observed.

Alpha-Spending: The Lan-DeMets alpha-spending function with O'Brien-Fleming-type boundaries will be used to control the overall Type I error rate at 0.05 (two-sided).

Stopping Boundaries:
- Efficacy: The study may be stopped early for efficacy if the observed treatment effect crosses the pre-specified efficacy boundary.
- Futility: Non-binding futility boundaries will be calculated using the Lan-DeMets beta-spending function.

Data Monitoring Committee: An independent Data Monitoring Committee (DMC) will review unblinded efficacy and safety data at the interim analysis and make recommendations regarding study continuation.

Calculations will be performed using EAST 6.5 or equivalent validated software."

Write the SAP Interim Analyses section:""",

    "subgroup_analyses": """Generate a subgroup analyses section for this SAP.

INPUT (Available Protocol Information):
{content}

OUTPUT REQUIREMENTS (MANDATORY):
- List all pre-specified subgroups
- Specify the statistical methods for subgroup analyses
- Describe interaction tests
- Include forest plot specifications
- Note the exploratory nature of subgroup analyses

EXAMPLE FORMAT:
"Subgroup Analyses:

Pre-specified Subgroups: The following subgroups are pre-specified for analysis:
- Age: <65 years vs ≥65 years
- Sex: Male vs Female
- ECOG Performance Status: 0 vs 1
- Geographic Region: North America vs Europe vs Asia
- Prior Therapy: Yes vs No
- Biomarker Status: Positive vs Negative

Statistical Methods: For each subgroup, the primary endpoint will be analyzed using the same methods as the primary analysis, with treatment-by-subgroup interaction terms included in the model.

Interaction Tests: Treatment-by-subgroup interaction p-values will be calculated. A p-value <0.10 will be considered indicative of potential heterogeneity.

Presentation: Results will be displayed in forest plots showing the hazard ratio and 95% confidence interval for each subgroup, along with interaction p-values.

Note: Subgroup analyses are exploratory in nature and will not be adjusted for multiplicity. Results should be interpreted with caution."

Write the SAP Subgroup Analyses section:"""
}


class ClaudeTransformer:
    """Transform protocol content to SAP language using Claude."""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.client = None

        if self.api_key:
            self._init_client()

    def _init_client(self):
        """Initialize Anthropic client."""
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
            console.print("[green]Claude transformer initialized[/green]")
        except ImportError:
            console.print("[red]anthropic package not installed[/red]")

    def transform_section(
        self,
        section_type: str,
        content: str,
        context: dict = None
    ) -> Optional[TransformedSection]:
        """Transform a protocol section to SAP language.

        Args:
            section_type: Type of section (objectives, endpoints, etc.)
            content: Original protocol content
            context: Additional context (study title, phase, etc.)

        Returns:
            TransformedSection with SAP-formatted content
        """
        if not self.client:
            console.print("[yellow]Claude not available, returning original content[/yellow]")
            return TransformedSection(
                section_type=section_type,
                original_content=content,
                sap_content=content,
                confidence=0.0
            )

        prompt_template = SAP_TRANSFORMATION_PROMPTS.get(section_type)
        if not prompt_template:
            return TransformedSection(
                section_type=section_type,
                original_content=content,
                sap_content=content,
                confidence=0.5
            )

        # Build prompt with context
        prompt = prompt_template.format(content=content[:15000])

        if context:
            context_str = f"\nStudy Context: {json.dumps(context)}\n"
            prompt = context_str + prompt

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            sap_content = response.content[0].text.strip()

            return TransformedSection(
                section_type=section_type,
                original_content=content,
                sap_content=sap_content,
                confidence=0.9
            )

        except Exception as e:
            console.print(f"[red]Transform failed for {section_type}: {e}[/red]")
            return TransformedSection(
                section_type=section_type,
                original_content=content,
                sap_content=content,
                confidence=0.0
            )

    def transform_protocol_to_sap(
        self,
        sections: dict[str, str],
        metadata: dict
    ) -> dict[str, TransformedSection]:
        """Transform all protocol sections to SAP format.

        Args:
            sections: Dict mapping section_type to content
            metadata: Study metadata (title, phase, NCT ID, etc.)

        Returns:
            Dict mapping section_type to TransformedSection
        """
        console.print(f"[blue]Transforming {len(sections)} sections to SAP language...[/blue]")

        transformed = {}
        context = {
            "study_title": metadata.get("title", ""),
            "phase": metadata.get("phase", ""),
            "nct_id": metadata.get("nct_id", ""),
        }

        for section_type, content in sections.items():
            console.print(f"  Transforming {section_type}...")
            result = self.transform_section(section_type, content, context)
            if result:
                transformed[section_type] = result

        successful = sum(1 for t in transformed.values() if t.confidence > 0.5)
        console.print(f"[green]Transformed {successful}/{len(sections)} sections successfully[/green]")

        return transformed
