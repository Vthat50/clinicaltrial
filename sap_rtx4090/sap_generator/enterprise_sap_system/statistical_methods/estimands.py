"""
Estimands Framework (ICH E9 R1)
================================

Framework for defining and implementing estimands per ICH E9(R1) Addendum.

ICH E9(R1) requires explicit definition of:
1. Treatment - intervention whose effect is to be estimated
2. Population - patients targeted by the clinical question
3. Variable (endpoint) - outcome measurement
4. Intercurrent events - events occurring after treatment initiation that affect interpretation
5. Population-level summary - how endpoint is summarized across population

Strategies for intercurrent events:
- Treatment policy strategy
- Composite strategy
- Hypothetical strategy
- Principal stratum strategy
- While on treatment strategy

References:
- ICH E9(R1): Addendum on Estimands and Sensitivity Analysis (2019)
- FDA Guidance: "Adjusting for Covariates in Randomized Clinical Trials" (2021)
- EMA Guidance: "Guideline on Missing Data in Confirmatory Clinical Trials" (2010)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IntercurrentEventStrategy(Enum):
    """Strategies for handling intercurrent events"""
    TREATMENT_POLICY = "Treatment Policy"
    COMPOSITE = "Composite"
    HYPOTHETICAL = "Hypothetical"
    PRINCIPAL_STRATUM = "Principal Stratum"
    WHILE_ON_TREATMENT = "While on Treatment"


class IntercurrentEventType(Enum):
    """Types of intercurrent events"""
    TREATMENT_DISCONTINUATION = "Treatment Discontinuation"
    RESCUE_MEDICATION = "Use of Rescue Medication"
    DEATH = "Death"
    DISEASE_PROGRESSION = "Disease Progression"
    NEW_ANTICANCER_THERAPY = "Initiation of New Anti-cancer Therapy"
    ADVERSE_EVENT = "Adverse Event Leading to Discontinuation"
    PROTOCOL_DEVIATION = "Major Protocol Deviation"
    WITHDRAWAL_CONSENT = "Withdrawal of Consent"
    LOSS_TO_FOLLOWUP = "Loss to Follow-up"


@dataclass
class IntercurrentEvent:
    """
    Specification for an intercurrent event.

    An event occurring after treatment initiation that affects
    interpretation or existence of measurements.
    """
    event_type: IntercurrentEventType
    description: str

    # Strategy
    strategy: IntercurrentEventStrategy

    # Definition
    occurs_when: str                     # When event is considered to occur
    affects_endpoint: bool = True        # Whether affects endpoint measurement

    # Implementation details
    data_handling: str = ""              # How data is handled after event
    analysis_method: str = ""            # Statistical method aligned with strategy

    # Examples
    example_scenarios: List[str] = field(default_factory=list)

    # Regulatory considerations
    regulatory_rationale: str = ""


@dataclass
class Estimand:
    """
    Complete estimand specification per ICH E9(R1).

    An estimand precisely defines the treatment effect to be estimated.
    """
    # Required attributes
    treatment: str                       # Intervention of interest
    population: str                      # Target population
    variable: str                        # Endpoint/outcome
    population_summary: str              # How to summarize (mean, median, HR, etc.)

    # Intercurrent events
    intercurrent_events: List[IntercurrentEvent] = field(default_factory=list)

    # Metadata
    estimand_name: str = ""              # e.g., "Primary Estimand", "Supplementary Estimand"
    estimand_type: str = "Primary"       # "Primary", "Supplementary", "Sensitivity"

    # Clinical interpretation
    clinical_question: str = ""          # What question does this answer?
    clinical_relevance: str = ""         # Why is this clinically meaningful?

    # Statistical method
    estimator: str = ""                  # Statistical method for estimation
    estimator_justification: str = ""    # Why this estimator is appropriate

    def __post_init__(self):
        """Validate estimand completeness"""
        if not all([self.treatment, self.population, self.variable, self.population_summary]):
            logger.warning("Estimand incomplete: all 4 core attributes should be specified")

    def is_complete(self) -> bool:
        """Check if estimand is completely defined"""
        return all([
            self.treatment,
            self.population,
            self.variable,
            self.population_summary,
            len(self.intercurrent_events) > 0
        ])


@dataclass
class EstimandFramework:
    """
    Complete estimand framework for a clinical trial.

    Contains primary estimand and all supplementary/sensitivity estimands.
    """
    # Trial context
    trial_objective: str
    endpoint_name: str
    endpoint_type: str                   # "time-to-event", "binary", "continuous"

    # Estimands
    primary_estimand: Estimand
    supplementary_estimands: List[Estimand] = field(default_factory=list)
    sensitivity_estimands: List[Estimand] = field(default_factory=list)

    # Alignment
    alignment_table: Dict[str, str] = field(default_factory=dict)  # estimand -> method

    def add_supplementary_estimand(self, estimand: Estimand):
        """Add supplementary estimand"""
        estimand.estimand_type = "Supplementary"
        self.supplementary_estimands.append(estimand)

    def add_sensitivity_estimand(self, estimand: Estimand):
        """Add sensitivity estimand"""
        estimand.estimand_type = "Sensitivity"
        self.sensitivity_estimands.append(estimand)


class EstimandService:
    """
    Service for creating and documenting estimands per ICH E9(R1).

    Provides templates and methodology text for SAP.
    """

    def __init__(self):
        """Initialize estimand service"""
        pass

    def create_survival_estimand(
        self,
        endpoint_name: str,
        population: str = "Intent-to-Treat",
        primary_strategy: IntercurrentEventStrategy = IntercurrentEventStrategy.TREATMENT_POLICY
    ) -> Estimand:
        """
        Create standard estimand for time-to-event endpoint.

        Args:
            endpoint_name: E.g., "Overall Survival", "Progression-Free Survival"
            population: Target population
            primary_strategy: Strategy for intercurrent events

        Returns:
            Estimand for survival endpoint
        """
        # Define common intercurrent events for survival endpoints
        intercurrent_events = []

        # Treatment discontinuation
        if primary_strategy == IntercurrentEventStrategy.TREATMENT_POLICY:
            intercurrent_events.append(IntercurrentEvent(
                event_type=IntercurrentEventType.TREATMENT_DISCONTINUATION,
                description="Subject discontinues randomized treatment for any reason",
                strategy=IntercurrentEventStrategy.TREATMENT_POLICY,
                occurs_when="At time of treatment discontinuation",
                data_handling="Continue collecting endpoint data regardless of treatment status",
                analysis_method="Include all data regardless of treatment discontinuation",
                regulatory_rationale="Reflects real-world effectiveness including discontinuation"
            ))

        # New anti-cancer therapy
        if endpoint_name == "Progression-Free Survival":
            if primary_strategy == IntercurrentEventStrategy.TREATMENT_POLICY:
                intercurrent_events.append(IntercurrentEvent(
                    event_type=IntercurrentEventType.NEW_ANTICANCER_THERAPY,
                    description="Subject initiates new anti-cancer therapy before progression",
                    strategy=IntercurrentEventStrategy.TREATMENT_POLICY,
                    occurs_when="At initiation of new therapy",
                    data_handling="Continue tumor assessments, count subsequent progression as event",
                    analysis_method="Treat as censoring at time of new therapy or count progression after new therapy",
                    regulatory_rationale="Policy question: effect allowing subsequent therapy"
                ))

        # Death (always relevant for survival endpoints)
        intercurrent_events.append(IntercurrentEvent(
            event_type=IntercurrentEventType.DEATH,
            description="Death from any cause",
            strategy=IntercurrentEventStrategy.COMPOSITE if "Progression-Free" in endpoint_name else IntercurrentEventStrategy.TREATMENT_POLICY,
            occurs_when="At time of death",
            affects_endpoint=True,
            data_handling="Counted as event",
            analysis_method="Death is the event of interest" if "Overall" in endpoint_name else "Death or progression, whichever occurs first"
        ))

        estimand = Estimand(
            estimand_name=f"{endpoint_name} - Primary Estimand",
            treatment=f"Experimental treatment vs Control treatment, assigned at randomization",
            population=f"{population} population (all randomized subjects)",
            variable=f"{endpoint_name}: time from randomization to event",
            population_summary="Hazard ratio comparing experimental to control",
            intercurrent_events=intercurrent_events,
            clinical_question=f"What is the effect of assigned treatment on {endpoint_name}, regardless of treatment discontinuation?",
            clinical_relevance=f"Treatment policy strategy reflects real-world effectiveness",
            estimator="Cox proportional hazards model",
            estimator_justification="Cox model provides hazard ratio estimate appropriate for treatment policy strategy"
        )

        return estimand

    def create_orr_estimand(
        self,
        population: str = "Intent-to-Treat",
        primary_strategy: IntercurrentEventStrategy = IntercurrentEventStrategy.HYPOTHETICAL
    ) -> Estimand:
        """
        Create estimand for Objective Response Rate.

        Args:
            population: Target population
            primary_strategy: Strategy for treatment discontinuation

        Returns:
            Estimand for ORR
        """
        intercurrent_events = []

        # Treatment discontinuation
        if primary_strategy == IntercurrentEventStrategy.HYPOTHETICAL:
            intercurrent_events.append(IntercurrentEvent(
                event_type=IntercurrentEventType.TREATMENT_DISCONTINUATION,
                description="Subject discontinues treatment before achieving response",
                strategy=IntercurrentEventStrategy.HYPOTHETICAL,
                occurs_when="At time of treatment discontinuation",
                data_handling="Continue tumor assessments, count responses occurring after discontinuation",
                analysis_method="Hypothetical scenario: what if treatment had been continued?",
                regulatory_rationale="Estimates treatment effect under adherence, relevant for regulatory decision"
            ))
        elif primary_strategy == IntercurrentEventStrategy.TREATMENT_POLICY:
            intercurrent_events.append(IntercurrentEvent(
                event_type=IntercurrentEventType.TREATMENT_DISCONTINUATION,
                description="Subject discontinues treatment before achieving response",
                strategy=IntercurrentEventStrategy.TREATMENT_POLICY,
                occurs_when="At time of treatment discontinuation",
                data_handling="Continue tumor assessments, count responses regardless",
                analysis_method="Include responses occurring before or after discontinuation",
                regulatory_rationale="Reflects real-world use including discontinuation"
            ))

        # New anti-cancer therapy before response
        intercurrent_events.append(IntercurrentEvent(
            event_type=IntercurrentEventType.NEW_ANTICANCER_THERAPY,
            description="Subject receives new anti-cancer therapy before achieving response",
            strategy=IntercurrentEventStrategy.COMPOSITE,
            occurs_when="At initiation of new therapy",
            data_handling="Considered non-responder (composite endpoint)",
            analysis_method="Count as non-responder in composite endpoint",
            regulatory_rationale="Need for subsequent therapy indicates lack of adequate response"
        ))

        # Death before response assessment
        intercurrent_events.append(IntercurrentEvent(
            event_type=IntercurrentEventType.DEATH,
            description="Death before adequate response assessment",
            strategy=IntercurrentEventStrategy.COMPOSITE,
            occurs_when="At time of death",
            data_handling="Considered non-responder",
            analysis_method="Count as non-responder",
            regulatory_rationale="Death prevents response achievement"
        ))

        estimand = Estimand(
            estimand_name="Objective Response Rate - Primary Estimand",
            treatment="Experimental treatment vs Control, assigned at randomization",
            population=f"{population} population (all randomized subjects)",
            variable="Best overall response (CR or PR) per RECIST 1.1",
            population_summary="Proportion of subjects achieving CR or PR",
            intercurrent_events=intercurrent_events,
            clinical_question="What proportion of subjects achieve objective response with assigned treatment?",
            clinical_relevance="ORR is a direct measure of anti-tumor activity",
            estimator="Cochran-Mantel-Haenszel test with Clopper-Pearson confidence intervals",
            estimator_justification="CMH test accounts for stratification; exact CI appropriate for binary outcome"
        )

        return estimand

    def generate_estimand_section(
        self,
        framework: EstimandFramework
    ) -> str:
        """
        Generate complete estimand section for SAP.

        Args:
            framework: EstimandFramework with all estimands

        Returns:
            Formatted SAP text
        """
        text = f"""
