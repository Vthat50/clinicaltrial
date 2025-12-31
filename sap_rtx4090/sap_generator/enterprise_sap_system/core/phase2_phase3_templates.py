#!/usr/bin/env python3
"""
Phase 2 and Phase 3 Trial Templates
====================================

Comprehensive templates for:
1. Single-arm Phase 2 (Simon's, Fleming, exact binomial)
2. Randomized Phase 2 (selection, pick-the-winner)
3. Phase 3 confirmatory (superiority, non-inferiority, equivalence)
4. Seamless Phase 2/3 (adaptive)
5. Group sequential designs (interim analyses)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math


# =============================================================================
# PHASE 2 SINGLE-ARM DESIGNS
# =============================================================================

class Phase2Design(Enum):
    """Phase 2 single-arm designs"""
    SIMON_OPTIMAL = "simon_optimal"
    SIMON_MINIMAX = "simon_minimax"
    FLEMING_SINGLE = "fleming_single"
    EXACT_BINOMIAL = "exact_binomial"


PHASE2_SINGLE_ARM_TEMPLATES = {
    Phase2Design.SIMON_OPTIMAL: {
        "name": "Simon's Two-Stage Optimal Design",
        "description": "Minimizes expected sample size under null hypothesis",
        "statistical_methods": """
### Simon's Two-Stage Optimal Design

**Design Philosophy:** Minimize expected sample size under H₀ while controlling Type I and II errors.

**Hypotheses:**
- H₀: p ≤ p₀ (uninteresting response rate)
- H₁: p ≥ p₁ (target response rate)

**Design Parameters:**
| Parameter | Description |
|-----------|-------------|
| p₀ | Null hypothesis response rate (e.g., 0.20) |
| p₁ | Alternative hypothesis response rate (e.g., 0.40) |
| α | Type I error (typically 0.05 or 0.10) |
| β | Type II error (1 - power, typically 0.10 or 0.20) |

**Stage 1:**
- Enroll n₁ patients
- If ≤r₁ responses: Stop for futility (reject H₁)
- If >r₁ responses: Proceed to Stage 2

**Stage 2:**
- Enroll additional n₂ patients (total N = n₁ + n₂)
- If ≤r responses in N patients: Fail to reject H₀
- If >r responses: Reject H₀, declare activity

**Example (p₀=0.20, p₁=0.40, α=0.05, β=0.20):**
| Design | n₁ | r₁ | N | r | EN(p₀) | PET(p₀) |
|--------|----|----|---|---|--------|---------|
| Optimal | 13 | 3 | 43 | 12 | 23.3 | 0.65 |
| Minimax | 15 | 3 | 37 | 10 | 26.8 | 0.60 |

**Operating Characteristics:**
- EN(p₀): Expected sample size under null
- PET(p₀): Probability of early termination under null

**Analysis:**
```
Stage 1: Observe X₁ responses in n₁ patients
  If X₁ ≤ r₁: Stop, conclude treatment not active

Stage 2: Observe X₂ responses in n₂ patients
  Total X = X₁ + X₂ in N patients
  If X ≤ r: Conclude treatment not active
  If X > r: Conclude treatment is active (reject H₀)
```

**Reporting:**
- Response rate with exact 95% CI (Clopper-Pearson)
- Stage at which study stopped
- Intent-to-treat and evaluable population analyses
""",
        "sample_size_table": """
### Common Simon's Two-Stage Designs

**One-sided α = 0.05, Power = 80%:**
| p₀ | p₁ | n₁ | r₁ | N | r | Design |
|----|----|----|----|----|---|--------|
| 0.05 | 0.20 | 9 | 0 | 24 | 2 | Optimal |
| 0.10 | 0.25 | 18 | 2 | 43 | 7 | Optimal |
| 0.10 | 0.30 | 10 | 1 | 29 | 5 | Optimal |
| 0.15 | 0.30 | 22 | 3 | 55 | 11 | Optimal |
| 0.20 | 0.35 | 32 | 6 | 72 | 18 | Optimal |
| 0.20 | 0.40 | 13 | 3 | 43 | 12 | Optimal |
| 0.25 | 0.45 | 15 | 4 | 46 | 15 | Optimal |
| 0.30 | 0.50 | 15 | 5 | 46 | 18 | Optimal |

