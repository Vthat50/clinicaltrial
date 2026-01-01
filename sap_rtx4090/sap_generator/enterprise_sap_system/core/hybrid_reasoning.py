#!/usr/bin/env python3
"""
Hybrid Reasoning Engine for SAP Generation
===========================================

Implements the correct reasoning approach for each SAP section:

| Section           | Reasoning Type   | Why                                    |
|-------------------|------------------|----------------------------------------|
| Populations       | Decision Tree    | Clear if-then logic, binary conditions |
| Derivations       | Decision Tree    | Explicit algorithms, deterministic     |
| Arms              | Regex            | Simple pattern matching                |
| Stratification    | RAG              | Domain-specific, learn from examples   |
| Endpoints         | RAG              | Complex, domain-specific criteria      |
| TEAE Logic        | Decision Tree    | Standard logic structure               |
| Follow-up Window  | RAG              | Extract from variable prose            |
| Methods           | RAG              | Method -> code mapping, high variation |

Key Principle: Use the SIMPLEST approach that works for each section.
- Decision Tree: When logic is deterministic and rules are known
- RAG: When we need to learn patterns from examples
- Regex: When extraction is simple pattern matching
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class ReasoningType(Enum):
    """Types of reasoning used for different sections"""
    DECISION_TREE = "decision_tree"  # Deterministic rule-based
    RAG = "rag"                      # Retrieval-augmented generation
    REGEX = "regex"                  # Pattern matching extraction
    TEMPLATE = "template"            # Simple template filling (fallback)


@dataclass
class ReasoningResult:
    """Result from any reasoning approach"""
    content: str
    reasoning_type: ReasoningType
    confidence: float = 1.0
    sources: List[str] = field(default_factory=list)
    rules_applied: List[str] = field(default_factory=list)
    rag_examples_used: List[str] = field(default_factory=list)


# =============================================================================
# DECISION TREE IMPLEMENTATIONS
# =============================================================================

class PopulationDecisionTree:
    """
    Decision Tree for Analysis Populations

    Rules:
    1. If randomized trial -> ITT = All randomized
    2. If single-arm -> ITT = All enrolled who received treatment
    3. FAS = ITT + at least one dose + at least one post-baseline assessment
    4. PP = FAS - protocol violations
    5. Safety = All who received at least one dose
    6. PK Population = If PK endpoints exist
    """

    def generate(self, facts: Dict[str, Any]) -> ReasoningResult:
        """Generate populations section using decision tree logic"""
        rules_applied = []

        # Extract key facts
        is_single_arm = facts.get('is_single_arm', False)
        is_randomized = facts.get('num_arms', 1) > 1 and not is_single_arm
        has_pk = self._has_pk_endpoints(facts)
        drug_name = facts.get('drug_name', 'study drug')

        # RULE 1: ITT Population definition
        if is_randomized:
            itt_def = "All patients who were randomized to treatment, regardless of whether they received study medication."
            rules_applied.append("RULE: Randomized trial -> ITT = All randomized")
        else:
            itt_def = f"All patients who were enrolled and received at least one dose of {drug_name}."
            rules_applied.append("RULE: Single-arm trial -> ITT = All enrolled + treated")

        # RULE 2: FAS Population (primary efficacy)
        if is_randomized:
            fas_def = "All randomized patients who received at least one dose of study medication and have at least one post-baseline efficacy assessment."
        else:
            fas_def = "All enrolled patients who received at least one dose of study medication and have at least one post-baseline efficacy assessment."
        rules_applied.append("RULE: FAS = ITT + dose + post-baseline assessment")

        # RULE 3: Per-Protocol Population
        pp_def = "All patients in the FAS who completed the study without major protocol deviations that could affect efficacy assessment."
        pp_exclusions = self._get_pp_exclusions(facts)
        rules_applied.append("RULE: PP = FAS - protocol violations")

        # RULE 4: Safety Population
        safety_def = f"All patients who received at least one dose of {drug_name}."
        rules_applied.append("RULE: Safety = All who received >= 1 dose")

        # RULE 5: PK Population (conditional)
        pk_section = ""
        if has_pk:
            pk_def = f"All patients in the Safety Population who have at least one measurable post-dose pharmacokinetic sample for {drug_name}."
            pk_section = f"""
### 4.5 Pharmacokinetic (PK) Population

{pk_def}

Patients will be excluded from PK analysis if:
- PK samples are missing or inadequate
- Dosing time records are incomplete
- Sample handling deviations occurred
"""
            rules_applied.append("RULE: PK endpoints exist -> Include PK population")

        # Build output
        content = f"""## 4. ANALYSIS POPULATIONS

### 4.1 Intent-to-Treat (ITT) Population

{itt_def}

This population will be used for sensitivity analyses of efficacy endpoints.

### 4.2 Full Analysis Set (FAS)

{fas_def}

This is the **primary analysis population** for efficacy analyses.

### 4.3 Per-Protocol (PP) Population

{pp_def}

**Major protocol deviations leading to exclusion from PP:**
{pp_exclusions}

This population will be used for supportive efficacy analyses.

### 4.4 Safety Population

{safety_def}

This is the primary analysis population for all safety analyses.
{pk_section}
### 4.6 Population Summary