## Estimand Framework

Per ICH E9(R1) Addendum on Estimands and Sensitivity Analysis, the treatment effect of
interest is precisely defined using an estimand framework.

### Trial Objective

{framework.trial_objective}

### Primary Estimand

The primary estimand defines the treatment effect targeted by the primary objective:

"""

        text += self._generate_single_estimand_text(framework.primary_estimand)

        # Supplementary estimands
        if framework.supplementary_estimands:
            text += """
### Supplementary Estimands

The following supplementary estimands address additional clinically relevant questions:

"""
            for i, estimand in enumerate(framework.supplementary_estimands, 1):
                text += f"\n#### Supplementary Estimand {i}\n\n"
                text += self._generate_single_estimand_text(estimand)

        # Sensitivity estimands
        if framework.sensitivity_estimands:
            text += """
### Sensitivity Estimands

The following sensitivity estimands assess robustness to assumptions:

"""
            for i, estimand in enumerate(framework.sensitivity_estimands, 1):
                text += f"\n#### Sensitivity Estimand {i}\n\n"
                text += self._generate_single_estimand_text(estimand)

        # Alignment table
        text += self._generate_alignment_section(framework)

        # Regulatory context
        text += self._generate_regulatory_context()

        return text.strip()

    def _generate_single_estimand_text(self, estimand: Estimand) -> str:
        """Generate text for a single estimand"""
        text = f"""
