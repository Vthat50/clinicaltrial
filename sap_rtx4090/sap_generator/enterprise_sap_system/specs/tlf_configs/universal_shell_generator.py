"""
Universal TLF Shell Generator

This module reads study configuration and automatically generates the correct
number of table shells by applying:

1. Study Period Stratification - Multiply safety/lab tables by study periods
2. Population × Assessment Matrix - Expand efficacy tables by population and assessment type
3. Region-Aware Variables - Include/exclude demographics based on regulatory region
4. PK/Immunogenicity Templates - Add domain-specific tables based on study type

Usage:
    from universal_shell_generator import UniversalShellGenerator

    generator = UniversalShellGenerator(
        study_config="path/to/study_config.yaml",
        output_dir="path/to/output"
    )

    shells = generator.generate()
    generator.export_markdown()
    generator.export_yaml()
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from copy import deepcopy


@dataclass
class TableShell:
    """Represents a single TLF shell specification."""
    number: str
    title: str
    population: str
    orientation: str
    source_dataset: str
    filter_condition: str
    columns: List[Dict]
    stub_rows: List[Dict]
    footnotes: List[Dict]
    programming_notes: List[str] = field(default_factory=list)
    period: Optional[str] = None
    assessment_type: Optional[str] = None
    category: str = "General"
    priority: int = 1


@dataclass
class StudyConfig:
    """Parsed study configuration."""
    study_id: str
    study_type: str
    indication: str
    phase: str
    regions: List[str]
    treatment_arms: List[Dict]
    stratification_factors: List[str]
    populations: List[Dict]
    endpoints: Dict
    period_config: str
    require_period_stratification: bool = False
    require_population_assessment_matrix: bool = True
    include_pk_immunogenicity: bool = False


class UniversalShellGenerator:
    """
    Universal generator for TLF shells that automatically applies:
    - Period stratification
    - Population × Assessment matrix expansion
    - Region-aware variable inclusion
    - PK/Immunogenicity templates
    """

    def __init__(self, study_config_path: str, core_config_dir: Optional[str] = None):
        """
        Initialize generator with study configuration.

        Args:
            study_config_path: Path to study-specific YAML config
            core_config_dir: Path to core config directory (defaults to ./core/)
        """
        self.study_config_path = Path(study_config_path)
        self.core_config_dir = Path(core_config_dir) if core_config_dir else \
            self.study_config_path.parent.parent / "core"

        # Load configurations
        self.study_config = self._load_study_config()
        self.period_config = self._load_period_config()
        self.population_matrix = self._load_population_matrix()
        self.region_variables = self._load_region_variables()
        self.pk_immuno_templates = self._load_pk_immuno_templates()

        # Generated shells storage
        self.shells: List[TableShell] = []
        self.shell_count_by_category: Dict[str, int] = {}

    def _load_yaml(self, path: Path) -> Dict:
        """Load YAML file safely."""
        if not path.exists():
            print(f"Warning: Config file not found: {path}")
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def _load_study_config(self) -> StudyConfig:
        """Load and parse study configuration."""
        config = self._load_yaml(self.study_config_path)
        study = config.get('study_config', {})

        return StudyConfig(
            study_id=study.get('study_id', 'UNKNOWN'),
            study_type=study.get('study_type', 'continuous'),
            indication=study.get('indication', ''),
            phase=study.get('phase', 'III'),
            regions=study.get('regions', ['global']),
            treatment_arms=study.get('treatment_arms', []),
            stratification_factors=study.get('stratification_factors', []),
            populations=study.get('populations', []),
            endpoints=config.get('endpoints', {}),
            period_config=study.get('period_config', 'single_period'),
            require_period_stratification=study.get('require_period_stratification', False),
            include_pk_immunogenicity=study.get('include_pk_immunogenicity', False)
        )

    def _load_period_config(self) -> Dict:
        """Load study period stratification configuration."""
        path = self.core_config_dir / "study_period_stratification.yaml"
        return self._load_yaml(path)

    def _load_population_matrix(self) -> Dict:
        """Load population × assessment matrix configuration."""
        path = self.core_config_dir / "population_assessment_matrix.yaml"
        return self._load_yaml(path)

    def _load_region_variables(self) -> Dict:
        """Load region-aware variables configuration."""
        path = self.core_config_dir / "region_aware_variables.yaml"
        return self._load_yaml(path)

    def _load_pk_immuno_templates(self) -> Dict:
        """Load PK/Immunogenicity templates."""
        path = self.core_config_dir / "pk_immunogenicity_templates.yaml"
        return self._load_yaml(path)

    # =========================================================================
    # PERIOD STRATIFICATION
    # =========================================================================

    def get_study_periods(self) -> List[Dict]:
        """
        Get list of study periods based on configuration.

        Returns:
            List of period dictionaries with id, name, abbreviation, etc.
        """
        period_configs = self.period_config.get('period_configurations', {})
        config_name = self.study_config.period_config

        if config_name not in period_configs:
            # Default to single period
            return [{'id': 'whole_study', 'name': 'Whole Study Period',
                     'abbreviation': 'Overall', 'is_primary': True}]

        return period_configs[config_name].get('periods', [])

    def should_stratify_by_period(self, table_type: str) -> bool:
        """
        Determine if a table type should be stratified by study period.

        Args:
            table_type: Type of table (e.g., "TEAE Overview", "Demographics")

        Returns:
            True if table should have period-specific versions
        """
        if not self.study_config.require_period_stratification:
            return False

        period_configs = self.period_config.get('period_configurations', {})
        config_name = self.study_config.period_config

        if config_name not in period_configs:
            return False

        config = period_configs[config_name]

        # Check if this table is in the stratified list
        stratified_tables = config.get('period_stratified_tables', [])
        whole_study_only = config.get('whole_study_only_tables', [])

        # Normalize for comparison
        table_type_lower = table_type.lower()

        if any(t.lower() in table_type_lower for t in whole_study_only):
            return False

        if any(t.lower() in table_type_lower for t in stratified_tables):
            return True

        # Default: check category
        if config.get('safety_tables_by_period') and 'teae' in table_type_lower:
            return True
        if config.get('laboratory_tables_by_period') and 'lab' in table_type_lower:
            return True
        if config.get('exposure_tables_by_period') and 'exposure' in table_type_lower:
            return True

        return False

    def expand_by_period(self, base_shell: TableShell) -> List[TableShell]:
        """
        Expand a single shell into period-specific versions.

        Args:
            base_shell: Original table shell

        Returns:
            List of shells (one per period, or just the original if no stratification)
        """
        if not self.should_stratify_by_period(base_shell.title):
            return [base_shell]

        periods = self.get_study_periods()
        naming = self.period_config.get('period_table_naming', {})
        title_templates = naming.get('title_templates', {})
        numbering_suffix = naming.get('numbering_suffix', {})

        expanded = []
        for period in periods:
            shell = deepcopy(base_shell)
            period_id = period.get('id', 'whole_study')

            # Update title
            template = title_templates.get(period_id, "{base_title}")
            shell.title = template.format(base_title=base_shell.title)

            # Update number
            suffix = numbering_suffix.get(period_id, '')
            shell.number = f"{base_shell.number}{suffix}"

            # Update filter condition
            filter_conditions = self.period_config.get('period_filter_conditions', {})
            period_filters = filter_conditions.get(period_id, {})

            dataset_key = f"ad{base_shell.source_dataset.lower()[:2]}_filter"
            if dataset_key in period_filters:
                period_filter = period_filters[dataset_key]
                if shell.filter_condition:
                    shell.filter_condition = f"({shell.filter_condition}) and ({period_filter})"
                else:
                    shell.filter_condition = period_filter

            shell.period = period.get('name', period_id)
            expanded.append(shell)

        return expanded

    # =========================================================================
    # POPULATION × ASSESSMENT MATRIX
    # =========================================================================

    def get_efficacy_populations(self) -> List[Dict]:
        """Get populations for efficacy analyses."""
        defaults = self.population_matrix.get('study_type_defaults', {})
        study_defaults = defaults.get(self.study_config.study_type, {})

        pop_ids = study_defaults.get('efficacy_populations', ['itt'])
        populations = self.population_matrix.get('populations', {})

        return [populations.get(pid, {'full_name': pid.upper()})
                for pid in pop_ids if pid in populations]

    def get_efficacy_assessments(self) -> List[Dict]:
        """Get assessment types for efficacy analyses."""
        defaults = self.population_matrix.get('study_type_defaults', {})
        study_defaults = defaults.get(self.study_config.study_type, {})

        assess_ids = study_defaults.get('efficacy_assessments', ['irc'])
        assessments = self.population_matrix.get('assessment_types', {})

        return [assessments.get(aid, {'full_name': aid.upper()})
                for aid in assess_ids if aid in assessments]

    def expand_by_population_assessment(self, base_shell: TableShell,
                                         table_type: str = "primary_efficacy") -> List[TableShell]:
        """
        Expand efficacy shell by population and assessment type.

        Args:
            base_shell: Original table shell
            table_type: Type for determining expansion rules

        Returns:
            List of expanded shells
        """
        # Get expansion rules
        matrix_rules = self.population_matrix.get('matrix_rules', {})
        rules = matrix_rules.get(table_type, {})

        pop_expansion = rules.get('population_expansion', {})
        assess_expansion = rules.get('assessment_expansion', {})

        # If no expansion needed
        if not pop_expansion and not assess_expansion:
            return [base_shell]

        populations = self.population_matrix.get('populations', {})
        assessments = self.population_matrix.get('assessment_types', {})
        naming = self.population_matrix.get('naming_conventions', {})

        # Determine populations to include
        pop_ids = []
        if pop_expansion:
            if 'primary' in pop_expansion:
                pop_ids.append(pop_expansion['primary'])
            if 'sensitivity' in pop_expansion:
                pop_ids.extend(pop_expansion.get('sensitivity', []))

        if not pop_ids:
            pop_ids = ['itt']

        # Determine assessments to include
        assess_ids = []
        if assess_expansion:
            if 'primary' in assess_expansion:
                assess_ids.append(assess_expansion['primary'])
            if 'sensitivity' in assess_expansion:
                assess_ids.extend(assess_expansion.get('sensitivity', []))

        if not assess_ids:
            assess_ids = [None]  # No assessment type (e.g., safety)

        # Generate cross-product
        expanded = []
        numbering = naming.get('numbering_convention', {})

        for pop_id in pop_ids:
            pop_info = populations.get(pop_id, {})
            pop_name = pop_info.get('full_name', pop_id.upper())
            pop_suffix = numbering.get('population_suffix', {}).get(pop_id, '')

            for assess_id in assess_ids:
                shell = deepcopy(base_shell)

                if assess_id:
                    assess_info = assessments.get(assess_id, {})
                    assess_name = assess_info.get('full_name', assess_id.upper())
                    assess_suffix = numbering.get('assessment_suffix', {}).get(assess_id, '')

                    # Update title with both
                    shell.title = f"{base_shell.title} ({pop_name}, {assess_name})"
                    shell.number = f"{base_shell.number}{pop_suffix}{assess_suffix}"
                    shell.assessment_type = assess_name
                else:
                    # Just population
                    shell.title = f"{base_shell.title} ({pop_name})"
                    shell.number = f"{base_shell.number}{pop_suffix}"

                shell.population = pop_name

                # Update filter condition
                filter_templates = self.population_matrix.get('filter_templates', {})
                pop_filters = filter_templates.get(pop_id, {})

                # Find appropriate filter key
                dataset = base_shell.source_dataset.lower()
                for key in [dataset, f"{dataset[:2]}sl", 'adsl']:
                    if key in pop_filters:
                        pop_filter = pop_filters[key]
                        if shell.filter_condition:
                            shell.filter_condition = f"({shell.filter_condition}) and ({pop_filter})"
                        else:
                            shell.filter_condition = pop_filter
                        break

                # Add assessment filter if applicable
                if assess_id:
                    assess_filters = filter_templates.get(assess_id, {})
                    for key in [dataset]:
                        if key in assess_filters:
                            assess_filter = assess_filters[key]
                            shell.filter_condition = f"({shell.filter_condition}) and ({assess_filter})"
                            break

                expanded.append(shell)

        return expanded

    # =========================================================================
    # REGION-AWARE DEMOGRAPHICS
    # =========================================================================

    def get_demographic_variables(self) -> List[Dict]:
        """
        Get list of demographic variables based on study regions.

        Returns:
            List of variable definitions to include
        """
        variables = []

        # Always include core demographics
        core = self.region_variables.get('core_demographics', {})
        for var_id, var_info in core.items():
            var_info['id'] = var_id
            variables.append(var_info)

        # Add region-specific variables
        region_specific = self.region_variables.get('region_specific_variables', {})
        inclusion_rules = self.region_variables.get('inclusion_rules', {})

        study_regions = self.study_config.regions

        for var_id, var_info in region_specific.items():
            # Check if should include based on region
            include_regions = inclusion_rules.get('include_if_region', {}).get(var_id, [])

            should_include = False
            for region in study_regions:
                if region.lower() in [r.lower() for r in include_regions]:
                    should_include = True
                    break
                if 'global' in include_regions and region.lower() != 'japan':
                    should_include = True
                    break

            if should_include:
                var_info['id'] = var_id
                variables.append(var_info)

        # Add indication-specific variables
        indication_rules = inclusion_rules.get('include_if_indication', {})
        indication = self.study_config.indication.lower()

        for var_id, indications in indication_rules.items():
            if any(ind.lower() in indication for ind in indications):
                if var_id in region_specific:
                    var_info = region_specific[var_id].copy()
                    var_info['id'] = var_id
                    if var_info not in variables:
                        variables.append(var_info)

        # Add ECOG PS for oncology
        indication_specific = self.region_variables.get('indication_specific', {})
        ecog = indication_specific.get('ecog_ps', {})
        if 'cancer' in indication or 'oncology' in self.study_config.study_type:
            ecog['id'] = 'ecog_ps'
            variables.append(ecog)

        return variables

    # =========================================================================
    # PK/IMMUNOGENICITY
    # =========================================================================

    def get_pk_immunogenicity_tables(self) -> List[TableShell]:
        """
        Get PK and immunogenicity table shells based on study type.

        Returns:
            List of TableShell objects for PK/immunogenicity
        """
        if not self.study_config.include_pk_immunogenicity:
            return []

        shells = []
        requirements = self.pk_immuno_templates.get('study_type_requirements', {})
        study_reqs = requirements.get(self.study_config.study_type, {})

        # PK tables
        pk_required = study_reqs.get('pk_tables_required', [])
        pk_templates = self.pk_immuno_templates.get('pk_tables', {})

        for table_id in pk_required:
            if table_id in pk_templates:
                template = pk_templates[table_id]
                shell = self._template_to_shell(template, category="PK")
                shells.append(shell)

        # Immunogenicity tables
        immuno_required = study_reqs.get('immunogenicity_tables_required', [])
        immuno_templates = self.pk_immuno_templates.get('immunogenicity_tables', {})

        for table_id in immuno_required:
            if table_id in immuno_templates:
                template = immuno_templates[table_id]
                shell = self._template_to_shell(template, category="Immunogenicity")
                shells.append(shell)

        return shells

    def _template_to_shell(self, template: Dict, category: str = "General") -> TableShell:
        """Convert template dictionary to TableShell object."""
        return TableShell(
            number=template.get('number_template', '14.4.x.x'),
            title=template.get('title_template', 'Untitled'),
            population=template.get('population', 'Safety'),
            orientation=template.get('orientation', 'PORTRAIT'),
            source_dataset=template.get('source_dataset', 'ADSL'),
            filter_condition=template.get('filter_condition', ''),
            columns=template.get('columns', []),
            stub_rows=template.get('stub_rows', []),
            footnotes=template.get('footnotes', []),
            programming_notes=template.get('programming_notes', []),
            category=category
        )

    # =========================================================================
    # MAIN GENERATION METHODS
    # =========================================================================

    def generate(self, base_shells: List[TableShell] = None) -> List[TableShell]:
        """
        Generate complete set of table shells with all expansions.

        Args:
            base_shells: Optional list of base shells to expand

        Returns:
            List of all generated TableShell objects
        """
        self.shells = []
        self.shell_count_by_category = {}

        if base_shells:
            for shell in base_shells:
                # Determine expansion type based on category
                if shell.category.lower() in ['efficacy', 'primary', 'secondary']:
                    expanded = self.expand_by_population_assessment(shell, 'primary_efficacy')
                elif shell.category.lower() in ['safety', 'teae', 'aesi']:
                    expanded = self.expand_by_period(shell)
                elif shell.category.lower() in ['laboratory', 'lab']:
                    expanded = self.expand_by_period(shell)
                elif shell.category.lower() in ['exposure']:
                    expanded = self.expand_by_period(shell)
                else:
                    expanded = [shell]

                self.shells.extend(expanded)

        # Add PK/Immunogenicity shells
        pk_immuno_shells = self.get_pk_immunogenicity_tables()
        self.shells.extend(pk_immuno_shells)

        # Count by category
        for shell in self.shells:
            cat = shell.category
            self.shell_count_by_category[cat] = self.shell_count_by_category.get(cat, 0) + 1

        return self.shells

    def get_summary(self) -> Dict:
        """
        Get summary of generated shells.

        Returns:
            Dictionary with counts and configuration info
        """
        periods = self.get_study_periods()
        demographics = self.get_demographic_variables()

        return {
            'study_id': self.study_config.study_id,
            'study_type': self.study_config.study_type,
            'total_shells': len(self.shells),
            'shells_by_category': self.shell_count_by_category,
            'period_stratification': {
                'enabled': self.study_config.require_period_stratification,
                'config': self.study_config.period_config,
                'periods': [p.get('name') for p in periods]
            },
            'population_assessment_matrix': {
                'populations': [p.get('full_name') for p in self.get_efficacy_populations()],
                'assessments': [a.get('full_name') for a in self.get_efficacy_assessments()]
            },
            'demographics': {
                'variables': [v.get('id', v.get('label')) for v in demographics]
            },
            'pk_immunogenicity': {
                'enabled': self.study_config.include_pk_immunogenicity
            }
        }

    def export_markdown(self, output_path: str) -> str:
        """
        Export shells to markdown format.

        Args:
            output_path: Path for output file

        Returns:
            Path to created file
        """
        lines = [
            f"# TLF Shell Specifications",
            f"",
            f"**Study:** {self.study_config.study_id}",
            f"**Type:** {self.study_config.study_type}",
            f"**Generated:** Universal Shell Generator",
            f"",
            f"## Summary",
            f"",
            f"**Total Tables:** {len(self.shells)}",
            f""
        ]

        # Summary by category
        lines.append("| Category | Count |")
        lines.append("|----------|-------|")
        for cat, count in sorted(self.shell_count_by_category.items()):
            lines.append(f"| {cat} | {count} |")
        lines.append("")

        # Group shells by category
        shells_by_cat: Dict[str, List[TableShell]] = {}
        for shell in self.shells:
            cat = shell.category
            if cat not in shells_by_cat:
                shells_by_cat[cat] = []
            shells_by_cat[cat].append(shell)

        # Output each category
        for cat, shells in sorted(shells_by_cat.items()):
            lines.append(f"---")
            lines.append(f"")
            lines.append(f"## {cat}")
            lines.append(f"")

            for shell in shells:
                lines.append(f"### Table {shell.number}: {shell.title}")
                lines.append(f"")
                lines.append(f"**Population:** {shell.population}")
                if shell.period:
                    lines.append(f"**Period:** {shell.period}")
                if shell.assessment_type:
                    lines.append(f"**Assessment:** {shell.assessment_type}")
                lines.append(f"**Source Dataset:** {shell.source_dataset}")
                if shell.filter_condition:
                    lines.append(f"**Filter:** `{shell.filter_condition}`")
                lines.append(f"")

                # Columns
                if shell.columns:
                    lines.append("#### Columns")
                    lines.append("")
                    lines.append("| Header | Width | Align |")
                    lines.append("|--------|-------|-------|")
                    for col in shell.columns:
                        header = col.get('header', '').replace('\n', ' / ')
                        lines.append(f"| {header} | {col.get('width', '-')} | {col.get('alignment', 'L')} |")
                    lines.append("")

                # Stub rows preview
                if shell.stub_rows:
                    lines.append("#### Row Structure")
                    lines.append("")
                    for row in shell.stub_rows[:10]:  # First 10 rows
                        indent = "  " * row.get('level', 0)
                        label = row.get('label', '')
                        if label:
                            if row.get('bold'):
                                lines.append(f"- **{indent}{label}**")
                            else:
                                lines.append(f"- {indent}{label}")
                    if len(shell.stub_rows) > 10:
                        lines.append(f"- ... ({len(shell.stub_rows) - 10} more rows)")
                    lines.append("")

                lines.append("---")
                lines.append("")

        content = "\n".join(lines)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_path


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def calculate_table_multiplier(study_config: Dict) -> Dict[str, int]:
    """
    Calculate how many tables will be generated from base shells.

    Args:
        study_config: Study configuration dictionary

    Returns:
        Dictionary mapping table types to multipliers
    """
    multipliers = {
        'demographics': 1,
        'disposition': 1,
        'efficacy_primary': 1,
        'efficacy_secondary': 1,
        'safety_overview': 1,
        'aesi': 1,
        'laboratory': 1,
        'exposure': 1,
    }

    # Period stratification multiplier
    period_config = study_config.get('period_config', 'single_period')
    if period_config == 'induction_maintenance':
        period_mult = 4  # Whole, Induction, Maintenance, Follow-up
    elif period_config == 'perioperative':
        period_mult = 4  # Whole, Neoadjuvant, Surgery, Adjuvant
    else:
        period_mult = 1

    # Apply period multiplier to safety/lab
    for key in ['safety_overview', 'aesi', 'laboratory', 'exposure']:
        multipliers[key] *= period_mult

    # Population × Assessment multiplier for efficacy
    populations = len(study_config.get('efficacy_populations', ['itt']))
    assessments = len(study_config.get('efficacy_assessments', ['irc']))

    efficacy_mult = populations * assessments

    for key in ['efficacy_primary', 'efficacy_secondary']:
        multipliers[key] *= efficacy_mult

    return multipliers


def estimate_total_tables(base_count: int, multipliers: Dict[str, int]) -> int:
    """
    Estimate total number of tables after expansion.

    Args:
        base_count: Number of base table shells
        multipliers: Multipliers by category

    Returns:
        Estimated total table count
    """
    # Simple average multiplier for estimation
    avg_multiplier = sum(multipliers.values()) / len(multipliers)
    return int(base_count * avg_multiplier)


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        # Default example
        config_path = "keynote_example/study_config.yaml"

    if not os.path.exists(config_path):
        print(f"Config not found: {config_path}")
        print("Usage: python universal_shell_generator.py <study_config.yaml>")
        sys.exit(1)

    generator = UniversalShellGenerator(config_path)

    # Print summary
    summary = generator.get_summary()
    print(f"\nStudy: {summary['study_id']}")
    print(f"Type: {summary['study_type']}")
    print(f"\nPeriod Stratification:")
    print(f"  Enabled: {summary['period_stratification']['enabled']}")
    print(f"  Config: {summary['period_stratification']['config']}")
    print(f"  Periods: {summary['period_stratification']['periods']}")
    print(f"\nPopulations: {summary['population_assessment_matrix']['populations']}")
    print(f"Assessments: {summary['population_assessment_matrix']['assessments']}")
    print(f"\nDemographic Variables: {summary['demographics']['variables']}")
    print(f"\nPK/Immunogenicity: {summary['pk_immunogenicity']['enabled']}")
