#!/usr/bin/env python3
"""
Operational Rules Integration
=============================

Integration module that wires together the three-tier operational rules system
with the SAP generation pipeline.

This module provides:
1. Study type detection from extracted protocol facts
2. Automatic loading of appropriate defaults
3. Merging of protocol-specific extractions with defaults
4. Generation of complete operational sections for SAP

Usage:
    from core.operational_integration import OperationalRulesIntegration

    # In pipeline
    integrator = OperationalRulesIntegration(extracted_facts)
    populations_section = integrator.generate_populations_section()
    methods_section = integrator.generate_statistical_methods_section()
    appendix = integrator.generate_operational_appendix()
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

from .operational_extraction_schema import (
    OperationalSpecifications,
    VisitSchedule,
    VisitWindow,
    PopulationSpecifications,
    PKPopulationCriteria,
    PPExclusionCriteria,
    DualPopulationRequirement,
    PeriodDefinitions,
    StudyPeriod,
    ControlledDiseaseCriteria,
    ModelCovariates,
    ICEFramework,
    InterimAnalysisSpecification,
    detect_study_type,
    create_default_operational_specs,
    validate_operational_specs
)

from .operational_appendix_generator import (
    OperationalAppendixGenerator,
    OperationalConfigLoader,
    generate_operational_appendix
)

from .ice_sensitivity_generator import (
    ICEGenerator,
    SensitivityAnalysisGenerator,
    ICE_TEMPLATES,
    SENSITIVITY_ANALYSIS_REGISTRY
)

logger = logging.getLogger(__name__)


# =============================================================================
# STUDY TYPE DETECTION
# =============================================================================

def detect_study_type_from_facts(facts: Dict[str, Any]) -> str:
    """
    Detect study type from extracted protocol facts.

    Args:
        facts: Dictionary of extracted protocol facts

    Returns:
        Study type string
    """
    # Extract relevant fields
    hypothesis = facts.get('hypothesis_framework', '').lower()
    drug_class = facts.get('drug_class', '').lower()
    treatment_setting = facts.get('treatment_setting', '').lower()
    has_pk = bool(facts.get('pk_endpoints')) or 'pk' in str(facts.get('secondary_endpoints', [])).lower()

    # Biosimilar detection
    if 'equivalence' in hypothesis or 'biosimilar' in drug_class:
        return 'biosimilar'

    # Maintenance study
    if 'maintenance' in treatment_setting:
        return 'maintenance'

    # Adjuvant study
    if 'adjuvant' in treatment_setting:
        return 'adjuvant'

    # Neoadjuvant study
    if 'neoadjuvant' in treatment_setting:
        return 'neoadjuvant'

    # Immuno-oncology
    io_keywords = ['pembrolizumab', 'nivolumab', 'atezolizumab', 'durvalumab',
                   'ipilimumab', 'checkpoint', 'pd-1', 'pd-l1', 'ctla-4',
                   'immunotherapy', 'immuno-oncology']
    drug_name = facts.get('drug_name', '').lower()
    if any(kw in drug_class or kw in drug_name for kw in io_keywords):
        return 'immuno_oncology'

    # Targeted therapy
    targeted_keywords = ['tki', 'kinase', 'egfr', 'alk', 'her2', 'braf',
                         'mek', 'cdk', 'parp', 'adc', 'antibody-drug']
    if any(kw in drug_class or kw in drug_name for kw in targeted_keywords):
        return 'targeted_therapy'

    # Single-arm
    if facts.get('is_single_arm', False) or facts.get('num_arms', 2) == 1:
        return 'single_arm'

    # Default
    return 'general_oncology'


# =============================================================================
# OPERATIONAL RULES INTEGRATION
# =============================================================================

class OperationalRulesIntegration:
    """
    Main integration class for operational rules in SAP generation.

    Combines:
    - Tier 1: Protocol-specific extractions
    - Tier 2: Industry standards (from operational_rules.yaml)
    - Tier 3: Study-type defaults (from study_type_defaults.yaml)
    """

    def __init__(
        self,
        extracted_facts: Dict[str, Any],
        tier1_specs: Optional[OperationalSpecifications] = None,
        config_dir: Optional[Path] = None
    ):
        """
        Initialize the integration.

        Args:
            extracted_facts: Dictionary of facts extracted from protocol
            tier1_specs: Optional pre-built Tier 1 specifications
            config_dir: Optional custom config directory
        """
        self.facts = extracted_facts

        # Detect study type
        self.study_type = detect_study_type_from_facts(extracted_facts)
        logger.info(f"Detected study type: {self.study_type}")

        # Load configurations
        self.config_loader = OperationalConfigLoader(config_dir)
        self.tier2 = self.config_loader.load_operational_rules()
        self.tier3 = self.config_loader.get_defaults_for_study_type(self.study_type)

        # Build or use provided Tier 1 specs
        if tier1_specs:
            self.tier1 = tier1_specs
        else:
            self.tier1 = self._build_tier1_from_facts()

        # Initialize generators
        self.appendix_generator = OperationalAppendixGenerator(
            tier1_specs=self.tier1,
            study_type=self.study_type,
            config_loader=self.config_loader
        )

        # Detect study characteristics
        self.crossover_permitted = self._detect_crossover()
        self.delayed_effect_expected = self.study_type == 'immuno_oncology'

        self.ice_generator = ICEGenerator(
            study_type=self.study_type,
            crossover_permitted=self.crossover_permitted,
            delayed_effect_expected=self.delayed_effect_expected
        )

        self.sensitivity_generator = SensitivityAnalysisGenerator(
            study_type=self.study_type,
            crossover_permitted=self.crossover_permitted,
            delayed_effect_expected=self.delayed_effect_expected
        )

    def _build_tier1_from_facts(self) -> OperationalSpecifications:
        """Build Tier 1 specifications from extracted facts."""
        specs = create_default_operational_specs()

        # Populate from facts
        specs.detected_study_type = self.study_type

        # Visit schedule (if extracted)
        if 'visit_schedule' in self.facts:
            specs.visit_schedule = self._parse_visit_schedule(self.facts['visit_schedule'])

        # Populations
        specs.populations = self._build_population_specs()

        # Covariates
        specs.covariates = self._build_covariate_specs()

        # Periods (for maintenance studies)
        if self.study_type == 'maintenance':
            specs.periods = self._build_period_definitions()

        # Interim analysis
        if self.facts.get('has_interim_analysis'):
            specs.interim_analysis = self._build_interim_specs()

        return specs

    def _parse_visit_schedule(self, schedule_data: Any) -> VisitSchedule:
        """Parse visit schedule from extracted data."""
        schedule = VisitSchedule()

        if isinstance(schedule_data, dict):
            for visit_name, visit_info in schedule_data.items():
                if isinstance(visit_info, dict):
                    window = VisitWindow(
                        visit_name=visit_name,
                        target_day=visit_info.get('target_day', 1),
                        window_minus=visit_info.get('window_minus', 3),
                        window_plus=visit_info.get('window_plus', 3)
                    )
                    schedule.visits.append(window)

        return schedule

    def _build_population_specs(self) -> PopulationSpecifications:
        """Build population specifications from facts."""
        pops = PopulationSpecifications()

        # ITT definition
        pops.itt_definition = self.facts.get(
            'itt_definition',
            'All randomized subjects'
        )

        # Safety definition
        pops.safety_definition = self.facts.get(
            'safety_definition',
            'All subjects who received at least one dose of study treatment'
        )

        # PK population (if applicable)
        if self.facts.get('has_pk_endpoints') or self.study_type == 'biosimilar':
            pops.pk_population = PKPopulationCriteria(
                included=True,
                definition=self.facts.get(
                    'pk_population_definition',
                    'Subjects with at least one evaluable PK sample'
                )
            )

        # Dual population requirement (biosimilars)
        if self.study_type == 'biosimilar':
            pops.dual_population = DualPopulationRequirement(
                required=True,
                primary_population="ITT",
                co_primary_population="PP",
                success_criterion="Equivalence must be demonstrated in BOTH populations",
                sap_text=self.tier3.get('population_requirements', {}).get('dual_population_text', '')
            )

        return pops

    def _build_covariate_specs(self) -> ModelCovariates:
        """Build model covariate specifications from facts."""
        covs = ModelCovariates()

        # Stratification factors
        covs.stratification_factors = self.facts.get('stratification_factors', [])
        covs.stratification_factor_levels = self.facts.get('stratification_factor_levels', {})

        # Primary analysis covariates
        covs.primary_analysis_covariates = ['Treatment group'] + covs.stratification_factors

        # Ensure both log-rank and Cox use stratification
        covs.stratification_in_logrank = True
        covs.stratification_in_cox = True

        return covs

    def _build_period_definitions(self) -> PeriodDefinitions:
        """Build period definitions for maintenance studies."""
        periods = PeriodDefinitions()

        # Induction period
        induction = StudyPeriod(
            name="Induction",
            start_criterion="First dose of study treatment",
            end_criterion="Completion of planned induction or disease progression"
        )
        periods.periods.append(induction)

        # Maintenance period
        maintenance = StudyPeriod(
            name="Maintenance",
            start_criterion="Controlled disease at end of induction",
            end_criterion="Disease progression or unacceptable toxicity"
        )
        periods.periods.append(maintenance)

        # Controlled disease definition
        periods.controlled_disease = ControlledDiseaseCriteria(
            definition=self.facts.get(
                'controlled_disease_definition',
                'CR, PR, or SD at end of induction assessment'
            ),
            qualifying_responses=['CR', 'PR', 'SD'],
            assessment_timing=self.facts.get('induction_end_assessment', 'End of induction')
        )

        return periods

    def _build_interim_specs(self) -> InterimAnalysisSpecification:
        """Build interim analysis specifications from facts."""
        interim = InterimAnalysisSpecification()

        interim.num_interim = self.facts.get('num_interim_analyses', 0)
        interim.alpha_spending_function = self.facts.get(
            'alpha_spending_function',
            'Lan-DeMets with O\'Brien-Fleming spending'
        )
        interim.futility_boundary = self.facts.get('futility_boundary', 'non-binding')

        # Calendar timeline
        if self.facts.get('interim_timing'):
            interim.one_year_report = self.facts.get('one_year_report', '')

        return interim

    def _detect_crossover(self) -> bool:
        """Detect if treatment crossover is permitted."""
        crossover_keywords = ['crossover', 'cross-over', 'switch', 'treatment switching']
        protocol_text = str(self.facts.get('protocol_text', '')).lower()
        return any(kw in protocol_text for kw in crossover_keywords)

    # =========================================================================
    # GENERATION METHODS
    # =========================================================================

    def generate_populations_section(self) -> str:
        """Generate complete populations section for SAP."""
        return self.appendix_generator.generate_populations_section()

    def generate_statistical_methods_section(self) -> str:
        """Generate statistical methods section with explicit covariates."""
        text = "## Statistical Methods\n\n"

        # Primary endpoint type
        primary_type = self.facts.get('primary_endpoint_type', 'PFS')
        primary_name = self.facts.get('primary_endpoint', 'Primary Endpoint')

        # Add model specification with explicit covariates
        text += "### Primary Analysis Model\n\n"

        if primary_type in ['PFS', 'OS', 'DFS']:
            text += self._generate_tte_methods()
        elif primary_type == 'ORR':
            text += self._generate_binary_methods()
        else:
            text += self._generate_generic_methods()

        # Add explicit covariates section
        text += self.appendix_generator.generate_covariates_section()

        # Add ICE section
        text += "\n"
        text += self.ice_generator.generate_estimand_section(
            primary_endpoint=primary_name,
            primary_endpoint_type=primary_type,
            population=self.facts.get('population', 'Adult patients with advanced cancer'),
            treatment=self.facts.get('treatment_description', 'Study treatment vs comparator'),
            summary_measure=self._get_summary_measure(primary_type)
        )

        return text

    def _generate_tte_methods(self) -> str:
        """Generate time-to-event methods section."""
        strat_factors = self.tier1.covariates.stratification_factors if self.tier1.covariates else []
        strat_text = ', '.join(strat_factors) if strat_factors else 'randomization stratification factors'

        text = f"""**Kaplan-Meier Method:**