**Clinical Question:** {estimand.clinical_question}

**Estimand Components:**

1. **Treatment:** {estimand.treatment}

2. **Population:** {estimand.population}

3. **Variable (Endpoint):** {estimand.variable}

4. **Intercurrent Events:**

"""

        for ie in estimand.intercurrent_events:
            text += f"""
   **{ie.event_type.value}:**
   - Definition: {ie.description}
   - Occurrence: {ie.occurs_when}
   - Strategy: {ie.strategy.value}
   - Data Handling: {ie.data_handling}
   - Analysis: {ie.analysis_method}
"""
            if ie.regulatory_rationale:
                text += f"   - Rationale: {ie.regulatory_rationale}\n"

        text += f"""
5. **Population-Level Summary:** {estimand.population_summary}

**Estimator:**
{estimand.estimator}

**Justification:**
{estimand.estimator_justification}

**Clinical Relevance:**
{estimand.clinical_relevance}

"""

        return text

    def _generate_alignment_section(self, framework: EstimandFramework) -> str:
        """Generate alignment between estimands and methods"""
        text = """
### Alignment of Estimands and Statistical Methods

The following table shows the alignment between estimands and statistical methods:

| Estimand | Intercurrent Event Strategy | Statistical Method | Estimator |
|----------|----------------------------|-------------------|-----------|
"""

        # Primary estimand
        primary = framework.primary_estimand
        strategies = ", ".join([ie.strategy.value for ie in primary.intercurrent_events])
        text += f"| Primary | {strategies} | {primary.estimator} | Main Analysis |\n"

        # Supplementary estimands
        for i, est in enumerate(framework.supplementary_estimands, 1):
            strategies = ", ".join([ie.strategy.value for ie in est.intercurrent_events])
            text += f"| Supplementary {i} | {strategies} | {est.estimator} | Supplementary |\n"

        # Sensitivity estimands
        for i, est in enumerate(framework.sensitivity_estimands, 1):
            strategies = ", ".join([ie.strategy.value for ie in est.intercurrent_events])
            text += f"| Sensitivity {i} | {strategies} | {est.estimator} | Sensitivity |\n"

        text += """