| Population | Definition | Primary Use |
|------------|------------|-------------|
| ITT | {self._short_def(itt_def)} | Sensitivity analysis |
| FAS | {self._short_def(fas_def)} | **PRIMARY EFFICACY** |
| PP | {self._short_def(pp_def)} | Supportive efficacy |
| Safety | {self._short_def(safety_def)} | **SAFETY ANALYSIS** |
"""

        return ReasoningResult(
            content=content,
            reasoning_type=ReasoningType.DECISION_TREE,
            confidence=0.95,
            rules_applied=rules_applied
        )

    def _has_pk_endpoints(self, facts: Dict[str, Any]) -> bool:
        """Check if protocol has PK endpoints"""
        pk_indicators = ['pharmacokinetic', 'pk ', 'cmax', 'auc', 'tmax', 'half-life']
        text = str(facts).lower()
        return any(ind in text for ind in pk_indicators)

    def _get_pp_exclusions(self, facts: Dict[str, Any]) -> str:
        """Get PP exclusion criteria based on study type"""
        exclusions = [
            "- Did not receive minimum required doses of study medication",
            "- Received prohibited concomitant medications",
            "- Had major deviations from visit schedule (>20% of visits missed)",
            "- Had significant protocol violations affecting efficacy assessment"
        ]

        # Add study-specific exclusions
        if facts.get('is_blinded'):
            exclusions.append("- Had unblinding events")

        return "\n".join(exclusions)

    def _short_def(self, definition: str) -> str:
        """Create short version for table"""
        return definition[:60] + "..." if len(definition) > 60 else definition


class DerivationDecisionTree:
    """
    Decision Tree for Variable Derivations

    Rules based on endpoint type and analysis requirements.
    """

    def generate(self, facts: Dict[str, Any]) -> ReasoningResult:
        """Generate derivations section using decision tree logic"""
        rules_applied = []

        endpoint_type = self._classify_endpoint(facts)
        drug_name = facts.get('drug_name', 'study drug')
        primary_timepoint = facts.get('primary_timepoint', 'Week 12')

        # RULE 1: Baseline derivation
        baseline_rules = self._get_baseline_rules(facts)
        rules_applied.append("RULE: Baseline = Last non-missing pre-first-dose assessment")

        # RULE 2: Change from baseline
        cfb_rules = self._get_cfb_rules(facts)
        rules_applied.append("RULE: CFB = Post-baseline value - Baseline value")

        # RULE 3: Response derivation based on endpoint type
        response_rules = self._get_response_rules(endpoint_type, facts)
        rules_applied.append(f"RULE: {endpoint_type} endpoint -> {self._get_response_method(endpoint_type)}")

        # RULE 4: Analysis visit windows
        window_rules = self._get_window_rules(facts)
        rules_applied.append("RULE: Multiple assessments in window -> Use closest to target")

        # RULE 5: Treatment duration
        duration_rules = self._get_duration_rules(drug_name)
        rules_applied.append("RULE: Duration = Last dose date - First dose date + 1")

        content = f"""## APPENDIX A: VARIABLE DERIVATIONS

### A.1 Baseline Definitions

{baseline_rules}

### A.2 Change from Baseline

{cfb_rules}

### A.3 Response/Endpoint Derivations

{response_rules}

### A.4 Analysis Visit Windows

{window_rules}

### A.5 Treatment Duration and Exposure

{duration_rules}

### A.6 Derivation Summary Table

| Variable | Derivation Rule | ADaM Variable |
|----------|-----------------|---------------|
| Baseline | Last non-missing assessment before first dose | BASE |
| Change from Baseline | Post-baseline - Baseline | CHG |
| Percent Change | (CHG / BASE) * 100 | PCHG |
| Response | Per endpoint-specific criteria | AVALC = 'Y'/'N' |
| Analysis Visit | Target day ± window | AVISIT, AVISITN |
| Treatment Duration | Last dose - First dose + 1 | TRTDUR |
"""

        return ReasoningResult(
            content=content,
            reasoning_type=ReasoningType.DECISION_TREE,
            confidence=0.90,
            rules_applied=rules_applied
        )

    def _classify_endpoint(self, facts: Dict[str, Any]) -> str:
        """Classify primary endpoint type"""
        endpoint = str(facts.get('primary_endpoint', '')).lower()

        if any(x in endpoint for x in ['survival', 'pfs', 'os', 'efs', 'dfs', 'time to']):
            return 'time_to_event'
        elif any(x in endpoint for x in ['response', 'remission', 'proportion', 'rate', 'orr', 'acr']):
            return 'binary'
        elif any(x in endpoint for x in ['change', 'score', 'mean', 'cfb']):
            return 'continuous'
        else:
            return 'binary'  # Default

    def _get_response_method(self, endpoint_type: str) -> str:
        """Get response derivation method for endpoint type"""
        methods = {
            'binary': 'Responder if criteria met at timepoint',
            'continuous': 'Change from baseline calculation',
            'time_to_event': 'Time to first event or censoring'
        }
        return methods.get(endpoint_type, 'Per protocol definition')

    def _get_baseline_rules(self, facts: Dict[str, Any]) -> str:
        """Generate baseline derivation rules"""
        return """**Baseline Value (BASE):**
- The last non-missing assessment obtained prior to the first dose of study medication
- If multiple assessments on same day, use the one closest to dosing time
- For laboratory parameters: Last value within 28 days prior to first dose
- For efficacy scores: Last value within 7 days prior to first dose

**Baseline Date:**
- The date of the baseline assessment
- Used as reference for calculating study days

**Algorithm:**
```
IF assessment_date < first_dose_date THEN
    baseline_candidate = TRUE
BASELINE = MAX(assessment_date) WHERE baseline_candidate = TRUE
```"""

    def _get_cfb_rules(self, facts: Dict[str, Any]) -> str:
        """Generate change from baseline rules"""
        return """**Change from Baseline (CHG):**
```
CHG = AVAL - BASE
```
Where:
- AVAL = Analysis value at post-baseline timepoint
- BASE = Baseline value

**Percent Change from Baseline (PCHG):**
```
PCHG = ((AVAL - BASE) / BASE) * 100
```
Note: PCHG is only calculated when BASE > 0

**Missing Data:**
- If BASE is missing, CHG and PCHG are set to missing
- If AVAL is missing, CHG and PCHG are set to missing for that timepoint"""

    def _get_response_rules(self, endpoint_type: str, facts: Dict[str, Any]) -> str:
        """Generate response derivation rules based on endpoint type"""
        if endpoint_type == 'time_to_event':
            return """**Time-to-Event Endpoint:**