Survival curves will be estimated using the Kaplan-Meier method. Median survival times with 95% confidence intervals will be calculated using the Brookmeyer-Crowley method.

**Stratified Log-Rank Test:**
Treatment comparison will be performed using the log-rank test stratified by {strat_text}.

**Hazard Ratio Estimation:**
Hazard ratio with 95% confidence interval will be estimated from a Cox proportional hazards model stratified by the same factors.

**Cox Model Specification:**
The Cox model will include:
- Treatment group (primary factor)
- Stratification factors: {strat_text}

**Note:** Both the stratified log-rank test AND the stratified Cox model will use the same stratification factors as used in randomization.

"""
        return text

    def _generate_binary_methods(self) -> str:
        """Generate binary endpoint methods section."""
        text = """**Response Rate Estimation:**
Objective response rate (ORR) will be calculated as the proportion of subjects achieving CR or PR.
95% confidence intervals will be calculated using the Clopper-Pearson exact method.

**Treatment Comparison:**
"""
        if self.study_type == 'biosimilar':
            text += """Risk difference with 95% confidence interval will be calculated.
Equivalence will be concluded if the 95% CI for the risk difference is contained within the pre-specified equivalence margin.

**Dual Population Requirement:**
Equivalence must be demonstrated in BOTH ITT and Per-Protocol populations.
"""
        else:
            text += """Cochran-Mantel-Haenszel test stratified by randomization factors.