**Interpretation:**
- The primary estimand addresses the primary clinical question
- Supplementary estimands provide additional clinically relevant perspectives
- Sensitivity estimands assess robustness to assumptions about intercurrent events

All estimands are pre-specified and will be estimated regardless of outcomes.
"""

        return text

    def _generate_regulatory_context(self) -> str:
        """Generate regulatory context section"""
        return """
### Regulatory Considerations

This estimand framework complies with:

- **ICH E9(R1) (2019):** Addendum on Estimands and Sensitivity Analysis in Clinical Trials
- **FDA Guidance (2021):** Adjusting for Covariates in Randomized Clinical Trials for Drugs and Biological Products
- **EMA Reflection Paper (2017):** on the Use of Extrapolation in the Development of Medicines for Paediatrics

**Key Principles:**

1. **Transparency:** All estimands are pre-specified before database lock
2. **Clinical Relevance:** Each estimand addresses a clinically meaningful question
3. **Alignment:** Statistical methods are aligned with estimand strategies
4. **Sensitivity:** Multiple estimands assess robustness
5. **Interpretation:** Primary conclusion based on primary estimand; others provide context

**Estimand Selection Rationale:**

The primary estimand was selected to address the primary objective and reflect the
intended use of the treatment. The choice of strategies for intercurrent events
balances regulatory requirements, clinical relevance, and practical feasibility.