Event Date Derivation:
- ADT = Date of first qualifying event
- If no event: ADT = Date of last known alive/event-free status

Censoring Rules:
```
IF event_observed = TRUE THEN
    CNSR = 0
    ADT = event_date
ELSE
    CNSR = 1
    ADT = MIN(last_contact_date, data_cutoff_date, new_therapy_date)
```

Analysis Duration:
```
AVAL = ADT - RANDDT + 1  (in days)
AVAL_months = AVAL / 30.4375  (for display)
```"""

        elif endpoint_type == 'continuous':
            return """**Continuous Endpoint:**

Response Criterion (if applicable):
```
AVALC = 'Y' IF CHG >= threshold OR PCHG >= threshold_pct
AVALC = 'N' OTHERWISE
```

Responder Derivation:
```
RESPFL = 'Y' IF AVALC = 'Y' at primary timepoint
RESPFL = 'N' OTHERWISE
```"""

        else:  # binary
            return """**Binary Response Endpoint:**

Response Criteria Applied:
```
AVALC = 'Y' IF all response criteria met
AVALC = 'N' IF any criterion not met
AVALC = 'NE' IF not evaluable (missing required assessments)
```

Responder Flag:
```
RESPFL = 'Y' IF AVALC = 'Y' at primary analysis timepoint
RESPFL = 'N' OTHERWISE (including NE treated as non-responder)
```"""

    def _get_window_rules(self, facts: Dict[str, Any]) -> str:
        """Generate analysis window rules"""
        timepoint = facts.get('primary_timepoint', 'Week 12')

        # Parse week number if possible
        week_match = re.search(r'week\s*(\d+)', timepoint.lower())
        week_num = int(week_match.group(1)) if week_match else 12

        return f"""**Analysis Visit Windows:**

| Scheduled Visit | Target Day | Window (Days) | AVISITN |
|-----------------|------------|---------------|---------|
| Baseline | Day 1 | -7 to 0 | 0 |
| Week 2 | Day 15 | 12-18 | 2 |
| Week 4 | Day 29 | 25-33 | 4 |
| Week 8 | Day 57 | 50-64 | 8 |
| Week {week_num} | Day {week_num * 7 + 1} | {week_num * 7 - 7}-{week_num * 7 + 7} | {week_num} |

**Window Assignment Algorithm:**
```
FOR each assessment:
    FIND closest target_day within allowed window
    IF multiple assessments in same window:
        SELECT assessment closest to target_day
        IF tied: SELECT later assessment
    ASSIGN AVISIT, AVISITN based on window
```"""

    def _get_duration_rules(self, drug_name: str) -> str:
        """Generate treatment duration rules"""
        return f"""**Treatment Duration:**
```
TRTDUR = TRTEDT - TRTSDT + 1
```
Where:
- TRTSDT = Date of first dose of {drug_name}
- TRTEDT = Date of last dose of {drug_name}

**Total Exposure:**
```
TOTDOSE = SUM(daily_doses) over treatment period
```

**Relative Dose Intensity:**
```
RDI = (actual_total_dose / planned_total_dose) * 100
```"""


class TEAEDecisionTree:
    """
    Decision Tree for Treatment-Emergent Adverse Event Logic

    Standard TEAE definitions with protocol-specific adjustments.
    """

    def generate(self, facts: Dict[str, Any]) -> ReasoningResult:
        """Generate TEAE logic using decision tree"""
        rules_applied = []

        drug_name = facts.get('drug_name', 'study drug')
        follow_up_days = facts.get('safety_follow_up_days', 30)

        # RULE 1: TEAE Definition
        rules_applied.append("RULE: TEAE = AE with onset during treatment period")

        # RULE 2: Treatment Period Definition
        rules_applied.append(f"RULE: Treatment period = First dose to last dose + {follow_up_days} days")

        # RULE 3: Severity grading
        rules_applied.append("RULE: Severity graded per CTCAE v5.0 or protocol-specific criteria")

        # RULE 4: Causality assessment
        rules_applied.append("RULE: Causality assessed by investigator (related/not related)")

        # RULE 5: Serious AE criteria
        rules_applied.append("RULE: SAE per ICH E2A criteria (death, life-threatening, hospitalization, etc.)")

        content = f"""## 8. SAFETY ANALYSIS

### 8.1 Treatment-Emergent Adverse Events (TEAEs)

**Definition:**
A treatment-emergent adverse event (TEAE) is defined as any adverse event that:
- Has onset on or after the first dose of {drug_name}, OR
- Was present before treatment but worsened in severity after the first dose of {drug_name}

**Treatment Period:**
```
TEAE_START = TRTSDT (first dose date)
TEAE_END = TRTEDT + {follow_up_days} days (last dose + follow-up)

IF ASTDT >= TEAE_START AND ASTDT <= TEAE_END THEN
    TRTEMFL = 'Y'
ELSE IF ASTDT < TEAE_START AND (AESEV_post > AESEV_pre) THEN
    TRTEMFL = 'Y'  -- Worsening pre-existing condition
ELSE
    TRTEMFL = 'N'
```

### 8.2 Adverse Event Classification

**Severity Grading (CTCAE v5.0):**

| Grade | Description |
|-------|-------------|
| 1 | Mild: Asymptomatic or mild symptoms; clinical or diagnostic observations only |
| 2 | Moderate: Minimal, local or noninvasive intervention indicated |
| 3 | Severe: Medically significant but not immediately life-threatening |
| 4 | Life-threatening: Urgent intervention indicated |
| 5 | Death related to AE |

**Causality Assessment:**
```
IF investigator_assessment IN ('related', 'possibly related', 'probably related') THEN
    AREL = 'Y'
ELSE
    AREL = 'N'
```

### 8.3 Serious Adverse Events (SAEs)

An adverse event is classified as serious if it:
- Results in death
- Is life-threatening
- Requires inpatient hospitalization or prolongation of existing hospitalization
- Results in persistent or significant disability/incapacity
- Is a congenital anomaly/birth defect
- Is an important medical event that may require intervention to prevent one of the above

