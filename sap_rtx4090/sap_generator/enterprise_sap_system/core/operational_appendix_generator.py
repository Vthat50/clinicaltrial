#!/usr/bin/env python3
"""
Operational Appendix Generator
==============================

Generates the complete operational rules appendix for SAP documents.

This module combines three tiers of information:
- Tier 1: Protocol-specific extractions (visit windows, covariates, etc.)
- Tier 2: Industry standards (study day formulas, baseline rules, etc.)
- Tier 3: Study-type defaults (biosimilar, IO, targeted therapy specifics)

The output is programmer-ready: explicit rules that allow implementation
without asking clarifying questions.
"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import logging

from .operational_extraction_schema import (
    OperationalSpecifications,
    VisitWindow,
    VisitSchedule,
    ModelCovariates,
    ICEFramework,
    ICESpecification,
    CensoringRule,
    InterimTrigger,
    detect_study_type
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION LOADER
# =============================================================================

class OperationalConfigLoader:
    """Loads Tier 2 and Tier 3 configuration files."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize loader with config directory."""
        if config_dir is None:
            # Default to specs/tlf_configs/core/
            self.config_dir = Path(__file__).parent.parent / "specs" / "tlf_configs" / "core"
        else:
            self.config_dir = config_dir

    def load_operational_rules(self) -> Dict[str, Any]:
        """Load Tier 2 industry standards from operational_rules.yaml."""
        rules_path = self.config_dir / "operational_rules.yaml"
        if rules_path.exists():
            with open(rules_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            logger.warning(f"operational_rules.yaml not found at {rules_path}")
            return {}

    def load_study_type_defaults(self) -> Dict[str, Any]:
        """Load Tier 3 study-type defaults from study_type_defaults.yaml."""
        defaults_path = self.config_dir / "study_type_defaults.yaml"
        if defaults_path.exists():
            with open(defaults_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            logger.warning(f"study_type_defaults.yaml not found at {defaults_path}")
            return {}

    def get_defaults_for_study_type(self, study_type: str) -> Dict[str, Any]:
        """Get Tier 3 defaults for a specific study type."""
        all_defaults = self.load_study_type_defaults()
        return all_defaults.get(study_type, {})


# =============================================================================
# OPERATIONAL APPENDIX GENERATOR
# =============================================================================

class OperationalAppendixGenerator:
    """
    Generates the operational rules appendix for SAP documents.

    Combines protocol-specific extractions with industry standards and
    study-type defaults to produce complete, programmer-ready specifications.
    """

    def __init__(
        self,
        tier1_specs: Optional[OperationalSpecifications] = None,
        study_type: str = "general_oncology",
        config_loader: Optional[OperationalConfigLoader] = None
    ):
        """
        Initialize the generator.

        Args:
            tier1_specs: Protocol-specific extractions (Tier 1)
            study_type: Study type for loading Tier 3 defaults
            config_loader: Config loader for Tier 2/3 (uses default if None)
        """
        self.tier1 = tier1_specs or OperationalSpecifications()
        self.study_type = study_type

        self.config_loader = config_loader or OperationalConfigLoader()
        self.tier2 = self.config_loader.load_operational_rules()
        self.tier3 = self.config_loader.get_defaults_for_study_type(study_type)

    def generate_complete_appendix(self) -> str:
        """
        Generate the complete operational rules appendix.

        Returns:
            Formatted markdown text for SAP Appendix C (or equivalent)
        """
        sections = []

        # Header with source attribution legend
        sections.append("# APPENDIX C: OPERATIONAL RULES AND DERIVATIONS\n")
        sections.append("""This appendix provides explicit operational rules for data derivation and analysis.

**Source Attribution Key:**
- **[PROTOCOL]** - Extracted from the study protocol; study-specific
- **[CDISC]** - Per CDISC ADaM/SDTM standards; industry standard
- **[ICH]** - Per ICH E9/E9(R1) guidelines; regulatory standard
- **[FDA/EMA]** - Per FDA or EMA guidance documents; regulatory standard
- **[DEFAULT]** - Study-type default; confirm with protocol if not explicitly stated
""")

        # C.1 Study Day Calculations
        sections.append(self.generate_study_day_section())

        # C.2 Visit Windowing
        sections.append(self.generate_visit_window_section())

        # C.3 Baseline Definition
        sections.append(self.generate_baseline_section())

        # C.4 Laboratory Value Handling
        sections.append(self.generate_lab_handling_section())

        # C.5 Duplicate Record Resolution
        sections.append(self.generate_duplicate_handling_section())

        # C.6 Censoring Rules (detailed tables)
        sections.append(self.generate_censoring_section())

        # C.7 Missing Data Rules
        sections.append(self.generate_missing_data_section())

        # C.8 Rounding Conventions
        sections.append(self.generate_rounding_section())

        # C.9 Population Definitions (PK, PP, Dual Population)
        sections.append(self.generate_populations_section())

        # C.10 Period Definitions (for maintenance studies)
        if self.study_type == "maintenance":
            sections.append(self.generate_period_definitions_section())

        # C.11 Model Covariates
        sections.append(self.generate_covariates_section())

        # C.12 Interim Analysis Timeline (if applicable)
        if self.tier1.interim_analysis and self.tier1.interim_analysis.num_interim > 0:
            sections.append(self.generate_interim_timeline_section())

        return "\n\n".join(sections)

    # =========================================================================
    # SECTION GENERATORS
    # =========================================================================

    def generate_study_day_section(self) -> str:
        """Generate C.1 Study Day Calculations section."""
        study_day_config = self.tier2.get('study_day', {})
        formulas = study_day_config.get('formulas', {})

        text = """## C.1 Study Day Calculations

**[CDISC]** Per CDISC ADaM Implementation Guide (ADaMIG v1.3):

Study Day 1 is defined as the date of first dose of study treatment (TRTSDT).

### C.1.1 Analysis Day (ADY) [CDISC]

**Post-baseline assessments:**
```
ADY = ADT - TRTSDT + 1
```
Where ADY ≥ 1 for assessments on or after first dose.

**Pre-baseline assessments:**
```
ADY = ADT - TRTSDT
```
Where ADY < 0 for assessments before first dose. Note: There is no Day 0.

### C.1.2 Duration Calculations [CDISC]

**Treatment Duration:**
```
TRTDUR = TRTEDT - TRTSDT + 1
```
Duration on treatment in days, inclusive of start and end dates.

**Analysis Duration (general):**
```
ADURN = END_DATE - START_DATE + 1
```
Duration in days, inclusive.

**Response Duration (responders only):**
```
DORDUR = date_of_progression_or_death - date_of_first_response + 1
```

**Follow-up Duration:**
```
FUDY = last_contact_date - RANDDT + 1
```
Days of follow-up from randomization.

### C.1.3 Relative Day Calculations [CDISC]

For analyses relative to events other than first dose:
```
ARDY = ADT - reference_date + 1
```
Where reference_date may be randomization (RANDDT), enrollment, or other protocol-specified anchor.
"""
        return text

    def generate_visit_window_section(self) -> str:
        """Generate C.2 Visit Windowing section with explicit day ranges."""
        text = "## C.2 Visit Windowing\n\n"

        # Get protocol-specific windows if available
        if self.tier1.visit_schedule and self.tier1.visit_schedule.visits:
            text += "### C.2.1 Analysis Visit Windows [PROTOCOL]\n\n"
            text += "**Source:** Protocol-specified visit schedule.\n\n"
            text += "The following visit windows are defined for analysis:\n\n"
            text += "| Visit | Target Day | Window | Study Day Range |\n"
            text += "|-------|------------|--------|------------------|\n"

            for visit in self.tier1.visit_schedule.visits:
                text += f"| {visit.visit_name} | Day {visit.target_day} | "
                text += f"±{visit.window_plus} days | "
                text += f"Day {visit.min_day} - {visit.max_day} |\n"
        else:
            # Use default windows from Tier 2
            text += "### C.2.1 Standard Visit Windows [DEFAULT]\n\n"
            text += "**Source:** Industry standard windowing conventions. *Confirm with protocol.*\n\n"
            text += "| Visit Frequency | Window Size | Example |\n"
            text += "|-----------------|-------------|----------|\n"
            text += "| Weekly (Weeks 1-4) | ±3 days | Week 2 (Day 15): Day 12-18 |\n"
            text += "| Biweekly | ±5 days | Week 4 (Day 29): Day 24-34 |\n"
            text += "| Monthly | ±7 days | Week 8 (Day 57): Day 50-64 |\n"
            text += "| Quarterly | ±14 days | Week 12 (Day 85): Day 71-99 |\n"

        # Window assignment rules from Tier 2
        windowing_rules = self.tier2.get('visit_windowing', {})
        assignment = windowing_rules.get('assignment_rules', {})

        text += """
### C.2.2 Visit Assignment Rules [CDISC]

**Source:** Per CDISC ADaM conventions for analysis visit derivation.

**Primary Rule:** Assessments are assigned to the analysis visit with the closest target day.

**Tie-Breaking:** If equidistant between two visits, assign to the earlier visit.

**Multiple Assessments in Same Window:**
- Continuous variables: Use assessment closest to target day
- Categorical variables: Use worst value
- Tumor assessments: Per RECIST rules for lesion selection

**Assessments Outside All Windows:**
- Excluded from scheduled (windowed) analyses
- Included in safety analyses as unscheduled visits

**Unscheduled Visits:**
- Efficacy analyses: Excluded from scheduled visits
- Safety analyses: Included
- If included, assign to nearest analysis window within range

**Early Termination:**
- Early termination assessments mapped to last scheduled visit window

**Period Boundaries:**
- If assessment falls on period boundary, assign to period containing the target visit day
"""
        return text

    def generate_baseline_section(self) -> str:
        """Generate C.3 Baseline Definition section."""
        baseline_config = self.tier2.get('baseline', {})
        tie_breaking = baseline_config.get('tie_breaking', {})

        text = """## C.3 Baseline Definition

**[CDISC]** Per CDISC ADaM Implementation Guide for baseline (BASE, ABLFL) derivation.

### C.3.1 General Definition [CDISC]

Baseline is defined as the **last non-missing assessment** obtained prior to the first dose of study treatment.

- Pre-dose assessments on Day 1 (prior to first dose) are considered baseline
- If no pre-dose Day 1 assessment is available, the last screening assessment will be used
- Baseline window: Day -28 to Day 1 pre-dose (unless protocol specifies otherwise)

### C.3.2 Tie-Breaking Rules [DEFAULT]

**Source:** Industry standard conventions. *Confirm with protocol if different rules apply.*

When multiple assessments occur on the same day:

| Variable Type | Tie-Breaking Rule |
|---------------|-------------------|
| **Continuous variables** | Mean of all assessments on the same day |
| **Categorical variables** | Last assessment by collection time; if time unavailable, last by entry sequence |
| **Laboratory values (efficacy)** | Last value by collection time |
| **Laboratory values (safety)** | Worst (highest) CTCAE grade |
| **Tumor assessments** | Last adequate tumor assessment per RECIST criteria |
| **Vital signs** | Mean of replicate measurements |
| **ECG parameters** | Mean of triplicate ECG measurements |

### C.3.3 Baseline for Specific Assessments [DEFAULT]

**Tumor Assessments:**
- Baseline tumor burden = sum of target lesion diameters at baseline
- Baseline must include all target lesions and assessment of all non-target lesions

**Laboratory Values:**
- Baseline CTCAE grade derived using same criteria as post-baseline
- For shift tables, baseline grade must be non-missing

**Vital Signs:**
- For blood pressure: mean of 2nd and 3rd readings if 3 taken
- Single reading used if only one taken
"""
        return text

    def generate_lab_handling_section(self) -> str:
        """Generate C.4 Laboratory Value Handling section."""
        lab_config = self.tier2.get('laboratory_handling', {})

        text = """## C.4 Laboratory Value Handling

**[CDISC]** Per CDISC SDTM/ADaM standards for laboratory data.

### C.4.1 Limit of Quantification [DEFAULT]

**Source:** Industry standard conventions for bioanalytical data.

| Situation | Handling Rule | SAS Implementation |
|-----------|--------------|-------------------|
| Below LLOQ | Impute as LLOQ / 2 | `if LBSTRESC = '<X' then AVAL = X/2;` |
| Above ULOQ | Set to ULOQ value | `if LBSTRESC = '>X' then AVAL = X;` |
| Not detected | Set to 0 | `if LBSTRESC = 'NEG' then AVAL = 0;` |

**Note for PK analyses:** Values below LLOQ may be set to LLOQ/2 or 0 depending on PK modeling requirements.

### C.4.2 Unit Conversion [CDISC]

All laboratory values will be converted to standard units before analysis:

| Parameter | Standard Unit |
|-----------|---------------|
| Hemoglobin | g/dL |
| Creatinine | mg/dL |
| Bilirubin | mg/dL |
| ALT/AST | U/L |
| Albumin | g/dL |

### C.4.3 Duplicate Laboratory Values [DEFAULT]

**Same-day duplicates:**
1. Query site for confirmation
2. If unresolved, use value with latest timestamp
3. If no timestamp available, use last entered value

**Unscheduled laboratory assessments:**
- Excluded from scheduled (windowed) efficacy analyses
- Included in all safety analyses
- For shift tables: Include unscheduled if represents worst post-baseline grade

### C.4.4 Local vs Central Laboratory

- Central laboratory values preferred when both available
- Use local laboratory values if central not available
- Sensitivity analysis using local laboratory values may be performed

### C.4.5 CTCAE Grade Derivation

- Grades derived per CTCAE v5.0 criteria
- Baseline grade derived using same criteria as post-baseline
- Shift = change from baseline grade to worst post-baseline grade

### C.4.6 Reference Range Flagging

```
ANRIND = 'L' if AVAL < ANRLO
ANRIND = 'N' if ANRLO <= AVAL <= ANRHI
ANRIND = 'H' if AVAL > ANRHI
```
"""
        return text

    def generate_duplicate_handling_section(self) -> str:
        """Generate C.5 Duplicate Record Resolution section."""
        text = """## C.5 Duplicate Record Resolution

**[DEFAULT]** Industry standard conventions for duplicate handling. *Confirm with protocol if different rules apply.*

### C.5.1 CRF Duplicates [DEFAULT]

Use the most recent entry timestamp when duplicate CRF entries exist.

### C.5.2 Laboratory Duplicates [DEFAULT]

1. Query site for confirmation of duplicate values
2. If unresolved, use value with latest timestamp
3. If no timestamp, use last entered value

### C.5.3 Adverse Event Duplicates [DEFAULT]

Review to determine if records represent the same event:
- Same verbatim term
- Overlapping dates
- Same body system

True duplicates: Merge into single record
Distinct events: Retain as separate records

### C.5.4 Efficacy Assessment Duplicates [RECIST]

**Source:** Per RECIST 1.1 guidelines for tumor response assessment.

Follow RECIST 1.1 rules for:
- Target lesion selection
- Measurement selection when duplicates exist
"""
        return text

    def generate_censoring_section(self) -> str:
        """Generate C.6 Censoring Rules section with complete tables."""
        pfs_rules = self.tier2.get('pfs_censoring', {}).get('rules', [])
        os_rules = self.tier2.get('os_censoring', {}).get('rules', [])
        dor_rules = self.tier2.get('dor_censoring', {}).get('rules', [])

        text = "## C.6 Censoring Rules\n\n"
        text += "**[FDA/EMA]** Per FDA and EMA guidance on censoring rules for time-to-event endpoints in oncology.\n\n"

        # PFS Censoring Table
        text += "### C.6.1 Progression-Free Survival (PFS) Censoring Rules [FDA/EMA]\n\n"
        text += "**Source:** Consistent with FDA Guidance for Industry on Clinical Trial Endpoints for Approval of Cancer Drugs and EMA Guidelines.\n\n"
        text += "| # | Situation | Event/Censored | Date Used | CNSR |\n"
        text += "|---|-----------|----------------|-----------|------|\n"

        if pfs_rules:
            for i, rule in enumerate(pfs_rules, 1):
                text += f"| {i} | {rule.get('situation', '')} | "
                text += f"{rule.get('event_censor', '')} | "
                text += f"{rule.get('date', '')} | {rule.get('cnsr', '')} |\n"
        else:
            # Default PFS censoring rules
            default_pfs = [
                (1, "Documented progression or death", "Event", "Date of progression or death", 0),
                (2, "No baseline tumor assessment", "Censored", "Date of randomization", 1),
                (3, "No post-baseline tumor assessment", "Censored", "Date of randomization", 1),
                (4, "Alive without progression at data cutoff", "Censored", "Date of last adequate tumor assessment", 1),
                (5, "Lost to follow-up", "Censored", "Date of last adequate tumor assessment", 1),
                (6, "Withdrew consent", "Censored", "Date of last adequate assessment before withdrawal", 1),
                (7, "Started new anticancer therapy before progression", "Censored", "Date of last adequate assessment before new therapy", 1),
                (8, "Death without prior documented progression", "Event", "Date of death", 0),
                (9, "Progression after ≥2 missed assessments", "Censored", "Date of last adequate assessment before missed", 1),
                (10, "Clinical progression only (no imaging)", "Event*", "Date of clinical progression", 0),
                (11, "Death after ≥2 missed assessments", "Event", "Date of death", 0),
                (12, "Symptomatic deterioration without radiological confirmation", "Censored*", "Date of last adequate tumor assessment", 1),
            ]
            for num, situation, event_censor, date, cnsr in default_pfs:
                text += f"| {num} | {situation} | {event_censor} | {date} | {cnsr} |\n"

        text += "\n*Protocol-dependent; verify with protocol specifications.\n"

        # OS Censoring Table
        text += "\n### C.6.2 Overall Survival (OS) Censoring Rules [FDA/EMA]\n\n"
        text += "**Source:** Standard survival analysis conventions per regulatory guidance.\n\n"
        text += "| # | Situation | Event/Censored | Date Used | CNSR |\n"
        text += "|---|-----------|----------------|-----------|------|\n"
        text += "| 1 | Death from any cause | Event | Date of death | 0 |\n"
        text += "| 2 | Alive at data cutoff | Censored | Date of last known alive | 1 |\n"
        text += "| 3 | Lost to follow-up | Censored | Date of last contact | 1 |\n"
        text += "| 4 | Withdrew consent for survival follow-up | Censored | Date of last contact before withdrawal | 1 |\n"

        # DOR Censoring Table
        text += "\n### C.6.3 Duration of Response (DOR) Censoring Rules [FDA/EMA]\n\n"
        text += "**Source:** Consistent with regulatory endpoints guidance for responder populations.\n\n"
        text += "**Population:** Subjects who achieved confirmed CR or PR\n\n"
        text += "**Start Date:** Date of first documented response\n\n"
        text += "| # | Situation | Event/Censored | Date Used | CNSR |\n"
        text += "|---|-----------|----------------|-----------|------|\n"
        text += "| 1 | Progression or death after response | Event | Date of progression or death | 0 |\n"
        text += "| 2 | Ongoing response at data cutoff | Censored | Date of last adequate tumor assessment | 1 |\n"
        text += "| 3 | Started new therapy while responding | Censored | Date of last adequate assessment before new therapy | 1 |\n"
        text += "| 4 | Lost to follow-up while responding | Censored | Date of last adequate tumor assessment | 1 |\n"

        return text

    def generate_missing_data_section(self) -> str:
        """Generate C.7 Missing Data Rules section."""
        text = """## C.7 Missing Data Rules

**[ICH]** Per ICH E9(R1) guidance on estimands and missing data handling.

### C.7.1 Incomplete Dates [DEFAULT]

**Source:** Industry standard date imputation conventions. *Confirm with protocol if different rules apply.*

| Missing Component | Start Date Imputation | End Date Imputation |
|-------------------|----------------------|---------------------|
| Day only | First of month | Last of month |
| Month and day | January 1 | December 31 |
| Year | Do not impute | Do not impute |

### C.7.2 Adverse Event Dates [DEFAULT]

- **Ongoing AE at data cutoff:** End date = data cutoff date
- **Resolution unknown:** Treat as ongoing; end date = last known date

### C.7.3 Concomitant Medication Dates [DEFAULT]

- **Ongoing medication:** End date = last dose date or data cutoff, whichever earlier

### C.7.4 Missing Response Assessments [ICH]

**Source:** Per ICH E9(R1) treatment policy strategy for missing outcomes.

For binary endpoints (ORR):
- Missing response assessments imputed as **non-responders** in primary analysis
- Sensitivity analysis may exclude subjects with missing assessments

### C.7.5 Missing Baseline Values [CDISC]

- For change from baseline: Subject excluded from analysis if baseline missing
- For shift tables: Baseline grade required; exclude if missing
"""
        return text

    def generate_rounding_section(self) -> str:
        """Generate C.8 Rounding Conventions section."""
        text = """## C.8 Rounding Conventions

**[DEFAULT]** Industry standard presentation conventions.

### C.8.1 General Rule [DEFAULT]

Round to nearest value; when exactly halfway, round up (e.g., 0.5 → 1).

### C.8.2 Specific Conventions [DEFAULT]

| Statistic | Decimal Places | Format |
|-----------|----------------|--------|
| Percentages | 1 | XX.X% |
| Means | Raw data + 1 | X.XX |
| Standard deviations | Raw data + 2 | X.XXX |
| Medians | Same as raw data | X.X |
| Confidence intervals | Same as point estimate | X.XX |
| Hazard ratios | 2 | X.XX |
| P-values | 4 | 0.XXXX |
| Event counts | 0 | Integer |

### C.8.3 P-value Reporting [DEFAULT]

- Report p-values to 4 decimal places
- If p < 0.0001, report as "<0.0001"
- If p > 0.9999, report as ">0.9999"
"""
        return text

    # =========================================================================
    # ICE AND SENSITIVITY ANALYSIS SECTIONS
    # =========================================================================

    def generate_ice_section(self, endpoint: str = "PFS") -> str:
        """Generate ICE handling section for a specific endpoint."""
        # Check for protocol-specific ICE handling
        if self.tier1.ice_framework and self.tier1.ice_framework.endpoint_ice_mapping:
            for mapping in self.tier1.ice_framework.endpoint_ice_mapping:
                if mapping.endpoint == endpoint:
                    text = f"### Intercurrent Events for {endpoint} [PROTOCOL]\n\n"
                    text += "**Source:** Protocol-specified ICE handling.\n\n"
                    return text + self._format_ice_from_extraction(mapping)

        # Use Tier 3 defaults based on study type
        ice_defaults = self.tier3.get('ice_defaults', {})

        text = f"### Intercurrent Events for {endpoint} [ICH/DEFAULT]\n\n"
        text += "**Source:** Per ICH E9(R1) estimand framework. *Confirm ICE strategies with protocol.*\n\n"

        if endpoint in ["PFS", "OS"]:
            text += """**Treatment Discontinuation:**
- Strategy: Treatment Policy
- Handling: Outcomes assessed regardless of whether treatment was discontinued

**Subsequent Anticancer Therapy:**
- Strategy: Treatment Policy (primary)
- Handling: Events assessed regardless of subsequent therapy
- Sensitivity: Censor at initiation of subsequent therapy (hypothetical strategy)

**Death Before Progression (PFS only):**
- Strategy: Composite
- Handling: Death included as a PFS event

"""
            if self.study_type == "immuno_oncology":
                text += """**Treatment Crossover (if permitted):**
- Strategy: Treatment Policy (primary ITT analysis)
- Sensitivity: RPSFT/IPE adjustment for treatment switching effect
"""

        return text

    def _format_ice_from_extraction(self, mapping) -> str:
        """Format ICE section from extracted specifications."""
        text = f"### Intercurrent Events for {mapping.endpoint}\n\n"

        for ice in mapping.ice_specifications:
            text += f"**{ice.event_name}:**\n"
            text += f"- Strategy: {ice.strategy.value.replace('_', ' ').title()}\n"
            if ice.handling_description:
                text += f"- Handling: {ice.handling_description}\n"
            if ice.sensitivity_strategy:
                text += f"- Sensitivity: {ice.sensitivity_strategy.value.replace('_', ' ').title()}\n"
            text += "\n"

        return text

    def generate_sensitivity_analyses_section(self, endpoint_type: str = "time_to_event") -> str:
        """Generate sensitivity analyses section based on endpoint type."""
        # Get Tier 3 defaults for study type
        sensitivity_defaults = self.tier3.get('sensitivity_analyses', {})

        if isinstance(sensitivity_defaults, list):
            analyses = sensitivity_defaults
        else:
            analyses = sensitivity_defaults.get(endpoint_type, [])

        text = f"### Sensitivity Analyses [ICH/DEFAULT]\n\n"
        text += f"**Source:** Per ICH E9(R1) guidance on sensitivity analyses. Study-type: {self.study_type}.\n\n"
        text += "The following sensitivity analyses will be performed:\n\n"

        # Standard sensitivity analyses
        standard_analyses = [
            ("Per-Protocol Population", "Primary analysis repeated in PP population", True),
            ("Unstratified Analysis", "Log-rank test and Cox model without stratification factors", True),
            ("Investigator Assessment", "Analysis using local investigator assessment", True),
        ]

        if endpoint_type == "time_to_event":
            standard_analyses.extend([
                ("Per-Protocol Censoring", "Patients censored at date of major protocol deviation", False),
                ("Alternative Event Definition", "Using protocol-specified alternative definitions", False),
            ])

            if self.study_type == "immuno_oncology":
                standard_analyses.extend([
                    ("RPSFT Adjustment", "Rank-preserving structural failure time model for treatment crossover", False),
                    ("Tipping Point Analysis", "Sensitivity to missing data assumptions", True),
                    ("Fleming-Harrington Analysis", "G(rho=0, gamma=1) weighted log-rank for delayed effects", False),
                ])

        text += "| Analysis | Description | Required |\n"
        text += "|----------|-------------|----------|\n"
        for name, desc, required in standard_analyses:
            req_str = "Yes" if required else "If applicable"
            text += f"| {name} | {desc} | {req_str} |\n"

        return text

    # =========================================================================
    # DUAL POPULATION AND PK SECTIONS
    # =========================================================================

    def generate_dual_population_section(self) -> str:
        """Generate dual population requirement section (biosimilars)."""
        if self.study_type != "biosimilar":
            return ""

        dual_pop = self.tier3.get('population_requirements', {})

        text = """### Dual Population Requirement

**Equivalence must be demonstrated in BOTH the Intent-to-Treat (ITT) and Per-Protocol (PP) populations.**

The study will be considered successful only if the equivalence margins are met in both populations:
- **ITT Population:** All randomized subjects
- **PP Population:** Subjects without major protocol deviations affecting efficacy

**Rationale:** Per FDA and EMA biosimilar guidance, demonstration of equivalence in both ITT and PP populations is required to establish biosimilarity. The ITT analysis preserves randomization while the PP analysis evaluates the effect in subjects who adhered to the protocol.
"""
        return text

    def generate_pk_population_section(self) -> str:
        """Generate PK population section if applicable."""
        if not self.tier1.populations or not self.tier1.populations.pk_population:
            if self.study_type == "biosimilar":
                # Use Tier 3 default for biosimilars
                pk_req = self.tier3.get('pk_requirements', {})
                return f"""### PK Population

{pk_req.get('pk_population_definition', 'The PK Population includes all subjects who received at least one dose and have at least one evaluable PK sample.')}

**PK Equivalence Criteria:**
{pk_req.get('pk_equivalence_criteria', 'Equivalence concluded if 90% CI for geometric mean ratios within 80.00% to 125.00%.')}
"""
            return ""

        pk_pop = self.tier1.populations.pk_population
        if not pk_pop.included:
            return ""

        text = "### PK Population\n\n"
        text += pk_pop.definition if pk_pop.definition else "The PK Population includes all subjects with at least one evaluable PK sample.\n"

        if pk_pop.required_timepoints:
            text += "\n**Required Sampling Timepoints:**\n"
            for tp in pk_pop.required_timepoints:
                text += f"- {tp}\n"

        if pk_pop.sampling_windows:
            text += "\n**Sampling Windows:**\n"
            for window_name, window_def in pk_pop.sampling_windows.items():
                text += f"- {window_name}: {window_def}\n"

        return text

    # =========================================================================
    # MAIN GENERATION METHODS
    # =========================================================================

    def generate_populations_section(self) -> str:
        """Generate complete populations section with all definitions."""
        text = "## Analysis Populations\n\n"

        # Standard populations
        text += """### Intent-to-Treat (ITT) Population

The ITT Population includes all randomized subjects. Subjects will be analyzed according to randomized treatment assignment.

### Safety Population

The Safety Population includes all subjects who received at least one dose of study treatment. Subjects will be analyzed according to actual treatment received.

### Per-Protocol (PP) Population

The PP Population includes all subjects in the ITT Population without major protocol deviations that could affect the efficacy evaluation.

**Major protocol deviations that exclude from PP:**
- Wrong treatment administered
- Less than 80% of planned dose received (unless due to AE or progression)
- Missing primary endpoint assessment without documented progression
- Major GCP violations affecting data integrity

"""
        # Add dual population if biosimilar
        text += self.generate_dual_population_section()

        # Add PK population if applicable
        text += self.generate_pk_population_section()

        return text

    def generate_covariates_section(self) -> str:
        """Generate explicit model covariates section."""
        # Determine source attribution
        if self.tier1.covariates and self.tier1.covariates.stratification_factors:
            source_tag = "[PROTOCOL]"
            source_text = "**Source:** Protocol-specified stratification factors."
            strat_factors = self.tier1.covariates.stratification_factors
            strat_levels = self.tier1.covariates.stratification_factor_levels
        else:
            source_tag = "[DEFAULT]"
            source_text = "**Source:** Placeholder - extract from protocol. *Confirm stratification factors with protocol.*"
            strat_factors = ["[Stratification Factor 1]", "[Stratification Factor 2]"]
            strat_levels = {}

        text = f"## C.11 Model Covariates {source_tag}\n\n"
        text += f"{source_text}\n\n"

        text += "### C.11.1 Stratification Factors\n\n"
        text += "**Stratification Factors (from randomization):**\n"
        for factor in strat_factors:
            levels = strat_levels.get(factor, [])
            if levels:
                text += f"- **{factor}:** {', '.join(levels)}\n"
            else:
                text += f"- {factor}\n"

        text += "\n### C.11.2 Primary Analysis Model Specification\n\n"
        text += "The primary analysis will include:\n"
        text += "- Treatment group (fixed effect, primary factor of interest)\n"
        text += "- All stratification factors used in randomization\n\n"

        text += "**Critical Requirement:** Both the **stratified log-rank test** AND the **stratified Cox proportional hazards model** will use the **SAME stratification factors** as used in randomization.\n\n"

        text += "### C.11.3 Covariate Handling Rules\n\n"
        text += "| Situation | Handling |\n"
        text += "|-----------|----------|\n"
        text += "| Stratum with <5% of patients | Pool with adjacent stratum |\n"
        text += "| Missing baseline covariate (continuous) | Impute with median |\n"
        text += "| Missing baseline covariate (categorical) | Impute with mode |\n"
        text += "| Stratification factor missing | Use IRT/IWRS stratification value |\n"

        return text

    def generate_period_definitions_section(self) -> str:
        """Generate period definitions section for maintenance studies."""
        text = "## C.10 Period Definitions [PROTOCOL/DEFAULT]\n\n"
        text += "**Source:** Period definitions for maintenance study design.\n\n"

        if self.tier1.periods and self.tier1.periods.periods:
            # Protocol-specific periods
            text += "### C.10.1 Study Periods [PROTOCOL]\n\n"
            for period in self.tier1.periods.periods:
                text += f"**{period.name} Period:**\n"
                text += f"- Start: {period.start_criterion}\n"
                text += f"- End: {period.end_criterion}\n"
                if period.planned_duration:
                    text += f"- Planned Duration: {period.planned_duration}\n"
                text += "\n"

            # Controlled disease definition
            if self.tier1.periods.controlled_disease:
                cd = self.tier1.periods.controlled_disease
                text += "### C.10.2 Controlled Disease Definition [PROTOCOL]\n\n"
                text += f"**Definition:** {cd.definition}\n\n"
                if cd.qualifying_responses:
                    text += f"**Qualifying Responses:** {', '.join(cd.qualifying_responses)}\n\n"
                if cd.assessment_timing:
                    text += f"**Assessment Timing:** {cd.assessment_timing}\n\n"
                if cd.additional_criteria:
                    text += "**Additional Criteria:**\n"
                    for crit in cd.additional_criteria:
                        text += f"- {crit}\n"
        else:
            # Default maintenance periods
            text += "### C.10.1 Study Periods [DEFAULT]\n\n"
            text += """**Induction Period:**
- Start: First dose of study treatment
- End: Completion of planned induction cycles or disease progression
- Typical Duration: 4-6 cycles (12-18 weeks)

**Maintenance Period:**
- Start: Controlled disease at end of induction assessment
- End: Disease progression, unacceptable toxicity, or withdrawal
- Duration: Until progression

### C.10.2 Controlled Disease Definition [DEFAULT]

**Definition:** Subjects with CR, PR, or SD at the end-of-induction tumor assessment.

**Qualifying Responses:** CR (Complete Response), PR (Partial Response), SD (Stable Disease)

**Assessment Timing:** End of induction assessment (typically Week 12-18)

*Confirm controlled disease definition with protocol.*
"""
        return text

    def generate_interim_timeline_section(self) -> str:
        """Generate interim analysis timeline section."""
        text = "## C.12 Interim Analysis Timeline [PROTOCOL]\n\n"

        if self.tier1.interim_analysis:
            ia = self.tier1.interim_analysis
            text += f"**Number of Interim Analyses:** {ia.num_interim}\n\n"

            if ia.alpha_spending_function:
                text += f"**Alpha Spending Function:** {ia.alpha_spending_function}\n\n"

            if ia.futility_boundary:
                text += f"**Futility Boundary:** {ia.futility_boundary}\n\n"

            # Triggers
            if ia.triggers:
                text += "### Interim Analysis Triggers\n\n"
                text += "| Analysis | Trigger Type | Trigger Value | Expected Timing |\n"
                text += "|----------|--------------|---------------|------------------|\n"
                for trigger in ia.triggers:
                    trigger_val = ""
                    if trigger.event_count:
                        trigger_val = f"{trigger.event_count} events"
                    elif trigger.calendar_time:
                        trigger_val = trigger.calendar_time
                    elif trigger.information_fraction:
                        trigger_val = f"{trigger.information_fraction*100:.0f}% IF"
                    text += f"| IA{trigger.analysis_number} | {trigger.trigger_type} | {trigger_val} | {trigger.expected_date} |\n"
                text += "\n"

            # Calendar milestones
            if ia.one_year_report:
                text += f"### Calendar Milestones\n\n"
                text += f"**1-Year Report:** {ia.one_year_report}\n\n"

            if ia.regulatory_submission_analysis:
                text += f"**Regulatory Submission Analysis:** {ia.regulatory_submission_analysis}\n\n"

            # DSMB
            if ia.dsmb_review:
                text += "### Data Safety Monitoring Board (DSMB)\n\n"
                text += "DSMB review is required for interim analyses.\n"
                if ia.dsmb_frequency:
                    text += f"**Review Frequency:** {ia.dsmb_frequency}\n"
        else:
            text += "*No interim analyses specified. Confirm with protocol.*\n"

        return text


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def generate_operational_appendix(
    tier1_specs: Optional[OperationalSpecifications] = None,
    study_type: str = "general_oncology"
) -> str:
    """
    Convenience function to generate operational appendix.

    Args:
        tier1_specs: Protocol-specific extractions
        study_type: Study type for defaults

    Returns:
        Complete operational appendix as markdown text
    """
    generator = OperationalAppendixGenerator(
        tier1_specs=tier1_specs,
        study_type=study_type
    )
    return generator.generate_complete_appendix()