**One-sided α = 0.10, Power = 90%:**
| p₀ | p₁ | n₁ | r₁ | N | r | Design |
|----|----|----|----|----|---|--------|
| 0.05 | 0.20 | 10 | 0 | 29 | 3 | Optimal |
| 0.10 | 0.30 | 12 | 1 | 35 | 6 | Optimal |
| 0.20 | 0.40 | 15 | 3 | 46 | 13 | Optimal |
| 0.30 | 0.50 | 19 | 6 | 54 | 21 | Optimal |
"""
    },

    Phase2Design.FLEMING_SINGLE: {
        "name": "Fleming's Single-Stage Design",
        "description": "Single-stage exact binomial test",
        "statistical_methods": """
### Fleming's Single-Stage Design

**Design:** Fixed sample size with exact binomial test

**Hypotheses:**
- H₀: p ≤ p₀
- H₁: p > p₀

**Decision Rule:**
- Reject H₀ if X ≥ r (critical value)
- Where X = number of responses in n patients

**Sample Size Formula:**
```
n = (Zα + Zβ)² × p(1-p) / (p₁ - p₀)²

Where:
  p = (p₀ + p₁) / 2
  Zα = Z-value for Type I error
  Zβ = Z-value for Type II error
```

**Example Designs:**
| p₀ | p₁ | α | Power | n | r |
|----|----|----|-------|---|---|
| 0.20 | 0.40 | 0.05 | 0.80 | 39 | 12 |
| 0.20 | 0.40 | 0.05 | 0.90 | 53 | 16 |
| 0.30 | 0.50 | 0.05 | 0.80 | 49 | 20 |

**Advantages:**
- Simple, single stage
- No interim futility look

**Disadvantages:**
- Cannot stop early for futility
- Larger expected sample size than Simon's
"""
    }
}


# =============================================================================
# PHASE 2 RANDOMIZED DESIGNS
# =============================================================================

PHASE2_RANDOMIZED_TEMPLATES = {
    "selection_design": {
        "name": "Randomized Phase 2 Selection Design",
        "description": "Select best arm to advance to Phase 3",
        "statistical_methods": """
### Randomized Phase 2 Selection Design

**Objective:** Select the most promising treatment arm(s) to advance to Phase 3

**Design:**
- Randomize patients to K treatment arms (± control)
- Compare response rates or early efficacy signals
- Select winner(s) based on ranking or thresholds

**No Formal Hypothesis Testing:**
- Goal is selection, not confirmation
- No multiplicity adjustment required
- P-values are descriptive only

**Selection Rules:**

**1. Pick-the-Winner:**
- Select arm with highest observed response rate
- Requires minimum sample size per arm (typically ≥20)

**2. Select if Exceeds Threshold:**
- Arm proceeds if ORR > threshold (e.g., 30%)
- Multiple arms may advance

**3. Ranking with Probability:**
- Calculate P(arm i is best)
- Select if P(best) > threshold (e.g., 0.80)

**Sample Size Considerations:**
```
Per arm: n = 20-40 patients typically
Total: K × n patients

Probability of correct selection (PCS):
- Depends on true difference between arms
- PCS > 0.80 usually desired
```

**Analysis:**
- Response rate per arm with 95% CI
- Ranking of arms by point estimate
- Probability statements (if Bayesian)