**SAE Flag Derivation:**
```
IF AESDTH = 'Y' OR AESLIFE = 'Y' OR AESHOSP = 'Y' OR
   AESDISAB = 'Y' OR AESCONG = 'Y' OR AESMIE = 'Y' THEN
    AESER = 'Y'
ELSE
    AESER = 'N'
```

### 8.4 Adverse Events of Special Interest (AESIs)

The following adverse events are designated as AESIs for {drug_name}:

| AESI Category | MedDRA Preferred Terms | Monitoring Requirements |
|---------------|------------------------|-------------------------|
| Infections | Per SMQ 'Infections' | Enhanced reporting |
| Injection site reactions | Injection site* terms | 48-hour follow-up |
| Hypersensitivity | Per SMQ 'Hypersensitivity' | Immediate reporting |
| Hepatic events | ALT/AST elevations | Per Hy's Law criteria |

### 8.5 TEAE Analysis Rules

**Primary TEAE Summaries:**
1. Overall TEAE incidence by treatment group
2. TEAEs by System Organ Class and Preferred Term
3. TEAEs by maximum severity grade
4. Treatment-related TEAEs
5. SAEs
6. TEAEs leading to discontinuation

**Counting Rules:**
- Each patient counted once per PT (at maximum severity)
- Each patient counted once per SOC (at maximum severity of any PT within SOC)
- Related = Possibly, probably, or definitely related per investigator

**Analysis Dataset Flags:**
```
AOCCFL = 'Y' for first occurrence of each PT
AOCCSFL = 'Y' for first occurrence of each SOC
AOCCPFL = 'Y' for first occurrence in population
```
"""

        return ReasoningResult(
            content=content,
            reasoning_type=ReasoningType.DECISION_TREE,
            confidence=0.95,
            rules_applied=rules_applied
        )


# =============================================================================
# RAG-ENHANCED IMPLEMENTATIONS
# =============================================================================

class RAGEnhancedGenerator:
    """
    Base class for RAG-enhanced generation.
    Actually USES the retrieved examples in output.
    """

    def __init__(self, rag_retriever=None):
        self.retriever = rag_retriever
        self._rag_available = rag_retriever is not None

    def _get_rag_examples(
        self,
        query: str,
        section_type: str,
        facts: Dict[str, Any],
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant examples from RAG"""
        if not self._rag_available:
            return []

        try:
            protocol_data = {
                'therapeutic_area': facts.get('therapeutic_area'),
                'phase': facts.get('phase'),
                'indication': facts.get('indication'),
                'primary_endpoint': facts.get('primary_endpoint'),
                'query': query
            }

            results = self.retriever.retrieve_for_section(
                section_type=section_type,
                protocol_data=protocol_data,
                n_results=n_results
            )
            return results
        except Exception as e:
            print(f"[RAG] Warning: Could not retrieve examples: {e}")
            return []

    def _format_rag_examples(self, examples: List[Dict[str, Any]], max_chars: int = 2000) -> str:
        """Format RAG examples for inclusion in output"""
        if not examples:
            return ""

        formatted = []
        total_chars = 0

        for i, ex in enumerate(examples, 1):
            content = ex.get('content', '')[:500]  # Limit each example
            nct_id = ex.get('nct_id', 'Unknown')
            score = ex.get('score', 0)

            if total_chars + len(content) > max_chars:
                break

            formatted.append(f"**Example {i}** (from {nct_id}, relevance: {score:.2f}):\n{content}")
            total_chars += len(content)

        return "\n\n".join(formatted)


