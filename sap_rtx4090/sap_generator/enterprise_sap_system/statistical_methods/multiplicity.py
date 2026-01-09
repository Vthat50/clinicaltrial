"""
Multiplicity Adjustment Methods
================================

Methods for controlling Type I error rate in the presence of multiple testing.

Required by ICH E9 for Phase 3 trials with:
- Multiple primary endpoints
- Multiple dose comparisons
- Multiple populations
- Multiple timepoints
- Interim analyses

Methods:
- Bonferroni correction
- Holm procedure
- Hochberg procedure
- Fixed-sequence (hierarchical) testing
- Fallback procedures
- Graphical approaches (Bretz et al.)
- Gatekeeping procedures
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MultiplicityMethod(Enum):
    """Multiple testing adjustment methods"""
    BONFERRONI = "Bonferroni"
    HOLM = "Holm"
    HOCHBERG = "Hochberg"
    FIXED_SEQUENCE = "Fixed-Sequence (Hierarchical)"
    FALLBACK = "Fallback Procedure"
    GRAPHICAL = "Graphical Approach"
    GATEKEEPING = "Gatekeeping"
    NONE = "No Adjustment"


class MultiplicitySource(Enum):
    """Sources of multiplicity"""
    MULTIPLE_ENDPOINTS = "Multiple Primary Endpoints"
    MULTIPLE_COMPARISONS = "Multiple Dose/Treatment Comparisons"
    MULTIPLE_POPULATIONS = "Multiple Analysis Populations"
    MULTIPLE_TIMEPOINTS = "Multiple Analysis Timepoints"
    INTERIM_ANALYSES = "Interim Analyses"
    SUBGROUPS = "Subgroup Analyses"


@dataclass
class Hypothesis:
    """
    Individual hypothesis in multiple testing framework.

    Each hypothesis represents a comparison to be tested.
    """
    hypothesis_id: str               # e.g., "H1", "H2"
    description: str                 # e.g., "PFS: Experimental vs Control"
    endpoint: str
    comparison: str                  # e.g., "Exp vs Ctrl"

    # Testing
    alpha_allocated: float = 0.025   # One-sided alpha level allocated
    test_statistic: str = ""         # e.g., "Log-rank", "CMH"

    # Priority
    priority_order: int = 1          # For hierarchical testing
    clinical_importance: str = ""    # Rationale for priority

    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Hypothesis IDs that must be rejected first


@dataclass
class BonferroniSpec:
    """
    Bonferroni correction specification.

    Most conservative, suitable when hypotheses are independent.
    """
    family_wise_alpha: float = 0.05  # Overall FWER
    num_hypotheses: int = 2

    # Weighting
    equal_weights: bool = True
    weights: List[float] = field(default_factory=list)  # Custom weights (must sum to 1)

    def calculate_adjusted_alpha(self, hypothesis_index: int) -> float:
        """Calculate adjusted alpha for a hypothesis"""
        if self.equal_weights:
            return self.family_wise_alpha / self.num_hypotheses
        else:
            return self.family_wise_alpha * self.weights[hypothesis_index]


@dataclass
class HolmSpec:
    """
    Holm step-down procedure specification.

    More powerful than Bonferroni, controls FWER.
    """
    family_wise_alpha: float = 0.05
    hypotheses: List[Hypothesis] = field(default_factory=list)

    def generate_testing_procedure(self) -> str:
        """Generate step-by-step testing procedure"""
        text = f"""
**Holm Step-Down Procedure:**

1. Order p-values from smallest to largest: p(1) ≤ p(2) ≤ ... ≤ p({len(self.hypotheses)})

2. Compare p-values to adjusted significance levels:
"""
        for i in range(len(self.hypotheses)):
            k = i + 1
            alpha_k = self.family_wise_alpha / (len(self.hypotheses) - i)
            text += f"   - p({k}) vs {alpha_k:.4f}\n"

        text += f"""
3. Reject H(i) if p(i) ≤ {self.family_wise_alpha}/{len(self.hypotheses) - i + 1}

4. Stop at first non-significant p-value; do not reject that hypothesis or any with larger p-values

**Properties:**
- Controls family-wise error rate at {self.family_wise_alpha}
- More powerful than Bonferroni
- Uniformly more powerful than Bonferroni for any configuration of true/false hypotheses
"""
        return text


@dataclass
class FixedSequenceSpec:
    """
    Fixed-sequence (hierarchical) testing specification.

    Tests hypotheses in pre-specified order, full alpha to each until failure.
    """
    family_wise_alpha: float = 0.05
    hypotheses: List[Hypothesis] = field(default_factory=list)  # Ordered by priority

    def generate_testing_procedure(self) -> str:
        """Generate testing procedure"""
        text = f"""