**Example Output:**
| Arm | N | Responses | ORR (95% CI) | Rank |
|-----|---|-----------|--------------|------|
| A | 35 | 14 | 40% (24-58%) | 1 |
| B | 33 | 10 | 30% (16-49%) | 2 |
| C | 34 | 8 | 24% (11-41%) | 3 |
| Control | 35 | 5 | 14% (5-30%) | 4 |

**Decision:** Arm A selected for Phase 3
"""
    },

    "randomized_phase2": {
        "name": "Randomized Phase 2 with Control",
        "description": "Randomized comparison with concurrent control",
        "statistical_methods": """
### Randomized Phase 2 Trial

**Design:** Randomized comparison of experimental vs control

**Typical Randomization:** 2:1 or 1:1 (experimental:control)

**Primary Endpoint Options:**
- Overall Response Rate (ORR)
- Progression-Free Survival (PFS)
- Clinical Benefit Rate (CBR)

**Statistical Methods:**

**For Binary Endpoints (ORR):**
```
Test: Chi-square or Fisher's exact test
Effect: Risk difference or odds ratio with 95% CI
```

**For Time-to-Event (PFS):**
```
Test: Stratified log-rank test
Effect: Hazard ratio with 95% CI
Estimation: Kaplan-Meier curves
```

**Sample Size (Randomized Phase 2):**
| Design | Control ORR | Experimental ORR | α | Power | N |
|--------|-------------|------------------|---|-------|---|
| 2:1 | 20% | 40% | 0.10 (1-sided) | 80% | 75 |
| 1:1 | 20% | 40% | 0.10 (1-sided) | 80% | 82 |
| 2:1 | 30% | 50% | 0.10 (1-sided) | 80% | 84 |

**Note:** Randomized Phase 2 often uses:
- One-sided α = 0.10-0.20 (less stringent than Phase 3)
- Power = 80% (not 90%)
- Not designed for regulatory approval alone

**Go/No-Go Criteria:**
```
GO: HR ≤ 0.67 (or ORR difference ≥ 15%)
CONSIDER: 0.67 < HR ≤ 0.80
NO-GO: HR > 0.80
```
"""
    }
}


# =============================================================================
# PHASE 3 CONFIRMATORY DESIGNS
# =============================================================================

PHASE3_TEMPLATES = {
    "superiority": {
        "name": "Phase 3 Superiority Trial",
        "description": "Demonstrate experimental is superior to control",
        "statistical_methods": """
### Phase 3 Superiority Trial

**Objective:** Demonstrate experimental treatment is superior to control

**Hypotheses:**
- H₀: θ_E = θ_C (no difference)
- H₁: θ_E ≠ θ_C (two-sided) or θ_E > θ_C (one-sided)

Where θ = treatment effect (HR for TTE, ORR for binary)

**Primary Endpoint Analysis:**

**For OS/PFS (Time-to-Event):**
```
Test: Stratified log-rank test
Effect: Hazard ratio with 95% CI (Cox model)

Superiority demonstrated if:
  Upper bound of 95% CI for HR < 1.0 (two-sided)
  OR p-value < 0.05 (two-sided)
```

**For ORR (Binary):**
```
Test: Stratified CMH test
Effect: Risk difference with 95% CI

Superiority demonstrated if:
  Lower bound of 95% CI for RD > 0
  OR p-value < 0.05 (two-sided)
```

**Sample Size for Superiority:**

**Time-to-Event (OS/PFS):**
```
Events = 4 × (Zα/2 + Zβ)² / (log(HR))²

Example: HR = 0.75, α = 0.05 (two-sided), Power = 90%
  Events = 4 × (1.96 + 1.28)² / (log(0.75))²
  Events = 4 × 10.50 / 0.083
  Events ≈ 508 events
```

**Binary (ORR):**
```
n per arm = 2 × (Zα/2 + Zβ)² × p̄(1-p̄) / (p₁ - p₀)²

Example: p₀ = 0.30, p₁ = 0.45, α = 0.05, Power = 90%
  n per arm ≈ 180
```