**Relationship to Missing Data:**

The estimand framework is distinct from but related to missing data handling:
- Estimands define the target of estimation (what we want to estimate)
- Missing data methods enable estimation when not all data are observed
- The missing data approach must be appropriate for the chosen estimand
"""

    def create_hypothetical_estimand(
        self,
        base_estimand: Estimand,
        hypothetical_scenario: str
    ) -> Estimand:
        """
        Create hypothetical strategy estimand from base estimand.

        Args:
            base_estimand: Base estimand to modify
            hypothetical_scenario: Description of hypothetical scenario

        Returns:
            New estimand with hypothetical strategy
        """
        # Clone base estimand
        hypothetical = Estimand(
            estimand_name=f"{base_estimand.estimand_name} - Hypothetical Strategy",
            estimand_type="Supplementary",
            treatment=base_estimand.treatment,
            population=base_estimand.population,
            variable=base_estimand.variable,
            population_summary=base_estimand.population_summary,
            clinical_question=f"What would the effect be under the hypothetical scenario: {hypothetical_scenario}?",
            clinical_relevance=f"Isolates biological effect by removing impact of intercurrent events"
        )

        # Modify intercurrent event strategies to hypothetical
        for ie in base_estimand.intercurrent_events:
            modified_ie = IntercurrentEvent(
                event_type=ie.event_type,
                description=ie.description,
                strategy=IntercurrentEventStrategy.HYPOTHETICAL,
                occurs_when=ie.occurs_when,
                data_handling=f"Hypothetical: {hypothetical_scenario}",
                analysis_method="Use data observed before intercurrent event; impute missing data under hypothetical scenario"
            )
            hypothetical.intercurrent_events.append(modified_ie)

        return hypothetical


# Singleton instance
_estimand_service: Optional[EstimandService] = None


def get_estimand_service() -> EstimandService:
    """
    Get estimand service instance.

    Returns:
        EstimandService instance
    """
    global _estimand_service

    if _estimand_service is None:
        _estimand_service = EstimandService()

    return _estimand_service