**Fixed-Sequence (Hierarchical) Testing Procedure:**

Hypotheses will be tested in the following pre-specified order at the full α = {self.family_wise_alpha} level:

"""
        for i, hyp in enumerate(self.hypotheses, 1):
            text += f"{i}. **{hyp.hypothesis_id}: {hyp.description}**\n"
            text += f"   - Full α = {self.family_wise_alpha} allocated\n"
            if hyp.clinical_importance:
                text += f"   - Rationale: {hyp.clinical_importance}\n"
            text += "\n"

        text += f"""
**Testing Rules:**
1. Test H1 at α = {self.family_wise_alpha}
2. If H1 is rejected, proceed to test H2 at α = {self.family_wise_alpha}
3. If H2 is rejected, proceed to test H3 at α = {self.family_wise_alpha}
4. Continue until a hypothesis is not rejected or all hypotheses are tested
5. Once a hypothesis fails to be rejected, stop testing and do not reject any subsequent hypotheses

**Properties:**
- Controls family-wise error rate at {self.family_wise_alpha}
- Maximum power for highest priority hypothesis
- Requires strong prior conviction about priority ordering
- No multiplicity adjustment needed (each test uses full α)
"""
        return text


@dataclass
class GraphicalApproachSpec:
    """
    Graphical approach for multiple testing (Bretz et al.).

    Flexible method using weighted Bonferroni tests with alpha propagation.
    """
    family_wise_alpha: float = 0.05
    hypotheses: List[Hypothesis] = field(default_factory=list)

    # Graph structure
    initial_weights: List[float] = field(default_factory=list)  # Initial alpha allocation
    transition_weights: List[List[float]] = field(default_factory=list)  # Propagation matrix

    def generate_testing_procedure(self) -> str:
        """Generate graphical testing procedure"""
        text = f"""
**Graphical Approach for Multiple Testing:**

The graphical approach provides a flexible framework for multiple testing using weighted Bonferroni tests with alpha propagation.

**Initial Alpha Allocation:**
"""
        for i, (hyp, weight) in enumerate(zip(self.hypotheses, self.initial_weights)):
            text += f"- {hyp.hypothesis_id}: α × {weight} = {self.family_wise_alpha * weight:.4f}\n"

        text += """
**Alpha Propagation:**
When a hypothesis is rejected, its alpha is redistributed to remaining hypotheses according to pre-specified transition weights.

**Testing Procedure:**
1. Test each hypothesis Hi at level αi (initial alpha allocation)
2. If Hi is rejected, propagate its alpha to other hypotheses:
   - αj := αj + αi × gij (where gij is transition weight from Hi to Hj)
3. Retest remaining hypotheses with updated alpha levels
4. Repeat until no more hypotheses can be rejected

**Properties:**
- Controls family-wise error rate at α
- Flexible: can accommodate complex clinical trial objectives
- Transparent: visual representation of testing strategy
- Optimal: can achieve high power for prioritized hypotheses

**Reference:**
Bretz F, Maurer W, Brannath W, Posch M. A graphical approach to sequentially rejective multiple test procedures. Stat Med. 2009;28(4):586-604.
"""
        return text


class MultiplicityService:
    """
    Service for multiplicity adjustment specifications.

    Provides methods for controlling Type I error in complex testing scenarios.
    """

    def __init__(self):
        """Initialize multiplicity service"""
        pass

    def generate_multiplicity_section(
        self,
        multiplicity_sources: List[MultiplicitySource],
        method: MultiplicityMethod,
        spec: any  # BonferroniSpec, HolmSpec, FixedSequenceSpec, etc.
    ) -> str:
        """
        Generate complete multiplicity control section for SAP.

        Args:
            multiplicity_sources: Sources of multiplicity
            method: Chosen multiplicity method
            spec: Method-specific specification

        Returns:
            Formatted SAP text
        """
        text = """
## Control of Type I Error Rate

### Sources of Multiplicity

This trial has multiple comparisons that could inflate the Type I error rate:

"""
        for source in multiplicity_sources:
            text += f"- {source.value}\n"

        text += f"""
### Overall Significance Level

The overall (family-wise) Type I error rate will be controlled at α = {spec.family_wise_alpha} (two-sided).

### Multiplicity Adjustment Method

**Method:** {method.value}

"""

        # Add method-specific text
        if isinstance(spec, FixedSequenceSpec):
            text += spec.generate_testing_procedure()
        elif isinstance(spec, HolmSpec):
            text += spec.generate_testing_procedure()
        elif isinstance(spec, GraphicalApproachSpec):
            text += spec.generate_testing_procedure()

        text += """
### Regulatory Compliance

