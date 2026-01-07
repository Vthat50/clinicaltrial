#!/usr/bin/env python3
"""
Fact Extractor (Tiered Regulatory Approach)
============================================

Four-tier extraction based on ICH E9/FDA requirements:
1. TIER 1: Regulatory Required (14 fields) - Every trial, no exceptions
2. TIER 2: Phase-Specific Required - Based on Phase 1 vs Phase 2/3
3. TIER 3: Oncology-Specific - Universal for oncology trials
4. TIER 4: Conditional - Based on detected conditions
5. OPEN: Protocol-specific details Claude finds
"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# Use OpenAI if key available, otherwise Anthropic
if os.environ.get('OPENAI_API_KEY'):
    from openai import OpenAI
    _USE_OPENAI = True
else:
    from anthropic import Anthropic
    _USE_OPENAI = False


@dataclass
class ProtocolFacts:
    """
    Tiered extraction results.
    """
    # =========================================================================
    # TIER 1: Regulatory Required (15 fields - ICH E9/FDA - every trial)
    # =========================================================================
    study_title: Optional[str] = None
    study_name: Optional[str] = None  # Short name/acronym (e.g., "KATHERINE", "KEYNOTE-001")
    protocol_number: Optional[str] = None
    nct_id: Optional[str] = None
    phase: Optional[str] = None
    sponsor: Optional[str] = None
    primary_endpoint: Optional[str] = None
    primary_endpoint_definition: Optional[str] = None
    endpoint_type: Optional[str] = None  # Binary, Time-to-Event, Continuous
    sample_size: Optional[str] = None
    alpha: Optional[str] = None
    power: Optional[str] = None
    randomization_ratio: Optional[str] = None
    blinding: Optional[str] = None
    analysis_populations: Optional[str] = None
    primary_analysis_method: Optional[str] = None

    # =========================================================================
    # TIER 2: Phase-Specific (conditional on phase)
    # =========================================================================
    # Phase 1 (Dose-Finding)
    dlt_definition: Optional[str] = None
    dose_escalation_method: Optional[str] = None
    mtd_definition: Optional[str] = None
    evaluation_window: Optional[str] = None
    starting_dose: Optional[str] = None
    dose_levels: Optional[List[str]] = None

    # Phase 2/3 (Efficacy)
    effect_size: Optional[str] = None
    interim_analysis: Optional[str] = None
    stopping_rules: Optional[str] = None
    alpha_spending: Optional[str] = None
    stratification_factors: Optional[List[str]] = None
    multiplicity_adjustment: Optional[str] = None

    # =========================================================================
    # TIER 3: Oncology-Specific
    # =========================================================================
    indication: Optional[str] = None
    treatment_setting: Optional[str] = None
    study_drug: Optional[str] = None
    comparator: Optional[str] = None
    response_criteria: Optional[str] = None
    safety_population_definition: Optional[str] = None

    # =========================================================================
    # TIER 4: Conditional (based on detected conditions)
    # =========================================================================
    # IF interim_analysis = Yes
    interim_analysis_timing: Optional[str] = None

    # IF time-to-event endpoint
    interim_events: Optional[str] = None
    final_events: Optional[str] = None
    hazard_ratio: Optional[str] = None
    median_survival_assumption: Optional[str] = None
    censoring_rules: Optional[str] = None

    # IF primary = ORR
    orr_definition: Optional[str] = None

    # IF secondary includes DoR
    dor_definition: Optional[str] = None

    # IF biomarker-selected
    biomarker_population: Optional[str] = None

    # IF crossover allowed
    crossover_rules: Optional[str] = None

    # IF NI design
    non_inferiority_margin: Optional[str] = None

    # =========================================================================
    # OPEN EXTRACTION (Protocol-specific - varies per protocol)
    # =========================================================================
    extracted: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for Layer 2."""
        result = {}

        # All fields except 'extracted'
        for field_name in [
            # Tier 1
            "study_title", "study_name", "protocol_number", "nct_id", "phase", "sponsor",
            "primary_endpoint", "primary_endpoint_definition",
            "sample_size", "alpha", "power",
            "randomization_ratio", "blinding",
            "analysis_populations", "primary_analysis_method",
            # Tier 2 - Phase 1
            "dlt_definition", "dose_escalation_method", "mtd_definition",
            "evaluation_window", "starting_dose", "dose_levels",
            # Tier 2 - Phase 2/3
            "effect_size", "interim_analysis", "stopping_rules",
            "alpha_spending", "stratification_factors", "multiplicity_adjustment",
            # Tier 3 - Oncology
            "indication", "treatment_setting", "study_drug", "comparator",
            "response_criteria", "safety_population_definition",
            # Tier 4 - Conditional
            "interim_analysis_timing", "interim_events", "final_events",
            "hazard_ratio", "median_survival_assumption", "censoring_rules",
            "orr_definition", "dor_definition", "biomarker_population",
            "crossover_rules", "non_inferiority_margin"
        ]:
            value = getattr(self, field_name, None)
            if value is not None and value != [] and value != "":
                result[field_name] = value

        # Add open extraction
        if self.extracted:
            result["protocol_specific"] = self.extracted

        return result

    def to_formatted_string(self) -> str:
        """Format for LLM prompt."""
        lines = ["## EXTRACTED PROTOCOL FACTS", ""]

        # Tier 1
        lines.append("### TIER 1: Regulatory Required (ICH E9/FDA)")
        tier1 = [
            ("Study Title", self.study_title),
            ("Study Name", self.study_name),
            ("Protocol Number", self.protocol_number),
            ("NCT ID", self.nct_id),
            ("Phase", self.phase),
            ("Sponsor", self.sponsor),
            ("Primary Endpoint", self.primary_endpoint),
            ("Primary Endpoint Definition", self.primary_endpoint_definition),
            ("Sample Size", self.sample_size),
            ("Alpha", self.alpha),
            ("Power", self.power),
            ("Randomization Ratio", self.randomization_ratio),
            ("Blinding", self.blinding),
            ("Analysis Populations", self.analysis_populations),
            ("Primary Analysis Method", self.primary_analysis_method),
        ]
        for label, value in tier1:
            status = value if value else "[NOT FOUND]"
            lines.append(f"- **{label}**: {status}")

        # Tier 2 - Phase 1
        if self.phase and "1" in self.phase:
            lines.append("")
            lines.append("### TIER 2: Phase 1 (Dose-Finding)")
            tier2_p1 = [
                ("DLT Definition", self.dlt_definition),
                ("Dose Escalation Method", self.dose_escalation_method),
                ("MTD Definition", self.mtd_definition),
                ("Evaluation Window", self.evaluation_window),
                ("Starting Dose", self.starting_dose),
                ("Dose Levels", self.dose_levels),
            ]
            for label, value in tier2_p1:
                if value:
                    lines.append(f"- **{label}**: {value}")

        # Tier 2 - Phase 2/3
        if self.phase and ("2" in self.phase or "3" in self.phase):
            lines.append("")
            lines.append("### TIER 2: Phase 2/3 (Efficacy)")
            tier2_p23 = [
                ("Effect Size", self.effect_size),
                ("Interim Analysis", self.interim_analysis),
                ("Stopping Rules", self.stopping_rules),
                ("Alpha Spending", self.alpha_spending),
                ("Stratification Factors", self.stratification_factors),
                ("Multiplicity Adjustment", self.multiplicity_adjustment),
            ]
            for label, value in tier2_p23:
                if value:
                    lines.append(f"- **{label}**: {value}")

        # Tier 3
        lines.append("")
        lines.append("### TIER 3: Oncology-Specific")
        tier3 = [
            ("Indication", self.indication),
            ("Treatment Setting", self.treatment_setting),
            ("Study Drug", self.study_drug),
            ("Comparator", self.comparator),
            ("Response Criteria", self.response_criteria),
            ("Safety Population Definition", self.safety_population_definition),
        ]
        for label, value in tier3:
            if value:
                lines.append(f"- **{label}**: {value}")

        # Tier 4 - Conditional
        tier4_fields = [
            ("Interim Analysis Timing", self.interim_analysis_timing),
            ("Interim Events", self.interim_events),
            ("Final Events", self.final_events),
            ("Hazard Ratio", self.hazard_ratio),
            ("Median Survival Assumption", self.median_survival_assumption),
            ("Censoring Rules", self.censoring_rules),
            ("ORR Definition", self.orr_definition),
            ("DoR Definition", self.dor_definition),
            ("Biomarker Population", self.biomarker_population),
            ("Crossover Rules", self.crossover_rules),
            ("Non-Inferiority Margin", self.non_inferiority_margin),
        ]
        tier4_present = [(l, v) for l, v in tier4_fields if v]
        if tier4_present:
            lines.append("")
            lines.append("### TIER 4: Conditional Fields")
            for label, value in tier4_present:
                lines.append(f"- **{label}**: {value}")

        # Open extraction
        if self.extracted:
            lines.append("")
            lines.append("### Protocol-Specific Details")
            lines.append(self._format_extracted(self.extracted, indent=0))

        return "\n".join(lines)

    def _format_extracted(self, data: Any, indent: int = 0) -> str:
        """Recursively format extracted data."""
        lines = []
        prefix = "  " * indent

        if isinstance(data, dict):
            for key, value in data.items():
                key_fmt = key.replace("_", " ").title()
                if isinstance(value, (dict, list)) and value:
                    lines.append(f"{prefix}- **{key_fmt}**:")
                    lines.append(self._format_extracted(value, indent + 1))
                elif value:
                    lines.append(f"{prefix}- **{key_fmt}**: {value}")
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    lines.append(self._format_extracted(item, indent))
                elif item:
                    lines.append(f"{prefix}  - {item}")
        elif data:
            lines.append(f"{prefix}{data}")

        return "\n".join(lines)