class EndpointRAGGenerator(RAGEnhancedGenerator):
    """
    RAG-enhanced endpoint generation.
    Uses retrieved examples to inform endpoint definitions and analysis approaches.
    """

    def generate(self, facts: Dict[str, Any]) -> ReasoningResult:
        """Generate endpoints section with RAG enhancement"""
        rag_examples_used = []

        primary_endpoint = facts.get('primary_endpoint', 'Primary efficacy endpoint')
        primary_timepoint = facts.get('primary_timepoint', 'Week 12')
        secondary_endpoints = facts.get('secondary_endpoints', [])
        therapeutic_area = facts.get('therapeutic_area', '')

        # RETRIEVE similar endpoint examples
        endpoint_examples = self._get_rag_examples(
            query=f"{therapeutic_area} {primary_endpoint}",
            section_type='endpoints',
            facts=facts,
            n_results=3
        )

        # Extract patterns from RAG examples
        rag_patterns = self._extract_endpoint_patterns(endpoint_examples)
        rag_examples_used = [ex.get('nct_id', 'Unknown') for ex in endpoint_examples]

        # Build censoring rules from RAG (for TTE endpoints)
        censoring_rules = self._build_censoring_rules(primary_endpoint, endpoint_examples)

        # Build secondary endpoint table with RAG enhancement
        secondary_table = self._build_secondary_table(secondary_endpoints, endpoint_examples)

        # Format RAG evidence for transparency
        rag_evidence_section = ""
        if endpoint_examples:
            rag_evidence_section = f"""
### 5.5 Evidence from Similar Studies

The endpoint definitions above are informed by analysis approaches used in similar studies:

{self._format_rag_examples(endpoint_examples)}
"""

        content = f"""## 5. ENDPOINTS

### 5.1 Primary Endpoint

**Endpoint:** {primary_endpoint}

**Timepoint:** {primary_timepoint}

**Definition:** {rag_patterns.get('primary_definition', self._default_primary_definition(primary_endpoint))}
{censoring_rules}

### 5.2 Secondary Endpoints

{secondary_table}

### 5.3 Exploratory Endpoints

Exploratory endpoints will include:
- Biomarker analyses (as applicable)
- Patient-reported outcomes
- Healthcare resource utilization

### 5.4 Endpoint Derivation Rules

{rag_patterns.get('derivation_rules', self._default_derivation_rules())}
{rag_evidence_section}"""

        return ReasoningResult(
            content=content,
            reasoning_type=ReasoningType.RAG,
            confidence=0.85 if endpoint_examples else 0.70,
            rag_examples_used=rag_examples_used,
            sources=[f"RAG: {nct}" for nct in rag_examples_used]
        )

    def _extract_endpoint_patterns(self, examples: List[Dict[str, Any]]) -> Dict[str, str]:
        """Extract endpoint patterns from RAG examples"""
        patterns = {}

        if not examples:
            return patterns

        # Look for definition patterns
        for ex in examples:
            content = ex.get('content', '').lower()

            # Extract response criteria patterns
            if 'response' in content and 'defined as' in content:
                # Extract the definition
                match = re.search(r'response.*?defined as[:\s]+([^.]+\.)', content, re.IGNORECASE)
                if match:
                    patterns['primary_definition'] = match.group(1).strip().capitalize()
                    break

        return patterns

    def _build_censoring_rules(self, endpoint: str, examples: List[Dict[str, Any]]) -> str:
        """Build censoring rules from RAG examples for TTE endpoints"""
        endpoint_lower = endpoint.lower()

        if not any(x in endpoint_lower for x in ['survival', 'pfs', 'efs', 'dfs', 'time to']):
            return ""

        # Check RAG examples for censoring rules
        rag_censoring = []
        for ex in examples:
            content = ex.get('content', '').lower()
            if 'censor' in content:
                # Extract censoring rules
                lines = content.split('\n')
                for line in lines:
                    if 'censor' in line and len(line) < 200:
                        rag_censoring.append(line.strip())

        # Use RAG censoring if found, otherwise defaults
        if rag_censoring:
            censoring_list = "\n".join([f"- {rule.capitalize()}" for rule in rag_censoring[:5]])
        else:
            censoring_list = """- Patients alive/without event at data cutoff: censored at last known alive date
- Patients lost to follow-up: censored at date of last contact
- Events after start of subsequent therapy: censored at start of new therapy
- Patients who withdraw consent: censored at withdrawal date"""

        return f"""

**Censoring Rules:**
{censoring_list}

**Data Collection:** Event data will be collected for all patients regardless of treatment discontinuation."""

    def _build_secondary_table(self, endpoints: List[str], examples: List[Dict[str, Any]]) -> str:
        """Build secondary endpoints table with RAG enhancement"""
        if endpoints:
            rows = []
            for i, ep in enumerate(endpoints[:10], 1):
                rows.append(f"| {i} | {ep} | Various |")
            return "| # | Endpoint | Timepoint |\n|---|----------|----------|\n" + "\n".join(rows)

        # Use RAG to suggest secondary endpoints
        rag_secondary = []
        for ex in examples:
            content = ex.get('content', '')
            # Look for numbered lists of secondary endpoints
            matches = re.findall(r'(?:secondary|key secondary)[^:]*:\s*([^\n]+)', content, re.IGNORECASE)
            rag_secondary.extend(matches[:3])

        if rag_secondary:
            rows = []
            for i, ep in enumerate(rag_secondary[:5], 1):
                rows.append(f"| {i} | {ep.strip()} | Per protocol |")
            return "| # | Endpoint | Timepoint |\n|---|----------|----------|\n" + "\n".join(rows)

        return "Secondary endpoints will be defined per protocol."

    def _default_primary_definition(self, endpoint: str) -> str:
        """Default definition when RAG doesn't provide one"""
        return f"As specified in the protocol. {endpoint} will be assessed according to protocol-defined criteria."

    def _default_derivation_rules(self) -> str:
        """Default derivation rules"""
        return """Endpoint values will be derived as follows:
- Binary endpoints: Responder (Y) if all criteria met, Non-responder (N) otherwise
- Continuous endpoints: Change from baseline = Post-baseline value - Baseline value
- Time-to-event: Days from randomization to first event or censoring"""