This multiplicity adjustment strategy is consistent with:
- **ICH E9:** Statistical Principles for Clinical Trials (Section 5.5 - Adjustment for Multiplicity)
- **FDA Guidance:** Multiple Endpoints in Clinical Trials (2017)
- **EMA Guideline:** Multiplicity Issues in Clinical Trials (2016)

**Key Principles:**
1. Family-wise error rate is controlled at pre-specified level
2. Testing hierarchy or adjustment method is pre-specified in SAP
3. All endpoints/comparisons included in multiplicity adjustment are clearly defined
4. Decision rules for claiming success are unambiguous
"""

        return text.strip()

    def create_fixed_sequence_for_endpoints(
        self,
        primary_endpoint: str,
        secondary_endpoints: List[str],
        alpha: float = 0.05
    ) -> FixedSequenceSpec:
        """
        Create fixed-sequence specification for multiple endpoints.

        Args:
            primary_endpoint: Primary endpoint name
            secondary_endpoints: List of secondary endpoint names
            alpha: Family-wise error rate

        Returns:
            FixedSequenceSpec
        """
        hypotheses = []

        # Primary endpoint
        hypotheses.append(Hypothesis(
            hypothesis_id="H1",
            description=f"{primary_endpoint}: Experimental vs Control",
            endpoint=primary_endpoint,
            comparison="Experimental vs Control",
            priority_order=1,
            clinical_importance="Primary efficacy endpoint"
        ))

        # Secondary endpoints
        for i, endpoint in enumerate(secondary_endpoints, 2):
            hypotheses.append(Hypothesis(
                hypothesis_id=f"H{i}",
                description=f"{endpoint}: Experimental vs Control",
                endpoint=endpoint,
                comparison="Experimental vs Control",
                priority_order=i,
                clinical_importance=f"Key secondary endpoint #{i-1}"
            ))

        return FixedSequenceSpec(
            family_wise_alpha=alpha,
            hypotheses=hypotheses
        )

    def create_graphical_approach_os_pfs(
        self,
        alpha: float = 0.025  # One-sided
    ) -> GraphicalApproachSpec:
        """
        Create graphical approach for OS and PFS co-primary endpoints.

        Common scenario: OS and PFS both considered clinically important.

        Args:
            alpha: One-sided alpha level

        Returns:
            GraphicalApproachSpec
        """
        hypotheses = [
            Hypothesis(
                hypothesis_id="H_OS",
                description="Overall Survival: Experimental vs Control",
                endpoint="Overall Survival",
                comparison="Experimental vs Control"
            ),
            Hypothesis(
                hypothesis_id="H_PFS",
                description="Progression-Free Survival: Experimental vs Control",
                endpoint="Progression-Free Survival",
                comparison="Experimental vs Control"
            )
        ]

        # Equal initial allocation
        initial_weights = [0.5, 0.5]

        # Full propagation: rejected hypothesis gives all alpha to other
        transition_weights = [
            [0.0, 1.0],  # H_OS rejected -> all alpha to H_PFS
            [1.0, 0.0]   # H_PFS rejected -> all alpha to H_OS
        ]

        return GraphicalApproachSpec(
            family_wise_alpha=alpha,
            hypotheses=hypotheses,
            initial_weights=initial_weights,
            transition_weights=transition_weights
        )

    def generate_decision_rules_text(self, spec: FixedSequenceSpec) -> str:
        """
        Generate clear decision rules for trial success.

        Args:
            spec: Testing specification

        Returns:
            Decision rules text
        """
        text = """
### Decision Rules for Trial Success

**Primary Success Criterion:**
"""
        primary_hyp = spec.hypotheses[0]
        text += f"The trial will be considered successful if {primary_hyp.hypothesis_id} ({primary_hyp.description}) is rejected at α = {spec.family_wise_alpha}.\n\n"

        if len(spec.hypotheses) > 1:
            text += "**Secondary Success Criteria:**\n"
            for hyp in spec.hypotheses[1:]:
                text += f"- {hyp.hypothesis_id} ({hyp.description}) can only be claimed if all preceding hypotheses in the hierarchy have been rejected.\n"

        text += """
**Interpretation:**
- Rejection of a hypothesis means statistically significant evidence of treatment benefit
- Failure to reject means insufficient evidence (NOT evidence of no effect)
- Type I error rate is controlled at the pre-specified level across all tests
"""
        return text


# Singleton instance
_multiplicity_service: Optional[MultiplicityService] = None


def get_multiplicity_service() -> MultiplicityService:
    """
    Get multiplicity service instance.

    Returns:
        MultiplicityService instance
    """
    global _multiplicity_service

    if _multiplicity_service is None:
        _multiplicity_service = MultiplicityService()

    return _multiplicity_service