Odds ratio with 95% confidence interval from stratified analysis.
"""
        return text

    def _generate_generic_methods(self) -> str:
        """Generate generic methods section."""
        return """**Analysis Method:**
Appropriate statistical methods will be applied based on the endpoint type.
Details provided in endpoint-specific sections below.
"""

    def _get_summary_measure(self, endpoint_type: str) -> str:
        """Get summary measure text for endpoint type."""
        measures = {
            'PFS': 'Hazard ratio with 95% confidence interval',
            'OS': 'Hazard ratio with 95% confidence interval',
            'DFS': 'Hazard ratio with 95% confidence interval',
            'ORR': 'Difference in proportions with 95% confidence interval',
            'DOR': 'Median duration with 95% confidence interval',
        }
        return measures.get(endpoint_type, 'Appropriate summary measure with confidence interval')

    def generate_sensitivity_analyses_section(self) -> str:
        """Generate complete sensitivity analyses section."""
        primary_type = self.facts.get('primary_endpoint_type', 'PFS')
        secondary_types = self.facts.get('secondary_endpoint_types', ['OS', 'ORR'])

        return self.sensitivity_generator.generate_complete_sensitivity_section(
            primary_endpoint_type=primary_type,
            secondary_endpoint_types=secondary_types
        )

    def generate_operational_appendix(self) -> str:
        """Generate complete operational rules appendix."""
        return self.appendix_generator.generate_complete_appendix()

    def generate_all_sections(self) -> Dict[str, str]:
        """
        Generate all operational sections for SAP.

        Returns:
            Dictionary with section names as keys and content as values
        """
        sections = {
            'populations': self.generate_populations_section(),
            'statistical_methods': self.generate_statistical_methods_section(),
            'sensitivity_analyses': self.generate_sensitivity_analyses_section(),
            'operational_appendix': self.generate_operational_appendix()
        }

        # Validate and warn about incomplete extractions
        warnings = validate_operational_specs(self.tier1)
        if warnings:
            logger.warning("Operational specifications validation warnings:")
            for w in warnings:
                logger.warning(f"  {w}")

        return sections


# =============================================================================
# CONVENIENCE FUNCTION FOR PIPELINE INTEGRATION
# =============================================================================

def integrate_operational_rules(
    extracted_facts: Dict[str, Any],
    config_dir: Optional[Path] = None
) -> Dict[str, str]:
    """
    Convenience function for pipeline integration.

    Args:
        extracted_facts: Dictionary of extracted protocol facts
        config_dir: Optional custom config directory

    Returns:
        Dictionary of generated SAP sections
    """
    integrator = OperationalRulesIntegration(
        extracted_facts=extracted_facts,
        config_dir=config_dir
    )
    return integrator.generate_all_sections()