class MethodsRAGGenerator(RAGEnhancedGenerator):
    """
    RAG-enhanced statistical methods generation.
    Uses retrieved examples to inform method selection and model specifications.
    """

    def generate(self, facts: Dict[str, Any]) -> ReasoningResult:
        """Generate methods section with RAG enhancement"""
        rag_examples_used = []

        primary_endpoint = facts.get('primary_endpoint', '')
        endpoint_type = self._classify_endpoint_type(primary_endpoint)
        therapeutic_area = facts.get('therapeutic_area', '')
        alpha = facts.get('alpha', 0.05)
        alpha_sidedness = facts.get('alpha_sidedness', 'two-sided')
        is_single_arm = facts.get('is_single_arm', False)

        # RETRIEVE similar methods examples
        methods_examples = self._get_rag_examples(
            query=f"{therapeutic_area} {endpoint_type} statistical analysis",
            section_type='methods',
            facts=facts,
            n_results=3
        )

        rag_examples_used = [ex.get('nct_id', 'Unknown') for ex in methods_examples]

        # Extract method patterns from RAG
        rag_methods = self._extract_method_patterns(methods_examples, endpoint_type)

        # Build method specification
        if is_single_arm:
            method_content = self._build_single_arm_methods(facts, rag_methods)
        else:
            method_content = self._build_comparative_methods(facts, rag_methods, endpoint_type)

        # Build sensitivity analyses from RAG
        sensitivity_section = self._build_sensitivity_analyses(methods_examples, is_single_arm)

        # RAG evidence
        rag_evidence = ""
        if methods_examples:
            rag_evidence = f"""
### 7.7 Methods Informed by Similar Studies

{self._format_rag_examples(methods_examples)}
"""

        content = f"""## 7. STATISTICAL METHODS

### 7.1 General Considerations

- Significance level: {alpha_sidedness} alpha = {alpha}
- Confidence intervals: {int((1 - alpha) * 100)}% confidence level
- All p-values will be rounded to 4 decimal places
- Analyses will be performed using SAS version 9.4 or later

### 7.2 Analysis of Primary Endpoint

{method_content}

### 7.3 Analysis of Secondary Endpoints

Secondary endpoints will be analyzed using methods appropriate to the endpoint type:
- Binary endpoints: Logistic regression or CMH test
- Continuous endpoints: ANCOVA or MMRM
- Time-to-event: Kaplan-Meier and Cox regression

### 7.4 Sensitivity Analyses

{sensitivity_section}

### 7.5 Subgroup Analyses

Subgroup analyses will be performed for the primary endpoint:
- Age group (<65, ≥65 years)
- Sex
- Geographic region
- Baseline disease severity
- Prior treatment history

Forest plots will display treatment effects across subgroups.

### 7.6 Multiplicity Adjustment

{self._get_multiplicity_approach(facts)}
{rag_evidence}"""

        return ReasoningResult(
            content=content,
            reasoning_type=ReasoningType.RAG,
            confidence=0.85 if methods_examples else 0.75,
            rag_examples_used=rag_examples_used,
            sources=[f"RAG: {nct}" for nct in rag_examples_used]
        )

    def _classify_endpoint_type(self, endpoint: str) -> str:
        """Classify endpoint for method selection"""
        endpoint_lower = endpoint.lower()
        if any(x in endpoint_lower for x in ['survival', 'pfs', 'os', 'efs', 'dfs', 'time to']):
            return 'time_to_event'
        elif any(x in endpoint_lower for x in ['response', 'remission', 'rate', 'proportion']):
            return 'binary'
        else:
            return 'continuous'

    def _extract_method_patterns(self, examples: List[Dict[str, Any]], endpoint_type: str) -> Dict[str, str]:
        """Extract method patterns from RAG examples"""
        patterns = {}

        for ex in examples:
            content = ex.get('content', '').lower()

            # Look for model specifications
            if 'model' in content or 'analysis' in content:
                if endpoint_type == 'binary' and 'logistic' in content:
                    match = re.search(r'logistic[^.]+model[^.]+\.', content)
                    if match:
                        patterns['model_spec'] = match.group(0)
                elif endpoint_type == 'continuous' and 'ancova' in content:
                    match = re.search(r'ancova[^.]+\.', content)
                    if match:
                        patterns['model_spec'] = match.group(0)
                elif endpoint_type == 'time_to_event' and 'cox' in content:
                    match = re.search(r'cox[^.]+\.', content)
                    if match:
                        patterns['model_spec'] = match.group(0)

        return patterns

    def _build_single_arm_methods(self, facts: Dict[str, Any], rag_methods: Dict) -> str:
        """Build methods for single-arm study"""
        return """**Single-Arm Analysis Approach:**

Since this is a single-arm study, the primary analysis will be descriptive:

**Point Estimate:**
- Response rate with exact (Clopper-Pearson) 95% confidence interval

**Historical Comparison (if applicable):**
- Comparison to historical control rate using one-sample exact binomial test
- Null hypothesis: response rate ≤ historical rate

**Supporting Analyses:**
- Kaplan-Meier estimates for duration of response
- Waterfall plots for best response
- Spider plots for individual patient trajectories"""

    def _build_comparative_methods(self, facts: Dict[str, Any], rag_methods: Dict, endpoint_type: str) -> str:
        """Build methods for comparative study"""
        drug_name = facts.get('drug_name', 'study drug')

        if endpoint_type == 'time_to_event':
            return f"""**Time-to-Event Analysis:**

**Primary Method:** Kaplan-Meier estimation with stratified log-rank test

**Model Specification:**
```
h(t|X) = h₀(t) × exp(β₁×Treatment + β₂×Strata)
```

**Treatment Effect:** Hazard ratio with 95% confidence interval from Cox proportional hazards model

**Key Outputs:**
- Kaplan-Meier curves by treatment group
- Median survival time with 95% CI per group
- Hazard ratio with 95% CI
- Log-rank p-value (stratified)

**Assumption Checking:**
- Proportional hazards assumption via Schoenfeld residuals
- Log-log survival plots"""

        elif endpoint_type == 'binary':
            return f"""**Binary Endpoint Analysis:**

**Primary Method:** Stratified Cochran-Mantel-Haenszel (CMH) test

**Model Specification:**
```
logit(P(Y=1)) = β₀ + β₁×Treatment + β₂×Strata + β₃×Baseline_covariates
```

**Treatment Effect:** Odds ratio with 95% confidence interval

**Key Outputs:**
- Response rates by treatment group with 95% CI
- Difference in proportions with 95% CI
- Odds ratio with 95% CI
- CMH p-value (stratified)"""

        else:  # continuous
            return f"""**Continuous Endpoint Analysis:**

**Primary Method:** ANCOVA (Analysis of Covariance)

**Model Specification:**
```
Y_post = μ + β₁×Treatment + β₂×Y_baseline + β₃×Strata + ε
```

**Treatment Effect:** Least squares mean difference with 95% confidence interval

**Key Outputs:**
- LS means by treatment group
- LS mean difference (treatment vs control)
- 95% confidence interval
- ANCOVA p-value"""

    def _build_sensitivity_analyses(self, examples: List[Dict[str, Any]], is_single_arm: bool) -> str:
        """Build sensitivity analyses from RAG examples"""
        # Extract sensitivity approaches from RAG
        rag_sensitivity = []
        for ex in examples:
            content = ex.get('content', '').lower()
            if 'sensitivity' in content:
                # Look for sensitivity analysis mentions
                matches = re.findall(r'sensitivity[^:]*:\s*([^\n]+)', content)
                rag_sensitivity.extend(matches[:2])

        base_analyses = """- Per-protocol population analysis
- Tipping point analysis for missing data
- Alternative imputation methods (LOCF, BOCF, multiple imputation)"""

        if rag_sensitivity:
            rag_list = "\n".join([f"- {s.strip().capitalize()}" for s in rag_sensitivity[:3]])
            return f"""{base_analyses}

**Additional sensitivity analyses (informed by similar studies):**
{rag_list}"""

        return base_analyses

    def _get_multiplicity_approach(self, facts: Dict[str, Any]) -> str:
        """Get multiplicity adjustment approach"""
        num_endpoints = len(facts.get('secondary_endpoints', [])) + 1

        if num_endpoints <= 2:
            return "No formal multiplicity adjustment for single primary endpoint."
        else:
            return """**Hierarchical Testing Procedure:**

Secondary endpoints will be tested in a pre-specified hierarchical order:
1. If primary endpoint is significant (p < 0.05), proceed to first secondary
2. If first secondary is significant, proceed to next
3. Continue until a non-significant result

This maintains the family-wise error rate at 0.05."""