class FactExtractor:
    """
    Tiered fact extractor based on ICH E9/FDA requirements.
    """

    def __init__(self):
        if _USE_OPENAI:
            self.client = OpenAI()
            self.use_openai = True
        else:
            self.client = Anthropic()
            self.use_openai = False

    def extract(self, protocol_text: str) -> ProtocolFacts:
        """Extract facts from protocol text using tiered approach."""

        # Truncate to ~80K chars to stay under token limits
        max_chars = 80000
        if len(protocol_text) > max_chars:
            protocol_text = protocol_text[:max_chars]

        prompt = f"""You are extracting facts from a clinical trial protocol for SAP generation.

## TASK
Extract ALL statistically relevant information using the tiered approach below.
COPY text exactly as written. If a field is not found, return null.

## TIER 1: REGULATORY REQUIRED (ICH E9/FDA - Every Trial)
These 15 fields are MANDATED. Extract for every protocol.

| Field | Source | Description |
|-------|--------|-------------|
| study_title | ICH E3/E9 | Exact protocol title |
| study_name | Protocol | Short name or acronym (e.g., "KATHERINE", "KEYNOTE-001", "CheckMate-067") |
| protocol_number | Regulatory ID | Protocol identifier |
| nct_id | ClinicalTrials.gov | NCT number |
| phase | ICH E8 | Phase 1, 1b, 2, 3, etc. |
| sponsor | ICH E6 GCP | Sponsor name |
| primary_endpoint | ICH E9 §2.2.2 | The ONE primary endpoint |
| primary_endpoint_definition | ICH E9 | Precise definition as used in analysis |
| endpoint_type | ICH E9 | Type: "Binary", "Time-to-Event", "Continuous", or "Count" |
| sample_size | ICH E9 §3.5 | Total N with breakdown |
| alpha | ICH E9 | Type I error with sidedness (e.g., "0.025 one-sided") |
| power | ICH E9 | Statistical power (e.g., "90%") |
| randomization_ratio | ICH E9 §2.3.2 | Ratio (e.g., "1:1", "2:1") |
| blinding | ICH E9 §2.3.1 | Double-blind, Open-label, etc. |
| analysis_populations | ICH E9 §5.2 | ITT, mITT, PP, Safety definitions |
| primary_analysis_method | ICH E9 §5.1 | Statistical test (e.g., "Stratified log-rank") |

## TIER 2: PHASE-SPECIFIC REQUIRED

### Phase 1 (Dose-Finding) - Extract if Phase 1/1a/1b:
| Field | Description |
|-------|-------------|
| dlt_definition | Exact DLT criteria |
| dose_escalation_method | 3+3, BOIN, CRM, mTPI, etc. |
| mtd_definition | How MTD is determined |
| evaluation_window | DLT evaluation period (e.g., "28 days") |
| starting_dose | First dose level |
| dose_levels | List of planned dose levels |

### Phase 2/3 (Efficacy) - Extract if Phase 2/3:
| Field | Description |
|-------|-------------|
| effect_size | HR, OR, difference assumption |
| interim_analysis | Yes/No and brief description |
| stopping_rules | Efficacy/futility rules |
| alpha_spending | Lan-DeMets, O'Brien-Fleming, etc. |
| stratification_factors | List of stratification factors |
| multiplicity_adjustment | Hochberg, Bonferroni, hierarchical, etc. |

## TIER 3: ONCOLOGY-SPECIFIC (Extract for all oncology trials)
| Field | Description |
|-------|-------------|
| indication | Cancer type (NSCLC, Breast, etc.) |
| treatment_setting | 1L, 2L, adjuvant, neoadjuvant, metastatic |
| study_drug | Active treatment name |
| comparator | Control arm (placebo, SOC, etc.) |
| response_criteria | RECIST 1.1, iRECIST, Lugano, etc. |
| safety_population_definition | Definition of safety analysis set |

## TIER 4: CONDITIONAL (Extract only if condition applies)

### IF interim_analysis = Yes:
| Field | Description |
|-------|-------------|
| interim_analysis_timing | When IAs occur (e.g., "50% and 75% of events") |

### IF time-to-event endpoint (PFS, OS, DFS, EFS):
| Field | Description |
|-------|-------------|
| interim_events | Number of events at each IA |
| final_events | Total events for final analysis |
| hazard_ratio | Assumed HR for sample size |
| median_survival_assumption | Assumed median in control arm |
| censoring_rules | How censoring is handled |

### IF primary = ORR:
| Field | Description |
|-------|-------------|
| orr_definition | Complete definition of response |

### IF secondary includes DoR:
| Field | Description |
|-------|-------------|
| dor_definition | How duration of response is calculated |

### IF biomarker-selected trial:
| Field | Description |
|-------|-------------|
| biomarker_population | Biomarker criteria and testing |

### IF crossover allowed:
| Field | Description |
|-------|-------------|
| crossover_rules | When/how crossover occurs |

### IF non-inferiority design:
| Field | Description |
|-------|-------------|
| non_inferiority_margin | NI margin with justification |

## OPEN EXTRACTION
After extracting all tiered fields, extract ANYTHING ELSE statistically relevant.
This is CRITICAL for accurate SAP generation. Look for:

1. **secondary_endpoints**: List ALL secondary endpoints with their definitions
2. **exploratory_endpoints**: List exploratory/tertiary endpoints
3. **pro_endpoints**: Patient-reported outcome measures (e.g., EORTC QLQ-C30, EQ-5D, PRO-CTCAE)
4. **hypotheses**: Formal hypotheses (H1, H2, H3...) with descriptions
5. **subgroup_analyses**: Planned subgroup analyses and variables
6. **sensitivity_analyses**: All planned sensitivity analyses
7. **missing_data_handling**: Imputation methods, censoring rules
8. **alpha_allocation**: How alpha is split across endpoints/hypotheses
9. **multiplicity_strategy**: Gatekeeping, hierarchical testing details
10. **treatment_arms**: Detailed treatment arm descriptions including doses
11. **estimands**: ICH E9(R1) estimand framework details
12. **intercurrent_events**: How intercurrent events are handled

Structure open extraction with these keys. Include EVERYTHING found - this data is essential.

## OUTPUT FORMAT (JSON)
{{
    "tier1": {{
        "study_title": "...",
        "study_name": "...",
        "protocol_number": "...",
        "nct_id": "...",
        "phase": "...",
        "sponsor": "...",
        "primary_endpoint": "...",
        "primary_endpoint_definition": "...",
        "sample_size": "...",
        "alpha": "...",
        "power": "...",
        "randomization_ratio": "...",
        "blinding": "...",
        "analysis_populations": "...",
        "primary_analysis_method": "..."
    }},
    "tier2_phase1": {{
        "dlt_definition": "...",
        "dose_escalation_method": "...",
        "mtd_definition": "...",
        "evaluation_window": "...",
        "starting_dose": "...",
        "dose_levels": ["...", "..."]
    }},
    "tier2_phase23": {{
        "effect_size": "...",
        "interim_analysis": "...",
        "stopping_rules": "...",
        "alpha_spending": "...",
        "stratification_factors": ["...", "..."],
        "multiplicity_adjustment": "..."
    }},
    "tier3_oncology": {{
        "indication": "...",
        "treatment_setting": "...",
        "study_drug": "...",
        "comparator": "...",
        "response_criteria": "...",
        "safety_population_definition": "..."
    }},
    "tier4_conditional": {{
        "interim_analysis_timing": "...",
        "interim_events": "...",
        "final_events": "...",
        "hazard_ratio": "...",
        "median_survival_assumption": "...",
        "censoring_rules": "...",
        "orr_definition": "...",
        "dor_definition": "...",
        "biomarker_population": "...",
        "crossover_rules": "...",
        "non_inferiority_margin": "..."
    }},
    "open_extraction": {{
        // Structure based on what's in THIS protocol
    }}
}}

## PROTOCOL TEXT
{protocol_text}

Return ONLY the JSON:"""

        if self.use_openai:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = response.choices[0].message.content.strip()
        else:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = response.content[0].text.strip()

        # Clean markdown
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        try:
            data = json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            print(f"[FactExtractor] JSON parse error: {e}")
            print(f"[FactExtractor] Response: {response_text[:500]}")
            return ProtocolFacts()

        # Build ProtocolFacts
        facts = ProtocolFacts()

        # Tier 1
        t1 = data.get("tier1", {})
        facts.study_title = t1.get("study_title")
        facts.study_name = t1.get("study_name")
        facts.protocol_number = t1.get("protocol_number")
        facts.nct_id = t1.get("nct_id")
        facts.phase = t1.get("phase")
        facts.sponsor = t1.get("sponsor")
        facts.primary_endpoint = t1.get("primary_endpoint")
        facts.primary_endpoint_definition = t1.get("primary_endpoint_definition")
        facts.sample_size = t1.get("sample_size")
        facts.alpha = t1.get("alpha")
        facts.power = t1.get("power")
        facts.randomization_ratio = t1.get("randomization_ratio")
        facts.blinding = t1.get("blinding")
        facts.analysis_populations = t1.get("analysis_populations")
        facts.primary_analysis_method = t1.get("primary_analysis_method")

        # Tier 2 - Phase 1
        t2p1 = data.get("tier2_phase1", {})
        facts.dlt_definition = t2p1.get("dlt_definition")
        facts.dose_escalation_method = t2p1.get("dose_escalation_method")
        facts.mtd_definition = t2p1.get("mtd_definition")
        facts.evaluation_window = t2p1.get("evaluation_window")
        facts.starting_dose = t2p1.get("starting_dose")
        facts.dose_levels = t2p1.get("dose_levels")

        # Tier 2 - Phase 2/3
        t2p23 = data.get("tier2_phase23", {})
        facts.effect_size = t2p23.get("effect_size")
        facts.interim_analysis = t2p23.get("interim_analysis")
        facts.stopping_rules = t2p23.get("stopping_rules")
        facts.alpha_spending = t2p23.get("alpha_spending")
        facts.stratification_factors = t2p23.get("stratification_factors")
        facts.multiplicity_adjustment = t2p23.get("multiplicity_adjustment")

        # Tier 3 - Oncology
        t3 = data.get("tier3_oncology", {})
        facts.indication = t3.get("indication")
        facts.treatment_setting = t3.get("treatment_setting")
        facts.study_drug = t3.get("study_drug")
        facts.comparator = t3.get("comparator")
        facts.response_criteria = t3.get("response_criteria")
        facts.safety_population_definition = t3.get("safety_population_definition")

        # Tier 4 - Conditional
        t4 = data.get("tier4_conditional", {})
        facts.interim_analysis_timing = t4.get("interim_analysis_timing")
        facts.interim_events = t4.get("interim_events")
        facts.final_events = t4.get("final_events")
        facts.hazard_ratio = t4.get("hazard_ratio")
        facts.median_survival_assumption = t4.get("median_survival_assumption")
        facts.censoring_rules = t4.get("censoring_rules")
        facts.orr_definition = t4.get("orr_definition")
        facts.dor_definition = t4.get("dor_definition")
        facts.biomarker_population = t4.get("biomarker_population")
        facts.crossover_rules = t4.get("crossover_rules")
        facts.non_inferiority_margin = t4.get("non_inferiority_margin")

        # Open extraction
        facts.extracted = data.get("open_extraction", {})

        return facts


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    test_text = """
    PROTOCOL TITLE: A Phase 3, Randomized, Double-Blind Study of ABC-123
    vs Placebo in First-Line Advanced NSCLC

    Protocol: ABC-123-301
    Sponsor: Pharma Inc.
    NCT05999999

    STUDY DESIGN
    Phase 3, randomized, double-blind, placebo-controlled.
    Randomization 2:1 (ABC-123 : Placebo).
    Stratification: ECOG PS (0 vs 1), PD-L1 (<50% vs ≥50%), smoking status.

    ENDPOINTS
    Primary: Progression-free survival (PFS) per RECIST 1.1
    PFS defined as time from randomization to progression or death.

    Secondary: OS, ORR, DOR, DCR

    ORR = CR + PR per RECIST 1.1, confirmed at ≥4 weeks.
    DOR = time from first response to progression or death.

    SAMPLE SIZE
    N = 600 (400 ABC-123, 200 placebo)
    Assumptions: HR = 0.70, median PFS control = 6 months
    Alpha = 0.025 one-sided, Power = 90%
    Final analysis at 400 PFS events.

    INTERIM ANALYSIS
    Two IAs at 50% (200 events) and 75% (300 events) of final PFS events.
    Lan-DeMets with O'Brien-Fleming boundaries.
    Futility: conditional power < 20%.

    ANALYSIS POPULATIONS
    ITT: All randomized patients
    Safety: All patients receiving ≥1 dose
    PP: ITT without major protocol deviations

    STATISTICAL METHODS
    Primary: Stratified log-rank test
    HR from stratified Cox model with 95% CI
    Censoring: Last known alive date if no progression

    CROSSOVER
    Placebo patients may cross to ABC-123 after confirmed progression.
    RPSFT analysis for OS sensitivity.
    """

    print("Testing Tiered Fact Extractor")
    print("=" * 60)

    extractor = FactExtractor()
    facts = extractor.extract(test_text)

    print("\n" + facts.to_formatted_string())
    print("\n" + "=" * 60)
    print("Raw dict:")
    print(json.dumps(facts.to_dict(), indent=2))