**Stratification Factors:**
- Geographic region
- Prior therapy (0-1 vs ≥2 lines)
- Performance status (ECOG 0-1 vs 2)
- Biomarker status (if applicable)
"""
    },

    "non_inferiority": {
        "name": "Phase 3 Non-Inferiority Trial",
        "description": "Demonstrate experimental is not worse than control by more than margin",
        "statistical_methods": """
### Phase 3 Non-Inferiority Trial

**Objective:** Demonstrate experimental is not clinically worse than control

**Hypotheses (for HR where lower is better):**
- H₀: HR ≥ M (experimental inferior by margin M or more)
- H₁: HR < M (experimental not inferior)

**Non-Inferiority Margin (M):**
```
Regulatory requirement: Preserve ≥50% of control effect

Example:
  Historical control vs placebo: HR = 0.60
  Preserved effect: (1 - 0.60) × 0.50 = 0.20
  Non-inferiority margin: M = 1/(1-0.20) = 1.25

  Or using M = sqrt(HR_historical) = sqrt(0.60) = 0.77
  Upper margin = 1/0.77 = 1.30
```

**Decision Rule:**
```
Non-inferiority demonstrated if:
  Upper bound of 95% CI for HR < M

Example with M = 1.30:
  HR = 1.05 (95% CI: 0.85-1.25) → Non-inferior ✓
  HR = 1.10 (95% CI: 0.90-1.35) → Not demonstrated ✗
```

**Sample Size:**
```
Events = 4 × (Zα + Zβ)² / (log(HR₁) - log(M))²

Where HR₁ = expected true HR under H₁

Example: M = 1.30, HR₁ = 1.00, α = 0.025 (one-sided), Power = 90%
  Events ≈ 350-400
```

**Additional Considerations:**
- Assay sensitivity: Must show control would beat placebo
- ITT and PP populations: Both should show non-inferiority
- Switching to superiority: Can test superiority if NI demonstrated

**Typical Margins by Endpoint:**
| Endpoint | Typical Margin |
|----------|----------------|
| OS | HR ≤ 1.20-1.30 |
| PFS | HR ≤ 1.25-1.35 |
| ORR | Difference ≥ -10% to -15% |
"""
    },

    "group_sequential": {
        "name": "Group Sequential Design (Interim Analyses)",
        "description": "Multiple interim analyses with alpha spending",
        "statistical_methods": """
### Group Sequential Design with Interim Analyses

**Purpose:** Allow early stopping for efficacy or futility

**Alpha Spending Functions:**

**1. O'Brien-Fleming (Conservative):**
```
α*(t) = 2 × (1 - Φ(Zα/2 / √t))

Spending at each look:
  Look 1 (50%): α₁ = 0.003
  Look 2 (75%): α₂ = 0.019
  Final (100%): α₃ = 0.043

Total: 0.05
```

**2. Pocock (Less Conservative):**
```
Uses same boundary at each look

Spending at each look (3 looks):
  Each look: α = 0.022
```

**3. Lan-DeMets (Flexible):**
```
Allows unequal spacing
Most commonly used in practice
```

**Stopping Boundaries:**

| Information Fraction | O'Brien-Fleming | Pocock |
|----------------------|-----------------|--------|
| 0.25 | 4.33 | 2.36 |
| 0.50 | 2.96 | 2.36 |
| 0.75 | 2.36 | 2.36 |
| 1.00 | 2.01 | 2.36 |

**Futility Boundaries (Non-Binding):**
```
Stop for futility if:
  Conditional power < 10-20%
  OR P(success | current data) < 5%
```

**Sample Size Inflation:**
```
Group sequential designs require ~2-5% more events
than fixed sample design to maintain power

Inflation factor:
  O'Brien-Fleming: ~1.02
  Pocock: ~1.05
```

**DSMB Review:**
- Unblinded interim analyses by independent DSMB
- Review efficacy, futility, and safety
- Recommendations: continue, stop for efficacy, stop for futility