class StratificationRAGGenerator(RAGEnhancedGenerator):
    """RAG-enhanced stratification factor generation"""

    def generate(self, facts: Dict[str, Any]) -> ReasoningResult:
        """Generate stratification section with RAG enhancement"""
        rag_examples_used = []

        therapeutic_area = facts.get('therapeutic_area', '')
        existing_factors = facts.get('stratification_factors', [])

        # RETRIEVE similar stratification examples
        strat_examples = self._get_rag_examples(
            query=f"{therapeutic_area} stratification randomization factors",
            section_type='stratification',
            facts=facts,
            n_results=3
        )

        rag_examples_used = [ex.get('nct_id', 'Unknown') for ex in strat_examples]

        # Extract stratification patterns from RAG
        rag_factors = self._extract_stratification_factors(strat_examples)

        # Combine existing factors with RAG suggestions
        all_factors = existing_factors or rag_factors or [
            "Geographic region",
            "Baseline disease severity",
            "Prior treatment history"
        ]

        factors_table = self._build_factors_table(all_factors)

        rag_evidence = ""
        if strat_examples:
            rag_evidence = f"""
**Stratification factors are informed by similar studies:**
{self._format_rag_examples(strat_examples)}
"""

        content = f"""### 3.4 Stratification Factors

Randomization will be stratified by the following factors:

{factors_table}

**Stratification Implementation:**
- Stratification will be implemented via the IWRS/IXRS system
- Stratification factors will be recorded at randomization
- Analyses will be stratified by randomization stratification factors
{rag_evidence}"""

        return ReasoningResult(
            content=content,
            reasoning_type=ReasoningType.RAG,
            confidence=0.80 if strat_examples else 0.70,
            rag_examples_used=rag_examples_used
        )

    def _extract_stratification_factors(self, examples: List[Dict[str, Any]]) -> List[str]:
        """Extract stratification factors from RAG examples"""
        factors = []

        for ex in examples:
            content = ex.get('content', '')
            # Look for stratification factor patterns
            matches = re.findall(r'stratif\w+\s+(?:by|factor)[s:\s]+([^\n]+)', content, re.IGNORECASE)
            for match in matches:
                # Split by common delimiters
                parts = re.split(r'[,;]|\band\b', match)
                for part in parts:
                    part = part.strip()
                    if len(part) > 3 and len(part) < 100:
                        factors.append(part)

        return list(set(factors))[:5]

    def _build_factors_table(self, factors: List[str]) -> str:
        """Build stratification factors table"""
        rows = ["| Factor | Levels | Rationale |", "|--------|--------|-----------|"]

        for factor in factors:
            levels = self._infer_levels(factor)
            rationale = self._infer_rationale(factor)
            rows.append(f"| {factor} | {levels} | {rationale} |")

        return "\n".join(rows)

    def _infer_levels(self, factor: str) -> str:
        """Infer factor levels from name"""
        factor_lower = factor.lower()
        if 'age' in factor_lower:
            return "<65, ≥65 years"
        elif 'region' in factor_lower:
            return "North America, Europe, Other"
        elif 'sever' in factor_lower:
            return "Mild, Moderate, Severe"
        elif 'prior' in factor_lower or 'previous' in factor_lower:
            return "Yes, No"
        else:
            return "Per protocol"

    def _infer_rationale(self, factor: str) -> str:
        """Infer rationale for factor"""
        factor_lower = factor.lower()
        if 'age' in factor_lower:
            return "Potential effect modifier"
        elif 'region' in factor_lower:
            return "Regulatory requirements"
        elif 'sever' in factor_lower:
            return "Prognostic factor"
        elif 'prior' in factor_lower:
            return "May affect response"
        else:
            return "Potential prognostic factor"


class FollowUpWindowRAGGenerator(RAGEnhancedGenerator):
    """RAG-enhanced follow-up window generation"""

    def generate(self, facts: Dict[str, Any]) -> ReasoningResult:
        """Generate follow-up windows with RAG enhancement"""
        rag_examples_used = []

        therapeutic_area = facts.get('therapeutic_area', '')
        primary_timepoint = facts.get('primary_timepoint', 'Week 12')

        # RETRIEVE similar window definitions
        window_examples = self._get_rag_examples(
            query=f"{therapeutic_area} visit windows analysis windows",
            section_type='windows',
            facts=facts,
            n_results=3
        )

        rag_examples_used = [ex.get('nct_id', 'Unknown') for ex in window_examples]

        # Extract window patterns from RAG
        rag_windows = self._extract_window_patterns(window_examples)

        # Build window table
        window_table = self._build_window_table(rag_windows, primary_timepoint)

        content = f"""### 7.8 Analysis Visit Windows

{window_table}

**Window Assignment Rules:**
- If multiple assessments fall within a window, use the one closest to target day
- If tied (same distance from target), use the later assessment
- Assessments outside all windows will be excluded from windowed analyses

**Unscheduled Visits:**
- Unscheduled assessments will be assigned to the nearest analysis window if within range
- Early termination visits will be analyzed as the last scheduled visit window"""

        return ReasoningResult(
            content=content,
            reasoning_type=ReasoningType.RAG,
            confidence=0.80 if window_examples else 0.70,
            rag_examples_used=rag_examples_used
        )

    def _extract_window_patterns(self, examples: List[Dict[str, Any]]) -> Dict[str, str]:
        """Extract window patterns from RAG examples"""
        patterns = {}

        for ex in examples:
            content = ex.get('content', '')
            # Look for window definitions
            matches = re.findall(r'week\s*(\d+)[:\s]+day\s*(\d+)\s*±\s*(\d+)', content, re.IGNORECASE)
            for week, day, window in matches:
                patterns[f"Week {week}"] = f"Day {day} ± {window} days"

        return patterns

    def _build_window_table(self, rag_windows: Dict[str, str], primary_timepoint: str) -> str:
        """Build visit window table"""
        # Parse primary timepoint
        week_match = re.search(r'week\s*(\d+)', primary_timepoint.lower())
        max_week = int(week_match.group(1)) if week_match else 12

        rows = ["| Visit | Target Day | Window |", "|-------|------------|--------|"]

        # Standard windows or RAG-informed
        standard_weeks = [2, 4, 8] + [max_week]
        standard_weeks = sorted(set(w for w in standard_weeks if w <= max_week))

        rows.append("| Baseline | Day 1 | Day -7 to Day 1 |")

        for week in standard_weeks:
            if f"Week {week}" in rag_windows:
                window = rag_windows[f"Week {week}"]
            else:
                target_day = week * 7 + 1
                window_size = 3 if week <= 4 else 7
                window = f"Day {target_day} ± {window_size} days"

            rows.append(f"| Week {week} | Day {week * 7 + 1} | {window} |")

        return "\n".join(rows)