**Software:** East, ADDPLAN, gsDesign (R), rpact (R)
"""
    }
}


# =============================================================================
# SEAMLESS PHASE 2/3 DESIGNS
# =============================================================================

SEAMLESS_TEMPLATES = {
    "adaptive_seamless": {
        "name": "Adaptive Seamless Phase 2/3 Design",
        "description": "Single trial combining Phase 2 and Phase 3 with adaptation",
        "statistical_methods": """
### Adaptive Seamless Phase 2/3 Design

**Concept:** Combine Phase 2 learning and Phase 3 confirmation in one trial

**Key Features:**
- Phase 2: Dose/regimen selection
- Interim: Adapt based on Phase 2 data
- Phase 3: Confirmatory analysis with selected arm(s)

**Types:**

**1. Operationally Seamless:**
- Same protocol, continuous enrollment
- Unblinded interim for arm selection
- Phase 2 patients may be included in Phase 3 analysis

**2. Inferentially Seamless:**
- Combined analysis of Phase 2 + Phase 3 data
- Pre-specified combination test
- Type I error controlled across trial

**Statistical Framework:**

**Combination Tests:**
```
p_combined = C(p₁, p₂)

Options:
  Fisher: p = p₁ × p₂ (compare to χ²₄)
  Inverse normal: Z = w₁Z₁ + w₂Z₂ / √(w₁² + w₂²)

Where w₁, w₂ are pre-specified weights
```

**Arm Selection at Interim:**
1. Compare arms to control using futility boundary
2. Drop futile arms
3. Select best arm(s) for Phase 3

**Alpha Allocation:**
```
Total α = 0.05

Example allocation:
  α₁ = 0.001 (interim efficacy)
  α₂ = 0.049 (final analysis)
```

**Sample Size:**
```
Phase 2: n₁ per arm (typically 30-50)
Phase 3: n₂ for selected arm(s)

Total: n₁ + n₂ (may reuse Phase 2 patients)
```

**Advantages:**
- Faster development timeline
- Efficient use of patients
- Reduced total sample size

**Challenges:**
- Complex statistical analysis
- Regulatory discussions needed
- Operational complexity

**Example Design:**
```
Phase 2 (n=150):
  - Arm A: 50 patients
  - Arm B: 50 patients
  - Control: 50 patients

Interim Analysis:
  - Drop Arm B (futility)
  - Continue Arm A vs Control

Phase 3 (additional n=300):
  - Arm A: 150 patients
  - Control: 150 patients

Final Analysis:
  - Combine Phase 2 + Phase 3 (total N=400)
  - Use inverse normal combination test
```
"""
    },

    "biomarker_adaptive": {
        "name": "Biomarker-Adaptive Enrichment Design",
        "description": "Adapt population based on biomarker results",
        "statistical_methods": """
### Biomarker-Adaptive Enrichment Design

**Concept:** Start with all-comer population, potentially enrich based on biomarker

**Design:**

**Stage 1:** Enroll all patients (biomarker+ and biomarker-)
**Interim:** Analyze efficacy by biomarker subgroup
**Stage 2:**
  - If treatment works in all: Continue all-comer
  - If treatment works only in biomarker+: Enrich to biomarker+ only

**Statistical Framework:**

**Hypotheses:**
- H₀⁺: No effect in biomarker+ patients
- H₀⁻: No effect in biomarker- patients
- H₀: No effect in overall population

**Alpha Allocation:**
```
Total α = 0.025 (one-sided)

Strategy A (prioritize overall):
  α_overall = 0.02
  α_biomarker+ = 0.005

Strategy B (split equally):
  α_overall = 0.0125
  α_biomarker+ = 0.0125
```

**Decision Rules at Interim:**
```
If p_overall < α_interim:
  Stop for efficacy in all patients

If p_biomarker+ < α_interim AND p_biomarker- > futility:
  Enrich to biomarker+ only

Otherwise:
  Continue as all-comer
```

**Final Analysis:**
- Closed testing procedure
- Test overall first, then biomarker+ if overall fails
- Control FWER at α = 0.025

**Sample Size:**
```
Stage 1: n₁ = 200 (100 biomarker+, 100 biomarker-)
Stage 2 (if enriched): n₂ = 150 (biomarker+ only)
Stage 2 (if all-comer): n₂ = 300 (150 each subgroup)
```

**Software:** FACTS, ART (R), custom simulations
"""
    }
}


# =============================================================================
# SAMPLE SIZE CALCULATORS
# =============================================================================

def simon_two_stage(p0: float, p1: float, alpha: float = 0.05,
                    beta: float = 0.20, design: str = "optimal") -> Dict:
    """
    Calculate Simon's two-stage design parameters

    Args:
        p0: Null response rate
        p1: Alternative response rate
        alpha: Type I error
        beta: Type II error (1 - power)
        design: "optimal" or "minimax"

    Returns:
        Dictionary with design parameters
    """
    # Pre-calculated common designs (approximate)
    designs = {
        (0.05, 0.20, 0.05, 0.20): {"n1": 9, "r1": 0, "n": 24, "r": 2},
        (0.10, 0.30, 0.05, 0.20): {"n1": 10, "r1": 1, "n": 29, "r": 5},
        (0.20, 0.40, 0.05, 0.20): {"n1": 13, "r1": 3, "n": 43, "r": 12},
        (0.30, 0.50, 0.05, 0.20): {"n1": 15, "r1": 5, "n": 46, "r": 18},
    }

    key = (p0, p1, alpha, beta)
    if key in designs:
        result = designs[key].copy()
        result["p0"] = p0
        result["p1"] = p1
        result["alpha"] = alpha
        result["power"] = 1 - beta
        return result

    # Return placeholder for other combinations
    return {
        "p0": p0,
        "p1": p1,
        "alpha": alpha,
        "power": 1 - beta,
        "n1": "Calculate using software",
        "r1": "Calculate using software",
        "n": "Calculate using software",
        "r": "Calculate using software",
        "note": "Use clinfun::ph2simon() in R or online calculator"
    }


def events_logrank(hr: float, alpha: float = 0.05, power: float = 0.90,
                   two_sided: bool = True) -> int:
    """
    Calculate number of events for log-rank test

    Args:
        hr: Target hazard ratio
        alpha: Type I error
        power: Statistical power
        two_sided: Two-sided test

    Returns:
        Number of events required
    """
    from scipy import stats

    if two_sided:
        z_alpha = stats.norm.ppf(1 - alpha/2)
    else:
        z_alpha = stats.norm.ppf(1 - alpha)

    z_beta = stats.norm.ppf(power)

    # Schoenfeld formula
    events = 4 * ((z_alpha + z_beta) ** 2) / (math.log(hr) ** 2)

    return int(math.ceil(events))


# =============================================================================
# PHASE 2/3 GENERATOR CLASS
# =============================================================================

class Phase23Generator:
    """
    Generate Phase 2/3 specific SAP content

    Usage:
        generator = Phase23Generator()

        # Single-arm Phase 2
        methods = generator.get_simon_design(p0=0.20, p1=0.40)

        # Randomized Phase 2
        methods = generator.get_randomized_phase2_methods()

        # Phase 3 superiority
        methods = generator.get_phase3_superiority(endpoint_type="tte")

        # Group sequential
        methods = generator.get_group_sequential_methods(n_looks=3)
    """

    def get_simon_design(self, p0: float, p1: float,
                         alpha: float = 0.05, power: float = 0.80) -> str:
        """Get Simon's two-stage design section"""
        design = simon_two_stage(p0, p1, alpha, 1-power)

        return f"""
### Simon's Two-Stage Design

**Design Parameters:**
- H₀: Response rate ≤ {p0*100:.0f}%
- H₁: Response rate ≥ {p1*100:.0f}%
- One-sided α = {alpha}
- Power = {power*100:.0f}%

**Stage 1:**
- Enroll n₁ = {design.get('n1', 'TBD')} patients
- If ≤{design.get('r1', 'TBD')} responses: Stop for futility
- If >{design.get('r1', 'TBD')} responses: Proceed to Stage 2

**Stage 2:**
- Enroll additional patients to total N = {design.get('n', 'TBD')}
- If ≤{design.get('r', 'TBD')} responses in N patients: Conclude not active
- If >{design.get('r', 'TBD')} responses: Conclude treatment is active

**Analysis:**
- Response rate with exact 95% Clopper-Pearson CI
- Report stage at which study concluded
"""

    def get_phase3_superiority(self, endpoint_type: str = "tte",
                               hr: float = 0.75, alpha: float = 0.05,
                               power: float = 0.90) -> str:
        """Get Phase 3 superiority methods"""
        if endpoint_type == "tte":
            events = events_logrank(hr, alpha, power)
            return f"""
### Phase 3 Superiority Analysis (Time-to-Event)

**Primary Hypothesis:**
- H₀: HR = 1.0 (no difference)
- H₁: HR ≠ 1.0 (two-sided) at α = {alpha}

**Target Effect:**
- Hazard ratio: {hr}
- Power: {power*100:.0f}%
- Required events: ~{events}

**Primary Analysis:**
- Stratified log-rank test
- Hazard ratio with 95% CI from Cox model
- Kaplan-Meier curves for survival estimation

**Superiority Criterion:**
- Reject H₀ if upper bound of 95% CI for HR < 1.0
- Equivalently, if two-sided p-value < {alpha}

**Stratification Factors:**
- [To be specified based on protocol]
"""
        else:
            return PHASE3_TEMPLATES["superiority"]["statistical_methods"]

    def get_group_sequential_methods(self, n_looks: int = 3,
                                     spending: str = "obf") -> str:
        """Get group sequential design methods"""
        return PHASE3_TEMPLATES["group_sequential"]["statistical_methods"]

    def get_seamless_phase23_methods(self) -> str:
        """Get seamless Phase 2/3 methods"""
        return SEAMLESS_TEMPLATES["adaptive_seamless"]["statistical_methods"]


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    print("="*70)
    print("PHASE 2 / PHASE 3 TEMPLATES")
    print("="*70)

    print("\n### Single-Arm Phase 2 Designs:")
    for design in Phase2Design:
        template = PHASE2_SINGLE_ARM_TEMPLATES.get(design)
        if template:
            print(f"  - {template['name']}")

    print("\n### Randomized Phase 2 Designs:")
    for name, template in PHASE2_RANDOMIZED_TEMPLATES.items():
        print(f"  - {template['name']}")

    print("\n### Phase 3 Designs:")
    for name, template in PHASE3_TEMPLATES.items():
        print(f"  - {template['name']}")

    print("\n### Seamless Phase 2/3 Designs:")
    for name, template in SEAMLESS_TEMPLATES.items():
        print(f"  - {template['name']}")

    print("\n" + "="*70)
    print("EXAMPLE: Simon's Two-Stage Design")
    print("="*70)

    generator = Phase23Generator()
    print(generator.get_simon_design(p0=0.20, p1=0.40))

    print("\n" + "="*70)
    print("EXAMPLE: Events Calculation")
    print("="*70)
    print(f"HR=0.75, α=0.05 (two-sided), Power=90%: {events_logrank(0.75)} events")
    print(f"HR=0.80, α=0.05 (two-sided), Power=90%: {events_logrank(0.80)} events")
    print(f"HR=0.70, α=0.05 (two-sided), Power=90%: {events_logrank(0.70)} events")