# =============================================================================
# HYBRID REASONING ENGINE
# =============================================================================

class HybridReasoningEngine:
    """
    Main engine that dispatches to the correct reasoning approach per section.

    This is the SINGLE entry point for all section generation.
    """

    # Section -> Reasoning Type mapping
    SECTION_REASONING = {
        'populations': ReasoningType.DECISION_TREE,
        'derivations': ReasoningType.DECISION_TREE,
        'teae_logic': ReasoningType.DECISION_TREE,
        'arms': ReasoningType.REGEX,
        'stratification': ReasoningType.RAG,
        'endpoints': ReasoningType.RAG,
        'methods': ReasoningType.RAG,
        'follow_up_windows': ReasoningType.RAG,
    }

    def __init__(self, rag_retriever=None):
        """
        Initialize hybrid reasoning engine.

        Args:
            rag_retriever: RAG retriever instance (optional, enables RAG sections)
        """
        self.rag_retriever = rag_retriever

        # Decision Tree generators
        self.population_tree = PopulationDecisionTree()
        self.derivation_tree = DerivationDecisionTree()
        self.teae_tree = TEAEDecisionTree()

        # RAG-enhanced generators
        self.endpoint_rag = EndpointRAGGenerator(rag_retriever)
        self.methods_rag = MethodsRAGGenerator(rag_retriever)
        self.stratification_rag = StratificationRAGGenerator(rag_retriever)
        self.followup_rag = FollowUpWindowRAGGenerator(rag_retriever)

    def generate_section(
        self,
        section_name: str,
        facts: Dict[str, Any]
    ) -> ReasoningResult:
        """
        Generate a section using the appropriate reasoning approach.

        Args:
            section_name: Name of section to generate
            facts: Protocol facts dictionary

        Returns:
            ReasoningResult with content and metadata
        """
        reasoning_type = self.SECTION_REASONING.get(section_name, ReasoningType.TEMPLATE)

        # Dispatch to appropriate generator
        if section_name == 'populations':
            return self.population_tree.generate(facts)

        elif section_name == 'derivations':
            return self.derivation_tree.generate(facts)

        elif section_name == 'teae_logic':
            return self.teae_tree.generate(facts)

        elif section_name == 'stratification':
            return self.stratification_rag.generate(facts)

        elif section_name == 'endpoints':
            return self.endpoint_rag.generate(facts)

        elif section_name == 'methods':
            return self.methods_rag.generate(facts)

        elif section_name == 'follow_up_windows':
            return self.followup_rag.generate(facts)

        else:
            # Fallback to template
            return ReasoningResult(
                content=f"[Section: {section_name} - Template fallback]",
                reasoning_type=ReasoningType.TEMPLATE,
                confidence=0.5
            )

    def generate_all_sections(
        self,
        facts: Dict[str, Any]
    ) -> Dict[str, ReasoningResult]:
        """
        Generate all sections using hybrid reasoning.

        Args:
            facts: Protocol facts dictionary

        Returns:
            Dictionary of section_name -> ReasoningResult
        """
        results = {}

        for section_name in self.SECTION_REASONING.keys():
            try:
                results[section_name] = self.generate_section(section_name, facts)
            except Exception as e:
                results[section_name] = ReasoningResult(
                    content=f"[Error generating {section_name}: {e}]",
                    reasoning_type=ReasoningType.TEMPLATE,
                    confidence=0.0
                )

        return results

    def get_reasoning_summary(self) -> str:
        """Get summary of reasoning approaches used"""
        summary = ["Hybrid Reasoning Engine - Section Mapping:", "=" * 50]

        for section, reasoning in self.SECTION_REASONING.items():
            icon = {
                ReasoningType.DECISION_TREE: "🌳",
                ReasoningType.RAG: "📚",
                ReasoningType.REGEX: "📝",
                ReasoningType.TEMPLATE: "📄"
            }.get(reasoning, "?")

            summary.append(f"  {icon} {section}: {reasoning.value}")

        return "\n".join(summary)


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_hybrid_engine(rag_retriever=None) -> HybridReasoningEngine:
    """Create a hybrid reasoning engine instance"""
    return HybridReasoningEngine(rag_retriever=rag_retriever)


def get_reasoning_type(section_name: str) -> ReasoningType:
    """Get the reasoning type for a section"""
    return HybridReasoningEngine.SECTION_REASONING.get(
        section_name,
        ReasoningType.TEMPLATE
    )
